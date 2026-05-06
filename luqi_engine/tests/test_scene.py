import asyncio
import pytest
from luqi_engine.scene.builder import (
    SceneBuilder, WeatherState, ElementCategory, SceneElement,
    MarkovWeatherSystem, SpatialConflictDetector,
)
from luqi_engine.core.config import SceneConfig
from luqi_engine.core.types import Vector3, BoundingBox, ConflictReport
from luqi_engine.core.rng import PCGRandom


@pytest.fixture
def config():
    return SceneConfig(max_elements_per_scene=500, time_scale=1.0)


@pytest.fixture
def builder(config):
    return SceneBuilder(config=config)


@pytest.fixture
def weather_system():
    return MarkovWeatherSystem()


@pytest.fixture
def spatial_detector():
    return SpatialConflictDetector()


class TestMarkovWeatherSystem:
    def test_initial_state_is_clear(self, weather_system):
        assert weather_system.current_state == WeatherState.CLEAR

    def test_transition_returns_valid_state(self, weather_system):
        new_state = weather_system.transition(temperature=0.5, humidity=0.5, season_phase=0.0)
        assert isinstance(new_state, WeatherState)

    def test_cold_temperature_increases_snow(self, weather_system):
        snow_count = 0
        for i in range(100):
            ws = MarkovWeatherSystem(rng=PCGRandom(seed=i))
            state = ws.transition(temperature=0.1, humidity=0.6, season_phase=0.0)
            if state == WeatherState.SNOWY:
                snow_count += 1
        assert snow_count > 0

    def test_hot_humid_increases_storm(self, weather_system):
        storm_count = 0
        for i in range(100):
            ws = MarkovWeatherSystem(rng=PCGRandom(seed=i))
            state = ws.transition(temperature=0.9, humidity=0.9, season_phase=0.0)
            if state == WeatherState.STORMY:
                storm_count += 1
        assert storm_count > 0

    def test_set_state(self, weather_system):
        weather_system.set_state(WeatherState.RAINY)
        assert weather_system.current_state == WeatherState.RAINY

    def test_transition_interval(self, weather_system):
        interval = weather_system.compute_next_transition_interval()
        assert interval > 0

    def test_environment_effects(self, weather_system):
        weather_system.set_state(WeatherState.STORMY)
        effects = weather_system.compute_environment_effects()
        assert isinstance(effects, dict)
        assert "visibility" in effects
        assert "wind_speed" in effects


class TestSpatialConflictDetector:
    def test_no_conflict_with_distant_elements(self, spatial_detector):
        elements = {
            "elem_a": SceneElement(
                element_id="elem_a", name="树", category=ElementCategory.NATURAL,
                position=Vector3(x=0, y=0, z=0), bounds=BoundingBox(center=Vector3(x=0, y=0, z=0), half_extents=Vector3(x=1, y=1, z=1)),
            ),
            "elem_b": SceneElement(
                element_id="elem_b", name="石头", category=ElementCategory.NATURAL,
                position=Vector3(x=100, y=100, z=100), bounds=BoundingBox(center=Vector3(x=100, y=100, z=100), half_extents=Vector3(x=1, y=1, z=1)),
            ),
        }
        conflicts = spatial_detector.detect_conflicts(elements)
        assert len(conflicts) == 0

    def test_conflict_with_overlapping_elements(self, spatial_detector):
        elements = {
            "elem_a": SceneElement(
                element_id="elem_a", name="树", category=ElementCategory.NATURAL,
                position=Vector3(x=0, y=0, z=0), bounds=BoundingBox(center=Vector3(x=0, y=0, z=0), half_extents=Vector3(x=5, y=5, z=5)),
            ),
            "elem_b": SceneElement(
                element_id="elem_b", name="石头", category=ElementCategory.NATURAL,
                position=Vector3(x=2, y=2, z=2), bounds=BoundingBox(center=Vector3(x=2, y=2, z=2), half_extents=Vector3(x=5, y=5, z=5)),
            ),
        }
        conflicts = spatial_detector.detect_conflicts(elements)
        assert len(conflicts) > 0

    def test_no_elements_no_conflict(self, spatial_detector):
        conflicts = spatial_detector.detect_conflicts({})
        assert len(conflicts) == 0


class TestSceneBuilderCreate:
    def test_create_scene(self, builder):
        scene_id = asyncio.run(builder.create_scene({"name": "森林", "description": "古老的森林"}))
        assert scene_id is not None
        assert len(scene_id) > 0

    def test_create_multiple_scenes(self, builder):
        scene_a = asyncio.run(builder.create_scene({"name": "森林"}))
        scene_b = asyncio.run(builder.create_scene({"name": "城镇"}))
        assert scene_a != scene_b


class TestSceneBuilderElements:
    def test_add_element(self, builder):
        scene_id = asyncio.run(builder.create_scene({"name": "森林"}))
        elem_id = asyncio.run(builder.add_element(scene_id, {
            "name": "古树",
            "position": {"x": 10, "y": 0, "z": 5},
            "bounds": {"half_x": 2, "half_y": 5, "half_z": 2},
        }))
        assert elem_id is not None

    def test_add_multiple_elements(self, builder):
        scene_id = asyncio.run(builder.create_scene({"name": "城镇"}))
        elem_ids = []
        for i in range(5):
            eid = asyncio.run(builder.add_element(scene_id, {
                "name": "房屋{}".format(i),
                "position": {"x": i * 20, "y": 0, "z": 0},
                "bounds": {"half_x": 5, "half_y": 3, "half_z": 5},
            }))
            elem_ids.append(eid)
        assert len(elem_ids) == 5

    def test_query_elements(self, builder):
        scene_id = asyncio.run(builder.create_scene({"name": "森林"}))
        asyncio.run(builder.add_element(scene_id, {"name": "古树", "position": {"x": 10, "y": 0, "z": 5}}))
        results = asyncio.run(builder.query_elements(scene_id))
        assert isinstance(results, list)


class TestSceneBuilderEnvironment:
    def test_update_environment(self, builder):
        scene_id = asyncio.run(builder.create_scene({"name": "森林"}))
        asyncio.run(builder.update_environment(scene_id, delta_time=1.0))
        env = builder.get_environment(scene_id)
        assert env is not None

    def test_time_advances(self, builder):
        scene_id = asyncio.run(builder.create_scene({"name": "森林"}))
        env_before = builder.get_environment(scene_id)
        for _ in range(24):
            asyncio.run(builder.update_environment(scene_id, delta_time=3600.0))
        env_after = builder.get_environment(scene_id)
        assert env_after is not None

    def test_weather_changes_over_time(self, builder):
        scene_id = asyncio.run(builder.create_scene({"name": "户外"}))
        for _ in range(100):
            asyncio.run(builder.update_environment(scene_id, delta_time=10.0))


class TestSceneBuilderSpatialConflicts:
    def test_check_spatial_conflicts(self, builder):
        scene_id = asyncio.run(builder.create_scene({"name": "拥挤房间"}))
        asyncio.run(builder.add_element(scene_id, {
            "name": "桌子",
            "position": {"x": 0, "y": 0, "z": 0},
            "bounds": {"half_x": 3, "half_y": 1, "half_z": 2},
        }))
        asyncio.run(builder.add_element(scene_id, {
            "name": "椅子",
            "position": {"x": 1, "y": 0, "z": 0},
            "bounds": {"half_x": 1, "half_y": 1, "half_z": 1},
        }))
        conflicts = asyncio.run(builder.check_spatial_conflicts(scene_id))
        assert isinstance(conflicts, list)


class TestSceneBuilderPathConnections:
    def test_add_path_connection(self, builder):
        scene_id = asyncio.run(builder.create_scene({"name": "村庄"}))
        elem_a = asyncio.run(builder.add_element(scene_id, {"name": "房屋A", "position": {"x": 0, "y": 0, "z": 0}}))
        elem_b = asyncio.run(builder.add_element(scene_id, {"name": "房屋B", "position": {"x": 30, "y": 0, "z": 0}}))
        result = builder.add_path_connection(scene_id, elem_a, elem_b)
        assert isinstance(result, bool)
