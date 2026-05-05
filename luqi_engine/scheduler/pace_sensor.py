"""节奏感知器 - 感知对话节奏"""

from __future__ import annotations

import logging
import math
from collections import deque
from typing import Deque, Optional

from luqi_engine.core.config import PaceConfig
from luqi_engine.core.interfaces import IPaceSensor
from luqi_engine.core.types import AutoModeConfig

logger = logging.getLogger(__name__)

_PACE_FROZEN = "frozen"
_PACE_SLOW = "slow"
_PACE_NORMAL = "normal"
_PACE_FAST = "fast"
_PACE_URGENT = "urgent"

_FROZEN_THRESHOLD_MULTIPLIER = 3.0
_URGENT_THRESHOLD_DIVISOR = 3.0

_AUTO_MODE_FROZEN_TIMEOUT = 120.0
_AUTO_MODE_FROZEN_MAX_TICKS = 3
_AUTO_MODE_FROZEN_NPC_AUTONOMY = 0.2

_AUTO_MODE_SLOW_TIMEOUT = 60.0
_AUTO_MODE_SLOW_MAX_TICKS = 5
_AUTO_MODE_SLOW_NPC_AUTONOMY = 0.4

_AUTO_MODE_NORMAL_TIMEOUT = 30.0
_AUTO_MODE_NORMAL_MAX_TICKS = 10
_AUTO_MODE_NORMAL_NPC_AUTONOMY = 0.5

_AUTO_MODE_FAST_TIMEOUT = 15.0
_AUTO_MODE_FAST_MAX_TICKS = 15
_AUTO_MODE_FAST_NPC_AUTONOMY = 0.7

_AUTO_MODE_URGENT_TIMEOUT = 5.0
_AUTO_MODE_URGENT_MAX_TICKS = 20
_AUTO_MODE_URGENT_NPC_AUTONOMY = 0.9


class PaceSensor(IPaceSensor):
    def __init__(self, config: Optional[PaceConfig] = None) -> None:
        self._config = config or PaceConfig()
        self._intervals: Deque[float] = deque(
            maxlen=self._config.pace_window_size,
        )
        self._current_pace: str = _PACE_NORMAL

    def get_current_pace(self) -> str:
        return self._current_pace

    def update_pace(self, message_interval_seconds: float) -> None:
        self._intervals.append(message_interval_seconds)
        if len(self._intervals) < 2:
            self._current_pace = _PACE_NORMAL
            return

        avg_interval = sum(self._intervals) / len(self._intervals)
        slow_threshold = self._config.slow_threshold
        fast_threshold = self._config.fast_threshold

        frozen_threshold = slow_threshold * _FROZEN_THRESHOLD_MULTIPLIER
        urgent_threshold = fast_threshold / _URGENT_THRESHOLD_DIVISOR

        if avg_interval >= frozen_threshold:
            self._current_pace = _PACE_FROZEN
        elif avg_interval >= slow_threshold:
            self._current_pace = _PACE_SLOW
        elif avg_interval <= urgent_threshold:
            self._current_pace = _PACE_URGENT
        elif avg_interval <= fast_threshold:
            self._current_pace = _PACE_FAST
        else:
            self._current_pace = _PACE_NORMAL

    def get_auto_mode_config(self) -> AutoModeConfig:
        pace_config_map = {
            _PACE_FROZEN: AutoModeConfig(
                enabled=True,
                trigger_timeout_seconds=_AUTO_MODE_FROZEN_TIMEOUT,
                max_auto_ticks=_AUTO_MODE_FROZEN_MAX_TICKS,
                npc_autonomy_level=_AUTO_MODE_FROZEN_NPC_AUTONOMY,
                advance_on_timeout=True,
                pause_on_branch_point=True,
            ),
            _PACE_SLOW: AutoModeConfig(
                enabled=True,
                trigger_timeout_seconds=_AUTO_MODE_SLOW_TIMEOUT,
                max_auto_ticks=_AUTO_MODE_SLOW_MAX_TICKS,
                npc_autonomy_level=_AUTO_MODE_SLOW_NPC_AUTONOMY,
                advance_on_timeout=True,
                pause_on_branch_point=True,
            ),
            _PACE_NORMAL: AutoModeConfig(
                enabled=True,
                trigger_timeout_seconds=_AUTO_MODE_NORMAL_TIMEOUT,
                max_auto_ticks=_AUTO_MODE_NORMAL_MAX_TICKS,
                npc_autonomy_level=_AUTO_MODE_NORMAL_NPC_AUTONOMY,
                advance_on_timeout=True,
                pause_on_branch_point=True,
            ),
            _PACE_FAST: AutoModeConfig(
                enabled=True,
                trigger_timeout_seconds=_AUTO_MODE_FAST_TIMEOUT,
                max_auto_ticks=_AUTO_MODE_FAST_MAX_TICKS,
                npc_autonomy_level=_AUTO_MODE_FAST_NPC_AUTONOMY,
                advance_on_timeout=True,
                pause_on_branch_point=False,
            ),
            _PACE_URGENT: AutoModeConfig(
                enabled=True,
                trigger_timeout_seconds=_AUTO_MODE_URGENT_TIMEOUT,
                max_auto_ticks=_AUTO_MODE_URGENT_MAX_TICKS,
                npc_autonomy_level=_AUTO_MODE_URGENT_NPC_AUTONOMY,
                advance_on_timeout=True,
                pause_on_branch_point=False,
            ),
        }
        return pace_config_map.get(self._current_pace, AutoModeConfig())
