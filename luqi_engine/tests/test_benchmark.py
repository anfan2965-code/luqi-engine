"""
性能基准测试 - 测试关键路径的性能

使用pytest-benchmark测量关键操作的执行时间
"""

from __future__ import annotations

import pytest

from luqi_engine.core.rng import PCGRandom
from luqi_engine.core.event_bus import EventBus, Event, EventType
from luqi_engine.character.personality import OceanPersonality
from luqi_engine.character.emotion import PADState, ocean_to_pad_baseline
from luqi_engine.character.desire import DesireEngine
from luqi_engine.character.goap import GOAPPlanner, GOAPAction, GOAPWorldState


class TestPCGRandomBenchmark:
    """PCG随机数生成器性能基准"""

    def test_next_uint32(self, benchmark):
        """测量next_uint32性能"""
        rng = PCGRandom(seed=42)
        benchmark(rng.next_uint32)

    def test_uniform(self, benchmark):
        """测量uniform性能"""
        rng = PCGRandom(seed=42)
        benchmark(rng.uniform)

    def test_gaussian(self, benchmark):
        """测量gaussian性能"""
        rng = PCGRandom(seed=42)
        benchmark(rng.gaussian)

    def test_weighted_choice(self, benchmark):
        """测量weighted_choice性能"""
        rng = PCGRandom(seed=42)
        weights = [0.1, 0.2, 0.3, 0.4]
        benchmark(rng.weighted_choice, weights)


class TestEventBusBenchmark:
    """EventBus性能基准"""

    def test_publish_sync(self, benchmark):
        """测量同步发布性能"""
        bus = EventBus()
        bus.resume()
        event = Event(event_type=EventType.CUSTOM, source="test", payload={})
        bus.subscribe(EventType.CUSTOM, lambda e: None)
        benchmark(bus.publish, event)

    def test_subscribe(self, benchmark):
        """测量订阅性能"""
        bus = EventBus()
        handler = lambda e: None
        benchmark(bus.subscribe, EventType.CUSTOM, handler)


class TestPersonalityBenchmark:
    """人格系统性能基准"""

    def test_ocean_creation(self, benchmark):
        """测量OCEAN人格创建性能"""
        benchmark(OceanPersonality)

    def test_get_score(self, benchmark):
        """测量获取分数性能"""
        personality = OceanPersonality()
        benchmark(personality.get_score, "openness")

    def test_to_dict(self, benchmark):
        """测量序列化性能"""
        personality = OceanPersonality()
        benchmark(personality.to_dict)


class TestEmotionBenchmark:
    """情感系统性能基准"""

    def test_pad_state_creation(self, benchmark):
        """测量PAD状态创建性能"""
        benchmark(PADState)

    def test_ocean_to_pad_baseline(self, benchmark):
        """测量OCEAN到PAD基线转换性能"""
        personality = OceanPersonality()
        benchmark(ocean_to_pad_baseline, personality.to_dict())

    def test_pad_update(self, benchmark):
        """测量PAD更新性能"""
        emotion = PADState()
        benchmark(emotion.update, 0.1, 0.2, 0.3)


class TestDesireBenchmark:
    """欲望系统性能基准"""

    def test_desire_engine_creation(self, benchmark):
        """测量欲望引擎创建性能"""
        benchmark(DesireEngine)


class TestGOAPBenchmark:
    """GOAP规划器性能基准"""

    def test_planner_creation(self, benchmark):
        """测量规划器创建性能"""
        benchmark(GOAPPlanner)


class TestIntegrationBenchmark:
    """集成性能基准"""

    def test_full_personality_emotion_cycle(self, benchmark):
        """测量完整人格-情感循环性能"""
        def cycle():
            personality = OceanPersonality()
            emotion = ocean_to_pad_baseline(personality.to_dict())
            return emotion
        
        benchmark(cycle)
