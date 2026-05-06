"""
马斯洛动机引擎 — 扩展8层需求层次 + 情境响应 + 冲突解决
基于Maslow需求层次理论(1943/1970)和Koltko-Rivera扩展(2006)，构建角色动机系统。

核心创新:
- 扩展至8层需求 (原始5层 + 认知/审美/超越)
- 倒金字塔基线配置 (低层满足度高, 高层有成长空间)
- 6种内置情境映射 (自动调整优先级)
- 4种冲突解决策略 (hierarchy_first/context_adaptive/compromise/delay)

解决的游戏设计问题:
1. 为什么角色会做出"不合理"的选择? → 需求层次决定动机优先级
2. 如何让角色行为随环境变化? → 情境映射动态调整权重
3. 如何处理多个动机冲突? → 博弈论冲突检测与解决
4. 如何避免角色动机单一化? → 8层模型提供丰富性

学术基础:
- Maslow, A.H. (1943). A theory of human motivation.
- Maslow, A.H. (1970). Motivation and personality (2nd ed.).
- Koltko-Rivera, M.E. (2006). Rediscovering the later version of Maslow's hierarchy.
- Kenrick, D.T. et al. (2010). A fundamental motives framework.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId


# ============================================================
# 常量定义（模块私有，前缀_）
# ============================================================

_DEFICIT_MIN: float = 0.0          # 缺失值最小
_DEFICIT_MAX: float = 1.0          # 缺失值最大
_PRIORITY_MIN: float = 0.0         # 优先级最小
_PRIORITY_MAX: float = 1.0         # 优先级最大
_STRENGTH_MIN: float = 0.0        # 强度最小
_STRENGTH_MAX: float = 1.0        # 强度最大

_URGENCY_COMBAT: float = 2.0      # 战斗情境紧急度乘数
_URGENCY_CRISIS: float = 1.5      # 危机情境紧急度乘数
_URGENCY_SOCIAL: float = 1.3      # 社交情境紧急度乘数
_URGENCY_CREATIVE: float = 1.1    # 创作情境紧急度乘数
_URGENCY_SOLITUDE: float = 0.9    # 独处情境紧急度乘数
_URGENCY_DEFAULT: float = 1.0     # 默认情境紧急度乘数

_SURVIVAL_BOOST: float = 1.5      # 生存本能放大系数
_META_NEED_SUPPRESSION: float = 0.3  # 高层需求抑制系数
_PRIORITY_ADJUST_CAP: float = 0.3  # 单次优先级调整上限

_CONFLICT_THRESHOLD: float = 0.5   # 冲突检测阈值
_COMPROMISE_REDUCTION: float = 0.15  # 折中方案强度削减比例
_DELAY_ANXIETY_BOOST: float = 0.2   # 延迟决策焦虑增加


def _clamp(value: float, low: float, high: float) -> float:
    """数值范围约束"""
    return max(low, min(high, value))


def _sigmoid(x: float, steepness: float = 1.0) -> float:
    """Sigmoid函数，输出范围(0, 1)"""
    if x > 500:
        return 1.0
    if x < -500:
        return 0.0
    return 1.0 / (1.0 + math.exp(-steepness * x))


# ============================================================
# 枚举定义
# ============================================================

class NeedLevel(Enum):
    """
    马斯洛需求层次 (扩展版: 原始5层 + 后期增加3层)
    
    层次关系 (从底到顶):
    
    Level 1-2: 基本需求 (Deficiency Needs / D-needs)
    └── 缺失时产生强烈负面动机
    
    Level 3-5: 心理需求 (Growth Needs / B-needs/G-needs)
    └── 满足时产生正面动机, 但不缺失也不会痛苦
    
    Level 6-8: 高阶需求 (Being Needs / meta-needs)
    └── 自我实现的深化和超越
    
    学术来源:
    - Maslow, A.H. (1943): 原始理论 (生理/安全/归属/尊重)
    - Maslow, A.H. (1970): 第二版增加认知/审美/自我实现
    - Koltko-Rivera, M.E. (2006): 发现超越需求层次
    """
    
    PHYSIOLOGICAL = auto()         # L1: 生理需求 (食物/水/睡眠/性)
    SAFETY = auto()                # L2: 安全需求 (身体安全/资源/健康)
    LOVE_BELONGING = auto()        # L3: 归属与爱 (友谊/亲密/家庭)
    ESTEEM = auto()                # L4: 尊重需求 (自尊/他人认可/地位)
    COGNITIVE = auto()             # L5: 认知需求 (知识/理解/好奇心)
    AESTHETIC = auto()             # L6: 审美需求 (对称/秩序/美感)
    SELF_ACTUALIZATION = auto()    # L7: 自我实现 (潜能发挥/创造力/意义)
    TRANSCENDENCE = auto()         # L8: 超越需求 (帮助他人实现/精神连接)


class ConflictStrategy(Enum):
    """
    动机冲突解决策略
    
    当多个需求同时产生强动机时的处理方式:
    
    hierarchy_first: 低层优先 (生存本能驱动)
    context_adaptive: 情境自适应 (根据当前环境调整)
    compromise: 折中方案 (各退一步, 降低强度)
    delay: 延迟决策 (产生焦虑情绪, 等待更多信息)
    
    设计原则:
    - D-needs冲突通常用hierarchy_first
    - G-needs冲突可用compromise或delay
    - meta-needs冲突适合delay (非紧急)
    """
    
    HIERARCHY_FIRST = auto()       # 层次优先 (低层 > 高层)
    CONTEXT_ADAPTIVE = auto()      # 情境自适应
    COMPROMISE = auto()            # 折中方案
    DELAY = auto()                 # 延迟决策


class ContextType(Enum):
    """
    情境类型 — 影响各层需求的优先级权重
    
    内置6种典型游戏情境:
    - combat: 战斗场景 (安全×2.0, 尊重×1.3)
    - social: 社交场景 (归属×1.5, 尊重×1.4)
    - solitude: 独处场景 (认知×1.3, 审美×1.2)
    - crisis: 危机场景 (安全×2.0, 生理×1.5)
    - creative: 创作场景 (审美×1.5, 自我实现×1.4)
    - default: 默认场景 (无特殊加权)
    """
    
    COMBAT = auto()                # 战斗
    SOCIAL = auto()                # 社交
    SOLITUDE = auto()              # 独处
    CRISIS = auto()                # 危机
    CREATIVE = auto()              # 创作
    DEFAULT = auto()               # 默认


# ============================================================
# 数据类型定义
# ============================================================

@dataclass
class NeedFulfillment:
    """
    单层需求满足状态
    
    核心字段:
    - value: 当前满足值 [0, 1] (1=完全满足, 0=完全缺失)
    - priority: 优先级权重 [0, 1] (影响动机强度计算)
    - deficit: 缺失程度 = 1 - value (内部计算)
    - strength: 动机强度 (基于deficit × priority × urgency)
    
    使用示例:
        >>> need = NeedFulfillment(NeedLevel.SAFETY, value=0.3, priority=0.9)
        >>> print(f"缺失程度: {need.deficit:.1%}")
        >>> print(f"动机强度: {need.strength:.2f}")
        
    学术依据:
    - Hull (1943): Drive reduction theory (驱力 = 缺失 × 重要性)
    - Atkinson (1964): Expectancy-value model of achievement
    """
    
    level: NeedLevel
    value: float = 0.5
    priority: float = 0.5
    
    def __post_init__(self):
        self.value = _clamp(self.value, _DEFICIT_MIN, _DEFICIT_MAX)
        self.priority = _clamp(self.priority, _PRIORITY_MIN, _PRIORITY_MAX)
    
    @property
    def deficit(self) -> float:
        """缺失程度 (1 - value), 范围[0, 1]"""
        return max(_DEFICIT_MIN, _DEFICIT_MAX - self.value)
    
    @property
    def is_deficiency_need(self) -> bool:
        """是否为缺失性需求 (L1-L2)"""
        return self.level in (NeedLevel.PHYSIOLOGICAL, NeedLevel.SAFETY)
    
    @property
    def is_growth_need(self) -> bool:
        """是否为成长性需求 (L3-L5)"""
        return self.level in (
            NeedLevel.LOVE_BELONGING,
            NeedLevel.ESTEEM,
            NeedLevel.COGNITIVE,
        )
    
    @property
    def is_meta_need(self) -> bool:
        """是否为存在性需求 (L6-L8)"""
        return self.level in (
            NeedLevel.AESTHETIC,
            NeedLevel.SELF_ACTUALIZATION,
            NeedLevel.TRANSCENDENCE,
        )
    
    @property
    def base_strength(self) -> float:
        """
        基础动机强度 (不考虑情境和抑制)
        
        公式:
        strength = deficit × priority
        
        特殊规则:
        - D-needs (L1-L2): 缺失时强度线性增长
        - G-needs (L3-L5): 满足时也有正向激励 (但较弱)
        - Meta-needs (L6-L8): 只有在低层基本满足后才激活
        """
        raw_strength = self.deficit * self.priority
        
        if self.is_deficiency_need:
            return _clamp(raw_strength * _SURVIVAL_BOOST, _STRENGTH_MIN, _STRENGTH_MAX)
        elif self.is_growth_need:
            growth_bonus = 0.2 * self.value  # 满足时的小奖励
            return _clamp(raw_strength + growth_bonus, _STRENGTH_MIN, _STRENGTH_MAX)
        else:
            meta_activation = 1.0 if self.value > 0.3 else 0.3
            return _clamp(raw_strength * meta_activation, _STRENGTH_MIN, _STRENGTH_MAX)
    
    def apply_context_adjustment(
        self,
        context: ContextType,
        urgency_multiplier: float = 1.0,
    ) -> float:
        """
        应用情境调整后的动机强度
        
        Args:
            context: 当前情境类型
            urgency_multiplier: 紧急度乘数 (默认1.0)
            
        Returns:
            调整后的动机强度 [0, 1]
        """
        context_weights = self._get_context_weights(context)
        weight = context_weights.get(self.level, 1.0)
        
        adjusted = self.base_strength * weight * urgency_multiplier
        
        if self.is_meta_need and context != ContextType.CREATIVE:
            adjusted *= _META_NEED_SUPPRESSION
            
        return _clamp(adjusted, _STRENGTH_MIN, _STRENGTH_MAX)
    
    def _get_context_weights(self, context: ContextType) -> Dict[NeedLevel, float]:
        """获取情境对应的权重字典"""
        weights_map = {
            ContextType.COMBAT: {
                NeedLevel.SAFETY: _URGENCY_COMBAT,
                NeedLevel.PHYSIOLOGICAL: 1.4,
                NeedLevel.ESTEEM: 1.3,
                NeedLevel.LOVE_BELONGING: 0.7,
                NeedLevel.COGNITIVE: 0.8,
                NeedLevel.AESTHETIC: 0.5,
                NeedLevel.SELF_ACTUALIZATION: 0.6,
                NeedLevel.TRANSCENDENCE: 0.3,
            },
            ContextType.SOCIAL: {
                NeedLevel.LOVE_BELONGING: 1.5,
                NeedLevel.ESTEEM: 1.4,
                NeedLevel.SAFETY: 0.8,
                NeedLevel.COGNITIVE: 1.1,
                NeedLevel.AESTHETIC: 1.0,
                NeedLevel.SELF_ACTUALIZATION: 0.9,
                NeedLevel.TRANSCENDENCE: 0.7,
            },
            ContextType.SOLITUDE: {
                NeedLevel.COGNITIVE: 1.3,
                NeedLevel.AESTHETIC: 1.2,
                NeedLevel.SELF_ACTUALIZATION: 1.1,
                NeedLevel.LOVE_BELONGING: 0.6,
                NeedLevel.ESTEEM: 0.8,
                NeedLevel.SAFETY: 0.9,
                NeedLevel.TRANSCENDENCE: 1.0,
            },
            ContextType.CRISIS: {
                NeedLevel.SAFETY: _URGENCY_COMBAT,
                NeedLevel.PHYSIOLOGICAL: _URGENCY_CRISIS,
                NeedLevel.ESTEEM: 0.7,
                NeedLevel.LOVE_BELONGING: 0.6,
                NeedLevel.COGNITIVE: 0.5,
                NeedLevel.AESTHETIC: 0.3,
                NeedLevel.SELF_ACTUALIZATION: 0.4,
                NeedLevel.TRANSCENDENCE: 0.2,
            },
            ContextType.CREATIVE: {
                NeedLevel.AESTHETIC: 1.5,
                NeedLevel.SELF_ACTUALIZATION: 1.4,
                NeedLevel.COGNITIVE: 1.2,
                NeedLevel.ESTEEM: 1.0,
                NeedLevel.LOVE_BELONGING: 0.8,
                NeedLevel.SAFETY: 0.7,
                NeedLevel.TRANSCENDENCE: 1.1,
            },
            ContextType.DEFAULT: {
                NeedLevel.PHYSIOLOGICAL: 1.0,
                NeedLevel.SAFETY: 1.0,
                NeedLevel.LOVE_BELONGING: 1.0,
                NeedLevel.ESTEEM: 1.0,
                NeedLevel.COGNITIVE: 1.0,
                NeedLevel.AESTHETIC: 1.0,
                NeedLevel.SELF_ACTUALIZATION: 1.0,
                NeedLevel.TRANSCENDENCE: 1.0,
            },
        }
        return weights_map.get(context, weights_map[ContextType.DEFAULT])


@dataclass
class MotivationConflict:
    """
    动机冲突记录
    
    当两个或更多需求同时产生高强度动机时记录此对象。
    
    字段说明:
    - conflicting_needs: 冲突的需求列表 (按强度降序)
    - conflict_type: 冲突类型 (D-vs-D / D-vs-G / G-vs-G等)
    - resolution_strategy: 解决策略
    - resolved: 是否已解决
    - winner: 最终胜出的需求 (如果已解决)
    - anxiety_level: 产生的焦虑程度 [0, 1]
    """
    
    conflicting_needs: List[Tuple[NeedLevel, float]] = field(default_factory=list)
    conflict_type: str = ""
    resolution_strategy: Optional[ConflictStrategy] = None
    resolved: bool = False
    winner: Optional[NeedLevel] = None
    anxiety_level: float = 0.0
    
    @property
    def has_conflict(self) -> bool:
        """是否存在未解决的冲突"""
        return len(self.conflicting_needs) >= 2 and not self.resolved


@dataclass
class MaslowProfile:
    """
    马斯洛需求剖面 — 角色的完整需求状态快照
    
    包含所有8层需求的满足状态、基线配置和元信息。
    
    默认基线 (倒金字塔):
    - L1 PHYSIOLOGICAL: 0.85 (基本满足)
    - L2 SAFETY: 0.80 (较安全)
    - L3 LOVE_BELONGING: 0.60 (有一定社交)
    - L4 ESTEEM: 0.50 (中等自尊)
    - L5 COGNITIVE: 0.45 (求知欲一般)
    - L6 AESTHETIC: 0.35 (审美需求较低)
    - L7 SELF_ACTUALIZATION: 0.30 (自我实现空间大)
    - L8 TRANSCENDENCE: 0.20 (超越需求最低)
    
    设计原理:
    倒金字塔反映真实人类心理: 基本需求通常得到较好满足，
    而高阶需求有更大的成长空间和追求动力。
    
    学术依据:
    - Maslow (1970): "A musician must make music..."
    - Kenrick et al. (2010): Fundamental motives framework
    """
    
    DEFAULT_BASELINE: ClassVar[Dict[NeedLevel, float]] = {
        NeedLevel.PHYSIOLOGICAL: 0.85,
        NeedLevel.SAFETY: 0.80,
        NeedLevel.LOVE_BELONGING: 0.60,
        NeedLevel.ESTEEM: 0.50,
        NeedLevel.COGNITIVE: 0.45,
        NeedLevel.AESTHETIC: 0.35,
        NeedLevel.SELF_ACTUALIZATION: 0.30,
        NeedLevel.TRANSCENDENCE: 0.20,
    }
    
    DEFAULT_PRIORITIES: ClassVar[Dict[NeedLevel, float]] = {
        NeedLevel.PHYSIOLOGICAL: 0.95,
        NeedLevel.SAFETY: 0.90,
        NeedLevel.LOVE_BELONGING: 0.75,
        NeedLevel.ESTEEM: 0.70,
        NeedLevel.COGNITIVE: 0.55,
        NeedLevel.AESTHETIC: 0.40,
        NeedLevel.SELF_ACTUALIZATION: 0.50,
        NeedLevel.TRANSCENDENCE: 0.30,
    }
    
    needs: Dict[NeedLevel, NeedFulfillment] = field(default_factory=dict)
    baseline: Dict[NeedLevel, float] = field(default_factory=dict)
    priorities: Dict[NeedLevel, float] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.needs:
            for level in NeedLevel:
                baseline_val = self.baseline.get(
                    level, self.DEFAULT_BASELINE[level]
                )
                priority_val = self.priorities.get(
                    level, self.DEFAULT_PRIORITIES[level]
                )
                self.needs[level] = NeedFulfillment(
                    level=level,
                    value=baseline_val,
                    priority=priority_val,
                )
                
        if not self.baseline:
            self.baseline = dict(self.DEFAULT_BASELINE)
            
        if not self.priorities:
            self.priorities = dict(self.DEFAULT_PRIORITIES)
    
    def update_need_value(self, level: NeedLevel, delta: float) -> None:
        """
        更新指定需求的满足值
        
        Args:
            level: 需求层级
            delta: 变化量 (正=提升满足,负=降低满足)
            
        Note:
            结果会被钳制到[0, 1]范围
        """
        if level in self.needs:
            new_value = self.needs[level].value + delta
            self.needs[level].value = _clamp(new_value, _DEFICIT_MIN, _DEFICIT_MAX)
    
    def get_dominant_need(self) -> Tuple[NeedLevel, float]:
        """
        获取当前最强烈的需求 (最高动机强度)
        
        Returns:
            (need_level, strength) 元组
        """
        best_level = NeedLevel.PHYSIOLOGICAL
        best_strength = 0.0
        
        for level, need in self.needs.items():
            if need.base_strength > best_strength:
                best_strength = need.base_strength
                best_level = level
                
        return (best_level, best_strength)
    
    def get_unmet_deficiency_needs(self) -> List[Tuple[NeedLevel, float]]:
        """
        获取所有未满足的缺失性需求 (L1-L2, value < 0.5)
        
        Returns:
            [(level, deficit)] 列表, 按deficit降序
        """
        unmet = []
        for level, need in self.needs.items():
            if need.is_deficiency_need and need.value < 0.5:
                unmet.append((level, need.deficit))
                
        unmet.sort(key=lambda x: x[1], reverse=True)
        return unmet
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式 (用于序列化/调试)"""
        return {
            "needs": {
                level.name: {
                    "value": need.value,
                    "priority": need.priority,
                    "deficit": need.deficit,
                    "base_strength": need.base_strength,
                }
                for level, need in self.needs.items()
            },
            "baseline": {level.name: val for level, val in self.baseline.items()},
            "priorities": {level.name: val for level, val in self.priorities.items()},
        }


class MotivationEngine:
    """
    马斯洛动机引擎 (主类)
    
    功能:
    - 计算各层需求的动机强度 (考虑情境和抑制)
    - 检测动机冲突 (多需求竞争)
    - 解决冲突 (4种策略)
    - 生成动机报告 (用于决策和prompt注入)
    - 更新需求状态 (模拟事件影响)
    
    使用示例:
        >>> engine = MotivationEngine(character_id="hero")
        >>> engine.set_context(ContextType.COMBAT)
        >>> report = engine.generate_report()
        >>> print(report.dominant_need)  # 可能是 SAFETY 或 ESTEEM
        >>> engine.update_from_event("win_battle", {"esteem": +0.1})
        
    设计约束:
    - 单例模式 (每个角色一个实例)
    - 所有数值严格钳制到[0, 1]
    - 支持运行时切换冲突解决策略
    """
    
    DEFAULT_STRATEGY: ClassVar[ConflictStrategy] = ConflictStrategy.HIERARCHY_FIRST
    
    def __init__(
        self,
        character_id: EntityId,
        profile: Optional[MaslowProfile] = None,
        default_strategy: ConflictStrategy = DEFAULT_STRATEGY,
    ) -> None:
        """
        初始化动机引擎
        
        Args:
            character_id: 所属角色ID
            profile: 自定义需求剖面 (None则使用默认倒金字塔)
            default_strategy: 默认冲突解决策略
        """
        self._character_id = character_id
        self._profile = profile or MaslowProfile()
        self._context: ContextType = ContextType.DEFAULT
        self._default_strategy = default_strategy
        self._current_conflict: Optional[MotivationConflict] = None
        self._urgency: float = 1.0
    
    @property
    def character_id(self) -> EntityId:
        """获取所属角色ID"""
        return self._character_id
    
    @property
    def profile(self) -> MaslowProfile:
        """获取当前需求剖面"""
        return self._profile
    
    @property
    def current_context(self) -> ContextType:
        """获取当前情境类型"""
        return self._context
    
    def set_context(self, context: ContextType, urgency: float = 1.0) -> None:
        """
        设置当前情境
        
        Args:
            context: 情境类型
            urgency: 紧急度乘数 [0.5, 2.0]
        """
        self._context = context
        self._urgency = _clamp(urgency, 0.5, 2.0)
    
    def calculate_all_motivations(self) -> Dict[NeedLevel, float]:
        """
        计算所有需求的情境调整后动机强度
        
        Returns:
            {need_level: adjusted_strength} 字典
        """
        motivations = {}
        
        for level, need in self._profile.needs.items():
            adjusted = need.apply_context_adjustment(
                context=self._context,
                urgency_multiplier=self._urgency,
            )
            motivations[level] = adjusted
            
        return motivations
    
    def detect_conflicts(self) -> Optional[MotivationConflict]:
        """
        检测动机冲突
        
        冲突定义:
        - 存在≥2个需求, 其adjusted_strength > threshold (0.5)
        - 这些需求属于不同层次 (如L2 vs L4)
        - 且它们的强度差 < 0.2 (势均力敌)
        
        Returns:
            MotivationConflict 对象 (无冲突则返回None)
        """
        motivations = self.calculate_all_motivations()
        
        strong_needs = [
            (level, strength)
            for level, strength in motivations.items()
            if strength > _CONFLICT_THRESHOLD
        ]
        
        strong_needs.sort(key=lambda x: x[1], reverse=True)
        
        if len(strong_needs) < 2:
            self._current_conflict = None
            return None
            
        top_two = strong_needs[:2]
        strength_diff = abs(top_two[0][1] - top_two[1][1])
        
        if strength_diff < 0.2:
            conflict_type = self._classify_conflict(top_two)
            
            conflict = MotivationConflict(
                conflicting_needs=top_two,
                conflict_type=conflict_type,
                anxiety_level=min(strength_diff * 2, 1.0),
            )
            
            self._current_conflict = conflict
            return conflict
            
        self._current_conflict = None
        return None
    
    def resolve_conflict(
        self,
        strategy: Optional[ConflictStrategy] = None,
    ) -> Optional[Tuple[NeedLevel, float]]:
        """
        解决当前检测到的冲突
        
        策略详解:
        
        1. HIERARCHY_FIRST:
           选择层次更低的需求作为winner
           (生存本能优先)
           
        2. CONTEXT_ADAPTIVE:
           选择在当前情境下权重更高的需求
           
        3. COMPROMISE:
           返回折中结果 (两个需求的平均强度 × 0.85)
           winner设为较强的那个, 但强度降低
           
        4. DELAY:
           不立即解决, 返回None
           设置anxiety_boost供后续使用
           适用于需要更多信息的情况
        
        Args:
            strategy: 解决策略 (None则使用default_strategy)
            
        Returns:
            (winner_need, final_strength) 元组
            如果strategy=DELAY则返回None
        """
        strategy = strategy or self._default_strategy
        
        if not self._current_conflict or not self._current_conflict.has_conflict:
            dominant = self._profile.get_dominant_need()
            return dominant if dominant[1] > 0 else None
        
        conflict = self._current_conflict
        need_a, str_a = conflict.conflicting_needs[0]
        need_b, str_b = conflict.conflicting_needs[1]
        
        if strategy == ConflictStrategy.HIERARCHY_FIRST:
            winner = min([need_a, need_b], key=lambda n: n.value)
            final_strength = max(str_a, str_b)
            
        elif strategy == ConflictStrategy.CONTEXT_ADAPTIVE:
            weights_a = NeedFulfillment(
                need_a, 0.5, 0.5
            )._get_context_weights(self._context).get(need_a, 1.0)
            weights_b = NeedFulfillment(
                need_b, 0.5, 0.5
            )._get_context_weights(self._context).get(need_b, 1.0)
            
            if weights_a >= weights_b:
                winner = need_a
                final_strength = str_a
            else:
                winner = need_b
                final_strength = str_b
                
        elif strategy == ConflictStrategy.COMPROMISE:
            avg_strength = (str_a + str_b) / 2 * (1 - _COMPROMISE_REDUCTION)
            winner = need_a if str_a >= str_b else need_b
            final_strength = _clamp(avg_strength, _STRENGTH_MIN, _STRENGTH_MAX)
            
        else:  # DELAY
            conflict.anxiety_level = min(
                conflict.anxiety_level + _DELAY_ANXIETY_BOOST,
                1.0,
            )
            conflict.resolved = False
            return None
        
        conflict.resolution_strategy = strategy
        conflict.resolved = True
        conflict.winner = winner
        
        return (winner, final_strength)
    
    def generate_report(self) -> Dict[str, Any]:
        """
        生成完整的动机报告 (用于决策/prompt注入)
        
        报告内容:
        - dominant_need: 最强烈需求
        - top_motivations: Top-5动机列表 (含强度)
        - unmet_deficiency_needs: 未满足的基本需求
        - active_conflict: 当前冲突 (如果有)
        - context_info: 当前情境信息
        - recommendations: 行动建议 (基于主导需求)
        
        Returns:
            格式化的报告字典
        """
        motivations = self.calculate_all_motivations()
        
        sorted_motivations = sorted(
            motivations.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        top_5 = sorted_motivations[:5]
        dominant = top_5[0] if top_5 else (NeedLevel.PHYSIOLOGICAL, 0.0)
        
        conflict = self.detect_conflicts()
        
        unmet_def = self._profile.get_unmet_deficiency_needs()
        
        recommendations = self._generate_recommendations(dominant[0])
        
        return {
            "dominant_need": {
                "level": dominant[0].name,
                "strength": round(dominant[1], 3),
            },
            "top_motivations": [
                {"level": level.name, "strength": round(str_, 3)}
                for level, str_ in top_5
            ],
            "unmet_deficiency_needs": [
                {"level": level.name, "deficit": round(deficit, 3)}
                for level, deficit in unmet_def
            ],
            "active_conflict": {
                "exists": conflict is not None and conflict.has_conflict,
                "type": conflict.conflict_type if conflict else "",
                "needs": [
                    n.name for n, _ in (conflict.conflicting_needs if conflict else [])
                ],
                "anxiety": round(conflict.anxiety_level, 3) if conflict else 0.0,
            } if conflict else {"exists": False},
            "context_info": {
                "type": self._context.name,
                "urgency": round(self._urgency, 2),
            },
            "recommendations": recommendations,
        }
    
    def update_from_event(
        self,
        event_type: str,
        effects: Dict[str, float],
    ) -> Dict[NeedLevel, float]:
        """
        根据事件更新需求状态
        
        事件示例:
        - "eat_food": {"physiological": +0.2}
        - "win_battle": {"esteem": +0.1, "safety": -0.05}
        - "make_friend": {"love_belonging": +0.15}
        - "learn_skill": {"cognitive": +0.1, "esteem": +0.05}
        - "create_art": {"aesthetic": +0.1, "self_actualization": +0.05}
        - "help_others": {"transcendence": +0.1, "esteem": +0.03}
        
        Args:
            event_type: 事件类型标识
            effects: 各需求的变化量字典
                     key可以是NeedLevel.name或小写别名
            
        Returns:
            实际变化的字典 {level: new_value}
        """
        name_to_level = {
            "physiological": NeedLevel.PHYSIOLOGICAL,
            "safety": NeedLevel.SAFETY,
            "love_belonging": NeedLevel.LOVE_BELONGING,
            "love": NeedLevel.LOVE_BELONGING,
            "esteem": NeedLevel.ESTEEM,
            "cognitive": NeedLevel.COGNITIVE,
            "aesthetic": NeedLevel.AESTHETIC,
            "self_actualization": NeedLevel.SELF_ACTUALIZATION,
            "self_actualization": NeedLevel.SELF_ACTUALIZATION,
            "transcendence": NeedLevel.TRANSCENDENCE,
        }
        
        actual_changes = {}
        
        for need_key, delta in effects.items():
            level_key = need_key.lower().replace(" ", "_")
            level = name_to_level.get(level_key)
            
            if level and level in self._profile.needs:
                old_value = self._profile.needs[level].value
                self._profile.update_need_value(level, delta)
                new_value = self._profile.needs[level].value
                actual_changes[level] = new_value
                
        return actual_changes
    
    def reset_to_baseline(self) -> None:
        """重置所有需求到基线值"""
        for level in NeedLevel:
            baseline_val = self._profile.baseline.get(
                level, MaslowProfile.DEFAULT_BASELINE[level]
            )
            self._profile.needs[level].value = baseline_val
    
    def _classify_conflict(
        self,
        needs: List[Tuple[NeedLevel, float]],
    ) -> str:
        """分类冲突类型"""
        levels = [n[0] for n in needs]
        
        types = []
        for lvl in levels:
            if lvl in (NeedLevel.PHYSIOLOGICAL, NeedLevel.SAFETY):
                types.append("D")
            elif lvl in (
                NeedLevel.LOVE_BELONGING,
                NeedLevel.ESTEEM,
                NeedLevel.COGNITIVE,
            ):
                types.append("G")
            else:
                types.append("M")
                
        return f"{types[0]}-vs-{types[1]}" if len(types) >= 2 else ""
    
    def _generate_recommendations(
        self,
        dominant: NeedLevel,
    ) -> List[str]:
        """根据主导需求生成行动建议"""
        rec_map = {
            NeedLevel.PHYSIOLOGICAL: [
                "寻找食物/水源",
                "休息恢复体力",
                "寻求庇护所",
            ],
            NeedLevel.SAFETY: [
                "评估威胁等级",
                "寻找安全位置",
                "准备防御措施",
            ],
            NeedLevel.LOVE_BELONGING: [
                "与同伴互动",
                "建立/加深关系",
                "参与社交活动",
            ],
            NeedLevel.ESTEEM: [
                "完成挑战性任务",
                "展示能力/成就",
                "获得认可",
            ],
            NeedLevel.COGNITIVE: [
                "探索新知识",
                "分析复杂问题",
                "学习新技能",
            ],
            NeedLevel.AESTHETIC: [
                "欣赏美的事物",
                "创造艺术作品",
                "追求和谐秩序",
            ],
            NeedLevel.SELF_ACTUALIZATION: [
                "发挥个人潜能",
                "追求有意义的目标",
                "创造性表达",
            ],
            NeedLevel.TRANSCENDENCE: [
                "帮助他人成长",
                "追求精神连接",
                "超越自我利益",
            ],
        }
        return rec_map.get(dominant, ["继续当前活动"])
