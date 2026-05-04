"""
场景构建器 - ISceneBuilder接口实现
场景元素分类、空间关系、马尔可夫链天气、Sweep-and-Prune空间冲突检测
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from logging import getLogger
from typing import Any, Dict, List, Optional, Set, Tuple

_logger = getLogger(__name__)

from luqi_engine.core.config import SceneConfig
from luqi_engine.core.interfaces import ISceneBuilder
from luqi_engine.core.snapshot import ISnapshotable
from luqi_engine.core.types import (
    BoundingBox,
    ConflictReport,
    EntityId,
    Vector3,
    generate_entity_id,
)
from luqi_engine.core.rng import PCGRandom


class WeatherState(Enum):
    CLEAR = 0
    CLOUDY = 1
    RAINY = 2
    STORMY = 3
    SNOWY = 4
    FOGGY = 5


class ElementCategory(Enum):
    NATURAL = auto()
    ARTIFICIAL = auto()
    INTERACTIVE = auto()


_WEATHER_STATE_COUNT: int = 6
_WEATHER_BASE_TRANSITION: Tuple[Tuple[float, ...], ...] = (
    (0.60, 0.25, 0.05, 0.02, 0.03, 0.05),
    (0.20, 0.40, 0.20, 0.05, 0.05, 0.10),
    (0.10, 0.25, 0.40, 0.15, 0.02, 0.08),
    (0.05, 0.20, 0.35, 0.30, 0.00, 0.10),
    (0.05, 0.15, 0.02, 0.00, 0.60, 0.18),
    (0.30, 0.25, 0.10, 0.03, 0.07, 0.25),
)

_WEATHER_TRANSITION_INTERVALS: Dict[WeatherState, Tuple[float, float]] = {
    WeatherState.CLEAR: (120.0, 300.0),
    WeatherState.CLOUDY: (60.0, 180.0),
    WeatherState.RAINY: (90.0, 240.0),
    WeatherState.STORMY: (30.0, 90.0),
    WeatherState.SNOWY: (120.0, 360.0),
    WeatherState.FOGGY: (60.0, 180.0),
}

_SNOWY_IDX: int = 4
_STORMY_IDX: int = 3
_FOGGY_IDX: int = 5
_CLEAR_IDX: int = 0
_CLOUDY_IDX: int = 1

_SNOW_TEMPERATURE_MIDPOINT: float = 0.4
_SNOW_TEMPERATURE_STEEPNESS: float = 10.0
_STORM_BASE_FACTOR: float = 0.3
_STORM_RANGE_FACTOR: float = 0.7
_FOG_BASE_FACTOR: float = 0.5
_FOG_RANGE_FACTOR: float = 0.5
_SEASONAL_BIAS_AMPLITUDE: float = 0.1

_SNOW_MODULATION_FLOOR: float = 0.1
_SNOW_MODULATION_CEIL: float = 0.9
_FOG_OPTIMAL_TEMPERATURE: float = 0.5
_FOG_TEMPERATURE_SENSITIVITY: float = 2.0
_SEASONAL_CLOUDY_BIAS_DECAY: float = 0.5

_WEATHER_EFFECTS_DEFAULT: Dict[str, float] = {
    "visibility": 1.0,
    "wind_speed": 0.0,
    "temperature_modifier": 0.0,
}
_WEATHER_STATE_EFFECTS: Dict[WeatherState, Dict[str, float]] = {
    WeatherState.CLEAR: {"visibility": 1.0, "wind_speed": 0.1, "temperature_modifier": 0.05},
    WeatherState.CLOUDY: {"visibility": 0.9, "wind_speed": 0.3, "temperature_modifier": -0.02},
    WeatherState.RAINY: {"visibility": 0.6, "wind_speed": 0.5, "temperature_modifier": -0.05},
    WeatherState.STORMY: {"visibility": 0.3, "wind_speed": 0.9, "temperature_modifier": -0.08},
    WeatherState.SNOWY: {"visibility": 0.5, "wind_speed": 0.4, "temperature_modifier": -0.15},
    WeatherState.FOGGY: {"visibility": 0.2, "wind_speed": 0.05, "temperature_modifier": -0.01},
}

_DEFAULT_TRANSITION_INTERVAL: Tuple[float, float] = (60.0, 180.0)
_TIME_SECONDS_TO_MS: int = 1000
_BOUNDS_HALF_EXTENT_DEFAULT: float = 1.0

_ELEMENT_CATEGORY_KEYWORDS: Dict[ElementCategory, Tuple[str, ...]] = {
    ElementCategory.NATURAL: (
        "树", "山", "河", "湖", "岩石", "草", "花", "泉", "洞", "沙",
        "tree", "mountain", "river", "lake", "rock", "grass",
    ),
    ElementCategory.ARTIFICIAL: (
        "房", "墙", "桥", "塔", "路", "门", "灯", "井", "碑", "栅",
        "house", "wall", "bridge", "tower", "road", "door",
    ),
    ElementCategory.INTERACTIVE: (
        "箱", "柜", "机关", "开关", "宝箱", "NPC", "商人", "守卫",
        "chest", "lever", "switch", "npc", "merchant", "guard",
    ),
}

_SPATIAL_RELATION_THRESHOLD: float = 50.0
_PATH_CONNECTION_MAX_DISTANCE: float = 100.0
_CONFLICT_SEVERITY_MIN: float = 0.0
_CONFLICT_SEVERITY_MAX: float = 1.0
_CONFLICT_SEVERITY_SCALE_FACTOR: float = 2.0

_SCENE_TIME_DEFAULT: float = 8.0
_SCENE_TIME_MAX: float = 24.0
_SCENE_TEMPERATURE_DEFAULT: float = 0.5
_SCENE_HUMIDITY_DEFAULT: float = 0.5
_SCENE_SEASON_PHASE_DEFAULT: float = 0.0

_SWEEP_TOLERANCE: float = 1e-9


@dataclass
class SceneElement:
    element_id: EntityId
    name: str
    category: ElementCategory
    position: Vector3
    bounds: BoundingBox
    properties: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[EntityId] = None
    children_ids: List[EntityId] = field(default_factory=list)
    path_connections: List[EntityId] = field(default_factory=list)


@dataclass
class SceneEnvironment:
    time_of_day: float = _SCENE_TIME_DEFAULT
    weather: WeatherState = WeatherState.CLEAR
    temperature: float = _SCENE_TEMPERATURE_DEFAULT
    humidity: float = _SCENE_HUMIDITY_DEFAULT
    season_phase: float = _SCENE_SEASON_PHASE_DEFAULT
    last_weather_change: float = 0.0
    next_weather_change: float = 300.0
    visibility: float = 1.0
    wind_speed: float = 0.0

    def advance_time(self, delta_hours: float) -> None:
        self.time_of_day = (self.time_of_day + delta_hours) % _SCENE_TIME_MAX
        season_rate = (2.0 * math.pi) / (365.25 * 24.0)
        self.season_phase += season_rate * delta_hours


class MarkovWeatherSystem:
    """
    马尔可夫链天气系统
    六态转移矩阵 + 环境参数连续调制 + Lorenz微扰
    """

    def __init__(
        self,
        rng: Optional[PCGRandom] = None,
        base_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None,
    ) -> None:
        self._rng = rng or PCGRandom(seed=int(time.time() * 1000))
        self._base_matrix = base_matrix or _WEATHER_BASE_TRANSITION
        self._current_state: WeatherState = WeatherState.CLEAR

    def transition(
        self,
        temperature: float = _SCENE_TEMPERATURE_DEFAULT,
        humidity: float = _SCENE_HUMIDITY_DEFAULT,
        season_phase: float = _SCENE_SEASON_PHASE_DEFAULT,
    ) -> WeatherState:
        modulated = self._modulate_matrix(temperature, humidity, season_phase)
        current_idx = self._current_state.value
        row = modulated[current_idx]
        next_idx = self._rng.weighted_choice(row)
        self._current_state = WeatherState(next_idx)
        return self._current_state

    def set_state(self, state: WeatherState) -> None:
        self._current_state = state

    @property
    def current_state(self) -> WeatherState:
        return self._current_state

    def compute_next_transition_interval(self) -> float:
        interval_range = _WEATHER_TRANSITION_INTERVALS.get(
            self._current_state, _DEFAULT_TRANSITION_INTERVAL
        )
        return self._rng.uniform(interval_range[0], interval_range[1])

    def compute_environment_effects(self) -> Dict[str, float]:
        return _WEATHER_STATE_EFFECTS.get(self._current_state, _WEATHER_EFFECTS_DEFAULT)

    def _modulate_matrix(
        self,
        temperature: float,
        humidity: float,
        season_phase: float,
    ) -> List[List[float]]:
        n = _WEATHER_STATE_COUNT
        modulated: List[List[float]] = []
        for i in range(n):
            row: List[float] = []
            for j in range(n):
                p = self._base_matrix[i][j]
                p = self._apply_snow_modulation(p, j, temperature)
                p = self._apply_storm_modulation(p, j, temperature, humidity)
                p = self._apply_fog_modulation(p, j, humidity, temperature)
                p = self._apply_seasonal_modulation(p, j, season_phase)
                row.append(max(0.0, p))
            row_sum = sum(row)
            if row_sum > 0.0:
                row = [v / row_sum for v in row]
            modulated.append(row)
        return modulated

    @staticmethod
    def _apply_snow_modulation(p: float, target_idx: int, temperature: float) -> float:
        if target_idx != _SNOWY_IDX:
            return p
        snow_factor = 1.0 / (1.0 + math.exp(
            _SNOW_TEMPERATURE_STEEPNESS * (temperature - _SNOW_TEMPERATURE_MIDPOINT)
        ))
        return p * (_SNOW_MODULATION_FLOOR + _SNOW_MODULATION_CEIL * snow_factor)

    @staticmethod
    def _apply_storm_modulation(
        p: float, target_idx: int, temperature: float, humidity: float,
    ) -> float:
        if target_idx != _STORMY_IDX:
            return p
        storm_factor = temperature * humidity
        return p * (_STORM_BASE_FACTOR + _STORM_RANGE_FACTOR * storm_factor)

    @staticmethod
    def _apply_fog_modulation(
        p: float, target_idx: int, humidity: float, temperature: float,
    ) -> float:
        if target_idx != _FOGGY_IDX:
            return p
        fog_factor = humidity * max(0.0, 1.0 - abs(temperature - _FOG_OPTIMAL_TEMPERATURE) * _FOG_TEMPERATURE_SENSITIVITY)
        return p * (_FOG_BASE_FACTOR + _FOG_RANGE_FACTOR * fog_factor)

    @staticmethod
    def _apply_seasonal_modulation(
        p: float, target_idx: int, season_phase: float,
    ) -> float:
        bias = _SEASONAL_BIAS_AMPLITUDE * math.sin(season_phase)
        if target_idx == _CLEAR_IDX:
            return p * (1.0 + bias)
        if target_idx == _CLOUDY_IDX:
            return p * (1.0 - bias * _SEASONAL_CLOUDY_BIAS_DECAY)
        return p


class SpatialConflictDetector:
    """
    空间冲突检测器
    Sweep-and-Prune宽相 + AABB窄相
    """

    def detect_conflicts(
        self, elements: Dict[EntityId, SceneElement],
    ) -> List[ConflictReport]:
        if len(elements) < 2:
            return []
        element_list = list(elements.values())
        candidate_pairs = self._broad_phase_sap(element_list)
        conflicts: List[ConflictReport] = []
        for i, j in candidate_pairs:
            elem_a = element_list[i]
            elem_b = element_list[j]
            if elem_a.bounds.intersects(elem_b.bounds):
                conflict = self._create_conflict_report(elem_a, elem_b)
                if conflict is not None:
                    conflicts.append(conflict)
        return conflicts

    @staticmethod
    def _broad_phase_sap(
        elements: List[SceneElement],
    ) -> List[Tuple[int, int]]:
        if len(elements) < 2:
            return []
        x_pairs = SpatialConflictDetector._sweep_axis(elements, "x")
        y_pairs = SpatialConflictDetector._sweep_axis(elements, "y")
        z_pairs = SpatialConflictDetector._sweep_axis(elements, "z")
        return list(x_pairs & y_pairs & z_pairs)

    @staticmethod
    def _sweep_axis(
        elements: List[SceneElement], axis: str,
    ) -> Set[Tuple[int, int]]:
        axis_idx = {"x": 0, "y": 1, "z": 2}[axis]
        endpoints: List[Tuple[float, int, bool]] = []
        for i, elem in enumerate(elements):
            center_val = (elem.bounds.center.x, elem.bounds.center.y, elem.bounds.center.z)[axis_idx]
            half_val = (elem.bounds.half_extents.x, elem.bounds.half_extents.y, elem.bounds.half_extents.z)[axis_idx]
            endpoints.append((center_val - half_val, i, True))
            endpoints.append((center_val + half_val, i, False))
        endpoints.sort(key=lambda e: (e[0], not e[2]))
        overlapping: Set[Tuple[int, int]] = set()
        active: Set[int] = set()
        for _, box_id, is_start in endpoints:
            if is_start:
                for active_id in active:
                    pair = (min(box_id, active_id), max(box_id, active_id))
                    overlapping.add(pair)
                active.add(box_id)
            else:
                active.discard(box_id)
        return overlapping

    @staticmethod
    def _create_conflict_report(
        elem_a: SceneElement, elem_b: SceneElement,
    ) -> Optional[ConflictReport]:
        penetration = SpatialConflictDetector._compute_penetration(
            elem_a.bounds, elem_b.bounds,
        )
        if penetration <= 0.0:
            return None
        min_extent = min(
            min(elem_a.bounds.half_extents.to_tuple()),
            min(elem_b.bounds.half_extents.to_tuple()),
        )
        if min_extent <= 0.0:
            severity = _CONFLICT_SEVERITY_MAX
        else:
            severity = min(
                _CONFLICT_SEVERITY_MAX,
                penetration / (min_extent * _CONFLICT_SEVERITY_SCALE_FACTOR),
            )
        mtv_axis = SpatialConflictDetector._compute_mtv_axis(
            elem_a.bounds, elem_b.bounds,
        )
        return ConflictReport(
            conflict_id=generate_entity_id("spatial"),
            conflict_type="spatial_overlap",
            description=f"场景元素'{elem_a.name}'与'{elem_b.name}'空间重叠，穿透深度{penetration:.2f}",
            severity=severity,
            involved_entities=[elem_a.element_id, elem_b.element_id],
            suggested_resolutions=[
                {
                    "strategy": "translate",
                    "description": f"沿{mtv_axis}轴分离，移动距离{penetration:.2f}",
                    "axis": mtv_axis,
                    "distance": penetration,
                },
                {
                    "strategy": "remove",
                    "description": f"移除元素'{elem_b.name}'",
                    "entity_id": elem_b.element_id,
                },
            ],
        )

    @staticmethod
    def _compute_penetration(a: BoundingBox, b: BoundingBox) -> float:
        dx = a.half_extents.x + b.half_extents.x - abs(a.center.x - b.center.x)
        dy = a.half_extents.y + b.half_extents.y - abs(a.center.y - b.center.y)
        dz = a.half_extents.z + b.half_extents.z - abs(a.center.z - b.center.z)
        if dx <= 0.0 or dy <= 0.0 or dz <= 0.0:
            return 0.0
        return min(dx, dy, dz)

    @staticmethod
    def _compute_mtv_axis(a: BoundingBox, b: BoundingBox) -> str:
        dx = a.half_extents.x + b.half_extents.x - abs(a.center.x - b.center.x)
        dy = a.half_extents.y + b.half_extents.y - abs(a.center.y - b.center.y)
        dz = a.half_extents.z + b.half_extents.z - abs(a.center.z - b.center.z)
        if dx <= dy and dx <= dz:
            return "x"
        if dy <= dx and dy <= dz:
            return "y"
        return "z"


class SceneBuilder(ISceneBuilder, ISnapshotable):
    """
    场景构建器
    实现ISceneBuilder接口
    """

    def __init__(self, config: Optional[SceneConfig] = None) -> None:
        self._config = config or SceneConfig()
        self._scenes: Dict[EntityId, Dict[str, Any]] = {}
        self._elements: Dict[EntityId, Dict[EntityId, SceneElement]] = {}
        self._environments: Dict[EntityId, SceneEnvironment] = {}
        self._weather_systems: Dict[EntityId, MarkovWeatherSystem] = {}
        self._conflict_detector = SpatialConflictDetector()

    async def create_scene(self, scene_config: Dict[str, Any]) -> EntityId:
        scene_id = generate_entity_id("scene")
        self._scenes[scene_id] = scene_config
        self._elements[scene_id] = {}
        seed = scene_config.get("seed", int(time.time() * _TIME_SECONDS_TO_MS))
        rng = PCGRandom(seed=seed)
        self._weather_systems[scene_id] = MarkovWeatherSystem(rng=rng)
        initial_weather = WeatherState[scene_config.get("initial_weather", "CLEAR").upper()]
        self._weather_systems[scene_id].set_state(initial_weather)
        self._environments[scene_id] = SceneEnvironment(
            time_of_day=scene_config.get("time_of_day", _SCENE_TIME_DEFAULT),
            weather=initial_weather,
            temperature=scene_config.get("temperature", _SCENE_TEMPERATURE_DEFAULT),
            humidity=scene_config.get("humidity", _SCENE_HUMIDITY_DEFAULT),
            season_phase=scene_config.get("season_phase", _SCENE_SEASON_PHASE_DEFAULT),
            last_weather_change=0.0,
            next_weather_change=rng.uniform(_DEFAULT_TRANSITION_INTERVAL[0], _DEFAULT_TRANSITION_INTERVAL[1]),
        )
        return scene_id

    async def add_element(
        self, scene_id: EntityId, element: Dict[str, Any],
    ) -> EntityId:
        self._validate_scene(scene_id)
        element_id = generate_entity_id("elem")
        category = self._classify_element(element)
        position = self._parse_position(element)
        bounds = self._compute_bounds(element, position)
        parent_id = element.get("parent_id")
        scene_elem = SceneElement(
            element_id=element_id,
            name=element.get("name", ""),
            category=category,
            position=position,
            bounds=bounds,
            properties=element.get("properties", {}),
            parent_id=parent_id,
        )
        if parent_id is not None and parent_id in self._elements[scene_id]:
            self._elements[scene_id][parent_id].children_ids.append(element_id)
        self._elements[scene_id][element_id] = scene_elem
        return element_id

    async def query_elements(
        self,
        scene_id: EntityId,
        element_type: Optional[str] = None,
        bounds: Optional[BoundingBox] = None,
    ) -> List[Dict[str, Any]]:
        self._validate_scene(scene_id)
        elements = self._elements.get(scene_id, {})
        results: List[Dict[str, Any]] = []
        for elem in elements.values():
            if element_type is not None:
                if elem.category.name.lower() != element_type.lower():
                    continue
            if bounds is not None:
                if not bounds.contains(elem.position):
                    continue
            results.append(self._element_to_dict(elem))
        return results

    async def update_environment(
        self, scene_id: EntityId, delta_time: float,
    ) -> None:
        self._validate_scene(scene_id)
        env = self._environments.get(scene_id)
        if env is None:
            return
        weather_system = self._weather_systems.get(scene_id)
        if weather_system is None:
            return
        time_scale = self._config.time_scale
        delta_hours = (delta_time * time_scale) / 3600.0
        env.advance_time(delta_hours)
        env.last_weather_change += delta_time
        if env.last_weather_change >= env.next_weather_change:
            new_weather = weather_system.transition(
                temperature=env.temperature,
                humidity=env.humidity,
                season_phase=env.season_phase,
            )
            env.weather = new_weather
            env.last_weather_change = 0.0
            env.next_weather_change = weather_system.compute_next_transition_interval()
            effects = weather_system.compute_environment_effects()
            env.visibility = effects["visibility"]
            env.wind_speed = effects["wind_speed"]
            env.temperature = max(
                0.0, min(1.0, env.temperature + effects["temperature_modifier"]
            ))

    async def check_spatial_conflicts(
        self, scene_id: EntityId,
    ) -> List[ConflictReport]:
        self._validate_scene(scene_id)
        elements = self._elements.get(scene_id, {})
        return self._conflict_detector.detect_conflicts(elements)

    def get_environment(self, scene_id: EntityId) -> Optional[Dict[str, Any]]:
        env = self._environments.get(scene_id)
        if env is None:
            return None
        return {
            "time_of_day": env.time_of_day,
            "weather": env.weather.name,
            "temperature": env.temperature,
            "humidity": env.humidity,
            "season_phase": env.season_phase,
            "visibility": env.visibility,
            "wind_speed": env.wind_speed,
        }

    def get_element(self, scene_id: EntityId, element_id: EntityId) -> Optional[Dict[str, Any]]:
        elements = self._elements.get(scene_id, {})
        elem = elements.get(element_id)
        if elem is None:
            return None
        return self._element_to_dict(elem)

    def remove_element(self, scene_id: EntityId, element_id: EntityId) -> bool:
        elements = self._elements.get(scene_id, {})
        elem = elements.get(element_id)
        if elem is None:
            return False
        if elem.parent_id is not None and elem.parent_id in elements:
            parent = elements[elem.parent_id]
            if element_id in parent.children_ids:
                parent.children_ids.remove(element_id)
        for child_id in elem.children_ids:
            child = elements.get(child_id)
            if child is not None:
                child.parent_id = elem.parent_id
        del elements[element_id]
        return True

    def add_path_connection(
        self, scene_id: EntityId, elem_a_id: EntityId, elem_b_id: EntityId,
    ) -> bool:
        elements = self._elements.get(scene_id, {})
        elem_a = elements.get(elem_a_id)
        elem_b = elements.get(elem_b_id)
        if elem_a is None or elem_b is None:
            return False
        distance = elem_a.position.distance_to(elem_b.position)
        if distance > _PATH_CONNECTION_MAX_DISTANCE:
            return False
        if elem_b_id not in elem_a.path_connections:
            elem_a.path_connections.append(elem_b_id)
        if elem_a_id not in elem_b.path_connections:
            elem_b.path_connections.append(elem_a_id)
        return True

    def _validate_scene(self, scene_id: EntityId) -> None:
        if scene_id not in self._scenes:
            raise KeyError(f"场景不存在: {scene_id}")

    @staticmethod
    def _classify_element(element: Dict[str, Any]) -> ElementCategory:
        name = element.get("name", "").lower()
        description = element.get("description", "").lower()
        combined = f"{name} {description}"
        best_category: ElementCategory = ElementCategory.NATURAL
        best_score: int = 0
        for category, keywords in _ELEMENT_CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > best_score:
                best_score = score
                best_category = category
        explicit = element.get("category")
        if explicit is not None:
            try:
                return ElementCategory[explicit.upper()]
            except KeyError:
                _logger.debug("元素分类'%s'不在ElementCategory枚举中", explicit)
        return best_category

    @staticmethod
    def _parse_position(element: Dict[str, Any]) -> Vector3:
        pos = element.get("position", {})
        if isinstance(pos, dict):
            return Vector3(
                x=float(pos.get("x", 0.0)),
                y=float(pos.get("y", 0.0)),
                z=float(pos.get("z", 0.0)),
            )
        if isinstance(pos, (list, tuple)) and len(pos) >= 3:
            return Vector3(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]))
        return Vector3()

    @staticmethod
    def _compute_bounds(element: Dict[str, Any], position: Vector3) -> BoundingBox:
        bounds_data = element.get("bounds", {})
        if isinstance(bounds_data, dict):
            half = Vector3(
                x=float(bounds_data.get("half_x", _BOUNDS_HALF_EXTENT_DEFAULT)),
                y=float(bounds_data.get("half_y", _BOUNDS_HALF_EXTENT_DEFAULT)),
                z=float(bounds_data.get("half_z", _BOUNDS_HALF_EXTENT_DEFAULT)),
            )
        else:
            half = Vector3(x=_BOUNDS_HALF_EXTENT_DEFAULT, y=_BOUNDS_HALF_EXTENT_DEFAULT, z=_BOUNDS_HALF_EXTENT_DEFAULT)
        return BoundingBox(center=position, half_extents=half)

    @staticmethod
    def _element_to_dict(elem: SceneElement) -> Dict[str, Any]:
        return {
            "element_id": elem.element_id,
            "name": elem.name,
            "category": elem.category.name,
            "position": {"x": elem.position.x, "y": elem.position.y, "z": elem.position.z},
            "bounds": {
                "center": {"x": elem.bounds.center.x, "y": elem.bounds.center.y, "z": elem.bounds.center.z},
                "half_extents": {
                    "x": elem.bounds.half_extents.x,
                    "y": elem.bounds.half_extents.y,
                    "z": elem.bounds.half_extents.z,
                },
            },
            "properties": elem.properties,
            "parent_id": elem.parent_id,
            "children_ids": elem.children_ids,
            "path_connections": elem.path_connections,
        }

    def save_snapshot(self) -> Dict[str, Any]:
        scenes_serialized = {}
        for scene_id, config in self._scenes.items():
            scenes_serialized[scene_id] = dict(config)
        elements_serialized = {}
        for scene_id, scene_elements in self._elements.items():
            elements_serialized[scene_id] = {}
            for elem_id, elem in scene_elements.items():
                elements_serialized[scene_id][elem_id] = self._element_to_dict(elem)
        environments_serialized = {}
        for scene_id, env in self._environments.items():
            environments_serialized[scene_id] = {
                "time_of_day": env.time_of_day,
                "weather": env.weather.name,
                "temperature": env.temperature,
                "humidity": env.humidity,
                "season_phase": env.season_phase,
                "visibility": env.visibility,
                "wind_speed": env.wind_speed,
            }
        weather_states = {}
        for scene_id, ws in self._weather_systems.items():
            weather_states[scene_id] = ws.current_state.name
        return {
            "scenes": scenes_serialized,
            "elements": elements_serialized,
            "environments": environments_serialized,
            "weather_states": weather_states,
        }

    def load_snapshot(self, data: Dict[str, Any]) -> None:
        self._scenes = {}
        for scene_id, config in data.get("scenes", {}).items():
            self._scenes[scene_id] = dict(config)
        self._elements = {}
        for scene_id, scene_elements in data.get("elements", {}).items():
            self._elements[scene_id] = {}
            for elem_id, elem_data in scene_elements.items():
                pos_data = elem_data.get("position", {})
                position = Vector3(
                    x=pos_data.get("x", 0.0),
                    y=pos_data.get("y", 0.0),
                    z=pos_data.get("z", 0.0),
                )
                bounds_data = elem_data.get("bounds", {})
                center_data = bounds_data.get("center", {})
                half_data = bounds_data.get("half_extents", {})
                bounds = BoundingBox(
                    center=Vector3(
                        x=center_data.get("x", 0.0),
                        y=center_data.get("y", 0.0),
                        z=center_data.get("z", 0.0),
                    ),
                    half_extents=Vector3(
                        x=half_data.get("x", _BOUNDS_HALF_EXTENT_DEFAULT),
                        y=half_data.get("y", _BOUNDS_HALF_EXTENT_DEFAULT),
                        z=half_data.get("z", _BOUNDS_HALF_EXTENT_DEFAULT),
                    ),
                )
                category = ElementCategory[elem_data["category"]]
                self._elements[scene_id][elem_id] = SceneElement(
                    element_id=elem_data["element_id"],
                    name=elem_data["name"],
                    category=category,
                    position=position,
                    bounds=bounds,
                    properties=dict(elem_data.get("properties", {})),
                    parent_id=elem_data.get("parent_id"),
                    children_ids=list(elem_data.get("children_ids", [])),
                    path_connections=list(elem_data.get("path_connections", [])),
                )
        self._environments = {}
        for scene_id, env_data in data.get("environments", {}).items():
            weather_name = env_data.get("weather", "CLEAR")
            weather = WeatherState[weather_name]
            self._environments[scene_id] = SceneEnvironment(
                time_of_day=env_data.get("time_of_day", _SCENE_TIME_DEFAULT),
                weather=weather,
                temperature=env_data.get("temperature", _SCENE_TEMPERATURE_DEFAULT),
                humidity=env_data.get("humidity", _SCENE_HUMIDITY_DEFAULT),
                season_phase=env_data.get("season_phase", _SCENE_SEASON_PHASE_DEFAULT),
                visibility=env_data.get("visibility", 1.0),
                wind_speed=env_data.get("wind_speed", 0.0),
            )
        self._weather_systems = {}
        for scene_id, weather_name in data.get("weather_states", {}).items():
            rng = PCGRandom(seed=int(time.time() * 1000))
            ws = MarkovWeatherSystem(rng=rng)
            ws.set_state(WeatherState[weather_name])
            self._weather_systems[scene_id] = ws
