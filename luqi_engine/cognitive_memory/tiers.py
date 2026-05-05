"""记忆层级模块 - 定义记忆的层级结构"""

from __future__ import annotations

from collections import OrderedDict
from typing import List, Optional, Tuple

from luqi_engine.cognitive_memory.types import CognitiveMemoryType, ProceduralRule
from luqi_engine.character.memory import MemoryEntry

_SENSORY_CAPACITY = 1000
_MILLER_LAW_CENTRAL = 7
_MILLER_LAW_VARIANCE = 2
_WORKING_CAPACITY = _MILLER_LAW_CENTRAL + _MILLER_LAW_VARIANCE
_SHORT_TERM_CAPACITY = 100
_LONG_TERM_CAPACITY = 10000
_CONDITION_MATCH_THRESHOLD = 0.3


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


class _CognitiveTier:
    def __init__(self, capacity: int, tier_type: CognitiveMemoryType) -> None:
        self._capacity = capacity
        self._tier_type = tier_type
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

    def size(self) -> int:
        return len(self._store)

    def capacity(self) -> int:
        return self._capacity


class SensoryTier(_CognitiveTier):
    def __init__(self) -> None:
        super().__init__(_SENSORY_CAPACITY, CognitiveMemoryType.SENSORY)

    def clear(self) -> None:
        self._store.clear()


class WorkingTier(_CognitiveTier):
    def __init__(self) -> None:
        super().__init__(_WORKING_CAPACITY, CognitiveMemoryType.WORKING)

    def add(self, entry: MemoryEntry) -> Optional[MemoryEntry]:
        evicted: Optional[MemoryEntry] = None
        if len(self._store) >= self._capacity and entry.entry_id not in self._store:
            _, evicted = self._store.popitem(last=False)
        self._store[entry.entry_id] = entry
        return evicted

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        entry = self._store.get(entry_id)
        if entry is not None:
            entry.touch()
        return entry

    def clear(self) -> None:
        self._store.clear()


class ShortTermTier(_CognitiveTier):
    def __init__(self) -> None:
        super().__init__(_SHORT_TERM_CAPACITY, CognitiveMemoryType.SHORT_TERM)


class LongTermTier(_CognitiveTier):
    def __init__(self) -> None:
        super().__init__(_LONG_TERM_CAPACITY, CognitiveMemoryType.LONG_TERM)


class ProceduralTier:
    def __init__(self) -> None:
        self._tier_type = CognitiveMemoryType.PROCEDURAL
        self._rules: List[ProceduralRule] = []

    def add_rule(self, rule: ProceduralRule) -> None:
        for idx, existing in enumerate(self._rules):
            if existing.rule_id == rule.rule_id:
                self._rules[idx] = rule
                return
        self._rules.append(rule)

    def get_rules(self) -> List[ProceduralRule]:
        return list(self._rules)

    def find_matching_rules(self, condition: str) -> List[ProceduralRule]:
        scored: List[Tuple[float, ProceduralRule]] = []
        condition_lower = condition.lower()
        for rule in self._rules:
            score = _text_similarity(rule.condition.lower(), condition_lower)
            if score >= _CONDITION_MATCH_THRESHOLD:
                combined = score * rule.priority
                scored.append((combined, rule))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [rule for _, rule in scored]
