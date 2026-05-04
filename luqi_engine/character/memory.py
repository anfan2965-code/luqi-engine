"""
记忆系统 - 三层分类存储（短期/长期/情感），LRU淘汰，相关性检索
基于5Ws框架（Who/What/When/Where/Why）的记忆条目
"""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.config import CharacterConfig
from luqi_engine.core.types import EntityId

_MEMORY_TYPE_SHORT_TERM: str = "short_term"
_MEMORY_TYPE_LONG_TERM: str = "long_term"
_MEMORY_TYPE_EMOTIONAL: str = "emotional"

_RELEVANCE_THRESHOLD: float = 0.1
_RELEVANCE_WEIGHT_WHO: float = 0.2
_RELEVANCE_WEIGHT_WHAT: float = 0.3
_RELEVANCE_WEIGHT_WHERE: float = 0.15
_RELEVANCE_WEIGHT_WHEN: float = 0.15
_RELEVANCE_WEIGHT_WHY: float = 0.2

_DECAY_BASE_RATE: float = 0.001
_EMOTIONAL_DECAY_MULTIPLIER: float = 0.5
_LONG_TERM_DECAY_MULTIPLIER: float = 0.1

_PROMOTION_ACCESS_THRESHOLD: int = 3
_PROMOTION_EMOTIONAL_THRESHOLD: float = 0.7

_TIMESTAMP_EPSILON: float = 1e-9
_IMPORTANCE_BOOST_FACTOR: float = 0.5
_ENTRY_ID_HEX_LENGTH: int = 12


class MemoryType(Enum):
    SHORT_TERM = auto()
    LONG_TERM = auto()
    EMOTIONAL = auto()

    @property
    def storage_key(self) -> str:
        mapping = {
            MemoryType.SHORT_TERM: _MEMORY_TYPE_SHORT_TERM,
            MemoryType.LONG_TERM: _MEMORY_TYPE_LONG_TERM,
            MemoryType.EMOTIONAL: _MEMORY_TYPE_EMOTIONAL,
        }
        return mapping[self]


@dataclass
class MemoryEntry:
    RELEVANCE_THRESHOLD: ClassVar[float] = _RELEVANCE_THRESHOLD

    who: str
    what: str
    when: float = field(default_factory=time.time)
    where: str = ""
    why: str = ""
    memory_type: MemoryType = MemoryType.SHORT_TERM
    emotional_valence: float = 0.0
    importance: float = 0.5
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    entry_id: str = ""

    def __post_init__(self) -> None:
        if not self.entry_id:
            import uuid
            self.entry_id = uuid.uuid4().hex[:_ENTRY_ID_HEX_LENGTH]

    def touch(self) -> None:
        self.access_count += 1

    def relevance_to(self, query: str) -> float:
        query_lower = query.lower()
        score = _RELEVANCE_WEIGHT_WHAT * _text_similarity(self.what.lower(), query_lower)
        score += _RELEVANCE_WEIGHT_WHO * _text_similarity(self.who.lower(), query_lower)
        score += _RELEVANCE_WEIGHT_WHERE * _text_similarity(self.where.lower(), query_lower)
        score += _RELEVANCE_WEIGHT_WHY * _text_similarity(self.why.lower(), query_lower)
        recency = 1.0 / (1.0 + abs(time.time() - self.when) * _DECAY_BASE_RATE)
        score += _RELEVANCE_WEIGHT_WHEN * recency
        score *= (1.0 + self.importance * _IMPORTANCE_BOOST_FACTOR)
        return score


def _text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


class _MemoryTier:
    _REMOVE_OLDEST_SENTINEL: ClassVar[bool] = True

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._store: OrderedDict[str, MemoryEntry] = OrderedDict()

    def add(self, entry: MemoryEntry) -> Optional[MemoryEntry]:
        evicted: Optional[MemoryEntry] = None
        if len(self._store) >= self._capacity and entry.entry_id not in self._store:
            _, evicted = self._store.popitem(last=False)
        self._store[entry.entry_id] = entry
        self._store.move_to_end(entry.entry_id)
        return evicted

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        entry = self._store.get(entry_id)
        if entry is not None:
            entry.touch()
            self._store.move_to_end(entry_id)
        return entry

    def remove(self, entry_id: str) -> Optional[MemoryEntry]:
        return self._store.pop(entry_id, None)

    def search(self, query: str, limit: int) -> List[MemoryEntry]:
        scored: List[Tuple[float, MemoryEntry]] = []
        for entry in self._store.values():
            score = entry.relevance_to(query)
            if score >= MemoryEntry.RELEVANCE_THRESHOLD:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def all_entries(self) -> List[MemoryEntry]:
        return list(self._store.values())

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def capacity(self) -> int:
        return self._capacity


class MemoryStore:
    PROMOTION_ACCESS_THRESHOLD: ClassVar[int] = _PROMOTION_ACCESS_THRESHOLD
    PROMOTION_EMOTIONAL_THRESHOLD: ClassVar[float] = _PROMOTION_EMOTIONAL_THRESHOLD

    def __init__(self, config: Optional[CharacterConfig] = None) -> None:
        cfg = config if config is not None else CharacterConfig()
        self._tiers: Dict[MemoryType, _MemoryTier] = {
            MemoryType.SHORT_TERM: _MemoryTier(cfg.short_term_memory_capacity),
            MemoryType.LONG_TERM: _MemoryTier(cfg.long_term_memory_capacity),
            MemoryType.EMOTIONAL: _MemoryTier(cfg.emotional_memory_capacity),
        }
        self._retrieval_limit: int = cfg.memory_retrieval_limit

    def store(self, entry: MemoryEntry) -> None:
        tier = self._tiers[entry.memory_type]
        evicted = tier.add(entry)
        if evicted is not None and entry.memory_type == MemoryType.SHORT_TERM:
            if evicted.access_count >= self.PROMOTION_ACCESS_THRESHOLD:
                promoted = MemoryEntry(
                    who=evicted.who,
                    what=evicted.what,
                    when=evicted.when,
                    where=evicted.where,
                    why=evicted.why,
                    memory_type=MemoryType.LONG_TERM,
                    emotional_valence=evicted.emotional_valence,
                    importance=evicted.importance,
                    access_count=evicted.access_count,
                    metadata=evicted.metadata,
                    entry_id=evicted.entry_id,
                )
                self._tiers[MemoryType.LONG_TERM].add(promoted)
            elif abs(evicted.emotional_valence) >= self.PROMOTION_EMOTIONAL_THRESHOLD:
                promoted = MemoryEntry(
                    who=evicted.who,
                    what=evicted.what,
                    when=evicted.when,
                    where=evicted.where,
                    why=evicted.why,
                    memory_type=MemoryType.EMOTIONAL,
                    emotional_valence=evicted.emotional_valence,
                    importance=evicted.importance,
                    access_count=evicted.access_count,
                    metadata=evicted.metadata,
                    entry_id=evicted.entry_id,
                )
                self._tiers[MemoryType.EMOTIONAL].add(promoted)

    def retrieve(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: Optional[int] = None,
    ) -> List[MemoryEntry]:
        effective_limit = limit if limit is not None else self._retrieval_limit
        if memory_type is not None:
            return self._tiers[memory_type].search(query, effective_limit)
        all_results: List[MemoryEntry] = []
        for tier in self._tiers.values():
            all_results.extend(tier.search(query, effective_limit))
        all_results.sort(key=lambda e: e.relevance_to(query), reverse=True)
        return all_results[:effective_limit]

    def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        for tier in self._tiers.values():
            entry = tier.get(entry_id)
            if entry is not None:
                return entry
        return None

    def remove(self, entry_id: str) -> bool:
        for tier in self._tiers.values():
            removed = tier.remove(entry_id)
            if removed is not None:
                return True
        return False

    def decay(self) -> None:
        now = time.time()
        for memory_type, tier in self._tiers.items():
            if memory_type == MemoryType.LONG_TERM:
                decay_rate = _DECAY_BASE_RATE * _LONG_TERM_DECAY_MULTIPLIER
            elif memory_type == MemoryType.EMOTIONAL:
                decay_rate = _DECAY_BASE_RATE * _EMOTIONAL_DECAY_MULTIPLIER
            else:
                decay_rate = _DECAY_BASE_RATE
            to_remove: List[str] = []
            for entry in tier.all_entries():
                age = now - entry.when
                entry.importance *= (1.0 - decay_rate * age)
                if entry.importance < MemoryEntry.RELEVANCE_THRESHOLD:
                    to_remove.append(entry.entry_id)
            for eid in to_remove:
                tier.remove(eid)

    def tier_stats(self) -> Dict[str, Dict[str, int]]:
        stats: Dict[str, Dict[str, int]] = {}
        for memory_type, tier in self._tiers.items():
            stats[memory_type.storage_key] = {
                "size": tier.size,
                "capacity": tier.capacity,
            }
        return stats
