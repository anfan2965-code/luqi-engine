"""
社交感知 - 关系势能/语境保真度/干预熵值
量化角色间社交关系的动态属性
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId

_RELATIONSHIP_POTENTIAL_MIN: float = -1.0
_RELATIONSHIP_POTENTIAL_MAX: float = 1.0
_RELATIONSHIP_POTENTIAL_NEUTRAL: float = 0.0

_CONTEXT_FIDELITY_MIN: float = 0.0
_CONTEXT_FIDELITY_MAX: float = 1.0
_CONTEXT_FIDELITY_FULL: float = 1.0

_INTERVENTION_ENTROPY_MIN: float = 0.0
_INTERVENTION_ENTROPY_MAX: float = 1.0

_POTENTIAL_DECAY_RATE: float = 0.01
_FIDELITY_DECAY_RATE: float = 0.005
_ENTROPY_GROWTH_RATE: float = 0.01

_PERCEPTION_INTERACTION_WEIGHT: float = 0.3
_PERCEPTION_DISTANCE_FACTOR: float = 0.05
_DISTORTION_REMOVAL_THRESHOLD: float = 0.001
_AVERAGING_FACTOR: float = 0.5


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class RelationshipPotential:
    POTENTIAL_MIN: ClassVar[float] = _RELATIONSHIP_POTENTIAL_MIN
    POTENTIAL_MAX: ClassVar[float] = _RELATIONSHIP_POTENTIAL_MAX
    POTENTIAL_NEUTRAL: ClassVar[float] = _RELATIONSHIP_POTENTIAL_NEUTRAL
    DECAY_RATE: ClassVar[float] = _POTENTIAL_DECAY_RATE

    value: float = _RELATIONSHIP_POTENTIAL_NEUTRAL
    velocity: float = 0.0

    def update(self, delta: float) -> None:
        self.velocity += delta
        self.value = _clamp(
            self.value + self.velocity,
            self.POTENTIAL_MIN,
            self.POTENTIAL_MAX,
        )
        self.velocity *= (1.0 - self.DECAY_RATE)

    def decay(self) -> None:
        self.value = _clamp(
            self.value * (1.0 - self.DECAY_RATE),
            self.POTENTIAL_MIN,
            self.POTENTIAL_MAX,
        )
        self.velocity *= (1.0 - self.DECAY_RATE)


@dataclass
class ContextFidelity:
    FIDELITY_MIN: ClassVar[float] = _CONTEXT_FIDELITY_MIN
    FIDELITY_MAX: ClassVar[float] = _CONTEXT_FIDELITY_MAX
    DECAY_RATE: ClassVar[float] = _FIDELITY_DECAY_RATE

    value: float = _CONTEXT_FIDELITY_FULL
    distortion_sources: Dict[str, float] = field(default_factory=dict)

    def update(self, source: str, distortion: float) -> None:
        self.distortion_sources[source] = distortion
        total_distortion = sum(self.distortion_sources.values())
        self.value = _clamp(
            _CONTEXT_FIDELITY_FULL - total_distortion,
            self.FIDELITY_MIN,
            self.FIDELITY_MAX,
        )

    def remove_distortion(self, source: str) -> None:
        self.distortion_sources.pop(source, None)
        total_distortion = sum(self.distortion_sources.values())
        self.value = _clamp(
            _CONTEXT_FIDELITY_FULL - total_distortion,
            self.FIDELITY_MIN,
            self.FIDELITY_MAX,
        )

    def decay(self) -> None:
        sources_to_remove: List[str] = []
        for source, distortion in self.distortion_sources.items():
            reduced = distortion * (1.0 - self.DECAY_RATE)
            if reduced < _DISTORTION_REMOVAL_THRESHOLD:
                sources_to_remove.append(source)
            else:
                self.distortion_sources[source] = reduced
        for source in sources_to_remove:
            del self.distortion_sources[source]
        total_distortion = sum(self.distortion_sources.values())
        self.value = _clamp(
            _CONTEXT_FIDELITY_FULL - total_distortion,
            self.FIDELITY_MIN,
            self.FIDELITY_MAX,
        )


@dataclass
class InterventionEntropy:
    ENTROPY_MIN: ClassVar[float] = _INTERVENTION_ENTROPY_MIN
    ENTROPY_MAX: ClassVar[float] = _INTERVENTION_ENTROPY_MAX
    GROWTH_RATE: ClassVar[float] = _ENTROPY_GROWTH_RATE

    value: float = _INTERVENTION_ENTROPY_MIN
    intervention_count: int = 0

    def record_intervention(self) -> None:
        self.intervention_count += 1
        self.value = _clamp(
            self.value + self.GROWTH_RATE * (1.0 - self.value),
            self.ENTROPY_MIN,
            self.ENTROPY_MAX,
        )

    def reduce(self, amount: float) -> None:
        self.value = _clamp(
            self.value - amount,
            self.ENTROPY_MIN,
            self.ENTROPY_MAX,
        )

    def decay(self) -> None:
        self.value = _clamp(
            self.value * (1.0 - self.GROWTH_RATE),
            self.ENTROPY_MIN,
            self.ENTROPY_MAX,
        )


class SocialPerception:
    INTERACTION_WEIGHT: ClassVar[float] = _PERCEPTION_INTERACTION_WEIGHT
    DISTANCE_FACTOR: ClassVar[float] = _PERCEPTION_DISTANCE_FACTOR

    def __init__(self) -> None:
        self._potentials: Dict[Tuple[EntityId, EntityId], RelationshipPotential] = {}
        self._fidelities: Dict[EntityId, ContextFidelity] = {}
        self._entropies: Dict[EntityId, InterventionEntropy] = {}

    def _pair_key(self, char_a: EntityId, char_b: EntityId) -> Tuple[EntityId, EntityId]:
        return (min(char_a, char_b), max(char_a, char_b))

    def get_potential(self, char_a: EntityId, char_b: EntityId) -> RelationshipPotential:
        key = self._pair_key(char_a, char_b)
        if key not in self._potentials:
            self._potentials[key] = RelationshipPotential()
        return self._potentials[key]

    def update_potential(self, char_a: EntityId, char_b: EntityId, delta: float) -> RelationshipPotential:
        potential = self.get_potential(char_a, char_b)
        potential.update(delta * self.INTERACTION_WEIGHT)
        return potential

    def update_potential_batch(self, updates: List[Tuple[EntityId, EntityId, float]]) -> None:
        for char_a, char_b, delta in updates:
            potential = self.get_potential(char_a, char_b)
            potential.update(delta * self.INTERACTION_WEIGHT)

    def get_fidelity(self, character_id: EntityId) -> ContextFidelity:
        if character_id not in self._fidelities:
            self._fidelities[character_id] = ContextFidelity()
        return self._fidelities[character_id]

    def add_distortion(self, character_id: EntityId, source: str, amount: float) -> ContextFidelity:
        fidelity = self.get_fidelity(character_id)
        fidelity.update(source, amount)
        return fidelity

    def get_entropy(self, character_id: EntityId) -> InterventionEntropy:
        if character_id not in self._entropies:
            self._entropies[character_id] = InterventionEntropy()
        return self._entropies[character_id]

    def record_intervention(self, character_id: EntityId) -> InterventionEntropy:
        entropy = self.get_entropy(character_id)
        entropy.record_intervention()
        return entropy

    def compute_perception_score(
        self,
        char_a: EntityId,
        char_b: EntityId,
    ) -> float:
        potential = self.get_potential(char_a, char_b)
        fidelity_a = self.get_fidelity(char_a)
        fidelity_b = self.get_fidelity(char_b)
        entropy_a = self.get_entropy(char_a)
        entropy_b = self.get_entropy(char_b)
        avg_fidelity = (fidelity_a.value + fidelity_b.value) * _AVERAGING_FACTOR
        avg_entropy = (entropy_a.value + entropy_b.value) * _AVERAGING_FACTOR
        normalized_potential = (potential.value - RelationshipPotential.POTENTIAL_MIN) / (
            RelationshipPotential.POTENTIAL_MAX - RelationshipPotential.POTENTIAL_MIN
        )
        score = normalized_potential * avg_fidelity * (1.0 - avg_entropy)
        return _clamp(score, 0.0, 1.0)

    def decay_all(self) -> None:
        for potential in self._potentials.values():
            potential.decay()
        for fidelity in self._fidelities.values():
            fidelity.decay()
        for entropy in self._entropies.values():
            entropy.decay()
