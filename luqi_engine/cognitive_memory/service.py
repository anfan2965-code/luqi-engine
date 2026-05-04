from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from luqi_engine.cognitive_memory.consolidation import ConsolidationEngine
from luqi_engine.cognitive_memory.knowledge_graph import MemoryGraph
from luqi_engine.cognitive_memory.llm_tools import MemoryToolProvider
from luqi_engine.cognitive_memory.module import MemoryModuleManager
from luqi_engine.cognitive_memory.retrieval import HybridRetriever
from luqi_engine.cognitive_memory.shared_memory import SharedMemoryLayer
from luqi_engine.cognitive_memory.store import CognitiveMemoryStore
from luqi_engine.cognitive_memory.types import ConsolidationReport, CognitiveMemoryType, SharedMemoryEntry
from luqi_engine.character.memory import MemoryEntry
from luqi_engine.core.config import CognitiveMemoryConfig


class MemoryService:
    def __init__(self, config: Optional[CognitiveMemoryConfig] = None) -> None:
        self._config = config if config is not None else CognitiveMemoryConfig()
        self._stores: Dict[str, CognitiveMemoryStore] = {}
        self._retriever = HybridRetriever(self._config)
        self._consolidation = ConsolidationEngine(self._config, self._retriever)
        self._shared_memory = SharedMemoryLayer(self._config) if self._config.shared_memory_enabled else None
        self._module_manager = MemoryModuleManager(self._config)
        self._tool_provider = MemoryToolProvider(self._config)
        self._graph: Optional[MemoryGraph] = None
        self._last_consolidation: float = 0.0

    def get_or_create_store(self, character_id: str) -> CognitiveMemoryStore:
        if character_id not in self._stores:
            store = CognitiveMemoryStore(self._config)
            if self._graph is None:
                self._graph = MemoryGraph(self._config.graph_db_path)
            store.set_graph(self._graph)
            self._stores[character_id] = store
        return self._stores[character_id]

    def write_agent(self, character_id: str, entry: MemoryEntry, target_type: Optional[CognitiveMemoryType] = None) -> Dict[str, Any]:
        store = self.get_or_create_store(character_id)
        surprise_result = store.store(entry, target_type)

        existing = store.retrieve(query=entry.what, limit=5)
        merged_entry = None
        if existing:
            merged_entry = self._consolidation.try_online_synthesis(entry, existing)
            if merged_entry is not None:
                store.store(merged_entry, CognitiveMemoryType.LONG_TERM)

        self._try_auto_consolidation(store)

        return {
            "surprise": surprise_result.surprise,
            "target_tier": surprise_result.target_tier.storage_key,
            "importance": surprise_result.importance,
            "merged": merged_entry is not None,
        }

    def retrieval_agent(self, character_id: str, query: str, limit: int = 0) -> List[Dict[str, Any]]:
        store = self.get_or_create_store(character_id)
        effective_limit = limit if limit > 0 else self._config.retrieval_limit

        all_entries = []
        for tier_attr in ("_working_tier", "_short_term_tier", "_long_term_tier", "_emotional_tier"):
            tier = getattr(store, tier_attr, None)
            if tier is not None:
                all_entries.extend(tier.all_entries())

        result = self._retriever.retrieve(query, all_entries, effective_limit)

        output = []
        for entry, score in zip(result.entries, result.scores):
            output.append({
                "entry_id": entry.entry_id,
                "who": entry.who,
                "what": entry.what,
                "when": entry.when,
                "where": entry.where,
                "why": entry.why,
                "emotional_valence": entry.emotional_valence,
                "importance": entry.importance,
                "retrieval_score": score,
            })

        if self._shared_memory is not None:
            shared = self._shared_memory.retrieve(character_id, query, effective_limit)
            for se in shared:
                output.append({
                    "entry_id": se.entry_id,
                    "who": "shared",
                    "what": str(se.content),
                    "when": se.creation_timestamp,
                    "where": "",
                    "why": "shared_event",
                    "emotional_valence": se.emotional_valence,
                    "importance": 0.5,
                    "retrieval_score": 0.0,
                    "shared": True,
                })

        return output

    def consolidation_agent(self, character_id: str) -> ConsolidationReport:
        store = self.get_or_create_store(character_id)
        long_term_entries = []
        for tier_attr in ("_long_term_tier", "_emotional_tier"):
            tier = getattr(store, tier_attr, None)
            if tier is not None:
                long_term_entries.extend(tier.all_entries())
        return self._consolidation.consolidate(long_term_entries, store.get_procedural_tier())

    def store_shared_memory(self, event_id: str, content: Dict[str, Any], participant_ids: List[str], emotional_valence: float = 0.0) -> None:
        if self._shared_memory is None:
            return
        entry = SharedMemoryEntry(
            entry_id=event_id,
            content=content,
            participant_ids=participant_ids,
            contributing_agents=participant_ids[:],
            creation_timestamp=time.time(),
            emotional_valence=emotional_valence,
        )
        self._shared_memory.store(entry)

    def retrieve_temporal(self, character_id: str, time_start: float, time_end: float, query: str = "", limit: int = 0) -> List[Dict[str, Any]]:
        store = self.get_or_create_store(character_id)
        effective_limit = limit if limit > 0 else self._config.retrieval_limit
        results = []

        if store.get_graph() is not None:
            nodes = store.get_graph().query_temporal(time_start, time_end)
            for node in nodes[:effective_limit]:
                results.append({
                    "node_id": node.node_id,
                    "concept": node.concept,
                    "node_type": node.node_type,
                    "importance": node.importance,
                })

        if self._shared_memory is not None:
            shared = self._shared_memory.retrieve_temporal(character_id, time_start, time_end, query, effective_limit)
            for se in shared:
                results.append({
                    "entry_id": se.entry_id,
                    "content": se.content,
                    "shared": True,
                })

        return results

    def memory_tool_call(self, character_id: str, tool_name: str, params: Dict[str, Any]) -> Any:
        store = self.get_or_create_store(character_id)
        if tool_name == "memory_replace":
            return self._tool_provider.memory_replace(store, params.get("entry_id", ""), params.get("old_text", ""), params.get("new_text", ""))
        elif tool_name == "memory_insert":
            return self._tool_provider.memory_insert(store, params.get("entry_id", ""), params.get("new_text", ""))
        elif tool_name == "memory_rethink":
            return self._tool_provider.memory_rethink(store, params.get("entry_id", ""), params.get("new_summary", ""))
        elif tool_name == "memory_search":
            return self._tool_provider.memory_search(store, params.get("query", ""), params.get("limit", 0))
        elif tool_name == "memory_consolidate":
            return self._tool_provider.memory_consolidate(store)
        return None

    def load_memory_module(self, character_id: str) -> None:
        module = self._module_manager.load_module(character_id)
        if module.store is not None:
            self._stores[character_id] = module.store

    def unload_memory_module(self, character_id: str) -> None:
        if character_id in self._stores:
            module = self._module_manager.get_module(character_id)
            if module is None:
                from luqi_engine.cognitive_memory.types import MemoryModule
                module = MemoryModule(
                    module_id=f"mod_{character_id}",
                    character_id=character_id,
                    store=self._stores[character_id],
                    graph=self._stores[character_id].get_graph(),
                    is_loaded=True,
                    last_access_time=time.time(),
                )
                self._module_manager._modules[character_id] = module
            else:
                module.store = self._stores[character_id]
            self._module_manager.unload_module(character_id)
            del self._stores[character_id]

    def decay_all(self) -> None:
        for store in self._stores.values():
            store.decay()

    def _try_auto_consolidation(self, store: CognitiveMemoryStore) -> None:
        now = time.time()
        if now - self._last_consolidation < self._config.consolidation_interval_seconds:
            return
        self._last_consolidation = now
        long_term_entries = []
        for tier_attr in ("_long_term_tier", "_emotional_tier"):
            tier = getattr(store, tier_attr, None)
            if tier is not None:
                long_term_entries.extend(tier.all_entries())
        self._consolidation.consolidate(long_term_entries, store.get_procedural_tier())
