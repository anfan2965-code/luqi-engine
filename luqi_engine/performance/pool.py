"""
对象池 - 减少频繁创建销毁对象的GC压力
泛型对象池，支持预分配、自动扩缩容、对象重置
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from luqi_engine.core.config import PerformanceConfig

T = TypeVar("T")

_POOL_DEFAULT_INITIAL_SIZE: int = 64
_POOL_DEFAULT_MAX_SIZE: int = 1024
_POOL_SHRINK_INTERVAL_SEC: float = 60.0
_POOL_SHRINK_THRESHOLD_RATIO: float = 0.3
_POOL_SHRINK_TARGET_RATIO: float = 0.5
_POOL_EXPANSION_FACTOR: float = 1.5
_POOL_MIN_AVAILABLE_BEFORE_EXPAND: int = 2


@dataclass
class PoolStats:
    total_created: int = 0
    total_reused: int = 0
    total_returned: int = 0
    total_discarded: int = 0
    current_available: int = 0
    current_in_use: int = 0
    peak_in_use: int = 0
    last_shrink_time: float = 0.0


class ObjectPool(Generic[T]):
    """
    泛型对象池
    线程安全，支持预分配、自动扩缩容、对象重置回调
    """

    def __init__(
        self,
        factory: Callable[[], T],
        reset_fn: Optional[Callable[[T], None]] = None,
        validate_fn: Optional[Callable[[T], bool]] = None,
        initial_size: int = _POOL_DEFAULT_INITIAL_SIZE,
        max_size: int = _POOL_DEFAULT_MAX_SIZE,
    ) -> None:
        self._factory = factory
        self._reset_fn = reset_fn
        self._validate_fn = validate_fn
        self._max_size = max_size
        self._available: List[T] = []
        self._in_use: Dict[int, T] = {}
        self._stats = PoolStats()
        self._lock = threading.Lock()
        self._preallocate(initial_size)

    def acquire(self) -> T:
        with self._lock:
            if self._available:
                obj = self._available.pop()
                obj_id = id(obj)
                self._in_use[obj_id] = obj
                self._stats.total_reused += 1
                self._stats.current_available = len(self._available)
                self._stats.current_in_use = len(self._in_use)
                self._stats.peak_in_use = max(self._stats.peak_in_use, self._stats.current_in_use)
                return obj
            if len(self._in_use) >= self._max_size:
                raise RuntimeError(
                    f"对象池已达上限 {self._max_size}，无法分配新对象"
                )
            obj = self._factory()
            obj_id = id(obj)
            self._in_use[obj_id] = obj
            self._stats.total_created += 1
            self._stats.current_available = len(self._available)
            self._stats.current_in_use = len(self._in_use)
            self._stats.peak_in_use = max(self._stats.peak_in_use, self._stats.current_in_use)
            return obj

    def release(self, obj: T) -> None:
        with self._lock:
            obj_id = id(obj)
            if obj_id not in self._in_use:
                self._stats.total_discarded += 1
                return
            del self._in_use[obj_id]
            if self._reset_fn is not None:
                try:
                    self._reset_fn(obj)
                except Exception:
                    self._stats.total_discarded += 1
                    return
            if self._validate_fn is not None:
                if not self._validate_fn(obj):
                    self._stats.total_discarded += 1
                    self._stats.current_available = len(self._available)
                    self._stats.current_in_use = len(self._in_use)
                    return
            self._available.append(obj)
            self._stats.total_returned += 1
            self._stats.current_available = len(self._available)
            self._stats.current_in_use = len(self._in_use)

    def shrink(self) -> int:
        with self._lock:
            total = len(self._available) + len(self._in_use)
            if total == 0:
                return 0
            available_ratio = len(self._available) / max(total, 1)
            if available_ratio < _POOL_SHRINK_THRESHOLD_RATIO:
                return 0
            target_available = int(total * _POOL_SHRINK_TARGET_RATIO)
            to_remove = max(0, len(self._available) - target_available)
            removed = 0
            while removed < to_remove and self._available:
                self._available.pop()
                removed += 1
            self._stats.total_discarded += removed
            self._stats.current_available = len(self._available)
            self._stats.last_shrink_time = time.time()
            return removed

    def expand(self, count: int) -> int:
        with self._lock:
            total = len(self._available) + len(self._in_use)
            can_add = min(count, self._max_size - total)
            for _ in range(can_add):
                obj = self._factory()
                self._available.append(obj)
                self._stats.total_created += 1
            self._stats.current_available = len(self._available)
            return can_add

    def auto_expand_if_needed(self) -> int:
        with self._lock:
            if len(self._available) < _POOL_MIN_AVAILABLE_BEFORE_EXPAND:
                current_total = len(self._available) + len(self._in_use)
                target = max(
                    int(current_total * _POOL_EXPANSION_FACTOR),
                    _POOL_DEFAULT_INITIAL_SIZE,
                )
                needed = min(target - current_total, self._max_size - current_total)
                if needed <= 0:
                    return 0
                for _ in range(needed):
                    obj = self._factory()
                    self._available.append(obj)
                    self._stats.total_created += 1
                self._stats.current_available = len(self._available)
                return needed
            return 0

    @property
    def stats(self) -> PoolStats:
        return self._stats

    @property
    def available_count(self) -> int:
        return len(self._available)

    @property
    def in_use_count(self) -> int:
        return len(self._in_use)

    def _preallocate(self, count: int) -> None:
        actual = min(count, self._max_size)
        for _ in range(actual):
            obj = self._factory()
            self._available.append(obj)
            self._stats.total_created += 1
        self._stats.current_available = len(self._available)


class PoolManager:
    """
    对象池管理器
    管理多种类型的对象池，统一调度扩缩容
    """

    def __init__(self, config: Optional[PerformanceConfig] = None) -> None:
        self._config = config or PerformanceConfig()
        self._pools: Dict[str, ObjectPool[Any]] = {}
        self._last_shrink_time: float = time.time()

    def register_pool(
        self,
        name: str,
        factory: Callable[[], Any],
        reset_fn: Optional[Callable[[Any], None]] = None,
        validate_fn: Optional[Callable[[Any], bool]] = None,
        initial_size: Optional[int] = None,
        max_size: int = _POOL_DEFAULT_MAX_SIZE,
    ) -> None:
        size = initial_size or self._config.object_pool_initial_size
        self._pools[name] = ObjectPool(
            factory=factory,
            reset_fn=reset_fn,
            validate_fn=validate_fn,
            initial_size=size,
            max_size=max_size,
        )

    def acquire(self, pool_name: str) -> Any:
        pool = self._pools.get(pool_name)
        if pool is None:
            raise KeyError(f"对象池不存在: {pool_name}")
        return pool.acquire()

    def release(self, pool_name: str, obj: Any) -> None:
        pool = self._pools.get(pool_name)
        if pool is not None:
            pool.release(obj)

    def maintenance(self) -> Dict[str, int]:
        results: Dict[str, int] = {}
        current_time = time.time()
        if current_time - self._last_shrink_time < _POOL_SHRINK_INTERVAL_SEC:
            return results
        for name, pool in self._pools.items():
            removed = pool.shrink()
            expanded = pool.auto_expand_if_needed()
            results[name] = expanded - removed
        self._last_shrink_time = current_time
        return results

    def get_all_stats(self) -> Dict[str, PoolStats]:
        return {name: pool.stats for name, pool in self._pools.items()}
