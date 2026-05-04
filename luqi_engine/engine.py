"""
LuqiEngine - 鹿栖AI世界基础与角色引擎主入口
三层混合架构整合：LLM核心层 + 算法控制层 + 本地兜底层
四智能体协作数据流：Dialogue → SupremeCourt → Critic → Novelist → Atmosphere → Voice → Assemble
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from luqi_engine.core.config import EngineConfig
from luqi_engine.core.event_bus import EventBus, Event, EventType
from luqi_engine.core.rng import PCGRandom, SeededRNGManager, NarrativeSeedHierarchy
from luqi_engine.core.snapshot import EngineSnapshot, SnapshotError
from luqi_engine.core.types import (
    EntityId, LLMRequest, LLMResponse, LLMStreamChunk,
    CanonicalIR, CriticVerdict, NarrativeDelta, AtmosphereOutput,
    ValidatedIR, ValidatedDelta,
)

from luqi_engine.worldview.renderer import WorldViewRenderer
from luqi_engine.scene.builder import SceneBuilder
from luqi_engine.character.character_manager import CharacterManager
from luqi_engine.narrative.controller import NarrativeController
from luqi_engine.narrative.document import NarrativeDocument
from luqi_engine.interaction.coordinator import InteractionCoordinator

from luqi_engine.llm.bridge import LLMBridge
from luqi_engine.llm.dialogue_modes import DialogueModes, DialogueMode
from luqi_engine.llm.fallback import LLMFallback, DegradationLevel
from luqi_engine.llm.local_llm_adapter import LocalLLMAdapter
from luqi_engine.llm.state_renderer import StateRenderer
from luqi_engine.llm.intent_classifier import IntentClassifier, IntentLevel

from luqi_engine.agents.dialogue_agent import DialogueAgent
from luqi_engine.agents.novelist_agent import NovelistAgent
from luqi_engine.agents.critic_agent import CriticAgent
from luqi_engine.agents.atmosphere_agent import AtmosphereAgent

from luqi_engine.core.supreme_court import AlgorithmSupremeCourt
from luqi_engine.voice.voice_renderer import VoiceRenderer
from luqi_engine.voice.output_assembler import OutputAssembler
from luqi_engine.scheduler.async_scheduler import AsyncTaskScheduler
from luqi_engine.scheduler.gap_precomputer import GapPrecomputer
from luqi_engine.scheduler.auto_mode import AutoModeExecutor
from luqi_engine.scheduler.pace_sensor import PaceSensor
from luqi_engine.training.sample_collector import SampleCollector
from luqi_engine.training.document_protector import DegradationDocumentProtector
from luqi_engine.core.constants import (
    AtmosphereMode,
    CriticMode,
    CriticVerdictType,
    NovelMode,
    PaceLevel,
    AssemblyMode,
    _FALLBACK_CRITIC_CONFIDENCE,
    _MAX_RECENT_FACTS,
    _MS_PER_SECOND,
    _DEFAULT_DOMINANT_EMOTION,
    _DEFAULT_EMOTION_INTENSITY,
    _CACHE_KEY_NOVEL,
)

from luqi_engine.local_model.pipeline import LocalModelPipeline

from luqi_engine.performance.pool import PoolManager
from luqi_engine.performance.resource_manager import ResourceManager

from luqi_engine.orchestration.chat_orchestrator import ChatOrchestrator
from luqi_engine.orchestration.engine_initializer import EngineInitializer
from luqi_engine.orchestration.character_extractor import CharacterExtractor


_ENGINE_VERSION: str = "0.1.0"
_ENGINE_NAME: str = "LuqiAI Engine"

_INIT_PHASE_CONFIG: str = "config"
_INIT_PHASE_CORE: str = "core"
_INIT_PHASE_MODULES: str = "modules"
_INIT_PHASE_LLM: str = "llm"
_INIT_PHASE_LOCAL_MODEL: str = "local_model"
_INIT_PHASE_LOCAL_LLM: str = "local_llm"
_INIT_PHASE_PERFORMANCE: str = "performance"
_INIT_PHASE_COMPLETE: str = "complete"

_LOCAL_LLM_OUTPUT_REQUIREMENTS: str = "第一人称回复，保持角色风格，回复长度50-200字"


_USE_ORCHESTRATOR: bool = True


class LuqiEngine:
    """
    鹿栖AI引擎主入口
    整合三层混合架构：LLM核心层 + 算法控制层 + 本地兜底层
    四智能体协作数据流：Dialogue → SupremeCourt → Critic → Novelist → Atmosphere → Voice → Assemble
    """

    def __init__(self, config: Optional[EngineConfig] = None,
                 config_path: Optional[str] = None,
                 default_snapshot_path: Optional[str] = None) -> None:
        """
        增强版构造函数，支持三种初始化方式：

        方式1: engine = LuqiEngine(config=my_config)           # 传入配置对象
        方式2: engine = LuqiEngine(config_path="config.yaml")   # 从YAML加载
        方式3: engine = LuqiEngine()                            # 全部使用默认值

        优先级：config 参数 > config_path > 默认值
        如果同时传了 config 和 config_path，以 config 为准（config_path 忽略并记录警告）
        """
        self._logger = logging.getLogger(__name__)
        self._config_path: Optional[str] = None

        if config is not None:
            self._config = config
            if config_path is not None:
                self._logger.warning(
                    "同时提供了 config 和 config_path 参数，将忽略 config_path: %s",
                    config_path,
                )
        elif config_path is not None:
            from .core.config_loader import load_config

            try:
                self._config = load_config(config_path)
                self._config_path = config_path
                self._logger.info("从配置文件加载: %s", config_path)
            except Exception as e:
                self._logger.warning("配置文件加载失败，使用默认配置: %s", e)
                self._config = EngineConfig()
        else:
            self._config = EngineConfig()

        self._event_bus = EventBus()
        self._seed_hierarchy: Optional[NarrativeSeedHierarchy] = None
        self._rng_manager: Optional[SeededRNGManager] = None
        self._worldview: Optional[WorldViewRenderer] = None
        self._scene_builder: Optional[SceneBuilder] = None
        self._character_manager: Optional[CharacterManager] = None
        self._narrative_controller: Optional[NarrativeController] = None
        self._interaction_coordinator: Optional[InteractionCoordinator] = None
        self._llm_bridge: Optional[LLMBridge] = None
        self._local_model: Optional[LocalModelPipeline] = None
        self._local_llm_adapter: Optional[LocalLLMAdapter] = None
        self._state_renderer: Optional[StateRenderer] = None
        self._intent_classifier: Optional[IntentClassifier] = None
        self._fallback: Optional[LLMFallback] = None
        self._pool_manager: Optional[PoolManager] = None
        self._resource_manager: Optional[ResourceManager] = None
        self._dialogue_modes: Optional[DialogueModes] = None
        self._initialized: bool = False
        self._init_phases: List[str] = []
        self._default_snapshot_path: Optional[str] = default_snapshot_path

        self._narrative_doc: Optional[NarrativeDocument] = None
        self._dialogue_agent: Optional[DialogueAgent] = None
        self._novelist_agent: Optional[NovelistAgent] = None
        self._critic_agent: Optional[CriticAgent] = None
        self._atmosphere_agent: Optional[AtmosphereAgent] = None
        self._supreme_court: Optional[AlgorithmSupremeCourt] = None
        self._voice_renderer: Optional[VoiceRenderer] = None
        self._output_assembler: Optional[OutputAssembler] = None
        self._scheduler: Optional[AsyncTaskScheduler] = None
        self._precomputer: Optional[GapPrecomputer] = None
        self._auto_mode: Optional[AutoModeExecutor] = None
        self._pace_sensor: Optional[PaceSensor] = None
        self._sample_collector: Optional[SampleCollector] = None
        self._doc_protector: Optional[DegradationDocumentProtector] = None
        self._last_user_message_time: float = 0.0
        self._world_id: Optional[str] = None

        self._orchestrator: Optional[ChatOrchestrator] = None
        self._engine_initializer: EngineInitializer = EngineInitializer(logger=self._logger)
        self._character_extractor: CharacterExtractor = CharacterExtractor()
        self._world_guidance: str = ""
        self._output_corrector = None

    async def initialize(self, snapshot_path: Optional[str] = None, **kwargs) -> None:
        """
        初始化引擎所有子系统
        按依赖顺序加载：配置→核心→模块→LLM→本地模型→本地LLM→性能

        Args:
            snapshot_path: 快照文件路径，提供时优先从快照恢复
            **kwargs: 保留用于未来扩展，保持向后兼容
        """
        if self._initialized:
            return

        if _USE_ORCHESTRATOR:
            await self._engine_initializer.initialize(self, snapshot_path)
            self._create_orchestration_components()
            return

        if snapshot_path is not None:
            self._logger.info("尝试从快照初始化引擎: %s", snapshot_path)
            try:
                self._init_phase(_INIT_PHASE_CONFIG)
                seed = self._config.seed or int(time.time() * _MS_PER_SECOND)
                self._seed_hierarchy = NarrativeSeedHierarchy(root_seed=seed)
                self._rng_manager = SeededRNGManager(master_seed=seed)

                self._init_phase(_INIT_PHASE_CORE)
                self._event_bus.resume()

                self._init_phase(_INIT_PHASE_MODULES)
                self._worldview = WorldViewRenderer()
                self._scene_builder = SceneBuilder(config=self._config.scene)
                self._character_manager = CharacterManager(config=self._config.character)
                scene_rng = self._rng_manager.get_stream("narrative")
                self._narrative_controller = NarrativeController(
                    config=self._config.narrative,
                    rng=scene_rng,
                )
                interaction_rng = self._rng_manager.get_stream("interaction")
                self._interaction_coordinator = InteractionCoordinator(
                    config=self._config.interaction,
                    rng=interaction_rng,
                )

                self.load_snapshot(snapshot_path)
                self._logger.info("引擎从快照成功恢复，跳过完整初始化流程")
                await self._event_bus.publish_async(Event(
                    event_type=EventType.CUSTOM,
                    source="engine",
                    payload={"action": "initialized_from_snapshot", "version": _ENGINE_VERSION},
                ))
                return
            except (SnapshotError, Exception) as exc:
                self._logger.warning(
                    "从快照恢复失败，回退到常规初始化流程: %s", exc
                )
                self._init_phases = []
                self._worldview = None
                self._scene_builder = None
                self._character_manager = None
                self._narrative_controller = None
                self._interaction_coordinator = None
                self._seed_hierarchy = None
                self._rng_manager = None

        self._init_phase(_INIT_PHASE_CONFIG)
        seed = self._config.seed or int(time.time() * _MS_PER_SECOND)
        self._seed_hierarchy = NarrativeSeedHierarchy(root_seed=seed)
        self._rng_manager = SeededRNGManager(master_seed=seed)

        self._init_phase(_INIT_PHASE_CORE)
        self._event_bus.resume()

        self._init_phase(_INIT_PHASE_MODULES)
        self._worldview = WorldViewRenderer()
        self._scene_builder = SceneBuilder(config=self._config.scene)
        self._character_manager = CharacterManager(config=self._config.character)
        scene_rng = self._rng_manager.get_stream("narrative")
        self._narrative_controller = NarrativeController(
            config=self._config.narrative,
            rng=scene_rng,
        )
        interaction_rng = self._rng_manager.get_stream("interaction")
        self._interaction_coordinator = InteractionCoordinator(
            config=self._config.interaction,
            rng=interaction_rng,
        )

        self._init_phase(_INIT_PHASE_LLM)
        self._dialogue_modes = DialogueModes()
        self._fallback = LLMFallback()

        self._init_phase(_INIT_PHASE_LOCAL_LLM)
        self._state_renderer = StateRenderer()
        self._intent_classifier = IntentClassifier()
        self._local_llm_adapter = None
        if self._config.local_llm.local_llm_enabled:
            self._local_llm_adapter = LocalLLMAdapter(
                model_path=self._config.local_llm.local_llm_model_path,
                n_gpu_layers=self._config.local_llm.local_llm_n_gpu_layers,
                n_ctx=self._config.local_llm.local_llm_n_ctx,
                max_tokens=self._config.local_llm.local_llm_max_tokens,
                temperature=self._config.local_llm.local_llm_temperature,
                top_p=self._config.local_llm.local_llm_top_p,
            )
        if self._config.llm.sdk_type == "local_llm" and self._local_llm_adapter is not None:
            self._llm_bridge = LLMBridge(
                config=self._config.llm,
                dialogue_modes=self._dialogue_modes,
                fallback=self._fallback,
                local_llm_adapter=self._local_llm_adapter,
            )
        else:
            self._llm_bridge = LLMBridge(
                config=self._config.llm,
                dialogue_modes=self._dialogue_modes,
                fallback=self._fallback,
            )
        from luqi_engine.llm.output_corrector import OutputCorrector
        self._output_corrector = OutputCorrector(
            adapter=self._llm_bridge,
            config=self._config.llm,
            enabled=True,
        )

        self._init_phase(_INIT_PHASE_LOCAL_MODEL)
        self._local_model = LocalModelPipeline(config=self._config.local_model)

        if self._fallback is not None and self._local_llm_adapter is not None:
            self._fallback.set_local_llm_adapter(
                self._local_llm_adapter,
                self._state_renderer,
            )

        self._init_phase(_INIT_PHASE_PERFORMANCE)
        self._pool_manager = PoolManager(config=self._config.performance)
        self._resource_manager = ResourceManager(
            mobile_config=self._config.mobile,
            perf_config=self._config.performance,
        )

        self._init_phase(_INIT_PHASE_COMPLETE)
        self._initialized = True

        self._narrative_doc = NarrativeDocument(
            document_id=f"narr_{self._world_id or 'default'}",
            world_id=self._world_id or "",
        )
        self._dialogue_agent = DialogueAgent()
        self._novelist_agent = NovelistAgent()
        self._critic_agent = CriticAgent()
        self._atmosphere_agent = AtmosphereAgent()
        self._supreme_court = AlgorithmSupremeCourt()
        self._voice_renderer = VoiceRenderer()
        self._output_assembler = OutputAssembler()
        self._scheduler = AsyncTaskScheduler()
        self._precomputer = GapPrecomputer()
        self._auto_mode = AutoModeExecutor()
        self._pace_sensor = PaceSensor(self._config.pace)
        self._sample_collector = SampleCollector(self._config.training)
        self._doc_protector = DegradationDocumentProtector()

        self._create_orchestration_components()

        await self._event_bus.publish_async(Event(
            event_type=EventType.CUSTOM,
            source="engine",
            payload={"action": "initialized", "version": _ENGINE_VERSION},
        ))

    def save_snapshot(self, path: Optional[str] = None) -> str:
        """
        运行时手动保存快照。

        Args:
            path: 快照保存路径，为None时使用_default_snapshot_path或生成默认路径

        Returns:
            str: 实际保存的文件路径

        Raises:
            RuntimeError: 引擎未初始化时抛出
            SnapshotError: 保存过程中发生错误
        """
        if not self._initialized:
            raise RuntimeError("引擎未初始化，无法保存快照")

        if path is None:
            path = self._default_snapshot_path
        if path is None:
            timestamp = int(time.time() * _MS_PER_SECOND)
            path = f"luqi_engine_snapshot_{timestamp}.json"

        self._logger.info("开始保存引擎快照到: %s", path)
        try:
            saved_path = EngineSnapshot.save(self, path)
            self._logger.info("引擎快照保存成功: %s", saved_path)
            return saved_path
        except SnapshotError:
            raise
        except Exception as exc:
            raise SnapshotError(f"保存快照失败: {exc}") from exc

    def load_snapshot(self, snapshot_path: str) -> None:
        """
        从快照恢复引擎状态。

        Args:
            snapshot_path: 快照文件路径

        Raises:
            SnapshotError: 快照不存在或格式错误
        """
        self._logger.info("开始从快照恢复引擎状态: %s", snapshot_path)
        try:
            data = EngineSnapshot.load(snapshot_path)
        except SnapshotError:
            raise
        except Exception as exc:
            raise SnapshotError(f"加载快照失败: {exc}") from exc

        subsystems = data.get("subsystems", {})
        for key, subsystem_data in subsystems.items():
            subsystem = getattr(self, key, None)
            if subsystem is not None and hasattr(subsystem, "load_snapshot"):
                try:
                    subsystem.load_snapshot(subsystem_data)
                    self._logger.debug("子系统 '%s' 状态已恢复", key)
                except Exception as exc:
                    self._logger.warning("恢复子系统 '%s' 失败: %s", key, exc)

        self._initialized = True
        self._logger.info("引擎状态从快照恢复完成")

    async def shutdown(self) -> None:
        """
        关闭引擎，释放所有资源
        关闭前如果配置了默认快照路径，自动保存快照
        """
        if not self._initialized:
            return

        if self._default_snapshot_path is not None:
            try:
                self.save_snapshot(self._default_snapshot_path)
                self._logger.info("关闭前已自动保存快照: %s", self._default_snapshot_path)
            except (RuntimeError, SnapshotError, Exception) as exc:
                self._logger.warning("关闭前自动保存快照失败（不影响关闭流程）: %s", exc)

        if self._local_llm_adapter is not None:
            self._local_llm_adapter.unload()
        if self._llm_bridge is not None:
            await self._llm_bridge.close()
        self._event_bus.pause()
        self._initialized = False

    async def chat(
        self,
        user_input: str,
        character_id: Optional[str] = None,
    ) -> Any:
        """
        四智能体协作数据流 — Phase 0→6
        Dialogue → SupremeCourt → Critic → Novelist → Atmosphere → Voice → Assemble

        当_USE_ORCHESTRATOR=True时，委托给ChatOrchestrator.orchestrate()
        否则使用原始内联逻辑（回退路径）
        """
        start_time = time.time()

        try:
            self._ensure_initialized()
        except RuntimeError:
            return {"error": "engine_not_initialized", "reply": "引擎未初始化"}

        if self._scheduler is not None:
            try:
                self._scheduler.start_sync()
            except Exception:
                self._logger.warning("AsyncTaskScheduler start_sync 失败，继续执行")

        target_char = self._resolve_character(character_id)
        if target_char is None:
            return {"error": "Character not found", "reply": "角色未找到"}

        now = time.time()
        if self._last_user_message_time > 0 and self._pace_sensor is not None:
            interval = now - self._last_user_message_time
            self._pace_sensor.update_pace(interval)
        self._last_user_message_time = now

        _is_local_llm_fast = (
            getattr(self._config.llm, 'sdk_type', '') == 'local_llm'
            and self._local_llm_adapter is not None
        )

        if _USE_ORCHESTRATOR and self._orchestrator is not None and self._character_extractor is not None:
            result = await self._orchestrator.orchestrate(
                user_input, target_char, _is_local_llm_fast, self._character_extractor,
            )
            result["character_id"] = character_id or ""
            return result

        novel_context: Dict[str, Any] = {}
        critic_context: Dict[str, Any] = {}
        atmosphere_context: Dict[str, Any] = {}

        try:
            dialogue_context = {
                "user_message": user_input,
                "character_name": target_char.name if hasattr(target_char, 'name') else "",
                "personality": self._extract_personality(target_char),
                "emotion_pad": self._extract_emotion_pad(target_char),
                "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
                "recent_exchanges": [],
            }
            canonical_ir = await self._dialogue_agent.run(dialogue_context, self._llm_bridge)
        except Exception as exc:
            self._logger.error("Phase 1 DialogueAgent 失败: %s", exc)
            return {"error": "dialogue_agent_failed", "reply": "对话处理异常"}

        try:
            validated_ir = self._supreme_court.validate_dialogue_ir(
                canonical_ir, target_char, self._narrative_doc
            )
        except Exception as exc:
            self._logger.warning("Phase 2 SupremeCourt 校验失败: %s", exc)
            validated_ir = ValidatedIR(ir=canonical_ir, violations=[], is_clean=True, needs_critic_review=False)

        critic_context: Dict[str, Any] = {}
        critic_verdict = CriticVerdict(verdict=CriticVerdictType.ACCEPT, checks=[], overall_confidence=_FALLBACK_CRITIC_CONFIDENCE, corrections=None)
        novel_delta: Optional[NarrativeDelta] = None
        atmosphere = None
        atm_mode = AtmosphereMode.LIGHT
        pace = PaceLevel.NORMAL

        if not _is_local_llm_fast:
            try:
                critic_context = {
                    "canonical_ir": canonical_ir,
                    "narrative_delta": None,
                    "character_state": self._extract_character_state(target_char),
                    "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
                }
                critic_verdict = await self._critic_agent.run(critic_context, self._llm_bridge, mode=CriticMode.LIGHT)
            except Exception as exc:
                self._logger.warning("Phase 3 CriticAgent 失败: %s", exc)

            if critic_verdict.verdict in (CriticVerdictType.REJECT, CriticVerdictType.MAJOR_REWRITE):
                canonical_ir = self._apply_critic_corrections(canonical_ir, critic_verdict)

            try:
                if self._scheduler is not None:
                    try:
                        self._scheduler.start_responding()
                    except Exception as exc:
                        self._logger.debug("调度器start_responding失败: %s", exc)
                novel_context = {
                    "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
                    "recent_facts": [f.content for f in self._narrative_doc.established_facts[-_MAX_RECENT_FACTS:]] if self._narrative_doc else [],
                    "canonical_ir": canonical_ir,
                    "open_questions": self._narrative_doc.open_questions if self._narrative_doc else [],
                }
                novel_delta = await self._novelist_agent.run(novel_context, self._llm_bridge, mode=NovelMode.INCREMENTAL)
            except Exception as exc:
                self._logger.warning("Phase 4 NovelistAgent 失败: %s", exc)

            try:
                atmosphere_context = {
                    "scene_name": self._narrative_doc.current_scene if self._narrative_doc else "",
                    "dominant_emotion": canonical_ir.emotion_delta.pleasure if canonical_ir.emotion_delta else _DEFAULT_DOMINANT_EMOTION,
                    "emotion_intensity": abs(canonical_ir.emotion_delta.arousal) if canonical_ir.emotion_delta else _DEFAULT_EMOTION_INTENSITY,
                    "characters_present": [target_char.name] if hasattr(target_char, 'name') else [],
                    "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
                }
                atmosphere = await self._atmosphere_agent.run(atmosphere_context, self._llm_bridge, mode=atm_mode)
            except Exception as exc:
                self._logger.warning("Phase 4.5 AtmosphereAgent 失败: %s", exc)

        try:
            if novel_delta is not None and self._supreme_court is not None:
                validated_delta = self._supreme_court.validate_novel_delta(novel_delta, self._narrative_doc)
            else:
                validated_delta = ValidatedDelta(delta=novel_delta, violations=[])
        except Exception as exc:
            self._logger.warning("Phase 4 SupremeCourt Delta 校验失败: %s", exc)
            validated_delta = ValidatedDelta(delta=novel_delta, violations=[])

        try:
            if novel_delta is not None and self._narrative_doc is not None and self._doc_protector is not None:
                is_degraded = (
                    self._fallback is not None
                    and self._fallback.current_level != DegradationLevel.NORMAL
                )
                protected_delta, _protection_report = self._doc_protector.safe_apply_delta(
                    novel_delta,
                    self._narrative_doc.established_facts,
                    self._narrative_doc.current_chapter_outline,
                    is_degraded=is_degraded,
                )
                self._narrative_doc.apply_delta(protected_delta)
        except Exception as exc:
            self._logger.warning("Phase 4 Delta 应用失败: %s", exc)

        if not _is_local_llm_fast:
            pace = self._pace_sensor.get_current_pace() if self._pace_sensor else PaceLevel.NORMAL
            atm_mode = AtmosphereMode.LIGHT if pace in (PaceLevel.FAST, PaceLevel.URGENT) else AtmosphereMode.FULL
            try:
                atmosphere_context = {
                    "scene_name": self._narrative_doc.current_scene if self._narrative_doc else "",
                    "dominant_emotion": canonical_ir.emotion_delta.pleasure if canonical_ir.emotion_delta else _DEFAULT_DOMINANT_EMOTION,
                    "emotion_intensity": abs(canonical_ir.emotion_delta.arousal) if canonical_ir.emotion_delta else _DEFAULT_EMOTION_INTENSITY,
                    "characters_present": [target_char.name] if hasattr(target_char, 'name') else [],
                    "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
                }
                atmosphere = await self._atmosphere_agent.run(atmosphere_context, self._llm_bridge, mode=atm_mode)
            except Exception as exc:
                self._logger.warning("Phase 4.5 AtmosphereAgent 失败: %s", exc)
                atmosphere = None

        try:
            voice_profile = {"name": target_char.name} if hasattr(target_char, 'name') else {}
            dialogue_text = self._voice_renderer.render(canonical_ir, voice_profile, seed=0)
        except Exception as exc:
            self._logger.warning("Phase 5 VoiceRenderer 失败: %s", exc)
            dialogue_text = " ".join(canonical_ir.key_points) if canonical_ir.key_points else user_input

        try:
            final_text = self._output_assembler.assemble_output(dialogue_text, atmosphere, AssemblyMode.WRAP)
        except Exception as exc:
            self._logger.warning("Phase 6 OutputAssembler 失败: %s", exc)
            final_text = dialogue_text

        try:
            if self._sample_collector is not None:
                self._collect_training_sample(
                    user_input, canonical_ir, novel_delta, critic_verdict,
                    atmosphere, validated_ir, final_text,
                )
        except Exception as exc:
            self._logger.warning("训练样本采集失败: %s", exc)

        try:
            if self._scheduler is not None:
                try:
                    self._scheduler.start_async_prep()
                except Exception as exc:
                    self._logger.debug("调度器start_async_prep失败: %s", exc)
                self._start_gap_precomputation(dialogue_context, novel_context, critic_context, atmosphere_context)
                try:
                    self._scheduler.mark_ready()
                except Exception as exc:
                    self._logger.debug("调度器mark_ready失败: %s", exc)
        except Exception as exc:
            self._logger.warning("异步预计算启动失败: %s", exc)

        try:
            if hasattr(target_char, 'emotion') and canonical_ir.emotion_delta:
                target_char.emotion.pleasure += canonical_ir.emotion_delta.pleasure
                target_char.emotion.arousal += canonical_ir.emotion_delta.arousal
                target_char.emotion.dominance += canonical_ir.emotion_delta.dominance
        except Exception as exc:
            self._logger.warning("角色情感更新失败: %s", exc)

        latency_ms = int((time.time() - start_time) * _MS_PER_SECOND)

        return {
            "reply": final_text,
            "character_id": character_id or "",
            "narrative_version": self._narrative_doc.version if self._narrative_doc else 0,
            "atmosphere_mode": atm_mode,
            "critic_verdict": critic_verdict.verdict,
            "validation_clean": validated_ir.is_clean,
            "pace": pace,
            "latency_ms": latency_ms,
        }

    async def chat_stream(
        self,
        character_id: EntityId,
        user_message: str,
        mode: DialogueMode = DialogueMode.MULTI_CHARACTER,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        流式对话 - 三级路由架构
        """
        self._ensure_initialized()
        character = self._character_manager.get_character(character_id) if self._character_manager else None
        if character is None:
            raise ValueError("角色不存在: {}".format(character_id))

        intent_level = self._classify_intent(user_message)

        if intent_level == IntentLevel.MODERATE and self._local_llm_adapter is not None:
            async for chunk in self._chat_stream_via_local_llm(character, user_message, history):
                yield chunk
            return

        if intent_level == IntentLevel.COMPLEX:
            offline = self._intent_classifier.is_offline if self._intent_classifier else False
            if offline and self._local_llm_adapter is not None:
                async for chunk in self._chat_stream_via_local_llm(character, user_message, history):
                    yield chunk
                return

        if self._llm_bridge is None:
            raise RuntimeError("LLM桥接器未初始化")

        from luqi_engine.llm.prompt_builder import PromptContext
        context = self._build_prompt_context(character, mode)
        request = self._llm_bridge.build_request(context, user_message, history)
        from luqi_engine.llm.openai_adapter import _CHINESE_ONLY_GRAMMAR
        request.grammar = _CHINESE_ONLY_GRAMMAR

        from luqi_engine.llm.prompt_builder import _PREFIX_FORCE_TEXT
        prefix_len = len(_PREFIX_FORCE_TEXT)
        raw_text = ""
        prefix_stripped = False
        async for chunk in self._llm_bridge.chat_stream(request):
            if chunk and hasattr(chunk, 'delta') and chunk.delta:
                if not prefix_stripped and chunk.delta.startswith(_PREFIX_FORCE_TEXT):
                    chunk_delta = chunk.delta[prefix_len:]
                    if chunk_delta:
                        raw_text += chunk_delta
                        yield LLMStreamChunk(delta=chunk_delta, finish_reason=chunk.finish_reason if hasattr(chunk, 'finish_reason') else None)
                    prefix_stripped = True
                else:
                    raw_text += chunk.delta
                    yield chunk

        if raw_text:
            truncated = self._truncate_repetition_loop(raw_text)
            if truncated is not None and len(truncated) < len(raw_text):
                self._logger.debug("检测到重复循环，截断 %d→%d 字符", len(raw_text), len(truncated))
                raw_text = truncated
            if self._output_corrector is not None:
                cleaned = self._output_corrector.parse_and_clean(raw_text)
                if cleaned != raw_text:
                    self._logger.debug("后处理清理: %d→%d 字符", len(raw_text), len(cleaned))
                    raw_text = cleaned
                await self._output_corrector.correct(raw_text)

    def _resolve_character(self, character_id: Optional[str]) -> Any:
        if character_id and self._character_manager is not None:
            char = self._character_manager.get_character(character_id)
            if char is not None:
                return char
        if self._character_manager is not None:
            all_chars = self._character_manager.list_characters() if hasattr(self._character_manager, 'list_characters') else []
            if all_chars:
                return self._character_manager.get_character(all_chars[0])
        return None

    @staticmethod
    def _truncate_repetition_loop(text: str) -> Optional[str]:
        if not text or len(text) < 8:
            return None
        import re as _re
        for pattern, min_repeat in [
            (r'(.{2,8})[：:]\s*\1[：:]\s*\1', 3),
            (r'(.{2,10})[，,]\s*\1([，,]\s*\1){1,}', 3),
            (r'(（内心[：:].*?）)\s*\1', 2),
            (r'(.{3,15})\s+\1\s+\1', 3),
        ]:
            match = _re.search(pattern, text)
            if match:
                cutoff = match.start()
                if cutoff > 6:
                    return text[:cutoff]
        for ngram_size in [6, 4]:
            seen: Dict[str, int] = {}
            for i in range(len(text) - ngram_size + 1):
                ngram = text[i:i + ngram_size]
                if ngram in seen:
                    gap = i - seen[ngram]
                    if gap <= ngram_size * 3 and i > ngram_size * 2:
                        return text[:seen[ngram]]
                else:
                    seen[ngram] = i
        return None

    def _apply_critic_corrections(self, ir: CanonicalIR, verdict: CriticVerdict) -> CanonicalIR:
        if verdict.corrections:
            if verdict.corrections.suggested_emotion_delta:
                ir.emotion_delta = verdict.corrections.suggested_emotion_delta
            if verdict.corrections.suggested_action:
                ir.action = verdict.corrections.suggested_action
        return ir

    def _extract_personality(self, character: Any) -> Dict[str, float]:
        if self._character_extractor is not None:
            return self._character_extractor.extract_personality(character)
        if not hasattr(character, 'personality'):
            return {}
        try:
            return {
                "openness": character.personality.get_score("openness"),
                "conscientiousness": character.personality.get_score("conscientiousness"),
                "extraversion": character.personality.get_score("extraversion"),
                "agreeableness": character.personality.get_score("agreeableness"),
                "neuroticism": character.personality.get_score("neuroticism"),
            }
        except Exception:
            return {}

    def _extract_emotion_pad(self, character: Any) -> Dict[str, float]:
        if self._character_extractor is not None:
            return self._character_extractor.extract_emotion_pad(character)
        if not hasattr(character, 'emotion'):
            return {}
        try:
            return {
                "pleasure": character.emotion.pleasure,
                "arousal": character.emotion.arousal,
                "dominance": character.emotion.dominance,
            }
        except Exception:
            return {}

    def _extract_character_state(self, character: Any) -> Dict[str, Any]:
        if self._character_extractor is not None:
            return self._character_extractor.extract_character_state(character)
        state: Dict[str, Any] = {}
        if hasattr(character, 'name'):
            state["name"] = character.name
        if hasattr(character, 'personality'):
            state["personality"] = self._extract_personality(character)
        if hasattr(character, 'emotion'):
            state["emotion_pad"] = self._extract_emotion_pad(character)
        return state

    def _collect_training_sample(
        self,
        user_input: str,
        ir: CanonicalIR,
        delta: Optional[NarrativeDelta],
        verdict: CriticVerdict,
        atmosphere: Optional[AtmosphereOutput],
        validated_ir: ValidatedIR,
        final_text: str,
    ) -> None:
        pass

    def _start_gap_precomputation(
        self,
        dialogue_ctx: Dict[str, Any],
        novel_ctx: Dict[str, Any],
        critic_ctx: Dict[str, Any],
        atm_ctx: Dict[str, Any],
    ) -> None:
        if self._precomputer is None:
            return
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    self._precomputer.run_all_tasks(
                        self._novelist_agent,
                        self._critic_agent,
                        self._dialogue_agent,
                        self._atmosphere_agent,
                        novel_ctx,
                        self._llm_bridge,
                    )
                )
        except Exception as exc:
            self._logger.debug("间隙预计算启动失败（不影响主流程）: %s", exc)

    def _classify_intent(self, user_message: str) -> IntentLevel:
        if self._intent_classifier is None:
            return IntentLevel.COMPLEX
        return self._intent_classifier.classify(user_message)

    async def _chat_via_local_llm(
        self,
        character: Any,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> LLMResponse:
        system_prompt = self._render_system_prompt(character)
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for msg in history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })
        messages.append({"role": "user", "content": user_message})

        request = LLMRequest(
            sdk_type=self._local_llm_adapter.get_sdk_type() if self._local_llm_adapter else None,
            messages=messages,
            temperature=self._config.local_llm.local_llm_temperature,
            max_tokens=self._config.local_llm.local_llm_max_tokens,
        )
        if self._fallback is not None:
            return await self._fallback.get_local_llm_response(request)
        if self._local_llm_adapter is not None:
            return await self._local_llm_adapter.chat(request)
        return LLMResponse(content="", role="assistant", finish_reason="error", usage={}, tokens=0)

    async def _chat_stream_via_local_llm(
        self,
        character: Any,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        system_prompt = self._render_system_prompt(character)
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for msg in history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })
        messages.append({"role": "user", "content": user_message})

        request = LLMRequest(
            sdk_type=self._local_llm_adapter.get_sdk_type() if self._local_llm_adapter else None,
            messages=messages,
            temperature=self._config.local_llm.local_llm_temperature,
            max_tokens=self._config.local_llm.local_llm_max_tokens,
        )
        if self._fallback is not None:
            async for chunk in self._fallback.get_local_llm_stream(request):
                yield chunk
            return
        if self._local_llm_adapter is not None:
            async for chunk in self._local_llm_adapter.chat_stream(request):
                yield chunk

    async def _chat_via_cloud_llm(
        self,
        character: Any,
        user_message: str,
        mode: DialogueMode,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> LLMResponse:
        if self._llm_bridge is None:
            raise RuntimeError("LLM桥接器未初始化")
        context = self._build_prompt_context(character, mode)
        request = self._llm_bridge.build_request(context, user_message, history)
        return await self._llm_bridge.chat(request)

    def _render_system_prompt(self, character: Any) -> str:
        if self._character_extractor is not None:
            return self._character_extractor.render_system_prompt(character)
        if self._state_renderer is None:
            return ""
        personality = {
            "openness": character.personality.get_score("openness"),
            "conscientiousness": character.personality.get_score("conscientiousness"),
            "extraversion": character.personality.get_score("extraversion"),
            "agreeableness": character.personality.get_score("agreeableness"),
            "neuroticism": character.personality.get_score("neuroticism"),
        }
        pad_emotion = {
            "pleasure": character.emotion.pleasure,
            "arousal": character.emotion.arousal,
            "dominance": character.emotion.dominance,
        }
        return self._state_renderer.render_system_prompt(
            character_name=character.name,
            personality=personality,
            pad_emotion=pad_emotion,
            seven_emotions=getattr(character, "seven_emotions", None),
            scene="",
            behavior_instruction="",
            memories=[],
            background=getattr(character, "background", ""),
            output_requirements=_LOCAL_LLM_OUTPUT_REQUIREMENTS,
        )

    def _build_prompt_context(self, character: Any, mode: DialogueMode) -> Any:
        if self._character_extractor is not None:
            return self._character_extractor.build_prompt_context(
                character, mode, self._world_guidance,
            )
        from luqi_engine.llm.prompt_builder import PromptContext
        return PromptContext(
            character_name=character.name,
            personality={
                "openness": character.personality.get_score("openness"),
                "conscientiousness": character.personality.get_score("conscientiousness"),
                "extraversion": character.personality.get_score("extraversion"),
                "agreeableness": character.personality.get_score("agreeableness"),
                "neuroticism": character.personality.get_score("neuroticism"),
            },
            emotion_pad={
                "pleasure": character.emotion.pleasure,
                "arousal": character.emotion.arousal,
                "dominance": character.emotion.dominance,
            },
            dominant_emotion=character.emotion.dominant_emotion if hasattr(character.emotion, 'dominant_emotion') else "neutral",
            memories=[],
            worldview_summary=self._world_guidance,
            narrative_rules=None,
            dialogue_mode_instruction=mode.value if hasattr(mode, 'value') else str(mode),
        )

    async def create_world(
        self,
        raw_content: str,
        content_type: str = "text",
    ) -> Dict[str, Any]:
        """
        从用户输入创建世界观
        """
        self._ensure_initialized()
        if self._worldview is None:
            raise RuntimeError("世界观渲染器未初始化")
        elements = await self._worldview.extract_elements(raw_content, content_type)
        classified = await self._worldview.classify_elements(elements)
        relations = await self._worldview.build_relations(classified)
        conflicts = await self._worldview.detect_conflicts({"classified": classified})
        if conflicts and self._local_model is not None:
            for conflict in conflicts:
                correction = await self._local_model.correct({
                    "conflict": {
                        "id": conflict.conflict_id,
                        "type": conflict.conflict_type,
                        "description": conflict.description,
                    },
                    "classified": classified,
                })
                if correction.get("suggestions"):
                    conflict.suggested_resolutions.extend(correction["suggestions"])
        guidance = await self._worldview.render_guidance({
            "classified": classified,
            "relations": relations,
        })
        self._world_guidance = guidance

        try:
            if self._narrative_doc is not None and self._novelist_agent is not None and self._llm_bridge is not None:
                novel_context = {
                    "narrative_context": str(classified),
                    "recent_facts": [],
                    "open_questions": [],
                }
                novel_delta = await self._novelist_agent.run(novel_context, self._llm_bridge, mode=NovelMode.INCREMENTAL)
                if novel_delta is not None:
                    self._narrative_doc.apply_delta(novel_delta)

            if self._critic_agent is not None and self._llm_bridge is not None:
                critic_context = {
                    "canonical_ir": None,
                    "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
                }
                await self._critic_agent.run(critic_context, self._llm_bridge, mode=CriticMode.LIGHT)

            if self._atmosphere_agent is not None and self._llm_bridge is not None:
                atm_context = {
                    "scene_name": self._narrative_doc.current_scene if self._narrative_doc else "",
                    "dominant_emotion": _DEFAULT_DOMINANT_EMOTION,
                }
                await self._atmosphere_agent.run(atm_context, self._llm_bridge, mode=AtmosphereMode.LIGHT)
        except Exception as exc:
            self._logger.warning("create_world 同步初始化流程失败（不影响世界观创建）: %s", exc)

        return {
            "elements": elements,
            "classified": classified,
            "relations": relations,
            "conflicts": [self._conflict_to_dict(c) for c in conflicts],
            "guidance": guidance,
        }

    async def create_scene(self, scene_config: Dict[str, Any]) -> EntityId:
        """
        创建场景
        """
        self._ensure_initialized()
        if self._scene_builder is None:
            raise RuntimeError("场景构建器未初始化")
        return await self._scene_builder.create_scene(scene_config)

    async def create_character(self, character_config: Dict[str, Any]) -> EntityId:
        """
        创建角色
        """
        self._ensure_initialized()
        if self._character_manager is None:
            raise RuntimeError("角色管理器未初始化")
        char_id = await self._character_manager.create_character(character_config)
        if self._interaction_coordinator is not None:
            character = self._character_manager.get_character(char_id)
            if character is not None:
                self._interaction_coordinator.register_character(
                    char_id,
                    {
                        "name": character.name,
                        "extraversion": character.personality.get_score("extraversion"),
                        "authority_rank": character_config.get("authority_rank", 0),
                    },
                )
        return char_id

    async def start_dialogue(
        self,
        participants: List[EntityId],
        topic: str,
        mode: DialogueMode = DialogueMode.MULTI_CHARACTER,
        max_rounds: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        启动多角色对话
        """
        self._ensure_initialized()
        if self._interaction_coordinator is None:
            raise RuntimeError("交互协调器未初始化")
        if mode == DialogueMode.SINGLE_CHARACTER and len(participants) == 1:
            char_id = participants[0]
            character = self._character_manager.get_character(char_id) if self._character_manager else None
            if character is None:
                return []
            return [{
                "round": 0,
                "speaker_id": char_id,
                "priority_score": 1.0,
                "topic": topic,
                "mode": "single_character",
            }]
        return await self._interaction_coordinator.coordinate_dialogue(
            participants=participants,
            topic=topic,
            max_rounds=max_rounds,
        )

    def get_performance_report(self) -> Dict[str, Any]:
        """
        获取性能报告
        """
        if self._resource_manager is None:
            return {"status": "not_initialized"}
        return self._resource_manager.get_resource_report()

    def get_engine_status(self) -> Dict[str, Any]:
        """
        获取引擎状态
        """
        return {
            "name": _ENGINE_NAME,
            "version": _ENGINE_VERSION,
            "initialized": self._initialized,
            "init_phases": self._init_phases,
            "config": {
                "seed": self._config.seed,
                "debug_mode": self._config.debug_mode,
                "llm_sdk_type": self._config.llm.sdk_type,
                "llm_model": self._config.llm.model,
                "mobile_target": self._config.mobile.target_device,
                "local_llm_enabled": self._config.local_llm.local_llm_enabled,
            },
            "modules": {
                "worldview": self._worldview is not None,
                "scene": self._scene_builder is not None,
                "character": self._character_manager is not None,
                "narrative": self._narrative_controller is not None,
                "interaction": self._interaction_coordinator is not None,
                "llm": self._llm_bridge is not None,
                "local_model": self._local_model is not None,
                "local_llm": self._local_llm_adapter is not None,
                "state_renderer": self._state_renderer is not None,
                "intent_classifier": self._intent_classifier is not None,
                "performance": self._resource_manager is not None,
            },
        }

    @property
    def config(self) -> EngineConfig:
        """返回当前引擎配置（只读访问）"""
        return self._config

    @property
    def config_path(self) -> Optional[str]:
        """返回当前使用的配置文件路径（如果有）"""
        return self._config_path

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def worldview(self) -> Optional[WorldViewRenderer]:
        return self._worldview

    @property
    def scene_builder(self) -> Optional[SceneBuilder]:
        return self._scene_builder

    @property
    def character_manager(self) -> Optional[CharacterManager]:
        return self._character_manager

    @property
    def narrative_controller(self) -> Optional[NarrativeController]:
        return self._narrative_controller

    @property
    def interaction_coordinator(self) -> Optional[InteractionCoordinator]:
        return self._interaction_coordinator

    @property
    def llm_bridge(self) -> Optional[LLMBridge]:
        return self._llm_bridge

    @property
    def local_model(self) -> Optional[LocalModelPipeline]:
        return self._local_model

    @property
    def local_llm_adapter(self) -> Optional[LocalLLMAdapter]:
        return self._local_llm_adapter

    @property
    def state_renderer(self) -> Optional[StateRenderer]:
        return self._state_renderer

    @property
    def intent_classifier(self) -> Optional[IntentClassifier]:
        return self._intent_classifier

    @property
    def resource_manager(self) -> Optional[ResourceManager]:
        return self._resource_manager

    @property
    def pool_manager(self) -> Optional[PoolManager]:
        return self._pool_manager

    def _init_phase(self, phase: str) -> None:
        self._init_phases.append(phase)

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("引擎未初始化，请先调用 initialize()")

    @staticmethod
    def _conflict_to_dict(conflict: Any) -> Dict[str, Any]:
        return {
            "conflict_id": conflict.conflict_id,
            "conflict_type": conflict.conflict_type,
            "description": conflict.description,
            "severity": conflict.severity,
            "involved_entities": conflict.involved_entities,
            "suggested_resolutions": conflict.suggested_resolutions,
        }

    async def __aenter__(self) -> LuqiEngine:
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.shutdown()

    def _create_orchestration_components(self) -> None:
        """创建/更新编排层委托组件（ChatOrchestrator + CharacterExtractor + EngineInitializer）

        _engine_initializer和_character_extractor已在__init__中创建，
        此处仅更新_character_extractor的state_renderer引用并创建_orchestrator
        """
        if self._character_extractor is not None:
            self._character_extractor._state_renderer = self._state_renderer
        self._orchestrator = ChatOrchestrator(
            dialogue_agent=self._dialogue_agent,
            novelist_agent=self._novelist_agent,
            critic_agent=self._critic_agent,
            atmosphere_agent=self._atmosphere_agent,
            supreme_court=self._supreme_court,
            voice_renderer=self._voice_renderer,
            output_assembler=self._output_assembler,
            doc_protector=self._doc_protector,
            llm_bridge=self._llm_bridge,
            narrative_doc=self._narrative_doc,
            scheduler=self._scheduler,
            precomputer=self._precomputer,
            pace_sensor=self._pace_sensor,
            sample_collector=self._sample_collector,
            fallback=self._fallback,
        )
