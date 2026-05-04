"""
资源管理器 - 移动端性能优化
骁龙695+6GB RAM适配、三层分离自适应更新、非活跃资源回收
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from luqi_engine.core.config import MobileConfig, PerformanceConfig


_UPDATE_LAYER_WORLD: str = "world"
_UPDATE_LAYER_CHARACTER: str = "character"
_UPDATE_LAYER_NARRATIVE: str = "narrative"

_UPDATE_FREQUENCY_HIGH: float = 1.0
_UPDATE_FREQUENCY_MEDIUM: float = 0.5
_UPDATE_FREQUENCY_LOW: float = 0.2

_DISTANCE_THRESHOLD_NEAR: float = 50.0
_DISTANCE_THRESHOLD_FAR: float = 200.0

_MEMORY_PRESSURE_LOW: float = 0.5
_MEMORY_PRESSURE_MEDIUM: float = 0.7
_MEMORY_PRESSURE_HIGH: float = 0.85
_MEMORY_PRESSURE_CRITICAL: float = 0.95

_RESOURCE_PRIORITY_CRITICAL: int = 0
_RESOURCE_PRIORITY_HIGH: int = 1
_RESOURCE_PRIORITY_MEDIUM: int = 2
_RESOURCE_PRIORITY_LOW: int = 3

_RECOVERY_EFFICIENCY_TARGET: float = 0.7
_INACTIVE_THRESHOLD_SEC: float = 300.0
_RECOVERY_CHECK_INTERVAL_SEC: float = 30.0

_CPU_SAMPLE_WINDOW: int = 10
_LATENCY_SAMPLE_WINDOW: int = 20

_ADAPTIVE_UPDATE_BASE_INTERVAL: float = 1.0
_ADAPTIVE_UPDATE_CPU_FACTOR: float = 0.5
_ADAPTIVE_UPDATE_MEMORY_FACTOR: float = 0.3


@dataclass
class ResourceEntry:
    resource_id: str
    resource_type: str
    priority: int = _RESOURCE_PRIORITY_MEDIUM
    memory_bytes: int = 0
    last_access_time: float = field(default_factory=time.time)
    access_count: int = 0
    is_active: bool = True
    layer: str = _UPDATE_LAYER_CHARACTER
    distance: float = 0.0
    release_callback: Optional[Callable[[], None]] = None
    restore_callback: Optional[Callable[[], None]] = None


@dataclass
class PerformanceMetrics:
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    memory_limit_mb: float = 2048.0
    avg_latency_ms: float = 0.0
    peak_latency_ms: float = 0.0
    active_resources: int = 0
    total_resources: int = 0
    recovery_count: int = 0
    last_recovery_time: float = 0.0

    @property
    def memory_pressure(self) -> float:
        if self.memory_limit_mb <= 0.0:
            return 1.0
        return self.memory_usage_mb / self.memory_limit_mb


@dataclass
class UpdateSchedule:
    layer: str
    interval_sec: float
    last_update: float = 0.0
    priority_multiplier: float = 1.0

    def should_update(self, current_time: float) -> bool:
        return (current_time - self.last_update) >= self.interval_sec

    def mark_updated(self, current_time: float) -> None:
        self.last_update = current_time


class ResourceManager:
    """
    资源管理器
    移动端性能优化：内存监控、非活跃资源回收、三层分离自适应更新
    """

    def __init__(
        self,
        mobile_config: Optional[MobileConfig] = None,
        perf_config: Optional[PerformanceConfig] = None,
    ) -> None:
        self._mobile_config = mobile_config or MobileConfig()
        self._perf_config = perf_config or PerformanceConfig()
        self._resources: Dict[str, ResourceEntry] = {}
        self._metrics = PerformanceMetrics(memory_limit_mb=self._mobile_config.max_memory_mb)
        self._cpu_samples: List[float] = []
        self._latency_samples: List[float] = []
        self._update_schedules: Dict[str, UpdateSchedule] = {
            _UPDATE_LAYER_WORLD: UpdateSchedule(
                layer=_UPDATE_LAYER_WORLD,
                interval_sec=_ADAPTIVE_UPDATE_BASE_INTERVAL,
                priority_multiplier=1.0,
            ),
            _UPDATE_LAYER_CHARACTER: UpdateSchedule(
                layer=_UPDATE_LAYER_CHARACTER,
                interval_sec=_ADAPTIVE_UPDATE_BASE_INTERVAL,
                priority_multiplier=1.0,
            ),
            _UPDATE_LAYER_NARRATIVE: UpdateSchedule(
                layer=_UPDATE_LAYER_NARRATIVE,
                interval_sec=_ADAPTIVE_UPDATE_BASE_INTERVAL,
                priority_multiplier=1.0,
            ),
        }
        self._last_recovery_check: float = time.time()

    def register_resource(
        self,
        resource_id: str,
        resource_type: str,
        priority: int = _RESOURCE_PRIORITY_MEDIUM,
        memory_bytes: int = 0,
        layer: str = _UPDATE_LAYER_CHARACTER,
        release_callback: Optional[Callable[[], None]] = None,
        restore_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._resources[resource_id] = ResourceEntry(
            resource_id=resource_id,
            resource_type=resource_type,
            priority=priority,
            memory_bytes=memory_bytes,
            layer=layer,
            release_callback=release_callback,
            restore_callback=restore_callback,
        )
        self._update_metrics()

    def unregister_resource(self, resource_id: str) -> None:
        entry = self._resources.pop(resource_id, None)
        if entry is not None and entry.is_active and entry.release_callback:
            entry.release_callback()
        self._update_metrics()

    def access_resource(self, resource_id: str) -> Optional[ResourceEntry]:
        entry = self._resources.get(resource_id)
        if entry is None:
            return None
        entry.last_access_time = time.time()
        entry.access_count += 1
        if not entry.is_active and entry.restore_callback:
            entry.restore_callback()
            entry.is_active = True
        self._update_metrics()
        return entry

    def update_distance(self, resource_id: str, distance: float) -> None:
        entry = self._resources.get(resource_id)
        if entry is not None:
            entry.distance = distance

    def record_cpu_sample(self, cpu_percent: float) -> None:
        self._cpu_samples.append(max(0.0, min(100.0, cpu_percent)))
        if len(self._cpu_samples) > _CPU_SAMPLE_WINDOW:
            self._cpu_samples = self._cpu_samples[-_CPU_SAMPLE_WINDOW:]
        self._metrics.cpu_usage_percent = (
            sum(self._cpu_samples) / len(self._cpu_samples)
            if self._cpu_samples else 0.0
        )

    def record_latency(self, latency_ms: float) -> None:
        self._latency_samples.append(max(0.0, latency_ms))
        if len(self._latency_samples) > _LATENCY_SAMPLE_WINDOW:
            self._latency_samples = self._latency_samples[-_LATENCY_SAMPLE_WINDOW:]
        self._metrics.avg_latency_ms = (
            sum(self._latency_samples) / len(self._latency_samples)
            if self._latency_samples else 0.0
        )
        self._metrics.peak_latency_ms = max(self._metrics.peak_latency_ms, latency_ms)

    def recover_inactive_resources(self) -> int:
        current_time = time.time()
        if current_time - self._last_recovery_check < _RECOVERY_CHECK_INTERVAL_SEC:
            return 0
        self._last_recovery_check = current_time
        recovered = 0
        pressure = self._metrics.memory_pressure
        if pressure < _MEMORY_PRESSURE_MEDIUM:
            return 0
        candidates = self._find_recovery_candidates(current_time)
        candidates.sort(key=lambda e: (e.priority, -e.last_access_time), reverse=True)
        target_recovery = self._compute_recovery_target()
        freed_bytes = 0
        for entry in candidates:
            if freed_bytes >= target_recovery:
                break
            if entry.is_active and entry.release_callback:
                entry.release_callback()
                entry.is_active = False
                freed_bytes += entry.memory_bytes
                recovered += 1
        if recovered > 0:
            self._metrics.recovery_count += recovered
            self._metrics.last_recovery_time = current_time
            self._update_metrics()
        return recovered

    def adapt_update_frequencies(self) -> Dict[str, float]:
        cpu = self._metrics.cpu_usage_percent
        memory_pressure = self._metrics.memory_pressure
        cpu_factor = max(0.2, 1.0 - (cpu / 100.0) * _ADAPTIVE_UPDATE_CPU_FACTOR)
        memory_factor = max(0.3, 1.0 - memory_pressure * _ADAPTIVE_UPDATE_MEMORY_FACTOR)
        combined_factor = cpu_factor * memory_factor
        schedules: Dict[str, float] = {}
        for layer_name, schedule in self._update_schedules.items():
            base = _ADAPTIVE_UPDATE_BASE_INTERVAL
            layer_multiplier = self._get_layer_multiplier(layer_name)
            adapted = base / (combined_factor * layer_multiplier)
            schedule.interval_sec = max(0.1, adapted)
            schedules[layer_name] = schedule.interval_sec
        return schedules

    def should_update_layer(self, layer: str) -> bool:
        schedule = self._update_schedules.get(layer)
        if schedule is None:
            return True
        return schedule.should_update(time.time())

    def mark_layer_updated(self, layer: str) -> None:
        schedule = self._update_schedules.get(layer)
        if schedule is not None:
            schedule.mark_updated(time.time())

    def get_update_frequency(self, layer: str, distance: float = 0.0) -> float:
        base_frequency = self._get_base_frequency_by_distance(distance)
        schedule = self._update_schedules.get(layer)
        if schedule is None:
            return base_frequency
        interval = schedule.interval_sec
        if interval <= 0.0:
            return base_frequency
        return min(base_frequency, 1.0 / interval)

    @property
    def metrics(self) -> PerformanceMetrics:
        return self._metrics

    def get_resource_report(self) -> Dict[str, Any]:
        active = sum(1 for e in self._resources.values() if e.is_active)
        total_memory = sum(e.memory_bytes for e in self._resources.values() if e.is_active)
        return {
            "total_resources": len(self._resources),
            "active_resources": active,
            "inactive_resources": len(self._resources) - active,
            "total_memory_mb": total_memory / (1024 * 1024),
            "memory_pressure": self._metrics.memory_pressure,
            "cpu_usage": self._metrics.cpu_usage_percent,
            "avg_latency_ms": self._metrics.avg_latency_ms,
            "recovery_count": self._metrics.recovery_count,
            "update_schedules": {
                name: {
                    "interval_sec": sched.interval_sec,
                    "last_update": sched.last_update,
                }
                for name, sched in self._update_schedules.items()
            },
        }

    def _find_recovery_candidates(
        self, current_time: float,
    ) -> List[ResourceEntry]:
        candidates: List[ResourceEntry] = []
        for entry in self._resources.values():
            if not entry.is_active:
                continue
            inactive_time = current_time - entry.last_access_time
            if inactive_time >= _INACTIVE_THRESHOLD_SEC:
                candidates.append(entry)
        return candidates

    def _compute_recovery_target(self) -> int:
        pressure = self._metrics.memory_pressure
        total_active_memory = sum(
            e.memory_bytes for e in self._resources.values() if e.is_active
        )
        if pressure >= _MEMORY_PRESSURE_CRITICAL:
            target_fraction = 0.5
        elif pressure >= _MEMORY_PRESSURE_HIGH:
            target_fraction = 0.3
        else:
            target_fraction = 0.15
        target_bytes = int(total_active_memory * target_fraction)
        target_bytes = max(target_bytes, int(self._mobile_config.max_memory_mb * 1024 * 1024 * 0.1))
        return target_bytes

    @staticmethod
    def _get_layer_multiplier(layer: str) -> float:
        multipliers: Dict[str, float] = {
            _UPDATE_LAYER_WORLD: 0.8,
            _UPDATE_LAYER_CHARACTER: 1.0,
            _UPDATE_LAYER_NARRATIVE: 0.6,
        }
        return multipliers.get(layer, 1.0)

    @staticmethod
    def _get_base_frequency_by_distance(distance: float) -> float:
        if distance <= _DISTANCE_THRESHOLD_NEAR:
            return _UPDATE_FREQUENCY_HIGH
        if distance <= _DISTANCE_THRESHOLD_FAR:
            return _UPDATE_FREQUENCY_MEDIUM
        return _UPDATE_FREQUENCY_LOW

    def _update_metrics(self) -> None:
        active = sum(1 for e in self._resources.values() if e.is_active)
        total_memory = sum(e.memory_bytes for e in self._resources.values() if e.is_active)
        self._metrics.active_resources = active
        self._metrics.total_resources = len(self._resources)
        self._metrics.memory_usage_mb = total_memory / (1024 * 1024)
