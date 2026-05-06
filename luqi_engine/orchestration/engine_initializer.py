"""
EngineInitializer - 引擎初始化编排器
从LuqiEngine.initialize()提取的7阶段初始化逻辑

架构权衡记录：
- 拆分原因：initialize()原161行7+职责，快照恢复路径和常规路径有~40行重复代码
- 合并重复：快照恢复失败后回退到常规初始化时，不再重复代码，而是统一走_init_common_modules()
- 前置条件：LuqiEngine.__init__()已完成，_config已就绪
- 后置条件：所有子系统已初始化，_initialized=True
- 可能异常：快照恢复失败时降级到常规初始化，不抛出异常
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from luqi_engine.core.config import EngineConfig
from luqi_engine.core.event_bus import EventBus, Event, EventType
from luqi_engine.core.rng import PCGRandom, SeededRNGManager, NarrativeSeedHierarchy
from luqi_engine.core.snapshot import EngineSnapshot, SnapshotError
from luqi_engine.core.constants import _MS_PER_SECOND

from luqi_engine.worldview.renderer import WorldViewRenderer
from luqi_engine.scene.builder import SceneBuilder
from luqi_engine.character.character_manager import CharacterManager
from luqi_engine.narrative.controller import NarrativeController
from luqi_engine.narrative.document import NarrativeDocument
from luqi_engine.interaction.coordinator import InteractionCoordinator

from luqi_engine.llm.bridge import LLMBridge
from luqi_engine.llm.dialogue_modes import DialogueModes
from luqi_engine.llm.fallback import LLMFallback
from luqi_engine.llm.local_llm_adapter import LocalLLMAdapter
from luqi_engine.llm.state_renderer import StateRenderer
from luqi_engine.llm.intent_classifier import IntentClassifier

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

from luqi_engine.local_model.pipeline import LocalModelPipeline
from luqi_engine.performance.pool import PoolManager
from luqi_engine.performance.resource_manager import ResourceManager

_ENGINE_VERSION: str = "0.1.0"

_INIT_PHASE_CONFIG: str = "config"
_INIT_PHASE_CORE: str = "core"
_INIT_PHASE_MODULES: str = "modules"
_INIT_PHASE_LLM: str = "llm"
_INIT_PHASE_LOCAL_MODEL: str = "local_model"
_INIT_PHASE_LOCAL_LLM: str = "local_llm"
_INIT_PHASE_PERFORMANCE: str = "performance"
_INIT_PHASE_COMPLETE: str = "complete"


class EngineInitializer:
    """引擎初始化编排器，从LuqiEngine.initialize()提取"""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._init_phases: List[str] = []

    @property
    def init_phases(self) -> List[str]:
        return list(self._init_phases)

    async def initialize(
        self,
        engine: Any,
        snapshot_path: Optional[str] = None,
    ) -> None:
        """
        初始化引擎所有子系统

        前置条件：engine._config已就绪
        后置条件：engine所有子系统属性已设置，engine._initialized=True
        可能异常：快照恢复失败时降级到常规初始化
        """
        if snapshot_path is not None:
            self._logger.info("尝试从快照初始化引擎: %s", snapshot_path)
            if await self._try_snapshot_restore(engine, snapshot_path):
                return
            self._logger.warning("从快照恢复失败，回退到常规初始化流程")
            self._reset_partial_init(engine)

        await self._init_full(engine)

    async def _try_snapshot_restore(
        self, engine: Any, snapshot_path: str
    ) -> bool:
        """
        尝试从快照恢复

        前置条件：snapshot_path非空
        后置条件：成功返回True，失败返回False并清理部分初始化状态

        修复说明：原快照恢复路径仅初始化seed/core/modules三层，
        导致LLM/agents/schedulers全部为None，chat()无法使用。
        现补齐全部初始化步骤后再load_snapshot()，确保子系统对象
        存在后快照数据才能正确恢复到它们上面。
        """
        try:
            self._init_seed_hierarchy(engine)
            self._init_core(engine)
            self._init_modules(engine)
            self._init_llm(engine)
            self._init_local_model(engine)
            self._init_performance(engine)
            self._init_agents_and_schedulers(engine)
            engine.load_snapshot(snapshot_path)
            self._record_phase(_INIT_PHASE_COMPLETE, engine)
            engine._initialized = True
            self._logger.info("引擎从快照成功恢复，跳过完整初始化流程")
            await engine._event_bus.publish_async(Event(
                event_type=EventType.CUSTOM,
                source="engine",
                payload={"action": "initialized_from_snapshot", "version": _ENGINE_VERSION},
            ))
            return True
        except Exception as exc:
            self._logger.warning("快照恢复异常: %s", exc)
            return False

    def _reset_partial_init(self, engine: Any) -> None:
        """重置部分初始化状态（快照恢复失败时调用）"""
        self._init_phases = []
        engine._worldview = None
        engine._scene_builder = None
        engine._character_manager = None
        engine._narrative_controller = None
        engine._interaction_coordinator = None
        engine._seed_hierarchy = None
        engine._rng_manager = None
        engine._dialogue_modes = None
        engine._fallback = None
        engine._state_renderer = None
        engine._intent_classifier = None
        engine._local_llm_adapter = None
        engine._llm_bridge = None
        engine._output_corrector = None
        engine._local_model = None
        engine._pool_manager = None
        engine._resource_manager = None
        engine._narrative_doc = None
        engine._dialogue_agent = None
        engine._novelist_agent = None
        engine._critic_agent = None
        engine._atmosphere_agent = None
        engine._supreme_court = None
        engine._voice_renderer = None
        engine._output_assembler = None
        engine._scheduler = None
        engine._precomputer = None
        engine._auto_mode = None
        engine._pace_sensor = None
        engine._sample_collector = None
        engine._doc_protector = None

    async def _init_full(self, engine: Any) -> None:
        """完整初始化流程"""
        self._init_seed_hierarchy(engine)
        self._init_core(engine)
        self._init_modules(engine)
        self._init_llm(engine)
        self._init_local_model(engine)
        self._init_performance(engine)

        self._record_phase(_INIT_PHASE_COMPLETE, engine)
        engine._initialized = True

        self._init_agents_and_schedulers(engine)

        await engine._event_bus.publish_async(Event(
            event_type=EventType.CUSTOM,
            source="engine",
            payload={"action": "initialized", "version": _ENGINE_VERSION},
        ))

    def _init_seed_hierarchy(self, engine: Any) -> None:
        """初始化种子层级和RNG管理器"""
        self._record_phase(_INIT_PHASE_CONFIG, engine)
        seed = engine._config.seed or int(time.time() * _MS_PER_SECOND)
        engine._seed_hierarchy = NarrativeSeedHierarchy(root_seed=seed)
        engine._rng_manager = SeededRNGManager(master_seed=seed)

    def _init_core(self, engine: Any) -> None:
        """初始化核心事件总线"""
        self._record_phase(_INIT_PHASE_CORE, engine)
        engine._event_bus.resume()

    def _init_modules(self, engine: Any) -> None:
        """初始化核心模块：世界观/场景/角色/叙事/交互"""
        self._record_phase(_INIT_PHASE_MODULES, engine)
        engine._worldview = WorldViewRenderer()
        engine._scene_builder = SceneBuilder(config=engine._config.scene)
        engine._character_manager = CharacterManager(config=engine._config.character)
        scene_rng = engine._rng_manager.get_stream("narrative")
        engine._narrative_controller = NarrativeController(
            config=engine._config.narrative,
            rng=scene_rng,
        )
        interaction_rng = engine._rng_manager.get_stream("interaction")
        engine._interaction_coordinator = InteractionCoordinator(
            config=engine._config.interaction,
            rng=interaction_rng,
        )

    def _init_llm(self, engine: Any) -> None:
        """初始化LLM层：对话模式/降级/桥接/输出校正"""
        self._record_phase(_INIT_PHASE_LLM, engine)
        engine._dialogue_modes = DialogueModes()
        engine._fallback = LLMFallback()

        self._record_phase(_INIT_PHASE_LOCAL_LLM, engine)
        engine._state_renderer = StateRenderer()
        engine._intent_classifier = IntentClassifier()
        engine._local_llm_adapter = None
        if engine._config.local_llm.local_llm_enabled:
            engine._local_llm_adapter = LocalLLMAdapter(
                model_path=engine._config.local_llm.local_llm_model_path,
                n_gpu_layers=engine._config.local_llm.local_llm_n_gpu_layers,
                n_ctx=engine._config.local_llm.local_llm_n_ctx,
                max_tokens=engine._config.local_llm.local_llm_max_tokens,
                temperature=engine._config.local_llm.local_llm_temperature,
                top_p=engine._config.local_llm.local_llm_top_p,
            )
        if engine._config.llm.sdk_type == "local_llm" and engine._local_llm_adapter is not None:
            engine._llm_bridge = LLMBridge(
                config=engine._config.llm,
                dialogue_modes=engine._dialogue_modes,
                fallback=engine._fallback,
                local_llm_adapter=engine._local_llm_adapter,
            )
        else:
            engine._llm_bridge = LLMBridge(
                config=engine._config.llm,
                dialogue_modes=engine._dialogue_modes,
                fallback=engine._fallback,
            )
        from luqi_engine.llm.output_corrector import OutputCorrector
        engine._output_corrector = OutputCorrector(
            adapter=engine._llm_bridge,
            config=engine._config.llm,
            enabled=True,
        )

    def _init_local_model(self, engine: Any) -> None:
        """初始化本地模型管线"""
        self._record_phase(_INIT_PHASE_LOCAL_MODEL, engine)
        engine._local_model = LocalModelPipeline(config=engine._config.local_model)
        if engine._fallback is not None and engine._local_llm_adapter is not None:
            engine._fallback.set_local_llm_adapter(
                engine._local_llm_adapter,
                engine._state_renderer,
            )

    def _init_performance(self, engine: Any) -> None:
        """初始化性能管理层"""
        self._record_phase(_INIT_PHASE_PERFORMANCE, engine)
        engine._pool_manager = PoolManager(config=engine._config.performance)
        engine._resource_manager = ResourceManager(
            mobile_config=engine._config.mobile,
            perf_config=engine._config.performance,
        )

    def _init_agents_and_schedulers(self, engine: Any) -> None:
        """初始化智能体和调度器（无依赖顺序，可批量创建）"""
        engine._narrative_doc = NarrativeDocument(
            document_id=f"narr_{engine._world_id or 'default'}",
            world_id=engine._world_id or "",
        )
        engine._dialogue_agent = DialogueAgent()
        engine._novelist_agent = NovelistAgent()
        engine._critic_agent = CriticAgent()
        engine._atmosphere_agent = AtmosphereAgent()
        engine._supreme_court = AlgorithmSupremeCourt()
        engine._voice_renderer = VoiceRenderer()
        engine._output_assembler = OutputAssembler()
        engine._scheduler = AsyncTaskScheduler()
        engine._precomputer = GapPrecomputer()
        engine._auto_mode = AutoModeExecutor()
        engine._pace_sensor = PaceSensor(engine._config.pace)
        engine._sample_collector = SampleCollector(engine._config.training)
        engine._doc_protector = DegradationDocumentProtector()

    def _record_phase(self, phase: str, engine: Any = None) -> None:
        self._init_phases.append(phase)
        if engine is not None:
            engine._init_phases = list(self._init_phases)
