import asyncio
import json
import os

import pytest
from unittest.mock import MagicMock

from luqi_engine.engine import LuqiEngine
from luqi_engine.core.snapshot import SnapshotError


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestSaveSnapshotBasic:
    def test_save_snapshot_basic(self, tmp_path):
        engine = LuqiEngine()
        _run_async(engine.initialize())
        save_path = str(tmp_path / "test_snapshot.json")
        result_path = engine.save_snapshot(save_path)
        assert result_path == save_path
        assert os.path.exists(save_path)
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "version" in data
        assert "timestamp" in data
        assert "subsystems" in data
        _run_async(engine.shutdown())


class TestSaveSnapshotDefaultPath:
    def test_save_snapshot_default_path(self, tmp_path):
        default_path = str(tmp_path / "default_snapshot.json")
        engine = LuqiEngine(default_snapshot_path=default_path)
        _run_async(engine.initialize())
        result_path = engine.save_snapshot()
        assert result_path == default_path
        assert os.path.exists(default_path)
        _run_async(engine.shutdown())


class TestLoadSnapshotRecovery:
    def test_load_snapshot_recovery(self, tmp_path):
        engine1 = LuqiEngine()
        _run_async(engine1.initialize())
        snapshot_path = str(tmp_path / "recovery_test.json")
        engine1.save_snapshot(snapshot_path)
        _run_async(engine1.shutdown())

        engine2 = LuqiEngine()
        _run_async(engine2.initialize())
        engine2.load_snapshot(snapshot_path)
        assert engine2._initialized is True
        with open(snapshot_path, "r", encoding="utf-8") as f:
            original_data = json.load(f)
        assert "subsystems" in original_data
        _run_async(engine2.shutdown())


class TestShutdownAutoSave:
    def test_shutdown_auto_save(self, tmp_path):
        snapshot_path = str(tmp_path / "auto_save_snapshot.json")
        engine = LuqiEngine(default_snapshot_path=snapshot_path)
        _run_async(engine.initialize())
        assert not os.path.exists(snapshot_path)
        _run_async(engine.shutdown())
        assert os.path.exists(snapshot_path)
        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "version" in data


class TestInitializeWithSnapshotPath:
    def test_initialize_with_snapshot_path(self, tmp_path):
        engine1 = LuqiEngine()
        _run_async(engine1.initialize())
        snapshot_path = str(tmp_path / "init_snapshot.json")
        engine1.save_snapshot(snapshot_path)
        _run_async(engine1.shutdown())

        engine2 = LuqiEngine()
        _run_async(engine2.initialize(snapshot_path=snapshot_path))
        assert engine2._initialized is True
        _run_async(engine2.shutdown())


class TestInitializeSnapshotFallback:
    def test_initialize_snapshot_fallback(self, tmp_path):
        invalid_path = str(tmp_path / "nonexistent_snapshot.json")
        engine = LuqiEngine()
        _run_async(engine.initialize(snapshot_path=invalid_path))
        assert engine._initialized is True
        _run_async(engine.shutdown())


class TestSaveSnapshotUninitialized:
    def test_save_snapshot_uninitialized(self):
        engine = LuqiEngine()
        with pytest.raises(RuntimeError, match="引擎未初始化"):
            engine.save_snapshot()


class TestLoadSnapshotCorrupted:
    def test_load_snapshot_corrupted(self, tmp_path):
        corrupted_path = str(tmp_path / "corrupted_snapshot.json")
        with open(corrupted_path, "w", encoding="utf-8") as f:
            f.write("{invalid json content!!!")
        engine = LuqiEngine()
        with pytest.raises(SnapshotError):
            engine.load_snapshot(corrupted_path)


class TestSnapshotIntegration:
    def test_multiple_snapshots_independent(self, tmp_path):
        engine = LuqiEngine()
        _run_async(engine.initialize())
        path1 = str(tmp_path / "snapshot1.json")
        path2 = str(tmp_path / "snapshot2.json")
        result1 = engine.save_snapshot(path1)
        result2 = engine.save_snapshot(path2)
        assert result1 == path1
        assert result2 == path2
        assert os.path.exists(path1)
        assert os.path.exists(path2)
        with open(path1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        with open(path2, "r", encoding="utf-8") as f:
            data2 = json.load(f)
        assert data1["version"] == data2["version"]
        _run_async(engine.shutdown())

    def test_shutdown_without_default_path_no_error(self):
        engine = LuqiEngine()
        _run_async(engine.initialize())
        _run_async(engine.shutdown())
        assert engine._initialized is False
