# 核心系统 (Core)

引擎基础设施层：随机数生成、事件总线、算法约束校验、快照管理、插件系统。

## 模块概览

```
luqi_engine/core/
├── rng.py              — PCGRandom PCG-XSH-RR确定性RNG
├── event_bus.py        — EventBus 发布/订阅事件总线
├── supreme_court.py    — AlgorithmSupremeCourt 5级约束金字塔
├── snapshot.py         — ISnapshotable / EngineSnapshot 快照接口
├── plugin.py           — PluginManager 插件管理
├── constants.py        — 全局枚举常量 (30+枚举)
├── types.py            — 核心数据类型 (50+数据类)
├── config.py           — 配置数据类 (CharacterConfig, NarrativeConfig...)
├── interfaces.py       — 抽象接口定义
└── unified_error.py    — 统一异常层次体系
```

## PCGRandom — 确定性随机数生成器

```python
class PCGRandom:
    """PCG-XSH-RR 变体随机数生成器

    特性:
    - 64位状态空间，32位输出
    - 多独立流支持 (stream参数)
    - 种子层级派生 (SHA256哈希链)
    - Box-Muller高斯采样

    类常量:
      _MULTIPLIER = 6364136223846793005
      _DEFAULT_INCREMENT = 1442695040888963407
    """

    def __init__(self, seed: int = 0, stream: int = 0) -> None: ...

    def next_uint32(self) -> int:
        """生成32位无符号整数 [0, 2³²-1]"""

    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        """均匀分布浮点数 [low, high]"""

    def gaussian(self, mean: float = 0.0, stddev: float = 1.0) -> float:
        """正态分布 (Box-Muller变换，缓存优化)"""

    def weighted_choice(self, weights: Sequence[float]) -> int:
        """按权重随机选择索引"""

    @property
    def state(self) -> Tuple[int, int]:
        """返回 (state, increment) 用于序列化/恢复"""

    @state.setter
    def state(self, value: Tuple[int, int]) -> None:
        """从元组恢复状态"""
```

**种子派生机制**:
```
Base Seed → SHA256 → hex[:16]
                    ↓
Sub-seed = f"{base}:{module}:{entity}" → SHA256 → new_seed
```

## EventBus — 中央事件总线

```python
@dataclass
class Event:
    event_type: EventType          # 事件类型枚举
    source: str                   # 来源模块标识
    payload: Dict[str, Any]       # 事件载荷
    timestamp: float              # 时间戳
    event_id: str                 # UUID前12字符
    priority: int = 0             # 优先级


class EventBus:
    """发布/订阅模式事件总线

    特性:
    - 同步/异步处理器共存
    - 通配符订阅 (subscribe_all)
    - 历史记录与回放 (max_history=500)
    - 暂停/恢复控制
    """

    def __init__(self, max_history: int = 500) -> None: ...

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler | AsyncEventHandler,
        is_async: bool = False,
    ) -> None:
        """订阅特定事件类型"""

    def subscribe_all(
        self,
        handler: EventHandler | AsyncEventHandler,
        is_async: bool = False,
    ) -> None:
        """通配符订阅所有事件"""

    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler | AsyncEventHandler,
        is_async: bool = False,
    ) -> None: ...

    def publish(self, event: Event) -> None:
        """同步发布，触发所有同步处理器"""

    async def publish_async(self, event: Event) -> None:
        """异步发布，同时触发同步和异步处理器"""

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 50,
        since: Optional[float] = None,
    ) -> List[Event]:
        """查询历史事件"""

    def pause(self) -> None: ...
    def resume(self) -> None: ...
```

## AlgorithmSupremeCourt — 算法最高法院 ⭐ 核心

```python
class AlgorithmSupremeCourt(IAlgorithmSupremeCourt):
    """5级约束金字塔校验器

    所有LLM输出必须经过此门验证后才能生效。

    校验规则 (HARD级别):
    1. PAD情感范围检查:
       - arousal: ±(base + neuroticism×factor)
       - pleasure: ±PLEASURE_DELTA_MAX
       - dominance: ±DOMINANCE_DELTA_MAX
    2. 行动非空检查: action不能为空
    3. 时间跳跃限制: skip_duration ≤ MAX_TIME_SKIP_PER_TURN
    4. 事实冲突检测: 新事实不得与已确立事实矛盾

    校验结果:
    - ValidatedIR: 包含修正后的IR + 违规列表
    - needs_critic_review: 有HARD违规时标记需Critic复核
    """

    def validate_dialogue_ir(
        self,
        ir: CanonicalIR,
        character: Any,
        narrative: Any,
    ) -> ValidatedIR:
        """校验对话中间表示(IR)

        返回:
          ValidatedIR(
            ir=CanonicalIR,           # 修正后的IR
            violations=[Violation],   # 违规列表
            is_clean=bool,            # 是否无违规
            needs_critic_review=bool, # 是否需要Critic复核
          )
        """

    def validate_novel_delta(
        self,
        delta: NarrativeDelta,
        narrative: Any,
    ) -> ValidatedDelta:
        """校验叙事增量 (事实冲突检测)"""
```

### Violation 违规记录

```python
@dataclass
class Violation:
    level: ViolationLevel     # HARD / SOFT / INFO / WARNING
    type: ViolationType       # EMOTION_OUT_OF_RANGE / ACTION_EMPTY / ...
    field: str                # 字段名
    original: Any             # 原始值
    forced: Any               # 强制修正值
```

**ViolationLevel 枚举**: `HARD` > `SOFT` > `INFO` > `WARNING`
**ViolationType 枚举**: `EMOTION_OUT_OF_RANGE`, `ACTION_EMPTY`, `TIME_SKIP_EXCEEDED`, `FACT_CONFLICT`, ...

## ISnapshotable & EngineSnapshot — 快照系统

```python
class ISnapshotable(ABC):
    """可快照对象接口"""

    @abstractmethod
    def take_snapshot(self) -> Dict[str, Any]:
        """获取当前状态快照"""

    @abstractmethod
    def restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """从快照恢复状态"""


@dataclass
class EngineSnapshot:
    """引擎全局快照"""
    timestamp: float
    version: str
    subsystems: Dict[str, Dict[str, Any]]
    rng_state: Optional[Tuple[int, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

## PluginManager — 插件管理系统

```python
class PluginState(Enum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


class PluginBase(ABC):
    """插件基类"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    async def initialize(self, engine: Any) -> None: ...

    @abstractmethod
    async def shutdown(self) -> None: ...


@dataclass
class PluginRecord:
    plugin: PluginBase
    state: PluginState = PluginState.UNLOADED
    error_message: Optional[str] = None


class PluginManager:
    """插件生命周期管理"""

    def __init__(self) -> None: ...

    def register(self, plugin: PluginBase) -> None: ...

    async def initialize_all(self, engine: Any) -> None: ...

    async def shutdown_all(self) -> None: ...

    def get_plugin(self, name: str) -> Optional[PluginRecord]: ...

    def list_plugins(self) -> List[str]: ...
```

## 核心常量 (constants.py)

| 枚举类 | 关键值 |
|--------|--------|
| `ViolationLevel` | HARD, SOFT, INFO, WARNING |
| `ViolationType` | EMOTION_OUT_OF_RANGE, ACTION_EMPTY, TIME_SKIP_EXCEEDED, FACT_CONFLICT |
| `NarrativeSignal` | TIME_SKIP, BRANCH_TAKEN, REGRESSION, CLIMAX |
| `StoryBeatStatus` | PENDING, ACTIVE, COMPLETED, SKIPPED |
| `ScopeLevel` | IMMEDIATE, SHORT_TERM, MEDIUM_TERM, LONG_TERM |
| `PaceLevel` | SLOW, NORMAL, FAST, RAPID |
| `ToneType` | CASUAL, FORMAL, DRAMATIC, MYSTERIOUS |
| `LengthHint` | BRIEF, NORMAL, DETAILED, EPIC |
| `CriticSeverity` | ERROR, WARNING, INFO, SUGGESTION |
| `CriticVerdictType` | APPROVED, REJECTED, CONDITIONAL, DEFERRED |
| `AtmosphereMode` | IMMERSIVE, MINIMAL, DYNAMIC |
| `CorrectionSeverity` | CLAMP, OVERRIDE, REJECT |
| `DialogueSource` | CLOUD, LOCAL, HYBRID, FALLBACK |
| `QualityGrade` | A_PLUS, A, B_PLUS, B, C, D, F |
| `AgentMode` | FULL_AUTO, SEMI_AUTO, MANUAL |
| `AssemblyMode` | FULL, PARTIAL, VOICE_ONLY |

## 核心数据类型 (types.py) — 重点

```python
@dataclass
class CanonicalIR:
    """规范中间表示 - LLM输出的标准格式"""
    action: str
    emotion_delta: EmotionDelta
    narrative_signal: NarrativeSignal
    action_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Fact:
    """叙事事实"""
    id: str
    content: str
    source: str                  # cloud / local / user
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class StoryBeat:
    """故事节拍"""
    beat_id: str
    content: str
    status: StoryBeatStatus = StoryBeatStatus.PENDING
    position: int = 0


@dataclass
class ChapterOutline:
    """章节大纲"""
    chapter_id: str
    title: str
    beats: List[StoryBeat] = field(default_factory=list)


@dataclass
class DesireVector:
    """欲望向量"""
    DIMENSION_MIN: ClassVar[float] = 0.0
    DIMENSION_MAX: ClassVar[float] = 1.0

    dimensions: Dict[str, float]

    def get_dimension(self, name: str) -> float: ...
    def set_dimension(self, name: str, value: float) -> None: ...


@dataclass
class SevenEmotions:
    """七情向量 (中医情感理论)"""
    joy: float = 0.0
    anger: float = 0.0
    sorrow: float = 0.0
    fear: float = 0.0
    love: float = 0.0
    disgust: float = 0.0
    desire: float = 0.0


@dataclass
class LLMRequest:
    """LLM请求"""
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 2048
    model: str = ""


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    model: str = ""
    usage: Optional[Dict[str, int]] = None
    finish_reason: str = "stop"
```

## 统一错误体系 (unified_error.py)

```
LuqiEngineError (基线)
├── ConfigurationError           # 配置错误
├── SubsystemInitializationError # 子系统初始化失败
├── BeliefError                  # 信念相关
│   ├── InvalidObservationError  # 无效观察
│   └── BeliefTargetLimitExceeded # 信念目标超限
├── GameTheoryError              # 博弈论相关
│   ├── NoEquilibriumFound       # 无均衡解
│   ├── InvalidPayoffMatrix      # 无效收益矩阵
│   └── TemperatureOutOfRange    # 温度参数越界
├── MechanismDesignError         # 机制设计相关
│   ├── IncompatibilityDetected  # 不兼容检测
│   └── ParameterOutOfBounds     # 参数越界
└── PerformanceBudgetExceeded    # 性能预算超限
```

## 使用示例

```python
from luqi_engine.core.rng import PCGRandom
from luqi_engine.core.event_bus import EventBus, Event
from luqi_engine.core.supreme_court import AlgorithmSupremeCourt
from luqi_engine.core.types import CanonicalIR, EmotionDelta, NarrativeSignal, EventType

# 初始化核心组件
rng = PCGRandom(seed=42, stream=0)
event_bus = EventBus(max_history=1000)
court = AlgorithmSupremeCourt()

# 使用RNG
random_idx = rng.weighted_choice([0.3, 0.5, 0.2])
gaussian_val = rng.gaussian(mean=100, stddev=15)

# 发布事件
event = Event(
    event_type=EventType.CHARACTER_EMOTION_CHANGED,
    source="emotion_engine",
    payload={"char_id": "hero_001", "delta": {"pleasure": 0.1}},
)
event_bus.publish(event)

# 校验LLM输出
ir = CanonicalIR(
    action="attack",
    emotion_delta=EmotionDelta(arousal=0.3, pleasure=-0.1, dominance=0.2),
    narrative_signal=NarrativeSignal.TIME_SKIP,
)
validated = court.validate_dialogue_ir(ir, character=some_char, narrative=some_narrative)
print(f"是否干净: {validated.is_clean}")
print(f"需要Critic复核: {validated.needs_critic_review}")
for v in validated.violations:
    print(f"  违规: {v.type.name} @ {v.field} = {v.original} → {v.forced}")
```
