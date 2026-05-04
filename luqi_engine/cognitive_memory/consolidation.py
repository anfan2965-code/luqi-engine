from __future__ import annotations

import time
from typing import TYPE_CHECKING, List, Optional, Set

from luqi_engine.character.memory import MemoryEntry, MemoryType
from luqi_engine.cognitive_memory.types import CognitiveMemoryType, ConsolidationReport, ProceduralRule
from luqi_engine.core.config import CognitiveMemoryConfig

if TYPE_CHECKING:
    from luqi_engine.cognitive_memory.retrieval import HybridRetriever
    from luqi_engine.cognitive_memory.tiers import ProceduralTier


class ConsolidationEngine:
    def __init__(self, config: CognitiveMemoryConfig, retriever: HybridRetriever) -> None:
        self._config = config
        self._retriever = retriever
        self._similarity_threshold = config.consolidation_similarity_threshold
        self._min_cluster_size = config.consolidation_min_cluster_size
        self._procedural_min_occurrences = config.procedural_min_occurrences
        self._procedural_min_success_rate = config.procedural_min_success_rate

    def try_online_synthesis(self, new_entry: MemoryEntry, existing_entries: List[MemoryEntry]) -> Optional[MemoryEntry]:
        if not existing_entries:
            return None
        best_match: Optional[MemoryEntry] = None
        best_sim = 0.0
        for entry in existing_entries:
            sim = self._compute_similarity(new_entry, entry)
            if sim > best_sim:
                best_sim = sim
                best_match = entry
        if best_sim < self._similarity_threshold or best_match is None:
            return None
        merged_what = new_entry.what if len(new_entry.what) >= len(best_match.what) else best_match.what
        who_parts = set()
        if new_entry.who:
            who_parts.update(new_entry.who.split(","))
        if best_match.who:
            who_parts.update(best_match.who.split(","))
        merged_who = ",".join(sorted(who_parts))
        merged_when = max(new_entry.when, best_match.when)
        merged_where = new_entry.where or best_match.where
        merged_why = new_entry.why if len(new_entry.why) >= len(best_match.why) else best_match.why
        merged_importance = max(new_entry.importance, best_match.importance)
        merged_access = new_entry.access_count + best_match.access_count
        merged_valence = new_entry.emotional_valence if abs(new_entry.emotional_valence) >= abs(best_match.emotional_valence) else best_match.emotional_valence

        return MemoryEntry(
            who=merged_who,
            what=merged_what,
            when=merged_when,
            where=merged_where,
            why=merged_why,
            memory_type=MemoryType.LONG_TERM,
            emotional_valence=merged_valence,
            importance=merged_importance,
            access_count=merged_access,
            metadata={**best_match.metadata, **new_entry.metadata},
        )

    def consolidate(self, long_term_entries: List[MemoryEntry], procedural_tier: ProceduralTier) -> ConsolidationReport:
        merged_count = 0
        extracted_rules = 0
        freed_entries = 0

        clusters = self._cluster_similar(long_term_entries)
        for cluster in clusters:
            if len(cluster) >= self._min_cluster_size:
                self._merge_cluster(cluster)
                merged_count += 1
                freed_entries += len(cluster) - 1

        rules = self._extract_procedural_rules(long_term_entries)
        for rule in rules:
            procedural_tier.add_rule(rule)
            extracted_rules += 1

        return ConsolidationReport(merged_count=merged_count, extracted_rules=extracted_rules, freed_entries=freed_entries)

    def _compute_similarity(self, entry_a: MemoryEntry, entry_b: MemoryEntry) -> float:
        emb_a = self._retriever.embed(entry_a.what)
        emb_b = self._retriever.embed(entry_b.what)
        if emb_a and emb_b:
            from luqi_engine.cognitive_memory.retrieval import HybridRetriever
            return HybridRetriever._cosine_similarity(emb_a, emb_b)
        set_a = set(entry_a.what.lower().split())
        set_b = set(entry_b.what.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    def _cluster_similar(self, entries: List[MemoryEntry]) -> List[List[MemoryEntry]]:
        visited: Set[str] = set()
        clusters: List[List[MemoryEntry]] = []
        for i, entry in enumerate(entries):
            if entry.entry_id in visited:
                continue
            cluster = [entry]
            visited.add(entry.entry_id)
            for j, other in enumerate(entries):
                if other.entry_id in visited:
                    continue
                if self._compute_similarity(entry, other) >= self._similarity_threshold:
                    cluster.append(other)
                    visited.add(other.entry_id)
            if len(cluster) >= self._min_cluster_size:
                clusters.append(cluster)
        return clusters

    def _merge_cluster(self, cluster: List[MemoryEntry]) -> MemoryEntry:
        longest_what = max(cluster, key=lambda e: len(e.what))
        who_parts: Set[str] = set()
        for e in cluster:
            if e.who:
                who_parts.update(e.who.split(","))
        merged_who = ",".join(sorted(who_parts))
        merged_when = max(e.when for e in cluster)
        merged_where = ""
        for e in cluster:
            if e.where:
                merged_where = e.where
                break
        longest_why = max(cluster, key=lambda e: len(e.why))
        merged_importance = max(e.importance for e in cluster)
        merged_access = sum(e.access_count for e in cluster)
        merged_valence = max(cluster, key=lambda e: abs(e.emotional_valence)).emotional_valence

        return MemoryEntry(
            who=merged_who,
            what=longest_what.what,
            when=merged_when,
            where=merged_where,
            why=longest_why.why,
            memory_type=MemoryType.LONG_TERM,
            emotional_valence=merged_valence,
            importance=merged_importance,
            access_count=merged_access,
        )

    def _extract_procedural_rules(self, entries: List[MemoryEntry]) -> List[ProceduralRule]:
        condition_groups: dict = {}
        for entry in entries:
            key_words = " ".join(entry.what.lower().split()[:3])
            if key_words not in condition_groups:
                condition_groups[key_words] = []
            condition_groups[key_words].append(entry)

        rules: List[ProceduralRule] = []
        for condition_key, group in condition_groups.items():
            if len(group) < self._procedural_min_occurrences:
                continue
            positive_count = sum(1 for e in group if e.emotional_valence > 0)
            success_rate = positive_count / len(group) if group else 0.0
            if success_rate < self._procedural_min_success_rate:
                continue
            import uuid
            rule = ProceduralRule(
                rule_id=uuid.uuid4().hex[:12],
                condition=condition_key,
                action=group[0].why if group[0].why else condition_key,
                priority=max(e.importance for e in group),
                success_count=positive_count,
                total_count=len(group),
                success_rate=success_rate,
                derived_from=[e.entry_id for e in group],
            )
            rules.append(rule)
        return rules
