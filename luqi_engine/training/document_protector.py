"""
降级文档保护器 — 降级期间保护叙事文档不被错误修改
核心规则：
  1. 降级期间拒绝覆盖已有事实（只有 cloud 来源允许覆盖）
  2. 降级期间拒绝缩减 chapter_outline beats 数量
  3. 降级期间预测置信度打折（乘以衰减因子）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from luqi_engine.core.types import (
    NarrativeDelta,
    NewFact,
    ChapterUpdate,
    NextPrediction,
    Fact,
    ChapterOutline,
    StoryBeat,
)
from luqi_engine.core.constants import _CONFIDENCE_ROUND_PRECISION

_FACT_SOURCE_CLOUD = "cloud"
_FACT_SOURCE_LOCAL = "local"
_FACT_SOURCE_FALLBACK = "fallback"

_DEGRADED_CONFIDENCE_DECAY_FACTOR = 0.7

_PROTECTION_REASON_FACT_OVERWRITE = "fact_overwrite_rejected"
_PROTECTION_REASON_BEAT_REDUCTION = "beat_reduction_rejected"
_PROTECTION_REASON_CONFIDENCE_DECAYED = "confidence_decayed"


@dataclass
class ProtectionReport:
    applied: bool = True
    fact_overwrites_blocked: int = 0
    beat_reduction_blocked: bool = False
    confidence_decay_applied: bool = False
    reasons: List[str] = None

    def __post_init__(self) -> None:
        if self.reasons is None:
            self.reasons = []


class DegradationDocumentProtector:
    """
    降级文档保护器
    在降级期间对 NarrativeDelta 施加保护规则
    is_degraded 参数由外部传入（来自 fallback.py 的当前降级级别）
    """

    def __init__(self, confidence_decay_factor: float = _DEGRADED_CONFIDENCE_DECAY_FACTOR) -> None:
        self._confidence_decay_factor = confidence_decay_factor

    def safe_apply_delta(
        self,
        delta: NarrativeDelta,
        existing_facts: List[Fact],
        current_chapter_outline: Optional[ChapterOutline],
        is_degraded: bool,
    ) -> Tuple[NarrativeDelta, ProtectionReport]:
        if not is_degraded:
            return delta, ProtectionReport()

        report = ProtectionReport()
        new_facts = self._filter_fact_overwrites(
            delta.new_facts, existing_facts, report
        )
        chapter_update = self._protect_beat_count(
            delta.chapter_update, current_chapter_outline, report
        )
        next_prediction = self._decay_confidence(
            delta.next_prediction, report
        )

        protected_delta = NarrativeDelta(
            version=delta.version,
            new_facts=new_facts,
            chapter_update=chapter_update,
            next_prediction=next_prediction,
            open_questions_added=delta.open_questions_added,
            open_questions_resolved=delta.open_questions_resolved,
            narrative_note=delta.narrative_note,
        )
        return protected_delta, report

    def _filter_fact_overwrites(
        self,
        new_facts: List[NewFact],
        existing_facts: List[Fact],
        report: ProtectionReport,
    ) -> List[NewFact]:
        filtered: List[NewFact] = []
        for new_fact in new_facts:
            if self._is_cloud_source(new_fact.source):
                filtered.append(new_fact)
                continue
            if self._would_overwrite(new_fact, existing_facts):
                report.fact_overwrites_blocked += 1
                report.reasons.append(_PROTECTION_REASON_FACT_OVERWRITE)
                continue
            filtered.append(new_fact)
        return filtered

    def _protect_beat_count(
        self,
        chapter_update: Optional[ChapterUpdate],
        current_outline: Optional[ChapterOutline],
        report: ProtectionReport,
    ) -> Optional[ChapterUpdate]:
        if chapter_update is None:
            return None
        if current_outline is None:
            return chapter_update
        if chapter_update.new_beat_suggested is None:
            return chapter_update

        new_beat_count = len(current_outline.beats) + 1
        if self._would_reduce_beats(chapter_update, current_outline):
            report.beat_reduction_blocked = True
            report.reasons.append(_PROTECTION_REASON_BEAT_REDUCTION)
            return ChapterUpdate(
                current_beat_progress=chapter_update.current_beat_progress,
                new_beat_suggested=None,
                character_arcs_update=chapter_update.character_arcs_update,
                constraints_added=chapter_update.constraints_added,
                constraints_removed=chapter_update.constraints_removed,
            )
        return chapter_update

    def _decay_confidence(
        self,
        prediction: Optional[NextPrediction],
        report: ProtectionReport,
    ) -> Optional[NextPrediction]:
        if prediction is None:
            return None
        if not prediction.likely_next_scenes:
            return prediction

        decayed_scenes: List[Dict[str, Any]] = []
        for scene in prediction.likely_next_scenes:
            decayed_scene = dict(scene)
            original_prob = decayed_scene.get("probability", 0.0)
            decayed_scene["probability"] = round(
                original_prob * self._confidence_decay_factor,
                _CONFIDENCE_ROUND_PRECISION,
            )
            decayed_scenes.append(decayed_scene)

        decayed_tension = prediction.narrative_tension * self._confidence_decay_factor

        report.confidence_decay_applied = True
        report.reasons.append(_PROTECTION_REASON_CONFIDENCE_DECAYED)

        return NextPrediction(
            likely_next_scenes=decayed_scenes,
            narrative_tension=round(decayed_tension, _CONFIDENCE_ROUND_PRECISION),
            suggested_pace=prediction.suggested_pace,
        )

    @staticmethod
    def _is_cloud_source(source: str) -> bool:
        return source.lower() == _FACT_SOURCE_CLOUD

    @staticmethod
    def _would_overwrite(new_fact: NewFact, existing_facts: List[Fact]) -> bool:
        if not new_fact.content:
            return False
        new_lower = new_fact.content.lower()
        for existing in existing_facts:
            if existing.is_retracted:
                continue
            if existing.content.lower() == new_lower:
                return True
            if new_fact.id and existing.id == new_fact.id:
                return True
        return False

    @staticmethod
    def _would_reduce_beats(
        chapter_update: ChapterUpdate,
        current_outline: ChapterOutline,
    ) -> bool:
        if chapter_update.new_beat_suggested is None:
            return False
        if not current_outline.beats:
            return False
        removal_count = len(chapter_update.constraints_removed)
        if removal_count <= 0:
            return False
        return True
