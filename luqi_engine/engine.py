"""
LuqiEngine - 鹿栖AI世界基础与角色引擎主入口
路由分发层：继承各模块，统一对外API

架构：
- EngineCore: 初始化、配置、生命周期管理
- EngineChat: 对话功能、流式对话
- EngineWorld: 世界观、场景、角色创建
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional

from luqi_engine.core.config import EngineConfig
from luqi_engine.core.types import EntityId, LLMStreamChunk
from luqi_engine.core.constants import _LOCAL_LLM_OUTPUT_REQUIREMENTS
from luqi_engine.llm.dialogue_modes import DialogueMode

from luqi_engine.engine_core import EngineCore
from luqi_engine.engine_chat import EngineChat
from luqi_engine.engine_world import EngineWorld


class LuqiEngine(EngineCore, EngineChat, EngineWorld):
    """
    鹿栖AI引擎主入口
    路由分发层：继承各模块，统一对外API
    
    继承：
    - EngineCore: 初始化、配置、生命周期管理
    - EngineChat: 对话功能、流式对话
    - EngineWorld: 世界观、场景、角色创建
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
        super().__init__(config=config, config_path=config_path, default_snapshot_path=default_snapshot_path)

    # 以下方法由EngineCore提供：
    # - initialize()
    # - shutdown()
    # - save_snapshot()
    # - load_snapshot()
    # - get_engine_status()
    # - get_performance_report()
    # - config, config_path, event_bus, worldview, scene_builder, character_manager,
    #   narrative_controller, interaction_coordinator, llm_bridge, local_model,
    #   local_llm_adapter, state_renderer, intent_classifier, resource_manager, pool_manager

    # 以下方法由EngineChat提供：
    # - chat()
    # - chat_stream()

    # 以下方法由EngineWorld提供：
    # - create_world()
    # - create_scene()
    # - create_character()
    # - start_dialogue()
