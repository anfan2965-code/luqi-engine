"""
叙事身份模型 — 基于保罗·利科(Paul Ricoeur)的叙事身份理论
处理角色的"人生故事"建模：人通过讲述自己的故事来构建身份认同。

核心概念:
- 叙事身份(Narrative Identity): 身份不是静态存在,而是通过故事构成的
- 配置(Mimesis III): 读者/听众对叙事的主动接受
- 核心叙事(CoreNarrative): 回答"我是谁,我从哪里来,我要到哪里去"

解决的游戏设计问题:
1. 为什么角色需要有背景故事? → 身份一致性基础
2. 为什么角色会对某些事件有强烈反应? → defining_moments的触发
3. 如何让角色有成长弧线? → LifeChapter的演进
4. 如何让角色行为有深度? → central_conflict驱动的内在矛盾
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional


# ============================================================
# 常量定义
# ============================================================

_SIGNIFICANCE_MIN: float = 0.0
_SIGNIFICANCE_MAX: float = 1.0
_EPISODE_LIMIT: int = 100
_RECENT_EPISODE_COUNT: int = 3
_SUMMARY_MAX_LENGTH: int = 500
_TRUNCATION_SUFFIX: str = "..."


def _clamp(value: float, low: float, high: float) -> float:
    """数值范围约束"""
    return max(low, min(high, value))


# ============================================================
# 枚举定义
# ============================================================

class LifeChapter(Enum):
    """
    人生阶段 — 角色的人生故事章节
    
    设计原则:
    - 每个阶段代表身份形成的一个关键时期
    - 阶段转换可以触发性格变化
    - 支持角色成长弧线的表达
    """
    ORIGIN = auto()           # 起源 — 背景故事/出身
    TRIALS = auto()           # 试炼 — 经历的挑战/困难
    TRANSFORMATION = auto()   # 转变 — 关键转折点
    MATURITY = auto()         # 成熟 — 当前状态/稳定期
    LEGACY = auto()           # 传承 — 对未来的影响/目标


# ============================================================
# 数据类型定义
# ============================================================

@dataclass
class NarrativeEpisode:
    """
    叙事片段 — 构成身份的基本单位
    
    每个NarrativeEpisode代表角色人生中的一个重要事件或时期,
    这些片段共同构成了角色的核心叙事。
    
    Attributes:
        episode_id: 唯一标识符
        title: 事件标题(简短描述)
        description: 详细描述
        chapter: 所属人生阶段
        timestamp: 发生时间戳(-1表示未知/远古)
        significance: 对身份塑造的重要性 [0, 1]
        emotional_tags: 情感标签列表
        learned_lesson: 从中学到的教训/感悟(可选)
        
    设计约束:
        - significance使用__post_init__确保范围合法
        - to_narrative_prompt()提供LLM友好的文本输出
        - 支持空值创建(用于测试或占位)
    """
    
    SIGNIFICANCE_RANGE: ClassVar[tuple] = (_SIGNIFICANCE_MIN, _SIGNIFICANCE_MAX)
    
    episode_id: str = ""
    title: str = ""
    description: str = ""
    chapter: LifeChapter = LifeChapter.ORIGIN
    timestamp: float = -1.0
    significance: float = 0.5
    emotional_tags: List[str] = field(default_factory=list)
    learned_lesson: Optional[str] = None
    
    def __post_init__(self):
        self.significance = _clamp(
            self.significance, *self.SIGNIFICANCE_RANGE
        )
    
    def to_narrative_prompt(self) -> str:
        """
        转换为叙事prompt片段
        
        输出格式:
        "[title]: description (情感: tag1, tag2)"
        
        Returns:
            格式化的字符串,适合注入LLM prompt
        """
        if not self.title and not self.description:
            return ""
        
        parts: List[str] = []
        
        if self.title:
            parts.append(f"[{self.title}]")
        
        if self.description:
            parts.append(self.description)
        
        if self.emotional_tags:
            tags_str = "、".join(self.emotional_tags[:3])
            parts.append(f"(情感: {tags_str})")
        
        result = " ".join(parts)
        
        if self.learned_lesson:
            result += f" — {self.learned_lesson}"
        
        return result
    
    @property
    def is_defining_moment(self) -> bool:
        """判断是否为决定性时刻(significance > 0.7)"""
        return self.significance > 0.7


@dataclass
class CoreNarrative:
    """
    核心叙事 — 角色的"人生故事线"
    
    这是区别于PAD/OCEAN的更高层次的身份描述。
    CoreNarrative回答三个根本问题:
    1. 我是谁? (origin_story + core_values)
    2. 我从哪里来? (defining_moments的历史序列)
    3. 我要到哪里去? (unfulfilled_destiny + fear_of_becoming)
    
    设计原则:
    - 所有字段都有合理默认值 → 支持渐进式构建
    - get_identity_summary()提供结构化的身份摘要
    - 支持与existential_model.py的central_conflict联动
    
    使用示例:
        >>> narrative = CoreNarrative(
        ...     origin_story="出生于贵族家庭,幼年目睹战争",
        ...     central_conflict="渴望和平vs家族责任",
        ...     unfulfilled_destiny="建立没有战争的世界",
        ... )
        >>> narrative.add_episode(NarrativeEpisode(
        ...     episode_id="battle_001",
        ...     title="初次战斗",
        ...     description="第一次上战场",
        ...     chapter=LifeChapter.TRIALS,
        ...     significance=0.8,
        ... ))
        >>> print(narrative.get_identity_summary())
    """
    
    origin_story: str = ""                    # 起源故事(背景)
    central_conflict: str = ""                 # 内心矛盾(核心冲突)
    unfulfilled_destiny: str = ""             # 未完成的命运(梦想/追求)
    fear_of_becoming: str = ""                # 对成为某种人的恐惧(最深恐惧)
    
    core_values: List[str] = field(default_factory=list)  # 核心价值观
    defining_moments: List[NarrativeEpisode] = field(default_factory=list)  # 决定性时刻
    
    current_chapter: LifeChapter = LifeChapter.MATURITY  # 当前所处阶段
    
    _episode_limit: ClassVar[int] = _EPISODE_LIMIT
    _recent_count: ClassVar[int] = _RECENT_EPISODE_COUNT
    
    def add_episode(self, episode: NarrativeEpisode) -> None:
        """
        添加一个叙事片段
        
        自动维护:
        - 数量限制(最多_EPISODE_LIMIT条)
        - 按时间戳排序(最新的在后面)
        
        Args:
            episode: 要添加的NarrativeEpisode实例
        """
        if not isinstance(episode, NarrativeEpisode):
            raise TypeError(f"期望NarrativeEpisode,得到{type(episode).__name__}")
        
        self.defining_moments.append(episode)
        
        if len(self.defining_moments) > self._episode_limit:
            self.defining_moments.pop(0)
        
        self.defining_moments.sort(key=lambda e: e.timestamp)
    
    def remove_episode(self, episode_id: str) -> Optional[NarrativeEpisode]:
        """
        移除指定ID的叙事片段
        
        Args:
            episode_id: 要移除的episode ID
            
        Returns:
            被移除的NarrativeEpisode,如果不存在则返回None
        """
        for i, ep in enumerate(self.defining_moments):
            if ep.episode_id == episode_id:
                return self.defining_moments.pop(i)
        return None
    
    def get_recent_episodes(self, count: Optional[int] = None) -> List[NarrativeEpisode]:
        """
        获取最近的叙事片段
        
        Args:
            count: 返回数量,None则使用默认值(_RECENT_EPISODE_COUNT)
            
        Returns:
            按时间排序的最近N个NarrativeEpisode列表
        """
        if count is None:
            count = self._recent_count
        
        sorted_episodes = sorted(
            self.defining_moments, key=lambda e: e.timestamp, reverse=True
        )
        return sorted_episodes[:count]
    
    def get_defining_moments(self) -> List[NarrativeEpisode]:
        """
        获取所有决定性时刻(significance > 0.7)
        
        Returns:
            按重要性降序排列的决定性时刻列表
        """
        defining = [ep for ep in self.defining_moments if ep.is_defining_moment]
        return sorted(defining, key=lambda e: e.significance, reverse=True)
    
    def get_identity_summary(self) -> str:
        """
        生成身份摘要（注入prompt）
        
        输出格式（按优先级排列）:
        1. 背景(origin_story)
        2. 内心矛盾(central_conflict)
        3. 梦想/追求(unfulfilled_destiny)
        4. 最深恐惧(fear_of_becoming)
        5. 最近重要经历(defining_moments最近3条)
        
        Returns:
            结构化的身份摘要字符串,
            空数据时返回空字符串
            
        设计约束:
        - 最大长度限制(_SUMMARY_MAX_LENGTH)防止token溢出
        - 各部分用换行符分隔,便于LLM解析
        - 空字段自动跳过
        """
        parts: List[str] = []
        
        # 1. 背景故事(最高优先级)
        if self.origin_story:
            parts.append(f"背景：{self.origin_story}")
        
        # 2. 内心矛盾
        if self.central_conflict:
            parts.append(f"内心矛盾：{self.central_conflict}")
        
        # 3. 梦想/追求
        if self.unfulfilled_destiny:
            parts.append(f"追求：{self.unfulfilled_destiny}")
        
        # 4. 最深恐惧
        if self.fear_of_becoming:
            parts.append(f"最深恐惧：{self.fear_of_becoming}")
        
        # 5. 最近重要经历(取最近_RECENT_EPISODE_COUNT条)
        recent = self.get_recent_episodes()
        if recent:
            ep_summaries = [ep.to_narrative_prompt() for ep in recent if ep.to_narrative_prompt()]
            if ep_summaries:
                parts.append(f"近期经历：{'；'.join(ep_summaries)}")
        
        if not parts:
            return ""
        
        result = "\n".join(parts)
        
        if len(result) > _SUMMARY_MAX_LENGTH:
            result = result[:_SUMMARY_MAX_LENGTH - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX
        
        return result
    
    def to_narrative_context(self) -> Dict[str, Any]:
        """
        导出为结构化字典(用于持久化或API返回)
        
        Returns:
            包含所有核心叙事数据的字典
        """
        return {
            "origin_story": self.origin_story,
            "central_conflict": self.central_conflict,
            "unfulfilled_destiny": self.unfulfilled_destiny,
            "fear_of_becoming": self.fear_of_becoming,
            "core_values": list(self.core_values),
            "current_chapter": self.current_chapter.name,
            "episode_count": len(self.defining_moments),
            "defining_moment_count": len(self.get_defining_moments()),
            "recent_episodes": [
                {
                    "id": ep.episode_id,
                    "title": ep.title,
                    "significance": ep.significance,
                    "chapter": ep.chapter.name,
                }
                for ep in self.get_recent_episodes()
            ],
        }
    
    @property
    def is_empty(self) -> bool:
        """判断是否为空叙事(无任何内容)"""
        return (
            not self.origin_story and
            not self.central_conflict and
            not self.unfulfilled_destiny and
            not self.fear_of_becoming and
            not self.defining_moments
        )
    
    @property
    def narrative_complexity(self) -> float:
        """
        计算叙事复杂度评分 [0, 1]
        
        基于:
        - 定义性时刻的数量和重要性
        - 核心叙事字段的填充程度
        - 人生阶段的多样性
        
        Returns:
            复杂度评分,越高表示角色背景越丰富
        """
        if self.is_empty:
            return 0.0
        
        score: float = 0.0
        
        filled_fields = sum([
            bool(self.origin_story),
            bool(self.central_conflict),
            bool(self.unfulfilled_destiny),
            bool(self.fear_of_becoming),
        ])
        score += (filled_fields / 4.0) * 0.3
        
        if self.defining_moments:
            total_significance = sum(ep.significance for ep in self.defining_moments)
            avg_significance = total_significance / len(self.defining_moments)
            episode_factor = min(len(self.defining_moments) / 10.0, 1.0)
            score += (avg_significance * episode_factor) * 0.5
        
        chapters_represented = len(set(ep.chapter for ep in self.defining_moments))
        diversity_factor = min(chapters_represented / len(LifeChapter), 1.0)
        score += diversity_factor * 0.2
        
        return _clamp(score, _SIGNIFICANCE_MIN, _SIGNIFICANCE_MAX)


class NarrativeIdentity:
    """
    叙事身份聚合器 — DeepCharacter的叙事子系统接口
    
    封装CoreNarrative和LifeChapter，提供统一的叙事状态访问。
    
    Attributes:
        character_id: 角色ID
        core_narrative: 核心叙事对象
        current_phase: 当前人生阶段
    """
    
    def __init__(self, character_id: str = "") -> None:
        self.character_id = character_id
        self.core_narrative = CoreNarrative()
        self.current_phase: LifeChapter = LifeChapter.ORIGIN
    
    @property  
    def current_phase_name(self) -> str:
        return self.current_phase.name if self.current_phase else ""
    
    def get_core_summary(self) -> str:
        """获取核心叙事摘要"""
        return self.core_narrative.get_identity_summary()
    
    def get_defining_moments(self) -> List[NarrativeEpisode]:
        """获取决定性时刻列表"""
        return self.core_narrative.get_defining_moments()
    
    def add_episode(self, episode: NarrativeEpisode) -> None:
        """添加叙事片段"""
        self.core_narrative.add_episode(episode)
    
    def advance_to_phase(self, phase: LifeChapter) -> None:
        """推进到指定人生阶段"""
        self.current_phase = phase
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "current_phase": self.current_phase.name if self.current_phase else "",
            "core_narrative": self.core_narrative.to_dict() if hasattr(self.core_narrative, 'to_dict') else {},
        }
