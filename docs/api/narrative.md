# 叙事引擎 (Narrative)

基于10层分支管理、三级回归引导和弹性系数的剧情走向控制系统。

## 模块概览

```
luqi_engine/narrative/
├── controller.py      — NarrativeController 剧情走向控制器 (核心)
├── atmosphere.py      — AtmosphereSubsystem 氛围子系统
└── document.py        — 叙事文档数据结构
```

> **注意**: `luqi_engine.narrative` 是生产版本。`stress_tests.wuxia_war.narrative_engine` 是压力测试专用版本（含武侠特定逻辑），两者API兼容但实现不同。

## 核心数据类型

### NodeType — 节点类型枚举

```python
class NodeType(Enum):
    KEY_EVENT = auto()          # 关键事件节点
    TURNING_POINT = auto()      # 转折点
    ENDING_CONDITION = auto()   # 结局条件
    TRANSITION = auto()         # 过渡节点
```

### RegressionMethod — 回归方法枚举

```python
class RegressionMethod(Enum):
    NATURAL = "natural"              # 自然回归
    EVENT_TRIGGERED = "event_triggered"  # 事件触发回归
    FORCED = "forced"                # 强制回归
```

### StoryNode — 故事节点

```python
@dataclass
class StoryNode:
    """故事节点数据结构"""
    node_id: EntityId
    node_type: NodeType
    name: str
    description: str
    depth: int
    parent_id: Optional[EntityId] = None
    children_ids: List[EntityId] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    core_relevance: float = 0.5           # 核心故事相关性 [0, 1]
    timestamp: float = field(default_factory=time.time)
    branch_state: str = "active"          # active/merged/pruned/dead_end
```

**分支状态**:
| 状态 | 说明 |
|------|------|
| active | 活跃分支，可选择 |
| merged | 已合并到主线 |
| pruned | 已裁剪（放弃此分支） |
| dead_end | 死胡同分支 |

### StoryBranch — 故事分支

```python
@dataclass
class StoryBranch:
    """故事分支数据结构"""
    branch_id: EntityId
    root_node_id: EntityId
    current_node_id: EntityId
    depth: int = 0
    status: str = "active"
    deviation_score: float = 0.0          # 偏离度分数 [0, 1]
    created_at: float = field(default_factory=time.time)
```

### RegressionResult — 回归结果

```python
@dataclass
class RegressionResult:
    """回归操作结果"""
    method: RegressionMethod
    target_node_id: EntityId
    success: bool
    deviation_before: float
    deviation_after: float
    narrative_event: Optional[str] = None
```

## NarrativeConsistencyChecker — 叙事一致性检查器

```python
class NarrativeConsistencyChecker:
    """检测剧情逻辑矛盾、时间线冲突、角色行为不一致

    检查维度:
    1. 时间线一致性: 事件顺序是否矛盾
    2. 因果链完整性: 前置条件是否满足
    3. 角色行为一致性: 是否与已建立的人设矛盾
    4. 世界规则遵守: 是否违反已建立的世界观设定

    置信度计算:
      初始置信度 = 1.0
      每项检查失败乘以对应惩罚因子:
        - 时间线冲突: ×0.7
        - 因果链断裂: ×0.6
        - 角色不一致: ×0.75
        - 世界规则违反: ×0.5
      最终置信度 < 0.5 时判定为不一致
    """

    def check_consistency(
        self,
        story_state: Dict[str, Any],
        proposed_change: Dict[str, Any],
    ) -> Tuple[bool, float, List[str]]:
        """
        返回: (是否一致, 置信度, 问题列表)
        """
```

**惩罚因子表**:

| 检查维度 | 惩罚因子 | 说明 |
|----------|----------|------|
| 时间线 | 0.7 | 事件顺序矛盾 |
| 因果性 | 0.6 | 前置条件未满足 |
| 角色行为 | 0.75 | 与人设矛盾 |
| 世界规则 | 0.65 | 违反世界观 |

## NarrativeController — 剧情走向控制器 ⭐ 核心

```python
class NarrativeController(INarrativeController, ISnapshotable):
    """10层分支管理 + 三级回归引导 + 弹性系数 + 一致性检查

    核心功能:
    - identify_nodes(): 识别当前可达的故事节点
    - compute_branch_weights(): 计算各分支权重（多因素加权）
    - take_branch(): 选择并进入指定分支
    - regress_to_main(): 回归到主线的三种策略

    分支权重计算公式:
      weight = w_core × core_relevance
             + w_character × character_score
             + w_random × random_factor
             + w_elasticity × deviation_bonus

    弹性系数作用:
      - 控制偏离主线的容忍度
      - elasticity高 → 允许更多探索分支
      - elasticity低 → 强制快速回归主线
    """

    def __init__(
        self,
        config: Optional[NarrativeConfig] = None,
        rng: Optional[PCGRandom] = None,
    ) -> None: ...

    async def identify_nodes(
        self, story_state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """识别当前可达的活跃故事节点
        返回按相关性降序排列的节点列表
        """

    async def compute_branch_weights(
        self,
        current_node: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, float]:
        """计算当前节点所有子分支的权重
        返回: {branch_id: weight} 归一化权重字典
        """

    async def take_branch(self, branch_id: str) -> ActionResult:
        """选择并进入指定分支
        会先进行一致性检查
        """

    async def regress_to_main(
        self,
        preferred_method: Optional[RegressionMethod] = None,
    ) -> RegressionResult:
        """回归到主线的三种策略:

        1. NATURAL (自然): 等待角色驱动回归
           - 适用: deviation < 0.7
           - 成功率: 高
           - 代价: 可能需要多轮

        2. EVENT_TRIGGERED (事件触发): 通过事件强制回归
           - 适用: 0.7 ≤ deviation < 0.9
           - 成功率: 中
           - 代价: 需要设计回归事件

        3. FORCED (强制): 直接跳转到主线节点
           - 适用: deviation ≥ 0.9
           - 成功率: 100%
           - 代价: 可能造成叙事断裂
        """

    def get_current_state(self) -> Dict[str, Any]: ...
    def get_branch_tree(self) -> Dict[str, Any]: ...
```

**分支权重配置参数**:

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `branch_weight_core_story` | 0.4 | 核心故事相关性权重 |
| `branch_weight_character_driven` | 0.3 | 角色驱动分数权重 |
| `branch_weight_random_event` | 0.15 | 随机事件权重 |
| `branch_weight_elasticity` | 0.15 | 弹性系数权重 |
| `elasticity_max` | 1.0 | 最大弹性系数 |
| `node_relevance_threshold` | 0.3 | 节点相关性阈值 |

**弹性系数与偏离度关系**:

```
deviation_bonus = max(0, 1 - core_relevance) × (elasticity / elasticity_max) × w_elasticity
```

- 高弹性(0.8-1.0): 鼓励探索，允许大幅偏离
- 中弹性(0.4-0.7): 平衡探索与回归
- 低弹性(0.0-0.3): 强制快速回归主线

## AtmosphereSubsystem — 氛围子系统

```python
class AtmosphereSubsystem:
    """叙事氛围管理

    功能:
    - 计算场景氛围值 (紧张/轻松/神秘/温馨等)
    - 根据剧情阶段调整氛围基调
    - 为LLM prompt生成氛围描述文本
    """

    def compute_atmosphere(self, scene_context: Dict[str, Any]) -> AtmosphereOutput: ...

    def get_atmosphere_prompt_text(self, atmosphere: AtmosphereOutput) -> str: ...
```

## 使用示例

```python
from luqi_engine.narrative.controller import NarrativeController, NodeType, RegressionMethod
from luqi_engine.core.config import NarrativeConfig
from luqi_engine.core.rng import PCGRandom

# 初始化控制器
config = NarrativeConfig(
    max_depth=10,
    elasticity_coefficient=0.6,
)
rng = PCGRandom(seed=42)
controller = NarrativeController(config=config, rng=rng)

# 构建故事树
story_state = {
    "events": ["intro", "conflict_introduced"],
    "flags": {"main_plot_active": True},
    "character_states": {},
}

# 识别可用节点
nodes = await controller.identify_nodes(story_state)
print(f"可用节点数: {len(nodes)}")

# 计算分支权重
if nodes:
    current_node = nodes[0]
    weights = await controller.compute_branch_weights(current_node, story_state)
    print("分支权重:", weights)

    # 选择分支
    best_branch = max(weights.items(), key=lambda x: x[1])[0]
    result = await controller.take_branch(best_branch)
    print(f"选择分支结果: success={result.success}")

# 需要回归时
if controller.get_current_state().get("deviation", 0) > 0.8:
    regression_result = await controller.regress_to_main(RegressionMethod.EVENT_TRIGGERED)
    print(f"回归成功: {regression_result.success}")
    print(f"偏离度变化: {regression_result.deviation_before} → {regression_result.deviation_after}")
```

## 学术引用与技术来源

| 技术/论文 | 应用位置 | 贡献 |
|-----------|----------|------|
| IDTENSION (Szilas 2007) | 分支管理 | 故事节点与分支数据结构 |
| Facade (Mateas & Stern 2005) | 氛围系统 | 氛围计算与prompt生成 |
| C2P (Yu & Riedl 2021) | 角色驱动评分 | character_driven_score计算 |
| 弹性系数理论 | 回归系统 | 偏离度控制与回归策略选择 |
| 叙事一致性理论 | 一致性检查 | 多维度矛盾检测框架 |
