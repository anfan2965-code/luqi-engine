# 世界观系统 (WorldView)

从非结构化文本中提取世界元素、构建关系、检测冲突并生成叙事指导。

> **v1.3.0 更新**: 分类体系从8类扩展为9+1维（geography/society/culture/history/magic_system/technology/politics/religion/ecology + unclassified）。支持ISnapshotable接口。

## 模块概览

```
luqi_engine/worldview/
└── renderer.py            — WorldViewRenderer 主渲染器 (IWorldViewRenderer + ISnapshotable)
```

## 处理管道

```
原始输入(text/markdown/json/image_desc/csv)
    → [1] extract_elements() → 结构化元素列表 (Dict)
    → [2] classify_elements() → 按维度分组 (9维分类)
    → [3] [内部] 关系构建 → 语义关系图
    → [4] [内部] 冲突检测 → 冲突报告列表
    → [5] [内部] 引导渲染 → LLM上下文指导文本
```

## WorldViewRenderer — 主渲染器

```python
class WorldViewRenderer(IWorldViewRenderer, ISnapshotable):
    """世界观渲染引导器

    实现双接口:
    - IWorldViewRenderer: 世界观渲染核心功能
    - ISnapshotable: 快照保存/恢复能力

    支持的内容类型:
    - text: 纯文本
    - markdown: Markdown格式
    - json: JSON数据
    - image_desc: 图像描述
    - csv: 表格数据

    分类维度 (9+1维):
    - geography: 地理（地形/山脉/河流/海洋/城市/气候）
    - society: 社会（阶级/组织/公会/家族/人口/职业）
    - culture: 文化（语言/艺术/节日/习俗/传统/信仰）
    - history: 历史（战争/纪元/朝代/事件/传说）
    - magic_system: 魔法系统（魔法/法术/咒语/魔力/元素/符文/炼金）
    - technology: 科技（科技/机械/工程/发明/武器/工具）
    - politics: 政治（政治/王国/帝国/联盟/条约/权力/统治）
    - religion: 宗教（宗教/神/神殿/祭祀/信仰/教派/神谕）
    - ecology: 生态（生态/生物/怪物/植物/动物/物种）
    - unclassified: 未分类
    """

    def __init__(self) -> None:
        """初始化世界观渲染器"""

    async def extract_elements(
        self,
        raw_content: str,
        content_type: str = "text",
    ) -> Dict[str, Any]:
        """从原始内容中提取世界元素

        Args:
            raw_content: 原始文本内容
            content_type: 内容类型 (text/markdown/json/csv)
        Returns:
            Dict 包含 elements 列表
        """

    async def classify_elements(
        self,
        elements: Dict[str, Any],
    ) -> Dict[str, List[Dict]]:
        """将提取的元素分类到9个标准维度

        Args:
            elements: Dict 包含 elements 列表
        Returns:
            Dict 按9维度分组的元素列表 + unclassified
        """
```

## 元素分类体系

**9+1维分类系统（基于关键词匹配 + Jaccard相似度）**:

| 维度 | 关键词示例 (中文/英文) |
|------|------------------------|
| geography | 地形/山脉/河流/海洋/城市/地图/地理/大陆/岛屿/气候, mountain/river/ocean/city/map |
| society | 社会/阶级/组织/公会/家族/部落/人口/职业, society/class/guild/clan |
| culture | 文化/语言/艺术/节日/习俗/传统/信仰, culture/language/art/festival |
| history | 历史/战争/纪元/朝代/事件/传说/过去, history/war/era/dynasty |
| magic_system | 魔法/法术/咒语/魔力/元素/符文/炼金, magic/spell/mana/rune |
| technology | 科技/机械/工程/发明/武器/工具, technology/machine/weapon |
| politics | 政治/王国/帝国/联盟/条约/权力/统治, politics/kingdom/empire |
| religion | 宗教/神/神殿/祭祀/信仰/教派/神谕, religion/god/temple |
| ecology | 生态/生物/怪物/植物/动物/物种, ecology/creature/monster |
| unclassified | 无法归类的元素 |

**分类算法**: 基于关键词匹配，使用Jaccard相似度选择最佳维度
- 强相关阈值: 0.3
- 中等相关阈值: 0.1
- 弱相关阈值: 0.05

## 关系类型

| 关系类型 | 说明 | 示例 |
|----------|------|------|
| contains | 包含 | 王国→包含→人类 |
| powers | 驱动/赋能 | 以太→驱动→魔法 |
| opposes | 对立 | 光明→对立→黑暗 |
| allies | 同盟 | A国→同盟→B国 |
| part_of | 组成部分 | 骑士团→part_of→王国 |
| causes | 因果关系 | 战争→causes→难民潮 |

## 冲突检测

**3种内置冲突模式（基于正则/规则检测）**:

| 类型 | 说明 | 检测方法 |
|------|------|----------|
| temporal | 时间线矛盾 | temporal_conflict 规则 |
| causal | 因果逻辑矛盾 | causal_conflict 规则 |
| attribute | 属性冲突 | attribute_conflict 规则 |

**关系权重系统**:
| 权重级别 | 值 | 说明 |
|----------|-----|------|
| 强关系 | 0.8 | 明确的包含/驱动关系 |
| 中等关系 | 0.5 | 一般关联 |
| 弱关系 | 0.2 | 微弱联系 |

```python
@dataclass
class ConflictReport:
    conflict_id: str
    conflict_type: str           # 冲突类型 (temporal/causal/attribute)
    description: str             # 问题描述
    severity: float              # 严重度 [0,1]，默认0.8
    involved_elements: List[str] # 涉及的元素ID
    suggested_resolutions: List[str]  # 修复建议（可选）
```

## 配置参数

WorldViewRenderer 无需外部配置，所有参数内部硬编码：

| 参数 | 值 | 说明 |
|------|-----|------|
| `_RENDER_ITEMS_PER_DIMENSION` | 10 | 每维度最大渲染项数 |
| `_RENDER_MAX_SOURCES` | 20 | 最大源数量 |
| `_RENDER_TARGETS_PER_SOURCE` | 3 | 每源最大目标数 |
| `_JACCARD_STRONG_THRESHOLD` | 0.3 | Jaccard强相关阈值 |
| `_JACCARD_MEDIUM_THRESHOLD` | 0.1 | Jaccard中等相关阈值 |
| `_JACCARD_WEAK_THRESHOLD` | 0.05 | Jaccard弱相关阈值 |
| `_CONFLICT_SEVERITY_DEFAULT` | 0.8 | 默认冲突严重度 |

## 使用示例

```python
import asyncio
from luqi_engine.engine import LuqiEngine

async def create_world():
    async with LuqiEngine() as engine:
        result = await engine.create_world("""
            这是一个名为"艾尔德兰"的奇幻世界。
            主要种族包括人类、精灵和矮人。
            魔法由一种叫做"以太"的能量驱动。
        """, content_type="text")

        print(f"提取到 {len(result['elements'])} 个世界元素")
        print(f"发现 {len(result['conflicts'])} 个冲突")
        if result.get('guidance'):
            print(result['guidance'][:300])

asyncio.run(create_world())
```
