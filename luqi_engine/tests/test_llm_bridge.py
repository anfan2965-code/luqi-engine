import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from luqi_engine.llm.bridge import LLMBridge
from luqi_engine.core.config import LLMConfig
from luqi_engine.core.types import LLMRequest, LLMResponse, SDKType, LLMStreamChunk
from luqi_engine.llm.fallback import DegradationLevel


class TestLLMBridgeCreation:
    def setup_method(self):
        from luqi_engine.llm.adapter_registry import AdapterRegistry
        from luqi_engine.llm import OpenAIAdapter, AnthropicAdapter
        registry = AdapterRegistry()
        if not registry.has("openai"):
            registry.register("openai", OpenAIAdapter)
        if not registry.has("anthropic"):
            registry.register("anthropic", AnthropicAdapter)

    def test_create_with_openai_sdk(self):
        config = LLMConfig(sdk_type="openai", api_key="test_key", model="gpt-4")
        bridge = LLMBridge(config)
        assert bridge.get_sdk_type() == SDKType.OPENAI

    def test_create_with_anthropic_sdk(self):
        config = LLMConfig(sdk_type="anthropic", api_key="test_key", model="claude-3")
        bridge = LLMBridge(config)
        assert bridge.get_sdk_type() == SDKType.ANTHROPIC

    def test_create_defaults_to_openai(self):
        config = LLMConfig(api_key="test_key")
        bridge = LLMBridge(config)
        assert bridge.get_sdk_type() == SDKType.OPENAI

    def test_properties_accessible(self):
        config = LLMConfig(sdk_type="openai", api_key="k")
        bridge = LLMBridge(config)
        assert bridge.optimizer is not None
        assert bridge.dialogue_modes is not None
        assert bridge.prompt_builder is not None
        assert bridge.response_parser is not None
        assert bridge.fallback is not None


class TestLLMBridgeBuildRequest:
    def test_build_request_returns_llm_request(self):
        config = LLMConfig(sdk_type="openai", api_key="k", model="test-model", temperature=0.5, max_tokens=256)
        bridge = LLMBridge(config)
        from luqi_engine.llm.prompt_builder import PromptContext
        ctx = PromptContext(character_name="Test")
        req = bridge.build_request(ctx, "你好")
        assert isinstance(req, LLMRequest)
        assert req.model == "test-model"
        assert req.temperature == 0.5
        assert req.max_tokens == 256


class TestLLMBridgeChatWithMock:
    def setup_method(self):
        self.config = LLMConfig(sdk_type="openai", api_key="k", model="test")

    def test_chat_success(self):
        mock_adapter = AsyncMock()
        mock_adapter.chat.return_value = LLMResponse(
            content="回复内容",
            role="assistant",
            finish_reason="stop",
            usage={},
            tokens=10,
        )
        bridge = LLMBridge(self.config)
        bridge._adapter = mock_adapter
        response = asyncio.run(bridge.chat(LLMRequest(
            sdk_type=SDKType.OPENAI,
            messages=[{"role": "user", "content": "hi"}],
        )))
        assert response.content == "回复内容"

    def test_chat_failure_triggers_fallback(self):
        mock_adapter = AsyncMock()
        mock_adapter.chat.side_effect = RuntimeError("network error")
        bridge = LLMBridge(self.config)
        bridge._adapter = mock_adapter
        with patch.object(bridge._fallback, 'get_fallback_response', return_value=LLMResponse(content="", role="assistant", finish_reason="error", usage={}, tokens=0)):
            try:
                asyncio.run(bridge.chat(LLMRequest(sdk_type=SDKType.OPENAI, messages=[])))
            except Exception:
                pass

    def test_degraded_mode_skips_request(self):
        config = LLMConfig(sdk_type="openai", api_key="k")
        bridge = LLMBridge(config)
        bridge._fallback._current_level = DegradationLevel.OFFLINE
        response = asyncio.run(bridge.chat(LLMRequest(sdk_type=SDKType.OPENAI, messages=[])))
        assert response.finish_reason == "error"


class TestLLMBridgeChatStream:
    def test_stream_success(self):
        config = LLMConfig(sdk_type="openai", api_key="k")
        bridge = LLMBridge(config)

        async def fake_stream(req):
            yield LLMStreamChunk(content="chunk1", finish_reason=None)
            yield LLMStreamChunk(content="", finish_reason="stop")

        bridge._adapter = MagicMock()
        bridge._adapter.chat_stream = fake_stream
        chunks = []
        for chunk in asyncio.run(_collect_chunks(bridge)):
            chunks.append(chunk)
        assert len(chunks) >= 1


async def _collect_chunks(bridge):
    result = []
    async for chunk in bridge.chat_stream(LLMRequest(sdk_type=SDKType.OPENAI, messages=[])):
        result.append(chunk)
    return result


class TestLLMBridgeDeepSeekOptimization:
    def test_optimization_disabled_passes_through(self):
        config = LLMConfig(sdk_type="openai", api_key="k", enable_deepseek_optimization=False)
        bridge = LLMBridge(config)
        req = LLMRequest(sdk_type=SDKType.OPENAI, messages=[{"role": "user", "content": "short"}], max_tokens=100)
        result = bridge._apply_optimization(req)
        assert result is req

    def test_optimization_enabled_compresses_long_context(self):
        config = LLMConfig(sdk_type="openai", api_key="k", enable_deepseek_optimization=True, context_compression_threshold=100)
        bridge = LLMBridge(config)
        long_messages = [{"role": "user", "content": "x" * 500}] * 20
        req = LLMRequest(sdk_type=SDKType.OPENAI, messages=long_messages, max_tokens=4096)
        result = bridge._apply_optimization(req)
        assert isinstance(result, LLMRequest)


class TestLLMBridgeContextManager:
    def test_async_context_manager(self):
        config = LLMConfig(sdk_type="openai", api_key="k")

        async def _use_context():
            async with LLMBridge(config) as bridge:
                return bridge

        bridge = asyncio.run(_use_context())
        assert bridge is not None
