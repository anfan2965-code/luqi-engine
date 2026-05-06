# 动机系统 (Motivation)

扩展8层马斯洛需求层次 + 冲突解决引擎。

## 模块概览

```
luqi_engine/motivation/
└── maslow_engine.py   — MotivationEngine / MaslowProfile / NeedFulfillment
```

## NeedLevel — 8层需求枚举

```python
class NeedLevel(Enum):
    """扩展马斯洛需求层次 (8层)

    传统5层 + 扩展3层:
      L1 PHYSIOLOGICAL     — 生理需求 (食物/水/休息)
      L2 SAFETY            — 安全需求 (庇护/健康/稳定)
      L3 BELONGING         — 归属需求 (友谊/亲密/团队)
      L4 ESTEEM            — 尊重需求 (认可/地位/成就)
      L5 COGNITIVE         — 认知需求 (知识/理解/探索)
      L6 AESTHETIC         — 审美需求 (秩序/美好/平衡)
      L7 SELF_ACTUALIZATION — 自我实现 (潜能发挥/创造力)
      L8 SELF_TRANSCENDENCE — 自我超越 (超越自我/助人)
    """
    PHYSIOLOGICAL = "physiological"
    SAFETY = "safety"
    BELONGING = "belonging"
    ESTEEM = "esteem"
    COGNITIVE = "cognitive"
    AESTHETIC = "aesthetic"
    SELF_ACTUALIZATION = "self_actualization"
    SELF_TRANSCENDENCE = "self_transcendence"


class ConflictStrategy(Enum):
    SUBORDINATION = "subordination"     # 从属 (低层优先)
    COMPROMISE = "compromise"           # 妥协 (折中)
    INTEGRATION = "integration"         # 整合 (同时满足)
    ESCALATION = "escalation"           # 升级 (高层优先)


class ContextType(Enum):
    NORMAL = "normal"                   # 正常环境
    DANGER = "danger"                  # 危险环境
    SOCIAL = "social"                  # 社交场景
    SOLITUDE = "solitude"              # 独处反思
```

## NeedFulfillment — 需求满足状态

```python
@dataclass
class NeedFulfillment:
    level: NeedLevel
    current_value: float = 0.5          # 当前满足度 [0, 1]
    baseline: float = 0.5              # 基线值
    threshold: float = 0.3             # 缺乏阈值 (低于此值产生驱动力)
    urgency: float = 0.0               # 当前紧迫性 [0, 1]
    last_updated: float = field(default_factory=time.time)

    def deficit(self) -> float:
        """需求缺口 = max(0, threshold - current_value)"""

    def is_deficient(self) -> bool:
        """是否处于缺乏状态"""

    def apply_context_adjustment(
        self,
        context: ContextType,
        context_urgency: float = 1.0,
    ) -> None:
        """根据上下文调整紧迫性

        DANGER → PHYSIOLOGICAL/SAFETY urgency ×2.0
        SOCIAL → BELONGING/ESTEEM urgency ×1.5
        SOLITUDE → COGNITIVE/AESTHETIC urgency ×1.3
        """
```

## MotivationConflict — 动机冲突

```python
@dataclass
class MotivationConflict:
    primary_need: NeedLevel           # 主要冲突需求
    secondary_need: NeedLevel         # 次要冲突需求
    conflict_magnitude: float         # 冲突强度 [0, 1]
    resolved: bool = False
    strategy_used: Optional[ConflictStrategy] = None
    resolution_detail: str = ""
```

## MaslowProfile — 马斯洛画像

```python
class MaslowProfile:
    """单个角色的完整马斯洛需求画像"""

    def __init__(self, character_id: str = "") -> None: ...

    @property
    def needs(self) -> Dict[NeedLevel, NeedFulfillment]: ...

    def update_need_value(self, level: NeedLevel, delta: float) -> None:
        """更新需求满足值 (自动钳制到[0,1])"""

    def get_dominant_need(self) -> Tuple[NeedLevel, float]:
        """返回最迫切的需求及其紧迫性"""

    def get_unmet_deficiency_needs(self) -> List[Tuple[NeedLevel, float]]:
        """返回所有未满足的缺失型需求 (L1-L4)，按紧迫性降序"""

    def detect_conflicts(self) -> List[MotivationConflict]:
        """检测当前动机冲突"""
```

## MotivationEngine — 动机引擎 ⭐ 核心

```python
class MotivationEngine:
    """扩展马斯洛动机引擎

    核心功能:
    - 管理8层需求状态
    - 上下文感知的紧迫性调整
    - 动机冲突检测与解决
    - 事件驱动的需求更新
    - 与DesireEngine联动

    解决策略优先级:
      1. INTEGRATION — 尝试同时满足双方
      2. COMPROMISE — 折中方案
      3. SUBORDINATION — 低层优先 (安全第一)
      4. ESCALATION — 高层优先 (成长导向)
    """

    def __init__(self, config: Optional[MotivationConfig] = None) -> None: ...

    def create_profile(self, character_id: str) -> MaslowProfile:
        """创建新角色的需求画像"""

    def get_profile(self, character_id: str) -> Optional[MaslowProfile]: ...

    def set_context(
        self,
        context: ContextType,
        urgency: float = 1.0,
    ) -> None:
        """设置全局上下文 (影响所有角色)"""

    def resolve_conflict(
        self,
        conflict: MotivationConflict,
        preferred_strategy: Optional[ConflictStrategy] = None,
    ) -> ConflictResolutionResult:
        """解决动机冲突"""

    def update_from_event(
        self,
        character_id: str,
        event_type: str,
        magnitude: float,
        affected_levels: Optional[List[NeedLevel]] = None,
    ) -> Dict[NeedLevel, float]:
        """根据事件更新需求值

        event_type示例: "food_eaten", "danger_encountered", "praise_received"
        返回: {level: delta} 各层级变化量
        """
```

## 使用示例

```python
from luqi_engine.motivation.maslow_engine import (
    MotivationEngine, MaslowProfile, NeedLevel, ContextType, ConflictStrategy
)

engine = MotivationEngine()
profile = engine.create_profile("hero_001")

# 设置危险上下文
engine.set_context(ContextType.DANGER, urgency=1.5)

# 更新需求 (遭遇危险事件)
deltas = engine.update_from_event(
    character_id="hero_001",
    event_type="danger_encountered",
    magnitude=0.7,
    affected_levels=[NeedLevel.SAFETY],
)
print(f"需求变化: {deltas}")

# 获取主导需求
dominant, urgency = profile.get_dominant_need()
print(f"主导需求: {dominant.name} (紧迫性={urgency:.2f})")

# 查看未满足的缺失需求
unmet = profile.get_unmet_deficiency_needs()
for level, urg in unmet[:3]:
    print(f"  {level.name}: 紧迫性={urg:.2f}")
```
