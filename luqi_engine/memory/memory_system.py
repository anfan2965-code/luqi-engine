"""
记忆管理系统 — 信息论驱动的记忆重要性 + 艾宾浩斯遗忘曲线
基于认知科学和信息论,构建角色记忆的存储、检索、衰减和清理机制。

核心创新:
- 信息论重要性计算 (Shannon信息量 + 情绪增强)
- 改进艾宾浩斯遗忘曲线 (含复习增强效应)
- 闪光灯记忆特殊处理 (重大事件衰减减半)
- 智能容量管理 (自动清理低重要性记忆)

解决的游戏设计问题:
1. 为什么角色会"忘记"重要事件? → 艾宾浩斯衰减模拟真实遗忘
2. 如何判断哪些记忆更重要? → 信息论公式 (熵+新颖性+情感强度)
3. 如何避免记忆无限膨胀? → 阈值自动清理机制
4. 如何让记忆影响行为? → 相关性排序+上下文prompt注入

学术基础:
- Ebbinghaus (1885): 遗忘曲线 R = e^(-t/S)
- Tulving (1972): 情景/语义/程序性记忆分类
- Anderson & Schooler (1991): 记忆的信息论模型
- Brown & Kulik (1977): 闪光灯记忆 (Flashbulb memories)
"""

from __future__ import annotations

import hashlib
import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId


# ============================================================
# 常量定义（模块私有，前缀_）
# ============================================================

_FORGETTING_THRESHOLD: float = 0.05       # 遗忘阈值
_SECONDS_PER_DAY: float = 86400.0         # 一天的秒数
_TRUNCATION_SUFFIX: str = "..."           # 截断后缀

_MAX_MEMORIES_PER_CHARACTER: int = 1000   # 最大记忆条目数
_AUTO_CLEANUP_THRESHOLD: float = 0.9      # 自动清理触发比例 (90%)
_DECAY_INTERVAL_SECONDS: float = 3600.0   # 衰减检查间隔 (小时)
_CLEANUP_PERCENTAGE: float = 0.1          # 每次清理比例 (10%)

_IMPORTANCE_WEIGHT_INFO: float = 0.25     # 信息量权重
_IMPORTANCE_WEIGHT_EMOTION: float = 0.25  # 情绪权重
_IMPORTANCE_WEIGHT_RECENCY: float = 0.20  # 近期性权重
_IMPORTANCE_WEIGHT_FREQUENCY: float = 0.15# 频率权重
_IMPORTANCE_WEIGHT_NOVELTY: float = 0.15  # 新颖性权重

_RECENCY_HALF_LIFE_DAYS: float = 7.0      # 近期性半衰期 (天)
_NOVELTY_DECAY_RATE: float = 0.01         # 新颖性衰减率

_FLASHBULB_BONUS_FACTOR: float = 1.5      # 闪光灯记忆加成
_STRONG_EMOTION_BOOST: float = 0.3        # 强情绪增强系数
_REVIEW_ENHANCEMENT_COEFF: float = 0.1    # 复习增强系数
_REVIEW_ENHANCEMENT_CAP: float = 2.0       # 复习增强上限

_DECAY_RATE_FLASHBULB: float = 0.03       # 闪光灯记忆衰减率
_DECAY_RATE_EPISODIC: float = 0.08        # 情景记忆衰减率
_DECAY_RATE_SEMANTIC: float = 0.05        # 语义记忆衰减率
_DECAY_RATE_PROCEDURAL: float = 0.02      # 程序性记忆衰减率

_CONFLICT_DETECTION_THRESHOLD: float = 0.5 # 冲突检测阈值
_SURVIVAL_BOOST_FACTOR: float = 1.5       # 生存本能放大系数
_META_NEED_SUPPRESSION: float = 0.3       # 高层需求抑制系数
_PRIORITY_ADJUSTMENT_CAP: float = 0.3     # 单次优先级调整上限

_CONTENT_LENGTH_NORM: float = 200.0       # 内容长度归一化基准
_ENTITY_COUNT_NORM: float = 5.0           # 实体数量归一化基准
_KEYWORD_MATCH_WEIGHT_TAG: float = 2.0    # 标签匹配权重
_KEYWORD_MATCH_WEIGHT_CONTENT: float = 1.0 # 内容匹配权重
_KEYWORD_MATCH_WEIGHT_ENTITY: float = 1.5 # 实体匹配权重


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

class MemoryType(Enum):
    """
    记忆类型分类 — 基于Tulving (1972)的记忆系统理论
    
    类型说明:
    - EPISODIC: 情景记忆 (个人经历的事件,有时间地点)
    - SEMANTIC: 语义记忆 (事实/概念/知识,无时间标记)
    - PROCEDURAL: 程序性记忆 (技能/习惯,如骑自行车)
    - FLASHBULB: 闪光灯记忆 (高情绪唤醒的重大事件,如9/11)
    
    学术来源:
    - Tulving, E. (1972). Episodic and semantic memory.
    - Brown, R., & Kulik, J. (1977). Flashbulb memories.
    """
    EPISODIC = auto()       # 情景记忆
    SEMANTIC = auto()       # 语义记忆
    PROCEDURAL = auto()     # 程序性记忆
    FLASHBULB = auto()      # 闪光灯记忆


class MemoryEmotion(Enum):
    """
    情绪类型分类 — 基于Ekman基本情绪理论
    
    扩展了Ekman的6种基本情绪,增加NEUTRAL(中性)
    
    学术来源:
    - Ekman, P. (1992). An argument for basic emotions.
    """
    JOY = auto()            # 喜悦
    SADNESS = auto()        # 悲伤
    ANGER = auto()          # 愤怒
    FEAR = auto()           # 恐惧
    SURPRISE = auto()       # 惊讶
    DISGUST = auto()        # 厌恶
    NEUTRAL = auto()        # 中性


# ============================================================
# 数据类型定义
# ============================================================

@dataclass
class MemoryEpisode:
    """
    记忆片段 — 构成角色记忆的基本单位
    
    设计原则 (来自认知科学):
    - 每条记忆包含: 内容、时间戳、情绪标签、重要性分数、访问频率
    - 重要性不是静态的，随时间和访问动态变化
    - 支持四种记忆类型: 情景/语义/程序性/闪光灯
    
    使用示例:
        >>> ep = MemoryEpisode(
        ...     content="在玫瑰酒馆遇到了神秘的旅人",
        ...     memory_type=MemoryType.EPISODIC,
        ...     emotions=[MemoryEmotion.SURPRISE],
        ... )
        >>> print(ep.current_importance)
        
    学术依据:
    - Tulving (1972): Episodic vs Semantic memory distinction
    - Brown & Kulik (1977): Flashbulb memories (高情绪唤醒)
    - Conway & Pleydell-Pearce (2000): Self-Memory System
    """
    
    INTENSITY_MIN: ClassVar[float] = 0.0
    INTENSITY_MAX: ClassVar[float] = 1.0
    IMPORTANCE_MIN: ClassVar[float] = 0.0
    IMPORTANCE_MAX: ClassVar[float] = 1.0
    
    episode_id: str = ""
    content: str = ""
    memory_type: MemoryType = MemoryType.EPISODIC
    
    timestamp: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    
    emotions: List[MemoryEmotion] = field(default_factory=list)
    emotional_intensity: float = 0.5
    
    base_importance: float = 0.5
    current_importance: float = 0.5
    
    associated_entities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    source_context: str = ""
    
    def __post_init__(self):
        """初始化时钳制所有数值字段并设置时间戳"""
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.last_accessed:
            self.last_accessed = self.timestamp
        if not self.episode_id:
            self.episode_id = self._generate_episode_id()
            
        self.emotional_intensity = _clamp(
            self.emotional_intensity,
            self.INTENSITY_MIN,
            self.INTENSITY_MAX,
        )
        self.base_importance = _clamp(
            self.base_importance,
            self.IMPORTANCE_MIN,
            self.IMPORTANCE_MAX,
        )
        if self.current_importance == 0.5 and self.base_importance != 0.5:
            self.current_importance = self.base_importance
        else:
            self.current_importance = _clamp(
                self.current_importance,
                self.IMPORTANCE_MIN,
                self.IMPORTANCE_MAX,
            )
    
    def access(self) -> None:
        """
        访问此记忆 (更新访问统计)
        
        效果:
        - last_accessed 更新为当前时间
        - access_count += 1
        """
        self.last_accessed = time.time()
        self.access_count += 1
    
    def to_prompt_fragment(self, max_length: int = 100) -> str:
        """
        转换为适合注入prompt的文本片段
        
        格式: "[{tags}] {content}" (如果超长则截断)
        
        Args:
            max_length: 最大字符长度
            
        Returns:
            格式化的记忆文本
        """
        if not self.content:
            return ""
            
        result = self.content
        
        if self.tags:
            tags_str = ", ".join(self.tags[:3])
            result = f"[{tags_str}] {result}"
            
        if len(result) > max_length:
            result = result[:max_length - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX
            
        return result
    
    @property
    def is_forgotten(self) -> bool:
        """判断是否已被遗忘 (current_importance < threshold)"""
        return self.current_importance < _FORGETTING_THRESHOLD
    
    @property
    def age_days(self) -> float:
        """记忆年龄 (天数)"""
        return (time.time() - self.timestamp) / _SECONDS_PER_DAY
    
    def _generate_episode_id(self) -> str:
        """生成唯一的episode_id (基于内容hash + 时间戳)"""
        raw = f"{self.content}{time.time()}{uuid.uuid4()}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]


@dataclass
class MemoryRetrievalResult:
    """
    记忆检索结果包装
    
    包含检索到的记忆列表和对应的相关性分数,
    以及原始查询信息。
    """
    
    episodes: List[Tuple[MemoryEpisode, float]] = field(default_factory=list)
    query_keywords: Optional[List[str]] = None
    total_searched: int = 0
    retrieval_time_ms: float = 0.0
    
    @property
    def count(self) -> int:
        """返回结果数量"""
        return len(self.episodes)
    
    def get_top_episodes(self, n: int = 5) -> List[Tuple[MemoryEpisode, float]]:
        """获取相关性最高的top-N结果"""
        sorted_results = sorted(
            self.episodes,
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_results[:n]


class MemoryImportanceCalculator:
    """
    记忆重要性计算器 (静态工具类)
    
    基于信息论和认知科学的混合模型:
    
    公式:
    importance = W_info × I_information
                + W_emotion × I_emotional
                + W_recency × I_recency
                + W_frequency × I_frequency
                + W_novelty × I_novelty
                
    其中:
    - I_information: 信息量 (基于内容长度和实体数量)
    - I_emotional: 情绪增强因子 (高强度情绪提升重要性)
    - I_recency: 近期性因子 (新记忆更重要)
    - I_frequency: 频率因子 (频繁回忆的记忆重要)
    - I_novelty: 新颖性因子 (罕见事件更难忘)
    
    权重配置 (可调优):
    W_info = 0.25, W_emotion = 0.25, W_recency = 0.20
    W_frequency = 0.15, W_novelty = 0.15
    
    学术依据:
    - Anderson & Schooler (1991): Information theory of memory
    - Rubin et al. (2004): Emotion and memory consolidation
    """
    
    WEIGHT_INFORMATION: ClassVar[float] = _IMPORTANCE_WEIGHT_INFO
    WEIGHT_EMOTIONAL: ClassVar[float] = _IMPORTANCE_WEIGHT_EMOTION
    WEIGHT_RECENCY: ClassVar[float] = _IMPORTANCE_WEIGHT_RECENCY
    WEIGHT_FREQUENCY: ClassVar[float] = _IMPORTANCE_WEIGHT_FREQUENCY
    WEIGHT_NOVELTY: ClassVar[float] = _IMPORTANCE_WEIGHT_NOVELTY
    
    RECENCY_HALF_LIFE_DAYS: ClassVar[float] = _RECENCY_HALF_LIFE_DAYS
    NOVELTY_DECAY_RATE: ClassVar[float] = _NOVELTY_DECAY_RATE
    
    @classmethod
    def compute_base_importance(
        cls,
        content: str,
        emotions: List[MemoryEmotion],
        emotional_intensity: float,
        entity_count: int,
        is_flashbulb: bool = False,
    ) -> float:
        """
        计算初始重要性 (创建记忆时调用一次)
        
        Args:
            content: 记忆内容文本
            emotions: 情绪标签列表
            emotional_intensity: 情绪强度 [0, 1]
            entity_count: 涉及实体数量
            is_flashbulb: 是否为闪光灯记忆 (重大事件)
            
        Returns:
            重要性分数 [0, 1]
            
        算法细节:
        1. I_information = min(content_len / 200, 1.0) * 0.6 + min(entity_count / 5, 1.0) * 0.4
        2. I_emotional = emotional_intensity × (1 + 0.3 × len(strong_emotions))
        3. 如果is_flashbulb: importance *= 1.5 (闪光灯记忆加成)
        4. 最终结果 clamp 到 [0, 1]
        """
        content_len_factor = min(len(content) / _CONTENT_LENGTH_NORM, 1.0)
        entity_factor = min(entity_count / _ENTITY_COUNT_NORM, 1.0)
        
        i_information = content_len_factor * 0.6 + entity_factor * 0.4
        
        strong_emotions = [
            em for em in emotions
            if em not in (MemoryEmotion.NEUTRAL,)
        ]
        i_emotional = emotional_intensity * (
            1.0 + _STRONG_EMOTION_BOOST * len(strong_emotions)
        )
        
        importance = (
            cls.WEIGHT_INFORMATION * i_information +
            cls.WEIGHT_EMOTIONAL * i_emotional
        )
        
        if is_flashbulb:
            importance *= _FLASHBULB_BONUS_FACTOR
            
        return _clamp(importance, 0.0, 1.0)
    
    @classmethod
    def update_importance_with_decay(
        cls,
        base_importance: float,
        age_days: float,
        access_count: int,
        days_since_last_access: float,
        memory_type: MemoryType = MemoryType.EPISODIC,
    ) -> float:
        """
        应用衰减后的当前重要性 (定期调用或查询时调用)
        
        基于改进的艾宾浩斯遗忘曲线:
        
        R(t) = base_importance × e^(-λt) × (1 + α × log(1 + access_count))
        
        其中:
        - t: 记忆年龄 (天)
        - λ: 衰减系数 (默认 0.1, 可根据记忆类型调整)
        - α: 复习增强系数 (默认 0.1)
        - access_count: 累计访问次数
        
        特殊处理:
        - FLASHBULB记忆: λ 减半 (衰减更慢)
        - 最近24小时内访问: 临时boost 20%
        
        Args:
            base_importance: 初始重要性
            age_days: 记忆年龄 (天)
            access_count: 累计访问次数
            days_since_last_access: 距上次访问天数
            memory_type: 记忆类型 (影响衰减速度)
            
        Returns:
            衰减后的当前重要性 [0, 1]
        """
        decay_rates = {
            MemoryType.FLASHBULB: _DECAY_RATE_FLASHBULB,
            MemoryType.EPISODIC: _DECAY_RATE_EPISODIC,
            MemoryType.SEMANTIC: _DECAY_RATE_SEMANTIC,
            MemoryType.PROCEDURAL: _DECAY_RATE_PROCEDURAL,
        }
        
        lambda_rate = decay_rates.get(memory_type, _DECAY_RATE_EPISODIC)
        
        base_retention = math.exp(-lambda_rate * age_days)
        
        review_boost = 1.0 + _REVIEW_ENHANCEMENT_COEFF * math.log(1 + access_count)
        review_boost = min(review_boost, _REVIEW_ENHANCEMENT_CAP)
        
        recent_boost = 1.0
        if days_since_last_access < 1.0:
            recent_boost = 1.2
        
        current_importance = (
            base_importance *
            base_retention *
            review_boost *
            recent_boost
        )
        
        return _clamp(current_importance, 0.0, 1.0)
    
    @classmethod
    def compute_relevance_score(
        cls,
        query_keywords: List[str],
        episode: MemoryEpisode,
    ) -> float:
        """
        计算查询相关性分数 (用于记忆检索排序)
        
        算法: TF-IDF简化版
        1. 分词 query 和 episode.content
        2. 计算词重叠度 (Jaccard similarity)
        3. 加权: 标签匹配 × 2.0, 内容匹配 × 1.0, 实体匹配 × 1.5
        4. 乘以 current_importance 作为最终相关性
        
        Args:
            query_keywords: 查询关键词列表
            episode: 目标记忆片段
            
        Returns:
            相关性分数 [0, 1]
        """
        if not query_keywords or not episode.content:
            return episode.current_importance * 0.1
        
        content_lower = episode.content.lower()
        tag_lower = [tag.lower() for tag in episode.tags]
        entity_lower = [e.lower() for e in episode.associated_entities]
        
        tag_score = 0.0
        content_score = 0.0
        entity_score = 0.0
        
        for keyword in query_keywords:
            kw_lower = keyword.lower()
            
            for tag in tag_lower:
                if kw_lower in tag:
                    tag_score += _KEYWORD_MATCH_WEIGHT_TAG
                    
            if kw_lower in content_lower:
                content_score += _KEYWORD_MATCH_WEIGHT_CONTENT
                
            for entity in entity_lower:
                if kw_lower in entity:
                    entity_score += _KEYWORD_MATCH_WEIGHT_ENTITY
        
        max_possible = len(query_keywords) * (
            _KEYWORD_MATCH_WEIGHT_TAG +
            _KEYWORD_MATCH_WEIGHT_CONTENT +
            _KEYWORD_MATCH_WEIGHT_ENTITY
        )
        
        if max_possible == 0:
            return episode.current_importance * 0.1
            
        raw_relevance = (tag_score + content_score + entity_score) / max_possible
        final_score = raw_relevance * episode.current_importance
        
        return _clamp(final_score, 0.0, 1.0)


class MemorySystem:
    """
    记忆管理系统 (主类)
    
    功能:
    - 存储记忆 (store)
    - 检索记忆 (retrieve by query/context/entity)
    - 自然遗忘 (decay - 基于艾宾浩斯曲线)
    - 手动遗忘 (forget - 强制删除)
    - Prompt生成 (get_memories_for_prompt)
    
    设计约束:
    - 单例模式 (每个角色一个实例)
    - 最大容量限制 (MAX_MEMORIES_PER_CHARACTER)
    - 自动清理低重要性记忆 (当接近容量上限时)
    
    使用示例:
        >>> mem_sys = MemorySystem(character_id="alice")
        >>> mem_sys.store("遇到了神秘旅人", emotions=[MemoryEmotion.SURPRISE])
        >>> results = mem_sys.retrieve(query=["旅人"])
        >>> for ep, score in results.episodes:
        ...     print(f"{score:.2f}: {ep.to_prompt_fragment()}")
    """
    
    MAX_MEMORIES: ClassVar[int] = _MAX_MEMORIES_PER_CHARACTER
    AUTO_CLEANUP_THRESHOLD: ClassVar[float] = _AUTO_CLEANUP_THRESHOLD
    FORGETTING_THRESHOLD: ClassVar[float] = _FORGETTING_THRESHOLD
    DECAY_INTERVAL_SECONDS: ClassVar[float] = _DECAY_INTERVAL_SECONDS
    
    def __init__(self, character_id: EntityId) -> None:
        """
        初始化记忆系统
        
        Args:
            character_id: 所属角色ID
        """
        self._character_id = character_id
        self._memories: Dict[str, MemoryEpisode] = {}
        self._last_decay_time: float = time.time()
    
    @property
    def character_id(self) -> EntityId:
        """获取所属角色ID"""
        return self._character_id
    
    @property
    def memory_count(self) -> int:
        """获取当前记忆数量"""
        return len(self._memories)
    
    def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        emotions: Optional[List[MemoryEmotion]] = None,
        emotional_intensity: float = 0.5,
        associated_entities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        source_context: str = "",
        episode_id: Optional[str] = None,
    ) -> MemoryEpisode:
        """
        存储一条新记忆
        
        流程:
        1. 创建MemoryEpisode对象
        2. 通过compute_base_importance()计算初始重要性
        3. 存入_memories字典
        4. 检查是否需要自动清理
        5. 返回创建的episode
        
        Args:
            content: 记忆内容 (必填, 不能为空)
            memory_type: 记忆类型 (默认EPISODIC)
            emotions: 情绪标签列表 (默认空列表=NEUTRAL)
            emotional_intensity: 情绪强度 [0, 1], 默认0.5
            associated_entities: 相关实体ID列表
            tags: 自定义标签
            source_context: 来源场景描述
            episode_id: 自定义ID (None则自动生成)
            
        Returns:
            创建的MemoryEpisode对象
            
        Raises:
            ValueError: 当content为空字符串时
        """
        if not content or not content.strip():
            raise ValueError("content cannot be empty")
        
        emotions = emotions or []
        associated_entities = associated_entities or []
        tags = tags or []
        
        is_flashbulb = (memory_type == MemoryType.FLASHBULB)
        
        base_importance = MemoryImportanceCalculator.compute_base_importance(
            content=content,
            emotions=emotions,
            emotional_intensity=emotional_intensity,
            entity_count=len(associated_entities),
            is_flashbulb=is_flashbulb,
        )
        
        episode = MemoryEpisode(
            episode_id=episode_id or "",
            content=content.strip(),
            memory_type=memory_type,
            emotions=emotions,
            emotional_intensity=emotional_intensity,
            base_importance=base_importance,
            current_importance=base_importance,
            associated_entities=associated_entities,
            tags=tags,
            source_context=source_context,
        )
        
        if episode_id and episode_id in self._memories:
            self._memories[episode_id] = episode
        else:
            self._memories[episode.episode_id] = episode
        
        if self.memory_count > int(self.MAX_MEMORIES * self.AUTO_CLEANUP_THRESHOLD):
            self._auto_cleanup()
            
        return episode
    
    def retrieve(
        self,
        query: Optional[List[str]] = None,
        entity_id: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        max_results: int = 10,
        min_importance: float = 0.1,
        include_forgotten: bool = False,
    ) -> MemoryRetrievalResult:
        """
        检索记忆
        
        支持多种检索模式:
        1. 关键词查询 (query): 基于内容相似度
        2. 实体过滤 (entity_id): 只返回关联指定实体的记忆
        3. 类型过滤 (memory_type): 只返回特定类型的记忆
        4. 组合查询: 可以同时使用多种条件 (AND逻辑)
        
        排序: 按 relevance_score 降序
        截断: 返回最多 max_results 条
        
        Args:
            query: 关键词列表 (None表示不按关键词过滤)
            entity_id: 实体ID过滤 (None表示不过滤)
            memory_type: 记忆类型过滤 (None表示不过滤)
            max_results: 最大返回数量, 默认10
            min_importance: 最小重要性阈值, 默认0.1
            include_forgotten: 是否包含已遗忘的记忆, 默认False
            
        Returns:
            MemoryRetrievalResult (包含episodes列表和对应的相关性分数)
        """
        start_time = time.perf_counter()
        
        candidates: List[Tuple[MemoryEpisode, float]] = []
        
        for episode in self._memories.values():
            if not include_forgotten and episode.is_forgotten:
                continue
            if episode.current_importance < min_importance:
                continue
            if memory_type and episode.memory_type != memory_type:
                continue
            if entity_id and entity_id not in episode.associated_entities:
                continue
                
            if query:
                relevance = MemoryImportanceCalculator.compute_relevance_score(
                    query, episode
                )
                if relevance <= 0.001:
                    continue
            else:
                relevance = episode.current_importance
                
            candidates.append((episode, relevance))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_results = candidates[:max_results]
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return MemoryRetrievalResult(
            episodes=top_results,
            query_keywords=query,
            total_searched=len(candidates),
            retrieval_time_ms=elapsed_ms,
        )
    
    def decay(self, force: bool = False) -> int:
        """
        执行记忆衰减 (基于艾宾浩斯曲线)
        
        应该定期调用 (建议每小时一次):
        - 遍历所有记忆
        - 对每条记忆调用update_importance_with_decay()
        - 标记current_importance < FORGETTING_THRESHOLD的记忆为"forgotten"
        - 返回本次衰减后被标记为forgotten的记忆数量
        
        Args:
            force: 是否强制执行 (忽略DECAY_INTERVAL_SECONDS限制)
            
        Returns:
            本次衰减后新增的forgotten记忆数量
        """
        current_time = time.time()
        time_since_last_decay = current_time - self._last_decay_time
        
        if not force and time_since_last_decay < self.DECAY_INTERVAL_SECONDS:
            return 0
            
        self._last_decay_time = current_time
        newly_forgotten = 0
        
        for episode in self._memories.values():
            old_importance = episode.current_importance
            
            new_importance = MemoryImportanceCalculator.update_importance_with_decay(
                base_importance=episode.base_importance,
                age_days=episode.age_days,
                access_count=episode.access_count,
                days_since_last_access=(
                    current_time - episode.last_accessed
                ) / _SECONDS_PER_DAY,
                memory_type=episode.memory_type,
            )
            
            episode.current_importance = new_importance
            
            if not episode.is_forgotten and new_importance < self.FORGETTING_THRESHOLD:
                newly_forgotten += 1
                
        return newly_forgotten
    
    def forget(self, episode_id: str) -> Optional[MemoryEpisode]:
        """
        手动遗忘 (强制删除指定记忆)
        
        Args:
            episode_id: 要遗忘的记忆ID
            
        Returns:
            被删除的MemoryEpisode, 如果不存在则返回None
        """
        return self._memories.pop(episode_id, None)
    
    def get_memories_for_prompt(
        self,
        max_count: int = 5,
        context_query: Optional[List[str]] = None,
        max_total_length: int = 300,
    ) -> str:
        """
        生成用于注入LLM prompt的记忆摘要
        
        选择策略:
        1. 如果有context_query: 先按相关性检索top-N
        2. 否则: 按current_importance取top-N
        3. 将选中的记忆转换为to_prompt_fragment()
        4. 拼接为完整文本, 控制总长度不超过max_total_length
        
        输出格式:
        "相关记忆:\n1. [tag] content\n2. ..."
        
        Args:
            max_count: 最大记忆条数, 默认5
            context_query: 上下文关键词 (用于相关性检索)
            max_total_length: 总最大字符长度, 默认300
            
        Returns:
            格式化的记忆摘要文本 (如果没有相关记忆则返回空字符串)
        """
        if context_query:
            result = self.retrieve(
                query=context_query,
                max_results=max_count,
                include_forgotten=False,
            )
            episodes = result.get_top_episodes(max_count)
        else:
            all_memories = sorted(
                self._memories.values(),
                key=lambda ep: ep.current_importance,
                reverse=True,
            )[:max_count]
            episodes = [(ep, ep.current_importance) for ep in all_memories]
        
        if not episodes:
            return ""
            
        fragments: List[str] = []
        current_length = 0
        header = "相关记忆:\n"
        current_length += len(header)
        
        for idx, (ep, _) in enumerate(episodes, 1):
            fragment = ep.to_prompt_fragment()
            line = f"{idx}. {fragment}\n"
            
            if current_length + len(line) > max_total_length:
                break
                
            fragments.append(line)
            current_length += len(line)
        
        if not fragments:
            return ""
            
        return header + "".join(fragments)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取记忆系统统计信息 (用于调试/监控)
        
        Returns:
            包含以下信息的字典:
            - total_memories: 总记忆数
            - active_memories: 未遗忘记忆数
            - forgotten_memories: 已遗忘记忆数
            - avg_importance: 平均重要性
            - oldest_memory_age_days: 最老记忆年龄 (天)
            - newest_memory_age_days: 最新记忆年龄 (天)
            - type_distribution: 各类型记忆数量分布
            - emotion_distribution: 各情绪类型分布
        """
        if not self._memories:
            return {
                "total_memories": 0,
                "active_memories": 0,
                "forgotten_memories": 0,
                "avg_importance": 0.0,
                "oldest_memory_age_days": 0.0,
                "newest_memory_age_days": 0.0,
                "type_distribution": {},
                "emotion_distribution": {},
            }
        
        active = [ep for ep in self._memories.values() if not ep.is_forgotten]
        forgotten = [ep for ep in self._memories.values() if ep.is_forgotten]
        
        avg_importance = (
            sum(ep.current_importance for ep in self._memories.values()) /
            len(self._memories)
        )
        
        oldest = min(self._memories.values(), key=lambda ep: ep.timestamp)
        newest = max(self._memories.values(), key=lambda ep: ep.timestamp)
        
        type_dist: Dict[str, int] = {}
        emotion_dist: Dict[str, int] = {}
        
        for ep in self._memories.values():
            type_name = ep.memory_type.name
            type_dist[type_name] = type_dist.get(type_name, 0) + 1
            
            for em in ep.emotions:
                em_name = em.name
                emotion_dist[em_name] = emotion_dist.get(em_name, 0) + 1
        
        return {
            "total_memories": len(self._memories),
            "active_memories": len(active),
            "forgotten_memories": len(forgotten),
            "avg_importance": avg_importance,
            "oldest_memory_age_days": oldest.age_days,
            "newest_memory_age_days": newest.age_days,
            "type_distribution": type_dist,
            "emotion_distribution": emotion_dist,
        }
    
    def _auto_cleanup(self) -> int:
        """
        内部方法: 自动清理低重要性记忆
        
        触发条件: memory_count > MAX_MEMORIES × AUTO_CLEANUP_THRESHOLD
        
        清理策略:
        1. 按current_importance升序排列
        2. 删除最低的10% (直到降到安全线以下)
        3. 返回删除的数量
        
        Returns:
            清理的记忆数量
        """
        if len(self._memories) == 0:
            return 0
            
        sorted_memories = sorted(
            self._memories.items(),
            key=lambda item: item[1].current_importance,
        )
        
        cleanup_count = max(
            1,
            int(len(sorted_memories) * _CLEANUP_PERCENTAGE),
        )
        
        to_remove = sorted_memories[:cleanup_count]
        
        for episode_id, _ in to_remove:
            del self._memories[episode_id]
            
        return len(to_remove)
