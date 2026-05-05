"""
引擎全局配置 - 所有可调参数集中管理
零硬编码：所有数值从此文件或外部YAML加载
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from luqi_engine.core.types import _DESIRE_DEFAULT_DIMENSIONS
from luqi_engine.core.constants import (
    AgentMode,
    NovelMode,
    AtmosphereMode,
    CriticMode,
    QualityLevel,
    _DEFAULT_TOKEN_BUDGET,
    _DEFAULT_AGENT_TEMPERATURE,
    _DIALOGUE_TOKEN_BUDGET,
    _DIALOGUE_TEMPERATURE,
    _NOVEL_TOKEN_BUDGET,
    _NOVEL_TEMPERATURE,
    _CRITIC_TOKEN_BUDGET,
    _CRITIC_TEMPERATURE,
    _ATMOSPHERE_TOKEN_BUDGET,
    _ATMOSPHERE_TEMPERATURE,
    _NARRATIVE_DOC_MAX_FACTS,
    _NARRATIVE_DOC_MAX_CHAPTER_DEPTH,
    _NARRATIVE_DOC_MAX_SCENE_PREDICTIONS,
    _NARRATIVE_DOC_AUTO_SAVE_INTERVAL,
    _PACE_FAST_THRESHOLD,
    _PACE_SLOW_THRESHOLD,
    _PACE_AUTO_MODE_TIMEOUT,
    _PACE_WINDOW_SIZE,
    _TRAINING_DEFAULT_STORAGE_PATH,
    _TRAINING_QUALITY_THRESHOLD,
    _TRAINING_MAX_SAMPLES_PER_CHARACTER,
)


class ConfigMixin:
    """配置类通用序列化mixin，消除to_dict/from_dict重复代码"""
    
    # 敏感字段列表，序列化时会被脱敏
    _SENSITIVE_FIELDS = {"api_key", "secret_key", "password", "token"}

    def to_dict(self, redact_sensitive: bool = True) -> dict:
        result = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            # 敏感字段脱敏处理
            if redact_sensitive and field_name in self._SENSITIVE_FIELDS:
                if value:  # 非空才脱敏
                    result[field_name] = "***REDACTED***"
                else:
                    result[field_name] = value
                continue
            
            if hasattr(value, 'to_dict') and callable(value.to_dict):
                result[field_name] = value.to_dict(redact_sensitive=redact_sensitive)
            elif isinstance(value, tuple):
                result[field_name] = list(value)
            elif isinstance(value, Enum):
                result[field_name] = value.value
            else:
                result[field_name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict):
        valid_data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid_data)


@dataclass
class PerformanceConfig(ConfigMixin):
    target_fps: int = 30
    max_cpu_percent: float = 70.0
    max_memory_mb: float = 4096.0
    response_latency_ms: float = 300.0
    inactive_release_threshold_sec: float = 300.0
    resource_recovery_efficiency: float = 0.7
    object_pool_initial_size: int = 64
    async_task_concurrency: int = 8


@dataclass
class WorldViewConfig(ConfigMixin):
    conflict_detection_accuracy: float = 0.95
    element_extraction_accuracy: float = 0.90
    relation_depth_limit: int = 5
    supported_content_types: list = field(
        default_factory=lambda: ["text", "markdown", "json", "image_desc", "csv"]
    )


@dataclass
class SceneConfig(ConfigMixin):
    spatial_conflict_accuracy: float = 0.95
    max_elements_per_scene: int = 500
    environment_update_interval_sec: float = 1.0
    time_scale: float = 1.0
    weather_transition_duration: float = 30.0


@dataclass
class CharacterConfig(ConfigMixin):
    personality_dimensions: int = 5
    personality_score_range: tuple = (0, 100)
    behavior_consistency_threshold: float = 0.95
    short_term_memory_capacity: int = 100
    long_term_memory_capacity: int = 10000
    emotional_memory_capacity: int = 500
    memory_retrieval_limit: int = 10
    personality_adaptation_rate: float = 0.02

    @classmethod
    def from_dict(cls, data: dict) -> 'CharacterConfig':
        valid_data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "personality_score_range" in valid_data and isinstance(valid_data["personality_score_range"], list):
            valid_data["personality_score_range"] = tuple(valid_data["personality_score_range"])
        return cls(**valid_data)


@dataclass
class NarrativeConfig(ConfigMixin):
    max_branch_depth: int = 10
    core_story_completion_rate: float = 0.85
    elasticity_coefficient: float = 50.0
    deviation_warning_response_sec: float = 1.0
    regression_methods: list = field(
        default_factory=lambda: ["natural", "event_triggered", "forced"]
    )
    branch_merge_enabled: bool = True
    branch_pruning_enabled: bool = True
    elasticity_min: float = 0.0
    elasticity_max: float = 100.0
    elasticity_default: float = 50.0
    branch_weight_core_story: float = 0.4
    branch_weight_character_driven: float = 0.25
    branch_weight_random_event: float = 0.15
    branch_weight_elasticity: float = 0.2
    regression_probability_natural: float = 0.3
    regression_probability_event_triggered: float = 0.7
    regression_probability_forced: float = 1.0
    core_story_min_completion: float = 0.85
    deviation_warning_threshold: float = 0.7
    node_relevance_threshold: float = 0.3
    dead_end_depth_penalty: float = 0.1


@dataclass
class InteractionConfig(ConfigMixin):
    max_concurrent_characters: int = 50
    dialogue_fluency_target: float = 4.0
    relationship_dimensions: list = field(
        default_factory=lambda: ["friendship", "trust", "hostility", "respect"]
    )
    social_rules_enabled: bool = True
    dialogue_max_rounds: int = 50
    context_window_turns: int = 50
    key_info_retention_rate: float = 0.98


@dataclass
class LLMConfig(ConfigMixin):
    sdk_type: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 30.0
    enable_deepseek_optimization: bool = True
    context_compression_threshold: int = 8000
    system_token_budget: int = 300
    fallback_thresholds: Dict[str, int] = field(default_factory=lambda: {
        "degraded": 3,
        "severely_degraded": 5,
        "offline": 10,
    })

    def __post_init__(self):
        if not self.api_key:
            from luqi_engine.core.env import get_api_key
            self.api_key = get_api_key()


@dataclass
class LocalModelConfig(ConfigMixin):
    model_path: str = ""
    classification_threshold: float = 0.85
    export_endpoint: str = ""
    enable_debug_output: bool = True
    max_memory_mb: float = 200.0


@dataclass
class DesireConfig(ConfigMixin):
    desire_dimensions: list = field(
        default_factory=lambda: list(_DESIRE_DEFAULT_DIMENSIONS)
    )
    emotion_trigger_threshold: float = 0.3
    value_system_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "physiological": 0.08,
            "safety": 0.10,
            "belonging": 0.12,
            "esteem": 0.10,
            "self_actualization": 0.10,
            "self_transcendence": 0.05,
            "sight": 0.04,
            "hearing": 0.03,
            "smell": 0.02,
            "taste": 0.02,
            "touch": 0.04,
            "mind": 0.08,
            "relatedness": 0.07,
            "transcendence": 0.03,
            "rootedness": 0.03,
            "identity": 0.03,
            "orientation": 0.02,
        }
    )
    drive_chain_max_depth: int = 5


@dataclass
class MobileConfig(ConfigMixin):
    target_device: str = "snapdragon_695"
    max_memory_mb: float = 2048.0
    max_cpu_percent: float = 70.0
    local_model_memory_mb: float = 200.0
    target_fps: int = 30


@dataclass
class CognitiveMemoryConfig(ConfigMixin):
    sensory_capacity: int = 1000
    working_capacity: int = 9
    short_term_capacity: int = 100
    long_term_capacity: int = 10000
    emotional_capacity: int = 500
    procedural_min_occurrences: int = 5
    procedural_min_success_rate: float = 0.8
    decay_lambda_short: float = 0.01
    decay_lambda_long: float = 0.001
    decay_lambda_emotional: float = 0.003
    decay_mu_importance: float = 0.5
    reinforcement_decay_factor: float = 0.7
    surprise_threshold_high: float = 0.8
    surprise_threshold_medium: float = 0.5
    emotional_surprise_boost: float = 0.3
    consolidation_similarity_threshold: float = 0.85
    consolidation_min_cluster_size: int = 3
    consolidation_interval_seconds: float = 60.0
    retrieval_bm25_weight: float = 0.20
    retrieval_vector_weight: float = 0.70
    retrieval_graph_weight: float = 0.10
    retrieval_limit: int = 10
    vector_model_name: str = "bge-micro-v2"
    vector_dimension: int = 64
    vector_model_path: str = ""
    module_idle_timeout_seconds: float = 300.0
    module_switch_latency_target_ms: float = 100.0
    graph_db_path: str = ""
    shared_memory_enabled: bool = True


@dataclass
class LocalLLMConfig(ConfigMixin):
    local_llm_enabled: bool = False
    local_llm_model_path: str = ""
    local_llm_n_gpu_layers: int = 0
    local_llm_n_ctx: int = 2048
    local_llm_max_tokens: int = 512
    local_llm_temperature: float = 0.7
    local_llm_top_p: float = 0.9
    # 安全选项：是否信任远程代码（仅在可信模型源时启用）
    # 默认禁用，防止远程代码执行攻击
    local_llm_trust_remote_code: bool = False


@dataclass
class IntentClassifierConfig(ConfigMixin):
    simple_max_length: int = 20
    moderate_max_length: int = 100


@dataclass
class ChaosConfig(ConfigMixin):
    sigma: float = 10.0
    rho: float = 28.0
    beta: float = field(default_factory=lambda: 8.0 / 3.0)


@dataclass
class SingleAgentConfig(ConfigMixin):
    token_budget: int = _DEFAULT_TOKEN_BUDGET
    temperature: float = _DEFAULT_AGENT_TEMPERATURE
    mode: str = AgentMode.DEFAULT


@dataclass
class AgentConfig(ConfigMixin):
    dialogue: SingleAgentConfig = field(default_factory=lambda: SingleAgentConfig(
        token_budget=_DIALOGUE_TOKEN_BUDGET, temperature=_DIALOGUE_TEMPERATURE, mode=AgentMode.DEFAULT
    ))
    novel: SingleAgentConfig = field(default_factory=lambda: SingleAgentConfig(
        token_budget=_NOVEL_TOKEN_BUDGET, temperature=_NOVEL_TEMPERATURE, mode=NovelMode.INCREMENTAL
    ))
    critic: SingleAgentConfig = field(default_factory=lambda: SingleAgentConfig(
        token_budget=_CRITIC_TOKEN_BUDGET, temperature=_CRITIC_TEMPERATURE, mode=CriticMode.FULL
    ))
    atmosphere: SingleAgentConfig = field(default_factory=lambda: SingleAgentConfig(
        token_budget=_ATMOSPHERE_TOKEN_BUDGET, temperature=_ATMOSPHERE_TEMPERATURE, mode=AtmosphereMode.LIGHT
    ))

    @classmethod
    def from_dict(cls, data: dict) -> 'AgentConfig':
        valid_data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "dialogue" in valid_data and isinstance(valid_data["dialogue"], dict):
            valid_data["dialogue"] = SingleAgentConfig.from_dict(valid_data["dialogue"])
        if "novel" in valid_data and isinstance(valid_data["novel"], dict):
            valid_data["novel"] = SingleAgentConfig.from_dict(valid_data["novel"])
        if "critic" in valid_data and isinstance(valid_data["critic"], dict):
            valid_data["critic"] = SingleAgentConfig.from_dict(valid_data["critic"])
        if "atmosphere" in valid_data and isinstance(valid_data["atmosphere"], dict):
            valid_data["atmosphere"] = SingleAgentConfig.from_dict(valid_data["atmosphere"])
        return cls(**valid_data)


@dataclass
class NarrativeDocConfig(ConfigMixin):
    quality_level: str = QualityLevel.STANDARD
    max_facts: int = _NARRATIVE_DOC_MAX_FACTS
    max_chapter_depth: int = _NARRATIVE_DOC_MAX_CHAPTER_DEPTH
    max_scene_predictions: int = _NARRATIVE_DOC_MAX_SCENE_PREDICTIONS
    auto_save_interval_seconds: float = _NARRATIVE_DOC_AUTO_SAVE_INTERVAL


@dataclass
class PaceConfig(ConfigMixin):
    fast_threshold: float = _PACE_FAST_THRESHOLD
    slow_threshold: float = _PACE_SLOW_THRESHOLD
    auto_mode_timeout: float = _PACE_AUTO_MODE_TIMEOUT
    pace_window_size: int = _PACE_WINDOW_SIZE


@dataclass
class TrainingConfig(ConfigMixin):
    storage_path: str = _TRAINING_DEFAULT_STORAGE_PATH
    per_character_isolation: bool = True
    quality_threshold: float = _TRAINING_QUALITY_THRESHOLD
    auto_collect: bool = True
    max_samples_per_character: int = _TRAINING_MAX_SAMPLES_PER_CHARACTER


@dataclass
class EngineConfig(ConfigMixin):
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    worldview: WorldViewConfig = field(default_factory=WorldViewConfig)
    scene: SceneConfig = field(default_factory=SceneConfig)
    character: CharacterConfig = field(default_factory=CharacterConfig)
    narrative: NarrativeConfig = field(default_factory=NarrativeConfig)
    interaction: InteractionConfig = field(default_factory=InteractionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    local_model: LocalModelConfig = field(default_factory=LocalModelConfig)
    desire: DesireConfig = field(default_factory=DesireConfig)
    mobile: MobileConfig = field(default_factory=MobileConfig)
    cognitive_memory: CognitiveMemoryConfig = field(default_factory=CognitiveMemoryConfig)
    local_llm: LocalLLMConfig = field(default_factory=LocalLLMConfig)
    chaos: ChaosConfig = field(default_factory=ChaosConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    narrative_doc: NarrativeDocConfig = field(default_factory=NarrativeDocConfig)
    pace: PaceConfig = field(default_factory=PaceConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    seed: Optional[int] = None
    debug_mode: bool = False

    def __post_init__(self) -> None:
        """配置验证：检查关键参数的有效性"""
        # 性能配置验证
        if self.performance.target_fps <= 0 or self.performance.target_fps > 240:
            raise ValueError(f"target_fps must be between 1 and 240, got {self.performance.target_fps}")
        if self.performance.max_cpu_percent <= 0 or self.performance.max_cpu_percent > 100:
            raise ValueError(f"max_cpu_percent must be between 0 and 100, got {self.performance.max_cpu_percent}")
        if self.performance.max_memory_mb <= 0:
            raise ValueError(f"max_memory_mb must be positive, got {self.performance.max_memory_mb}")
        
        # LLM配置验证
        if self.llm.temperature < 0 or self.llm.temperature > 2.0:
            raise ValueError(f"LLM temperature must be between 0 and 2.0, got {self.llm.temperature}")
        if self.llm.max_tokens <= 0:
            raise ValueError(f"LLM max_tokens must be positive, got {self.llm.max_tokens}")
        if self.llm.timeout <= 0:
            raise ValueError(f"LLM timeout must be positive, got {self.llm.timeout}")
        
        # 本地LLM配置验证
        if self.local_llm.local_llm_enabled:
            if not self.local_llm.local_llm_model_path:
                raise ValueError("local_llm_model_path is required when local_llm is enabled")
            if self.local_llm.local_llm_n_ctx <= 0:
                raise ValueError(f"local_llm_n_ctx must be positive, got {self.local_llm.local_llm_n_ctx}")
            if self.local_llm.local_llm_max_tokens <= 0:
                raise ValueError(f"local_llm_max_tokens must be positive, got {self.local_llm.local_llm_max_tokens}")
        
        # 角色配置验证
        if self.character.personality_score_range[0] >= self.character.personality_score_range[1]:
            raise ValueError(f"personality_score_range min must be less than max, got {self.character.personality_score_range}")
        if self.character.short_term_memory_capacity <= 0:
            raise ValueError(f"short_term_memory_capacity must be positive, got {self.character.short_term_memory_capacity}")
        if self.character.long_term_memory_capacity <= 0:
            raise ValueError(f"long_term_memory_capacity must be positive, got {self.character.long_term_memory_capacity}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EngineConfig:
        config = cls()
        if "performance" in data:
            config.performance = PerformanceConfig.from_dict(data["performance"])
        if "worldview" in data:
            config.worldview = WorldViewConfig.from_dict(data["worldview"])
        if "scene" in data:
            config.scene = SceneConfig.from_dict(data["scene"])
        if "character" in data:
            config.character = CharacterConfig.from_dict(data["character"])
        if "narrative" in data:
            config.narrative = NarrativeConfig.from_dict(data["narrative"])
        if "interaction" in data:
            config.interaction = InteractionConfig.from_dict(data["interaction"])
        if "llm" in data:
            config.llm = LLMConfig.from_dict(data["llm"])
        if "local_model" in data:
            config.local_model = LocalModelConfig.from_dict(data["local_model"])
        if "desire" in data:
            config.desire = DesireConfig.from_dict(data["desire"])
        if "mobile" in data:
            config.mobile = MobileConfig.from_dict(data["mobile"])
        if "cognitive_memory" in data:
            config.cognitive_memory = CognitiveMemoryConfig.from_dict(data["cognitive_memory"])
        if "local_llm" in data:
            config.local_llm = LocalLLMConfig.from_dict(data["local_llm"])
        if "chaos" in data:
            config.chaos = ChaosConfig.from_dict(data["chaos"])
        if "agent" in data:
            config.agent = AgentConfig.from_dict(data["agent"])
        if "narrative_doc" in data:
            config.narrative_doc = NarrativeDocConfig.from_dict(data["narrative_doc"])
        if "pace" in data:
            config.pace = PaceConfig.from_dict(data["pace"])
        if "training" in data:
            config.training = TrainingConfig.from_dict(data["training"])
        config.seed = data.get("seed")
        config.debug_mode = data.get("debug_mode", False)
        return config
