"""
PAD情感模型 - Pleasure/Arousal/Dominance三维情感空间
包含基础PADState（带阻尼更新）和ExtendedPAD（P/A/D × 七情权重矩阵）
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.types import SevenEmotionType, SevenEmotions, TCMEmotionType, PlutchikPrimary, PlutchikDyad

_PAD_DIMENSION_MIN: float = -1.0
_PAD_DIMENSION_MAX: float = 1.0
_PAD_NEUTRAL: float = 0.0
_PAD_DEFAULT_DAMPING: float = 0.85
_PAD_DEFAULT_DELTA_SCALE: float = 1.0

_EXTENDED_PAD_DEFAULT_WEIGHT: float = 0.0
_EXTENDED_PAD_EMOTION_SCALE: float = 0.2

_JOY_PAD_VECTOR: Tuple[float, float, float] = (0.6, 0.5, 0.3)
_ANGER_PAD_VECTOR: Tuple[float, float, float] = (-0.6, 0.7, 0.4)
_SORROW_PAD_VECTOR: Tuple[float, float, float] = (-0.7, -0.3, -0.4)
_FEAR_PAD_VECTOR: Tuple[float, float, float] = (-0.7, 0.5, -0.5)
_LOVE_PAD_VECTOR: Tuple[float, float, float] = (0.5, 0.3, 0.2)
_DISGUST_PAD_VECTOR: Tuple[float, float, float] = (-0.5, 0.3, 0.1)
_DESIRE_PAD_VECTOR: Tuple[float, float, float] = (0.3, 0.6, 0.2)

_EMOTION_PAD_MAP: Dict[str, Tuple[float, float, float]] = {
    SevenEmotionType.JOY.value: _JOY_PAD_VECTOR,
    SevenEmotionType.ANGER.value: _ANGER_PAD_VECTOR,
    SevenEmotionType.SORROW.value: _SORROW_PAD_VECTOR,
    SevenEmotionType.FEAR.value: _FEAR_PAD_VECTOR,
    SevenEmotionType.LOVE.value: _LOVE_PAD_VECTOR,
    SevenEmotionType.DISGUST.value: _DISGUST_PAD_VECTOR,
    SevenEmotionType.DESIRE.value: _DESIRE_PAD_VECTOR,
}

_SURPRISE_PAD_VECTOR: Tuple[float, float, float] = (0.2, 0.6, -0.1)
_CURIOSITY_PAD_VECTOR: Tuple[float, float, float] = (0.2, 0.3, -0.1)

_ENGLISH_EMOTION_PAD_MAP: Dict[str, Tuple[float, float, float]] = {
    "joy": _JOY_PAD_VECTOR,
    "anger": _ANGER_PAD_VECTOR,
    "sorrow": _SORROW_PAD_VECTOR,
    "fear": _FEAR_PAD_VECTOR,
    "love": _LOVE_PAD_VECTOR,
    "disgust": _DISGUST_PAD_VECTOR,
    "desire": _DESIRE_PAD_VECTOR,
    "sadness": _SORROW_PAD_VECTOR,
    "anxiety": _FEAR_PAD_VECTOR,
    "surprise": _SURPRISE_PAD_VECTOR,
    "trust": _LOVE_PAD_VECTOR,
    "hope": _JOY_PAD_VECTOR,
    "curiosity": _CURIOSITY_PAD_VECTOR,
}


def _clamp_pad(value: float) -> float:
    return max(_PAD_DIMENSION_MIN, min(_PAD_DIMENSION_MAX, value))


_OCEAN_RANGE_CENTER: float = 50.0
_OCEAN_RANGE_HALF: float = 50.0

_OCEAN_PLEASURE_WEIGHTS: Dict[str, float] = {
    "extraversion": 0.21,
    "agreeableness": 0.25,
    "neuroticism": -0.26,
    "conscientiousness": 0.12,
    "openness": 0.08,
}

_OCEAN_AROUSAL_WEIGHTS: Dict[str, float] = {
    "extraversion": 0.15,
    "neuroticism": 0.20,
    "openness": 0.18,
    "agreeableness": -0.05,
    "conscientiousness": 0.05,
}

_OCEAN_DOMINANCE_WEIGHTS: Dict[str, float] = {
    "extraversion": 0.30,
    "conscientiousness": 0.15,
    "agreeableness": -0.12,
    "neuroticism": -0.22,
    "openness": 0.05,
}


def ocean_to_pad_baseline(ocean_scores: Dict[str, float]) -> PADState:
    """
    OCEAN大五人格 → PAD情感基线映射
    基于Mehrabian(1996) "Analysis of the Big-five Personality Factors
    in Terms of the PAD Temperament Model" 的实证相关系数

    映射关系:
      Pleasure:  E(+0.21) A(+0.25) N(-0.26) C(+0.12) O(+0.08)
      Arousal:   E(+0.15) N(+0.20) O(+0.18) A(-0.05) C(+0.05)
      Dominance: E(+0.30) C(+0.15) A(-0.12) N(-0.22) O(+0.05)

    ocean_scores: 0-100范围的OCEAN分数
    返回: PADState，各维度在[-1, 1]范围
    """
    normalized: Dict[str, float] = {}
    for trait, score in ocean_scores.items():
        normalized[trait] = (score - _OCEAN_RANGE_CENTER) / _OCEAN_RANGE_HALF

    pleasure = sum(
        _OCEAN_PLEASURE_WEIGHTS.get(trait, 0.0) * value
        for trait, value in normalized.items()
    )
    arousal = sum(
        _OCEAN_AROUSAL_WEIGHTS.get(trait, 0.0) * value
        for trait, value in normalized.items()
    )
    dominance = sum(
        _OCEAN_DOMINANCE_WEIGHTS.get(trait, 0.0) * value
        for trait, value in normalized.items()
    )

    return PADState(
        pleasure=_clamp_pad(pleasure),
        arousal=_clamp_pad(arousal),
        dominance=_clamp_pad(dominance),
    )


@dataclass
class PADState:
    DIMENSION_MIN: ClassVar[float] = _PAD_DIMENSION_MIN
    DIMENSION_MAX: ClassVar[float] = _PAD_DIMENSION_MAX
    NEUTRAL: ClassVar[float] = _PAD_NEUTRAL
    DEFAULT_DAMPING: ClassVar[float] = _PAD_DEFAULT_DAMPING

    pleasure: float = _PAD_NEUTRAL
    arousal: float = _PAD_NEUTRAL
    dominance: float = _PAD_NEUTRAL
    damping: float = _PAD_DEFAULT_DAMPING

    def update(self, delta_p: float, delta_a: float, delta_d: float, scale: float = _PAD_DEFAULT_DELTA_SCALE) -> PADState:
        new_p = _clamp_pad(self.pleasure * self.damping + delta_p * scale)
        new_a = _clamp_pad(self.arousal * self.damping + delta_a * scale)
        new_d = _clamp_pad(self.dominance * self.damping + delta_d * scale)
        return PADState(pleasure=new_p, arousal=new_a, dominance=new_d, damping=self.damping)

    def decay(self) -> PADState:
        new_p = _clamp_pad(self.pleasure * self.damping)
        new_a = _clamp_pad(self.arousal * self.damping)
        new_d = _clamp_pad(self.dominance * self.damping)
        return PADState(pleasure=new_p, arousal=new_a, dominance=new_d, damping=self.damping)

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.pleasure, self.arousal, self.dominance)

    @classmethod
    def from_tuple(cls, values: Tuple[float, float, float], damping: float = _PAD_DEFAULT_DAMPING) -> PADState:
        return cls(
            pleasure=_clamp_pad(values[0]),
            arousal=_clamp_pad(values[1]),
            dominance=_clamp_pad(values[2]),
            damping=damping,
        )

    def distance_to(self, other: PADState) -> float:
        dp = self.pleasure - other.pleasure
        da = self.arousal - other.arousal
        dd = self.dominance - other.dominance
        return math.sqrt(dp * dp + da * da + dd * dd)

    def magnitude(self) -> float:
        return math.sqrt(self.pleasure ** 2 + self.arousal ** 2 + self.dominance ** 2)

    def blend(self, other: PADState, weight: float) -> PADState:
        weight = max(0.0, min(1.0, weight))
        inv_weight = 1.0 - weight
        return PADState(
            pleasure=_clamp_pad(self.pleasure * inv_weight + other.pleasure * weight),
            arousal=_clamp_pad(self.arousal * inv_weight + other.arousal * weight),
            dominance=_clamp_pad(self.dominance * inv_weight + other.dominance * weight),
            damping=self.damping,
        )


class ExtendedPAD:
    EMOTION_SCALE: ClassVar[float] = _EXTENDED_PAD_EMOTION_SCALE
    DEFAULT_WEIGHT: ClassVar[float] = _EXTENDED_PAD_DEFAULT_WEIGHT

    def __init__(
        self,
        pad_state: Optional[PADState] = None,
        seven_emotions: Optional[SevenEmotions] = None,
    ) -> None:
        self._pad = pad_state if pad_state is not None else PADState()
        self._emotions = seven_emotions if seven_emotions is not None else SevenEmotions()
        self._emotion_pad_map: Dict[str, Tuple[float, float, float]] = dict(_EMOTION_PAD_MAP)
        self._emotion_pad_map.update(_ENGLISH_EMOTION_PAD_MAP)

    def update_from_emotion(self, emotion_name: str, intensity: float) -> PADState:
        self._emotions.set_emotion(emotion_name, intensity)
        pad_vector = self._emotion_pad_map.get(emotion_name)
        if pad_vector is None:
            return self._pad
        scaled_p = pad_vector[0] * intensity * self.EMOTION_SCALE
        scaled_a = pad_vector[1] * intensity * self.EMOTION_SCALE
        scaled_d = pad_vector[2] * intensity * self.EMOTION_SCALE
        self._pad = self._pad.update(scaled_p, scaled_a, scaled_d)
        return self._pad

    def compute_composite(self) -> PADState:
        composite_p = _PAD_NEUTRAL
        composite_a = _PAD_NEUTRAL
        composite_d = _PAD_NEUTRAL
        for emotion_type in SevenEmotionType:
            name = emotion_type.value
            intensity = self._emotions.get_emotion(name)
            if intensity == _PAD_NEUTRAL:
                continue
            pad_vector = self._emotion_pad_map.get(name)
            if pad_vector is None:
                continue
            weight_matrix = self._emotions.weights.get(name, {})
            cross_weight = sum(weight_matrix.values()) / max(len(weight_matrix), 1)
            effective_intensity = intensity * (1.0 + cross_weight * self.EMOTION_SCALE)
            composite_p += pad_vector[0] * effective_intensity * self.EMOTION_SCALE
            composite_a += pad_vector[1] * effective_intensity * self.EMOTION_SCALE
            composite_d += pad_vector[2] * effective_intensity * self.EMOTION_SCALE
        self._pad = PADState(
            pleasure=_clamp_pad(composite_p),
            arousal=_clamp_pad(composite_a),
            dominance=_clamp_pad(composite_d),
            damping=self._pad.damping,
        )
        return self._pad

    def set_emotion_pad_mapping(self, emotion_name: str, pad_vector: Tuple[float, float, float]) -> None:
        self._emotion_pad_map[emotion_name] = (
            _clamp_pad(pad_vector[0]),
            _clamp_pad(pad_vector[1]),
            _clamp_pad(pad_vector[2]),
        )

    @property
    def pad_state(self) -> PADState:
        return self._pad

    @pad_state.setter
    def pad_state(self, value: PADState) -> None:
        self._pad = value

    @property
    def pleasure(self) -> float:
        return self._pad.pleasure

    @property
    def arousal(self) -> float:
        return self._pad.arousal

    @property
    def dominance(self) -> float:
        return self._pad.dominance

    @property
    def emotions(self) -> SevenEmotions:
        return self._emotions

    def dominant_emotion(self) -> Optional[str]:
        return self._emotions.dominant_emotion()


_TCM_EMOTION_PAD_MAP: Dict[str, Tuple[float, float, float]] = {
    TCMEmotionType.JOY.value: (0.6, 0.5, 0.3),
    TCMEmotionType.ANGER.value: (-0.6, 0.7, 0.4),
    TCMEmotionType.ANXIETY.value: (-0.3, 0.2, -0.2),
    TCMEmotionType.THOUGHT.value: (0.0, -0.1, 0.1),
    TCMEmotionType.GRIEF.value: (-0.7, -0.3, -0.4),
    TCMEmotionType.FEAR.value: (-0.7, 0.5, -0.5),
    TCMEmotionType.FRIGHT.value: (-0.5, 0.8, -0.3),
}

_PLUTCHIK_PRIMARY_PAD: Dict[PlutchikPrimary, Tuple[float, float, float]] = {
    PlutchikPrimary.JOY: (0.6, 0.5, 0.3),
    PlutchikPrimary.TRUST: (0.4, 0.2, 0.1),
    PlutchikPrimary.FEAR: (-0.7, 0.5, -0.5),
    PlutchikPrimary.SURPRISE: (0.1, 0.7, -0.1),
    PlutchikPrimary.SADNESS: (-0.7, -0.3, -0.4),
    PlutchikPrimary.DISGUST: (-0.5, 0.3, 0.1),
    PlutchikPrimary.ANGER: (-0.6, 0.7, 0.4),
    PlutchikPrimary.ANTICIPATION: (0.3, 0.6, 0.2),
}

_PLUTCHIK_DYAD_COMPOSITIONS: Dict[PlutchikDyad, Tuple[PlutchikPrimary, PlutchikPrimary]] = {
    PlutchikDyad.LOVE: (PlutchikPrimary.JOY, PlutchikPrimary.TRUST),
    PlutchikDyad.SUBMISSION: (PlutchikPrimary.TRUST, PlutchikPrimary.FEAR),
    PlutchikDyad.AWE: (PlutchikPrimary.FEAR, PlutchikPrimary.SURPRISE),
    PlutchikDyad.DISAPPROVAL: (PlutchikPrimary.SURPRISE, PlutchikPrimary.SADNESS),
    PlutchikDyad.REMORSE: (PlutchikPrimary.SADNESS, PlutchikPrimary.DISGUST),
    PlutchikDyad.CONTEMPT: (PlutchikPrimary.DISGUST, PlutchikPrimary.ANGER),
    PlutchikDyad.AGGRESSIVENESS: (PlutchikPrimary.ANGER, PlutchikPrimary.ANTICIPATION),
    PlutchikDyad.OPTIMISM: (PlutchikPrimary.ANTICIPATION, PlutchikPrimary.JOY),
}

_SEVEN_TO_PLUTCHIK_MAP: Dict[SevenEmotionType, PlutchikPrimary] = {
    SevenEmotionType.JOY: PlutchikPrimary.JOY,
    SevenEmotionType.ANGER: PlutchikPrimary.ANGER,
    SevenEmotionType.SORROW: PlutchikPrimary.SADNESS,
    SevenEmotionType.FEAR: PlutchikPrimary.FEAR,
    SevenEmotionType.LOVE: PlutchikPrimary.TRUST,
    SevenEmotionType.DISGUST: PlutchikPrimary.DISGUST,
    SevenEmotionType.DESIRE: PlutchikPrimary.ANTICIPATION,
}

_TCM_TO_SEVEN_MAP: Dict[TCMEmotionType, SevenEmotionType] = {
    TCMEmotionType.JOY: SevenEmotionType.JOY,
    TCMEmotionType.ANGER: SevenEmotionType.ANGER,
    TCMEmotionType.ANXIETY: SevenEmotionType.FEAR,
    TCMEmotionType.THOUGHT: SevenEmotionType.DESIRE,
    TCMEmotionType.GRIEF: SevenEmotionType.SORROW,
    TCMEmotionType.FEAR: SevenEmotionType.FEAR,
    TCMEmotionType.FRIGHT: SevenEmotionType.FEAR,
}


def compute_plutchik_dyad(
    primary_a: PlutchikPrimary,
    primary_b: PlutchikPrimary,
    intensity_a: float = 1.0,
    intensity_b: float = 1.0,
) -> Tuple[Optional[PlutchikDyad], PADState]:
    pair = (primary_a, primary_b)
    pair_rev = (primary_b, primary_a)
    dyad = None
    for d, composition in _PLUTCHIK_DYAD_COMPOSITIONS.items():
        if composition == pair or composition == pair_rev:
            dyad = d
            break
    pad_a = _PLUTCHIK_PRIMARY_PAD.get(primary_a, (0.0, 0.0, 0.0))
    pad_b = _PLUTCHIK_PRIMARY_PAD.get(primary_b, (0.0, 0.0, 0.0))
    avg_p = (pad_a[0] * intensity_a + pad_b[0] * intensity_b) / (intensity_a + intensity_b)
    avg_a = (pad_a[1] * intensity_a + pad_b[1] * intensity_b) / (intensity_a + intensity_b)
    avg_d = (pad_a[2] * intensity_a + pad_b[2] * intensity_b) / (intensity_a + intensity_b)
    return dyad, PADState(pleasure=_clamp_pad(avg_p), arousal=_clamp_pad(avg_a), dominance=_clamp_pad(avg_d))


def seven_to_plutchik(emotion: SevenEmotionType) -> PlutchikPrimary:
    return _SEVEN_TO_PLUTCHIK_MAP.get(emotion, PlutchikPrimary.ANTICIPATION)


def tcm_to_seven(emotion: TCMEmotionType) -> SevenEmotionType:
    return _TCM_TO_SEVEN_MAP.get(emotion, SevenEmotionType.DESIRE)
