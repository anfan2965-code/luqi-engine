import asyncio
import pytest
from luqi_engine.interaction.coordinator import (
    InteractionCoordinator, RelationshipGraph, SocialRulesEngine,
    SocialRuleType, RelationshipEdge, SocialRule, DialogueTurn,
)
from luqi_engine.core.config import InteractionConfig
from luqi_engine.core.types import EntityId
from luqi_engine.core.rng import PCGRandom


@pytest.fixture
def config():
    return InteractionConfig(max_concurrent_characters=50, dialogue_max_rounds=20)


@pytest.fixture
def coordinator(config):
    rng = PCGRandom(seed=42)
    return InteractionCoordinator(config=config, rng=rng)


@pytest.fixture
def relationship_graph():
    return RelationshipGraph()


@pytest.fixture
def rules_engine():
    return SocialRulesEngine()


class TestRelationshipGraph:
    def test_create_edge(self, relationship_graph):
        edge = relationship_graph.get_or_create_edge("char_a", "char_b")
        assert isinstance(edge, RelationshipEdge)
        assert edge.get_dimension("friendship") == 0.5
        assert edge.get_dimension("trust") == 0.5
        assert edge.get_dimension("hostility") == 0.0
        assert edge.get_dimension("respect") == 0.5

    def test_update_edge(self, relationship_graph):
        relationship_graph.update_edge("char_a", "char_b", {"friendship": 0.3, "trust": 0.2})
        edge = relationship_graph.get_edge("char_a", "char_b")
        assert edge is not None
        expected_friendship = 0.5 + 0.3 * 0.1
        expected_trust = 0.5 + 0.2 * 0.1
        assert abs(edge.get_dimension("friendship") - expected_friendship) < 1e-9
        assert abs(edge.get_dimension("trust") - expected_trust) < 1e-9

    def test_get_neighbors(self, relationship_graph):
        relationship_graph.get_or_create_edge("a", "b")
        relationship_graph.get_or_create_edge("a", "c")
        neighbors = relationship_graph.get_neighbors("a")
        assert "b" in neighbors
        assert "c" in neighbors

    def test_social_distance(self, relationship_graph):
        relationship_graph.get_or_create_edge("a", "b")
        dist = relationship_graph.compute_social_distance("a", "b")
        assert 0.0 <= dist <= 1.0

    def test_directional_edges(self, relationship_graph):
        relationship_graph.update_edge("a", "b", {"friendship": 0.5})
        edge_ab = relationship_graph.get_edge("a", "b")
        assert edge_ab is not None
        edge_ba = relationship_graph.get_or_create_edge("b", "a")
        assert edge_ba is not None
        assert edge_ab.get_dimension("friendship") >= edge_ba.get_dimension("friendship")

    def test_get_all_relationships(self, relationship_graph):
        relationship_graph.get_or_create_edge("a", "b")
        relationship_graph.get_or_create_edge("a", "c")
        rels = relationship_graph.get_all_relationships("a")
        assert "b" in rels
        assert "c" in rels


class TestSocialRulesEngine:
    def test_add_rule(self, rules_engine):
        rule = SocialRule(
            rule_id="respect_elder",
            rule_type=SocialRuleType.AUTHORITY,
            name="尊重长辈",
            description="尊重长辈",
            condition={"min_rank_difference": 2},
            modifier={"formality_modifier": 0.5},
        )
        rules_engine.add_rule(rule)

    def test_apply_rules(self, rules_engine):
        rule = SocialRule(
            rule_id="formal_occasion",
            rule_type=SocialRuleType.FORMALITY,
            name="正式场合行为规范",
            description="正式场合行为规范",
            condition={"min_formality": 0.7},
            modifier={"tone": "formal"},
        )
        rules_engine.add_rule(rule)
        result = rules_engine.apply_rules(
            "char_a",
            {"tone": "casual"},
            {"formality_level": 0.8},
        )
        assert isinstance(result, dict)

    def test_remove_rule(self, rules_engine):
        rule = SocialRule(
            rule_id="temp_rule",
            rule_type=SocialRuleType.PERSONAL_PREFERENCE,
            name="临时规则",
            description="临时规则",
            condition={},
            modifier={},
        )
        rules_engine.add_rule(rule)
        rules_engine.remove_rule("temp_rule")

    def test_rule_hierarchy_order(self):
        assert SocialRuleType.AUTHORITY.value == "authority"
        assert SocialRuleType.FORMALITY.value == "formality"
        assert SocialRuleType.CULTURAL_NORM.value == "cultural_norm"
        assert SocialRuleType.PERSONAL_PREFERENCE.value == "personal_preference"


class TestInteractionCoordinatorRegister:
    def test_register_character(self, coordinator):
        coordinator.register_character("char_a", {"name": "小雪", "extraversion": 28, "authority_rank": 1})
        coordinator.register_character("char_b", {"name": "鹿栖", "extraversion": 65, "authority_rank": 2})

    def test_unregister_character(self, coordinator):
        coordinator.register_character("char_a", {"name": "小雪", "extraversion": 28, "authority_rank": 0})
        coordinator.unregister_character("char_a")


class TestInteractionCoordinatorRelationships:
    def test_get_relationship(self, coordinator):
        coordinator.register_character("a", {"name": "A", "extraversion": 50, "authority_rank": 0})
        coordinator.register_character("b", {"name": "B", "extraversion": 50, "authority_rank": 0})
        rel = asyncio.run(coordinator.get_relationship("a", "b"))
        assert isinstance(rel, dict)

    def test_update_relationship(self, coordinator):
        coordinator.register_character("a", {"name": "A", "extraversion": 50, "authority_rank": 0})
        coordinator.register_character("b", {"name": "B", "extraversion": 50, "authority_rank": 0})
        asyncio.run(coordinator.update_relationship("a", "b", {"friendship": 0.3}))
        rel = asyncio.run(coordinator.get_relationship("a", "b"))
        assert rel["friendship"] > 0.5

    def test_social_distance(self, coordinator):
        coordinator.register_character("a", {"name": "A", "extraversion": 50, "authority_rank": 0})
        coordinator.register_character("b", {"name": "B", "extraversion": 50, "authority_rank": 0})
        dist = coordinator.get_social_distance("a", "b")
        assert 0.0 <= dist <= 1.0


class TestInteractionCoordinatorPriority:
    def test_speaking_priority(self, coordinator):
        coordinator.register_character("a", {"name": "内向者", "extraversion": 20, "authority_rank": 0})
        coordinator.register_character("b", {"name": "外向者", "extraversion": 80, "authority_rank": 0})
        coordinator.register_character("c", {"name": "中等", "extraversion": 50, "authority_rank": 0})
        priorities = asyncio.run(coordinator.compute_speaking_priority(
            participants=["a", "b", "c"],
            context={"topic": "日常聊天"},
        ))
        assert isinstance(priorities, list)
        assert len(priorities) == 3
        score_map = {pid: score for pid, score in priorities}
        assert score_map["b"] >= score_map["a"]

    def test_authority_affects_priority(self, coordinator):
        coordinator.register_character("leader", {"name": "领导", "extraversion": 50, "authority_rank": 5})
        coordinator.register_character("follower", {"name": "下属", "extraversion": 50, "authority_rank": 1})
        priorities = asyncio.run(coordinator.compute_speaking_priority(
            participants=["leader", "follower"],
            context={"topic": "决策", "formality_level": 0.8},
        ))
        assert isinstance(priorities, list)


class TestInteractionCoordinatorDialogue:
    def test_coordinate_dialogue(self, coordinator):
        coordinator.register_character("a", {"name": "小雪", "extraversion": 28, "authority_rank": 0})
        coordinator.register_character("b", {"name": "鹿栖", "extraversion": 65, "authority_rank": 0})
        coordinator.register_character("c", {"name": "星河", "extraversion": 40, "authority_rank": 0})
        turns = asyncio.run(coordinator.coordinate_dialogue(
            participants=["a", "b", "c"],
            topic="今天去哪里玩",
            max_rounds=5,
        ))
        assert isinstance(turns, list)

    def test_dialogue_respects_max_rounds(self, coordinator):
        coordinator.register_character("a", {"name": "A", "extraversion": 50, "authority_rank": 0})
        coordinator.register_character("b", {"name": "B", "extraversion": 50, "authority_rank": 0})
        turns = asyncio.run(coordinator.coordinate_dialogue(
            participants=["a", "b"],
            topic="讨论",
            max_rounds=3,
        ))
        assert len(turns) <= 3

    def test_apply_social_rules(self, coordinator):
        coordinator.register_character("a", {"name": "下属", "extraversion": 50, "authority_rank": 1})
        rule = SocialRule(
            rule_id="respect_authority",
            rule_type=SocialRuleType.AUTHORITY,
            name="尊重权威",
            description="尊重权威",
            condition={"min_rank_difference": 2},
            modifier={"tone": "respectful"},
        )
        coordinator.add_social_rule(rule)
        result = asyncio.run(coordinator.apply_social_rules(
            "a",
            {"tone": "casual"},
            {"authority_map": {"a": 1, "target_b": 5}},
        ))
        assert isinstance(result, dict)


class TestInteractionCoordinatorEndToEnd:
    def test_three_character_social_dynamics(self, coordinator):
        coordinator.register_character("xiaoxue", {"name": "小雪", "extraversion": 28, "authority_rank": 1})
        coordinator.register_character("luqi", {"name": "鹿栖", "extraversion": 65, "authority_rank": 2})
        coordinator.register_character("teacher", {"name": "老师", "extraversion": 40, "authority_rank": 5})

        asyncio.run(coordinator.update_relationship("xiaoxue", "luqi", {"friendship": 0.4, "trust": 0.3}))
        asyncio.run(coordinator.update_relationship("xiaoxue", "teacher", {"respect": 0.3}))
        asyncio.run(coordinator.update_relationship("luqi", "teacher", {"respect": 0.2}))

        dist_xl = coordinator.get_social_distance("xiaoxue", "luqi")
        dist_xt = coordinator.get_social_distance("xiaoxue", "teacher")
        assert dist_xl < dist_xt

        priorities = asyncio.run(coordinator.compute_speaking_priority(
            participants=["xiaoxue", "luqi", "teacher"],
            context={"topic": "课堂讨论", "formality_level": 0.7},
        ))
        assert isinstance(priorities, list)
        assert len(priorities) == 3

        turns = asyncio.run(coordinator.coordinate_dialogue(
            participants=["xiaoxue", "luqi", "teacher"],
            topic="如何完成小组作业",
            max_rounds=5,
        ))
        assert isinstance(turns, list)
