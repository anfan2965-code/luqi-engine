"""四智能体协作架构 — 共享常量与枚举"""
from __future__ import annotations

from enum import Enum


class ViolationLevel(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    SUGGESTION = "suggestion"


class ViolationType(str, Enum):
    EMOTION_OUT_OF_RANGE = "emotion_out_of_range"
    ACTION_EMPTY = "action_empty"
    TIME_SKIP_EXCEEDED = "time_skip_exceeded"
    FACT_CONFLICT = "fact_conflict"


class NarrativeSignal(str, Enum):
    TIME_SKIP = "time_skip"


class StoryBeatStatus(str, Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class ScopeLevel(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class PaceLevel(str, Enum):
    FROZEN = "frozen"
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"
    URGENT = "urgent"


class ToneType(str, Enum):
    NEUTRAL = "neutral"
    CASUAL = "casual"
    CAUTIOUS = "cautious"
    FORMAL = "formal"
    ANGRY = "angry"
    SAD = "sad"


class LengthHint(str, Enum):
    TINY = "tiny"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class CriticSeverity(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class CriticVerdictType(str, Enum):
    ACCEPT = "accept"
    MINOR_FIX = "minor_fix"
    MAJOR_REWRITE = "major_rewrite"
    REJECT = "reject"
    REVIEW = "review"


class AtmosphereMode(str, Enum):
    LIGHT = "light"
    FULL = "full"


class CriticMode(str, Enum):
    FULL = "full"
    LIGHT = "light"


class AtmospherePosition(str, Enum):
    PREFIX = "prefix"
    SUFFIX = "suffix"
    WRAP = "wrap"
    INTERLEAVE = "interleave"


class LengthBudget(str, Enum):
    TINY = "tiny"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class CorrectionSeverity(str, Enum):
    CLAMP = "clamp"
    REPLACE = "replace"
    OVERRIDE = "override"
    REJECT = "reject"


class DialogueSource(str, Enum):
    ORIGINAL = "original"


class QualityGrade(str, Enum):
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    CONTAMINATED = "contaminated"
    QUARANTINE = "quarantine"


class PromptContextMode(str, Enum):
    STANDARD = "standard"
    COMPACT = "compact"
    DETAILED = "detailed"
    PROSE = "prose"


class NovelMode(str, Enum):
    FULL_UPDATE = "full_update"
    INCREMENTAL = "incremental"
    PREDICTION_ONLY = "prediction_only"


class AgentMode(str, Enum):
    DEFAULT = "default"


class QualityLevel(str, Enum):
    ECONOMY = "economy"
    STANDARD = "standard"
    QUALITY = "quality"
    CINEMATIC = "cinematic"


class LLMMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class MemoryType(str, Enum):
    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EMOTIONAL = "emotional"
    PROCEDURAL = "procedural"
    SHARED = "shared"


class AssemblyMode(str, Enum):
    PREFIX = "prefix"
    SUFFIX = "suffix"
    WRAP = "wrap"
    INTERLEAVE = "interleave"


_PERSONALITY_SCORE_MAX = 100.0
_AROUSAL_DELTA_BASE = 0.3
_AROUSAL_DELTA_NEUROTICISM_FACTOR = 0.5
_PLEASURE_DELTA_MAX = 1.0
_DOMINANCE_DELTA_MAX = 1.0
_MAX_TIME_SKIP_PER_TURN = 3600.0
_DEFAULT_FORCED_ACTION = "idle"
_FACT_ID_PREFIX = "fact_"
_FACT_ID_ZERO_PAD_WIDTH = 3
_TICK_ID_PREFIX = "tick_"
_DEFAULT_CHARACTER_NAME = "角色"
_DEFAULT_MAX_KEY_POINTS = 3
_DEFAULT_EMOTION_INTENSITY = 0.5
_DEFAULT_ATMOSPHERE_PRIORITY = 0.5
_DEFAULT_MOOD_INTENSITY = 0.5
_FALLBACK_CRITIC_CONFIDENCE = 0.5
_FALLBACK_CONTEXT_MAX_LENGTH = 200
_FALLBACK_SOURCE = "fallback"
_MAX_RECENT_FACTS = 5
_MS_PER_SECOND = 1000
_SAMPLE_ID_HEX_LENGTH = 12
_CONFIDENCE_ROUND_PRECISION = 4
_LAYER_DIR_PREFIX = "layer"
_SAMPLE_FILE_EXTENSION = ".json"
_DEFAULT_DIALOGUE_SOURCE = "original"
_DEFAULT_GRADE = "bronze"
_DEFAULT_PACING_HINT = "normal"
_DEFAULT_SUGGESTED_POSITION = "prefix"
_DEFAULT_LENGTH_BUDGET = "short"
_DEFAULT_SCENE_NAME = "未知场景"
_DEFAULT_DOMINANT_EMOTION = "neutral"
_FALLBACK_STAGE_ACTION = "静立"
_DEFAULT_TOKEN_BUDGET = 1000
_DEFAULT_AGENT_TEMPERATURE = 0.7
_DIALOGUE_TOKEN_BUDGET = 2000
_DIALOGUE_TEMPERATURE = 0.8
_NOVEL_TOKEN_BUDGET = 1500
_NOVEL_TEMPERATURE = 0.7
_CRITIC_TOKEN_BUDGET = 800
_CRITIC_TEMPERATURE = 0.3
_ATMOSPHERE_TOKEN_BUDGET = 1000
_ATMOSPHERE_TEMPERATURE = 0.8
_NARRATIVE_DOC_MAX_FACTS = 1000
_NARRATIVE_DOC_MAX_CHAPTER_DEPTH = 10
_NARRATIVE_DOC_MAX_SCENE_PREDICTIONS = 5
_NARRATIVE_DOC_AUTO_SAVE_INTERVAL = 60.0
_PACE_FAST_THRESHOLD = 15.0
_PACE_SLOW_THRESHOLD = 60.0
_PACE_AUTO_MODE_TIMEOUT = 30.0
_PACE_WINDOW_SIZE = 10
_TRAINING_DEFAULT_STORAGE_PATH = "training_data"
_TRAINING_QUALITY_THRESHOLD = 0.3
_TRAINING_MAX_SAMPLES_PER_CHARACTER = 10000
_MAX_RECENT_EXCHANGES = 5
_DEFAULT_ROLE_LABEL = "unknown"
_MAX_MEMORY_ITEMS_PER_TYPE = 5
_MAX_PROMPT_RECENT_FACTS = 10
_DEFAULT_ACTION_TYPE = "general"
_ANTHROPIC_PREFILL_DIALOGUE = "我已理解角色设定和上下文，请继续。"
_ANTHROPIC_PREFILL_NOVELIST = "我已理解叙事上下文，请继续。"
_ANTHROPIC_PREFILL_CRITIC = "我已理解审查标准，请提供待审查内容。"
_ANTHROPIC_PREFILL_ATMOSPHERE = "我已理解氛围生成要求，请提供场景信息。"
_SCENE_LABEL_PREFIX = "当前场景："
_TASK_NAME_NOVEL_UPDATE = "novel_update"
_TASK_NAME_CRITIC_PRECHECK = "critic_precheck"
_TASK_NAME_DIALOGUE_PREANALYZE = "dialogue_preanalyze"
_TASK_NAME_ATMOSPHERE_PRERENDER = "atmosphere_prerender"
_CACHE_KEY_NOVEL = "novel"
_CACHE_KEY_CRITIC = "critic"
_CACHE_KEY_DIALOGUE = "dialogue"
_CACHE_KEY_ATMOSPHERE = "atmosphere"
_CTX_KEY_GOAP_NEXT_ACTION = "goap_next_action"
_CTX_KEY_GOAP_PLAN_LENGTH = "goap_plan_length"
_CTX_KEY_CANONICAL_IR = "canonical_ir"
_CTX_KEY_DOMINANT_EMOTION = "dominant_emotion"

OCEAN_HIGH_THRESHOLD = 65.0
OCEAN_LOW_THRESHOLD = 35.0
PAD_POSITIVE_THRESHOLD = 0.2
PAD_NEGATIVE_THRESHOLD = -0.2

# 输入验证常量
_MAX_INPUT_LENGTH: int = 10000  # 字符数

# 重复检测常量
_REPETITION_MIN_TEXT_LENGTH: int = 8  # 文本最小长度才进行重复检测
_REPETITION_SHORT_PATTERN_MIN: int = 2  # 短模式最小重复次数
_REPETITION_SHORT_PATTERN_MAX: int = 8  # 短模式最大长度
_REPETITION_MEDIUM_PATTERN_MIN: int = 2  # 中模式最小重复次数
_REPETITION_MEDIUM_PATTERN_MAX: int = 10  # 中模式最大长度
_REPETITION_LONG_PATTERN_MIN: int = 3  # 长模式最小长度
_REPETITION_LONG_PATTERN_MAX: int = 15  # 长模式最大长度
_REPETITION_CUTOFF_MIN: int = 6  # 截断位置最小值
_REPETITION_NGRAM_SIZES: tuple = (6, 4)  # n-gram大小列表
_REPETITION_NGRAM_GAP_MULTIPLIER: int = 3  # n-gram间隔乘数
_REPETITION_NGRAM_POSITION_MULTIPLIER: int = 2  # n-gram位置乘数

# 对话默认值
_DEFAULT_MAX_ROUNDS: int = 20  # 多角色对话默认最大轮次
_DEFAULT_AUTHORITY_RANK: int = 0  # 默认权限等级

# 本地LLM输出要求
_LOCAL_LLM_OUTPUT_REQUIREMENTS: str = "第一人称回复，保持角色风格，回复长度50-200字"

# 快照文件格式
_SNAPSHOT_FILE_PREFIX: str = "luqi_engine_snapshot_"
_SNAPSHOT_FILE_EXTENSION: str = ".json"

# 引擎版本
_ENGINE_VERSION: str = "0.1.0"
_ENGINE_NAME: str = "LuqiAI Engine"
