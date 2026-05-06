import pytest
from luqi_engine.llm.intent_config import IntentKeywordConfig
from luqi_engine.llm.intent_classifier import IntentClassifier, IntentLevel


class TestIntentKeywordConfigDefaults:
    def test_default_emotion_keywords_not_empty(self):
        c = IntentKeywordConfig()
        assert len(c.emotion_keywords) > 0

    def test_default_narrative_keywords_not_empty(self):
        c = IntentKeywordConfig()
        assert len(c.narrative_keywords) > 0

    def test_default_multi_character_indicators_not_empty(self):
        c = IntentKeywordConfig()
        assert len(c.multi_character_indicators) > 0

    def test_custom_emotion_keywords(self):
        c = IntentKeywordConfig(emotion_keywords=["happy", "sad"])
        assert c.emotion_keywords == ["happy", "sad"]

    def test_custom_narrative_keywords(self):
        c = IntentKeywordConfig(narrative_keywords=["story"])
        assert c.narrative_keywords == ["story"]

    def test_custom_multi_character_indicators(self):
        c = IntentKeywordConfig(multi_character_indicators=["they"])
        assert c.multi_character_indicators == ["they"]


class TestIntentKeywordConfigDictRoundtrip:
    def test_to_dict_and_from_dict(self):
        original = IntentKeywordConfig(
            emotion_keywords=["joy"],
            narrative_keywords=["plot"],
            multi_character_indicators=["team"],
        )
        d = original.to_dict()
        restored = IntentKeywordConfig.from_dict(d)
        assert restored.emotion_keywords == ["joy"]
        assert restored.narrative_keywords == ["plot"]
        assert restored.multi_character_indicators == ["team"]

    def test_from_dict_empty(self):
        c = IntentKeywordConfig.from_dict({})
        assert len(c.emotion_keywords) > 0


class TestIntentKeywordConfigYaml:
    def test_from_yaml_missing_file_returns_defaults(self):
        c = IntentKeywordConfig.from_yaml("/nonexistent/path/config.yaml")
        assert len(c.emotion_keywords) > 0

    def test_from_yaml_actual_file(self):
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        yaml_path = os.path.join(here, "..", "llm", "intent_config.yaml")
        if os.path.exists(yaml_path):
            c = IntentKeywordConfig.from_yaml(yaml_path)
            assert len(c.emotion_keywords) > 0
            assert "难过" in c.emotion_keywords or len(c.emotion_keywords) > 0


class TestIntentClassifierWithDefaultConfig:
    def test_simple_input(self):
        ic = IntentClassifier()
        assert ic.classify("你好") == IntentLevel.SIMPLE

    def test_empty_input(self):
        ic = IntentClassifier()
        assert ic.classify("") == IntentLevel.SIMPLE

    def test_emotion_keyword_triggers_moderate(self):
        ic = IntentClassifier()
        assert ic.classify("我今天很开心") == IntentLevel.MODERATE

    def test_long_text_triggers_complex(self):
        ic = IntentClassifier()
        long_text = "内容" * 200
        assert ic.classify(long_text) == IntentLevel.COMPLEX

    def test_narrative_keyword_triggers_complex(self):
        ic = IntentClassifier()
        assert ic.classify("这个故事的发展很有趣") == IntentLevel.COMPLEX

    def test_multi_character_indicator_triggers_complex(self):
        ic = IntentClassifier()
        assert ic.classify("他们一起去玩吧") == IntentLevel.COMPLEX

    def test_num_characters_forces_complex(self):
        ic = IntentClassifier()
        assert ic.classify("简单对话", num_characters=3) == IntentLevel.COMPLEX

    def test_offline_mode_downgrades_complex_to_moderate(self):
        ic = IntentClassifier(offline_mode=True)
        long_text = "内容" * 50
        assert ic.classify(long_text) == IntentLevel.MODERATE

    def test_config_property(self):
        ic = IntentClassifier()
        assert isinstance(ic.config, IntentKeywordConfig)


class TestIntentClassifierWithCustomConfig:
    def test_custom_emotion_keyword(self):
        custom = IntentKeywordConfig(emotion_keywords=["超级开心"])
        ic = IntentClassifier(keyword_config=custom)
        assert ic.classify("我超级开心") == IntentLevel.MODERATE

    def test_custom_keyword_not_in_defaults(self):
        custom = IntentKeywordConfig(emotion_keywords=["unique_emotion"])
        ic = IntentClassifier(keyword_config=custom)
        assert ic.classify("我很开心") == IntentLevel.SIMPLE

    def test_custom_narrative_keyword(self):
        custom = IntentKeywordConfig(narrative_keywords=["传说中"])
        ic = IntentClassifier(keyword_config=custom)
        assert ic.classify("传说中有条龙") == IntentLevel.COMPLEX

    def test_set_offline_mode(self):
        ic = IntentClassifier()
        ic.set_offline_mode(True)
        assert ic.is_offline is True
