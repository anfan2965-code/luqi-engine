from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List

from luqi_engine.core.logging_config import get_logger

_logger = get_logger(__name__)


class MiddlewareBase(ABC):
    @abstractmethod
    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return request

    def process_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return response


class LoggingMiddleware(MiddlewareBase):
    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        _logger.info("Request: %s", request.get("action", "unknown"))
        return request

    def process_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        _logger.info("Response: status=%s", response.get("status", "unknown"))
        return response


class MiddlewarePipeline:
    def __init__(self) -> None:
        self._middlewares: List[MiddlewareBase] = []

    def add_middleware(self, middleware: MiddlewareBase) -> None:
        self._middlewares.append(middleware)

    def remove_middleware(self, middleware_type: type) -> bool:
        for i, mw in enumerate(self._middlewares):
            if isinstance(mw, middleware_type):
                self._middlewares.pop(i)
                return True
        return False

    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        result = request
        for mw in self._middlewares:
            try:
                result = mw.process_request(result)
            except Exception as exc:
                _logger.error("Middleware request processing failed: %s - %s", type(mw).__name__, exc)
        return result

    def process_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        result = response
        for mw in reversed(self._middlewares):
            try:
                result = mw.process_response(result)
            except Exception as exc:
                _logger.error("Middleware response processing failed: %s - %s", type(mw).__name__, exc)
        return result

    def execute(self, request: Dict[str, Any], handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        processed_request = self.process_request(request)
        response = handler(processed_request)
        return self.process_response(response)

    @property
    def middleware_count(self) -> int:
        return len(self._middlewares)

    def clear(self) -> None:
        self._middlewares.clear()
