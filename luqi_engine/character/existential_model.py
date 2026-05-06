"""
存在主义模型 — 萨特本真性/自欺/认知失调
基于存在主义哲学(J-P.Sartre)和认知社会心理学(L.Festinger)，
处理角色的"非理性行为"建模：为什么人会做出不符合自身利益的选择？
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId


# ============================================================
# 常量定义
# ============================================================

_STRENGTH_MIN: float = 0.0
_STRENGTH_MAX: float = 1.0
_ANXIETY_MIN: float = 0.0
_ANXIETY_MAX: float = 1.0
_AVOIDANCE_MIN: float = 0.0
_AVOIDANCE_MAX: float = 1.0
_THRESHOLD_MIN: float = 0.0
_THRESHOLD_MAX: float = 1.0

_DEFAULT_ANXIETY: float = 0.0
_DEFAULT_AVOIDANCE: float = 0.3
_DEFAULT_THRESHOLD: float = 0.5

_DISSONANCE_RECORD_LIMIT: int = 50
_DISSONANCE_MAGNITUDE_MIN: float = 0.0
_DISSONANCE_MAGNITUDE_MAX: float = 1.0
_BELIEF_STRENGTH_FACTOR: float = 0.8
_DISSONANCE_DETECTION_THRESHOLD: float = 0.3

_RESOLUTION_JUSTIFY: str = "justify"
_RESOLUTION_DENY: str = "deny"
_RESOLUTION_CHANGE_BELIEF: str = "change_belief"
_RESOLUTION_SEEK_INFO: str = "seek_info"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ============================================================
# 枚举定义
# ============================================================

class AuthenticityState(Enum):
    """本真性状态"""
    AUTHENTIC = auto()
    BAD_FAITH = auto()
    COMPROMISED = auto()
    CRISIS = auto()


class ResolutionStrategy(Enum):
    """认知失调解决策略"""
    JUSTIFY = _RESOLUTION_JUSTIFY
    DENY = _RESOLUTION_DENY
    CHANGE_BELIEF = _RESOLUTION_CHANGE_BELIEF
    SEEK_INFO = _RESOLUTION_SEEK_INFO


# ============================================================
# 数据类型定义
# ============================================================

@dataclass
class Belief:
    """
    信念条目
    
    content: 信念内容描述
    strength: 确信程度 [0, 1]
    source: 来源（经验/他人/内在）
    created_at: 形成时间戳
    """
    
    STRENGTH_MIN: ClassVar[float] = _STRENGTH_MIN
    STRENGTH_MAX: ClassVar[float] = _STRENGTH_MAX
    
    content: str = ""
    strength: float = 0.5
    source: str = ""
    created_at: float = 0.0
    
    def __post_init__(self):
        self.strength = _clamp(self.strength, self.STRENGTH_MIN, self.STRENGTH_MAX)


@dataclass
class DissonanceRecord:
    """
    认知失调记录
    
    记录一次信念冲突事件及其处理方式
    """
    
    MAGNITUDE_MIN: ClassVar[float] = _DISSONANCE_MAGNITUDE_MIN
    MAGNITUDE_MAX: ClassVar[float] = _DISSONANCE_MAGNITUDE_MAX
    
    conflicting_beliefs: Tuple[str, str] = ("", "")
    dissonance_magnitude: float = 0.0
    timestamp: float = 0.0
    resolution_strategy: Optional[ResolutionStrategy] = None
    resolved: bool = False
    
    def __post_init__(self):
        self.dissonance_magnitude = _clamp(
            self.dissonance_magnitude, self.MAGNITUDE_MIN, self.MAGNITUDE_MAX
        )


@dataclass
class ExistentialProfile:
    """
    存在主义剖面 — 处理角色的"非理性行为"
    
    解决的问题:
    1. 为什么角色有时会做出"不符合其利益"的选择？→ freedom_avoidance（逃避自由）
    2. 为什么角色会坚持一个明显错误的信念？→ bad faith + dissonance resolution
    3. 为什么角色会在关键时刻"退缩"？→ anxiety_level（存在焦虑）
    4. 为什么角色会有"口是心非"的表现？→ COMPROMISED状态
    
    核心机制:
    - detect_dissonance(): 检测新行为/信念与现有信念的矛盾
    - choose_resolution_strategy(): 根据freedom_avoidance选择应对方式
    - update_state(): 更新authenticity状态
    """
    
    ANXIETY_RANGE: ClassVar[Tuple[float, float]] = (_ANXIETY_MIN, _ANXIETY_MAX)
    AVOIDANCE_RANGE: ClassVar[Tuple[float, float]] = (_AVOIDANCE_MIN, _AVOIDANCE_MAX)
    THRESHOLD_RANGE: ClassVar[Tuple[float, float]] = (_THRESHOLD_MIN, _THRESHOLD_MAX)
    
    authenticity: AuthenticityState = AuthenticityState.AUTHENTIC
    anxiety_level: float = _DEFAULT_ANXIETY
    freedom_avoidance: float = _DEFAULT_AVOIDANCE
    responsibility_threshold: float = _DEFAULT_THRESHOLD
    
    beliefs: Dict[str, Belief] = field(default_factory=dict)
    dissonance_history: List[DissonanceRecord] = field(default_factory=list)
    
    core_values: List[str] = field(default_factory=list)
    existential_dread_triggers: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.anxiety_level = _clamp(self.anxiety_level, *self.ANXIETY_RANGE)
        self.freedom_avoidance = _clamp(self.freedom_avoidance, *self.AVOIDANCE_RANGE)
        self.responsibility_threshold = _clamp(
            self.responsibility_threshold, *self.THRESHOLD_RANGE
        )
    
    def add_belief(self, belief_id: str, content: str, strength: float = 0.5,
                   source: str = "") -> None:
        """添加一条新信念"""
        belief = Belief(
            content=content,
            strength=strength,
            source=source,
            created_at=time.time(),
        )
        self.beliefs[belief_id] = belief
    
    def remove_belief(self, belief_id: str) -> Optional[Belief]:
        """移除一条信念，返回被移除的信念"""
        return self.beliefs.pop(belief_id, None)
    
    def get_belief(self, belief_id: str) -> Optional[Belief]:
        """获取指定信念"""
        return self.beliefs.get(belief_id)
    
    def _is_contradictory(self, content_a: str, content_b: str) -> bool:
        """
        判断两个信念内容是否矛盾
        
        使用简单的关键词对立检测：
        - 包含互斥词对（如"喜欢"/"讨厌", "信任"/"不信任"）
        - 或包含明确的否定关系
        
        注意：这是一个简化实现。完整版应使用语义嵌入或LLM判断。
        """
        if not content_a or not content_b:
            return False
        
        a_lower = content_a.lower()
        b_lower = content_b.lower()
        
        opposite_pairs: List[Tuple[str, str]] = [
            ("喜欢", "讨厌"), ("爱", "恨"), ("信任", "不信任"),
            ("相信", "怀疑"), ("支持", "反对"), ("勇敢", "懦弱"),
            ("诚实", "欺骗"), ("善良", "邪恶"), ("自由", "束缚"),
            ("重要", "不重要"), ("有价值", "无价值"), ("对", "错"),
            ("好", "坏"), ("强", "弱"), ("安全", "危险"),
            ("like", "hate"), ("love", "fear"), ("trust", "distrust"),
            ("believe", "doubt"), ("support", "oppose"),
        ]
        
        for pos, neg in opposite_pairs:
            a_has_pos = pos in a_lower or pos in b_lower
            a_has_neg = neg in a_lower or neg in b_lower
            
            if a_has_pos and a_has_neg:
                in_a_pos = pos in a_lower
                in_a_neg = neg in a_lower
                in_b_pos = pos in b_lower
                in_b_neg = neg in b_lower
                
                if (in_a_pos and in_b_neg) or (in_a_neg and in_b_pos):
                    return True
        
        if "不" in b_lower or "没" in b_lower or "非" in b_lower or "not" in b_lower:
            short_a = a_lower[:20]
            if short_a in b_lower or a_lower in b_lower:
                return True
        
        return False
    
    def detect_dissonance(
        self, new_action: str, new_belief_content: str,
    ) -> Optional[DissonanceRecord]:
        """
        检测新行为/信念是否与现有信念产生认知失调
        
        流程:
        1. 遍历所有现有beliefs
        2. 对每个belief调用_is_contradictory()做语义对比
        3. 发现矛盾 → magnitude = belief.strength × BELIEF_STRENGTH_FACTOR
        4. magnitude > DETECTION_THRESHOLD → 创建DissonanceRecord
        5. 自动调用choose_resolution_strategy()分配策略
        
        Args:
            new_action: 新行为描述
            new_belief_content: 新行为的隐含信念内容
            
        Returns:
            DissonanceRecord 如果检测到显著失调，否则None
        """
        combined_new = f"{new_action} {new_belief_content}".strip()
        
        for bid, belief in self.beliefs.items():
            if self._is_contradictory(belief.content, combined_new):
                magnitude = belief.strength * _BELIEF_STRENGTH_FACTOR
                
                if magnitude > _DISSONANCE_DETECTION_THRESHOLD:
                    record = DissonanceRecord(
                        conflicting_beliefs=(bid, combined_new),
                        dissonance_magnitude=magnitude,
                        timestamp=time.time(),
                    )
                    record.resolution_strategy = self._choose_resolution_strategy(magnitude)
                    
                    if len(self.dissonance_history) >= _DISSONANCE_RECORD_LIMIT:
                        self.dissonance_history.pop(0)
                    self.dissonance_history.append(record)
                    
                    self._update_authenticity_from_dissonance(magnitude)
                    
                    return record
        
        return None
    
    def _choose_resolution_strategy(self, magnitude: float) -> ResolutionStrategy:
        """
        根据角色参数选择认知失调解决策略
        
        决策矩阵:
        - 高逃避(>0.7) + 高失调(>0.7) → justify (找理由合理化)
        - 高逃避(>0.7) + 低失调(≤0.7) → deny (直接否认)
        - 低逃避(≤0.7) + 高失调(>0.6) → change_belief (改变旧信念)
        - 低逃避(≤0.7) + 低失调(≤0.6) → seek_info (寻求更多信息)
        """
        high_avoidance = self.freedom_avoidance > 0.7
        high_magnitude = magnitude > 0.7
        medium_high_magnitude = magnitude > 0.6
        
        if high_avoidance and high_magnitude:
            return ResolutionStrategy.JUSTIFY
        elif high_avoidance and not high_magnitude:
            return ResolutionStrategy.DENY
        elif not high_avoidance and medium_high_magnitude:
            return ResolutionStrategy.CHANGE_BELIEF
        else:
            return ResolutionStrategy.SEEK_INFO
    
    def _update_authenticity_from_dissonance(self, magnitude: float) -> None:
        """根据失调强度更新本真性状态"""
        if magnitude > 0.7:
            if self.freedom_avoidance > 0.8:
                self.authenticity = AuthenticityState.BAD_FAITH
            else:
                self.authenticity = AuthenticityState.CRISIS
        elif magnitude > 0.4:
            self.authenticity = AuthenticityState.COMPROMISED
    
    def resolve_dissonance(self, record_index: int, strategy: Optional[ResolutionStrategy] = None) -> bool:
        """
        解决一条失调记录
        
        Args:
            record_index: 失调记录在history中的索引
            strategy: 指定解决策略，None则使用记录原有策略
            
        Returns:
            是否成功解决
        """
        if record_index < 0 or record_index >= len(self.dissonance_history):
            return False
        
        record = self.dissonance_history[record_index]
        if record.resolved:
            return False
        
        final_strategy = strategy or record.resolution_strategy
        if final_strategy is None:
            final_strategy = self._choose_resolution_strategy(record.dissonance_magnitude)
        
        record.resolution_strategy = final_strategy
        record.resolved = True
        
        if final_strategy == ResolutionStrategy.CHANGE_BELIEF:
            old_bid = record.conflicting_beliefs[0]
            if old_bid in self.beliefs:
                old_belief = self.beliefs[old_bid]
                old_belief.strength = _clamp(
                    old_belief.strength * 0.5,
                    Belief.STRENGTH_MIN, Belief.STRENGTH_MAX,
                )
        
        resolved_count = sum(1 for r in self.dissonance_history if r.resolved)
        unresolved_count = len(self.dissonance_history) - resolved_count
        
        if unresolved_count == 0 and self.authenticity != AuthenticityState.AUTHENTIC:
            self.authenticity = AuthenticityState.AUTHENTIC
        
        return True
    
    def get_active_dissonance_count(self) -> int:
        """获取未解决的失调数量"""
        return sum(1 for r in self.dissonance_history if not r.resolved)
    
    def get_max_dissonance_magnitude(self) -> float:
        """获取当前最大失调强度"""
        active = [r for r in self.dissonance_history if not r.resolved]
        if not active:
            return 0.0
        return max(r.dissonance_magnitude for r in active)
    
    def to_prompt_summary(self) -> str:
        """
        生成用于注入prompt的存在主义状态摘要
        
        包含: 本真性状态、焦虑水平、活跃失调警告、核心冲突提示
        """
        parts: List[str] = []
        
        state_names: Dict[AuthenticityState, str] = {
            AuthenticityState.AUTHENTIC: "本真",
            AuthenticityState.BAD_FAITH: "自欺",
            AuthenticityState.COMPROMISED: "妥协",
            AuthenticityState.CRISIS: "危机",
        }
        parts.append(f"心理状态：{state_names.get(self.authenticity, '未知')}")
        
        if self.anxiety_level > 0.5:
            anxiety_labels = [(0.5, "略显焦虑"), (0.7, "明显焦虑"), (0.9, "深度焦虑")]
            label = "高度紧张"
            for threshold, lbl in anxiety_labels:
                if self.anxiety_level < threshold:
                    label = lbl
                    break
            parts.append(f"存在{label}")
        
        active_count = self.get_active_dissonance_count()
        if active_count > 0:
            max_mag = self.get_max_dissonance_magnitude()
            parts.append(f"内心矛盾({active_count}项未解决, 强度{max_mag:.0%})")
        
        if self.core_values:
            parts.append(f"核心价值观：{'、'.join(self.core_values[:3])}")
        
        return "; ".join(parts) if parts else ""
