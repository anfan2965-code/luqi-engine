"""
LLM桥接器 - 双SDK适配器的中央协调器
整合DeepSeek优化、对话模式、提示词构建、响应解析、降级策略
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from luqi_engine.core.config import LLMConfig
from luqi_engine.core.interfaces import ILLMBridge
from luqi_engine.core.types import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    SDKType,
)

from luqi_engine.llm.openai_adapter import OpenAIAdapter
from luqi_engine.llm.anthropic_adapter import AnthropicAdapter
from luqi_engine.llm.local_llm_adapter import LocalLLMAdapter
from luqi_engine.llm.deepseek_optimizer import DeepSeekOptimizer
from luqi_engine.llm.dialogue_modes import DialogueModes, DialogueMode
from luqi_engine.llm.prompt_builder import PromptBuilder, PromptContext
from luqi_engine.llm.response_parser import ResponseParser, ParsedResponse
from luqi_engine.llm.fallback import LLMFallback, DegradationLevel

_SDK_TYPE_MAP: Dict[str, SDKType] = {
    "openai": SDKType.OPENAI,
    "anthropic": SDKType.ANTHROPIC,
    "local_llm": SDKType.LOCAL_LLM,
}

_LOCAL_LLM_N_CTX_DEFAULT: int = 2048
_LOCAL_LLM_MAX_TOKENS_DEFAULT: int = 512
_LOCAL_LLM_TEMPERATURE_DEFAULT: float = 0.7
_LOCAL_LLM_TOP_P_DEFAULT: float = 0.9


class LLMBridge(ILLMBridge):
    """
    LLM桥接器 - 中央协调器
    根据sdk_type自动选择适配器
    整合优化/模式/构建/解析/降级
    """

    def __init__(
        self,
        config: LLMConfig,
        dialogue_modes: Optional[DialogueModes] = None,
        fallback: Optional[LLMFallback] = None,
        local_llm_adapter: Optional[Any] = None,
    ) -> None:
        self._config = config
        self._sdk_type = self._resolve_sdk_type(config.sdk_type)
        if self._sdk_type == SDKType.LOCAL_LLM and local_llm_adapter is not None:
            self._adapter = local_llm_adapter
        else:
            self._adapter = self._create_adapter(config, self._sdk_type)
        self._optimizer = DeepSeekOptimizer(config)
        self._dialogue_modes = dialogue_modes or DialogueModes()
        self._prompt_builder = PromptBuilder()
        self._response_parser = ResponseParser()
        self._fallback = fallback or LLMFallback()
        self._logger = logging.getLogger(__name__)

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """
        同步对话 - 整合降级检查、优化、适配器调用
        """
        if not self._fallback.should_attempt_request():
            return self._fallback.get_fallback_response()

        optimized_request = self._apply_optimization(request)

        try:
            response = await self._adapter.chat(optimized_request)
            self._fallback.report_success()
            return response
        except Exception as exc:
            self._logger.error("LLM chat调用失败: %s", exc, exc_info=True)
            self._fallback.report_failure()
            if self._fallback.current_level != DegradationLevel.NORMAL:
                return self._fallback.get_fallback_response()
            raise

    async def chat_stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        流式对话 - 整合降级检查、优化、适配器调用
        """
        if not self._fallback.should_attempt_request():
            yield self._fallback.get_fallback_stream_chunk()
            return

        optimized_request = self._apply_optimization(request)

        try:
            async for chunk in self._adapter.chat_stream(optimized_request):
                yield chunk
            self._fallback.report_success()
        except Exception as exc:
            self._logger.error("LLM chat_stream调用失败: %s", exc, exc_info=True)
            self._fallback.report_failure()
            yield self._fallback.get_fallback_stream_chunk()

    async def embed(self, text: str) -> List[float]:
        return await self._adapter.embed(text)

    async def validate(self) -> bool:
        return await self._adapter.validate()

    def get_sdk_type(self) -> SDKType:
        return self._sdk_type

    def build_request(
        self,
        context: PromptContext,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> LLMRequest:
        """
        便捷方法：使用PromptBuilder构建请求
        """
        messages = self._prompt_builder.build_messages(
            context, self._sdk_type, user_message, history
        )
        return LLMRequest(
            sdk_type=self._sdk_type,
            messages=messages,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            model=self._config.model,
            stream=False,
        )

    def parse_response(self, response: LLMResponse) -> ParsedResponse:
        """
        便捷方法：使用ResponseParser解析响应
        """
        return self._response_parser.parse(response, self._sdk_type)

    @property
    def optimizer(self) -> DeepSeekOptimizer:
        return self._optimizer

    @property
    def dialogue_modes(self) -> DialogueModes:
        return self._dialogue_modes

    @property
    def prompt_builder(self) -> PromptBuilder:
        return self._prompt_builder

    @property
    def response_parser(self) -> ResponseParser:
        return self._response_parser

    @property
    def fallback(self) -> LLMFallback:
        return self._fallback

    def _apply_optimization(self, request: LLMRequest) -> LLMRequest:
        """
        应用DeepSeek优化（上下文压缩等）
        """
        if not self._config.enable_deepseek_optimization:
            return request

        estimated = self._optimizer.estimate_tokens(request.messages)
        if estimated <= self._config.context_compression_threshold:
            return request

        result = self._optimizer.compress_dialogue_context(request.messages)
        return LLMRequest(
            sdk_type=request.sdk_type,
            messages=result.compressed_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            model=request.model,
            stream=request.stream,
        )

    @staticmethod
    def _resolve_sdk_type(sdk_type_str: str) -> SDKType:
        return _SDK_TYPE_MAP.get(sdk_type_str.lower(), SDKType.OPENAI)

    @staticmethod
    def _create_adapter(config: LLMConfig, sdk_type: SDKType) -> ILLMBridge:
        if sdk_type == SDKType.LOCAL_LLM:
            return LocalLLMAdapter(
                model_path=getattr(config, 'model_path', '') or config.model,
                n_gpu_layers=getattr(config, 'n_gpu_layers', 0),
                n_ctx=getattr(config, 'n_ctx', _LOCAL_LLM_N_CTX_DEFAULT),
                max_tokens=config.max_tokens or _LOCAL_LLM_MAX_TOKENS_DEFAULT,
                temperature=config.temperature or _LOCAL_LLM_TEMPERATURE_DEFAULT,
                top_p=getattr(config, 'top_p', _LOCAL_LLM_TOP_P_DEFAULT),
            )
        from luqi_engine.llm.adapter_registry import AdapterRegistry
        registry = AdapterRegistry()
        sdk_name = sdk_type.value if hasattr(sdk_type, "value") else str(sdk_type)
        adapter_class = registry.get(sdk_name)
        if adapter_class is None:
            raise ValueError(f"Unsupported SDK type: {sdk_name}. Available: {registry.list_adapters()}")
        return adapter_class(config)

    async def close(self) -> None:
        if hasattr(self._adapter, "close"):
            await self._adapter.close()

    async def __aenter__(self) -> LLMBridge:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
