"""认知记忆服务测试"""

import pytest
from luqi_engine.cognitive_memory.service import MemoryService
from luqi_engine.character.memory import MemoryEntry
from luqi_engine.core.config import CognitiveMemoryConfig


class TestMemoryServiceCreation:
    def test_default_creation(self):
        svc = MemoryService()
        assert svc is not None

    def test_with_config(self):
        cfg = CognitiveMemoryConfig(short_term_capacity=50)
        svc = MemoryService(config=cfg)
        assert svc is not None


class TestMemoryServiceStoreOps:
    def setup_method(self):
        self.svc = MemoryService()

    def test_write_and_retrieve(self):
        entry = MemoryEntry(who="char_a", what="今天吃了面包", where="厨房", why="饿了")
        result = self.svc.write_agent("char_1", entry)
        assert "surprise" in result
        assert "target_tier" in result

    def test_retrieve_after_write(self):
        self.svc.write_agent("char_1", MemoryEntry(who="c", what="重要事件", importance=0.9))
        results = self.svc.retrieval_agent("char_1", "事件")
        assert len(results) > 0

    def test_multiple_entries(self):
        for i in range(5):
            self.svc.write_agent("lim", MemoryEntry(who="l", what=f"item{i}"))
        results = self.svc.retrieval_agent("lim", "item")
        # 修复弱断言：验证至少返回5个结果
        assert len(results) >= 5, f"Expected at least 5 results, got {len(results)}"

    def test_separate_character_stores(self):
        self.svc.write_agent("a", MemoryEntry(who="a", what="A的事件"))
        self.svc.write_agent("b", MemoryEntry(who="b", what="B的事件"))
        a_res = self.svc.retrieval_agent("a", "A")
        b_res = self.svc.retrieval_agent("b", "B")
        assert len(a_res) > 0
        assert len(b_res) > 0

    def test_limit_parameter(self):
        for i in range(10):
            self.svc.write_agent("lim", MemoryEntry(who="l", what=f"item{i}"))
        results = self.svc.retrieval_agent("lim", "", limit=3)
        assert len(results) <= 3


class TestMemoryServiceConsolidation:
    def setup_method(self):
        self.svc = MemoryService()

    def test_consolidation_runs(self):
        for i in range(3):
            self.svc.write_agent("cons", MemoryEntry(who="c", what=f"记忆{i}", importance=0.9))
        report = self.svc.consolidation_agent("cons")
        assert report is not None

    def test_consolidation_empty_store(self):
        report = self.svc.consolidation_agent("empty")
        assert report is not None


class TestMemoryServiceSharedMemory:
    def setup_method(self):
        cfg = CognitiveMemoryConfig(shared_memory_enabled=True)
        self.svc = MemoryService(config=cfg)

    def test_store_shared_memory(self):
        self.svc.store_shared_memory(
            event_id="evt_1",
            content={"text": "共同经历"},
            participant_ids=["a", "b"],
            emotional_valence=0.6,
        )

    def test_retrieve_shared_includes_shared(self):
        self.svc.store_shared_memory(
            event_id="evt_2",
            content={"text": "共享记忆"},
            participant_ids=["x"],
        )
        results = self.svc.retrieval_agent("x", "共享")
        shared_found = any(r.get("shared") for r in results)
        assert shared_found is True


class TestMemoryServiceDecay:
    def test_decay_all_does_not_crash(self):
        svc = MemoryService()
        svc.write_agent("d", MemoryEntry(who="d", what="temp"))
        svc.decay_all()


class TestMemoryServiceTools:
    def setup_method(self):
        self.svc = MemoryService()

    def test_memory_search_tool(self):
        self.svc.write_agent("tool", MemoryEntry(who="t", what="搜索目标"))
        result = self.svc.memory_tool_call("tool", "memory_search", {"query": "搜索目标"})
        assert result is not None

    def test_unknown_tool_returns_none(self):
        result = self.svc.memory_tool_call("t", "unknown_tool", {})
        assert result is None
