"""文档保护器测试"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from luqi_engine.training.document_protector import (
    DegradationDocumentProtector,
    ProtectionReport,
)
from luqi_engine.core.types import (
    NarrativeDelta,
    NewFact,
    ChapterUpdate,
    NextPrediction,
    Fact,
    ChapterOutline,
    StoryBeat,
)


def _make_existing_facts(count: int = 2) -> list:
    return [
        Fact(
            id=f"fact_{i:03d}",
            sequence_number=i,
            timestamp="tick_1",
            source="local",
            content=f"已有事实{i}",
            participants=["角色A"],
        )
        for i in range(count)
    ]


def _make_chapter_outline(beat_count: int = 3) -> ChapterOutline:
    beats = [
        StoryBeat(
            name=f"beat_{i}",
            description=f"节拍{i}",
            expected_participants=["角色A"],
        )
        for i in range(beat_count)
    ]
    return ChapterOutline(
        chapter_id=1,
        title="测试章节",
        beats=beats,
    )


def _make_delta(
    new_facts: list = None,
    chapter_update: ChapterUpdate = None,
    next_prediction: NextPrediction = None,
) -> NarrativeDelta:
    return NarrativeDelta(
        version=1,
        new_facts=new_facts or [],
        chapter_update=chapter_update,
        next_prediction=next_prediction,
    )


class TestDocumentProtectorNormalMode(unittest.TestCase):
    def test_normal_mode_passes_through(self):
        protector = DegradationDocumentProtector()
        delta = _make_delta(
            new_facts=[NewFact(source="local", content="新事实")],
        )
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=None,
            is_degraded=False,
        )
        self.assertTrue(report.applied)
        self.assertEqual(len(protected.new_facts), 1)
        self.assertEqual(report.fact_overwrites_blocked, 0)

    def test_normal_mode_no_protection(self):
        protector = DegradationDocumentProtector()
        delta = _make_delta(
            new_facts=[NewFact(source="local", content="已有事实0")],
        )
        existing = _make_existing_facts(1)
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=existing,
            current_chapter_outline=None,
            is_degraded=False,
        )
        self.assertEqual(len(protected.new_facts), 1)
        self.assertEqual(report.fact_overwrites_blocked, 0)


class TestDocumentProtectorFactOverwrite(unittest.TestCase):
    def test_degraded_blocks_local_overwrite(self):
        protector = DegradationDocumentProtector()
        existing = _make_existing_facts(1)
        delta = _make_delta(
            new_facts=[NewFact(source="local", content="已有事实0")],
        )
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=existing,
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertEqual(len(protected.new_facts), 0)
        self.assertEqual(report.fact_overwrites_blocked, 1)

    def test_degraded_allows_cloud_overwrite(self):
        protector = DegradationDocumentProtector()
        existing = _make_existing_facts(1)
        delta = _make_delta(
            new_facts=[NewFact(source="cloud", content="已有事实0")],
        )
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=existing,
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertEqual(len(protected.new_facts), 1)
        self.assertEqual(report.fact_overwrites_blocked, 0)

    def test_degraded_allows_new_local_fact(self):
        protector = DegradationDocumentProtector()
        existing = _make_existing_facts(2)
        delta = _make_delta(
            new_facts=[NewFact(source="local", content="全新事实")],
        )
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=existing,
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertEqual(len(protected.new_facts), 1)
        self.assertEqual(report.fact_overwrites_blocked, 0)

    def test_degraded_blocks_by_id(self):
        protector = DegradationDocumentProtector()
        existing = [Fact(
            id="fact_special",
            sequence_number=1,
            timestamp="tick_1",
            source="local",
            content="特殊事实",
            participants=[],
        )]
        delta = _make_delta(
            new_facts=[NewFact(id="fact_special", source="local", content="覆盖内容")],
        )
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=existing,
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertEqual(len(protected.new_facts), 0)
        self.assertEqual(report.fact_overwrites_blocked, 1)

    def test_degraded_mixed_facts(self):
        protector = DegradationDocumentProtector()
        existing = _make_existing_facts(1)
        delta = _make_delta(
            new_facts=[
                NewFact(source="local", content="已有事实0"),
                NewFact(source="cloud", content="已有事实0"),
                NewFact(source="local", content="全新事实"),
            ],
        )
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=existing,
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertEqual(len(protected.new_facts), 2)
        self.assertEqual(report.fact_overwrites_blocked, 1)

    def test_degraded_retracted_fact_not_blocking(self):
        protector = DegradationDocumentProtector()
        existing = [Fact(
            id="fact_retracted",
            sequence_number=1,
            timestamp="tick_1",
            source="local",
            content="已撤回事实",
            participants=[],
            is_retracted=True,
        )]
        delta = _make_delta(
            new_facts=[NewFact(source="local", content="已撤回事实")],
        )
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=existing,
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertEqual(len(protected.new_facts), 1)
        self.assertEqual(report.fact_overwrites_blocked, 0)


class TestDocumentProtectorBeatReduction(unittest.TestCase):
    def test_degraded_blocks_beat_reduction(self):
        protector = DegradationDocumentProtector()
        outline = _make_chapter_outline(3)
        update = ChapterUpdate(
            current_beat_progress=0.5,
            new_beat_suggested={"name": "new_beat"},
            constraints_removed=["constraint_1"],
        )
        delta = _make_delta(chapter_update=update)
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=outline,
            is_degraded=True,
        )
        self.assertTrue(report.beat_reduction_blocked)
        self.assertIsNone(protected.chapter_update.new_beat_suggested)

    def test_degraded_allows_beat_addition(self):
        protector = DegradationDocumentProtector()
        outline = _make_chapter_outline(3)
        update = ChapterUpdate(
            current_beat_progress=0.5,
            new_beat_suggested={"name": "new_beat"},
            constraints_removed=[],
        )
        delta = _make_delta(chapter_update=update)
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=outline,
            is_degraded=True,
        )
        self.assertFalse(report.beat_reduction_blocked)
        self.assertIsNotNone(protected.chapter_update.new_beat_suggested)

    def test_degraded_no_chapter_update(self):
        protector = DegradationDocumentProtector()
        delta = _make_delta(chapter_update=None)
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=_make_chapter_outline(3),
            is_degraded=True,
        )
        self.assertIsNone(protected.chapter_update)
        self.assertFalse(report.beat_reduction_blocked)


class TestDocumentProtectorConfidenceDecay(unittest.TestCase):
    def test_degraded_decays_confidence(self):
        protector = DegradationDocumentProtector(confidence_decay_factor=0.7)
        prediction = NextPrediction(
            likely_next_scenes=[
                {"scene_id": "s1", "probability": 0.9},
                {"scene_id": "s2", "probability": 0.6},
            ],
            narrative_tension=0.8,
            suggested_pace="normal",
        )
        delta = _make_delta(next_prediction=prediction)
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertTrue(report.confidence_decay_applied)
        self.assertAlmostEqual(
            protected.next_prediction.likely_next_scenes[0]["probability"],
            0.63,
            places=2,
        )
        self.assertAlmostEqual(
            protected.next_prediction.likely_next_scenes[1]["probability"],
            0.42,
            places=2,
        )
        self.assertAlmostEqual(
            protected.next_prediction.narrative_tension,
            0.56,
            places=2,
        )

    def test_normal_mode_no_decay(self):
        protector = DegradationDocumentProtector(confidence_decay_factor=0.7)
        prediction = NextPrediction(
            likely_next_scenes=[
                {"scene_id": "s1", "probability": 0.9},
            ],
            narrative_tension=0.8,
            suggested_pace="normal",
        )
        delta = _make_delta(next_prediction=prediction)
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=None,
            is_degraded=False,
        )
        self.assertFalse(report.confidence_decay_applied)
        self.assertAlmostEqual(
            protected.next_prediction.likely_next_scenes[0]["probability"],
            0.9,
            places=2,
        )

    def test_degraded_no_prediction(self):
        protector = DegradationDocumentProtector()
        delta = _make_delta(next_prediction=None)
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertIsNone(protected.next_prediction)
        self.assertFalse(report.confidence_decay_applied)

    def test_degraded_empty_prediction_scenes(self):
        protector = DegradationDocumentProtector()
        prediction = NextPrediction(
            likely_next_scenes=[],
            narrative_tension=0.5,
            suggested_pace="normal",
        )
        delta = _make_delta(next_prediction=prediction)
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertFalse(report.confidence_decay_applied)


class TestDocumentProtectorCustomDecayFactor(unittest.TestCase):
    def test_custom_decay_factor(self):
        protector = DegradationDocumentProtector(confidence_decay_factor=0.5)
        prediction = NextPrediction(
            likely_next_scenes=[
                {"scene_id": "s1", "probability": 0.8},
            ],
            narrative_tension=0.6,
            suggested_pace="normal",
        )
        delta = _make_delta(next_prediction=prediction)
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertAlmostEqual(
            protected.next_prediction.likely_next_scenes[0]["probability"],
            0.4,
            places=2,
        )
        self.assertAlmostEqual(
            protected.next_prediction.narrative_tension,
            0.3,
            places=2,
        )


class TestDocumentProtectorCombined(unittest.TestCase):
    def test_all_protections_active(self):
        protector = DegradationDocumentProtector()
        existing = _make_existing_facts(1)
        outline = _make_chapter_outline(3)
        delta = _make_delta(
            new_facts=[
                NewFact(source="local", content="已有事实0"),
                NewFact(source="cloud", content="已有事实0"),
                NewFact(source="local", content="全新事实"),
            ],
            chapter_update=ChapterUpdate(
                current_beat_progress=0.5,
                new_beat_suggested={"name": "new"},
                constraints_removed=["c1"],
            ),
            next_prediction=NextPrediction(
                likely_next_scenes=[{"scene_id": "s1", "probability": 0.9}],
                narrative_tension=0.7,
                suggested_pace="normal",
            ),
        )
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=existing,
            current_chapter_outline=outline,
            is_degraded=True,
        )
        self.assertEqual(len(protected.new_facts), 2)
        self.assertEqual(report.fact_overwrites_blocked, 1)
        self.assertTrue(report.beat_reduction_blocked)
        self.assertTrue(report.confidence_decay_applied)
        self.assertEqual(len(report.reasons), 3)

    def test_preserves_other_delta_fields(self):
        protector = DegradationDocumentProtector()
        delta = NarrativeDelta(
            version=5,
            new_facts=[],
            chapter_update=None,
            next_prediction=None,
            open_questions_added=["问题1"],
            open_questions_resolved=["问题0"],
            narrative_note="备注",
        )
        protected, report = protector.safe_apply_delta(
            delta=delta,
            existing_facts=[],
            current_chapter_outline=None,
            is_degraded=True,
        )
        self.assertEqual(protected.version, 5)
        self.assertEqual(protected.open_questions_added, ["问题1"])
        self.assertEqual(protected.open_questions_resolved, ["问题0"])
        self.assertEqual(protected.narrative_note, "备注")


if __name__ == "__main__":
    unittest.main()
