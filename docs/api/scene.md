# 场景系统 (Scene)

场景构建、环境模拟与空间冲突检测，支持马尔可夫链天气系统、Sweep-and-Prune空间检测和结构化感知类型。

## 模块概览

```
luqi_engine/scene/
├── builder.py           — SceneBuilder 场景构建器 (ISceneBuilder接口实现)
└── awareness_types.py   — 结构化场景感知类型定义
```

## 核心枚举类型

### WeatherState — 天气状态

```python
class WeatherState(Enum):
    CLEAR = 0     # 晴朗
    CLOUDY = 1    # 多云
    RAINY = 2     # 下雨
    STORMY = 3    # 暴风雨
    SNOWY = 4     # 下雪
    FOGGY = 5     # 雾
```

### ElementCategory — 元素类别

```python
class ElementCategory(Enum):
    NATURAL = auto()       # 自然元素 (树木/岩石/水源)
    ARTIFICIAL = auto()    # 人造元素 (建筑/家具)
    INTERACTIVE = auto()   # 可交互元素 (机关/传送门)
```

### AreaType — 区域分类

```python
class AreaType(Enum):
    OUTDOOR_OPEN = auto()        # 开阔户外 (广场/平原)
    OUTDOOR_SEMI_OPEN = auto()   # 半开放户外 (走廊/凉亭)
    INDOOR_PUBLIC = auto()       # 公共室内 (大厅/集市)
    INDOOR_SEMI_PUBLIC = auto()  # 半公共室内 (茶楼/客栈大堂)
    INDOOR_PRIVATE = auto()      # 私密室内 (房间/书房)
    INDOOR_SECRET = auto()       # 隐秘室内 (密室/地下室)
```

### AmbientAttribute — 环境属性维度

```python
class AmbientAttribute(Enum):
    LIGHTING = auto()      # 光照: 0=黑暗, 1=明亮
    NOISE_LEVEL = auto()   # 噪音: 0=安静, 1=嘈杂
    CROWDING = auto()      # 拥挤: 0=空旷, 1=拥挤
    TEMPERATURE = auto()   # 温度: 0=寒冷, 1=炎热
    SAFETY = auto()        # 安全: 0=危险, 1=安全
```

### SpatialRelationType — 空间关系

```python
class SpatialRelationType(Enum):
    NEARBY = "nearby"       # 附近
    ADJACENT = "adjacent"   # 相邻
    OPPOSITE = "opposite"   # 对面
    ABOVE = "above"         # 上方
    BELOW = "below"         # 下方
    FAR = "far"             # 远处
    HIDDEN = "hidden"       # 隐藏 (视线外)
```

## 核心数据类

### SceneElement — 场景元素

```python
@dataclass
class SceneElement:
    """场景内元素的基础数据结构"""
    element_id: EntityId
    name: str
    category: ElementCategory
    position: Vector3
    bounding_box: BoundingBox
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### SceneEnvironment — 场景环境

```python
@dataclass
class SceneEnvironment:
    """场景环境状态容器"""
    weather: WeatherState = WeatherState.CLEAR
    temperature: float = 20.0        # 摄氏度
    ambient_state: AmbientState = field(default_factory=AmbientState)
    time_of_day: str = "noon"
    effects: Dict[str, float] = field(default_factory=dict)
```

### AmbientState — 环境属性状态

```python
@dataclass
class AmbientState:
    """多维环境属性容器

    每个属性值范围 [0, 1]:
    - LIGHTING: 黑暗 ↔ 明亮
    - NOISE_LEVEL: 安静 ↔ 嘈杂
    - CROWDING: 空旷 ↔ 拥挤
    - TEMPERATURE: 寒冷 ↔ 炎热
    - SAFETY: 危险 ↔ 安全
    """

    RANGE_MIN: ClassVar[float] = 0.0
    RANGE_MAX: ClassVar[float] = 1.0
    values: Dict[AmbientAttribute, float] = field(default_factory=dict)

    def set(self, attribute: AmbientAttribute, value: float) -> None: ...
    def get(self, attribute: AmbientAttribute, default: float = 0.5) -> float: ...
    def is_empty(self) -> bool: ...
```

### EntityPresence — 在场实体

```python
@dataclass
class EntityPresence:
    """实体在场景中的存在状态"""
    entity_id: EntityId = ""
    role: EntityRole = EntityRole.NPC         # PLAYER / NPC / CREATURE
    name: str = ""
    position: Optional[str] = None
    activity: str = ""                        # 当前活动描述
    visible_to_player: bool = True            # 是否对玩家可见
    metadata: Dict[str, Any] = field(default_factory=dict)
```

## MarkovWeatherSystem — 马尔可夫链天气系统

```python
class MarkovWeatherSystem:
    """基于马尔可夫链的天气状态转换系统

    特性:
    - 6种天气状态: CLEAR/CLOUDY/RAINY/STORMY/SNOWY/FOGGY
    - 平滑概率转移矩阵 (6×6)
    - 季节性偏差调制
    - 温度与降雪/暴风关联
    - 可配置的转换间隔范围

    转换间隔 (秒):
      CLEAR: 120~300  (稳定期长)
      CLOUDY: 60~180  (过渡态中等)
      RAINY: 90~240   (降雨持续)
      STORMY: 30~90   (风暴短暂)
      SNOWY: 120~360  (降雪持久)
      FOGGY: 60~180   (雾气多变)
    """

    def __init__(self, initial_state: WeatherState = WeatherState.CLEAR) -> None: ...

    def update(self, elapsed_seconds: float, season_factor: float = 0.0) -> WeatherState:
        """更新天气状态，返回新状态"""

    def get_effects(self) -> Dict[str, float]:
        """获取当前天气对环境的影响因子
        返回: {visibility, wind_speed, temperature_modifier}
        """
```

**默认转移矩阵** (行=当前状态, 列=下一状态):

| 当前\下一 | CLEAR | CLOUDY | RAINY | STORMY | SNOWY | FOGGY |
|-----------|-------|--------|-------|--------|-------|-------|
| **CLEAR** | 0.60 | 0.25 | 0.05 | 0.02 | 0.03 | 0.05 |
| **CLOUDY** | 0.20 | 0.40 | 0.20 | 0.05 | 0.05 | 0.10 |
| **RAINY** | 0.10 | 0.25 | 0.40 | 0.15 | 0.02 | 0.08 |
| **STORMY** | 0.05 | 0.20 | 0.35 | 0.30 | 0.00 | 0.10 |
| **SNOWY** | 0.05 | 0.15 | 0.02 | 0.00 | 0.60 | 0.18 |
| **FOGGY** | 0.30 | 0.25 | 0.10 | 0.03 | 0.07 | 0.25 |

## SpatialConflictDetector — 空间冲突检测器

```python
class SpatialConflictDetector:
    """Sweep-and-Prune 空间碰撞检测

    算法步骤:
    1. X轴排序 → 快速排除不可能碰撞的对
    2. Y轴精确检查 → AABB重叠判定
    3. Z轴可选验证 → 需要时启用3D检测
    4. 冲突分类 → full(完全)/partial(部分)

    复杂度: O(n log n) 排序 + O(n+k) 扫描 (k为实际碰撞数)
    """

    def detect(self, elements: List[SceneElement]) -> List[ConflictReport]: ...
```

**ConflictReport 结构** (定义于 core.types):

```python
@dataclass
class ConflictReport:
    element_a_id: str
    element_b_id: str
    overlap_type: str              # "full" / "partial"
    suggested_resolution: str      # 调整建议
```

## SceneBuilder — 场景构建器 ⭐ 核心

```python
class SceneBuilder(ISceneBuilder, ISnapshotable):
    """虚拟场景的完整构建与管理

    功能:
    - create_scene(): 从配置创建场景，返回场景ID
    - add_element(): 向场景添加元素（自动空间冲突检测）
    - remove_element(): 移除场景元素
    - update_environment(): 更新环境状态（天气/温度/光照等）
    - check_spatial_conflicts(): 手动触发空间冲突检测
    - get_environment(): 获取当前环境状态
    - get_element(): 查询元素详情
    - add_path_connection(): 添加路径连接关系

    实现接口:
    - ISceneBuilder: 场景构建标准接口
    - ISnapshotable: 支持状态快照与恢复
    """

    def __init__(self, config: SceneConfig) -> None: ...

    async def create_scene(self, scene_config: Dict[str, Any]) -> EntityId:
        """构建并返回场景ID"""

    async def add_element(
        self,
        scene_id: EntityId,
        element: SceneElement,
    ) -> bool:
        """添加元素到场景，自动检测空间冲突"""

    async def update_environment(
        self,
        scene_id: EntityId,
        elapsed_seconds: float,
    ) -> Optional[SceneEnvironment]:
        """更新环境状态（天气转换+温度变化）"""

    async def check_spatial_conflicts(
        self,
        scene_id: EntityId,
    ) -> List[ConflictReport]:
        """检测指定场景的空间冲突"""

    def get_environment(self, scene_id: EntityId) -> Optional[Dict[str, Any]]: ...
    def get_element(self, scene_id: EntityId, element_id: EntityId) -> Optional[Dict[str, Any]]: ...
    def remove_element(self, scene_id: EntityId, element_id: EntityId) -> bool: ...
    def add_path_connection(self, scene_id: EntityId, from_id: EntityId, to_id: EntityId) -> None: ...
```

## 天气效果参数

| 天气 | 能见度 | 风速 | 温度修正 |
|------|--------|------|----------|
| CLEAR | 1.0 | 0.1 | +0.05°C |
| CLOUDY | 0.9 | 0.3 | -0.02°C |
| RAINY | 0.6 | 0.5 | -0.05°C |
| STORMY | 0.3 | 0.9 | -0.08°C |
| SNOWY | 0.5 | 0.4 | -0.15°C |
| FOGGY | 0.2 | 0.05 | -0.01°C |

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_elements_per_scene` | 500 | 单场景最大元素数 |
| `spatial_conflict_accuracy` | 0.95 | 冲突检测精度 [0,1] |
| `environment_update_interval_sec` | 1.0 | 环境更新间隔(秒) |
| `weather_transition_duration` | 30.0 | 天气切换基础时长(秒) |

## 移动端优化配置示例

```python
from luqi_engine.core.config import SceneConfig

mobile_scene = SceneConfig(
    max_elements_per_scene=200,          # 减少元素数
    environment_update_interval_sec=2.0,  # 降低更新频率
    spatial_conflict_accuracy=0.90,       # 换性能
)
```

## 使用示例

```python
from luqi_engine.scene.builder import SceneBuilder, WeatherState, ElementCategory
from luqi_engine.scene.awareness_types import AmbientAttribute, AmbientState
from luqi_engine.core.config import SceneConfig
from luqi_engine.core.types import Vector3, BoundingBox

# 初始化
config = SceneConfig(max_elements_per_scene=500)
builder = SceneBuilder(config)

# 创建场景
scene_config = {
    "name": "武林广场",
    "area_type": "outdoor_open",
    "base_temperature": 22.0,
}
scene_id = await builder.create_scene(scene_config)

# 添加元素
element = SceneElement(
    element_id="elem_sword_stand",
    name="剑架",
    category=ElementCategory.ARTIFICIAL,
    position=Vector3(x=10.0, y=0.0, z=5.0),
    bounding_box=BoundingBox(min_vec=Vector3(9.5, 0, 4.5), max_vec=Vector3(10.5, 2, 5.5)),
)
success = await builder.add_element(scene_id, element)

# 更新环境（经过60秒）
env = await builder.update_environment(scene_id, elapsed_seconds=60.0)
print(f"当前天气: {env.weather.name}")
print(f"能见度: {env.effects.get('visibility', 1.0)}")

# 检测冲突
conflicts = await builder.check_spatial_conflicts(scene_id)
for c in conflicts:
    print(f"冲突: {c.element_a_id} <-> {c.element_b_id} ({c.overlap_type})")
    print(f"建议: {c.suggested_resolution}")

# 获取环境状态
current_env = builder.get_environment(scene_id)
ambient = current_env.get("ambient_state", AmbientState())
lighting = ambient.get(AmbientAttribute.LIGHTING)
print(f"光照强度: {lighting}")
```
