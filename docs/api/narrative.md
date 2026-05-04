# 叙事系统 (Narrative)

叙事系统负责故事分支管理、剧情弹性控制和主线回归机制。

## 核心组件

::: luqi_engine.narrative.controller
    options:
      show_root_heading: true
      show_root_toc_entry: true

## 四因子分支系统

叙事引擎使用**四因子权重模型**决定故事走向：

| 因子 | 权重 | 说明 |
|------|------|------|
| 主线剧情 (core_story) | 40% | 推动核心叙事发展 |
| 角色驱动 (character_driven) | 25% | 基于角色性格和动机的选择 |
| 随机事件 (random_event) | 15% | 增加不可预测性和趣味性 |
| 弹性系数 (elasticity) | 20% | 控制偏离主线的程度 |

## 弹性控制

弹性系数控制故事偏离主线的程度：

```python
from luqi_engine.core.config import NarrativeConfig

config = NarrativeConfig(
    elasticity_coefficient=50.0,  # 弹性系数 0-100
    max_branch_depth=10,          # 最大分支深度
    elasticity_min=0.0,           # 最小弹性（严格遵循主线）
    elasticity_max=100.0,         # 最大弹性（完全自由发展）
)
```

### 弹性行为

| 弹性值 | 行为描述 |
|--------|----------|
| 0-20 | 严格遵循主线，很少偏离 |
| 21-40 | 轻微偏离，快速回归 |
| 41-60 | 平衡模式（默认） |
| 61-80 | 允许较大偏离，缓慢回归 |
| 81-100 | 自由探索，仅关键点回归 |

## 回归机制

当剧情偏离主线过远时，触发回归：

| 回归方式 | 概率 | 触发条件 |
|----------|------|----------|
| 自然回归 (natural) | 30% | 角色选择自然回到主线 |
| 事件触发 (event_triggered) | 70% | 特定事件强制引导 |
| 强制回归 (forced) | 100% | 极端情况直接跳转 |

## 故事节点

叙事以**有向无环图 (DAG)** 形式组织：

```
[开始节点]
    ↓
[分支A] ←→ [分支B]   （弹性选择）
    ↓         ↓
[汇聚节点]
    ↓
[结局节点]
```

### 关键参数

```python
config = NarrativeConfig(
    branch_weight_core_story=0.4,       # 主线权重
    branch_weight_character_driven=0.25, # 角色驱动权重
    branch_weight_random_event=0.15,     # 随机事件权重
    branch_weight_elasticity=0.2,        # 弹性权重
    core_story_completion_rate=0.85,     # 主线完成率目标
    deviation_warning_threshold=0.7,     # 偏离警告阈值
    node_relevance_threshold=0.3,        # 节点相关性阈值
    dead_end_depth_penalty=0.1,          # 死胡同深度惩罚
)
```

## 分支合并与剪枝

- **分支合并**: 当多个分支汇聚时，智能整合各路径的状态变化
- **分支剪枝**: 自动移除低相关性或死胡同分支，保持叙事图清晰

```python
config.branch_merge_enabled = True   # 启用分支合并
config.branch_pruning_enabled = True # 启用分支剪枝
```

## 使用示例

```python
import asyncio
from luqi_engine.engine import LuqiEngine
from luqi_engine.core.config import EngineConfig

async def demo_narrative():
    config = EngineConfig()
    config.narrative.max_branch_depth = 8
    config.narrative.elasticity_coefficient = 60.0

    engine = LuqiEngine(config=config)
    await engine.initialize()

    controller = engine.narrative_controller

    # 查询当前叙事状态
    if hasattr(controller, 'get_status'):
        status = controller.get_status()
        print(f"当前分支深度: {status.get('current_depth', 0)}")
        print(f"主线进度: {status.get('core_progress', 0):.1%}")

    await engine.shutdown()

asyncio.run(demo_narrative())
```
