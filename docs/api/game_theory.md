# 博弈论系统 (Game Theory)

Phase 4 核心模块：信念推断、混合策略纳什均衡、威胁可信度评估、机制设计。

## 模块概览

```
luqi_engine/game_theory/
├── belief_system.py      — BeliefSystem Beta分布信念管理
├── mixed_strategy.py     — MixedStrategyEngine Softmax策略选择
├── threat_credibility.py — ThreatCredibilityEngine 威胁可信度
├── mechanism_design.py   — MechanismDesigner 机制设计
└── types.py              — 全部数据类型和枚举定义
```

## BeliefSystem — 信念系统 ⭐ 核心

```python
class BeliefSystem:
    """基于贝叶斯推断的多维概率信念管理

    数据结构:
      _beliefs: OrderedDict[target_id, Dict[BeliefDimension, BeliefState]]

    算法:
    - Beta-Bernoulli 共轭闭式更新 (α += evidence, β += 1-evidence)
    - 维度耦合传播 (单向, 深度=1)
    - 时间指数衰减 (向无信息先验回归)
    - LRU淘汰 (max_tracked_targets=20)

    学术依据:
    - Harsanyi 转换: 不完全信息博弈 → 类型空间概率分布
    - Beta-Bernoulli 共轭: 后验 = 先验 + 数据计数
    """

    MAX_TRACKED_TARGETS: ClassVar[int] = 20

    def __init__(
        self,
        character_id: str,
        config: Optional[BeliefSystemConfig] = None,
    ) -> None: ...

    @property
    def config(self) -> BeliefSystemConfig: ...

    def observe(
        self,
        target_id: str,
        dimension: BeliefDimension,
        observation: Observation,
    ) -> BeliefUpdateOutcome:
        """记录观测并更新信念状态

        更新公式:
          effective_evidence = value × type_reliability × source_reliability × strength
          α_new = α_old + effective_evidence
          β_new = β_old + (1 - effective_evidence) × decay_factor

        返回: BeliefUpdateOutcome (UPDATED/WEAK/NO_CHANGE/TARGET_FULL)
        """

    def get_belief(
        self,
        target_id: str,
        dimension: BeliefDimension,
    ) -> Optional[BeliefState]:
        """获取指定目标在指定维度上的信念状态"""

    def get_mean_belief(self, target_id: str, dimension: BeliefDimension) -> float:
        """获取Beta分布的期望值 E = α / (α + β)"""

    def predict(self, target_id: str, dimension: BeliefDimension) -> float:
        """预测未来行为倾向 (考虑时间衰减后的期望值)"""

    def forget(self, target_id: str) -> int:
        """移除目标的全部信念记录，返回被移除的维度数"""

    @property
    def tracked_target_count(self) -> int: ...
    @property
    def total_belief_count(self) -> int: ...
```

### BeliefDimension 枚举

| 维度 | 说明 | 默认先验(α,β) |
|------|------|---------------|
| `COOPERATIVITY` | 合作意愿 | (3.0, 2.0) |
| `HONESTY` | 诚实程度 | (4.0, 1.0) |
| `THREAT_LEVEL` | 威胁等级 | (1.0, 4.0) |
| `STABILITY` | 行为稳定性 | (3.5, 1.5) |
| `ALIGNMENT` | 目标一致性 | (2.0, 3.0) |
| `COMPETENCE` | 能力水平 | (3.0, 2.0) |

### ObservationType 观测类型可靠性

| 类型 | 可靠性系数 | 说明 |
|------|-----------|------|
| `DIRECT_ACTION` | 1.0 | 直接观察到的行动 |
| `REPORTED_INFO` | 0.7 | 他方报告的信息 |
| `SIGNAL_SENT` | 0.6 | 发出的信号 |
| `ABSENCE_OF_ACTION` | 0.5 | 未采取行动（沉默） |
| `CONTEXTUAL_CUE` | 0.3 | 上下文线索推断 |

### 维度耦合传播规则

```
COOPERATIVITY (+0.30) → HONESTY
COOPERATIVITY (-0.20) → THREAT_LEVEL
THREAT_LEVEL (-0.30) → STABILITY
HONESTY (-0.40) → COOPERATIVITY
ALIGNMENT (+0.25) → COOPERATIVITY
COMPETENCE (+0.15) → THREAT_LEVEL
```

## MixedStrategyEngine — 混合策略引擎

```python
class MixedStrategyEngine:
    """基于Softmax (Boltzmann) 的概率化策略选择

    算法流程:
    1. 收集各动作的payoff估计
    2. 应用场景温度映射调整τ
    3. log-sum-exp稳定化softmax计算
    4. 强制最小概率保底 (MIN_PROBABILITY)
    5. 归一化并计算熵
    6. 熵 < entropy_floor 时重新分配

    温度参数 τ 物理意义:
    - τ → 0+: 贪婪选择 (最大payoff动作概率→1)
    - τ = 1.0: 标准softmax
    - τ → ∞: 均匀随机

    场景关键词映射:
      crisis/danger/combat → τ=0.3~0.4 (果断)
      negotiation/peaceful → τ=0.8~3.0 (灵活)
      safe/exploration → τ=2.5~3.0 (探索)
    """

    def __init__(self, config: Optional[MixedStrategyConfig] = None) -> None: ...

    @property
    def config(self) ->MixedStrategyConfig: ...

    def generate(
        self,
        payoffs: List[StrategyPayoff],
        temperature: Optional[float] = None,
        urgency_level: float = 1.0,
        scene_context: Optional[str] = None,
    ) -> MixedStrategyProfile:
        """生成混合策略剖面

        Args:
            payoffs: 各动作收益估计列表
            temperature: 显式温度 (None=自动)
            urgency_level: 紧急度 [0.5, 3.0]
            scene_context: 场景描述 (用于关键词匹配)

        Returns:
            MixedStrategyProfile (action_probabilities, entropy, temperature_used, ...)
        """
```

### MixedStrategyProfile 输出结构

```python
@dataclass
class MixedStrategyProfile:
    action_probabilities: Dict[StrategyAction, float]  # 动作→概率映射
    entropy: float                                    # 分布熵
    temperature_used: float                           # 实际使用的温度
    dominant_action: Optional[StrategyAction]         # 主导动作
    is_pure_strategy: bool                            # 是否退化为纯策略
    generated_at: float                               # 生成时间戳
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### StrategyAction & StrategyPayoff

```python
class StrategyAction(Enum):
    COOPERATE = "cooperate"
    DEFECT = "defect"
    ATTACK = "attack"
    FLEE = "flee"
    NEGOTIATE = "negotiate"
    OBSERVE = "observe"
    DECEIVE = "deceive"


@dataclass
class StrategyPayoff:
    action: StrategyAction
    expected_payoff: float           # 期望收益
    confidence: float = 1.0          # 收益置信度
    context: Dict[str, Any] = field(default_factory=dict)
```

## ThreatCredibilityEngine — 威胁可信度引擎

```python
class ThreatCredibilityEngine:
    """四分量合成威胁可信度评估

    合成公式:
      overall = w_c·consistency + w_cs·cost_signal + w_r·recency + w_p·pattern

    各分量算法:
    - consistency: EMA(执行率), smoothing=config.consistency_smoothing
    - cost_signal: Σ(cost_i^power) / N, power=config.cost_credibility_power
    - recency: Σ(w_i·executed_i), w_i = exp(-ln(2)·Δt/T_half)
    - pattern: 1 / (CV + ε), CV=σ/μ of execution delays

    承诺等级成本乘数:
      NONE(0.3) < VERBAL(0.5) < MATERIAL(0.8) < IRREVERSIBLE(1.0)
    """

    def __init__(
        self,
        character_id: str,
        config: Optional[ThreatCredibilityConfig] = None,
    ) -> None: ...

    @property
    def config(self) -> ThreatCredibilityConfig: ...

    def record_threat(self, record: ThreatRecord) -> None:
        """记录新的威胁声明"""

    def assess(self, entity_id: str) -> CredibilityScore:
        """评估实体当前的可信度评分"""

    def get_history(self, entity_id: str) -> List[ThreatRecord]:
        """获取实体的全部威胁记录"""
```

### ThreatRecord & CredibilityScore

```python
@dataclass
class ThreatRecord:
    threat_type: ThreatType               # BLUFF/COMMITMENT/SIGNALING/RETALIATORY/DETERRENCE
    commitment_level: CommitmentLevel     # NONE/VERBAL/MATERIAL/IRREVERSIBLE
    declared_action: str                  # 声称要执行的行动
    estimated_cost: float                 # 估算执行成本
    executed: bool                        # 是否已执行
    execution_delay: float = 0.0          # 执行延迟(秒)
    timestamp: float = field(default_factory=time.time)


@dataclass
class CredibilityScore:
    overall: float                        # 综合可信度 [0, 1]
    consistency: float                    # 声明-行为一致性
    cost_signal: float                    # 成本信号强度
    recency: float                        # 近期权重
    pattern: float                        # 模式稳定性
    record_count: int                     # 记录数
    last_assessed_at: float               # 最后评估时间
```

## MechanismDesigner — 机制设计器

```python
class MechanismDesigner:
    """激励机制设计工具

    功能:
    - 设计满足激励相容性(IC)的规则
    - 参数敏感性分析
    - 均衡预测
    """

    def __init__(self, config: Optional[MechanismConfig] = None) -> None: ...

    def propose_mechanism(
        self,
        objective: str,
        participants: List[str],
        constraints: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """提出机制设计方案"""

    def check_incentive_compatibility(
        self,
        mechanism: Dict[str, Any],
    ) -> IncentiveCompatibilityReport:
        """检查激励相容性"""

    def predict_equilibrium(
        self,
        mechanism: Dict[str, Any],
    ) -> EquilibriumPrediction:
        """预测均衡结果"""
```

## 使用示例

```python
from luqi_engine.game_theory.belief_system import BeliefSystem, BeliefDimension, Observation, ObservationType
from luqi_engine.game_theory.mixed_strategy import MixedStrategyEngine, StrategyPayoff, StrategyAction
from luqi_engine.game_theory.threat_credibility import ThreatCredibilityEngine, ThreatRecord, ThreatType, CommitmentLevel

# 初始化信念系统
belief_sys = BeliefSystem(character_id="hero_001")

# 记录观察
outcome = belief_sys.observe(
    target_id="villain_001",
    dimension=BeliefDimension.COOPERATIVITY,
    observation=Observation(
        observation_type=ObservationType.DIRECT_ACTION,
        evidence_value=0.9,       # 高合作证据
        source_reliability=0.95,
        strength_weight=0.8,
    ),
)
print(f"更新结果: {outcome.name}")

# 查询信念
mean_coop = belief_sys.get_mean_belief("villian_001", BeliefDimension.COOPERATIVITY)
print(f"合作度期望: {mean_coop:.3f}")

# 混合策略生成
ms_engine = MixedStrategyEngine()
profile = ms_engine.generate(payoffs=[
    StrategyPayoff(action=StrategyAction.NEGOTIATE, expected_payoff=0.7),
    StrategyPayoff(action=StrategyAction.ATTACK, expected_payoff=0.4),
    StrategyPayoff(action=StrategyAction.FLEE, expected_payoff=0.2),
], scene_context="negotiation")
print(f"主导动作: {profile.dominant_action}")
print(f"分布熵: {profile.entropy:.3f}")

# 威胁可信度评估
tc_engine = ThreatCredibilityEngine(character_id="hero_001")
tc_engine.record_threat(ThreatRecord(
    threat_type=ThreatType.COMMITMENT,
    commitment_level=CommitmentLevel.IRREVERSIBLE,
    declared_action="attack_if_betrayed",
    estimated_cost=0.8,
    executed=True,
))
score = tc_engine.assess(entity_id="ally_001")
print(f"综合可信度: {score.overall:.3f}")
```
