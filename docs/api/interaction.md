# 交互系统 (Interaction)

交互系统负责多角色对话协调、社交关系建模和对话流畅性管理。

## 核心组件

::: luqi_engine.interaction.coordinator
    options:
      show_root_heading: true
      show_root_toc_entry: true

## 多角色对话协调

### 启动多角色对话

```python
import asyncio
from luqi_engine.engine import LuqiEngine
from luqi_engine.llm.dialogue_modes import DialogueMode

async def multi_char_dialogue():
    engine = LuqiEngine()
    await engine.initialize()

    # 创建多个角色
    char1 = await engine.create_character({"name": "学者", "template": "scholar"})
    char2 = await engine.create_character({"name": "商人", "template": "merchant"})

    # 启动多角色对话
    dialogue_history = await engine.start_dialogue(
        participants=[char1, char2],
        topic="讨论魔法与贸易的关系",
        mode=DialogueMode.MULTI_CHARACTER,
        max_rounds=10,
    )

    for round_data in dialogue_history:
        print(f"回合 {round_data['round']}: "
              f"发言者ID={round_data['speaker_id']}, "
              f"优先级={round_data['priority_score']:.2f}")

    await engine.shutdown()

asyncio.run(multi_char_dialogue())
```

### 对话模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `SINGLE_CHARACTER` | 单角色一对一对话 | 玩家与NPC交互 |
| `MULTI_CHARACTER` | 多角色群组讨论 | 剧情演绎、社交场景 |

## 社交关系建模

### 关系维度

引擎使用**多维关系模型**描述角色间的社交关系：

| 维度 | 范围 | 说明 |
|------|------|------|
| 友谊 (friendship) | -1 ~ 1 | 亲密程度 |
| 信任 (trust) | -1 ~ 1 | 可信赖程度 |
| 敌意 (hostility) | 0 ~ 1 | 冲突倾向 |
| 尊重 (respect) | -1 ~ 1 | 地位认同 |

```python
from luqi_engine.core.config import InteractionConfig

config = InteractionConfig(
    relationship_dimensions=["friendship", "trust", "hostility", "respect"],
    max_concurrent_characters=50,
    dialogue_max_rounds=50,
    dialogue_fluency_target=4.0,      # 流畅度目标 (1-5分)
    social_rules_enabled=True,         # 启用社交规则
)
```

### 关系影响行为

角色间的关系会影响：

1. **发言优先级**: 高友谊/信任的角色更倾向于先发言
2. **回应内容**: 关系好的角色语气更友好
3. **合作意愿**: 高信任度增加合作概率
4. **冲突可能性**: 高敌意值可能引发争执

## 对话轮次控制

```python
config = InteractionConfig(
    dialogue_max_rounds=50,            # 最大对话轮次
    context_window_turns=50,           # 上下文窗口（保留的历史轮数）
    key_info_retention_rate=0.98,      # 关键信息保持率
)
```

### 对话流程

```
[开始] → [确定参与角色] → [计算优先级] → [选择发言者] → [生成回复]
                                                    ↓
                                            [更新关系状态]
                                                    ↓
                                            [检查是否继续]
                                                   / \
                                                 [是] [否]
                                                  ↓     ↓
                                             [下一轮] [结束]
```

## 社交规则引擎

当启用社交规则时 (`social_rules_enabled=True`)，系统会：

1. **礼貌性检查**: 确保回应符合基本社交礼仪
2. **一致性验证**: 回应是否符合当前关系状态
3. **情感传染**: 角色情绪会相互影响
4. **话题引导**: 根据关系动态调整话题走向

## 轮次调度器 (TurnScheduler)

概率型轮次调度器，支持6种轮次类型：

| 类型 | 默认权重 | 说明 |
|------|---------|------|
| main_char | 0.35 | 主要角色发言 |
| secondary_char | 0.15 | 次要角色发言 |
| user | 0.15 | 用户插入机会 |
| atmosphere | 0.05 | 氛围描写 |
| silence | 0.10 | 沉默/间歇 |
| reaction | 0.20 | 微反应（嗯…、点头等） |

### 用户插入机制

- 当角色对话中提及用户（"旅人"、"你"、"阁下"、"客官"），自动标记 `mark_user_addressed()`
- 用户缺席超过10轮时，获得额外+0.10权重加成
- 连续对话超过5轮时强制插入用户机会

### 反应微交互

reaction 类型生成简短反应（"嗯…"、"…"、"（点头）"等），模拟真实对话中的倾听反馈。

## 用户在场追踪 (UserPresenceTracker)

追踪用户在场状态，提供对话约束：

```python
from luqi_engine.interaction.user_tracker import UserPresenceTracker

tracker = UserPresenceTracker()
tracker.arrive(round_num=15)
tracker.depart(round_num=80)

# 查询约束
constraint = tracker.get_departure_constraint()
is_present = tracker.is_present()
```

## 性能配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_concurrent_characters` | 50 | 同时在线的最大角色数 |
| `dialogue_fluency_target` | 4.0 | 目标流畅度评分 (1-5) |
| `dialogue_max_rounds` | 50 | 单次对话最大轮数 |
| `context_window_turns` | 50 | 上下文历史保留轮数 |
| `key_info_retention_rate` | 0.98 | 关键信息遗忘率 (越低越不容易忘) |

## 使用示例：动态关系变化

```python
async def relationship_demo():
    engine = LuqiEngine()
    await engine.initialize()

    alice = await engine.create_character({"name": "爱丽丝", "template": "scholar"})
    bob = await engine.create_character({"name": "鲍勃", "template": "merchant"})

    # 第一次对话 - 初次见面
    result1 = await engine.start_dialogue(
        participants=[alice, bob],
        topic="自我介绍",
        max_rounds=3,
    )
    print("初次对话完成")

    # 第二次对话 - 关系可能已变化
    result2 = await engine.start_dialogue(
        participants=[alice, bob],
        topic="讨论合作项目",
        max_rounds=5,
    )
    print("后续对话完成")

    await engine.shutdown()
```
