"""
叙事智能体 - 生成叙事差量 NarrativeDelta
职责：事实更新、章节推进、场景预测、开放问题管理
支持三种模式：full_update / incremental / prediction_only
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from luqi_engine.core.interfaces import IAgentRunner
from luqi_engine.core.types import (
    ChapterUpdate,
    LLMRequest,
    LLMResponse,
    NarrativeDelta,
    NextPrediction,
    NewFact,
    SDKType,
)
from luqi_engine.core.constants import (
    LLMMessageRole,
    NovelMode,
    PaceLevel,
    _FALLBACK_CONTEXT_MAX_LENGTH,
    _FALLBACK_SOURCE,
    _ANTHROPIC_PREFILL_NOVELIST,
)
from luqi_engine.llm.prompt_builder import PromptBuilder
from luqi_engine.llm.response_parser import ResponseParser

logger = logging.getLogger(__name__)

_MODE_FULL_UPDATE = NovelMode.FULL_UPDATE
_MODE_INCREMENTAL = NovelMode.INCREMENTAL
_MODE_PREDICTION_ONLY = NovelMode.PREDICTION_ONLY
_VALID_MODES = frozenset({_MODE_FULL_UPDATE, _MODE_INCREMENTAL, _MODE_PREDICTION_ONLY})
_DEFAULT_MODE = _MODE_INCREMENTAL


class NovelistAgent(IAgentRunner):
    """
    叙事智能体
    根据对话结果和叙事上下文生成 NarrativeDelta
    """

    def __init__(
        self,
        prompt_builder: Optional[PromptBuilder] = None,
        response_parser: Optional[ResponseParser] = None,
    ) -> None:
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._response_parser = response_parser or ResponseParser()

    async def run(
        self,
        context: Dict[str, Any],
        llm_bridge: Any,
        **kwargs: Any,
    ) -> NarrativeDelta:
        """
        运行叙事智能体

        context 必需字段:
            - narrative_context: str — 当前叙事上下文
        context 可选字段:
            - chapter_outline: Dict — 章节大纲
            - character_arcs: Dict — 角色弧线
            - open_questions: List[str] — 开放问题
            - recent_facts: List[Dict] — 近期事实
            - canonical_ir: Dict — 对话智能体输出

        kwargs:
            - mode: str — 运行模式 (full_update / incremental / prediction_only)
        """
        mode = kwargs.get("mode", _DEFAULT_MODE)
        if mode not in _VALID_MODES:
            logger.warning(
                "NovelistAgent 收到无效模式 %r，回退到 %s", mode, _DEFAULT_MODE
            )
            mode = _DEFAULT_MODE

        context["novel_mode"] = mode
        prompt_text = self._prompt_builder.build_novel_prompt(context)
        sdk_type = llm_bridge.get_sdk_type()

        messages = self._build_messages(prompt_text, context, sdk_type)
        request = LLMRequest(
            sdk_type=sdk_type,
            messages=messages,
        )

        try:
            response: LLMResponse = await llm_bridge.chat(request)
            delta = self._response_parser.parse_narrative_delta(response.content)
            return self._apply_mode_filter(delta, mode)
        except Exception as exc:
            logger.warning(
                "NovelistAgent LLM 调用失败，启用降级: %s", exc
            )
            return self._build_fallback_delta(context, mode)

    def get_name(self) -> str:
        return "novelist"

    def get_output_type(self) -> str:
        return "NarrativeDelta"

    @staticmethod
    def _build_messages(
        prompt_text: str,
        context: Dict[str, Any],
        sdk_type: SDKType,
    ) -> List[Dict[str, str]]:
        narrative_context = context.get("narrative_context", "")
        if sdk_type == SDKType.ANTHROPIC:
            return [
                {"role": LLMMessageRole.USER, "content": prompt_text},
                {"role": LLMMessageRole.ASSISTANT, "content": _ANTHROPIC_PREFILL_NOVELIST},
                {"role": LLMMessageRole.USER, "content": narrative_context},
            ]
        return [
            {"role": LLMMessageRole.SYSTEM, "content": prompt_text},
            {"role": LLMMessageRole.USER, "content": narrative_context},
        ]

    @staticmethod
    def _apply_mode_filter(
        delta: NarrativeDelta, mode: str
    ) -> NarrativeDelta:
        """
        根据模式过滤 NarrativeDelta 字段
        - full_update: 保留全部字段
        - incremental: 保留 new_facts + chapter_update + open_questions
        - prediction_only: 仅保留 next_prediction
        """
        if mode == _MODE_FULL_UPDATE:
            return delta

        if mode == _MODE_PREDICTION_ONLY:
            return NarrativeDelta(
                version=delta.version,
                next_prediction=delta.next_prediction,
            )

        return NarrativeDelta(
            version=delta.version,
            new_facts=delta.new_facts,
            chapter_update=delta.chapter_update,
            open_questions_added=delta.open_questions_added,
            open_questions_resolved=delta.open_questions_resolved,
        )

    @staticmethod
    def _build_fallback_delta(
        context: Dict[str, Any], mode: str
    ) -> NarrativeDelta:
        """
        基于规则的降级 NarrativeDelta
        """
        narrative_context = context.get("narrative_context", "")

        if mode == _MODE_PREDICTION_ONLY:
            return NarrativeDelta(
                next_prediction=NextPrediction(
                    likely_next_scenes=[],
                    narrative_tension=0.0,
                    suggested_pace=PaceLevel.NORMAL,
                ),
                narrative_note="降级模式：LLM不可用",
            )

        return NarrativeDelta(
            new_facts=[
                NewFact(
                    id="",
                    timestamp="",
                    source=_FALLBACK_SOURCE,
                    content=narrative_context[:_FALLBACK_CONTEXT_MAX_LENGTH] if narrative_context else "",
                )
            ],
            chapter_update=ChapterUpdate(),
            narrative_note="降级模式：LLM不可用",
        )
