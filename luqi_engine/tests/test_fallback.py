from __future__ import annotations

import asyncio
import sys
import os
import time
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from luqi_engine.llm.fallback import LLMFallback, DegradationLevel, FallbackStats
from luqi_engine.core.types import LLMRequest, LLMResponse, LLMStreamChunk, SDKType
from luqi_engine.core.config import LLMConfig


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestLLMFallbackBasic(unittest.TestCase):
    def test_initial_state(self):
        fb = LLMFallback()
        self.assertEqual(fb.current_level, DegradationLevel.NORMAL)
        self.assertFalse(fb.has_local_llm)

    def test_report_success_stays_normal(self):
        fb = LLMFallback()
        fb.report_success()
        self.assertEqual(fb.current_level, DegradationLevel.NORMAL)

    def test_report_failure_degrades(self):
        fb = LLMFallback()
        for _ in range(3):
            fb.report_failure()
        self.assertEqual(fb.current_level, DegradationLevel.DEGRADED)

    def test_severe_degradation(self):
        fb = LLMFallback()
        for _ in range(5):
            fb.report_failure()
        self.assertEqual(fb.current_level, DegradationLevel.SEVERELY_DEGRADED)

    def test_offline(self):
        fb = LLMFallback()
        for _ in range(10):
            fb.report_failure()
        self.assertEqual(fb.current_level, DegradationLevel.OFFLINE)

    def test_recovery(self):
        fb = LLMFallback()
        for _ in range(3):
            fb.report_failure()
        self.assertEqual(fb.current_level, DegradationLevel.DEGRADED)
        for _ in range(2):
            fb.report_success()
        self.assertEqual(fb.current_level, DegradationLevel.NORMAL)

    def test_should_attempt_request_offline_with_time(self):
        fb = LLMFallback()
        for _ in range(10):
            fb.report_failure()
        self.assertEqual(fb.current_level, DegradationLevel.OFFLINE)
        fb._last_recovery_check = time.time() - 60.0
        self.assertTrue(fb.should_attempt_request())

    def test_should_attempt_request_offline_too_soon(self):
        fb = LLMFallback()
        for _ in range(10):
            fb.report_failure()
        fb._last_recovery_check = time.time()
        self.assertFalse(fb.should_attempt_request())

    def test_should_attempt_request_normal(self):
        fb = LLMFallback()
        self.assertTrue(fb.should_attempt_request())

    def test_get_fallback_response_normal(self):
        fb = LLMFallback()
        response = fb.get_fallback_response()
        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(response.finish_reason, "fallback")

    def test_get_fallback_stream_chunk(self):
        fb = LLMFallback()
        chunk = fb.get_fallback_stream_chunk()
        self.assertIsInstance(chunk, LLMStreamChunk)
        self.assertEqual(chunk.finish_reason, "fallback")


class TestLLMFallbackWithLocalLLM(unittest.TestCase):
    def _create_mock_adapter(self, content="本地模型回复"):
        mock_adapter = MagicMock()
        mock_adapter.chat = AsyncMock(return_value=LLMResponse(
            content=content,
            role="assistant",
            finish_reason="stop",
            usage={"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
            tokens=40,
        ))
        return mock_adapter

    def test_set_local_llm_adapter(self):
        fb = LLMFallback()
        mock_adapter = self._create_mock_adapter()
        fb.set_local_llm_adapter(mock_adapter)
        self.assertTrue(fb.has_local_llm)

    def test_degraded_uses_local_llm(self):
        fb = LLMFallback()
        mock_adapter = self._create_mock_adapter("本地回复内容")
        fb.set_local_llm_adapter(mock_adapter)
        for _ in range(3):
            fb.report_failure()
        self.assertEqual(fb.current_level, DegradationLevel.DEGRADED)
        response = fb.get_fallback_response()
        self.assertIsInstance(response, LLMResponse)

    def test_get_local_llm_response(self):
        fb = LLMFallback()
        mock_adapter = self._create_mock_adapter("本地回复")
        fb.set_local_llm_adapter(mock_adapter)
        request = LLMRequest(
            sdk_type=SDKType.OPENAI,
            messages=[{"role": "user", "content": "你好"}],
        )
        result = _run_async(fb.get_local_llm_response(request))
        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.content, "本地回复")

    def test_get_local_llm_response_no_adapter(self):
        fb = LLMFallback()
        request = LLMRequest(
            sdk_type=SDKType.OPENAI,
            messages=[{"role": "user", "content": "你好"}],
        )
        result = _run_async(fb.get_local_llm_response(request))
        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.finish_reason, "fallback")

    def test_get_local_llm_stream(self):
        fb = LLMFallback()
        mock_adapter = MagicMock()

        async def mock_stream(request):
            yield LLMStreamChunk(delta="你", finish_reason=None)
            yield LLMStreamChunk(delta="好", finish_reason="stop")

        mock_adapter.chat_stream = mock_stream
        fb.set_local_llm_adapter(mock_adapter)

        request = LLMRequest(
            sdk_type=SDKType.OPENAI,
            messages=[{"role": "user", "content": "你好"}],
        )

        async def collect():
            chunks = []
            async for chunk in fb.get_local_llm_stream(request):
                chunks.append(chunk)
            return chunks

        chunks = _run_async(collect())
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].delta, "你")
        self.assertEqual(chunks[1].delta, "好")


class TestLLMFallbackWithConfig(unittest.TestCase):
    def test_default_thresholds_without_config(self):
        fb = LLMFallback()
        self.assertEqual(fb._degraded_threshold, 3)
        self.assertEqual(fb._severely_degraded_threshold, 5)
        self.assertEqual(fb._offline_threshold, 10)

    def test_custom_thresholds_from_config(self):
        config = LLMConfig(
            fallback_thresholds={
                "degraded": 2,
                "severely_degraded": 4,
                "offline": 8,
            }
        )
        fb = LLMFallback(config=config)
        self.assertEqual(fb._degraded_threshold, 2)
        self.assertEqual(fb._severely_degraded_threshold, 4)
        self.assertEqual(fb._offline_threshold, 8)

    def test_custom_degraded_threshold_triggers_earlier(self):
        config = LLMConfig(
            fallback_thresholds={
                "degraded": 2,
                "severely_degraded": 4,
                "offline": 6,
            }
        )
        fb = LLMFallback(config=config)
        for _ in range(2):
            fb.report_failure()
        self.assertEqual(fb.current_level, DegradationLevel.DEGRADED)

    def test_custom_offline_threshold_triggers_earlier(self):
        config = LLMConfig(
            fallback_thresholds={
                "degraded": 1,
                "severely_degraded": 3,
                "offline": 5,
            }
        )
        fb = LLMFallback(config=config)
        for _ in range(5):
            fb.report_failure()
        self.assertEqual(fb.current_level, DegradationLevel.OFFLINE)

    def test_partial_thresholds_with_defaults(self):
        config = LLMConfig(
            fallback_thresholds={
                "degraded": 1,
            }
        )
        fb = LLMFallback(config=config)
        self.assertEqual(fb._degraded_threshold, 1)
        self.assertEqual(fb._severely_degraded_threshold, 5)
        self.assertEqual(fb._offline_threshold, 10)


if __name__ == "__main__":
    unittest.main()
