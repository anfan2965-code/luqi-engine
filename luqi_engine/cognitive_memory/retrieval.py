from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from luqi_engine.character.memory import MemoryEntry
from luqi_engine.cognitive_memory.types import MemoryNode, RetrievalResult
from luqi_engine.core.config import CognitiveMemoryConfig

if TYPE_CHECKING:
    from luqi_engine.cognitive_memory.knowledge_graph import MemoryGraph

_BM25_K1: float = 1.5
_BM25_B: float = 0.75


class HybridRetriever:
    def __init__(self, config: CognitiveMemoryConfig, graph: Optional[MemoryGraph] = None) -> None:
        self._config = config
        self._graph = graph
        self._vector_available: bool = False
        self._vector_model = None
        self._bm25_weight = config.retrieval_bm25_weight
        self._vector_weight = config.retrieval_vector_weight
        self._graph_weight = config.retrieval_graph_weight

    def retrieve(self, query: str, entries: List[MemoryEntry], limit: int = 0) -> RetrievalResult:
        effective_limit = limit if limit > 0 else self._config.retrieval_limit
        bm25_results = self._bm25_search(query, entries, effective_limit)
        vector_results = self._vector_search(query, entries, effective_limit)
        graph_results = self._graph_search(query, effective_limit)

        score_map: Dict[str, float] = {}
        all_ids: set = set()
        for eid, score in bm25_results:
            score_map[eid] = score_map.get(eid, 0.0) + self._bm25_weight * score
            all_ids.add(eid)
        for eid, score in vector_results:
            score_map[eid] = score_map.get(eid, 0.0) + self._vector_weight * score
            all_ids.add(eid)
        for nid, score in graph_results:
            score_map[nid] = score_map.get(nid, 0.0) + self._graph_weight * score
            all_ids.add(nid)

        sorted_ids = sorted(all_ids, key=lambda x: score_map.get(x, 0.0), reverse=True)[:effective_limit]

        entry_map = {e.entry_id: e for e in entries}
        result_entries = [entry_map[eid] for eid in sorted_ids if eid in entry_map]
        result_scores = [score_map[eid] for eid in sorted_ids if eid in entry_map]

        return RetrievalResult(entries=result_entries, scores=result_scores, source="hybrid")

    def embed(self, text: str) -> List[float]:
        if not self._vector_available:
            self._load_vector_model()
        if not self._vector_available or self._vector_model is None:
            return []
        try:
            embedding = self._vector_model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception:
            return []

    def _bm25_search(self, query: str, entries: List[MemoryEntry], limit: int) -> List[Tuple[str, float]]:
        if not entries:
            return []
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        N = len(entries)
        df: Dict[str, int] = {}
        for entry in entries:
            doc_tokens = set(self._tokenize(f"{entry.what} {entry.who} {entry.where} {entry.why}"))
            for token in doc_tokens:
                df[token] = df.get(token, 0) + 1

        scored: List[Tuple[str, float]] = []
        total_doc_len = 0
        for entry in entries:
            total_doc_len += len(self._tokenize(f"{entry.what} {entry.who} {entry.where} {entry.why}"))
        avg_dl = total_doc_len / max(N, 1)

        for entry in entries:
            doc_text = f"{entry.what} {entry.who} {entry.where} {entry.why}"
            doc_tokens = self._tokenize(doc_text)
            doc_len = len(doc_tokens)

            tf_map: Dict[str, int] = {}
            for t in doc_tokens:
                tf_map[t] = tf_map.get(t, 0) + 1

            score = 0.0
            for qt in query_tokens:
                if qt not in df:
                    continue
                idf = math.log((N - df[qt] + 0.5) / (df[qt] + 0.5) + 1.0)
                tf = tf_map.get(qt, 0)
                tf_norm = (tf * (_BM25_K1 + 1)) / (tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_len / max(avg_dl, 1)))
                score += idf * tf_norm

            if score > 0:
                scored.append((entry.entry_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _vector_search(self, query: str, entries: List[MemoryEntry], limit: int) -> List[Tuple[str, float]]:
        query_emb = self.embed(query)
        if not query_emb:
            return []

        scored: List[Tuple[str, float]] = []
        for entry in entries:
            if not entry.metadata:
                continue
            entry_emb = entry.metadata.get("embedding")
            if entry_emb is None:
                continue
            sim = self._cosine_similarity(query_emb, entry_emb)
            if sim > 0:
                scored.append((entry.entry_id, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _graph_search(self, query: str, limit: int) -> List[Tuple[str, float]]:
        if self._graph is None:
            return []
        matched_nodes = self._graph.search_nodes(query, limit=limit)
        if not matched_nodes:
            return []

        scored: List[Tuple[str, float]] = []
        seen: set = set()
        for node in matched_nodes:
            if node.node_id not in seen:
                scored.append((node.node_id, 1.0))
                seen.add(node.node_id)
            expanded = self._graph.expand_one_hop(node.node_id)
            for edge, target in expanded:
                if target.node_id not in seen:
                    scored.append((target.node_id, edge.strength))
                    seen.add(target.node_id)

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _load_vector_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            model_path = self._config.vector_model_path
            model_name = self._config.vector_model_name
            if model_path:
                self._vector_model = SentenceTransformer(model_path)
            else:
                self._vector_model = SentenceTransformer(model_name)
            self._vector_available = True
        except Exception:
            self._vector_available = False
            self._vector_model = None

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a < 1e-9 or norm_b < 1e-9:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        if not text:
            return []
        tokens: List[str] = []
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                tokens.append(char)
            elif char.isalnum():
                tokens.append(char.lower())
        if not tokens:
            tokens = text.lower().split()
        return tokens
