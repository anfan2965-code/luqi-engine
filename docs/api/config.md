# 配置系统 (Config)

引擎全局配置管理，支持代码配置、YAML文件加载和环境变量覆盖。

> **v1.3.0 更新**: 新增 `DesireConfig`、`AgentConfig`（四智能体独立配置）、`NarrativeDocConfig`、`PaceConfig`、`TrainingConfig`。保留 `CognitiveMemoryConfig`（向后兼容）。修正 `LocalModelConfig` 参数。

## 模块概览

```
luqi_engine/core/
├── config.py               — EngineConfig 主配置 + 所有子配置dataclass + ConfigMixin序列化
├── config_loader.py         — YAML/JSON配置文件加载器
└── gbnf_schema.py           — GBNF格式约束定义
```

## EngineConfig — 主配置类

```python
@dataclass
class EngineConfig(ConfigMixin):
    """引擎总配置，聚合所有子配置

    继承 ConfigMixin 提供 to_dict() / from_dict() 序列化能力
    """

    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    worldview: WorldViewConfig = field(default_factory=WorldViewConfig)
    scene: SceneConfig = field(default_factory=SceneConfig)
    character: CharacterConfig = field(default_factory=CharacterConfig)
    narrative: NarrativeConfig = field(default_factory=NarrativeConfig)
    interaction: InteractionConfig = field(default_factory=InteractionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    local_model: LocalModelConfig = field(default_factory=LocalModelConfig)
    desire: DesireConfig = field(default_factory=DesireConfig)
    mobile: MobileConfig = field(default_factory=MobileConfig)
    cognitive_memory: CognitiveMemoryConfig = field(default_factory=CognitiveMemoryConfig)
    local_llm: LocalLLMConfig = field(default_factory=LocalLLMConfig)
    chaos: ChaosConfig = field(default_factory=ChaosConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)              # v1.3.0 新增
    narrative_doc: NarrativeDocConfig = field(default_factory=NarrativeDocConfig)  # v1.3.0 新增
    pace: PaceConfig = field(default_factory=PaceConfig)                # v1.3.0 新增
    training: TrainingConfig = field(default_factory=TrainingConfig)    # v1.3.0 新增
    seed: Optional[int] = None
    debug_mode: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EngineConfig':
        """从字典创建配置，支持部分字段更新"""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（递归处理嵌套dataclass）"""
```

## 子配置类速查

### LLMConfig — LLM配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `sdk_type` | `"openai"` | SDK类型 (openai/deepseek/anthropic) |
| `api_key` | `""` | API密钥 (也支持环境变量 `LLM_API_KEY`) |
| `base_url` | `"https://api.openai.com/v1"` | API端点 |
| `model` | `"deepseek-chat"` | 模型名称 |
| `temperature` | `0.7` | 生成温度 [0,1] |
| `max_tokens` | `4096` | 最大输出token数 |
| `timeout` | `30.0` | 请求超时(秒) |
| `enable_deepseek_optimization` | `True` | DeepSeek特殊优化开关 |
| `context_compression_threshold` | `8000` | 上下文压缩阈值(tokens) |

### LocalModelConfig — 本地模型管线配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `model_path` | `""` | 模型文件路径 |
| `classification_threshold` | `0.85` | 分类置信度阈值 |
| `export_endpoint` | `""` | 训练数据导出端点 |
| `enable_debug_output` | `True` | 调试输出开关 |
| `max_memory_mb` | `200.0` | 最大内存占用(MB) |

### PerformanceConfig — 性能配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `target_fps` | `30` | 目标帧率 |
| `max_cpu_percent` | `70.0` | CPU上限(%) |
| `max_memory_mb` | `4096.0` | 内存上限(MB) |
| `response_latency_ms` | `300.0` | 目标延迟(ms) |
| `inactive_release_threshold_sec` | `300.0` | 非活跃释放阈值(秒) |
| `resource_recovery_efficiency` | `0.7` | 资源回收效率 |
| `object_pool_initial_size` | `64` | 对象池初始容量 |
| `async_task_concurrency` | `8` | 异步并发数 |

### NarrativeConfig — 叙事配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_branch_depth` | `10` | 最大分支深度 |
| `core_story_completion_rate` | `0.85` | 主线完成目标 |
| `elasticity_coefficient` | `50.0` | 弹性系数 [0,100] |
| `deviation_warning_response_sec` | `1.0` | 偏差警告响应时间(秒) |
| `regression_methods` | `["natural","event_triggered","forced"]` | 回归方法列表 |
| `branch_merge_enabled` | `True` | 分支合并开关 |
| `branch_pruning_enabled` | `True` | 分支剪枝开关 |

### CharacterConfig — 角色配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `personality_dimensions` | `5` | OCEAN维度数 |
| `personality_score_range` | `(0, 100)` | 分数范围 |
| `behavior_consistency_threshold` | `0.95` | 一致性阈值 |
| `short_term_memory_capacity` | `100` | 短期记忆容量 |
| `long_term_memory_capacity` | `10000` | 长期记忆容量 |
| `emotional_memory_capacity` | `500` | 情感记忆容量 |
| `memory_retrieval_limit` | `10` | 记忆检索上限 |
| `personality_adaptation_rate` | `0.02` | 性格适应速率 |

### DesireConfig — 欲望系统配置 (v1.3.0 新增)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `desire_dimensions` | `[16项]` | 欲望维度列表 (生理/安全/归属/尊重/自我实现/自我超越/感知/...) |
| `emotion_trigger_threshold` | `0.3` | 情感触发阈值 |
| `value_system_weights` | `{Dict}` | 价值体系权重 (各维度权重分配) |
| `drive_chain_max_depth` | `5` | 驱动链最大深度 |

### AgentConfig — 四智能体配置 (v1.3.0 新增)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `dialogue` | SingleAgentConfig | DialogueAgent配置 (token_budget/temperature/mode) |
| `novel` | SingleAgentConfig | NovelistAgent配置 (默认INCREMENTAL模式) |
| `critic` | SingleAgentConfig | CriticAgent配置 (默认FULL模式) |
| `atmosphere` | SingleAgentConfig | AtmosphereAgent配置 (默认LIGHT模式) |

**SingleAgentConfig 子参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `token_budget` | int | Token预算 |
| `temperature` | float | 生成温度 |
| `mode` | str | 运行模式 (DEFAULT/FULL/LIGHT/INCREMENTAL等) |

### NarrativeDocConfig — 叙事文档配置 (v1.3.0 新增)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `quality_level` | `"standard"` | 质量等级 |
| `max_facts` | `int` | 最大事实数 |
| `max_chapter_depth` | `int` | 最大章节深度 |
| `max_scene_predictions` | `int` | 最大场景预测数 |
| `auto_save_interval_seconds` | `float` | 自动保存间隔(秒) |

### PaceConfig — 节奏控制配置 (v1.3.0 新增)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `fast_threshold` | `float` | 快节奏阈值 |
| `slow_threshold` | `float` | 慢节奏阈值 |
| `auto_mode_timeout` | `float` | 自动模式超时(秒) |
| `pace_window_size` | `int` | 节奏窗口大小 |

### TrainingConfig — 训练数据配置 (v1.3.0 新增)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `storage_path` | `str` | 存储路径 |
| `per_character_isolation` | `True` | 按角色隔离存储 |
| `quality_threshold` | `float` | 质量阈值 |
| `auto_collect` | `True` | 自动采集开关 |
| `max_samples_per_character` | `int` | 每角色最大样本数 |

## 配置加载方式

```python
from luqi_engine.core.config import EngineConfig

# 方式1: 代码创建
config = EngineConfig()
config.llm.model = "gpt-4o-mini"

# 方式2: 字典加载
config = EngineConfig.from_dict({"llm": {"model": "gpt-4o-mini"}})

# 方式3: YAML加载
import yaml
with open("luqi_engine.yaml") as f:
    config = EngineConfig.from_dict(yaml.safe_load(f))

# 验证
errors = config.validate()
if errors:
    for e in errors:
        print(f"配置错误: {e}")
```

## 完整YAML示例

```yaml
engine:
  seed: 42
  debug_mode: false

llm:
  sdk_type: openai
  model: deepseek-chat
  temperature: 0.7
  max_tokens: 4096

local_model:
  enable_bge_semantic: false
  max_text_length: 5000

narrative:
  max_branch_depth: 10
  elasticity_coefficient: 50.0

game_theory:
  belief_learning_rate: 0.3
  mixed_strategy_iterations: 100

stress_test:
  max_rounds: 5000
  narrative_arc_enabled: true
```
