from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from luqi_engine.training.data_store import TrainingDataStore, StoreStats
from luqi_engine.core.types import (
    TrainingSample,
    SampleQuality,
    TrainingInput,
    FinalOutput,
    AgentOutputs,
    AlgorithmCorrections,
    CorrectionRecord,
    NarrativeDelta,
    CanonicalIR,
    CriticVerdict,
    AtmosphereOutput,
    EmotionDelta,
)
from luqi_engine.core.config import TrainingConfig


def _make_sample(
    sample_id: str = "sample_test001",
    character_id: str = "char_test",
    usage_tags: list = None,
    grade: str = "gold",
) -> TrainingSample:
    return TrainingSample(
        sample_id=sample_id,
        character_id=character_id,
        timestamp=1000.0,
        narrative_version=1,
        input=TrainingInput(
            narrative_summary="测试摘要",
            user_message="你好",
        ),
        quality=SampleQuality(
            overall_score=0.9,
            coherence_score=0.9,
            character_faithfulness=0.9,
            narrative_alignment=0.9,
            grade=grade,
        ),
        final_output=FinalOutput(
            reply_text="你好！",
            executed_action="wave",
            dialogue_source="original",
            voice_renderer_used=False,
            narrative_version_after=1,
        ),
        usage_tags=usage_tags or ["layer1_narrative", "layer2_decision"],
    )


class TestTrainingDataStoreBasic(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="training_store_test_")
        self._config = TrainingConfig(storage_path=self._tmpdir)
        self._store = TrainingDataStore(config=self._config)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_store_creates_files(self):
        sample = _make_sample()
        path = self._store.store(sample)
        self.assertTrue(os.path.isfile(path))

    def test_store_rejects_empty_character_id(self):
        sample = _make_sample(character_id="")
        with self.assertRaises(ValueError):
            self._store.store(sample)

    def test_store_rejects_empty_sample_id(self):
        sample = _make_sample(sample_id="")
        with self.assertRaises(ValueError):
            self._store.store(sample)

    def test_list_samples_empty(self):
        ids = self._store.list_samples("char_nonexist")
        self.assertEqual(ids, [])

    def test_list_samples_after_store(self):
        sample = _make_sample()
        self._store.store(sample)
        ids = self._store.list_samples("char_test")
        self.assertIn("sample_test001", ids)

    def test_list_samples_by_layer(self):
        sample = _make_sample(usage_tags=["layer1_narrative"])
        self._store.store(sample)
        ids_layer1 = self._store.list_samples("char_test", layer=1)
        self.assertIn("sample_test001", ids_layer1)
        ids_layer2 = self._store.list_samples("char_test", layer=2)
        self.assertEqual(ids_layer2, [])

    def test_get_sample(self):
        sample = _make_sample()
        self._store.store(sample)
        retrieved = self._store.get_sample("char_test", "sample_test001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.sample_id, "sample_test001")
        self.assertEqual(retrieved.character_id, "char_test")

    def test_get_sample_by_layer(self):
        sample = _make_sample(usage_tags=["layer1_narrative"])
        self._store.store(sample)
        retrieved = self._store.get_sample("char_test", "sample_test001", layer=1)
        self.assertIsNotNone(retrieved)

    def test_get_sample_nonexist(self):
        retrieved = self._store.get_sample("char_test", "nonexist_id")
        self.assertIsNone(retrieved)


class TestTrainingDataStoreIsolation(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="training_iso_test_")
        self._config = TrainingConfig(storage_path=self._tmpdir)
        self._store = TrainingDataStore(config=self._config)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_character_isolation_directories(self):
        sample_a = _make_sample(sample_id="s_a", character_id="char_a")
        sample_b = _make_sample(sample_id="s_b", character_id="char_b")
        self._store.store(sample_a)
        self._store.store(sample_b)
        dir_a = os.path.join(self._tmpdir, "char_a")
        dir_b = os.path.join(self._tmpdir, "char_b")
        self.assertTrue(os.path.isdir(dir_a))
        self.assertTrue(os.path.isdir(dir_b))

    def test_character_isolation_no_cross_access(self):
        sample_a = _make_sample(sample_id="s_a", character_id="char_a")
        self._store.store(sample_a)
        retrieved_from_b = self._store.get_sample("char_b", "s_a")
        self.assertIsNone(retrieved_from_b)

    def test_list_samples_per_character(self):
        for i in range(3):
            self._store.store(
                _make_sample(sample_id=f"s_a_{i}", character_id="char_a")
            )
        for i in range(2):
            self._store.store(
                _make_sample(sample_id=f"s_b_{i}", character_id="char_b")
            )
        ids_a = self._store.list_samples("char_a")
        ids_b = self._store.list_samples("char_b")
        self.assertEqual(len(ids_a), 3)
        self.assertEqual(len(ids_b), 2)


class TestTrainingDataStoreStats(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="training_stats_test_")
        self._config = TrainingConfig(storage_path=self._tmpdir)
        self._store = TrainingDataStore(config=self._config)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_stats_empty(self):
        stats = self._store.get_stats()
        self.assertEqual(stats.total_samples, 0)

    def test_stats_after_store(self):
        self._store.store(_make_sample(sample_id="s1", grade="gold"))
        self._store.store(_make_sample(sample_id="s2", grade="silver"))
        stats = self._store.get_stats(character_id="char_test")
        self.assertEqual(stats.total_samples, 2)
        self.assertIn("char_test", stats.samples_by_character)
        self.assertEqual(stats.samples_by_character["char_test"], 2)

    def test_stats_storage_bytes(self):
        self._store.store(_make_sample())
        stats = self._store.get_stats(character_id="char_test")
        self.assertGreater(stats.storage_bytes, 0)


class TestTrainingDataStoreMaxSamples(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="training_max_test_")
        self._config = TrainingConfig(
            storage_path=self._tmpdir,
            max_samples_per_character=3,
        )
        self._store = TrainingDataStore(config=self._config)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_max_samples_enforced(self):
        for i in range(5):
            self._store.store(
                _make_sample(sample_id=f"s_{i:03d}", character_id="char_limited")
            )
        ids = self._store.list_samples("char_limited")
        self.assertLessEqual(len(ids), 3)


class TestTrainingDataStoreMultiLayer(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="training_multi_test_")
        self._config = TrainingConfig(storage_path=self._tmpdir)
        self._store = TrainingDataStore(config=self._config)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_multi_layer_storage(self):
        sample = _make_sample(
            usage_tags=["layer1_narrative", "layer4_critic", "layer5_atmosphere"]
        )
        self._store.store(sample)
        ids_l1 = self._store.list_samples("char_test", layer=1)
        ids_l4 = self._store.list_samples("char_test", layer=4)
        ids_l5 = self._store.list_samples("char_test", layer=5)
        self.assertIn("sample_test001", ids_l1)
        self.assertIn("sample_test001", ids_l4)
        self.assertIn("sample_test001", ids_l5)

    def test_file_structure(self):
        sample = _make_sample(usage_tags=["layer2_decision"])
        self._store.store(sample)
        expected_dir = os.path.join(self._tmpdir, "char_test", "layer2")
        self.assertTrue(os.path.isdir(expected_dir))
        files = os.listdir(expected_dir)
        self.assertTrue(any(f.endswith(".json") for f in files))


class TestTrainingDataStoreRoundTrip(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="training_roundtrip_test_")
        self._config = TrainingConfig(storage_path=self._tmpdir)
        self._store = TrainingDataStore(config=self._config)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_round_trip_basic_fields(self):
        sample = _make_sample()
        self._store.store(sample)
        retrieved = self._store.get_sample("char_test", "sample_test001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.sample_id, sample.sample_id)
        self.assertEqual(retrieved.character_id, sample.character_id)
        self.assertEqual(retrieved.timestamp, sample.timestamp)
        self.assertEqual(retrieved.narrative_version, sample.narrative_version)
        self.assertEqual(retrieved.usage_tags, sample.usage_tags)

    def test_round_trip_input_fields(self):
        sample = _make_sample()
        self._store.store(sample)
        retrieved = self._store.get_sample("char_test", "sample_test001")
        self.assertIsNotNone(retrieved)
        self.assertIsNotNone(retrieved.input)
        self.assertEqual(retrieved.input.narrative_summary, "测试摘要")
        self.assertEqual(retrieved.input.user_message, "你好")

    def test_round_trip_quality_fields(self):
        sample = _make_sample()
        self._store.store(sample)
        retrieved = self._store.get_sample("char_test", "sample_test001")
        self.assertIsNotNone(retrieved)
        self.assertIsNotNone(retrieved.quality)
        self.assertEqual(retrieved.quality.overall_score, 0.9)
        self.assertEqual(retrieved.quality.grade, "gold")

    def test_round_trip_final_output_fields(self):
        sample = _make_sample()
        self._store.store(sample)
        retrieved = self._store.get_sample("char_test", "sample_test001")
        self.assertIsNotNone(retrieved)
        self.assertIsNotNone(retrieved.final_output)
        self.assertEqual(retrieved.final_output.reply_text, "你好！")
        self.assertEqual(retrieved.final_output.narrative_version_after, 1)

    def test_round_trip_agent_outputs(self):
        agent_outputs = AgentOutputs(
            novel=NarrativeDelta(version=2),
            dialogue=CanonicalIR(intent="greet", confidence=0.9),
            critic=CriticVerdict(verdict="accept", overall_confidence=0.95),
            atmosphere=AtmosphereOutput(mode="light"),
            novel_token_usage=100,
            dialogue_token_usage=200,
            critic_token_usage=50,
            atmosphere_token_usage=80,
            total_latency_ms=430,
        )
        sample = TrainingSample(
            sample_id="sample_rt_ao",
            character_id="char_rt",
            timestamp=1000.0,
            narrative_version=2,
            input=TrainingInput(narrative_summary="测试", user_message="你好"),
            agent_outputs=agent_outputs,
            final_output=FinalOutput(reply_text="你好！", narrative_version_after=2),
            quality=SampleQuality(overall_score=0.9, grade="gold"),
            usage_tags=["layer1_narrative"],
        )
        self._store.store(sample)
        retrieved = self._store.get_sample("char_rt", "sample_rt_ao")
        self.assertIsNotNone(retrieved)
        self.assertIsNotNone(retrieved.agent_outputs)
        self.assertIsNotNone(retrieved.agent_outputs.novel)
        self.assertEqual(retrieved.agent_outputs.novel.version, 2)
        self.assertIsNotNone(retrieved.agent_outputs.dialogue)
        self.assertEqual(retrieved.agent_outputs.dialogue.intent, "greet")
        self.assertAlmostEqual(retrieved.agent_outputs.dialogue.confidence, 0.9)
        self.assertIsNotNone(retrieved.agent_outputs.critic)
        self.assertEqual(retrieved.agent_outputs.critic.verdict, "accept")
        self.assertIsNotNone(retrieved.agent_outputs.atmosphere)
        self.assertEqual(retrieved.agent_outputs.atmosphere.mode, "light")
        self.assertEqual(retrieved.agent_outputs.novel_token_usage, 100)
        self.assertEqual(retrieved.agent_outputs.dialogue_token_usage, 200)
        self.assertEqual(retrieved.agent_outputs.total_latency_ms, 430)

    def test_round_trip_algorithm_corrections(self):
        algorithm_corrections = AlgorithmCorrections(
            dialogue_corrections=[
                CorrectionRecord(
                    field="emotion",
                    original_value="anger",
                    corrected_value="neutral",
                    reason="out of range",
                    severity="clamp",
                ),
            ],
            novel_corrections=[
                CorrectionRecord(
                    field="narrative_note",
                    reason="inconsistent",
                    severity="override",
                ),
            ],
        )
        sample = TrainingSample(
            sample_id="sample_rt_ac",
            character_id="char_rt",
            timestamp=1000.0,
            narrative_version=1,
            input=TrainingInput(narrative_summary="测试", user_message="你好"),
            algorithm_corrections=algorithm_corrections,
            final_output=FinalOutput(reply_text="你好！", narrative_version_after=1),
            quality=SampleQuality(overall_score=0.7, grade="silver"),
            usage_tags=["layer1_narrative"],
        )
        self._store.store(sample)
        retrieved = self._store.get_sample("char_rt", "sample_rt_ac")
        self.assertIsNotNone(retrieved)
        self.assertIsNotNone(retrieved.algorithm_corrections)
        self.assertEqual(len(retrieved.algorithm_corrections.dialogue_corrections), 1)
        dc = retrieved.algorithm_corrections.dialogue_corrections[0]
        self.assertEqual(dc.field, "emotion")
        self.assertEqual(dc.original_value, "anger")
        self.assertEqual(dc.corrected_value, "neutral")
        self.assertEqual(dc.reason, "out of range")
        self.assertEqual(dc.severity, "clamp")
        self.assertEqual(len(retrieved.algorithm_corrections.novel_corrections), 1)
        nc = retrieved.algorithm_corrections.novel_corrections[0]
        self.assertEqual(nc.field, "narrative_note")
        self.assertEqual(nc.severity, "override")

    def test_round_trip_full_sample(self):
        agent_outputs = AgentOutputs(
            novel=NarrativeDelta(version=3),
            dialogue=CanonicalIR(
                intent="question",
                confidence=0.85,
                emotion_delta=EmotionDelta(pleasure=0.3, arousal=0.1),
                action="think",
            ),
            critic=CriticVerdict(verdict="accept", overall_confidence=0.9),
            atmosphere=AtmosphereOutput(mode="full"),
            novel_token_usage=150,
            total_latency_ms=500,
        )
        algorithm_corrections = AlgorithmCorrections(
            dialogue_corrections=[
                CorrectionRecord(field="tone", severity="clamp", reason="too casual"),
            ],
            novel_corrections=[],
        )
        sample = TrainingSample(
            sample_id="sample_rt_full",
            character_id="char_full",
            timestamp=2000.0,
            narrative_version=3,
            input=TrainingInput(
                narrative_summary="完整测试",
                user_message="为什么？",
                chapter_context="第二章",
            ),
            agent_outputs=agent_outputs,
            algorithm_corrections=algorithm_corrections,
            final_output=FinalOutput(
                reply_text="因为...",
                executed_action="think",
                narrative_version_after=3,
                voice_renderer_used=True,
            ),
            quality=SampleQuality(
                overall_score=0.85,
                coherence_score=0.9,
                character_faithfulness=0.8,
                narrative_alignment=0.85,
                grade="gold",
            ),
            usage_tags=["layer1_narrative", "layer2_decision", "layer3_voice"],
        )
        self._store.store(sample)
        retrieved = self._store.get_sample("char_full", "sample_rt_full")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.sample_id, "sample_rt_full")
        self.assertEqual(retrieved.narrative_version, 3)
        self.assertIsNotNone(retrieved.input)
        self.assertEqual(retrieved.input.narrative_summary, "完整测试")
        self.assertIsNotNone(retrieved.agent_outputs)
        self.assertEqual(retrieved.agent_outputs.novel.version, 3)
        self.assertEqual(retrieved.agent_outputs.dialogue.intent, "question")
        self.assertIsNotNone(retrieved.agent_outputs.dialogue.emotion_delta)
        self.assertAlmostEqual(
            retrieved.agent_outputs.dialogue.emotion_delta.pleasure, 0.3
        )
        self.assertIsNotNone(retrieved.algorithm_corrections)
        self.assertEqual(
            len(retrieved.algorithm_corrections.dialogue_corrections), 1
        )
        self.assertIsNotNone(retrieved.final_output)
        self.assertTrue(retrieved.final_output.voice_renderer_used)
        self.assertIsNotNone(retrieved.quality)
        self.assertEqual(retrieved.quality.grade, "gold")

    def test_round_trip_without_agent_outputs(self):
        sample = _make_sample()
        self._store.store(sample)
        retrieved = self._store.get_sample("char_test", "sample_test001")
        self.assertIsNotNone(retrieved)
        self.assertIsNone(retrieved.agent_outputs)
        self.assertIsNone(retrieved.algorithm_corrections)


if __name__ == "__main__":
    unittest.main()
