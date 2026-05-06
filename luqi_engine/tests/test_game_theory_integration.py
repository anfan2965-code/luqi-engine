"""
Phase 4 集成测试 — DeepCharacter v2 + 博弈论子系统
覆盖: 惰性初始化/事件分发/状态快照/一致性规则/渲染集成
"""

from __future__ import annotations

import unittest

from luqi_engine.character.deep_character import (
    DeepCharacter,
    DeepCharacterState,
    ConsistencyIssue,
    ConsistencySeverity,
)
from luqi_engine.game_theory.types import (
    BeliefDimension,
    StrategyAction,
)


class TestDeepCharacterP4LazyInit(unittest.TestCase):
    """P4 子系统惰性初始化测试"""

    def test_belief_system_lazy_init(self) -> None:
        dc = DeepCharacter(character_id="test_char")
        
        self.assertIsNone(dc._belief_system)
        
        bs = dc.belief_system
        
        self.assertIsNotNone(bs)
        self.assertIsNotNone(dc._belief_system)

    def test_threat_engine_lazy_init(self) -> None:
        dc = DeepCharacter(character_id="test_char")
        
        self.assertIsNone(dc._threat_engine)
        
        te = dc.threat_engine
        
        self.assertIsNotNone(te)
        self.assertIsNotNone(dc._threat_engine)

    def test_strategy_engine_lazy_init(self) -> None:
        dc = DeepCharacter(character_id="test_char")
        
        self.assertIsNone(dc._strategy_engine)
        
        se = dc.strategy_engine
        
        self.assertIsNotNone(se)
        self.assertIsNotNone(dc._strategy_engine)

    def test_cached_after_first_access(self) -> None:
        """首次访问后缓存, 不重复创建"""
        dc = DeepCharacter(character_id="cached")
        
        bs1 = dc.belief_system
        bs2 = dc.belief_system
        
        self.assertIs(bs1, bs2)


class TestDeepCharacterEventDispatch(unittest.TestCase):
    """事件分发到博弈论子系统测试"""

    def test_dialogue_event_updates_beliefs(self) -> None:
        """对话事件 → 信念系统更新"""
        dc = DeepCharacter(character_id="observer")
        
        affected = dc.on_event(
            event_type="dialogue_input",
            intensity=0.7,
            metadata={
                "content": "我会帮助你的，请相信我",
                "speaker_id": "helper_entity",
                "action_type": "DIALOGUE",
            },
        )
        
        self.assertIn("belief_system", affected)

    def test_social_action_updates_threats(self) -> None:
        """社交动作事件 → 威胁引擎记录"""
        dc = DeepCharacter(character_id="observer")
        
        affected = dc.on_event(
            event_type="social_action",
            intensity=0.8,
            metadata={
                "target_id": "rival_entity",
                "action_type": "THREATEN",
                "value": -0.7,
            },
        )
        
        self.assertIn("threat_engine", affected)
        self.assertIn("belief_system", affected)

    def test_normal_dialogue_no_p4_dispatch(self) -> None:
        """无speaker_id的对话不触发P4分发"""
        dc = DeepCharacter(character_id="obs")
        
        affected = dc.on_event(
            event_type="dialogue_input",
            intensity=0.5,
            metadata={
                "content": "今天天气不错",
            },
        )
        
        self.assertNotIn("belief_system", affected)


class TestDeepCharacterStateSnapshotP4(unittest.TestCase):
    """状态快照包含 P4 字段测试"""

    def test_state_includes_primary_target_beliefs(self) -> None:
        dc = DeepCharacter(character_id="obs")
        
        dc.on_event(
            event_type="dialogue_input",
            intensity=0.6,
            metadata={
                "content": "我支持你",
                "speaker_id": "ally_01",
            },
        )
        
        state = dc.get_state_snapshot(
            target_entity_id="ally_01",
            force_refresh=True,
        )
        
        self.assertIsInstance(state.primary_target_beliefs, dict)

    def test_state_includes_active_threats(self) -> None:
        dc = DeepCharacter(character_id="obs")
        
        dc.on_event(
            event_type="social_action",
            intensity=0.9,
            metadata={
                "target_id": "enemy_01",
                "action_type": "THREATEN",
            },
        )
        
        state = dc.get_state_snapshot(
            target_entity_id="enemy_01",
            force_refresh=True,
        )
        
        self.assertIsInstance(state.active_threats, list)

    def test_state_includes_current_strategy(self) -> None:
        dc = DeepCharacter(character_id="obs")
        
        dc.on_event(
            event_type="dialogue_input",
            intensity=0.5,
            metadata={
                "content": "你好",
                "speaker_id": "target_01",
            },
        )
        
        state = dc.get_state_snapshot(
            target_entity_id="target_01",
            force_refresh=True,
        )
        
        if state.current_strategy is not None:
            self.assertIn("dominant_action", state.current_strategy)

    def test_state_clamping(self) -> None:
        """P4 字段值被正确限制在 [0, 1]"""
        dc = DeepCharacter(character_id="obs")
        
        state = dc.get_state_snapshot(force_refresh=True)
        
        self.assertGreaterEqual(state.belief_action_alignment, 0.0)
        self.assertLessEqual(state.belief_action_alignment, 1.0)
        self.assertGreaterEqual(state.threat_response_readiness, 0.0)
        self.assertLessEqual(state.threat_response_readiness, 1.0)


class TestDeepCharacterConsistencyRulesP4(unittest.TestCase):
    """P4 一致性规则测试"""

    def test_belief_strategy_mismatch_rule(self) -> None:
        """规则1: BELIEF_STRATEGY_MISMATCH 检测"""
        from luqi_engine.game_theory.belief_system import BeliefSystem
        from luqi_engine.game_theory.types import Observation
        
        dc = DeepCharacter(character_id="mismatch_test")
        
        for _ in range(10):
            dc.belief_system.observe(
                target_id="cooperative_target",
                dimension=BeliefDimension.COOPERATIVITY,
                observation=Observation(evidence_value=0.95),
            )
        
        state = dc.get_state_snapshot(
            target_entity_id="cooperative_target",
            force_refresh=True,
        )
        
        if state.current_strategy:
            state.current_strategy["dominant_action"] = "DEFECT"
            state.current_strategy["cooperate_probability"] = 0.15
        
        issues = dc._check_belief_strategy_mismatch(state)
        
        if state.primary_target_beliefs and state.current_strategy:
            belief_val = max(state.primary_target_beliefs.values())
            if belief_val > 0.6:
                coop_prob = state.current_strategy.get("cooperate_probability", 0.5)
                if coop_prob < 0.3:
                    self.assertIsNotNone(issues)
                    if issues:
                        self.assertEqual(issues.severity, ConsistencySeverity.WARNING)

    def test_threat_ignore_rule(self) -> None:
        """规则2: THREAT_IGNORE_HIGH_CREDIBILITY 检测"""
        dc = DeepCharacter(character_id="ignore_test")
        
        state = dc.get_state_snapshot(force_refresh=True)
        state.threat_response_readiness = 0.15
        state.active_threats.append({
            "target": "dangerous_entity",
            "credibility_score": 0.85,
        })
        state.current_strategy = {"dominant_action": "OBSERVE"}
        
        issue = dc._check_threat_ignore_high_credibility(state)
        self.assertIsNotNone(issue)
        if issue:
            self.assertEqual(issue.severity, ConsistencySeverity.ERROR)

    def test_low_entropy_high_uncertainty_rule(self) -> None:
        """规则3: LOW_ENTROPY_HIGH_UNCERTAINTY 检测"""
        dc = DeepCharacter(character_id="entropy_test")
        
        state = dc.get_state_snapshot(force_refresh=True)
        state.primary_target_beliefs = {"uncertain_target": 0.52}
        state.current_strategy = {
            "dominant_action": "COOPERATE",
            "entropy": 0.3,
        }
        
        issue = dc._check_low_entropy_high_uncertainty(state)
        self.assertIsNotNone(issue)
        if issue:
            self.assertEqual(issue.severity, ConsistencySeverity.INFO)

    def test_incentive_incompatible_rule(self) -> None:
        """规则4: INCENTIVE_INCOMPATIBLE_BEHAVIOR 检测"""
        dc = DeepCharacter(character_id="ic_test")
        
        state = dc.get_state_snapshot(force_refresh=True)
        state.trust_level_current = 0.85
        state.current_strategy = {
            "dominant_action": "DEFECT",
            "cooperate_probability": 0.12,
        }
        
        issue = dc._check_incentive_incompatible_behavior(state)
        self.assertIsNotNone(issue)
        if issue:
            self.assertEqual(issue.severity, ConsistencySeverity.WARNING)

    def test_rules_return_none_when_ok(self) -> None:
        """正常状态 → 规则返回 None"""
        dc = DeepCharacter(character_id="ok_test")
        
        state = dc.get_state_snapshot(force_refresh=True)
        
        self.assertIsNone(dc._check_belief_strategy_mismatch(state))
        self.assertIsNone(dc._check_threat_ignore_high_credibility(state))
        self.assertIsNone(dc._check_low_entropy_high_uncertainty(state))
        self.assertIsNone(dc._check_incentive_incompatible_behavior(state))


class TestDeepCharacterHealthStatusP4(unittest.TestCase):
    """健康状态包含 P4 子系统测试"""

    def test_health_includes_p4_subsystems(self) -> None:
        dc = DeepCharacter(character_id="health_test")
        
        status = dc.get_health_status()
        
        self.assertIn("belief_system", status)
        self.assertIn("threat_engine", status)
        self.assertIn("strategy_engine", status)

    def test_p4_uninitialized_status(self) -> None:
        """未初始化时显示未初始化"""
        dc = DeepCharacter(character_id="uninit_test")
        
        status = dc.get_health_status()
        
        for name in ["belief_system", "threat_engine", "strategy_engine"]:
            if not getattr(dc, f"_{name}", None):
                self.assertFalse(status[name].is_healthy)


class TestStateRendererV3Integration(unittest.TestCase):
    """StateRenderer v3 + P4 状态渲染测试"""

    def test_renderer_v3_weights_include_p4(self) -> None:
        from luqi_engine.llm.state_renderer import StateRenderer
        
        renderer = StateRenderer()
        
        weights = StateRenderer.DEEP_SECTION_WEIGHTS
        self.assertIn("belief_state", weights)
        self.assertIn("threat_assessment", weights)
        self.assertIn("strategy_hint", weights)

    def test_render_deep_state_with_p4_fields(self) -> None:
        from luqi_engine.llm.state_renderer import StateRenderer
        
        renderer = StateRenderer()
        
        state = DeepCharacterState(
            primary_target_beliefs={"t1": 0.75},
            active_threats=[{"target": "e1"}],
            current_strategy={"dominant_action": "COOPERATE"},
            threat_response_readiness=0.65,
        )
        
        result = renderer.render_deep_state(state, max_tokens=2000)
        
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 10)

    def test_token_budget_v3_profile(self) -> None:
        from luqi_engine.llm.state_renderer import TokenBudgetProfile
        
        profile = TokenBudgetProfile()
        
        self.assertIn("belief_state", profile.section_weights)
        self.assertIn("threat_assessment", profile.section_weights)
        self.assertIn("strategy_hint", profile.section_weights)


class TestSerializationWithP4Fields(unittest.TestCase):
    """序列化/反序列化包含 P4 字段测试"""

    def test_to_dict_includes_p4_fields(self) -> None:
        state = DeepCharacterState(
            primary_target_beliefs={"target_a": 0.8, "target_b": 0.35},
            active_threats=[{"target": "x", "credibility_score": 0.72}],
            current_strategy={
                "dominant_action": "COOPERATE",
                "cooperate_probability": 0.68,
                "entropy": 0.85,
                "temperature": 1.2,
            },
            belief_action_alignment=0.78,
            threat_response_readiness=0.82,
        )
        
        d = state.to_dict()
        
        self.assertIn("primary_target_beliefs", d)
        self.assertIn("active_threats", d)
        self.assertIn("current_strategy", d)
        self.assertIn("belief_action_alignment", d)
        self.assertIn("threat_response_readiness", d)

    def test_dict_values_correct(self) -> None:
        state = DeepCharacterState(
            primary_target_beliefs={"t1": 0.91},
            belief_action_alignment=0.55,
            threat_response_readiness=0.77,
        )
        
        d = state.to_dict()
        
        self.assertAlmostEqual(d["belief_action_alignment"], 0.55, places=5)
        self.assertAlmostEqual(d["threat_response_readiness"], 0.77, places=5)


if __name__ == "__main__":
    unittest.main()
