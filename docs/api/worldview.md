# 世界观系统 (WorldView)

世界观系统负责从用户输入中提取世界元素、构建元素关系、检测冲突并生成叙事指导。

## 核心组件

::: luqi_engine.worldview.renderer
    options:
      show_root_heading: true
      show_root_toc_entry: true

## 世界创建流程

```python
import asyncio
from luqi_engine.engine import LuqiEngine

async def create_world():
    engine = LuqiEngine()
    await engine.initialize()

    # 从文本输入创建世界观
    world_data = await engine.create_world(
        raw_content="""
        这是一个名为"艾尔德兰"的奇幻世界。
        主要种族包括人类、精灵和矮人。
        魔法由一种叫做"以太"的能量驱动。
        世界被分为五个王国，每个王国由不同的元素守护。
        """,
        content_type="text",
    )

    print(f"提取到 {len(world_data['elements'])} 个世界元素")
    print(f"分类结果: {len(world_data['classified'])} 类")
    print(f"发现 {len(world_data['relations'])} 条关系")
    print(f"检测到 {len(world_data['conflicts'])} 个潜在冲突")

    if world_data.get('guidance'):
        print("\n生成的叙事指导:")
        print(world_data['guidance'][:500])

    await engine.shutdown()

asyncio.run(create_world())
```

## 处理管道

世界观渲染采用**多阶段处理管道**：

```
原始输入 → 元素提取 → 元素分类 → 关系构建 → 冲突检测 → 指导生成
                ↓           ↓          ↓           ↓          ↓
          [NLP/规则]   [类型标签]  [语义关联]  [逻辑检查]  [模板填充]
```

### 1. 元素提取 (Element Extraction)

从非结构化文本中提取结构化的世界元素：

**支持的内容类型**：
- `text`: 纯文本
- `markdown`: Markdown 格式
- `json`: JSON 数据
- `image_desc`: 图像描述
- `csv`: 表格数据

**提取精度**: ~90% (可配置)

### 2. 元素分类 (Element Classification)

自动将提取的元素归类为预定义类型：

| 类型 | 说明 | 示例 |
|------|------|------|
| `location` | 地理位置 | 城市、山脉、森林 |
| `character` | 角色/种族 | 人类、精灵、神明 |
| `organization` | 组织/势力 | 王国、公会、教会 |
| `concept` | 抽象概念 | 魔法系统、信仰 |
| `item` | 物品/神器 | 武器、圣物 |
| `event` | 历史事件 | 战争、灾难、条约 |
| `rule` | 世界法则 | 物理定律、社会规则 |

### 3. 关系构建 (Relation Building)

分析元素之间的语义关系：

```python
# 关系示例
relations = [
    {
        "source": "艾尔德兰",
        "target": "人类",
        "relation_type": "contains",
        "confidence": 0.95,
    },
    {
        "source": "以太",
        "target": "魔法",
        "relation_type": "powers",
        "confidence": 0.92,
    },
]
```

**关系类型**：
- contains (包含)
- powers (驱动/赋能)
- opposes (对立)
- allies (同盟)
- part_of (组成部分)
- causes (因果关系)

### 4. 冲突检测 (Conflict Detection)

自动识别世界观中的逻辑矛盾或不一致：

**检测精度**: ~95%

**常见冲突类型**：
- 时间线矛盾 (同一事件有两个不同时间)
- 属性矛盾 (一个实体同时具有互斥属性)
- 层级错误 (子概念被定义为父概念的父级)
- 循环依赖 (A→B→C→A 的因果链)

**冲突严重级别**：
| 级别 | 说明 | 建议 |
|------|------|------|
| `info` | 信息缺失 | 补充细节 |
| `warning` | 轻微不一致 | 可以接受 |
| `error` | 明显矛盾 | 需要修正 |
| `critical` | 严重冲突 | 必须解决 |

### 5. 冲突解决建议

当检测到冲突时，系统提供修改建议：

```python
conflicts = world_data["conflicts"]
for conflict in conflicts:
    print(f"冲突 ID: {conflict.conflict_id}")
    print(f"类型: {conflict.conflict_type}")
    print(f"描述: {conflict.description}")
    print(f"严重度: {conflict.severity}")
    print("建议解决方案:")
    for suggestion in conflict.suggested_resolutions:
        print(f"  - {suggestion}")
```

### 6. 叙事指导生成 (Guidance Rendering)

基于处理后的世界数据，生成用于 LLM 上下文的指导文本：

```python
guidance = world_data["guidance"]
"""
【世界观设定】
世界名称: 艾尔德兰
主要种族: 人类、精灵、矮人
能量体系: 以太魔法
政治格局: 五元素王国

【叙事约束】
- 魔法需要通过仪式或天赋才能使用
- 各王国之间既有竞争也有合作
- 古代遗迹中隐藏着失传的知识

【一致性要求】
- 提及魔法时需说明其来源或表现形式
- 角色行为应符合其所属种族的文化特征
"""
```

## 配置参数

```python
from luqi_engine.core.config import WorldViewConfig

config = WorldViewConfig(
    conflict_detection_accuracy=0.95,       # 冲突检测精度
    element_extraction_accuracy=0.90,       # 元素提取精度
    relation_depth_limit=5,                 # 关系推理最大深度
    supported_content_types=[
        "text", "markdown", "json", "image_desc", "csv"
    ],
)
```

## 最佳实践

### 输入质量建议

✅ **推荐做法**：
- 使用清晰的结构化语言
- 明确区分事实和假设
- 提供足够的背景信息
- 保持内部一致性

❌ **避免**：
- 过于模糊的描述
- 自相矛盾的设定
- 缺少关键定义
- 过于复杂的嵌套关系

### 迭式完善

```python
# 第一次：粗略框架
world_v1 = await engine.create_world("一个有龙的奇幻世界")

# 根据反馈补充细节
world_v2 = await engine.create_world("""
之前的设定基础上补充：
- 龙分为五种元素属性
- 人类与龙族曾有过战争
- 现在处于和平共处时期
""")
```
