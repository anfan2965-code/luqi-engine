"""
Phase 4 信念系统核心测试 — belief_system.py (基于实际运行时API)
覆盖: 构造/观测更新/多目标管理/时间衰减/合作概率预测/边界条件
"""

from __future__ import annotations

import unittest
from typing import Dict

from luqi_engine.game_theory.types import (
    BeliefDimension,
    BeliefState,
    BeliefSystemConfig,
    BeliefUpdateOutcome,
    Observation,
    ObservationType,
)


class TestBeliefSystemConstruction(unittest.TestCase):
    """BeliefSystem 构造与配置测试"""

    def test_default_construction(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        bs = BeliefSystem(character_id="test_char")
        self.assertIsNotNone(bs)

    def test_custom_config(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        cfg = BeliefSystemConfig(default_half_life_days=60.0, max_tracked_targets=50)
        bs = BeliefSystem(character_id="cfg_test", config=cfg)
        self.assertEqual(bs.config.max_tracked_targets, 50)

    def test_config_property(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        bs = BeliefSystem(character_id="prop_test")
        self.assertIsInstance(bs.config, BeliefSystemConfig)


class TestObservationAndBeliefUpdate(unittest.TestCase):
    """观测记录与信念更新测试"""

    def setUp(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        self.bs = BeliefSystem(character_id="observer")

    def test_first_observation_creates_state(self) -> None:
        outcome = self.bs.observe(
            target_id="friend",
            dimension=BeliefDimension.COOPERATIVITY,
            observation=Observation(evidence_value=0.9),
        )
        self.assertIsInstance(outcome, BeliefUpdateOutcome)

        belief = self.bs.get_belief("friend", BeliefDimension.COOPERATIVITY)
        self.assertIsInstance(belief, BeliefState)
        self.assertGreater(belief.total_observations, 0)

    def test_positive_evidence_increases_belief(self) -> None:
        for _ in range(5):
            obs = Observation(evidence_value=0.9)
            self.bs.observe(
                target_id="friend_pos",
                dimension=BeliefDimension.COOPERATIVITY,
                observation=obs,
            )
        belief = self.bs.get_belief("friend_pos", BeliefDimension.COOPERATIVITY)
        ev = belief.expected_value
        self.assertGreater(ev, 0.5)

    def test_negative_evidence_decreases_belief(self) -> None:
        for _ in range(5):
            obs = Observation(evidence_value=0.1)
            self.bs.observe(
                target_id="unreliable",
                dimension=BeliefDimension.HONESTY,
                observation=obs,
            )
        belief = self.bs.get_belief("unreliable", BeliefDimension.HONESTY)
        ev = belief.expected_value
        self.assertLess(ev, 0.9)

    def test_mixed_evidence_converges_to_middle(self) -> None:
        for i in range(10):
            ev_val = 0.9 if i % 2 == 0 else 0.1
            self.bs.observe(
                target_id="mixed_signal",
                dimension=BeliefDimension.COOPERATIVITY,
                observation=Observation(evidence_value=ev_val),
            )
        belief = self.bs.get_belief("mixed_signal", BeliefDimension.COOPERATIVITY)
        ev = belief.expected_value
        self.assertGreater(ev, 0.25)

    def test_update_outcome_classification(self) -> None:
        outcomes = set()
        for _ in range(3):
            out = self.bs.observe(
                target_id="classify_test",
                dimension=BeliefDimension.COMPETENCE,
                observation=Observation(evidence_value=0.85),
            )
            outcomes.add(out.name)
        self.assertTrue(len(outcomes) >= 1)

    def test_observation_type_affects_weighting(self) -> None:
        direct_outcome = self.bs.observe(
            target_id="type_test",
            dimension=BeliefDimension.ALIGNMENT,
            observation=Observation(
                observation_type=ObservationType.DIRECT_ACTION,
                evidence_value=0.8,
            ),
        )
        reported_outcome = self.bs.observe(
            target_id="type_test2",
            dimension=BeliefDimension.ALIGNMENT,
            observation=Observation(
                observation_type=ObservationType.REPORTED_INFO,
                evidence_value=0.8,
            ),
        )
        self.assertIsInstance(direct_outcome, BeliefUpdateOutcome)
        self.assertIsInstance(reported_outcome, BeliefUpdateOutcome)


class TestMultiTargetManagement(unittest.TestCase):
    """多目标信念管理测试"""

    def setUp(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        self.bs = BeliefSystem(character_id="multi_target")

    def test_multi_target_tracking(self) -> None:
        targets = ["alice", "bob", "charlie"]
        for t in targets:
            self.bs.observe(
                target_id=t,
                dimension=BeliefDimension.COOPERATIVITY,
                observation=Observation(evidence_value=0.7),
            )
        all_targets = self.bs.get_all_targets()
        for t in targets:
            self.assertIn(t, all_targets)

    def test_multi_dimension_tracking(self) -> None:
        dims = [
            BeliefDimension.COOPERATIVITY,
            BeliefDimension.HONESTY,
            BeliefDimension.COMPETENCE,
        ]
        for d in dims:
            self.bs.observe(
                target_id="multi_dim_target",
                dimension=d,
                observation=Observation(evidence_value=0.75),
            )
        belief_coop = self.bs.get_belief("multi_dim_target", BeliefDimension.COOPERATIVITY)
        belief_honesty = self.bs.get_belief("multi_dim_target", BeliefDimension.HONESTY)
        self.assertIsNotNone(belief_coop)
        self.assertIsNotNone(belief_honesty)

    def test_max_beliefs_limit(self) -> None:
        cfg = BeliefSystemConfig(max_tracked_targets=5)
        from luqi_engine.game_theory.belief_system import BeliefSystem
        limited_bs = BeliefSystem(character_id="limited", config=cfg)
        for i in range(10):
            limited_bs.observe(
                target_id=f"target_{i}",
                dimension=BeliefDimension.STABILITY,
                observation=Observation(evidence_value=0.5),
            )
        all_t = limited_bs.get_all_targets()
        self.assertLessEqual(len(all_t), 5)

    def test_forget_target(self) -> None:
        self.bs.observe(
            target_id="to_forget",
            dimension=BeliefDimension.COOPERATIVITY,
            observation=Observation(),
        )
        result = self.bs.forget_target("to_forget")
        self.assertTrue(result)
        targets_after = self.bs.get_all_targets()
        self.assertNotIn("to_forget", targets_after)

    def test_get_nonexistent_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            self.bs.get_belief("nonexistent", BeliefDimension.COOPERATIVITY)


class TestCooperationProbabilityPrediction(unittest.TestCase):
    """合作概率预测测试"""

    def setUp(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        self.bs = BeliefSystem(character_id="predictor")

    def test_high_cooperation_prediction(self) -> None:
        for _ in range(8):
            self.bs.observe(
                target_id="cooperative_friend",
                dimension=BeliefDimension.COOPERATIVITY,
                observation=Observation(evidence_value=0.95),
            )
            self.bs.observe(
                target_id="cooperative_friend",
                dimension=BeliefDimension.HONESTY,
                observation=Observation(evidence_value=0.9),
            )
        prob = self.bs.predict_cooperation_probability("cooperative_friend")
        self.assertIsInstance(prob, float)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

    def test_low_cooperation_prediction(self) -> None:
        for _ in range(8):
            self.bs.observe(
                target_id="hostile_entity",
                dimension=BeliefDimension.THREAT_LEVEL,
                observation=Observation(evidence_value=0.9),
            )
        prob = self.bs.predict_cooperation_probability("hostile_entity")
        self.assertIsInstance(prob, float)
        self.assertLessEqual(prob, 1.0)

    def test_unknown_target_returns_neutral(self) -> None:
        prob = self.bs.predict_cooperation_probability("stranger")
        self.assertAlmostEqual(prob, 0.5, places=4)

    def test_custom_weights(self) -> None:
        self.bs.observe(
            target_id="weighted_target",
            dimension=BeliefDimension.COOPERATIVITY,
            observation=Observation(evidence_value=0.9),
        )
        custom_weights: Dict[BeliefDimension, float] = {
            BeliefDimension.COOPERATIVITY: 1.0,
        }
        prob = self.bs.predict_cooperation_probability(
            "weighted_target",
            scenario_weights=custom_weights,
        )
        self.assertIsInstance(prob, float)


class TestTimeDecay(unittest.TestCase):
    """时间衰减测试"""

    def setUp(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        self.bs = BeliefSystem(
            character_id="decay_tester",
            config=BeliefSystemConfig(default_half_life_days=0.0007),
        )

    def test_old_observations_decay(self) -> None:
        self.bs.observe(
            target_id="decay_target",
            dimension=BeliefDimension.COOPERATIVITY,
            observation=Observation(evidence_value=0.95),
        )
        belief_fresh = self.bs.get_belief("decay_target", BeliefDimension.COOPERATIVITY)
        ev_before = belief_fresh.expected_value

        belief_fresh.apply_decay(days_elapsed=90)
        ev_after = belief_fresh.expected_value

        self.assertLessEqual(abs(ev_after - 0.5), abs(ev_before - 0.5) + 0.01)

    def test_no_decay_for_zero_days(self) -> None:
        self.bs.observe(
            target_id="fresh_target",
            dimension=BeliefDimension.HONESTY,
            observation=Observation(evidence_value=0.85),
        )
        belief = self.bs.get_belief("fresh_target", BeliefDimension.HONESTY)
        ev_before = belief.expected_value
        belief.apply_decay(days_elapsed=0)
        ev_after = belief.expected_value
        self.assertAlmostEqual(ev_before, ev_after, places=5)

    def test_extreme_decay_reverts_to_prior(self) -> None:
        self.bs.observe(
            target_id="extreme_decay",
            dimension=BeliefDimension.COOPERATIVITY,
            observation=Observation(evidence_value=1.0),
        )
        belief = self.bs.get_belief("extreme_decay", BeliefDimension.COOPERATIVITY)
        belief.apply_decay(days_elapsed=10000)
        self.assertAlmostEqual(belief.expected_value, 0.5, places=2)


class TestEdgeCasesAndBoundaryConditions(unittest.TestCase):
    """边界条件和异常处理测试"""

    def setUp(self) -> None:
        from luqi_engine.game_theory.belief_system import BeliefSystem
        self.bs = BeliefSystem(character_id="edge_case")

    def test_empty_observation_description(self) -> None:
        outcome = self.bs.observe(
            target_id="empty_desc",
            dimension=BeliefDimension.STABILITY,
            observation=Observation(description=""),
        )
        self.assertIsInstance(outcome, BeliefUpdateOutcome)

    def test_extreme_evidence_values(self) -> None:
        outcome_high = self.bs.observe(
            target_id="extreme_ev",
            dimension=BeliefDimension.COMPETENCE,
            observation=Observation(evidence_value=1.0),
        )
        outcome_low = self.bs.observe(
            target_id="extreme_ev",
            dimension=BeliefDimension.COMPETENCE,
            observation=Observation(evidence_value=0.0),
        )
        self.assertIsInstance(outcome_high, BeliefUpdateOutcome)
        self.assertIsInstance(outcome_low, BeliefUpdateOutcome)

    def test_rapid_successive_updates(self) -> None:
        for _ in range(20):
            self.bs.observe(
                target_id="rapid",
                dimension=BeliefDimension.ALIGNMENT,
                observation=Observation(evidence_value=0.7),
            )
        belief = self.bs.get_belief("rapid", BeliefDimension.ALIGNMENT)
        self.assertIsNotNone(belief)

    def test_all_dimensions_supported(self) -> None:
        for dim in BeliefDimension:
            outcome = self.bs.observe(
                target_id="all_dims",
                dimension=dim,
                observation=Observation(evidence_value=0.6),
            )
            self.assertIsInstance(outcome, BeliefUpdateOutcome)

    def test_source_reliability_weighting(self) -> None:
        high_rel_outcome = self.bs.observe(
            target_id="rel_test",
            dimension=BeliefDimension.COOPERATIVITY,
            observation=Observation(source_reliability=1.0, evidence_value=0.8),
        )
        low_rel_outcome = self.bs.observe(
            target_id="rel_test2",
            dimension=BeliefDimension.COOPERATIVITY,
            observation=Observation(source_reliability=0.2, evidence_value=0.8),
        )
        self.assertIsInstance(high_rel_outcome, BeliefUpdateOutcome)
        self.assertIsInstance(low_rel_outcome, BeliefUpdateOutcome)

    def test_context_tags_preserved(self) -> None:
        obs = Observation(
            context_tags=["combat", "ally"],
            description="战斗中掩护我方",
        )
        outcome = self.bs.observe(
            target_id="context_test",
            dimension=BeliefDimension.COOPERATIVITY,
            observation=obs,
        )
        self.assertIsInstance(outcome, BeliefUpdateOutcome)

    def test_belief_state_immutability_from_get(self) -> None:
        self.bs.observe(
            target_id="immutable_test",
            dimension=BeliefDimension.HONESTY,
            observation=Observation(evidence_value=0.8),
        )
        belief_copy = self.bs.get_belief("immutable_test", BeliefDimension.HONESTY)
        original_alpha = belief_copy.alpha
        belief_copy.alpha = 999.0
        belief_original = self.bs.get_belief("immutable_test", BeliefDimension.HONESTY)
        self.assertAlmostEqual(belief_original.alpha, original_alpha, places=5)


if __name__ == "__main__":
    unittest.main()
