"""意图分类器测试"""

from __future__ import annotations

import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from luqi_engine.llm.intent_classifier import IntentClassifier, IntentLevel
from luqi_engine.core.config import IntentClassifierConfig


class TestIntentClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = IntentClassifier()

    def test_simple_short_input(self):
        result = self.classifier.classify("你好")
        self.assertEqual(result, IntentLevel.SIMPLE)

    def test_simple_very_short(self):
        result = self.classifier.classify("嗯")
        self.assertEqual(result, IntentLevel.SIMPLE)

    def test_moderate_medium_input(self):
        result = self.classifier.classify("今天天气怎么样啊，我想出去走走散散心呢，好吗")
        self.assertEqual(result, IntentLevel.MODERATE)

    def test_moderate_emotion_keyword(self):
        result = self.classifier.classify("我很难过")
        self.assertEqual(result, IntentLevel.MODERATE)

    def test_moderate_emotion_keyword_love(self):
        result = self.classifier.classify("我喜欢你")
        self.assertEqual(result, IntentLevel.MODERATE)

    def test_complex_long_input(self):
        long_input = "今天我在学校遇到了一件很有趣的事情" + "，然后我们聊了很多" * 10
        result = self.classifier.classify(long_input)
        self.assertEqual(result, IntentLevel.COMPLEX)

    def test_complex_narrative_keyword(self):
        result = self.classifier.classify("给我讲一个故事吧")
        self.assertEqual(result, IntentLevel.COMPLEX)

    def test_complex_multi_character(self):
        result = self.classifier.classify("他们都在做什么", num_characters=2)
        self.assertEqual(result, IntentLevel.COMPLEX)

    def test_offline_degradation(self):
        classifier = IntentClassifier(offline_mode=True)
        result = classifier.classify("给我讲一个很长的故事关于这个世界的背景设定")
        self.assertEqual(result, IntentLevel.MODERATE)

    def test_offline_mode_property(self):
        classifier = IntentClassifier(offline_mode=True)
        self.assertTrue(classifier.is_offline)
        classifier.set_offline_mode(False)
        self.assertFalse(classifier.is_offline)

    def test_empty_input(self):
        result = self.classifier.classify("")
        self.assertEqual(result, IntentLevel.SIMPLE)

    def test_moderate_thanks_keyword(self):
        result = self.classifier.classify("谢谢你帮我")
        self.assertEqual(result, IntentLevel.MODERATE)

    def test_complex_worldview_keyword(self):
        result = self.classifier.classify("这个世界的世界观是什么样的")
        self.assertEqual(result, IntentLevel.COMPLEX)

    def test_default_config_values(self):
        classifier = IntentClassifier()
        self.assertEqual(classifier.intent_config.simple_max_length, 20)
        self.assertEqual(classifier.intent_config.moderate_max_length, 100)

    def test_custom_config_values(self):
        custom_config = IntentClassifierConfig(simple_max_length=10, moderate_max_length=50)
        classifier = IntentClassifier(intent_config=custom_config)
        self.assertEqual(classifier.intent_config.simple_max_length, 10)
        self.assertEqual(classifier.intent_config.moderate_max_length, 50)

    def test_classify_uses_custom_simple_threshold(self):
        custom_config = IntentClassifierConfig(simple_max_length=5)
        classifier = IntentClassifier(intent_config=custom_config)
        result = classifier.classify("你好世界今天天气真好")
        self.assertEqual(result, IntentLevel.MODERATE)

    def test_classify_uses_custom_moderate_threshold(self):
        custom_config = IntentClassifierConfig(moderate_max_length=30)
        classifier = IntentClassifier(intent_config=custom_config)
        medium_input = "这是一个中等长度的输入测试用于验证配置化功能是否正常工作" * 2
        result = classifier.classify(medium_input)
        self.assertEqual(result, IntentLevel.COMPLEX)


if __name__ == "__main__":
    unittest.main()
