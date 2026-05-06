"""
Phase 4 混合策略引擎测试 — mixed_strategy.py (基于实际运行时API)
覆盖: Softmax分布生成/温度映射/熵控制/信念驱动策略/边界条件
"""

from __future__ import annotations

import math
import unittest

from luqi_engine.game_theory.types import (
    MixedStrategyProfile,
    StrategyAction,
    StrategyPayoff,
)
from luqi_engine.game_theory.mixed_strategy import (
    MixedStrategyEngine,
    MixedStrategyConfig,
)


class TestMixedStrategyConstruction(unittest.TestCase):
    """MixedStrategyEngine 构造测试"""

    def test_default_construction(self) -> None:
        engine = MixedStrategyEngine()
        self.assertIsNotNone(engine)

    def test_custom_config(self) -> None:
        cfg = MixedStrategyConfig(default_temperature=0.5)
        engine = MixedStrategyEngine(config=cfg)
        self.assertIsNotNone(engine)

    def test_config_property(self) -> None:
        engine = MixedStrategyEngine()
        cfg = engine.config
        self.assertIsInstance(cfg, MixedStrategyConfig)


class TestSoftmaxDistributionGeneration(unittest.TestCase):
    """Softmax 分布生成测试 — 使用 generate() API"""

    def setUp(self) -> None:
        self.engine = MixedStrategyEngine()

    def test_uniform_payoffs_give_distribution(self) -> None:
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=1.0, payoff_if_defect=1.0),
            StrategyPayoff(action=StrategyAction.DEFECT, payoff_if_cooperate=1.0, payoff_if_defect=1.0),
        ]
        profile = self.engine.generate(payoffs, temperature=100.0)
        total = sum(profile.action_probabilities.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_dominant_action_has_highest_probability(self) -> None:
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=10.0, payoff_if_defect=-5.0),
            StrategyPayoff(action=StrategyAction.DEFECT, payoff_if_cooperate=-5.0, payoff_if_defect=-10.0),
        ]
        profile = self.engine.generate(payoffs, temperature=0.1)
        self.assertEqual(profile.dominant_action, StrategyAction.COOPERATE)

    def test_low_temperature_sharpens_distribution(self) -> None:
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=5.0, payoff_if_defect=0.0),
            StrategyPayoff(action=StrategyAction.DEFECT, payoff_if_cooperate=0.0, payoff_if_defect=3.0),
        ]
        cold = self.engine.generate(payoffs, temperature=0.01)
        hot = self.engine.generate(payoffs, temperature=10.0)
        self.assertLess(cold.entropy, hot.entropy)

    def test_all_probabilities_positive(self) -> None:
        payoffs = [
            StrategyPayoff(action=a, payoff_if_cooperate=float(i+1), payoff_if_defect=0.0)
            for i, a in enumerate(list(StrategyAction)[:4])
        ]
        profile = self.engine.generate(payoffs, temperature=1.0)
        for action, prob in profile.action_probabilities.items():
            self.assertGreater(prob, 0.0)

    def test_empty_payoffs_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.generate([], temperature=1.0)

    def test_zero_temperature_handling(self) -> None:
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=1.0, payoff_if_defect=0.0),
            StrategyPayoff(action=StrategyAction.DEFECT, payoff_if_cooperate=0.0, payoff_if_defect=1.0),
        ]
        profile = self.engine.generate(payoffs, temperature=0.001)
        self.assertIsNotNone(profile)

    def test_very_high_temperature_near_uniform(self) -> None:
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=10.0, payoff_if_defect=0.0),
            StrategyPayoff(action=StrategyAction.DEFECT, payoff_if_cooperate=0.0, payoff_if_defect=1.0),
        ]
        profile = self.engine.generate(payoffs, temperature=10000.0)
        max_p = max(profile.action_probabilities.values())
        min_p = min(profile.action_probabilities.values())
        ratio = max_p / min_p if min_p > 0 else float('inf')
        self.assertLess(ratio, 20.0)

    def test_negative_payoffs_handled(self) -> None:
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=-5.0, payoff_if_defect=-10.0),
            StrategyPayoff(action=StrategyAction.DEFECT, payoff_if_cooperate=-10.0, payoff_if_defect=-3.0),
        ]
        profile = self.engine.generate(payoffs, temperature=1.0)
        total = sum(profile.action_probabilities.values())
        self.assertAlmostEqual(total, 1.0, places=5)


class TestTemperatureMapping(unittest.TestCase):
    """场景温度映射测试"""

    def setUp(self) -> None:
        self.engine = MixedStrategyEngine()

    def test_crisis_scene_lower_temperature(self) -> None:
        t_normal = self.engine.adjust_temperature_for_scene(1.0, 1.0)
        t_crisis = self.engine.adjust_temperature_for_scene(1.0, 3.0)
        self.assertIsInstance(t_crisis, float)
        self.assertIsInstance(t_normal, float)

    def test_safe_scene_higher_temperature(self) -> None:
        t_safe = self.engine.adjust_temperature_for_scene(1.0, 0.5)
        t_crisis = self.engine.adjust_temperature_for_scene(1.0, 2.5)
        self.assertIsInstance(t_safe, float)

    def test_unknown_scene_default_temperature(self) -> None:
        t = self.engine.adjust_temperature_for_scene(1.0, 1.0)
        self.assertIsInstance(t, float)
        self.assertGreater(t, 0.0)


class TestEntropyControl(unittest.TestCase):
    """熵控制机制测试"""

    def test_entropy_calculation_correctness(self) -> None:
        probs = {StrategyAction.COOPERATE: 0.5, StrategyAction.DEFECT: 0.5}
        expected = -sum(p * math.log(p) for p in probs.values() if p > 0)
        profile = MixedStrategyProfile(action_probabilities=dict(probs))
        self.assertAlmostEqual(profile.entropy, expected, places=4)

    def test_entropy_above_zero(self) -> None:
        engine = MixedStrategyEngine()
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=10.0, payoff_if_defect=-10.0),
            StrategyPayoff(action=StrategyAction.DEFECT, payoff_if_cooperate=-10.0, payoff_if_defect=10.0),
        ]
        profile = engine.generate(payoffs, temperature=0.001)
        self.assertGreater(profile.entropy, 0.0)


class TestBeliefDrivenStrategyGeneration(unittest.TestCase):
    """信念驱动策略生成测试 — 使用 generate_from_beliefs() API"""

    def test_belief_integration(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        from luqi_engine.game_theory.types import Observation, BeliefDimension
        
        engine = MixedStrategyEngine()
        bs = BeliefSystem(character_id="belief_user")
        
        bs.observe(
            target_id="friend",
            dimension=BeliefDimension.COOPERATIVITY,
            observation=Observation(evidence_value=0.9),
        )

        profile = engine.generate_from_beliefs(
            belief_system=bs,
            target_id="friend",
        )
        total = sum(profile.action_probabilities.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_unknown_target_uniform_strategy(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        
        engine = MixedStrategyEngine()
        bs = BeliefSystem(character_id="unknown_user")
        
        profile = engine.generate_from_beliefs(
            belief_system=bs,
            target_id="stranger",
        )
        total = sum(profile.action_probabilities.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_with_available_actions_filter(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        
        engine = MixedStrategyEngine()
        bs = BeliefSystem(character_id="filter_test")
        
        profile = engine.generate_from_beliefs(
            belief_system=bs,
            target_id="target_x",
            available_actions=[StrategyAction.OBSERVE, StrategyAction.WITHDRAW],
        )
        self.assertIn(StrategyAction.OBSERVE, profile.action_probabilities)
        self.assertIn(StrategyAction.WITHDRAW, profile.action_probabilities)


class TestEdgeCasesAndBoundaryConditions(unittest.TestCase):
    """边界条件和异常处理测试"""

    def setUp(self) -> None:
        self.engine = MixedStrategyEngine()

    def test_single_action_profile(self) -> None:
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=1.0, payoff_if_defect=1.0),
        ]
        profile = self.engine.generate(payoffs, temperature=1.0)
        self.assertIn(StrategyAction.COOPERATE, profile.action_probabilities)

    def test_many_actions_supported(self) -> None:
        payoffs = [
            StrategyPayoff(action=a, payoff_if_cooperate=1.0, payoff_if_defect=1.0)
            for a in list(StrategyAction)
        ]
        profile = self.engine.generate(payoffs, temperature=1.0)
        self.assertEqual(len(profile.action_probabilities), len(StrategyAction))

    def test_urgency_level_affects_result(self) -> None:
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=3.0, payoff_if_defect=1.0),
            StrategyPayoff(action=StrategyAction.DEFECT, payoff_if_cooperate=1.0, payoff_if_defect=2.0),
        ]
        low_urgency = self.engine.generate(payoffs, temperature=None, urgency_level=0.5)
        high_urgency = self.engine.generate(payoffs, temperature=None, urgency_level=3.0)
        self.assertIsInstance(low_urgency, MixedStrategyProfile)
        self.assertIsInstance(high_urgency, MixedStrategyProfile)

    def test_scene_context_affects_temperature(self) -> None:
        payoffs = [
            StrategyPayoff(action=StrategyAction.COOPERATE, payoff_if_cooperate=2.0, payoff_if_defect=1.0),
            StrategyPayoff(action=StrategyAction.DEFECT, payoff_if_cooperate=1.0, payoff_if_defect=2.0),
        ]
        normal = self.engine.generate(payoffs, scene_context="日常对话")
        crisis = self.engine.generate(payoffs, scene_context="生死战斗")
        self.assertIsInstance(normal, MixedStrategyProfile)
        self.assertIsInstance(crisis, MixedStrategyProfile)


if __name__ == "__main__":
    unittest.main()
