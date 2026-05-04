"""
核心基础模块 - 定义引擎级别的数据类型、接口协议和事件系统
"""

from luqi_engine.core.types import (
    EntityId,
    Vector3,
    BoundingBox,
    WorldState,
    ActionResult,
    EventType,
)
from luqi_engine.core.event_bus import EventBus, Event
from luqi_engine.core.interfaces import (
    IWorldViewRenderer,
    ISceneBuilder,
    ICharacterManager,
    INarrativeController,
    IInteractionCoordinator,
    IDesireEngine,
)
from luqi_engine.core.config import EngineConfig
from luqi_engine.core.rng import (
    PCGRandom,
    SeededRNGManager,
    NarrativeSeedHierarchy,
)
from luqi_engine.core.chaos import (
    LorenzAttractor,
    EmotionalFluctuation,
)
from luqi_engine.core.distributions import DistributionToolkit

__all__ = [
    "EntityId",
    "Vector3",
    "BoundingBox",
    "WorldState",
    "ActionResult",
    "EventType",
    "EventBus",
    "Event",
    "IWorldViewRenderer",
    "ISceneBuilder",
    "ICharacterManager",
    "INarrativeController",
    "IInteractionCoordinator",
    "IDesireEngine",
    "EngineConfig",
    "PCGRandom",
    "SeededRNGManager",
    "NarrativeSeedHierarchy",
    "LorenzAttractor",
    "EmotionalFluctuation",
    "DistributionToolkit",
]
