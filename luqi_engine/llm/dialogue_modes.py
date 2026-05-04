"""
对话模式管理 - 多角色对话模式 + 单角色对话模式
单角色模式为阉割版多角色模式（省略轮次分配但保留性格/情感/记忆）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId

_OCEAN_SCORE_MIDPOINT: float = 50.0
_OCEAN_SCORE_SCALE: float = 100.0
_WEIGHT_EXTRAVERSION_FALLBACK: float = 0.3
_WEIGHT_RELATIONSHIP_RELEVANCE_FALLBACK: float = 0.25
_WEIGHT_NARRATIVE_ROLE_FALLBACK: float = 0.25
_WEIGHT_EMOTIONAL_URGENCY_FALLBACK: float = 0.2
_CHAR_DATA_RELATIONSHIP_RELEVANCE_DEFAULT: float = 0.5
_CHAR_DATA_NARRATIVE_ROLE_DEFAULT: float = 0.5
_CHAR_DATA_EMOTIONAL_URGENCY_DEFAULT: float = 0.0
_NARRATIVE_WEIGHT_DEFAULT: float = 0.5


class DialogueMode(Enum):
    MULTI_CHARACTER = "multi_character"
    SINGLE_CHARACTER = "single_character"


@dataclass
class MultiCharacterConfig:
    max_rounds: int = 20
    max_participants: int = 10
    speaking_priority_weights: Dict[str, float] = field(default_factory=lambda: {
        "personality_extraversion": 0.30,
        "relationship_relevance": 0.25,
        "narrative_role": 0.25,
        "emotional_urgency": 0.20,
    })
    turn_allocation_strategy: str = "priority"
    enable_social_rules: bool = True
    enable_relationship_tracking: bool = True
    enable_interruption: bool = False


@dataclass
class SingleCharacterConfig:
    max_history_turns: int = 30
    emotion_retention_enabled: bool = True
    personality_retention_enabled: bool = True
    memory_retention_enabled: bool = True
    desire_retention_enabled: bool = True


@dataclass
class TurnAllocation:
    character_id: EntityId
    priority_score: float
    reason: str = ""


_PRIORITY_STRATEGY: str = "priority"
_ROUND_ROBIN_STRATEGY: str = "round_robin"
_NARRATIVE_DRIVEN_STRATEGY: str = "narrative_driven"


class DialogueModes:
    """
    对话模式管理器
    支持多角色对话和单角色对话两种模式
    """

    def __init__(
        self,
        multi_config: Optional[MultiCharacterConfig] = None,
        single_config: Optional[SingleCharacterConfig] = None,
    ) -> None:
        self._multi_config = multi_config or MultiCharacterConfig()
        self._single_config = single_config or SingleCharacterConfig()

    def build_mode_instruction(
        self, mode: DialogueMode, participants: Optional[List[EntityId]] = None
    ) -> str:
        """
        根据对话模式生成模式指令
        """
        if mode == DialogueMode.MULTI_CHARACTER:
            return self._build_multi_instruction(participants or [])
        return self._build_single_instruction()

    def allocate_turns(
        self,
        mode: DialogueMode,
        participants: List[EntityId],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TurnAllocation]:
        """
        分配对话轮次
        多角色模式：基于优先级策略分配
        单角色模式：直接返回唯一角色
        """
        if mode == DialogueMode.SINGLE_CHARACTER:
            if participants:
                return [
                    TurnAllocation(
                        character_id=participants[0],
                        priority_score=1.0,
                        reason="single_character_mode",
                    )
                ]
            return []

        strategy = self._multi_config.turn_allocation_strategy
        if strategy == _PRIORITY_STRATEGY:
            return self._allocate_by_priority(participants, context or {})
        elif strategy == _ROUND_ROBIN_STRATEGY:
            return self._allocate_round_robin(participants)
        elif strategy == _NARRATIVE_DRIVEN_STRATEGY:
            return self._allocate_narrative_driven(participants, context or {})
        return self._allocate_by_priority(participants, context or {})

    def get_retained_features(self, mode: DialogueMode) -> Dict[str, bool]:
        """
        获取当前模式保留的功能特性
        """
        if mode == DialogueMode.MULTI_CHARACTER:
            return {
                "turn_allocation": True,
                "social_rules": self._multi_config.enable_social_rules,
                "relationship_tracking": self._multi_config.enable_relationship_tracking,
                "interruption": self._multi_config.enable_interruption,
                "personality": True,
                "emotion": True,
                "memory": True,
                "desire": True,
            }
        return {
            "turn_allocation": False,
            "social_rules": False,
            "relationship_tracking": False,
            "interruption": False,
            "personality": self._single_config.personality_retention_enabled,
            "emotion": self._single_config.emotion_retention_enabled,
            "memory": self._single_config.memory_retention_enabled,
            "desire": self._single_config.desire_retention_enabled,
        }

    def _build_multi_instruction(
        self, participants: List[EntityId]
    ) -> str:
        parts = [
            "当前为多角色对话模式。",
            f"参与角色数：{len(participants)}。",
            f"最大轮次：{self._multi_config.max_rounds}。",
        ]
        if self._multi_config.enable_social_rules:
            parts.append("需遵守社交规则（礼仪、权力结构、文化习俗）。")
        if self._multi_config.enable_interruption:
            parts.append("允许角色在适当时机打断对话。")
        return " ".join(parts)

    def _build_single_instruction(self) -> str:
        parts = ["当前为单角色对话模式。"]
        if self._single_config.emotion_retention_enabled:
            parts.append("保留情感反应能力。")
        if self._single_config.memory_retention_enabled:
            parts.append("保留记忆检索能力。")
        if self._single_config.personality_retention_enabled:
            parts.append("保持性格一致性。")
        return " ".join(parts)

    def _allocate_by_priority(
        self,
        participants: List[EntityId],
        context: Dict[str, Any],
    ) -> List[TurnAllocation]:
        weights = self._multi_config.speaking_priority_weights
        allocations: List[TurnAllocation] = []

        for pid in participants:
            score = 0.0
            char_data = context.get("characters", {}).get(pid, {})

            extraversion = char_data.get("extraversion", _OCEAN_SCORE_MIDPOINT) / _OCEAN_SCORE_SCALE
            score += weights.get("personality_extraversion", _WEIGHT_EXTRAVERSION_FALLBACK) * extraversion

            rel_relevance = char_data.get("relationship_relevance", _CHAR_DATA_RELATIONSHIP_RELEVANCE_DEFAULT)
            score += weights.get("relationship_relevance", _WEIGHT_RELATIONSHIP_RELEVANCE_FALLBACK) * rel_relevance

            narrative_role = char_data.get("narrative_role", _CHAR_DATA_NARRATIVE_ROLE_DEFAULT)
            score += weights.get("narrative_role", _WEIGHT_NARRATIVE_ROLE_FALLBACK) * narrative_role

            emotional_urgency = char_data.get("emotional_urgency", _CHAR_DATA_EMOTIONAL_URGENCY_DEFAULT)
            score += weights.get("emotional_urgency", _WEIGHT_EMOTIONAL_URGENCY_FALLBACK) * emotional_urgency

            allocations.append(
                TurnAllocation(
                    character_id=pid,
                    priority_score=score,
                    reason="priority_based",
                )
            )

        allocations.sort(key=lambda a: a.priority_score, reverse=True)
        return allocations

    @staticmethod
    def _allocate_round_robin(
        participants: List[EntityId],
    ) -> List[TurnAllocation]:
        return [
            TurnAllocation(
                character_id=pid,
                priority_score=1.0 - (i / max(len(participants), 1)),
                reason="round_robin",
            )
            for i, pid in enumerate(participants)
        ]

    @staticmethod
    def _allocate_narrative_driven(
        participants: List[EntityId],
        context: Dict[str, Any],
    ) -> List[TurnAllocation]:
        narrative_weights = context.get("narrative_weights", {})
        allocations = [
            TurnAllocation(
                character_id=pid,
                priority_score=narrative_weights.get(pid, _NARRATIVE_WEIGHT_DEFAULT),
                reason="narrative_driven",
            )
            for pid in participants
        ]
        allocations.sort(key=lambda a: a.priority_score, reverse=True)
        return allocations
