from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from luqi_engine.cognitive_memory.types import MemoryModule, ProceduralRule
from luqi_engine.core.config import CognitiveMemoryConfig

_MODULE_CACHE_DIR_NAME: str = "memory_modules"
_MODULE_STORE_FILE: str = "store.json"
_MODULE_RULES_FILE: str = "rules.json"


class MemoryModuleManager:
    def __init__(self, config: CognitiveMemoryConfig) -> None:
        self._config = config
        self._modules: Dict[str, MemoryModule] = {}
        self._idle_timestamps: Dict[str, float] = {}
        self._cache_dir: str = ""

    def load_module(self, character_id: str) -> MemoryModule:
        if character_id in self._modules:
            module = self._modules[character_id]
            module.last_access_time = time.time()
            self._idle_timestamps[character_id] = time.time()
            return module

        cache_path = self._get_cache_dir(character_id)
        module = self._deserialize_module(character_id, cache_path)
        if module is None:
            module = MemoryModule(
                module_id=f"mod_{character_id}",
                character_id=character_id,
                store=None,
                graph=None,
                procedural_rules=[],
                is_loaded=True,
                last_access_time=time.time(),
            )

        module.is_loaded = True
        module.last_access_time = time.time()
        self._modules[character_id] = module
        self._idle_timestamps[character_id] = time.time()
        return module

    def unload_module(self, character_id: str) -> None:
        if character_id not in self._modules:
            return
        module = self._modules[character_id]
        cache_path = self._get_cache_dir(character_id)
        self._serialize_module(module, cache_path)
        module.is_loaded = False
        del self._modules[character_id]
        self._idle_timestamps.pop(character_id, None)

    def switch_module(self, from_character_id: str, to_character_id: str) -> None:
        self.unload_module(from_character_id)
        self.load_module(to_character_id)

    def get_module(self, character_id: str) -> Optional[MemoryModule]:
        return self._modules.get(character_id)

    def check_idle_modules(self) -> int:
        now = time.time()
        unloaded = 0
        to_unload: List[str] = []
        for cid, last_access in self._idle_timestamps.items():
            if now - last_access >= self._config.module_idle_timeout_seconds:
                to_unload.append(cid)
        for cid in to_unload:
            self.unload_module(cid)
            unloaded += 1
        return unloaded

    def _serialize_module(self, module: MemoryModule, path: str) -> None:
        os.makedirs(path, exist_ok=True)

        store_data: Dict[str, Any] = {}
        if module.store is not None:
            from luqi_engine.cognitive_memory.tiers import (
                SensoryTier, WorkingTier, ShortTermTier, LongTermTier, ProceduralTier
            )
            for tier_name in ("sensory", "working", "short_term", "long_term", "emotional"):
                tier = getattr(module.store, f"_{tier_name}_tier", None)
                if tier is not None:
                    entries_data = []
                    for entry in tier.all_entries():
                        entries_data.append({
                            "who": entry.who,
                            "what": entry.what,
                            "when": entry.when,
                            "where": entry.where,
                            "why": entry.why,
                            "memory_type": entry.memory_type.storage_key,
                            "emotional_valence": entry.emotional_valence,
                            "importance": entry.importance,
                            "access_count": entry.access_count,
                            "entry_id": entry.entry_id,
                        })
                    store_data[tier_name] = entries_data

        store_path = os.path.join(path, _MODULE_STORE_FILE)
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(store_data, f, ensure_ascii=False)

        rules_data = []
        for rule in module.procedural_rules:
            rules_data.append({
                "rule_id": rule.rule_id,
                "condition": rule.condition,
                "action": rule.action,
                "priority": rule.priority,
                "success_count": rule.success_count,
                "total_count": rule.total_count,
                "success_rate": rule.success_rate,
                "derived_from": rule.derived_from,
            })
        rules_path = os.path.join(path, _MODULE_RULES_FILE)
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, ensure_ascii=False)

    def _deserialize_module(self, character_id: str, path: str) -> Optional[MemoryModule]:
        store_path = os.path.join(path, _MODULE_STORE_FILE)
        rules_path = os.path.join(path, _MODULE_RULES_FILE)

        if not os.path.exists(store_path) and not os.path.exists(rules_path):
            return None

        from luqi_engine.character.memory import MemoryEntry, MemoryType as LegacyMemoryType

        store = None
        if os.path.exists(store_path):
            from luqi_engine.cognitive_memory.store import CognitiveMemoryStore
            store = CognitiveMemoryStore(self._config)
            with open(store_path, "r", encoding="utf-8") as f:
                store_data = json.load(f)
            type_map = {
                "short_term": LegacyMemoryType.SHORT_TERM,
                "long_term": LegacyMemoryType.LONG_TERM,
                "emotional": LegacyMemoryType.EMOTIONAL,
            }
            for tier_name, entries_data in store_data.items():
                mtype = type_map.get(tier_name, LegacyMemoryType.SHORT_TERM)
                for ed in entries_data:
                    entry = MemoryEntry(
                        who=ed.get("who", ""),
                        what=ed.get("what", ""),
                        when=ed.get("when", 0.0),
                        where=ed.get("where", ""),
                        why=ed.get("why", ""),
                        memory_type=mtype,
                        emotional_valence=ed.get("emotional_valence", 0.0),
                        importance=ed.get("importance", 0.5),
                        access_count=ed.get("access_count", 0),
                        entry_id=ed.get("entry_id", ""),
                    )
                    store.store(entry)

        rules: List[ProceduralRule] = []
        if os.path.exists(rules_path):
            with open(rules_path, "r", encoding="utf-8") as f:
                rules_data = json.load(f)
            for rd in rules_data:
                rules.append(ProceduralRule(
                    rule_id=rd.get("rule_id", ""),
                    condition=rd.get("condition", ""),
                    action=rd.get("action", ""),
                    priority=rd.get("priority", 0.5),
                    success_count=rd.get("success_count", 0),
                    total_count=rd.get("total_count", 0),
                    success_rate=rd.get("success_rate", 0.0),
                    derived_from=rd.get("derived_from", []),
                ))

        return MemoryModule(
            module_id=f"mod_{character_id}",
            character_id=character_id,
            store=store,
            graph=None,
            procedural_rules=rules,
            is_loaded=False,
            last_access_time=0.0,
        )

    def _get_cache_dir(self, character_id: str) -> str:
        if not self._cache_dir:
            if self._config.graph_db_path:
                self._cache_dir = os.path.dirname(self._config.graph_db_path)
            else:
                import tempfile
                self._cache_dir = tempfile.gettempdir()
        return os.path.join(self._cache_dir, _MODULE_CACHE_DIR_NAME, character_id)
