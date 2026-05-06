# 记忆系统 (Memory)

信息论重要性计算 + 艾宾浩斯遗忘曲线实现的完整记忆管理。

## 模块概览

```
luqi_engine/memory/
└── memory_system.py     — MemorySystem / MemoryEpisode / MemoryImportanceCalculator
```

## MemorySystem — 记忆系统 ⭐ 核心

```python
class MemoryType(Enum):
    EPISODIC = "episodic"        # 情景记忆 (具体事件)
    SEMANTIC = "semantic"        # 语义记忆 (抽象知识)
    FLASHBULB = "flashbulb"      # 闪光灯记忆 (高情绪冲击)


class MemoryEmotion(Enum):
    JOY = "joy"
    ANGER = "anger"
    SORROW = "sorrow"
    FEAR = "fear"
    LOVE = "love"
    DISGUST = "disgust"
    DESIRE = "desire"


@dataclass
class MemoryEpisode:
    """记忆条目 (核心数据结构)"""
    episode_id: str
    content: str
    memory_type: MemoryType
    emotion: Optional[MemoryEmotion] = None
    emotion_intensity: float = 0.5       # 情绪强度 [0, 1]
    importance: float = 0.5              # 重要性 [0, 1] (由计算器生成)
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    associated_characters: List[str] = field(default_factory=list)
    decay_factor: float = 1.0            # 衰减因子 (艾宾浩斯)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryRetrievalResult:
    """检索结果"""
    episodes: List[MemoryEpisode]
    query: str
    total_matches: int
    retrieval_time_ms: float
    used_strategy: str                   # "keyword" / "semantic" / "temporal" / "importance"
```

### MemoryImportanceCalculator — 重要性计算器

```python
class MemoryImportanceCalculator:
    """信息论 + 多维度重要性评估

    算法:
      importance = w_info × information_content
                + w_emotion × emotion_intensity × emotion_novelty
                + w_recency × recency_factor
                + w_access × access_frequency_factor

    信息量公式 (Shannon):
      I(x) = -log₂(P(x))

    艾宾浩斯遗忘曲线:
      R(t) = e^(-t/S)
      其中 S = strength_factor (受情绪强度影响)
    """

    def compute_importance(self, episode: MemoryEpisode) -> float:
        """计算单条记忆的重要性分数 [0, 1]"""

    def compute_batch_importance(self, episodes: List[MemoryEpisode]) -> List[float]:
        """批量计算"""

    def update_decay_factors(self, episodes: List[MemoryEpisode], elapsed_seconds: float) -> None:
        """根据艾宾浩斯曲线更新衰减因子"""
```

### MemorySystem 完整API

```python
class MemorySystem:
    """角色级记忆管理系统

    特性:
    - 按角色ID隔离存储
    - 多策略检索 (关键词/语义/时间/重要性)
    - 自动重要性排序
    - 遗忘曲线衰减
    - 容量限制与淘汰
    """

    def __init__(self, config: Optional[MemoryConfig] = None) -> None: ...

    async def store(
        self,
        character_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        emotion: Optional[MemoryEmotion] = None,
        emotion_intensity: float = 0.5,
        tags: Optional[List[str]] = None,
        associated_characters: Optional[List[str]] = None,
    ) -> MemoryEpisode:
        """存储新记忆 (自动计算重要性)"""

    async def retrieve(
        self,
        character_id: str,
        query: str,
        top_k: int = 10,
        memory_type: Optional[MemoryType] = None,
        min_importance: float = 0.0,
        time_range: Optional[Tuple[float, float]] = None,
    ) -> MemoryRetrievalResult:
        """多策略记忆检索"""

    async def forget(self, character_id: str, episode_id: str) -> bool:
        """遗忘指定记忆"""

    async def get_stats(self, character_id: str) -> Dict[str, Any]:
        """获取统计信息"""

    async def decay_all(self, character_id: str, elapsed_seconds: float) -> int:
        """应用时间衰减，返回受影响条目数"""

    def get_episode(self, character_id: str, episode_id: str) -> Optional[MemoryEpisode]: ...
    def list_episodes(self, character_id: str, limit: int = 50) -> List[MemoryEpisode]: ...
```

## 使用示例

```python
from luqi_engine.memory.memory_system import (
    MemorySystem, MemoryType, MemoryEmotion, MemoryEpisode
)

mem_sys = MemorySystem()

# 存储记忆
episode = await mem_sys.store(
    character_id="hero_001",
    content="在断桥边遇到了神秘女子",
    memory_type=MemoryType.FLASHBULB,
    emotion=MemoryEmotion.LOVE,
    emotion_intensity=0.9,
    tags=["相遇", "重要剧情"],
    associated_characters=["mystery_girl"],
)
print(f"存储成功: {episode.episode_id}")
print(f"重要性: {episode.importance:.3f}")

# 检索记忆
result = await mem_sys.retrieve(
    character_id="hero_001",
    query="相遇",
    top_k=5,
)
for ep in result.episodes:
    print(f"[{ep.memory_type.value}] {ep.content[:30]}... (重要性={ep.importance:.2f})")
```
