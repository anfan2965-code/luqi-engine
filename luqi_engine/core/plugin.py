from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from luqi_engine.core.logging_config import get_logger

_logger = get_logger(__name__)


class PluginState(Enum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    ERROR = "error"


class PluginBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        ...

    def on_load(self) -> None:
        pass

    def on_init(self, context: Dict[str, Any]) -> None:
        pass

    def on_execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return data

    def on_unload(self) -> None:
        pass


class PluginRecord:
    def __init__(self, plugin: PluginBase) -> None:
        self.plugin = plugin
        self.state = PluginState.UNLOADED
        self.error_message: Optional[str] = None


class PluginManager:
    def __init__(self) -> None:
        self._plugins: Dict[str, PluginRecord] = {}

    def load_plugin(self, plugin: PluginBase) -> None:
        if plugin.name in self._plugins:
            _logger.warning("Plugin '%s' already loaded", plugin.name)
            return
        record = PluginRecord(plugin)
        try:
            plugin.on_load()
            record.state = PluginState.LOADED
            _logger.info("Plugin loaded: %s v%s", plugin.name, plugin.version)
        except Exception as exc:
            record.state = PluginState.ERROR
            record.error_message = str(exc)
            _logger.error("Plugin load failed: %s - %s", plugin.name, exc)
        self._plugins[plugin.name] = record

    def init_plugin(self, name: str, context: Optional[Dict[str, Any]] = None) -> bool:
        record = self._plugins.get(name)
        if record is None or record.state != PluginState.LOADED:
            return False
        try:
            record.plugin.on_init(context or {})
            record.state = PluginState.INITIALIZED
            _logger.info("Plugin initialized: %s", name)
            return True
        except Exception as exc:
            record.state = PluginState.ERROR
            record.error_message = str(exc)
            _logger.error("Plugin init failed: %s - %s", name, exc)
            return False

    def execute_plugin(self, name: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        record = self._plugins.get(name)
        if record is None or record.state not in (PluginState.INITIALIZED, PluginState.ACTIVE):
            return None
        try:
            result = record.plugin.on_execute(data)
            record.state = PluginState.ACTIVE
            return result
        except Exception as exc:
            record.state = PluginState.ERROR
            record.error_message = str(exc)
            _logger.error("Plugin execute failed: %s - %s", name, exc)
            return None

    def unload_plugin(self, name: str) -> bool:
        record = self._plugins.get(name)
        if record is None:
            return False
        try:
            record.plugin.on_unload()
            record.state = PluginState.UNLOADED
            del self._plugins[name]
            _logger.info("Plugin unloaded: %s", name)
            return True
        except Exception as exc:
            _logger.error("Plugin unload failed: %s - %s", name, exc)
            return False

    def get_plugin(self, name: str) -> Optional[PluginBase]:
        record = self._plugins.get(name)
        return record.plugin if record else None

    def get_state(self, name: str) -> Optional[PluginState]:
        record = self._plugins.get(name)
        return record.state if record else None

    def list_plugins(self) -> List[str]:
        return list(self._plugins.keys())

    def unload_all(self) -> None:
        for name in list(self._plugins.keys()):
            self.unload_plugin(name)
