"""叙事文档 — 所有智能体共享的唯一真相源"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from luqi_engine.core.types import (
    Fact, ChapterOutline, ScenePrediction, PaceState, AutoModeConfig,
    NarrativeDelta, NewFact,
)
from luqi_engine.core.interfaces import INarrativeDocument
from luqi_engine.core.constants import (
    PromptContextMode,
    StoryBeatStatus,
    _FACT_ID_PREFIX,
    _FACT_ID_ZERO_PAD_WIDTH,
    _TICK_ID_PREFIX,
)

_PROMPT_COMPACT_FACT_LIMIT = 5
_PROMPT_STANDARD_FACT_LIMIT = 10
_PROMPT_DETAILED_FACT_LIMIT = 20
_PROMPT_MAX_PREDICTIONS = 3
_PROMPT_MAX_OPEN_QUESTIONS = 5
_PROMPT_BEAT_DESC_MAX_LENGTH = 50
_PROMPT_PROSE_DRAFT_MAX_LENGTH = 500

_NEGATION_WORDS = ("不", "没", "非", "无", "未", "别", "否", "not ", "no ", "never ")


@dataclass
class NarrativeDocument(INarrativeDocument):
    """活体叙事文档 — 所有智能体共享的唯一真相源"""

    document_id: str = ""
    world_id: str = ""
    version: int = 0
    created_at: float = 0.0
    last_updated: float = 0.0

    current_chapter: int = 1
    current_scene: str = ""
    timeline_position: float = 0.0
    narrative_tick: int = 0

    established_facts: List[Fact] = field(default_factory=list)
    current_chapter_outline: Optional[ChapterOutline] = None
    next_scene_predictions: List[ScenePrediction] = field(default_factory=list)
    active_prediction: Optional[int] = None

    pending_absorptions: List[Dict[str, Any]] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    resolved_questions: List[str] = field(default_factory=list)

    pace_state: Optional[PaceState] = None
    auto_mode_config: Optional[AutoModeConfig] = None

    prose_draft: Optional[str] = None
    scene_descriptions: Dict[str, str] = field(default_factory=dict)
    dialogue_transcripts: List[Dict[str, Any]] = field(default_factory=list)

    def apply_delta(self, delta: NarrativeDelta) -> None:
        self.version += 1
        self.last_updated = time.time()
        self.narrative_tick += 1

        for new_fact in delta.new_facts:
            fact = Fact(
                id=new_fact.id or f"{_FACT_ID_PREFIX}{len(self.established_facts) + 1:0{_FACT_ID_ZERO_PAD_WIDTH}d}",
                sequence_number=len(self.established_facts) + 1,
                timestamp=new_fact.timestamp or f"{_TICK_ID_PREFIX}{self.narrative_tick}",
                source=new_fact.source,
                content=new_fact.content,
                participants=new_fact.participants,
                emotional_valence=new_fact.emotional_valence,
                tags=new_fact.tags,
            )
            self.established_facts.append(fact)

        if delta.chapter_update:
            self._apply_chapter_update(delta.chapter_update)

        if delta.next_prediction:
            self.next_scene_predictions = [
                ScenePrediction(
                    scene_id=p.get("scene_id", ""),
                    scene_name=p.get("scene_name", ""),
                    probability=p.get("probability", 0.0),
                    description=p.get("description", ""),
                    expected_participants=p.get("expected_participants", []),
                    estimated_tension=p.get("estimated_tension", 0.0),
                )
                for p in delta.next_prediction.likely_next_scenes
            ]

        self.open_questions.extend(delta.open_questions_added)
        for q in delta.open_questions_resolved:
            if q in self.open_questions:
                self.open_questions.remove(q)
            self.resolved_questions.append(q)

    def _apply_chapter_update(self, update: Any) -> None:
        if self.current_chapter_outline is None:
            return
        if update.current_beat_progress > 0:
            if self.current_chapter_outline.beats:
                idx = self.current_chapter_outline.current_beat_index
                if idx < len(self.current_chapter_outline.beats):
                    self.current_chapter_outline.beats[idx].progress = update.current_beat_progress

    def to_prompt_context(self, mode: str = PromptContextMode.STANDARD) -> str:
        parts: List[str] = []

        if mode in (PromptContextMode.STANDARD, PromptContextMode.DETAILED, PromptContextMode.PROSE):
            parts.append(f"[叙事文档 v{self.version}]")
            parts.append(f"当前章节: 第{self.current_chapter}章")
            parts.append(f"当前场景: {self.current_scene}")
            parts.append(f"叙事进度: {self.timeline_position:.0%}")

        if self.established_facts:
            fact_limit = (
                _PROMPT_COMPACT_FACT_LIMIT
                if mode == PromptContextMode.COMPACT
                else _PROMPT_DETAILED_FACT_LIMIT
                if mode == PromptContextMode.DETAILED
                else _PROMPT_STANDARD_FACT_LIMIT
            )
            recent_facts = self.established_facts[-fact_limit:]
            parts.append("\n[最近事实]")
            for f in recent_facts:
                parts.append(f"  - {f.content}")

        if self.current_chapter_outline and mode != PromptContextMode.COMPACT:
            parts.append(f"\n[章节大纲] {self.current_chapter_outline.title}")
            if self.current_chapter_outline.beats:
                for beat in self.current_chapter_outline.beats:
                    status_mark = "●" if beat.status == StoryBeatStatus.ACTIVE else "○"
                    parts.append(f"  {status_mark} {beat.name}: {beat.description[:_PROMPT_BEAT_DESC_MAX_LENGTH]}")

        if self.next_scene_predictions and mode != PromptContextMode.COMPACT:
            parts.append("\n[场景预测]")
            for pred in self.next_scene_predictions[:_PROMPT_MAX_PREDICTIONS]:
                parts.append(f"  - {pred.scene_name} (概率:{pred.probability:.0%})")

        if self.open_questions and mode in (PromptContextMode.DETAILED, PromptContextMode.PROSE):
            parts.append("\n[未解问题]")
            for q in self.open_questions[:_PROMPT_MAX_OPEN_QUESTIONS]:
                parts.append(f"  ? {q}")

        if mode == PromptContextMode.PROSE and self.prose_draft:
            parts.append(f"\n[小说草稿]\n{self.prose_draft[:_PROMPT_PROSE_DRAFT_MAX_LENGTH]}")

        return "\n".join(parts)

    def find_conflicting_fact(self, new_fact: Any) -> Optional[Fact]:
        new_content_lower = ""
        if hasattr(new_fact, 'content'):
            new_content_lower = new_fact.content.lower()
        elif isinstance(new_fact, dict):
            new_content_lower = new_fact.get("content", "").lower()

        if not new_content_lower:
            return None

        for existing in self.established_facts:
            if existing.is_retracted:
                continue
            existing_lower = existing.content.lower()
            if self._has_negation_conflict(new_content_lower, existing_lower):
                return existing

        return None

    @staticmethod
    def _has_negation_conflict(text_a: str, text_b: str) -> bool:
        for neg in _NEGATION_WORDS:
            if neg in text_a and neg not in text_b:
                core_a = text_a.replace(neg, "").strip()
                core_b = text_b.strip()
                if core_a and core_b and (core_a in core_b or core_b in core_a):
                    return True
            elif neg not in text_a and neg in text_b:
                core_a = text_a.strip()
                core_b = text_b.replace(neg, "").strip()
                if core_a and core_b and (core_a in core_b or core_b in core_a):
                    return True
        return False
