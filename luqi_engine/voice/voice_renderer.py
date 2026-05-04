"""确定性语音渲染器 — IR→自然语言，保证降级时风格一致"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from luqi_engine.core.types import CanonicalIR
from luqi_engine.core.interfaces import IVoiceRenderer
from luqi_engine.core.constants import (
    ToneType,
    _DEFAULT_CHARACTER_NAME,
    _DEFAULT_MAX_KEY_POINTS,
)

_TONE_TEMPLATES: Dict[str, str] = {
    "casual": "{name}说道：「{content}」",
    "cautious": "{name}低声说道：「{content}」",
    "formal": "{name}郑重地说：「{content}」",
    "angry": "{name}怒道：「{content}」",
    "sad": "{name}黯然道：「{content}」",
    "neutral": "{name}：「{content}」",
}

_ACTION_TEMPLATES: Dict[str, str] = {
    "smile_nod": "{name}微笑着点了点头。",
    "step_back_draw_weapon": "{name}猛地后退一步，右手本能地按上了腰间的剑柄。",
    "idle": "",
}

_LENGTH_HINT_MAX_POINTS: Dict[str, int] = {
    "tiny": 1,
    "short": 2,
    "medium": 3,
    "long": 5,
}

_CONNECTORS: List[str] = ["，", "。", "……", "，而且", "，不过"]

_LCG_MULTIPLIER = 1103515245
_LCG_INCREMENT = 12345
_LCG_MODULUS_MASK = 0x7FFFFFFF


class _SeededRNG:
    """确定性伪随机数生成器"""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def next_int(self, max_val: int) -> int:
        if max_val <= 0:
            return 0
        self._state = (self._state * _LCG_MULTIPLIER + _LCG_INCREMENT) & _LCG_MODULUS_MASK
        return self._state % max_val

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self.next_int(i + 1)
            items[i], items[j] = items[j], items[i]


class VoiceRenderer(IVoiceRenderer):
    """确定性 IR→自然语言渲染器"""

    def render(
        self,
        ir: CanonicalIR,
        voice_profile: Optional[Dict[str, Any]] = None,
        seed: int = 0,
    ) -> str:
        rng = _SeededRNG(seed)
        name = voice_profile.get("name", _DEFAULT_CHARACTER_NAME) if voice_profile else _DEFAULT_CHARACTER_NAME

        parts: List[str] = []

        action_template = _ACTION_TEMPLATES.get(ir.action, "")
        if action_template:
            parts.append(action_template.format(name=name))

        if ir.key_points:
            key_points_copy = list(ir.key_points)
            rng.shuffle(key_points_copy)
            content = self._render_dialogue_from_keypoints(
                key_points_copy, ir.tone, ir.length_hint, rng, voice_profile
            )
            tone = ir.tone if ir.tone in _TONE_TEMPLATES else ToneType.NEUTRAL
            template = _TONE_TEMPLATES[tone]
            parts.append(template.format(name=name, content=content))

        return "\n".join(parts)

    def _render_dialogue_from_keypoints(
        self,
        key_points: List[str],
        tone: str,
        length_hint: str,
        rng: Any,
        voice_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        max_points = _LENGTH_HINT_MAX_POINTS.get(length_hint, _DEFAULT_MAX_KEY_POINTS)
        selected = key_points[:max_points]

        result_parts = []
        for i, point in enumerate(selected):
            result_parts.append(point)
            if i < len(selected) - 1:
                result_parts.append(_CONNECTORS[rng.next_int(len(_CONNECTORS))])

        return "".join(result_parts)
