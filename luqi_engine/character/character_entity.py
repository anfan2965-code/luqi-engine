"""
角色实体 - 整合OCEAN+扩展PAD+欲望+记忆+动机的完整角色
实现完整决策循环：感知→动机评估→GOAP规划→IAUS评分→人格/情感修饰→CEM扰动→执行
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId, WorldState, ActionResult, generate_entity_id
from luqi_engine.core.config import CharacterConfig
from luqi_engine.character.personality import OceanPersonality
from luqi_engine.character.emotion import PADState, ExtendedPAD, ocean_to_pad_baseline
from luqi_engine.character.desire import DesireEngine
from luqi_engine.character.memory import MemoryStore, MemoryType, MemoryEntry
from luqi_engine.character.goap import GOAPPlanner, GOAPAction, GOAPWorldState
from luqi_engine.character.utility import UtilityBasedAI, CEMPlanner, BehaviorOption
from luqi_engine.character.social_perception import SocialPerception

_URGENCY_EXPONENTIAL: str = "exponential"
_URGENCY_SIGMOID: str = "sigmoid"
_URGENCY_LINEAR: str = "linear"

_LAYER_WEIGHTS: Dict[int, float] = {1: 3.0, 2: 2.0, 3: 1.0}
_LAYER_NAMES: Dict[int, str] = {1: "生存", 2: "社交", 3: "自我实现"}

_MOTIVE_SATIATION_DECAY: float = 0.001
_MOTIVE_CONTEXT_DANGER_MODIFIER: float = 1.5
_MOTIVE_SOCIAL_MODIFIER: float = 1.2

_CONSISTENCY_THRESHOLD: float = 0.95
_CONSISTENCY_WEIGHT_PERSONALITY: float = 0.4
_CONSISTENCY_WEIGHT_EMOTION: float = 0.3
_CONSISTENCY_WEIGHT_MEMORY: float = 0.3


@dataclass
class Motive:
    motive_id: str
    name: str
    layer: int
    base_intensity: float
    decay_rate: float = _MOTIVE_SATIATION_DECAY
    urgency_curve: str = _URGENCY_SIGMOID
    current_satisfaction: float = 0.5


class MotivationEngine:
    """
    三层动机引擎
    生存/社交/自我实现层级结构
    非线性紧迫性曲线
    """

    def __init__(self, motives: Optional[List[Motive]] = None) -> None:
        self._motives: Dict[str, Motive] = {}
        if motives:
            for m in motives:
                self._motives[m.motive_id] = m

    def add_motive(self, motive: Motive) -> None:
        self._motives[motive.motive_id] = motive

    def calculate_drive_strength(
        self, motive: Motive, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        计算动机驱动力强度
        使用非线性紧迫性曲线
        """
        deprivation = 1.0 - motive.current_satisfaction

        if motive.urgency_curve == _URGENCY_EXPONENTIAL:
            urgency = deprivation ** 2.0
        elif motive.urgency_curve == _URGENCY_SIGMOID:
            k = 10.0
            urgency = 1.0 / (1.0 + math.exp(-k * (deprivation - 0.5)))
        else:
            urgency = deprivation

        layer_weight = _LAYER_WEIGHTS.get(motive.layer, 1.0)
        context_mod = self._context_modifier(motive, context or {})

        strength = motive.base_intensity * urgency * layer_weight * context_mod
        return max(0.0, min(1.0, strength))

    def get_prioritized_motives(
        self, context: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, float]]:
        """
        获取按优先级排序的动机列表
        """
        scored = [
            (m.motive_id, self.calculate_drive_strength(m, context))
            for m in self._motives.values()
        ]
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def update_satisfaction(
        self, motive_id: str, delta: float
    ) -> None:
        if motive_id in self._motives:
            m = self._motives[motive_id]
            m.current_satisfaction = max(
                0.0, min(1.0, m.current_satisfaction + delta)
            )

    def decay_all(self, delta_time: float) -> None:
        for m in self._motives.values():
            m.current_satisfaction = max(
                0.0,
                m.current_satisfaction - m.decay_rate * delta_time,
            )

    @staticmethod
    def _context_modifier(
        motive: Motive, context: Dict[str, Any]
    ) -> float:
        modifier = 1.0
        if motive.layer == 1 and context.get("danger_level", 0.0) > 0.7:
            modifier *= _MOTIVE_CONTEXT_DANGER_MODIFIER
        if motive.layer == 2 and context.get("nearby_allies", 0) > 3:
            modifier *= _MOTIVE_SOCIAL_MODIFIER
        return modifier

    @property
    def motives(self) -> Dict[str, Motive]:
        return self._motives


class CharacterEntity:
    """
    完整角色实体
    整合人格/情感/欲望/记忆/动机/规划/效用/熵最大化
    """

    def __init__(
        self,
        entity_id: Optional[EntityId] = None,
        name: str = "",
        personality: Optional[OceanPersonality] = None,
        emotion: Optional[PADState] = None,
        extended_emotion: Optional[ExtendedPAD] = None,
        desire_engine: Optional[DesireEngine] = None,
        memory: Optional[MemoryStore] = None,
        motivation: Optional[MotivationEngine] = None,
        goap_planner: Optional[GOAPPlanner] = None,
        utility_ai: Optional[UtilityBasedAI] = None,
        cem_planner: Optional[CEMPlanner] = None,
        social_perception: Optional[SocialPerception] = None,
        config: Optional[CharacterConfig] = None,
    ) -> None:
        self.entity_id = entity_id or generate_entity_id("char")
        self.name = name
        self._config = config or CharacterConfig()

        self.personality = personality or OceanPersonality()
        self.emotion = emotion or self._derive_pad_from_personality()
        self.extended_emotion = extended_emotion or ExtendedPAD(pad_state=self.emotion)
        self.desire_engine = desire_engine or DesireEngine(self.entity_id)
        self.memory = memory or MemoryStore(config=self._config)
        self.motivation = motivation or MotivationEngine()
        self.goap_planner = goap_planner or GOAPPlanner(actions=[])
        self.utility_ai = utility_ai or UtilityBasedAI()
        self.cem_planner = cem_planner or CEMPlanner()
        self.social_perception = social_perception or SocialPerception()

        self._current_goal: Optional[str] = None
        self._current_plan: Optional[List[GOAPAction]] = None
        self._position: Optional[Dict[str, float]] = None
        self._state: Dict[str, Any] = {}

    async def decide(
        self,
        context: Dict[str, Any],
        available_actions: Optional[List[GOAPAction]] = None,
        available_behaviors: Optional[List[BehaviorOption]] = None,
    ) -> Optional[GOAPAction]:
        """
        完整决策循环
        感知→动机评估→GOAP规划→IAUS评分→人格/情感修饰→CEM扰动→执行
        """
        prioritized = self.motivation.get_prioritized_motives(context)

        primary_goal_id = ""
        chosen_action = None
        action_utilities: Dict[GOAPAction, float] = {}

        if prioritized:
            primary_goal_id = prioritized[0][0]
            self._current_goal = primary_goal_id

        if available_actions:
            self.goap_planner = GOAPPlanner(actions=available_actions)

        if available_behaviors:
            self.utility_ai = UtilityBasedAI(behaviors=available_behaviors)

        if self.goap_planner.actions and primary_goal_id:
            goal_state = self._translate_motive_to_goal(primary_goal_id)
            current_state = self._get_current_world_state()
            self._current_plan = self.goap_planner.plan(current_state, goal_state)

        if self._current_plan and len(self._current_plan) > 0:
            next_action = self._current_plan[0]

            base_score = 0.5
            if self.utility_ai.behaviors:
                base_score = self._evaluate_action_utility(next_action, context)

            personality_mod = self.personality.influence_decision(
                base_score, self._classify_action_type(next_action)
            )

            emotion_mod = self._emotion_modifier()

            final_score = base_score * personality_mod * emotion_mod

            action_utilities = {next_action: final_score}
            chosen_action = self.cem_planner.select_action_with_entropy(
                action_utilities,
                temperature=self._adaptive_temperature(context),
            )

        return {
            "dominant_desire": primary_goal_id,
            "selected_action": chosen_action,
            "goap_plan": list(self._current_plan) if self._current_plan else [],
            "utility_scores": {a.name: s for a, s in action_utilities.items()},
        }

    def validate_behavior_consistency(
        self, proposed_action: Dict[str, Any]
    ) -> Tuple[bool, float]:
        """
        验证行为是否符合性格设定
        返回: (是否一致, 一致性分数0-1)
        目标: 一致性概率>=95%
        """
        score = 0.0

        personality_score = self._personality_consistency(proposed_action)
        emotion_score = self._emotion_consistency(proposed_action)
        memory_score = self._memory_consistency(proposed_action)

        score = (
            personality_score * _CONSISTENCY_WEIGHT_PERSONALITY
            + emotion_score * _CONSISTENCY_WEIGHT_EMOTION
            + memory_score * _CONSISTENCY_WEIGHT_MEMORY
        )

        is_consistent = score >= _CONSISTENCY_THRESHOLD
        return is_consistent, score

    def on_event(self, event: Dict[str, Any]) -> None:
        """
        处理外部事件
        更新情感、欲望、记忆
        """
        emotion_impact = event.get("emotion_impact", {})
        if emotion_impact:
            self.emotion.update_from_dict(emotion_impact, self.personality)

        desire_trigger = event.get("desire_trigger", {})
        if desire_trigger:
            self.desire_engine.update_desires(self.entity_id, desire_trigger)

        memory_data = event.get("memory", {})
        if memory_data:
            entry = MemoryEntry(
                who=memory_data.get("who", ""),
                what=memory_data.get("what", ""),
                when=memory_data.get("when", time.time()),
                where=memory_data.get("where", ""),
                why=memory_data.get("why", ""),
                emotional_valence=memory_data.get("emotional_valence", 0.0),
            )
            mtype_str = memory_data.get("memory_type", "short_term")
            mtype = MemoryType(mtype_str) if mtype_str in [mt.value for mt in MemoryType] else MemoryType.SHORT_TERM
            self.memory.store(entry, mtype)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "personality": self.personality.to_dict() if hasattr(self.personality, "to_dict") else {},
            "emotion": {
                "pleasure": self.emotion.pleasure,
                "arousal": self.emotion.arousal,
                "dominance": self.emotion.dominance,
            },
            "current_goal": self._current_goal,
            "state": self._state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CharacterEntity:
        return cls(
            entity_id=data.get("entity_id"),
            name=data.get("name", ""),
        )

    def _translate_motive_to_goal(self, motive_id: str) -> GOAPWorldState:
        return GOAPWorldState(data={f"motive_{motive_id}_satisfied": True})

    def _derive_pad_from_personality(self) -> PADState:
        ocean_scores: Dict[str, float] = {}
        for trait in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
            ocean_scores[trait] = self.personality.get_score(trait)
        return ocean_to_pad_baseline(ocean_scores)

    def _get_current_world_state(self) -> GOAPWorldState:
        facts: Dict[str, bool] = {}
        for mid, motive in self.motivation.motives.items():
            facts[f"motive_{mid}_satisfied"] = motive.current_satisfaction >= 0.7
        return GOAPWorldState(data=facts)

    @staticmethod
    def _classify_action_type(action: GOAPAction) -> str:
        name = action.name.lower()
        if any(k in name for k in ["attack", "fight", "flee", "defend"]):
            return "risky_action"
        if any(k in name for k in ["talk", "chat", "greet", "negotiate"]):
            return "social_interaction"
        if any(k in name for k in ["plan", "prepare", "organize"]):
            return "careful_planning"
        if any(k in name for k in ["create", "invent", "experiment"]):
            return "creative_solution"
        return "general_action"

    def _evaluate_action_utility(
        self, action: GOAPAction, context: Dict[str, Any]
    ) -> float:
        cost_factor = 1.0 / (1.0 + action.cost)
        goal_relevance = 1.0 if self._current_goal else 0.5
        context_bonus = context.get("action_bonus", 0.0)
        return cost_factor * goal_relevance + context_bonus

    def _emotion_modifier(self) -> float:
        p = (self.emotion.pleasure + 1.0) / 2.0
        a = (self.emotion.arousal + 1.0) / 2.0
        d = (self.emotion.dominance + 1.0) / 2.0
        return 0.4 * p + 0.3 * a + 0.3 * d

    @staticmethod
    def _adaptive_temperature(context: Dict[str, Any]) -> float:
        base = 1.0
        if context.get("in_combat"):
            base *= 0.5
        if context.get("is_safe_zone"):
            base *= 1.5
        if context.get("hp_ratio", 1.0) < 0.3:
            base *= 0.7
        return base

    def _personality_consistency(self, action: Dict[str, Any]) -> float:
        action_type = action.get("type", "general")
        p = self.personality
        if action_type == "risky" and p.get_score("openness") < 30:
            return 0.6
        if action_type == "social" and p.get_score("extraversion") < 30:
            return 0.7
        if action_type == "careful" and p.get_score("conscientiousness") > 70:
            return 1.0
        return 0.9

    def _emotion_consistency(self, action: Dict[str, Any]) -> float:
        if self.emotion.pleasure < -0.5 and action.get("type") == "friendly":
            return 0.6
        if self.emotion.arousal > 0.5 and action.get("type") == "passive":
            return 0.7
        return 0.9

    def _memory_consistency(self, action: Dict[str, Any]) -> float:
        target = action.get("target", "")
        if target:
            memories = self.memory.retrieve(query=target, limit=5)
            for mem in memories:
                if mem.emotional_valence < -0.5 and action.get("type") == "helpful":
                    return 0.6
        return 0.9
