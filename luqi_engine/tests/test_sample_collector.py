from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from luqi_engine.training.sample_collector import SampleCollector, _CORRECTION_SEVERITY_WEIGHTS
from luqi_engine.core.types import (
    TrainingInput,
    AgentOutputs,
    AlgorithmCorrections,
    FinalOutput,
    EmotionDelta,
    CanonicalIR,
    NarrativeDelta,
    CriticVerdict,
    CriticCheck,
    CriticCorrections,
    AtmosphereOutput,
    CorrectionRecord,
)
from luqi_engine.core.config import TrainingConfig
from luqi_engine.core.constants import CorrectionSeverity


def _make_input() -> TrainingInput:
    return TrainingInput(
        narrative_summary="测试叙事摘要",
        user_message="你好",
        chapter_context="第一章",
    )


def _make_outputs(
    novel: bool = True,
    dialogue: bool = True,
    critic: bool = True,
    atmosphere: bool = True,
) -> AgentOutputs:
    return AgentOutputs(
        novel=NarrativeDelta(version=1) if novel else None,
        dialogue=CanonicalIR(intent="greet", confidence=0.9) if dialogue else None,
        critic=CriticVerdict(verdict="accept", overall_confidence=0.95) if critic else None,
        atmosphere=AtmosphereOutput(mode="light") if atmosphere else None,
    )


def _make_corrections(
    dialogue_count: int = 0,
    novel_count: int = 0,
    severity: str = "clamp",
) -> AlgorithmCorrections:
    dialogue_corrections = [
        CorrectionRecord(field=f"field_d_{i}", severity=severity)
        for i in range(dialogue_count)
    ]
    novel_corrections = [
        CorrectionRecord(field=f"field_n_{i}", severity=severity)
        for i in range(novel_count)
    ]
    return AlgorithmCorrections(
        dialogue_corrections=dialogue_corrections,
        novel_corrections=novel_corrections,
    )


def _make_output(
    action: str = "",
    emotion: bool = False,
    voice: bool = False,
) -> FinalOutput:
    return FinalOutput(
        reply_text="你好！",
        executed_action=action,
        final_emotion=EmotionDelta(pleasure=0.5) if emotion else None,
        voice_renderer_used=voice,
        narrative_version_after=1,
    )


class TestSampleCollectorBasic(unittest.TestCase):
    def test_collect_returns_training_sample(self):
        collector = SampleCollector()
        sample = collector.collect(
            character_id="char_001",
            training_input=_make_input(),
            agent_outputs=_make_outputs(),
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(),
        )
        self.assertEqual(sample.character_id, "char_001")
        self.assertTrue(sample.sample_id.startswith("sample_"))
        self.assertGreater(sample.timestamp, 0.0)
        self.assertIsNotNone(sample.input)
        self.assertIsNotNone(sample.agent_outputs)
        self.assertIsNotNone(sample.algorithm_corrections)
        self.assertIsNotNone(sample.final_output)
        self.assertIsNotNone(sample.quality)

    def test_collect_with_config(self):
        config = TrainingConfig(quality_threshold=0.5)
        collector = SampleCollector(config=config)
        sample = collector.collect(
            character_id="char_002",
            training_input=_make_input(),
            agent_outputs=_make_outputs(),
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(),
        )
        self.assertEqual(sample.character_id, "char_002")


class TestSampleQuality(unittest.TestCase):
    def test_no_corrections_gold_grade(self):
        collector = SampleCollector()
        sample = collector.collect(
            character_id="char_003",
            training_input=_make_input(),
            agent_outputs=_make_outputs(),
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(),
        )
        self.assertGreaterEqual(sample.quality.overall_score, 0.8)
        self.assertEqual(sample.quality.grade, "gold")

    def test_many_clamp_corrections_lowers_score(self):
        collector = SampleCollector()
        corrections = _make_corrections(dialogue_count=5, novel_count=5, severity="clamp")
        sample = collector.collect(
            character_id="char_004",
            training_input=_make_input(),
            agent_outputs=_make_outputs(),
            algorithm_corrections=corrections,
            final_output=_make_output(),
        )
        no_correction_sample = collector.collect(
            character_id="char_004b",
            training_input=_make_input(),
            agent_outputs=_make_outputs(),
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(),
        )
        self.assertLess(sample.quality.overall_score, no_correction_sample.quality.overall_score)

    def test_reject_severity_creates_contamination_flag(self):
        collector = SampleCollector()
        corrections = _make_corrections(dialogue_count=1, severity="reject")
        sample = collector.collect(
            character_id="char_005",
            training_input=_make_input(),
            agent_outputs=_make_outputs(),
            algorithm_corrections=corrections,
            final_output=_make_output(),
        )
        self.assertTrue(len(sample.quality.contamination_flags) > 0)

    def test_critic_reject_lowers_coherence(self):
        collector = SampleCollector()
        outputs_accept = _make_outputs()
        outputs_reject = AgentOutputs(
            novel=NarrativeDelta(version=1),
            dialogue=CanonicalIR(intent="greet", confidence=0.9),
            critic=CriticVerdict(verdict="reject", overall_confidence=0.3),
            atmosphere=AtmosphereOutput(mode="light"),
        )
        sample_accept = collector.collect(
            character_id="char_006a",
            training_input=_make_input(),
            agent_outputs=outputs_accept,
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(),
        )
        sample_reject = collector.collect(
            character_id="char_006b",
            training_input=_make_input(),
            agent_outputs=outputs_reject,
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(),
        )
        self.assertGreater(
            sample_accept.quality.coherence_score,
            sample_reject.quality.coherence_score,
        )

    def test_scores_bounded_zero_to_one(self):
        collector = SampleCollector()
        corrections = _make_corrections(dialogue_count=10, novel_count=10, severity="reject")
        sample = collector.collect(
            character_id="char_007",
            training_input=_make_input(),
            agent_outputs=_make_outputs(),
            algorithm_corrections=corrections,
            final_output=_make_output(),
        )
        self.assertGreaterEqual(sample.quality.overall_score, 0.0)
        self.assertLessEqual(sample.quality.overall_score, 1.0)
        self.assertGreaterEqual(sample.quality.coherence_score, 0.0)
        self.assertLessEqual(sample.quality.coherence_score, 1.0)
        self.assertGreaterEqual(sample.quality.character_faithfulness, 0.0)
        self.assertLessEqual(sample.quality.character_faithfulness, 1.0)
        self.assertGreaterEqual(sample.quality.narrative_alignment, 0.0)
        self.assertLessEqual(sample.quality.narrative_alignment, 1.0)


class TestUsageTags(unittest.TestCase):
    def test_all_agents_present(self):
        collector = SampleCollector()
        sample = collector.collect(
            character_id="char_008",
            training_input=_make_input(),
            agent_outputs=_make_outputs(novel=True, dialogue=True, critic=True, atmosphere=True),
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(voice=True),
        )
        self.assertIn("layer1_narrative", sample.usage_tags)
        self.assertIn("layer2_decision", sample.usage_tags)
        self.assertIn("layer3_voice", sample.usage_tags)
        self.assertIn("layer4_critic", sample.usage_tags)
        self.assertIn("layer5_atmosphere", sample.usage_tags)

    def test_no_agents_no_voice(self):
        collector = SampleCollector()
        sample = collector.collect(
            character_id="char_009",
            training_input=_make_input(),
            agent_outputs=AgentOutputs(),
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(voice=False),
        )
        self.assertEqual(len(sample.usage_tags), 0)

    def test_partial_agents(self):
        collector = SampleCollector()
        outputs = AgentOutputs(
            novel=NarrativeDelta(version=1),
            dialogue=None,
            critic=None,
            atmosphere=None,
        )
        sample = collector.collect(
            character_id="char_010",
            training_input=_make_input(),
            agent_outputs=outputs,
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(voice=False),
        )
        self.assertEqual(sample.usage_tags, ["layer1_narrative"])


class TestGradeThresholds(unittest.TestCase):
    def test_gold_threshold(self):
        collector = SampleCollector()
        sample = collector.collect(
            character_id="char_gold",
            training_input=_make_input(),
            agent_outputs=_make_outputs(),
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(),
        )
        self.assertEqual(sample.quality.grade, "gold")

    def test_bronze_with_many_corrections(self):
        collector = SampleCollector()
        corrections = _make_corrections(dialogue_count=3, novel_count=3, severity="override")
        sample = collector.collect(
            character_id="char_bronze",
            training_input=_make_input(),
            agent_outputs=_make_outputs(),
            algorithm_corrections=corrections,
            final_output=_make_output(),
        )
        self.assertIn(sample.quality.grade, ("bronze", "silver", "gold", "rejected"))


class TestEmotionActionAlignment(unittest.TestCase):
    def test_action_alignment_bonus(self):
        collector = SampleCollector()
        outputs = AgentOutputs(
            novel=NarrativeDelta(version=1),
            dialogue=CanonicalIR(intent="greet", confidence=0.9, action="wave"),
            critic=CriticVerdict(verdict="accept"),
            atmosphere=AtmosphereOutput(mode="light"),
        )
        sample = collector.collect(
            character_id="char_align",
            training_input=_make_input(),
            agent_outputs=outputs,
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(action="wave"),
        )
        self.assertGreater(sample.quality.character_faithfulness, 0.0)

    def test_emotion_delta_alignment(self):
        collector = SampleCollector()
        outputs = AgentOutputs(
            novel=NarrativeDelta(version=1),
            dialogue=CanonicalIR(
                intent="greet",
                confidence=0.9,
                emotion_delta=EmotionDelta(pleasure=0.5),
            ),
            critic=CriticVerdict(verdict="accept"),
            atmosphere=AtmosphereOutput(mode="light"),
        )
        sample = collector.collect(
            character_id="char_emotion",
            training_input=_make_input(),
            agent_outputs=outputs,
            algorithm_corrections=_make_corrections(),
            final_output=_make_output(emotion=True),
        )
        self.assertGreater(sample.quality.character_faithfulness, 0.0)


class TestCorrectionSeverityWeights(unittest.TestCase):
    def test_all_keys_are_enum_instances(self):
        for key in _CORRECTION_SEVERITY_WEIGHTS:
            self.assertIsInstance(key, CorrectionSeverity)

    def test_override_key_is_enum(self):
        self.assertIn(CorrectionSeverity.OVERRIDE, _CORRECTION_SEVERITY_WEIGHTS)
        self.assertEqual(_CORRECTION_SEVERITY_WEIGHTS[CorrectionSeverity.OVERRIDE], 0.3)

    def test_clamp_key_is_enum(self):
        self.assertIn(CorrectionSeverity.CLAMP, _CORRECTION_SEVERITY_WEIGHTS)
        self.assertEqual(_CORRECTION_SEVERITY_WEIGHTS[CorrectionSeverity.CLAMP], 0.1)

    def test_reject_key_is_enum(self):
        self.assertIn(CorrectionSeverity.REJECT, _CORRECTION_SEVERITY_WEIGHTS)
        self.assertEqual(_CORRECTION_SEVERITY_WEIGHTS[CorrectionSeverity.REJECT], 0.5)


class TestVersionConsistency(unittest.TestCase):
    def test_matching_versions_returns_one(self):
        collector = SampleCollector()
        delta = NarrativeDelta(version=3)
        result = collector._version_consistency(delta, 3)
        self.assertEqual(result, 1.0)

    def test_mismatched_versions_returns_zero(self):
        collector = SampleCollector()
        delta = NarrativeDelta(version=2)
        result = collector._version_consistency(delta, 5)
        self.assertEqual(result, 0.0)

    def test_missing_novel_delta_returns_half(self):
        collector = SampleCollector()
        result = collector._version_consistency(None, 3)
        self.assertEqual(result, 0.5)

    def test_zero_version_returns_half(self):
        collector = SampleCollector()
        delta = NarrativeDelta(version=0)
        result = collector._version_consistency(delta, 3)
        self.assertEqual(result, 0.5)

    def test_zero_version_after_returns_half(self):
        collector = SampleCollector()
        delta = NarrativeDelta(version=3)
        result = collector._version_consistency(delta, 0)
        self.assertEqual(result, 0.5)

    def test_negative_version_after_returns_half(self):
        collector = SampleCollector()
        delta = NarrativeDelta(version=3)
        result = collector._version_consistency(delta, -1)
        self.assertEqual(result, 0.5)


if __name__ == "__main__":
    unittest.main()
