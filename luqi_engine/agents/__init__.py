"""
智能体运行器 - 四智能体（Dialogue / Novelist / Critic / Atmosphere）的统一抽象
每个智能体实现 IAgentRunner 接口，通过 LLM 生成结构化输出
"""

from luqi_engine.agents.dialogue_agent import DialogueAgent
from luqi_engine.agents.novelist_agent import NovelistAgent
from luqi_engine.agents.critic_agent import CriticAgent
from luqi_engine.agents.atmosphere_agent import AtmosphereAgent

__all__ = [
    "DialogueAgent",
    "NovelistAgent",
    "CriticAgent",
    "AtmosphereAgent",
]
