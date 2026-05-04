from __future__ import annotations

from typing import Any, Dict, List, Optional

from luqi_engine.core.config import LLMConfig
from luqi_engine.core.constants import (
    OCEAN_HIGH_THRESHOLD,
    OCEAN_LOW_THRESHOLD,
    PAD_POSITIVE_THRESHOLD,
    PAD_NEGATIVE_THRESHOLD,
)

_OCEAN_TRAIT_MAP: Dict[str, Dict[str, str]] = {
    "openness": {"high": "开放/好奇/富有想象力", "low": "保守/传统/务实", "mid": "适度开放"},
    "conscientiousness": {"high": "尽责/自律/有条理", "low": "随性/灵活/不拘小节", "mid": "适度尽责"},
    "extraversion": {"high": "外向/热情/善交际", "low": "内向/安静/独处", "mid": "适度外向"},
    "agreeableness": {"high": "友善/合作/体贴", "low": "直率/独立/好辩", "mid": "适度友善"},
    "neuroticism": {"high": "敏感/易焦虑/情绪波动", "low": "稳定/冷静/从容", "mid": "适度敏感"},
}

_PAD_EMOTION_MAP: Dict[str, Dict[str, str]] = {
    "pleasure": {"high": "愉悦", "low": "不悦", "mid": "平淡"},
    "arousal": {"high": "激动", "low": "平静", "mid": "一般"},
    "dominance": {"high": "主导", "low": "顺从", "mid": "平等"},
}

_SEVEN_EMOTIONS: List[str] = ["喜", "怒", "忧", "思", "悲", "恐", "惊"]

_MAX_MEMORY_ITEMS: int = 5
_TOKEN_PER_CHAR_ESTIMATE: float = 0.6


class StateRenderer:
    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self._max_system_token_estimate: int = (
            config.system_token_budget if config else 300
        )

    def render_system_prompt(
        self,
        character_name: str = "",
        personality: Optional[Dict[str, float]] = None,
        pad_emotion: Optional[Dict[str, float]] = None,
        seven_emotions: Optional[Dict[str, float]] = None,
        scene: str = "",
        behavior_instruction: str = "",
        memories: Optional[List[Dict[str, Any]]] = None,
        background: str = "",
        output_requirements: str = "",
    ) -> str:
        parts: List[str] = []

        if character_name:
            parts.append("[角色]{}".format(character_name))

        if background:
            bg_summary = background
            if len(bg_summary) > 60:
                bg_summary = bg_summary[:57] + "..."
            parts.append("[背景]{}".format(bg_summary))

        if personality:
            traits = self._render_personality(personality)
            if traits:
                parts.append("[性格]{}".format(traits))

        if pad_emotion:
            emotion_str = self._render_pad_emotion(pad_emotion)
            if emotion_str:
                parts.append("[情绪]{}".format(emotion_str))

        if seven_emotions:
            emo_str = self._render_seven_emotions(seven_emotions)
            if emo_str:
                parts.append("[七情]{}".format(emo_str))

        if scene:
            parts.append("[场景]{}".format(scene))

        if behavior_instruction:
            parts.append("[指令]{}".format(behavior_instruction))

        if memories:
            mem_str = self._render_memories(memories)
            if mem_str:
                parts.append("[记忆]{}".format(mem_str))

        if output_requirements:
            parts.append("[要求]{}".format(output_requirements))

        result = " ".join(parts)

        estimated_tokens = len(result) * _TOKEN_PER_CHAR_ESTIMATE
        if estimated_tokens > self._max_system_token_estimate:
            result = self._compress_prompt(result)

        return result

    def _render_personality(self, personality: Dict[str, float]) -> str:
        traits: List[str] = []
        for dim, score in personality.items():
            dim_key = dim.lower()
            if dim_key not in _OCEAN_TRAIT_MAP:
                continue
            if score >= OCEAN_HIGH_THRESHOLD:
                traits.append(_OCEAN_TRAIT_MAP[dim_key]["high"].split("/")[0])
            elif score <= OCEAN_LOW_THRESHOLD:
                traits.append(_OCEAN_TRAIT_MAP[dim_key]["low"].split("/")[0])
            else:
                traits.append(_OCEAN_TRAIT_MAP[dim_key]["mid"].split("/")[0])
        return "/".join(traits)

    def _render_pad_emotion(self, pad: Dict[str, float]) -> str:
        parts: List[str] = []
        for dim, score in pad.items():
            dim_key = dim.lower()
            if dim_key not in _PAD_EMOTION_MAP:
                continue
            if score >= PAD_POSITIVE_THRESHOLD:
                parts.append("{}{:.1f}".format(_PAD_EMOTION_MAP[dim_key]["high"], abs(score)))
            elif score <= PAD_NEGATIVE_THRESHOLD:
                parts.append("{}{:.1f}".format(_PAD_EMOTION_MAP[dim_key]["low"], abs(score)))
        return "/".join(parts)

    def _render_seven_emotions(self, emotions: Dict[str, float]) -> str:
        parts: List[str] = []
        for emo_name in _SEVEN_EMOTIONS:
            score = emotions.get(emo_name, 0.0)
            if score >= 0.3:
                parts.append("{}{:.1f}".format(emo_name, score))
        return "/".join(parts)

    def _render_memories(self, memories: List[Dict[str, Any]]) -> str:
        items = memories[:_MAX_MEMORY_ITEMS]
        parts: List[str] = []
        for mem in items:
            who = mem.get("who", "")
            what = mem.get("what", "")
            if what:
                if who:
                    parts.append("{}:{}".format(who, what[:20]))
                else:
                    parts.append(what[:20])
        return "|".join(parts)

    def _compress_prompt(self, prompt: str) -> str:
        while len(prompt) * _TOKEN_PER_CHAR_ESTIMATE > self._max_system_token_estimate:
            parts = prompt.split(" ")
            if len(parts) <= 3:
                break
            mid = len(parts) // 2
            parts.pop(mid)
            prompt = " ".join(parts)
        return prompt
