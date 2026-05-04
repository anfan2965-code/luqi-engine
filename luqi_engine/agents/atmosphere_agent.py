"""
氛围智能体 - 生成场景氛围描述 AtmosphereOutput
职责：环境描写、叙事旁白、舞台指示、情绪声明
支持两种模式：light / full
降级策略：模板引擎（Light: 场景名+情感词模板拼接；Full 降级为 Light）
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from luqi_engine.core.interfaces import IAgentRunner
from luqi_engine.core.types import (
    AtmosphereEnvironment,
    AtmosphereNarration,
    AtmosphereOutput,
    LLMRequest,
    LLMResponse,
    MoodDeclaration,
    SDKType,
    StageDirection,
)
from luqi_engine.core.constants import (
    LLMMessageRole,
    AtmosphereMode,
    _DEFAULT_SCENE_NAME,
    _DEFAULT_DOMINANT_EMOTION,
    _DEFAULT_EMOTION_INTENSITY,
    _DEFAULT_ATMOSPHERE_PRIORITY,
    _FALLBACK_STAGE_ACTION,
    _DEFAULT_PACING_HINT,
    _DEFAULT_SUGGESTED_POSITION,
    _DEFAULT_LENGTH_BUDGET,
    _SCENE_LABEL_PREFIX,
    _ANTHROPIC_PREFILL_ATMOSPHERE,
)
from luqi_engine.llm.prompt_builder import PromptBuilder
from luqi_engine.llm.response_parser import ResponseParser

logger = logging.getLogger(__name__)

_MODE_LIGHT = AtmosphereMode.LIGHT
_MODE_FULL = AtmosphereMode.FULL
_VALID_MODES = frozenset({_MODE_LIGHT, _MODE_FULL})
_DEFAULT_MODE = _MODE_LIGHT

_TEMPLATE_SCENE_EMOTION = "{scene_name}中弥漫着{emotion_word}的气息"
_TEMPLATE_VISUAL = "{scene_name}的景色映入眼帘"
_TEMPLATE_AUDITORY = "远处传来细微的声响"
_TEMPLATE_OLFACTORY = "空气中带着淡淡的气味"
_TEMPLATE_THERMAL = "温度适宜"
_TEMPLATE_SPATIAL = "空间开阔"

_EMOTION_WORD_MAP: Dict[str, str] = {
    "joy": "欢快",
    "anger": "紧张",
    "sorrow": "哀伤",
    "fear": "不安",
    "love": "温暖",
    "disgust": "压抑",
    "desire": "渴望",
    "neutral": "平和",
}


class AtmosphereAgent(IAgentRunner):
    """
    氛围智能体
    根据场景和情感上下文生成 AtmosphereOutput
    """

    def __init__(
        self,
        prompt_builder: Optional[PromptBuilder] = None,
        response_parser: Optional[ResponseParser] = None,
    ) -> None:
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._response_parser = response_parser or ResponseParser()

    async def run(
        self,
        context: Dict[str, Any],
        llm_bridge: Any,
        **kwargs: Any,
    ) -> AtmosphereOutput:
        """
        运行氛围智能体

        context 必需字段:
            - scene_name: str — 场景名称
        context 可选字段:
            - dominant_emotion: str — 主导情感
            - emotion_intensity: float — 情感强度
            - characters_present: List[str] — 在场角色
            - narrative_context: str — 叙事上下文
            - time_of_day: str — 时间段

        kwargs:
            - mode: str — 运行模式 (light / full)
        """
        mode = kwargs.get("mode", _DEFAULT_MODE)
        if mode not in _VALID_MODES:
            logger.warning(
                "AtmosphereAgent 收到无效模式 %r，回退到 %s", mode, _DEFAULT_MODE
            )
            mode = _DEFAULT_MODE

        context["atmosphere_mode"] = mode
        prompt_text = self._prompt_builder.build_atmosphere_prompt(context)
        sdk_type = llm_bridge.get_sdk_type()

        messages = self._build_messages(prompt_text, context, sdk_type)
        request = LLMRequest(
            sdk_type=sdk_type,
            messages=messages,
        )

        try:
            response: LLMResponse = await llm_bridge.chat(request)
            output = self._response_parser.parse_atmosphere_output(response.content)
            output.mode = mode
            return output
        except Exception as exc:
            logger.warning(
                "AtmosphereAgent LLM 调用失败，启用模板降级: %s", exc
            )
            return self._build_template_output(context, mode)

    def get_name(self) -> str:
        return "atmosphere"

    def get_output_type(self) -> str:
        return "AtmosphereOutput"

    @staticmethod
    def _build_messages(
        prompt_text: str,
        context: Dict[str, Any],
        sdk_type: SDKType,
    ) -> List[Dict[str, str]]:
        scene_name = context.get("scene_name", "")
        if sdk_type == SDKType.ANTHROPIC:
            return [
                {"role": LLMMessageRole.USER, "content": prompt_text},
                {"role": LLMMessageRole.ASSISTANT, "content": _ANTHROPIC_PREFILL_ATMOSPHERE},
                {"role": LLMMessageRole.USER, "content": f"{_SCENE_LABEL_PREFIX}{scene_name}"},
            ]
        return [
            {"role": LLMMessageRole.SYSTEM, "content": prompt_text},
            {"role": LLMMessageRole.USER, "content": f"{_SCENE_LABEL_PREFIX}{scene_name}"},
        ]

    @staticmethod
    def _build_template_output(
        context: Dict[str, Any], mode: str
    ) -> AtmosphereOutput:
        """
        模板引擎降级
        Light Mode: 场景名+情感词模板拼接
        Full Mode: 降级为 Light
        """
        scene_name = context.get("scene_name", _DEFAULT_SCENE_NAME)
        dominant_emotion = context.get("dominant_emotion", _DEFAULT_DOMINANT_EMOTION)
        emotion_intensity = context.get("emotion_intensity", _DEFAULT_EMOTION_INTENSITY)

        emotion_word = _EMOTION_WORD_MAP.get(
            dominant_emotion, _EMOTION_WORD_MAP["neutral"]
        )

        environment = AtmosphereEnvironment(
            visual=_TEMPLATE_VISUAL.format(scene_name=scene_name),
            auditory=_TEMPLATE_AUDITORY,
            olfactory=_TEMPLATE_OLFACTORY,
            thermal=_TEMPLATE_THERMAL,
            spatial=_TEMPLATE_SPATIAL,
        )

        narration = AtmosphereNarration(
            transition=_TEMPLATE_SCENE_EMOTION.format(
                scene_name=scene_name, emotion_word=emotion_word
            ),
            inner_voice=None,
            omniscient_note=None,
        )

        characters = context.get("characters_present", [])
        stage_directions = [
            StageDirection(
                character=char,
                action=_FALLBACK_STAGE_ACTION,
                detail="",
            )
            for char in characters
        ]

        mood = MoodDeclaration(
            dominant_emotion=dominant_emotion,
            intensity=emotion_intensity,
            color_palette=[],
            pacing_hint=_DEFAULT_PACING_HINT,
        )

        effective_mode = _MODE_LIGHT if mode == _MODE_FULL else mode

        return AtmosphereOutput(
            mode=effective_mode,
            environment=environment,
            narration=narration,
            stage_directions=stage_directions,
            mood_declaration=mood,
            suggested_position=_DEFAULT_SUGGESTED_POSITION,
            length_budget=_DEFAULT_LENGTH_BUDGET,
            priority=_DEFAULT_ATMOSPHERE_PRIORITY,
        )
