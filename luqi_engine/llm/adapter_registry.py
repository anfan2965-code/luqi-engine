"""适配器注册表 - 管理LLM适配器的注册和获取"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Type

from luqi_engine.core.logging_config import get_logger

_logger = get_logger(__name__)


class AdapterRegistry:
    _instance: Optional[AdapterRegistry] = None

    def __new__(cls) -> AdapterRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry: Dict[str, Type[Any]] = {}
        return cls._instance

    def register(self, name: str, adapter_class: Type[Any]) -> None:
        if name in self._registry:
            _logger.warning("Adapter '%s' already registered, overwriting", name)
        self._registry[name] = adapter_class
        _logger.info("Registered adapter: %s", name)

    def unregister(self, name: str) -> bool:
        if name in self._registry:
            del self._registry[name]
            _logger.info("Unregistered adapter: %s", name)
            return True
        _logger.warning("Adapter '%s' not found for unregistration", name)
        return False

    def get(self, name: str) -> Optional[Type[Any]]:
        return self._registry.get(name)

    def has(self, name: str) -> bool:
        return name in self._registry

    def list_adapters(self) -> list:
        return list(self._registry.keys())

    def clear(self) -> None:
        self._registry.clear()

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
