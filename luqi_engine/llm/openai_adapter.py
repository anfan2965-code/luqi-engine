"""
OpenAI兼容API适配器 - 支持OpenAI/DeepSeek/通义千问等
使用httpx直接调用API，支持SSE流式响应
"""

from __future__ import annotations

import asyncio
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

_SSE_DATA_PREFIX: str = "data: "
_SSE_DONE_SIGNAL: str = "[DONE]"
_SSE_LINE_DELIMITER: str = "\n\n"
_CHAT_COMPLETIONS_PATH: str = "/chat/completions"
_EMBEDDINGS_PATH: str = "/embeddings"
_MODELS_PATH: str = "/models"
_REPETITION_PENALTY_DEFAULT: float = 1.9
_DEFAULT_HTTP_TIMEOUT: float = 60.0
_DEFAULT_MAX_RETRIES: int = 2
_RETRY_DELAY_BASE: float = 1.0

_CN_PUNCT: str = '\u3001\u3002\uff01\uff1f\uff0c\uff1a\uff1b\u201c\u201d\u2018\u2019\u2026\u2014\u00b7\u300a\u300b\u3010\u3011\uff08\xff09'

_CHINESE_ONLY_GRAMMAR: str = (
    "root ::= item+\n"
    "item ::= cjk | p | nl\n"
    f"cjk ::= [一-鿿]\n"
    f"p ::= [{_CN_PUNCT}]\n"
    'nl ::= "\\n"'
)


class OpenAIAdapter(ILLMBridge):
    """
    OpenAI兼容API适配器
    通过httpx直接调用，不依赖openai库
    """

    RETRY_DELAY_BASE: float = _RETRY_DELAY_BASE
    MAX_RETRIES: int = _DEFAULT_MAX_RETRIES

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._base_url = config.base_url.rstrip("/")

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(
                    max(self._config.timeout, _DEFAULT_HTTP_TIMEOUT),
                    connect=10.0,
                ),
                transport=httpx.AsyncHTTPTransport(verify=False),
            )
        return self._client

    async def chat(self, request: LLMRequest) -> LLMResponse:
        client = await self._ensure_client()
        payload = self._build_payload(request)

        last_error: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = await client.post(_CHAT_COMPLETIONS_PATH, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return self._parse_response(data)
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(delay)

        return LLMResponse(
            content="",
            role="assistant",
            finish_reason="error",
            usage={},
            tokens=0,
        )

    async def chat_stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        client = await self._ensure_client()
        payload = self._build_payload(request)
        payload["stream"] = True

        async with client.stream(
            "POST", _CHAT_COMPLETIONS_PATH, json=payload
        ) as response:
            response.raise_for_status()
            buffer = ""
            async for line in response.aiter_lines():
                buffer += line + "\n"
                if _SSE_LINE_DELIMITER in buffer:
                    chunks = buffer.split(_SSE_LINE_DELIMITER)
                    for chunk_str in chunks[:-1]:
                        chunk_str = chunk_str.strip()
                        if not chunk_str:
                            continue
                        parsed = self._parse_sse_chunk(chunk_str)
                        if parsed is not None:
                            yield parsed
                    buffer = chunks[-1]

    async def embed(self, text: str) -> List[float]:
        client = await self._ensure_client()
        payload = {
            "model": self._config.model,
            "input": text,
        }
        resp = await client.post(_EMBEDDINGS_PATH, json=payload)
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("data", [])
        if embeddings and len(embeddings) > 0:
            return embeddings[0].get("embedding", [])
        return []

    async def validate(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get(_MODELS_PATH)
            return resp.status_code == 200
        except Exception:
            return False

    def get_sdk_type(self) -> SDKType:
        return SDKType.OPENAI

    def _build_payload(self, request: LLMRequest) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": request.model or self._config.model,
            "messages": request.messages,
            "temperature": request.temperature
            if request.temperature is not None
            else self._config.temperature,
            "max_tokens": request.max_tokens
            if request.max_tokens is not None
            else self._config.max_tokens,
            "stream": request.stream,
            "repetition_penalty": _REPETITION_PENALTY_DEFAULT,
        }
        if request.grammar:
            payload["grammar"] = request.grammar
        return payload

    @staticmethod
    def _parse_response(data: Dict[str, Any]) -> LLMResponse:
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(
                content="", role="assistant", finish_reason="empty",
                usage=data.get("usage", {}), tokens=0,
            )
        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        role = message.get("role", "assistant")
        finish_reason = choice.get("finish_reason", "stop")
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens", 0)
        return LLMResponse(
            content=content,
            role=role,
            finish_reason=finish_reason,
            usage=usage,
            tokens=tokens,
        )

    @staticmethod
    def _parse_sse_chunk(chunk_str: str) -> Optional[LLMStreamChunk]:
        for line in chunk_str.split("\n"):
            line = line.strip()
            if not line.startswith(_SSE_DATA_PREFIX):
                continue
            data_str = line[len(_SSE_DATA_PREFIX):]
            if data_str == _SSE_DONE_SIGNAL:
                return LLMStreamChunk(delta="", finish_reason="stop")
            try:
                data = json.loads(data_str)
                choices = data.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                finish_reason = choices[0].get("finish_reason")
                return LLMStreamChunk(
                    delta=content, finish_reason=finish_reason or None
                )
            except json.JSONDecodeError:
                continue
        return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> OpenAIAdapter:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
