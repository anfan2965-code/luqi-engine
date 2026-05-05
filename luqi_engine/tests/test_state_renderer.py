"""状态渲染器测试"""

from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from luqi_engine.llm.state_renderer import StateRenderer
from luqi_engine.core.config import LLMConfig


class TestStateRenderer(unittest.TestCase):
    def setUp(self):
        self.renderer = StateRenderer()

    def test_basic_render(self):
        result = self.renderer.render_system_prompt(
            character_name="小雪",
            personality={"openness": 70.0, "conscientiousness": 50.0, "extraversion": 30.0, "agreeableness": 80.0, "neuroticism": 60.0},
            pad_emotion={"pleasure": -0.5, "arousal": 0.3, "dominance": -0.2},
            scene="教室",
            behavior_instruction="坦诚表达难过",
        )
        self.assertIn("[角色]小雪", result)
        self.assertIn("[性格]", result)
        self.assertIn("[情绪]", result)
        self.assertIn("[场景]教室", result)
        self.assertIn("[指令]坦诚表达难过", result)

    def test_personality_high_openness(self):
        result = self.renderer.render_system_prompt(
            character_name="测试",
            personality={"openness": 80.0, "conscientiousness": 50.0, "extraversion": 50.0, "agreeableness": 50.0, "neuroticism": 50.0},
        )
        self.assertIn("开放", result)

    def test_personality_low_extraversion(self):
        result = self.renderer.render_system_prompt(
            character_name="测试",
            personality={"openness": 50.0, "conscientiousness": 50.0, "extraversion": 20.0, "agreeableness": 50.0, "neuroticism": 50.0},
        )
        self.assertIn("内向", result)

    def test_pad_emotion_negative_pleasure(self):
        result = self.renderer.render_system_prompt(
            character_name="测试",
            pad_emotion={"pleasure": -0.7, "arousal": 0.5, "dominance": -0.3},
        )
        self.assertIn("不悦", result)
        self.assertIn("激动", result)
        self.assertIn("顺从", result)

    def test_seven_emotions(self):
        result = self.renderer.render_system_prompt(
            character_name="测试",
            seven_emotions={"喜": 0.1, "怒": 0.0, "忧": 0.8, "思": 0.3, "悲": 0.6, "恐": 0.0, "惊": 0.4},
        )
        self.assertIn("[七情]", result)
        self.assertIn("忧", result)
        self.assertIn("悲", result)

    def test_seven_emotions_filter_low(self):
        result = self.renderer.render_system_prompt(
            character_name="测试",
            seven_emotions={"喜": 0.1, "怒": 0.0, "忧": 0.0, "思": 0.0, "悲": 0.0, "恐": 0.0, "惊": 0.0},
        )
        self.assertNotIn("[七情]", result)

    def test_memories_render(self):
        memories = [
            {"who": "小明", "what": "一起去了公园散步聊天"},
            {"who": "小红", "what": "分享了生日蛋糕"},
        ]
        result = self.renderer.render_system_prompt(
            character_name="测试",
            memories=memories,
        )
        self.assertIn("[记忆]", result)
        self.assertIn("小明", result)

    def test_background_truncation(self):
        long_bg = "这是一个非常长的背景故事" * 20
        result = self.renderer.render_system_prompt(
            character_name="测试",
            background=long_bg,
        )
        self.assertIn("[背景]", result)
        self.assertTrue(len(result) < len(long_bg) + 100)

    def test_output_requirements(self):
        result = self.renderer.render_system_prompt(
            character_name="测试",
            output_requirements="第一人称回复，保持角色风格",
        )
        self.assertIn("[要求]第一人称回复，保持角色风格", result)

    def test_empty_character_name(self):
        result = self.renderer.render_system_prompt(character_name="")
        self.assertNotIn("[角色]", result)

    def test_token_estimate_within_limit(self):
        result = self.renderer.render_system_prompt(
            character_name="小雪",
            personality={"openness": 70.0, "conscientiousness": 50.0, "extraversion": 30.0, "agreeableness": 80.0, "neuroticism": 60.0},
            pad_emotion={"pleasure": -0.5, "arousal": 0.3, "dominance": -0.2},
            seven_emotions={"喜": 0.5, "怒": 0.0, "忧": 0.8, "思": 0.0, "悲": 0.6, "恐": 0.0, "惊": 0.0},
            scene="教室",
            behavior_instruction="坦诚表达难过",
            memories=[{"who": "小明", "what": "一起去了公园"}],
            background="转学生",
            output_requirements="第一人称回复",
        )
        estimated_tokens = len(result) * 0.6
        self.assertLessEqual(estimated_tokens, 300, "System prompt should be within 300 token estimate")


class TestStateRendererWithConfig(unittest.TestCase):
    def test_default_token_budget_without_config(self):
        renderer = StateRenderer()
        self.assertEqual(renderer._max_system_token_estimate, 300)

    def test_custom_token_budget_from_config(self):
        config = LLMConfig(system_token_budget=500)
        renderer = StateRenderer(config=config)
        self.assertEqual(renderer._max_system_token_estimate, 500)

    def test_small_token_budget_triggers_compression(self):
        config = LLMConfig(system_token_budget=50)
        renderer = StateRenderer(config=config)
        result = renderer.render_system_prompt(
            character_name="小雪",
            personality={"openness": 70.0, "conscientiousness": 50.0, "extraversion": 30.0, "agreeableness": 80.0, "neuroticism": 60.0},
            pad_emotion={"pleasure": -0.5, "arousal": 0.3, "dominance": -0.2},
            scene="教室",
            behavior_instruction="坦诚表达难过",
            memories=[{"who": "小明", "what": "一起去了公园"}],
            background="转学生",
            output_requirements="第一人称回复",
        )
        estimated_tokens = len(result) * 0.6
        self.assertLessEqual(estimated_tokens, 50)


if __name__ == "__main__":
    unittest.main()
