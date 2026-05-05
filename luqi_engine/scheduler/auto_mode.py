"""自动模式执行器 - 实现自动对话模式"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from luqi_engine.core.types import (
    AtmosphereOutput,
    AutoModeConfig,
    CanonicalIR,
    CriticVerdict,
    NarrativeDelta,
)
from luqi_engine.core.constants import (
    AtmosphereMode,
    CriticVerdictType,
    _CTX_KEY_GOAP_NEXT_ACTION,
    _CTX_KEY_GOAP_PLAN_LENGTH,
    _DEFAULT_DOMINANT_EMOTION,
)

logger = logging.getLogger(__name__)

_CRITIC_MODE_LIGHT = AtmosphereMode.LIGHT
_ATMOSPHERE_MODE_LIGHT = AtmosphereMode.LIGHT
_VERDICT_REJECT = CriticVerdictType.REJECT
_BRANCH_POINT_NARRATIVE_SIGNAL = "branch_point"


@dataclass
class TickResult:
    tick_number: int
    dialogue_ir: Optional[CanonicalIR] = None
    critic_verdict: Optional[CriticVerdict] = None
    atmosphere_output: Optional[AtmosphereOutput] = None
    is_branch_point: bool = False
    paused_at_branch: bool = False


class AutoModeExecutor:
    def __init__(self, config: Optional[AutoModeConfig] = None) -> None:
        self._config = config or AutoModeConfig()
        self._tick_count: int = 0
        self._paused: bool = False

    async def execute_tick(
        self,
        dialogue_agent: Any,
        critic_agent: Any,
        atmosphere_agent: Any,
        context: Dict[str, Any],
        llm_bridge: Any,
        goap_planner: Any = None,
        goap_start_state: Any = None,
        goap_goal_state: Any = None,
    ) -> TickResult:
        self._tick_count += 1
        tick_result = TickResult(tick_number=self._tick_count)

        if goap_planner is not None and goap_start_state is not None and goap_goal_state is not None:
            plan = goap_planner.plan(goap_start_state, goap_goal_state)
            if plan is not None and len(plan) > 0:
                next_action = plan[0]
                context[_CTX_KEY_GOAP_NEXT_ACTION] = next_action.name
                context[_CTX_KEY_GOAP_PLAN_LENGTH] = len(plan)

        try:
            dialogue_ir: CanonicalIR = await dialogue_agent.run(
                context, llm_bridge,
            )
            tick_result.dialogue_ir = dialogue_ir
        except Exception as exc:
            logger.warning("AutoModeExecutor tick %d dialogue 失败: %s", self._tick_count, exc)
            return tick_result

        critic_context = dict(context)
        critic_context["canonical_ir"] = dialogue_ir
        try:
            critic_verdict: CriticVerdict = await critic_agent.run(
                critic_context, llm_bridge, mode=_CRITIC_MODE_LIGHT,
            )
            tick_result.critic_verdict = critic_verdict
        except Exception as exc:
            logger.warning("AutoModeExecutor tick %d critic 失败: %s", self._tick_count, exc)

        if (
            tick_result.critic_verdict is not None
            and tick_result.critic_verdict.verdict == _VERDICT_REJECT
        ):
            logger.info(
                "AutoModeExecutor tick %d 被 Critic 拒绝，终止本轮",
                self._tick_count,
            )
            return tick_result

        atmosphere_context = dict(context)
        atmosphere_context[_DEFAULT_DOMINANT_EMOTION] = (
            dialogue_ir.emotion_delta.pleasure
            if dialogue_ir.emotion_delta else _DEFAULT_DOMINANT_EMOTION
        )
        try:
            atmosphere_output: AtmosphereOutput = await atmosphere_agent.run(
                atmosphere_context, llm_bridge, mode=_ATMOSPHERE_MODE_LIGHT,
            )
            tick_result.atmosphere_output = atmosphere_output
        except Exception as exc:
            logger.warning("AutoModeExecutor tick %d atmosphere 失败: %s", self._tick_count, exc)

        if self.is_branch_point(dialogue_ir):
            tick_result.is_branch_point = True
            if self._config.pause_on_branch_point:
                self._paused = True
                tick_result.paused_at_branch = True
                logger.info(
                    "AutoModeExecutor tick %d 到达分支点，已暂停",
                    self._tick_count,
                )

        return tick_result

    def is_branch_point(self, dialogue_ir: CanonicalIR) -> bool:
        return dialogue_ir.narrative_signal == _BRANCH_POINT_NARRATIVE_SIGNAL

    def set_pause_at_branch(self, paused: bool) -> None:
        self._paused = paused

    def is_paused(self) -> bool:
        return self._paused

    def get_tick_count(self) -> int:
        return self._tick_count

    def reset_ticks(self) -> None:
        self._tick_count = 0
        self._paused = False
