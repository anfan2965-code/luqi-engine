"""
场景感知数据类型 — 结构化场景上下文定义
为场景感知增强系统提供类型安全的场景状态描述，
替代原始的str类型scene_context，支持渐进式填充和LLM prompt生成
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.types import EntityId


# ============================================================
# 常量定义（模块私有）
# ============================================================

_DEFAULT_AMBIENT_VALUE: float = 0.5
_TRUNCATION_SUFFIX: str = "..."

_ENTITY_ROLE_PLAYER: str = "player"
_ENTITY_ROLE_NPC: str = "npc"
_ENTITY_ROLE_CREATURE: str = "creature"

_OBJECT_CATEGORY_FURNITURE: str = "furniture"
_OBJECT_CATEGORY_TOOL: str = "tool"
_OBJECT_CATEGORY_WEAPON: str = "weapon"
_OBJECT_CATEGORY_CONSUMABLE: str = "consumable"
_OBJECT_CATEGORY_DECORATION: str = "decoration"
_OBJECT_CATEGORY_OTHER: str = "other"

_SPATIAL_REL_NEARBY: str = "nearby"
_SPATIAL_REL_ADJACENT: str = "adjacent"
_SPATIAL_REL_OPPOSITE: str = "opposite"
_SPATIAL_REL_ABOVE: str = "above"
_SPATIAL_REL_BELOW: str = "below"
_SPATIAL_REL_FAR: str = "far"
_SPATIAL_REL_HIDDEN: str = "hidden"

_EVENT_TYPE_ARRIVAL: str = "arrival"
_EVENT_TYPE_DEPARTURE: str = "departure"
_EVENT_TYPE_INTERACTION: str = "interaction"
_EVENT_TYPE_COMBAT: str = "combat"
_EVENT_TYPE_DIALOGUE: str = "dialogue"
_EVENT_TYPE_ENVIRONMENTAL: str = "environmental"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ============================================================
# 枚举定义
# ============================================================

class AreaType(Enum):
    """区域分类 — 决定社交规则和环境参数"""
    OUTDOOR_OPEN = auto()
    OUTDOOR_SEMI_OPEN = auto()
    INDOOR_PUBLIC = auto()
    INDOOR_SEMI_PUBLIC = auto()
    INDOOR_PRIVATE = auto()
    INDOOR_SECRET = auto()


class AmbientAttribute(Enum):
    """环境属性维度"""
    LIGHTING = auto()
    NOISE_LEVEL = auto()
    CROWDING = auto()
    TEMPERATURE = auto()
    SAFETY = auto()


class EntityRole(Enum):
    """在场实体的角色分类"""
    PLAYER = _ENTITY_ROLE_PLAYER
    NPC = _ENTITY_ROLE_NPC
    CREATURE = _ENTITY_ROLE_CREATURE


class ObjectCategory(Enum):
    """可交互物体类别"""
    FURNITURE = _OBJECT_CATEGORY_FURNITURE
    TOOL = _OBJECT_CATEGORY_TOOL
    WEAPON = _OBJECT_CATEGORY_WEAPON
    CONSUMABLE = _OBJECT_CATEGORY_CONSUMABLE
    DECORATION = _OBJECT_CATEGORY_DECORATION
    OTHER = _OBJECT_CATEGORY_OTHER


class SpatialRelationType(Enum):
    """空间关系类型"""
    NEARBY = _SPATIAL_REL_NEARBY
    ADJACENT = _SPATIAL_REL_ADJACENT
    OPPOSITE = _SPATIAL_REL_OPPOSITE
    ABOVE = _SPATIAL_REL_ABOVE
    BELOW = _SPATIAL_REL_BELOW
    FAR = _SPATIAL_REL_FAR
    HIDDEN = _SPATIAL_REL_HIDDEN


class SceneEventType(Enum):
    """场景事件类型"""
    ARRIVAL = _EVENT_TYPE_ARRIVAL
    DEPARTURE = _EVENT_TYPE_DEPARTURE
    INTERACTION = _EVENT_TYPE_INTERACTION
    COMBAT = _EVENT_TYPE_COMBAT
    DIALOGUE = _EVENT_TYPE_DIALOGUE
    ENVIRONMENTAL = _EVENT_TYPE_ENVIRONMENTAL


# ============================================================
# 数据类型定义
# ============================================================

@dataclass
class AmbientState:
    """
    环境状态容器
    
    每个AmbientAttribute映射到[0,1]区间的值:
    - LIGHTING: 0=黑暗, 1=明亮
    - NOISE_LEVEL: 0=安静, 1=嘈杂
    - CROWDING: 0=空旷, 1=拥挤
    - TEMPERATURE: 0=寒冷, 1=炎热
    - SAFETY: 0=危险, 1=安全
    """
    
    RANGE_MIN: ClassVar[float] = 0.0
    RANGE_MAX: ClassVar[float] = 1.0
    
    values: Dict[AmbientAttribute, float] = field(default_factory=dict)
    
    def set(self, attribute: AmbientAttribute, value: float) -> None:
        """设置环境属性值，自动钳制到合法范围"""
        self.values[attribute] = _clamp(value, self.RANGE_MIN, self.RANGE_MAX)
    
    def get(self, attribute: AmbientAttribute, default: float = _DEFAULT_AMBIENT_VALUE) -> float:
        """获取环境属性值，不存在时返回默认值"""
        return self.values.get(attribute, default)
    
    def is_empty(self) -> bool:
        """判断是否无任何属性设置"""
        return len(self.values) == 0


@dataclass
class EntityPresence:
    """
    在场实体描述
    
    记录一个实体在当前场景中的存在状态
    """
    entity_id: EntityId = ""
    role: EntityRole = EntityRole.NPC
    name: str = ""
    position: Optional[str] = None
    activity: str = ""
    visible_to_player: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectState:
    """
    可交互物体状态
    
    描述场景中可被角色操作的物体
    """
    object_id: EntityId = ""
    category: ObjectCategory = ObjectCategory.OTHER
    name: str = ""
    description: str = ""
    interactable: bool = True
    accessibility: float = 1.0
    current_state: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneEvent:
    """
    场景事件记录
    
    带有时间衰减的事件条目，用于构建"最近发生的事"上下文
    """
    event_type: SceneEventType = SceneEventType.DIALOGUE
    description: str = ""
    timestamp: float = 0.0
    relevance_decay: float = 0.05
    involved_entities: List[EntityId] = field(default_factory=list)
    
    RELEVANCE_MIN: ClassVar[float] = 0.01
    RELEVANCE_MAX: ClassVar[float] = 1.0
    
    @property
    def current_relevance(self) -> float:
        """计算当前相关性（随时间衰减）"""
        if self.timestamp <= 0:
            return self.RELEVANCE_MAX
        
        elapsed = time.time() - self.timestamp
        decayed = math.exp(-self.relevance_decay * elapsed)
        return _clamp(decayed, self.RELEVANCE_MIN, self.RELEVANCE_MAX)
    
    def is_stale(self, threshold: float = 0.1) -> bool:
        """判断事件是否已过期"""
        return self.current_relevance < threshold


@dataclass
class SpatialRelation:
    """
    空间关系描述
    
    描述两个实体之间的空间位置关系
    """
    target_id: EntityId = ""
    relation_type: SpatialRelationType = SpatialRelationType.NEARBY
    distance_estimate: float = 1.0
    description: str = ""
    
    DISTANCE_MIN: ClassVar[float] = 0.0
    DISTANCE_MAX: ClassVar[float] = 100.0
    
    def __post_init__(self):
        self.distance_estimate = _clamp(
            self.distance_estimate, self.DISTANCE_MIN, self.DISTANCE_MAX
        )


@dataclass
class SceneContext:
    """
    结构化场景上下文（核心数据类型）
    
    设计约束:
    - 所有字段都有合理默认值 → 向后兼容
    - to_llm_prompt() → 兼容旧接口的字符串输出
    - is_empty() → 快速判断是否已初始化
    - max_length参数 → 控制prompt长度防止token溢出
    
    使用方式:
    - 渐进式填充：先只填 location + area_type，后续逐步丰富
    - 作为dict注入dialogue context的"scene_context"字段
    """
    
    location: str = ""
    location_description: str = ""
    area_type: AreaType = AreaType.INDOOR_PUBLIC
    
    ambient: AmbientState = field(default_factory=AmbientState)
    
    present_entities: List[EntityPresence] = field(default_factory=list)
    available_objects: List[ObjectState] = field(default_factory=list)
    recent_events: List[SceneEvent] = field(default_factory=list)
    
    spatial_relations: List[SpatialRelation] = field(default_factory=list)
    
    time_of_day: str = ""
    weather: str = ""
    
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """
        判断场景上下文是否为空（未初始化）
        
        仅当location为空且无任何实体/事件时返回True
        """
        if self.location:
            return False
        if self.present_entities:
            return False
        if self.available_objects:
            return False
        if self.recent_events:
            return False
        if self.spatial_relations:
            return False
        return True

    def to_llm_prompt(self, max_length: int = 500) -> str:
        """
        转换为适合注入 LLM prompt 的文本
        
        这是向后兼容的关键方法：
        - 旧的 scene_context: str 直接使用此方法的输出
        - 新代码可以使用完整的 SceneContext 对象
        
        输出格式规则:
        1. 每项以句号结尾
        2. 使用中文描述
        3. 按重要性排序: 位置 > 时间天气 > 人物 > 物品 > 氛围 > 近期事件
        4. 总长度不超过max_length字符，超长截断加"..."
        5. 空字段不输出对应行
        
        Args:
            max_length: 最大输出字符数
            
        Returns:
            格式化的场景上下文字符串
        """
        parts: List[str] = []
        
        # 1. 位置信息（最高优先级）
        if self.location:
            area_name = self._area_type_to_display(self.area_type)
            loc_part = f"当前位置：{self.location}（{area_name}）"
            parts.append(loc_part)
            
            if self.location_description:
                parts.append(f"环境描述：{self.location_description}")
        
        # 2. 时间与天气
        time_parts: List[str] = []
        if self.time_of_day:
            time_parts.append(self.time_of_day)
        if self.weather:
            time_parts.append(self.weather)
        if time_parts:
            parts.append(f"时间天气：{'，'.join(time_parts)}")
        
        # 3. 在场人物
        if self.present_entities:
            names = [e.name or e.entity_id for e in self.present_entities if e.visible_to_player]
            if names:
                parts.append(f"在场人物：{'、'.join(names)}")
        
        # 4. 可交互物品
        if self.available_objects:
            obj_names = [o.name or o.object_id for o in self.available_objects if o.interactable]
            if obj_names:
                parts.append(f"可见物品：{'、'.join(obj_names)}")
        
        # 5. 环境氛围
        if not self.ambient.is_empty():
            ambient_descs = self._ambient_to_description()
            if ambient_descs:
                parts.append(f"环境氛围：{'; '.join(ambient_descs)}")
        
        # 6. 空间关系（仅保留对player有意义的）
        player_relations = [
            r for r in self.spatial_relations
            if r.description or r.relation_type != SpatialRelationType.FAR
        ]
        if player_relations:
            rel_descs = [r.description or f"{r.target_id}在{r.relation_type.value}" for r in player_relations]
            parts.append(f"空间关系：{'; '.join(rel_descs)}")
        
        # 7. 近期事件（按相关性排序，取top3）
        valid_events = sorted(
            [e for e in self.recent_events if not e.is_stale()],
            key=lambda e: e.current_relevance,
            reverse=True,
        )[:3]
        if valid_events:
            event_descs = [e.description for e in valid_events if e.description]
            if event_descs:
                parts.append(f"最近发生的事：{'；'.join(event_descs)}")
        
        if not parts:
            return ""
        
        result = "。".join(parts) + "。"
        
        if len(result) > max_length:
            result = result[:max_length - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX
        
        return result
    
    @staticmethod
    def _area_type_to_display(area_type: AreaType) -> str:
        """将AreaType枚举转换为中文显示名称"""
        mapping: Dict[AreaType, str] = {
            AreaType.OUTDOOR_OPEN: "室外开阔区域",
            AreaType.OUTDOOR_SEMI_OPEN: "室外半开放区域",
            AreaType.INDOOR_PUBLIC: "室内公共场所",
            AreaType.INDOOR_SEMI_PUBLIC: "室内半公共场所",
            AreaType.INDOOR_PRIVATE: "室内私密空间",
            AreaType.INDOOR_SECRET: "隐秘空间",
        }
        return mapping.get(area_type, "未知区域")
    
    def _ambient_to_description(self) -> List[str]:
        """将环境属性转换为可读中文描述列表"""
        desc_map: Dict[AmbientAttribute, Tuple[str, str, str]] = {
            AmbientAttribute.LIGHTING: ("光线", "昏暗", "明亮"),
            AmbientAttribute.NOISE_LEVEL: ("噪音", "安静", "嘈杂"),
            AmbientAttribute.CROWDING: ("拥挤度", "空旷", "拥挤"),
            AmbientAttribute.TEMPERATURE: ("温度", "寒冷", "炎热"),
            AmbientAttribute.SAFETY: ("安全性", "危险", "安全"),
        }
        
        results: List[str] = []
        for attr, val in self.ambient.values.items():
            if attr in desc_map:
                name, low_label, high_label = desc_map[attr]
                display_val = val * 100
                if display_val < 30:
                    label = low_label
                elif display_val > 70:
                    label = high_label
                else:
                    label = "一般"
                results.append(f"{name}{label}")
        
        return results
