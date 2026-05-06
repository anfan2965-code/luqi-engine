from __future__ import annotations

import unicodedata
from typing import ClassVar, FrozenSet, List

from luqi_engine.core.config import LocalModelConfig
from luqi_engine.core.logging_config import get_logger

_JIEBA_AVAILABLE: bool = False
try:
    import jieba

    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False

_CJK_PUNCTUATION_RANGES: tuple = (
    (0x3000, 0x303F),
    (0xFF00, 0xFFEF),
)
_LATIN_PUNCTUATION_CATEGORIES: FrozenSet[str] = frozenset({
    "Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po",
})
_SYMBOL_CATEGORIES: FrozenSet[str] = frozenset({
    "Sc", "Sk", "Sm", "So",
})
_SEPARATOR_CATEGORIES: FrozenSet[str] = frozenset({
    "Zs", "Zl", "Zp",
})

_logger = get_logger(__name__)


def _is_punctuation_or_symbol(token: str) -> bool:
    if len(token) != 1:
        return False
    code = ord(token)
    for start, end in _CJK_PUNCTUATION_RANGES:
        if start <= code <= end:
            return True
    if 0x2000 <= code <= 0x206F:
        return True
    if 0x0080 <= code <= 0x00BF:
        return True
    cat = unicodedata.category(token)
    if cat in _LATIN_PUNCTUATION_CATEGORIES:
        return True
    if cat in _SYMBOL_CATEGORIES:
        return True
    if cat in _SEPARATOR_CATEGORIES:
        return True
    return False


class CustomTokenizer:
    _MIN_TOKEN_LENGTH: ClassVar[int] = 1
    _TOKEN_SEPARATOR: ClassVar[str] = " "
    _EMPTY_STRING: ClassVar[str] = ""

    def __init__(self, config: LocalModelConfig | None = None) -> None:
        self._config = config or LocalModelConfig()
        self._use_jieba = _JIEBA_AVAILABLE

    async def tokenize(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []

        if self._use_jieba:
            tokens = self._tokenize_with_jieba(text)
        else:
            tokens = self._tokenize_char_level(text)

        tokens = [t for t in tokens if not _is_punctuation_or_symbol(t)]

        if self._config.enable_debug_output:
            _logger.debug(
                "input_length=%d, token_count=%d, use_jieba=%s",
                len(text), len(tokens), self._use_jieba,
            )

        return tokens

    def _tokenize_with_jieba(self, text: str) -> List[str]:
        raw_tokens = jieba.lcut(text)
        return [t for t in raw_tokens if len(t) >= self._MIN_TOKEN_LENGTH]

    def _tokenize_char_level(self, text: str) -> List[str]:
        tokens: List[str] = []
        current_chunk: List[str] = []
        for char in text:
            if self._is_cjk_char(char):
                if current_chunk:
                    chunk_str = self._EMPTY_STRING.join(current_chunk).strip()
                    if chunk_str:
                        tokens.append(chunk_str)
                    current_chunk = []
                tokens.append(char)
            elif char.isspace():
                if current_chunk:
                    chunk_str = self._EMPTY_STRING.join(current_chunk).strip()
                    if chunk_str:
                        tokens.append(chunk_str)
                    current_chunk = []
            else:
                current_chunk.append(char)
        if current_chunk:
            chunk_str = self._EMPTY_STRING.join(current_chunk).strip()
            if chunk_str:
                tokens.append(chunk_str)
        return [t for t in tokens if len(t) >= self._MIN_TOKEN_LENGTH]

    @staticmethod
    def _is_cjk_char(char: str) -> bool:
        code = ord(char)
        return (
            (0x4E00 <= code <= 0x9FFF)
            or (0x3400 <= code <= 0x4DBF)
            or (0x20000 <= code <= 0x2A6DF)
            or (0x2A700 <= code <= 0x2B73F)
            or (0x2B740 <= code <= 0x2B81F)
            or (0x2B820 <= code <= 0x2CEAF)
            or (0xF900 <= code <= 0xFAFF)
            or (0x2F800 <= code <= 0x2FA1F)
        )

    def validate_output(self, tokens: List[str]) -> bool:
        if not tokens:
            return False
        return any(len(t) >= self._MIN_TOKEN_LENGTH for t in tokens)
