# 本地模型管线 (Local Model)

离线优先的本地NLP处理管线，4阶段架构实现零网络依赖的文本理解能力。

> **v1.3.0 更新**: 新增 `HybridLocalModelPipeline` 混合管线，支持 `BGESemanticEngine` 语义引擎。

## 模块概览

```
luqi_engine/local_model/
├── pipeline.py           — 标准管线 (4阶段: 预处理→分词→向量化→分类)
├── hybrid_pipeline.py    — 混合管线 (标准+语义+安全)
├── preprocessor.py       — 文本预处理器
├── tokenizer.py          — 自定义分词器 (CJK/英文混合)
├── vectorizer.py         — TF-IDF 向量化器
├── semantic_vectorizer.py— BGE语义向量器
├── classifier.py         — 内容分类器 (意图/情感/动作)
├── corrector.py          — 内容纠正器 (错别字/格式)
├── safety_checker.py     — 上下文安全检查器
├── resource_loader.py    — NLP资源加载器 (词向量/模型)
└── data_exporter.py      — 训练数据导出器
```

## LocalModelPipeline — 标准管线

```python
class LocalModelPipeline(ILocalModel):
    """4阶段本地NLP管线

    Stage 1: preprocess  → TextPreprocessor   (清洗/标准化/截断)
    Stage 2: tokenize    → CustomTokenizer     (CJK分词/停用词过滤)
    Stage 3: vectorize   → TFIDFVectorizer    (稀疏向量/特征提取)
    Stage 4: classify    → ContentClassifier   (意图分类/置信度)
    Stage 5: safety      → ContextSafetyChecker(内容安全审查) [可选]
    """

    def __init__(
        self,
        config: LocalModelConfig | None = None,
        resource_loader: Optional[NLPResourceLoader] = None,
    ) -> None: ...

    async def process(self, text: str, context: Dict[str, Any] | None = None) -> LocalModelOutput:
        """执行完整管线处理"""

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """返回各阶段耗时统计"""
```

**管线输出 `LocalModelOutput`**:
| 字段 | 类型 | 说明 |
|------|------|------|
| text | str | 处理后文本 |
| intent | str | 意图分类结果 |
| confidence | float | 分类置信度 [0,1] |
| emotion | EmotionDelta | 情感偏移量 |
| action | str | 动作类型 |
| safety_verdict | SafetyVerdict \| None | 安全检查结果 |

## HybridLocalModelPipeline — 混合管线

```python
class HybridLocalModelPipeline(LocalModelPipeline):
    """扩展标准管线，增加语义理解和安全检查

    在 classify 之后增加:
    - BGESemanticEngine: BGE语义相似度计算
    - ContextSafetyChecker: 多维度安全扫描
    """

    def __init__(self, config: LocalModelConfig | None = None) -> None: ...

    async def process(self, text: str, context: Dict[str, Any] | None = None) -> LocalModelOutput:
        """5阶段混合处理"""
```

## 各阶段组件

### TextPreprocessor — 文本预处理
```python
class TextPreprocessor:
    """文本清洗与标准化: 去除特殊字符/统一标点/长度截断/Unicode规范化"""
```

### CustomTokenizer — 自定义分词器
```python
class CustomTokenizer:
    """CJK-英文混合分词: 最大匹配算法 + 停用词表 + 自定义词典"""
```

### TFIDFVectorizer — TF-IDF向量化器
```python
class TFIDFVectorizer:
    """稀疏特征提取: TF归一化 + IDF加权 + 维度裁剪"""
```

### BGESemanticEngine — BGE语义引擎
```python
class BGESemanticEngine:
    """基于BGE模型的语义相似度计算（可选依赖）"""
```

### ContentClassifier — 内容分类器
```python
class ContentClassifier:
    """多标签分类: 意图(SIMPLE/MODERATE/COMPLEX) + 情感(PAD偏移) + 动作类型"""
```

### ContentCorrector — 内容纠正器
```python
class ContentCorrector:
    """后处理纠错: 错别字修正/格式规范化/长度调整"""
```

### ContextSafetyChecker — 安全检查器
```python
class ContextSafetyChecker:
    """多维度安全扫描: 敏感词/暴力/色情/政治/自定义规则"""

    class SafetyLevel(Enum):
        SAFE = "safe"
        WARNING = "warning"
        UNSAFE = "unsafe"
        BLOCKED = "blocked"

    @dataclass
    class SafetyVerdict:
        level: SafetyLevel
        reasons: List[str]
        score: float           # 安全评分 [0,1], 越高越安全
```

### NLPResourceLoader — 资源加载器
```python
class NLPResourceLoader:
    """懒加载NLP资源: 词向量文件/停用词表/敏感词库/分词字典"""
```

### TrainingDataExporter — 数据导出器
```python
class TrainingDataExporter:
    """将管线中间产物导出为训练样本格式"""
```

## 性能特征

| 指标 | 值 |
|------|-----|
| 单次处理延迟 | <50ms (CPU模式) |
| 内存占用 | ~200MB (含词向量) |
| 网络依赖 | **零** (完全离线) |
| 冷启动时间 | ~2s (首次加载资源) |

## 相关文档

- [核心配置](config.md) — `LocalModelConfig` 参数说明
- [LLM层](llm.md) — 与 `LocalLLMAdapter` 的协作关系
- [性能管理](performance.md) — `ObjectPool` 对象复用优化
