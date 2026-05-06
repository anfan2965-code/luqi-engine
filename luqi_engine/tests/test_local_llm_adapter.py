from __future__ import annotations

import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from luqi_engine.llm.local_llm_adapter import LocalLLMAdapter
from luqi_engine.core.types import LLMRequest, LLMResponse, LLMStreamChunk, SDKType


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestLocalLLMAdapterInit(unittest.TestCase):
    def test_default_params(self):
        adapter = LocalLLMAdapter()
        self.assertEqual(adapter.model_path, "")
        self.assertFalse(adapter.is_loaded)

    def test_custom_params(self):
        adapter = LocalLLMAdapter(
            model_path="/path/to/model.gguf",
            n_gpu_layers=0,
            n_ctx=2048,
            max_tokens=512,
            temperature=0.7,
            top_p=0.9,
        )
        self.assertEqual(adapter.model_path, "/path/to/model.gguf")
        self.assertFalse(adapter.is_loaded)

    def test_get_sdk_type(self):
        adapter = LocalLLMAdapter()
        self.assertEqual(adapter.get_sdk_type(), SDKType.LOCAL_LLM)

    def test_validate_no_path(self):
        adapter = LocalLLMAdapter(model_path="")
        result = _run_async(adapter.validate())
        self.assertFalse(result)

    def test_validate_nonexistent_path(self):
        adapter = LocalLLMAdapter(model_path="/nonexistent/model.gguf")
        result = _run_async(adapter.validate())
        self.assertFalse(result)

    def test_embed_raises(self):
        adapter = LocalLLMAdapter()
        with self.assertRaises(NotImplementedError):
            _run_async(adapter.embed("test"))

    def test_unload_without_load(self):
        adapter = LocalLLMAdapter()
        adapter.unload()
        self.assertFalse(adapter.is_loaded)


class TestLocalLLMAdapterWithMock(unittest.TestCase):
    def _create_mock_model(self, content="你好，我是小雪", finish_reason="stop"):
        mock_model = MagicMock()
        mock_model.create_chat_completion.return_value = {
            "choices": [{
                "message": {"content": content, "role": "assistant"},
                "finish_reason": finish_reason,
            }],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        }
        return mock_model

    def _create_stream_mock_model(self, chunks):
        mock_model = MagicMock()
        mock_model.create_chat_completion.return_value = iter(chunks)
        return mock_model

    def test_chat_success(self):
        adapter = LocalLLMAdapter(model_path="/fake/model.gguf")
        mock_model = self._create_mock_model("嗯呢~谢谢你！")
        adapter._model = mock_model
        adapter._loaded = True

        request = LLMRequest(
            sdk_type=SDKType.OPENAI,
            messages=[{"role": "user", "content": "你好"}],
        )
        result = _run_async(adapter.chat(request))
        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.content, "嗯呢~谢谢你！")
        self.assertEqual(result.role, "assistant")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.tokens, 70)

    def test_chat_error_handling(self):
        adapter = LocalLLMAdapter(model_path="/fake/model.gguf")
        mock_model = MagicMock()
        mock_model.create_chat_completion.side_effect = RuntimeError("Model error")
        adapter._model = mock_model
        adapter._loaded = True

        request = LLMRequest(
            sdk_type=SDKType.OPENAI,
            messages=[{"role": "user", "content": "你好"}],
        )
        result = _run_async(adapter.chat(request))
        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.content, "")
        self.assertEqual(result.finish_reason, "error")

    def test_chat_stream_success(self):
        stream_chunks = [
            {"choices": [{"delta": {"content": "你"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "好"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
        ]
        adapter = LocalLLMAdapter(model_path="/fake/model.gguf")
        mock_model = self._create_stream_mock_model(stream_chunks)
        adapter._model = mock_model
        adapter._loaded = True

        request = LLMRequest(
            sdk_type=SDKType.OPENAI,
            messages=[{"role": "user", "content": "你好"}],
        )

        async def collect_stream():
            chunks = []
            async for chunk in adapter.chat_stream(request):
                chunks.append(chunk)
            return chunks

        chunks = _run_async(collect_stream())
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].delta, "你")
        self.assertEqual(chunks[1].delta, "好")

    def test_unload_releases_model(self):
        adapter = LocalLLMAdapter(model_path="/fake/model.gguf")
        adapter._model = MagicMock()
        adapter._loaded = True
        adapter.unload()
        self.assertIsNone(adapter._model)
        self.assertFalse(adapter.is_loaded)

    def test_validate_with_loaded_model(self):
        adapter = LocalLLMAdapter(model_path="/fake/model.gguf")
        adapter._model = MagicMock()
        adapter._loaded = True
        with patch("os.path.exists", return_value=True):
            result = _run_async(adapter.validate())
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
