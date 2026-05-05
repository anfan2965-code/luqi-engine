"""
事件总线 - 模块间异步通信的核心基础设施
支持发布/订阅模式，解耦各引擎模块
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from luqi_engine.core.logging_config import get_logger
from luqi_engine.core.types import EventType

_logger = get_logger(__name__)

_EVENT_ID_HEX_LENGTH: int = 12
_DEFAULT_MAX_HISTORY: int = 500
_HISTORY_QUERY_DEFAULT_LIMIT: int = 50


@dataclass
class Event:
    event_type: EventType
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = ""
    priority: int = 0

    def __post_init__(self):
        if not self.event_id:
            import uuid
            self.event_id = uuid.uuid4().hex[:_EVENT_ID_HEX_LENGTH]


EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]


class EventBus:
    """
    中央事件总线
    - 同步和异步处理器共存
    - 按事件类型路由
    - 优先级排序
    - 历史记录与回放
    """

    def __init__(self, max_history: int = 500):
        self._sync_subscribers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._async_subscribers: Dict[EventType, List[AsyncEventHandler]] = defaultdict(list)
        self._wildcard_sync: List[EventHandler] = []
        self._wildcard_async: List[AsyncEventHandler] = []
        self._history: List[Event] = []
        self._max_history = max_history
        self._paused = False

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler | AsyncEventHandler,
        is_async: bool = False,
    ) -> None:
        if is_async:
            self._async_subscribers[event_type].append(handler)
        else:
            self._sync_subscribers[event_type].append(handler)

    def subscribe_all(
        self,
        handler: EventHandler | AsyncEventHandler,
        is_async: bool = False,
    ) -> None:
        if is_async:
            self._wildcard_async.append(handler)
        else:
            self._wildcard_sync.append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler | AsyncEventHandler,
        is_async: bool = False,
    ) -> None:
        target = self._async_subscribers if is_async else self._sync_subscribers
        if event_type in target:
            try:
                target[event_type].remove(handler)
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
        if self._paused:
            return

        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        for handler in self._sync_subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as exc:
                _logger.error("Event handler %s raised exception: %s", handler, exc, exc_info=True)

        for handler in self._wildcard_sync:
            try:
                handler(event)
            except Exception as exc:
                _logger.error("Event handler %s raised exception: %s", handler, exc, exc_info=True)

    async def publish_async(self, event: Event) -> None:
        if self._paused:
            return

        self.publish(event)

        async_handlers = list(self._async_subscribers.get(event.event_type, []))
        async_handlers.extend(self._wildcard_async)

        # 并行执行所有异步处理器，提高性能
        if async_handlers:
            tasks = []
            for handler in async_handlers:
                try:
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        tasks.append(result)
                    # 如果不是协程，说明是同步函数，已经执行完毕
                except Exception as exc:
                    _logger.error("Event handler %s raised exception: %s", handler, exc, exc_info=True)
            
            # 并行等待所有异步任务
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        _logger.error("Async event handler %s raised exception: %s", 
                                    async_handlers[i], result, exc_info=True)

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 50,
        since: Optional[float] = None,
    ) -> List[Event]:
        events = self._history
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        if since is not None:
            events = [e for e in events if e.timestamp >= since]
        return events[-limit:]

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def clear_history(self) -> None:
        self._history.clear()
