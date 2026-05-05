# Phase 2: 动态动机生成机制

> **版本**: v1.0.0  
> **更新日期**: 2026-05-05  
> **状态**: 已实现

## 概述

动态动机生成机制是角色决策的核心驱动力链，由四个子系统串联组成：

```
OCEAN人格 → PAD情感基线 → 七情PAD更新 → DesireEngine欲望驱动 → GOAP规划 → 效用评分 → 行动执行
```

这套机制的核心理念是：**人格决定情感基线，情感变化触发欲望更新，欲望排序驱动目标选择，GOAP 规划具体行动路径**。整个链条是完全可计算、可量化、可验证的。

## 一、OCEAN 五维人格模型

### 1.1 定义

OCEAN 是心理学中广泛验证的大五人格理论（Big Five），引擎将其量化为 0-100 分制的五维数值：

| 维度 | 英文 | 含义 | 高分倾向 | 低分倾向 |
|------|------|------|----------|----------|
| O | Openness | 开放性 | 好奇心强、喜欢新事物 | 传统保守、偏好熟悉事物 |
| C | Conscientiousness | 尽责性 | 自律有条理、计划周全 | 随性自由、即兴行动 |
| E | Extraversion | 外向性 | 喜欢社交、精力充沛 | 内向安静、独处充电 |
| A | Agreeableness | 宜人性 | 合作友善、避免冲突 | 独立自主、直率坦诚 |
| N | Neuroticism | 神经质 | 情绪敏感、容易焦虑 | 情绪稳定、抗压能力强 |

### 1.2 人格影响决策

当角色需要在不同行动间选择时，`influence_decision()` 方法根据 OCEAN 分数调整各行动的基础权重：

```
modifier = Σ(trait_score - midpoint) × influence_scale × trait_weight
```

各维度的权重系数：

| 维度 | 权重 | 影响的行动类型 |
|------|------|---------------|
| 开放性 | 0.30 | 探索类行动得分放大 |
| 尽责性 | 0.30 | 计划类行动得分放大 |
| 外向性 | 0.30 | 社交类行动得分放大 |
| 宜人性 | 0.30 | 合作类行动得分放大 |
| 神经质 | 0.25 | 危险规避类行动得分放大（负向） |

**计算示例**：一个外向性=80的角色，社交类行动的基础权重会额外增加 `(80-50)×0.02×0.30=0.18` 分。

### 1.3 人格漂移

PersonalityAdapter 允许人格随经历缓慢演化：

```
new_score = clamp(old_score + delta × adaptation_rate)
```

- adaptation_rate 默认 0.02（每次最大漂移 2%）
- 漂移范围限制在 [0, 100]
- 这是渐进过程，不会突变

## 二、PAD 三维情感空间

### 2.1 定义

所有情感最终归约到三个连续轴上：

| 轴 | 英文 | 范围 | 含义 |
|----|------|------|------|
| Pleasure | 愉悦度 | [-1, +1] | 正面↔负面感受 |
| Arousal | 激活度 | [-1, +1] | 平静↔激动 |
| Dominance | 支配感 | [-1, +1] | 被动↔掌控 |

### 2.2 七情→PAD 映射

引擎定义七种基础情绪，每种有固定的 PAD 向量：

| 情绪 | P | A | D | 直觉 |
|------|---|---|---|------|
| 喜(Joy) | +0.6 | +0.5 | +0.3 | 开心、有活力、略主动 |
| 怒(Anger) | -0.6 | +0.7 | +0.4 | 不爽、很激动、想对抗 |
| 悲(Sorrow) | -0.7 | -0.3 | -0.4 | 消沉、低能量、被动 |
| 恐(Fear) | -0.7 | +0.5 | -0.5 | 极度不安、紧张、逃避 |
| 爱(Love) | +0.5 | +0.3 | +0.2 | 温暖、平和、轻微主动 |
| 厌(Disgust) | -0.5 | +0.3 | +0.1 | 不适、有些激动、略抗拒 |
| 欲(Desire) | +0.3 | +0.6 | +0.2 | 期待、兴奋、有点主动 |

此外还有补充情绪：
- 惊(Surprise): (+0.2, +0.6, -0.1) — 意外发现
- 好(Curiosity): (+0.2, +0.3, -0.1) — 探索欲
- 信(Trust): 同 Love 向量 — 信任依赖
- 忧(Sadness): 同 Sorrow 向量 — 忧郁低落
- 焦(Anxiety): 同 Fear 向量 — 焦虑不安
- 盼(Hope): 同 Joy 向量 — 希望

### 2.3 动态更新公式

```
新值 = clamp(旧值 × damping + event_impact × scale)
```

- **damping（阻尼）**: 默认 0.85，每次更新保留 85% 的旧状态
- **scale（缩放因子）**: 默认 1.0，控制事件冲击强度
- **clamp**: 结果钳位到 [-1, +1]

这意味着情感变化是**平滑过渡**而非瞬间跳变，模拟真实人类情绪惯性。

### 2.4 扩展 PAD (ExtendedPAD)

ExtendedPAD 在基础 PAD 上增加**七情交叉影响矩阵**——一种情绪的强度通过权重矩阵间接增强或抑制其他情绪的表现力。

## 三、OCEAN → PAD 基线映射

基于 Mehrabian (1996) "Pleasure-Arousal-Dominance Temperament Model" 的实证相关系数：

### 完整 5×3 权重矩阵

**Pleasure（愉悦度）权重：**

| OCEAN维度 | 权重 | 解释 |
|-----------|------|------|
| 外向性(E) | +0.21 | 外向的人更愉悦 |
| 宜人性(A) | +0.25 | 宜人的人更正面 |
| 神经质(N) | -0.26 | 神经质的人更容易消极 |
| 尽责性(C) | +0.12 | 自律带来轻微正向 |
| 开放性(O) | +0.08 | 影响较小 |

**Arousal（激活度）权重：**

| OCEAN维度 | 权重 | 解释 |
|-----------|------|------|
| 外向性(E) | +0.15 | 外向的人更活跃 |
| 神经质(N) | +0.20 | 焦虑带来高激活 |
| 开放性(O) | +0.18 | 新奇刺激提升激活 |
| 宜人性(A) | -0.05 | 和平型略偏平静 |
| 尽责性(C) | +0.05 | 影响较小 |

**Dominance（支配感）权重：**

| OCEAN维度 | 权重 | 解释 |
|-----------|------|------|
| 外向性(E) | +0.30 | 外向的人更主动掌控 |
| 尽责性(C) | +0.15 | 计划者更有主导性 |
| 宜人性(A) | -0.12 | 合作者略退让 |
| 神经质(N) | -0.22 | 焦虑降低掌控感 |
| 开放性(O) | +0.05 | 影响较小 |

**映射流程**：
1. OCEAN 分数（0-100）归一化到 (-1, +1)：`(score - 50) / 50`
2. 各维度加权求和得到 P/A/D 三个值
3. 最终钳位到 [-1, +1]

这就是角色的**情感基线**——没有任何外部刺激时的默认心情状态。

## 四、DesireEngine 欲望驱动引擎

### 4.1 核心：情感→欲望映射

DesireEngine 的核心是将情感变化转化为欲望向量的增量更新：

```
desire_delta = emotion_value × dim_weight × update_scale × value_weight × satiation_factor
```

**情感→欲望映射矩阵**（EMOTION_DESIRE_MAP）：

| 情感 | 受影响的欲望维度及权重 |
|------|----------------------|
| 喜(joy) | belonging(+0.6), self_actualization(+0.4), esteem(+0.2) |
| 恐(fear) | safety(+0.8), physiological(+0.3) |
| 悲(sorrow) | esteem(+0.5), belonging(+0.4), safety(+0.2) |
| 怒(anger) | esteem(+0.6), safety(+0.3), self_actualization(+0.1) |
| 爱(love) | belonging(+0.7), relatedness(+0.5), physiological(+0.1) |
| 欲(desire) | physiological(+0.6), touch(+0.3), taste(+0.2) |
| 厌(disgust) | safety(+0.4), orientation(+0.3) |
| 信(trust) | relatedness(+0.5), belonging(+0.3) |
| 惊(surprise) | orientation(+0.5), mind(+0.3) |
| 忧(sadness) | esteem(+0.4), belonging(+0.5), rootedness(+0.2) |
| 焦(anxiety) | safety(+0.6), orientation(+0.4) |
| 盼(hope) | self_actualization(+0.6), self_transcendence(+0.3) |
| 好(curiosity) | mind(+0.5), sight(+0.3), hearing(+0.2) |

### 4.2 饱和度机制

每个欲望维度有一个独立的**饱和度值**（satiation），模拟生理/心理满足感：

- 当欲望被满足时，饱和度增加（`apply_satiation()`）
- 饱和度随时间自然衰减（`decay_satiation()`，衰减率 0.01/次）
- **未满足的欲望驱动力更强**：`urgency = desire_val × (MAX_SATIATION - satiation_val)`
- 已高度满足的欲望几乎不再驱动行为

### 4.3 驱动链排序

`compute_drive_chain()` 将所有欲望维度按紧迫度排序：

```
priority = urgency × value_system_weight
```

输出为有序的目标列表（drive_chain），包含 goal/priority/urgency/desire_name/strength 五个字段。排在最前面的是**主导欲望**（dominant_desire），它将决定 GOAP 规划的目标方向。

### 4.4 溢出效应

即使某个情感没有直接的欲望映射，其总强度也会通过**溢出分数**（spillover）微弱地影响所有未直接映射的维度：

```
spillover_base = 0.05 × total_emotion_intensity × update_scale
```

这保证了任何情感波动都会产生某种程度的欲望响应，只是强度不同。

## 五、GOAP 目标导向行动规划

### 5.1 GOAPWorldState

世界状态表示为键值对字典 `Dict[str, Any]`，支持任意类型的值（布尔、数值、字符串、嵌套字典）：

```python
state = GOAPWorldState(data={"threat_avoided": True, "is_alone": False})
state.get("threat_avoided")  # True
state.set("conversation_started", True)
new_state = state.apply({"has_memory": True})  # 返回新状态，不可变风格
state.satisfies(GOAPWorldState(data={"threat_avoided": True}))  # True
```

### 5.2 GOAPAction

行动定义了前置条件和效果：

```python
action = GOAPAction(
    name="talk_to_player",
    preconditions={"is_alone": False},
    effects={"conversation_started": True},
    cost=1.0,
)
action.is_valid(current_state)  # 检查前置条件是否满足
next_state = action.execute(current_state)  # 应用效果
```

### 5.3 A\* 规划器

使用标准 A\* 算法搜索从起始状态到目标状态的最优行动序列：

- 启发式函数：`h(state, goal) = unsatisfied_count(goal)`（未满足的条件数）
- 最大搜索节点数：1000（防止无限循环）
- 复杂度：O(n log n)，n 为搜索树大小

### 5.4 GOAPGoalSelector — 从PAD/OCEAN自动选目标

这是动机链到行动规划的桥梁。根据当前的 PAD 情感和 OCEAN 人格自动选择 GOAP 目标：

| 条件 | 选择的目标 | 含义 |
|------|-----------|------|
| pleasure < -0.3 | safety (威胁已避免 + 情况已评估) | 负面情感高 → 优先安全 |
| arousal > 0.5 且 pleasure > 0.2 | social (对话开始 + 不孤单) | 高激活+愉悦 → 寻求社交 |
| arousal > 0.4 且 pleasure ≤ 0 | expression (对话开始 + 不孤单) | 高激活+中性 → 表达需求 |
| pleasure > 0.3 | growth (情况已评估 + 记忆反思) | 正面情感 → 成长探索 |
| openness > 65 | reflection (记忆反思 + 有记忆) | 高开放性 → 内省 |
| extraversion > 60 | social (对话开始 + 不孤单) | 高外向性 → 社交互动 |
| 默认 | comfort (情况已评估 + 不孤单) | 默认舒适目标 |

## 六、完整数据流

```
外部事件
    ↓
PAD情感更新（阻尼0.85）
    ↓
DesireEngine.update_desires()
    ├── 有直接映射 → 定向更新对应欲望维度
    └── 无直接映射 → 溢出效应微弱影响全部维度
    ↓
DesireEngine.compute_drive_chain()
    ├── urgency = desire_val × (max_sat - satiation)
    ├── priority = urgency × value_weight
    └── 排序 → dominant_desire
    ↓
GOAPGoalSelector.select_goal(pad, ocean)
    ├── 根据 PAD/OCEAN 阈值匹配预设目标
    └── 返回 GOAPWorldState 目标
    ↓
GOAPPlanner.plan(start_state, goal_state)
    ├── A* 搜索最优行动序列
    └── 返回 List[GOAPAction]
    ↓
效用评分 + OCEAN人格修正 + CEM熵扰动
    ↓
一致性验证（人格40% + 情感30% + 记忆30%，阈值≥95%）
    ↓
行动执行
```
