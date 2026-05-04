"""
LuqiAI Engine - 鹿栖AI世界基础与角色引擎
"""

__version__ = "0.1.0"
__author__ = "LuqiAI Team"


def __getattr__(name: str):
    if name == "LuqiEngine":
        from luqi_engine.engine import LuqiEngine
        return LuqiEngine
    if name == "EngineConfig":
        from luqi_engine.core.config import EngineConfig
        return EngineConfig
    raise AttributeError(f"module 'luqi_engine' has no attribute {name!r}")
