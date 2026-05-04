"""
Anthropic API适配器 - 支持Claude等
使用httpx直接调用API，支持SSE流式响应
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from luqi_engine.core.config import LLMConfig
from luqi_engine.core.interfaces import ILLMBridge
from luqi_engine.core.types import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    SDKType,
)

_ANTHROPIC_VERSION: str = "2023-06-01"
_MESSAGES_PATH: str = "/v1/messages"
_ROLE_SYSTEM: str = "system"
_ROLE_USER: str = "user"
_ROLE_ASSISTANT: str = "assistant"
_SSE_EVENT_PREFIX: str = "event: "
_SSE_DATA_PREFIX: str = "data: "
_DEFAULT_HTTP_TIMEOUT: float = 60.0
_DEFAULT_MAX_TOKENS: int = 4096


class AnthropicAdapter(ILLMBridge):
    """
    Anthropic API适配器
    通过httpx直接调用，不依赖anthropic库
    """

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._base_url = config.base_url.rstrip("/")

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "x-api-key": self._config.api_key,
                    "anthropic-version": _ANTHROPIC_VERSION,
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(
                    max(self._config.timeout, _DEFAULT_HTTP_TIMEOUT),
                    connect=10.0,
                ),
            )
        return self._client

    async def chat(self, request: LLMRequest) -> LLMResponse:
        client = await self._ensure_client()
        system_text, messages = self._convert_messages(request.messages)
        payload = self._build_payload(request, system_text, messages)

        resp = await client.post(_MESSAGES_PATH, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return self._parse_response(data)

    async def chat_stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        client = await self._ensure_client()
        system_text, messages = self._convert_messages(request.messages)
        payload = self._build_payload(request, system_text, messages)
        payload["stream"] = True

        async with client.stream(
            "POST", _MESSAGES_PATH, json=payload
        ) as response:
            response.raise_for_status()
            event_type = ""
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith(_SSE_EVENT_PREFIX):
                    event_type = line[len(_SSE_EVENT_PREFIX):]
                elif line.startswith(_SSE_DATA_PREFIX):
                    data_str = line[len(_SSE_DATA_PREFIX):]
                    chunk = self._parse_stream_event(event_type, data_str)
                    if chunk is not None:
                        yield chunk

    async def embed(self, text: str) -> List[float]:
        raise NotImplementedError(
            "Anthropic does not provide an embedding endpoint"
        )

    async def validate(self) -> bool:
        try:
            client = await self._ensure_client()
            payload = {
                "model": self._config.model,
                "max_tokens": 1,
                "messages": [{"role": _ROLE_USER, "content": "hi"}],
            }
            resp = await client.post(_MESSAGES_PATH, json=payload)
            return resp.status_code in (200, 400)
        except Exception:
            return False

    def get_sdk_type(self) -> SDKType:
        return SDKType.ANTHROPIC

    @staticmethod
    def _convert_messages(
        messages: List[Dict[str, str]],
    ) -> tuple:
        system_parts: List[str] = []
        converted: List[Dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == _ROLE_SYSTEM:
                system_parts.append(content)
            elif role in (_ROLE_USER, _ROLE_ASSISTANT):
                converted.append({"role": role, "content": content})
        system_text = "\n\n".join(system_parts) if system_parts else ""
        return system_text, converted

    def _build_payload(
        self,
        request: LLMRequest,
        system_text: str,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": request.model or self._config.model,
            "max_tokens": request.max_tokens
            if request.max_tokens is not None
            else self._config.max_tokens,
            "messages": messages,
        }
        if system_text:
            payload["system"] = system_text
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        elif self._config.temperature is not None:
            payload["temperature"] = self._config.temperature
        return payload

    @staticmethod
    def _parse_response(data: Dict[str, Any]) -> LLMResponse:
        content_blocks = data.get("content", [])
        text_parts = []
        thinking_parts = []
        for b in content_blocks:
            block_type = b.get("type", "")
            if block_type == "text":
                text_parts.append(b.get("text", ""))
            elif block_type == "thinking":
                thinking_parts.append(b.get("thinking", ""))
        content = "".join(text_parts)
        thinking = "".join(thinking_parts)
        finish_reason = data.get("stop_reason", "end_turn")
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        return LLMResponse(
            content=content,
            role=_ROLE_ASSISTANT,
            finish_reason=finish_reason,
            usage=usage,
            tokens=input_tokens + output_tokens,
            thinking=thinking,
        )

    @staticmethod
    def _parse_stream_event(
        event_type: str, data_str: str
    ) -> Optional[LLMStreamChunk]:
        if event_type in ("ping", "content_block_stop", "message_start",
                          "content_block_start"):
            return None
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            return None

        if event_type == "content_block_delta":
            delta = data.get("delta", {})
            delta_type = delta.get("type", "")
            if delta_type == "thinking_delta":
                text = delta.get("thinking", "")
                return LLMStreamChunk(delta=text, finish_reason=None)
            elif delta_type == "text_delta":
                text = delta.get("text", "")
                return LLMStreamChunk(delta=text, finish_reason=None)
            elif delta_type == "signature_delta":
                return None
            text = delta.get("text", delta.get("thinking", ""))
            if text:
                return LLMStreamChunk(delta=text, finish_reason=None)
            return None
        elif event_type == "message_delta":
            stop_reason = data.get("delta", {}).get("stop_reason")
            return LLMStreamChunk(delta="", finish_reason=stop_reason)
        elif event_type == "message_stop":
            return LLMStreamChunk(delta="", finish_reason="end_turn")
        elif event_type == "error":
            return LLMStreamChunk(delta="", finish_reason="error")
        return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> AnthropicAdapter:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
