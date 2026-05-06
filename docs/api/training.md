# 训练数据采集 (Training)

引擎运行时的训练样本自动采集、存储与降级保护模块。

## 模块概览

```
luqi_engine/training/
├── sample_collector.py      — SampleCollector 样本采集器 (多维度质量评估)
├── data_store.py            — TrainingDataStore 数据存储 (按角色分桶隔离)
└── document_protector.py    — DegradationDocumentProtector 降级文档保护器
```

## QualityWeights — 质量权重配置

```python
@dataclass
class QualityWeights:
    """训练样本质量评估权重配置"""
    coherence: float = 0.35    # 连贯性权重
    faithfulness: float = 0.35 # 忠实度权重
    alignment: float = 0.30    # 对齐度权重
```

**质量评估公式**:
```
quality_score = w_coherence × coherence_score
             + w_faithful × faithful_score
             + w_alignment × alignment_score
```

**评级阈值**:
| 等级 | 阈值 | 说明 |
|------|------|------|
| gold | ≥0.8 | 高质量样本，可用于微调 |
| silver | ≥0.6-0.8 | 中等质量，可用于数据增强 |
| bronze | ≥0.3-0.6 | 低质量，仅用于离线分析 |
| rejected | <0.3 | 拒绝，不存储 |

## SampleCollector — 样本采集器

```python
class SampleCollector:
    """训练样本自动采集器

    功能:
    - collect(): 采集单轮交互完整数据（输入+输出+中间产物+修正记录）
    - 多维度质量评估: 连贯性/忠实度/对齐度加权算法
    - 自动用途标签: layer1_narrative / layer2_decision / layer3_voice / layer4_critic / layer5_atmosphere
    - 修正严重度感知: CLAMP(0.1) < OVERRIDE(0.3) < REJECT(0.5)

    采集内容:
    - TrainingInput: 用户输入+上下文
    - AgentOutputs: 各智能体完整输出
    - AlgorithmCorrections: 算法修正记录
    - FinalOutput: 最终输出结果
    """

    def __init__(self, config: Optional[TrainingConfig] = None) -> None: ...

    def collect(
        self,
        character_id: str,
        training_input: TrainingInput,
        agent_outputs: AgentOutputs,
        algorithm_corrections: AlgorithmCorrections,
        final_output: FinalOutput,
        narrative_version: int = 0,
    ) -> TrainingSample:
        """采集一轮对话的完整训练样本"""

    def _calculate_quality(self, sample_data: Dict[str, Any]) -> Tuple[float, str, SampleQuality]:
        """计算质量评分和等级 (内部方法)"""

    def _assign_usage_tags(self, quality_grade: str, has_corrections: bool) -> List[str]:
        """分配用途标签 (内部方法)"""
```

**修正严重度权重映射**:

```python
_CORRECTION_SEVERITY_WEIGHTS = {
    CorrectionSeverity.CLAMP: 0.1,     # 轻微钳制
    CorrectionSeverity.OVERRIDE: 0.3,  # 强制覆盖
    CorrectionSeverity.REJECT: 0.5,    # 拒绝并替换
}
```

**批评家判决影响**:

| 判决类型 | 分数调整 |
|----------|----------|
| ACCEPT | +0.2 奖励 |
| REVIEW | 0.0 无影响 |
| REJECT | -0.3 惩罚 |
| NARRATIVE_RISK | -0.15 风险惩罚 |

## StoreStats — 存储统计

```python
@dataclass
class StoreStats:
    """训练数据存储统计信息"""
    total_samples: int = 0
    samples_by_character: Dict[str, int]   # 按角色统计
    samples_by_layer: Dict[int, int]       # 按层级统计
    samples_by_grade: Dict[str, int]       # 按质量等级统计
    storage_bytes: int = 0                 # 存储占用字节数
```

## TrainingDataStore — 数据存储

```python
class TrainingDataStore:
    """训练数据分桶存储系统

    特性:
    - 按 character_id 完全隔离存储（防止风格污染）
    - 按 layer 分类存储（layer1~layer5）
    - 自动路径管理: training_data/{char_id}/layer{N}/{sample_id}.json
    - 最大样本数限制（可配置）
    - 支持按角色/层级/等级查询

    存储格式: JSON (indent=2, ensure_ascii=False)
    """

    def __init__(self, config: Optional[TrainingConfig] = None) -> None: ...

    def store(self, sample: TrainingSample) -> str:
        """存储样本，返回主存储路径"""

    def list_samples(
        self,
        character_id: str,
        layer: Optional[int] = None,
    ) -> List[str]:
        """列出指定角色的样本路径"""

    def get_stats(self, character_id: Optional[str] = None) -> StoreStats:
        """获取存储统计信息"""

    def export_character_data(
        self,
        character_id: str,
        output_dir: str,
        format: str = "jsonl",
    ) -> str:
        """导出指定角色的所有训练数据"""
```

**存储目录结构**:
```
training_data/
├── char_001/
│   ├── layer1/
│   │   └── {sample_id}.json
│   ├── layer2/
│   │   └── {sample_id}.json
│   └── ...
├── char_002/
│   └── ...
└── ...
```

## ProtectionReport — 保护报告

```python
@dataclass
class ProtectionReport:
    """降级保护操作报告"""
    applied: bool = True                          # 是否应用了保护
    fact_overwrites_blocked: int = 0              # 阻止的事实覆盖次数
    beat_reduction_blocked: bool = False          # 是否阻止了Beat缩减
    confidence_decay_applied: bool = False        # 是否应用了置信度衰减
    reasons: List[str] = None                     # 保护原因列表
```

## DegradationDocumentProtector — 降级文档保护器

```python
class DegradationDocumentProtector:
    """降级期间叙事文档保护器

    核心规则 (仅在 is_degraded=True 时激活):
    1. 事实覆盖保护: 仅允许 cloud 来源覆盖已有事实
    2. Beat数量保护: 拒绝缩减 chapter_outline 的 beats 数量
    3. 置信度衰减: 降级期间预测置信度乘以衰减因子 (默认0.7)

    使用场景:
    - LLM服务降级时防止错误修改叙事文档
    - 保证降级期间文档一致性不被破坏
    """

    def __init__(self, confidence_decay_factor: float = 0.7) -> None: ...

    def safe_apply_delta(
        self,
        delta: NarrativeDelta,
        existing_facts: List[Fact],
        current_chapter_outline: Optional[ChapterOutline],
        is_degraded: bool,
    ) -> Tuple[NarrativeDelta, ProtectionReport]:
        """安全应用叙事增量变更，返回保护后的delta和保护报告"""
```

**保护规则详解**:

| 规则 | 触发条件 | 保护行为 | 原因代码 |
|------|----------|----------|----------|
| 事实覆盖保护 | source ≠ "cloud" | 过滤掉非cloud来源的新事实 | fact_overwrite_rejected |
| Beat缩减保护 | 新beats < 原beats | 保持原beats数量不变 | beat_reduction_rejected |
| 置信度衰减 | is_degraded=True | confidence *= decay_factor | confidence_decayed |

**置信度衰减计算**:
```python
decayed_confidence = original_confidence * _DEGRADED_CONFIDENCE_DECAY_FACTOR  # 默认 0.7
```

## 使用示例

```python
from luqi_engine.training.sample_collector import SampleCollector
from luqi_engine.training.data_store import TrainingDataStore
from luqi_engine.training.document_protector import DegradationDocumentProtector
from luqi_engine.core.config import TrainingConfig

# 初始化
config = TrainingConfig(max_samples_per_character=1000)
collector = SampleCollector(config)
store = TrainingDataStore(config)
protector = DegradationDocumentProtector()

# 采集样本
sample = collector.collect(
    character_id="char_001",
    training_input=input_data,
    agent_outputs=outputs,
    algorithm_corrections=corrections,
    final_output=final_result,
)

# 存储
path = store.store(sample)

# 降级保护
protected_delta, report = protector.safe_apply_delta(
    delta=narrative_delta,
    existing_facts=current_facts,
    current_chapter_outline=outline,
    is_degraded=True,  # 当前处于降级状态
)

print(f"保护已启用: {report.applied}")
print(f"阻止的事实覆盖: {report.fact_overwrites_blocked}次")
```
