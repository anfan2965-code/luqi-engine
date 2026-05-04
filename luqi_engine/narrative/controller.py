"""
剧情走向控制器 - INarrativeController接口实现
10层分支管理、三级回归引导、弹性系数、叙事一致性检查
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple

from luqi_engine.core.config import NarrativeConfig
from luqi_engine.core.interfaces import INarrativeController
from luqi_engine.core.snapshot import ISnapshotable
from luqi_engine.core.types import ActionResult, EntityId, WorldState, generate_entity_id
from luqi_engine.core.rng import PCGRandom


class NodeType(Enum):
    KEY_EVENT = auto()
    TURNING_POINT = auto()
    ENDING_CONDITION = auto()
    TRANSITION = auto()


class RegressionMethod(Enum):
    NATURAL = "natural"
    EVENT_TRIGGERED = "event_triggered"
    FORCED = "forced"


_BRANCH_STATE_ACTIVE: str = "active"
_BRANCH_STATE_MERGED: str = "merged"
_BRANCH_STATE_PRUNED: str = "pruned"
_BRANCH_STATE_DEAD_END: str = "dead_end"

_CONSISTENCY_INITIAL_CONFIDENCE: float = 1.0
_CONSISTENCY_TIMELINE_PENALTY: float = 0.7
_CONSISTENCY_CAUSALITY_PENALTY: float = 0.6
_CONSISTENCY_CHARACTER_PENALTY: float = 0.75
_CONSISTENCY_WORLD_RULE_PENALTY: float = 0.65
_CONSISTENCY_THRESHOLD: float = 0.5

_RELEVANCE_DEPTH_DECAY: float = 0.1
_RELEVANCE_DEPTH_WEIGHT: float = 0.3
_RELEVANCE_CORE_WEIGHT: float = 0.4
_RELEVANCE_TYPE_WEIGHT: float = 0.3

_TYPE_WEIGHT_KEY_EVENT: float = 0.9
_TYPE_WEIGHT_TURNING_POINT: float = 0.8
_TYPE_WEIGHT_ENDING_CONDITION: float = 0.7
_TYPE_WEIGHT_TRANSITION: float = 0.4
_TYPE_WEIGHT_DEFAULT: float = 0.5

_CHARACTER_DRIVEN_DEFAULT_SCORE: float = 0.5
_CHARACTER_PRIORITY_DEFAULT: float = 0.5

_DEVIATION_HIGH_RELEVANCE_THRESHOLD: float = 0.8
_DEVIATION_ELASTICITY_SCALE: float = 0.5
_DEVIATION_DEPTH_PENALTY_SCALE: float = 0.01
_CORE_ANCESTOR_RELEVANCE_THRESHOLD: float = 0.7
_NATURAL_REGRESSION_TOLERANCE: float = 0.9
_DEAD_END_DEPTH_RATIO: float = 0.8
_DEAD_END_RELEVANCE_THRESHOLD: float = 0.3
_CORE_STORY_KEY_EVENT_INCREMENT: float = 0.1
_CORE_STORY_ENDING_FLOOR: float = 0.9

_TIME_SECONDS_TO_MS: int = 1000


@dataclass
class StoryNode:
    node_id: EntityId
    node_type: NodeType
    name: str
    description: str
    depth: int
    parent_id: Optional[EntityId] = None
    children_ids: List[EntityId] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    core_relevance: float = 0.5
    timestamp: float = field(default_factory=time.time)
    branch_state: str = _BRANCH_STATE_ACTIVE


@dataclass
class StoryBranch:
    branch_id: EntityId
    root_node_id: EntityId
    current_node_id: EntityId
    depth: int = 0
    status: str = _BRANCH_STATE_ACTIVE
    deviation_score: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass
class RegressionResult:
    method: RegressionMethod
    target_node_id: EntityId
    success: bool
    deviation_before: float
    deviation_after: float
    narrative_event: Optional[str] = None


class NarrativeConsistencyChecker:
    """
    叙事一致性检查器
    检测剧情逻辑矛盾、时间线冲突、角色行为不一致
    """

    def check_consistency(
        self,
        story_state: Dict[str, Any],
        proposed_change: Dict[str, Any],
    ) -> Tuple[bool, float, List[str]]:
        issues: List[str] = []
        confidence = _CONSISTENCY_INITIAL_CONFIDENCE
        timeline_ok = self._check_timeline(story_state, proposed_change)
        if not timeline_ok:
            issues.append("时间线冲突：事件顺序矛盾")
            confidence *= _CONSISTENCY_TIMELINE_PENALTY
        causal_ok = self._check_causality(story_state, proposed_change)
        if not causal_ok:
            issues.append("因果链断裂：前置条件未满足")
            confidence *= _CONSISTENCY_CAUSALITY_PENALTY
        character_ok = self._check_character_consistency(story_state, proposed_change)
        if not character_ok:
            issues.append("角色行为不一致：与已建立的人设矛盾")
            confidence *= _CONSISTENCY_CHARACTER_PENALTY
        world_ok = self._check_world_rules(story_state, proposed_change)
        if not world_ok:
            issues.append("世界规则违反：与已建立的世界观设定矛盾")
            confidence *= _CONSISTENCY_WORLD_RULE_PENALTY
        return len(issues) == 0, confidence, issues

    @staticmethod
    def _check_timeline(
        story_state: Dict[str, Any], proposed_change: Dict[str, Any],
    ) -> bool:
        existing_events = story_state.get("events", [])
        new_time = proposed_change.get("timestamp", 0.0)
        prerequisites = proposed_change.get("prerequisites", [])
        for prereq_id in prerequisites:
            found = False
            for event in existing_events:
                if event.get("id") == prereq_id and event.get("timestamp", float("inf")) <= new_time:
                    found = True
                    break
            if not found and prerequisites:
                return False
        return True

    @staticmethod
    def _check_causality(
        story_state: Dict[str, Any], proposed_change: Dict[str, Any],
    ) -> bool:
        required_flags = proposed_change.get("required_flags", [])
        active_flags = story_state.get("flags", {})
        for flag in required_flags:
            if not active_flags.get(flag, False):
                return False
        return True

    @staticmethod
    def _check_character_consistency(
        story_state: Dict[str, Any], proposed_change: Dict[str, Any],
    ) -> bool:
        character_actions = proposed_change.get("character_actions", [])
        character_states = story_state.get("character_states", {})
        for action in character_actions:
            char_id = action.get("character_id", "")
            required_state = action.get("required_state", {})
            char_state = character_states.get(char_id, {})
            for key, value in required_state.items():
                if char_state.get(key) != value:
                    return False
        return True

    @staticmethod
    def _check_world_rules(
        story_state: Dict[str, Any], proposed_change: Dict[str, Any],
    ) -> bool:
        world_rules = story_state.get("world_rules", [])
        for rule in world_rules:
            rule_type = rule.get("type", "")
            if rule_type == "impossible":
                condition = rule.get("condition", {})
                matches = all(
                    proposed_change.get(k) == v for k, v in condition.items()
                )
                if matches:
                    return False
        return True


class NarrativeController(INarrativeController, ISnapshotable):
    """
    剧情走向控制器
    实现INarrativeController接口
    """

    def __init__(
        self,
        config: Optional[NarrativeConfig] = None,
        rng: Optional[PCGRandom] = None,
    ) -> None:
        self._config = config or NarrativeConfig()
        self._rng = rng or PCGRandom(seed=int(time.time() * _TIME_SECONDS_TO_MS))
        self._nodes: Dict[EntityId, StoryNode] = {}
        self._branches: Dict[EntityId, StoryBranch] = {}
        self._root_node_id: Optional[EntityId] = None
        self._current_node_id: Optional[EntityId] = None
        self._elasticity: float = self._config.elasticity_coefficient
        self._story_state: Dict[str, Any] = {
            "events": [],
            "flags": {},
            "character_states": {},
            "world_rules": [],
        }
        self._consistency_checker = NarrativeConsistencyChecker()
        self._core_story_progress: float = 0.0

    async def identify_nodes(
        self, story_state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        current = self._current_node_id
        if current is None:
            return []
        current_node = self._nodes.get(current)
        if current_node is None:
            return []
        identified: List[Dict[str, Any]] = []
        for node_id, node in self._nodes.items():
            if node.branch_state != _BRANCH_STATE_ACTIVE:
                continue
            if node.depth <= current_node.depth:
                continue
            relevance = self._compute_node_relevance(node, current_node, story_state)
            if relevance >= self._config.node_relevance_threshold:
                identified.append({
                    "node_id": node.node_id,
                    "node_type": node.node_type.name,
                    "name": node.name,
                    "description": node.description,
                    "depth": node.depth,
                    "core_relevance": node.core_relevance,
                    "relevance_to_current": relevance,
                })
        identified.sort(key=lambda n: n["relevance_to_current"], reverse=True)
        return identified

    async def compute_branch_weights(
        self,
        current_node: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, float]:
        node_id = current_node.get("node_id", "")
        node = self._nodes.get(node_id)
        if node is None:
            return {}
        weights: Dict[str, float] = {}
        for child_id in node.children_ids:
            child = self._nodes.get(child_id)
            if child is None or child.branch_state != _BRANCH_STATE_ACTIVE:
                continue
            core_score = child.core_relevance * self._config.branch_weight_core_story
            character_score = self._compute_character_driven_score(child, context) * self._config.branch_weight_character_driven
            random_score = self._rng.uniform(0.0, 1.0) * self._config.branch_weight_random_event
            elasticity_factor = (self._elasticity / self._config.elasticity_max) * self._config.branch_weight_elasticity
            deviation_bonus = max(0.0, 1.0 - child.core_relevance) * elasticity_factor
            weights[child_id] = core_score + character_score + random_score + deviation_bonus
        total = sum(weights.values())
        if total > 0.0:
            weights = {k: v / total for k, v in weights.items()}
        return weights

    async def take_branch(self, branch_id: str) -> ActionResult:
        target_node = self._nodes.get(branch_id)
        if target_node is None:
            return ActionResult(
                success=False,
                entity_id=branch_id,
                action_name="take_branch",
                error_message=f"节点不存在: {branch_id}",
            )
        if target_node.branch_state != _BRANCH_STATE_ACTIVE:
            return ActionResult(
                success=False,
                entity_id=branch_id,
                action_name="take_branch",
                error_message=f"节点不可用: {target_node.branch_state}",
            )
        is_consistent, confidence, issues = self._consistency_checker.check_consistency(
            self._story_state, target_node.state,
        )
        if not is_consistent and confidence < _CONSISTENCY_THRESHOLD:
            return ActionResult(
                success=False,
                entity_id=branch_id,
                action_name="take_branch",
                error_message=f"叙事一致性不足: {'; '.join(issues)}",
            )
        previous_node_id = self._current_node_id
        self._current_node_id = branch_id
        self._merge_story_state(target_node.state)
        self._update_core_story_progress(target_node)
        deviation = self._compute_deviation_score(target_node)
        for branch in self._branches.values():
            if branch.current_node_id == previous_node_id:
                branch.current_node_id = branch_id
                branch.deviation_score = deviation
                break
        return ActionResult(
            success=True,
            entity_id=branch_id,
            action_name="take_branch",
            state_delta=WorldState(
                flags=target_node.state.get("flags", {}),
                variables={"deviation_score": deviation, "core_progress": self._core_story_progress},
            ),
        )

    async def detect_dead_ends(
        self, story_graph: Dict[str, Any],
    ) -> List[str]:
        dead_ends: List[str] = []
        for node_id, node in self._nodes.items():
            if node.branch_state != _BRANCH_STATE_ACTIVE:
                continue
            if len(node.children_ids) == 0:
                if node.node_type != NodeType.ENDING_CONDITION:
                    dead_ends.append(node_id)
            elif self._is_effective_dead_end(node):
                dead_ends.append(node_id)
        return dead_ends

    async def guide_back(
        self,
        current_state: Dict[str, Any],
        method: str = "natural",
    ) -> ActionResult:
        regression_method = RegressionMethod(method)
        current_node = self._nodes.get(self._current_node_id or "")
        if current_node is None:
            return ActionResult(
                success=False,
                entity_id="",
                action_name="guide_back",
                error_message="无当前节点",
            )
        deviation_before = self._compute_deviation_score(current_node)
        if deviation_before < self._config.deviation_warning_threshold:
            return ActionResult(
                success=True,
                entity_id=current_node.node_id,
                action_name="guide_back",
                state_delta=WorldState(
                    variables={"deviation_score": deviation_before},
                ),
            )
        target_node = self._find_regression_target(current_node, regression_method)
        if target_node is None:
            return ActionResult(
                success=False,
                entity_id=current_node.node_id,
                action_name="guide_back",
                error_message="未找到合适的回归目标节点",
            )
        probability = self._get_regression_probability(regression_method)
        if self._rng.uniform(0.0, 1.0) > probability:
            return ActionResult(
                success=False,
                entity_id=current_node.node_id,
                action_name="guide_back",
                error_message=f"{regression_method.value}回归未成功触发",
            )
        self._current_node_id = target_node.node_id
        deviation_after = self._compute_deviation_score(target_node)
        narrative_event = self._generate_regression_event(regression_method, current_node, target_node)
        return ActionResult(
            success=True,
            entity_id=target_node.node_id,
            action_name="guide_back",
            state_delta=WorldState(
                flags={"regression_method": regression_method.value},
                variables={
                    "deviation_before": deviation_before,
                    "deviation_after": deviation_after,
                },
            ),
            side_effects=[{"event": narrative_event}] if narrative_event else [],
        )

    async def get_elasticity_coefficient(self) -> float:
        return self._elasticity

    async def set_elasticity_coefficient(self, value: float) -> None:
        self._elasticity = max(self._config.elasticity_min, min(self._config.elasticity_max, value))

    async def guide_story_step(self, context: Dict[str, Any]) -> ActionResult:
        if self._current_node_id is None:
            self.add_story_node(
                name="story_start",
                node_type=NodeType.KEY_EVENT,
                description="故事开始",
            )
        identified = await self.identify_nodes(context)
        if not identified:
            self.add_story_node(
                name="transition",
                node_type=NodeType.TRANSITION,
                description="过渡",
                parent_id=self._current_node_id,
            )
        current_node = self._nodes.get(self._current_node_id or "")
        if current_node is None:
            return ActionResult(
                success=False,
                entity_id="",
                action_name="guide_story_step",
                error_message="当前节点不存在",
            )
        current_node_dict = {
            "node_id": current_node.node_id,
            "node_type": current_node.node_type.name,
            "name": current_node.name,
            "description": current_node.description,
            "depth": current_node.depth,
            "core_relevance": current_node.core_relevance,
        }
        weights = await self.compute_branch_weights(current_node_dict, context)
        if not weights:
            return ActionResult(
                success=False,
                entity_id=self._current_node_id or "",
                action_name="guide_story_step",
                error_message="无可选分支",
            )
        best_branch = max(weights, key=lambda k: weights[k])
        return await self.take_branch(best_branch)

    def get_deviation_score(self) -> float:
        current_node = self._nodes.get(self._current_node_id or "")
        if current_node is None:
            return 0.0
        return self._compute_deviation_score(current_node)

    def add_story_node(
        self,
        name: str,
        node_type: NodeType,
        description: str = "",
        parent_id: Optional[EntityId] = None,
        core_relevance: Optional[float] = None,
        state: Optional[Dict[str, Any]] = None,
    ) -> EntityId:
        if core_relevance is None:
            core_relevance = self._config.node_relevance_threshold
        node_id = generate_entity_id("node")
        parent = self._nodes.get(parent_id) if parent_id else None
        depth = (parent.depth + 1) if parent else 0
        if depth > self._config.max_branch_depth:
            depth = self._config.max_branch_depth
        node = StoryNode(
            node_id=node_id,
            node_type=node_type,
            name=name,
            description=description,
            depth=depth,
            parent_id=parent_id,
            core_relevance=core_relevance,
            state=state or {},
        )
        self._nodes[node_id] = node
        if parent is not None:
            parent.children_ids.append(node_id)
        if self._root_node_id is None:
            self._root_node_id = node_id
            self._current_node_id = node_id
        return node_id

    def create_branch(
        self,
        from_node_id: EntityId,
        branch_name: str = "",
    ) -> Optional[EntityId]:
        from_node = self._nodes.get(from_node_id)
        if from_node is None:
            return None
        branch_id = generate_entity_id("branch")
        branch = StoryBranch(
            branch_id=branch_id,
            root_node_id=from_node_id,
            current_node_id=from_node_id,
            depth=from_node.depth,
        )
        self._branches[branch_id] = branch
        return branch_id

    def merge_branch(
        self,
        source_branch_id: EntityId,
        target_node_id: EntityId,
    ) -> bool:
        source_branch = self._branches.get(source_branch_id)
        if source_branch is None:
            return False
        target_node = self._nodes.get(target_node_id)
        if target_node is None:
            return False
        source_branch.status = _BRANCH_STATE_MERGED
        source_branch.current_node_id = target_node_id
        return True

    def prune_branch(self, branch_id: EntityId) -> bool:
        branch = self._branches.get(branch_id)
        if branch is None:
            return False
        branch.status = _BRANCH_STATE_PRUNED
        self._mark_branch_nodes_pruned(branch.root_node_id, branch.branch_id)
        return True

    def get_current_state(self) -> Dict[str, Any]:
        current_node = self._nodes.get(self._current_node_id or "")
        return {
            "current_node_id": self._current_node_id,
            "current_node_name": current_node.name if current_node else "",
            "elasticity": self._elasticity,
            "core_story_progress": self._core_story_progress,
            "total_nodes": len(self._nodes),
            "active_branches": sum(
                1 for b in self._branches.values()
                if b.status == _BRANCH_STATE_ACTIVE
            ),
            "story_state": self._story_state,
        }

    def _compute_node_relevance(
        self,
        node: StoryNode,
        current: StoryNode,
        story_state: Dict[str, Any],
    ) -> float:
        depth_diff = abs(node.depth - current.depth)
        depth_factor = 1.0 / (1.0 + depth_diff * _RELEVANCE_DEPTH_DECAY)
        core_factor = node.core_relevance
        type_factor = self._get_type_relevance_factor(node.node_type, story_state)
        return depth_factor * _RELEVANCE_DEPTH_WEIGHT + core_factor * _RELEVANCE_CORE_WEIGHT + type_factor * _RELEVANCE_TYPE_WEIGHT

    @staticmethod
    def _get_type_relevance_factor(
        node_type: NodeType, story_state: Dict[str, Any],
    ) -> float:
        type_weights: Dict[NodeType, float] = {
            NodeType.KEY_EVENT: _TYPE_WEIGHT_KEY_EVENT,
            NodeType.TURNING_POINT: _TYPE_WEIGHT_TURNING_POINT,
            NodeType.ENDING_CONDITION: _TYPE_WEIGHT_ENDING_CONDITION,
            NodeType.TRANSITION: _TYPE_WEIGHT_TRANSITION,
        }
        return type_weights.get(node_type, _TYPE_WEIGHT_DEFAULT)

    @staticmethod
    def _compute_character_driven_score(
        node: StoryNode, context: Dict[str, Any],
    ) -> float:
        character_ids = node.state.get("involved_characters", [])
        character_priorities = context.get("character_priorities", {})
        if not character_ids or not character_priorities:
            return _CHARACTER_DRIVEN_DEFAULT_SCORE
        total = sum(character_priorities.get(cid, _CHARACTER_PRIORITY_DEFAULT) for cid in character_ids)
        return min(1.0, total / max(len(character_ids), 1))

    def _compute_deviation_score(self, node: StoryNode) -> float:
        if node.core_relevance >= _DEVIATION_HIGH_RELEVANCE_THRESHOLD:
            return 0.0
        elasticity_factor = self._elasticity / self._config.elasticity_max
        deviation = (1.0 - node.core_relevance) * (1.0 - elasticity_factor * _DEVIATION_ELASTICITY_SCALE)
        depth_penalty = node.depth * self._config.dead_end_depth_penalty * _DEVIATION_DEPTH_PENALTY_SCALE
        return min(1.0, deviation + depth_penalty)

    def _find_regression_target(
        self,
        current_node: StoryNode,
        method: RegressionMethod,
    ) -> Optional[StoryNode]:
        if method == RegressionMethod.FORCED:
            return self._find_core_ancestor(current_node)
        if method == RegressionMethod.EVENT_TRIGGERED:
            return self._find_event_trigger_target(current_node)
        return self._find_natural_regression_target(current_node)

    def _find_core_ancestor(
        self, current_node: StoryNode,
    ) -> Optional[StoryNode]:
        node = current_node
        while node.parent_id is not None:
            parent = self._nodes.get(node.parent_id)
            if parent is None:
                break
            if parent.core_relevance >= _CORE_ANCESTOR_RELEVANCE_THRESHOLD:
                return parent
            node = parent
        return self._nodes.get(self._root_node_id or "")

    def _find_event_trigger_target(
        self, current_node: StoryNode,
    ) -> Optional[StoryNode]:
        for child_id in current_node.children_ids:
            child = self._nodes.get(child_id)
            if child is None:
                continue
            if child.core_relevance > current_node.core_relevance:
                return child
        return self._find_core_ancestor(current_node)

    def _find_natural_regression_target(
        self, current_node: StoryNode,
    ) -> Optional[StoryNode]:
        for child_id in current_node.children_ids:
            child = self._nodes.get(child_id)
            if child is None:
                continue
            if child.core_relevance >= current_node.core_relevance * _NATURAL_REGRESSION_TOLERANCE:
                return child
        if current_node.parent_id is not None:
            parent = self._nodes.get(current_node.parent_id)
            if parent is not None and parent.core_relevance > current_node.core_relevance:
                return parent
        return None

    def _get_regression_probability(self, method: RegressionMethod) -> float:
        probabilities: Dict[RegressionMethod, float] = {
            RegressionMethod.NATURAL: self._config.regression_probability_natural,
            RegressionMethod.EVENT_TRIGGERED: self._config.regression_probability_event_triggered,
            RegressionMethod.FORCED: self._config.regression_probability_forced,
        }
        return probabilities.get(method, self._config.regression_probability_natural)

    @staticmethod
    def _generate_regression_event(
        method: RegressionMethod,
        from_node: StoryNode,
        to_node: StoryNode,
    ) -> Optional[str]:
        event_templates: Dict[RegressionMethod, str] = {
            RegressionMethod.NATURAL: "故事自然地回到了主线：{to_name}",
            RegressionMethod.EVENT_TRIGGERED: "一个突发事件将故事引回了主线：{to_name}",
            RegressionMethod.FORCED: "命运之力将故事强行拉回正轨：{to_name}",
        }
        template = event_templates.get(method, "")
        if not template:
            return None
        return template.format(
            from_name=from_node.name,
            to_name=to_node.name,
        )

    def _is_effective_dead_end(self, node: StoryNode) -> bool:
        active_children = 0
        for child_id in node.children_ids:
            child = self._nodes.get(child_id)
            if child is not None and child.branch_state == _BRANCH_STATE_ACTIVE:
                active_children += 1
        if active_children > 0:
            return False
        if node.node_type == NodeType.ENDING_CONDITION:
            return False
        return node.depth >= self._config.max_branch_depth * _DEAD_END_DEPTH_RATIO and node.core_relevance < _DEAD_END_RELEVANCE_THRESHOLD

    def _mark_branch_nodes_pruned(
        self, root_node_id: EntityId, branch_id: EntityId,
    ) -> None:
        node = self._nodes.get(root_node_id)
        if node is None:
            return
        if node.branch_state == _BRANCH_STATE_ACTIVE:
            node.branch_state = _BRANCH_STATE_PRUNED
        for child_id in node.children_ids:
            self._mark_branch_nodes_pruned(child_id, branch_id)

    def _merge_story_state(self, new_state: Dict[str, Any]) -> None:
        flags = new_state.get("flags", {})
        self._story_state["flags"].update(flags)
        events = new_state.get("events", [])
        self._story_state["events"].extend(events)
        char_states = new_state.get("character_states", {})
        self._story_state["character_states"].update(char_states)
        world_rules = new_state.get("world_rules", [])
        self._story_state["world_rules"].extend(world_rules)

    def _update_core_story_progress(self, node: StoryNode) -> None:
        if node.node_type == NodeType.KEY_EVENT:
            self._core_story_progress += node.core_relevance * _CORE_STORY_KEY_EVENT_INCREMENT
        elif node.node_type == NodeType.ENDING_CONDITION:
            self._core_story_progress = max(self._core_story_progress, _CORE_STORY_ENDING_FLOOR)
        self._core_story_progress = min(1.0, self._core_story_progress)

    def save_snapshot(self) -> Dict[str, Any]:
        nodes_serialized = {}
        for node_id, node in self._nodes.items():
            node_dict = asdict(node)
            node_dict["node_type"] = node.node_type.name
            nodes_serialized[node_id] = node_dict
        branches_serialized = {}
        for branch_id, branch in self._branches.items():
            branches_serialized[branch_id] = asdict(branch)
        return {
            "nodes": nodes_serialized,
            "branches": branches_serialized,
            "root_node_id": self._root_node_id,
            "current_node_id": self._current_node_id,
            "elasticity": self._elasticity,
            "story_state": dict(self._story_state),
            "core_story_progress": self._core_story_progress,
        }

    def load_snapshot(self, data: Dict[str, Any]) -> None:
        self._nodes = {}
        for node_id, node_data in data.get("nodes", {}).items():
            node_type = NodeType[node_data["node_type"]]
            self._nodes[node_id] = StoryNode(
                node_id=node_data["node_id"],
                node_type=node_type,
                name=node_data["name"],
                description=node_data["description"],
                depth=node_data["depth"],
                parent_id=node_data.get("parent_id"),
                children_ids=list(node_data.get("children_ids", [])),
                state=dict(node_data.get("state", {})),
                core_relevance=node_data.get("core_relevance", 0.5),
                timestamp=node_data.get("timestamp", 0.0),
                branch_state=node_data.get("branch_state", _BRANCH_STATE_ACTIVE),
            )
        self._branches = {}
        for branch_id, branch_data in data.get("branches", {}).items():
            self._branches[branch_id] = StoryBranch(
                branch_id=branch_data["branch_id"],
                root_node_id=branch_data["root_node_id"],
                current_node_id=branch_data["current_node_id"],
                depth=branch_data.get("depth", 0),
                status=branch_data.get("status", _BRANCH_STATE_ACTIVE),
                deviation_score=branch_data.get("deviation_score", 0.0),
                created_at=branch_data.get("created_at", 0.0),
            )
        self._root_node_id = data.get("root_node_id")
        self._current_node_id = data.get("current_node_id")
        self._elasticity = data.get("elasticity", self._config.elasticity_coefficient)
        self._story_state = dict(data.get("story_state", {
            "events": [],
            "flags": {},
            "character_states": {},
            "world_rules": [],
        }))
        self._core_story_progress = data.get("core_story_progress", 0.0)
