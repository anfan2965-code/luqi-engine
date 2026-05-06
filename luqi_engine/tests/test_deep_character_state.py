"""
DeepCharacterState 数据结构测试 — Phase 3 深度聚合层
覆盖: 构造/钳制/to_prompt_fragment/to_dict/is_under_stress/complexity_score
"""

from __future__ import annotations

import time
import unittest

from luqi_engine.character.deep_character import (
    ConsistencyIssue,
    ConsistencyIssueType,
    ConsistencySeverity,
    ConsistencyValidator,
    DeepCharacterState,
    MotivationDominance,
    NarrativeArcPhase,
    PsychologicalTensionLevel,
    ShadowActivationState,
    SubsystemHealthStatus,
)


class TestDeepCharacterStateConstruction(unittest.TestCase):
    """DeepCharacterState 构造和默认值测试"""

    def test_default_construction(self) -> None:
        state = DeepCharacterState()
        
        self.assertEqual(state.character_id, "")
        self.assertEqual(state.scene_context, "")
        self.assertEqual(state.dominant_archetype, "")
        self.assertEqual(state.shadow_state, ShadowActivationState.DORMANT)
        self.assertEqual(state.active_shadow_aspects, [])
        self.assertFalse(state.persona_active)
        self.assertEqual(state.persona_description, "")
        self.assertEqual(state.tension_level, PsychologicalTensionLevel.CALM)
        self.assertAlmostEqual(state.authenticity_score, 0.5, places=5)
        self.assertAlmostEqual(state.cognitive_dissonance, 0.0, places=5)
        self.assertAlmostEqual(state.existential_anxiety, 0.0, places=5)
        self.assertEqual(state.bad_faith_indicators, [])
        self.assertEqual(state.narrative_phase, NarrativeArcPhase.CALL)
        self.assertEqual(state.core_narrative, "")
        self.assertEqual(state.identity_statement, "")
        self.assertAlmostEqual(state.narrative_tension, 0.0, places=5)
        self.assertEqual(state.relationship_summary, "")
        self.assertEqual(state.social_role, "")
        self.assertAlmostEqual(state.trust_level_current, 0.5, places=5)
        self.assertEqual(state.relevant_memories, [])
        self.assertEqual(state.memory_count_total, 0)
        self.assertEqual(state.recent_memory_emotion, "")
        self.assertEqual(state.dominant_need, "")
        self.assertEqual(state.motivation_dominance, MotivationDominance.DEFICIENCY)
        self.assertEqual(state.need_satisfaction_map, {})
        self.assertIsNone(state.current_conflict)
        self.assertAlmostEqual(state.urgency_level, 1.0, places=5)
        self.assertEqual(state.overall_mood, "")
        self.assertEqual(state.behavioral_tendency, "")
        self.assertEqual(state.response_style_hint, "")
        self.assertFalse(state.should_trigger_shadow)
        self.assertEqual(state.consistency_issues, [])

    def test_timestamp_auto_set(self) -> None:
        before = time.time()
        state = DeepCharacterState()
        after = time.time()
        
        self.assertGreaterEqual(state.timestamp, before)
        self.assertLessEqual(state.timestamp, after)

    def test_explicit_timestamp(self) -> None:
        ts = 1700000000.5
        state = DeepCharacterState(timestamp=ts)
        
        self.assertEqual(state.timestamp, ts)

    def test_full_construction(self) -> None:
        state = DeepCharacterState(
            character_id="char_001",
            scene_context="酒馆",
            dominant_archetype="HERO",
            shadow_state=ShadowActivationState.ACTIVE,
            active_shadow_aspects=["傲慢"],
            persona_active=True,
            persona_description="勇敢的骑士",
            tension_level=PsychologicalTensionLevel.TENSE,
            authenticity_score=0.7,
            cognitive_dissonance=0.4,
            existential_anxiety=0.3,
            bad_faith_indicators=["否认恐惧"],
            narrative_phase=NarrativeArcPhase.ORDEAL,
            core_narrative="面对巨龙",
            identity_statement="我是屠龙者",
            narrative_tension=0.8,
            relationship_summary="与公主亲密",
            social_role="守护者",
            trust_level_current=0.9,
            relevant_memories=[{"content": "初遇公主", "emotion": "喜悦"}],
            memory_count_total=42,
            recent_memory_emotion="喜悦",
            dominant_need="ESTEEM",
            motivation_dominance=MotivationDominance.GROWTH,
            need_satisfaction_map={"ESTEEM": 0.6},
            current_conflict=None,
            urgency_level=1.2,
            overall_mood="焦虑+内心冲突",
            behavioral_tendency="寻求认可",
            response_style_hint="坚定",
            should_trigger_shadow=True,
            consistency_issues=["情绪-阴影不一致"],
        )
        
        self.assertEqual(state.character_id, "char_001")
        self.assertEqual(state.scene_context, "酒馆")
        self.assertEqual(state.dominant_archetype, "HERO")
        self.assertEqual(state.shadow_state, ShadowActivationState.ACTIVE)
        self.assertEqual(state.active_shadow_aspects, ["傲慢"])
        self.assertTrue(state.persona_active)
        self.assertEqual(state.persona_description, "勇敢的骑士")


class TestDeepCharacterStateClamping(unittest.TestCase):
    """数值字段钳制测试"""

    def test_authenticity_clamp_high(self) -> None:
        state = DeepCharacterState(authenticity_score=2.0)
        self.assertAlmostEqual(state.authenticity_score, 1.0, places=5)

    def test_authenticity_clamp_low(self) -> None:
        state = DeepCharacterState(authenticity_score=-1.0)
        self.assertAlmostEqual(state.authenticity_score, 0.0, places=5)

    def test_authenticity_boundary_high(self) -> None:
        state = DeepCharacterState(authenticity_score=1.0)
        self.assertAlmostEqual(state.authenticity_score, 1.0, places=5)

    def test_authenticity_boundary_low(self) -> None:
        state = DeepCharacterState(authenticity_score=0.0)
        self.assertAlmostEqual(state.authenticity_score, 0.0, places=5)

    def test_cognitive_dissonance_clamp(self) -> None:
        state = DeepCharacterState(cognitive_dissonance=5.0)
        self.assertAlmostEqual(state.cognitive_dissonance, 1.0, places=5)
        
        state2 = DeepCharacterState(cognitive_dissonance=-0.5)
        self.assertAlmostEqual(state2.cognitive_dissonance, 0.0, places=5)

    def test_existential_anxiety_clamp(self) -> None:
        state = DeepCharacterState(existential_anxiety=10.0)
        self.assertAlmostEqual(state.existential_anxiety, 1.0, places=5)

    def test_narrative_tension_clamp(self) -> None:
        state = DeepCharacterState(narrative_tension=-5.0)
        self.assertAlmostEqual(state.narrative_tension, 0.0, places=5)

    def test_trust_level_clamp(self) -> None:
        state = DeepCharacterState(trust_level_current=999.0)
        self.assertAlmostEqual(state.trust_level_current, 1.0, places=5)

    def test_urgency_clamp_high(self) -> None:
        state = DeepCharacterState(urgency_level=100.0)
        self.assertAlmostEqual(state.urgency_level, 2.0, places=5)

    def test_urgency_clamp_low(self) -> None:
        state = DeepCharacterState(urgency_level=0.0)
        self.assertAlmostEqual(state.urgency_level, 0.5, places=5)


class TestDeepCharacterStateToPromptFragment(unittest.TestCase):
    """to_prompt_fragment() 测试"""

    def test_empty_state_empty_output(self) -> None:
        state = DeepCharacterState()
        result = state.to_prompt_fragment()
        self.assertEqual(result, "")

    def test_with_archetype_only(self) -> None:
        state = DeepCharacterState(dominant_archetype="HERO")
        result = state.to_prompt_fragment()
        
        self.assertIn("[深层人格]", result)
        self.assertIn("原型:", result)
        self.assertIn("阴影:DORMANT", result)
        self.assertIn("面具:未激活", result)

    def test_with_active_persona(self) -> None:
        state = DeepCharacterState(
            dominant_archetype="CREATOR",
            persona_active=True,
            persona_description="艺术家",
        )
        result = state.to_prompt_fragment()
        
        self.assertIn("面具:艺术家", result)

    def test_with_tension_and_anxiety(self) -> None:
        state = DeepCharacterState(
            tension_level=PsychologicalTensionLevel.CRISIS,
            existential_anxiety=0.7,
            authenticity_score=0.4,
        )
        result = state.to_prompt_fragment()
        
        self.assertIn("[存在状态]", result)
        self.assertIn("危机", result)
        self.assertIn("本真:40%", result)
        self.assertIn("焦虑:70%", result)

    def test_with_narrative(self) -> None:
        state = DeepCharacterState(
            narrative_phase=NarrativeArcPhase.TRANSFORMATION,
            core_narrative="蜕变中",
            narrative_tension=0.6,
        )
        result = state.to_prompt_fragment()
        
        self.assertIn("[叙事弧]", result)
        self.assertIn("蜕变转化", result)
        self.assertIn("蜕变中", result)

    def test_with_motivation(self) -> None:
        state = DeepCharacterState(
            dominant_need="BELONGING",
            need_satisfaction_map={"BELONGING": 0.3},
            urgency_level=1.5,
            current_conflict="安全vs归属",
        )
        result = state.to_prompt_fragment()
        
        self.assertIn("主导需求", result)
        self.assertIn("满足度:30%", result)
        self.assertIn("冲突:安全vs归属", result)

    def test_with_memories(self) -> None:
        memories = [
            {"content": "第一次见面时她笑了", "emotion": "喜悦"},
            {"content": "他说过会保护我", "emotion": "安心"},
            {"content": "那个雨夜", "emotion": "悲伤"},
        ]
        state = DeepCharacterState(relevant_memories=memories)
        result = state.to_prompt_fragment()
        
        self.assertIn("[核心记忆]", result)
        self.assertIn("第一次见面时她笑了", result)

    def test_with_social(self) -> None:
        state = DeepCharacterState(
            relationship_summary="信任的伙伴",
            social_role="盟友",
            trust_level_current=0.85,
        )
        result = state.to_prompt_fragment()
        
        self.assertIn("[社交关系]", result)
        self.assertIn("信任的伙伴", result)
        self.assertIn("85%", result)

    def test_max_length_truncation(self) -> None:
        state = DeepCharacterState(
            dominant_archetype="HERO",
            active_shadow_aspects=["傲慢", "嫉妒", "愤怒", "贪婪", "懒惰"],
            persona_active=True,
            persona_description="一个非常非常长的面具描述用来测试截断功能是否正常工作",
            tension_level=PsychologicalTensionLevel.CRISIS,
            existential_anxiety=0.9,
            authenticity_score=0.2,
            narrative_phase=NarrativeArcPhase.ORDEAL,
            core_narrative="这是一个非常长的叙事描述用来测试截断功能" * 10,
            dominant_need="SAFETY",
            need_satisfaction_map={"SAFETY": 0.1},
            urgency_level=1.8,
            current_conflict="生存vs尊严",
            relevant_memories=[
                {"content": f"记忆{i}的内容描述" * 20, "emotion": f"情绪{i}"}
                for i in range(5)
            ],
            relationship_summary="复杂的关系网络描述" * 10,
            social_role="多重身份角色",
            trust_level_current=0.95,
        )
        result = state.to_prompt_fragment(max_length=100)
        
        self.assertLessEqual(len(result), 103)

    def test_combined_sections_order(self) -> None:
        state = DeepCharacterState(
            dominant_archetype="SAGE",
            tension_level=PsychologicalTensionLevel.TENSE,
            existential_anxiety=0.5,
            narrative_phase=NarrativeArcPhase.INITIATION,
            core_narrative="学习阶段",
            dominant_need="COGNITIVE",
            need_satisfaction_map={"COGNITIVE": 0.6},
            relevant_memories=[{"content": "读书笔记", "emotion": "好奇"}],
            relationship_summary="师生关系",
            trust_level_current=0.7,
        )
        result = state.to_prompt_fragment()
        
        sections_order = []
        if "[深层人格]" in result:
            sections_order.append("personality")
        if "[存在状态]" in result:
            sections_order.append("existential")
        if "[叙事弧]" in result:
            sections_order.append("narrative")
        if "[主导需求]" in result:
            sections_order.append("motivation")
        if "[核心记忆]" in result:
            sections_order.append("memory")
        if "[社交关系]" in result:
            sections_order.append("social")
        
        expected_order = ["personality", "existential", "narrative", "motivation", "memory", "social"]
        self.assertEqual(sections_order, expected_order)


class TestDeepCharacterStateToDict(unittest.TestCase):
    """to_dict() 序列化测试"""

    def test_empty_state_dict(self) -> None:
        state = DeepCharacterState()
        d = state.to_dict()
        
        self.assertIsInstance(d, dict)
        self.assertEqual(d["character_id"], "")
        self.assertEqual(d["shadow_state"], "DORMANT")
        self.assertEqual(d["tension_level"], "CALM")
        self.assertEqual(d["narrative_phase"], "CALL")
        self.assertEqual(d["active_shadow_aspects"], [])
        self.assertEqual(d["bad_faith_indicators"], [])

    def test_populated_state_dict(self) -> None:
        state = DeepCharacterState(
            character_id="test_id",
            dominant_archetype="EXPLORER",
            shadow_state=ShadowActivationState.RUMBLING,
            active_shadow_aspects=["冲动"],
            persona_active=True,
            persona_description="冒险家",
            tension_level=PsychologicalTensionLevel.DISSOCIATED,
            authenticity_score=0.8,
            cognitive_dissonance=0.5,
            existential_anxiety=0.6,
            bad_faith_indicators=["逃避选择"],
            narrative_phase=NarrativeArcPhase.RETURN,
            core_narrative="归来",
            identity_statement="成熟的探索者",
            narrative_tension=0.3,
            relationship_summary="老友",
            social_role="向导",
            trust_level_current=0.8,
            relevant_memories=[{"content": "远征归来", "emotion": "释然"}],
            memory_count_total=99,
            recent_memory_emotion="释然",
            dominant_need="SELF_ACTUALIZATION",
            motivation_dominance=MotivationDominance.META,
            need_satisfaction_map={"SELF_ACTUALIZATION": 0.7},
            current_conflict=None,
            urgency_level=0.9,
            overall_mood="平静",
            behavioral_tendency="开放坦诚",
            response_style_hint="沉稳从容",
            should_trigger_shadow=False,
            consistency_issues=[],
        )
        d = state.to_dict()
        
        self.assertEqual(d["character_id"], "test_id")
        self.assertEqual(d["dominant_archetype"], "EXPLORER")
        self.assertEqual(d["shadow_state"], "RUMBLING")
        self.assertEqual(d["active_shadow_aspects"], ["冲动"])
        self.assertTrue(d["persona_active"])
        self.assertEqual(d["persona_description"], "冒险家")
        self.assertEqual(d["tension_level"], "DISSOCIATED")
        self.assertAlmostEqual(d["authenticity_score"], 0.8, places=5)
        self.assertEqual(d["narrative_phase"], "RETURN")
        self.assertEqual(d["dominant_need"], "SELF_ACTUALIZATION")
        self.assertEqual(d["motivation_dominance"], "META")

    def test_none_conflict_serialized_correctly(self) -> None:
        state = DeepCharacterState(current_conflict=None)
        d = state.to_dict()
        self.assertIsNone(d["current_conflict"])


class TestDeepCharacterStateIsUnderStress(unittest.TestCase):
    """is_under_stress 属性测试"""

    def test_calm_no_anxiety_dormant_shadow_not_stressed(self) -> None:
        state = DeepCharacterState(
            tension_level=PsychologicalTensionLevel.CALM,
            existential_anxiety=0.1,
            shadow_state=ShadowActivationState.DORMANT,
        )
        self.assertFalse(state.is_under_stress)

    def test_tense_is_stressed(self) -> None:
        state = DeepCharacterState(tension_level=PsychologicalTensionLevel.TENSE)
        self.assertTrue(state.is_under_stress)

    def test_crisis_is_stressed(self) -> None:
        state = DeepCharacterState(tension_level=PsychologicalTensionLevel.CRISIS)
        self.assertTrue(state.is_under_stress)

    def test_dissociated_is_stressed(self) -> None:
        state = DeepCharacterState(tension_level=PsychologicalTensionLevel.DISSOCIATED)
        self.assertTrue(state.is_under_stress)

    def test_high_anxiety_is_stressed(self) -> None:
        state = DeepCharacterState(
            tension_level=PsychologicalTensionLevel.CALM,
            existential_anxiety=0.7,
            shadow_state=ShadowActivationState.DORMANT,
        )
        self.assertTrue(state.is_under_stress)

    def test_active_shadow_is_stressed(self) -> None:
        state = DeepCharacterState(
            tension_level=PsychologicalTensionLevel.CALM,
            existential_anxiety=0.3,
            shadow_state=ShadowActivationState.ACTIVE,
        )
        self.assertTrue(state.is_under_stress)

    def test_overrun_shadow_is_stressed(self) -> None:
        state = DeepCharacterState(shadow_state=ShadowActivationState.OVERRUN)
        self.assertTrue(state.is_under_stress)

    def test_rumbling_shadow_alone_not_stressed(self) -> None:
        state = DeepCharacterState(shadow_state=ShadowActivationState.RUMBLING)
        self.assertFalse(state.is_under_stress)


class TestDeepCharacterStateComplexityScore(unittest.TestCase):
    """complexity_score 属性测试"""

    def test_empty_state_zero_complexity(self) -> None:
        state = DeepCharacterState()
        score = state.complexity_score
        self.assertAlmostEqual(score, 0.0, places=5)

    def test_single_shadow_aspect(self) -> None:
        state = DeepCharacterState(active_shadow_aspects=["傲慢"])
        score = state.complexity_score
        self.assertAlmostEqual(score, 0.15, places=5)

    def test_multiple_shadow_aspects_capped(self) -> None:
        aspects = [f"aspect_{i}" for i in range(10)]
        state = DeepCharacterState(active_shadow_aspects=aspects)
        score = state.complexity_score
        self.assertLessEqual(score, 0.30)

    def test_tense_adds_complexity(self) -> None:
        state = DeepCharacterState(tension_level=PsychologicalTensionLevel.TENSE)
        score = state.complexity_score
        self.assertAlmostEqual(score, 0.15, places=5)

    def test_high_anxiety_adds_complexity(self) -> None:
        state = DeepCharacterState(existential_anxiety=0.6)
        score = state.complexity_score
        self.assertAlmostEqual(score, 0.10, places=5)

    def test_conflict_adds_complexity(self) -> None:
        state = DeepCharacterState(current_conflict="生存vs归属")
        score = state.complexity_score
        self.assertAlmostEqual(score, 0.20, places=5)

    def test_memories_add_complexity(self) -> None:
        memories = [{"content": f"mem{i}"} for i in range(5)]
        state = DeepCharacterState(relevant_memories=memories)
        score = state.complexity_score
        self.assertAlmostEqual(score, 0.15, places=5)

    def test_many_memories_capped(self) -> None:
        memories = [{"content": f"mem{i}"} for i in range(50)]
        state = DeepCharacterState(relevant_memories=memories)
        score = state.complexity_score
        self.assertLessEqual(score, 0.15)

    def test_narrative_tension_adds_complexity(self) -> None:
        state = DeepCharacterState(
            core_narrative="重要转折",
            narrative_tension=0.8,
        )
        score = state.complexity_score
        self.assertAlmostEqual(score, 0.10, places=5)

    def test_combined_factors_capped_at_one(self) -> None:
        state = DeepCharacterState(
            active_shadow_aspects=["a", "b", "c", "d", "e"],
            tension_level=PsychologicalTensionLevel.CRISIS,
            existential_anxiety=0.9,
            current_conflict="多重冲突",
            relevant_memories=[{"content": f"m{i}"} for i in range(5)],
            core_narrative="重大事件",
            narrative_tension=0.9,
        )
        score = state.complexity_score
        self.assertGreaterEqual(score, 0.5)
        self.assertLessEqual(score, 1.0)


class TestConsistencyIssueDataclass(unittest.TestCase):
    """ConsistencyIssue 数据类测试"""

    def test_default_construction(self) -> None:
        issue = ConsistencyIssue(
            issue_type=ConsistencyIssueType.EMOTION_SHADOW_MISMATCH,
            severity=ConsistencySeverity.WARNING,
        )
        
        self.assertEqual(issue.issue_type, ConsistencyIssueType.EMOTION_SHADOW_MISMATCH)
        self.assertEqual(issue.severity, ConsistencySeverity.WARNING)
        self.assertEqual(issue.message, "")
        self.assertEqual(issue.suggestion, "")
        self.assertEqual(issue.subsystems_involved, [])

    def test_full_construction(self) -> None:
        issue = ConsistencyIssue(
            issue_type=ConsistencyIssueType.MEMORY_MOTIVATION_CONTRADICTION,
            severity=ConsistencySeverity.ERROR,
            message="记忆显示威胁但安全感高",
            suggestion="降低安全需求满足度",
            subsystems_involved=["memory", "motivation"],
        )
        
        self.assertEqual(issue.issue_type, ConsistencyIssueType.MEMORY_MOTIVATION_CONTRADICTION)
        self.assertEqual(issue.severity, ConsistencySeverity.ERROR)
        self.assertEqual(issue.message, "记忆显示威胁但安全感高")
        self.assertEqual(issue.suggestion, "降低安全需求满足度")
        self.assertEqual(issue.subsystems_involved, ["memory", "motivation"])


class TestSubsystemHealthStatusDataclass(unittest.TestCase):
    """SubsystemHealthStatus 数据类测试"""

    def test_default_healthy(self) -> None:
        status = SubsystemHealthStatus(subsystem_name="jungian")
        
        self.assertEqual(status.subsystem_name, "jungian")
        self.assertTrue(status.is_healthy)
        self.assertEqual(status.issues, [])

    def test_unhealthy_with_issues(self) -> None:
        status = SubsystemHealthStatus(
            subsystem_name="memory",
            is_healthy=False,
            issues=["连接超时", "数据损坏"],
        )
        
        self.assertFalse(status.is_healthy)
        self.assertEqual(status.issues, ["连接超时", "数据损坏"])


if __name__ == "__main__":
    unittest.main()
