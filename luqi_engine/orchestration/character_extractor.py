"""
CharacterExtractor - 角色信息提取器
从LuqiEngine提取的重复角色信息提取逻辑

架构权衡记录：
- 拆分原因：_extract_personality/emotion_pad/character_state在chat()、_render_system_prompt()、
  _build_prompt_context()中重复出现3次，每次都手写hasattr/get_score
- 边界防御：所有方法对None/缺失属性做安全降级，不抛异常
- 前置条件：character对象可以是CharacterEntity或任意具有personality/emotion属性的对象
- 后置条件：返回Dict[str, float]，缺失字段不包含在返回值中
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from luqi_engine.llm.state_renderer import StateRenderer
from luqi_engine.llm.dialogue_modes import DialogueMode
from luqi_engine.core.constants import _LOCAL_LLM_OUTPUT_REQUIREMENTS

_OCEAN_TRAIT_KEYS: tuple = (
    "openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"
)

_PAD_DIMENSION_KEYS: tuple = ("pleasure", "arousal", "dominance")


class CharacterExtractor:
    """角色信息提取器，统一提取OCEAN/PAD/角色状态"""

    def __init__(self, state_renderer: Optional[StateRenderer] = None) -> None:
        self._state_renderer = state_renderer

    def set_state_renderer(self, renderer: Optional[StateRenderer]) -> None:
        self._state_renderer = renderer

    def extract_personality(self, character: Any) -> Dict[str, float]:
        """
        提取OCEAN性格分数

        前置条件：character具有personality属性且personality有get_score方法
        后置条件：返回5维OCEAN分数Dict，缺失返回空Dict
        """
        if not hasattr(character, 'personality'):
            return {}
        personality = character.personality
        if not hasattr(personality, 'get_score'):
            return {}
        result: Dict[str, float] = {}
        for trait in _OCEAN_TRAIT_KEYS:
            try:
                result[trait] = personality.get_score(trait)
            except Exception:
                continue
        return result

    def extract_emotion_pad(self, character: Any) -> Dict[str, float]:
        """
        提取PAD情感状态

        前置条件：character具有emotion属性且emotion有pleasure/arousal/dominance属性
        后置条件：返回3维PAD Dict，缺失返回空Dict
        """
        if not hasattr(character, 'emotion'):
            return {}
        emotion = character.emotion
        result: Dict[str, float] = {}
        for dim in _PAD_DIMENSION_KEYS:
            val = getattr(emotion, dim, None)
            if val is not None:
                try:
                    result[dim] = float(val)
                except (TypeError, ValueError):
                    continue
        return result

    def extract_character_state(self, character: Any) -> Dict[str, Any]:
        """
        提取完整角色状态（name + personality + emotion_pad）

        前置条件：character可以是任意对象
        后置条件：返回包含可用字段的Dict
        """
        state: Dict[str, Any] = {}
        if hasattr(character, 'name'):
            state["name"] = character.name
        personality = self.extract_personality(character)
        if personality:
            state["personality"] = personality
        emotion_pad = self.extract_emotion_pad(character)
        if emotion_pad:
            state["emotion_pad"] = emotion_pad
        return state

    def render_system_prompt(self, character: Any) -> str:
        """
        渲染本地LLM系统提示词

        前置条件：state_renderer已初始化，character具有name/personality/emotion
        后置条件：返回系统提示词字符串，state_renderer不可用时返回空字符串
        """
        if self._state_renderer is None:
            return ""
        personality = self.extract_personality(character)
        pad_emotion = self.extract_emotion_pad(character)
        return self._state_renderer.render_system_prompt(
            character_name=getattr(character, 'name', ''),
            personality=personality,
            pad_emotion=pad_emotion,
            seven_emotions=getattr(character, "seven_emotions", None),
            scene="",
            behavior_instruction="",
            memories=[],
            background=getattr(character, "background", ""),
            output_requirements=_LOCAL_LLM_OUTPUT_REQUIREMENTS,
        )

    def build_prompt_context(
        self, character: Any, mode: DialogueMode, world_guidance: str = ""
    ) -> Any:
        """
        构建LLM PromptContext

        前置条件：character具有name/personality/emotion
        后置条件：返回PromptContext对象
        """
        from luqi_engine.llm.prompt_builder import PromptContext
        personality = self.extract_personality(character)
        emotion_pad = self.extract_emotion_pad(character)
        dominant_emotion = "neutral"
        if hasattr(character, 'emotion') and hasattr(character.emotion, 'dominant_emotion'):
            de = character.emotion.dominant_emotion
            dominant_emotion = de() if callable(de) else de
        mode_value = mode.value if hasattr(mode, 'value') else str(mode)
        return PromptContext(
            character_name=getattr(character, 'name', ''),
            personality=personality,
            emotion_pad=emotion_pad,
            dominant_emotion=dominant_emotion,
            memories=[],
            worldview_summary=world_guidance,
            narrative_rules=None,
            dialogue_mode_instruction=mode_value,
        )
