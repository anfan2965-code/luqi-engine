"""
认知记忆整合模块 - 负责记忆的整合、聚类和程序性规则提取

功能：
- 记忆聚类：基于MinHash签名的快速近似相似度计算
- 记忆整合：合并相似记忆条目
- 程序性规则提取：从重复行为中提取规则
"""

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
        """
        计算两个记忆条目之间的相似度
        
        Args:
            entry_a: 第一个记忆条目
            entry_b: 第二个记忆条目
            
        Returns:
            相似度分数（0.0到1.0之间）
        """
        # 优先使用embedding计算余弦相似度
        emb_a = self._retriever.embed(entry_a.what)
        emb_b = self._retriever.embed(entry_b.what)
        if emb_a and emb_b:
            from luqi_engine.cognitive_memory.retrieval import HybridRetriever
            return HybridRetriever._cosine_similarity(emb_a, emb_b)
        
        # 回退到Jaccard相似度
        set_a = set(entry_a.what.lower().split())
        set_b = set(entry_b.what.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    def _compute_minhash_signature(self, text: str, num_hashes: int = 128) -> List[int]:
        """
        计算文本的MinHash签名
        
        Args:
            text: 输入文本
            num_hashes: 哈希函数数量（签名长度）
            
        Returns:
            MinHash签名（整数列表）
        """
        import hashlib
        
        # 将文本转换为字符集合（shingles）
        words = text.lower().split()
        if len(words) < 2:
            return [hash(w) % (2**32) for w in words] + [0] * (num_hashes - len(words))
        
        # 使用2-gram作为shingles
        shingles = set()
        for i in range(len(words) - 1):
            shingle = f"{words[i]}_{words[i+1]}"
            shingles.add(shingle)
        
        # 计算MinHash签名
        signature = []
        for i in range(num_hashes):
            min_hash = float('inf')
            for shingle in shingles:
                # 使用不同的哈希函数
                hash_input = f"{shingle}_{i}".encode('utf-8')
                hash_value = int(hashlib.md5(hash_input).hexdigest(), 16) % (2**32)
                min_hash = min(min_hash, hash_value)
            signature.append(min_hash)
        
        return signature

    def _minhash_similarity(self, sig_a: List[int], sig_b: List[int]) -> float:
        """
        计算两个MinHash签名之间的相似度
        
        Args:
            sig_a: 第一个签名
            sig_b: 第二个签名
            
        Returns:
            相似度分数（0.0到1.0之间）
        """
        if not sig_a or not sig_b:
            return 0.0
        
        # 计算签名中相同元素的比例
        matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
        return matches / len(sig_a)

    def _cluster_similar(self, entries: List[MemoryEntry]) -> List[List[MemoryEntry]]:
        """
        聚类相似的记忆条目
        
        使用MinHash签名进行快速近似相似度计算，
        将时间复杂度从O(n²)降为近似O(n)
        
        Args:
            entries: 记忆条目列表
            
        Returns:
            聚类结果列表
        """
        if not entries:
            return []
        
        # 预计算所有条目的MinHash签名
        signatures: Dict[str, List[int]] = {}
        for entry in entries:
            signatures[entry.entry_id] = self._compute_minhash_signature(entry.what)
        
        visited: Set[str] = set()
        clusters: List[List[MemoryEntry]] = []
        
        for i, entry in enumerate(entries):
            if entry.entry_id in visited:
                continue
            
            cluster = [entry]
            visited.add(entry.entry_id)
            entry_sig = signatures[entry.entry_id]
            
            # 使用MinHash签名进行快速相似度计算
            for j, other in enumerate(entries):
                if other.entry_id in visited:
                    continue
                
                other_sig = signatures[other.entry_id]
                similarity = self._minhash_similarity(entry_sig, other_sig)
                
                # 如果MinHash相似度接近阈值，再使用精确相似度验证
                if similarity >= self._similarity_threshold * 0.8:
                    exact_similarity = self._compute_similarity(entry, other)
                    if exact_similarity >= self._similarity_threshold:
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
