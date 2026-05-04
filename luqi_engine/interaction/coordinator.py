"""
交互协调器 - IInteractionCoordinator接口实现
有向加权关系图、对话轮次分配、社交规则引擎、多角色对话协调
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple

from luqi_engine.core.config import InteractionConfig
from luqi_engine.core.interfaces import IInteractionCoordinator
from luqi_engine.core.snapshot import ISnapshotable
from luqi_engine.core.types import EntityId, generate_entity_id
from luqi_engine.core.rng import PCGRandom


_RELATIONSHIP_DIMENSION_DEFAULTS: Dict[str, float] = {
    "friendship": 0.5,
    "trust": 0.5,
    "hostility": 0.0,
    "respect": 0.5,
}

_RELATIONSHIP_VALUE_MIN: float = -1.0
_RELATIONSHIP_VALUE_MAX: float = 1.0
_RELATIONSHIP_DELTA_SCALE: float = 0.1
_RELATIONSHIP_DECAY_RATE: float = 0.01

_PRIORITY_WEIGHT_EXTRAVERSION: float = 0.15
_PRIORITY_WEIGHT_RELATIONSHIP: float = 0.25
_PRIORITY_WEIGHT_NARRATIVE: float = 0.25
_PRIORITY_WEIGHT_EMOTION: float = 0.20
_PRIORITY_COOLDOWN_PENALTY: float = 0.3
_PRIORITY_COOLDOWN_ROUNDS: int = 3
_PRIORITY_SILENCE_BONUS: float = 0.4
_PRIORITY_SILENCE_THRESHOLD: int = 5

_SOCIAL_RULE_HIERARCHY: Tuple[str, ...] = (
    "authority",
    "formality",
    "cultural_norm",
    "personal_preference",
)

_DIALOGUE_TURN_MIN_PRIORITY: float = 0.1
_DIALOGUE_CONTEXT_WINDOW: int = 50
_DIALOGUE_KEY_INFO_RETENTION: float = 0.98

_AUTHORITY_OBEYANCE_THRESHOLD: float = 0.6
_FORMALITY_MODIFIER_RANGE: float = 0.3
_CULTURAL_NORM_WEIGHT: float = 0.4

_REVERSE_RELATIONSHIP_WEIGHT: float = 0.6
_EXTRAVERSION_SCORE_DEFAULT: float = 50.0
_EXTRAVERSION_SCORE_SCALE: float = 100.0
_NARRATIVE_ROLE_DEFAULT: float = 0.5
_EMOTIONAL_URGENCY_DEFAULT: float = 0.0
_SILENCE_BONUS_RAMP_PERIOD: float = 5.0
_FORMALITY_LEVEL_DEFAULT: float = 0.5
_DIALOGUE_FRIENDSHIP_INCREMENT: float = 0.01
_SOCIAL_DISTANCE_DIMENSION_COUNT: float = 3.0

_TIME_SECONDS_TO_MS: int = 1000
_UNSET_ROUND_SENTINEL: int = -999
_DIALOGUE_MAX_ROUNDS_DEFAULT: int = 20


class SocialRuleType(Enum):
    AUTHORITY = "authority"
    FORMALITY = "formality"
    CULTURAL_NORM = "cultural_norm"
    PERSONAL_PREFERENCE = "personal_preference"


@dataclass
class RelationshipEdge:
    source_id: EntityId
    target_id: EntityId
    dimensions: Dict[str, float] = field(default_factory=dict)
    interaction_count: int = 0
    last_interaction: float = 0.0

    def get_dimension(self, name: str) -> float:
        return self.dimensions.get(name, _RELATIONSHIP_DIMENSION_DEFAULTS.get(name, 0.5))

    def set_dimension(self, name: str, value: float) -> None:
        clamped = max(_RELATIONSHIP_VALUE_MIN, min(_RELATIONSHIP_VALUE_MAX, value))
        self.dimensions[name] = clamped


@dataclass
class SocialRule:
    rule_id: str
    rule_type: SocialRuleType
    name: str
    description: str
    condition: Dict[str, Any] = field(default_factory=dict)
    modifier: Dict[str, float] = field(default_factory=dict)
    priority: int = 0
    enabled: bool = True


@dataclass
class DialogueTurn:
    speaker_id: EntityId
    content: str
    timestamp: float = field(default_factory=time.time)
    emotion_tag: str = ""
    action_tag: str = ""
    target_id: Optional[EntityId] = None


class RelationshipGraph:
    """
    有向加权关系图
    维护角色间多维度关系指标
    """

    def __init__(self, dimensions: Optional[List[str]] = None) -> None:
        self._dimensions = dimensions or list(_RELATIONSHIP_DIMENSION_DEFAULTS.keys())
        self._edges: Dict[Tuple[EntityId, EntityId], RelationshipEdge] = {}
        self._adjacency: Dict[EntityId, Set[EntityId]] = {}

    def get_edge(
        self, source: EntityId, target: EntityId,
    ) -> Optional[RelationshipEdge]:
        return self._edges.get((source, target))

    def get_or_create_edge(
        self, source: EntityId, target: EntityId,
    ) -> RelationshipEdge:
        key = (source, target)
        if key not in self._edges:
            edge = RelationshipEdge(
                source_id=source,
                target_id=target,
                dimensions={d: _RELATIONSHIP_DIMENSION_DEFAULTS.get(d, 0.5) for d in self._dimensions},
            )
            self._edges[key] = edge
            if source not in self._adjacency:
                self._adjacency[source] = set()
            self._adjacency[source].add(target)
        return self._edges[key]

    def update_edge(
        self,
        source: EntityId,
        target: EntityId,
        deltas: Dict[str, float],
    ) -> None:
        edge = self.get_or_create_edge(source, target)
        for dim, delta in deltas.items():
            current = edge.get_dimension(dim)
            edge.set_dimension(dim, current + delta * _RELATIONSHIP_DELTA_SCALE)
        edge.interaction_count += 1
        edge.last_interaction = time.time()

    def get_neighbors(self, character_id: EntityId) -> Set[EntityId]:
        return self._adjacency.get(character_id, set())

    def get_all_relationships(
        self, character_id: EntityId,
    ) -> Dict[EntityId, Dict[str, float]]:
        result: Dict[EntityId, Dict[str, float]] = {}
        for neighbor_id in self.get_neighbors(character_id):
            edge = self._edges.get((character_id, neighbor_id))
            if edge is not None:
                result[neighbor_id] = dict(edge.dimensions)
        return result

    def compute_social_distance(
        self, char_a: EntityId, char_b: EntityId,
    ) -> float:
        edge_ab = self._edges.get((char_a, char_b))
        edge_ba = self._edges.get((char_b, char_a))
        if edge_ab is None and edge_ba is None:
            return 1.0
        total = 0.0
        count = 0
        for edge in (edge_ab, edge_ba):
            if edge is not None:
                friendship = edge.get_dimension("friendship")
                trust = edge.get_dimension("trust")
                hostility = edge.get_dimension("hostility")
                total += (friendship + trust - hostility) / _SOCIAL_DISTANCE_DIMENSION_COUNT
                count += 1
        if count == 0:
            return 1.0
        avg = total / count
        return max(0.0, min(1.0, 1.0 - avg))


class SocialRulesEngine:
    """
    社交规则引擎
    应用礼仪规则、权力结构、文化习俗约束
    """

    def __init__(self) -> None:
        self._rules: Dict[str, SocialRule] = {}
        self._rule_priority_order: Dict[SocialRuleType, int] = {
            SocialRuleType.AUTHORITY: 0,
            SocialRuleType.FORMALITY: 1,
            SocialRuleType.CULTURAL_NORM: 2,
            SocialRuleType.PERSONAL_PREFERENCE: 3,
        }

    def add_rule(self, rule: SocialRule) -> None:
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    def apply_rules(
        self,
        character_id: EntityId,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        modified_action = dict(action)
        applicable_rules = self._find_applicable_rules(character_id, action, context)
        sorted_rules = sorted(
            applicable_rules,
            key=lambda r: self._rule_priority_order.get(r.rule_type, 99),
        )
        for rule in sorted_rules:
            if not rule.enabled:
                continue
            modified_action = self._apply_single_rule(modified_action, rule, context)
        return modified_action

    def _find_applicable_rules(
        self,
        character_id: EntityId,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[SocialRule]:
        applicable: List[SocialRule] = []
        for rule in self._rules.values():
            if self._is_rule_applicable(rule, character_id, action, context):
                applicable.append(rule)
        return applicable

    @staticmethod
    def _is_rule_applicable(
        rule: SocialRule,
        character_id: EntityId,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> bool:
        if not rule.enabled:
            return False
        condition = rule.condition
        if not condition:
            return True
        target_id = action.get("target_id", "")
        if rule.rule_type == SocialRuleType.AUTHORITY:
            authority_map = context.get("authority_map", {})
            char_rank = authority_map.get(character_id, 0)
            target_rank = authority_map.get(target_id, 0)
            min_rank_diff = condition.get("min_rank_difference", 0)
            if target_rank - char_rank >= min_rank_diff:
                return True
            return False
        if rule.rule_type == SocialRuleType.FORMALITY:
            formality_level = context.get("formality_level", _FORMALITY_LEVEL_DEFAULT)
            min_formality = condition.get("min_formality", 0.0)
            return formality_level >= min_formality
        if rule.rule_type == SocialRuleType.CULTURAL_NORM:
            culture_id = context.get("culture_id", "")
            required_culture = condition.get("culture_id", "")
            return culture_id == required_culture or not required_culture
        return True

    @staticmethod
    def _apply_single_rule(
        action: Dict[str, Any],
        rule: SocialRule,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        modified = dict(action)
        for key, modifier in rule.modifier.items():
            if key in modified:
                if isinstance(modified[key], (int, float)):
                    modified[key] = modified[key] + modifier
                elif isinstance(modified[key], str):
                    modified[key] = modified[key]
            else:
                modified[key] = modifier
        modified["applied_rules"] = modified.get("applied_rules", [])
        modified["applied_rules"].append(rule.rule_id)
        return modified


class InteractionCoordinator(IInteractionCoordinator, ISnapshotable):
    """
    交互协调器
    实现IInteractionCoordinator接口
    """

    def __init__(
        self,
        config: Optional[InteractionConfig] = None,
        rng: Optional[PCGRandom] = None,
    ) -> None:
        self._config = config or InteractionConfig()
        self._rng = rng or PCGRandom(seed=int(time.time() * _TIME_SECONDS_TO_MS))
        self._relationship_graph = RelationshipGraph(
            dimensions=self._config.relationship_dimensions,
        )
        self._social_rules_engine = SocialRulesEngine()
        self._dialogue_history: Dict[str, List[DialogueTurn]] = {}
        self._character_data: Dict[EntityId, Dict[str, Any]] = {}
        self._last_spoken_round: Dict[EntityId, int] = {}

    async def get_relationship(
        self,
        char_a: EntityId,
        char_b: EntityId,
    ) -> Dict[str, float]:
        edge = self._relationship_graph.get_edge(char_a, char_b)
        if edge is None:
            return {d: _RELATIONSHIP_DIMENSION_DEFAULTS.get(d, 0.5) for d in self._config.relationship_dimensions}
        return dict(edge.dimensions)

    async def update_relationship(
        self,
        char_a: EntityId,
        char_b: EntityId,
        deltas: Dict[str, float],
    ) -> None:
        self._relationship_graph.update_edge(char_a, char_b, deltas)
        reverse_deltas = {}
        for dim, delta in deltas.items():
            reverse_deltas[dim] = delta * _REVERSE_RELATIONSHIP_WEIGHT
        self._relationship_graph.update_edge(char_b, char_a, reverse_deltas)

    async def compute_speaking_priority(
        self,
        participants: List[EntityId],
        context: Dict[str, Any],
    ) -> List[Tuple[EntityId, float]]:
        current_round = context.get("round", 0)
        priorities: List[Tuple[EntityId, float]] = []
        for pid in participants:
            char_data = self._character_data.get(pid, context.get("characters", {}).get(pid, {}))
            extraversion = char_data.get("extraversion", _EXTRAVERSION_SCORE_DEFAULT) / _EXTRAVERSION_SCORE_SCALE
            extraversion_score = _PRIORITY_WEIGHT_EXTRAVERSION * extraversion
            relationship_score = self._compute_relationship_relevance(pid, participants, context)
            relationship_score *= _PRIORITY_WEIGHT_RELATIONSHIP
            narrative_role = char_data.get("narrative_role", _NARRATIVE_ROLE_DEFAULT)
            narrative_score = _PRIORITY_WEIGHT_NARRATIVE * narrative_role
            emotional_urgency = char_data.get("emotional_urgency", _EMOTIONAL_URGENCY_DEFAULT)
            emotion_score = _PRIORITY_WEIGHT_EMOTION * emotional_urgency
            total = extraversion_score + relationship_score + narrative_score + emotion_score
            last_round = self._last_spoken_round.get(pid, _UNSET_ROUND_SENTINEL)
            rounds_since = current_round - last_round
            if 0 < rounds_since <= _PRIORITY_COOLDOWN_ROUNDS:
                cooldown_factor = rounds_since / _PRIORITY_COOLDOWN_ROUNDS
                total *= cooldown_factor * _PRIORITY_COOLDOWN_PENALTY
            if rounds_since >= _PRIORITY_SILENCE_THRESHOLD:
                silence_bonus = _PRIORITY_SILENCE_BONUS * min(1.0, (rounds_since - _PRIORITY_SILENCE_THRESHOLD + 1) / _SILENCE_BONUS_RAMP_PERIOD)
                total += silence_bonus
            priorities.append((pid, total))
        priorities.sort(key=lambda p: p[1], reverse=True)
        return priorities

    def record_speaker(self, character_id: EntityId, round_num: int) -> None:
        self._last_spoken_round[character_id] = round_num

    def get_speaker_stats(self) -> Dict[EntityId, Dict[str, Any]]:
        stats: Dict[EntityId, Dict[str, Any]] = {}
        for pid in self._character_data:
            stats[pid] = {
                "last_spoken_round": self._last_spoken_round.get(pid, -1),
                "name": self._character_data[pid].get("name", ""),
            }
        return stats

    async def apply_social_rules(
        self,
        character_id: EntityId,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self._config.social_rules_enabled:
            return action
        return self._social_rules_engine.apply_rules(character_id, action, context)

    async def coordinate_dialogue(
        self,
        participants: List[EntityId],
        topic: str,
        max_rounds: int = _DIALOGUE_MAX_ROUNDS_DEFAULT,
    ) -> List[Dict[str, Any]]:
        if not participants:
            return []
        effective_max = min(max_rounds, self._config.dialogue_max_rounds)
        dialogue_key = f"dlg_{int(time.time() * 1000)}"
        self._dialogue_history[dialogue_key] = []
        dialogue_result: List[Dict[str, Any]] = []
        context: Dict[str, Any] = {
            "topic": topic,
            "participants": participants,
            "authority_map": self._build_authority_map(participants),
            "formality_level": _FORMALITY_LEVEL_DEFAULT,
            "culture_id": "",
        }
        for round_num in range(effective_max):
            priorities = await self.compute_speaking_priority(participants, context)
            if not priorities:
                break
            speaker_id, priority_score = priorities[0]
            if priority_score < _DIALOGUE_TURN_MIN_PRIORITY:
                break
            turn = DialogueTurn(
                speaker_id=speaker_id,
                content=f"[round_{round_num}] {topic}",
                emotion_tag="neutral",
            )
            self._dialogue_history[dialogue_key].append(turn)
            dialogue_result.append({
                "round": round_num,
                "speaker_id": speaker_id,
                "priority_score": priority_score,
                "topic": topic,
            })
            context["last_speaker"] = speaker_id
            context["round"] = round_num
            await self.update_relationship(
                speaker_id,
                participants[(participants.index(speaker_id) + 1) % len(participants)],
                {"friendship": _DIALOGUE_FRIENDSHIP_INCREMENT},
            )
        return dialogue_result

    async def coordinate_turn(
        self,
        participants: List[EntityId],
        context: Dict[str, Any],
    ) -> Tuple[EntityId, float, str]:
        priorities = await self.compute_speaking_priority(participants, context)
        if not priorities:
            return ("", 0.0, "")
        speaker_id, priority_score = priorities[0]
        topic_suggestion = "general_conversation"
        if "topic" in context:
            topic_suggestion = context["topic"]
        elif "last_event" in context:
            last_event = context["last_event"]
            if isinstance(last_event, dict) and "type" in last_event:
                topic_suggestion = f"event_{last_event['type']}"
            elif isinstance(last_event, str):
                topic_suggestion = f"event_{last_event}"
        return (speaker_id, priority_score, topic_suggestion)

    def register_character(
        self,
        character_id: EntityId,
        data: Dict[str, Any],
    ) -> None:
        self._character_data[character_id] = data

    def unregister_character(self, character_id: EntityId) -> None:
        self._character_data.pop(character_id, None)

    def add_social_rule(self, rule: SocialRule) -> None:
        self._social_rules_engine.add_rule(rule)

    def remove_social_rule(self, rule_id: str) -> None:
        self._social_rules_engine.remove_rule(rule_id)

    def get_social_distance(
        self, char_a: EntityId, char_b: EntityId,
    ) -> float:
        return self._relationship_graph.compute_social_distance(char_a, char_b)

    def get_character_relationships(
        self, character_id: EntityId,
    ) -> Dict[EntityId, Dict[str, float]]:
        return self._relationship_graph.get_all_relationships(character_id)

    def _compute_relationship_relevance(
        self,
        character_id: EntityId,
        participants: List[EntityId],
        context: Dict[str, Any],
    ) -> float:
        total_relevance = 0.0
        count = 0
        for pid in participants:
            if pid == character_id:
                continue
            distance = self._relationship_graph.compute_social_distance(character_id, pid)
            relevance = 1.0 - distance
            total_relevance += relevance
            count += 1
        if count == 0:
            return 0.5
        return total_relevance / count

    def _build_authority_map(
        self, participants: List[EntityId],
    ) -> Dict[EntityId, int]:
        authority_map: Dict[EntityId, int] = {}
        for pid in participants:
            char_data = self._character_data.get(pid, {})
            authority_map[pid] = char_data.get("authority_rank", 0)
        return authority_map

    def save_snapshot(self) -> Dict[str, Any]:
        edges_serialized = []
        for (source_id, target_id), edge in self._relationship_graph._edges.items():
            edges_serialized.append({
                "source_id": source_id,
                "target_id": target_id,
                "dimensions": dict(edge.dimensions),
                "interaction_count": edge.interaction_count,
                "last_interaction": edge.last_interaction,
            })
        dialogue_history_serialized = {}
        for key, turns in self._dialogue_history.items():
            dialogue_history_serialized[key] = [asdict(turn) for turn in turns]
        return {
            "relationship_edges": edges_serialized,
            "dialogue_history": dialogue_history_serialized,
            "character_data": {k: dict(v) for k, v in self._character_data.items()},
        }

    def load_snapshot(self, data: Dict[str, Any]) -> None:
        self._relationship_graph = RelationshipGraph(
            dimensions=list(_RELATIONSHIP_DIMENSION_DEFAULTS.keys()),
        )
        for edge_data in data.get("relationship_edges", []):
            source = edge_data["source_id"]
            target = edge_data["target_id"]
            edge = self._relationship_graph.get_or_create_edge(source, target)
            edge.dimensions = dict(edge_data.get("dimensions", {}))
            edge.interaction_count = edge_data.get("interaction_count", 0)
            edge.last_interaction = edge_data.get("last_interaction", 0.0)
        self._dialogue_history = {}
        for key, turns_data in data.get("dialogue_history", {}).items():
            self._dialogue_history[key] = []
            for turn_data in turns_data:
                self._dialogue_history[key].append(DialogueTurn(
                    speaker_id=turn_data["speaker_id"],
                    content=turn_data["content"],
                    timestamp=turn_data.get("timestamp", 0.0),
                    emotion_tag=turn_data.get("emotion_tag", ""),
                    action_tag=turn_data.get("action_tag", ""),
                    target_id=turn_data.get("target_id"),
                ))
        self._character_data = {}
        for char_id, char_data in data.get("character_data", {}).items():
            self._character_data[char_id] = dict(char_data)
