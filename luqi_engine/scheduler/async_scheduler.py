from __future__ import annotations

import logging
from enum import Enum, auto
from typing import FrozenSet

logger = logging.getLogger(__name__)


class EngineState(Enum):
    IDLE = auto()
    SYNC = auto()
    RESPONDING = auto()
    ASYNC_PREP = auto()
    READY = auto()
    AUTO = auto()


_STATES_ACCEPT_INPUT: FrozenSet[EngineState] = frozenset({
    EngineState.IDLE,
    EngineState.READY,
    EngineState.AUTO,
})

_VALID_TRANSITIONS: dict[EngineState, FrozenSet[EngineState]] = {
    EngineState.IDLE: frozenset({EngineState.SYNC}),
    EngineState.SYNC: frozenset({EngineState.RESPONDING, EngineState.IDLE}),
    EngineState.RESPONDING: frozenset({EngineState.ASYNC_PREP, EngineState.IDLE}),
    EngineState.ASYNC_PREP: frozenset({EngineState.READY, EngineState.IDLE}),
    EngineState.READY: frozenset({EngineState.AUTO, EngineState.SYNC, EngineState.IDLE}),
    EngineState.AUTO: frozenset({EngineState.SYNC, EngineState.IDLE}),
}


class _TransitionError(Exception):
    pass


class AsyncTaskScheduler:
    def __init__(self) -> None:
        self._state: EngineState = EngineState.IDLE

    def get_state(self) -> EngineState:
        return self._state

    def can_accept_input(self) -> bool:
        return self._state in _STATES_ACCEPT_INPUT

    def is_auto_mode(self) -> bool:
        return self._state == EngineState.AUTO

    def start_sync(self) -> None:
        self._transition(EngineState.SYNC)

    def start_responding(self) -> None:
        self._transition(EngineState.RESPONDING)

    def start_async_prep(self) -> None:
        self._transition(EngineState.ASYNC_PREP)

    def mark_ready(self) -> None:
        self._transition(EngineState.READY)

    def enter_auto(self) -> None:
        self._transition(EngineState.AUTO)

    def reset(self) -> None:
        self._state = EngineState.IDLE

    def _transition(self, target: EngineState) -> None:
        allowed = _VALID_TRANSITIONS.get(self._state, frozenset())
        if target not in allowed:
            raise _TransitionError(
                f"不允许从 {self._state.name} 转换到 {target.name}，"
                f"允许的目标状态: {[s.name for s in allowed]}"
            )
        logger.debug(
            "AsyncTaskScheduler 状态转换: %s → %s",
            self._state.name,
            target.name,
        )
        self._state = target
