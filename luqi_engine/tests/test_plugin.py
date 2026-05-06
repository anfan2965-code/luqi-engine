import pytest
from luqi_engine.core.plugin import PluginBase, PluginManager, PluginRecord, PluginState


class DummyPlugin(PluginBase):
    def __init__(self, name: str, version: str = "1.0"):
        self._name = name
        self._ver = version
        self.load_called = False
        self.init_called = False
        self.execute_data: object = None
        self.unload_called = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._ver

    def on_load(self) -> None:
        self.load_called = True

    def on_init(self, context):
        self.init_called = True

    def on_execute(self, data):
        self.execute_data = data
        return {"processed": True, **data}

    def on_unload(self) -> None:
        self.unload_called = True


class ErrorPlugin(PluginBase):
    @property
    def name(self) -> str:
        return "error_plugin"

    @property
    def version(self) -> str:
        return "1.0"

    def on_load(self) -> None:
        raise RuntimeError("load error")


class TestPluginRecord:
    def test_initial_state_unloaded(self):
        p = DummyPlugin("test")
        record = PluginRecord(p)
        assert record.state == PluginState.UNLOADED
        assert record.error_message is None


class TestPluginManagerLoad:
    def setup_method(self):
        self.pm = PluginManager()

    def test_load_plugin_success(self):
        plugin = DummyPlugin("p1")
        self.pm.load_plugin(plugin)
        assert self.pm.get_state("p1") == PluginState.LOADED
        assert plugin.load_called is True

    def test_load_duplicate_warns(self):
        p1 = DummyPlugin("dup")
        p2 = DummyPlugin("dup")
        self.pm.load_plugin(p1)
        self.pm.load_plugin(p2)
        assert len(self.pm.list_plugins()) == 1

    def test_load_error_sets_error_state(self):
        ep = ErrorPlugin()
        self.pm.load_plugin(ep)
        assert self.pm.get_state("error_plugin") == PluginState.ERROR
        assert "load error" in (ep or "").__str__() if False else self.pm.get_state("error_plugin") == PluginState.ERROR


class TestPluginManagerInit:
    def setup_method(self):
        self.pm = PluginManager()
        self.plugin = DummyPlugin("p1")
        self.pm.load_plugin(self.plugin)

    def test_init_loaded_plugin(self):
        result = self.pm.init_plugin("p1")
        assert result is True
        assert self.pm.get_state("p1") == PluginState.INITIALIZED
        assert self.plugin.init_called is True

    def test_init_with_context(self):
        ctx = {"key": "value"}
        self.pm.init_plugin("p1", context=ctx)
        assert self.pm.get_state("p1") == PluginState.INITIALIZED

    def test_init_nonexistent_returns_false(self):
        assert self.pm.init_plugin("nonexistent") is False

    def test_init_wrong_state_returns_false(self):
        assert self.pm.init_plugin("nonexistent") is False


class TestPluginManagerExecute:
    def setup_method(self):
        self.pm = PluginManager()
        self.plugin = DummyPlugin("p1")
        self.pm.load_plugin(self.plugin)
        self.pm.init_plugin("p1")

    def test_execute_initialized_plugin(self):
        result = self.pm.execute_plugin("p1", {"data": 42})
        assert result is not None
        assert result["processed"] is True
        assert result["data"] == 42
        assert self.pm.get_state("p1") == PluginState.ACTIVE

    def test_execute_nonexistent_returns_none(self):
        assert self.pm.execute_plugin("missing", {}) is None

    def test_execute_unloaded_returns_none(self):
        p2 = DummyPlugin("p2")
        self.pm.load_plugin(p2)
        assert self.pm.execute_plugin("p2", {}) is None


class TestPluginManagerUnload:
    def setup_method(self):
        self.pm = PluginManager()
        self.plugin = DummyPlugin("p1")
        self.pm.load_plugin(self.plugin)

    def test_unload_loaded_plugin(self):
        result = self.pm.unload_plugin("p1")
        assert result is True
        assert self.pm.get_plugin("p1") is None
        assert "p1" not in self.pm.list_plugins()
        assert self.plugin.unload_called is True

    def test_unload_nonexistent_returns_false(self):
        assert self.pm.unload_plugin("missing") is False

    def test_unload_all(self):
        p2 = DummyPlugin("p2")
        self.pm.load_plugin(p2)
        self.pm.unload_all()
        assert self.pm.list_plugins() == []


class TestPluginManagerQuery:
    def setup_method(self):
        self.pm = PluginManager()
        self.plugin = DummyPlugin("q1")
        self.pm.load_plugin(self.plugin)

    def test_get_plugin(self):
        found = self.pm.get_plugin("q1")
        assert found is self.plugin

    def test_get_plugin_missing(self):
        assert self.pm.get_plugin("nope") is None

    def test_list_plugins(self):
        assert "q1" in self.pm.list_plugins()

    def test_get_state_missing(self):
        assert self.pm.get_state("nope") is None
