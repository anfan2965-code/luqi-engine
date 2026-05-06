"""
深度角色聚合层 — DeepCharacter 统一聚合器
整合Phase 1(人格建模)和Phase 2(记忆/动机)全部子系统,
提供一致性的状态查询接口、事件驱动同步和Prompt就绪的状态快照。

设计原则:
- 组合模式 (Composition): 不修改任何P1/P2已完成文件
- 惰性初始化: 子系统按需创建, 减少启动开销
- 事件驱动: 通过on_event()统一分发更新
- 一致性保证: 自动检测子系统间输出矛盾

学术依据:
- McAdams (1995): 三层人格架构 (特质→个人关切→叙事身份)
- 整合性人格理论: 多子系统协同激活模型
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId


# ============================================================
# 常量定义（模块私有，前缀_）
# ============================================================

_DEFAULT_SHADOW_THRESHOLD: float = 0.6
_DEFAULT_TENSION_THRESHOLD: float = 0.5
_CONSISTENCY_CHECK_INTERVAL: int = 5
_MAX_CONSISTENCY_ISSUES: int = 10
_MAX_RECENT_EVENTS: int = 50
_MAX_BAD_FAITH_INDICATORS: int = 5

_TENSION_MIN: float = 0.0
_TENSION_MAX: float = 1.0
_AUTHENTICITY_MIN: float = 0.0
_AUTHENTICITY_MAX: float = 1.0
_URGENCY_MIN: float = 0.5
_URGENCY_MAX: float = 2.0


def _clamp(value: float, low: float, high: float) -> float:
    """将value钳制到[low, high]区间"""
    return max(low, min(high, value))


# ============================================================
# 枚举定义
# ============================================================

class PsychologicalTensionLevel(Enum):
    """存在主义张力等级"""
    CALM = auto()
    TENSE = auto()
    CRISIS = auto()
    DISSOCIATED = auto()


class ShadowActivationState(Enum):
    """阴影激活状态"""
    DORMANT = auto()
    RUMBLING = auto()
    ACTIVE = auto()
    OVERRUN = auto()


class NarrativeArcPhase(Enum):
    """叙事弧阶段 (英雄之旅映射)"""
    CALL = auto()
    INITIATION = auto()
    ORDEAL = auto()
    TRANSFORMATION = auto()
    RETURN = auto()


class MotivationDominance(Enum):
    """动机主导类型"""
    DEFICIENCY = auto()
    GROWTH = auto()
    META = auto()
    CONFLICT = auto()


class ConsistencyIssueType(Enum):
    """一致性问题描述类型"""
    EMOTION_SHADOW_MISMATCH = auto()
    MEMORY_MOTIVATION_CONTRADICTION = auto()
    NARRATIVE_BEHAVIOR_MISMATCH = auto()
    SOCIAL_PERSONALITY_CONFLICT = auto()
    EXISTENTIAL_CHOICE_CONTRADICTION = auto()


class ConsistencySeverity(Enum):
    """一致性检查严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ============================================================
# 数据类型定义
# ============================================================

@dataclass
class ConsistencyIssue:
    """
    一致性问题记录
    
    Attributes:
        issue_type: 问题类型
        severity: 严重程度
        message: 问题描述
        suggestion: 修复建议
        subsystems_involved: 涉及的子系统名称列表
    """
    
    issue_type: ConsistencyIssueType
    severity: ConsistencySeverity
    message: str = ""
    suggestion: str = ""
    subsystems_involved: List[str] = field(default_factory=list)


@dataclass
class SubsystemHealthStatus:
    """
    子系统健康状态
    
    Attributes:
        subsystem_name: 子系统名称
        is_healthy: 是否健康
        issues: 问题列表
    """
    
    subsystem_name: str = ""
    is_healthy: bool = True
    issues: List[str] = field(default_factory=list)


@dataclass
class DeepCharacterState:
    """
    深度角色心理状态快照 — DeepCharacter对外输出的核心数据结构
    
    设计原则:
    - 包含来自所有子系统的聚合状态
    - 可直接用于Prompt注入、日志记录、调试可视化
    - 所有数值字段经过__post_init__范围钳制
    
    使用示例:
        >>> state = deep_char.get_state_snapshot()
        >>> prompt_text = state.to_prompt_fragment(max_length=500)
    """
    
    # === 元信息 ===
    character_id: str = ""
    timestamp: float = 0.0
    scene_context: str = ""
    
    # === Phase 1: 人格内核 ===
    dominant_archetype: str = ""
    shadow_state: ShadowActivationState = ShadowActivationState.DORMANT
    active_shadow_aspects: List[str] = field(default_factory=list)
    persona_active: bool = False
    persona_description: str = ""
    
    tension_level: PsychologicalTensionLevel = PsychologicalTensionLevel.CALM
    authenticity_score: float = 0.5
    cognitive_dissonance: float = 0.0
    existential_anxiety: float = 0.0
    bad_faith_indicators: List[str] = field(default_factory=list)
    
    narrative_phase: NarrativeArcPhase = NarrativeArcPhase.CALL
    core_narrative: str = ""
    identity_statement: str = ""
    narrative_tension: float = 0.0
    
    relationship_summary: str = ""
    social_role: str = ""
    trust_level_current: float = 0.5
    
    # === Phase 2: 记忆与动机 ===
    relevant_memories: List[Dict[str, Any]] = field(default_factory=list)
    memory_count_total: int = 0
    recent_memory_emotion: str = ""
    
    dominant_need: str = ""
    motivation_dominance: MotivationDominance = MotivationDominance.DEFICIENCY
    need_satisfaction_map: Dict[str, float] = field(default_factory=dict)
    current_conflict: Optional[str] = None
    urgency_level: float = 1.0
    
    # === 综合衍生指标 ===
    overall_mood: str = ""
    behavioral_tendency: str = ""
    response_style_hint: str = ""
    should_trigger_shadow: bool = False
    consistency_issues: List[str] = field(default_factory=list)
    
    # === Phase 4: 博弈论状态 ===
    primary_target_beliefs: Dict[str, float] = field(default_factory=dict)
    active_threats: List[Dict[str, Any]] = field(default_factory=list)
    current_strategy: Optional[Dict[str, Any]] = None
    belief_action_alignment: float = 0.5
    threat_response_readiness: float = 0.5
    
    # === ClassVar常量 ===
    TENSION_MIN: ClassVar[float] = _TENSION_MIN
    TENSION_MAX: ClassVar[float] = _TENSION_MAX
    AUTHENTICITY_MIN: ClassVar[float] = _AUTHENTICITY_MIN
    AUTHENTICITY_MAX: ClassVar[float] = _AUTHENTICITY_MAX
    
    def __post_init__(self) -> None:
        """初始化时钳制所有数值字段"""
        if not self.timestamp:
            self.timestamp = time.time()
        
        self.authenticity_score = _clamp(
            self.authenticity_score,
            self.AUTHENTICITY_MIN,
            self.AUTHENTICITY_MAX,
        )
        self.cognitive_dissonance = _clamp(self.cognitive_dissonance, 0.0, 1.0)
        self.existential_anxiety = _clamp(self.existential_anxiety, 0.0, 1.0)
        self.narrative_tension = _clamp(self.narrative_tension, 0.0, 1.0)
        self.trust_level_current = _clamp(self.trust_level_current, 0.0, 1.0)
        self.urgency_level = _clamp(self.urgency_level, _URGENCY_MIN, _URGENCY_MAX)
        self.belief_action_alignment = _clamp(self.belief_action_alignment, 0.0, 1.0)
        self.threat_response_readiness = _clamp(self.threat_response_readiness, 0.0, 1.0)
    
    def to_prompt_fragment(self, max_length: int = 500) -> str:
        """
        转换为适合注入LLM prompt的结构化文本
        
        格式规则:
        1. 分段清晰, 使用[标签]标识各部分
        2. 按重要性排序: 人格内核 > 动机 > 记忆 > 社交 > 场景
        3. 低重要性字段省略 (值为默认值时)
        4. 总长度不超过max_length
        
        Args:
            max_length: 最大字符长度
            
        Returns:
            格式化的状态文本
        """
        sections: List[str] = []
        
        if self.dominant_archetype:
            shadow_str = f"阴影:{self.shadow_state.name}"
            persona_str = f"面具:{self.persona_description}" if self.persona_active else "面具:未激活"
            sections.append(f"[深层人格] 原型:{self.dominant_archetype} | {shadow_str} | {persona_str}")
        
        tension_map = {
            PsychologicalTensionLevel.CALM: "平静",
            PsychologicalTensionLevel.TENSE: "紧绷",
            PsychologicalTensionLevel.CRISIS: "危机",
            PsychologicalTensionLevel.DISSOCIATED: "解离",
        }
        if self.tension_level != PsychologicalTensionLevel.CALM or self.existential_anxiety > 0.3:
            auth_pct = int(self.authenticity_score * 100)
            anxiety_pct = int(self.existential_anxiety * 100)
            sections.append(
                f"[存在状态] 张力:{tension_map.get(self.tension_level, '未知')} "
                f"| 本真:{auth_pct}% | 焦虑:{anxiety_pct}%"
            )
        
        phase_map = {
            NarrativeArcPhase.CALL: "启程召唤",
            NarrativeArcPhase.INITIATION: "试炼入门",
            NarrativeArcPhase.ORDEAL: "严峻考验",
            NarrativeArcPhase.TRANSFORMATION: "蜕变转化",
            NarrativeArcPhase.RETURN: "回归升华",
        }
        if self.core_narrative:
            phase_name = phase_map.get(self.narrative_phase, "未知")
            sections.append(f"[叙事弧] 阶段:{phase_name}: {self.core_narrative}")
        
        if self.dominant_need:
            sat = self.need_satisfaction_map.get(self.dominant_need, 0.5)
            sat_pct = int(sat * 100)
            urg = f"{self.urgency_level:.1f}"
            conflict_str = f" | 冲突:{self.current_conflict}" if self.current_conflict else ""
            sections.append(f"[主导需求] {self.dominant_need}(满足度:{sat_pct}% | 紧急:{urg}){conflict_str}")
        
        if self.relevant_memories:
            mem_parts: List[str] = []
            for m in self.relevant_memories[:3]:
                content = m.get("content", "")
                emotion = m.get("emotion", "")
                if content:
                    entry = content[:40]
                    if emotion:
                        entry = f"{entry}({emotion})"
                    mem_parts.append(entry)
            if mem_parts:
                sections.append(f"[核心记忆] {'; '.join(mem_parts)}")
        
        if self.relationship_summary:
            trust_pct = int(self.trust_level_current * 100)
            role_str = f" | 角色:{self.social_role}" if self.social_role else ""
            sections.append(f"[社交关系] {self.relationship_summary} | 信任:{trust_pct}%{role_str}")
        
        result = " ".join(sections)
        
        if len(result) > max_length:
            result = result[:max_length - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典 (用于持久化/传输)"""
        return {
            "character_id": self.character_id,
            "timestamp": self.timestamp,
            "scene_context": self.scene_context,
            "dominant_archetype": self.dominant_archetype,
            "shadow_state": self.shadow_state.name,
            "active_shadow_aspects": list(self.active_shadow_aspects),
            "persona_active": self.persona_active,
            "persona_description": self.persona_description,
            "tension_level": self.tension_level.name,
            "authenticity_score": self.authenticity_score,
            "cognitive_dissonance": self.cognitive_dissonance,
            "existential_anxiety": self.existential_anxiety,
            "bad_faith_indicators": list(self.bad_faith_indicators),
            "narrative_phase": self.narrative_phase.name,
            "core_narrative": self.core_narrative,
            "identity_statement": self.identity_statement,
            "narrative_tension": self.narrative_tension,
            "relationship_summary": self.relationship_summary,
            "social_role": self.social_role,
            "trust_level_current": self.trust_level_current,
            "relevant_memories": list(self.relevant_memories),
            "memory_count_total": self.memory_count_total,
            "recent_memory_emotion": self.recent_memory_emotion,
            "dominant_need": self.dominant_need,
            "motivation_dominance": self.motivation_dominance.name,
            "need_satisfaction_map": dict(self.need_satisfaction_map),
            "current_conflict": self.current_conflict,
            "urgency_level": self.urgency_level,
            "overall_mood": self.overall_mood,
            "behavioral_tendency": self.behavioral_tendency,
            "response_style_hint": self.response_style_hint,
            "should_trigger_shadow": self.should_trigger_shadow,
            "consistency_issues": list(self.consistency_issues),
            # === Phase 4: 博弈论状态 ===
            "primary_target_beliefs": dict(self.primary_target_beliefs),
            "active_threats": list(self.active_threats),
            "current_strategy": dict(self.current_strategy) if self.current_strategy else None,
            "belief_action_alignment": self.belief_action_alignment,
            "threat_response_readiness": self.threat_response_readiness,
        }
    
    @property
    def is_under_stress(self) -> bool:
        """判断是否处于压力状态"""
        high_tension = self.tension_level in (
            PsychologicalTensionLevel.TENSE,
            PsychologicalTensionLevel.CRISIS,
            PsychologicalTensionLevel.DISSOCIATED,
        )
        high_anxiety = self.existential_anxiety > 0.6
        active_shadow = self.shadow_state in (
            ShadowActivationState.ACTIVE,
            ShadowActivationState.OVERRUN,
        )
        return high_tension or high_anxiety or active_shadow
    
    @property
    def complexity_score(self) -> float:
        """
        计算状态复杂度分数 (用于决定Prompt信息密度)
        
        Returns:
            复杂度 [0.0, 1.0]
        """
        score: float = 0.0
        
        if self.active_shadow_aspects:
            score += min(len(self.active_shadow_aspects) * 0.15, 0.30)
        if self.tension_level != PsychologicalTensionLevel.CALM:
            score += 0.15
        if self.existential_anxiety > 0.3:
            score += 0.10
        if self.current_conflict:
            score += 0.20
        if self.relevant_memories:
            score += min(len(self.relevant_memories) * 0.03, 0.15)
        if self.core_narrative and self.narrative_tension > 0.5:
            score += 0.10
        
        return min(score, 1.0)


_TRUNCATION_SUFFIX: str = "..."


# ============================================================
# ConsistencyValidator — 一致性验证工具类
# ============================================================

class ConsistencyValidator:
    """
    一致性验证器 (静态工具类)
    
    功能:
    - 检查多个子系统输出之间的逻辑一致性
    - 生成问题描述和修复建议
    - 提供严重程度评级
    
    学术依据:
    - 认知一致性理论 (Festinger, 1957): 减少认知失调的动机
    - 心理测量学: 信度/效度检验方法论
    """
    
    SEVERITY_INFO = ConsistencySeverity.INFO
    SEVERITY_WARNING = ConsistencySeverity.WARNING
    SEVERITY_ERROR = ConsistencySeverity.ERROR
    
    SHADOW_ACTIVE_THRESHOLD: ClassVar[float] = 0.3
    HIGH_EMOTION_THRESHOLD: ClassVar[float] = 0.6
    LOW_SAFETY_THRESHOLD: ClassVar[float] = 0.35
    LOW_BELONGING_THRESHOLD: ClassVar[float] = 0.35
    
    @staticmethod
    def validate_emotion_shadow_consistency(
        emotion_state: Dict[str, float],
        shadow_state: ShadowActivationState,
        active_shadows: List[str],
    ) -> Optional[ConsistencyIssue]:
        """
        验证情绪与阴影状态的一致性
        
        规则:
        - OVERRUN → 必须有高强度负面情绪
        - ACTIVE → 应该有中等以上负面情绪
        - DORMANT + 高强度负面情绪 → 可能是未识别的阴影
        
        Args:
            emotion_state: {emotion_name: intensity} 字典
            shadow_state: 当前阴影激活状态
            active_shadows: 当前活跃阴影面名称列表
            
        Returns:
            None 如果一致, 否则返回ConsistencyIssue
        """
        if not emotion_state:
            return None
        
        max_emotion_val = max(emotion_state.values()) if emotion_state.values() else 0.0
        
        if shadow_state == ShadowActivationState.OVERRUN:
            if max_emotion_val < ConsistencyValidator.HIGH_EMOTION_THRESHOLD:
                return ConsistencyIssue(
                    issue_type=ConsistencyIssueType.EMOTION_SHADOW_MISMATCH,
                    severity=ConsistencyValidator.SEVERITY_ERROR,
                    message=f"阴影处于OVERRUN状态但情绪强度仅{max_emotion_val:.2f}",
                    suggestion="提升情绪强度或降低阴影激活等级",
                    subsystems_involved=["jungian", "emotion"],
                )
        
        elif shadow_state == ShadowActivationState.ACTIVE:
            if max_emotion_val < 0.4:
                return ConsistencyIssue(
                    issue_type=ConsistencyIssueType.EMOTION_SHADOW_MISMATCH,
                    severity=ConsistencyValidator.SEVERITY_WARNING,
                    message=f"阴影ACTIVE但情绪强度偏低({max_emotion_val:.2f})",
                    suggestion="确认阴影触发条件或调整情绪状态",
                    subsystems_involved=["jungian", "emotion"],
                )
        
        elif shadow_state == ShadowActivationState.DORMANT and active_shadows:
            if max_emotion_val > ConsistencyValidator.HIGH_EMOTION_THRESHOLD:
                return ConsistencyIssue(
                    issue_type=ConsistencyIssueType.EMOTION_SHADOW_MISMATCH,
                    severity=ConsistencyValidator.SEVERITY_WARNING,
                    message="高强度负面情绪但阴影标记为DORMANT, 可能有未识别阴影面",
                    suggestion="考虑添加对应的ShadowAspect或重新评估阴影状态",
                    subsystems_involved=["jungian", "emotion"],
                )
        
        return None
    
    @staticmethod
    def validate_memory_motivation_consistency(
        recent_memories: List[Dict[str, Any]],
        dominant_need: str,
        need_satisfaction: Dict[str, float],
    ) -> Optional[ConsistencyIssue]:
        """
        验证记忆与动机的一致性
        
        规则:
        - 威胁事件 → SAFETY需求应该低
        - 社交成功 → BELONGING/ESTEEM应该受影响
        - 长期孤独 → BELONGING应该很低
        
        Args:
            recent_memories: 最近的相关记忆列表
            dominant_need: 主导需求名称
            need_satisfaction: 各层级满足度字典
            
        Returns:
            None 如果一致, 否则返回ConsistencyIssue
        """
        if not recent_memories or not need_satisfaction:
            return None
        
        threat_keywords = ["威胁", "危险", "袭击", "恐惧", "攻击", "死亡"]
        social_positive_keywords = ["友好", "帮助", "信任", "感谢", "赞赏"]
        isolation_keywords = ["孤独", "被抛弃", "无人", "独自"]
        
        for mem in recent_memories[:5]:
            content_lower = (mem.get("content", "") or "").lower()
            
            has_threat = any(kw in content_lower for kw in threat_keywords)
            has_social_pos = any(kw in content_lower for kw in social_positive_keywords)
            has_isolation = any(kw in content_lower for kw in isolation_keywords)
            
            safety_sat = need_satisfaction.get("PHYSIOLOGICAL", 0.5)
            belonging_sat = need_satisfaction.get("BELONGING", 0.5)
            
            if has_threat and safety_sat > 0.7:
                return ConsistencyIssue(
                    issue_type=ConsistencyIssueType.MEMORY_MOTIVATION_CONTRADICTION,
                    severity=ConsistencyValidator.SEVERITY_WARNING,
                    message=f"最近记忆包含威胁但安全满足度为{safety_sat:.2f}",
                    suggestion="降低安全需求满足度或更新记忆检索结果",
                    subsystems_involved=["memory", "motivation"],
                )
            
            if has_social_pos and belonging_sat < 0.25:
                return ConsistencyIssue(
                    issue_type=ConsistencyIssueType.MEMORY_MOTIVATION_CONTRADICTION,
                    severity=ConsistencyValidator.SEVERITY_INFO,
                    message="社交正面记忆与低归属感并存(可能是近期变化)",
                    suggestion="确认时间线一致性或接受为正常状态变迁",
                    subsystems_involved=["memory", "motivation"],
                )
            
            if has_isolation and belonging_sat > 0.7:
                return ConsistencyIssue(
                    issue_type=ConsistencyIssueType.MEMORY_MOTIVATION_CONTRADICTION,
                    severity=ConsistencyValidator.SEVERITY_WARNING,
                    message="孤立相关记忆与高归属感矛盾",
                    suggestion="检查归属感计算或记忆相关性评分",
                    subsystems_involved=["memory", "motivation"],
                )
        
        return None
    
    @staticmethod
    def validate_narrative_behavior_consistency(
        narrative_phase: NarrativeArcPhase,
        behavioral_tendency: str,
        authenticity_score: float,
    ) -> Optional[ConsistencyIssue]:
        """
        验证叙事阶段与行为倾向的一致性
        
        规则:
        - CALL阶段: 探索欲/困惑
        - ORDEAL阶段: 挣扎/坚持
        - TRANSFORMATION阶段: 成长/释然
        - RETURN阶段: 自信/智慧
        
        Args:
            narrative_phase: 当前叙事弧阶段
            behavioral_tendency: 行为倾向描述
            authenticity_score: 本真性分数
            
        Returns:
            None 如果一致, 否则返回ConsistencyIssue
        """
        if not behavioral_tendency:
            return None
        
        expected_tendencies = {
            NarrativeArcPhase.CALL: ["探索", "困惑", "迷茫", "好奇"],
            NarrativeArcPhase.INITIATION: ["学习", "尝试", "成长", "适应"],
            NarrativeArcPhase.ORDEAL: ["挣扎", "坚持", "痛苦", "对抗"],
            NarrativeArcPhase.TRANSFORMATION: ["成长", "释然", "领悟", "改变"],
            NarrativeArcPhase.RETURN: ["自信", "智慧", "平静", "从容"],
        }
        
        expected_keywords = expected_tendencies.get(narrative_phase, [])
        behavior_lower = behavioral_tendency.lower()
        
        has_expected = any(kw in behavior_lower for kw in expected_keywords)
        
        opposite_map = {
            NarrativeArcPhase.ORDEAL: ["轻松", "随意", "无忧"],
            NarrativeArcPhase.TRANSFORMATION: ["固执", "绝望", "崩溃"],
            NarrativeArcPhase.RETURN: ["慌乱", "困惑", "冲动"],
        }
        opposite_keywords = opposite_map.get(narrative_phase, [])
        has_opposite = any(kw in behavior_lower for kw in opposite_keywords)
        
        if has_opposite and not has_expected:
            return ConsistencyIssue(
                issue_type=ConsistencyIssueType.NARRATIVE_BEHAVIOR_MISMATCH,
                severity=ConsistencyValidator.SEVERITY_WARNING,
                message=f"叙事阶段{narrative_phase.name}与行为倾向'{behavioral_tendency}'不匹配",
                suggestion="调整行为倾向描述或重新评估叙事阶段",
                subsystems_involved=["narrative", "behavior"],
            )
        
        return None


# ============================================================
# DeepCharacter — 深度角色聚合器 (主类)
# ============================================================

class DeepCharacter:
    """
    深度角色聚合器 (主类)
    
    功能:
    - 统一管理所有Phase 1/2子系统
    - 提供一致性的状态查询接口
    - 自动执行子系统间的一致性验证
    - 生成可用于Prompt注入的完整状态快照
    
    设计约束:
    - 组合模式 (非继承), 每个子系统作为独立组件
    - 惰性初始化 (首次访问时创建子系统)
    - 事件驱动同步 (子系统变化时通知聚合层)
    
    使用示例:
        >>> dc = DeepCharacter(character_id="alice", name="爱丽丝")
        >>> state = dc.get_state_snapshot(scene="玫瑰酒馆")
        >>> prompt_text = state.to_prompt_fragment()
    """
    
    DEFAULT_SHADOW_THRESHOLD: ClassVar[float] = _DEFAULT_SHADOW_THRESHOLD
    DEFAULT_TENSION_THRESHOLD: ClassVar[float] = _DEFAULT_TENSION_THRESHOLD
    CONSISTENCY_CHECK_INTERVAL: ClassVar[int] = _CONSISTENCY_CHECK_INTERVAL
    MAX_CONSISTENCY_ISSUES: ClassVar[int] = _MAX_CONSISTENCY_ISSUES
    
    def __init__(
        self,
        character_id: EntityId,
        name: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._character_id = character_id
        self._name = name
        self._config = config or {}
        
        self._jungian: Optional[Any] = None
        self._existential: Optional[Any] = None
        self._narrative: Optional[Any] = None
        self._social: Optional[Any] = None
        self._memory: Optional[Any] = None
        self._motivation: Optional[Any] = None
        
        # === Phase 4: 博弈论子系统 (惰性初始化) ===
        self._belief_system: Optional[Any] = None
        self._threat_engine: Optional[Any] = None
        self._strategy_engine: Optional[Any] = None
        
        self._operation_count: int = 0
        self._last_consistency_check: int = 0
        self._cached_state: Optional[DeepCharacterState] = None
        self._cache_valid: bool = False
        self._recent_events: List[Tuple[str, float, float]] = []
    
    @property
    def character_id(self) -> EntityId:
        """获取角色ID"""
        return self._character_id
    
    @property
    def name(self) -> str:
        """获取角色名称"""
        return self._name
    
    # ================================================================
    # 子系统访问器 (惰性初始化)
    # ================================================================
    
    @property
    def jungian(self) -> Any:
        """获取荣格模型 (不存在则用默认配置创建)"""
        if self._jungian is None:
            from luqi_engine.character.jungian_model import JungianProfile
            self._jungian = JungianProfile()
        return self._jungian
    
    @property
    def existential(self) -> Any:
        """获取存在主义模型 (不存在则用默认配置创建)"""
        if self._existential is None:
            from luqi_engine.character.existential_model import ExistentialProfile
            self._existential = ExistentialProfile()
        return self._existential
    
    @property
    def narrative(self) -> Any:
        """获取叙事身份 (不存在则用默认配置创建)"""
        if self._narrative is None:
            from luqi_engine.character.narrative_identity import NarrativeIdentity
            self._narrative = NarrativeIdentity(character_id=self._character_id)
        return self._narrative
    
    @property
    def social(self) -> Any:
        """获取社交演化引擎 (不存在则用默认配置创建)"""
        if self._social is None:
            from luqi_engine.character.social_evolution import SocialEvolutionEngine
            self._social = SocialEvolutionEngine(character_id=self._character_id)
        return self._social
    
    @property
    def memory(self) -> Any:
        """获取记忆系统 (不存在则创建)"""
        if self._memory is None:
            from luqi_engine.memory.memory_system import MemorySystem
            self._memory = MemorySystem(character_id=self._character_id)
        return self._memory
    
    @property
    def motivation(self) -> Any:
        """获取动机引擎 (不存在则创建)"""
        if self._motivation is None:
            from luqi_engine.motivation.maslow_engine import MotivationEngine
            self._motivation = MotivationEngine(character_id=self._character_id)
        return self._motivation
    
    # === Phase 4: 博弈论子系统访问器 (惰性初始化) ===
    
    @property
    def belief_system(self) -> Any:
        """获取信念系统 (不存在则用默认配置创建)"""
        if self._belief_system is None:
            from luqi_engine.game_theory.belief_system import BeliefSystem
            self._belief_system = BeliefSystem(character_id=self._character_id)
        return self._belief_system
    
    @property
    def threat_engine(self) -> Any:
        """获取威胁可信度引擎 (不存在则用默认配置创建)"""
        if self._threat_engine is None:
            from luqi_engine.game_theory.threat_credibility import ThreatCredibilityEngine
            self._threat_engine = ThreatCredibilityEngine(
                character_id=self._character_id,
            )
        return self._threat_engine
    
    @property
    def strategy_engine(self) -> Any:
        """获取混合策略引擎 (不存在则用默认配置创建)"""
        if self._strategy_engine is None:
            from luqi_engine.game_theory.mixed_strategy import MixedStrategyEngine
            self._strategy_engine = MixedStrategyEngine()
        return self._strategy_engine
    
    # ================================================================
    # 初始化方法
    # ================================================================
    
    def initialize_from_profile(
        self,
        jungian_config: Optional[Dict[str, Any]] = None,
        existential_config: Optional[Dict[str, Any]] = None,
        narrative_config: Optional[Dict[str, Any]] = None,
        social_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        从配置字典批量初始化各子系统
        
        Args:
            jungian_config: 荣格模型配置 (原型选择、阴影定义等)
            existential_config: 存在主义模型配置
            narrative_config: 叙事身份配置
            social_config: 社交演化配置
        """
        if jungian_config:
            from luqi_engine.character.jungian_model import JungianProfile, Archetype, ShadowAspect, PersonaLayer
            archetype_name = jungian_config.get("archetype", "EVERYMAN")
            archetype = Archetype[archetype_name] if archetype_name in Archetype.__members__ else Archetype.EVERYMAN
            
            shadows_data = jungian_config.get("shadows", [])
            shadows = []
            for sd in shadows_data:
                shadows.append(ShadowAspect(
                    name=sd.get("name", ""),
                    intensity=sd.get("intensity", 0.0),
                    repression_level=sd.get("repression_level", 0.5),
                    trigger_conditions=sd.get("trigger_conditions", []),
                ))
            
            persona_data = jungian_config.get("persona")
            persona = None
            if persona_data:
                persona = PersonaLayer(
                    description=persona_data.get("description", ""),
                    strength=persona_data.get("strength", 0.5),
                    expected_behaviors=persona_data.get("social_contexts", []),
                )
            
            confidence = jungian_config.get("archetype_confidence", 0.5)
            self._jungian = JungianProfile(
                shadows=shadows,
                persona=persona,
                archetype=archetype,
                archetype_confidence=confidence,
            )
        
        if existential_config:
            from luqi_engine.character.existential_model import ExistentialProfile, AuthenticityState
            auth_name = existential_config.get("authenticity", "AUTHENTIC")
            auth_state = AuthenticityState[auth_name] if auth_name in AuthenticityState.__members__ else AuthenticityState.AUTHENTIC
            
            self._existential = ExistentialProfile(
                authenticity=auth_state,
                anxiety_level=existential_config.get("anxiety_level", 0.0),
                freedom_avoidance=existential_config.get("freedom_avoidance", 0.3),
                responsibility_threshold=existential_config.get("responsibility_threshold", 0.5),
                core_values=existential_config.get("core_values", []),
                existential_dread_triggers=existential_config.get("dread_triggers", []),
            )
            
            beliefs_data = existential_config.get("beliefs", {})
            for bid, bdata in beliefs_data.items():
                if isinstance(bdata, dict):
                    self._existential.add_belief(
                        belief_id=bid,
                        content=bdata.get("content", ""),
                        strength=bdata.get("strength", 0.5),
                        source=bdata.get("source", ""),
                    )
        
        if narrative_config:
            from luqi_engine.character.narrative_identity import NarrativeIdentity, NarrativeEpisode, LifeChapter
            self._narrative = NarrativeIdentity(character_id=self._character_id)
            
            episodes_data = narrative_config.get("episodes", [])
            for ep_data in episodes_data:
                if isinstance(ep_data, dict):
                    chapter_name = ep_data.get("chapter", "ORIGIN")
                    chapter = LifeChapter[chapter_name] if chapter_name in LifeChapter.__members__ else LifeChapter.ORIGIN
                    
                    episode = NarrativeEpisode(
                        episode_id=ep_data.get("episode_id", ""),
                        title=ep_data.get("title", ""),
                        description=ep_data.get("description", ""),
                        chapter=chapter,
                        timestamp=ep_data.get("timestamp", -1.0),
                        significance=ep_data.get("significance", 0.5),
                        emotional_tags=ep_data.get("emotional_tags", []),
                        learned_lesson=ep_data.get("learned_lesson"),
                    )
                    self._narrative.add_episode(episode)
        
        self.invalidate_cache()
    
    def initialize_from_existing(
        self,
        jungian: Optional[Any] = None,
        existential: Optional[Any] = None,
        narrative: Optional[Any] = None,
        social: Optional[Any] = None,
        memory: Optional[Any] = None,
        motivation: Optional[Any] = None,
    ) -> None:
        """注入已有的子系统实例 (用于从存档恢复或测试)"""
        if jungian is not None:
            self._jungian = jungian
        if existential is not None:
            self._existential = existential
        if narrative is not None:
            self._narrative = narrative
        if social is not None:
            self._social = social
        if memory is not None:
            self._memory = memory
        if motivation is not None:
            self._motivation = motivation
        self.invalidate_cache()
    
    # ================================================================
    # 核心功能: 状态快照
    # ================================================================
    
    def get_state_snapshot(
        self,
        scene_context: str = "",
        query_keywords: Optional[List[str]] = None,
        target_entity_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> DeepCharacterState:
        """
        生成完整的心理状态快照
        
        Args:
            scene_context: 当前场景描述
            query_keywords: 关键词 (用于检索相关记忆)
            target_entity_id: 目标实体ID
            force_refresh: 是否强制刷新
            
        Returns:
            完整的DeepCharacterState对象
        """
        if not force_refresh and self._cache_valid and self._cached_state is not None:
            cached = self._cached_state
            if scene_context == cached.scene_context:
                return cached
        
        state = DeepCharacterState(
            character_id=self._character_id,
            scene_context=scene_context,
        )
        
        keywords = query_keywords or []
        
        self._populate_jungian_state(state, keywords)
        self._populate_existential_state(state)
        self._populate_narrative_state(state)
        self._populate_social_state(state, target_entity_id)
        self._populate_memory_state(state, keywords)
        self._populate_motivation_state(state)
        self._populate_game_theory_state(state, target_entity_id)
        self._compute_derived_indicators(state)
        
        self._operation_count += 1
        
        if self._operation_count - self._last_consistency_check >= self.CONSISTENCY_CHECK_INTERVAL:
            issues = self.check_consistency()
            state.consistency_issues = [i.message for i in issues]
            self._last_consistency_check = self._operation_count
        
        self._cached_state = state
        self._cache_valid = True
        
        return state
    
    def invalidate_cache(self) -> None:
        """使状态缓存失效"""
        self._cache_valid = False
        self._cached_state = None
    
    # ================================================================
    # 内部方法: 状态填充
    # ================================================================
    
    def _populate_jungian_state(
        self, state: DeepCharacterState, keywords: List[str]
    ) -> None:
        """从荣格模型提取状态"""
        try:
            jp = self.jungian
            
            state.dominant_archetype = jp.archetype.name if hasattr(jp, 'archetype') else ""
            
            dominant_shadow, influence = jp.get_dominant_shadow(keywords)
            
            if influence >= 0.8:
                state.shadow_state = ShadowActivationState.OVERRUN
            elif influence >= 0.4:
                state.shadow_state = ShadowActivationState.ACTIVE
            elif influence >= 0.1:
                state.shadow_state = ShadowActivationState.RUMBLING
            else:
                state.shadow_state = ShadowActivationState.DORMANT
            
            if dominant_shadow is not None:
                state.active_shadow_aspects.append(dominant_shadow.name)
                
                all_influence_sum = 0.0
                for s in jp.shadows:
                    si = s.get_influence_context(keywords)
                    all_influence_sum += si
                    if si > 0.05 and s is not dominant_shadow:
                        state.active_shadow_aspects.append(s.name)
            
            if jp.persona is not None:
                state.persona_active = jp.persona.strength > 0.3
                state.persona_description = jp.persona.description
            
            inner_conflict = jp.compute_inner_conflict(keywords)
            if inner_conflict > 0.6:
                state.tension_level = PsychologicalTensionLevel.CRISIS
            elif inner_conflict > 0.3:
                state.tension_level = PsychologicalTensionLevel.TENSE
            elif inner_conflict > 0.0:
                state.tension_level = PsychologicalTensionLevel.TENSE
            
            state.should_trigger_shadow = influence >= self.DEFAULT_SHADOW_THRESHOLD
            
        except Exception:
            pass
    
    def _populate_existential_state(self, state: DeepCharacterState) -> None:
        """从存在主义模型提取状态"""
        try:
            ep = self.existential
            
            anxiety = getattr(ep, 'anxiety_level', 0.0)
            state.existential_anxiety = _clamp(anxiety, 0.0, 1.0)
            
            auth_state = getattr(ep, 'authenticity', None)
            if auth_state is not None:
                auth_map = {
                    "AUTHENTIC": 0.9,
                    "COMPROMISED": 0.5,
                    "BAD_FAITH": 0.3,
                    "CRISIS": 0.1,
                }
                state.authenticity_score = auth_map.get(auth_state.name if hasattr(auth_state, 'name') else str(auth_state), 0.5)
            
            dissonance_count = 0
            max_dissonance = 0.0
            if hasattr(ep, 'dissonance_history'):
                dissonance_count = ep.get_active_dissonance_count() if hasattr(ep, 'get_active_dissonance_count') else len(ep.dissonance_history)
                max_dissonance = ep.get_max_dissonance_magnitude() if hasattr(ep, 'get_max_dissonance_magnitude') else 0.0
                
                for d in ep.dissonance_history[-_MAX_BAD_FAITH_INDICATORS:]:
                    if hasattr(d, 'resolution_strategy') and d.resolution_strategy:
                        rs_name = d.resolution_strategy.name if hasattr(d.resolution_strategy, 'name') else str(d.resolution_strategy)
                        if rs_name in ("deny", "DENY"):
                            state.bad_faith_indicators.append(f"否认冲突: {d.conflicting_beliefs}")
            
            state.cognitive_dissonance = _clamp(max_dissonance, 0.0, 1.0)
            
            if state.existential_anxiety > 0.7:
                state.tension_level = PsychologicalTensionLevel.DISSOCIATED
            elif state.existential_anxiety > 0.4 and state.tension_level == PsychologicalTensionLevel.CALM:
                state.tension_level = PsychologicalTensionLevel.TENSE
            
        except Exception:
            pass
    
    def _populate_narrative_state(self, state: DeepCharacterState) -> None:
        """从叙事身份提取状态"""
        try:
            ni = self.narrative
            
            identity_summary = ni.get_identity_summary() if hasattr(ni, 'get_identity_summary') else ""
            if identity_summary:
                state.identity_statement = identity_summary[:100]
                state.core_narrative = identity_summary[:80]
            
            defining_moments = ni.get_defining_moments() if hasattr(ni, 'get_defining_moments') else []
            if defining_moments:
                total_sig = sum(dm.significance for dm in defining_moments)
                count = max(len(defining_moments), 1)
                avg_tension = total_sig / count
                state.narrative_tension = _clamp(avg_tension, 0.0, 1.0)
                
                most_significant = max(defining_moments, key=lambda x: x.significance)
                chapter_name = most_significant.chapter.name if hasattr(most_significant.chapter, 'name') else str(most_significant.chapter)
                
                chapter_to_phase = {
                    "ORIGIN": NarrativeArcPhase.CALL,
                    "TRIALS": NarrativeArcPhase.INITIATION,
                    "TRANSFORMATION": NarrativeArcPhase.TRANSFORMATION,
                    "MATURITY": NarrativeArcPhase.RETURN,
                    "LEGACY": NarrativeArcPhase.RETURN,
                }
                state.narrative_phase = chapter_to_phase.get(chapter_name, NarrativeArcPhase.CALL)
                
                if most_significant.learned_lesson:
                    state.core_narrative = most_significant.learned_lesson[:80]
            
        except Exception:
            pass
    
    def _populate_social_state(
        self, state: DeepCharacterState, target_entity_id: Optional[str]
    ) -> None:
        """从社交演化系统提取状态"""
        try:
            se = self.social
            
            if target_entity_id:
                rel = se.get_relationship(self._character_id, target_entity_id)
                if rel is not None:
                    state.trust_level_current = _clamp(rel.trust, 0.0, 1.0)
                    
                    if rel.intimacy > 0.5:
                        state.social_role = "亲密伙伴"
                    elif rel.intimacy > 0.2:
                        state.social_role = "熟人"
                    elif rel.intimacy > -0.2:
                        state.social_role = "陌生人"
                    else:
                        state.social_role = "对立者"
                    
                    summary = se.get_relation_summary_for_prompt(target_entity_id)
                    if summary:
                        state.relationship_summary = summary[:80]
            
            state.relationship_summary = state.relationship_summary or ""
            state.social_role = state.social_role or ""
            
        except Exception:
            pass
    
    def _populate_memory_state(
        self, state: DeepCharacterState, keywords: List[str]
    ) -> None:
        """从记忆系统提取状态"""
        try:
            ms = self.memory
            
            state.memory_count_total = ms.memory_count
            
            if keywords:
                retrieval = ms.retrieve(query=keywords, max_results=5)
                state.relevant_memories = []
                for episode, score in retrieval.episodes:
                    state.relevant_memories.append({
                        "content": episode.content[:60],
                        "importance": round(episode.current_importance, 3),
                        "emotion": ", ".join(e.name for e in episode.emotions) if episode.emotions else "",
                    })
                    
                    if not state.recent_memory_emotion and episode.emotions:
                        state.recent_memory_emotion = episode.emotions[0].name
            
            if not state.relevant_memories and state.memory_count_total > 0:
                stats = ms.get_statistics()
                top_memories = stats.get("top_memories", [])
                if top_memories:
                    for tm in top_memories[:3]:
                        if isinstance(tm, dict):
                            state.relevant_memories.append({
                                "content": tm.get("content", "")[:60],
                                "importance": tm.get("importance", 0.5),
                                "emotion": tm.get("emotion", ""),
                            })
        
        except Exception:
            pass
    
    def _populate_motivation_state(self, state: DeepCharacterState) -> None:
        """从马斯洛动机引擎提取状态"""
        try:
            me = self.motivation
            
            dominant, strength = me.profile.get_dominant_need()
            state.dominant_need = dominant.name if hasattr(dominant, 'name') else str(dominant)
            
            motivations = me.calculate_all_motivations()
            state.need_satisfaction_map = {}
            for level, mot_strength in motivations.items():
                level_name = level.name if hasattr(level, 'name') else str(level)
                state.need_satisfaction_map[level_name] = round(mot_strength, 3)
            
            if strength > 0.7:
                state.motivation_dominance = MotivationDominance.DEFICIENCY
            elif strength > 0.4:
                state.motivation_dominance = MotivationDominance.GROWTH
            elif strength > 0.2:
                state.motivation_dominance = MotivationDominance.META
            else:
                state.motivation_dominance = MotivationDominance.CONFLICT
            
            conflict = me.detect_conflicts()
            if conflict is not None:
                state.current_conflict = conflict.conflict_type.name if hasattr(conflict.conflict_type, 'name') else str(conflict.conflict_type)
                state.motivation_dominance = MotivationDominance.CONFLICT
            
            state.urgency_level = _clamp(getattr(me, '_urgency', 1.0), _URGENCY_MIN, _URGENCY_MAX)
        
        except Exception:
            pass
    
    def _populate_game_theory_state(
        self, state: DeepCharacterState, target_entity_id: Optional[str]
    ) -> None:
        """从博弈论子系统提取状态 (Phase 4)"""
        try:
            bs = self.belief_system
            
            all_targets = bs.get_all_targets()
            
            if target_entity_id and target_entity_id in all_targets:
                summary = bs.get_target_summary(target_entity_id)
                state.primary_target_beliefs[target_entity_id] = round(
                    summary.get("overall_cooperation_estimate", 0.5), 4
                )
            
            if not target_entity_id and all_targets:
                primary = all_targets[0] if all_targets else ""
                if primary:
                    summary = bs.get_target_summary(primary)
                    state.primary_target_beliefs[primary] = round(
                        summary.get("overall_cooperation_estimate", 0.5), 4
                    )
            
            for tid in list(state.primary_target_beliefs.keys())[:5]:
                belief_frag = bs.to_prompt_fragment(tid, max_length=100)
                state.active_threats.append({
                    "target": tid,
                    "belief_summary": belief_frag,
                })
        
        except Exception:
            pass
        
        try:
            te = self.threat_engine
            
            if target_entity_id:
                try:
                    cred = te.get_credibility(target_entity_id)
                    state.threat_response_readiness = _clamp(
                        cred.overall_score, 0.0, 1.0
                    )
                except KeyError:
                    pass
        
        except Exception:
            pass
        
        try:
            se = self.strategy_engine
            
            if target_entity_id:
                try:
                    profile = se.generate_from_beliefs(
                        belief_system=self.belief_system,
                        target_id=target_entity_id,
                        urgency_level=state.urgency_level,
                    )
                    
                    dominant = profile.dominant_action
                    coop_prob = profile.action_probabilities.get(
                        __import__("luqi_engine.game_theory.types", fromlist=["StrategyAction"]).StrategyAction.COOPERATE,
                        0.3,
                    ) if hasattr(profile, 'action_probabilities') else 0.3
                    
                    belief_val = (
                        list(state.primary_target_beliefs.values())[0]
                        if state.primary_target_beliefs else 0.5
                    )
                    
                    state.current_strategy = {
                        "dominant_action": dominant.name if dominant else "OBSERVE",
                        "cooperate_probability": round(coop_prob, 3),
                        "entropy": round(profile.entropy, 3),
                        "temperature": round(profile.temperature, 2),
                    }
                    
                    alignment_diff = abs(coop_prob - belief_val)
                    state.belief_action_alignment = round(1.0 - min(alignment_diff * 2, 1.0), 3)
                
                except (KeyError, ValueError):
                    pass
        
        except Exception:
            pass
    
    def _compute_derived_indicators(self, state: DeepCharacterState) -> None:
        """计算综合衍生指标"""
        mood_parts: List[str] = []
        
        if state.existential_anxiety > 0.6:
            mood_parts.append("焦虑")
        if state.shadow_state in (ShadowActivationState.ACTIVE, ShadowActivationState.OVERRUN):
            mood_parts.append("内心冲突")
        if state.cognitive_dissonance > 0.4:
            mood_parts.append("矛盾")
        if state.narrative_tension > 0.6:
            mood_parts.append("挣扎中")
        
        if not mood_parts:
            if state.is_under_stress:
                mood_parts.append("紧张")
            else:
                mood_parts.append("平静")
        
        state.overall_mood = "+".join(mood_parts)
        
        tendency_parts: List[str] = []
        if state.dominant_need:
            need_tendency_map = {
                "PHYSIOLOGICAL": "寻求生存保障",
                "SAFETY": "规避风险",
                "BELONGING": "寻求连接",
                "ESTEEM": "追求认可",
                "COGNITIVE": "探索求知",
                "AESTHETIC": "追求美感",
                "SELF_ACTUALIZATION": "自我实现",
                "TRANSCENDENCE": "超越自我",
            }
            tendency_parts.append(need_tendency_map.get(state.dominant_need, ""))
        
        if state.authenticity_score < 0.4:
            tendency_parts.append("防御性姿态")
        elif state.authenticity_score > 0.8:
            tendency_parts.append("开放坦诚")
        
        if state.should_trigger_shadow:
            tendency_parts.append("可能受阴影影响")
        
        state.behavioral_tendency = ", ".join([t for t in tendency_parts if t])
        
        style_hints: List[str] = []
        if state.is_under_stress:
            style_hints.append("简短有力")
        if state.shadow_state == ShadowActivationState.OVERRUN:
            style_hints.append("可能出现失控表达")
        if state.narrative_phase == NarrativeArcPhase.ORDEAL:
            style_hints.append("带有一丝疲惫或坚定")
        if state.narrative_phase == NarrativeArcPhase.RETURN:
            style_hints.append("沉稳从容")
        
        state.response_style_hint = "; ".join(style_hints) if style_hints else "自然流畅"
    
    # ================================================================
    # 事件处理接口
    # ================================================================
    
    def on_event(
        self,
        event_type: str,
        intensity: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        处理外部事件, 同步更新所有相关子系统
        
        Args:
            event_type: 事件类型标识符
            intensity: 事件强度 [0, 1]
            metadata: 事件附加数据
            
        Returns:
            受影响的子系统名称列表
        """
        meta = metadata or {}
        affected: List[str] = []
        now = time.time()
        
        self._recent_events.append((event_type, intensity, now))
        if len(self._recent_events) > _MAX_RECENT_EVENTS:
            self._recent_events = self._recent_events[-_MAX_RECENT_EVENTS:]
        
        clamped_intensity = _clamp(intensity, 0.0, 1.0)
        
        if event_type == "dialogue_input":
            content = meta.get("content", "")
            speaker_id = meta.get("speaker_id")
            
            try:
                emotions = meta.get("emotions", [])
                entity_list = content.split()[:10] if content else []
                self.memory.store(
                    content=content[:200],
                    associated_entities=entity_list,
                    emotional_intensity=clamped_intensity,
                )
                affected.append("memory")
            except Exception:
                pass
            
            if speaker_id:
                try:
                    self.social.evolve_relationship(
                        char_a=self._character_id,
                        char_b=speaker_id,
                        action_type=meta.get("action_type", "DIALOGUE"),
                        interaction_context={"location": meta.get("location", "")},
                    )
                    affected.append("social")
                except Exception:
                    pass
            
            # === Phase 4: 信念更新 (对话事件) ===
            if speaker_id:
                try:
                    from luqi_engine.game_theory.types import (
                        BeliefDimension, Observation, ObservationType,
                    )
                    
                    content_text = meta.get("content", "")
                    positive_kw = ["帮助", "支持", "友好", "信任", "感谢", "保护"]
                    negative_kw = ["威胁", "攻击", "背叛", "欺骗", "危险", "恐吓"]
                    
                    content_lower = (content_text or "").lower()
                    is_positive = any(k in content_lower for k in positive_kw)
                    is_negative = any(k in content_lower for k in negative_kw)
                    
                    evidence_val = 0.8 if is_positive else (0.2 if is_negative else 0.5)
                    
                    obs = Observation(
                        observation_type=ObservationType.DIRECT_ACTION,
                        evidence_value=evidence_val,
                        description=f"对话:{(content_text or '')[:50]}",
                    )
                    self.belief_system.observe(
                        target_id=speaker_id,
                        dimension=BeliefDimension.COOPERATIVITY,
                        observation=obs,
                    )
                    affected.append("belief_system")
                except Exception:
                    pass
            
            try:
                shadow, _ = self.jungian.get_dominant_shadow(content.split())
                if shadow is not None and clamped_intensity > 0.5:
                    self.existential.anxiety_level = _clamp(
                        self.existential.anxiety_level + clamped_intensity * 0.1,
                        0.0, 1.0,
                    )
                    affected.append("existential")
            except Exception:
                pass
        
        elif event_type == "social_action":
            target_id = meta.get("target_id")
            action_type = meta.get("action_type", "DIALOGUE")
            value = meta.get("value", 0.0)
            
            if target_id:
                try:
                    self.social.evolve_relationship(
                        char_a=self._character_id,
                        char_b=target_id,
                        action_type=action_type,
                        interaction_context={"value": value},
                    )
                    affected.append("social")
                except Exception:
                    pass
            
            try:
                if clamped_intensity > 0.6:
                    new_belief = f"对{target_id}的{action_type}行为"
                    self.existential.detect_dissonance(
                        new_action=new_belief,
                        new_belief_content=new_belief,
                    )
                    affected.append("existential")
            except Exception:
                pass
            
            # === Phase 4: 威胁记录 (社交动作事件) ===
            if target_id and clamped_intensity > 0.5:
                try:
                    from luqi_engine.game_theory.types import (
                        ThreatRecord, ThreatType, CommitmentLevel,
                    )
                    
                    is_threatening = action_type in (
                        "THREATEN", "ATTACK", "INTIMIDATE", "COERCE"
                    )
                    
                    if is_threatening:
                        threat = ThreatRecord(
                            threat_type=ThreatType.COMMITMENT,
                            content=f"{action_type} against {target_id}",
                            commitment_level=CommitmentLevel.VERBAL,
                            estimated_cost=clamped_intensity,
                        )
                        self.threat_engine.record_threat(threat)
                        affected.append("threat_engine")
                    
                    from luqi_engine.game_theory.types import (
                        BeliefDimension, Observation, ObservationType,
                    )
                    evidence_val = 0.2 if is_threatening else 0.6
                    obs = Observation(
                        observation_type=ObservationType.DIRECT_ACTION,
                        evidence_value=evidence_val,
                        description=f"社交:{action_type}@{target_id}",
                    )
                    self.belief_system.observe(
                        target_id=target_id,
                        dimension=BeliefDimension.COOPERATIVITY,
                        observation=obs,
                    )
                    affected.append("belief_system")
                
                except Exception:
                    pass
        
        elif event_type == "environment_change":
            change_type = meta.get("change_type", "")
            description = meta.get("description", "")
            
            if "threat" in change_type.lower() or "danger" in description.lower():
                try:
                    from luqi_engine.motivation.maslow_engine import NeedLevel
                    self.motivation._profile.update_need_value(NeedLevel.SAFETY, delta=-clamped_intensity * 0.3)
                    affected.append("motivation")
                except Exception:
                    pass
                
                try:
                    self.existential.anxiety_level = _clamp(
                        self.existential.anxiety_level + clamped_intensity * 0.15,
                        0.0, 1.0,
                    )
                    affected.append("existential")
                except Exception:
                    pass
        
        elif event_type == "time_passage":
            delta_hours = meta.get("delta_hours", 1.0)
            
            try:
                self.memory.decay(force=True)
                affected.append("memory")
            except Exception:
                pass
            
            try:
                decay_factor = min(delta_hours / 24.0, 1.0) * 0.05
                new_anxiety = max(0.0, self.existential.anxiety_level - decay_factor)
                self.existential.anxiety_level = new_anxiety
                affected.append("existential")
            except Exception:
                pass
        
        elif event_type == "internal_conflict":
            try:
                self.existential.anxiety_level = _clamp(
                    self.existential.anxiety_level + clamped_intensity * 0.2,
                    0.0, 1.0,
                )
                affected.append("existential")
            except Exception:
                pass
            
            if clamped_intensity > 0.5:
                try:
                    self.jungian.compute_inner_conflict(meta.get("keywords", []))
                    affected.append("jungian")
                except Exception:
                    pass
        
        self.invalidate_cache()
        return affected
    
    def on_dialogue_turn(
        self,
        input_text: str,
        speaker_id: Optional[str] = None,
    ) -> None:
        """
        对话回合快捷方法
        
        Args:
            input_text: 用户/其他角色的输入文本
            speaker_id: 说话者ID (None=玩家/未知)
        """
        self.on_event(
            event_type="dialogue_input",
            intensity=0.5,
            metadata={
                "content": input_text,
                "speaker_id": speaker_id,
            },
        )
    
    # ================================================================
    # 一致性验证
    # ================================================================
    
    def check_consistency(self) -> List[ConsistencyIssue]:
        """
        执行完整的一致性验证
        
        Returns:
            发现的一致性问题列表 (空列表=完全一致)
        """
        if getattr(self, '_checking_consistency', False):
            return []
        
        self._checking_consistency = True
        try:
            issues: List[ConsistencyIssue] = []
            
            state = self.get_state_snapshot(force_refresh=True)
            
            emotion_dict: Dict[str, float] = {}
            if state.existential_anxiety > 0:
                emotion_dict["anxiety"] = state.existential_anxiety
            if state.cognitive_dissonance > 0:
                emotion_dict["dissonance"] = state.cognitive_dissonance
            
            shadow_issue = ConsistencyValidator.validate_emotion_shadow_consistency(
                emotion_state=emotion_dict,
                shadow_state=state.shadow_state,
                active_shadows=state.active_shadow_aspects,
            )
            if shadow_issue:
                issues.append(shadow_issue)
            
            memory_issue = ConsistencyValidator.validate_memory_motivation_consistency(
                recent_memories=state.relevant_memories,
                dominant_need=state.dominant_need,
                need_satisfaction=state.need_satisfaction_map,
            )
            if memory_issue:
                issues.append(memory_issue)
            
            narrative_issue = ConsistencyValidator.validate_narrative_behavior_consistency(
                narrative_phase=state.narrative_phase,
                behavioral_tendency=state.behavioral_tendency,
                authenticity_score=state.authenticity_score,
            )
            if narrative_issue:
                issues.append(narrative_issue)
            
            # === Phase 4: 博弈论一致性规则 ===
            
            belief_strategy_issue = self._check_belief_strategy_mismatch(state)
            if belief_strategy_issue:
                issues.append(belief_strategy_issue)
            
            threat_ignore_issue = self._check_threat_ignore_high_credibility(state)
            if threat_ignore_issue:
                issues.append(threat_ignore_issue)
            
            low_entropy_issue = self._check_low_entropy_high_uncertainty(state)
            if low_entropy_issue:
                issues.append(low_entropy_issue)
            
            ic_issue = self._check_incentive_incompatible_behavior(state)
            if ic_issue:
                issues.append(ic_issue)
            
            return issues[:self.MAX_CONSISTENCY_ISSUES]
        finally:
            self._checking_consistency = False
    
    def get_health_status(self) -> Dict[str, SubsystemHealthStatus]:
        """
        获取各子系统的健康状态
        
        Returns:
            {subsystem_name: SubsystemHealthStatus} 字典
        """
        status_map: Dict[str, SubsystemHealthStatus] = {}
        
        subsystems = {
            "jungian": self._jungian,
            "existential": self._existential,
            "narrative": self._narrative,
            "social": self._social,
            "memory": self._memory,
            "motivation": self._motivation,
            # === Phase 4: 博弈论子系统 ===
            "belief_system": self._belief_system,
            "threat_engine": self._threat_engine,
            "strategy_engine": self._strategy_engine,
        }
        
        for name, inst in subsystems.items():
            is_healthy = inst is not None
            issues: List[str] = [] if is_healthy else ["未初始化"]
            status_map[name] = SubsystemHealthStatus(
                subsystem_name=name,
                is_healthy=is_healthy,
                issues=issues,
            )
        
        return status_map
    
    # ================================================================
    # Phase 4: 博弈论一致性检查方法
    # ================================================================
    
    @staticmethod
    def _check_belief_strategy_mismatch(
        state: DeepCharacterState,
    ) -> Optional[ConsistencyIssue]:
        """
        规则1: BELIEF_STRATEGY_MISMATCH
        高合作信念 + DEFECT主导策略 → WARNING
        
        当角色相信对方会合作(>0.6), 但自身策略选择背叛为主时,
        可能是策略计算错误或内部矛盾。
        """
        beliefs = getattr(state, 'primary_target_beliefs', {})
        strategy = getattr(state, 'current_strategy', None)
        
        if not beliefs or not strategy:
            return None
        
        belief_val = max(beliefs.values()) if beliefs else 0.5
        dominant_action = strategy.get("dominant_action", "")
        coop_prob = strategy.get("cooperate_probability", 0.5)
        
        if belief_val > 0.6 and dominant_action == "DEFECT" and coop_prob < 0.3:
            return ConsistencyIssue(
                issue_type=ConsistencyIssueType.SOCIAL_PERSONALITY_CONFLICT,
                severity=ConsistencySeverity.WARNING,
                message=(
                    f"高合作信念({belief_val:.2f})与背叛主导策略"
                    f"(coop={coop_prob:.2f})不匹配"
                ),
                suggestion="检查混合策略输入或信念系统数据",
                subsystems_involved=["belief_system", "strategy_engine"],
            )
        
        return None
    
    @staticmethod
    def _check_threat_ignore_high_credibility(
        state: DeepCharacterState,
    ) -> Optional[ConsistencyIssue]:
        """
        规则2: THREAT_IGNORE_HIGH_CREDIBILITY
        高可信威胁 + 无应对策略/低准备度 → ERROR
        
        当威胁引擎判定某实体威胁高度可信(>0.7),
        但角色的威胁响应准备度很低(<0.3)时, 存在安全风险。
        """
        readiness = getattr(state, 'threat_response_readiness', 0.5)
        threats = getattr(state, 'active_threats', [])
        strategy = getattr(state, 'current_strategy', None)
        
        has_high_cred = any(
            t.get("credibility_score", 0) > 0.7 for t in threats
        )
        
        if has_high_cred and readiness < 0.3:
            dominant = strategy.get("dominant_action", "") if strategy else ""
            is_passive = dominant in ("OBSERVE", "WITHDRAW")
            
            severity = ConsistencySeverity.ERROR if is_passive else ConsistencySeverity.WARNING
            
            return ConsistencyIssue(
                issue_type=ConsistencyIssueType.EXISTENTIAL_CHOICE_CONTRADICTION,
                severity=severity,
                message=(
                    f"高可信威胁存在但响应准备度极低({readiness:.2f}), "
                    f"当前策略:{dominant or '未生成'}"
                ),
                suggestion="提升威胁应对准备度或调整策略",
                subsystems_involved=["threat_engine", "strategy_engine"],
            )
        
        return None
    
    @staticmethod
    def _check_low_entropy_high_uncertainty(
        state: DeepCharacterState,
    ) -> Optional[ConsistencyIssue]:
        """
        规则3: LOW_ENTROPY_HIGH_UNCERTAINTY
        低置信信念 + 确定性策略 → INFO
        
        当对目标的信念置信度很低(<0.4), 但混合策略的熵也很低(<0.5),
        说明策略过于确定而信息不足。
        """
        beliefs = getattr(state, 'primary_target_beliefs', {})
        strategy = getattr(state, 'current_strategy', None)
        
        if not beliefs or not strategy:
            return None
        
        belief_val = max(beliefs.values()) if beliefs else 0.5
        uncertainty = 1.0 - abs(belief_val - 0.5) * 2
        entropy = strategy.get("entropy", 1.0)
        
        if uncertainty > 0.6 and entropy < 0.5:
            return ConsistencyIssue(
                issue_type=ConsistencyIssueType.MEMORY_MOTIVATION_CONTRADICTION,
                severity=ConsistencySeverity.INFO,
                message=(
                    f"高不确定性信念({uncertainty:.2f})配合低熵策略"
                    f"(H={entropy:.2f}), 可能过度自信"
                ),
                suggestion="提高策略温度或收集更多观测数据",
                subsystems_involved=["belief_system", "strategy_engine"],
            )
        
        return None
    
    @staticmethod
    def _check_incentive_incompatible_behavior(
        state: DeepCharacterState,
    ) -> Optional[ConsistencyIssue]:
        """
        规则4: INCENTIVE_INCOMPATIBLE_BEHAVIOR
        当前策略偏离机制激励方向 → WARNING
        
        简化检测: 如果合作概率很低(<0.25)但信任度很高(>0.65),
        则可能存在激励不相容。
        """
        trust = getattr(state, 'trust_level_current', 0.5)
        strategy = getattr(state, 'current_strategy', None)
        
        if not strategy:
            return None
        
        coop_prob = strategy.get("cooperate_probability", 0.5)
        
        if trust > 0.65 and coop_prob < 0.25:
            return ConsistencyIssue(
                issue_type=ConsistencyIssueType.NARRATIVE_BEHAVIOR_MISMATCH,
                severity=ConsistencySeverity.WARNING,
                message=(
                    f"高信任环境(trust={trust:.2f})下选择低合作策略"
                    f"(coop={coop_prob:.2f}), 可能偏离激励方向"
                ),
                suggestion="验证机制参数或策略生成逻辑",
                subsystems_involved=["social", "strategy_engine"],
            )
        
        return None
    
    # ================================================================
    # 持久化支持
    # ================================================================
    
    def serialize(self) -> Dict[str, Any]:
        """
        序列化整个DeepCharacter状态 (用于存档)
        
        Returns:
            包含所有子系统状态的嵌套字典
        """
        state = self.get_state_snapshot(force_refresh=True)
        base = state.to_dict()
        
        base["config"] = dict(self._config)
        base["name"] = self._name
        base["operation_count"] = self._operation_count
        base["recent_events"] = [
            {"type": et, "intensity": ei, "timestamp": ts}
            for et, ei, ts in self._recent_events[-20:]
        ]
        
        return base
    
    @classmethod
    def deserialize(
        cls,
        data: Dict[str, Any],
        character_id: EntityId,
        name: str = "",
    ) -> "DeepCharacter":
        """
        从序列化数据恢复DeepCharacter (工厂方法)
        
        Args:
            data: serialize()输出的字典
            character_id: 角色ID
            name: 角色名称
            
        Returns:
            恢复的DeepCharacter实例
        """
        dc = cls(
            character_id=character_id,
            name=name or data.get("name", ""),
            config=data.get("config"),
        )
        
        dc._operation_count = data.get("operation_count", 0)
        
        events_data = data.get("recent_events", [])
        for ed in events_data:
            dc._recent_events.append((
                ed.get("type", ""),
                ed.get("intensity", 0.5),
                ed.get("timestamp", 0.0),
            ))
        
        return dc
