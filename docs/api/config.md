# 配置系统 (Config)

配置系统集中管理引擎的所有可调参数，支持代码配置和外部YAML文件加载。

## EngineConfig 主配置类

::: luqi_engine.core.config.EngineConfig
    options:
      show_root_heading: true
      show_root_toc_entry: true

## 子配置类

### PerformanceConfig - 性能配置

::: luqi_engine.core.config.PerformanceConfig
    options:
      show_root_heading: true

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `target_fps` | 30 | 目标帧率 |
| `max_cpu_percent` | 70.0 | CPU使用上限 (%) |
| `max_memory_mb` | 4096.0 | 内存使用上限 (MB) |
| `response_latency_ms` | 300.0 | 目标响应延迟 (ms) |
| `inactive_release_threshold_sec` | 300.0 | 不活跃资源释放阈值 (秒) |
| `resource_recovery_efficiency` | 0.7 | 资源回收效率 |
| `object_pool_initial_size` | 64 | 对象池初始大小 |
| `async_task_concurrency` | 8 | 异步任务并发数 |

### LLMConfig - LLM配置

::: luqi_engine.core.config.LLMConfig
    options:
      show_root_heading: true

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `sdk_type` | "openai" | SDK类型 (openai/deepseek/anthropic) |
| `api_key` | "" | API密钥 (也可通过环境变量设置) |
| `base_url` | "https://api.openai.com/v1" | API端点 |
| `model` | "deepseek-chat" | 模型名称 |
| `temperature` | 0.7 | 生成温度 (0-1) |
| `max_tokens` | 4096 | 最大生成token数 |
| `timeout` | 30.0 | 请求超时时间 (秒) |
| `enable_deepseek_optimization` | True | 是否启用DeepSeek优化 |
| `context_compression_threshold` | 8000 | 上下文压缩阈值 (tokens) |
| `system_token_budget` | 300 | 系统提示词预算 (tokens) |

### NarrativeConfig - 叙事配置

::: luqi_engine.core.config.NarrativeConfig
    options:
      show_root_heading: true

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_branch_depth` | 10 | 最大分支深度 |
| `core_story_completion_rate` | 0.85 | 主线完成率目标 |
| `elasticity_coefficient` | 50.0 | 弹性系数 (0-100) |
| `deviation_warning_response_sec` | 1.0 | 偏离警告响应时间 (秒) |
| `branch_merge_enabled` | True | 启用分支合并 |
| `branch_pruning_enabled` | True | 启用分支剪枝 |
| `elasticity_min` | 0.0 | 最小弹性值 |
| `elasticity_max` | 100.0 | 最大弹性值 |
| `branch_weight_core_story` | 0.4 | 主线权重 |
| `branch_weight_character_driven` | 0.25 | 角色驱动权重 |
| `branch_weight_random_event` | 0.15 | 随机事件权重 |
| `branch_weight_elasticity` | 0.2 | 弹性权重 |

### CharacterConfig - 角色配置

::: luqi_engine.core.config.CharacterConfig
    options:
      show_root_heading: true

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `personality_dimensions` | 5 | 性格维度数 (OCEAN=5) |
| `personality_score_range` | (0, 100) | 性格分数范围 |
| `behavior_consistency_threshold` | 0.95 | 行为一致性阈值 |
| `short_term_memory_capacity` | 100 | 短期记忆容量 |
| `long_term_memory_capacity` | 10000 | 长期记忆容量 |
| `emotional_memory_capacity` | 500 | 情绪记忆容量 |
| `memory_retrieval_limit` | 10 | 记忆检索限制数 |
| `personality_adaptation_rate` | 0.02 | 性格适应速率 |

### SceneConfig - 场景配置

::: luqi_engine.core.config.SceneConfig
    options:
      show_root_heading: true

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `spatial_conflict_accuracy` | 0.95 | 空间冲突检测精度 |
| `max_elements_per_scene` | 500 | 单场景最大元素数 |
| `environment_update_interval_sec` | 1.0 | 环境更新间隔 (秒) |
| `time_scale` | 1.0 | 时间流速倍率 |
| `weather_transition_duration` | 30.0 | 天气过渡时长 (秒) |

### InteractionConfig - 交互配置

::: luqi_engine.core.config.InteractionConfig
    options:
      show_root_heading: true

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_concurrent_characters` | 50 | 最大同时在线角色数 |
| `dialogue_fluency_target` | 4.0 | 对话流畅度目标 (1-5分) |
| `relationship_dimensions` | ["friendship", ...] | 关系维度列表 |
| `social_rules_enabled` | True | 启用社交规则 |
| `dialogue_max_rounds` | 50 | 最大对话轮数 |
| `context_window_turns` | 50 | 上下文窗口轮数 |
| `key_info_retention_rate` | 0.98 | 关键信息保持率 |

### WorldViewConfig - 世界观配置

::: luqi_engine.core.config.WorldViewConfig
    options:
      show_root_heading: true

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `conflict_detection_accuracy` | 0.95 | 冲突检测精度 |
| `element_extraction_accuracy` | 0.90 | 元素提取精度 |
| `relation_depth_limit` | 5 | 关系推理深度限制 |
| `supported_content_types` | [...] | 支持的内容类型 |

### LocalLLMConfig - 本地LLM配置

::: luqi_engine.core.config.LocalLLMConfig
    options:
      show_root_heading: true

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `local_llm_enabled` | False | 是否启用本地LLM |
| `local_llm_model_path` | "" | 模型文件路径 (.gguf) |
| `local_llm_n_gpu_layers` | 0 | GPU加速层数 (0=CPU only) |
| `local_llm_n_ctx` | 2048 | 上下文长度 |
| `local_llm_max_tokens` | 512 | 最大输出token数 |
| `local_llm_temperature` | 0.7 | 生成温度 |
| `local_llm_top_p` | 0.9 | Top-P采样参数 |

### MobileConfig - 移动端配置

::: luqi_engine.core.config.MobileConfig
    options:
      show_root_heading: true

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `target_device` | "snapdragon_695" | 目标设备型号 |
| `max_memory_mb` | 2048.0 | 最大内存限制 (MB) |
| `max_cpu_percent` | 70.0 | CPU使用上限 (%) |
| `local_model_memory_mb` | 200.0 | 本地模型内存 (MB) |
| `target_fps` | 30 | 目标帧率 |

### CognitiveMemoryConfig - 认知记忆配置

::: luqi_engine.core.config.CognitiveMemoryConfig
    options:
      show_root_heading: true

包含感知、工作、短期、长期、情绪等多层记忆系统的详细配置。

### ChaosConfig - 混沌系统配置

::: luqi_engine.core.config.ChaosConfig
    options:
      show_root_heading: true

Lorenz混沌吸引子参数，用于情感引擎的非线性动力学模拟。

## 配置加载方式

### 方式1: 代码直接创建

```python
from luqi_engine.core.config import EngineConfig

config = EngineConfig()
config.llm.model = "gpt-4o-mini"
config.narrative.elasticity_coefficient = 60.0
```

### 方式2: 从字典加载

```python
data = {
    "llm": {
        "model": "gpt-4o-mini",
        "temperature": 0.8,
    },
    "narrative": {
        "max_branch_depth": 5,
    }
}
config = EngineConfig.from_dict(data)
```

### 方式3: 从YAML文件加载 (Demo中使用)

```python
import yaml

with open("luqi_engine.yaml", "r") as f:
    data = yaml.safe_load(f)

config = EngineConfig.from_dict(data)
```

### 方式4: 环境变量覆盖

部分敏感配置可通过环境变量设置：

```bash
export LLM_API_KEY="sk-xxx"
export OPENAI_BASE_URL="https://your-endpoint/v1"
```

## 移动端优化配置示例

```python
from luqi_engine.core.config import (
    EngineConfig, MobileConfig, SceneConfig,
    CharacterConfig, PerformanceConfig
)

mobile_config = EngineConfig()
mobile_config.mobile = MobileConfig(
    target_device="snapdragon_695",
    max_memory_mb=2048.0,
)
mobile_config.scene = SceneConfig(max_elements_per_scene=200)
mobile_config.character = CharacterConfig(short_term_memory_capacity=50)
mobile_config.performance = PerformanceConfig(target_fps=24, async_task_concurrency=4)
```

## 完整配置示例

```yaml
engine:
  seed: 42
  debug_mode: false

llm:
  sdk_type: openai
  model: gpt-4o-mini
  temperature: 0.7
  max_tokens: 2048

narrative:
  max_branch_depth: 8
  elasticity_coefficient: 55.0
  branch_merge_enabled: true

character:
  short_term_memory_capacity: 100
  personality_adaptation_rate: 0.02

scene:
  max_elements_per_scene: 300

interaction:
  dialogue_max_rounds: 20
  social_rules_enabled: true

local_llm:
  local_llm_enabled: false
  local_llm_model_path: ""
```
