# 性能系统 (Performance)

对象池管理、资源监控和基准测试工具。

## 模块概览

```
luqi_engine/performance/
├── pool.py              — ObjectPool / PoolManager 泛型对象池
├── resource_manager.py  — ResourceManager 资源使用监控
└── benchmark.py         — 各子系统Benchmark测试套件
```

## ObjectPool — 泛型对象池 ⭐ 核心

```python
@dataclass
class PoolStats:
    """对象池统计信息"""
    total_created: int = 0
    total_reused: int = 0
    total_returned: int = 0
    total_discarded: int = 0
    current_available: int = 0
    current_in_use: int = 0
    peak_in_use: int = 0
    last_shrink_time: float = 0.0


class ObjectPool(Generic[T]):
    """线程安全泛型对象池

    特性:
    - 预分配初始容量 (default=64)
    - 自动扩容至max_size (default=1024)
    - 自动缩容 (空闲率>30%时收缩至50%)
    - 对象重置回调 (reset_fn)
    - 对象验证回调 (validate_fn)

    扩容因子: 1.5x
    缩容阈值: available_ratio > 0.3
    缩容目标: available_ratio → 0.5
    """

    def __init__(
        self,
        factory: Callable[[], T],
        reset_fn: Optional[Callable[[T], None]] = None,
        validate_fn: Optional[Callable[[T], bool]] = None,
        initial_size: int = 64,
        max_size: int = 1024,
    ) -> None: ...

    def acquire(self) -> T:
        """获取对象 (优先复用，不足时创建或扩容)

        Raises:
            RuntimeError: 达到max_size上限
        """

    def release(self, obj: T) -> None:
        """归还对象 (自动reset+validate后回池)"""

    def shrink(self) -> int:
        """缩容，返回释放的对象数"""

    @property
    def stats(self) -> PoolStats:
        """返回当前统计信息"""
```

## PoolManager — 多池管理器

```python
class PoolManager:
    """统一管理多个命名对象池"""

    def __init__(self) -> None: ...

    def register_pool(
        self,
        name: str,
        factory: Callable[[], T],
        reset_fn: Optional[Callable[[T], None]] = None,
        **kwargs,
    ) -> ObjectPool[T]:
        """注册并创建新池"""

    def acquire(self, pool_name: str) -> Any:
        """从指定池获取对象"""

    def release(self, pool_name: str, obj: Any) -> None:
        """归还对象到指定池"""

    def get_stats(self, pool_name: str) -> Optional[PoolStats]: ...
    def get_all_stats(self) -> Dict[str, PoolStats]: ...
```

## ResourceManager — 资源监控

```python
@dataclass
class ResourceEntry:
    resource_id: str
    name: str
    allocated: float = 0.0
    limit: float = 1.0
    unit: str = ""


@dataclass
class PerformanceMetrics:
    cpu_usage: float = 0.0
    memory_usage_mb: float = 0.0
    memory_limit_mb: float = 0.0
    gpu_usage: float = 0.0
    gpu_memory_mb: float = 0.0
    active_tasks: int = 0
    queue_depth: int = 0
    timestamp: float = field(default_factory=time.time)


class ResourceManager:
    """系统资源使用监控与预算管理"""

    def __init__(self) -> None: ...

    def register_resource(
        self,
        entry: ResourceEntry,
    ) -> None: ...

    def allocate(
        self,
        resource_id: str,
        amount: float,
    ) -> bool:
        """分配资源，返回是否成功"""

    def deallocate(
        self,
        resource_id: str,
        amount: float,
    ) -> None: ...

    def get_metrics(self) -> PerformanceMetrics: ...
    def check_budget(self) -> bool:
        """检查是否超出性能预算"""
```

## Benchmark 基准测试套件

```python
@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_time_sec: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p50_time_ms: float
    p99_time_ms: float
    throughput_per_sec: float
    success_rate: float
    errors: List[str] = field(default_factory=list)


class BeliefSystemBenchmark:
    """信念系统性能基准"""

    async def run(self, iterations: int = 1000) -> BenchmarkResult: ...


class ThreatCredibilityBenchmark:
    """威胁可信度评估基准"""

    async def run(self, iterations: int = 1000) -> BenchmarkResult: ...


class MixedStrategyBenchmark:
    """混合策略计算基准"""

    async def run(self, iterations: int = 1000) -> BenchmarkResult: ...


class IntegrationBenchmark:
    """全链路集成基准 (observe→belief→strategy→threat)"""

    async def run(self, iterations: int = 500) -> BenchmarkResult: ...
```

## 使用示例

```python
from luqi_engine.performance.pool import ObjectPool, PoolManager
from luqi_engine.performance.resource_manager import ResourceManager

# 创建对象池
pool = ObjectPool(
    factory=dict,                    # 工厂函数
    reset_fn=lambda d: d.clear(),     # 重置回调
    initial_size=32,
    max_size=256,
)

# 获取/归还
obj = pool.acquire()
obj["key"] = "value"
pool.release(obj)

print(f"统计: 复用={pool.stats.total_reused}, 新建={pool.stats.total_created}")

# 多池管理
mgr = PoolManager()
mgr.register_pool("dict_pool", dict, lambda d: d.clear())
d = mgr.acquire("dict_pool")
mgr.release("dict_pool", d)
```
