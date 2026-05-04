"""
评论智能体 - 对 CanonicalIR 和 NarrativeDelta 进行质量审查
职责：一致性检查、情感合理性、叙事风险标记、修正建议
支持两种模式：full / light
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from luqi_engine.core.interfaces import IAgentRunner
from luqi_engine.core.types import (
    CriticCheck,
    CriticCorrections,
    CriticVerdict,
    EmotionDelta,
    LLMRequest,
    LLMResponse,
    SDKType,
)
from luqi_engine.core.constants import (
    LLMMessageRole,
    CriticMode,
    CriticSeverity,
    CriticVerdictType,
    _FALLBACK_CRITIC_CONFIDENCE,
    _ANTHROPIC_PREFILL_CRITIC,
)
from luqi_engine.llm.prompt_builder import PromptBuilder
from luqi_engine.llm.response_parser import ResponseParser

logger = logging.getLogger(__name__)

_MODE_FULL = CriticMode.FULL
_MODE_LIGHT = CriticMode.LIGHT
_VALID_MODES = frozenset({_MODE_FULL, _MODE_LIGHT})
_DEFAULT_MODE = _MODE_LIGHT

_VERDICT_ACCEPT = CriticVerdictType.ACCEPT
_VERDICT_REJECT = CriticVerdictType.REJECT
_VERDICT_REVISE = CriticVerdictType.REVIEW

_LIGHT_CHECK_DIMENSIONS = ("consistency", "emotion_plausibility")
_FULL_CHECK_DIMENSIONS = (
    "consistency",
    "emotion_plausibility",
    "narrative_alignment",
    "character_faithfulness",
    "action_reasonableness",
    "tone_appropriateness",
)


class CriticAgent(IAgentRunner):
    """
    评论智能体
    对对话和叙事输出进行质量审查，输出 CriticVerdict
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
        mode: CriticMode = CriticMode.FULL,
    ) -> CriticVerdict:
        """
        运行评论智能体

        context 必需字段:
            - canonical_ir: Dict — 待审查的 CanonicalIR
        context 可选字段:
            - narrative_delta: Dict — 待审查的 NarrativeDelta
            - character_state: Dict — 角色当前状态
            - narrative_context: str — 叙事上下文

        Args:
            mode: CriticMode — 运行模式 (CriticMode.FULL / CriticMode.LIGHT)
        """
        if mode not in _VALID_MODES:
            logger.warning(
                "CriticAgent 收到无效模式 %r，回退到 %s", mode, _DEFAULT_MODE
            )
            mode = _DEFAULT_MODE

        context["critic_mode"] = mode
        prompt_text = self._prompt_builder.build_critic_prompt(context)
        sdk_type = llm_bridge.get_sdk_type()

        messages = self._build_messages(prompt_text, context, sdk_type)
        request = LLMRequest(
            sdk_type=sdk_type,
            messages=messages,
        )

        try:
            response: LLMResponse = await llm_bridge.chat(request)
            verdict = self._response_parser.parse_critic_verdict(response.content)
            return self._apply_mode_filter(verdict, mode)
        except Exception as exc:
            logger.warning(
                "CriticAgent LLM 调用失败，启用降级: %s", exc
            )
            return self._build_fallback_verdict(context, mode)

    def get_name(self) -> str:
        return "critic"

    def get_output_type(self) -> str:
        return "CriticVerdict"

    @staticmethod
    def _build_messages(
        prompt_text: str,
        context: Dict[str, Any],
        sdk_type: SDKType,
    ) -> List[Dict[str, str]]:
        ir_summary = str(context.get("canonical_ir", ""))
        if sdk_type == SDKType.ANTHROPIC:
            return [
                {"role": LLMMessageRole.USER, "content": prompt_text},
                {"role": LLMMessageRole.ASSISTANT, "content": _ANTHROPIC_PREFILL_CRITIC},
                {"role": LLMMessageRole.USER, "content": ir_summary},
            ]
        return [
            {"role": LLMMessageRole.SYSTEM, "content": prompt_text},
            {"role": LLMMessageRole.USER, "content": ir_summary},
        ]

    @staticmethod
    def _apply_mode_filter(verdict: CriticVerdict, mode: str) -> CriticVerdict:
        """
        根据模式过滤 CriticVerdict
        - full: 保留全部检查维度和修正建议
        - light: 仅保留一致性检查和情感合理性
        """
        if mode == _MODE_FULL:
            return verdict

        allowed = set(_LIGHT_CHECK_DIMENSIONS)
        filtered_checks = [
            check for check in verdict.checks
            if check.dimension in allowed
        ]
        return CriticVerdict(
            verdict=verdict.verdict,
            checks=filtered_checks,
            overall_confidence=verdict.overall_confidence,
            corrections=None,
            override_recommendation=verdict.override_recommendation,
        )

    @staticmethod
    def _build_fallback_verdict(
        context: Dict[str, Any], mode: str
    ) -> CriticVerdict:
        """
        基于规则的降级 CriticVerdict
        降级时默认 accept，置信度降低
        """
        dimensions = (
            _LIGHT_CHECK_DIMENSIONS
            if mode == _MODE_LIGHT
            else _FULL_CHECK_DIMENSIONS
        )
        checks = [
            CriticCheck(
                dimension=dim,
                severity=CriticSeverity.PASS,
                score=1.0,
                detail="降级模式：LLM不可用，默认通过",
            )
            for dim in dimensions
        ]

        return CriticVerdict(
            verdict=_VERDICT_ACCEPT,
            checks=checks,
            overall_confidence=_FALLBACK_CRITIC_CONFIDENCE,
            corrections=None,
            override_recommendation=None,
        )
