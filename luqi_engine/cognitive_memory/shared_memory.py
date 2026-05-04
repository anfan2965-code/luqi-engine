from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

from luqi_engine.cognitive_memory.types import SharedMemoryEntry
from luqi_engine.core.config import CognitiveMemoryConfig

_MEMORY_DB_IN_MEMORY = ":memory:"

_SQL_CREATE_SHARED_MEMORIES = (
    "CREATE TABLE IF NOT EXISTS shared_memories ("
    "entry_id TEXT PRIMARY KEY,"
    "content TEXT NOT NULL DEFAULT '{}',"
    "participant_ids TEXT NOT NULL DEFAULT '[]',"
    "contributing_agents TEXT NOT NULL DEFAULT '[]',"
    "accessed_resources TEXT NOT NULL DEFAULT '[]',"
    "creation_timestamp REAL NOT NULL DEFAULT 0.0,"
    "emotional_valence REAL NOT NULL DEFAULT 0.0)"
)

_SQL_INDEX_TIMESTAMP = (
    "CREATE INDEX IF NOT EXISTS idx_shared_timestamp ON shared_memories(creation_timestamp)"
)

_SQL_INSERT_SHARED = (
    "INSERT INTO shared_memories"
    " (entry_id, content, participant_ids, contributing_agents, accessed_resources,"
    "  creation_timestamp, emotional_valence)"
    " VALUES (?, ?, ?, ?, ?, ?, ?)"
    " ON CONFLICT(entry_id) DO UPDATE SET"
    " content = excluded.content,"
    " participant_ids = excluded.participant_ids,"
    " contributing_agents = excluded.contributing_agents,"
    " accessed_resources = excluded.accessed_resources,"
    " creation_timestamp = excluded.creation_timestamp,"
    " emotional_valence = excluded.emotional_valence"
)

_SQL_SELECT_BY_PARTICIPANT = (
    "SELECT entry_id, content, participant_ids, contributing_agents, accessed_resources,"
    " creation_timestamp, emotional_valence FROM shared_memories"
    " WHERE EXISTS (SELECT 1 FROM json_each(participant_ids) WHERE json_each.value = ?)"
)

_SQL_SELECT_BY_ID = (
    "SELECT entry_id, content, participant_ids, contributing_agents, accessed_resources,"
    " creation_timestamp, emotional_valence FROM shared_memories WHERE entry_id = ?"
)

_SQL_DELETE_BY_ID = "DELETE FROM shared_memories WHERE entry_id = ?"

_SQL_SELECT_TEMPORAL_BY_PARTICIPANT = (
    "SELECT entry_id, content, participant_ids, contributing_agents, accessed_resources,"
    " creation_timestamp, emotional_valence FROM shared_memories"
    " WHERE creation_timestamp >= ? AND creation_timestamp <= ?"
    " AND EXISTS (SELECT 1 FROM json_each(participant_ids) WHERE json_each.value = ?)"
)


def _extract_text_from_content(content: Dict[str, Any]) -> str:
    parts: List[str] = []
    for value in content.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
        elif isinstance(value, dict):
            parts.append(_extract_text_from_content(value))
    return " ".join(parts)


class SharedMemoryLayer:
    def __init__(self, config: CognitiveMemoryConfig) -> None:
        self._config = config
        effective_path = config.graph_db_path if config.graph_db_path else _MEMORY_DB_IN_MEMORY
        if effective_path != _MEMORY_DB_IN_MEMORY:
            dir_path = os.path.dirname(effective_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
        self._conn = sqlite3.connect(effective_path)
        self._conn.execute(_SQL_CREATE_SHARED_MEMORIES)
        self._conn.execute(_SQL_INDEX_TIMESTAMP)
        self._conn.commit()

    def store(self, entry: SharedMemoryEntry) -> None:
        self._conn.execute(
            _SQL_INSERT_SHARED,
            (
                entry.entry_id,
                json.dumps(entry.content),
                json.dumps(entry.participant_ids),
                json.dumps(entry.contributing_agents),
                json.dumps(entry.accessed_resources),
                entry.creation_timestamp,
                entry.emotional_valence,
            ),
        )
        self._conn.commit()

    def retrieve(self, character_id: str, query: str = "", limit: int = 0) -> List[SharedMemoryEntry]:
        effective_limit = limit if limit > 0 else self._config.retrieval_limit
        cursor = self._conn.execute(_SQL_SELECT_BY_PARTICIPANT, (character_id,))
        rows = cursor.fetchall()
        entries = [self._row_to_entry(row) for row in rows]
        if query:
            scored = [(self._text_match_score(e.content, query), e) for e in entries]
            scored.sort(key=lambda x: x[0], reverse=True)
            entries = [e for _, e in scored]
        return entries[:effective_limit]

    def retrieve_temporal(self, character_id: str, time_start: float, time_end: float,
                          query: str = "", limit: int = 0) -> List[SharedMemoryEntry]:
        effective_limit = limit if limit > 0 else self._config.retrieval_limit
        cursor = self._conn.execute(
            _SQL_SELECT_TEMPORAL_BY_PARTICIPANT,
            (time_start, time_end, character_id),
        )
        rows = cursor.fetchall()
        entries = [self._row_to_entry(row) for row in rows]
        if query:
            scored = [(self._text_match_score(e.content, query), e) for e in entries]
            scored.sort(key=lambda x: x[0], reverse=True)
            entries = [e for _, e in scored]
        return entries[:effective_limit]

    def get_by_id(self, entry_id: str) -> Optional[SharedMemoryEntry]:
        cursor = self._conn.execute(_SQL_SELECT_BY_ID, (entry_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def remove(self, entry_id: str) -> bool:
        cursor = self._conn.execute(_SQL_DELETE_BY_ID, (entry_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def get_participant_memories(self, character_id: str, limit: int = 0) -> List[SharedMemoryEntry]:
        effective_limit = limit if limit > 0 else self._config.retrieval_limit
        cursor = self._conn.execute(_SQL_SELECT_BY_PARTICIPANT, (character_id,))
        rows = cursor.fetchall()
        entries = [self._row_to_entry(row) for row in rows]
        return entries[:effective_limit]

    def close(self) -> None:
        self._conn.close()

    def _row_to_entry(self, row: tuple) -> SharedMemoryEntry:
        return SharedMemoryEntry(
            entry_id=row[0],
            content=json.loads(row[1]),
            participant_ids=json.loads(row[2]),
            contributing_agents=json.loads(row[3]),
            accessed_resources=json.loads(row[4]),
            creation_timestamp=row[5],
            emotional_valence=row[6],
        )

    def _text_match_score(self, content: Dict[str, Any], query: str) -> float:
        text = _extract_text_from_content(content)
        if not text or not query:
            return 0.0
        if text == query:
            return 1.0
        set_a = set(text.lower().split())
        set_b = set(query.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)
