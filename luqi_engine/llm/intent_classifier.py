from __future__ import annotations

from enum import Enum
from typing import List, Optional

from luqi_engine.core.config import IntentClassifierConfig
from luqi_engine.core.logging_config import get_logger
from luqi_engine.llm.intent_config import IntentKeywordConfig

_logger = get_logger(__name__)


class IntentLevel(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class IntentClassifier:
    def __init__(self, offline_mode: bool = False, keyword_config: Optional[IntentKeywordConfig] = None, intent_config: Optional[IntentClassifierConfig] = None) -> None:
        self._offline_mode = offline_mode
        self._config = keyword_config or IntentKeywordConfig()
        self._intent_config = intent_config or IntentClassifierConfig()

    def classify(self, user_input: str, num_characters: int = 1) -> IntentLevel:
        if not user_input:
            return IntentLevel.SIMPLE

        input_len = len(user_input)
        has_emotion = self._contains_emotion_keywords(user_input)
        has_narrative = self._contains_narrative_keywords(user_input)
        has_multi_char = num_characters > 1 or self._contains_multi_character_indicators(user_input)

        if has_multi_char or has_narrative or input_len > self._intent_config.moderate_max_length:
            level = IntentLevel.COMPLEX
        elif input_len > self._intent_config.simple_max_length or has_emotion:
            level = IntentLevel.MODERATE
        else:
            level = IntentLevel.SIMPLE

        if self._offline_mode and level == IntentLevel.COMPLEX:
            level = IntentLevel.MODERATE

        return level

    def set_offline_mode(self, offline: bool) -> None:
        self._offline_mode = offline

    @property
    def is_offline(self) -> bool:
        return self._offline_mode

    @property
    def config(self) -> IntentKeywordConfig:
        return self._config

    @property
    def intent_config(self) -> IntentClassifierConfig:
        return self._intent_config

    def _contains_emotion_keywords(self, text: str) -> bool:
        text_lower = text.lower()
        for kw in self._config.emotion_keywords:
            if kw in text_lower:
                return True
        return False

    def _contains_narrative_keywords(self, text: str) -> bool:
        text_lower = text.lower()
        for kw in self._config.narrative_keywords:
            if kw in text_lower:
                return True
        return False

    def _contains_multi_character_indicators(self, text: str) -> bool:
        text_lower = text.lower()
        for kw in self._config.multi_character_indicators:
            if kw in text_lower:
                return True
        return False
