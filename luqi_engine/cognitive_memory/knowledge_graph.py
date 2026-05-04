from __future__ import annotations

import json
import os
import sqlite3
import struct
from typing import Dict, List, Optional, Tuple

from luqi_engine.cognitive_memory.types import MemoryEdge, MemoryNode

_MEMORY_DB_IN_MEMORY = ":memory:"
_STRUCT_DOUBLE_SIZE = 8
_STRUCT_ENDIAN_PREFIX = "<"
_SQL_LIKE_ESCAPE_CHAR = "!"
_MAX_SEARCH_WORDS = 10

_SQL_CREATE_NODES = (
    "CREATE TABLE IF NOT EXISTS memory_nodes ("
    "node_id TEXT PRIMARY KEY,"
    "concept TEXT NOT NULL,"
    "node_type TEXT NOT NULL,"
    "properties TEXT NOT NULL DEFAULT '{}',"
    "temporal_start REAL NOT NULL DEFAULT 0.0,"
    "temporal_end REAL NOT NULL,"
    "importance REAL NOT NULL DEFAULT 0.5,"
    "embedding BLOB)"
)

_SQL_CREATE_EDGES = (
    "CREATE TABLE IF NOT EXISTS memory_edges ("
    "edge_id TEXT PRIMARY KEY,"
    "source_id TEXT NOT NULL,"
    "target_id TEXT NOT NULL,"
    "relation TEXT NOT NULL,"
    "strength REAL NOT NULL DEFAULT 1.0,"
    "valid_from REAL NOT NULL DEFAULT 0.0,"
    "valid_until REAL NOT NULL,"
    "FOREIGN KEY (source_id) REFERENCES memory_nodes(node_id) ON DELETE CASCADE,"
    "FOREIGN KEY (target_id) REFERENCES memory_nodes(node_id) ON DELETE CASCADE)"
)

_SQL_INDEX_EDGE_SOURCE = (
    "CREATE INDEX IF NOT EXISTS idx_edges_source ON memory_edges(source_id)"
)

_SQL_INDEX_EDGE_TARGET = (
    "CREATE INDEX IF NOT EXISTS idx_edges_target ON memory_edges(target_id)"
)

_SQL_INDEX_NODE_TYPE = (
    "CREATE INDEX IF NOT EXISTS idx_nodes_type ON memory_nodes(node_type)"
)

_SQL_PRAGMA_FOREIGN_KEYS = "PRAGMA foreign_keys = ON"

_SQL_INSERT_NODE = (
    "INSERT INTO memory_nodes"
    " (node_id, concept, node_type, properties, temporal_start, temporal_end, importance, embedding)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    " ON CONFLICT(node_id) DO UPDATE SET"
    " concept = excluded.concept,"
    " node_type = excluded.node_type,"
    " properties = excluded.properties,"
    " temporal_start = excluded.temporal_start,"
    " temporal_end = excluded.temporal_end,"
    " importance = excluded.importance,"
    " embedding = excluded.embedding"
)

_SQL_INSERT_EDGE = (
    "INSERT INTO memory_edges"
    " (edge_id, source_id, target_id, relation, strength, valid_from, valid_until)"
    " VALUES (?, ?, ?, ?, ?, ?, ?)"
    " ON CONFLICT(edge_id) DO UPDATE SET"
    " source_id = excluded.source_id,"
    " target_id = excluded.target_id,"
    " relation = excluded.relation,"
    " strength = excluded.strength,"
    " valid_from = excluded.valid_from,"
    " valid_until = excluded.valid_until"
)

_SQL_SELECT_NODE = (
    "SELECT node_id, concept, node_type, properties, temporal_start, temporal_end,"
    " importance, embedding FROM memory_nodes WHERE node_id = ?"
)

_SQL_DELETE_NODE = "DELETE FROM memory_nodes WHERE node_id = ?"

_SQL_DELETE_EDGE = "DELETE FROM memory_edges WHERE edge_id = ?"

_SQL_SELECT_EDGES_FROM = (
    "SELECT edge_id, source_id, target_id, relation, strength, valid_from, valid_until"
    " FROM memory_edges WHERE source_id = ?"
)

_SQL_SELECT_EDGES_TO = (
    "SELECT edge_id, source_id, target_id, relation, strength, valid_from, valid_until"
    " FROM memory_edges WHERE target_id = ?"
)

_SQL_SELECT_TEMPORAL = (
    "SELECT node_id, concept, node_type, properties, temporal_start, temporal_end,"
    " importance, embedding FROM memory_nodes"
    " WHERE temporal_start <= ? AND temporal_end >= ?"
)

_SQL_SELECT_TEMPORAL_BY_TYPE = (
    "SELECT node_id, concept, node_type, properties, temporal_start, temporal_end,"
    " importance, embedding FROM memory_nodes"
    " WHERE temporal_start <= ? AND temporal_end >= ? AND node_type = ?"
)

_SQL_EXPAND_OUTGOING = (
    "SELECT e.edge_id, e.source_id, e.target_id, e.relation, e.strength,"
    " e.valid_from, e.valid_until,"
    " n.node_id, n.concept, n.node_type, n.properties, n.temporal_start,"
    " n.temporal_end, n.importance, n.embedding"
    " FROM memory_edges e"
    " INNER JOIN memory_nodes n ON e.target_id = n.node_id"
    " WHERE e.source_id = ?"
)

_SQL_EXPAND_INCOMING = (
    "SELECT e.edge_id, e.source_id, e.target_id, e.relation, e.strength,"
    " e.valid_from, e.valid_until,"
    " n.node_id, n.concept, n.node_type, n.properties, n.temporal_start,"
    " n.temporal_end, n.importance, n.embedding"
    " FROM memory_edges e"
    " INNER JOIN memory_nodes n ON e.source_id = n.node_id"
    " WHERE e.target_id = ?"
)

_SQL_SEARCH_NODES = (
    "SELECT node_id, concept, node_type, properties, temporal_start, temporal_end,"
    " importance, embedding FROM memory_nodes WHERE concept LIKE ? ESCAPE ?"
)

_SQL_COUNT_NODES = "SELECT COUNT(*) FROM memory_nodes"

_SQL_COUNT_EDGES = "SELECT COUNT(*) FROM memory_edges"


def _pack_embedding(embedding: Optional[List[float]]) -> Optional[bytes]:
    if embedding is None or len(embedding) == 0:
        return None
    fmt = f"{_STRUCT_ENDIAN_PREFIX}{len(embedding)}d"
    return struct.pack(fmt, *embedding)


def _unpack_embedding(blob: Optional[bytes]) -> Optional[List[float]]:
    if blob is None or len(blob) == 0:
        return None
    count = len(blob) // _STRUCT_DOUBLE_SIZE
    fmt = f"{_STRUCT_ENDIAN_PREFIX}{count}d"
    return list(struct.unpack(fmt, blob))


def _escape_like_pattern(pattern: str) -> str:
    return (
        pattern
        .replace(_SQL_LIKE_ESCAPE_CHAR, _SQL_LIKE_ESCAPE_CHAR * 2)
        .replace("%", f"{_SQL_LIKE_ESCAPE_CHAR}%")
        .replace("_", f"{_SQL_LIKE_ESCAPE_CHAR}_")
    )


def _concept_similarity(concept: str, query: str) -> float:
    if not concept or not query:
        return 0.0
    if concept == query:
        return 1.0
    set_a = set(concept.lower().split())
    set_b = set(query.lower().split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


class MemoryGraph:
    def __init__(self, db_path: str = "") -> None:
        effective_path = db_path if db_path else _MEMORY_DB_IN_MEMORY
        if effective_path != _MEMORY_DB_IN_MEMORY:
            dir_path = os.path.dirname(effective_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
        self._conn = sqlite3.connect(effective_path)
        self._conn.execute(_SQL_PRAGMA_FOREIGN_KEYS)
        self._conn.execute(_SQL_CREATE_NODES)
        self._conn.execute(_SQL_CREATE_EDGES)
        self._conn.execute(_SQL_INDEX_EDGE_SOURCE)
        self._conn.execute(_SQL_INDEX_EDGE_TARGET)
        self._conn.execute(_SQL_INDEX_NODE_TYPE)
        self._conn.commit()

    def add_node(self, node: MemoryNode) -> None:
        props_json = json.dumps(node.properties)
        embedding_blob = _pack_embedding(node.embedding)
        self._conn.execute(
            _SQL_INSERT_NODE,
            (
                node.node_id,
                node.concept,
                node.node_type,
                props_json,
                node.temporal_start,
                node.temporal_end,
                node.importance,
                embedding_blob,
            ),
        )
        self._conn.commit()

    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        cursor = self._conn.execute(_SQL_SELECT_NODE, (node_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def remove_node(self, node_id: str) -> bool:
        cursor = self._conn.execute(_SQL_DELETE_NODE, (node_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def add_edge(self, edge: MemoryEdge) -> None:
        self._conn.execute(
            _SQL_INSERT_EDGE,
            (
                edge.edge_id,
                edge.source_id,
                edge.target_id,
                edge.relation,
                edge.strength,
                edge.valid_from,
                edge.valid_until,
            ),
        )
        self._conn.commit()

    def remove_edge(self, edge_id: str) -> bool:
        cursor = self._conn.execute(_SQL_DELETE_EDGE, (edge_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def get_edges_from(self, node_id: str) -> List[MemoryEdge]:
        cursor = self._conn.execute(_SQL_SELECT_EDGES_FROM, (node_id,))
        return [self._row_to_edge(row) for row in cursor.fetchall()]

    def get_edges_to(self, node_id: str) -> List[MemoryEdge]:
        cursor = self._conn.execute(_SQL_SELECT_EDGES_TO, (node_id,))
        return [self._row_to_edge(row) for row in cursor.fetchall()]

    def query_temporal(
        self, time_start: float, time_end: float, node_type: str = ""
    ) -> List[MemoryNode]:
        if node_type:
            cursor = self._conn.execute(
                _SQL_SELECT_TEMPORAL_BY_TYPE, (time_end, time_start, node_type)
            )
        else:
            cursor = self._conn.execute(
                _SQL_SELECT_TEMPORAL, (time_end, time_start)
            )
        return [self._row_to_node(row) for row in cursor.fetchall()]

    def expand_one_hop(
        self, node_id: str
    ) -> List[Tuple[MemoryEdge, MemoryNode]]:
        results: List[Tuple[MemoryEdge, MemoryNode]] = []
        cursor = self._conn.execute(_SQL_EXPAND_OUTGOING, (node_id,))
        for row in cursor.fetchall():
            edge = self._row_to_edge(row[:7])
            node = self._row_to_node(row[7:])
            results.append((edge, node))
        cursor = self._conn.execute(_SQL_EXPAND_INCOMING, (node_id,))
        for row in cursor.fetchall():
            edge = self._row_to_edge(row[:7])
            node = self._row_to_node(row[7:])
            results.append((edge, node))
        return results

    def search_nodes(self, query: str, limit: int) -> List[MemoryNode]:
        words = query.split()[:_MAX_SEARCH_WORDS]
        if not words:
            return []
        candidates: Dict[str, MemoryNode] = {}
        for word in words:
            escaped = _escape_like_pattern(word)
            cursor = self._conn.execute(
                _SQL_SEARCH_NODES,
                (f"%{escaped}%", _SQL_LIKE_ESCAPE_CHAR),
            )
            for row in cursor.fetchall():
                node = self._row_to_node(row)
                candidates[node.node_id] = node
        scored: List[Tuple[float, MemoryNode]] = []
        for node in candidates.values():
            score = _concept_similarity(node.concept, query) * node.importance
            scored.append((score, node))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in scored[:limit]]

    def node_count(self) -> int:
        cursor = self._conn.execute(_SQL_COUNT_NODES)
        return cursor.fetchone()[0]

    def edge_count(self) -> int:
        cursor = self._conn.execute(_SQL_COUNT_EDGES)
        return cursor.fetchone()[0]

    def close(self) -> None:
        self._conn.close()

    def _row_to_node(self, row: tuple) -> MemoryNode:
        return MemoryNode(
            node_id=row[0],
            concept=row[1],
            node_type=row[2],
            properties=json.loads(row[3]),
            temporal_start=row[4],
            temporal_end=row[5],
            importance=row[6],
            embedding=_unpack_embedding(row[7]),
        )

    def _row_to_edge(self, row: tuple) -> MemoryEdge:
        return MemoryEdge(
            edge_id=row[0],
            source_id=row[1],
            target_id=row[2],
            relation=row[3],
            strength=row[4],
            valid_from=row[5],
            valid_until=row[6],
        )
