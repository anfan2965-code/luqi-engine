from __future__ import annotations

import re
from typing import ClassVar

from luqi_engine.core.config import LocalModelConfig
from luqi_engine.core.logging_config import get_logger

_logger = get_logger(__name__)


class TextPreprocessor:
    _CONTROL_CHAR_PATTERN: ClassVar[str] = r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
    _HTML_TAG_PATTERN: ClassVar[str] = r"<[^>]+>"
    _SPECIAL_CHAR_PATTERN: ClassVar[str] = (
        r"[^\w\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"
        r"\u2000-\u206f"
        r"，。！？；：""''（）、—…《》【】"
        r"\.,!?;:'\"()\-\u2014\u2013\u2026]"
    )
    _WHITESPACE_PATTERN: ClassVar[str] = r"\s+"
    _REPLACEMENT_WHITESPACE: ClassVar[str] = " "
    _MIN_OUTPUT_LENGTH: ClassVar[int] = 1
    _EMPTY_STRING: ClassVar[str] = ""

    def __init__(self, config: LocalModelConfig | None = None) -> None:
        self._config = config or LocalModelConfig()
        self._control_char_re = re.compile(self._CONTROL_CHAR_PATTERN)
        self._html_tag_re = re.compile(self._HTML_TAG_PATTERN)
        self._special_char_re = re.compile(self._SPECIAL_CHAR_PATTERN)
        self._whitespace_re = re.compile(self._WHITESPACE_PATTERN)

    async def process(self, text: str) -> str:
        if not text or not text.strip():
            return self._EMPTY_STRING

        cleaned = self._control_char_re.sub(self._REPLACEMENT_WHITESPACE, text)
        cleaned = self._html_tag_re.sub(self._EMPTY_STRING, cleaned)
        cleaned = self._special_char_re.sub(self._REPLACEMENT_WHITESPACE, cleaned)
        cleaned = self._whitespace_re.sub(self._REPLACEMENT_WHITESPACE, cleaned)
        cleaned = cleaned.strip()

        if self._config.enable_debug_output:
            _logger.debug("input_length=%d, output_length=%d", len(text), len(cleaned))

        return cleaned

    def validate_output(self, output: str) -> bool:
        return len(output) >= self._MIN_OUTPUT_LENGTH
