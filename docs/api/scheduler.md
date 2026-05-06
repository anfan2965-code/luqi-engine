# 调度系统 (Scheduler)

异步任务调度、节奏感知和自动模式执行。

## 模块概览

```
luqi_engine/scheduler/
├── async_scheduler.py  — AsyncTaskScheduler 状态机调度器 ⭐核心
├── pace_sensor.py      — PaceSensor 节奏感知器
├── gap_precomputer.py  — GapPrecomputer 缺口预计算
└── auto_mode.py        — AutoModeExecutor 自动模式执行
```

## AsyncTaskScheduler — 异步任务状态机 ⭐ 核心

```python
class EngineState(Enum):
    IDLE = auto()         # 空闲，可接受输入
    SYNC = auto()         # 同步处理中
    RESPONDING = auto()   # LLM响应中
    ASYNC_PREP = auto()   # 异步准备中
    READY = auto()        # 准备就绪
    AUTO = auto()         # 自动模式运行中


class AsyncTaskScheduler:
    """6状态有限状态机调度器

    有效转换规则:
      IDLE → SYNC
      SYNC → RESPONDING | IDLE
      RESPONDING → ASYNC_PREP | IDLE
      ASYNC_PREP → READY | IDLE
      READY → AUTO | SYNC | IDLE
      AUTO → SYNC | IDLE

    可接受输入的状态: IDLE, READY, AUTO
    """

    def __init__(self) -> None: ...

    def get_state(self) -> EngineState: ...
    def can_accept_input(self) -> bool: ...
    def is_auto_mode(self) -> bool: ...

    def start_sync(self) -> None:
        """IDLE → SYNC"""

    def start_responding(self) -> None:
        """SYNC → RESPONDING"""

    def start_async_prep(self) -> None:
        """RESPONDING → ASYNC_PREP"""

    def mark_ready(self) -> None:
        """ASYNC_PREP → READY"""

    def enter_auto(self) -> None:
        """READY → AUTO"""

    def reset(self) -> None:
        """任意状态 → IDLE"""
```

**状态转换图**:
```
[IDLE] ──start_sync──▶ [SYNC] ──start_responding──▶ [RESPONDING]
  ▲                       │                              │
  │                   (cancel)                      (cancel)
  │                       ▼                              ▼
  │                     [IDLE]                         [IDLE]
  │                                                      │
  │                                    start_async_prep   │
  │                                      ▼                │
  │                                  [ASYNC_PREP] ──mark_ready──▶ [READY]
  │                                       │                    │
  │                                   (cancel)            enter_auto │
  │                                       ▼                    ▼
  │                                     [IDLE]              [AUTO]
  │                                                            │
  └────────────────────────────(reset/cancel)─────────────────┘
```

## PaceSensor — 节奏感知器

```python
class PaceSensor(IPaceSensor):
    """对话节奏感知与控制

    功能:
    - 检测当前节奏等级 (SLOW/NORMAL/FAST/RAPID)
    - 根据用户输入频率动态调整
    - 输出PaceState供其他模块参考
    """

    def __init__(self, config: Optional[PaceConfig] = None) -> None: ...

    def record_interaction(self, timestamp: Optional[float] = None) -> None:
        """记录一次交互时间戳"""

    def set_pace(self, level: PaceLevel) -> None:
        """手动设置节奏等级"""

    def get_pace_state(self) -> PaceState:
        """获取当前节奏状态

        Returns:
          PaceState(level, interval_hint, auto_mode_config, ...)
        """
```

### PaceState & AutoModeConfig

```python
@dataclass
class PaceState:
    level: PaceLevel              # SLOW / NORMAL / FAST / RAPID
    interval_hint: float          # 建议响应间隔(秒)
    auto_mode_config: Optional[AutoModeConfig] = None
    last_interaction: float = 0.0
    interactions_count: int = 0


@dataclass
class AutoModeConfig:
    enabled: bool = False
    tick_interval_sec: float = 30.0
    max_ticks_per_session: int = 20
    require_idle_threshold_sec: float = 60.0
```

## GapPrecomputer — 缺口预计算

```python
@dataclass
class GapTaskResult:
    task_id: str
    completed: bool = False
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_sec: float = 0.0


class GapPrecomputer:
    """在用户等待LLM响应期间预计算后续任务

    预计算任务示例:
    - 叙事分支预加载
    - 场景环境更新
    - 角色记忆整理
    - 下轮候选行动预评估
    """

    def __init__(self) -> None: ...

    async def submit(self, task_id: str, coro_func, *args, **kwargs) -> None:
        """提交预计算任务"""

    async def get_result(self, task_id: str) -> Optional[GapTaskResult]: ...
    def get_pending_count(self) -> int: ...
    def cancel_all(self) -> None: ...
```

## AutoModeExecutor — 自动模式执行器

```python
@dataclass
class TickResult:
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    tick_number: int = 0


class AutoModeExecutor:
    """自动模式下按固定间隔触发引擎Tick

    行为:
    - 每tick_interval秒触发一次orchestrate
    - 使用空输入或上下文延续
    - 受max_ticks限制
    - 可随时被用户输入中断
    """

    def __init__(self, config: Optional[AutoModeConfig] = None) -> None: ...

    async def execute_tick(
        self,
        orchestrator: Any,
        character_id: str,
        context: Dict[str, Any],
    ) -> TickResult:
        """执行单次自动Tick"""

    async def start_auto_loop(
        self,
        orchestrator: Any,
        character_id: str,
        context: Dict[str, Any],
    ) -> AsyncIterator[TickResult]:
        """启动自动循环 (异步迭代器)"""

    def stop(self) -> None: ...
    @property
    def ticks_executed(self) -> int: ...
```

## 使用示例

```python
from luqi_engine.scheduler.async_scheduler import AsyncTaskScheduler, EngineState
from luqi_engine.scheduler.pace_sensor import PaceSensor, PaceLevel

# 初始化调度器
scheduler = AsyncTaskScheduler()
print(f"初始状态: {scheduler.get_state().name}")
print(f"可接受输入: {scheduler.can_accept_input()}")

# 模拟对话流程
scheduler.start_sync()
print(f"状态: {scheduler.get_state().name}")  # SYNC

scheduler.start_responding()
print(f"状态: {scheduler.get_state().name}")  # RESPONDING

scheduler.start_async_prep()
print(f"状态: {scheduler.get_state().name}")  # ASYNC_PREP

scheduler.mark_ready()
print(f"状态: {scheduler.get_state().name}")  # READY

scheduler.enter_auto()
print(f"状态: {scheduler.get_state().name}")  # AUTO
print(f"自动模式: {scheduler.is_auto_mode()}")

# 重置
scheduler.reset()
print(f"重置后: {scheduler.get_state().name}")  # IDLE

# 节奏感知
sensor = PaceSensor()
sensor.record_interaction()
state = sensor.get_pace_state()
print(f"节奏等级: {state.level.name}")
```
