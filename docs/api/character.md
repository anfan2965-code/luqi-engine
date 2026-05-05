# 角色系统 (Character)

角色系统负责管理虚拟角色的创建、性格建模、记忆存储和行为一致性验证。

## 核心组件

::: luqi_engine.character.character_manager
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.character.character_entity
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.character.personality
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.character.emotion
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: luqi_engine.character.memory
    options:
      show_root_heading: true
      show_root_toc_entry: true

## OCEAN 性格模型

角色性格基于**大五人格模型 (OCEAN)** 量化：

| 维度 | 英文 | 说明 | 高分特征 | 低分特征 |
|------|------|------|----------|----------|
| **O** | Openness | 开放性 | 创意、好奇 | 实际、传统 |
| **C** | Conscientiousness | 尽责性 | 有条理、自律 | 随性、灵活 |
| **E** | Extraversion | 外向性 | 社交、活跃 | 内向、独立 |
| **A** | Agreeableness | 宜人性 | 合作、友善 | 竞争、批判 |
| **N** | Neuroticism | 神经质 | 敏感、情绪化 | 稳定、冷静 |

每个维度分数范围：**0-100**

```python
from luqi_engine.character.personality import OceanPersonality

# 创建性格实例
personality = OceanPersonality(
    openness=85,
    conscientiousness=70,
    extraversion=35,
    agreeableness=75,
    neuroticism=55,
)

# 获取分数
score = personality.get_score("openness")  # 85.0

# 动态调整（根据经历微调）
personality.set_score("openness", 88.0)
```

## 角色管理器 (CharacterManager)

### 创建角色

```python
import asyncio
from luqi_engine.engine import LuqiEngine

async def create_characters():
    engine = LuqiEngine()
    await engine.initialize()

    # 方式1: 使用模板创建
    char_id1 = await engine.create_character({
        "name": "守卫A",
        "template": "guard",  # 使用内置模板
        "overrides": {
            "name": "铁壁守卫",
            "personality": {"conscientiousness": 95},
        },
    })

    # 方式2: 完全自定义
    char_id2 = await engine.create_character({
        "name": "自定义角色",
        "personality": {
            "openness": 60,
            "conscientiousness": 50,
            "extraversion": 70,
            "agreeableness": 65,
            "neuroticism": 40,
        },
        "motives": [
            {"motive_id": "exploration", "name": "探索", "layer": 2, "base_intensity": 0.8},
        ],
        "background": "来自远方的旅行者",
    })

    return char_id1, char_id2
```

### 内置 NPC 模板

引擎提供 6 种预定义模板：

| 模板名 | 类型 | 典型特征 |
|--------|------|----------|
| `guard` | 守卫 | 高尽责性、秩序感强、职责驱动 |
| `merchant` | 商人 | 高外向性、利润导向、社交能力强 |
| `scholar` | 学者 | 高开放性、求知欲强、内向 |
| `warrior` | 战士 | 中高外向性、战斗动机、荣誉感 |
| `mage` | 法师 | 极高开放性、神秘感、知识驱动 |
| `assassin` | 刺客 | 高尽责性、隐匿动机、谨慎 |

### 查询角色信息

```python
# 获取角色实体
character = engine.character_manager.get_character(char_id)
print(character.name)           # 角色名称
print(character.entity_id)      # 唯一ID

# 获取性格量化值
personality = await engine.character_manager.get_personality(char_id)
print(personality)
# {'openness': 85.0, 'conscientiousness': 70.0, ...}

# 列出所有角色
all_chars = engine.character_manager.list_characters()
print(f"当前有 {len(all_chars)} 个角色")
```

## 记忆系统

角色具备**分层记忆**能力：

```python
# 存储记忆
await engine.character_manager.store_memory(
    character_id=char_id,
    memory_type="short_term",
    content={
        "who": "玩家",
        "what": "送了我一本书",
        "when": time.time(),
        "where": "图书馆",
        "why": "作为礼物",
        "emotional_valence": 0.8,  # 正面情感 -1~1
    },
)

# 检索相关记忆
memories = await engine.character_manager.retrieve_memories(
    character_id=char_id,
    query="书 礼物",
    limit=5,
)
for mem in memories:
    print(f"{mem['who']}: {mem['what']}")
```

### 记忆类型

| 类型 | 枚举值 | 说明 | 容量 | 保持时间 |
|------|--------|------|------|----------|
| `MemoryType.SHORT_TERM` | `"short_term"` | 短期记忆 | 100条 | 数小时~数天 |
| `MemoryType.LONG_TERM` | `"long_term"` | 长期记忆 | 10000条 | 永久 |
| `MemoryType.EMOTIONAL` | `"emotional"` | 情绪记忆 | 500条 | 情感关联 |

> **注意**: `memory_type` 参数应使用 `MemoryType` 枚举（如 `MemoryType.SHORT_TERM`），而非直接传入字符串字面量。`MemoryType` 为 `str, Enum` 类型，可直接与字符串比较。

## 行为一致性验证

确保角色行为符合其性格设定：

```python
is_consistent, score = await engine.character_manager.validate_behavior_consistency(
    character_id=char_id,
    proposed_action={
        "action": "attack",
        "target": "innocent_person",
    },
)

if is_consistent:
    print(f"行为一致 (置信度: {score:.2f})")
else:
    print(f"行为可能不一致 (置信度: {score:.2f})")
    # 对于高宜人性的角色，攻击无辜者是不一致的
```

## 动机系统

角色行为由**多层动机**驱动：

```python
from luqi_engine.character.character_entity import Motive, MotivationEngine

engine = MotivationEngine()

# 添加动机
engine.add_motive(Motive(
    motive_id="knowledge",
    name="求知",
    layer=3,  # 层级: 1=生存, 2=社交, 3=自我实现
    base_intensity=0.9,  # 基础强度 0-1
    urgency_curve="sigmoid",  # 紧急程度曲线
))

# 获取当前主导动机
dominant = engine.get_dominant_motive()
print(f"当前主导动机: {dominant.name} (强度: {dominant.current_intensity})")
```

## PAD 情感模型

角色情感状态使用 **PAD三维模型** 表示：

| 维度 | 范围 | 说明 |
|------|------|------|
| **Pleasure** | -1 ~ 1 | 愉悦度（正/负面情绪） |
| **Arousal** | -1 ~ 1 | 唤醒度（平静/激动） |
| **Dominance** | -1 ~ 1 | 支配度（顺从/控制） |

```python
character = engine.character_manager.get_character(char_id)

# 当前情感状态
print(f"愉悦度: {character.emotion.pleasure:.2f}")
print(f"唤醒度: {character.emotion.arousal:.2f}")
print(f"支配度: {character.emotion.dominance:.2f}")

# 情感会随对话和事件动态变化
```

## 决策管线 (Decision Pipeline)

角色决策采用**多层级管线架构**，从动机到行动经过6个阶段：

```
动机排序 → 欲望驱动链 → GOAP目标选择 → IAUS效用评估 → CEM行为选择 → 性格/情感修正
```

### GOAP 目标选择器 (GOAPGoalSelector)

根据PAD/OCEAN状态自动选择GOAP目标世界状态：

| PAD条件 | 目标状态 |
|---------|---------|
| pleasure < -0.3 | threat_avoided + situation_assessed |
| arousal > 0.5 & pleasure > 0.2 | conversation_started + is_alone=False |
| arousal > 0.4 & pleasure < 0 | conversation_started + is_alone=False |
| pleasure > 0.3 | situation_assessed + memory_reflected |
| openness > 65 | memory_reflected + has_memory |
| extraversion > 60 | conversation_started + is_alone=False |

### 效用评估 (UtilityBasedAI)

基于IAUS架构的效用评估，Consideration的input_fn自动绑定PAD/OCEAN运行时值。

### 默认行为 (DefaultBehaviors)

引擎预置5种默认行为选项：

| 行为 | 说明 |
|------|------|
| socialize | 社交互动 |
| express | 情感表达 |
| observe | 观察环境 |
| reminisce | 回忆往事 |
| depart | 离开场景 |

## 欲望引擎 (DesireEngine)

欲望引擎通过 `EMOTION_DESIRE_MAP` 将13种情感映射到特定欲望维度，实现情感驱动的欲望更新。

### 情感-欲望映射

| 情感 | 目标欲望维度 | 权重 |
|------|-------------|------|
| joy | self_actualization | 0.3 |
| anger | esteem | 0.5 |
| sorrow | belonging | 0.6 |
| fear | safety | 0.8 |
| love | belonging | 0.7 |
| disgust | safety | 0.4 |
| desire | esteem | 0.5 |
| anxiety | safety | 0.7 |
| surprise | self_actualization | 0.2 |
| trust | belonging | 0.4 |
| hope | self_actualization | 0.5 |
| curiosity | self_actualization | 0.6 |

## 轻量角色 (LightCharacter)

用于次要角色的轻量级数据结构，仅保留名称、性格摘要和叙事角色权重：

```python
from luqi_engine.character.light_character import LightCharacter

light = LightCharacter(
    name="路人甲",
    personality_summary="普通市民，性格温和",
    narrative_role=0.3,
)
```
