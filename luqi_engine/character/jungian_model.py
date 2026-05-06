"""
荣格深度人格模型 — 阴影/面具/原型三层结构
基于分析心理学(C.G.Jung)的深度人格建模，
支持阴影面触发、面具-阴影张力计算、原型归属判定

合规注意: Shadow功能默认关闭，通过DeepHumanModelConfig.enable_shadow控制（见MEMO-001）
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId


# ============================================================
# 常量定义
# ============================================================

_INTENSITY_MIN: float = 0.0
_INTENSITY_MAX: float = 1.0
_REPRESSION_MIN: float = 0.0
_REPRESSION_MAX: float = 1.0
_INTEGRATION_MIN: float = 0.0
_INTEGRATION_MAX: float = 1.0

_DEFAULT_REPRESSION_LEVEL: float = 0.5
_DEFAULT_INTENSITY: float = 0.0
_SPRING_EFFECT_COEFFICIENT: float = 0.5
_CONFLICT_WEIGHT_SHADOW: float = 1.0
_CONFLICT_WEIGHT_TENSION: float = 1.0

_PERSONA_LAYER_MIN: float = 0.0
_PERSONA_LAYER_MAX: float = 1.0
_ARCHETYPE_CONFIDENCE_MIN: float = 0.0
_ARCHETYPE_CONFIDENCE_MAX: float = 1.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sigmoid(x: float, steepness: float = 1.0) -> float:
    if x > 500:
        return 1.0
    if x < -500:
        return 0.0
    return 1.0 / (1.0 + math.exp(-steepness * x))


# ============================================================
# 枚举定义
# ============================================================

class Archetype(Enum):
    """荣格12种原型"""
    INNOCENT = auto()
    SAGE = auto()
    EXPLORER = auto()
    RULER = auto()
    CREATOR = auto()
    CAREGIVER = auto()
    MAGICIAN = auto()
    HERO = auto()
    OUTLAW = auto()
    LOVER = auto()
    JESTER = auto()
    EVERYMAN = auto()


# ============================================================
# 数据类型定义
# ============================================================

@dataclass
class ShadowAspect:
    """
    阴影面 — 被压抑或隐藏的心理侧面
    
    设计原则：
    - 每个Shadow都有一个对应的"触发条件"（trigger_conditions）
    - 当触发时，Shadow会影响行为但不完全控制
    - Shadow可以通过"整合"(integration)过程逐渐被接纳
    - 压抑越强(repression_level越高)，爆发时的冲击越大（弹簧效应）
    
    影响力公式:
        if 无触发词匹配:
            influence = 0.0
        
        base = intensity × (1 - repression_level)
        spring_effect = 1.0 + repression_level × SPRING_EFFECT_COEFFICIENT
        result = base × spring_effect
        result = clamp(result, 0.0, 1.0)
    """
    
    RANGE_INTENSITY: ClassVar[Tuple[float, float]] = (_INTENSITY_MIN, _INTENSITY_MAX)
    RANGE_REPRESSION: ClassVar[Tuple[float, float]] = (_REPRESSION_MIN, _REPRESSION_MAX)
    RANGE_INTEGRATION: ClassVar[Tuple[float, float]] = (_INTEGRATION_MIN, _INTEGRATION_MAX)
    
    name: str = ""
    intensity: float = _DEFAULT_INTENSITY
    repression_level: float = _DEFAULT_REPRESSION_LEVEL
    trigger_conditions: List[str] = field(default_factory=list)
    behavioral_bias: Dict[str, float] = field(default_factory=dict)
    integration_progress: float = _INTEGRATION_MIN
    
    def __post_init__(self):
        self.intensity = _clamp(self.intensity, *self.RANGE_INTENSITY)
        self.repression_level = _clamp(self.repression_level, *self.RANGE_REPRESSION)
        self.integration_progress = _clamp(self.integration_progress, *self.RANGE_INTEGRATION)

    def get_influence_context(self, context_keywords: List[str]) -> float:
        """
        计算当前情境下阴影面的影响力
        
        Args:
            context_keywords: 当前情境的关键词列表
            
        Returns:
            影响力 [0.0, 1.0]，0表示无影响，1表示完全主导
        """
        if not context_keywords or not self.trigger_conditions:
            return 0.0
        
        matched = False
        for trigger in self.trigger_conditions:
            for kw in context_keywords:
                if trigger.lower() in kw.lower():
                    matched = True
                    break
            if matched:
                break
        
        if not matched:
            return 0.0
        
        base = self.intensity * (1.0 - self.repression_level)
        
        spring_effect = 1.0 + self.repression_level * _SPRING_EFFECT_COEFFICIENT
        
        raw_result = base * spring_effect
        
        integration_discount = 1.0 - self.integration_progress * 0.5
        
        final_result = raw_result * integration_discount
        
        return _clamp(final_result, _INTENSITY_MIN, _INTENSITY_MAX)


@dataclass
class PersonaLayer:
    """
    面具层 — 社会化呈现的形象
    
    角色在社交场合中展现的"外在自我"，
    与内在的Shadow形成张力关系。
    
    strength: 面具强度（0=无面具完全真实, 1=完全伪装）
    description: 面具描述（如"冷静的领导者"、"乐观的朋友"）
    """
    
    STRENGTH_MIN: ClassVar[float] = _PERSONA_LAYER_MIN
    STRENGTH_MAX: ClassVar[float] = _PERSONA_LAYER_MAX
    
    name: str = ""
    strength: float = 0.5
    description: str = ""
    expected_behaviors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.strength = _clamp(self.strength, self.STRENGTH_MIN, self.STRENGTH_MAX)


@dataclass
class JungianProfile:
    """
    荣格式完整人格剖面
    
    组合三个层次:
    - shadows: 被压抑的阴影面列表
    - persona: 社交面具层
    - archetype: 主导原型（12种之一）
    - archetype_confidence: 原型归属置信度
    """
    
    CONFIDENCE_MIN: ClassVar[float] = _ARCHETYPE_CONFIDENCE_MIN
    CONFIDENCE_MAX: ClassVar[float] = _ARCHETYPE_CONFIDENCE_MAX
    
    shadows: List[ShadowAspect] = field(default_factory=list)
    persona: Optional[PersonaLayer] = None
    archetype: Archetype = Archetype.EVERYMAN
    archetype_confidence: float = 0.5
    
    def __post_init__(self):
        self.archetype_confidence = _clamp(
            self.archetype_confidence, self.CONFIDENCE_MIN, self.CONFIDENCE_MAX
        )
    
    def add_shadow(self, shadow: ShadowAspect) -> None:
        """添加一个阴影面"""
        self.shadows.append(shadow)
    
    def get_dominant_shadow(
        self, context_keywords: Optional[List[str]] = None,
    ) -> Tuple[Optional[ShadowAspect], float]:
        """
        获取当前情境下影响力最大的阴影面
        
        Returns:
            (shadow_or_none, max_influence)
        """
        if not self.shadows:
            return None, 0.0
        
        keywords = context_keywords or []
        best_shadow: Optional[ShadowAspect] = None
        best_influence: float = 0.0
        
        for shadow in self.shadows:
            influence = shadow.get_influence_context(keywords)
            if influence > best_influence:
                best_influence = influence
                best_shadow = shadow
        
        return best_shadow, best_influence
    
    def compute_inner_conflict(self, context_keywords: Optional[List[str]] = None) -> float:
        """
        计算内在冲突强度
        
        公式:
            conflict = Σ(shadow_influences) × persona_shadow_tension
        
        输出: [0, 1]
        0 = 完全和谐
        1 = 严重内在冲突
        
        Args:
            context_keywords: 当前情境关键词
            
        Returns:
            冲突强度 [0.0, 1.0]
        """
        self.get_dominant_shadow(context_keywords)
        
        all_influences: float = 0.0
        for shadow in self.shadows:
            all_influences += shadow.get_influence_context(context_keywords or [])
        
        tension: float = 0.0
        if self.persona is not None:
            tension = self.persona.strength * _CONFLICT_WEIGHT_TENSION
        
        conflict = all_influences * (1.0 + tension) * _CONFLICT_WEIGHT_SHADOW
        
        return _clamp(conflict, _INTENSITY_MIN, _INTENSITY_MAX)
    
    def get_archetype_description(self) -> str:
        """获取原型的中文描述"""
        descriptions: Dict[Archetype, str] = {
            Archetype.INNOCENT: "天真者 — 追求幸福与安全",
            Archetype.SAGE: "智者 — 追求真理与知识",
            Archetype.EXPLORER: "探索者 — 追求自由与冒险",
            Archetype.RULER: "统治者 — 追求控制与秩序",
            Archetype.CREATOR: "创造者 — 追求创新与表达",
            Archetype.CAREGIVER: "照顾者 — 追求服务与保护",
            Archetype.MAGICIAN: "魔术师 — 追求变革与奇迹",
            Archetype.HERO: "英雄 — 追求勇气与成就",
            Archetype.OUTLAW: "反叛者 — 追求解放与颠覆",
            Archetype.LOVER: "恋人 — 追求亲密与激情",
            Archetype.JESTER: "小丑 — 追求快乐与活在当下",
            Archetype.EVERYMAN: "普通人 — 追求归属与平凡",
        }
        return descriptions.get(self.archetype, "未知原型")
    
    def to_prompt_summary(self) -> str:
        """
        生成用于注入prompt的人格摘要文本
        
        包含: 原型信息、活跃阴影警告、内在冲突提示
        """
        parts: List[str] = []
        
        archetype_desc = self.get_archetype_description()
        parts.append(f"核心原型：{archetype_desc}")
        
        if self.archetype_confidence < 0.7:
            parts.append(f"(原型归属度较低：{self.archetype_confidence:.0%})")
        
        dominant_shadow, influence = self.get_dominant_shadow([])
        if dominant_shadow is not None and influence > 0.3:
            parts.append(f"潜在阴影倾向：{dominant_shadow.name}(强度{influence:.0%})")
        
        if self.persona is not None and self.persona.strength > 0.6:
            parts.append(f"社会面具：{self.persona.name}({self.persona.description})")
        
        return "; ".join(parts) if parts else ""
