# 核心 (Core)

核心基础设施模块，提供配置管理、事件总线、快照系统等基础服务。

## 模块概览

::: luqi_engine.core.config
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.core.event_bus
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.core.snapshot
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.core.types
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.core.rng
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.core.env
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.core.interfaces
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.core.constants
    options:
      show_root_heading: true
      show_root_toc_entry: true

## 使用示例

### 配置加载

```python
from luqi_engine.core.config import EngineConfig

# 使用默认配置
config = EngineConfig()

# 从字典加载
config = EngineConfig.from_dict({
    "llm": {
        "model": "gpt-4o-mini",
        "temperature": 0.8,
    },
    "narrative": {
        "max_branch_depth": 5,
    }
})
```

### 事件总线

```python
from luqi_engine.core.event_bus import EventBus, Event, EventType

event_bus = EventBus()

# 订阅事件
def handler(event: Event):
    print(f"收到事件: {event.payload}")

event_bus.subscribe(EventType.CUSTOM, handler)

# 发布事件
event_bus.publish(Event(
    event_type=EventType.CUSTOM,
    source="my_module",
    payload={"action": "test"},
))
```

### 快照操作

```python
from luqi_engine.core.snapshot import EngineSnapshot

# 保存快照
path = EngineSnapshot.save(engine, "snapshot.json")

# 加载快照
data = EngineSnapshot.load("snapshot.json")
```
