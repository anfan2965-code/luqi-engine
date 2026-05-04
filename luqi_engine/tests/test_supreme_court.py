from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from luqi_engine.core.types import (
    CanonicalIR, EmotionDelta, NarrativeDelta,
    NewFact, ValidatedIR, ValidatedDelta, Violation,
)
from luqi_engine.core.supreme_court import (
    AlgorithmSupremeCourt,
)
from luqi_engine.core.constants import _MAX_TIME_SKIP_PER_TURN


@dataclass
class _MockPersonality:
    scores: Dict[str, float]

    def get_score(self, trait: str) -> float:
        return self.scores.get(trait, 50.0)


@dataclass
class _MockEmotion:
    pleasure: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0


@dataclass
class _MockCharacter:
    personality: _MockPersonality
    emotion: _MockEmotion


@dataclass
class _MockConflictingFact:
    id: str


@dataclass
class _MockNarrative:
    established_facts: List[Any]

    def find_conflicting_fact(self, new_fact: Any) -> Optional[_MockConflictingFact]:
        for fact in self.established_facts:
            if hasattr(fact, 'content') and fact.content == new_fact.content:
                return _MockConflictingFact(id="conflict_001")
        return None


class TestAlgorithmSupremeCourtCleanIR:
    def test_clean_ir_no_violations(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            intent="greet",
            action="smile_nod",
            emotion_delta=EmotionDelta(pleasure=0.1, arousal=0.05, dominance=0.0),
            key_points=["你好"],
            tone="casual",
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(pleasure=0.0, arousal=0.0, dominance=0.0),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        assert result.is_clean is True
        assert len(result.violations) == 0
        assert result.needs_critic_review is False

    def test_clean_ir_preserves_values(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            intent="greet",
            action="smile_nod",
            emotion_delta=EmotionDelta(pleasure=0.1, arousal=0.05, dominance=0.0),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        assert result.ir is not ir
        assert result.ir.intent == ir.intent
        assert result.ir.action == ir.action
        assert result.ir.emotion_delta.pleasure == ir.emotion_delta.pleasure
        assert result.ir.emotion_delta.arousal == ir.emotion_delta.arousal
        assert result.ir.emotion_delta.dominance == ir.emotion_delta.dominance


class TestAlgorithmSupremeCourtEmotionRange:
    def test_arousal_within_range_no_violation(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(arousal=0.4),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        emotion_violations = [v for v in result.violations if v.type == "emotion_out_of_range"]
        assert len(emotion_violations) == 0

    def test_arousal_exceeds_range_triggers_violation(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(arousal=0.8),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 20.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        emotion_violations = [v for v in result.violations if v.type == "emotion_out_of_range"]
        assert len(emotion_violations) == 1
        assert emotion_violations[0].level == "hard"
        assert emotion_violations[0].original == 0.8

    def test_high_neuroticism_allows_larger_arousal(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(arousal=0.6),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 80.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        emotion_violations = [v for v in result.violations if v.type == "emotion_out_of_range"]
        assert len(emotion_violations) == 0

    def test_forced_arousal_is_clamped(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(arousal=1.0),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 0.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        emotion_violations = [v for v in result.violations if v.type == "emotion_out_of_range"]
        assert len(emotion_violations) == 1
        assert emotion_violations[0].forced == pytest.approx(0.3, abs=1e-9)

    def test_arousal_correction_applied_to_ir(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(arousal=1.0),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 0.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        assert result.ir.emotion_delta.arousal == pytest.approx(0.3, abs=1e-9)
        assert ir.emotion_delta.arousal == 1.0

    def test_pleasure_within_range_no_violation(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(pleasure=0.5),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        pleasure_violations = [
            v for v in result.violations
            if v.type == "emotion_out_of_range" and "pleasure" in v.field
        ]
        assert len(pleasure_violations) == 0

    def test_pleasure_exceeds_range_triggers_violation(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(pleasure=1.5),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        pleasure_violations = [
            v for v in result.violations
            if v.type == "emotion_out_of_range" and "pleasure" in v.field
        ]
        assert len(pleasure_violations) == 1
        assert pleasure_violations[0].level == "hard"
        assert pleasure_violations[0].original == 1.5

    def test_pleasure_correction_applied_to_ir(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(pleasure=-2.0),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        assert result.ir.emotion_delta.pleasure == pytest.approx(-1.0, abs=1e-9)
        assert ir.emotion_delta.pleasure == -2.0

    def test_dominance_within_range_no_violation(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(dominance=-0.8),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        dominance_violations = [
            v for v in result.violations
            if v.type == "emotion_out_of_range" and "dominance" in v.field
        ]
        assert len(dominance_violations) == 0

    def test_dominance_exceeds_range_triggers_violation(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(dominance=1.5),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        dominance_violations = [
            v for v in result.violations
            if v.type == "emotion_out_of_range" and "dominance" in v.field
        ]
        assert len(dominance_violations) == 1
        assert dominance_violations[0].level == "hard"
        assert dominance_violations[0].original == 1.5

    def test_dominance_correction_applied_to_ir(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(dominance=2.5),
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        assert result.ir.emotion_delta.dominance == pytest.approx(1.0, abs=1e-9)
        assert ir.emotion_delta.dominance == 2.5


class TestAlgorithmSupremeCourtActionEmpty:
    def test_empty_action_triggers_violation(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(action="")
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        action_violations = [v for v in result.violations if v.type == "action_empty"]
        assert len(action_violations) == 1
        assert action_violations[0].forced == "idle"
        assert action_violations[0].level == "hard"

    def test_non_empty_action_no_violation(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(action="smile_nod")
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        action_violations = [v for v in result.violations if v.type == "action_empty"]
        assert len(action_violations) == 0

    def test_empty_action_correction_applied_to_ir(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(action="")
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        assert result.ir.action == "idle"
        assert ir.action == ""


class TestAlgorithmSupremeCourtTimeSkip:
    def test_time_skip_within_limit(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            narrative_signal="time_skip",
            action_params={"skip_duration": 1800.0},
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        time_violations = [v for v in result.violations if v.type == "time_skip_exceeded"]
        assert len(time_violations) == 0

    def test_time_skip_exceeds_limit(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            narrative_signal="time_skip",
            action_params={"skip_duration": 7200.0},
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        time_violations = [v for v in result.violations if v.type == "time_skip_exceeded"]
        assert len(time_violations) == 1
        assert time_violations[0].original == 7200.0
        assert time_violations[0].forced == _MAX_TIME_SKIP_PER_TURN

    def test_non_time_skip_no_check(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            narrative_signal="continue",
            action_params={"skip_duration": 7200.0},
        )
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        time_violations = [v for v in result.violations if v.type == "time_skip_exceeded"]
        assert len(time_violations) == 0


class TestAlgorithmSupremeCourtNeedsCriticReview:
    def test_hard_violation_triggers_critic_review(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(action="")
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        assert result.needs_critic_review is True

    def test_no_violation_no_critic_review(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(action="idle")
        character = _MockCharacter(
            personality=_MockPersonality(scores={"neuroticism": 50.0}),
            emotion=_MockEmotion(),
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        assert result.needs_critic_review is False


class TestAlgorithmSupremeCourtNoCharacterAttrs:
    def test_missing_personality_no_crash(self):
        court = AlgorithmSupremeCourt()
        ir = CanonicalIR(
            action="idle",
            emotion_delta=EmotionDelta(arousal=0.8),
        )
        character = object()
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_dialogue_ir(ir, character, narrative)
        assert isinstance(result, ValidatedIR)


class TestAlgorithmSupremeCourtValidateNovelDelta:
    def test_no_conflicts_clean(self):
        court = AlgorithmSupremeCourt()
        delta = NarrativeDelta(
            new_facts=[NewFact(id="f1", content="天气晴朗", source="test")],
        )
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_novel_delta(delta, narrative)
        assert len(result.violations) == 0

    def test_fact_conflict_detected(self):
        court = AlgorithmSupremeCourt()
        existing_fact = NewFact(id="f0", content="天在下雨", source="test")
        new_fact = NewFact(id="f1", content="天在下雨", source="test")
        delta = NarrativeDelta(new_facts=[new_fact])
        narrative = _MockNarrative(established_facts=[existing_fact])
        result = court.validate_novel_delta(delta, narrative)
        assert len(result.violations) == 1
        assert result.violations[0].type == "fact_conflict"
        assert result.violations[0].level == "hard"

    def test_no_established_facts_attr(self):
        court = AlgorithmSupremeCourt()
        delta = NarrativeDelta(
            new_facts=[NewFact(id="f1", content="测试", source="test")],
        )
        narrative = object()
        result = court.validate_novel_delta(delta, narrative)
        assert len(result.violations) == 0

    def test_empty_new_facts(self):
        court = AlgorithmSupremeCourt()
        delta = NarrativeDelta(new_facts=[])
        narrative = _MockNarrative(established_facts=[])
        result = court.validate_novel_delta(delta, narrative)
        assert len(result.violations) == 0
