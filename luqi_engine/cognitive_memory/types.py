from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

_COGNITIVE_MEMORY_KEY_SENSORY: str = "sensory"
_COGNITIVE_MEMORY_KEY_WORKING: str = "working"
_COGNITIVE_MEMORY_KEY_SHORT_TERM: str = "short_term"
_COGNITIVE_MEMORY_KEY_LONG_TERM: str = "long_term"
_COGNITIVE_MEMORY_KEY_EMOTIONAL: str = "emotional"
_COGNITIVE_MEMORY_KEY_PROCEDURAL: str = "procedural"

_MEMORY_NODE_DEFAULT_IMPORTANCE: float = 0.5
_TEMPORAL_START_EPOCH: float = 0.0
_TEMPORAL_END_UNBOUNDED: float = float("inf")
_MEMORY_EDGE_DEFAULT_STRENGTH: float = 1.0
_VALID_FROM_EPOCH: float = 0.0
_VALID_UNTIL_UNBOUNDED: float = float("inf")
_CREATION_TIMESTAMP_EPOCH: float = 0.0
_PROCEDURAL_RULE_DEFAULT_PRIORITY: float = 0.5
_PROCEDURAL_RULE_DEFAULT_SUCCESS_COUNT: int = 0
_PROCEDURAL_RULE_DEFAULT_TOTAL_COUNT: int = 0
_PROCEDURAL_RULE_DEFAULT_SUCCESS_RATE: float = 0.0
_MEMORY_MODULE_DEFAULT_LOADED: bool = False
_MEMORY_MODULE_DEFAULT_ACCESS_TIME: float = 0.0


class CognitiveMemoryType(Enum):
    SENSORY = auto()
    WORKING = auto()
    SHORT_TERM = auto()
    LONG_TERM = auto()
    EMOTIONAL = auto()
    PROCEDURAL = auto()

    @property
    def storage_key(self) -> str:
        mapping = {
            CognitiveMemoryType.SENSORY: _COGNITIVE_MEMORY_KEY_SENSORY,
            CognitiveMemoryType.WORKING: _COGNITIVE_MEMORY_KEY_WORKING,
            CognitiveMemoryType.SHORT_TERM: _COGNITIVE_MEMORY_KEY_SHORT_TERM,
            CognitiveMemoryType.LONG_TERM: _COGNITIVE_MEMORY_KEY_LONG_TERM,
            CognitiveMemoryType.EMOTIONAL: _COGNITIVE_MEMORY_KEY_EMOTIONAL,
            CognitiveMemoryType.PROCEDURAL: _COGNITIVE_MEMORY_KEY_PROCEDURAL,
        }
        return mapping[self]


@dataclass
class MemoryNode:
    node_id: str
    concept: str
    node_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    temporal_start: float = _TEMPORAL_START_EPOCH
    temporal_end: float = _TEMPORAL_END_UNBOUNDED
    importance: float = _MEMORY_NODE_DEFAULT_IMPORTANCE
    embedding: Optional[List[float]] = None


@dataclass
class MemoryEdge:
    edge_id: str
    source_id: str
    target_id: str
    relation: str
    strength: float = _MEMORY_EDGE_DEFAULT_STRENGTH
    valid_from: float = _VALID_FROM_EPOCH
    valid_until: float = _VALID_UNTIL_UNBOUNDED


@dataclass
class SharedMemoryEntry:
    entry_id: str
    content: Dict[str, Any] = field(default_factory=dict)
    participant_ids: List[str] = field(default_factory=list)
    contributing_agents: List[str] = field(default_factory=list)
    accessed_resources: List[str] = field(default_factory=list)
    creation_timestamp: float = _CREATION_TIMESTAMP_EPOCH
    emotional_valence: float = 0.0


@dataclass
class ProceduralRule:
    rule_id: str
    condition: str = ""
    action: str = ""
    priority: float = _PROCEDURAL_RULE_DEFAULT_PRIORITY
    success_count: int = _PROCEDURAL_RULE_DEFAULT_SUCCESS_COUNT
    total_count: int = _PROCEDURAL_RULE_DEFAULT_TOTAL_COUNT
    success_rate: float = _PROCEDURAL_RULE_DEFAULT_SUCCESS_RATE
    derived_from: List[str] = field(default_factory=list)


@dataclass
class MemoryModule:
    module_id: str
    character_id: str
    store: Optional[Any] = None
    graph: Optional[Any] = None
    procedural_rules: List[ProceduralRule] = field(default_factory=list)
    is_loaded: bool = _MEMORY_MODULE_DEFAULT_LOADED
    last_access_time: float = _MEMORY_MODULE_DEFAULT_ACCESS_TIME


@dataclass
class SurpriseResult:
    surprise: float
    target_tier: CognitiveMemoryType
    importance: float


@dataclass
class RetrievalResult:
    entries: List = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    source: str = ""


@dataclass
class ConsolidationReport:
    merged_count: int = 0
    extracted_rules: int = 0
    freed_entries: int = 0
