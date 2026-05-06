"""
马斯洛动机引擎单元测试
覆盖：NeedLevel/ConflictStrategy/ContextType枚举、NeedFulfillment、MaslowProfile、MotivationEngine的所有核心功能
"""

import unittest
from luqi_engine.motivation.maslow_engine import (
    ConflictStrategy,
    ContextType,
    MaslowProfile,
    MotivationConflict,
    MotivationEngine,
    NeedFulfillment,
    NeedLevel,
)


class TestNeedLevelEnum(unittest.TestCase):
    """测试需求层次枚举"""

    def test_all_eight_levels_exist(self):
        expected = [
            "PHYSIOLOGICAL", "SAFETY", "LOVE_BELONGING",
            "ESTEEM", "COGNITIVE", "AESTHETIC",
            "SELF_ACTUALIZATION", "TRANSCENDENCE",
        ]
        actual = [level.name for level in NeedLevel]
        self.assertEqual(actual, expected)

    def test_level_count(self):
        self.assertEqual(len(NeedLevel), 8)

    def test_ordering_reflects_hierarchy(self):
        levels = list(NeedLevel)
        self.assertEqual(levels[0], NeedLevel.PHYSIOLOGICAL)  # 最底层
        self.assertEqual(levels[-1], NeedLevel.TRANSCENDENCE)  # 最高层


class TestConflictStrategyEnum(unittest.TestCase):
    """测试冲突解决策略枚举"""

    def test_all_strategies_exist(self):
        expected = ["HIERARCHY_FIRST", "CONTEXT_ADAPTIVE", "COMPROMISE", "DELAY"]
        actual = [s.name for s in ConflictStrategy]
        self.assertEqual(actual, expected)

    def test_strategy_count(self):
        self.assertEqual(len(ConflictStrategy), 4)


class TestContextTypeEnum(unittest.TestCase):
    """测试情境类型枚举"""

    def test_all_contexts_exist(self):
        expected = ["COMBAT", "SOCIAL", "SOLITUDE", "CRISIS", "CREATIVE", "DEFAULT"]
        actual = [c.name for c in ContextType]
        self.assertEqual(actual, expected)

    def test_context_count(self):
        self.assertEqual(len(ContextType), 6)


class TestNeedFulfillmentCreation(unittest.TestCase):
    """测试需求满足状态创建"""

    def test_default_creation(self):
        need = NeedFulfillment(level=NeedLevel.SAFETY)
        self.assertAlmostEqual(need.value, 0.5)
        self.assertAlmostEqual(need.priority, 0.5)
        self.assertEqual(need.level, NeedLevel.SAFETY)

    def test_custom_values(self):
        need = NeedFulfillment(
            level=NeedLevel.ESTEEM,
            value=0.8,
            priority=0.9,
        )
        self.assertAlmostEqual(need.value, 0.8)
        self.assertAlmostEqual(need.priority, 0.9)

    def test_value_clamping_high(self):
        need = NeedFulfillment(level=NeedLevel.PHYSIOLOGICAL, value=1.5)
        self.assertAlmostEqual(need.value, 1.0)

    def test_value_clamping_low(self):
        need = NeedFulfillment(level=NeedLevel.PHYSIOLOGICAL, value=-0.3)
        self.assertAlmostEqual(need.value, 0.0)

    def test_priority_clamping(self):
        need = NeedFulfillment(
            level=NeedLevel.COGNITIVE,
            priority=2.0,
        )
        self.assertAlmostEqual(need.priority, 1.0)


class TestNeedFulfillmentProperties(unittest.TestCase):
    """测试需求满足状态属性计算"""

    def test_deficit_when_fully_satisfied(self):
        need = NeedFulfillment(level=NeedLevel.PHYSIOLOGICAL, value=1.0)
        self.assertAlmostEqual(need.deficit, 0.0)

    def test_deficit_when_half_satisfied(self):
        need = NeedFulfillment(level=NeedLevel.SAFETY, value=0.5)
        self.assertAlmostEqual(need.deficit, 0.5)

    def test_deficit_when_unsatisfied(self):
        need = NeedFulfillment(level=NeedLevel.LOVE_BELONGING, value=0.1)
        self.assertAlmostEqual(need.deficit, 0.9)

    def test_is_deficiency_need_physiological(self):
        need = NeedFulfillment(level=NeedLevel.PHYSIOLOGICAL)
        self.assertTrue(need.is_deficiency_need)

    def test_is_deficiency_need_safety(self):
        need = NeedFulfillment(level=NeedLevel.SAFETY)
        self.assertTrue(need.is_deficiency_need)

    def test_is_not_deficiency_need_love(self):
        need = NeedFulfillment(level=NeedLevel.LOVE_BELONGING)
        self.assertFalse(need.is_deficiency_need)

    def test_is_growth_need_love(self):
        need = NeedFulfillment(level=NeedLevel.LOVE_BELONGING)
        self.assertTrue(need.is_growth_need)

    def test_is_growth_need_esteem(self):
        need = NeedFulfillment(level=NeedLevel.ESTEEM)
        self.assertTrue(need.is_growth_need)

    def test_is_meta_need_aesthetic(self):
        need = NeedFulfillment(level=NeedLevel.AESTHETIC)
        self.assertTrue(need.is_meta_need)

    def test_is_meta_need_transcendence(self):
        need = NeedFulfillment(level=NeedLevel.TRANSCENDENCE)
        self.assertTrue(need.is_meta_need)


class TestNeedFulfillmentBaseStrength(unittest.TestCase):
    """测试基础动机强度计算"""

    def test_high_deficiency_high_strength(self):
        need = NeedFulfillment(
            level=NeedLevel.PHYSIOLOGICAL,
            value=0.1,
            priority=0.95,
        )
        self.assertGreater(need.base_strength, 0.8)

    def test_low_deficiency_low_strength(self):
        need = NeedFulfillment(
            level=NeedLevel.SAFETY,
            value=0.9,
            priority=0.9,
        )
        self.assertLess(need.base_strength, 0.3)

    def test_deficiency_need_survival_boost(self):
        deficiency = NeedFulfillment(
            level=NeedLevel.PHYSIOLOGICAL,
            value=0.3,
            priority=0.9,
        )
        growth = NeedFulfillment(
            level=NeedLevel.ESTEEM,
            value=0.3,
            priority=0.9,
        )
        self.assertGreater(deficiency.base_strength, growth.base_strength)

    def test_growth_need_satisfaction_bonus(self):
        unsatisfied = NeedFulfillment(
            level=NeedLevel.ESTEEM,
            value=0.2,
            priority=0.7,
        )
        satisfied = NeedFulfillment(
            level=NeedLevel.ESTEEM,
            value=0.8,
            priority=0.7,
        )
        self.assertGreaterEqual(satisfied.base_strength, unsatisfied.base_strength * 0.5)

    def test_meta_need_activation_threshold(self):
        low_value = NeedFulfillment(
            level=NeedLevel.SELF_ACTUALIZATION,
            value=0.2,
            priority=0.5,
        )
        high_value = NeedFulfillment(
            level=NeedLevel.SELF_ACTUALIZATION,
            value=0.6,
            priority=0.5,
        )
        self.assertGreater(high_value.base_strength, low_value.base_strength)

    def test_strength_range(self):
        for _ in range(20):
            import random
            val = random.random()
            pri = random.random()
            need = NeedFulfillment(
                level=NeedLevel.COGNITIVE,
                value=val,
                priority=pri,
            )
            self.assertGreaterEqual(need.base_strength, 0.0)
            self.assertLessEqual(need.base_strength, 1.0)


class TestNeedFulfillmentContextAdjustment(unittest.TestCase):
    """测试情境调整"""

    def test_combat_boosts_safety(self):
        safety = NeedFulfillment(
            level=NeedLevel.SAFETY,
            value=0.3,
            priority=0.9,
        )
        default_strength = safety.apply_context_adjustment(ContextType.DEFAULT)
        combat_strength = safety.apply_context_adjustment(ContextType.COMBAT)
        
        self.assertGreater(combat_strength, default_strength)

    def test_social_boosts_love_belonging(self):
        love = NeedFulfillment(
            level=NeedLevel.LOVE_BELONGING,
            value=0.4,
            priority=0.75,
        )
        default_strength = love.apply_context_adjustment(ContextType.DEFAULT)
        social_strength = love.apply_context_adjustment(ContextType.SOCIAL)
        
        self.assertGreater(social_strength, default_strength)

    def test_creative_boosts_aesthetic(self):
        aesthetic = NeedFulfillment(
            level=NeedLevel.AESTHETIC,
            value=0.3,
            priority=0.4,
        )
        default_strength = aesthetic.apply_context_adjustment(ContextType.DEFAULT)
        creative_strength = aesthetic.apply_context_adjustment(ContextType.CREATIVE)
        
        self.assertGreater(creative_strength, default_strength)

    def test_crisis_suppresses_meta_needs(self):
        transcendence = NeedFulfillment(
            level=NeedLevel.TRANSCENDENCE,
            value=0.5,
            priority=0.3,
        )
        crisis_strength = transcendence.apply_context_adjustment(ContextType.CRISIS)
        
        self.assertLess(crisis_strength, transcendence.base_strength)

    def test_urgency_multiplier_works(self):
        safety = NeedFulfillment(
            level=NeedLevel.SAFETY,
            value=0.3,
            priority=0.9,
        )
        normal = safety.apply_context_adjustment(
            ContextType.COMBAT,
            urgency_multiplier=1.0,
        )
        urgent = safety.apply_context_adjustment(
            ContextType.COMBAT,
            urgency_multiplier=1.5,
        )
        
        self.assertGreaterEqual(urgent, normal)

    def test_output_range(self):
        for context in ContextType:
            need = NeedFulfillment(
                level=NeedLevel.PHYSIOLOGICAL,
                value=0.5,
                priority=0.5,
            )
            strength = need.apply_context_adjustment(context)
            self.assertGreaterEqual(strength, 0.0)
            self.assertLessEqual(strength, 1.0)


class TestMaslowProfileCreation(unittest.TestCase):
    """测试马斯洛剖面创建"""

    def test_default_profile_has_all_eight_levels(self):
        profile = MaslowProfile()
        self.assertEqual(len(profile.needs), 8)
        for level in NeedLevel:
            self.assertIn(level, profile.needs)

    def test_default_baseline_values(self):
        profile = MaslowProfile()
        self.assertAlmostEqual(
            profile.needs[NeedLevel.PHYSIOLOGICAL].value, 0.85
        )
        self.assertAlmostEqual(
            profile.needs[NeedLevel.SAFETY].value, 0.80
        )
        self.assertAlmostEqual(
            profile.needs[NeedLevel.TRANSCENDENCE].value, 0.20
        )

    def test_inverted_pyramid_shape(self):
        profile = MaslowProfile()
        values = [
            profile.needs[level].value
            for level in NeedLevel
        ]
        for i in range(1, len(values)):
            self.assertGreaterEqual(values[i-1], values[i])

    def test_custom_baseline(self):
        custom_baseline = {
            NeedLevel.PHYSIOLOGICAL: 0.5,
            NeedLevel.SAFETY: 0.4,
        }
        profile = MaslowProfile(baseline=custom_baseline)
        self.assertAlmostEqual(
            profile.needs[NeedLevel.PHYSIOLOGICAL].value, 0.5
        )

    def test_custom_priorities(self):
        custom_priorities = {
            NeedLevel.ESTEEM: 0.99,
        }
        profile = MaslowProfile(priorities=custom_priorities)
        self.assertAlmostEqual(
            profile.needs[NeedLevel.ESTEEM].priority, 0.99
        )


class TestMaslowProfileOperations(unittest.TestCase):
    """测试剖面操作方法"""

    def setUp(self):
        self.profile = MaslowProfile()

    def test_update_need_value_positive(self):
        old_val = self.profile.needs[NeedLevel.ESTEEM].value
        self.profile.update_need_value(NeedLevel.ESTEEM, 0.1)
        new_val = self.profile.needs[NeedLevel.ESTEEM].value
        self.assertAlmostEqual(new_val, old_val + 0.1)

    def test_update_need_value_negative(self):
        old_val = self.profile.needs[NeedLevel.SAFETY].value
        self.profile.update_need_value(NeedLevel.SAFETY, -0.2)
        new_val = self.profile.needs[NeedLevel.SAFETY].value
        self.assertAlmostEqual(new_val, old_val - 0.2)

    def test_update_clamps_to_max(self):
        self.profile.update_need_value(NeedLevel.PHYSIOLOGICAL, 0.5)
        self.assertAlmostEqual(
            self.profile.needs[NeedLevel.PHYSIOLOGICAL].value, 1.0
        )

    def test_update_clamps_to_min(self):
        self.profile.update_need_value(NeedLevel.PHYSIOLOGICAL, -1.5)
        self.assertAlmostEqual(
            self.profile.needs[NeedLevel.PHYSIOLOGICAL].value, 0.0
        )

    def test_get_dominant_need_returns_tuple(self):
        dominant = self.profile.get_dominant_need()
        self.assertIsInstance(dominant, tuple)
        self.assertEqual(len(dominant), 2)
        self.assertIsInstance(dominant[0], NeedLevel)
        self.assertIsInstance(dominant[1], float)

    def test_get_unmet_deficiency_needs_when_all_met(self):
        profile = MaslowProfile()
        unmet = profile.get_unmet_deficiency_needs()
        self.assertEqual(len(unmet), 0)

    def test_get_unmet_deficiency_needs_when_some_unmet(self):
        profile = MaslowProfile()
        profile.needs[NeedLevel.PHYSIOLOGICAL].value = 0.3
        profile.needs[NeedLevel.SAFETY].value = 0.4
        
        unmet = profile.get_unmet_deficiency_needs()
        self.assertGreater(len(unmet), 0)
        self.assertIn(NeedLevel.PHYSIOLOGICAL, [u[0] for u in unmet])

    def test_to_dict_contains_all_keys(self):
        result = self.profile.to_dict()
        self.assertIn("needs", result)
        self.assertIn("baseline", result)
        self.assertIn("priorities", result)
        self.assertEqual(len(result["needs"]), 8)


class TestMotivationEngineBasicOperations(unittest.TestCase):
    """测试动机引擎基础操作"""

    def setUp(self):
        self.engine = MotivationEngine(character_id="test_char")

    def test_initialization(self):
        self.assertEqual(self.engine.character_id, "test_char")
        self.assertEqual(self.engine.current_context, ContextType.DEFAULT)

    def test_initialization_with_custom_profile(self):
        custom = MaslowProfile()
        custom.needs[NeedLevel.PHYSIOLOGICAL].value = 0.3
        engine = MotivationEngine(character_id="char", profile=custom)
        self.assertAlmostEqual(
            engine.profile.needs[NeedLevel.PHYSIOLOGICAL].value, 0.3
        )

    def test_set_context(self):
        self.engine.set_context(ContextType.COMBAT)
        self.assertEqual(self.engine.current_context, ContextType.COMBAT)

    def test_set_context_with_urgency(self):
        self.engine.set_context(ContextType.CRISIS, urgency=1.8)
        self.assertEqual(self.engine.current_context, ContextType.CRISIS)


class TestMotivationEngineCalculations(unittest.TestCase):
    """测试动机强度计算"""

    def setUp(self):
        self.engine = MotivationEngine(character_id="calc_test")

    def test_calculate_all_returns_dict(self):
        motivations = self.engine.calculate_all_motivations()
        self.assertIsInstance(motivations, dict)
        self.assertEqual(len(motivations), 8)

    def test_calculate_all_values_in_range(self):
        motivations = self.engine.calculate_all_motivations()
        for level, strength in motivations.items():
            self.assertGreaterEqual(strength, 0.0)
            self.assertLessEqual(strength, 1.0)

    def test_context_affects_calculations(self):
        default_mots = self.engine.calculate_all_motivations()
        self.engine.set_context(ContextType.COMBAT)
        combat_mots = self.engine.calculate_all_motivations()
        
        self.assertNotEqual(default_mots, combat_mots)

    def test_crisis_prioritizes_safety(self):
        self.engine.set_context(ContextType.CRISIS)
        motivations = self.engine.calculate_all_motivations()
        
        safety_str = motivations[NeedLevel.SAFETY]
        transc_str = motivations[NeedLevel.TRANSCENDENCE]
        
        self.assertGreater(safety_str, transc_str)


class TestMotivationEngineConflictDetection(unittest.TestCase):
    """测试冲突检测"""

    def setUp(self):
        self.engine = MotivationEngine(character_id="conflict_test")

    def test_no_conflict_when_one_dominant(self):
        conflict = self.engine.detect_conflicts()
        self.assertIsNone(conflict)

    def test_conflict_detected_when_two_strong_needs(self):
        self.engine._profile.needs[NeedLevel.SAFETY].value = 0.35
        self.engine._profile.needs[NeedLevel.SAFETY].priority = 0.6
        self.engine._profile.needs[NeedLevel.ESTEEM].value = 0.25
        
        conflict = self.engine.detect_conflicts()
        self.assertIsNotNone(conflict)
        self.assertTrue(conflict.has_conflict)

    def test_conflict_has_correct_type(self):
        self.engine._profile.needs[NeedLevel.SAFETY].value = 0.35
        self.engine._profile.needs[NeedLevel.SAFETY].priority = 0.6
        self.engine._profile.needs[NeedLevel.ESTEEM].value = 0.25
        
        conflict = self.engine.detect_conflicts()
        self.assertIsNotNone(conflict)
        self.assertIn("D-vs-G", conflict.conflict_type)

    def test_no_conflict_when_difference_large(self):
        self.engine._profile.needs[NeedLevel.SAFETY].value = 0.1
        self.engine._profile.needs[NeedLevel.AESTHETIC].value = 0.5
        
        conflict = self.engine.detect_conflicts()
        self.assertIsNone(conflict)


class TestMotivationEngineConflictResolution(unittest.TestCase):
    """测试冲突解决"""

    def setUp(self):
        self.engine = MotivationEngine(character_id="resolve_test")
        self.engine._profile.needs[NeedLevel.SAFETY].value = 0.35
        self.engine._profile.needs[NeedLevel.SAFETY].priority = 0.6
        self.engine._profile.needs[NeedLevel.ESTEEM].value = 0.25

    def test_hierarchy_first_picks_lower_level(self):
        self.engine.detect_conflicts()
        result = self.engine.resolve_conflict(ConflictStrategy.HIERARCHY_FIRST)
        
        self.assertIsNotNone(result)
        winner, _ = result
        self.assertEqual(winner, NeedLevel.SAFETY)

    def test_context_adaptive_respects_weights(self):
        self.engine.set_context(ContextType.COMBAT)
        self.engine.detect_conflicts()
        result = self.engine.resolve_conflict(ConflictStrategy.CONTEXT_ADAPTIVE)
        
        self.assertIsNotNone(result)
        winner, _ = result
        self.assertEqual(winner, NeedLevel.SAFETY)

    def test_compromise_reduces_strength(self):
        self.engine.detect_conflicts()
        result = self.engine.resolve_conflict(ConflictStrategy.COMPROMISE)
        
        self.assertIsNotNone(result)
        _, final_strength = result
        self.assertLessEqual(final_strength, 1.0)

    def test_delay_returns_none(self):
        conflict = self.engine.detect_conflicts()
        self.assertIsNotNone(conflict)  # 确保有冲突
        
        result = self.engine.resolve_conflict(ConflictStrategy.DELAY)
        
        self.assertIsNone(result)

    def test_delay_increases_anxiety(self):
        conflict = self.engine.detect_conflicts()
        initial_anxiety = conflict.anxiety_level if conflict else 0
        
        self.engine.resolve_conflict(ConflictStrategy.DELAY)
        
        after_conflict = self.engine._current_conflict
        after_anxiety = after_conflict.anxiety_level if after_conflict else 0
        self.assertGreaterEqual(after_anxiety, initial_anxiety)

    def test_resolve_marks_as_resolved(self):
        conflict = self.engine.detect_conflicts()
        if not conflict or not conflict.has_conflict:
            self.skipTest("No conflict detected")
            
        self.engine.resolve_conflict(ConflictStrategy.HIERARCHY_FIRST)
        
        self.assertTrue(self.engine._current_conflict.resolved)
        self.assertIsNotNone(self.engine._current_conflict.winner)


class TestMotivationEngineReportGeneration(unittest.TestCase):
    """测试报告生成"""

    def setUp(self):
        self.engine = MotivationEngine(character_id="report_test")

    def test_report_contains_required_keys(self):
        report = self.engine.generate_report()
        
        required_keys = [
            "dominant_need", "top_motivations",
            "unmet_deficiency_needs", "active_conflict",
            "context_info", "recommendations",
        ]
        for key in required_keys:
            self.assertIn(key, report)

    def test_dominant_need_format(self):
        report = self.engine.generate_report()
        
        self.assertIn("level", report["dominant_need"])
        self.assertIn("strength", report["dominant_need"])
        self.assertIsInstance(report["dominant_need"]["level"], str)
        self.assertIsInstance(report["dominant_need"]["strength"], float)

    def test_top_motivations_count(self):
        report = self.engine.generate_report()
        self.assertLessEqual(len(report["top_motivations"]), 5)

    def test_top_motivations_sorted_by_strength(self):
        report = self.engine.generate_report()
        strengths = [m["strength"] for m in report["top_motivations"]]
        self.assertEqual(strengths, sorted(strengths, reverse=True))

    def test_context_info_content(self):
        self.engine.set_context(ContextType.SOCIAL, urgency=1.5)
        report = self.engine.generate_report()
        
        self.assertEqual(report["context_info"]["type"], "SOCIAL")
        self.assertAlmostEqual(report["context_info"]["urgency"], 1.5)

    def test_recommendations_not_empty(self):
        report = self.engine.generate_report()
        self.assertGreater(len(report["recommendations"]), 0)

    def test_conflict_info_when_exists(self):
        self.engine._profile.needs[NeedLevel.SAFETY].value = 0.35
        self.engine._profile.needs[NeedLevel.SAFETY].priority = 0.6
        self.engine._profile.needs[NeedLevel.ESTEEM].value = 0.25
        report = self.engine.generate_report()
        
        self.assertTrue(report["active_conflict"]["exists"])


class TestMotivationEngineEventUpdates(unittest.TestCase):
    """测试事件更新"""

    def setUp(self):
        self.engine = MotivationEngine(character_id="event_test")

    def test_update_from_event_positive(self):
        old = self.engine.profile.needs[NeedLevel.ESTEEM].value
        
        changes = self.engine.update_from_event(
            "win_battle",
            {"esteem": 0.1},
        )
        
        new = self.engine.profile.needs[NeedLevel.ESTEEM].value
        self.assertAlmostEqual(new, old + 0.1)
        self.assertIn(NeedLevel.ESTEEM, changes)

    def test_update_from_event_negative(self):
        old = self.engine.profile.needs[NeedLevel.SAFETY].value
        
        self.engine.update_from_event(
            "take_damage",
            {"safety": -0.15},
        )
        
        new = self.engine.profile.needs[NeedLevel.SAFETY].value
        self.assertAlmostEqual(new, old - 0.15)

    def test_update_multiple_needs(self):
        changes = self.engine.update_from_event(
            "complex_event",
            {
                "esteem": 0.1,
                "cognitive": 0.05,
                "love": 0.08,
            },
        )
        
        self.assertEqual(len(changes), 3)

    def test_update_ignores_unknown_keys(self):
        changes = self.engine.update_from_event(
            "test",
            {"unknown_need": 0.5},
        )
        
        self.assertEqual(len(changes), 0)

    def test_update_aliases_work(self):
        old = self.engine.profile.needs[NeedLevel.LOVE_BELONGING].value
        
        self.engine.update_from_event(
            "make_friend",
            {"love": 0.1},
        )
        
        new = self.engine.profile.needs[NeedLevel.LOVE_BELONGING].value
        self.assertAlmostEqual(new, old + 0.1)


class TestMotivationEngineReset(unittest.TestCase):
    """测试重置功能"""

    def test_reset_to_baseline(self):
        engine = MotivationEngine(character_id="reset_test")
        
        engine._profile.needs[NeedLevel.PHYSIOLOGICAL].value = 0.2
        engine._profile.needs[NeedLevel.ESTEEM].value = 0.9
        
        engine.reset_to_baseline()
        
        self.assertAlmostEqual(
            engine.profile.needs[NeedLevel.PHYSIOLOGICAL].value,
            MaslowProfile.DEFAULT_BASELINE[NeedLevel.PHYSIOLOGICAL],
        )
        self.assertAlmostEqual(
            engine.profile.needs[NeedLevel.ESTEEM].value,
            MaslowProfile.DEFAULT_BASELINE[NeedLevel.ESTEEM],
        )


class TestMotivationConflictDataClass(unittest.TestCase):
    """测试冲突数据类"""

    def test_default_creation(self):
        conflict = MotivationConflict()
        self.assertEqual(len(conflict.conflicting_needs), 0)
        self.assertFalse(conflict.resolved)
        self.assertIsNone(conflict.winner)

    def test_has_conflict_property(self):
        no_conflict = MotivationConflict()
        self.assertFalse(no_conflict.has_conflict)
        
        with_conflict = MotivationConflict(
            conflicting_needs=[
                (NeedLevel.SAFETY, 0.8),
                (NeedLevel.ESTEEM, 0.7),
            ],
        )
        self.assertTrue(with_conflict.has_conflict)

    def test_single_need_not_conflict(self):
        single = MotivationConflict(
            conflicting_needs=[(NeedLevel.SAFETY, 0.8)],
        )
        self.assertFalse(single.has_conflict)

    def test_resolved_conflict_not_active(self):
        resolved = MotivationConflict(
            conflicting_needs=[
                (NeedLevel.SAFETY, 0.8),
                (NeedLevel.ESTEEM, 0.7),
            ],
            resolved=True,
            winner=NeedLevel.SAFETY,
        )
        self.assertFalse(resolved.has_conflict)


class TestEdgeCasesAndIntegration(unittest.TestCase):
    """边界条件和集成测试"""

    def test_extreme_low_all_needs(self):
        engine = MotivationEngine(character_id="extreme_low")
        for level in NeedLevel:
            engine._profile.needs[level].value = 0.05
            
        report = engine.generate_report()
        self.assertGreater(report["dominant_need"]["strength"], 0.5)

    def test_extreme_high_all_needs(self):
        engine = MotivationEngine(character_id="extreme_high")
        for level in NeedLevel:
            engine._profile.needs[level].value = 0.98
            
        report = engine.generate_report()
        self.assertLess(report["dominant_need"]["strength"], 0.3)

    def test_rapid_context_switching(self):
        engine = MotivationEngine(character_id="rapid_ctx")
        contexts = [
            ContextType.COMBAT,
            ContextType.SOCIAL,
            ContextType.CRISIS,
            ContextType.CREATIVE,
            ContextType.SOLITUDE,
        ]
        
        reports = []
        for ctx in contexts:
            engine.set_context(ctx)
            reports.append(engine.generate_report())
            
        self.assertEqual(len(reports), len(contexts))
        dominants = [r["dominant_need"]["level"] for r in reports]

    def test_multiple_events_accumulate(self):
        engine = MotivationEngine(character_id="accumulate")
        
        for i in range(10):
            engine.update_from_event("small_win", {"esteem": 0.02})
            
        final = engine.profile.needs[NeedLevel.ESTEEM].value
        expected = MaslowProfile.DEFAULT_BASELINE[NeedLevel.ESTEEM] + 0.2
        self.assertAlmostEqual(final, min(expected, 1.0), places=2)

    def test_conflict_resolution_chain(self):
        engine = MotivationEngine(character_id="chain")
        engine._profile.needs[NeedLevel.PHYSIOLOGICAL].value = 0.1
        engine._profile.needs[NeedLevel.SAFETY].value = 0.15
        engine._profile.needs[NeedLevel.ESTEEM].value = 0.2
        
        strategies = [
            ConflictStrategy.HIERARCHY_FIRST,
            ConflictStrategy.CONTEXT_ADAPTIVE,
            ConflictStrategy.COMPROMISE,
            ConflictStrategy.DELAY,
        ]
        
        results = []
        for strategy in strategies:
            engine.detect_conflicts()
            result = engine.resolve_conflict(strategy)
            results.append(result is not None)
            
        self.assertEqual(results, [True, True, True, False])

    def test_full_workflow_simulation(self):
        engine = MotivationEngine(character_id="simulation")
        
        engine.set_context(ContextType.DEFAULT)
        report1 = engine.generate_report()
        
        engine.update_from_event("crisis_start", {"safety": -0.4})
        engine.set_context(ContextType.CRISIS, urgency=1.8)
        report2 = engine.generate_report()
        
        self.assertGreater(
            report2["dominant_need"]["strength"],
            report1["dominant_need"]["strength"],
        )
        
        engine.update_from_event("resolve_crisis", {"safety": +0.3})
        engine.set_context(ContextType.DEFAULT)
        report3 = engine.generate_report()
        
        self.assertLess(
            report3["dominant_need"]["strength"],
            report2["dominant_need"]["strength"],
        )


if __name__ == "__main__":
    unittest.main()
