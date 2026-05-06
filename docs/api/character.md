# 角色系统 (Character)

完整角色实体系统，整合OCEAN人格、PAD情感、欲望驱动、GOAP规划、效用决策和社交感知。

## 模块概览

```
luqi_engine/character/
├── personality.py          — OceanPersonality OCEAN五因素人格
├── emotion.py              — PADState / ExtendedPAD PAD情感空间
├── desire.py               — DesireEngine 欲望驱动引擎
├── memory.py               — MemoryStore 角色记忆存储
├── goap.py                 — GOAPPlanner / GOAPAction 目标导向规划
├── utility.py              — UtilityBasedAI / CEMPlanner 效用决策
├── social_perception.py    — SocialPerception 社交感知
├── character_entity.py     — CharacterEntity 完整角色实体 ⭐核心
├── deep_character.py       — DeepCharacter 深度角色分析
├── narrative_identity.py   — NarrativeIdentity 叙事身份
├── existential_model.py    — ExistentialProfile 存在主义模型
├── jungian_model.py        — JungianProfile 荣格心理模型
└── social_evolution.py     — SocialEvolutionEngine 社交关系演化
```

## OceanPersonality — OCEAN人格模型

```python
class OceanPersonality:
    """基于Big Five (OCEAN) 的性格量化模型

    五维度: Openness / Conscientiousness / Extraversion / Agreeableness / Neuroticism
    分数范围: [0, 100] 每维度，默认50.0（中间值）

    类常量:
      DIMENSION_NAMES = ("openness", "conscientiousness", "extraversion",
                         "agreeableness", "neuroticism")
      SCORE_MIN = 0
      SCORE_MAX = 100
      SCORE_MIDPOINT = 50.0
      INFLUENCE_SCALE = 0.02  # 人格对决策的影响系数
    """

    def __init__(
        self,
        openness: float = 50.0,
        conscientiousness: float = 50.0,
        extraversion: float = 50.0,
        agreeableness: float = 50.0,
        neuroticism: float = 50.0,
        config: Optional[CharacterConfig] = None,
    ) -> None: ...

    def get_score(self, dimension: str) -> float:
        """获取指定维度的分数"""

    def set_score(self, dimension: str, value: float) -> None:
        """设置指定维度的分数 (自动钳制到[0,100])"""

    def adapt(self, deltas: Dict[str, float]) -> None:
        """渐进式适应调整 (受adaptation_rate控制)"""

    def influence_decision(self, action_weights: Dict[str, float]) -> Dict[str, float]:
        """人格影响决策权重计算
        各维度影响因子:
          openness × 0.3 (探索)
          conscientiousness × 0.3 (计划)
          extraversion × 0.3 (社交)
          agreeableness × 0.3 (合作)
          neuroticism × -0.25 (压力，负向)
        """

    def to_dict(self) -> Dict[str, float]: ...
    def distance_to(self, other: OceanPersonality) -> float: ...

    @classmethod
    def from_dict(cls, data: Dict[str, float], config: Optional[CharacterConfig] = None) -> OceanPersonality: ...
```

## PADState — PAD情感状态

```python
@dataclass
class PADState:
    """Pleasure/Arousal/Dominance 三维情感空间

    维度范围: [-1.0, 1.0]
    - pleasure: 愉悦度 (-1=痛苦, +1=快乐)
    - arousal: 唤醒度 (-1=平静, +1=激动)
    - dominance: 支配度 (-1=被支配, +1=支配)

    阻尼机制: 每次更新后自动衰减 (默认damping=0.85)
    """

    DIMENSION_MIN: ClassVar[float] = -1.0
    DIMENSION_MAX: ClassVar[float] = 1.0
    NEUTRAL: ClassVar[float] = 0.0
    DEFAULT_DAMPING: ClassVar[float] = 0.85

    pleasure: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0
    damping: float = 0.85

    def update(self, delta_p: float, delta_a: float, delta_d: float,
                scale: float = 1.0) -> PADState:
        """带阻尼的增量更新"""

    def decay(self) -> PADState:
        """自然衰减回归中性"""

    def to_tuple(self) -> Tuple[float, float, float]: ...
```

**七情→PAD映射表**:

| 情感 | P(愉悦) | A(唤醒) | D(支配) |
|------|---------|---------|---------|
| joy | +0.6 | +0.5 | +0.3 |
| anger | -0.6 | +0.7 | +0.4 |
| sorrow | -0.7 | -0.3 | -0.4 |
| fear | -0.7 | +0.5 | -0.5 |
| love | +0.5 | +0.3 | +0.2 |
| disgust | -0.5 | +0.3 | +0.1 |
| desire | +0.3 | +0.6 | +0.2 |

**OCEAN→PAD基线映射** (Mehrabian 1996):
```
Pleasure  = E(+0.21) + A(+0.25) + N(-0.26) + C(+0.12) + O(+0.08)
Arousal   = E(+0.15) + N(+0.20) + O(+0.18) + A(-0.05) + C(+0.05)
Dominance = E(+0.30) + C(+0.15) + A(-0.12) + N(-0.22) + O(+0.05)
```

## DesireEngine — 欲望驱动引擎

```python
class DesireEngine(IDesireEngine):
    """情感触发 → 欲望更新 → 目标优化驱动链

    核心方法:
    - get_desires(): 获取当前欲望向量
    - update_desires(): 根据情感变化更新欲望
    - compute_drive_chain(): 计算驱动力链 (优先级排序的目标列表)

    情感-欲望映射 (EMOTION_DESIRE_MAP):
      joy → belonging(+0.6), self_actualization(+0.4)
      fear → safety(+0.8), physiological(+0.3)
      love → belonging(+0.7), relatedness(+0.5)
      anger → esteem(+0.6), safety(+0.3)
    """

    UPDATE_SCALE: ClassVar[float] = 0.1
    SATIATION_DECAY: ClassVar[float] = 0.01
    EMOTION_DESIRE_MAP: ClassVar[Dict] = {...}

    def __init__(self, config: Optional[DesireConfig] = None) -> None: ...

    async def get_desires(self, character_id: EntityId) -> DesireVector: ...

    async def update_desires(
        self,
        character_id: EntityId,
        emotion_delta: Dict[str, float],
    ) -> DesireVector: ...

    async def compute_drive_chain(
        self,
        character_id: EntityId,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """返回按优先级排序的驱动力链 [{goal, priority, urgency, desire_name, strength}]"""
```

## Motive & MotivationEngine — 动机系统

```python
@dataclass
class Motive:
    """动机单元"""
    motive_id: str
    name: str
    layer: int                    # 1=生存层, 2=社交层, 3=自我实现层
    base_intensity: float         # 基础强度 [0, 1]
    decay_rate: float = 0.001     # 衰减率
    urgency_curve: str = "sigmoid"  # exponential/sigmoid/linear
    current_satisfaction: float = 0.5


class MotivationEngine:
    """三层动机引擎

    层级权重:
      Layer 1 (生存): weight=3.0
      Layer 2 (社交): weight=2.0
      Layer 3 (自我实现): weight=1.0

    紧迫性曲线:
      - exponential: strength = deprivation² (快速上升)
      - sigmoid: 1/(1+e^(-10(deprivation-0.5))) (平滑过渡)
      - linear: strength = deprivation (线性)
    """

    def __init__(self, motives: Optional[List[Motive]] = None) -> None: ...

    def add_motive(self, motive: Motive) -> None: ...

    def calculate_drive_strength(
        self, motive: Motive, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """计算动机驱动力强度 = intensity × urgency × layer_weight × context_mod"""

    def get_prioritized_motives(
        self, context: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, float]]:
        """返回 [(motive_id, strength)] 按强度降序排列"""

    def update_satisfaction(self, motive_id: str, delta: float) -> None: ...
    def decay_all(self, delta_time: float) -> None: ...

    @property
    def motives(self) -> Dict[str, Motive]: ...
```

## SocialPerception — 社交感知

```python
class SocialPerception:
    """社交关系量化系统

    三个核心维度:
    - RelationshipPotential: 关系势能 [-1, 1]，带速度衰减
    - ContextFidelity: 语境保真度 [0, 1]，多源失真累积
    - InterventionEntropy: 干预熵值 [0, 1]，记录外部干预频率
    """

    INTERACTION_WEIGHT: ClassVar[float] = 0.3
    DISTANCE_FACTOR: ClassVar[float] = 0.05

    def __init__(self) -> None: ...

    def update_potential(
        self, char_a: EntityId, char_b: EntityId, delta: float
    ) -> None: ...

    def get_potential(self, char_a: EntityId, char_b: EntityId) -> RelationshipPotential: ...

    def update_fidelity(self, char_id: EntityId, source: str, distortion: float) -> None: ...

    def record_intervention(self, char_id: EntityId) -> None: ...
```

### RelationshipPotential — 关系势能

```python
@dataclass
class RelationshipPotential:
    POTENTIAL_MIN: ClassVar[float] = -1.0
    POTENTIAL_MAX: ClassVar[float] = 1.0
    DECAY_RATE: ClassVar[float] = 0.01

    value: float = 0.0           # 当前势能值
    velocity: float = 0.0        # 变化速度 (带惯性)

    def update(self, delta: float) -> None:
        """增量更新，velocity提供惯性效果"""

    def decay(self) -> None:
        """自然衰减回归零点"""
```

### ContextFidelity — 语境保真度

```python
@dataclass
class ContextFidelity:
    FIDELITY_MIN: ClassVar[float] = 0.0
    FIDELITY_MAX: ClassVar[float] = 1.0
    DECAY_RATE: ClassVar[float] = 0.005

    value: float = 1.0
    distortion_sources: Dict[str, float] = field(default_factory=dict)

    def update(self, source: str, distortion: float) -> None:
        """添加失真源，自动累加"""

    def remove_distortion(self, source: str) -> None:
        """移除指定失真源"""

    def decay(self) -> None:
        """各失真源独立衰减"""
```

## GOAPPlanner — 目标导向行动规划

```python
class GOAPAction:
    """GOAP行动定义"""
    action_name: str
    preconditions: Dict[str, Any]    # 前置条件
    effects: Dict[str, Any]          # 执行效果
    cost: float = 1.0                # 行动代价


class GOAPWorldState:
    """世界状态容器"""
    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def matches(self, other: GOAPWorldState, keys: Optional[List[str]] = None) -> bool: ...


class GOAPPlanner:
    """目标导向行动规划器 (A*搜索)

    算法:
    1. 从目标状态反向推导前置条件图
    2. A*搜索找到最小代价行动序列
    3. 返回有序的行动计划或None(不可达)
    """

    def __init__(self, actions: Optional[List[GOAPAction]] = None) -> None: ...

    def plan(self, current_state: GOAPWorldState, goal_state: GOAPWorldState) -> Optional[List[GOAPAction]]:
        """规划从当前状态到目标状态的行动序列"""

    def register_action(self, action: GOAPAction) -> None: ...
```

## CharacterEntity — 完整角色实体 ⭐ 核心

```python
class CharacterEntity:
    """完整角色实体

    整合子系统:
    - personality: OceanPersonality (OCEAN人格)
    - emotion: PADState (基础情感)
    - extended_emotion: ExtendedPAD (扩展情感+七情权重)
    - desire_engine: DesireEngine (欲望驱动)
    - memory: MemoryStore (记忆存储)
    - motivation: MotivationEngine (三层动机)
    - goap_planner: GOAPPlanner (目标规划)
    - utility_ai: UtilityBasedAI (效用决策)
    - cem_planner: CEMPlanner (交叉熵方法)
    - social_perception: SocialPerception (社交感知)

    决策循环:
      perceive → motivation.evaluate → GOAP.plan → IAUS.score
      → personality.modify → emotion.apply → CEM.perturb → execute
    """

    def __init__(
        self,
        entity_id: Optional[EntityId] = None,
        name: str = "",
        personality: Optional[OceanPersonality] = None,
        emotion: Optional[PADState] = None,
        extended_emotion: Optional[ExtendedPAD] = None,
        desire_engine: Optional[DesireEngine] = None,
        memory: Optional[MemoryStore] = None,
        motivation: Optional[MotivationEngine] = None,
        goap_planner: Optional[GOAPPlanner] = None,
        utility_ai: Optional[UtilityBasedAI] = None,
        cem_planner: Optional[CEMPlanner] = None,
        social_perception: Optional[SocialPerception] = None,
        config: Optional[CharacterConfig] = None,
    ) -> None: ...

    async def decide(
        self,
        context: Dict[str, Any],
        available_actions: Optional[List[GOAPAction]] = None,
        available_behaviors: Optional[List[BehaviorOption]] = None,
    ) -> Optional[GOAPAction]:
        """完整决策循环，返回选定的行动"""

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典 (用于序列化/快照)"""

    @property
    def current_goal(self) -> Optional[str]: ...
    @property
    def current_plan(self) -> Optional[List[GOAPAction]]: ...
```

## MemoryStore — 角色记忆存储

```python
class MemoryType(str, Enum):
    EPISODIC = "episodic"      # 情景记忆 (事件)
    SEMANTIC = "semantic"      # 语义记忆 (知识)
    FLASHBULB = "flashbulb"    # 闪光灯记忆 (高情绪)


@dataclass
class MemoryEntry:
    entry_id: str
    content: str
    memory_type: MemoryType
    importance: float = 0.5
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryStore:
    """分层记忆存储系统

    特性:
    - 分层管理: 近期/中期/长期三层
    - 自动衰减: 访问频率和重要性加权
    - 容量限制: 可配置每层容量
    """

    def __init__(self, config: Optional[CharacterConfig] = None) -> None: ...

    def store(self, entry: MemoryEntry) -> str:
        """存储记忆条目，返回entry_id"""

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[MemoryType] = None,
    ) -> List[MemoryEntry]:
        """相关性检索"""

    def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]: ...
    def forget(self, entry_id: str) -> bool: ...
    def get_stats(self) -> Dict[str, int]: ...
```

## 使用示例

```python
from luqi_engine.character.character_entity import CharacterEntity
from luqi_engine.character.personality import OceanPersonality
from luqi_engine.character.emotion import PADState
from luqi_engine.character.desire import DesireEngine
from luqi_engine.character.motivation import Motive, MotivationEngine

# 创建角色
char = CharacterEntity(
    entity_id="hero_001",
    name="李逍遥",
    personality=OceanPersonality(
        openness=75,      # 探索欲强
        conscientiousness=60,
        extraversion=80,   # 外向
        agreeableness=65,
        neuroticism=35,    # 情绪稳定
    ),
    emotion=PADState(pleasure=0.3, arousal=0.5, dominance=0.2),
)

# 设置动机
motivation = MotivationEngine(motives=[
    Motive("survival", "生存", layer=1, base_intensity=0.9),
    Motive("belonging", "归属", layer=2, base_intensity=0.7),
    Motive("self_actual", "自我实现", layer=3, base_intensity=0.5),
])
char.motivation = motivation

# 决策
action = await char.decide(context={"danger_level": 0.3})
print(f"选定行动: {action.action_name if action else '无'}")
print(f"当前目标: {char.current_goal}")
```
