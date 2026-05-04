"""
OCEAN人格模型 - 五因素人格量化系统
维度：开放性(O)/尽责性(C)/外向性(E)/宜人性(A)/神经质(N)
范围0-100，支持性格驱动决策影响计算
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.config import CharacterConfig

_OCEAN_DIMENSION_NAMES: Tuple[str, ...] = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)

_OCEAN_SCORE_MIN: int = 0
_OCEAN_SCORE_MAX: int = 100
_OCEAN_SCORE_MIDPOINT: float = 50.0
_OCEAN_SCORE_RANGE: float = 100.0

_PERSONALITY_INFLUENCE_NEUTRAL: float = 0.0
_PERSONALITY_INFLUENCE_SCALE: float = 0.02
_PERSONALITY_ADAPTATION_DEFAULT: float = 0.02
_PERSONALITY_ADAPTATION_MIN: float = 0.0
_PERSONALITY_ADAPTATION_MAX: float = 1.0

_TRAIT_OPENNESS_EXPLORATION_WEIGHT: float = 0.3
_TRAIT_CONSCIENTIOUSNESS_PLANNING_WEIGHT: float = 0.3
_TRAIT_EXTRAVERSION_SOCIAL_WEIGHT: float = 0.3
_TRAIT_AGREEABLENESS_COOPERATION_WEIGHT: float = 0.3
_TRAIT_NEUROTICISM_STRESS_WEIGHT: float = 0.25


class OceanPersonality:
    DIMENSION_NAMES: ClassVar[Tuple[str, ...]] = _OCEAN_DIMENSION_NAMES
    SCORE_MIN: ClassVar[int] = _OCEAN_SCORE_MIN
    SCORE_MAX: ClassVar[int] = _OCEAN_SCORE_MAX
    SCORE_MIDPOINT: ClassVar[float] = _OCEAN_SCORE_MIDPOINT
    INFLUENCE_SCALE: ClassVar[float] = _PERSONALITY_INFLUENCE_SCALE

    def __init__(
        self,
        openness: float = _OCEAN_SCORE_MIDPOINT,
        conscientiousness: float = _OCEAN_SCORE_MIDPOINT,
        extraversion: float = _OCEAN_SCORE_MIDPOINT,
        agreeableness: float = _OCEAN_SCORE_MIDPOINT,
        neuroticism: float = _OCEAN_SCORE_MIDPOINT,
        config: Optional[CharacterConfig] = None,
    ) -> None:
        self._scores: Dict[str, float] = {
            "openness": self._clamp(openness),
            "conscientiousness": self._clamp(conscientiousness),
            "extraversion": self._clamp(extraversion),
            "agreeableness": self._clamp(agreeableness),
            "neuroticism": self._clamp(neuroticism),
        }
        self._adaptation_rate: float = (
            config.personality_adaptation_rate if config is not None else _PERSONALITY_ADAPTATION_DEFAULT
        )

    def _clamp(self, value: float) -> float:
        return max(float(self.SCORE_MIN), min(float(self.SCORE_MAX), value))

    def get_score(self, dimension: str) -> float:
        return self._scores.get(dimension, self.SCORE_MIDPOINT)

    def set_score(self, dimension: str, value: float) -> None:
        if dimension in self._scores:
            self._scores[dimension] = self._clamp(value)

    def adapt(self, deltas: Dict[str, float]) -> None:
        for dim, delta in deltas.items():
            if dim in self._scores:
                current = self._scores[dim]
                self._scores[dim] = self._clamp(current + delta * self._adaptation_rate)

    def influence_decision(self, action_weights: Dict[str, float]) -> Dict[str, float]:
        influenced: Dict[str, float] = {}
        openness = self._scores["openness"]
        conscientiousness = self._scores["conscientiousness"]
        extraversion = self._scores["extraversion"]
        agreeableness = self._scores["agreeableness"]
        neuroticism = self._scores["neuroticism"]

        for action, base_weight in action_weights.items():
            modifier = _PERSONALITY_INFLUENCE_NEUTRAL
            modifier += (openness - self.SCORE_MIDPOINT) * self.INFLUENCE_SCALE * _TRAIT_OPENNESS_EXPLORATION_WEIGHT
            modifier += (conscientiousness - self.SCORE_MIDPOINT) * self.INFLUENCE_SCALE * _TRAIT_CONSCIENTIOUSNESS_PLANNING_WEIGHT
            modifier += (extraversion - self.SCORE_MIDPOINT) * self.INFLUENCE_SCALE * _TRAIT_EXTRAVERSION_SOCIAL_WEIGHT
            modifier += (agreeableness - self.SCORE_MIDPOINT) * self.INFLUENCE_SCALE * _TRAIT_AGREEABLENESS_COOPERATION_WEIGHT
            modifier -= (neuroticism - self.SCORE_MIDPOINT) * self.INFLUENCE_SCALE * _TRAIT_NEUROTICISM_STRESS_WEIGHT
            influenced[action] = base_weight + modifier
        return influenced

    def to_dict(self) -> Dict[str, float]:
        return dict(self._scores)

    @classmethod
    def from_dict(cls, data: Dict[str, float], config: Optional[CharacterConfig] = None) -> OceanPersonality:
        return cls(
            openness=data.get("openness", cls.SCORE_MIDPOINT),
            conscientiousness=data.get("conscientiousness", cls.SCORE_MIDPOINT),
            extraversion=data.get("extraversion", cls.SCORE_MIDPOINT),
            agreeableness=data.get("agreeableness", cls.SCORE_MIDPOINT),
            neuroticism=data.get("neuroticism", cls.SCORE_MIDPOINT),
            config=config,
        )

    def distance_to(self, other: OceanPersonality) -> float:
        squared_sum = 0.0
        for dim in self.DIMENSION_NAMES:
            diff = self._scores[dim] - other._scores[dim]
            squared_sum += diff * diff
        return math.sqrt(squared_sum)

    @property
    def adaptation_rate(self) -> float:
        return self._adaptation_rate

    @adaptation_rate.setter
    def adaptation_rate(self, value: float) -> None:
        self._adaptation_rate = max(_PERSONALITY_ADAPTATION_MIN, min(_PERSONALITY_ADAPTATION_MAX, value))


class PersonalityAdapter:
    _ADAPTATION_STEP_LIMIT: ClassVar[int] = 100
    _CONVERGENCE_THRESHOLD: ClassVar[float] = 0.5

    def __init__(self, personality: OceanPersonality) -> None:
        self._personality = personality

    def adapt_towards(
        self,
        target: OceanPersonality,
        experience_strength: float = 1.0,
    ) -> Dict[str, float]:
        deltas: Dict[str, float] = {}
        for dim in OceanPersonality.DIMENSION_NAMES:
            current = self._personality.get_score(dim)
            target_val = target.get_score(dim)
            delta = (target_val - current) * experience_strength
            deltas[dim] = delta
        self._personality.adapt(deltas)
        return deltas

    def is_converged(self, target: OceanPersonality) -> bool:
        return self._personality.distance_to(target) < self._CONVERGENCE_THRESHOLD

    @property
    def personality(self) -> OceanPersonality:
        return self._personality
