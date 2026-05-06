from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from luqi_engine.core.logging_config import get_logger

_logger = get_logger(__name__)

_DEFAULT_EMOTION_KEYWORDS: List[str] = [
    "难过", "开心", "生气", "害怕", "焦虑", "孤独", "感动", "失望",
    "思念", "心疼", "委屈", "愤怒", "悲伤", "快乐", "幸福", "痛苦",
    "紧张", "担心", "想念", "喜欢", "讨厌", "爱", "恨", "抱歉",
    "对不起", "谢谢", "感谢", "安慰", "拥抱", "哭", "笑",
]

_DEFAULT_NARRATIVE_KEYWORDS: List[str] = [
    "故事", "剧情", "叙事", "发展", "转折", "冲突", "高潮", "结局",
    "背景", "世界观", "设定", "规则", "体系", "历史", "传说",
]

_DEFAULT_MULTI_CHARACTER_INDICATORS: List[str] = [
    "他们", "大家", "所有人", "一起", "彼此", "互相", "众人",
]


class IntentKeywordConfig:
    def __init__(
        self,
        emotion_keywords: Optional[List[str]] = None,
        narrative_keywords: Optional[List[str]] = None,
        multi_character_indicators: Optional[List[str]] = None,
        simple_max_length: Optional[int] = None,
        moderate_max_length: Optional[int] = None,
    ) -> None:
        self.emotion_keywords = emotion_keywords if emotion_keywords is not None else list(_DEFAULT_EMOTION_KEYWORDS)
        self.narrative_keywords = narrative_keywords if narrative_keywords is not None else list(_DEFAULT_NARRATIVE_KEYWORDS)
        self.multi_character_indicators = multi_character_indicators if multi_character_indicators is not None else list(_DEFAULT_MULTI_CHARACTER_INDICATORS)
        self.simple_max_length = simple_max_length if simple_max_length is not None else 20
        self.moderate_max_length = moderate_max_length if moderate_max_length is not None else 100

    @classmethod
    def from_yaml(cls, path: str | Path) -> IntentKeywordConfig:
        yaml_path = Path(path)
        if not yaml_path.exists():
            _logger.info("Intent config file not found: %s, using defaults", yaml_path)
            return cls()
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return cls(
                emotion_keywords=data.get("emotion_keywords"),
                narrative_keywords=data.get("narrative_keywords"),
                multi_character_indicators=data.get("multi_character_indicators"),
                simple_max_length=data.get("simple_max_length"),
                moderate_max_length=data.get("moderate_max_length"),
            )
        except ImportError:
            _logger.warning("PyYAML not installed, using default keywords")
            return cls()
        except Exception as exc:
            _logger.error("Failed to load intent config: %s", exc)
            return cls()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IntentKeywordConfig:
        return cls(
            emotion_keywords=data.get("emotion_keywords"),
            narrative_keywords=data.get("narrative_keywords"),
            multi_character_indicators=data.get("multi_character_indicators"),
            simple_max_length=data.get("simple_max_length"),
            moderate_max_length=data.get("moderate_max_length"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotion_keywords": list(self.emotion_keywords),
            "narrative_keywords": list(self.narrative_keywords),
            "multi_character_indicators": list(self.multi_character_indicators),
            "simple_max_length": self.simple_max_length,
            "moderate_max_length": self.moderate_max_length,
        }
