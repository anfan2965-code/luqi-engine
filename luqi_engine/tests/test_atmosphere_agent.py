import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from luqi_engine.agents.atmosphere_agent import AtmosphereAgent
from luqi_engine.core.types import AtmosphereOutput, LLMResponse, SDKType


_MOCK_ATMOSPHERE_OUTPUT_JSON = json.dumps({
    "mode": "full",
    "environment": {
        "visual": "暮色中的古堡轮廓",
        "auditory": "远处钟声回荡",
        "olfactory": "空气中弥漫着潮湿的泥土气息",
        "thermal": "微凉",
        "spatial": "开阔的庭院",
    },
    "narration": {
        "transition": "夜幕降临，古堡笼罩在一片阴影之中",
        "inner_voice": "这里似乎隐藏着什么秘密",
        "omniscient_note": "命运的齿轮开始转动",
    },
    "stage_directions": [
        {"character": "角色A", "action": "缓缓走向大门", "detail": "神情凝重"},
        {"character": "角色B", "action": "驻足观望", "detail": "目光闪烁"},
    ],
    "mood_declaration": {
        "dominant_emotion": "fear",
        "intensity": 0.7,
        "color_palette": ["深紫", "暗灰"],
        "pacing_hint": "slow",
    },
    "suggested_position": "prefix",
    "length_budget": "medium",
    "priority": 0.8,
})


def _make_mock_bridge(response_content: str) -> MagicMock:
    bridge = MagicMock()
    bridge.get_sdk_type.return_value = SDKType.OPENAI
    bridge.chat = AsyncMock(return_value=LLMResponse(
        content=response_content,
        role="assistant",
        finish_reason="stop",
        usage={},
        tokens=120,
    ))
    return bridge


class TestAtmosphereAgentNameAndType:
    def test_get_name(self):
        agent = AtmosphereAgent()
        assert agent.get_name() == "atmosphere"

    def test_get_output_type(self):
        agent = AtmosphereAgent()
        assert agent.get_output_type() == "AtmosphereOutput"


class TestAtmosphereAgentRunLight:
    def test_light_mode_returns_output(self):
        agent = AtmosphereAgent()
        light_json = json.dumps({
            "mode": "light",
            "environment": {
                "visual": "明亮的房间",
                "auditory": "鸟鸣",
                "olfactory": "花香",
                "thermal": "温暖",
                "spatial": "紧凑",
            },
            "narration": {"transition": "阳光洒入窗内"},
            "stage_directions": [],
            "mood_declaration": {
                "dominant_emotion": "joy",
                "intensity": 0.6,
                "color_palette": [],
                "pacing_hint": "normal",
            },
            "suggested_position": "prefix",
            "length_budget": "short",
            "priority": 0.5,
        })
        bridge = _make_mock_bridge(light_json)
        context = {"scene_name": "花园", "dominant_emotion": "joy"}

        result = asyncio.run(agent.run(context, bridge, mode="light"))
        assert isinstance(result, AtmosphereOutput)
        assert result.mode == "light"
        assert result.environment.visual == "明亮的房间"
        assert result.mood_declaration.dominant_emotion == "joy"


class TestAtmosphereAgentRunFull:
    def test_full_mode_returns_complete_output(self):
        agent = AtmosphereAgent()
        bridge = _make_mock_bridge(_MOCK_ATMOSPHERE_OUTPUT_JSON)
        context = {"scene_name": "古堡", "dominant_emotion": "fear"}

        result = asyncio.run(agent.run(context, bridge, mode="full"))
        assert isinstance(result, AtmosphereOutput)
        assert result.mode == "full"
        assert result.environment.visual == "暮色中的古堡轮廓"
        assert result.narration.transition is not None
        assert result.narration.inner_voice is not None
        assert len(result.stage_directions) == 2
        assert result.stage_directions[0].character == "角色A"
        assert result.mood_declaration.intensity == pytest.approx(0.7)
        assert result.priority == pytest.approx(0.8)


class TestAtmosphereAgentTemplateFallback:
    def test_fallback_light_mode_uses_template(self):
        agent = AtmosphereAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("不可用"))

        context = {
            "scene_name": "森林",
            "dominant_emotion": "fear",
            "emotion_intensity": 0.8,
            "characters_present": ["角色A", "角色B"],
        }
        result = asyncio.run(agent.run(context, bridge, mode="light"))

        assert isinstance(result, AtmosphereOutput)
        assert result.mode == "light"
        assert "森林" in result.narration.transition
        assert "不安" in result.narration.transition
        assert result.environment.visual != ""
        assert len(result.stage_directions) == 2
        assert result.mood_declaration.dominant_emotion == "fear"

    def test_fallback_full_mode_degrades_to_light(self):
        agent = AtmosphereAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("不可用"))

        context = {
            "scene_name": "古堡",
            "dominant_emotion": "sorrow",
        }
        result = asyncio.run(agent.run(context, bridge, mode="full"))

        assert isinstance(result, AtmosphereOutput)
        assert result.mode == "light"

    def test_fallback_uses_emotion_word_map(self):
        agent = AtmosphereAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("不可用"))

        context = {
            "scene_name": "湖畔",
            "dominant_emotion": "joy",
        }
        result = asyncio.run(agent.run(context, bridge, mode="light"))

        assert "欢快" in result.narration.transition

    def test_fallback_unknown_emotion_defaults_neutral(self):
        agent = AtmosphereAgent()
        bridge = MagicMock()
        bridge.get_sdk_type.return_value = SDKType.OPENAI
        bridge.chat = AsyncMock(side_effect=RuntimeError("不可用"))

        context = {
            "scene_name": "荒野",
            "dominant_emotion": "unknown_emotion",
        }
        result = asyncio.run(agent.run(context, bridge, mode="light"))

        assert "平和" in result.narration.transition


class TestAtmosphereAgentInvalidMode:
    def test_invalid_mode_defaults_to_light(self):
        agent = AtmosphereAgent()
        bridge = _make_mock_bridge(_MOCK_ATMOSPHERE_OUTPUT_JSON)
        context = {"scene_name": "测试"}

        result = asyncio.run(agent.run(context, bridge, mode="invalid"))
        assert isinstance(result, AtmosphereOutput)
