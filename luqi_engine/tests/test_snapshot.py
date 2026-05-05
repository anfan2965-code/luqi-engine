"""快照系统测试"""

import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from luqi_engine.core.snapshot import ISnapshotable, SnapshotError, EngineSnapshot
from luqi_engine.worldview.renderer import WorldViewRenderer
from luqi_engine.narrative.controller import NarrativeController, NodeType
from luqi_engine.scene.builder import SceneBuilder
from luqi_engine.interaction.coordinator import InteractionCoordinator
from luqi_engine.character.character_manager import CharacterManager


class TestISnapshotableProtocol:
    def test_isnapshotable_is_abstract(self):
        with pytest.raises(TypeError):
            ISnapshotable()

    def test_worldview_renderer_implements_snapshotable(self):
        renderer = WorldViewRenderer()
        assert isinstance(renderer, ISnapshotable)
        assert hasattr(renderer, "save_snapshot")
        assert hasattr(renderer, "load_snapshot")

    def test_narrative_controller_implements_snapshotable(self):
        controller = NarrativeController()
        assert isinstance(controller, ISnapshotable)

    def test_scene_builder_implements_snapshotable(self):
        builder = SceneBuilder()
        assert isinstance(builder, ISnapshotable)

    def test_interaction_coordinator_implements_snapshotable(self):
        coordinator = InteractionCoordinator()
        assert isinstance(coordinator, ISnapshotable)

    def test_character_manager_implements_snapshotable(self):
        manager = CharacterManager()
        assert isinstance(manager, ISnapshotable)


class TestEngineSnapshotSave:
    def test_save_generates_valid_json(self, tmp_path):
        mock_engine = MagicMock()
        mock_subsystem = MagicMock(spec=ISnapshotable)
        mock_subsystem.save_snapshot.return_value = {"test": "data"}
        mock_engine.worldview = mock_subsystem
        mock_engine.narrative = mock_subsystem
        mock_engine.scene = mock_subsystem
        mock_engine.interaction = mock_subsystem
        mock_engine.character_manager = mock_subsystem

        save_path = str(tmp_path / "test_snapshot.json")
        result_path = EngineSnapshot.save(mock_engine, save_path)

        assert result_path == save_path
        assert os.path.exists(save_path)

        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == EngineSnapshot.SNAPSHOT_VERSION
        assert "timestamp" in data
        assert "subsystems" in data
        assert "worldview" in data["subsystems"]

    def test_save_atomic_write(self, tmp_path):
        mock_engine = MagicMock()
        mock_subsystem = MagicMock(spec=ISnapshotable)
        mock_subsystem.save_snapshot.return_value = {}
        mock_engine.worldview = mock_subsystem
        mock_engine.narrative = mock_subsystem
        mock_engine.scene = mock_subsystem
        mock_engine.interaction = mock_subsystem
        mock_engine.character_manager = mock_subsystem

        save_path = str(tmp_path / "atomic_test.json")
        EngineSnapshot.save(mock_engine, save_path)

        tmp_path_candidate = save_path + ".tmp"
        assert not os.path.exists(tmp_path_candidate)
        assert os.path.exists(save_path)

    def test_save_missing_subsystem_raises_error(self, tmp_path):
        mock_engine = MagicMock()
        mock_engine.worldview = None
        mock_engine.narrative = None
        mock_engine.scene = "not_snapshotable"
        mock_engine.interaction = None
        mock_engine.character_manager = None

        with pytest.raises(SnapshotError, match="未实现 ISnapshotable"):
            EngineSnapshot.save(mock_engine, str(tmp_path / "bad.json"))

    def test_save_creates_parent_directories(self, tmp_path):
        mock_engine = MagicMock()
        mock_subsystem = MagicMock(spec=ISnapshotable)
        mock_subsystem.save_snapshot.return_value = {}
        mock_engine.worldview = mock_subsystem
        mock_engine.narrative = mock_subsystem
        mock_engine.scene = mock_subsystem
        mock_engine.interaction = mock_subsystem
        mock_engine.character_manager = mock_subsystem

        nested_path = str(tmp_path / "nested" / "dir" / "snapshot.json")
        result = EngineSnapshot.save(mock_engine, nested_path)
        assert os.path.exists(result)


class TestEngineSnapshotLoad:
    def test_load_valid_snapshot(self, tmp_path):
        snapshot_data = {
            "version": "1.0",
            "timestamp": 1000.0,
            "subsystems": {
                "worldview": {"elements": {}, "relations": {}, "world_model": {}},
                "narrative": {},
                "scene": {},
                "interaction": {},
                "character_manager": {},
            },
        }
        snap_path = tmp_path / "valid_snap.json"
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f)

        result = EngineSnapshot.load(str(snap_path))
        assert result["version"] == "1.0"
        assert result["timestamp"] == 1000.0
        assert "subsystems" in result

    def test_load_nonexistent_file_raises_error(self):
        with pytest.raises(SnapshotError, match="不存在"):
            EngineSnapshot.load("/nonexistent/path/snapshot.json")

    def test_load_invalid_json_raises_error(self, tmp_path):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("{invalid json}", encoding="utf-8")

        with pytest.raises(SnapshotError, match="读取快照文件失败"):
            EngineSnapshot.load(str(bad_path))

    def test_load_missing_version_raises_error(self, tmp_path):
        no_version = {"timestamp": 0, "subsystems": {}}
        snap_path = tmp_path / "no_version.json"
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(no_version, f)

        with pytest.raises(SnapshotError, match="version"):
            EngineSnapshot.load(str(snap_path))

    def test_load_version_mismatch_raises_error(self, tmp_path):
        wrong_version = {
            "version": "99.0",
            "timestamp": 0,
            "subsystems": {},
        }
        snap_path = tmp_path / "wrong_version.json"
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(wrong_version, f)

        with pytest.raises(SnapshotError, match="版本不兼容"):
            EngineSnapshot.load(str(snap_path))

    def test_load_missing_subsystems_raises_error(self, tmp_path):
        no_subsystems = {"version": "1.0", "timestamp": 0}
        snap_path = tmp_path / "no_subsystems.json"
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(no_subsystems, f)

        with pytest.raises(SnapshotError, match="subsystems"):
            EngineSnapshot.load(str(snap_path))


class TestWorldViewRendererRoundTrip:
    def test_round_trip_empty_state(self):
        renderer = WorldViewRenderer()
        data = renderer.save_snapshot()
        assert isinstance(data, dict)
        assert "elements" in data
        assert "relations" in data
        assert "world_model" in data

        new_renderer = WorldViewRenderer()
        new_renderer.load_snapshot(data)
        restored = new_renderer.save_snapshot()
        assert restored == data

    def test_round_trip_with_data(self):
        import asyncio

        renderer = WorldViewRenderer()
        elements = asyncio.run(renderer.extract_elements(
            "- 龙脊山: 北方最高的山脉\n- 元素魔法: 基于自然元素的魔法体系",
            "text",
        ))
        classified = asyncio.run(renderer.classify_elements(elements))
        asyncio.run(renderer.build_relations(classified))

        data = renderer.save_snapshot()
        assert len(data["elements"]) > 0 or len(data["relations"]) > 0

        new_renderer = WorldViewRenderer()
        new_renderer.load_snapshot(data)
        restored = new_renderer.save_snapshot()
        assert restored["elements"] == data["elements"]
        assert restored["relations"] == data["relations"]


class TestNarrativeControllerRoundTrip:
    def test_round_trip_with_nodes(self):
        controller = NarrativeController()
        root_id = controller.add_story_node("开端", NodeType.KEY_EVENT, "故事开始")
        child_id = controller.add_story_node("冲突", NodeType.TURNING_POINT, "矛盾出现", parent_id=root_id)
        branch_id = controller.create_branch(root_id)

        data = controller.save_snapshot()
        assert data["root_node_id"] == root_id
        assert len(data["nodes"]) == 2
        assert len(data["branches"]) == 1

        new_controller = NarrativeController()
        new_controller.load_snapshot(data)
        restored = new_controller.save_snapshot()
        assert restored["root_node_id"] == data["root_node_id"]
        assert len(restored["nodes"]) == len(data["nodes"])
        assert restored["elasticity"] == data["elasticity"]
        assert restored["core_story_progress"] == data["core_story_progress"]

    def test_round_trip_empty_controller(self):
        controller = NarrativeController()
        data = controller.save_snapshot()

        new_controller = NarrativeController()
        new_controller.load_snapshot(data)
        restored = new_controller.save_snapshot()
        assert restored == data


class TestSceneBuilderRoundTrip:
    def test_round_trip_with_scene(self):
        import asyncio

        builder = SceneBuilder()
        scene_id = asyncio.run(builder.create_scene({
            "name": "测试场景",
            "initial_weather": "CLEAR",
        }))
        asyncio.run(builder.add_element(scene_id, {
            "name": "测试树",
            "category": "natural",
            "position": {"x": 1.0, "y": 0.0, "z": 2.0},
        }))

        data = builder.save_snapshot()
        assert scene_id in data["scenes"]
        assert scene_id in data["elements"]
        assert scene_id in data["environments"]

        new_builder = SceneBuilder()
        new_builder.load_snapshot(data)
        restored = new_builder.save_snapshot()
        assert len(restored["scenes"]) == len(data["scenes"])
        assert len(restored["elements"][scene_id]) == len(data["elements"][scene_id])
        assert restored["environments"][scene_id]["weather"] == data["environments"][scene_id]["weather"]

    def test_round_trip_empty_builder(self):
        builder = SceneBuilder()
        data = builder.save_snapshot()

        new_builder = SceneBuilder()
        new_builder.load_snapshot(data)
        restored = new_builder.save_snapshot()
        assert restored == data


class TestInteractionCoordinatorRoundTrip:
    def test_round_trip_with_relationships(self):
        coordinator = InteractionCoordinator()
        coordinator.register_character("char_a", {"extraversion": 70})
        coordinator.register_character("char_b", {"extraversion": 40})

        import asyncio
        asyncio.run(coordinator.update_relationship("char_a", "char_b", {"friendship": 0.3}))

        data = coordinator.save_snapshot()
        assert len(data["relationship_edges"]) > 0
        assert "char_a" in data["character_data"]

        new_coordinator = InteractionCoordinator()
        new_coordinator.load_snapshot(data)
        restored = new_coordinator.save_snapshot()
        assert len(restored["relationship_edges"]) == len(data["relationship_edges"])
        assert len(restored["character_data"]) == len(data["character_data"])

    def test_round_trip_empty_coordinator(self):
        coordinator = InteractionCoordinator()
        data = coordinator.save_snapshot()

        new_coordinator = InteractionCoordinator()
        new_coordinator.load_snapshot(data)
        restored = new_coordinator.save_snapshot()
        assert restored == data


class TestCharacterManagerRoundTrip:
    def test_round_trip_with_characters(self):
        import asyncio

        manager = CharacterManager()
        char_id = asyncio.run(manager.create_character({
            "name": "测试角色",
            "template": "guard",
        }))

        data = manager.save_snapshot()
        assert len(data["characters"]) == 1
        assert data["characters"][0]["name"] == "测试角色"

        new_manager = CharacterManager()
        new_manager.load_snapshot(data)
        restored = new_manager.save_snapshot()
        assert len(restored["characters"]) == len(data["characters"])
        assert restored["characters"][0]["entity_id"] == data["characters"][0]["entity_id"]

    def test_round_trip_empty_manager(self):
        manager = CharacterManager()
        data = manager.save_snapshot()

        new_manager = CharacterManager()
        new_manager.load_snapshot(data)
        restored = new_manager.save_snapshot()
        assert restored == data
