"""适配器注册表测试"""

import pytest
from luqi_engine.llm.adapter_registry import AdapterRegistry


class TestAdapterRegistrySingleton:
    def test_singleton_pattern(self):
        r1 = AdapterRegistry()
        r2 = AdapterRegistry()
        assert r1 is r2

    def test_reset_creates_new_instance(self):
        r1 = AdapterRegistry()
        AdapterRegistry.reset()
        r2 = AdapterRegistry()
        assert r1 is not r2


class TestAdapterRegistryCRUD:
    def setup_method(self):
        self._original = AdapterRegistry._instance
        AdapterRegistry.reset()

    def teardown_method(self):
        if self._original is not None:
            AdapterRegistry._instance = self._original
        else:
            from luqi_engine.llm import OpenAIAdapter, AnthropicAdapter
            registry = AdapterRegistry()
            if not registry.has("openai"):
                registry.register("openai", OpenAIAdapter)
            if not registry.has("anthropic"):
                registry.register("anthropic", AnthropicAdapter)

    def test_register_and_get(self):
        registry = AdapterRegistry()
        registry.register("test", str)
        assert registry.get("test") is str

    def test_register_overwrite_warning(self):
        registry = AdapterRegistry()
        registry.register("dup", int)
        registry.register("dup", str)
        assert registry.get("dup") is str

    def test_unregister(self):
        registry = AdapterRegistry()
        registry.register("temp", list)
        assert registry.unregister("temp")
        assert registry.get("temp") is None

    def test_unregister_nonexistent(self):
        registry = AdapterRegistry()
        assert not registry.unregister("nonexistent")

    def test_has(self):
        registry = AdapterRegistry()
        registry.register("exists", dict)
        assert registry.has("exists")
        assert not registry.has("missing")

    def test_list_adapters_empty(self):
        registry = AdapterRegistry()
        assert registry.list_adapters() == []

    def test_list_adapters_populated(self):
        registry = AdapterRegistry()
        registry.register("a", int)
        registry.register("b", float)
        names = registry.list_adapters()
        assert "a" in names
        assert "b" in names

    def test_clear(self):
        registry = AdapterRegistry()
        registry.register("a", int)
        registry.clear()
        assert registry.list_adapters() == []


class TestBuiltinAdapters:
    def setup_method(self):
        from luqi_engine.llm import OpenAIAdapter, AnthropicAdapter
        registry = AdapterRegistry()
        if not registry.has("openai"):
            registry.register("openai", OpenAIAdapter)
        if not registry.has("anthropic"):
            registry.register("anthropic", AnthropicAdapter)

    def test_openai_registered_after_import(self):
        from luqi_engine.llm import OpenAIAdapter
        registry = AdapterRegistry()
        assert registry.has("openai")
        assert registry.get("openai") is OpenAIAdapter

    def test_anthropic_registered_after_import(self):
        from luqi_engine.llm import AnthropicAdapter
        registry = AdapterRegistry()
        assert registry.has("anthropic")
        assert registry.get("anthropic") is AnthropicAdapter

    def test_custom_adapter_registration(self):
        registry = AdapterRegistry()

        class CustomAdapter:
            pass

        registry.register("custom", CustomAdapter)
        assert registry.has("custom")
        assert registry.get("custom") is CustomAdapter
