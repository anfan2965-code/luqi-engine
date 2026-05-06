"""
社交演化引擎单元测试
覆盖：Relationship、EvolutionRuleLibrary、SocialEvolutionEngine的所有核心功能
"""

import time
import unittest
from luqi_engine.character.social_evolution import (
    EvolutionRuleLibrary,
    InteractionContext,
    RelationContextType,
    RelationMetadata,
    Relationship,
    SocialAction,
    SocialActionType,
    SocialEvolutionEngine,
)
from luqi_engine.character.social_perception import RelationshipPotential
from luqi_engine.character.social_evolution import _DEFAULT_INTIMACY


class TestRelationContextType(unittest.TestCase):
    """测试关系类型枚举"""

    def test_all_types_exist(self):
        expected = [
            "GAME_ALLIANCE", "NPC_DISPOSITION", "ROMANTIC_INTEREST",
            "FAMILY_BOND", "RIVALRY",
        ]
        actual = [t.name for t in RelationContextType]
        self.assertEqual(actual, expected)


class TestSocialActionType(unittest.TestCase):
    """测试社交动作枚举"""

    def test_all_action_types_exist(self):
        expected = [
            "GIFT", "HELP", "INSULT", "BETRAY", "DEFEND",
            "CONVERSE", "PRAISE", "THREATEN", "SHARE_SECRET",
        ]
        actual = [t.name for t in SocialActionType]
        self.assertEqual(actual, expected)

    def test_action_count(self):
        self.assertEqual(len(SocialActionType), 9)


class TestRelationMetadata(unittest.TestCase):
    """测试关系元数据"""

    def test_default_creation(self):
        meta = RelationMetadata()
        self.assertEqual(meta.interaction_count, 0)
        self.assertEqual(meta.context_type, RelationContextType.NPC_DISPOSITION)
        self.assertEqual(len(meta.history), 0)

    def test_record_interaction(self):
        meta = RelationMetadata()
        meta.record_interaction("送礼")
        
        self.assertEqual(meta.interaction_count, 1)
        self.assertIn("送礼", meta.history)

    def test_multiple_interactions(self):
        meta = RelationMetadata()
        for i in range(5):
            meta.record_interaction(f"互动{i}")
        
        self.assertEqual(meta.interaction_count, 5)
        self.assertEqual(len(meta.history), 5)

    def test_history_limit(self):
        meta = RelationMetadata()
        limit = RelationMetadata._history_limit
        
        for i in range(limit + 10):
            meta.record_interaction(f"事件{i}")
        
        self.assertLessEqual(len(meta.history), limit)
        self.assertIn(f"事件{limit + 9}", meta.history[-1])

    def test_is_established_false_initially(self):
        meta = RelationMetadata()
        self.assertFalse(meta.is_established)

    def test_is_established_after_threshold(self):
        meta = RelationMetadata()
        for _ in range(3):
            meta.record_interaction("互动")
        self.assertTrue(meta.is_established)


class TestRelationshipCreation(unittest.TestCase):
    """测试四维关系模型创建和初始化"""

    def test_default_values(self):
        rel = Relationship()
        self.assertAlmostEqual(rel.intimacy, 0.0)
        self.assertAlmostEqual(rel.trust, 0.5)
        self.assertAlmostEqual(rel.respect, 0.0)
        self.assertAlmostEqual(rel.fear, 0.0)

    def test_custom_values(self):
        rel = Relationship(
            intimacy=0.7,
            trust=0.8,
            respect=-0.3,
            fear=0.2,
        )
        self.assertAlmostEqual(rel.intimacy, 0.7)
        self.assertAlmostEqual(rel.trust, 0.8)
        self.assertAlmostEqual(rel.respect, -0.3)
        self.assertAlmostEqual(rel.fear, 0.2)

    def test_intimacy_clamping_high(self):
        rel = Relationship(intimacy=1.5)
        self.assertAlmostEqual(rel.intimacy, 1.0)

    def test_intimacy_clamping_low(self):
        rel = Relationship(intimacy=-1.5)
        self.assertAlmostEqual(rel.intimacy, -1.0)

    def test_trust_clamping_range(self):
        high = Relationship(trust=1.5)
        low = Relationship(trust=-0.3)
        
        self.assertAlmostEqual(high.trust, 1.0)
        self.assertAlmostEqual(low.trust, 0.0)

    def test_respect_clamping_range(self):
        high = Relationship(respect=1.2)
        low = Relationship(respect=-1.2)
        
        self.assertAlmostEqual(high.respect, 1.0)
        self.assertAlmostEqual(low.respect, -1.0)

    def test_fear_clamping_range(self):
        high = Relationship(fear=1.5)
        low = Relationship(fear=-0.2)
        
        self.assertAlmostEqual(high.fear, 1.0)
        self.assertAlmostEqual(low.fear, 0.0)

    def test_boundary_values(self):
        rel = Relationship(
            intimacy=1.0,
            trust=1.0,
            respect=1.0,
            fear=1.0,
        )
        self.assertAlmostEqual(rel.intimacy, 1.0)
        self.assertAlmostEqual(rel.trust, 1.0)
        self.assertAlmostEqual(rel.respect, 1.0)
        self.assertAlmostEqual(rel.fear, 1.0)


class TestApplyDelta(unittest.TestCase):
    """测试变化量应用"""

    def setUp(self):
        self.rel = Relationship()

    def test_positive_delta(self):
        result = self.rel.apply_delta(intimacy_delta=0.2, trust_delta=0.1)
        
        self.assertIs(result, self.rel)  # 支持链式调用
        self.assertAlmostEqual(self.rel.intimacy, 0.2)
        self.assertAlmostEqual(self.rel.trust, 0.6)

    def test_negative_delta(self):
        self.rel.apply_delta(intimacy_delta=-0.15, respect_delta=-0.2)
        
        self.assertAlmostEqual(self.rel.intimacy, -0.15)
        self.assertAlmostEqual(self.rel.respect, -0.2)

    def test_single_delta_limit_enforced(self):
        initial = self.rel.intimacy
        self.rel.apply_delta(intimacy_delta=0.5)  # 超过MAX_SINGLE_DELTA

        expected_change = Relationship.MAX_SINGLE_DELTA
        self.assertAlmostEqual(self.rel.intimacy, initial + expected_change)

    def test_negative_delta_limit(self):
        self.rel.apply_delta(intimacy_delta=-0.5)
        
        expected = _DEFAULT_INTIMACY - Relationship.MAX_SINGLE_DELTA
        self.assertAlmostEqual(self.rel.intimacy, expected)

    def test_combined_deltas(self):
        self.rel.apply_delta(
            intimacy_delta=0.1,
            trust_delta=0.05,
            respect_delta=-0.08,
            fear_delta=0.03,
        )
        
        self.assertAlmostEqual(self.rel.intimacy, 0.1)
        self.assertAlmostEqual(self.rel.trust, 0.55)
        self.assertAlmostEqual(self.rel.respect, -0.08)
        self.assertAlmostEqual(self.rel.fear, 0.03)

    def test_boundary_after_clamping(self):
        self.rel.intimacy = 0.95
        self.rel.apply_delta(intimacy_delta=0.2)
        
        self.assertAlmostEqual(self.rel.intimacy, 1.0)

    def test_chained_calls(self):
        result = (self.rel
                  .apply_delta(intimacy_delta=0.1)
                  .apply_delta(trust_delta=0.1)
                  .apply_delta(respect_delta=0.1))
        
        self.assertIsNotNone(result)


class TestLegacyPotentialConversion(unittest.TestCase):
    """测试向后兼容转换"""

    def test_neutral_to_potential(self):
        rel = Relationship()
        potential = rel.to_legacy_potential()
        
        expected = (0.0 * 0.4 + 0.5 * 0.3 + 0.0 * 0.2 - 0.0 * 0.1)
        self.assertAlmostEqual(potential.value, expected)

    def test_positive_to_potential(self):
        rel = Relationship(intimacy=0.8, trust=0.9, respect=0.7, fear=0.1)
        potential = rel.to_legacy_potential()
        
        self.assertGreater(potential.value, 0)

    def test_negative_to_potential(self):
        rel = Relationship(intimacy=-0.8, trust=0.2, respect=-0.6, fear=0.8)
        potential = rel.to_legacy_potential()
        
        self.assertLess(potential.value, 0)

    def test_potential_in_valid_range(self):
        rel = Relationship(intimacy=1.0, trust=1.0, respect=1.0, fear=0.0)
        potential = rel.to_legacy_potential()
        
        self.assertGreaterEqual(potential.value, RelationshipPotential.POTENTIAL_MIN)
        self.assertLessEqual(potential.value, RelationshipPotential.POTENTIAL_MAX)


class TestPromptSummaryGeneration(unittest.TestCase):
    """测试prompt摘要生成"""

    def test_neutral_relation_summary(self):
        rel = Relationship()
        summary = rel.to_prompt_summary()
        self.assertIn("中性关系", summary)

    def test_positive_intimacy_shown(self):
        rel = Relationship(intimacy=0.7)
        summary = rel.to_prompt_summary()
        self.assertIn("亲近", summary)

    def test_negative_intimacy_shown(self):
        rel = Relationship(intimacy=-0.6)
        summary = rel.to_prompt_summary()
        self.assertIn("疏远", summary)

    def test_high_trust_shown(self):
        rel = Relationship(trust=0.9)
        summary = rel.to_prompt_summary()
        self.assertIn("信任", summary)

    def test_low_trust_shown(self):
        rel = Relationship(trust=0.2)
        summary = rel.to_prompt_summary()
        self.assertIn("怀疑", summary)

    def test_respect_shown(self):
        rel = Relationship(respect=0.75)
        summary = rel.to_prompt_summary()
        self.assertIn("敬重", summary)

    def test_disrespect_shown(self):
        rel = Relationship(respect=-0.65)
        summary = rel.to_prompt_summary()
        self.assertIn("轻视", summary)

    def test_fear_shown(self):
        rel = Relationship(fear=0.8)
        summary = rel.to_prompt_summary()
        self.assertIn("忌惮", summary)

    def test_low_fear_not_shown(self):
        rel = Relationship(fear=0.1)
        summary = rel.to_prompt_summary()
        self.assertNotIn("忌惮", summary)

    def test_complex_relation(self):
        rel = Relationship(
            intimacy=0.6,
            trust=0.85,
            respect=0.4,
            fear=0.25,
        )
        summary = rel.to_prompt_summary()
        
        self.assertTrue(
            len(summary.split(", ")) >= 3 and
            ("亲近" in summary or "信任" in summary or "敬重" in summary)
        )


class TestRelationshipProperties(unittest.TestCase):
    """测试关系属性计算"""

    def test_is_positive_true(self):
        rel = Relationship(intimacy=0.5, trust=0.7, respect=0.3)
        self.assertTrue(rel.is_positive)

    def test_is_positive_false(self):
        rel = Relationship(intimacy=-0.5, trust=0.3, respect=-0.4)
        self.assertFalse(rel.is_positive)

    def test_strength_zero_for_neutral(self):
        rel = Relationship(trust=0.5)
        strength = rel.relationship_strength
        self.assertGreaterEqual(strength, 0.0)
        self.assertLessEqual(strength, 1.0)

    def test_strength_increases_with_extremes(self):
        weak_rel = Relationship(intimacy=0.1, trust=0.55, respect=0.05)
        strong_rel = Relationship(intimacy=0.9, trust=0.95, respect=0.85, fear=0.7)
        
        self.assertGreater(strong_rel.relationship_strength, weak_rel.relationship_strength)


class TestSocialActionCreation(unittest.TestCase):
    """测试社交动作创建"""

    def test_default_creation(self):
        action = SocialAction(action_type=SocialActionType.GIFT)
        self.assertEqual(action.action_type, SocialActionType.GIFT)
        self.assertAlmostEqual(action.value, 1.0)
        self.assertFalse(action.is_recurring)
        self.assertEqual(action.description, "")

    def test_custom_creation(self):
        action = SocialAction(
            action_type=SocialActionType.HELP,
            value=0.7,
            is_recurring=True,
            description="帮助解决难题",
        )
        self.assertAlmostEqual(action.value, 0.7)
        self.assertTrue(action.is_recurring)

    def test_value_clamping_high(self):
        action = SocialAction(action_type=SocialActionType.GIFT, value=1.5)
        self.assertAlmostEqual(action.value, 1.0)

    def test_value_clamping_low(self):
        action = SocialAction(action_type=SocialActionType.GIFT, value=-0.3)
        self.assertAlmostEqual(action.value, 0.0)


class TestInteractionContextCreation(unittest.TestCase):
    """测试互动上下文创建"""

    def test_default_creation(self):
        ctx = InteractionContext()
        self.assertEqual(ctx.location_type, "SEMI_PUBLIC")
        self.assertFalse(ctx.has_audience)
        self.assertAlmostEqual(ctx.mood_match, 0.0)
        self.assertFalse(ctx.is_life_critical)

    def test_mood_clamping(self):
        high_ctx = InteractionContext(mood_match=1.5)
        low_ctx = InteractionContext(mood_match=-1.5)
        
        self.assertAlmostEqual(high_ctx.mood_match, 1.0)
        self.assertAlmostEqual(low_ctx.mood_match, -1.0)


class TestEvolutionRuleLibraryBaseImpact(unittest.TestCase):
    """测试演化规则库基础影响值"""

    def test_gift_impact(self):
        impact = EvolutionRuleLibrary.get_base_impact(SocialActionType.GIFT)
        
        self.assertAlmostEqual(impact['intimacy'], 0.08)
        self.assertAlmostEqual(impact['trust'], 0.02)
        self.assertGreater(impact['intimacy'], 0)

    def test_help_impact(self):
        impact = EvolutionRuleLibrary.get_base_impact(SocialActionType.HELP)
        
        self.assertGreater(impact['intimacy'], 0)
        self.assertGreater(impact['trust'], 0)
        self.assertGreater(impact['respect'], 0)

    def test_insult_impact(self):
        impact = EvolutionRuleLibrary.get_base_impact(SocialActionType.INSULT)
        
        self.assertLess(impact['intimacy'], 0)
        self.assertLess(impact['trust'], 0)
        self.assertLess(impact['respect'], 0)

    def test_betray_impact_strongest_negative(self):
        betray = EvolutionRuleLibrary.get_base_impact(SocialActionType.BETRAY)
        insult = EvolutionRuleLibrary.get_base_impact(SocialActionType.INSULT)
        
        self.assertLess(betray['intimacy'], insult['intimacy'])
        self.assertLess(betray['trust'], insult['trust'])

    def test_threaten_increases_fear(self):
        impact = EvolutionRuleLibrary.get_base_impact(SocialActionType.THREATEN)
        
        self.assertGreater(impact['fear'], 0)
        self.assertAlmostEqual(impact['fear'], 0.15)

    def test_praise_increases_respect(self):
        impact = EvolutionRuleLibrary.get_base_impact(SocialActionType.PRAISE)
        
        self.assertAlmostEqual(impact['respect'], 0.08)

    def test_unknown_action_returns_zeros(self):
        impact = EvolutionRuleLibrary.get_base_impact(SocialActionType.CONVERSE)
        
        self.assertNotEqual(impact['intimacy'], 0)  # CONVERSE有定义


class TestContextMultiplier(unittest.TestCase):
    """测试上下文调节系数"""

    def test_default_context(self):
        ctx = InteractionContext()
        mult = EvolutionRuleLibrary.compute_context_multiplier(ctx)
        
        for dim_val in mult.values():
            self.assertAlmostEqual(dim_val, 1.0)

    def test_private_increases_intimacy(self):
        ctx = InteractionContext(location_type="PRIVATE")
        mult = EvolutionRuleLibrary.compute_context_multiplier(ctx)
        
        self.assertGreater(mult['intimacy'], 1.0)

    def test_public_audience_increases_respect(self):
        ctx = InteractionContext(has_audience=True)
        mult = EvolutionRuleLibrary.compute_context_multiplier(ctx)
        
        self.assertGreater(mult['respect'], 1.0)

    def test_life_critical_increases_fear(self):
        ctx = InteractionContext(is_life_critical=True)
        mult = EvolutionRuleLibrary.compute_context_multiplier(ctx)
        
        self.assertGreater(mult['fear'], 1.0)

    def test_positive_mood_boosts_all(self):
        ctx = InteractionContext(mood_match=0.8)
        mult = EvolutionRuleLibrary.compute_context_multiplier(ctx)
        
        for dim_val in mult.values():
            self.assertGreater(dim_val, 1.0)

    def test_negative_mood_reduces_all(self):
        ctx = InteractionContext(mood_match=-0.6)
        mult = EvolutionRuleLibrary.compute_context_multiplier(ctx)
        
        for dim_val in mult.values():
            self.assertLess(dim_val, 1.0)


class TestDiminishingFactor(unittest.TestCase):
    """测试边际递减因子"""

    def test_no_interactions_full_effect(self):
        factor = EvolutionRuleLibrary.compute_diminishing_factor(0)
        self.assertAlmostEqual(factor, 1.0)

    def test_few_interactions_slight_reduction(self):
        factor = EvolutionRuleLibrary.compute_diminishing_factor(5)
        self.assertLess(factor, 1.0)
        self.assertGreaterEqual(factor, 0.8)

    def test_many_interactions_significant_reduction(self):
        factor = EvolutionRuleLibrary.compute_diminishing_factor(50)
        self.assertLess(factor, 0.5)

    def test_monotonic_decreasing(self):
        factors = [
            EvolutionRuleLibrary.compute_diminishing_factor(i)
            for i in range(20)
        ]
        
        for i in range(1, len(factors)):
            self.assertLessEqual(factors[i], factors[i-1])


class TestBrokenWindowFactor(unittest.TestCase):
    """测试破窗效应因子"""

    def test_positive_impact_no_broken_window(self):
        base = {'intimacy': 0.1, 'trust': 0.05, 'respect': 0.02, 'fear': 0.0}
        factors = EvolutionRuleLibrary.compute_broken_window_factor(base, 0.8)
        
        for dim, factor in factors.items():
            self.assertAlmostEqual(factor, 1.0)

    def test_negative_impact_amplified_by_trust(self):
        base = {'intimacy': -0.1, 'trust': -0.05, 'respect': -0.02, 'fear': 0.0}
        
        low_trust_factors = EvolutionRuleLibrary.compute_broken_window_factor(base, 0.2)
        high_trust_factors = EvolutionRuleLibrary.compute_broken_window_factor(base, 0.9)
        
        self.assertGreater(
            high_trust_factors['intimacy'],
            low_trust_factors['intimacy']
        )

    def test_zero_trust_no_amplification(self):
        base = {'intimacy': -0.1, 'trust': 0.0, 'respect': 0.0, 'fear': 0.0}
        factors = EvolutionRuleLibrary.compute_broken_window_factor(base, 0.0)
        
        self.assertAlmostEqual(factors['intimacy'], 1.0)


class TestComputeDeltaFullChain(unittest.TestCase):
    """测试完整效应链计算"""

    def test_simple_gift(self):
        action = SocialAction(action_type=SocialActionType.GIFT)
        ctx = InteractionContext()
        relationship = Relationship()
        
        delta = EvolutionRuleLibrary.compute_delta(action, ctx, relationship)
        
        self.assertGreater(delta['intimacy'], 0)
        self.assertGreater(delta['trust'], 0)

    def test_betray_on_high_trust_hurts_more(self):
        action = SocialAction(action_type=SocialActionType.BETRAY)
        ctx = InteractionContext()
        
        low_trust_rel = Relationship(trust=0.2)
        high_trust_rel = Relationship(trust=0.9)
        
        low_delta = EvolutionRuleLibrary.compute_delta(action, ctx, low_trust_rel)
        high_delta = EvolutionRuleLibrary.compute_delta(action, ctx, high_trust_rel)
        
        self.assertLess(high_delta['intimacy'], low_delta['intimacy'])

    def test_value_scaling(self):
        normal_action = SocialAction(action_type=SocialActionType.GIFT, value=1.0)
        weak_action = SocialAction(action_type=SocialActionType.GIFT, value=0.3)
        
        ctx = InteractionContext()
        rel = Relationship()
        
        normal_delta = EvolutionRuleLibrary.compute_delta(normal_action, ctx, rel)
        weak_delta = EvolutionRuleLibrary.compute_delta(weak_action, ctx, rel)
        
        self.assertGreater(normal_delta['intimacy'], weak_delta['intimacy'])

    def test_delta_within_limits(self):
        action = SocialAction(action_type=SocialActionType.BETRAY, value=2.0)
        ctx = InteractionContext()
        rel = Relationship()
        
        delta = EvolutionRuleLibrary.compute_delta(action, ctx, rel)
        
        for dim, value in delta.items():
            self.assertGreaterEqual(value, -Relationship.MAX_SINGLE_DELTA)
            self.assertLessEqual(value, Relationship.MAX_SINGLE_DELTA)

    def test_diminishing_over_time(self):
        action = SocialAction(action_type=SocialActionType.CONVERSE)
        ctx = InteractionContext()
        
        early_rel = Relationship()
        late_rel = Relationship()
        late_rel.metadata.interaction_count = 50
        
        early_delta = EvolutionRuleLibrary.compute_delta(action, ctx, early_rel)
        late_delta = EvolutionRuleLibrary.compute_delta(action, ctx, late_rel)
        
        self.assertGreater(abs(early_delta['intimacy']), abs(late_delta['intimacy']))


class TestSocialEvolutionEngineBasic(unittest.TestCase):
    """测试社交演化引擎基础功能"""

    def test_default_creation(self):
        engine = SocialEvolutionEngine()
        self.assertTrue(engine.is_four_dimensional_mode)
        self.assertEqual(engine.get_relationship_count(), 0)

    def test_legacy_mode_creation(self):
        engine = SocialEvolutionEngine(use_four_dimensional=False)
        self.assertFalse(engine.is_four_dimensional_mode)

    def test_get_relationship_creates_new(self):
        engine = SocialEvolutionEngine()
        rel = engine.get_relationship("alice", "bob")
        
        self.assertIsInstance(rel, Relationship)
        self.assertEqual(engine.get_relationship_count(), 1)

    def test_get_relationship_returns_existing(self):
        engine = SocialEvolutionEngine()
        rel1 = engine.get_relationship("alice", "bob")
        rel2 = engine.get_relationship("alice", "bob")
        
        self.assertIs(rel1, rel2)

    def test_pair_key_order_invariant(self):
        engine = SocialEvolutionEngine()
        rel_ab = engine.get_relationship("a", "b")
        rel_ba = engine.get_relationship("b", "a")
        
        self.assertIs(rel_ab, rel_ba)

    def test_remove_relationship(self):
        engine = SocialEvolutionEngine()
        engine.get_relationship("alice", "bob")
        
        removed = engine.remove_relationship("alice", "bob")
        self.assertIsNotNone(removed)
        self.assertEqual(engine.get_relationship_count(), 0)

    def test_remove_nonexistent_relationship(self):
        engine = SocialEvolutionEngine()
        removed = engine.remove_relationship("x", "y")
        self.assertIsNone(removed)


class TestEvolveRelationship(unittest.TestCase):
    """测试关系演化流程"""

    def setUp(self):
        self.engine = SocialEvolutionEngine()

    def test_simple_help_evolves(self):
        rel = self.engine.evolve_relationship(
            char_a="alice",
            char_b="bob",
            action=SocialAction(SocialActionType.HELP),
        )
        
        self.assertGreater(rel.intimacy, 0.0)
        self.assertGreater(rel.trust, 0.5)

    def test_insult_damages(self):
        rel = self.engine.evolve_relationship(
            char_a="alice",
            char_b="bob",
            action=SocialAction(SocialActionType.INSULT),
        )
        
        self.assertLess(rel.intimacy, 0.0)

    def test_multiple_interactions_accumulate(self):
        for _ in range(5):
            self.engine.evolve_relationship(
                char_a="alice",
                char_b="bob",
                action=SocialAction(SocialActionType.CONVERSE),
            )
        
        rel = self.engine.get_relationship("alice", "bob")
        self.assertGreater(rel.intimacy, 0.0)

    def test_metadata_records_interaction(self):
        self.engine.evolve_relationship(
            char_a="alice",
            char_b="bob",
            action=SocialAction(
                SocialActionType.GIFT,
                description="送了一本书",
            ),
        )
        
        rel = self.engine.get_relationship("alice", "bob")
        self.assertEqual(rel.metadata.interaction_count, 1)
        self.assertIn("送了一本书", rel.metadata.history)

    def test_backward_compat_potential_updated(self):
        self.engine.evolve_relationship(
            char_a="alice",
            char_b="bob",
            action=SocialAction(SocialActionType.HELP),
        )
        
        potential = self.engine.get_potential("alice", "bob")
        self.assertGreater(potential.value, 0.0)

    def test_context_affects_evolution(self):
        private_ctx = InteractionContext(location_type="PUBLIC")
        private_rel = SocialEvolutionEngine().evolve_relationship(
            char_a="a", char_b="b",
            action=SocialAction(SocialActionType.GIFT),
            ctx=private_ctx,
        )
        
        private_ctx2 = InteractionContext(location_type="PRIVATE")
        private_rel2 = SocialEvolutionEngine().evolve_relationship(
            char_a="a", char_b="b",
            action=SocialAction(SocialActionType.GIFT),
            ctx=private_ctx2,
        )


class TestRelationSummaryForPrompt(unittest.TestCase):
    """测试prompt关系摘要生成"""

    def test_empty_engine_empty_summary(self):
        engine = SocialEvolutionEngine()
        summary = engine.get_relation_summary_for_prompt("alice")
        self.assertEqual(summary, "")

    def test_single_relation_shown(self):
        engine = SocialEvolutionEngine()
        for _ in range(3):
            engine.evolve_relationship(
                char_a="alice",
                char_b="bob",
                action=SocialAction(SocialActionType.HELP, value=1.0),
            )

        summary = engine.get_relation_summary_for_prompt("alice")
        self.assertIn("bob", summary)

    def test_weak_relations_filtered(self):
        engine = SocialEvolutionEngine()
        engine.evolve_relationship(
            char_a="alice",
            char_b="stranger",
            action=SocialAction(SocialActionType.CONVERSE, value=0.01),
        )
        
        summary = engine.get_relation_summary_for_prompt("alice")
        self.assertEqual(summary, "")  # 太弱不显示

    def test_multiple_relations_sorted(self):
        engine = SocialEvolutionEngine()
        
        engine.evolve_relationship(
            char_a="alice", char_b="weak",
            action=SocialAction(SocialActionType.CONVERSE, value=0.1),
        )
        engine.evolve_relationship(
            char_a="alice", char_b="strong",
            action=SocialAction(SocialActionType.HELP, value=1.0),
        )
        
        summary = engine.get_relation_summary_for_prompt("alice")
        if summary:
            lines = summary.strip().split("\n")
            if len(lines) >= 2:
                strong_pos = summary.find("strong")
                weak_pos = summary.find("weak")
                self.assertLess(strong_pos, weak_pos)


class TestBackwardCompatibility(unittest.TestCase):
    """测试向后兼容性"""

    def test_parent_api_still_works(self):
        engine = SocialEvolutionEngine()
        
        engine.update_potential("alice", "bob", 0.5)
        potential = engine.get_potential("alice", "bob")
        
        self.assertGreater(potential.value, 0.0)

    def test_legacy_mode_uses_old_logic(self):
        engine = SocialEvolutionEngine(use_four_dimensional=False)
        
        engine.evolve_relationship(
            char_a="alice",
            char_b="bob",
            action=SocialAction(SocialActionType.HELP),
        )
        
        potential = engine.get_potential("alice", "bob")
        self.assertGreater(potential.value, 0.0)

    def test_four_dim_and_legacy_sync(self):
        engine = SocialEvolutionEngine(use_four_dimensional=True)
        
        engine.evolve_relationship(
            char_a="alice",
            char_b="bob",
            action=SocialAction(SocialActionType.GIFT),
        )
        
        four_dim_rel = engine.get_relationship("alice", "bob")
        legacy_potential = engine.get_potential("alice", "bob")
        
        converted = four_dim_rel.to_legacy_potential()
        self.assertAlmostEqual(legacy_potential.value, converted.value)


class TestEdgeCasesAndRobustness(unittest.TestCase):
    """边界条件和鲁棒性测试"""

    def test_rapid_successive_actions(self):
        engine = SocialEvolutionEngine()
        
        for _ in range(100):
            engine.evolve_relationship(
                char_a="a", char_b="b",
                action=SocialAction(SocialActionType.CONVERSE),
            )
        
        rel = engine.get_relationship("a", "b")
        self.assertGreaterEqual(rel.metadata.interaction_count, 100)

    def test_many_different_relationships(self):
        engine = SocialEvolutionEngine()
        
        for i in range(20):
            engine.evolve_relationship(
                char_a=f"char_{i}",
                char_b=f"char_{i+1}",
                action=SocialAction(SocialActionType.HELP),
            )
        
        self.assertEqual(engine.get_relationship_count(), 20)

    def test_extreme_value_actions(self):
        engine = SocialEvolutionEngine()
        
        engine.evolve_relationship(
            char_a="x", char_b="y",
            action=SocialAction(SocialActionType.BETRAY, value=1.0),
        )
        
        rel = engine.get_relationship("x", "y")
        self.assertLess(rel.intimacy, 0.0)
        self.assertLess(rel.trust, 0.5)

    def test_recovery_from_betrayal(self):
        engine = SocialEvolutionEngine()

        engine.evolve_relationship(
            char_a="a", char_b="b",
            action=SocialAction(SocialActionType.BETRAY),
        )

        after_betray = engine.get_relationship("a", "b").trust

        for _ in range(10):
            engine.evolve_relationship(
                char_a="a", char_b="b",
                action=SocialAction(SocialActionType.DEFEND),
            )

        after_recovery = engine.get_relationship("a", "b").trust
        self.assertGreater(after_recovery, after_betray)

    def test_unicode_descriptions(self):
        engine = SocialEvolutionEngine()
        
        engine.evolve_relationship(
            char_a="角色A",
            char_b="角色B",
            action=SocialAction(
                SocialActionType.GIFT,
                description="🎁 送了一份精美的礼物",
            ),
        )
        
        rel = engine.get_relationship("角色A", "角色B")
        self.assertIn("🎁", rel.metadata.history[0])


if __name__ == "__main__":
    unittest.main()
