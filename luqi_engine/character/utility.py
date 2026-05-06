"""
效用AI与CEM规划器 - IAUS考虑因子/行为选项 + CEM Boltzmann分布自适应温度
实现基于效用的决策系统和上下文熵模型规划
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.rng import PCGRandom

_UTILITY_MIN: float = 0.0
_UTILITY_MAX: float = 1.0
_UTILITY_MIDPOINT: float = 0.5

_RESPONSE_CURVE_LINEAR: str = "linear"
_RESPONSE_CURVE_QUADRATIC: str = "quadratic"
_RESPONSE_CURVE_LOGISTIC: str = "logistic"
_RESPONSE_CURVE_SIGMOID: str = "sigmoid"

_BOLTZMANN_DEFAULT_TEMPERATURE: float = 1.0
_BOLTZMANN_MIN_TEMPERATURE: float = 0.01
_BOLTZMANN_MAX_TEMPERATURE: float = 10.0
_BOLTZMANN_ADAPTATION_RATE: float = 0.1
_BOLTZMANN_ENTROPY_TARGET: float = 0.5

_CEM_SELECTION_COUNT: int = 3
_CEM_COMPENSATION_FACTOR: float = 0.2

_LOGISTIC_K: float = 10.0
_LOGISTIC_X0: float = 0.5
_SIGMOID_STEEPNESS: float = 5.0
_EXPONENT_CLAMP_MIN: float = -50.0
_EXPONENT_CLAMP_MAX: float = 50.0
_UTILITY_EPSILON: float = 1e-6


def _clamp_utility(value: float) -> float:
    return max(_UTILITY_MIN, min(_UTILITY_MAX, value))


class ResponseCurve:
    LINEAR: ClassVar[str] = _RESPONSE_CURVE_LINEAR
    QUADRATIC: ClassVar[str] = _RESPONSE_CURVE_QUADRATIC
    LOGISTIC: ClassVar[str] = _RESPONSE_CURVE_LOGISTIC
    SIGMOID: ClassVar[str] = _RESPONSE_CURVE_SIGMOID

    def __init__(
        self,
        curve_type: str = _RESPONSE_CURVE_LINEAR,
        slope: float = 1.0,
        x_shift: float = 0.0,
        y_shift: float = 0.0,
    ) -> None:
        self._curve_type = curve_type
        self._slope = slope
        self._x_shift = x_shift
        self._y_shift = y_shift

    def evaluate(self, input_value: float) -> float:
        x = input_value + self._x_shift
        if self._curve_type == self.QUADRATIC:
            result = self._slope * x * x
        elif self._curve_type == self.LOGISTIC:
            exponent = _LOGISTIC_K * (x - _LOGISTIC_X0)
            exponent = max(_EXPONENT_CLAMP_MIN, min(_EXPONENT_CLAMP_MAX, exponent))
            result = self._slope / (1.0 + math.exp(-exponent))
        elif self._curve_type == self.SIGMOID:
            exponent = _SIGMOID_STEEPNESS * (x - _UTILITY_MIDPOINT)
            exponent = max(_EXPONENT_CLAMP_MIN, min(_EXPONENT_CLAMP_MAX, exponent))
            result = 1.0 / (1.0 + math.exp(-exponent))
            result = self._slope * result
        else:
            result = self._slope * x
        return _clamp_utility(result + self._y_shift)


@dataclass
class Consideration:
    name: str
    curve: ResponseCurve = field(default_factory=ResponseCurve)
    weight: float = 1.0
    input_fn: Optional[Callable[[], float]] = None

    def evaluate(self) -> float:
        if self.input_fn is None:
            return _UTILITY_MIDPOINT
        raw = self.input_fn()
        return self.curve.evaluate(raw) * self.weight


@dataclass
class BehaviorOption:
    name: str
    considerations: List[Consideration] = field(default_factory=list)
    base_weight: float = 1.0
    compensations: Dict[str, float] = field(default_factory=dict)

    def compute_utility(self) -> float:
        if not self.considerations:
            return _clamp_utility(self.base_weight)
        product = self.base_weight
        for consideration in self.considerations:
            score = consideration.evaluate()
            product *= max(score, _UTILITY_EPSILON)
        num_considerations = len(self.considerations)
        if num_considerations > 1:
            modification_factor = 1.0 - (1.0 / num_considerations)
            makeup_value = (1.0 - product) * modification_factor
            product = product + makeup_value * product
        return _clamp_utility(product)

    def apply_compensation(self, context_name: str, factor: float) -> None:
        self.compensations[context_name] = factor

    def compensated_utility(self) -> float:
        base = self.compute_utility()
        compensation_product = 1.0
        for factor in self.compensations.values():
            compensation_product *= factor
        return _clamp_utility(base * compensation_product)


class DefaultBehaviors:
    @staticmethod
    def create_all() -> List[BehaviorOption]:
        return [
            BehaviorOption(
                name="socialize",
                considerations=[
                    Consideration(name="extraversion", curve=ResponseCurve(curve_type=ResponseCurve.LINEAR, slope=0.5), weight=0.6),
                    Consideration(name="arousal", curve=ResponseCurve(curve_type=ResponseCurve.SIGMOID), weight=0.4),
                ],
                base_weight=0.5,
            ),
            BehaviorOption(
                name="express",
                considerations=[
                    Consideration(name="openness", curve=ResponseCurve(curve_type=ResponseCurve.LINEAR, slope=0.5), weight=0.5),
                    Consideration(name="pleasure", curve=ResponseCurve(curve_type=ResponseCurve.QUADRATIC, slope=0.3), weight=0.5),
                ],
                base_weight=0.4,
            ),
            BehaviorOption(
                name="observe",
                considerations=[
                    Consideration(name="neuroticism", curve=ResponseCurve(curve_type=ResponseCurve.LINEAR, slope=0.4), weight=0.6),
                    Consideration(name="safety_urgency", curve=ResponseCurve(curve_type=ResponseCurve.LOGISTIC), weight=0.4),
                ],
                base_weight=0.3,
            ),
            BehaviorOption(
                name="reminisce",
                considerations=[
                    Consideration(name="conscientiousness", curve=ResponseCurve(curve_type=ResponseCurve.LINEAR, slope=0.3), weight=0.5),
                    Consideration(name="dominance", curve=ResponseCurve(curve_type=ResponseCurve.SIGMOID), weight=0.5),
                ],
                base_weight=0.2,
            ),
            BehaviorOption(
                name="depart",
                considerations=[
                    Consideration(name="low_pleasure", curve=ResponseCurve(curve_type=ResponseCurve.LOGISTIC, slope=-0.5, x_shift=0.3), weight=0.7),
                    Consideration(name="high_arousal", curve=ResponseCurve(curve_type=ResponseCurve.QUADRATIC, slope=-0.3), weight=0.3),
                ],
                base_weight=0.1,
            ),
        ]


class UtilityBasedAI:
    def __init__(self, rng: Optional[PCGRandom] = None, register_defaults: bool = False) -> None:
        self._behaviors: List[BehaviorOption] = []
        self._rng = rng if rng is not None else PCGRandom()
        if register_defaults:
            for behavior in DefaultBehaviors.create_all():
                self.add_behavior(behavior)

    @property
    def behaviors(self) -> List[BehaviorOption]:
        """获取当前可用的行为选项列表 (只读副本)"""
        return list(self._behaviors)

    def add_behavior(self, behavior: BehaviorOption) -> None:
        self._behaviors.append(behavior)

    def remove_behavior(self, name: str) -> None:
        self._behaviors = [b for b in self._behaviors if b.name != name]

    def evaluate_all(self) -> List[Tuple[str, float]]:
        results: List[Tuple[str, float]] = []
        for behavior in self._behaviors:
            utility = behavior.compensated_utility()
            results.append((behavior.name, utility))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def select_best(self) -> Optional[BehaviorOption]:
        if not self._behaviors:
            return None
        evaluated = self.evaluate_all()
        best_name = evaluated[0][0]
        for behavior in self._behaviors:
            if behavior.name == best_name:
                return behavior
        return None

    def select_weighted(self) -> Optional[BehaviorOption]:
        if not self._behaviors:
            return None
        utilities = self.evaluate_all()
        weights = [u for _, u in utilities]
        total = sum(weights)
        if total <= 0.0:
            return None
        threshold = self._rng.uniform(0.0, total)
        cumulative = 0.0
        selected_name = utilities[0][0]
        for name, utility in utilities:
            cumulative += utility
            if cumulative >= threshold:
                selected_name = name
                break
        for behavior in self._behaviors:
            if behavior.name == selected_name:
                return behavior
        return None

    @property
    def behavior_count(self) -> int:
        return len(self._behaviors)

    @property
    def behaviors(self) -> Tuple[BehaviorOption, ...]:
        return tuple(self._behaviors)


class CEMPlanner:
    DEFAULT_TEMPERATURE: ClassVar[float] = _BOLTZMANN_DEFAULT_TEMPERATURE
    MIN_TEMPERATURE: ClassVar[float] = _BOLTZMANN_MIN_TEMPERATURE
    MAX_TEMPERATURE: ClassVar[float] = _BOLTZMANN_MAX_TEMPERATURE
    ADAPTATION_RATE: ClassVar[float] = _BOLTZMANN_ADAPTATION_RATE
    ENTROPY_TARGET: ClassVar[float] = _BOLTZMANN_ENTROPY_TARGET
    SELECTION_COUNT: ClassVar[int] = _CEM_SELECTION_COUNT
    COMPENSATION_FACTOR: ClassVar[float] = _CEM_COMPENSATION_FACTOR

    def __init__(
        self,
        utility_ai: Optional[UtilityBasedAI] = None,
        rng: Optional[PCGRandom] = None,
        temperature: float = _BOLTZMANN_DEFAULT_TEMPERATURE,
    ) -> None:
        self._utility_ai = utility_ai if utility_ai is not None else UtilityBasedAI(rng)
        self._rng = rng if rng is not None else PCGRandom()
        self._temperature = max(self.MIN_TEMPERATURE, min(self.MAX_TEMPERATURE, temperature))
        self._selection_history: List[str] = []

    def _compute_boltzmann_probabilities(self, utilities: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        if not utilities:
            return []
        max_utility = max(u for _, u in utilities)
        exp_values: List[Tuple[str, float]] = []
        for name, utility in utilities:
            exp_val = math.exp((utility - max_utility) / self._temperature)
            exp_values.append((name, exp_val))
        total = sum(ev for _, ev in exp_values)
        if total <= 0.0:
            count = len(utilities)
            return [(name, 1.0 / count) for name, _ in utilities]
        return [(name, ev / total) for name, ev in exp_values]

    def _compute_entropy(self, probabilities: List[Tuple[str, float]]) -> float:
        entropy = 0.0
        for _, prob in probabilities:
            if prob > 0.0:
                entropy -= prob * math.log(prob)
        max_entropy = math.log(max(len(probabilities), 1))
        if max_entropy <= 0.0:
            return 0.0
        return entropy / max_entropy

    def _adapt_temperature(self, normalized_entropy: float) -> None:
        error = self.ENTROPY_TARGET - normalized_entropy
        adjustment = error * self.ADAPTATION_RATE
        self._temperature = max(
            self.MIN_TEMPERATURE,
            min(self.MAX_TEMPERATURE, self._temperature + adjustment),
        )

    def select(self) -> Optional[BehaviorOption]:
        utilities = self._utility_ai.evaluate_all()
        if not utilities:
            return None
        probabilities = self._compute_boltzmann_probabilities(utilities)
        normalized_entropy = self._compute_entropy(probabilities)
        self._adapt_temperature(normalized_entropy)
        rand_val = self._rng.uniform(0.0, 1.0)
        cumulative = 0.0
        selected_name = probabilities[0][0]
        for name, prob in probabilities:
            cumulative += prob
            if rand_val <= cumulative:
                selected_name = name
                break
        self._selection_history.append(selected_name)
        for behavior in self._utility_ai._behaviors:
            if behavior.name == selected_name:
                return behavior
        return None

    def select_ranked(self, count: Optional[int] = None) -> List[BehaviorOption]:
        effective_count = count if count is not None else self.SELECTION_COUNT
        utilities = self._utility_ai.evaluate_all()
        probabilities = self._compute_boltzmann_probabilities(utilities)
        normalized_entropy = self._compute_entropy(probabilities)
        self._adapt_temperature(normalized_entropy)
        sorted_probs = sorted(probabilities, key=lambda x: x[1], reverse=True)
        top_names = [name for name, _ in sorted_probs[:effective_count]]
        results: List[BehaviorOption] = []
        for behavior in self._utility_ai._behaviors:
            if behavior.name in top_names:
                results.append(behavior)
        return results

    def apply_context_compensation(self, context_name: str, factor: float) -> None:
        for behavior in self._utility_ai._behaviors:
            behavior.apply_compensation(context_name, factor * self.COMPENSATION_FACTOR)

    def clear_compensations(self) -> None:
        for behavior in self._utility_ai._behaviors:
            behavior.compensations.clear()

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, value: float) -> None:
        self._temperature = max(self.MIN_TEMPERATURE, min(self.MAX_TEMPERATURE, value))

    @property
    def selection_history(self) -> List[str]:
        return list(self._selection_history)

    @property
    def utility_ai(self) -> UtilityBasedAI:
        return self._utility_ai
