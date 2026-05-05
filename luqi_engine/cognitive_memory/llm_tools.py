"""LLM工具模块 - 提供LLM相关的工具函数"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from luqi_engine.cognitive_memory.store import CognitiveMemoryStore
from luqi_engine.cognitive_memory.types import ConsolidationReport
from luqi_engine.core.config import CognitiveMemoryConfig


class MemoryToolProvider:
    def __init__(self, config: CognitiveMemoryConfig) -> None:
        self._config = config

    def memory_replace(self, store: CognitiveMemoryStore, entry_id: str, old_text: str, new_text: str) -> bool:
        entry = store.get_by_id(entry_id)
        if entry is None:
            return False
        if old_text in entry.what:
            entry.what = entry.what.replace(old_text, new_text)
            return True
        if old_text in entry.why:
            entry.why = entry.why.replace(old_text, new_text)
            return True
        return False

    def memory_insert(self, store: CognitiveMemoryStore, entry_id: str, new_text: str) -> bool:
        entry = store.get_by_id(entry_id)
        if entry is None:
            return False
        entry.what = f"{entry.what} {new_text}".strip()
        graph = store.get_graph()
        if graph is not None:
            from luqi_engine.cognitive_memory.types import MemoryNode
            import uuid
            graph.add_node(MemoryNode(
                node_id=f"insert_{uuid.uuid4().hex[:8]}",
                concept=new_text,
                node_type="event",
                temporal_start=entry.when,
            ))
        return True

    def memory_rethink(self, store: CognitiveMemoryStore, entry_id: str, new_summary: str) -> bool:
        entry = store.get_by_id(entry_id)
        if entry is None:
            return False
        if not entry.metadata:
            entry.metadata = {}
        entry.metadata["original_why"] = entry.why
        entry.why = new_summary
        return True

    def memory_search(self, store: CognitiveMemoryStore, query: str, limit: int = 0) -> List[Dict[str, Any]]:
        effective_limit = limit if limit > 0 else self._config.retrieval_limit
        entries = store.retrieve(query=query, limit=effective_limit)
        return [
            {
                "entry_id": e.entry_id,
                "who": e.who,
                "what": e.what,
                "when": e.when,
                "where": e.where,
                "why": e.why,
                "emotional_valence": e.emotional_valence,
                "importance": e.importance,
            }
            for e in entries
        ]

    def memory_consolidate(self, store: CognitiveMemoryStore) -> ConsolidationReport:
        from luqi_engine.cognitive_memory.consolidation import ConsolidationEngine
        from luqi_engine.cognitive_memory.retrieval import HybridRetriever

        retriever = HybridRetriever(self._config, store.get_graph())
        engine = ConsolidationEngine(self._config, retriever)

        long_term_entries = []
        for tier_attr in ("_long_term_tier", "_emotional_tier"):
            tier = getattr(store, tier_attr, None)
            if tier is not None:
                long_term_entries.extend(tier.all_entries())

        return engine.consolidate(long_term_entries, store.get_procedural_tier())

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "memory_replace",
                "description": "Replace text in a memory entry",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entry_id": {"type": "string"},
                        "old_text": {"type": "string"},
                        "new_text": {"type": "string"},
                    },
                    "required": ["entry_id", "old_text", "new_text"],
                },
            },
            {
                "name": "memory_insert",
                "description": "Insert new content into a memory entry",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entry_id": {"type": "string"},
                        "new_text": {"type": "string"},
                    },
                    "required": ["entry_id", "new_text"],
                },
            },
            {
                "name": "memory_rethink",
                "description": "Replace the summary of a memory entry with a new understanding",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entry_id": {"type": "string"},
                        "new_summary": {"type": "string"},
                    },
                    "required": ["entry_id", "new_summary"],
                },
            },
            {
                "name": "memory_search",
                "description": "Search for relevant memories",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memory_consolidate",
                "description": "Trigger memory consolidation (merge similar memories and extract procedural rules)",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]
