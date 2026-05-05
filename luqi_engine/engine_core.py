"""
EngineCore - 引擎核心模块
负责初始化、配置管理、生命周期管理、属性访问
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from luqi_engine.core.config import EngineConfig
from luqi_engine.core.event_bus import EventBus
from luqi_engine.core.snapshot import EngineSnapshot, SnapshotError
from luqi_engine.core.constants import (
    _ENGINE_VERSION,
    _ENGINE_NAME,
    _SNAPSHOT_FILE_PREFIX,
    _SNAPSHOT_FILE_EXTENSION,
    _MS_PER_SECOND,
)

from luqi_engine.worldview.renderer import WorldViewRenderer
from luqi_engine.scene.builder import SceneBuilder
from luqi_engine.character.character_manager import CharacterManager
from luqi_engine.narrative.controller import NarrativeController
from luqi_engine.narrative.document import NarrativeDocument
from luqi_engine.interaction.coordinator import InteractionCoordinator

from luqi_engine.llm.bridge import LLMBridge
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
from luqi_engine.scheduler.pace_sensor import PaceSensor
from luqi_engine.training.sample_collector import SampleCollector
from luqi_engine.training.document_protector import DegradationDocumentProtector

from luqi_engine.local_model.pipeline import LocalModelPipeline

from luqi_engine.performance.pool import PoolManager
from luqi_engine.performance.resource_manager import ResourceManager

from luqi_engine.orchestration.chat_orchestrator import ChatOrchestrator
from luqi_engine.orchestration.engine_initializer import EngineInitializer
from luqi_engine.orchestration.character_extractor import CharacterExtractor


_logger = logging.getLogger(__name__)


class EngineCore:
    """
    引擎核心模块
    负责初始化、配置管理、生命周期管理、属性访问
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
        
        Args:
            config: 引擎配置对象
            config_path: 配置文件路径
            default_snapshot_path: 默认快照路径
        """
        self._logger = _logger
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
            except FileNotFoundError as exc:
                self._logger.error("配置文件不存在: %s", exc)
                raise
            except PermissionError as exc:
                self._logger.error("配置文件权限错误: %s", exc)
                raise
            except Exception as exc:
                self._logger.error("配置文件加载失败: %s", exc)
                raise
        else:
            self._config = EngineConfig()

        self._event_bus = EventBus()
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

        await self._engine_initializer.initialize(self, snapshot_path)
        self._create_orchestration_components()

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
            except SnapshotError as exc:
                self._logger.error("关闭前自动保存快照失败: %s", exc)
            except Exception as exc:
                self._logger.error("关闭前自动保存快照失败: %s", exc)

        if self._local_llm_adapter is not None:
            self._local_llm_adapter.unload()
        if self._llm_bridge is not None:
            await self._llm_bridge.close()
        self._event_bus.pause()
        self._initialized = False

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
            path = f"{_SNAPSHOT_FILE_PREFIX}{timestamp}{_SNAPSHOT_FILE_EXTENSION}"

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

    def get_engine_status(self) -> Dict[str, Any]:
        """
        获取引擎状态
        
        Returns:
            引擎状态Dict
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

    def get_performance_report(self) -> Dict[str, Any]:
        """
        获取性能报告
        
        Returns:
            性能报告Dict
        """
        if self._resource_manager is None:
            return {"status": "not_initialized"}
        return self._resource_manager.get_resource_report()

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
        """返回事件总线"""
        return self._event_bus

    @property
    def worldview(self) -> Optional[WorldViewRenderer]:
        """返回世界观渲染器"""
        return self._worldview

    @property
    def scene_builder(self) -> Optional[SceneBuilder]:
        """返回场景构建器"""
        return self._scene_builder

    @property
    def character_manager(self) -> Optional[CharacterManager]:
        """返回角色管理器"""
        return self._character_manager

    @property
    def narrative_controller(self) -> Optional[NarrativeController]:
        """返回叙事控制器"""
        return self._narrative_controller

    @property
    def interaction_coordinator(self) -> Optional[InteractionCoordinator]:
        """返回交互协调器"""
        return self._interaction_coordinator

    @property
    def llm_bridge(self) -> Optional[LLMBridge]:
        """返回LLM桥接器"""
        return self._llm_bridge

    @property
    def local_model(self) -> Optional[LocalModelPipeline]:
        """返回本地模型管线"""
        return self._local_model

    @property
    def local_llm_adapter(self) -> Optional[LocalLLMAdapter]:
        """返回本地LLM适配器"""
        return self._local_llm_adapter

    @property
    def state_renderer(self) -> Optional[StateRenderer]:
        """返回状态渲染器"""
        return self._state_renderer

    @property
    def intent_classifier(self) -> Optional[IntentClassifier]:
        """返回意图分类器"""
        return self._intent_classifier

    @property
    def resource_manager(self) -> Optional[ResourceManager]:
        """返回资源管理器"""
        return self._resource_manager

    @property
    def pool_manager(self) -> Optional[PoolManager]:
        """返回对象池管理器"""
        return self._pool_manager

    def _init_phase(self, phase: str) -> None:
        """
        记录初始化阶段
        
        Args:
            phase: 阶段名称
        """
        self._init_phases.append(phase)

    def _ensure_initialized(self) -> None:
        """
        确保引擎已初始化
        
        Raises:
            RuntimeError: 引擎未初始化
        """
        if not self._initialized:
            raise RuntimeError("引擎未初始化，请先调用 initialize()")

    async def __aenter__(self) -> EngineCore:
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        """异步上下文管理器出口"""
        await self.shutdown()

    def _create_orchestration_components(self) -> None:
        """创建/更新编排层委托组件（ChatOrchestrator + CharacterExtractor + EngineInitializer）

        _engine_initializer和_character_extractor已在__init__中创建，
        此处仅更新_character_extractor的state_renderer引用并创建_orchestrator
        """
        self._character_extractor.set_state_renderer(self._state_renderer)
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
