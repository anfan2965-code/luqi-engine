"""
欲望驱动引擎 - 情感触发→欲望更新→目标优化驱动链
实现IDesireEngine接口，基于DesireConfig配置
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.config import DesireConfig
from luqi_engine.core.interfaces import IDesireEngine
from luqi_engine.core.types import DesireVector, EntityId

_DESIRE_UPDATE_SCALE: float = 0.1
_DESIRE_SATIATION_DECAY: float = 0.01
_DESIRE_PRIORITY_NORMALIZATION: float = 1.0
_EMOTION_SPILLOVER_FRACTION: float = 0.05

_EMOTION_DESIRE_MAP: Dict[str, Dict[str, float]] = {
    "joy": {"belonging": 0.6, "self_actualization": 0.4, "esteem": 0.2},
    "fear": {"safety": 0.8, "physiological": 0.3},
    "sorrow": {"esteem": 0.5, "belonging": 0.4, "safety": 0.2},
    "anger": {"esteem": 0.6, "safety": 0.3, "self_actualization": 0.1},
    "love": {"belonging": 0.7, "relatedness": 0.5, "physiological": 0.1},
    "desire": {"physiological": 0.6, "touch": 0.3, "taste": 0.2},
    "disgust": {"safety": 0.4, "orientation": 0.3},
    "trust": {"relatedness": 0.5, "belonging": 0.3},
    "surprise": {"orientation": 0.5, "mind": 0.3},
    "sadness": {"esteem": 0.4, "belonging": 0.5, "rootedness": 0.2},
    "anxiety": {"safety": 0.6, "orientation": 0.4},
    "hope": {"self_actualization": 0.6, "self_transcendence": 0.3},
    "curiosity": {"mind": 0.5, "sight": 0.3, "hearing": 0.2},
}

_DRIVE_CHAIN_GOAL_KEY: str = "goal"
_DRIVE_CHAIN_PRIORITY_KEY: str = "priority"
_DRIVE_CHAIN_URGENCY_KEY: str = "urgency"
_DRIVE_CHAIN_DESIRE_KEY: str = "desire_name"
_DRIVE_CHAIN_STRENGTH_KEY: str = "strength"


class DesireEngine(IDesireEngine):
    UPDATE_SCALE: ClassVar[float] = _DESIRE_UPDATE_SCALE
    SATIATION_DECAY: ClassVar[float] = _DESIRE_SATIATION_DECAY
    EMOTION_DESIRE_MAP: ClassVar[Dict[str, Dict[str, float]]] = _EMOTION_DESIRE_MAP

    def __init__(self, config: Optional[DesireConfig] = None) -> None:
        self._config = config if config is not None else DesireConfig()
        self._desires: Dict[EntityId, DesireVector] = {}
        self._satiation: Dict[EntityId, Dict[str, float]] = {}

    def _ensure_character(self, character_id: EntityId) -> DesireVector:
        if character_id not in self._desires:
            dimensions = {name: DesireVector.DIMENSION_MIN for name in self._config.desire_dimensions}
            self._desires[character_id] = DesireVector(dimensions=dimensions)
        if character_id not in self._satiation:
            self._satiation[character_id] = {name: DesireVector.DIMENSION_MIN for name in self._config.desire_dimensions}
        return self._desires[character_id]

    async def get_desires(self, character_id: EntityId) -> DesireVector:
        return self._ensure_character(character_id)

    async def update_desires(
        self,
        character_id: EntityId,
        emotion_delta: Dict[str, float],
    ) -> DesireVector:
        desires = self._ensure_character(character_id)
        satiation = self._satiation[character_id]
        has_mapping = any(key in self.EMOTION_DESIRE_MAP for key in emotion_delta)
        if has_mapping:
            targeted_dims: Dict[str, float] = {}
            for emotion_key, emotion_val in emotion_delta.items():
                dim_map = self.EMOTION_DESIRE_MAP.get(emotion_key)
                if dim_map is None:
                    continue
                for dim_name, dim_weight in dim_map.items():
                    weight = self._config.value_system_weights.get(dim_name, _DESIRE_PRIORITY_NORMALIZATION)
                    influence = emotion_val * dim_weight * self.UPDATE_SCALE * weight
                    targeted_dims[dim_name] = targeted_dims.get(dim_name, DesireVector.DIMENSION_MIN) + influence
            total_emotion = sum(emotion_delta.values())
            spillover_base = _EMOTION_SPILLOVER_FRACTION * total_emotion * self.UPDATE_SCALE
            for dim_name in self._config.desire_dimensions:
                satiation_factor = DesireVector.DIMENSION_MAX - satiation.get(dim_name, DesireVector.DIMENSION_MIN)
                if dim_name in targeted_dims:
                    delta = targeted_dims[dim_name] * satiation_factor
                else:
                    weight = self._config.value_system_weights.get(dim_name, _DESIRE_PRIORITY_NORMALIZATION)
                    delta = spillover_base * weight * satiation_factor
                current = desires.get_dimension(dim_name)
                desires.set_dimension(dim_name, current + delta)
        else:
            for dim_name in self._config.desire_dimensions:
                weight = self._config.value_system_weights.get(dim_name, _DESIRE_PRIORITY_NORMALIZATION)
                emotion_influence = sum(emotion_delta.values()) * self.UPDATE_SCALE * weight
                satiation_factor = DesireVector.DIMENSION_MAX - satiation.get(dim_name, DesireVector.DIMENSION_MIN)
                delta = emotion_influence * satiation_factor
                current = desires.get_dimension(dim_name)
                desires.set_dimension(dim_name, current + delta)
        return desires

    async def compute_drive_chain(
        self,
        character_id: EntityId,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        desires = self._ensure_character(character_id)
        satiation = self._satiation[character_id]
        ranked: List[Tuple[str, float]] = []
        for dim_name in self._config.desire_dimensions:
            desire_val = desires.get_dimension(dim_name)
            satiation_val = satiation.get(dim_name, DesireVector.DIMENSION_MIN)
            urgency = desire_val * (DesireVector.DIMENSION_MAX - satiation_val)
            weight = self._config.value_system_weights.get(dim_name, _DESIRE_PRIORITY_NORMALIZATION)
            priority = urgency * weight
            ranked.append((dim_name, priority))
        ranked.sort(key=lambda x: x[1], reverse=True)
        chain_depth = min(self._config.drive_chain_max_depth, len(ranked))
        drive_chain: List[Dict[str, Any]] = []
        for i in range(chain_depth):
            dim_name, priority = ranked[i]
            drive_chain.append({
                _DRIVE_CHAIN_GOAL_KEY: dim_name,
                _DRIVE_CHAIN_PRIORITY_KEY: priority,
                _DRIVE_CHAIN_URGENCY_KEY: ranked[i][1],
                _DRIVE_CHAIN_DESIRE_KEY: dim_name,
                _DRIVE_CHAIN_STRENGTH_KEY: desires.get_dimension(dim_name),
            })
        return {
            "character_id": character_id,
            "drive_chain": drive_chain,
            "dominant_desire": ranked[0][0] if ranked else "",
            "total_urgency": sum(p for _, p in ranked),
        }

    def apply_satiation(self, character_id: EntityId, dimension: str, amount: float) -> None:
        self._ensure_character(character_id)
        satiation = self._satiation[character_id]
        current = satiation.get(dimension, DesireVector.DIMENSION_MIN)
        satiation[dimension] = max(
            DesireVector.DIMENSION_MIN,
            min(DesireVector.DIMENSION_MAX, current + amount),
        )

    def decay_satiation(self, character_id: EntityId) -> None:
        if character_id not in self._satiation:
            return
        for dim_name in self._satiation[character_id]:
            current = self._satiation[character_id][dim_name]
            self._satiation[character_id][dim_name] = max(
                DesireVector.DIMENSION_MIN,
                current - self.SATIATION_DECAY,
            )

    def get_dominant_desire(self, character_id: EntityId) -> Optional[str]:
        if character_id not in self._desires:
            return None
        desires = self._desires[character_id]
        best_name: Optional[str] = None
        best_val = DesireVector.DIMENSION_MIN
        for dim_name in self._config.desire_dimensions:
            val = desires.get_dimension(dim_name)
            if val > best_val:
                best_val = val
                best_name = dim_name
        return best_name
