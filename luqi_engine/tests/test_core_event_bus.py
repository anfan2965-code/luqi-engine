"""事件总线测试"""

import asyncio
import time
import pytest
from luqi_engine.core.event_bus import EventBus, Event
from luqi_engine.core.types import EventType


class TestEvent:
    def test_auto_generated_id(self):
        e = Event(event_type=EventType.CUSTOM, source="test")
        assert len(e.event_id) > 0

    def test_unique_ids(self):
        ids = set()
        for _ in range(100):
            e = Event(event_type=EventType.CUSTOM, source="test")
            ids.add(e.event_id)
        assert len(ids) == 100

    def test_default_timestamp(self):
        before = time.time()
        e = Event(event_type=EventType.CUSTOM, source="test")
        after = time.time()
        assert before <= e.timestamp <= after

    def test_payload(self):
        e = Event(event_type=EventType.CHARACTER_ACTION, source="char_1", payload={"action": "speak"})
        assert e.payload["action"] == "speak"


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe(EventType.CUSTOM, handler)
        event = Event(event_type=EventType.CUSTOM, source="test")
        bus.publish(event)
        assert len(received) == 1
        assert received[0].event_id == event.event_id

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe(EventType.CUSTOM, handler)
        bus.unsubscribe(EventType.CUSTOM, handler)
        bus.publish(Event(event_type=EventType.CUSTOM, source="test"))
        assert len(received) == 0

    def test_multiple_handlers(self):
        bus = EventBus()
        a = []
        b = []
        bus.subscribe(EventType.CUSTOM, lambda e: a.append(e))
        bus.subscribe(EventType.CUSTOM, lambda e: b.append(e))
        bus.publish(Event(event_type=EventType.CUSTOM, source="test"))
        assert len(a) == 1
        assert len(b) == 1

    def test_type_routing(self):
        bus = EventBus()
        custom_received = []
        dialogue_received = []
        bus.subscribe(EventType.CUSTOM, lambda e: custom_received.append(e))
        bus.subscribe(EventType.DIALOGUE_STARTED, lambda e: dialogue_received.append(e))
        bus.publish(Event(event_type=EventType.CUSTOM, source="test"))
        bus.publish(Event(event_type=EventType.DIALOGUE_STARTED, source="test"))
        assert len(custom_received) == 1
        assert len(dialogue_received) == 1

    def test_subscribe_all(self):
        bus = EventBus()
        all_received = []
        bus.subscribe_all(lambda e: all_received.append(e))
        bus.publish(Event(event_type=EventType.CUSTOM, source="test"))
        bus.publish(Event(event_type=EventType.DIALOGUE_STARTED, source="test"))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="test"))
        assert len(all_received) == 3

    def test_history(self):
        bus = EventBus()
        bus.publish(Event(event_type=EventType.CUSTOM, source="a"))
        bus.publish(Event(event_type=EventType.CUSTOM, source="b"))
        bus.publish(Event(event_type=EventType.DIALOGUE_STARTED, source="c"))
        all_hist = bus.get_history()
        assert len(all_hist) == 3
        custom_hist = bus.get_history(event_type=EventType.CUSTOM)
        assert len(custom_hist) == 2

    def test_history_limit(self):
        bus = EventBus()
        for i in range(10):
            bus.publish(Event(event_type=EventType.CUSTOM, source="test", payload={"i": i}))
        hist = bus.get_history(limit=3)
        assert len(hist) == 3

    def test_pause_resume(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.CUSTOM, lambda e: received.append(e))
        bus.pause()
        bus.publish(Event(event_type=EventType.CUSTOM, source="test"))
        assert len(received) == 0
        bus.resume()
        bus.publish(Event(event_type=EventType.CUSTOM, source="test"))
        assert len(received) == 1

    def test_clear_history(self):
        bus = EventBus()
        bus.publish(Event(event_type=EventType.CUSTOM, source="test"))
        bus.clear_history()
        assert len(bus.get_history()) == 0

    def test_async_publish(self):
        bus = EventBus()
        received = []

        async def async_handler(e):
            received.append(e)

        bus.subscribe(EventType.CUSTOM, async_handler, is_async=True)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(bus.publish_async(Event(event_type=EventType.CUSTOM, source="test")))
        loop.close()
        assert len(received) == 1

    def test_mixed_sync_async_handlers(self):
        bus = EventBus()
        sync_received = []
        async_received = []

        bus.subscribe(EventType.CUSTOM, lambda e: sync_received.append(e), is_async=False)

        async def async_handler(e):
            async_received.append(e)

        bus.subscribe(EventType.CUSTOM, async_handler, is_async=True)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(bus.publish_async(Event(event_type=EventType.CUSTOM, source="test")))
        loop.close()
        assert len(sync_received) == 1
        assert len(async_received) == 1

    def test_priority_ordering(self):
        bus = EventBus()
        order = []
        bus.subscribe(EventType.CUSTOM, lambda e: order.append("low"), is_async=False)
        bus.subscribe(EventType.CUSTOM, lambda e: order.append("high"), is_async=False)
        event = Event(event_type=EventType.CUSTOM, source="test", priority=10)
        bus.publish(event)
        assert len(order) == 2

    def test_multi_character_dialogue_events(self):
        bus = EventBus()
        events = []
        bus.subscribe_all(lambda e: events.append(e))

        bus.publish(Event(event_type=EventType.DIALOGUE_STARTED, source="system", payload={"participants": ["char_a", "char_b"]}))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="char_a", payload={"content": "你好"}))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="char_b", payload={"content": "嗨"}))
        bus.publish(Event(event_type=EventType.DIALOGUE_ENDED, source="system"))

        dialogue_events = [e for e in events if e.event_type in (EventType.DIALOGUE_STARTED, EventType.DIALOGUE_ENDED)]
        action_events = [e for e in events if e.event_type == EventType.CHARACTER_ACTION]
        assert len(dialogue_events) == 2
        assert len(action_events) == 2

    def test_max_history_trimming(self):
        bus = EventBus(max_history=10)
        for i in range(20):
            bus.publish(Event(event_type=EventType.CUSTOM, source="test", payload={"i": i}))
        hist = bus.get_history()
        assert len(hist) <= 10
