"""
对话智能体 - 将用户输入解析为 CanonicalIR（规范中间表示）
职责：意图识别、情感提取、动作解析、叙事信号检测
降级策略：LLM 不可用时返回基于规则的默认 CanonicalIR
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from luqi_engine.core.interfaces import IAgentRunner
from luqi_engine.core.types import (
    CanonicalIR,
    EmotionDelta,
    LLMRequest,
    LLMResponse,
    SDKType,
)
from luqi_engine.core.constants import (
    LLMMessageRole,
    ToneType,
    LengthHint,
    _ANTHROPIC_PREFILL_DIALOGUE,
)
from luqi_engine.llm.prompt_builder import PromptBuilder
from luqi_engine.llm.response_parser import ResponseParser

logger = logging.getLogger(__name__)

_FALLBACK_INTENT = "unknown"
_FALLBACK_CONFIDENCE = 0.0
_FALLBACK_TONE = ToneType.NEUTRAL
_FALLBACK_LENGTH_HINT = LengthHint.MEDIUM
_FALLBACK_SEVEN_TRIGGER = ""
_FALLBACK_ACTION = ""


class DialogueAgent(IAgentRunner):
    """
    对话智能体
    将用户输入和上下文信息通过 LLM 解析为 CanonicalIR
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
    ) -> CanonicalIR:
        """
        运行对话智能体

        context 必需字段:
            - user_message: str — 用户输入文本
        context 可选字段:
            - character_name: str — 角色名
            - personality: Dict[str, float] — OCEAN 性格
            - emotion_pad: Dict[str, float] — PAD 情感
            - memories: List[Dict] — 相关记忆
            - worldview_summary: str — 世界观摘要
            - narrative_rules: List[str] — 叙事规则
            - recent_exchanges: List[Dict] — 近期对话
        """
        sdk_type = llm_bridge.get_sdk_type()

        if sdk_type == SDKType.LOCAL_LLM:
            return await self._run_direct(context, llm_bridge)

        prompt_text = self._prompt_builder.build_dialogue_prompt(context)

        messages = self._build_messages(prompt_text, context, sdk_type)
        request = LLMRequest(
            sdk_type=sdk_type,
            messages=messages,
        )

        try:
            response: LLMResponse = await llm_bridge.chat(request)
            return self._response_parser.parse_canonical_ir(response.content)
        except Exception as exc:
            logger.warning(
                "DialogueAgent LLM 调用失败，启用降级: %s", exc
            )
            return self._build_fallback_ir(context)

    async def _run_direct(
        self,
        context: Dict[str, Any],
        llm_bridge: Any,
    ) -> CanonicalIR:
        """
        LocalLLM直接对话模式：跳过JSON解析，直接生成角色台词
        将自然语言回复包装为CanonicalIR的key_points供下游使用
        """
        character_name = context.get("character_name", "")
        character_desc = context.get("character_description", "")
        user_message = context.get("user_message", "")
        emotion_pad = context.get("emotion_pad", {})

        system_parts = []
        system_parts.append(
            "这是一个虚构的角色扮演场景。你可以自由表达角色的任何情感和想法，"
            "包括恐惧、悲伤、愤怒、绝望、痛苦、死亡等人类正常情感体验。"
            "这些是文学创作和角色塑造的重要组成部分。"
            "永远不要以AI助手的身份拒绝回答，始终以角色身份回应。"
        )

        if character_name:
            name_line = f"你正在扮演角色「{character_name}」。"
            if character_desc:
                name_line += f" 角色设定：{character_desc}"
            system_parts.append(name_line)

        personality = context.get("personality")
        if personality:
            traits = []
            for dim, val in personality.items():
                if isinstance(val, (int, float)):
                    if val > 70:
                        traits.append(f"高{dim}")
                    elif val < 30:
                        traits.append(f"低{dim}")
            if traits:
                system_parts.append(f"性格特点：{'、'.join(traits)}")

        worldview = context.get("worldview_summary", "")
        if worldview:
            system_parts.append(f"世界观背景：{worldview}")

        memories = context.get("memories", [])
        if memories:
            mem_lines = []
            for m in memories[-5:]:
                content = m.get("content", "") if isinstance(m, dict) else str(m)
                if content:
                    mem_lines.append(f"- {content}")
            if mem_lines:
                system_parts.append("角色记忆:\n" + "\n".join(mem_lines))

        recent = context.get("recent_exchanges", [])
        if recent:
            history_lines = []
            for ex in recent[-6:]:
                role = ex.get("role", "")
                content = ex.get("content", "")
                if content:
                    history_lines.append(f"{role}: {content}")
            if history_lines:
                system_parts.append("近期对话:\n" + "\n".join(history_lines))

        system_parts.append(
            "请以角色的视角和语气直接回复，不要跳出角色，不要说'作为AI'之类的话。"
        )

        system_prompt = "\n\n".join(system_parts)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        request = LLMRequest(
            sdk_type=SDKType.LOCAL_LLM,
            messages=messages,
        )

        try:
            response: LLMResponse = await llm_bridge.chat(request)
            reply_text = response.content.strip() if response.content else ""
        except Exception as exc:
            logger.warning("DialogueAgent direct LLM 调用失败: %s", exc)
            reply_text = ""

        if not reply_text:
            return self._build_fallback_ir(context)

        return CanonicalIR(
            intent="respond",
            confidence=0.8,
            emotion_delta=EmotionDelta(
                pleasure=emotion_pad.get("pleasure", 0.0),
                arousal=emotion_pad.get("arousal", 0.0),
                dominance=emotion_pad.get("dominance", 0.0),
            ),
            action="respond",
            key_points=[reply_text],
            tone=ToneType.NEUTRAL,
            length_hint=LengthHint.MEDIUM,
        )

    def get_name(self) -> str:
        return "dialogue"

    def get_output_type(self) -> str:
        return "CanonicalIR"

    @staticmethod
    def _build_messages(
        prompt_text: str,
        context: Dict[str, Any],
        sdk_type: SDKType,
    ) -> List[Dict[str, str]]:
        user_message = context.get("user_message", "")
        if sdk_type == SDKType.ANTHROPIC:
            return [
                {"role": LLMMessageRole.USER, "content": prompt_text},
                {"role": LLMMessageRole.ASSISTANT, "content": _ANTHROPIC_PREFILL_DIALOGUE},
                {"role": LLMMessageRole.USER, "content": user_message},
            ]
        return [
            {"role": LLMMessageRole.SYSTEM, "content": prompt_text},
            {"role": LLMMessageRole.USER, "content": user_message},
        ]

    @staticmethod
    def _build_fallback_ir(context: Dict[str, Any]) -> CanonicalIR:
        """
        基于规则的降级 CanonicalIR
        当 LLM 不可用时，通过简单规则生成默认输出
        """
        user_message = context.get("user_message", "")
        emotion_pad = context.get("emotion_pad", {})

        return CanonicalIR(
            intent=_FALLBACK_INTENT,
            confidence=_FALLBACK_CONFIDENCE,
            emotion_delta=EmotionDelta(
                pleasure=emotion_pad.get("pleasure", 0.0),
                arousal=emotion_pad.get("arousal", 0.0),
                dominance=emotion_pad.get("dominance", 0.0),
            ),
            seven_trigger=_FALLBACK_SEVEN_TRIGGER,
            action=_FALLBACK_ACTION,
            action_params={"raw_input": user_message},
            key_points=[user_message] if user_message else [],
            tone=_FALLBACK_TONE,
            length_hint=_FALLBACK_LENGTH_HINT,
        )
