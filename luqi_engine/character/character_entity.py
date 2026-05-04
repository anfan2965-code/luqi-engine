"""
角色实体 - 整合OCEAN+扩展PAD+欲望+记忆+动机的完整角色
实现完整决策循环：感知→动机评估→GOAP规划→IAUS评分→人格/情感修饰→CEM扰动→执行
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId, WorldState, ActionResult, generate_entity_id
from luqi_engine.core.config import CharacterConfig
from luqi_engine.character.personality import OceanPersonality
from luqi_engine.character.emotion import PADState, ExtendedPAD, ocean_to_pad_baseline
from luqi_engine.character.desire import DesireEngine
from luqi_engine.character.memory import MemoryStore, MemoryType, MemoryEntry
from luqi_engine.character.goap import GOAPPlanner, GOAPAction, GOAPWorldState, GOAPGoalSelector
from luqi_engine.character.utility import UtilityBasedAI, CEMPlanner, BehaviorOption, DefaultBehaviors
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

_MOTIVE_SATISFACTION_HIGH: float = 0.7
_URGENCY_SIGMOID_K: float = 10.0
_URGENCY_SIGMOID_MIDPOINT: float = 0.5
_MOTIVE_SATISFACTION_CLAMP_MIN: float = 0.0
_MOTIVE_SATISFACTION_CLAMP_MAX: float = 1.0
_MOTIVE_STRENGTH_CLAMP_MIN: float = 0.0
_MOTIVE_STRENGTH_CLAMP_MAX: float = 1.0
_DANGER_LEVEL_THRESHOLD: float = 0.7

_PERSONALITY_INFLUENCE_WEIGHTS: Dict[str, float] = {"social": 0.5, "explore": 0.3, "rest": 0.2}
_DECISION_FINAL_SCORE_SCALE: float = 0.5

_GOAP_MOTIVE_SATISFACTION_THRESHOLD: float = 0.7
_GOAP_THREAT_PLEASURE_THRESHOLD: float = -0.3
_GOAP_SUPPRESSED_AROUSAL_THRESHOLD: float = -0.2
_GOAP_DISTRESSED_PLEASURE_THRESHOLD: float = -0.2

_UTILITY_COST_FACTOR_BASE: float = 1.0

_EMOTION_MODIFIER_P_WEIGHT: float = 0.4
_EMOTION_MODIFIER_A_WEIGHT: float = 0.3
_EMOTION_MODIFIER_D_WEIGHT: float = 0.3
_EMOTION_NORMALIZATION_SCALE: float = 2.0
_EMOTION_NORMALIZATION_OFFSET: float = 1.0

_OCEAN_SCORE_SCALE: float = 100.0
_OCEAN_SCORE_DEFAULT: float = 50.0

_HP_RATIO_LOW_THRESHOLD: float = 0.3
_HP_RATIO_DEFAULT: float = 1.0
_PLEASURE_LOW_THRESHOLD: float = -0.5
_AROUSAL_HIGH_THRESHOLD: float = 0.5
_EMOTIONAL_VALENCE_LOW_THRESHOLD: float = -0.5

_PERSONALITY_CONSISTENCY_LOW_OPENNESS_RISKY: float = 0.6
_PERSONALITY_CONSISTENCY_LOW_EXTRAVERSION_SOCIAL: float = 0.7
_PERSONALITY_CONSISTENCY_HIGH_CONSCIENTIOUSNESS_CAREFUL: float = 1.0
_PERSONALITY_CONSISTENCY_DEFAULT: float = 0.9
_OCEAN_LOW_SCORE_THRESHOLD: float = 30.0
_OCEAN_HIGH_SCORE_THRESHOLD: float = 70.0

_EMOTION_CONSISTENCY_LOW_PLEASURE_FRIENDLY: float = 0.6
_EMOTION_CONSISTENCY_HIGH_AROUSAL_PASSIVE: float = 0.7
_EMOTION_CONSISTENCY_DEFAULT: float = 0.9

_MEMORY_CONSISTENCY_NEGATIVE_VALENCE_HELPFUL: float = 0.6
_MEMORY_CONSISTENCY_DEFAULT: float = 0.9
_MEMORY_NEGATIVE_VALENCE_THRESHOLD: float = -0.5

_NEARBY_ALLIES_THRESHOLD: int = 3


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
        deprivation = _MOTIVE_SATISFACTION_CLAMP_MAX - motive.current_satisfaction

        if motive.urgency_curve == _URGENCY_EXPONENTIAL:
            urgency = deprivation ** 2.0
        elif motive.urgency_curve == _URGENCY_SIGMOID:
            urgency = _UTILITY_COST_FACTOR_BASE / (_UTILITY_COST_FACTOR_BASE + math.exp(-_URGENCY_SIGMOID_K * (deprivation - _URGENCY_SIGMOID_MIDPOINT)))
        else:
            urgency = deprivation

        layer_weight = _LAYER_WEIGHTS.get(motive.layer, 1.0)
        context_mod = self._context_modifier(motive, context or {})

        strength = motive.base_intensity * urgency * layer_weight * context_mod
        return max(_MOTIVE_STRENGTH_CLAMP_MIN, min(_MOTIVE_STRENGTH_CLAMP_MAX, strength))

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
        if motive.layer == 1 and context.get("danger_level", 0.0) > _DANGER_LEVEL_THRESHOLD:
            modifier *= _MOTIVE_CONTEXT_DANGER_MODIFIER
        if motive.layer == 2 and context.get("nearby_allies", 0) > _NEARBY_ALLIES_THRESHOLD:
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
        self.desire_engine = desire_engine or DesireEngine()
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
        self._in_conversation: bool = False

    async def decide(
        self,
        context: Dict[str, Any],
        available_actions: Optional[List[GOAPAction]] = None,
        available_behaviors: Optional[List[BehaviorOption]] = None,
    ) -> Dict[str, Any]:
        """多层级决策：动机→欲望→GOAP→IAUS→CEM→性格/情感修正"""
        prioritized = self.motivation.get_prioritized_motives(context)
        if not prioritized:
            return {
                "dominant_desire": "",
                "goap_plan": [],
                "selected_action": None,
                "utility_scores": [],
            }

        primary_goal_id = prioritized[0][0]
        self._current_goal = primary_goal_id

        if available_actions:
            for action in available_actions:
                if action.name not in self.goap_planner.available_actions:
                    self.goap_planner.add_action(action)

        if available_behaviors:
            for behavior in available_behaviors:
                self.utility_ai.add_behavior(behavior)

        drive_result = await self.desire_engine.compute_drive_chain(self.entity_id, context)
        dominant_desire = drive_result.get("dominant_desire", "")

        goal_selector = GOAPGoalSelector(rng=self._rng_if_available())
        goal_state = goal_selector.select_goal(
            pad_state={"pleasure": self.emotion.pleasure, "arousal": self.emotion.arousal, "dominance": self.emotion.dominance},
            ocean_state=self.personality.to_dict() if hasattr(self.personality, "to_dict") else None,
        )
        current_state = self._get_current_world_state()
        self._current_plan = self.goap_planner.plan(current_state, goal_state)

        goap_plan_names = [a.name for a in (self._current_plan or [])]

        if not self.utility_ai.behavior_count:
            for behavior in DefaultBehaviors.create_all():
                self.utility_ai.add_behavior(behavior)

        self._bind_consideration_inputs()
        utility_scores = self.utility_ai.evaluate_all()

        selected_behavior = self.cem_planner.select()

        if selected_behavior and selected_behavior.name in ("socialize", "express"):
            self._in_conversation = True

        personality_weights = self.personality.influence_decision(
            _PERSONALITY_INFLUENCE_WEIGHTS
        )
        personality_mod = sum(personality_weights.values()) / max(len(personality_weights), 1)
        emotion_mod = self._emotion_modifier()
        final_score = _DECISION_FINAL_SCORE_SCALE * personality_mod * emotion_mod

        return {
            "dominant_desire": dominant_desire,
            "goap_plan": goap_plan_names,
            "selected_action": selected_behavior.name if selected_behavior else "",
            "utility_scores": utility_scores,
            "final_score": final_score,
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

    def _derive_pad_from_personality(self) -> PADState:
        ocean_scores: Dict[str, float] = {}
        for trait in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
            ocean_scores[trait] = self.personality.get_score(trait)
        return ocean_to_pad_baseline(ocean_scores)

    def _get_current_world_state(self) -> GOAPWorldState:
        """从PAD/OCEAN/动机状态推导GOAP世界事实"""
        facts: Dict[str, bool] = {}
        for mid, motive in self.motivation.motives.items():
            facts[f"motive_{mid}_satisfied"] = motive.current_satisfaction >= _GOAP_MOTIVE_SATISFACTION_THRESHOLD
        p = self.emotion.pleasure if hasattr(self.emotion, 'pleasure') else 0.0
        a = self.emotion.arousal if hasattr(self.emotion, 'arousal') else 0.0
        d = self.emotion.dominance if hasattr(self.emotion, 'dominance') else 0.0
        facts["is_alone"] = not getattr(self, '_in_conversation', False)
        facts["threat_present"] = p < _GOAP_THREAT_PLEASURE_THRESHOLD
        facts["emotion_suppressed"] = a < _GOAP_SUPPRESSED_AROUSAL_THRESHOLD
        facts["has_memory"] = hasattr(self, 'memory') and self.memory.size() > 0 if hasattr(self, 'memory') and hasattr(self.memory, 'size') else False
        facts["other_distressed"] = p < _GOAP_DISTRESSED_PLEASURE_THRESHOLD
        facts["conversation_started"] = getattr(self, '_in_conversation', False)
        return GOAPWorldState(data=facts)

    def _emotion_modifier(self) -> float:
        p = (self.emotion.pleasure + _EMOTION_NORMALIZATION_OFFSET) / _EMOTION_NORMALIZATION_SCALE
        a = (self.emotion.arousal + _EMOTION_NORMALIZATION_OFFSET) / _EMOTION_NORMALIZATION_SCALE
        d = (self.emotion.dominance + _EMOTION_NORMALIZATION_OFFSET) / _EMOTION_NORMALIZATION_SCALE
        return _EMOTION_MODIFIER_P_WEIGHT * p + _EMOTION_MODIFIER_A_WEIGHT * a + _EMOTION_MODIFIER_D_WEIGHT * d

    def _rng_if_available(self):
        try:
            from luqi_engine.core.rng import PCGRandom
            return PCGRandom()
        except Exception as exc:
            _logger.debug("PCGRandom不可用，降级为None: %s", exc)
            return None

    def _bind_consideration_inputs(self) -> None:
        """将PAD/OCEAN运行时值绑定到UtilityBasedAI的Consideration.input_fn"""
        ocean = self.personality.to_dict() if hasattr(self.personality, "to_dict") else {}
        p = self.emotion.pleasure if hasattr(self.emotion, "pleasure") else 0.0
        a = self.emotion.arousal if hasattr(self.emotion, "arousal") else 0.0
        d = self.emotion.dominance if hasattr(self.emotion, "dominance") else 0.0
        input_map: Dict[str, Callable[[], float]] = {
            "extraversion": lambda: ocean.get("extraversion", _OCEAN_SCORE_DEFAULT) / _OCEAN_SCORE_SCALE,
            "arousal": lambda: (a + _EMOTION_NORMALIZATION_OFFSET) / _EMOTION_NORMALIZATION_SCALE,
            "openness": lambda: ocean.get("openness", _OCEAN_SCORE_DEFAULT) / _OCEAN_SCORE_SCALE,
            "pleasure": lambda: (p + _EMOTION_NORMALIZATION_OFFSET) / _EMOTION_NORMALIZATION_SCALE,
            "neuroticism": lambda: ocean.get("neuroticism", _OCEAN_SCORE_DEFAULT) / _OCEAN_SCORE_SCALE,
            "safety_urgency": lambda: max(_MOTIVE_STRENGTH_CLAMP_MIN, -p),
            "conscientiousness": lambda: ocean.get("conscientiousness", _OCEAN_SCORE_DEFAULT) / _OCEAN_SCORE_SCALE,
            "dominance": lambda: (d + _EMOTION_NORMALIZATION_OFFSET) / _EMOTION_NORMALIZATION_SCALE,
            "low_pleasure": lambda: max(_MOTIVE_STRENGTH_CLAMP_MIN, -p),
            "high_arousal": lambda: max(_MOTIVE_STRENGTH_CLAMP_MIN, a),
        }
        for behavior in self.utility_ai._behaviors:
            for consideration in behavior.considerations:
                if consideration.name in input_map:
                    consideration.input_fn = input_map[consideration.name]

    def _personality_consistency(self, action: Dict[str, Any]) -> float:
        """根据OCEAN特质评估行动的性格一致性(0-1)"""
        action_type = action.get("type", "general")
        p = self.personality
        if action_type == "risky" and p.get_score("openness") < _OCEAN_LOW_SCORE_THRESHOLD:
            return _PERSONALITY_CONSISTENCY_LOW_OPENNESS_RISKY
        if action_type == "social" and p.get_score("extraversion") < _OCEAN_LOW_SCORE_THRESHOLD:
            return _PERSONALITY_CONSISTENCY_LOW_EXTRAVERSION_SOCIAL
        if action_type == "careful" and p.get_score("conscientiousness") > _OCEAN_HIGH_SCORE_THRESHOLD:
            return _PERSONALITY_CONSISTENCY_HIGH_CONSCIENTIOUSNESS_CAREFUL
        return _PERSONALITY_CONSISTENCY_DEFAULT

    def _emotion_consistency(self, action: Dict[str, Any]) -> float:
        """根据PAD情感状态评估行动的情感一致性(0-1)"""
        if self.emotion.pleasure < _PLEASURE_LOW_THRESHOLD and action.get("type") == "friendly":
            return _EMOTION_CONSISTENCY_LOW_PLEASURE_FRIENDLY
        if self.emotion.arousal > _AROUSAL_HIGH_THRESHOLD and action.get("type") == "passive":
            return _EMOTION_CONSISTENCY_HIGH_AROUSAL_PASSIVE
        return _EMOTION_CONSISTENCY_DEFAULT

    def _memory_consistency(self, action: Dict[str, Any]) -> float:
        """根据记忆中的情感效价评估行动的记忆一致性(0-1)"""
        target = action.get("target", "")
        if target:
            memories = self.memory.retrieve(query=target, limit=5)
            for mem in memories:
                if mem.emotional_valence < _MEMORY_NEGATIVE_VALENCE_THRESHOLD and action.get("type") == "helpful":
                    return _MEMORY_CONSISTENCY_NEGATIVE_VALENCE_HELPFUL
        return _MEMORY_CONSISTENCY_DEFAULT
