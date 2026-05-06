import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from luqi_engine.agents.critic_agent import CriticAgent
from luqi_engine.core.constants import CriticMode, CriticVerdictType
from luqi_engine.core.types import CriticVerdict, LLMResponse, SDKType


_MOCK_CRITIC_VERDICT_JSON = json.dumps({
    "verdict": "minor_fix",
    "checks": [
        {"dimension": "consistency", "severity": "warning", "score": 0.6, "detail": "情感变化幅度过大"},
        {"dimension": "emotion_plausibility", "severity": "pass", "score": 0.9, "detail": "情感合理性良好"},
        {"dimension": "narrative_alignment", "severity": "pass", "score": 0.85, "detail": "叙事对齐良好"},
        {"dimension": "character_faithfulness", "severity": "pass", "score": 0.8, "detail": "角色忠实度可接受"},
        {"dimension": "action_reasonableness", "severity": "warning", "score": 0.5, "detail": "动作合理性存疑"},
        {"dimension": "tone_appropriateness", "severity": "pass", "score": 0.9, "detail": "语气适当"},
    ],
    "overall_confidence": 0.75,
    "corrections": {
        "suggested_emotion_delta": {"pleasure": -0.1, "arousal": 0.0, "dominance": 0.1},
        "suggested_action": "soften_response",
        "suggested_key_point_addition": "考虑角色当前压力",
        "narrative_risk_flag": False,
    },
    "override_recommendation": None,
})


def _make_mock_bridge(response_content: str) -> MagicMock:
    bridge = MagicMock()
    bridge.get_sdk_type.return_value = SDKType.OPENAI
    bridge.chat = AsyncMock(return_value=LLMResponse(
        content=response_content,
        role="assistant",
        finish_reason="stop",
        usage={},
        tokens=80,
    ))
    return bridge


class TestCriticAgentNameAndType:
    def test_get_name(self):
        agent = CriticAgent()
        assert agent.get_name() == "critic"

    def test_get_output_type(self):
        agent = CriticAgent()
        assert agent.get_output_type() == "CriticVerdict"


class TestCriticAgentRunFull:
    def test_full_mode_returns_all_checks(self):
        agent = CriticAgent()
        bridge = _make_mock_bridge(_MOCK_CRITIC_VERDICT_JSON)
        context = {"canonical_ir": {"intent": "test"}}

        result = asyncio.run(agent.run(context, bridge, mode=CriticMode.FULL))
        assert isinstance(result, CriticVerdict)
        assert result.verdict == CriticVerdictType.MINOR_FIX
        assert len(result.checks) == 6
        assert result.overall_confidence == pytest.approx(0.75)

    def test_full_mode_includes_corrections(self):
        agent = CriticAgent()
        bridge = _make_mock_bridge(_MOCK_CRITIC_VERDICT_JSON)
        context = {"canonical_ir": {"intent": "test"}}

        result = asyncio.run(agent.run(context, bridge, mode=CriticMode.FULL))
        assert result.corrections is not None
        assert result.corrections.suggested_action == "soften_response"
        assert result.corrections.suggested_emotion_delta is not None
        assert result.corrections.suggested_emotion_delta.pleasure == pytest.approx(-0.1)
        assert result.corrections.narrative_risk_flag is False


class TestCriticAgentRunLight:
    def test_light_mode_filters_checks(self):
        agent = CriticAgent()
        bridge = _make_mock_bridge(_MOCK_CRITIC_VERDICT_JSON)
        context = {"canonical_ir": {"intent": "test"}}

        result = asyncio.run(agent.run(context, bridge, mode=CriticMode.LIGHT))
        assert isinstance(result, CriticVerdict)
        assert len(result.checks) == 2
        dimensions = {c.dimension for c in result.checks}
        assert dimensions == {"consistency", "emotion_plausibility"}

    def test_light_mode_removes_corrections(self):
        agent = CriticAgent()
        bridge = _make_mock_bridge(_MOCK_CRITIC_VERDICT_JSON)
        context = {"canonical_ir": {"intent": "test"}}

        result = asyncio.run(agent.run(context, bridge, mode=CriticMode.LIGHT))
        assert result.corrections is None


class TestCriticAgentFallback:
    def test_fallback_returns_accept_verdict(self):
        agent = CriticAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("连接失败"))

        context = {"canonical_ir": {"intent": "test"}}
        result = asyncio.run(agent.run(context, bridge, mode=CriticMode.LIGHT))

        assert isinstance(result, CriticVerdict)
        assert result.verdict == "accept"
        assert result.overall_confidence == pytest.approx(0.5)
        assert len(result.checks) == 2

    def test_fallback_full_mode_has_more_checks(self):
        agent = CriticAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("超时"))

        context = {"canonical_ir": {"intent": "test"}}
        result = asyncio.run(agent.run(context, bridge, mode=CriticMode.FULL))

        assert isinstance(result, CriticVerdict)
        assert len(result.checks) == 6


class TestCriticAgentInvalidMode:
    def test_invalid_mode_defaults_to_light(self):
        agent = CriticAgent()
        bridge = _make_mock_bridge(_MOCK_CRITIC_VERDICT_JSON)
        context = {"canonical_ir": {"intent": "test"}}

        result = asyncio.run(agent.run(context, bridge, mode="invalid"))
        assert isinstance(result, CriticVerdict)
        assert len(result.checks) == 2
