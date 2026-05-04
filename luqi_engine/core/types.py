"""
核心数据类型定义 - 引擎全局使用的基础数据结构
所有数值参数均通过配置注入，不使用魔法数字
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.constants import (
    StoryBeatStatus,
    ScopeLevel,
    PaceLevel,
    ToneType,
    LengthHint,
    CriticSeverity,
    CriticVerdictType,
    AtmosphereMode,
    CorrectionSeverity,
    _DEFAULT_SUGGESTED_POSITION,
    _DEFAULT_LENGTH_BUDGET,
    _DEFAULT_DIALOGUE_SOURCE,
    QualityGrade,
)


EntityId = str

_ENTITY_ID_HEX_LENGTH_WITH_PREFIX: int = 12
_ENTITY_ID_HEX_LENGTH_NO_PREFIX: int = 16


def generate_entity_id(prefix: str = "") -> EntityId:
    return f"{prefix}_{uuid.uuid4().hex[:_ENTITY_ID_HEX_LENGTH_WITH_PREFIX]}" if prefix else uuid.uuid4().hex[:_ENTITY_ID_HEX_LENGTH_NO_PREFIX]


@dataclass(frozen=True)
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: Vector3) -> float:
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )

    def lerp(self, other: Vector3, t: float) -> Vector3:
        t = max(0.0, min(1.0, t))
        return Vector3(
            x=self.x + (other.x - self.x) * t,
            y=self.y + (other.y - self.y) * t,
            z=self.z + (other.z - self.z) * t,
        )

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class BoundingBox:
    center: Vector3
    half_extents: Vector3

    def contains(self, point: Vector3) -> bool:
        return (
            abs(point.x - self.center.x) <= self.half_extents.x
            and abs(point.y - self.center.y) <= self.half_extents.y
            and abs(point.z - self.center.z) <= self.half_extents.z
        )

    def intersects(self, other: BoundingBox) -> bool:
        return (
            abs(self.center.x - other.center.x)
            <= self.half_extents.x + other.half_extents.x
            and abs(self.center.y - other.center.y)
            <= self.half_extents.y + other.half_extents.y
            and abs(self.center.z - other.center.z)
            <= self.half_extents.z + other.half_extents.z
        )


class EventType(Enum):
    ENTITY_SPAWNED = auto()
    ENTITY_DESPAWNED = auto()
    STATE_CHANGED = auto()
    DIALOGUE_STARTED = auto()
    DIALOGUE_ENDED = auto()
    NARRATIVE_NODE_REACHED = auto()
    NARRATIVE_BRANCH_TAKEN = auto()
    CHARACTER_ACTION = auto()
    SCENE_TRANSITION = auto()
    CONFLICT_DETECTED = auto()
    CUSTOM = auto()


@dataclass
class WorldState:
    flags: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, float] = field(default_factory=dict)
    timestamps: Dict[str, float] = field(default_factory=dict)

    def get_flag(self, key: str, default: Any = None) -> Any:
        return self.flags.get(key, default)

    def set_flag(self, key: str, value: Any) -> None:
        self.flags[key] = value

    def get_variable(self, key: str, default: float = 0.0) -> float:
        return self.variables.get(key, default)

    def set_variable(self, key: str, value: float) -> None:
        self.variables[key] = value

    def merge(self, other: WorldState) -> WorldState:
        merged = WorldState(
            flags={**self.flags, **other.flags},
            variables={**self.variables, **other.variables},
            timestamps={**self.timestamps, **other.timestamps},
        )
        return merged


@dataclass
class ActionResult:
    success: bool
    entity_id: EntityId
    action_name: str
    state_delta: WorldState = field(default_factory=WorldState)
    side_effects: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    error_message: Optional[str] = None


@dataclass
class ConflictReport:
    conflict_id: str
    conflict_type: str
    description: str
    severity: float
    involved_entities: List[EntityId]
    suggested_resolutions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TimingConstraints:
    earliest: float = 0.0
    latest: float = float("inf")
    cooldown: float = 0.0
    last_triggered: float = 0.0

    def is_valid_at(self, current_time: float) -> bool:
        if current_time < self.earliest:
            return False
        if current_time > self.latest:
            return False
        if current_time - self.last_triggered < self.cooldown:
            return False
        return True


class SDKType(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL_LLM = "local_llm"


class SevenEmotionType(Enum):
    JOY = "喜"
    ANGER = "怒"
    SORROW = "哀"
    FEAR = "惧"
    LOVE = "爱"
    DISGUST = "恶"
    DESIRE = "欲"


class TCMEmotionType(Enum):
    JOY = "喜"
    ANGER = "怒"
    ANXIETY = "忧"
    THOUGHT = "思"
    GRIEF = "悲"
    FEAR = "恐"
    FRIGHT = "惊"


class PlutchikPrimary(Enum):
    JOY = "joy"
    TRUST = "trust"
    FEAR = "fear"
    SURPRISE = "surprise"
    SADNESS = "sadness"
    DISGUST = "disgust"
    ANGER = "anger"
    ANTICIPATION = "anticipation"


class PlutchikDyad(Enum):
    LOVE = "love"
    SUBMISSION = "submission"
    AWE = "awe"
    DISAPPROVAL = "disapproval"
    REMORSE = "remorse"
    CONTEMPT = "contempt"
    AGGRESSIVENESS = "aggressiveness"
    OPTIMISM = "optimism"


class SixDesireType(Enum):
    SIGHT = "眼"
    HEARING = "耳"
    SMELL = "鼻"
    TASTE = "舌"
    TOUCH = "身"
    MIND = "意"


class MaslowNeedType(Enum):
    PHYSIOLOGICAL = "physiological"
    SAFETY = "safety"
    LOVE_BELONGING = "love_belonging"
    ESTEEM = "esteem"
    SELF_ACTUALIZATION = "self_actualization"
    SELF_TRANSCENDENCE = "self_transcendence"


class FrommNeedType(Enum):
    RELATEDNESS = "relatedness"
    TRANSCENDENCE = "transcendence"
    ROOTEDNESS = "rootedness"
    IDENTITY = "identity"
    ORIENTATION = "orientation"


_DESIRE_DIMENSION_MIN = 0.0
_DESIRE_DIMENSION_MAX = 1.0
_DESIRE_DEFAULT_DIMENSIONS: Tuple[str, ...] = (
    "physiological",
    "safety",
    "belonging",
    "esteem",
    "self_actualization",
    "self_transcendence",
    "sight",
    "hearing",
    "smell",
    "taste",
    "touch",
    "mind",
    "relatedness",
    "transcendence",
    "rootedness",
    "identity",
    "orientation",
)


@dataclass
class DesireVector:
    DIMENSION_MIN: ClassVar[float] = _DESIRE_DIMENSION_MIN
    DIMENSION_MAX: ClassVar[float] = _DESIRE_DIMENSION_MAX
    DEFAULT_DIMENSIONS: ClassVar[Tuple[str, ...]] = _DESIRE_DEFAULT_DIMENSIONS

    dimensions: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in self.DEFAULT_DIMENSIONS:
            if name not in self.dimensions:
                self.dimensions[name] = self.DIMENSION_MIN

    def set_dimension(self, name: str, value: float) -> None:
        clamped = max(self.DIMENSION_MIN, min(self.DIMENSION_MAX, value))
        self.dimensions[name] = clamped

    def get_dimension(self, name: str) -> float:
        return self.dimensions.get(name, self.DIMENSION_MIN)

    def add_dimension(self, name: str, initial_value: float = _DESIRE_DIMENSION_MIN) -> None:
        if name not in self.dimensions:
            clamped = max(self.DIMENSION_MIN, min(self.DIMENSION_MAX, initial_value))
            self.dimensions[name] = clamped

    def remove_dimension(self, name: str) -> None:
        self.dimensions.pop(name, None)

    def magnitude(self) -> float:
        if not self.dimensions:
            return _DESIRE_DIMENSION_MIN
        return math.sqrt(sum(v ** 2 for v in self.dimensions.values()))

    def normalize(self) -> DesireVector:
        mag = self.magnitude()
        if mag == _DESIRE_DIMENSION_MIN:
            return DesireVector(dimensions=dict(self.dimensions))
        return DesireVector(
            dimensions={k: v / mag for k, v in self.dimensions.items()}
        )


_EMOTION_DEFAULT_WEIGHT = 0.0
_EMOTION_NEUTRAL_INTENSITY = 0.0


@dataclass
class SevenEmotions:
    DEFAULT_WEIGHT: ClassVar[float] = _EMOTION_DEFAULT_WEIGHT
    NEUTRAL_INTENSITY: ClassVar[float] = _EMOTION_NEUTRAL_INTENSITY

    weights: Dict[str, Dict[str, float]] = field(default_factory=dict)
    active_emotions: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        emotion_names = [e.value for e in SevenEmotionType]
        for source in emotion_names:
            if source not in self.weights:
                self.weights[source] = {}
            for target in emotion_names:
                if target not in self.weights[source]:
                    self.weights[source][target] = self.DEFAULT_WEIGHT

    def set_weight(self, source: str, target: str, weight: float) -> None:
        if source not in self.weights:
            self.weights[source] = {}
        self.weights[source][target] = weight

    def get_weight(self, source: str, target: str) -> float:
        return self.weights.get(source, {}).get(target, self.DEFAULT_WEIGHT)

    def set_emotion(self, name: str, intensity: float) -> None:
        self.active_emotions[name] = intensity

    def get_emotion(self, name: str) -> float:
        return self.active_emotions.get(name, self.NEUTRAL_INTENSITY)

    def dominant_emotion(self) -> Optional[str]:
        if not self.active_emotions:
            return None
        return max(self.active_emotions, key=self.active_emotions.get)


_DESIRE_INTENSITY_MIN = 0.0
_DESIRE_INTENSITY_MAX = 1.0


@dataclass
class SixDesires:
    MIN_INTENSITY: ClassVar[float] = _DESIRE_INTENSITY_MIN
    MAX_INTENSITY: ClassVar[float] = _DESIRE_INTENSITY_MAX

    intensities: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for desire in SixDesireType:
            if desire.value not in self.intensities:
                self.intensities[desire.value] = self.MIN_INTENSITY

    def set_intensity(self, desire_name: str, value: float) -> None:
        clamped = max(self.MIN_INTENSITY, min(self.MAX_INTENSITY, value))
        self.intensities[desire_name] = clamped

    def get_intensity(self, desire_name: str) -> float:
        return self.intensities.get(desire_name, self.MIN_INTENSITY)


_LLM_DEFAULT_TEMPERATURE = 0.7
_LLM_DEFAULT_MAX_TOKENS = 1024
_LLM_DEFAULT_STREAM = False


@dataclass
class LLMRequest:
    DEFAULT_TEMPERATURE: ClassVar[float] = _LLM_DEFAULT_TEMPERATURE
    DEFAULT_MAX_TOKENS: ClassVar[int] = _LLM_DEFAULT_MAX_TOKENS
    DEFAULT_STREAM: ClassVar[bool] = _LLM_DEFAULT_STREAM

    sdk_type: SDKType
    messages: List[Dict[str, str]]
    temperature: float = _LLM_DEFAULT_TEMPERATURE
    max_tokens: int = _LLM_DEFAULT_MAX_TOKENS
    model: str = ""
    stream: bool = _LLM_DEFAULT_STREAM
    grammar: Optional[str] = None


_LLM_RESPONSE_DEFAULT_TOKENS = 0


@dataclass
class LLMResponse:
    DEFAULT_TOKENS: ClassVar[int] = _LLM_RESPONSE_DEFAULT_TOKENS

    content: str
    role: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    tokens: int = _LLM_RESPONSE_DEFAULT_TOKENS
    thinking: str = ""


@dataclass
class LLMStreamChunk:
    delta: str
    finish_reason: Optional[str] = None


_LOCAL_MODEL_DEFAULT_CONFIDENCE = 0.0


@dataclass
class LocalModelOutput:
    DEFAULT_CONFIDENCE: ClassVar[float] = _LOCAL_MODEL_DEFAULT_CONFIDENCE

    classification: str
    confidence: float = _LOCAL_MODEL_DEFAULT_CONFIDENCE
    correction_suggestions: List[str] = field(default_factory=list)



_PACE_DEFAULT_USER_PREFERENCE = 0.5
_PACE_SCENES_PER_CHAPTER_TARGET = 5
_AUTO_MODE_DEFAULT_TIMEOUT_SECONDS = 30.0
_AUTO_MODE_DEFAULT_MAX_TICKS = 10
_AUTO_MODE_DEFAULT_NPC_AUTONOMY = 0.5
_CRITIC_CHECK_DEFAULT_SCORE = 1.0
_CRITIC_VERDICT_DEFAULT_CONFIDENCE = 1.0
_MOOD_DEFAULT_INTENSITY = 0.5
_ATMOSPHERE_DEFAULT_PRIORITY = 0.5


@dataclass
class Fact:
    id: str
    sequence_number: int
    timestamp: str
    source: str
    content: str
    participants: List[str]
    location: Optional[str] = None
    emotional_valence: float = 0.0
    tags: List[str] = field(default_factory=list)
    is_retracted: bool = False


@dataclass
class StoryBeat:
    name: str
    description: str
    expected_participants: List[str]
    tension_level: float = 0.0
    status: StoryBeatStatus = StoryBeatStatus.UPCOMING
    progress: float = 0.0


@dataclass
class CharacterArc:
    character_id: str = ""
    arc_name: str = ""
    starting_state: Dict[str, Any] = field(default_factory=dict)
    current_state: Dict[str, Any] = field(default_factory=dict)
    target_state: Dict[str, Any] = field(default_factory=dict)
    position: float = 0.0
    key_moments: List[str] = field(default_factory=list)
    development_notes: List[str] = field(default_factory=list)


@dataclass
class ChapterOutline:
    chapter_id: int = 0
    title: str = ""
    arc_summary: str = ""
    beats: List[StoryBeat] = field(default_factory=list)
    current_beat_index: int = 0
    character_arcs: Dict[str, CharacterArc] = field(default_factory=dict)
    hard_constraints: List[str] = field(default_factory=list)
    soft_constraints: List[str] = field(default_factory=list)
    estimated_scope: str = ScopeLevel.MEDIUM


@dataclass
class ScenePrediction:
    scene_id: str = ""
    scene_name: str = ""
    probability: float = 0.0
    description: str = ""
    expected_participants: List[str] = field(default_factory=list)
    estimated_tension: float = 0.0
    prerequisites: List[str] = field(default_factory=list)
    blocking_issues: List[str] = field(default_factory=list)


@dataclass
class PaceState:
    current_pace: PaceLevel = PaceLevel.NORMAL
    user_pace_preference: float = _PACE_DEFAULT_USER_PREFERENCE
    scenes_per_chapter_target: int = _PACE_SCENES_PER_CHAPTER_TARGET
    actual_scenes_this_chapter: int = 0
    ticks_since_last_progress: int = 0
    stagnation_detected: bool = False


@dataclass
class AutoModeConfig:
    enabled: bool = True
    trigger_timeout_seconds: float = _AUTO_MODE_DEFAULT_TIMEOUT_SECONDS
    max_auto_ticks: int = _AUTO_MODE_DEFAULT_MAX_TICKS
    npc_autonomy_level: float = _AUTO_MODE_DEFAULT_NPC_AUTONOMY
    advance_on_timeout: bool = True
    pause_on_branch_point: bool = True


@dataclass
class NewFact:
    id: str = ""
    timestamp: str = ""
    source: str = ""
    content: str = ""
    participants: List[str] = field(default_factory=list)
    emotional_valence: float = 0.0
    tags: List[str] = field(default_factory=list)


@dataclass
class ChapterUpdate:
    current_beat_progress: float = 0.0
    new_beat_suggested: Optional[Dict[str, Any]] = None
    character_arcs_update: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    constraints_added: List[str] = field(default_factory=list)
    constraints_removed: List[str] = field(default_factory=list)


@dataclass
class NextPrediction:
    likely_next_scenes: List[Dict[str, Any]] = field(default_factory=list)
    narrative_tension: float = 0.0
    suggested_pace: str = PaceLevel.NORMAL


@dataclass
class NarrativeDelta:
    version: int = 0
    new_facts: List[NewFact] = field(default_factory=list)
    chapter_update: Optional[ChapterUpdate] = None
    next_prediction: Optional[NextPrediction] = None
    open_questions_added: List[str] = field(default_factory=list)
    open_questions_resolved: List[str] = field(default_factory=list)
    narrative_note: str = ""


@dataclass
class EmotionDelta:
    pleasure: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0


@dataclass
class CanonicalIR:
    intent: str = ""
    confidence: float = 0.0
    emotion_delta: EmotionDelta = field(default_factory=EmotionDelta)
    seven_trigger: str = ""
    action: str = ""
    action_params: Dict[str, Any] = field(default_factory=dict)
    key_points: List[str] = field(default_factory=list)
    tone: ToneType = ToneType.NEUTRAL
    length_hint: LengthHint = LengthHint.MEDIUM
    narrative_signal: Optional[str] = None
    memory_to_add: Optional[Dict[str, Any]] = None


@dataclass
class CriticCheck:
    dimension: str = ""
    severity: CriticSeverity = CriticSeverity.PASS
    score: float = _CRITIC_CHECK_DEFAULT_SCORE
    detail: str = ""


@dataclass
class CriticCorrections:
    suggested_emotion_delta: Optional[EmotionDelta] = None
    suggested_action: Optional[str] = None
    suggested_key_point_addition: Optional[str] = None
    narrative_risk_flag: bool = False


@dataclass
class CriticVerdict:
    verdict: CriticVerdictType = CriticVerdictType.ACCEPT
    checks: List[CriticCheck] = field(default_factory=list)
    overall_confidence: float = _CRITIC_VERDICT_DEFAULT_CONFIDENCE
    corrections: Optional[CriticCorrections] = None
    override_recommendation: Optional[str] = None


@dataclass
class AtmosphereEnvironment:
    visual: str = ""
    auditory: str = ""
    olfactory: str = ""
    thermal: str = ""
    spatial: str = ""


@dataclass
class AtmosphereNarration:
    transition: Optional[str] = None
    inner_voice: Optional[str] = None
    omniscient_note: Optional[str] = None


@dataclass
class StageDirection:
    character: str = ""
    action: str = ""
    detail: str = ""


@dataclass
class MoodDeclaration:
    dominant_emotion: ToneType = ToneType.NEUTRAL
    intensity: float = _MOOD_DEFAULT_INTENSITY
    color_palette: List[str] = field(default_factory=list)
    pacing_hint: PaceLevel = PaceLevel.NORMAL


@dataclass
class AtmosphereOutput:
    mode: AtmosphereMode = AtmosphereMode.LIGHT
    environment: AtmosphereEnvironment = field(default_factory=AtmosphereEnvironment)
    narration: AtmosphereNarration = field(default_factory=AtmosphereNarration)
    stage_directions: List[StageDirection] = field(default_factory=list)
    mood_declaration: MoodDeclaration = field(default_factory=MoodDeclaration)
    suggested_position: str = _DEFAULT_SUGGESTED_POSITION
    length_budget: str = _DEFAULT_LENGTH_BUDGET
    priority: float = _ATMOSPHERE_DEFAULT_PRIORITY


@dataclass
class Violation:
    level: str = ""
    type: str = ""
    field: str = ""
    original: Any = None
    forced: Any = None
    score: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class ValidatedIR:
    ir: Optional[CanonicalIR] = None
    violations: List[Violation] = field(default_factory=list)
    is_clean: bool = True
    needs_critic_review: bool = False


@dataclass
class ValidatedDelta:
    delta: Optional[NarrativeDelta] = None
    violations: List[Violation] = field(default_factory=list)


@dataclass
class CharacterStateSnapshot:
    ocean_scores: Dict[str, float] = field(default_factory=dict)
    pad_state: Dict[str, float] = field(default_factory=dict)
    seven_emotions: Dict[str, float] = field(default_factory=dict)
    current_desires: Dict[str, float] = field(default_factory=dict)
    current_action: str = ""


@dataclass
class TrainingInput:
    narrative_summary: str = ""
    narrative_facts_recent: List[str] = field(default_factory=list)
    chapter_context: str = ""
    user_message: str = ""
    character_state_snapshot: Optional[CharacterStateSnapshot] = None
    scene_context: str = ""
    recent_exchanges: List[Dict[str, Any]] = field(default_factory=list)
    pace_context: str = ""


@dataclass
class AgentOutputs:
    novel: Optional[NarrativeDelta] = None
    dialogue: Optional[CanonicalIR] = None
    critic: Optional[CriticVerdict] = None
    atmosphere: Optional[AtmosphereOutput] = None
    novel_token_usage: int = 0
    dialogue_token_usage: int = 0
    critic_token_usage: int = 0
    atmosphere_token_usage: int = 0
    total_latency_ms: int = 0


@dataclass
class CorrectionRecord:
    field: str = ""
    original_value: Any = None
    corrected_value: Any = None
    reason: str = ""
    severity: str = CorrectionSeverity.CLAMP


@dataclass
class AlgorithmCorrections:
    dialogue_corrections: List[CorrectionRecord] = field(default_factory=list)
    novel_corrections: List[CorrectionRecord] = field(default_factory=list)


@dataclass
class FinalOutput:
    reply_text: str = ""
    executed_action: str = ""
    final_emotion: Optional[EmotionDelta] = None
    memory_entries_created: List[str] = field(default_factory=list)
    narrative_version_after: int = 0
    dialogue_source: str = _DEFAULT_DIALOGUE_SOURCE
    voice_renderer_used: bool = False


@dataclass
class SampleQuality:
    overall_score: float = 0.0
    coherence_score: float = 0.0
    character_faithfulness: float = 0.0
    narrative_alignment: float = 0.0
    grade: str = QualityGrade.BRONZE
    contamination_flags: List[str] = field(default_factory=list)


@dataclass
class TrainingSample:
    sample_id: str = ""
    character_id: str = ""
    timestamp: float = 0.0
    narrative_version: int = 0
    input: Optional[TrainingInput] = None
    agent_outputs: Optional[AgentOutputs] = None
    algorithm_corrections: Optional[AlgorithmCorrections] = None
    final_output: Optional[FinalOutput] = None
    quality: Optional[SampleQuality] = None
    usage_tags: List[str] = field(default_factory=list)
