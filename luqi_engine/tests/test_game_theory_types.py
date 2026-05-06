"""
Phase 4 博弈论类型系统测试 — types.py (基于实际运行时API)
覆盖: 枚举值/数据类构造/属性计算/边界条件/序列化
"""

from __future__ import annotations

import math
import time
import unittest

from luqi_engine.game_theory.types import (
    BeliefDimension,
    BeliefState,
    BeliefSystemConfig,
    BeliefUpdateOutcome,
    CredibilityScore,
    EquilibriumPrediction,
    IncentiveCompatibilityReport,
    MechanismConfig,
    MechanismParameter,
    MixedStrategyProfile,
    Observation,
    ObservationType,
    StrategyAction,
    StrategyPayoff,
    ThreatRecord,
    ThreatType,
    ThreatCredibilityConfig,
    CommitmentLevel,
)


class TestBeliefDimensionEnum(unittest.TestCase):
    """信念维度枚举测试"""

    def test_all_dimensions_exist(self) -> None:
        expected = [
            "COOPERATIVITY", "THREAT_LEVEL", "COMPETENCE",
            "ALIGNMENT", "HONESTY", "STABILITY",
        ]
        actual = [d.name for d in BeliefDimension]
        self.assertEqual(sorted(expected), sorted(actual))

    def test_dimension_count(self) -> None:
        self.assertEqual(len(BeliefDimension), 6)

    def test_dimension_values_unique(self) -> None:
        values = [d.value for d in BeliefDimension]
        self.assertEqual(len(values), len(set(values)))


class TestStrategyActionEnum(unittest.TestCase):
    """策略动作枚举测试"""

    def test_all_actions_exist(self) -> None:
        expected = [
            "COOPERATE", "DEFECT", "EXPLOIT", "OBSERVE",
            "WITHDRAW", "NEGOTIATE", "DECEIVE", "SUPPORT",
        ]
        actual = [a.name for a in StrategyAction]
        self.assertEqual(sorted(expected), sorted(actual))


class TestThreatTypeEnum(unittest.TestCase):
    """威胁类型枚举测试"""

    def test_threat_types(self) -> None:
        expected = ["BLUFF", "COMMITMENT", "SIGNALING", "RETALIATORY", "DETERRENCE"]
        actual = [t.name for t in ThreatType]
        self.assertEqual(sorted(expected), sorted(actual))


class TestObservationType(unittest.TestCase):
    """观测类型枚举测试"""

    def test_observation_types(self) -> None:
        types = [o.name for o in ObservationType]
        self.assertIn("DIRECT_ACTION", types)
        self.assertIn("REPORTED_INFO", types)
        self.assertIn("SIGNAL_SENT", types)
        self.assertIn("ABSENCE_OF_ACTION", types)
        self.assertIn("CONTEXTUAL_CUE", types)


class TestCommitmentLevelEnum(unittest.TestCase):
    """承诺等级枚举测试"""

    def test_commitment_levels(self) -> None:
        levels = [l.name for l in CommitmentLevel]
        self.assertIn("NONE", levels)
        self.assertIn("VERBAL", levels)
        self.assertIn("MATERIAL", levels)
        self.assertIn("IRREVERSIBLE", levels)


class TestBeliefUpdateOutcomeEnum(unittest.TestCase):
    """信念更新结果枚举测试"""

    def test_outcome_values(self) -> None:
        outcomes = [o.name for o in BeliefUpdateOutcome]
        self.assertIn("STRENGTHENED", outcomes)
        self.assertIn("WEAKENED", outcomes)
        self.assertIn("REVERSED", outcomes)
        self.assertIn("UNCHANGED", outcomes)


class TestBeliefStateDataClass(unittest.TestCase):
    """BeliefState 数据类测试 — Beta分布参数化"""

    def test_default_construction(self) -> None:
        bs = BeliefState()
        
        self.assertEqual(bs.target_id, "")
        self.assertEqual(bs.dimension, BeliefDimension.COOPERATIVITY)
        self.assertAlmostEqual(bs.alpha, 1.0, places=5)
        self.assertAlmostEqual(bs.beta_param, 1.0, places=5)
        self.assertEqual(bs.total_observations, 0)
        self.assertAlmostEqual(bs.half_life_days, 30.0, places=5)

    def test_expected_value_uniform_prior(self) -> None:
        bs = BeliefState(alpha=1.0, beta_param=1.0)
        self.assertAlmostEqual(bs.expected_value, 0.5, places=5)

    def test_expected_value_high_cooperation(self) -> None:
        bs = BeliefState(alpha=9.0, beta_param=1.0)
        self.assertAlmostEqual(bs.expected_value, 0.9, places=4)

    def test_expected_value_low_cooperation(self) -> None:
        bs = BeliefState(alpha=1.0, beta_param=9.0)
        self.assertAlmostEqual(bs.expected_value, 0.1, places=4)

    def test_expected_value_zero_total_clamped(self) -> None:
        """α+β被钳制到MIN后 → 非零期望"""
        bs = BeliefState(alpha=0.0, beta_param=0.0)
        ev = bs.expected_value
        self.assertIsInstance(ev, float)
        self.assertGreaterEqual(ev, 0.0)
        self.assertLessEqual(ev, 1.0)

    def test_confidence_uniform_prior(self) -> None:
        """先验 α=β=1 → 置信度约 0.71 (基于Beta方差公式)"""
        bs = BeliefState(alpha=1.0, beta_param=1.0)
        self.assertGreater(bs.confidence, 0.5)
        self.assertLess(bs.confidence, 0.8)

    def test_confidence_high_certainty(self) -> None:
        bs = BeliefState(alpha=100.0, beta_param=100.0)
        self.assertGreater(bs.confidence, 0.85)

    def test_confidence_extreme_values(self) -> None:
        bs = BeliefState(alpha=50.0, beta_param=2.0)
        self.assertGreater(bs.confidence, 0.8)

    def test_confidence_min_params(self) -> None:
        """MIN钳制后的置信度 > 0"""
        bs = BeliefState(alpha=0.0, beta_param=0.0)
        conf = bs.confidence
        self.assertIsInstance(conf, float)
        self.assertGreaterEqual(conf, 0.0)

    def test_to_dict_roundtrip(self) -> None:
        bs = BeliefState(
            target_id="target_001",
            dimension=BeliefDimension.HONESTY,
            alpha=5.0,
            beta_param=3.0,
            total_observations=10,
            half_life_days=15.0,
        )
        d = bs.to_dict()
        self.assertEqual(d["target_id"], "target_001")
        self.assertEqual(d["dimension"], "HONESTY")
        self.assertAlmostEqual(d["alpha"], 5.0, places=5)
        self.assertAlmostEqual(d["beta"], 3.0, places=5)

    def test_negative_alpha_handling(self) -> None:
        bs = BeliefState(alpha=-1.0, beta_param=1.0)
        val = bs.expected_value
        self.assertIsInstance(val, float)

    def test_large_parameters(self) -> None:
        bs = BeliefState(alpha=1e6, beta_param=1e6)
        val = bs.expected_value
        self.assertAlmostEqual(val, 0.5, places=3)


class TestObservationDataClass(unittest.TestCase):
    """Observation 数据类测试 — 基于运行时验证的实际行为"""

    def test_default_observation(self) -> None:
        obs = Observation()
        self.assertIsInstance(obs.evidence_value, float)
        self.assertEqual(obs.observation_type, ObservationType.DIRECT_ACTION)
        self.assertIsInstance(obs.source_reliability, float)

    def test_evidence_in_valid_range(self) -> None:
        obs = Observation()
        self.assertGreaterEqual(obs.evidence_value, 0.0)
        self.assertLessEqual(obs.evidence_value, 1.0)

    def test_source_reliability_in_range(self) -> None:
        obs = Observation(source_reliability=0.5)
        self.assertGreaterEqual(obs.source_reliability, 0.0)
        self.assertLessEqual(obs.source_reliability, 1.0)

    def test_observation_type_settable(self) -> None:
        obs = Observation(observation_type=ObservationType.REPORTED_INFO)
        self.assertEqual(obs.observation_type, ObservationType.REPORTED_INFO)

    def test_description_preserved(self) -> None:
        obs = Observation(description="test observation content")
        self.assertEqual(obs.description, "test observation content")

    def test_timestamp_auto_generated(self) -> None:
        before = time.time()
        obs = Observation()
        after = time.time()
        self.assertGreaterEqual(obs.timestamp, before)
        self.assertLessEqual(obs.timestamp, after + 1)


class TestThreatRecordDataClass(unittest.TestCase):
    """ThreatRecord 数据类测试"""

    def test_default_threat(self) -> None:
        tr = ThreatRecord()
        self.assertEqual(tr.threat_type, ThreatType.BLUFF)
        self.assertFalse(tr.was_executed)
        self.assertIsNone(tr.execution_delay)

    def test_executed_threat(self) -> None:
        tr = ThreatRecord(was_executed=True, execution_delay=60.0)
        self.assertTrue(tr.was_executed)
        self.assertIsNotNone(tr.execution_delay)

    def test_threat_auto_timestamp(self) -> None:
        before = time.time()
        tr = ThreatRecord(content="test threat")
        after = time.time()
        self.assertGreaterEqual(tr.timestamp, before)
        self.assertLessEqual(tr.timestamp, after + 1)

    def test_cost_clamped(self) -> None:
        tr = ThreatRecord(estimated_cost=5.0)
        self.assertLessEqual(tr.estimated_cost, 1.0)
        self.assertGreaterEqual(tr.estimated_cost, 0.0)


class TestCredibilityScoreDataClass(unittest.TestCase):
    """CredibilityScore 数据类测试"""

    def test_default_score(self) -> None:
        cs = CredibilityScore()
        self.assertAlmostEqual(cs.overall_score, 0.5, places=5)
        self.assertEqual(cs.sample_size, 0)
        self.assertFalse(cs.is_reliable)

    def test_high_credibility(self) -> None:
        cs = CredibilityScore(
            overall_score=0.92,
            consistency_score=0.95,
            cost_signal_score=0.88,
            recency_score=0.90,
            pattern_score=0.94,
            sample_size=20,
        )
        self.assertAlmostEqual(cs.overall_score, 0.92, places=5)
        self.assertTrue(cs.is_reliable)

    def test_is_reliable_threshold(self) -> None:
        cs_low = CredibilityScore(overall_score=0.29, sample_size=3)
        self.assertFalse(cs_low.is_reliable)

        cs_high = CredibilityScore(overall_score=0.91, sample_size=8)
        self.assertTrue(cs_high.is_reliable)

    def test_to_dict(self) -> None:
        cs = CredibilityScore(entity_id="test_ent", overall_score=0.77)
        d = cs.to_dict()
        self.assertEqual(d["entity_id"], "test_ent")
        self.assertAlmostEqual(d["overall_score"], 0.77, places=3)


class TestMixedStrategyProfile(unittest.TestCase):
    """MixedStrategyProfile 数据类测试"""

    def test_default_profile(self) -> None:
        mp = MixedStrategyProfile()
        self.assertIsNotNone(mp)

    def test_probability_normalization(self) -> None:
        probs = {
            StrategyAction.COOPERATE: 0.4,
            StrategyAction.DEFECT: 0.3,
            StrategyAction.OBSERVE: 0.2,
            StrategyAction.WITHDRAW: 0.1,
        }
        mp = MixedStrategyProfile(action_probabilities=dict(probs))
        total = sum(mp.action_probabilities.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_dominant_action_detection(self) -> None:
        probs = {
            StrategyAction.COOPERATE: 0.6,
            StrategyAction.DEFECT: 0.25,
            StrategyAction.OBSERVE: 0.15,
        }
        mp = MixedStrategyProfile(action_probabilities=dict(probs))
        self.assertEqual(mp.dominant_action, StrategyAction.COOPERATE)

    def test_entropy_calculation(self) -> None:
        probs = {
            StrategyAction.COOPERATE: 0.5,
            StrategyAction.DEFECT: 0.5,
        }
        mp = MixedStrategyProfile(action_probabilities=dict(probs))
        expected_entropy = -0.5 * math.log(0.5) * 2
        self.assertAlmostEqual(mp.entropy, expected_entropy, places=4)

    def test_to_dict(self) -> None:
        mp = MixedStrategyProfile(
            action_probabilities={StrategyAction.COOPERATE: 1.0},
            temperature=1.5,
        )
        d = mp.to_dict()
        self.assertIn("action_probabilities", d)
        self.assertIn("temperature", d)
        self.assertIn("entropy", d)


class TestEquilibriumPrediction(unittest.TestCase):
    """EquilibriumPrediction 数据类测试"""

    def test_default_prediction(self) -> None:
        ep = EquilibriumPrediction()
        self.assertAlmostEqual(ep.predicted_cooperation_rate, 0.5, places=5)
        self.assertAlmostEqual(ep.predicted_conflict_rate, 0.2, places=5)

    def test_custom_fields(self) -> None:
        ep = EquilibriumPrediction(
            config_name="test_config",
            predicted_cooperation_rate=0.75,
            predicted_conflict_rate=0.12,
        )
        self.assertEqual(ep.config_name, "test_config")
        self.assertAlmostEqual(ep.predicted_cooperation_rate, 0.75, places=5)

    def test_warnings_list(self) -> None:
        ep = EquilibriumPrediction(warnings=["warning1", "warning2"])
        self.assertEqual(len(ep.warnings), 2)

    def test_sensitivity_dict(self) -> None:
        ep = EquilibriumPrediction(sensitivity={"param_a": 0.3})
        self.assertIn("param_a", ep.sensitivity)


class TestMechanismConfig(unittest.TestCase):
    """MechanismConfig 数据类测试 — 基于实际运行时行为"""

    def test_default_config(self) -> None:
        mc = MechanismConfig()
        val = mc.get(MechanismParameter.REWARD_COOPERATION_BONUS, 0.3)
        self.assertIsInstance(val, float)

    def test_set_and_get_within_bounds(self) -> None:
        mc = MechanismConfig()
        bounds = (0.0, 2.0)
        test_val = (bounds[0] + bounds[1]) / 2.0
        mc.set(MechanismParameter.INFORMATION_TRANSPARENCY, test_val)
        val = mc.get(MechanismParameter.INFORMATION_TRANSPARENCY)
        self.assertIsInstance(val, float)

    def test_copy_creates_independent_object(self) -> None:
        mc1 = MechanismConfig()
        mc1.set(MechanismParameter.SHADOW_ACTIVATION_THRESHOLD, 0.5)
        mc2 = mc1.copy()
        self.assertIsNot(mc1.parameter_values, mc2.parameter_values)

    def test_parameter_clamping_high(self) -> None:
        mc = MechanismConfig()
        mc.set(MechanismParameter.INFORMATION_TRANSPARENCY, 5.0)
        val = mc.get(MechanismParameter.INFORMATION_TRANSPARENCY)
        self.assertLessEqual(val, 1.0)

    def test_parameter_clamping_low(self) -> None:
        mc = MechanismConfig()
        mc.set(MechanismParameter.INFORMATION_TRANSPARENCY, -1.0)
        val = mc.get(MechanismParameter.INFORMATION_TRANSPARENCY)
        self.assertGreaterEqual(val, 0.0)

    def test_to_dict(self) -> None:
        mc = MechanismConfig()
        mc.set(MechanismParameter.REWARD_COOPERATION_BONUS, 0.42)
        d = mc.to_dict()
        self.assertIsInstance(d, dict)


class TestIncentiveCompatibilityReport(unittest.TestCase):
    """IncentiveCompatibilityReport 测试"""

    def test_compatible_report(self) -> None:
        icr = IncentiveCompatibilityReport(
            target_behavior="COOPERATE",
            is_incentive_compatible=True,
            confidence=0.92,
        )
        self.assertTrue(icr.is_incentive_compatible)

    def test_incompatible_report(self) -> None:
        icr = IncentiveCompatibilityReport(
            target_behavior="COOPERATE",
            is_incentive_compatible=False,
            deviation_payoff=0.65,
            confidence=0.88,
        )
        self.assertFalse(icr.is_incentive_compatible)


class TestStrategyPayoff(unittest.TestCase):
    """StrategyPayoff 测试"""

    def test_expected_payoff(self) -> None:
        sp = StrategyPayoff(
            action=StrategyAction.COOPERATE,
            payoff_if_cooperate=5.0,
            payoff_if_defect=-2.0,
            estimated_probability=0.7,
        )
        expected = 0.7 * 5.0 + 0.3 * (-2.0)
        self.assertAlmostEqual(sp.expected_payoff, expected, places=5)

    def test_risk_calculation(self) -> None:
        sp = StrategyPayoff(
            action=StrategyAction.COOPERATE,
            payoff_if_cooperate=10.0,
            payoff_if_defect=-5.0,
        )
        self.assertAlmostEqual(sp.risk, 15.0, places=5)


class TestBeliefSystemConfig(unittest.TestCase):
    """BeliefSystemConfig 测试"""

    def test_default_config(self) -> None:
        cfg = BeliefSystemConfig()
        self.assertAlmostEqual(cfg.default_half_life_days, 30.0, places=5)

    def test_custom_config(self) -> None:
        cfg = BeliefSystemConfig(default_half_life_days=60.0, max_tracked_targets=50)
        self.assertAlmostEqual(cfg.default_half_life_days, 60.0, places=5)
        self.assertEqual(cfg.max_tracked_targets, 50)


class TestThreatCredibilityConfig(unittest.TestCase):
    """ThreatCredibilityConfig 测试"""

    def test_default_config(self) -> None:
        cfg = ThreatCredibilityConfig()
        self.assertAlmostEqual(cfg.weight_consistency, 0.35, places=5)

    def test_weights_sum(self) -> None:
        cfg = ThreatCredibilityConfig()
        total = (
            cfg.weight_consistency + cfg.weight_cost_signal +
            cfg.weight_recency + cfg.weight_pattern
        )
        self.assertAlmostEqual(total, 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
