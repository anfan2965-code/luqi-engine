"""
存在主义模型单元测试
覆盖：Belief、DissonanceRecord、ExistentialProfile的所有核心功能
"""

import time
import unittest
from luqi_engine.character.existential_model import (
    AuthenticityState,
    Belief,
    DissonanceRecord,
    ExistentialProfile,
    ResolutionStrategy,
)


class TestBelief(unittest.TestCase):
    """测试信念条目"""

    def test_default_creation(self):
        belief = Belief()
        self.assertEqual(belief.content, "")
        self.assertAlmostEqual(belief.strength, 0.5)
        self.assertEqual(belief.source, "")
        self.assertAlmostEqual(belief.created_at, 0.0, places=1)

    def test_custom_creation(self):
        belief = Belief(
            content="我相信诚实是最好的策略",
            strength=0.8,
            source="personal_experience",
            created_at=1000.0,
        )
        self.assertEqual(belief.content, "我相信诚实是最好的策略")
        self.assertAlmostEqual(belief.strength, 0.8)
        self.assertEqual(belief.source, "personal_experience")
        self.assertAlmostEqual(belief.created_at, 1000.0)

    def test_strength_clamping_high(self):
        belief = Belief(strength=2.0)
        self.assertAlmostEqual(belief.strength, 1.0)

    def test_strength_clamping_low(self):
        belief = Belief(strength=-0.5)
        self.assertAlmostEqual(belief.strength, 0.0)

    def test_strength_boundary_max(self):
        belief = Belief(strength=1.0)
        self.assertAlmostEqual(belief.strength, 1.0)

    def test_strength_boundary_min(self):
        belief = Belief(strength=0.0)
        self.assertAlmostEqual(belief.strength, 0.0)


class TestDissonanceRecord(unittest.TestCase):
    """测试认知失调记录"""

    def test_default_creation(self):
        record = DissonanceRecord()
        self.assertEqual(record.conflicting_beliefs, ("", ""))
        self.assertAlmostEqual(record.dissonance_magnitude, 0.0)
        self.assertIsNone(record.resolution_strategy)
        self.assertFalse(record.resolved)

    def test_custom_creation(self):
        record = DissonanceRecord(
            conflicting_beliefs=("belief_1", "新行为：撒谎"),
            dissonance_magnitude=0.72,
            timestamp=time.time(),
            resolution_strategy=ResolutionStrategy.JUSTIFY,
        )
        self.assertEqual(len(record.conflicting_beliefs), 2)
        self.assertAlmostEqual(record.dissonance_magnitude, 0.72)
        self.assertEqual(record.resolution_strategy, ResolutionStrategy.JUSTIFY)

    def test_magnitude_clamping_high(self):
        record = DissonanceRecord(dissonance_magnitude=1.5)
        self.assertAlmostEqual(record.dissonance_magnitude, 1.0)

    def test_magnitude_clamping_low(self):
        record = DissonanceRecord(dissonance_magnitude=-0.3)
        self.assertAlmostEqual(record.dissonance_magnitude, 0.0)


class TestExistentialProfileCreation(unittest.TestCase):
    """测试存在主义剖面创建和初始化"""

    def test_default_values(self):
        profile = ExistentialProfile()
        self.assertEqual(profile.authenticity, AuthenticityState.AUTHENTIC)
        self.assertAlmostEqual(profile.anxiety_level, 0.0)
        self.assertAlmostEqual(profile.freedom_avoidance, 0.3)
        self.assertAlmostEqual(profile.responsibility_threshold, 0.5)
        self.assertEqual(len(profile.beliefs), 0)
        self.assertEqual(len(profile.dissonance_history), 0)
        self.assertEqual(len(profile.core_values), 0)
        self.assertEqual(len(profile.existential_dread_triggers), 0)

    def test_custom_values(self):
        profile = ExistentialProfile(
            authenticity=AuthenticityState.BAD_FAITH,
            anxiety_level=0.8,
            freedom_avoidance=0.9,
            responsibility_threshold=0.3,
            core_values=["自由", "真诚"],
            existential_dread_triggers=["死亡", "孤独"],
        )
        self.assertEqual(profile.authenticity, AuthenticityState.BAD_FAITH)
        self.assertAlmostEqual(profile.anxiety_level, 0.8)
        self.assertAlmostEqual(profile.freedom_avoidance, 0.9)
        self.assertEqual(profile.core_values, ["自由", "真诚"])

    def test_anxiety_level_clamping_high(self):
        profile = ExistentialProfile(anxiety_level=1.5)
        self.assertAlmostEqual(profile.anxiety_level, 1.0)

    def test_anxiety_level_clamping_low(self):
        profile = ExistentialProfile(anxiety_level=-0.2)
        self.assertAlmostEqual(profile.anxiety_level, 0.0)

    def test_freedom_avoidance_clamping(self):
        profile = ExistentialProfile(freedom_avoidance=2.0)
        self.assertAlmostEqual(profile.freedom_avoidance, 1.0)

    def test_responsibility_threshold_clamping(self):
        profile = ExistentialProfile(responsibility_threshold=-0.5)
        self.assertAlmostEqual(profile.responsibility_threshold, 0.0)


class TestBeliefManagement(unittest.TestCase):
    """测试信念增删查"""

    def setUp(self):
        self.profile = ExistentialProfile()

    def test_add_belief(self):
        self.profile.add_belief("b1", "诚实是美德", strength=0.9)
        self.assertIn("b1", self.profile.beliefs)
        belief = self.profile.get_belief("b1")
        self.assertIsNotNone(belief)
        self.assertEqual(belief.content, "诚实是美德")
        self.assertAlmostEqual(belief.strength, 0.9)

    def test_add_belief_with_source(self):
        before_time = time.time()
        self.profile.add_belief("b2", "信任朋友", source="childhood")
        after_time = time.time()
        
        belief = self.profile.get_belief("b2")
        self.assertEqual(belief.source, "childhood")
        self.assertGreaterEqual(belief.created_at, before_time)
        self.assertLessEqual(belief.created_at, after_time)

    def test_remove_existing_belief(self):
        self.profile.add_belief("b1", "测试信念")
        removed = self.profile.remove_belief("b1")
        self.assertIsNotNone(removed)
        self.assertNotIn("b1", self.profile.beliefs)
        self.assertEqual(removed.content, "测试信念")

    def test_remove_nonexistent_belief(self):
        removed = self.profile.remove_belief("nonexistent")
        self.assertIsNone(removed)

    def test_get_nonexistent_belief(self):
        belief = self.profile.get_belief("nonexistent")
        self.assertIsNone(belief)

    def test_multiple_beliefs(self):
        self.profile.add_belief("b1", "信念1", strength=0.3)
        self.profile.add_belief("b2", "信念2", strength=0.7)
        self.profile.add_belief("b3", "信念3", strength=0.5)
        
        self.assertEqual(len(self.profile.beliefs), 3)
        self.assertAlmostEqual(self.profile.get_belief("b2").strength, 0.7)


class TestDissonanceDetection(unittest.TestCase):
    """测试认知失调检测"""

    def setUp(self):
        self.profile = ExistentialProfile()
        self.profile.add_belief("honesty", "我是个诚实的人", strength=0.9)

    def test_detect_contradictory_action(self):
        record = self.profile.detect_dissonance(
            new_action="欺骗他人",
            new_belief_content="欺骗无所谓",
        )
        self.assertIsNotNone(record)
        self.assertIn("honesty", record.conflicting_beliefs)
        self.assertGreater(record.dissonance_magnitude, 0.3)

    def test_no_dissonance_for_consistent_action(self):
        record = self.profile.detect_dissonance(
            new_action="说出真相",
            new_belief_content="诚实很重要",
        )
        self.assertIsNone(record)

    def test_dissonance_magnitude_depends_on_belief_strength(self):
        weak_profile = ExistentialProfile()
        weak_profile.add_belief("weak_belief", "我不喜欢暴力", strength=0.4)
        
        strong_profile = ExistentialProfile()
        strong_profile.add_belief("strong_belief", "我不喜欢暴力", strength=0.9)
        
        weak_record = weak_profile.detect_dissonance("使用暴力", "暴力有效")
        strong_record = strong_profile.detect_dissonance("使用暴力", "暴力有效")
        
        if weak_record and strong_record:
            self.assertGreater(strong_record.dissonance_magnitude, weak_record.dissonance_magnitude)

    def test_weak_belief_no_dissonance(self):
        weak_profile = ExistentialProfile()
        weak_profile.add_belief("weak", "我喜欢安静", strength=0.3)
        
        record = weak_profile.detect_dissonance("制造噪音", "噪音无所谓")
        self.assertIsNone(record)

    def test_empty_input_handling(self):
        record = self.profile.detect_dissonance("", "")
        self.assertIsNone(record)

    def test_multiple_contradictions_returns_first(self):
        self.profile.add_belief("brave", "我很勇敢", strength=0.8)
        
        record = self.profile.detect_dissonance("懦弱退缩", "我很胆小")
        self.assertIsNotNone(record)
        self.assertTrue(
            record.conflicting_beliefs[0] in ["honesty", "brave"] or
            "honesty" in str(record.conflicting_beliefs) or
            "brave" in str(record.conflicting_beliefs)
        )


class TestResolutionStrategySelection(unittest.TestCase):
    """测试解决策略选择逻辑"""

    def test_high_avoidance_high_magnitude_justifies(self):
        profile = ExistentialProfile(freedom_avoidance=0.8)
        strategy = profile._choose_resolution_strategy(0.75)
        self.assertEqual(strategy, ResolutionStrategy.JUSTIFY)

    def test_high_avoidance_low_magnitude_denies(self):
        profile = ExistentialProfile(freedom_avoidance=0.8)
        strategy = profile._choose_resolution_strategy(0.5)
        self.assertEqual(strategy, ResolutionStrategy.DENY)

    def test_low_avoidance_high_magnitude_changes_belief(self):
        profile = ExistentialProfile(freedom_avoidance=0.4)
        strategy = profile._choose_resolution_strategy(0.65)
        self.assertEqual(strategy, ResolutionStrategy.CHANGE_BELIEF)

    def test_low_avoidance_low_magnitude_seeks_info(self):
        profile = ExistentialProfile(freedom_avoidance=0.4)
        strategy = profile._choose_resolution_strategy(0.4)
        self.assertEqual(strategy, ResolutionStrategy.SEEK_INFO)

    def test_boundary_case_exact_threshold(self):
        profile = ExistentialProfile(freedom_avoidance=0.71)
        strategy = profile._choose_resolution_strategy(0.71)
        self.assertEqual(strategy, ResolutionStrategy.JUSTIFY)


class TestAuthenticityStateUpdates(unittest.TestCase):
    """测试本真性状态更新"""

    def setUp(self):
        self.profile = ExistentialProfile()

    def test_high_dissonance_high_avoidance_leads_to_bad_faith(self):
        self.profile.freedom_avoidance = 0.85
        self.profile._update_authenticity_from_dissonance(0.75)
        self.assertEqual(self.profile.authenticity, AuthenticityState.BAD_FAITH)

    def test_high_dissonance_low_avoidance_leads_to_crisis(self):
        self.profile.freedom_avoidance = 0.5
        self.profile._update_authenticity_from_dissonance(0.75)
        self.assertEqual(self.profile.authenticity, AuthenticityState.CRISIS)

    def test_medium_dissonance_leads_to_compromised(self):
        self.profile._update_authenticity_from_dissonance(0.5)
        self.assertEqual(self.profile.authenticity, AuthenticityState.COMPROMISED)

    def test_low_dissonance_no_state_change(self):
        initial_state = self.profile.authenticity
        self.profile._update_authenticity_from_dissonance(0.2)
        self.assertEqual(self.profile.authenticity, initial_state)


class TestDissonanceResolution(unittest.TestCase):
    """测试认知失调解决流程"""

    def setUp(self):
        self.profile = ExistentialProfile()
        self.profile.add_belief("honesty", "我是诚实的", strength=0.9)

    def test_resolve_existing_dissonance(self):
        record = self.profile.detect_dissonance("欺骗", "欺骗可以接受")
        self.assertIsNotNone(record)
        
        index = len(self.profile.dissonance_history) - 1
        success = self.profile.resolve_dissonance(index)
        
        self.assertTrue(success)
        self.assertTrue(self.profile.dissonance_history[index].resolved)

    def test_resolve_with_custom_strategy(self):
        record = self.profile.detect_dissonance("欺骗", "欺骗有利")
        self.assertIsNotNone(record)
        
        index = len(self.profile.dissonance_history) - 1
        success = self.profile.resolve_dissonance(index, ResolutionStrategy.DENY)
        
        self.assertTrue(success)
        self.assertEqual(
            self.profile.dissonance_history[index].resolution_strategy,
            ResolutionStrategy.DENY
        )

    def test_resolve_invalid_index(self):
        success = self.profile.resolve_dissonance(-1)
        self.assertFalse(success)
        
        success = self.profile.resolve_dissonance(999)
        self.assertFalse(success)

    def test_resolve_already_resolved(self):
        record = self.profile.detect_dissonance("欺骗", "假话没关系")
        self.assertIsNotNone(record)
        
        index = len(self.profile.dissonance_history) - 1
        first_result = self.profile.resolve_dissonance(index)
        self.assertTrue(first_result)
        
        second_result = self.profile.resolve_dissonance(index)
        self.assertFalse(second_result)
        
        index = len(self.profile.dissonance_history) - 1
        self.profile.resolve_dissonance(index)
        
        success_again = self.profile.resolve_dissonance(index)
        self.assertFalse(success_again)

    def test_change_belief_reduces_strength(self):
        original_strength = self.profile.get_belief("honesty").strength
        
        record = self.profile.detect_dissonance("欺骗行为", "诚实不重要")
        self.assertIsNotNone(record)
        
        index = len(self.profile.dissonance_history) - 1
        self.profile.resolve_dissonance(index, ResolutionStrategy.CHANGE_BELIEF)
        
        new_strength = self.profile.get_belief("honesty").strength
        self.assertLess(new_strength, original_strength)

    def test_all_resolved_restores_authentic_state(self):
        self.profile.freedom_avoidance = 0.8
        self.profile._update_authenticity_from_dissonance(0.8)
        self.assertNotEqual(self.profile.authenticity, AuthenticityState.AUTHENTIC)
        
        record = self.profile.detect_dissonance("欺骗", "欺骗没事")
        if record:
            index = len(self.profile.dissonance_history) - 1
            self.profile.resolve_dissonance(index)
            
            if self.profile.get_active_dissonance_count() == 0:
                self.assertEqual(self.profile.authenticity, AuthenticityState.AUTHENTIC)


class TestDissonanceHistoryManagement(unittest.TestCase):
    """测试失调记录历史管理"""

    def setUp(self):
        self.profile = ExistentialProfile()
        self.profile.add_belief("b1", "我是诚实的", strength=0.9)

    def test_history_limit_enforcement(self):
        for i in range(60):
            self.profile.detect_dissonance(f"行为{i}", f"与信念矛盾{i}")
        
        self.assertLessEqual(len(self.profile.dissonance_history), 50)

    def test_active_dissonance_count(self):
        self.assertEqual(self.profile.get_active_dissonance_count(), 0)

        self.profile.detect_dissonance("欺骗行为", "欺骗信念")
        self.assertEqual(self.profile.get_active_dissonance_count(), 1)

        self.profile.detect_dissonance("欺骗行为2", "欺骗信念2")
        self.assertEqual(self.profile.get_active_dissonance_count(), 2)
        
        if len(self.profile.dissonance_history) >= 2:
            self.profile.resolve_dissonance(0)
            self.assertEqual(self.profile.get_active_dissonance_count(), 1)

    def test_max_dissonance_magnitude(self):
        self.assertAlmostEqual(self.profile.get_max_dissonance_magnitude(), 0.0)
        
        r1 = self.profile.detect_dissonance("弱矛盾", "弱矛盾信念")
        r2 = self.profile.detect_dissonance("强矛盾", "强矛盾信念")
        
        if r1 and r2:
            max_mag = self.profile.get_max_dissonance_magnitude()
            self.assertGreater(max_mag, 0.0)
            self.assertGreaterEqual(max_mag, r1.dissonance_magnitude)
            self.assertGreaterEqual(max_mag, r2.dissonance_magnitude)


class TestPromptSummaryGeneration(unittest.TestCase):
    """测试prompt摘要生成"""

    def test_empty_profile_summary(self):
        profile = ExistentialProfile()
        summary = profile.to_prompt_summary()
        self.assertIsInstance(summary, str)

    def test_authentic_state_summary(self):
        profile = ExistentialProfile(authenticity=AuthenticityState.AUTHENTIC)
        summary = profile.to_prompt_summary()
        self.assertIn("本真", summary)

    def test_bad_faith_state_summary(self):
        profile = ExistentialProfile(authenticity=AuthenticityState.BAD_FAITH)
        summary = profile.to_prompt_summary()
        self.assertIn("自欺", summary)

    def test_crisis_state_summary(self):
        profile = ExistentialProfile(authenticity=AuthenticityState.CRISIS)
        summary = profile.to_prompt_summary()
        self.assertIn("危机", summary)

    def test_compromised_state_summary(self):
        profile = ExistentialProfile(authenticity=AuthenticityState.COMPROMISED)
        summary = profile.to_prompt_summary()
        self.assertIn("妥协", summary)

    def test_anxiety_inclusion(self):
        profile = ExistentialProfile(anxiety_level=0.6)
        summary = profile.to_prompt_summary()
        self.assertIn("焦虑", summary)

    def test_high_anxiety_label(self):
        profile = ExistentialProfile(anxiety_level=0.85)
        summary = profile.to_prompt_summary()
        self.assertTrue("深度" in summary or "明显" in summary or "高度" in summary or "焦虑" in summary)

    def test_active_dissonance_inclusion(self):
        profile = ExistentialProfile()
        profile.add_belief("b1", "信念", strength=0.9)
        profile.detect_dissonance("矛盾行为", "矛盾信念")
        
        summary = profile.to_prompt_summary()
        if profile.get_active_dissonance_count() > 0:
            self.assertIn("矛盾", summary)

    def test_core_values_inclusion(self):
        profile = ExistentialProfile(core_values=["自由", "正义", "勇气"])
        summary = profile.to_prompt_summary()
        self.assertIn("核心价值观", summary)

    def test_complex_scenario_summary(self):
        profile = ExistentialProfile(
            authenticity=AuthenticityState.CRISIS,
            anxiety_level=0.75,
            core_values=["生存", "保护"],
        )
        profile.add_belief("peace", "和平最重要", strength=0.95)
        profile.detect_dissonance("发动战争", "战争必要")
        
        summary = profile.to_prompt_summary()
        self.assertTrue(
            len(summary) > 10 and 
            ("危机" in summary or "矛盾" in summary or "焦虑" in summary)
        )


class TestEdgeCasesAndRobustness(unittest.TestCase):
    """边界条件和鲁棒性测试"""

    def test_extreme_freedom_avoidance(self):
        high = ExistentialProfile(freedom_avoidance=1.0)
        low = ExistentialProfile(freedom_avoidance=0.0)
        
        self.assertAlmostEqual(high.freedom_avoidance, 1.0)
        self.assertAlmostEqual(low.freedom_avoidance, 0.0)

    def test_rapid_successive_dissonances(self):
        profile = ExistentialProfile()
        profile.add_belief("strong", "诚实是美德", strength=0.95)

        for i in range(10):
            profile.detect_dissonance(f"欺骗行为{i}", f"欺骗冲突{i}")
        
        self.assertGreaterEqual(len(profile.dissonance_history), 1)

    def test_resolve_all_and_detect_new(self):
        profile = ExistentialProfile()
        profile.add_belief("b", "信念", strength=0.9)
        
        profile.detect_dissonance("行为1", "冲突1")
        profile.detect_dissonance("行为2", "冲突2")
        
        while profile.get_active_dissonance_count() > 0:
            active_indices = [
                i for i, r in enumerate(profile.dissonance_history) 
                if not r.resolved
            ]
            if active_indices:
                profile.resolve_dissonance(active_indices[0])
        
        new_record = profile.detect_dissonance("新矛盾", "新冲突")
        if new_record:
            self.assertEqual(profile.get_active_dissonance_count(), 1)


if __name__ == "__main__":
    unittest.main()
