"""记忆存储模块 - 实现多层记忆存储结构"""

from __future__ import annotations

import math
import time
from typing import Dict, List, Optional, Tuple

from luqi_engine.character.memory import MemoryEntry, MemoryType
from luqi_engine.cognitive_memory.knowledge_graph import MemoryGraph
from luqi_engine.cognitive_memory.tiers import (
    LongTermTier,
    ProceduralTier,
    SensoryTier,
    ShortTermTier,
    WorkingTier,
)
from luqi_engine.cognitive_memory.types import CognitiveMemoryType, SurpriseResult
from luqi_engine.core.config import CognitiveMemoryConfig


class CognitiveMemoryStore:
    def __init__(self, config: Optional[CognitiveMemoryConfig] = None) -> None:
        self._config = config if config is not None else CognitiveMemoryConfig()
        self._sensory_tier = SensoryTier()
        self._working_tier = WorkingTier()
        self._short_term_tier = ShortTermTier()
        self._long_term_tier = LongTermTier()
        self._emotional_tier = LongTermTier()
        self._procedural_tier = ProceduralTier()
        self._graph: Optional[MemoryGraph] = None
        self._retrieval_limit: int = self._config.retrieval_limit

    def store(self, entry: MemoryEntry, target_type: Optional[CognitiveMemoryType] = None) -> SurpriseResult:
        surprise_result = self._compute_surprise(entry)
        effective_type = target_type if target_type is not None else surprise_result.target_tier
        entry.importance = surprise_result.importance

        if effective_type == CognitiveMemoryType.SENSORY:
            self._sensory_tier.add(entry)
        elif effective_type == CognitiveMemoryType.WORKING:
            self._working_tier.add(entry)
        elif effective_type == CognitiveMemoryType.SHORT_TERM:
            evicted = self._short_term_tier.add(entry)
            if evicted is not None:
                self._try_promote(evicted)
        elif effective_type == CognitiveMemoryType.LONG_TERM:
            self._long_term_tier.add(entry)
        elif effective_type == CognitiveMemoryType.EMOTIONAL:
            self._emotional_tier.add(entry)
        elif effective_type == CognitiveMemoryType.PROCEDURAL:
            pass

        if self._graph is not None:
            self._update_graph(entry)

        return surprise_result

    def retrieve(
        self,
        query: str,
        memory_type: Optional[CognitiveMemoryType] = None,
        limit: Optional[int] = None,
    ) -> List[MemoryEntry]:
        effective_limit = limit if limit is not None else self._retrieval_limit
        if memory_type is not None:
            tier = self._get_tier(memory_type)
            if tier is not None and not isinstance(tier, ProceduralTier):
                return tier.search(query, effective_limit)
            return []

        all_results: List[MemoryEntry] = []
        for tier in (self._working_tier, self._short_term_tier, self._long_term_tier, self._emotional_tier):
            all_results.extend(tier.search(query, effective_limit))
        all_results.sort(key=lambda e: e.relevance_to(query), reverse=True)
        return all_results[:effective_limit]

    def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        for tier in (self._sensory_tier, self._working_tier, self._short_term_tier, self._long_term_tier, self._emotional_tier):
            entry = tier.get(entry_id)
            if entry is not None:
                return entry
        return None

    def remove(self, entry_id: str) -> bool:
        for tier in (self._sensory_tier, self._working_tier, self._short_term_tier, self._long_term_tier, self._emotional_tier):
            removed = tier.remove(entry_id)
            if removed is not None:
                return True
        return False

    def decay(self) -> None:
        now = time.time()
        self._decay_tier(self._short_term_tier, self._config.decay_lambda_short, now)
        self._decay_tier(self._long_term_tier, self._config.decay_lambda_long, now)
        self._decay_tier(self._emotional_tier, self._config.decay_lambda_emotional, now)

    def clear_sensory(self) -> None:
        self._sensory_tier.clear()

    def clear_working(self) -> None:
        self._working_tier.clear()

    def set_graph(self, graph: MemoryGraph) -> None:
        self._graph = graph

    def get_graph(self) -> Optional[MemoryGraph]:
        return self._graph

    def get_procedural_tier(self) -> ProceduralTier:
        return self._procedural_tier

    def tier_stats(self) -> Dict[str, Dict[str, int]]:
        return {
            "sensory": {"size": self._sensory_tier.size(), "capacity": self._sensory_tier.capacity()},
            "working": {"size": self._working_tier.size(), "capacity": self._working_tier.capacity()},
            "short_term": {"size": self._short_term_tier.size(), "capacity": self._short_term_tier.capacity()},
            "long_term": {"size": self._long_term_tier.size(), "capacity": self._long_term_tier.capacity()},
            "emotional": {"size": self._emotional_tier.size(), "capacity": self._emotional_tier.capacity()},
        }

    def _compute_surprise(self, entry: MemoryEntry) -> SurpriseResult:
        existing = self.retrieve(query=entry.what, limit=5)
        surprise = 1.0
        if existing:
            from luqi_engine.cognitive_memory.retrieval import HybridRetriever
            new_emb = []
            best_sim = 0.0
            for e in existing:
                set_a = set(entry.what.lower().split())
                set_b = set(e.what.lower().split())
                if set_a and set_b:
                    sim = len(set_a & set_b) / len(set_a | set_b)
                    best_sim = max(best_sim, sim)
            surprise = 1.0 - best_sim

        if abs(entry.emotional_valence) >= 0.7:
            surprise *= (1.0 + abs(entry.emotional_valence) * self._config.emotional_surprise_boost)

        if surprise >= self._config.surprise_threshold_high:
            target_tier = CognitiveMemoryType.LONG_TERM
            importance = 0.9
        elif surprise >= self._config.surprise_threshold_medium:
            target_tier = CognitiveMemoryType.SHORT_TERM
            importance = 0.7
        else:
            target_tier = CognitiveMemoryType.SHORT_TERM
            importance = 0.3

        return SurpriseResult(surprise=surprise, target_tier=target_tier, importance=importance)

    def _try_promote(self, evicted: MemoryEntry) -> None:
        if evicted.access_count >= 3:
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
            self._long_term_tier.add(promoted)
        elif abs(evicted.emotional_valence) >= 0.7:
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
            self._emotional_tier.add(promoted)

    def _decay_tier(self, tier, lambda_base: float, now: float) -> None:
        to_remove: List[str] = []
        mu = self._config.decay_mu_importance
        for entry in tier.all_entries():
            time_since = now - entry.when
            effective_lambda = lambda_base * math.exp(-mu * entry.importance)
            reinforcement_factor = self._config.reinforcement_decay_factor ** getattr(entry, '_reinforcement_count', 0)
            effective_lambda *= reinforcement_factor
            retention = math.exp(-effective_lambda * time_since)
            entry.importance *= retention
            if entry.importance < 0.1:
                to_remove.append(entry.entry_id)
        for eid in to_remove:
            tier.remove(eid)

    def _update_graph(self, entry: MemoryEntry) -> None:
        if self._graph is None:
            return
        from luqi_engine.cognitive_memory.types import MemoryNode, MemoryEdge
        import uuid

        if entry.who:
            self._graph.add_node(MemoryNode(
                node_id=f"entity_{entry.who}_{uuid.uuid4().hex[:6]}",
                concept=entry.who,
                node_type="entity",
                temporal_start=entry.when,
            ))
        if entry.where:
            self._graph.add_node(MemoryNode(
                node_id=f"location_{entry.where}_{uuid.uuid4().hex[:6]}",
                concept=entry.where,
                node_type="location",
                temporal_start=entry.when,
            ))

    def _get_tier(self, memory_type: CognitiveMemoryType):
        mapping = {
            CognitiveMemoryType.SENSORY: self._sensory_tier,
            CognitiveMemoryType.WORKING: self._working_tier,
            CognitiveMemoryType.SHORT_TERM: self._short_term_tier,
            CognitiveMemoryType.LONG_TERM: self._long_term_tier,
            CognitiveMemoryType.EMOTIONAL: self._emotional_tier,
            CognitiveMemoryType.PROCEDURAL: self._procedural_tier,
        }
        return mapping.get(memory_type)
