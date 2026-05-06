# 交互系统 (Interaction)

多角色对话协调、社交关系建模和用户在场追踪。

> **v1.3.0 更新**: 新增 `UserPresenceTracker`，`TurnScheduler` 概率权重可配置。

## 模块概览

```
luqi_engine/interaction/
├── coordinator.py         — InteractionCoordinator 多角色交互协调器
├── turn_scheduler.py      — TurnScheduler 概率型轮次调度器
└── user_tracker.py        — UserPresenceTracker 用户在场追踪
```

## InteractionCoordinator — 交互协调器

```python
class InteractionCoordinator:
    """多角色对话的完整协调

    功能:
    - 参与者管理: 注册/移除/查询活跃角色
    - 轮次调度: 委托 TurnScheduler 选择发言者
    - 关系更新: 对话后自动更新关系状态
    - 流畅度监控: 实时计算对话流畅度评分
    """

    def __init__(self, config: InteractionConfig) -> None: ...

    async def run_dialogue_round(
        self,
        participants: List[EntityId],
        context: DialogueContext,
    ) -> DialogueRoundResult:
        """执行一轮多角色对话"""

    def get_relationship(self, a_id: EntityId, b_id: EntityId) -> RelationshipState: ...
```

## TurnScheduler — 轮次调度器

```python
class TurnScheduler:
    """概率型轮次调度器

    6种轮次类型及默认权重:
    | 类型 | 权重 | 说明 |
    |------|------|------|
    | main_char | 0.35 | 主要角色发言 |
    | secondary_char | 0.15 | 次要角色发言 |
    | user | 0.15 | 用户插入机会 |
    | atmosphere | 0.05 | 氛围描写 |
    | silence | 0.10 | 沉默/间歇 |
    | reaction | 0.20 | 微反应（嗯…/点头） |

    特殊机制:
    - 用户被@时强制插入机会
    - 用户缺席>10轮获得+0.10加成
    - 连续>5轮对话强制用户机会
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None: ...

    def select_speaker(
        self,
        candidates: List[EntityId],
        round_num: int,
        user_addressed: bool = False,
        user_absent_rounds: int = 0,
    ) -> Tuple[EntityId, str]:
        """返回 (speaker_id, turn_type)"""
```

## UserPresenceTracker — 用户在场追踪

```python
class UserPresenceTracker:
    """追踪用户在多角色对话中的在场状态

    状态转换:
      ABSENT → PRESENT (arrive())
      PRESENT → ABSENT (depart())

    约束输出:
    - get_departure_constraint(): 返回用户缺席后的行为约束
    - is_present(): 当前是否在场
    """

    def __init__(self) -> None: ...
    def arrive(self, round_num: int) -> None: ...
    def depart(self, round_num: int) -> None: ...
    def is_present(self) -> bool: ...
    def get_departure_constraint(self) -> DepartureConstraint: ...
```

## 社交关系模型

| 维度 | 范围 | 说明 |
|------|------|------|
| friendship | [-1, 1] | 亲密程度 |
| trust | [-1, 1] | 可信赖程度 |
| hostility | [0, 1] | 冲突倾向 |
| respect | [-1, 1] | 地位认同 |

关系影响:
- **发言优先级**: 高友谊/信任→更高优先级
- **回应风格**: 关系好→友好语气
- **合作概率**: 高信任→增加合作
- **冲突可能**: 高敌意→增加争执概率

## 对话流程

```
[开始] → [确定参与者] → [TurnScheduler选发言者] → [生成回复]
                                              ↓
                                      [更新关系状态]
                                              ↓
                                      [检查继续?]
                                         /     \
                                       [是]   [否]
                                        ↓       ↓
                                    [下一轮] [结束]
```

## 性能配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_concurrent_characters` | 50 | 最大同时在线角色数 |
| `dialogue_fluency_target` | 4.0 | 流畅度目标 (1-5分) |
| `dialogue_max_rounds` | 50 | 最大对话轮数 |
| `context_window_turns` | 50 | 上下文窗口轮数 |
| `key_info_retention_rate` | 0.98 | 关键信息保持率 |
| `social_rules_enabled` | True | 社交规则引擎开关 |

## 相关文档

- [角色系统](character.md) — SocialPerceptionSystem 详细API
- [引擎门面](engine.md) — start_dialogue() 入口说明
