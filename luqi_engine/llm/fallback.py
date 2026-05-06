"""
LLM降级策略 - LLM不可用时切换到本地模型兜底
多级降级：NORMAL → DEGRADED(LocalLLMAdapter) → SEVERELY_DEGRADED → OFFLINE
Atmosphere降级路径：FULL → TEMPLATE_PCG → TEMPLATE_ONLY → MINIMAL_SKIP
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from luqi_engine.core.config import LLMConfig
from luqi_engine.core.types import LLMRequest, LLMResponse, LLMStreamChunk

_LEVEL_NORMAL_RESPONSE: str = ""
_LEVEL_DEGRADED_RESPONSE: str = "服务暂时不稳定，回复质量可能下降。"
_LEVEL_SEVERELY_RESPONSE: str = "服务严重不稳定，正在尝试恢复中。"
_LEVEL_OFFLINE_RESPONSE: str = "服务暂时不可用，请稍后重试。"


class DegradationLevel(Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    SEVERELY_DEGRADED = "severely_degraded"
    OFFLINE = "offline"


class AtmosphereDegradationMode(Enum):
    FULL = "full"
    TEMPLATE_PCG = "template_pcg"
    TEMPLATE_ONLY = "template_only"
    MINIMAL_SKIP = "minimal_skip"


_ATMOSPHERE_DEGRADATION_MAP = {
    DegradationLevel.NORMAL: AtmosphereDegradationMode.FULL,
    DegradationLevel.DEGRADED: AtmosphereDegradationMode.TEMPLATE_PCG,
    DegradationLevel.SEVERELY_DEGRADED: AtmosphereDegradationMode.TEMPLATE_ONLY,
    DegradationLevel.OFFLINE: AtmosphereDegradationMode.MINIMAL_SKIP,
}


@dataclass
class FallbackStats:
    consecutive_failures: int = 0
    total_failures: int = 0
    total_requests: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    current_level: DegradationLevel = DegradationLevel.NORMAL
    degradation_history: List[Dict[str, Any]] = field(default_factory=list)


class LLMFallback:
    """
    LLM降级管理器
    根据连续失败次数自动降级
    支持自动恢复和回调通知
    DEGRADED级别支持LocalLLMAdapter本地推理
    """

    def __init__(
        self,
        on_degrade: Optional[Callable[[DegradationLevel], None]] = None,
        on_recover: Optional[Callable[[], None]] = None,
        on_offline: Optional[Callable[[], None]] = None,
        fallback_response_generator: Optional[
            Callable[[DegradationLevel], str]
        ] = None,
        config: Optional[LLMConfig] = None,
    ) -> None:
        self._stats = FallbackStats()
        self._on_degrade = on_degrade
        self._on_recover = on_recover
        self._on_offline = on_offline
        self._fallback_generator = fallback_response_generator
        self._local_llm_adapter: Optional[Any] = None
        self._state_renderer: Optional[Any] = None
        self._recovery_successes: int = 0
        self._last_recovery_check: float = 0.0
        self._logger = logging.getLogger(__name__)

        thresholds = config.fallback_thresholds if config else {
            "degraded": 3,
            "severely_degraded": 5,
            "offline": 10,
        }
        self._degraded_threshold: int = thresholds.get("degraded", 3)
        self._severely_degraded_threshold: int = thresholds.get("severely_degraded", 5)
        self._offline_threshold: int = thresholds.get("offline", 10)
        self._recovery_check_interval: float = 30.0
        self._recovery_success_count: int = 2

    def set_local_llm_adapter(self, adapter: Any, state_renderer: Any = None) -> None:
        self._local_llm_adapter = adapter
        self._state_renderer = state_renderer

    def report_success(self) -> None:
        """
        报告请求成功
        连续成功达到阈值时触发恢复
        """
        self._stats.total_requests += 1
        self._stats.consecutive_failures = 0
        self._stats.last_success_time = time.time()
        self._recovery_successes += 1

        if (
            self._stats.current_level != DegradationLevel.NORMAL
            and self._recovery_successes >= self._recovery_success_count
        ):
            self._recover()

    def report_failure(self) -> None:
        """
        报告请求失败
        根据连续失败次数触发降级
        """
        self._stats.total_requests += 1
        self._stats.total_failures += 1
        self._stats.consecutive_failures += 1
        self._stats.last_failure_time = time.time()
        self._recovery_successes = 0

        old_level = self._stats.current_level
        new_level = self._calculate_level(self._stats.consecutive_failures)

        if new_level != old_level:
            self._stats.current_level = new_level
            self._stats.degradation_history.append(
                {
                    "from": old_level.value,
                    "to": new_level.value,
                    "timestamp": time.time(),
                    "consecutive_failures": self._stats.consecutive_failures,
                }
            )
            if new_level == DegradationLevel.OFFLINE and self._on_offline:
                self._on_offline(new_level)
            elif self._on_degrade:
                self._on_degrade(new_level)

    def get_fallback_response(self) -> LLMResponse:
        """
        获取降级响应
        DEGRADED级别优先使用LocalLLMAdapter
        """
        level = self._stats.current_level
        if level == DegradationLevel.DEGRADED and self._local_llm_adapter is not None:
            return self._generate_degraded_response()
        content = self._generate_fallback_content(level)
        return LLMResponse(
            content=content,
            role="assistant",
            finish_reason="fallback",
            usage={},
            tokens=0,
        )

    def get_fallback_stream_chunk(self) -> LLMStreamChunk:
        """
        获取降级流式块
        """
        level = self._stats.current_level
        content = self._generate_fallback_content(level)
        return LLMStreamChunk(delta=content, finish_reason="fallback")

    async def get_local_llm_response(self, request: LLMRequest) -> LLMResponse:
        """
        使用LocalLLMAdapter生成响应
        用于IntentClassifier路由到本地模型的场景
        """
        if self._local_llm_adapter is None:
            return self.get_fallback_response()
        try:
            return await self._local_llm_adapter.chat(request)
        except Exception as exc:
            self._logger.warning("LocalLLMAdapter.chat失败，回退到降级响应: %s", exc)
            return self.get_fallback_response()

    async def get_local_llm_stream(self, request: LLMRequest):
        """
        使用LocalLLMAdapter流式生成响应
        """
        if self._local_llm_adapter is None:
            yield self.get_fallback_stream_chunk()
            return
        try:
            async for chunk in self._local_llm_adapter.chat_stream(request):
                yield chunk
        except Exception as exc:
            self._logger.warning("LocalLLMAdapter.chat_stream失败，回退到降级响应: %s", exc)
            yield self.get_fallback_stream_chunk()

    def should_attempt_request(self) -> bool:
        """
        判断是否应该尝试请求
        OFFLINE状态下按时间间隔探测
        """
        if self._stats.current_level == DegradationLevel.OFFLINE:
            now = time.time()
            if now - self._last_recovery_check >= self._recovery_check_interval:
                self._last_recovery_check = now
                return True
            return False
        return True

    @property
    def current_level(self) -> DegradationLevel:
        return self._stats.current_level

    @property
    def stats(self) -> FallbackStats:
        return self._stats

    @property
    def has_local_llm(self) -> bool:
        return self._local_llm_adapter is not None

    @property
    def atmosphere_mode(self) -> AtmosphereDegradationMode:
        """
        获取当前Atmosphere降级模式
        NORMAL → FULL: 完整LLM生成
        DEGRADED → TEMPLATE_PCG: 模板引擎+PCG
        SEVERELY_DEGRADED → TEMPLATE_ONLY: 纯模板
        OFFLINE → MINIMAL_SKIP: 极简标记/跳过
        """
        return _ATMOSPHERE_DEGRADATION_MAP.get(
            self._stats.current_level, AtmosphereDegradationMode.MINIMAL_SKIP
        )

    def _calculate_level(self, consecutive_failures: int) -> DegradationLevel:
        if consecutive_failures >= self._offline_threshold:
            return DegradationLevel.OFFLINE
        if consecutive_failures >= self._severely_degraded_threshold:
            return DegradationLevel.SEVERELY_DEGRADED
        if consecutive_failures >= self._degraded_threshold:
            return DegradationLevel.DEGRADED
        return DegradationLevel.NORMAL

    def _recover(self) -> None:
        """
        恢复到NORMAL状态
        """
        old_level = self._stats.current_level
        self._stats.current_level = DegradationLevel.NORMAL
        self._stats.consecutive_failures = 0
        self._recovery_successes = 0
        self._stats.degradation_history.append(
            {
                "from": old_level.value,
                "to": DegradationLevel.NORMAL.value,
                "timestamp": time.time(),
                "event": "recovery",
            }
        )
        if self._on_recover:
            self._on_recover()

    def _generate_degraded_response(self) -> LLMResponse:
        """
        该方法返回静态降级文本而非调用LocalLLMAdapter
        当LocalLLMAdapter可用但无法异步调用时使用
        """
        return LLMResponse(
            content=_LEVEL_DEGRADED_RESPONSE,
            role="assistant",
            finish_reason="fallback_local",
            usage={},
            tokens=0,
        )

    def _generate_fallback_content(self, level: DegradationLevel) -> str:
        if self._fallback_generator:
            return self._fallback_generator(level)
        level_messages = {
            DegradationLevel.NORMAL: _LEVEL_NORMAL_RESPONSE,
            DegradationLevel.DEGRADED: _LEVEL_DEGRADED_RESPONSE,
            DegradationLevel.SEVERELY_DEGRADED: _LEVEL_SEVERELY_RESPONSE,
            DegradationLevel.OFFLINE: _LEVEL_OFFLINE_RESPONSE,
        }
        return level_messages.get(level, _LEVEL_OFFLINE_RESPONSE)
