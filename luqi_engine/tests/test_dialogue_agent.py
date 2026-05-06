import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from luqi_engine.agents.dialogue_agent import DialogueAgent
from luqi_engine.core.types import CanonicalIR, EmotionDelta, LLMResponse, SDKType
from luqi_engine.core.constants import ToneType, LengthHint


_MOCK_CANONICAL_IR_JSON = json.dumps({
    "intent": "greeting",
    "confidence": 0.9,
    "emotion_delta": {"pleasure": 0.3, "arousal": 0.1, "dominance": 0.0},
    "seven_trigger": "喜",
    "action": "respond",
    "action_params": {"target": "user"},
    "key_points": ["问候", "友好"],
    "tone": "casual",
    "length_hint": "medium",
    "narrative_signal": None,
    "memory_to_add": None,
})


def _make_mock_bridge(response_content: str) -> MagicMock:
    bridge = MagicMock()
    bridge.get_sdk_type.return_value = SDKType.OPENAI
    bridge.chat = AsyncMock(return_value=LLMResponse(
        content=response_content,
        role="assistant",
        finish_reason="stop",
        usage={},
        tokens=50,
    ))
    return bridge


class TestDialogueAgentNameAndType:
    def test_get_name(self):
        agent = DialogueAgent()
        assert agent.get_name() == "dialogue"

    def test_get_output_type(self):
        agent = DialogueAgent()
        assert agent.get_output_type() == "CanonicalIR"


class TestDialogueAgentRun:
    def test_run_returns_canonical_ir(self):
        agent = DialogueAgent()
        bridge = _make_mock_bridge(_MOCK_CANONICAL_IR_JSON)
        context = {"user_message": "你好", "character_name": "测试角色"}

        result = asyncio.run(agent.run(context, bridge))
        assert isinstance(result, CanonicalIR)
        assert result.intent == "greeting"
        assert result.confidence == pytest.approx(0.9)
        assert result.tone == ToneType.CASUAL
        assert result.length_hint == LengthHint.MEDIUM
        assert result.seven_trigger == "喜"
        assert result.action == "respond"
        assert result.key_points == ["问候", "友好"]

    def test_run_parses_emotion_delta(self):
        agent = DialogueAgent()
        bridge = _make_mock_bridge(_MOCK_CANONICAL_IR_JSON)
        context = {"user_message": "你好"}

        result = asyncio.run(agent.run(context, bridge))
        assert isinstance(result.emotion_delta, EmotionDelta)
        assert result.emotion_delta.pleasure == pytest.approx(0.3)
        assert result.emotion_delta.arousal == pytest.approx(0.1)
        assert result.emotion_delta.dominance == pytest.approx(0.0)

    def test_run_handles_fenced_json(self):
        fenced = f"```json\n{_MOCK_CANONICAL_IR_JSON}\n```"
        agent = DialogueAgent()
        bridge = _make_mock_bridge(fenced)
        context = {"user_message": "你好"}

        result = asyncio.run(agent.run(context, bridge))
        assert isinstance(result, CanonicalIR)
        assert result.intent == "greeting"


class TestDialogueAgentFallback:
    def test_fallback_on_llm_failure(self):
        agent = DialogueAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("连接失败"))

        context = {"user_message": "你好", "emotion_pad": {"pleasure": 0.5, "arousal": -0.1, "dominance": 0.2}}
        result = asyncio.run(agent.run(context, bridge))

        assert isinstance(result, CanonicalIR)
        assert result.intent == "unknown"
        assert result.confidence == 0.0
        assert result.tone == "neutral"
        assert result.emotion_delta.pleasure == pytest.approx(0.5)
        assert result.emotion_delta.arousal == pytest.approx(-0.1)

    def test_fallback_preserves_user_message(self):
        agent = DialogueAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("超时"))

        context = {"user_message": "测试消息"}
        result = asyncio.run(agent.run(context, bridge))

        assert isinstance(result, CanonicalIR)
        assert "测试消息" in result.key_points
        assert result.action_params.get("raw_input") == "测试消息"


class TestDialogueAgentAnthropic:
    def test_anthropic_sdk_builds_correct_messages(self):
        agent = DialogueAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.ANTHROPIC
        bridge.chat = AsyncMock(return_value=LLMResponse(
            content=_MOCK_CANONICAL_IR_JSON,
            role="assistant",
            finish_reason="stop",
            usage={},
            tokens=50,
        ))

        context = {"user_message": "你好", "character_name": "角色"}
        result = asyncio.run(agent.run(context, bridge))

        assert isinstance(result, CanonicalIR)
        call_args = bridge.chat.call_args
        request = call_args[0][0]
        roles = [m["role"] for m in request.messages]
        assert "system" not in roles
