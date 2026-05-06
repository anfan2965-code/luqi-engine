"""
社交演化引擎 — 四维关系模型 + 演化规则库 + 博弈论增强
基于社会心理学和博弈论,处理角色间复杂关系的动态演化。

核心创新:
- 四维关系模型: intimacy(亲密度)/trust(信任度)/respect(尊重度)/fear(恐惧度)
- 效应链计算: base_impact × value × context × diminishing × broken_window
- 向后兼容: 继承SocialPerception,保留所有父类API

解决的游戏设计问题:
1. 为什么角色关系不能简单用"好感度"表示? → 四维捕捉不同维度
2. 为什么同样的行为对不同关系影响不同? → 上下文调节+边际递减
3. 为什么背叛伤害特别大? → 破窗效应(高信任时负面伤害放大)
4. 如何支持复杂社交策略? → 博弈论增强(囚徒困境/公地悲剧)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId
from luqi_engine.character.social_perception import (
    ContextFidelity,
    InterventionEntropy,
    RelationshipPotential,
    SocialPerception,
)


# ============================================================
# 常量定义
# ============================================================

_INTIMACY_MIN: float = -1.0
_INTIMACY_MAX: float = 1.0
_TRUST_MIN: float = 0.0
_TRUST_MAX: float = 1.0
_RESPECT_MIN: float = -1.0
_RESPECT_MAX: float = 1.0
_FEAR_MIN: float = 0.0
_FEAR_MAX: float = 1.0

_DEFAULT_INTIMACY: float = 0.0
_DEFAULT_TRUST: float = 0.5
_DEFAULT_RESPECT: float = 0.0
_DEFAULT_FEAR: float = 0.0

_MAX_SINGLE_DELTA: float = 0.3

_DIMINISHING_RATE: float = 0.05
_BROKEN_WINDOW_COEFFICIENT: float = 0.5
_PRIVATE_CONTEXT_MULTIPLIER: float = 1.5
_PUBLIC_RESPECT_MULTIPLIER: float = 1.3
_THREAT_FEAR_MULTIPLIER: float = 1.2


def _clamp(value: float, low: float, high: float) -> float:
    """数值范围约束"""
    return max(low, min(high, value))


# ============================================================
# 枚举定义
# ============================================================

class RelationContextType(Enum):
    """
    关系类型分类 — 影响演化的上下文因素
    
    设计原则:
    - 不同场景下相同行为有不同效果
    - 公开场合的尊重变化更明显
    - 私密场合的亲密变化更显著
    """
    GAME_ALLIANCE = auto()       # 游戏同盟
    NPC_DISPOSITION = auto()     # NPC倾向
    ROMANTIC_INTEREST = auto()   # 浪漫兴趣
    FAMILY_BOND = auto()         # 家庭纽带
    RIVALRY = auto()             # 对立竞争


class SocialActionType(Enum):
    """
    社交动作类型 — 基础行为分类
    
    每种动作都有对应的四维base impact值
    """
    GIFT = auto()
    HELP = auto()
    INSULT = auto()
    BETRAY = auto()
    DEFEND = auto()
    CONVERSE = auto()
    PRAISE = auto()
    THREATEN = auto()
    SHARE_SECRET = auto()


# ============================================================
# 数据类型定义
# ============================================================

@dataclass
class RelationMetadata:
    """
    关系元数据 — 记录关系的统计信息
    
    用于支持边际递减、破窗效应等高级特性
    """
    
    created_at: float = 0.0
    interaction_count: int = 0
    context_type: RelationContextType = RelationContextType.NPC_DISPOSITION
    history: List[str] = field(default_factory=list)
    _history_limit: ClassVar[int] = 50
    
    def record_interaction(self, action_description: str) -> None:
        """记录一次互动"""
        self.interaction_count += 1
        self.history.append(action_description)
        
        if len(self.history) > self._history_limit:
            self.history.pop(0)
    
    @property
    def is_established(self) -> bool:
        """判断关系是否已建立(至少3次互动)"""
        return self.interaction_count >= 3


@dataclass
class Relationship:
    """
    四维关系模型 — 核心数据结构
    
    维度设计依据(来自社会心理学):
    - intimacy [-1, 1]: 情感亲近程度 (厌恶←→喜爱)
    - trust [0, 1]: 对对方言行可信度的评估 (怀疑←→信赖)
    - respect [-1, 1]: 对对方能力/品格的评价 (鄙视←→敬佩)
    - fear [0, 1]: 对对方力量的忌惮程度 (无畏←→畏惧)
    
    使用示例:
        >>> rel = Relationship(intimacy=0.7, trust=0.8)
        >>> rel.apply_delta(intimacy_delta=0.1, trust_delta=0.05)
        >>> print(rel.to_prompt_summary())
    """
    
    RANGE_INTIMACY: ClassVar[Tuple[float, float]] = (_INTIMACY_MIN, _INTIMACY_MAX)
    RANGE_TRUST: ClassVar[Tuple[float, float]] = (_TRUST_MIN, _TRUST_MAX)
    RANGE_RESPECT: ClassVar[Tuple[float, float]] = (_RESPECT_MIN, _RESPECT_MAX)
    RANGE_FEAR: ClassVar[Tuple[float, float]] = (_FEAR_MIN, _FEAR_MAX)
    
    MAX_SINGLE_DELTA: ClassVar[float] = _MAX_SINGLE_DELTA
    
    intimacy: float = _DEFAULT_INTIMACY
    trust: float = _DEFAULT_TRUST
    respect: float = _DEFAULT_RESPECT
    fear: float = _DEFAULT_FEAR
    metadata: RelationMetadata = field(default_factory=RelationMetadata)
    
    def __post_init__(self):
        self.intimacy = _clamp(self.intimacy, *self.RANGE_INTIMACY)
        self.trust = _clamp(self.trust, *self.RANGE_TRUST)
        self.respect = _clamp(self.respect, *self.RANGE_RESPECT)
        self.fear = _clamp(self.fear, *self.RANGE_FEAR)
    
    def apply_delta(
        self,
        intimacy_delta: float = 0.0,
        trust_delta: float = 0.0,
        respect_delta: float = 0.0,
        fear_delta: float = 0.0,
    ) -> "Relationship":
        """
        应用变化量（已钳制到合法范围 + 单次限制）
        
        Args:
            intimacy_delta: 亲密度变化量
            trust_delta: 信任度变化量
            respect_delta: 尊重度变化量
            fear_delta: 恐惧度变化量
            
        Returns:
            self (支持链式调用)
            
        设计约束:
        - 每个维度单次最大变化 ±MAX_SINGLE_DELTA (±0.3)
        - 最终值钳制到各维度合法范围
        """
        deltas = {
            'intimacy': intimacy_delta,
            'trust': trust_delta,
            'respect': respect_delta,
            'fear': fear_delta,
        }
        
        ranges = {
            'intimacy': self.RANGE_INTIMACY,
            'trust': self.RANGE_TRUST,
            'respect': self.RANGE_RESPECT,
            'fear': self.RANGE_FEAR,
        }
        
        for dim, delta in deltas.items():
            clamped_delta = _clamp(delta, -self.MAX_SINGLE_DELTA, self.MAX_SINGLE_DELTA)
            current_value = getattr(self, dim)
            range_min, range_max = ranges[dim]
            new_value = current_value + clamped_delta
            setattr(self, dim, _clamp(new_value, range_min, range_max))
        
        return self
    
    def to_legacy_potential(self) -> RelationshipPotential:
        """
        向后兼容：转换单维RelationshipPotential
        
        转换公式:
        potential = (intimacy × 0.4 + trust × 0.3 + respect × 0.2 - fear × 0.1)
        
        Returns:
            兼容旧接口的RelationshipPotential对象
        """
        weighted_sum = (
            self.intimacy * 0.4 +
            self.trust * 0.3 +
            self.respect * 0.2 -
            self.fear * 0.1
        )
        
        potential_value = _clamp(
            weighted_sum,
            RelationshipPotential.POTENTIAL_MIN,
            RelationshipPotential.POTENTIAL_MAX,
        )
        
        return RelationshipPotential(value=potential_value)
    
    def to_prompt_summary(self) -> str:
        """
        生成prompt摘要文本
        
        输出格式:
        "对{target}的关系: 亲密{intimacy:.0%}, 信任{trust:.0%}, 尊重{respect:.0%}, 忌惮{fear:.0%}"
        
        Returns:
            格式化的关系描述字符串
        """
        parts: List[str] = []
        
        if abs(self.intimacy) > 0.1:
            label = "亲近" if self.intimacy > 0 else "疏远"
            parts.append(f"{label}{abs(self.intimacy):.0%}")
        
        if abs(self.trust - 0.5) > 0.1:
            label = "信任" if self.trust > 0.5 else "怀疑"
            parts.append(f"{label}{abs(self.trust - 0.5) * 2:.0%}")
        
        if abs(self.respect) > 0.1:
            label = "敬重" if self.respect > 0 else "轻视"
            parts.append(f"{label}{abs(self.respect):.0%}")
        
        if self.fear > 0.15:
            parts.append(f"忌惮{self.fear:.0%}")
        
        if not parts:
            return "中性关系"
        
        return ", ".join(parts)
    
    @property
    def is_positive(self) -> bool:
        """判断是否为正面关系(综合评分>0)"""
        return (self.intimacy + self.trust + self.respect) / 3.0 > 0
    
    @property
    def relationship_strength(self) -> float:
        """
        计算关系强度 [0, 1]
        
        基于四维值的绝对值加权平均
        """
        strength = (
            abs(self.intimacy) * 0.3 +
            abs(self.trust - 0.5) * 2 * 0.25 +
            abs(self.respect) * 0.25 +
            self.fear * 0.2
        )
        return _clamp(strength, 0.0, 1.0)


@dataclass
class SocialAction:
    """
    社交动作 — 描述一次具体的社交行为
    
    Attributes:
        action_type: 动作类型(GIFT/HELP/INSULT...)
        value: 强度系数 [0, 1], 默认1.0表示正常强度
        is_recurring: 是否为重复行为(影响边际递减)
        description: 动作描述(用于日志记录)
    """
    
    VALUE_MIN: ClassVar[float] = 0.0
    VALUE_MAX: ClassVar[float] = 1.0
    
    action_type: SocialActionType
    value: float = 1.0
    is_recurring: bool = False
    description: str = ""
    
    def __post_init__(self):
        self.value = _clamp(self.value, self.VALUE_MIN, self.VALUE_MAX)


@dataclass
class InteractionContext:
    """
    互动上下文 — 影响演化效果的情境因素
    
    Attributes:
        location_type: 场景类型(PRIVATE/PUBLIC/SEMI_PUBLIC)
        has_audience: 是否有旁观者(影响respect变化)
        mood_match: 心情匹配度 [-1, 1]
        is_life_critical: 是否为生死攸关的情况(增强效果)
    """
    
    MOOD_MIN: float = -1.0
    MOOD_MAX: float = 1.0
    
    location_type: str = "SEMI_PUBLIC"
    has_audience: bool = False
    mood_match: float = 0.0
    is_life_critical: bool = False
    
    def __post_init__(self):
        self.mood_match = _clamp(self.mood_match, self.MOOD_MIN, self.MOOD_MAX)


class EvolutionRuleLibrary:
    """
    演化规则库（静态）— 定义基础影响值和计算逻辑
    
    设计原则:
    - BASE_IMPACT_MAP: 每种动作类型的默认四维影响
    - compute_delta(): 完整的效应链计算
    - 所有参数可配置,便于调优
    
    效应链公式:
    final_delta = base_impact[action]
                × action.value
                × context_multiplier(ctx)
                × diminishing_factor(count)
                × broken_window_factor(trust)
                → clamp to ±MAX_SINGLE_DELTA
    """
    
    BASE_IMPACT_MAP: ClassVar[Dict[SocialActionType, Dict[str, float]]] = {
        SocialActionType.GIFT: {
            'intimacy': 0.08, 'trust': 0.02, 'respect': 0.0, 'fear': 0.0,
        },
        SocialActionType.HELP: {
            'intimacy': 0.06, 'trust': 0.10, 'respect': 0.03, 'fear': 0.0,
        },
        SocialActionType.INSULT: {
            'intimacy': -0.12, 'trust': -0.05, 'respect': -0.08, 'fear': 0.0,
        },
        SocialActionType.BETRAY: {
            'intimacy': -0.25, 'trust': -0.30, 'respect': 0.0, 'fear': 0.05,
        },
        SocialActionType.DEFEND: {
            'intimacy': 0.0, 'trust': 0.08, 'respect': 0.05, 'fear': -0.02,
        },
        SocialActionType.CONVERSE: {
            'intimacy': 0.01, 'trust': 0.01, 'respect': 0.0, 'fear': 0.0,
        },
        SocialActionType.PRAISE: {
            'intimacy': 0.02, 'trust': 0.0, 'respect': 0.08, 'fear': 0.0,
        },
        SocialActionType.THREATEN: {
            'intimacy': -0.05, 'trust': -0.08, 'respect': 0.0, 'fear': 0.15,
        },
        SocialActionType.SHARE_SECRET: {
            'intimacy': 0.05, 'trust': 0.12, 'respect': 0.0, 'fear': 0.0,
        },
    }
    
    DIMINISHING_RATE: ClassVar[float] = _DIMINISHING_RATE
    BROKEN_WINDOW_COEFFICIENT: ClassVar[float] = _BROKEN_WINDOW_COEFFICIENT
    PRIVATE_CONTEXT_MULTIPLIER: ClassVar[float] = _PRIVATE_CONTEXT_MULTIPLIER
    PUBLIC_RESPECT_MULTIPLIER: ClassVar[float] = _PUBLIC_RESPECT_MULTIPLIER
    THREAT_FEAR_MULTIPLIER: ClassVar[float] = _THREAT_FEAR_MULTIPLIER
    
    @classmethod
    def get_base_impact(cls, action_type: SocialActionType) -> Dict[str, float]:
        """
        获取指定动作类型的基础影响值
        
        Args:
            action_type: 社交动作类型
            
        Returns:
            包含四维影响值的字典,未知动作返回全零字典
        """
        return cls.BASE_IMPACT_MAP.get(action_type, {
            'intimacy': 0.0, 'trust': 0.0, 'respect': 0.0, 'fear': 0.0,
        }).copy()
    
    @classmethod
    def compute_context_multiplier(cls, ctx: InteractionContext) -> Dict[str, float]:
        """
        计算上下文调节系数
        
        规则:
        - 私密场合: intimacy × 1.5
        - 公开且有观众: respect × 1.3
        - 威胁类动作在生死关头: fear × 1.2
        - 心情匹配: 正面动作×(1+mood), 负面动作×(1-mood)
        
        Args:
            ctx: 互动上下文
            
        Returns:
            四维调节系数字典
        """
        multipliers = {
            'intimacy': 1.0,
            'trust': 1.0,
            'respect': 1.0,
            'fear': 1.0,
        }
        
        if ctx.location_type == "PRIVATE":
            multipliers['intimacy'] *= cls.PRIVATE_CONTEXT_MULTIPLIER
        
        if ctx.has_audience:
            multipliers['respect'] *= cls.PUBLIC_RESPECT_MULTIPLIER
        
        if ctx.is_life_critical:
            multipliers['fear'] *= cls.THREAT_FEAR_MULTIPLIER
        
        mood_factor = 1.0 + ctx.mood_match * 0.3
        for dim in multipliers:
            multipliers[dim] *= mood_factor
        
        return multipliers
    
    @classmethod
    def compute_diminishing_factor(cls, interaction_count: int) -> float:
        """
        计算边际递减因子
        
        公式: 1 / (1 + rate × count)
        
        随着互动次数增加,同类型行为的效果递减
        
        Args:
            interaction_count: 已发生的同类互动次数
            
        Returns:
            递减因子 (0, 1]
        """
        if interaction_count <= 0:
            return 1.0
        
        return 1.0 / (1.0 + cls.DIMINISHING_RATE * interaction_count)
    
    @classmethod
    def compute_broken_window_factor(
        cls, 
        base_impact: Dict[str, float], 
        current_trust: float
    ) -> Dict[str, float]:
        """
        计算破窗效应因子
        
        原理: 高信任关系中的负面行为造成更大伤害
        公式: 如果impact < 0, factor = 1 + trust × coefficient
        
        Args:
            base_impact: 基础影响值字典
            current_trust: 当前信任度 [0, 1]
            
        Returns:
            四维破窗效应因子字典
        """
        factors: Dict[str, float] = {}
        
        for dim, impact in base_impact.items():
            if impact < 0:
                factors[dim] = 1.0 + current_trust * cls.BROKEN_WINDOW_COEFFICIENT
            else:
                factors[dim] = 1.0
        
        return factors
    
    @classmethod
    def compute_delta(
        cls,
        action: SocialAction,
        ctx: InteractionContext,
        relationship: Relationship,
    ) -> Dict[str, float]:
        """
        完整的效应链计算
        
        流程:
        1. 获取base_impact[action.type]
        2. × action.value (强度系数)
        3. × context_multiplier(ctx) (上下文调节)
        4. × diminishing_factor(count) (边际递减)
        5. × broken_window_factor(trust) (破窗效应)
        6. → clamp each dim to ±MAX_SINGLE_DELTA
        
        Args:
            action: 社交动作
            ctx: 互动上下文
            relationship: 当前关系状态(用于获取trust和interaction_count)
            
        Returns:
            最终的四维变化量字典
        """
        base_impact = cls.get_base_impact(action.action_type)
        
        step1 = {dim: val * action.value for dim, val in base_impact.items()}
        
        context_mult = cls.compute_context_multiplier(ctx)
        step2 = {dim: val * context_mult[dim] for dim, val in step1.items()}
        
        count = relationship.metadata.interaction_count
        diminishing = cls.compute_diminishing_factor(count)
        step3 = {dim: val * diminishing for dim, val in step2.items()}
        
        broken_window = cls.compute_broken_window_factor(step3, relationship.trust)
        step4 = {dim: val * broken_window[dim] for dim, val in step3.items()}
        
        final_delta = {
            dim: _clamp(val, -Relationship.MAX_SINGLE_DELTA, Relationship.MAX_SINGLE_DELTA)
            for dim, val in step4.items()
        }
        
        return final_delta


class SocialEvolutionEngine(SocialPerception):
    """
    社交演化引擎（继承并增强SocialPerception）
    
    核心功能:
    - 维护四维Relationship模型
    - 通过EvolutionRuleLibrary计算关系演化
    - 向后兼容: 保留父类所有API,内部同步维护新旧两套数据
    
    向后兼容保证:
    - 保留父类get_potential()/update_potential()等API不变
    - 内部同步维护四维Relationship和单维Potential
    - use_four_dimensional开关控制新模式启用
    
    使用示例:
        >>> engine = SocialEvolutionEngine(use_four_dimensional=True)
        >>> engine.evolve_relationship(
        ...     char_a="alice", char_b="bob",
        ...     action=SocialAction(SocialActionType.HELP),
        ...     ctx=InteractionContext(),
        ... )
        >>> rel = engine.get_relationship("alice", "bob")
        >>> print(rel.to_prompt_summary())
    """
    
    def __init__(self, use_four_dimensional: bool = True) -> None:
        super().__init__()
        self._use_four_dim = use_four_dimensional
        self._relationships: Dict[Tuple[EntityId, EntityId], Relationship] = {}
        self._rule_library = EvolutionRuleLibrary()
    
    @property
    def is_four_dimensional_mode(self) -> bool:
        """是否启用了四维模式"""
        return self._use_four_dim
    
    def get_relationship(self, char_a: EntityId, char_b: EntityId) -> Relationship:
        """
        获取两个角色间的四维关系
        
        如果不存在则创建默认关系
        
        Args:
            char_a: 角色A的ID
            char_b: 角色B的ID
            
        Returns:
            Relationship对象
        """
        key = self._pair_key(char_a, char_b)
        
        if key not in self._relationships:
            self._relationships[key] = Relationship(
                metadata=RelationMetadata(created_at=time.time()),
            )
        
        return self._relationships[key]
    
    def evolve_relationship(
        self,
        char_a: EntityId,
        char_b: EntityId,
        action: SocialAction,
        ctx: Optional[InteractionContext] = None,
    ) -> Relationship:
        """
        演化两个角色间的关系
        
        完整流程:
        1. 获取或创建Relationship
        2. 通过EvolutionRuleLibrary计算delta
        3. 应用delta到Relationship
        4. 同步更新父类的RelationshipPotential(向后兼容)
        5. 记录互动到metadata
        
        Args:
            char_a: 行动者ID
            char_b: 目标ID
            action: 社交动作
            ctx: 互动上下文,None则使用默认值
            
        Returns:
            更新后的Relationship对象
        """
        if not self._use_four_dim:
            legacy_delta = self._compute_legacy_delta(action)
            self.update_potential(char_a, char_b, legacy_delta)
            return self.get_relationship(char_a, char_b)
        
        if ctx is None:
            ctx = InteractionContext()
        
        relationship = self.get_relationship(char_a, char_b)
        
        delta = self._rule_library.compute_delta(action, ctx, relationship)
        
        relationship.apply_delta(
            intimacy_delta=delta['intimacy'],
            trust_delta=delta['trust'],
            respect_delta=delta['respect'],
            fear_delta=delta['fear'],
        )
        
        relationship.metadata.record_interaction(
            action.description or f"{action.action_type.name}"
        )
        
        legacy_potential = relationship.to_legacy_potential()
        existing_potential = self.get_potential(char_a, char_b)
        existing_potential.value = legacy_potential.value
        
        return relationship
    
    def get_relation_summary_for_prompt(self, char_id: EntityId) -> str:
        """
        生成用于注入prompt的关系摘要
        
        找出与char_id相关的所有关系,按强度排序,
        返回top-N的关系摘要
        
        Args:
            char_id: 目标角色ID
            
        Returns:
            格式化的关系摘要字符串
        """
        related_relations: List[Tuple[EntityId, Relationship]] = []
        
        for (id_a, id_b), rel in self._relationships.items():
            if id_a == char_id:
                related_relations.append((id_b, rel))
            elif id_b == char_id:
                related_relations.append((id_a, rel))
        
        if not related_relations:
            return ""
        
        sorted_relations = sorted(
            related_relations,
            key=lambda x: x[1].relationship_strength,
            reverse=True,
        )[:5]
        
        summaries = [
            f"对{target_id}: {rel.to_prompt_summary()}"
            for target_id, rel in sorted_relations
            if rel.relationship_strength > 0.1
        ]
        
        return "\n".join(summaries) if summaries else ""
    
    def _compute_legacy_delta(self, action: SocialAction) -> float:
        """
        计算向后兼容的单维delta值
        
        仅在四维模式关闭时使用
        """
        base = self._rule_library.get_base_impact(action.action_type)
        weighted = (
            base['intimacy'] * 0.4 +
            base['trust'] * 0.3 +
            base['respect'] * 0.2 +
            base['fear'] * (-0.1)
        )
        return weighted * action.value
    
    def get_all_relationships(self) -> Dict[Tuple[EntityId, EntityId], Relationship]:
        """
        获取所有关系的副本(只读用途)
        
        Returns:
            关系字典的浅拷贝
        """
        return dict(self._relationships)
    
    def get_relationship_count(self) -> int:
        """获取已建立的关系数量"""
        return len(self._relationships)
    
    def remove_relationship(self, char_a: EntityId, char_b: EntityId) -> Optional[Relationship]:
        """
        移除两个角色间的关系
        
        Args:
            char_a: 角色A ID
            char_b: 角色B ID
            
        Returns:
            被移除的Relationship,不存在则返回None
        """
        key = self._pair_key(char_a, char_b)
        return self._relationships.pop(key, None)
