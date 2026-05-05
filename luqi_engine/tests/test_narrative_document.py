"""叙事文档测试"""

import pytest

from luqi_engine.core.types import (
    Fact, NewFact, ChapterOutline, StoryBeat, ScenePrediction,
    NarrativeDelta, ChapterUpdate, NextPrediction,
)
from luqi_engine.narrative.document import NarrativeDocument


@pytest.fixture
def empty_doc():
    return NarrativeDocument(document_id="doc_001", world_id="world_alpha")


@pytest.fixture
def doc_with_facts(empty_doc):
    empty_doc.established_facts = [
        Fact(
            id="fact_001",
            sequence_number=1,
            timestamp="tick_1",
            source="user",
            content="主角到达了王城",
            participants=["主角"],
        ),
        Fact(
            id="fact_002",
            sequence_number=2,
            timestamp="tick_2",
            source="novel",
            content="主角不喜欢雨天",
            participants=["主角"],
        ),
    ]
    empty_doc.version = 2
    return empty_doc


@pytest.fixture
def doc_with_outline(empty_doc):
    empty_doc.current_chapter_outline = ChapterOutline(
        chapter_id=1,
        title="初入王城",
        arc_summary="主角首次进入王城",
        beats=[
            StoryBeat(
                name="入城",
                description="主角穿过城门进入王城",
                expected_participants=["主角"],
                status="completed",
                progress=1.0,
            ),
            StoryBeat(
                name="遭遇守卫",
                description="主角在城门口被守卫拦下",
                expected_participants=["主角", "守卫"],
                status="active",
                progress=0.3,
            ),
        ],
        current_beat_index=1,
    )
    return empty_doc


class TestNarrativeDocumentCreation:
    def test_create_empty_document(self, empty_doc):
        assert empty_doc.document_id == "doc_001"
        assert empty_doc.world_id == "world_alpha"
        assert empty_doc.version == 0
        assert empty_doc.created_at == 0.0
        assert empty_doc.last_updated == 0.0
        assert empty_doc.current_chapter == 1
        assert empty_doc.current_scene == ""
        assert empty_doc.timeline_position == 0.0
        assert empty_doc.narrative_tick == 0
        assert empty_doc.established_facts == []
        assert empty_doc.current_chapter_outline is None
        assert empty_doc.next_scene_predictions == []
        assert empty_doc.active_prediction is None
        assert empty_doc.pending_absorptions == []
        assert empty_doc.open_questions == []
        assert empty_doc.resolved_questions == []
        assert empty_doc.pace_state is None
        assert empty_doc.auto_mode_config is None
        assert empty_doc.prose_draft is None
        assert empty_doc.scene_descriptions == {}
        assert empty_doc.dialogue_transcripts == []

    def test_default_factory_isolation(self):
        doc_a = NarrativeDocument()
        doc_b = NarrativeDocument()
        doc_a.established_facts.append(
            Fact(id="x", sequence_number=1, timestamp="t", source="s", content="c", participants=[])
        )
        assert len(doc_b.established_facts) == 0


class TestApplyDeltaVersion:
    def test_apply_delta_increments_version(self, empty_doc):
        delta = NarrativeDelta()
        empty_doc.apply_delta(delta)
        assert empty_doc.version == 1

    def test_apply_delta_increments_tick(self, empty_doc):
        delta = NarrativeDelta()
        empty_doc.apply_delta(delta)
        assert empty_doc.narrative_tick == 1

    def test_apply_delta_updates_timestamp(self, empty_doc):
        delta = NarrativeDelta()
        empty_doc.apply_delta(delta)
        assert empty_doc.last_updated > 0.0

    def test_multiple_deltas_increment_version(self, empty_doc):
        for _ in range(5):
            empty_doc.apply_delta(NarrativeDelta())
        assert empty_doc.version == 5
        assert empty_doc.narrative_tick == 5


class TestApplyDeltaFacts:
    def test_apply_delta_appends_new_facts(self, empty_doc):
        delta = NarrativeDelta(
            new_facts=[
                NewFact(
                    source="user",
                    content="主角到达了王城",
                    participants=["主角"],
                ),
            ],
        )
        empty_doc.apply_delta(delta)
        assert len(empty_doc.established_facts) == 1
        assert empty_doc.established_facts[0].content == "主角到达了王城"
        assert empty_doc.established_facts[0].source == "user"
        assert empty_doc.established_facts[0].sequence_number == 1

    def test_apply_delta_auto_generates_fact_id(self, empty_doc):
        delta = NarrativeDelta(
            new_facts=[
                NewFact(source="novel", content="事件A", participants=[]),
                NewFact(source="novel", content="事件B", participants=[]),
            ],
        )
        empty_doc.apply_delta(delta)
        assert empty_doc.established_facts[0].id == "fact_001"
        assert empty_doc.established_facts[1].id == "fact_002"

    def test_apply_delta_preserves_explicit_fact_id(self, empty_doc):
        delta = NarrativeDelta(
            new_facts=[
                NewFact(id="custom_id", source="novel", content="事件", participants=[]),
            ],
        )
        empty_doc.apply_delta(delta)
        assert empty_doc.established_facts[0].id == "custom_id"

    def test_apply_delta_auto_generates_timestamp(self, empty_doc):
        delta = NarrativeDelta(
            new_facts=[
                NewFact(source="novel", content="事件", participants=[]),
            ],
        )
        empty_doc.apply_delta(delta)
        assert empty_doc.established_facts[0].timestamp == "tick_1"

    def test_apply_delta_preserves_explicit_timestamp(self, empty_doc):
        delta = NarrativeDelta(
            new_facts=[
                NewFact(source="novel", content="事件", participants=[], timestamp="custom_ts"),
            ],
        )
        empty_doc.apply_delta(delta)
        assert empty_doc.established_facts[0].timestamp == "custom_ts"

    def test_apply_delta_copies_emotional_valence_and_tags(self, empty_doc):
        delta = NarrativeDelta(
            new_facts=[
                NewFact(
                    source="novel",
                    content="感人场景",
                    participants=["主角"],
                    emotional_valence=0.8,
                    tags=["情感", "关键"],
                ),
            ],
        )
        empty_doc.apply_delta(delta)
        fact = empty_doc.established_facts[0]
        assert fact.emotional_valence == 0.8
        assert fact.tags == ["情感", "关键"]


class TestApplyDeltaPredictions:
    def test_apply_delta_updates_predictions(self, empty_doc):
        delta = NarrativeDelta(
            next_prediction=NextPrediction(
                likely_next_scenes=[
                    {
                        "scene_id": "scene_01",
                        "scene_name": "王城广场",
                        "probability": 0.7,
                        "description": "主角前往广场",
                        "expected_participants": ["主角"],
                        "estimated_tension": 0.3,
                    },
                    {
                        "scene_id": "scene_02",
                        "scene_name": "暗巷",
                        "probability": 0.3,
                        "description": "主角进入暗巷",
                        "expected_participants": ["主角", "神秘人"],
                        "estimated_tension": 0.8,
                    },
                ],
                narrative_tension=0.5,
            ),
        )
        empty_doc.apply_delta(delta)
        assert len(empty_doc.next_scene_predictions) == 2
        assert empty_doc.next_scene_predictions[0].scene_name == "王城广场"
        assert empty_doc.next_scene_predictions[0].probability == 0.7
        assert empty_doc.next_scene_predictions[1].scene_name == "暗巷"

    def test_apply_delta_replaces_predictions(self, empty_doc):
        delta1 = NarrativeDelta(
            next_prediction=NextPrediction(
                likely_next_scenes=[
                    {"scene_id": "s1", "scene_name": "场景A", "probability": 0.6},
                ],
            ),
        )
        delta2 = NarrativeDelta(
            next_prediction=NextPrediction(
                likely_next_scenes=[
                    {"scene_id": "s2", "scene_name": "场景B", "probability": 0.9},
                ],
            ),
        )
        empty_doc.apply_delta(delta1)
        empty_doc.apply_delta(delta2)
        assert len(empty_doc.next_scene_predictions) == 1
        assert empty_doc.next_scene_predictions[0].scene_name == "场景B"

    def test_apply_delta_no_prediction_leaves_unchanged(self, empty_doc):
        empty_doc.next_scene_predictions = [
            ScenePrediction(scene_id="s1", scene_name="旧场景", probability=0.5),
        ]
        empty_doc.apply_delta(NarrativeDelta())
        assert len(empty_doc.next_scene_predictions) == 1
        assert empty_doc.next_scene_predictions[0].scene_name == "旧场景"


class TestApplyDeltaQuestions:
    def test_apply_delta_adds_open_questions(self, empty_doc):
        delta = NarrativeDelta(
            open_questions_added=["谁是幕后黑手？", "宝剑在哪里？"],
        )
        empty_doc.apply_delta(delta)
        assert "谁是幕后黑手？" in empty_doc.open_questions
        assert "宝剑在哪里？" in empty_doc.open_questions

    def test_apply_delta_resolves_questions(self, empty_doc):
        empty_doc.open_questions = ["谁是幕后黑手？", "宝剑在哪里？"]
        delta = NarrativeDelta(
            open_questions_resolved=["谁是幕后黑手？"],
        )
        empty_doc.apply_delta(delta)
        assert "谁是幕后黑手？" not in empty_doc.open_questions
        assert "谁是幕后黑手？" in empty_doc.resolved_questions
        assert "宝剑在哪里？" in empty_doc.open_questions

    def test_apply_delta_resolve_nonexistent_question(self, empty_doc):
        empty_doc.open_questions = ["问题A"]
        delta = NarrativeDelta(
            open_questions_resolved=["不存在的问题"],
        )
        empty_doc.apply_delta(delta)
        assert "不存在的问题" in empty_doc.resolved_questions
        assert len(empty_doc.open_questions) == 1


class TestApplyDeltaChapterUpdate:
    def test_apply_chapter_update_beat_progress(self, doc_with_outline):
        delta = NarrativeDelta(
            chapter_update=ChapterUpdate(current_beat_progress=0.7),
        )
        doc_with_outline.apply_delta(delta)
        assert doc_with_outline.current_chapter_outline.beats[1].progress == 0.7

    def test_apply_chapter_update_no_outline(self, empty_doc):
        delta = NarrativeDelta(
            chapter_update=ChapterUpdate(current_beat_progress=0.5),
        )
        empty_doc.apply_delta(delta)
        assert empty_doc.current_chapter_outline is None

    def test_apply_chapter_update_zero_progress(self, doc_with_outline):
        original_progress = doc_with_outline.current_chapter_outline.beats[1].progress
        delta = NarrativeDelta(
            chapter_update=ChapterUpdate(current_beat_progress=0.0),
        )
        doc_with_outline.apply_delta(delta)
        assert doc_with_outline.current_chapter_outline.beats[1].progress == original_progress


class TestToPromptContext:
    def test_standard_mode(self, doc_with_facts):
        context = doc_with_facts.to_prompt_context("standard")
        assert "[叙事文档 v2]" in context
        assert "当前章节: 第1章" in context
        assert "[最近事实]" in context
        assert "主角到达了王城" in context

    def test_compact_mode(self, doc_with_facts):
        context = doc_with_facts.to_prompt_context("compact")
        assert "[叙事文档" not in context
        assert "[最近事实]" in context

    def test_detailed_mode(self, doc_with_facts):
        context = doc_with_facts.to_prompt_context("detailed")
        assert "[叙事文档 v2]" in context
        assert "[最近事实]" in context

    def test_prose_mode_with_draft(self, doc_with_facts):
        doc_with_facts.prose_draft = "夜色笼罩着王城，主角独自走在空旷的街道上。" * 20
        context = doc_with_facts.to_prompt_context("prose")
        assert "[小说草稿]" in context
        assert "夜色笼罩着王城" in context

    def test_prose_mode_without_draft(self, doc_with_facts):
        context = doc_with_facts.to_prompt_context("prose")
        assert "[小说草稿]" not in context

    def test_shows_chapter_outline(self, doc_with_outline):
        context = doc_with_outline.to_prompt_context("standard")
        assert "[章节大纲] 初入王城" in context
        assert "○ 入城" in context
        assert "● 遭遇守卫" in context

    def test_compact_hides_chapter_outline(self, doc_with_outline):
        context = doc_with_outline.to_prompt_context("compact")
        assert "[章节大纲]" not in context

    def test_shows_predictions(self, empty_doc):
        empty_doc.next_scene_predictions = [
            ScenePrediction(scene_id="s1", scene_name="广场", probability=0.7),
            ScenePrediction(scene_id="s2", scene_name="暗巷", probability=0.3),
        ]
        context = empty_doc.to_prompt_context("standard")
        assert "[场景预测]" in context
        assert "广场" in context
        assert "概率:70%" in context

    def test_compact_hides_predictions(self, empty_doc):
        empty_doc.next_scene_predictions = [
            ScenePrediction(scene_id="s1", scene_name="广场", probability=0.7),
        ]
        context = empty_doc.to_prompt_context("compact")
        assert "[场景预测]" not in context

    def test_shows_open_questions_in_detailed(self, empty_doc):
        empty_doc.open_questions = ["谁是幕后黑手？", "宝剑在哪里？"]
        context = empty_doc.to_prompt_context("detailed")
        assert "[未解问题]" in context
        assert "谁是幕后黑手？" in context

    def test_standard_hides_open_questions(self, empty_doc):
        empty_doc.open_questions = ["谁是幕后黑手？"]
        context = empty_doc.to_prompt_context("standard")
        assert "[未解问题]" not in context

    def test_empty_doc_standard_mode(self, empty_doc):
        context = empty_doc.to_prompt_context("standard")
        assert "[叙事文档 v0]" in context
        assert "当前章节: 第1章" in context

    def test_empty_doc_compact_mode(self, empty_doc):
        context = empty_doc.to_prompt_context("compact")
        assert "[最近事实]" not in context

    def test_timeline_position_formatting(self, empty_doc):
        empty_doc.timeline_position = 0.65
        context = empty_doc.to_prompt_context("standard")
        assert "65%" in context


class TestFindConflictingFact:
    def test_detect_chinese_negation_conflict(self, doc_with_facts):
        new_fact = NewFact(
            source="novel",
            content="主角喜欢雨天",
            participants=["主角"],
        )
        result = doc_with_facts.find_conflicting_fact(new_fact)
        assert result is not None
        assert result.id == "fact_002"

    def test_no_conflict_for_compatible_facts(self, doc_with_facts):
        new_fact = NewFact(
            source="novel",
            content="主角遇到了朋友",
            participants=["主角"],
        )
        result = doc_with_facts.find_conflicting_fact(new_fact)
        assert result is None

    def test_skips_retracted_facts(self, doc_with_facts):
        doc_with_facts.established_facts[1].is_retracted = True
        new_fact = NewFact(
            source="novel",
            content="主角喜欢雨天",
            participants=["主角"],
        )
        result = doc_with_facts.find_conflicting_fact(new_fact)
        assert result is None

    def test_accepts_dict_input(self, doc_with_facts):
        new_fact = {"content": "主角喜欢雨天"}
        result = doc_with_facts.find_conflicting_fact(new_fact)
        assert result is not None

    def test_returns_none_for_empty_content(self, doc_with_facts):
        new_fact = NewFact(source="novel", content="", participants=[])
        result = doc_with_facts.find_conflicting_fact(new_fact)
        assert result is None

    def test_english_negation_conflict(self, empty_doc):
        empty_doc.established_facts = [
            Fact(
                id="fact_001",
                sequence_number=1,
                timestamp="tick_1",
                source="novel",
                content="The hero is not brave",
                participants=["hero"],
            ),
        ]
        new_fact = NewFact(
            source="novel",
            content="The hero is brave",
            participants=["hero"],
        )
        result = empty_doc.find_conflicting_fact(new_fact)
        assert result is not None


class TestHasNegationConflict:
    def test_chinese_negation_conflict(self):
        assert NarrativeDocument._has_negation_conflict(
            "主角不喜欢雨天", "主角喜欢雨天"
        )

    def test_no_conflict_both_negated(self):
        assert not NarrativeDocument._has_negation_conflict(
            "主角不喜欢雨天", "主角不喜欢晴天"
        )

    def test_no_conflict_unrelated(self):
        assert not NarrativeDocument._has_negation_conflict(
            "主角到达了王城", "守卫拦住了主角"
        )

    def test_english_not_conflict(self):
        assert NarrativeDocument._has_negation_conflict(
            "the hero is not brave", "the hero is brave"
        )

    def test_english_never_conflict(self):
        assert NarrativeDocument._has_negation_conflict(
            "he never returned", "he returned"
        )

    def test_no_conflict_same_negation(self):
        assert not NarrativeDocument._has_negation_conflict(
            "主角不喜欢雨天", "主角不喜欢雨天"
        )

    def test_empty_strings(self):
        assert not NarrativeDocument._has_negation_conflict("", "")

    def test_single_negation_no_core_overlap(self):
        assert not NarrativeDocument._has_negation_conflict(
            "主角不喜欢雨天", "天气非常好"
        )
