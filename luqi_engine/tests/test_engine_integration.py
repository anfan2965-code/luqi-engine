"""引擎集成测试"""

from __future__ import annotations

import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from luqi_engine.core.config import EngineConfig, LocalLLMConfig
from luqi_engine.llm.intent_classifier import IntentLevel, IntentClassifier
from luqi_engine.llm.state_renderer import StateRenderer


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestEngineConfig(unittest.TestCase):
    def test_default_local_llm_config(self):
        config = EngineConfig()
        self.assertFalse(config.local_llm.local_llm_enabled)
        self.assertEqual(config.local_llm.local_llm_model_path, "")
        self.assertEqual(config.local_llm.local_llm_n_gpu_layers, 0)
        self.assertEqual(config.local_llm.local_llm_n_ctx, 2048)
        self.assertEqual(config.local_llm.local_llm_max_tokens, 512)

    def test_from_dict_with_local_llm(self):
        data = {
            "local_llm": {
                "local_llm_enabled": True,
                "local_llm_model_path": "/path/to/model.gguf",
                "local_llm_n_gpu_layers": 0,
                "local_llm_n_ctx": 4096,
                "local_llm_max_tokens": 1024,
                "local_llm_temperature": 0.8,
                "local_llm_top_p": 0.95,
            }
        }
        config = EngineConfig.from_dict(data)
        self.assertTrue(config.local_llm.local_llm_enabled)
        self.assertEqual(config.local_llm.local_llm_model_path, "/path/to/model.gguf")
        self.assertEqual(config.local_llm.local_llm_n_ctx, 4096)
        self.assertEqual(config.local_llm.local_llm_max_tokens, 1024)
        self.assertAlmostEqual(config.local_llm.local_llm_temperature, 0.8)
        self.assertAlmostEqual(config.local_llm.local_llm_top_p, 0.95)

    def test_from_dict_without_local_llm(self):
        data = {}
        config = EngineConfig.from_dict(data)
        self.assertFalse(config.local_llm.local_llm_enabled)


class TestEngineModules(unittest.TestCase):
    def test_intent_classifier_routing_simple(self):
        classifier = IntentClassifier()
        level = classifier.classify("你好")
        self.assertEqual(level, IntentLevel.SIMPLE)

    def test_intent_classifier_routing_moderate(self):
        classifier = IntentClassifier()
        level = classifier.classify("我很难过，你能安慰我吗")
        self.assertEqual(level, IntentLevel.MODERATE)

    def test_intent_classifier_routing_complex(self):
        classifier = IntentClassifier()
        level = classifier.classify("给我讲一个关于这个世界的完整故事背景和设定体系")
        self.assertEqual(level, IntentLevel.COMPLEX)

    def test_state_renderer_basic(self):
        renderer = StateRenderer()
        mock_character = MagicMock()
        mock_character.name = "小雪"
        mock_character.personality.get_score.side_effect = lambda dim: {
            "openness": 70, "conscientiousness": 50, "extraversion": 30,
            "agreeableness": 80, "neuroticism": 60,
        }[dim]
        mock_character.emotion.pleasure = -0.5
        mock_character.emotion.arousal = 0.3
        mock_character.emotion.dominance = -0.2
        mock_character.background = "转学生"

        from luqi_engine.engine import _LOCAL_LLM_OUTPUT_REQUIREMENTS
        result = renderer.render_system_prompt(
            character_name=mock_character.name,
            personality={
                "openness": mock_character.personality.get_score("openness"),
                "conscientiousness": mock_character.personality.get_score("conscientiousness"),
                "extraversion": mock_character.personality.get_score("extraversion"),
                "agreeableness": mock_character.personality.get_score("agreeableness"),
                "neuroticism": mock_character.personality.get_score("neuroticism"),
            },
            pad_emotion={
                "pleasure": mock_character.emotion.pleasure,
                "arousal": mock_character.emotion.arousal,
                "dominance": mock_character.emotion.dominance,
            },
            seven_emotions=None,
            scene="",
            behavior_instruction="",
            memories=[],
            background=mock_character.background,
            output_requirements=_LOCAL_LLM_OUTPUT_REQUIREMENTS,
        )
        self.assertIn("[角色]小雪", result)
        self.assertIn("[性格]", result)
        self.assertIn("[情绪]", result)
        self.assertIn("[要求]", result)

    def test_engine_init_local_llm_not_initialized_before_initialize(self):
        from luqi_engine.engine import LuqiEngine
        config = EngineConfig()
        config.local_llm.local_llm_enabled = False
        engine = LuqiEngine(config=config)
        self.assertIsNone(engine.local_llm_adapter)
        self.assertIsNone(engine.state_renderer)
        self.assertIsNone(engine.intent_classifier)

    def test_engine_init_local_llm_enabled_but_not_loaded(self):
        from luqi_engine.engine import LuqiEngine
        config = EngineConfig()
        config.local_llm.local_llm_enabled = True
        config.local_llm.local_llm_model_path = "/fake/model.gguf"
        engine = LuqiEngine(config=config)
        self.assertIsNone(engine.local_llm_adapter)


if __name__ == "__main__":
    unittest.main()
