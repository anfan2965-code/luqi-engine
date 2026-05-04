# 场景系统 (Scene)

场景系统负责构建和管理虚拟世界中的空间环境，包括场景元素、空间冲突检测和环境动态更新。

## 核心组件

::: luqi_engine.scene.builder
    options:
      show_root_heading: true
      show_root_toc_entry: true

## 场景构建

### 创建场景

```python
import asyncio
from luqi_engine.engine import LuqiEngine

async def create_scene_demo():
    engine = LuqiEngine()
    await engine.initialize()

    scene_config = {
        "name": "魔法学院大厅",
        "description": "宏伟的大厅，天花板上有星空壁画",
        "elements": [
            {"type": "furniture", "name": "长桌", "position": [0, 0, 0]},
            {"type": "npc", "name": "图书管理员", "position": [5, 0, 3]},
            {"type": "prop", "name": "魔法书", "position": [5, 1, 3]},
        ],
        "environment": {
            "weather": "晴朗",
            "time_of_day": "下午",
            "lighting": "自然光 + 魔法光",
        },
    }

    scene_id = await engine.create_scene(scene_config)
    print(f"场景创建成功，ID: {scene_id}")

    await engine.shutdown()

asyncio.run(create_scene_demo())
```

## 场景元素

场景由多种元素组成：

| 元素类型 | 说明 | 示例 |
|----------|------|------|
| `furniture` | 家具/建筑结构 | 桌子、椅子、墙壁 |
| `npc` | NPC角色 | 守卫、商人、学者 |
| `prop` | 可交互物品 | 书籍、武器、钥匙 |
| `trigger` | 触发区域 | 传送门、陷阱入口 |
| `decoration` | 装饰物 | 画作、雕像、植物 |

## 空间冲突检测

引擎自动检测并处理空间冲突：

```python
from luqi_engine.core.config import SceneConfig

config = SceneConfig(
    spatial_conflict_accuracy=0.95,       # 冲突检测精度
    max_elements_per_scene=500,           # 单场景最大元素数
    environment_update_interval_sec=1.0,  # 环境更新间隔
    time_scale=1.0,                       # 时间流速倍率
    weather_transition_duration=30.0,     # 天气过渡时长(秒)
)
```

### 冲突处理策略

当两个元素试图占据同一位置时：
1. **精确碰撞**: 95%准确率检测重叠
2. **智能调整**: 微调位置避免完全重叠
3. **优先级排序**: 重要元素（如NPC）优先保留位置
4. **日志记录**: 记录所有冲突及解决方案

## 环境动态更新

场景环境随时间自动演变：

```python
# 环境属性
environment = {
    "weather": "sunny",          # 天气状态
    "temperature": 22.5,         # 温度 (°C)
    "humidity": 60,              # 湿度 (%)
    "time_of_day": "afternoon",  # 一天中的时段
    "lighting_condition": "natural_light",  # 光照条件
    "ambient_sound": "birds_chirping",      # 环境音效
}

# 天气过渡示例
# sunny → cloudy → rainy (30秒平滑过渡)
```

## 场景配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `spatial_conflict_accuracy` | 0.95 | 空间冲突检测精度 (0-1) |
| `max_elements_per_scene` | 500 | 单场景最大元素数量 |
| `environment_update_interval_sec` | 1.0 | 环境状态更新间隔 |
| `time_scale` | 1.0 | 游戏内时间流速 (1.0=实时) |
| `weather_transition_duration` | 30.0 | 天气切换动画时长(秒) |

## 性能优化建议

对于移动设备或性能受限环境：

```python
mobile_scene_config = SceneConfig(
    max_elements_per_scene=200,           # 减少最大元素数
    environment_update_interval_sec=2.0,  # 降低更新频率
    spatial_conflict_accuracy=0.90,       # 略微降低精度换性能
)
```
