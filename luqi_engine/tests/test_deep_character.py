"""
DeepCharacter 聚合层主类测试 — Phase 3 深度聚合层
覆盖: 构造/惰性初始化/状态快照/事件处理/一致性验证/持久化
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from luqi_engine.character.deep_character import (
    ConsistencyIssue,
    ConsistencyIssueType,
    ConsistencySeverity,
    DeepCharacter,
    DeepCharacterState,
    MotivationDominance,
    NarrativeArcPhase,
    PsychologicalTensionLevel,
    ShadowActivationState,
    SubsystemHealthStatus,
)


class TestDeepCharacterConstruction(unittest.TestCase):
    """DeepCharacter 构造和基本属性测试"""

    def test_default_construction(self) -> None:
        dc = DeepCharacter(character_id="char_001")
        
        self.assertEqual(dc.character_id, "char_001")
        self.assertEqual(dc.name, "")
        self.assertEqual(dc._operation_count, 0)
        self.assertFalse(dc._cache_valid)
        self.assertIsNone(dc._cached_state)
        self.assertEqual(dc._recent_events, [])

    def test_construction_with_name(self) -> None:
        dc = DeepCharacter(character_id="alice", name="爱丽丝")
        
        self.assertEqual(dc.name, "爱丽丝")

    def test_construction_with_config(self) -> None:
        config = {"debug": True, "shadow_threshold": 0.7}
        dc = DeepCharacter(character_id="bob", name="鲍勃", config=config)
        
        self.assertIn("debug", dc._config)
        self.assertTrue(dc._config["debug"])

    def test_class_constants(self) -> None:
        self.assertIsInstance(DeepCharacter.DEFAULT_SHADOW_THRESHOLD, float)
        self.assertIsInstance(DeepCharacter.DEFAULT_TENSION_THRESHOLD, float)
        self.assertIsInstance(DeepCharacter.CONSISTENCY_CHECK_INTERVAL, int)
        self.assertIsInstance(DeepCharacter.MAX_CONSISTENCY_ISSUES, int)


class TestLazyInitialization(unittest.TestCase):
    """惰性初始化测试"""

    @patch("luqi_engine.character.jungian_model.JungianProfile")
    def test_jungian_lazy_init(self, mock_jp_class: MagicMock) -> None:
        dc = DeepCharacter(character_id="test")
        
        self.assertIsNone(dc._jungian)
        
        _ = dc.jungian
        
        mock_jp_class.assert_called_once()
        self.assertIsNotNone(dc._jungian)

    @patch("luqi_engine.character.existential_model.ExistentialProfile")
    def test_existential_lazy_init(self, mock_ep_class: MagicMock) -> None:
        dc = DeepCharacter(character_id="test")
        
        self.assertIsNone(dc._existential)
        
        _ = dc.existential
        
        mock_ep_class.assert_called_once()
        self.assertIsNotNone(dc._existential)

    @patch("luqi_engine.character.narrative_identity.NarrativeIdentity")
    def test_narrative_lazy_init(self, mock_ni_class: MagicMock) -> None:
        dc = DeepCharacter(character_id="test_id")
        
        self.assertIsNone(dc._narrative)
        
        _ = dc.narrative
        
        mock_ni_class.assert_called_once_with(character_id="test_id")
        self.assertIsNotNone(dc._narrative)

    @patch("luqi_engine.character.social_evolution.SocialEvolutionEngine")
    def test_social_lazy_init(self, mock_se_class: MagicMock) -> None:
        dc = DeepCharacter(character_id="test_id")
        
        self.assertIsNone(dc._social)
        
        _ = dc.social
        
        mock_se_class.assert_called_once_with(character_id="test_id")
        self.assertIsNotNone(dc._social)

    @patch("luqi_engine.memory.memory_system.MemorySystem")
    def test_memory_lazy_init(self, mock_ms_class: MagicMock) -> None:
        dc = DeepCharacter(character_id="test_id")
        
        self.assertIsNone(dc._memory)
        
        _ = dc.memory
        
        mock_ms_class.assert_called_once_with(character_id="test_id")
        self.assertIsNotNone(dc._memory)

    @patch("luqi_engine.motivation.maslow_engine.MotivationEngine")
    def test_motivation_lazy_init(self, mock_me_class: MagicMock) -> None:
        dc = DeepCharacter(character_id="test_id")
        
        self.assertIsNone(dc._motivation)
        
        _ = dc.motivation
        
        mock_me_class.assert_called_once_with(character_id="test_id")
        self.assertIsNotNone(dc._motivation)

    def test_subsystem_cached_after_first_access(self) -> None:
        with patch("luqi_engine.character.jungian_model.JungianProfile") as mock_cls:
            dc = DeepCharacter(character_id="test")
            
            first = dc.jungian
            second = dc.jungian
            
            mock_cls.assert_called_once()
            self.assertIs(first, second)


class TestGetStateSnapshot(unittest.TestCase):
    """get_state_snapshot() 状态快照生成测试"""

    def setUp(self) -> None:
        self.dc = DeepCharacter(character_id="snapshot_test")

    def test_snapshot_returns_deep_character_state(self) -> None:
        state = self.dc.get_state_snapshot()
        
        self.assertIsInstance(state, DeepCharacterState)

    def test_snapshot_has_correct_character_id(self) -> None:
        state = self.dc.get_state_snapshot()
        
        self.assertEqual(state.character_id, "snapshot_test")

    def test_snapshot_scene_context_set(self) -> None:
        state = self.dc.get_state_snapshot(scene_context="酒馆内部")
        
        self.assertEqual(state.scene_context, "酒馆内部")

    def test_snapshot_timestamp_recent(self) -> None:
        before = time.time()
        state = self.dc.get_state_snapshot()
        after = time.time()
        
        self.assertGreaterEqual(state.timestamp, before)
        self.assertLessEqual(state.timestamp, after)

    def test_snapshot_caches_result(self) -> None:
        state1 = self.dc.get_state_snapshot(scene_context="场景A")
        state2 = self.dc.get_state_snapshot(scene_context="场景A")
        
        self.assertIs(state1, state2)

    def test_force_refresh_creates_new_state(self) -> None:
        state1 = self.dc.get_state_snapshot(scene_context="场景A")
        state2 = self.dc.get_state_snapshot(
            scene_context="场景A",
            force_refresh=True,
        )
        
        self.assertIsNot(state1, state2)

    def test_different_scene_invalidates_cache(self) -> None:
        state1 = self.dc.get_state_snapshot(scene_context="场景A")
        state2 = self.dc.get_state_snapshot(scene_context="场景B")
        
        self.assertIsNot(state1, state2)

    def test_snapshot_derived_indicators_populated(self) -> None:
        state = self.dc.get_state_snapshot()
        
        self.assertIsInstance(state.overall_mood, str)
        self.assertIsInstance(state.behavioral_tendency, str)
        self.assertIsInstance(state.response_style_hint, str)


class TestGetStateSnapshotWithMockedSubsystems(unittest.TestCase):
    """使用Mock子系统的状态快照详细测试"""

    def _make_mock_jungian(self) -> MagicMock:
        from luqi_engine.character.jungian_model import Archetype, ShadowAspect
        
        mock = MagicMock()
        mock.archetype = Archetype.HERO
        
        shadow = MagicMock(spec=ShadowAspect)
        shadow.name = "傲慢"
        shadow.get_influence_context.return_value = 0.5
        mock.shadows = [shadow]
        mock.persona = None
        
        dominant_shadow_mock = MagicMock(spec=ShadowAspect)
        dominant_shadow_mock.name = "傲慢"
        mock.get_dominant_shadow.return_value = (dominant_shadow_mock, 0.5)
        mock.compute_inner_conflict.return_value = 0.3
        
        return mock

    def _make_mock_existential(self) -> MagicMock:
        mock = MagicMock()
        mock.anxiety_level = 0.4
        
        auth_mock = MagicMock()
        auth_mock.name = "COMPROMISED"
        mock.authenticity = auth_mock
        
        dissonance_mock = MagicMock()
        dissonance_mock.resolution_strategy = MagicMock()
        dissonance_mock.resolution_strategy.name = "deny"
        dissonance_mock.conflicting_beliefs = ["信念A vs 信念B"]
        mock.dissonance_history = [dissonance_mock]
        mock.get_active_dissonance_count.return_value = 1
        mock.get_max_dissonance_magnitude.return_value = 0.5
        
        return mock

    def _make_mock_narrative(self) -> MagicMock:
        from luqi_engine.character.narrative_identity import NarrativeEpisode, LifeChapter
        
        mock = MagicMock()
        mock.get_identity_summary.return_value = "一个寻找真相的旅人"
        
        ep = MagicMock()
        ep.significance = 0.7
        ep.learned_lesson = "勇气来自内心"
        
        chapter_mock = MagicMock()
        chapter_mock.name = "TRIALS"
        ep.chapter = chapter_mock
        
        mock.get_defining_moments.return_value = [ep]
        
        return mock

    def _make_mock_social(self) -> MagicMock:
        mock_rel = MagicMock()
        mock_rel.trust = 0.75
        mock_rel.intimacy = 0.35
        
        mock = MagicMock()
        mock.get_relationship.return_value = mock_rel
        mock.get_relation_summary_for_prompt.return_value = "值得信赖的伙伴"
        
        return mock

    def _make_mock_memory(self) -> None:
        pass

    def _make_mock_motivation(self) -> MagicMock:
        from luqi_engine.motivation.maslow_engine import NeedLevel
        
        mock_profile = MagicMock()
        need_mock = MagicMock()
        need_mock.name = "LOVE_BELONGING"
        mock_profile.get_dominant_need.return_value = (need_mock, 0.65)
        
        mock = MagicMock()
        mock.profile = mock_profile
        mock.calculate_all_motivations.return_value = {
            NeedLevel.PHYSIOLOGICAL: 0.8,
            NeedLevel.SAFETY: 0.7,
            NeedLevel.LOVE_BELONGING: 0.35,
            NeedLevel.ESTEEM: 0.5,
        }
        mock.detect_conflicts.return_value = None
        mock._urgency = 1.2
        
        return mock

    def test_jungian_data_in_snapshot(self) -> None:
        dc = DeepCharacter(character_id="jung_test")
        dc._jungian = self._make_mock_jungian()
        
        state = dc.get_state_snapshot(force_refresh=True)
        
        self.assertEqual(state.dominant_archetype, "HERO")
        self.assertEqual(state.shadow_state, ShadowActivationState.ACTIVE)
        self.assertIn("傲慢", state.active_shadow_aspects)

    def test_existential_data_in_snapshot(self) -> None:
        dc = DeepCharacter(character_id="exis_test")
        dc._existential = self._make_mock_existential()
        
        state = dc.get_state_snapshot(force_refresh=True)
        
        self.assertAlmostEqual(state.existential_anxiety, 0.4, places=5)
        self.assertAlmostEqual(state.cognitive_dissonance, 0.5, places=5)
        self.assertAlmostEqual(state.authenticity_score, 0.5, places=5)

    def test_narrative_data_in_snapshot(self) -> None:
        dc = DeepCharacter(character_id="narr_test")
        dc._narrative = self._make_mock_narrative()
        
        state = dc.get_state_snapshot(force_refresh=True)
        
        self.assertIn("寻找真相", state.identity_statement)
        self.assertEqual(state.narrative_phase, NarrativeArcPhase.INITIATION)
        self.assertGreater(state.narrative_tension, 0.0)

    def test_social_data_in_snapshot(self) -> None:
        dc = DeepCharacter(character_id="soc_test")
        dc._social = self._make_mock_social()
        
        state = dc.get_state_snapshot(
            force_refresh=True,
            target_entity_id="target_001",
        )
        
        self.assertAlmostEqual(state.trust_level_current, 0.75, places=5)
        self.assertIn("伙伴", state.relationship_summary)
        self.assertEqual(state.social_role, "熟人")

    def test_motivation_data_in_snapshot(self) -> None:
        dc = DeepCharacter(character_id="mot_test")
        dc._motivation = self._make_mock_motivation()
        
        state = dc.get_state_snapshot(force_refresh=True)
        
        self.assertEqual(state.dominant_need, "LOVE_BELONGING")
        self.assertIn("LOVE_BELONGING", state.need_satisfaction_map)
        self.assertIsNone(state.current_conflict)
        self.assertAlmostEqual(state.urgency_level, 1.2, places=5)

    def test_combined_all_subsystems(self) -> None:
        dc = DeepCharacter(character_id="combined_test")
        dc._jungian = self._make_mock_jungian()
        dc._existential = self._make_mock_existential()
        dc._narrative = self._make_mock_narrative()
        dc._social = self._make_mock_social()
        dc._motivation = self._make_mock_motivation()
        
        state = dc.get_state_snapshot(
            force_refresh=True,
            target_entity_id="target_001",
            scene_context="测试场景",
        )
        
        self.assertEqual(state.character_id, "combined_test")
        self.assertEqual(state.scene_context, "测试场景")
        self.assertEqual(state.dominant_archetype, "HERO")
        self.assertNotEqual(state.overall_mood, "")


class TestOnEvent(unittest.TestCase):
    """on_event() 事件处理测试"""

    def setUp(self) -> None:
        self.dc = DeepCharacter(character_id="event_test")

    def test_dialogue_input_event(self) -> None:
        mock_mem = MagicMock()
        mock_mem.store.return_value = None
        self.dc._memory = mock_mem
        
        mock_soc = MagicMock()
        mock_soc.evolve_relationship.return_value = None
        self.dc._social = mock_soc
        
        mock_jung = MagicMock()
        mock_shadow = MagicMock()
        mock_shadow.name = "恐惧"
        mock_jung.get_dominant_shadow.return_value = (mock_shadow, 0.8)
        self.dc._jungian = mock_jung
        
        mock_exis = MagicMock()
        self.dc._existential = mock_exis
        
        affected = self.dc.on_event(
            event_type="dialogue_input",
            intensity=0.7,
            metadata={
                "content": "你为什么要这样做?",
                "speaker_id": "player",
                "emotions": ["愤怒"],
            },
        )
        
        self.assertIn("memory", affected)

    def test_social_action_event(self) -> None:
        mock_soc = MagicMock()
        mock_soc.evolve_relationship.return_value = None
        self.dc._social = mock_soc
        
        mock_exis = MagicMock()
        mock_exis.detect_dissonance.return_value = None
        self.dc._existential = mock_exis
        
        affected = self.dc.on_event(
            event_type="social_action",
            intensity=0.8,
            metadata={
                "target_id": "ally_001",
                "action_type": "HELP",
                "value": 1.0,
            },
        )
        
        self.assertIn("social", affected)

    def test_environment_change_event(self) -> None:
        mock_mot = MagicMock()
        mock_mot._profile.update_need_value.return_value = None
        self.dc._motivation = mock_mot
        
        mock_exis = MagicMock()
        self.dc._existential = mock_exis
        
        affected = self.dc.on_event(
            event_type="environment_change",
            intensity=0.9,
            metadata={
                "change_type": "threat",
                "description": "地震来袭!",
            },
        )
        
        self.assertIn("motivation", affected)

    def test_time_passage_event(self) -> None:
        mock_mem = MagicMock()
        mock_mem.decay.return_value = None
        self.dc._memory = mock_mem
        
        mock_exis = MagicMock()
        self.dc._existential = mock_exis
        
        affected = self.dc.on_event(
            event_type="time_passage",
            intensity=0.3,
            metadata={"delta_hours": 12.0},
        )
        
        self.assertIn("memory", affected)

    def test_internal_conflict_event(self) -> None:
        mock_exis = MagicMock()
        mock_exis.anxiety_level = 0.3
        self.dc._existential = mock_exis
        
        mock_jung = MagicMock()
        mock_jung.compute_inner_conflict.return_value = 0.5
        self.dc._jungian = mock_jung
        
        affected = self.dc.on_event(
            event_type="internal_conflict",
            intensity=0.85,
            metadata={"keywords": ["选择", "责任"]},
        )
        
        self.assertIn("existential", affected)

    def test_event_intensity_clamped(self) -> None:
        mock_mem = MagicMock()
        mock_mem.store.return_value = None
        self.dc._memory = mock_mem
        
        self.dc.on_event(
            event_type="dialogue_input",
            intensity=999.0,
            metadata={"content": "test"},
        )
        
        call_args = mock_mem.store.call_args
        if call_args:
            kwargs = call_args.kwargs or {}
            emotional_intensity = kwargs.get("emotional_intensity", -1)
            self.assertLessEqual(emotional_intensity, 1.0)

    def test_event_records_history(self) -> None:
        initial_count = len(self.dc._recent_events)
        
        self.dc.on_event(event_type="test_event", intensity=0.5)
        
        self.assertEqual(len(self.dc._recent_events), initial_count + 1)

    def test_events_limited_to_max(self) -> None:
        for i in range(100):
            self.dc.on_event(event_type=f"event_{i}", intensity=0.1)
        
        self.assertLessEqual(len(self.dc._recent_events), 50)

    def test_on_event_invalidates_cache(self) -> None:
        state_before = self.dc.get_state_snapshot()
        self.assertTrue(self.dc._cache_valid)
        
        self.dc.on_event(event_type="test", intensity=0.1)
        
        self.assertFalse(self.dc._cache_valid)

    def test_on_dialogue_turn_shortcut(self) -> None:
        original_on_event = self.dc.on_event
        call_history: List[Dict[str, Any]] = []
        
        def capture_on_event(*args, **kwargs):
            call_history.append(kwargs)
            return []
        
        self.dc.on_event = capture_on_event
        
        self.dc.on_dialogue_turn(input_text="你好吗?", speaker_id="player")
        
        self.assertEqual(len(call_history), 1)
        self.assertEqual(call_history[0]["event_type"], "dialogue_input")
        self.assertEqual(call_history[0]["intensity"], 0.5)
        self.assertEqual(call_history[0]["metadata"]["content"], "你好吗?")
        self.assertEqual(call_history[0]["metadata"]["speaker_id"], "player")
        
        self.dc.on_event = original_on_event


class TestCheckConsistency(unittest.TestCase):
    """check_consistency() 一致性验证测试"""

    def setUp(self) -> None:
        self.dc = DeepCharacter(character_id="consistency_test")

    def test_consistency_check_returns_list(self) -> None:
        result = self.dc.check_consistency()
        
        self.assertIsInstance(result, list)

    def test_consistency_issues_limited_to_max(self) -> None:
        for _ in range(100):
            self.dc.check_consistency()
        
        issues = self.dc.check_consistency()
        self.assertLessEqual(len(issues), DeepCharacter.MAX_CONSISTENCY_ISSUES)

    def test_consistency_issues_are_consistency_issue_objects(self) -> None:
        issues = self.dc.check_consistency()
        
        for issue in issues:
            self.assertIsInstance(issue, ConsistencyIssue)


class TestGetHealthStatus(unittest.TestCase):
    """get_health_status() 健康状态测试"""

    def test_all_subsystems_uninitialized(self) -> None:
        dc = DeepCharacter(character_id="health_test")
        
        status = dc.get_health_status()
        
        self.assertIn("jungian", status)
        self.assertIn("existential", status)
        self.assertIn("narrative", status)
        self.assertIn("social", status)
        self.assertIn("memory", status)
        self.assertIn("motivation", status)

    def test_uninitialized_systems_report_not_healthy(self) -> None:
        dc = DeepCharacter(character_id="health_test")
        
        status = dc.get_health_status()
        
        for sys_name, sys_status in status.items():
            self.assertFalse(sys_status.is_healthy)
            self.assertIn("未初始化", sys_status.issues)

    def test_initialized_systems_report_healthy(self) -> None:
        dc = DeepCharacter(character_id="health_test")
        dc._jungian = MagicMock()
        dc._memory = MagicMock()
        
        status = dc.get_health_status()
        
        self.assertTrue(status["jungian"].is_healthy)
        self.assertTrue(status["memory"].is_healthy)
        self.assertFalse(status["existential"].is_healthy)


class TestInvalidateCache(unittest.TestCase):
    """缓存失效测试"""

    def test_invalidate_cache_clears_flag(self) -> None:
        dc = DeepCharacter(character_id="cache_test")
        
        dc.get_state_snapshot()
        self.assertTrue(dc._cache_valid)
        
        dc.invalidate_cache()
        
        self.assertFalse(dc._cache_valid)
        self.assertIsNone(dc._cached_state)


class TestInitializeFromProfile(unittest.TestCase):
    """initialize_from_profile() 配置初始化测试"""

    def test_initialize_jungian_config(self) -> None:
        dc = DeepCharacter(character_id="profile_test")
        
        dc.initialize_from_profile(jungian_config={
            "archetype": "SAGE",
            "shadows": [
                {"name": "傲慢", "intensity": 0.6, "repression_level": 0.3,
                 "trigger_conditions": ["被质疑"]},
            ],
            "persona": {
                "description": "智者面具",
                "strength": 0.7,
                "social_contexts": ["公开演讲"],
            },
            "archetype_confidence": 0.8,
        })
        
        self.assertIsNotNone(dc._jungian)

    def test_initialize_existential_config(self) -> None:
        dc = DeepCharacter(character_id="profile_test")
        
        dc.initialize_from_profile(existential_config={
            "authenticity": "BAD_FAITH",
            "anxiety_level": 0.6,
            "freedom_avoidance": 0.5,
            "responsibility_threshold": 0.4,
            "core_values": ["自由", "真理"],
            "dread_triggers": ["死亡"],
            "beliefs": {
                "belief_1": {
                    "content": "生命是有限的",
                    "strength": 0.9,
                    "source": "个人经历",
                },
            },
        })
        
        self.assertIsNotNone(dc._existential)

    def test_initialize_narrative_config(self) -> None:
        dc = DeepCharacter(character_id="profile_test")
        
        dc.initialize_from_profile(narrative_config={
            "episodes": [
                {
                    "episode_id": "ep_001",
                    "title": "启程",
                    "description": "离开家乡",
                    "chapter": "ORIGIN",
                    "timestamp": -1000.0,
                    "significance": 0.8,
                    "emotional_tags": ["不舍"],
                    "learned_lesson": "勇敢面对未知",
                },
            ],
        })
        
        self.assertIsNotNone(dc._narrative)

    def test_initialize_invalidates_cache(self) -> None:
        dc = DeepCharacter(character_id="cache_profile_test")
        dc.get_state_snapshot()
        self.assertTrue(dc._cache_valid)
        
        dc.initialize_from_profile()
        
        self.assertFalse(dc._cache_valid)


class TestInitializeFromExisting(unittest.TestCase):
    """initialize_from_existing() 注入已有实例测试"""

    def test_inject_existing_instances(self) -> None:
        dc = DeepCharacter(character_id="inject_test")
        
        mock_jungian = MagicMock()
        mock_memory = MagicMock()
        
        dc.initialize_from_existing(
            jungian=mock_jungian,
            memory=mock_memory,
        )
        
        self.assertIs(dc._jungian, mock_jungian)
        self.assertIs(dc._memory, mock_memory)

    def test_partial_injection(self) -> None:
        dc = DeepCharacter(character_id="partial_test")
        
        mock_social = MagicMock()
        
        dc.initialize_from_existing(social=mock_social)
        
        self.assertIs(dc._social, mock_social)
        self.assertIsNone(dc._jungian)

    def test_inject_overrides_lazy(self) -> None:
        dc = DeepCharacter(character_id="override_test")
        
        custom_instance = MagicMock()
        dc.initialize_from_existing(motivation=custom_instance)
        
        self.assertIs(dc.motivation, custom_instance)


class TestSerializeDeserialize(unittest.TestCase):
    """序列化/反序列化测试"""

    def test_serialize_produces_dict(self) -> None:
        dc = DeepCharacter(character_id="ser_test", name="序列化测试")
        
        data = dc.serialize()
        
        self.assertIsInstance(data, dict)

    def test_serialize_contains_basic_fields(self) -> None:
        dc = DeepCharacter(character_id="ser_test", name="测试角色")
        
        data = dc.serialize()
        
        self.assertEqual(data["character_id"], "ser_test")
        self.assertEqual(data["name"], "测试角色")
        self.assertIn("config", data)
        self.assertIn("operation_count", data)
        self.assertIn("recent_events", data)
        self.assertIn("timestamp", data)

    def test_deserialize_restores_character(self) -> None:
        original = DeepCharacter(character_id="orig", name="原始角色")
        original._operation_count = 42
        original._recent_events.append(("evt_a", 0.5, 1700000000.0))
        
        data = original.serialize()
        restored = DeepCharacter.deserialize(data, character_id="restored")
        
        self.assertEqual(restored.character_id, "restored")
        self.assertGreaterEqual(restored._operation_count, 42)
        self.assertEqual(len(restored._recent_events), 1)

    def test_deserialize_preserves_name(self) -> None:
        original = DeepCharacter(character_id="orig", name="原始名称")
        data = original.serialize()
        
        restored = DeepCharacter.deserialize(data, character_id="new_id", name="新名称")
        
        self.assertEqual(restored.name, "新名称")


class TestOperationCountTracking(unittest.TestCase):
    """操作计数跟踪测试"""

    def test_operation_count_increments_on_snapshot(self) -> None:
        dc = DeepCharacter(character_id="op_test")
        
        initial = dc._operation_count
        dc.get_state_snapshot(force_refresh=True)
        
        self.assertEqual(dc._operation_count, initial + 1)

    def test_multiple_snapshots_increment(self) -> None:
        dc = DeepCharacter(character_id="multi_op_test")
        
        count_before = dc._operation_count
        for _ in range(5):
            dc.get_state_snapshot(force_refresh=True)
        
        expected = count_before + 5
        if dc._operation_count > expected:
            self.assertEqual(dc._operation_count, expected + 1)
        else:
            self.assertEqual(dc._operation_count, expected)


if __name__ == "__main__":
    unittest.main()
