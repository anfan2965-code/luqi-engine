"""氛围生成器 - 生成场景氛围描述"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from luqi_engine.core.rng import PCGRandom
from luqi_engine.core.types import LLMRequest, SDKType

_logger = logging.getLogger(__name__)

_EVENT_HISTORY_MAX: int = 20
_MIN_INTERVAL_ROUNDS: int = 5
_BASE_PROBABILITY: float = 0.07
_EVENT_BOOST_PROBABILITY: float = 0.3
_EMOTION_BOOST_PROBABILITY: float = 0.1
_EMOTION_DEPRESSED_THRESHOLD: float = -0.2
_EMOTION_INTENSE_LOW: float = -0.2
_EMOTION_INTENSE_HIGH: float = 0.5
_PLEASURE_DEPRESSED_THRESHOLD: float = -0.2
_PLEASURE_BRIGHT_THRESHOLD: float = 0.3
_AROUSAL_BRIGHT_THRESHOLD: float = 0.3
_RECENT_EVENT_WINDOW: int = 5
_DEFAULT_LAST_ATMOSPHERE_ROUND: int = -10
_ATMOSPHERE_MAX_TOKENS: int = 128
_ATMOSPHERE_TEMPERATURE: float = 0.8

_EVENT_BOOST_TYPES: frozenset[str] = frozenset({
    "user_depart", "user_arrive", "conflict", "scene_change",
})

_IMAGERY_DEPRESSED: str = "压抑/阴暗/沉重的意象"
_IMAGERY_BRIGHT: str = "明亮/活跃/温暖的意象"
_IMAGERY_NEUTRAL: str = "中性/日常的意象"

_PROMPT_SYSTEM: str = (
    "你是一位擅长氛围描写的文学助手。"
    "请根据给定的场景和情感上下文，生成1-2句氛围描写。"
    "描写应使用{imagery}，与当前情绪氛围匹配。"
    "只输出描写文本，不要加任何解释或标号。"
)


class AtmosphereSubsystem:
    def __init__(self, rng: Optional[PCGRandom] = None) -> None:
        self._rng = rng if rng is not None else PCGRandom()
        self._event_history: List[Dict[str, Any]] = []
        self._last_atmosphere_round: int = _DEFAULT_LAST_ATMOSPHERE_ROUND
        self._base_probability: float = _BASE_PROBABILITY

    def record_event(
        self,
        event_type: str,
        round_num: int,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry: Dict[str, Any] = {
            "event_type": event_type,
            "round_num": round_num,
        }
        if details is not None:
            entry["details"] = details
        self._event_history.append(entry)
        if len(self._event_history) > _EVENT_HISTORY_MAX:
            self._event_history = self._event_history[-_EVENT_HISTORY_MAX:]

    def should_generate(
        self,
        round_num: int,
        recent_events: List[Dict[str, Any]],
        avg_emotion: float,
    ) -> bool:
        if round_num - self._last_atmosphere_round < _MIN_INTERVAL_ROUNDS:
            return False
        probability = self._base_probability
        cutoff = round_num - _RECENT_EVENT_WINDOW
        for evt in recent_events:
            evt_round = evt.get("round_num", 0)
            evt_type = evt.get("event_type", "")
            if evt_round >= cutoff and evt_type in _EVENT_BOOST_TYPES:
                probability = _EVENT_BOOST_PROBABILITY
                break
        if avg_emotion < _EMOTION_INTENSE_LOW or avg_emotion > _EMOTION_INTENSE_HIGH:
            probability += _EMOTION_BOOST_PROBABILITY
        return self._rng.uniform(0.0, 1.0) < probability

    async def generate(
        self,
        scene_name: str,
        emotion_context: Dict[str, float],
        llm_bridge: Any,
    ) -> str:
        avg_p = emotion_context.get("pleasure", 0.0)
        avg_a = emotion_context.get("arousal", 0.0)
        avg_d = emotion_context.get("dominance", 0.0)

        if avg_p < _PLEASURE_DEPRESSED_THRESHOLD:
            imagery = _IMAGERY_DEPRESSED
        elif avg_p > _PLEASURE_BRIGHT_THRESHOLD and avg_a > _AROUSAL_BRIGHT_THRESHOLD:
            imagery = _IMAGERY_BRIGHT
        else:
            imagery = _IMAGERY_NEUTRAL

        system_content = _PROMPT_SYSTEM.format(imagery=imagery)
        user_content = (
            f"场景：{scene_name}\n"
            f"情感上下文 — 愉悦度(P): {avg_p:.2f}, "
            f"唤醒度(A): {avg_a:.2f}, "
            f"支配度(D): {avg_d:.2f}"
        )

        sdk_type = llm_bridge.get_sdk_type()
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        request = LLMRequest(
            sdk_type=sdk_type,
            messages=messages,
            temperature=_ATMOSPHERE_TEMPERATURE,
            max_tokens=_ATMOSPHERE_MAX_TOKENS,
        )

        try:
            response = await llm_bridge.chat(request)
            current_round = emotion_context.get("round", self._last_atmosphere_round + _MIN_INTERVAL_ROUNDS)
            self._last_atmosphere_round = current_round
            return response.content
        except Exception as exc:
            _logger.warning("AtmosphereAgent LLM调用失败: %s", exc)
            return ""
