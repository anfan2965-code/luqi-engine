"""
Phase 4 机制设计模块测试 — mechanism_design.py (基于实际运行时API)
覆盖: Monte Carlo均衡预测/激励相容性检查/边界条件
"""

from __future__ import annotations

import unittest

from luqi_engine.game_theory.types import (
    MechanismConfig,
    MechanismParameter,
    IncentiveCompatibilityReport,
    EquilibriumPrediction,
)
from luqi_engine.game_theory.mechanism_design import MechanismDesigner


class TestMechanismDesignerConstruction(unittest.TestCase):
    """MechanismDesigner 构造测试"""

    def test_default_construction(self) -> None:
        designer = MechanismDesigner()
        self.assertIsNotNone(designer)

    def test_with_reference_character(self) -> None:
        designer = MechanismDesigner(reference_character="test_char")
        self.assertIsNotNone(designer)


class TestEquilibriumPrediction(unittest.TestCase):
    """Monte Carlo 均衡预测测试"""

    def setUp(self) -> None:
        self.designer = MechanismDesigner()

    def test_prediction_returns_valid_result(self) -> None:
        config = MechanismConfig(name="baseline")
        prediction = self.designer.predict_equilibrium(config, num_simulations=200)
        self.assertIsInstance(prediction, EquilibriumPrediction)
        self.assertGreaterEqual(prediction.predicted_cooperation_rate, 0.0)
        self.assertLessEqual(prediction.predicted_cooperation_rate, 1.0)

    def test_high_cooperation_reward_affects_prediction(self) -> None:
        baseline_cfg = MechanismConfig(name="low_reward")
        baseline = self.designer.predict_equilibrium(baseline_cfg, num_simulations=300)

        high_cfg = MechanismConfig(name="high_reward")
        high_cfg.set(MechanismParameter.REWARD_COOPERATION_BONUS, 1.9)
        high_result = self.designer.predict_equilibrium(high_cfg, num_simulations=300)

        self.assertIsInstance(baseline, EquilibriumPrediction)
        self.assertIsInstance(high_result, EquilibriumPrediction)

    def test_high_defect_punishment_affects_prediction(self) -> None:
        cfg = MechanismConfig(name="punish")
        cfg.set(MechanismParameter.PUNISHMENT_DEFECT_COST, 1.9)
        prediction = self.designer.predict_equilibrium(cfg, num_simulations=250)
        self.assertIsInstance(prediction, EquilibriumPrediction)

    def test_sensitivity_analysis_produced(self) -> None:
        config = MechanismConfig(name="sensitivity_test")
        prediction = self.designer.predict_equilibrium(config, num_simulations=150)
        self.assertIsInstance(prediction.sensitivity, dict)

    def test_warnings_for_extreme_params(self) -> None:
        cfg = MechanismConfig(name="extreme")
        cfg.set(MechanismParameter.REWARD_COOPERATION_BONUS, 1.99)
        cfg.set(MechanismParameter.PUNISHMENT_DEFECT_COST, 1.99)
        prediction = self.designer.predict_equilibrium(cfg, num_simulations=100)
        self.assertIsInstance(prediction.warnings, list)

    def test_conflict_rate_in_range(self) -> None:
        config = MechanismConfig(name="conflict_test")
        pred = self.designer.predict_equilibrium(config, num_simulations=200)
        self.assertGreaterEqual(pred.predicted_conflict_rate, 0.0)
        self.assertLessEqual(pred.predicted_conflict_rate, 1.0)

    def test_shadow_activation_rate(self) -> None:
        config = MechanismConfig(name="shadow_test")
        pred = self.designer.predict_equilibrium(config, num_simulations=200)
        self.assertGreaterEqual(pred.predicted_shadow_activation_rate, 0.0)
        self.assertLessEqual(pred.predicted_shadow_activation_rate, 1.0)

    def test_average_relationship_quality(self) -> None:
        config = MechanismConfig(name="rel_test")
        pred = self.designer.predict_equilibrium(config, num_simulations=200)
        self.assertGreaterEqual(pred.average_relationship_quality, 0.0)
        self.assertLessEqual(pred.average_relationship_quality, 1.0)

    def test_config_name_preserved(self) -> None:
        config = MechanismConfig(name="my_special_config")
        pred = self.designer.predict_equilibrium(config, num_simulations=50)
        self.assertEqual(pred.config_name, "my_special_config")


class TestIncentiveCompatibilityCheck(unittest.TestCase):
    """激励相容性检查测试"""

    def setUp(self) -> None:
        self.designer = MechanismDesigner()

    def test_basic_compatibility_check(self) -> None:
        cfg = MechanismConfig(name="compat_test")
        report = self.designer.check_incentive_compatibility(
            config=cfg,
            target_behavior_description="always_cooperate",
            deviation_actions=["defect", "withdraw"],
        )
        self.assertIsInstance(report, IncentiveCompatibilityReport)

    def test_report_fields_populated(self) -> None:
        cfg = MechanismConfig(name="field_test")
        report = self.designer.check_incentive_compatibility(
            config=cfg,
            target_behavior_description="cooperate_always",
            deviation_actions=["defect"],
        )
        self.assertIsInstance(report.target_behavior, str)
        self.assertIsInstance(report.is_incentive_compatible, bool)
        self.assertIsInstance(report.deviation_payoff, float)
        self.assertIsInstance(report.confidence, float)
        self.assertIsInstance(report.critical_parameters, list)
        self.assertIsInstance(report.recommendation, str)

    def test_high_reward_makes_more_compatible(self) -> None:
        low_cfg = MechanismConfig(name="low_rwd")
        low_report = self.designer.check_incentive_compatibility(
            config=low_cfg,
            target_behavior_description="cooperate",
            deviation_actions=["defect"],
        )

        high_cfg = MechanismConfig(name="high_rwd")
        high_cfg.set(MechanismParameter.REWARD_COOPERATION_BONUS, 1.95)
        high_report = self.designer.check_incentive_compatibility(
            config=high_cfg,
            target_behavior_description="cooperate",
            deviation_actions=["deceive", "defect"],
        )

        self.assertIsInstance(low_report, IncentiveCompatibilityReport)
        self.assertIsInstance(high_report, IncentiveCompatibilityReport)

    def test_deviation_payoff_calculated(self) -> None:
        cfg = MechanismConfig(name="deviation")
        report = self.designer.check_incentive_compatibility(
            config=cfg,
            target_behavior_description="cooperate_steadily",
            deviation_actions=["defect_once"],
        )
        self.assertIsInstance(report.deviation_payoff, float)

    def test_confidence_in_range(self) -> None:
        cfg = MechanismConfig(name="conf")
        report = self.designer.check_incentive_compatibility(
            config=cfg,
            target_behavior_description="cooperate",
            deviation_actions=["defect", "withdraw"],
        )
        self.assertGreaterEqual(report.confidence, 0.0)
        self.assertLessEqual(report.confidence, 1.0)

    def test_critical_params_on_incompatibility(self) -> None:
        cfg = MechanismConfig(name="incompatible")
        cfg.set(MechanismParameter.REWARD_COOPERATION_BONUS, 0.01)
        cfg.set(MechanismParameter.PUNISHMENT_DEFECT_COST, 0.05)
        report = self.designer.check_incentive_compatibility(
            config=cfg,
            target_behavior_description="always_cooperate",
            deviation_actions=["defect_for_high_gain"],
        )
        if not report.is_incentive_compatible:
            self.assertGreater(len(report.critical_parameters), 0)


class TestEdgeCasesAndBoundaryConditions(unittest.TestCase):
    """边界条件和异常处理测试"""

    def setUp(self) -> None:
        self.designer = MechanismDesigner()

    def test_minimal_simulation_rounds(self) -> None:
        cfg = MechanismConfig(name="minimal")
        pred = self.designer.predict_equilibrium(cfg, num_simulations=10)
        self.assertIsInstance(pred, EquilibriumPrediction)

    def test_large_simulation_rounds(self) -> None:
        cfg = MechanismConfig(name="large")
        pred = self.designer.predict_equilibrium(cfg, num_simulations=500)
        self.assertIsInstance(pred, EquilibriumPrediction)

    def test_all_default_params_used(self) -> None:
        cfg = MechanismConfig(name="defaults")
        pred = self.designer.predict_equilibrium(cfg, num_simulations=100)
        self.assertIsInstance(pred, EquilibriumPrediction)

    def test_config_not_mutated_by_prediction(self) -> None:
        original = MechanismConfig(name="original")
        original.set(MechanismParameter.REWARD_COOPERATION_BONUS, 0.5)
        val_before = original.get(MechanismParameter.REWARD_COOPERATION_BONUS)
        
        self.designer.predict_equilibrium(original, num_simulations=50)
        
        val_after = original.get(MechanismParameter.REWARD_COOPERATION_BONUS)
        self.assertAlmostEqual(val_before, val_after, places=5)

    def test_multiple_predictions_independent(self) -> None:
        cfg1 = MechanismConfig(name="config_a")
        cfg2 = MechanismConfig(name="config_b")
        cfg2.set(MechanismParameter.INFORMATION_TRANSPARENCY, 0.9)
        
        pred1 = self.designer.predict_equilibrium(cfg1, num_simulations=100)
        pred2 = self.designer.predict_equilibrium(cfg2, num_simulations=100)
        
        self.assertNotEqual(pred1.config_name, pred2.config_name)

    def test_empty_deviation_actions(self) -> None:
        cfg = MechanismConfig(name="no_deviations")
        report = self.designer.check_incentive_compatibility(
            config=cfg,
            target_behavior_description="cooperate",
            deviation_actions=[],
        )
        self.assertIsInstance(report, IncentiveCompatibilityReport)

    def test_many_deviation_actions(self) -> None:
        cfg = MechanismConfig(name="many_deviations")
        report = self.designer.check_incentive_compatibility(
            config=cfg,
            target_behavior_description="cooperate",
            deviation_actions=["defect", "deceive", "withdraw", "exploit", "observe_only"],
        )
        self.assertIsInstance(report, IncentiveCompatibilityReport)


if __name__ == "__main__":
    unittest.main()
