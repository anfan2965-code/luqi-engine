"""
DeepSeek-V4-pro特别调优器
利用长上下文能力、思维链格式、上下文压缩策略、响应格式约束
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from luqi_engine.core.config import LLMConfig

_COT_THINK_OPEN: str = "<think>"
_COT_THINK_CLOSE: str = "</think>"
_COT_RESPONSE_OPEN: str = "<response>"
_COT_RESPONSE_CLOSE: str = "</response>"
_FORMAT_ACTION_OPEN: str = "<action>"
_FORMAT_ACTION_CLOSE: str = "</action>"
_FORMAT_DIALOGUE_OPEN: str = "<dialogue>"
_FORMAT_DIALOGUE_CLOSE: str = "</dialogue>"
_FORMAT_EMOTION_OPEN: str = "<emotion>"
_FORMAT_EMOTION_CLOSE: str = "</emotion>"

_TOKEN_BUDGET_SYSTEM_WEIGHT: float = 0.15
_TOKEN_BUDGET_MEMORY_WEIGHT: float = 0.35
_TOKEN_BUDGET_WORLDVIEW_WEIGHT: float = 0.20
_TOKEN_BUDGET_DIALOGUE_WEIGHT: float = 0.30

_COMPRESSION_RECENT_TURNS: int = 4
_COMPRESSION_MID_TURNS: int = 10
_COMPRESSION_RECENT_WEIGHT: float = 1.0
_COMPRESSION_MID_WEIGHT: float = 0.6
_COMPRESSION_OLD_WEIGHT: float = 0.3


@dataclass
class CompressionResult:
    compressed_messages: List[Dict[str, str]]
    estimated_tokens: int
    compression_ratio: float
    removed_turns: int = 0


class DeepSeekOptimizer:
    """
    针对DeepSeek-V4-pro的特别调优
    - 长上下文提示词模板（128K窗口）
    - 思维链格式适配
    - 多轮对话上下文压缩策略
    - 响应格式约束
    """

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._compression_threshold = config.context_compression_threshold

    def build_long_context_prompt(
        self,
        system_prompt: str,
        memory_section: str,
        worldview_section: str,
        dialogue_section: str,
    ) -> str:
        """
        按权重分配token预算构建长上下文提示词
        """
        budget = self._compression_threshold
        sections = {
            "system": (system_prompt, _TOKEN_BUDGET_SYSTEM_WEIGHT),
            "memory": (memory_section, _TOKEN_BUDGET_MEMORY_WEIGHT),
            "worldview": (worldview_section, _TOKEN_BUDGET_WORLDVIEW_WEIGHT),
            "dialogue": (dialogue_section, _TOKEN_BUDGET_DIALOGUE_WEIGHT),
        }
        result_parts: List[str] = []
        for name, (content, weight) in sections.items():
            if content:
                section_budget = int(budget * weight)
                truncated = self._truncate_to_token_estimate(
                    content, section_budget
                )
                result_parts.append(truncated)
        return "\n\n".join(result_parts)

    def format_cot_prompt(self, task_description: str) -> str:
        """
        格式化思维链提示词
        DeepSeek-V4-pro支持<think}>标签的思维链
        """
        return (
            f"{task_description}\n\n"
            f"请先在{_COT_THINK_OPEN}...{_COT_THINK_CLOSE}标签中思考，"
            f"然后在{_COT_RESPONSE_OPEN}...{_COT_RESPONSE_CLOSE}标签中给出最终回答。"
        )

    @staticmethod
    def extract_cot_response(full_text: str) -> tuple:
        """
        从思维链输出中分离思考过程和最终回答
        返回: (thinking, response)
        """
        thinking = ""
        response = full_text

        think_start = full_text.find(_COT_THINK_OPEN)
        think_end = full_text.find(_COT_THINK_CLOSE)
        if think_start >= 0 and think_end > think_start:
            thinking = full_text[
                think_start + len(_COT_THINK_OPEN) : think_end
            ].strip()

        resp_start = full_text.find(_COT_RESPONSE_OPEN)
        resp_end = full_text.find(_COT_RESPONSE_CLOSE)
        if resp_start >= 0 and resp_end > resp_start:
            response = full_text[
                resp_start + len(_COT_RESPONSE_OPEN) : resp_end
            ].strip()
        elif thinking:
            after_think = full_text[think_end + len(_COT_THINK_CLOSE) :].strip()
            if after_think:
                response = after_think

        return thinking, response

    def compress_dialogue_context(
        self, messages: List[Dict[str, str]]
    ) -> CompressionResult:
        """
        基于优先级的对话上下文压缩
        最近的对话保留完整，中间对话压缩，早期对话摘要化
        """
        if not messages:
            return CompressionResult(
                compressed_messages=[],
                estimated_tokens=0,
                compression_ratio=1.0,
            )

        total = len(messages)
        recent_count = min(_COMPRESSION_RECENT_TURNS * 2, total)
        mid_count = min(_COMPRESSION_MID_TURNS * 2, total - recent_count)

        recent = messages[-recent_count:] if recent_count > 0 else []
        mid = (
            messages[-(recent_count + mid_count) : -recent_count]
            if mid_count > 0
            else []
        )
        old = (
            messages[: -(recent_count + mid_count)]
            if (recent_count + mid_count) < total
            else []
        )

        compressed: List[Dict[str, str]] = []

        if old:
            summary = self._summarize_messages(old, _COMPRESSION_OLD_WEIGHT)
            compressed.append(
                {"role": "system", "content": f"[早期对话摘要] {summary}"}
            )

        if mid:
            mid_compressed = self._compress_messages(
                mid, _COMPRESSION_MID_WEIGHT
            )
            compressed.extend(mid_compressed)

        compressed.extend(recent)

        original_tokens = self._estimate_tokens(messages)
        new_tokens = self._estimate_tokens(compressed)
        ratio = new_tokens / max(original_tokens, 1)

        return CompressionResult(
            compressed_messages=compressed,
            estimated_tokens=new_tokens,
            compression_ratio=ratio,
            removed_turns=total - len(compressed),
        )

    def build_format_constraint_prompt(self) -> str:
        """
        构建响应格式约束提示词
        要求LLM使用结构化标签输出
        """
        return (
            "请使用以下结构化格式输出：\n"
            f"1. 动作：{_FORMAT_ACTION_OPEN}动作描述{_FORMAT_ACTION_CLOSE}\n"
            f"2. 对话：{_FORMAT_DIALOGUE_OPEN}角色名(语气): 对话内容{_FORMAT_DIALOGUE_CLOSE}\n"
            f"3. 情感变化：{_FORMAT_EMOTION_OPEN}pleasure:值,arousal:值,dominance:值{_FORMAT_EMOTION_CLOSE}\n"
            "以上三项按需使用，不必全部包含。"
        )

    def estimate_tokens(self, messages: list) -> int:
        """公共接口：估算消息列表的token数"""
        return self._estimate_tokens(messages)

    @staticmethod
    def _estimate_tokens(messages: List[Dict[str, str]]) -> int:
        """
        估算消息的token数
        中文约1.5字/token，英文约4字符/token
        使用加权平均
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return int(total_chars * 0.6)

    @staticmethod
    def _truncate_to_token_estimate(text: str, max_tokens: int) -> str:
        """
        按token估算截断文本
        """
        max_chars = int(max_tokens / 0.6)
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "...[已截断]"

    @staticmethod
    def _summarize_messages(
        messages: List[Dict[str, str]], weight: float
    ) -> str:
        """
        将消息列表摘要化为简短描述
        weight控制保留的细节程度
        """
        if not messages:
            return ""
        key_points: List[str] = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "user")
            if len(content) > 100:
                content = content[:100] + "..."
            key_points.append(f"[{role}]{content}")
        max_points = max(1, int(len(key_points) * weight))
        selected = key_points[:max_points]
        return "; ".join(selected)

    @staticmethod
    def _compress_messages(
        messages: List[Dict[str, str]], weight: float
    ) -> List[Dict[str, str]]:
        """
        压缩消息列表，保留weight比例的消息
        """
        if not messages:
            return []
        keep_count = max(2, int(len(messages) * weight))
        if keep_count >= len(messages):
            return messages
        step = len(messages) / keep_count
        result: List[Dict[str, str]] = []
        for i in range(keep_count):
            idx = min(int(i * step), len(messages) - 1)
            result.append(messages[idx])
        return result
