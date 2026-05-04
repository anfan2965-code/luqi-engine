"""
输出语言检测器 + 后处理分离器

功能：
  - 中英文比例统计和日志记录（不干预生成）
  - 对话/内心/动作三段式解析与分离
  - 各段独立质量清理（截断循环、修复格式）
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_ENGLISH_RATIO_THRESHOLD: float = 0.3
_MIN_DETECTION_LENGTH: int = 4

_INNER_PATTERN = re.compile(r'[\uff08]内心[\uff1a\uff1a](.*?)(?:[\uff09]|$)', re.DOTALL)
_ACTION_PATTERN = re.compile(r'^([\uff08](?!内心)[^\uff09]*?)[\uff09]', re.DOTALL)
_UNCLOSED_INNER = re.compile(r'[\uff08]内心[\uff1a\uff1a][^\uff09]*$')
_SINGLE_CHAR_FLOOD_RATIO = 0.40


class OutputCorrector:
    """
    输出语言检测器（仅统计，不修改内容）
    """

    def __init__(self, adapter=None, config=None, enabled: bool = True, english_threshold: float = _ENGLISH_RATIO_THRESHOLD) -> None:
        self._adapter = adapter
        self._config = config
        self._enabled = enabled
        self._english_threshold = english_threshold
        self._total_checks: int = 0
        self._english_count: int = 0
        self._chinese_count: int = 0
        self._avg_english_ratio: float = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def stats(self) -> dict:
        return {
            "total_checks": self._total_checks,
            "english_dominant": self._english_count,
            "chinese_dominant": self._chinese_count,
            "chinese_rate": f"{(self._chinese_count / max(self._total_checks, 1)) * 100:.1f}%",
            "avg_english_ratio": f"{self._avg_english_ratio:.3f}",
        }

    def needs_correction(self, text: str) -> bool:
        ratio = self._analyze(text)
        if ratio is None:
            return False
        return ratio > self._english_threshold

    async def correct(self, text: str, character_name: str = "") -> str:
        ratio = self._analyze(text)
        if ratio is not None and ratio > self._english_threshold:
            logger.info(
                "OutputDetector: 英文占比 %.0f%% (%d字符) | %s",
                ratio * 100, len(text), text[:80],
            )
        return text

    def _analyze(self, text: str) -> Optional[float]:
        if not self._enabled or not text or len(text.strip()) < _MIN_DETECTION_LENGTH:
            return None
        cn = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF)
        en = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        total = cn + en
        if total == 0:
            return None
        self._total_checks += 1
        ratio = en / total
        running_avg = (self._avg_english_ratio * (self._total_checks - 1) + ratio) / self._total_checks
        self._avg_english_ratio = running_avg
        if ratio > self._english_threshold:
            self._english_count += 1
        else:
            self._chinese_count += 1
        return ratio

    def parse_and_clean(self, raw_text: str) -> str:
        if not raw_text or len(raw_text.strip()) < 4:
            return raw_text
        action, dialogue, inner = self._parse_segments(raw_text)
        dialogue = self._clean_segment(dialogue, "对话")
        inner = self._clean_segment(inner, "内心")
        parts = []
        if action:
            parts.append(action)
        if dialogue:
            parts.append(dialogue)
        if inner and len(inner) >= 4:
            inner = inner if inner.endswith('）') else inner + '）'
            parts.append(inner)
        result = ''.join(parts).strip()
        if result != raw_text:
            logger.debug("后处理分离: %d→%d 字符 | 动作:%d 对话:%d 内心:%d",
                         len(raw_text), len(result),
                         len(action) if action else 0,
                         len(dialogue) if dialogue else 0,
                         len(inner) if inner else 0)
        return result

    def _parse_segments(self, text: str) -> Tuple[Optional[str], str, str]:
        action = None
        dialogue = text
        inner = ""
        action_match = _ACTION_PATTERN.match(text)
        if action_match and action_match.end() < len(text):
            action_candidate = text[:action_match.end()]
            if action_candidate.endswith('）'):
                action = action_candidate
                dialogue = text[action_match.end():]
        inner_matches = list(_INNER_PATTERN.finditer(dialogue))
        if inner_matches:
            last_inner = inner_matches[-1]
            inner_start = last_inner.start()
            inner_text = last_inner.group(1).strip()
            if inner_text and len(inner_text) >= 2:
                inner = inner_text
                dialogue = dialogue[:inner_start].strip()
        return action, dialogue, inner

    @staticmethod
    def _clean_segment(text: str, label: str) -> str:
        if not text or len(text.strip()) < 2:
            return text.strip()
        text = text.strip()
        for pattern in [
            (r'(.{2,8})[：:]\s*\1[：:]\s*\1', 3),
            (r'(.{2,10})[，,]\s*\1([，,]\s*\1){1,}', 3),
            (r'(.{3,15})\s+\1\s+\1', 3),
        ]:
            match = re.search(pattern[0], text)
            if match and match.start() > 4:
                return text[:match.start()].rstrip('，。、 ')
        if len(text) > 20:
            char_counts = Counter(text)
            top_char, top_count = char_counts.most_common(1)[0]
            if top_count > len(text) * _SINGLE_CHAR_FLOOD_RATIO:
                for i, c in enumerate(text):
                    if c == top_char and i > 6:
                        return text[:i].rstrip('，。、 ')
        return text

    def reset_stats(self) -> None:
        self._total_checks = 0
        self._english_count = 0
        self._chinese_count = 0
        self._avg_english_ratio = 0.0
