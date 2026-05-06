import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from luqi_engine.agents.novelist_agent import NovelistAgent
from luqi_engine.core.types import LLMResponse, NarrativeDelta, SDKType


_MOCK_NARRATIVE_DELTA_JSON = json.dumps({
    "version": 3,
    "new_facts": [
        {
            "id": "fact_001",
            "timestamp": "2025-01-01T12:00:00",
            "source": "dialogue",
            "content": "角色A与角色B发生了争执",
            "participants": ["角色A", "角色B"],
            "emotional_valence": -0.5,
            "tags": ["冲突", "关系"],
        }
    ],
    "chapter_update": {
        "current_beat_progress": 0.6,
        "new_beat_suggested": {"name": "对峙升级", "description": "争执进一步恶化"},
        "character_arcs_update": {"角色A": {"tension": 0.8}},
        "constraints_added": ["争执不可轻易化解"],
        "constraints_removed": [],
    },
    "next_prediction": {
        "likely_next_scenes": [
            {"scene_name": "和解尝试", "probability": 0.3},
            {"scene_name": "关系破裂", "probability": 0.7},
        ],
        "narrative_tension": 0.8,
        "suggested_pace": "fast",
    },
    "open_questions_added": ["争执的真正原因是什么？"],
    "open_questions_resolved": [],
    "narrative_note": "冲突升级中",
})


def _make_mock_bridge(response_content: str) -> MagicMock:
    bridge = MagicMock()
    bridge.get_sdk_type.return_value = SDKType.OPENAI
    bridge.chat = AsyncMock(return_value=LLMResponse(
        content=response_content,
        role="assistant",
        finish_reason="stop",
        usage={},
        tokens=100,
    ))
    return bridge


class TestNovelistAgentNameAndType:
    def test_get_name(self):
        agent = NovelistAgent()
        assert agent.get_name() == "novelist"

    def test_get_output_type(self):
        agent = NovelistAgent()
        assert agent.get_output_type() == "NarrativeDelta"


class TestNovelistAgentRunIncremental:
    def test_run_incremental_returns_delta(self):
        agent = NovelistAgent()
        bridge = _make_mock_bridge(_MOCK_NARRATIVE_DELTA_JSON)
        context = {"narrative_context": "角色A与B争执中"}

        result = asyncio.run(agent.run(context, bridge, mode="incremental"))
        assert isinstance(result, NarrativeDelta)
        assert result.version == 3
        assert len(result.new_facts) == 1
        assert result.new_facts[0].content == "角色A与角色B发生了争执"
        assert result.chapter_update is not None
        assert result.chapter_update.current_beat_progress == pytest.approx(0.6)

    def test_incremental_filters_prediction(self):
        agent = NovelistAgent()
        bridge = _make_mock_bridge(_MOCK_NARRATIVE_DELTA_JSON)
        context = {"narrative_context": "测试"}

        result = asyncio.run(agent.run(context, bridge, mode="incremental"))
        assert result.next_prediction is None


class TestNovelistAgentRunFullUpdate:
    def test_full_update_keeps_all_fields(self):
        agent = NovelistAgent()
        bridge = _make_mock_bridge(_MOCK_NARRATIVE_DELTA_JSON)
        context = {"narrative_context": "测试"}

        result = asyncio.run(agent.run(context, bridge, mode="full_update"))
        assert isinstance(result, NarrativeDelta)
        assert result.new_facts is not None
        assert result.chapter_update is not None
        assert result.next_prediction is not None
        assert result.next_prediction.narrative_tension == pytest.approx(0.8)
        assert result.next_prediction.suggested_pace == "fast"


class TestNovelistAgentRunPredictionOnly:
    def test_prediction_only_keeps_only_prediction(self):
        agent = NovelistAgent()
        bridge = _make_mock_bridge(_MOCK_NARRATIVE_DELTA_JSON)
        context = {"narrative_context": "测试"}

        result = asyncio.run(agent.run(context, bridge, mode="prediction_only"))
        assert isinstance(result, NarrativeDelta)
        assert result.next_prediction is not None
        assert not result.new_facts
        assert result.chapter_update is None


class TestNovelistAgentFallback:
    def test_fallback_on_llm_failure(self):
        agent = NovelistAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("超时"))

        context = {"narrative_context": "测试叙事"}
        result = asyncio.run(agent.run(context, bridge, mode="incremental"))

        assert isinstance(result, NarrativeDelta)
        assert "降级模式" in result.narrative_note
        assert len(result.new_facts) >= 1

    def test_fallback_prediction_only_mode(self):
        agent = NovelistAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("超时"))

        context = {"narrative_context": "测试"}
        result = asyncio.run(agent.run(context, bridge, mode="prediction_only"))

        assert isinstance(result, NarrativeDelta)
        assert result.next_prediction is not None
        assert result.next_prediction.suggested_pace == "normal"


class TestNovelistAgentInvalidMode:
    def test_invalid_mode_defaults_to_incremental(self):
        agent = NovelistAgent()
        bridge = _make_mock_bridge(_MOCK_NARRATIVE_DELTA_JSON)
        context = {"narrative_context": "测试"}

        result = asyncio.run(agent.run(context, bridge, mode="invalid_mode"))
        assert isinstance(result, NarrativeDelta)
