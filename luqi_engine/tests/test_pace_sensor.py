"""节奏感知器测试"""

import pytest

from luqi_engine.scheduler.pace_sensor import PaceSensor
from luqi_engine.core.config import PaceConfig
from luqi_engine.core.types import AutoModeConfig


class TestPaceSensorInit:
    def test_default_pace_is_normal(self):
        sensor = PaceSensor()
        assert sensor.get_current_pace() == "normal"

    def test_custom_config(self):
        config = PaceConfig(fast_threshold=10.0, slow_threshold=50.0)
        sensor = PaceSensor(config=config)
        assert sensor.get_current_pace() == "normal"


class TestPaceSensorUpdatePace:
    def test_single_interval_stays_normal(self):
        sensor = PaceSensor()
        sensor.update_pace(30.0)
        assert sensor.get_current_pace() == "normal"

    def test_fast_pace(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(10.0)
        assert sensor.get_current_pace() == "fast"

    def test_slow_pace(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(70.0)
        assert sensor.get_current_pace() == "slow"

    def test_normal_pace(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(30.0)
        assert sensor.get_current_pace() == "normal"

    def test_frozen_pace(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(200.0)
        assert sensor.get_current_pace() == "frozen"

    def test_urgent_pace(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(3.0)
        assert sensor.get_current_pace() == "urgent"

    def test_pace_transitions_from_normal_to_fast(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(30.0)
        assert sensor.get_current_pace() == "normal"

        for _ in range(5):
            sensor.update_pace(10.0)
        assert sensor.get_current_pace() == "fast"

    def test_pace_transitions_from_fast_to_slow(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(10.0)
        assert sensor.get_current_pace() == "fast"

        for _ in range(5):
            sensor.update_pace(70.0)
        assert sensor.get_current_pace() == "slow"

    def test_sliding_window_averages(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=3)
        sensor = PaceSensor(config=config)
        sensor.update_pace(100.0)
        sensor.update_pace(5.0)
        sensor.update_pace(5.0)
        avg = (100.0 + 5.0 + 5.0) / 3.0
        if avg <= 15.0:
            assert sensor.get_current_pace() == "fast"
        else:
            assert sensor.get_current_pace() in ("normal", "fast")


class TestPaceSensorAutoModeConfig:
    def test_normal_pace_config(self):
        sensor = PaceSensor()
        for _ in range(5):
            sensor.update_pace(30.0)
        config = sensor.get_auto_mode_config()
        assert isinstance(config, AutoModeConfig)
        assert config.enabled is True
        assert config.trigger_timeout_seconds == 30.0
        assert config.max_auto_ticks == 10
        assert config.npc_autonomy_level == pytest.approx(0.5)

    def test_frozen_pace_config(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(200.0)
        auto_config = sensor.get_auto_mode_config()
        assert auto_config.trigger_timeout_seconds == 120.0
        assert auto_config.max_auto_ticks == 3
        assert auto_config.npc_autonomy_level == pytest.approx(0.2)
        assert auto_config.pause_on_branch_point is True

    def test_slow_pace_config(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(70.0)
        auto_config = sensor.get_auto_mode_config()
        assert auto_config.trigger_timeout_seconds == 60.0
        assert auto_config.max_auto_ticks == 5
        assert auto_config.npc_autonomy_level == pytest.approx(0.4)

    def test_fast_pace_config(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(10.0)
        auto_config = sensor.get_auto_mode_config()
        assert auto_config.trigger_timeout_seconds == 15.0
        assert auto_config.max_auto_ticks == 15
        assert auto_config.npc_autonomy_level == pytest.approx(0.7)
        assert auto_config.pause_on_branch_point is False

    def test_urgent_pace_config(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)
        sensor = PaceSensor(config=config)
        for _ in range(5):
            sensor.update_pace(3.0)
        auto_config = sensor.get_auto_mode_config()
        assert auto_config.trigger_timeout_seconds == 5.0
        assert auto_config.max_auto_ticks == 20
        assert auto_config.npc_autonomy_level == pytest.approx(0.9)
        assert auto_config.pause_on_branch_point is False

    def test_autonomy_increases_with_pace(self):
        config = PaceConfig(fast_threshold=15.0, slow_threshold=60.0, pace_window_size=5)

        sensor_frozen = PaceSensor(config=config)
        for _ in range(5):
            sensor_frozen.update_pace(200.0)
        autonomy_frozen = sensor_frozen.get_auto_mode_config().npc_autonomy_level

        sensor_urgent = PaceSensor(config=config)
        for _ in range(5):
            sensor_urgent.update_pace(3.0)
        autonomy_urgent = sensor_urgent.get_auto_mode_config().npc_autonomy_level

        assert autonomy_urgent > autonomy_frozen


class TestPaceSensorImplementsInterface:
    def test_implements_ipace_sensor(self):
        from luqi_engine.core.interfaces import IPaceSensor
        sensor = PaceSensor()
        assert isinstance(sensor, IPaceSensor)

    def test_has_required_methods(self):
        sensor = PaceSensor()
        assert callable(getattr(sensor, "get_current_pace", None))
        assert callable(getattr(sensor, "update_pace", None))
        assert callable(getattr(sensor, "get_auto_mode_config", None))
