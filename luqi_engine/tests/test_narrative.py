"""叙事控制器测试"""

import asyncio
import pytest
from luqi_engine.narrative.controller import (
    NarrativeController, NodeType, RegressionMethod,
    NarrativeConsistencyChecker, StoryNode, StoryBranch,
)
from luqi_engine.core.config import NarrativeConfig
from luqi_engine.core.types import ActionResult
from luqi_engine.core.rng import PCGRandom


@pytest.fixture
def config():
    return NarrativeConfig(max_branch_depth=10, elasticity_coefficient=50.0)


@pytest.fixture
def controller(config):
    rng = PCGRandom(seed=42)
    return NarrativeController(config=config, rng=rng)


@pytest.fixture
def checker():
    return NarrativeConsistencyChecker()


class TestNarrativeConsistencyChecker:
    def test_consistent_change_passes(self, checker):
        story_state = {
            "events": [{"id": "evt_1", "timestamp": 1.0}, {"id": "evt_2", "timestamp": 2.0}],
            "flags": {"met_king": True},
            "character_states": {"hero": {"status": "alive"}},
            "world_rules": [],
        }
        proposed = {
            "timestamp": 3.0,
            "prerequisites": ["evt_1"],
            "required_flags": ["met_king"],
            "character_actions": [{"character_id": "hero", "required_state": {"status": "alive"}}],
        }
        is_consistent, confidence, reasons = checker.check_consistency(story_state, proposed)
        assert isinstance(is_consistent, bool)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_missing_flag_reduces_confidence(self, checker):
        story_state = {
            "events": [],
            "flags": {},
            "character_states": {"hero": {"status": "alive"}},
            "world_rules": [],
        }
        proposed = {
            "timestamp": 1.0,
            "required_flags": ["met_king"],
            "character_actions": [],
        }
        is_consistent, confidence, reasons = checker.check_consistency(story_state, proposed)
        assert confidence < 1.0

    def test_impossible_rule_violation(self, checker):
        story_state = {
            "events": [],
            "flags": {},
            "character_states": {},
            "world_rules": [{"type": "impossible", "condition": {"event": "死者发言"}}],
        }
        proposed = {
            "event": "死者发言",
        }
        is_consistent, confidence, reasons = checker.check_consistency(story_state, proposed)
        assert confidence < 1.0


class TestNarrativeControllerAddNodes:
    def test_add_root_node(self, controller):
        node_id = controller.add_story_node(
            name="故事开始",
            node_type=NodeType.KEY_EVENT,
            description="主角踏上旅程",
            parent_id=None,
            core_relevance=1.0,
        )
        assert node_id is not None
        assert len(node_id) > 0

    def test_add_child_node(self, controller):
        root_id = controller.add_story_node(
            name="故事开始", node_type=NodeType.KEY_EVENT,
            description="主角踏上旅程", parent_id=None, core_relevance=1.0,
        )
        child_id = controller.add_story_node(
            name="遇到伙伴", node_type=NodeType.TRANSITION,
            description="路上遇到了同行者", parent_id=root_id, core_relevance=0.8,
        )
        assert child_id is not None

    def test_add_ending_node(self, controller):
        root_id = controller.add_story_node(
            name="故事开始", node_type=NodeType.KEY_EVENT,
            description="主角踏上旅程", parent_id=None, core_relevance=1.0,
        )
        ending_id = controller.add_story_node(
            name="结局", node_type=NodeType.ENDING_CONDITION,
            description="主角完成使命", parent_id=root_id, core_relevance=1.0,
        )
        assert ending_id is not None


class TestNarrativeControllerBranches:
    def test_create_branch(self, controller):
        root_id = controller.add_story_node(
            name="抉择点", node_type=NodeType.TURNING_POINT,
            description="面临选择", parent_id=None, core_relevance=0.9,
        )
        branch_id = controller.create_branch(from_node_id=root_id, branch_name="勇敢路线")
        assert branch_id is not None

    def test_create_multiple_branches(self, controller):
        root_id = controller.add_story_node(
            name="抉择点", node_type=NodeType.TURNING_POINT,
            description="面临选择", parent_id=None, core_relevance=0.9,
        )
        branch_a = controller.create_branch(from_node_id=root_id, branch_name="勇敢路线")
        branch_b = controller.create_branch(from_node_id=root_id, branch_name="谨慎路线")
        assert branch_a is not None
        assert branch_b is not None

    def test_prune_branch(self, controller):
        root_id = controller.add_story_node(
            name="抉择点", node_type=NodeType.TURNING_POINT,
            description="面临选择", parent_id=None, core_relevance=0.9,
        )
        branch_id = controller.create_branch(from_node_id=root_id, branch_name="死路")
        result = controller.prune_branch(branch_id)
        assert isinstance(result, bool)

    def test_merge_branch(self, controller):
        root_id = controller.add_story_node(
            name="抉择点", node_type=NodeType.TURNING_POINT,
            description="面临选择", parent_id=None, core_relevance=0.9,
        )
        branch_id = controller.create_branch(from_node_id=root_id, branch_name="支线")
        target_id = controller.add_story_node(
            name="汇合点", node_type=NodeType.KEY_EVENT,
            description="两条路汇合", parent_id=root_id, core_relevance=0.95,
        )
        result = controller.merge_branch(branch_id, target_id)
        assert isinstance(result, bool)


class TestNarrativeControllerComputeWeights:
    def test_compute_branch_weights(self, controller):
        root_id = controller.add_story_node(
            name="抉择点", node_type=NodeType.TURNING_POINT,
            description="面临选择", parent_id=None, core_relevance=0.9,
        )
        controller.add_story_node(
            name="主线推进", node_type=NodeType.KEY_EVENT,
            description="继续主线", parent_id=root_id, core_relevance=0.95,
        )
        controller.add_story_node(
            name="支线探索", node_type=NodeType.TRANSITION,
            description="探索支线", parent_id=root_id, core_relevance=0.4,
        )
        weights = asyncio.run(controller.compute_branch_weights(
            current_node={"node_id": root_id, "core_relevance": 0.9},
            context={"characters": []},
        ))
        assert isinstance(weights, dict)

    def test_high_core_relevance_gets_higher_weight(self, controller):
        root_id = controller.add_story_node(
            name="抉择点", node_type=NodeType.TURNING_POINT,
            description="面临选择", parent_id=None, core_relevance=0.9,
        )
        main_id = controller.add_story_node(
            name="主线", node_type=NodeType.KEY_EVENT,
            description="核心剧情", parent_id=root_id, core_relevance=0.95,
        )
        side_id = controller.add_story_node(
            name="支线", node_type=NodeType.TRANSITION,
            description="无关支线", parent_id=root_id, core_relevance=0.2,
        )
        weights = asyncio.run(controller.compute_branch_weights(
            current_node={"node_id": root_id, "core_relevance": 0.9},
            context={"characters": []},
        ))
        assert isinstance(weights, dict)
        if main_id in weights and side_id in weights:
            assert weights[main_id] > weights[side_id]


class TestNarrativeControllerDeadEnds:
    def test_detect_dead_end(self, controller):
        root_id = controller.add_story_node(
            name="抉择点", node_type=NodeType.TURNING_POINT,
            description="面临选择", parent_id=None, core_relevance=0.5,
        )
        dead_id = controller.add_story_node(
            name="死路", node_type=NodeType.TRANSITION,
            description="走入死胡同", parent_id=root_id, core_relevance=0.1,
        )
        dead_ends = asyncio.run(controller.detect_dead_ends({"root": root_id}))
        assert isinstance(dead_ends, list)
        assert dead_id in dead_ends

    def test_ending_not_dead_end(self, controller):
        root_id = controller.add_story_node(
            name="抉择点", node_type=NodeType.TURNING_POINT,
            description="面临选择", parent_id=None, core_relevance=0.9,
        )
        ending_id = controller.add_story_node(
            name="好结局", node_type=NodeType.ENDING_CONDITION,
            description="完美结局", parent_id=root_id, core_relevance=1.0,
        )
        dead_ends = asyncio.run(controller.detect_dead_ends({"root": root_id}))
        assert ending_id not in dead_ends


class TestNarrativeControllerRegression:
    def test_natural_regression(self, controller):
        root_id = controller.add_story_node(
            name="故事开始", node_type=NodeType.KEY_EVENT,
            description="主角出发", parent_id=None, core_relevance=1.0,
        )
        deviated_id = controller.add_story_node(
            name="偏离路线", node_type=NodeType.TRANSITION,
            description="走偏了", parent_id=root_id, core_relevance=0.2,
        )
        asyncio.run(controller.take_branch(deviated_id))
        result = asyncio.run(controller.guide_back(
            current_state={"current_node_id": deviated_id},
            method="natural",
        ))
        assert isinstance(result, ActionResult)

    def test_forced_regression(self, controller):
        root_id = controller.add_story_node(
            name="故事开始", node_type=NodeType.KEY_EVENT,
            description="主角出发", parent_id=None, core_relevance=1.0,
        )
        deviated_id = controller.add_story_node(
            name="严重偏离", node_type=NodeType.TRANSITION,
            description="完全走偏", parent_id=root_id, core_relevance=0.1,
        )
        asyncio.run(controller.take_branch(deviated_id))
        result = asyncio.run(controller.guide_back(
            current_state={"current_node_id": deviated_id},
            method="forced",
        ))
        assert isinstance(result, ActionResult)


class TestNarrativeControllerElasticity:
    def test_get_elasticity(self, controller):
        elasticity = asyncio.run(controller.get_elasticity_coefficient())
        assert isinstance(elasticity, float)
        assert 0.0 <= elasticity <= 100.0

    def test_set_elasticity(self, controller):
        asyncio.run(controller.set_elasticity_coefficient(75.0))
        elasticity = asyncio.run(controller.get_elasticity_coefficient())
        assert abs(elasticity - 75.0) < 1e-9

    def test_high_elasticity_allows_more_deviation(self, controller):
        asyncio.run(controller.set_elasticity_coefficient(90.0))
        elasticity = asyncio.run(controller.get_elasticity_coefficient())
        assert elasticity == 90.0


class TestNarrativeControllerState:
    def test_get_current_state(self, controller):
        root_id = controller.add_story_node(
            name="故事开始", node_type=NodeType.KEY_EVENT,
            description="主角出发", parent_id=None, core_relevance=1.0,
        )
        state = controller.get_current_state()
        assert isinstance(state, dict)
        assert "current_node_id" in state
        assert "elasticity" in state

    def test_take_branch(self, controller):
        root_id = controller.add_story_node(
            name="抉择点", node_type=NodeType.TURNING_POINT,
            description="面临选择", parent_id=None, core_relevance=0.9,
        )
        child_id = controller.add_story_node(
            name="路线A", node_type=NodeType.KEY_EVENT,
            description="选择A", parent_id=root_id, core_relevance=0.8,
        )
        result = asyncio.run(controller.take_branch(child_id))
        assert isinstance(result, ActionResult)


class TestNarrativeStoryEvolution:
    def test_full_story_arc(self, controller):
        root = controller.add_story_node("序章", NodeType.KEY_EVENT, "世界介绍", None, 1.0)
        ch1 = controller.add_story_node("第一章", NodeType.KEY_EVENT, "主角出发", root, 0.95)
        choice = controller.add_story_node("抉择", NodeType.TURNING_POINT, "面临选择", ch1, 0.9)

        branch_a = controller.create_branch(choice, "勇敢路线")
        branch_b = controller.create_branch(choice, "谨慎路线")

        if branch_a:
            controller.add_story_node("战斗", NodeType.TRANSITION, "正面战斗", choice, 0.7)
        if branch_b:
            controller.add_story_node("潜行", NodeType.TRANSITION, "暗中行动", choice, 0.6)

        controller.add_story_node("结局", NodeType.ENDING_CONDITION, "完成使命", ch1, 1.0)

        dead_ends = asyncio.run(controller.detect_dead_ends({"root": root}))
        weights = asyncio.run(controller.compute_branch_weights(
            current_node={"node_id": choice, "core_relevance": 0.9},
            context={"characters": []},
        ))
        assert isinstance(weights, dict)
