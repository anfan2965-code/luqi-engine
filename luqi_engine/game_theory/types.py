"""
博弈论能力层共享类型定义 — Phase 4 所有模块共用的枚举、数据结构和常量
包含: BeliefDimension / ThreatType / StrategyAction / MechanismParameter 等
以及: Observation / ThreatRecord / StrategyPayoff 等核心数据类

设计原则:
- 所有数值字段通过 __post_init__ 范围钳制, 无硬编码魔法数字
- 枚举值语义清晰, 可直接用于 switch/match 逻辑
- dataclass 全部 frozen=False (需要修改), 但提供 to_dict() 序列化接口
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple


# ============================================================
# 常量定义（模块私有，前缀_）
# ============================================================

_BELIEF_DECISIVE_THRESHOLD: float = 0.25
_BELIEF_CONFIDENCE_THRESHOLD: float = 0.6
_LN2: float = math.log(2.0)

_BELIEF_MIN_ALPHA: float = 0.1
_BELIEF_MIN_BETA: float = 0.1
_BELIEF_MAX_ALPHA_BETA: float = 100.0

_CREDIBILITY_RELIABLE_THRESHOLD: float = 0.7

_STRATEGY_MIN_PROBABILITY: float = 0.01

_OBSERVATION_EVIDENCE_MIN: float = 0.0
_OBSERVATION_EVIDENCE_MAX: float = 1.0
_OBSERVATION_RELIABILITY_MIN: float = 0.0
_OBSERVATION_RELIABILITY_MAX: float = 1.0

_THREAT_COST_MIN: float = 0.0
_THREAT_COST_MAX: float = 1.0


def _clamp(value: float, low: float, high: float) -> float:
    """将 value 钳制到 [low, high] 区间"""
    return max(low, min(high, high))


# ============================================================
# BeliefSystem 相关类型
# ============================================================

class BeliefDimension(Enum):
    """
    信念维度 — 角色对他人的多维度概率推断空间
    
    每个维度独立维护一个 Beta 分布的信念状态,
    维度间通过耦合规则产生间接影响。
    
    维度选择依据:
    - COOPERATIVITY: 核心社交维度, 决定合作/背叛倾向推断
    - THREAT_LEVEL: 安全相关, 影响恐惧/回避行为
    - COMPETENCE: 能力评估, 影响威胁可信度判断
    - ALIGNMENT: 目标一致性, 预测长期合作潜力
    - HONESTY: 诚实度, 区分信号型vs信息型行为
    - STABILITY: 行为稳定性, 预测未来行为可预测性
    """
    
    COOPERATIVITY = auto()
    THREAT_LEVEL = auto()
    COMPETENCE = auto()
    ALIGNMENT = auto()
    HONESTY = auto()
    STABILITY = auto()


class ObservationType(Enum):
    """
    观测类型 — 分类输入证据的来源和性质
    
    不同类型的观测具有不同的可靠性折扣:
    - DIRECT_ACTION: 最高可靠性 (亲眼所见)
    - REPORTED_INFO: 中等可靠性 (可能失真)
    - SIGNAL_SENT: 较低可靠性 (可能是伪装)
    - ABSENCE_OF_ACTION: 特殊处理 (沉默的含义依赖上下文)
    - CONTEXTUAL_CUE: 低可靠性 (模糊线索)
    """
    
    DIRECT_ACTION = auto()
    REPORTED_INFO = auto()
    SIGNAL_SENT = auto()
    ABSENCE_OF_ACTION = auto()
    CONTEXTUAL_CUE = auto()


class BeliefUpdateOutcome(Enum):
    """
    信念更新结果分类
    
    用于:
    1. observe() 的返回值, 告知调用者更新性质
    2. 触发条件判断 (如 REVERSED 时可能触发特殊事件)
    3. 日志记录和分析统计
    """
    
    STRENGTHENED = auto()
    WEAKENED = auto()
    REVERSED = auto()
    UNCHANGED = auto()


@dataclass
class Observation:
    """
    单次观测记录 — BeliefSystem.observe() 的输入数据
    
    Attributes:
        observation_type: 观测来源类型 (影响可靠性折扣)
        evidence_value: 证据值 [0, 1], 1=完全支持正向信念, 0=完全支持负向
        source_reliability: 来源自身可靠性 [0, 1] (进一步调节有效证据强度)
        timestamp: 观测发生时间戳 (用于衰减计算)
        context_tags: 上下文标签列表 (用于情境加权, 可选)
        description: 人类可读描述 (用于日志/Prompt输出)
    
    使用示例:
        >>> obs = Observation(
        ...     observation_type=ObservationType.DIRECT_ACTION,
        ...     evidence_value=0.9,
        ...     description="Bob在战斗中掩护了我",
        ... )
    """
    
    observation_type: ObservationType = ObservationType.DIRECT_ACTION
    evidence_value: float = 0.5
    source_reliability: float = 1.0
    timestamp: float = 0.0
    context_tags: List[str] = field(default_factory=list)
    description: str = ""
    
    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()
        self.evidence_value = _clamp(
            self.evidence_value,
            _OBSERVATION_EVIDENCE_MIN,
            _OBSERVATION_EVIDENCE_MAX,
        )
        self.source_reliability = _clamp(
            self.source_reliability,
            _OBSERVATION_RELIABILITY_MIN,
            _OBSERVATION_RELIABILITY_MAX,
        )


@dataclass
class BeliefState:
    """
    单维度信念状态 — 基于 Beta(α, β) 分布的参数化表示
    
    数学模型:
    - 先验: Beta(α₀, β₀), 默认 α₀=β₀=1 (无信息均匀先验)
    - 后验: Beta(α₀+Σeᵢ, β₀+Σ(1-eᵢ)), 其中 eᵢ 为第i次有效证据
    - 期望: E[belief] = α / (α + β) ∈ [0, 1]
    - 方差: Var = αβ / ((α+β)²(α+β+1))
    - 置信度代理: conf ≈ 1 - √Var ∈ [0, 1]
    
    时间衰减:
    - 向先验回归: α' = 1 + (α-1)·exp(-ln2·t/T½), β' 同理
    - 半衰期 T_half 控制衰减速度 (默认30天)
    
    Attributes:
        target_id: 被观察目标实体ID
        dimension: 信念维度 (COOPERATIVITY / THREAT_LEVEL 等)
        alpha: 正向伪计数 (Beta分布α参数)
        beta_param: 负向伪计数 (Beta分布β参数, 避免与Python关键字冲突)
        last_updated: 最后更新时间戳
        total_observations: 累计观测次数
        strong_evidences: 强证据次数 (|e-0.5|>0.3 的观测)
        half_life_days: 衰减半衰期天数
    """
    
    target_id: str = ""
    dimension: BeliefDimension = BeliefDimension.COOPERATIVITY
    
    alpha: float = 1.0
    beta_param: float = 1.0
    
    last_updated: float = 0.0
    total_observations: int = 0
    strong_evidences: int = 0
    half_life_days: float = 30.0
    
    _MIN_ALPHA: ClassVar[float] = _BELIEF_MIN_ALPHA
    _MIN_BETA: ClassVar[float] = _BELIEF_MIN_BETA
    _MAX_ALPHA_BETA: ClassVar[float] = _BELIEF_MAX_ALPHA_BETA
    
    def __post_init__(self) -> None:
        self.alpha = max(self.alpha, self._MIN_ALPHA)
        self.beta_param = max(self.beta_param, self._MIN_BETA)
        self.alpha = min(self.alpha, self._MAX_ALPHA_BETA)
        self.beta_param = min(self.beta_param, self._MAX_ALPHA_BETA)
    
    @property
    def expected_value(self) -> float:
        """
        信念期望值 E[belief] = α / (α + β)
        
        Returns:
            期望信念值 [0.0, 1.0], 0.5 表示完全不确定
        """
        total = self.alpha + self.beta_param
        if total <= 0:
            return 0.5
        return self.alpha / total
    
    @property
    def confidence(self) -> float:
        """
        置信度 [0.0, 1.0]
        
        基于 Beta 分布方差的单调递减函数:
        conf = 1 - √Var, 其中 Var = αβ / ((α+β)²(α+β+1))
        
        特性:
        - α+β 小 → 方差大 → 置信度低 (观测不足)
        - α+β 大 → 方差小 → 置信度高 (充分观测)
        - α≈β → 即使总数大, 若接近0.5则置信度也受限
        """
        total = self.alpha + self.beta_param
        if total <= 0:
            return 0.0
        variance = (self.alpha * self.beta_param) / (
            (total * total) * (total + 1)
        ) if total > 0 else 0.25
        return 1.0 - min(math.sqrt(variance), 1.0)
    
    @property
    def is_decisive(self) -> bool:
        """
        是否已形成决定性信念
        
        判定条件 (需同时满足):
        1. |E - 0.5| > decisive_threshold (明显偏向一侧)
        2. confidence > confidence_threshold (足够确信)
        
        Returns:
            True 如果信念已足够确定可用于决策
        """
        return (
            abs(self.expected_value - 0.5) > _BELIEF_DECISIVE_THRESHOLD
            and self.confidence > _BELIEF_CONFIDENCE_THRESHOLD
        )
    
    def apply_decay(self, days_elapsed: float) -> None:
        """
        应用时间衰减 — 将 α, β 向无信息先验 (1, 1) 回归
        
        衰减公式 (指数衰减):
        α' = 1 + (α - 1) · exp(-ln(2) · t / T_half)
        β' = 1 + (β - 1) · exp(-ln(2) · t / T_half)
        
        特性:
        - t = 0 → 无变化
        - t = T_half → 距离先验减半
        - t → ∞ → 回归到 (1, 1) 即 E=0.5, conf=0
        
        Args:
            days_elapsed: 经过的天数 (非负数)
        """
        if days_elapsed <= 0:
            return
        decay_factor = math.exp(-_LN2 * days_elapsed / self.half_life_days)
        self.alpha = 1.0 + (self.alpha - 1.0) * decay_factor
        self.beta_param = 1.0 + (self.beta_param - 1.0) * decay_factor
        self.alpha = max(self.alpha, self._MIN_ALPHA)
        self.beta_param = max(self.beta_param, self._MIN_BETA)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 (用于持久化/传输/日志)"""
        return {
            "target_id": self.target_id,
            "dimension": self.dimension.name,
            "alpha": round(self.alpha, 4),
            "beta": round(self.beta_param, 4),
            "expected_value": round(self.expected_value, 4),
            "confidence": round(self.confidence, 4),
            "is_decisive": self.is_decisive,
            "total_observations": self.total_observations,
            "last_updated": self.last_updated,
        }


@dataclass
class BeliefSystemConfig:
    """
    信念系统配置 — 控制 BeliefSystem 更新行为的全部可调参数
    
    设计原则: 所有行为参数化, 零硬编码魔法数字
    每个参数都有明确的物理/统计学含义和合理取值范围
    """
    
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    default_half_life_days: float = 30.0
    strong_evidence_weight: float = 2.0
    weak_evidence_weight: float = 0.5
    direct_action_reliability: float = 1.0
    reported_info_discount: float = 0.7
    signal_sent_reliability: float = 0.6
    decisive_threshold: float = 0.25
    confidence_threshold: float = 0.6
    max_tracked_targets: int = 20
    max_observation_history: int = 100


# ============================================================
# ThreatCredibility 相关类型
# ============================================================

class ThreatType(Enum):
    """
    威胁类型分类 — 影响可信度计算的初始权重分配
    
    类型含义:
    - BLUFF: 虚张声势, 零/低成本, 天然低可信
    - COMMITMENT: 承诺型, 有实际代价, 高可信潜力
    - SIGNALING: 信号型, 展示能力但不一定执行, 中等可信
    - RETALIATORY: 报复性, 基于历史模式, 取决于历史一致性
    - DETERRENCE: 威慑性, 预防性质, 通常高成本高可信
    """
    
    BLUFF = auto()
    COMMITMENT = auto()
    SIGNALING = auto()
    RETALIATORY = auto()
    DETERRENCE = auto()


class CommitmentLevel(Enum):
    """
    承诺等级 — 描述威胁发出者的代价承诺程度
    
    与可信度的关系: 成本越高 → 越难虚假威胁 → 越可信
    经济学依据: 廉价磋商定理 (Farrell, 1987)
    """
    
    NONE = auto()
    VERBAL = auto()
    MATERIAL = auto()
    IRREVERSIBLE = auto()


@dataclass
class ThreatRecord:
    """
    单次威胁记录 — ThreatCredibilityEngine 的输入单元
    
    Attributes:
        threat_type: 威胁类型分类
        content: 威胁内容的人类可读描述
        commitment_level: 承诺等级 (影响 cost_signal 分量)
        estimated_cost: 估算执行成本 [0, 1], 用于成本信号计算
        was_executed: 是否实际执行 (影响 consistency 分量)
        execution_delay: 执行延迟秒数 (未执行时为 None)
        timestamp: 威胁发出时间戳
    """
    
    threat_type: ThreatType = ThreatType.BLUFF
    content: str = ""
    commitment_level: CommitmentLevel = CommitmentLevel.VERBAL
    estimated_cost: float = 0.5
    was_executed: bool = False
    execution_delay: Optional[float] = None
    timestamp: float = 0.0
    
    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()
        self.estimated_cost = _clamp(
            self.estimated_cost, _THREAT_COST_MIN, _THREAT_COST_MAX
        )


@dataclass
class CredibilityScore:
    """
    可信度评分 — 四分量加权合成结果
    
    合成公式:
    overall = w_c·consistency + w_cs·cost_signal + w_r·recency + w_p·pattern
    
    各分量含义:
    - consistency: 声明-行为一致性的指数移动平均
    - cost_signal: 基于执行成本的凸函数得分
    - recency: 近期行为的指数衰减加权得分
    - pattern: 行为模式稳定性 (变异系数倒数)
    
    Attributes:
        entity_id: 被评估实体ID
        overall_score: 综合可信度 [0, 1]
        consistency_score: 一致性分量 [0, 1]
        cost_signal_score: 成本信号分量 [0, 1]
        recency_score: 近期性分量 [0, 1]
        pattern_score: 模式稳定性分量 [0, 1]
        sample_size: 基于多少条威胁记录计算
        last_updated: 最后更新时间
        is_reliable: 是否达到"可靠"阈值
    """
    
    entity_id: str = ""
    overall_score: float = 0.5
    consistency_score: float = 0.5
    cost_signal_score: float = 0.5
    recency_score: float = 0.5
    pattern_score: float = 0.5
    
    sample_size: int = 0
    last_updated: float = 0.0
    is_reliable: bool = False
    
    _RELIABLE_THRESHOLD: ClassVar[float] = _CREDIBILITY_RELIABLE_THRESHOLD
    
    def __post_init__(self) -> None:
        if not self.last_updated:
            self.last_updated = time.time()
        self.is_reliable = self.overall_score >= self._RELIABLE_THRESHOLD
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "overall_score": round(self.overall_score, 3),
            "consistency_score": round(self.consistency_score, 3),
            "cost_signal_score": round(self.cost_signal_score, 3),
            "recency_score": round(self.recency_score, 3),
            "pattern_score": round(self.pattern_score, 3),
            "sample_size": self.sample_size,
            "is_reliable": self.is_reliable,
        }


@dataclass
class ThreatCredibilityConfig:
    """
    威胁可信度系统配置 — 四分量权重与算法参数
    """
    
    weight_consistency: float = 0.35
    weight_cost_signal: float = 0.25
    weight_recency: float = 0.20
    weight_pattern: float = 0.20
    
    recency_half_life_days: float = 14.0
    cost_credibility_power: float = 0.7
    base_credibility: float = 0.3
    consistency_smoothing: float = 0.8
    
    reliable_threshold: float = 0.7
    untrustworthy_threshold: float = 0.3
    max_tracked_entities: int = 15


# ============================================================
# MixedStrategy 相关类型
# ============================================================

class StrategyAction(Enum):
    """
    离散策略动作空间 — 角色在交互中的可选策略集合
    
    动作设计考量:
    - 覆盖从纯合作到纯对抗的全谱系
    - 包含信息收集(OBSERVE)和回避(WITHDRAW)等非对抗选项
    - DECEIVE 为高级策略, 仅在高复杂度场景启用
    - 数量为8个, 保证混合策略有足够的熵空间
    """
    
    COOPERATE = auto()
    DEFECT = auto()
    EXPLOIT = auto()
    OBSERVE = auto()
    WITHDRAW = auto()
    NEGOTIATE = auto()
    DECEIVE = auto()
    SUPPORT = auto()


@dataclass
class StrategyPayoff:
    """
    策略收益估计 — MixedStrategyEngine.softmax() 的输入
    
    模型假设: 2人博弈简化模型
    - 我方选择 action, 对手选择 合作(Cooperate) 或 背叛(Defect)
    - payoff_if_cooperate: 对手合作时我方的收益
    - payoff_if_defect: 对手背叛时我方的收益
    - estimated_probability: 对手合作的先验概率 (来自 BeliefSystem)
    
    期望收益: E[payoff] = P(coop)·payoff_coop + (1-P)·payoff_defect
    风险度量: risk = |payoff_coop - payoff_defect| (收益方差代理)
    """
    
    action: StrategyAction = StrategyAction.COOPERATE
    payoff_if_cooperate: float = 0.0
    payoff_if_defect: float = 0.0
    estimated_probability: float = 0.5
    
    @property
    def expected_payoff(self) -> float:
        p = self.estimated_probability
        return p * self.payoff_if_cooperate + (1 - p) * self.payoff_if_defect
    
    @property
    def risk(self) -> float:
        return abs(self.payoff_if_cooperate - self.payoff_if_defect)


@dataclass
class MixedStrategyProfile:
    """
    混合策略剖面 — Softmax (Boltzmann) 分布输出
    
    核心公式: P(action_i) = exp(payoff_i / τ) / Σ_j exp(payoff_j / τ)
    
    约束条件:
    - Σ P(action) = 1.0 (概率归一化)
    - P(action) ≥ MIN_PROBABILITY (最小概率保底, 保证探索性)
    - entropy ≥ entropy_floor (熵下限, 避免过度确定)
    
    信息论属性:
    - H = -Σ p_i · log(p_i) (香农熵, 单位: nat)
    - temperature τ 控制熵的大小
      τ → 0: 贪婪 (H→0), τ → ∞: 均匀 (H→log(N))
    
    Attributes:
        action_probabilities: 动作→概率映射字典
        temperature: 生成此剖面时的温度参数
        entropy: 当前剖面的香农熵
        dominant_action: 最高概率的动作 (None 如果为空)
        generated_at: 生成时间戳
    """
    
    action_probabilities: Dict[StrategyAction, float] = field(default_factory=dict)
    temperature: float = 1.0
    entropy: float = 0.0
    dominant_action: Optional[StrategyAction] = None
    generated_at: float = 0.0
    
    _MIN_PROBABILITY: ClassVar[float] = _STRATEGY_MIN_PROBABILITY
    _DEFAULT_ACTIONS: ClassVar[List[StrategyAction]] = [
        StrategyAction.COOPERATE,
        StrategyAction.DEFECT,
        StrategyAction.OBSERVE,
        StrategyAction.WITHDRAW,
        StrategyAction.NEGOTIATE,
    ]
    
    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = time.time()
        if self.action_probabilities:
            self._normalize()
            self._compute_entropy()
            self.dominant_action = self._find_dominant()
    
    def _normalize(self) -> None:
        """概率归一化 + 最小概率约束"""
        total = sum(self.action_probabilities.values())
        if total > 0:
            for k in self.action_probabilities:
                self.action_probabilities[k] /= total
        for k in list(self.action_probabilities.keys()):
            if self.action_probabilities[k] < self._MIN_PROBABILITY:
                self.action_probabilities[k] = self._MIN_PROBABILITY
        total = sum(self.action_probabilities.values())
        if total > 0:
            for k in self.action_probabilities:
                self.action_probabilities[k] /= total
    
    def _compute_entropy(self) -> None:
        """计算香农熵 H = -Σ p·log(p)"""
        h = 0.0
        for p in self.action_probabilities.values():
            if p > 1e-10:
                h -= p * math.log(p)
        self.entropy = h
    
    def _find_dominant(self) -> Optional[StrategyAction]:
        """找到最高概率的动作"""
        if not self.action_probabilities:
            return None
        return max(
            self.action_probabilities, key=self.action_probabilities.get
        )
    
    def sample(self, rng: Any) -> StrategyAction:
        """
        根据概率分布采样一个动作
        
        使用逆变换采样法 (Inverse Transform Sampling):
        生成均匀随机数 r ~ U(0,1), 找到最小的 k 使 Σ_{i≤k} p_i ≥ r
        
        Args:
            rng: 实现了 uniform(0,1) 方法的随机数生成器
            
        Returns:
            采样的 StrategyAction
        """
        if not self.action_probabilities:
            return StrategyAction.OBSERVE
        r = getattr(rng, 'uniform', lambda a, b: 0.5)(0.0, 1.0)
        cumulative = 0.0
        sorted_actions = sorted(
            self.action_probabilities.items(), key=lambda x: x[1]
        )
        for action, prob in sorted_actions:
            cumulative += prob
            if r <= cumulative:
                return action
        return sorted_actions[-1][0] if sorted_actions else StrategyAction.OBSERVE
    
    def to_dict(self) -> Dict[str, Any]:
        probs = {k.name: round(v, 4) for k, v in self.action_probabilities.items()}
        return {
            "action_probabilities": probs,
            "temperature": round(self.temperature, 3),
            "entropy": round(self.entropy, 3),
            "dominant_action": self.dominant_action.name if self.dominant_action else None,
        }


@dataclass
class MixedStrategyConfig:
    """
    混合策略引擎配置 — 温度参数范围与场景映射
    """
    
    min_temperature: float = 0.1
    max_temperature: float = 5.0
    default_temperature: float = 1.0
    min_entropy_ratio: float = 0.3
    absolute_min_entropy: float = 0.5
    crisis_temperature: float = 0.3
    normal_temperature: float = 1.0
    safe_temperature: float = 2.0
    urgency_low_temp: float = 0.5
    urgency_high_temp: float = 3.0
    default_actions: List[StrategyAction] = field(default_factory=lambda: [
        StrategyAction.COOPERATE,
        StrategyAction.DEFECT,
        StrategyAction.OBSERVE,
        StrategyAction.WITHDRAW,
        StrategyAction.NEGOTIATE,
    ])


# ============================================================
# MechanismDesign 相关类型
# ============================================================

class MechanismParameter(Enum):
    """
    可调机制参数 — MechanismDesign 层操纵均衡的旋钮
    
    参数分组:
    - 激励结构: REWARD_COOPERATION_BONUS, PUNISHMENT_DEFECT_COST
    - 信息环境: INFORMATION_TRANSPARENCY
    - 子系统阈值: SHADOW_ACTIVATION_THRESHOLD, etc.
    - 动态速率: SOCIAL_EVOLUTION_SPEED, BELIEF_UPDATE_RATE, etc.
    - 策略约束: MIXED_STRATEGY_ENTROPY_FLOOR, THREAT_CREDIBILITY_DECAY
    """
    
    REWARD_COOPERATION_BONUS = auto()
    PUNISHMENT_DEFECT_COST = auto()
    INFORMATION_TRANSPARENCY = auto()
    SHADOW_ACTIVATION_THRESHOLD = auto()
    MEMORY_IMPORTANCE_WEIGHT = auto()
    SOCIAL_EVOLUTION_SPEED = auto()
    MOTIVATION_URGENCY_SENSITIVITY = auto()
    BELIEF_UPDATE_RATE = auto()
    MIXED_STRATEGY_ENTROPY_FLOOR = auto()
    THREAT_CREDIBILITY_DECAY = auto()


_MECHANISM_PARAMETER_BOUNDS: Dict[MechanismParameter, Tuple[float, float]] = {
    MechanismParameter.REWARD_COOPERATION_BONUS: (0.0, 2.0),
    MechanismParameter.PUNISHMENT_DEFECT_COST: (0.0, 2.0),
    MechanismParameter.INFORMATION_TRANSPARENCY: (0.0, 1.0),
    MechanismParameter.SHADOW_ACTIVATION_THRESHOLD: (0.1, 0.9),
    MechanismParameter.MEMORY_IMPORTANCE_WEIGHT: (0.0, 1.0),
    MechanismParameter.SOCIAL_EVOLUTION_SPEED: (0.1, 3.0),
    MechanismParameter.MOTIVATION_URGENCY_SENSITIVITY: (0.5, 2.0),
    MechanismParameter.BELIEF_UPDATE_RATE: (0.1, 3.0),
    MechanismParameter.MIXED_STRATEGY_ENTROPY_FLOOR: (0.0, 2.0),
    MechanismParameter.THREAT_CREDIBILITY_DECAY: (0.05, 1.0),
}


@dataclass
class MechanismConfig:
    """
    机制配置 — 一组参数值的完整快照
    
    每个 MechanismParameter 映射到一个 [min, max] 范围内的浮点值。
    set() 方法自动执行范围钳制, get() 方法支持默认值回退。
    """
    
    parameter_values: Dict[MechanismParameter, float] = field(default_factory=dict)
    name: str = ""
    description: str = ""
    created_at: float = 0.0
    
    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.time()
    
    def get(self, param: MechanismParameter, default: float = 0.5) -> float:
        """获取参数值, 不存在则返回默认值"""
        return self.parameter_values.get(param, default)
    
    def set(self, param: MechanismParameter, value: float) -> None:
        """
        设置参数值 (自动范围钳制)
        
        Args:
            param: 机制参数枚举
            value: 目标值 (超出范围时自动钳制到边界)
        """
        bounds = _MECHANISM_PARAMETER_BOUNDS.get(param)
        if bounds:
            lo, hi = bounds
            value = _clamp(value, lo, hi)
        self.parameter_values[param] = value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            k.name: round(v, 4) for k, v in self.parameter_values.items()
        }
    
    def copy(self) -> "MechanismConfig":
        """创建深拷贝"""
        return MechanismConfig(
            parameter_values=dict(self.parameter_values),
            name=self.name,
            description=self.description,
        )


@dataclass
class EquilibriumPrediction:
    """
    均衡预测 — MechanismDesigner.predict_equilibrium() 的输出
    
    通过 Monte Carlo 模拟预测给定 MechanismConfig 下的系统稳态行为。
    """
    
    config_name: str = ""
    predicted_cooperation_rate: float = 0.5
    predicted_conflict_rate: float = 0.2
    predicted_shadow_activation_rate: float = 0.1
    average_relationship_quality: float = 0.5
    narrative_tension_level: float = 0.3
    system_entropy: float = 0.0
    
    sensitivity: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]: ...


@dataclass
class IncentiveCompatibilityReport:
    """
    激励相容性报告 — MechanismDesigner.check_incentive_compatibility() 的输出
    
    核心问题: 在给定配置下, 角色是否有动机偏离目标行为?
    IC 成立条件: 对于所有可能的偏离动作 a', U(target) ≥ U(a')
    """
    
    target_behavior: str = ""
    is_incentive_compatible: bool = False
    deviation_payoff: float = 0.0
    critical_parameters: List[Tuple[str, float]] = field(default_factory=list)
    recommendation: str = ""
    confidence: float = 0.0
