from __future__ import annotations

import asyncio
import json
import time
import urllib.request
import urllib.error
from typing import Any, ClassVar, Dict, List, Optional

from luqi_engine.core.config import LocalModelConfig
from luqi_engine.core.logging_config import get_logger

_logger = get_logger(__name__)


class TrainingDataExporter:
    _HTTP_METHOD_POST: ClassVar[str] = "POST"
    _HTTP_CONTENT_TYPE: ClassVar[str] = "application/json"
    _HTTP_TIMEOUT_SEC: ClassVar[float] = 30.0
    _EXPORT_KEY_CASES: ClassVar[str] = "correction_cases"
    _EXPORT_KEY_TIMESTAMP: ClassVar[str] = "export_timestamp"
    _EXPORT_KEY_VERSION: ClassVar[str] = "schema_version"
    _EXPORT_KEY_SOURCE: ClassVar[str] = "source"
    _EXPORT_SOURCE_VALUE: ClassVar[str] = "luqi_engine_local_model"
    _SCHEMA_VERSION: ClassVar[str] = "1.0"
    _HTTP_SUCCESS_MIN: ClassVar[int] = 200
    _HTTP_SUCCESS_MAX: ClassVar[int] = 299

    def __init__(self, config: LocalModelConfig | None = None) -> None:
        self._config = config or LocalModelConfig()
        self._pending_cases: List[Dict[str, Any]] = []

    def add_correction_case(
        self,
        original_content: Dict[str, Any],
        corrected_content: Dict[str, Any],
        classification: str,
        confidence: float,
        corrections: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        case = {
            "original": original_content,
            "corrected": corrected_content,
            "classification": classification,
            "confidence": confidence,
            "corrections": corrections or [],
            "case_timestamp": time.time(),
        }
        self._pending_cases.append(case)

    async def export(self, since: float) -> List[Dict[str, Any]]:
        filtered_cases = [
            case for case in self._pending_cases
            if case.get("case_timestamp", 0.0) >= since
        ]

        if not filtered_cases:
            return []

        export_payload = self._build_export_payload(filtered_cases)

        if self._config.export_endpoint:
            await self._send_to_endpoint(export_payload)

        if self._config.enable_debug_output:
            _logger.info("exported %d cases since=%.2f", len(filtered_cases), since)

        return filtered_cases

    def _build_export_payload(self, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            self._EXPORT_KEY_CASES: cases,
            self._EXPORT_KEY_TIMESTAMP: time.time(),
            self._EXPORT_KEY_VERSION: self._SCHEMA_VERSION,
            self._EXPORT_KEY_SOURCE: self._EXPORT_SOURCE_VALUE,
        }

    async def _send_to_endpoint(self, payload: Dict[str, Any]) -> bool:
        endpoint = self._config.export_endpoint
        if not endpoint:
            return False

        try:
            result = await asyncio.to_thread(
                self._http_post_sync, endpoint, payload
            )
            return result
        except Exception as exc:
            _logger.error("HTTP export failed: %s", exc)
            return False

    def _http_post_sync(self, endpoint: str, payload: Dict[str, Any]) -> bool:
        try:
            json_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(
                endpoint,
                data=json_data,
                method=self._HTTP_METHOD_POST,
            )
            request.add_header("Content-Type", self._HTTP_CONTENT_TYPE)

            timeout = self._HTTP_TIMEOUT_SEC
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status_code = response.getcode()
                return self._HTTP_SUCCESS_MIN <= status_code <= self._HTTP_SUCCESS_MAX

        except urllib.error.URLError as exc:
            _logger.error("URL error: %s", exc)
            return False
        except Exception as exc:
            _logger.error("HTTP error: %s", exc)
            return False

    def format_as_json(self, cases: Optional[List[Dict[str, Any]]] = None) -> str:
        target_cases = cases if cases is not None else self._pending_cases
        payload = self._build_export_payload(target_cases)
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def clear_exported_cases(self, before_timestamp: Optional[float] = None) -> int:
        if before_timestamp is None:
            count = len(self._pending_cases)
            self._pending_cases.clear()
            return count

        remaining: List[Dict[str, Any]] = []
        removed = 0
        for case in self._pending_cases:
            if case.get("case_timestamp", 0.0) < before_timestamp:
                removed += 1
            else:
                remaining.append(case)
        self._pending_cases = remaining
        return removed

    @property
    def pending_case_count(self) -> int:
        return len(self._pending_cases)
