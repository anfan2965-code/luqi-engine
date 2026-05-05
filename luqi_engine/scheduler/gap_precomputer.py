"""间隙预计算器 - 利用用户阅读时间预计算"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from luqi_engine.core.types import (
    AtmosphereOutput,
    CanonicalIR,
    CriticVerdict,
    NarrativeDelta,
)
from luqi_engine.core.constants import (
    NovelMode,
    AtmosphereMode,
    _TASK_NAME_NOVEL_UPDATE,
    _TASK_NAME_CRITIC_PRECHECK,
    _TASK_NAME_DIALOGUE_PREANALYZE,
    _TASK_NAME_ATMOSPHERE_PRERENDER,
    _CACHE_KEY_NOVEL,
    _CACHE_KEY_CRITIC,
    _CACHE_KEY_DIALOGUE,
    _CACHE_KEY_ATMOSPHERE,
)

logger = logging.getLogger(__name__)

_NOVEL_MODE_INCREMENTAL = NovelMode.INCREMENTAL
_CRITIC_MODE_LIGHT = AtmosphereMode.LIGHT
_ATMOSPHERE_MODE_LIGHT = AtmosphereMode.LIGHT


@dataclass
class GapTaskResult:
    task_name: str
    success: bool
    result: Any = None
    error_message: str = ""


class GapPrecomputer:
    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}

    async def task_a_novel_update(
        self,
        novel_agent: Any,
        context: Dict[str, Any],
        llm_bridge: Any,
    ) -> GapTaskResult:
        try:
            delta: NarrativeDelta = await novel_agent.run(
                context, llm_bridge, mode=_NOVEL_MODE_INCREMENTAL,
            )
            self._cache[_CACHE_KEY_NOVEL] = delta
            return GapTaskResult(task_name=_TASK_NAME_NOVEL_UPDATE, success=True, result=delta)
        except Exception as exc:
            logger.warning("GapPrecomputer task_a_novel_update 失败: %s", exc)
            return GapTaskResult(
                task_name=_TASK_NAME_NOVEL_UPDATE,
                success=False,
                error_message=str(exc),
            )

    async def task_b_critic_precheck(
        self,
        critic_agent: Any,
        context: Dict[str, Any],
        llm_bridge: Any,
    ) -> GapTaskResult:
        try:
            verdict: CriticVerdict = await critic_agent.run(
                context, llm_bridge, mode=_CRITIC_MODE_LIGHT,
            )
            self._cache[_CACHE_KEY_CRITIC] = verdict
            return GapTaskResult(task_name=_TASK_NAME_CRITIC_PRECHECK, success=True, result=verdict)
        except Exception as exc:
            logger.warning("GapPrecomputer task_b_critic_precheck 失败: %s", exc)
            return GapTaskResult(
                task_name=_TASK_NAME_CRITIC_PRECHECK,
                success=False,
                error_message=str(exc),
            )

    async def task_c_dialogue_preanalyze(
        self,
        dialogue_agent: Any,
        context: Dict[str, Any],
        llm_bridge: Any,
    ) -> GapTaskResult:
        try:
            ir: CanonicalIR = await dialogue_agent.run(context, llm_bridge)
            self._cache[_CACHE_KEY_DIALOGUE] = ir
            return GapTaskResult(task_name=_TASK_NAME_DIALOGUE_PREANALYZE, success=True, result=ir)
        except Exception as exc:
            logger.warning("GapPrecomputer task_c_dialogue_preanalyze 失败: %s", exc)
            return GapTaskResult(
                task_name=_TASK_NAME_DIALOGUE_PREANALYZE,
                success=False,
                error_message=str(exc),
            )

    async def task_d_atmosphere_prerender(
        self,
        atmosphere_agent: Any,
        context: Dict[str, Any],
        llm_bridge: Any,
    ) -> GapTaskResult:
        try:
            output: AtmosphereOutput = await atmosphere_agent.run(
                context, llm_bridge, mode=_ATMOSPHERE_MODE_LIGHT,
            )
            self._cache[_CACHE_KEY_ATMOSPHERE] = output
            return GapTaskResult(task_name=_TASK_NAME_ATMOSPHERE_PRERENDER, success=True, result=output)
        except Exception as exc:
            logger.warning("GapPrecomputer task_d_atmosphere_prerender 失败: %s", exc)
            return GapTaskResult(
                task_name=_TASK_NAME_ATMOSPHERE_PRERENDER,
                success=False,
                error_message=str(exc),
            )

    async def run_all_tasks(
        self,
        novel_agent: Any,
        critic_agent: Any,
        dialogue_agent: Any,
        atmosphere_agent: Any,
        context: Dict[str, Any],
        llm_bridge: Any,
    ) -> List[GapTaskResult]:
        tasks = [
            self.task_a_novel_update(novel_agent, context, llm_bridge),
            self.task_b_critic_precheck(critic_agent, context, llm_bridge),
            self.task_c_dialogue_preanalyze(dialogue_agent, context, llm_bridge),
            self.task_d_atmosphere_prerender(atmosphere_agent, context, llm_bridge),
        ]
        results: List[GapTaskResult] = await asyncio.gather(*tasks)
        return list(results)

    def get_cached_results(self) -> Dict[str, Any]:
        return dict(self._cache)

    def clear_cache(self) -> None:
        self._cache.clear()
