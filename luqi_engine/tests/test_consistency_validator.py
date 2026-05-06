"""
ConsistencyValidator 一致性验证器测试 — Phase 3 深度聚合层
覆盖: validate_emotion_shadow / validate_memory_motivation / validate_narrative_behavior
"""

from __future__ import annotations

import unittest

from luqi_engine.character.deep_character import (
    ConsistencyIssue,
    ConsistencyIssueType,
    ConsistencySeverity,
    ConsistencyValidator,
    MotivationDominance,
    NarrativeArcPhase,
    ShadowActivationState,
)


class TestValidateEmotionShadowConsistency(unittest.TestCase):
    """情绪-阴影一致性验证测试"""

    def test_empty_emotion_no_issue(self) -> None:
        result = ConsistencyValidator.validate_emotion_shadow_consistency(
            emotion_state={},
            shadow_state=ShadowActivationState.DORMANT,
            active_shadows=[],
        )
        self.assertIsNone(result)

    def test_dormant_shadow_low_emotion_ok(self) -> None:
        result = ConsistencyValidator.validate_emotion_shadow_consistency(
            emotion_state={"fear": 0.2, "anger": 0.1},
            shadow_state=ShadowActivationState.DORMANT,
            active_shadows=["傲慢"],
        )
        self.assertIsNone(result)

    def test_overrun_with_low_emotion_error(self) -> None:
        result = ConsistencyValidator.validate_emotion_shadow_consistency(
            emotion_state={"fear": 0.2},
            shadow_state=ShadowActivationState.OVERRUN,
            active_shadows=["愤怒"],
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(
            result.issue_type,
            ConsistencyIssueType.EMOTION_SHADOW_MISMATCH,
        )
        self.assertEqual(result.severity, ConsistencySeverity.ERROR)
        self.assertIn("OVERRUN", result.message)
        self.assertIn("jungian", result.subsystems_involved)
        self.assertIn("emotion", result.subsystems_involved)

    def test_overrun_with_high_emotion_ok(self) -> None:
        result = ConsistencyValidator.validate_emotion_shadow_consistency(
            emotion_state={"fear": 0.8, "anger": 0.9},
            shadow_state=ShadowActivationState.OVERRUN,
            active_shadows=["愤怒", "恐惧"],
        )
        self.assertIsNone(result)

    def test_active_with_very_low_emotion_warning(self) -> None:
        result = ConsistencyValidator.validate_emotion_shadow_consistency(
            emotion_state={"anxiety": 0.3},
            shadow_state=ShadowActivationState.ACTIVE,
            active_shadows=["嫉妒"],
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.severity, ConsistencySeverity.WARNING)
        self.assertIn("ACTIVE", result.message)

    def test_active_with_moderate_emotion_ok(self) -> None:
        result = ConsistencyValidator.validate_emotion_shadow_consistency(
            emotion_state={"anger": 0.6, "shame": 0.5},
            shadow_state=ShadowActivationState.ACTIVE,
            active_shadows=["羞耻"],
        )
        self.assertIsNone(result)

    def test_rumbling_any_emotion_ok(self) -> None:
        result = ConsistencyValidator.validate_emotion_shadow_consistency(
            emotion_state={"fear": 0.1},
            shadow_state=ShadowActivationState.RUMBLING,
            active_shadows=[],
        )
        self.assertIsNone(result)

    def test_dormant_with_high_emotion_warning(self) -> None:
        result = ConsistencyValidator.validate_emotion_shadow_consistency(
            emotion_state={"rage": 0.9, "despair": 0.7},
            shadow_state=ShadowActivationState.DORMANT,
            active_shadows=["未激活的阴影面"],
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.severity, ConsistencySeverity.WARNING)
        self.assertIn("DORMANT", result.message)
        self.assertIn("ShadowAspect", result.suggestion)

    def test_dormant_active_shadows_with_high_emotion_warning(self) -> None:
        result = ConsistencyValidator.validate_emotion_shadow_consistency(
            emotion_state={"fury": 0.85},
            shadow_state=ShadowActivationState.DORMANT,
            active_shadows=["愤怒"],
        )
        
        self.assertIsNotNone(result)
        self.assertIn("高强度负面情绪", result.message)


class TestValidateMemoryMotivationConsistency(unittest.TestCase):
    """记忆-动机一致性验证测试"""

    def test_empty_inputs_no_issue(self) -> None:
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=[],
            dominant_need="SAFETY",
            need_satisfaction={},
        )
        self.assertIsNone(result)

    def test_none_memories_no_issue(self) -> None:
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=None,
            dominant_need="",
            need_satisfaction=None,
        )
        self.assertIsNone(result)

    def test_threat_memory_high_safety_warning(self) -> None:
        memories = [
            {"content": "遭遇了致命的威胁和危险攻击"},
            {"content": "差点被杀死"},
        ]
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=memories,
            dominant_need="SAFETY",
            need_satisfaction={"PHYSIOLOGICAL": 0.9, "SAFETY": 0.85},
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(
            result.issue_type,
            ConsistencyIssueType.MEMORY_MOTIVATION_CONTRADICTION,
        )
        self.assertEqual(result.severity, ConsistencySeverity.WARNING)
        self.assertIn("威胁", result.message)
        self.assertIn("memory", result.subsystems_involved)
        self.assertIn("motivation", result.subsystems_involved)

    def test_threat_memory_low_safety_ok(self) -> None:
        memories = [{"content": "遇到了危险"}]
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=memories,
            dominant_need="SAFETY",
            need_satisfaction={"SAFETY": 0.2},
        )
        self.assertIsNone(result)

    def test_social_positive_low_belonging_info(self) -> None:
        memories = [
            {"content": "朋友非常友好地帮助了我"},
            {"content": "大家都很信任我"},
        ]
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=memories,
            dominant_need="BELONGING",
            need_satisfaction={"BELONGING": 0.1},
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.severity, ConsistencySeverity.INFO)
        self.assertIn("社交正面记忆", result.message)

    def test_social_positive_normal_belonging_ok(self) -> None:
        memories = [{"content": "朋友的帮助让我感到温暖"}]
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=memories,
            dominant_need="BELONGING",
            need_satisfaction={"BELONGING": 0.6},
        )
        self.assertIsNone(result)

    def test_isolation_memory_high_belonging_warning(self) -> None:
        memories = [
            {"content": "被所有人抛弃了，孤独一人"},
            {"content": "无人关心我的死活"},
        ]
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=memories,
            dominant_need="BELONGING",
            need_satisfaction={"BELONGING": 0.95},
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.severity, ConsistencySeverity.WARNING)
        self.assertIn("孤立", result.message)

    def test_isolation_memory_low_belonging_ok(self) -> None:
        memories = [{"content": "感到非常孤独"}]
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=memories,
            dominant_need="BELONGING",
            need_satisfaction={"BELONGING": 0.15},
        )
        self.assertIsNone(result)

    def test_neutral_memory_no_issue(self) -> None:
        memories = [
            {"content": "今天天气不错"},
            {"content": "吃了一顿美味的午餐"},
        ]
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=memories,
            dominant_need="COGNITIVE",
            need_satisfaction={"COGNITIVE": 0.5},
        )
        self.assertIsNone(result)

    def test_only_first_five_memories_checked(self) -> None:
        memories = [{"content": f"中性内容{i}"} for i in range(10)]
        result = ConsistencyValidator.validate_memory_motivation_consistency(
            recent_memories=memories,
            dominant_need="PHYSIOLOGICAL",
            need_satisfaction={"PHYSIOLOGICAL": 0.99},
        )
        self.assertIsNone(result)


class TestValidateNarrativeBehaviorConsistency(unittest.TestCase):
    """叙事-行为一致性验证测试"""

    def test_empty_behavior_no_issue(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.ORDEAL,
            behavioral_tendency="",
            authenticity_score=0.5,
        )
        self.assertIsNone(result)

    def test_ordeal_struggle_behavior_ok(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.ORDEAL,
            behavioral_tendency="在痛苦中坚持挣扎对抗命运",
            authenticity_score=0.6,
        )
        self.assertIsNone(result)

    def test_ordeal_relaxed_behavior_warning(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.ORDEAL,
            behavioral_tendency="轻松随意无忧无虑地生活",
            authenticity_score=0.5,
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(
            result.issue_type,
            ConsistencyIssueType.NARRATIVE_BEHAVIOR_MISMATCH,
        )
        self.assertEqual(result.severity, ConsistencySeverity.WARNING)
        self.assertIn("ORDEAL", result.message)

    def test_transformation_growing_behavior_ok(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.TRANSFORMATION,
            behavioral_tendency="正在成长释然领悟生命的意义",
            authenticity_score=0.8,
        )
        self.assertIsNone(result)

    def test_transformation_desperate_behavior_warning(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.TRANSFORMATION,
            behavioral_tendency="固执绝望崩溃无法接受现实",
            authenticity_score=0.3,
        )
        
        self.assertIsNotNone(result)
        self.assertIn("TRANSFORMATION", result.message)

    def test_return_calm_behavior_ok(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.RETURN,
            behavioral_tendency="自信智慧平静从容面对一切",
            authenticity_score=0.9,
        )
        self.assertIsNone(result)

    def test_return_panicked_behavior_warning(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.RETURN,
            behavioral_tendency="慌乱困惑冲动不知所措",
            authenticity_score=0.4,
        )
        
        self.assertIsNotNone(result)
        self.assertIn("RETURN", result.message)

    def test_call_exploring_behavior_ok(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.CALL,
            behavioral_tendency="探索好奇迷茫中寻找方向",
            authenticity_score=0.5,
        )
        self.assertIsNone(result)

    def test_initiation_learning_behavior_ok(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.INITIATION,
            behavioral_tendency="学习尝试成长适应新环境",
            authenticity_score=0.6,
        )
        self.assertIsNone(result)

    def test_expected_keyword_overrides_opposite(self) -> None:
        result = ConsistencyValidator.validate_narrative_behavior_consistency(
            narrative_phase=NarrativeArcPhase.ORDEAL,
            behavioral_tendency="痛苦坚持但也偶尔轻松",
            authenticity_score=0.5,
        )
        self.assertIsNone(result)


class TestConsistencyValidatorConstants(unittest.TestCase):
    """验证器常量测试"""

    def test_threshold_constants_defined(self) -> None:
        self.assertIsInstance(ConsistencyValidator.SHADOW_ACTIVE_THRESHOLD, float)
        self.assertIsInstance(ConsistencyValidator.HIGH_EMOTION_THRESHOLD, float)
        self.assertIsInstance(ConsistencyValidator.LOW_SAFETY_THRESHOLD, float)
        self.assertIsInstance(ConsistencyValidator.LOW_BELONGING_THRESHOLD, float)

    def test_severity_constants_accessible(self) -> None:
        self.assertEqual(ConsistencyValidator.SEVERITY_INFO, ConsistencySeverity.INFO)
        self.assertEqual(ConsistencyValidator.SEVERITY_WARNING, ConsistencySeverity.WARNING)
        self.assertEqual(ConsistencyValidator.SEVERITY_ERROR, ConsistencySeverity.ERROR)


if __name__ == "__main__":
    unittest.main()
