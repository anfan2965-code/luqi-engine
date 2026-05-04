"""算法最高法院 — 所有LLM输出必须经过此门"""
from __future__ import annotations

import copy
from typing import Any, List, Optional

from luqi_engine.core.types import (
    CanonicalIR, EmotionDelta, NarrativeDelta,
    ValidatedIR, ValidatedDelta, Violation,
)
from luqi_engine.core.interfaces import IAlgorithmSupremeCourt
from luqi_engine.core.constants import (
    ViolationLevel,
    ViolationType,
    NarrativeSignal,
    _PERSONALITY_SCORE_MAX,
    _AROUSAL_DELTA_BASE,
    _AROUSAL_DELTA_NEUROTICISM_FACTOR,
    _PLEASURE_DELTA_MAX,
    _DOMINANCE_DELTA_MAX,
    _MAX_TIME_SKIP_PER_TURN,
    _DEFAULT_FORCED_ACTION,
)


class AlgorithmSupremeCourt(IAlgorithmSupremeCourt):
    """5级约束金字塔校验器"""

    def validate_dialogue_ir(
        self, ir: CanonicalIR, character: Any, narrative: Any
    ) -> ValidatedIR:
        violations: List[Violation] = []

        if hasattr(character, 'personality') and hasattr(character, 'emotion'):
            try:
                neuroticism = character.personality.get_score("neuroticism") / _PERSONALITY_SCORE_MAX
                max_arousal_delta = _AROUSAL_DELTA_BASE + neuroticism * _AROUSAL_DELTA_NEUROTICISM_FACTOR
                if abs(ir.emotion_delta.arousal) > max_arousal_delta:
                    clamped_a = max(-max_arousal_delta, min(max_arousal_delta, ir.emotion_delta.arousal))
                    violations.append(Violation(
                        level=ViolationLevel.HARD, type=ViolationType.EMOTION_OUT_OF_RANGE,
                        field="arousal",
                        original=ir.emotion_delta.arousal, forced=clamped_a,
                    ))
                if abs(ir.emotion_delta.pleasure) > _PLEASURE_DELTA_MAX:
                    clamped_p = max(-_PLEASURE_DELTA_MAX, min(_PLEASURE_DELTA_MAX, ir.emotion_delta.pleasure))
                    violations.append(Violation(
                        level=ViolationLevel.HARD, type=ViolationType.EMOTION_OUT_OF_RANGE,
                        field="pleasure",
                        original=ir.emotion_delta.pleasure, forced=clamped_p,
                    ))
                if abs(ir.emotion_delta.dominance) > _DOMINANCE_DELTA_MAX:
                    clamped_d = max(-_DOMINANCE_DELTA_MAX, min(_DOMINANCE_DELTA_MAX, ir.emotion_delta.dominance))
                    violations.append(Violation(
                        level=ViolationLevel.HARD, type=ViolationType.EMOTION_OUT_OF_RANGE,
                        field="dominance",
                        original=ir.emotion_delta.dominance, forced=clamped_d,
                    ))
            except (AttributeError, TypeError):
                pass

        if not ir.action:
            violations.append(Violation(
                level=ViolationLevel.HARD, type=ViolationType.ACTION_EMPTY,
                original=ir.action, forced=_DEFAULT_FORCED_ACTION,
            ))

        if ir.narrative_signal == NarrativeSignal.TIME_SKIP:
            skip_duration = ir.action_params.get("skip_duration", 0)
            if skip_duration > _MAX_TIME_SKIP_PER_TURN:
                violations.append(Violation(
                    level=ViolationLevel.HARD, type=ViolationType.TIME_SKIP_EXCEEDED,
                    original=skip_duration, forced=_MAX_TIME_SKIP_PER_TURN,
                ))

        corrected_ir = copy.deepcopy(ir)
        for v in violations:
            if v.forced is not None:
                if v.type == ViolationType.EMOTION_OUT_OF_RANGE:
                    try:
                        forced_val = float(v.forced)
                    except (ValueError, TypeError):
                        forced_val = 0.0
                    if "arousal" in v.field:
                        corrected_ir.emotion_delta.arousal = forced_val
                    elif "pleasure" in v.field:
                        corrected_ir.emotion_delta.pleasure = forced_val
                    elif "dominance" in v.field:
                        corrected_ir.emotion_delta.dominance = forced_val
                elif v.type == ViolationType.ACTION_EMPTY:
                    corrected_ir.action = v.forced

        needs_critic_review = any(v.level == ViolationLevel.HARD for v in violations)
        return ValidatedIR(
            ir=corrected_ir,
            violations=violations,
            is_clean=len(violations) == 0,
            needs_critic_review=needs_critic_review,
        )

    def validate_novel_delta(
        self, delta: NarrativeDelta, narrative: Any
    ) -> ValidatedDelta:
        violations: List[Violation] = []

        if hasattr(narrative, 'established_facts') and delta.new_facts:
            for new_fact in delta.new_facts:
                conflicting = narrative.find_conflicting_fact(new_fact)
                if conflicting:
                    violations.append(Violation(
                        level=ViolationLevel.HARD, type=ViolationType.FACT_CONFLICT,
                        original=new_fact.content,
                        forced=f"FLAGGED: conflicts with {conflicting.id}",
                    ))

        return ValidatedDelta(delta=delta, violations=violations)
