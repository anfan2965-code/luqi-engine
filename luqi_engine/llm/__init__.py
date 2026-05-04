"""
LLM集成层 - 双SDK适配器（OpenAI/Anthropic）+ DeepSeek调优 + 单/多角色模式
+ LocalLLMAdapter本地推理 + StateRenderer状态渲染 + IntentClassifier意图路由
"""

from luqi_engine.llm.bridge import LLMBridge
from luqi_engine.llm.openai_adapter import OpenAIAdapter
from luqi_engine.llm.anthropic_adapter import AnthropicAdapter
from luqi_engine.llm.deepseek_optimizer import DeepSeekOptimizer, CompressionResult
from luqi_engine.llm.dialogue_modes import (
    DialogueMode,
    DialogueModes,
    MultiCharacterConfig,
    SingleCharacterConfig,
    TurnAllocation,
)
from luqi_engine.llm.prompt_builder import PromptBuilder, PromptContext
from luqi_engine.llm.response_parser import (
    ResponseParser,
    ParsedResponse,
    ParsedAction,
    ParsedDialogue,
    ParsedEmotionDelta,
)
from luqi_engine.llm.fallback import LLMFallback, DegradationLevel, FallbackStats
from luqi_engine.llm.local_llm_adapter import LocalLLMAdapter
from luqi_engine.llm.state_renderer import StateRenderer
from luqi_engine.llm.intent_classifier import IntentClassifier, IntentLevel
from luqi_engine.llm.intent_config import IntentKeywordConfig
from luqi_engine.llm.adapter_registry import AdapterRegistry


def _register_builtin_adapters() -> None:
    registry = AdapterRegistry()
    if not registry.has("openai"):
        registry.register("openai", OpenAIAdapter)
    if not registry.has("anthropic"):
        registry.register("anthropic", AnthropicAdapter)


_register_builtin_adapters()

__all__ = [
    "LLMBridge",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "DeepSeekOptimizer",
    "CompressionResult",
    "DialogueMode",
    "DialogueModes",
    "MultiCharacterConfig",
    "SingleCharacterConfig",
    "TurnAllocation",
    "PromptBuilder",
    "PromptContext",
    "ResponseParser",
    "ParsedResponse",
    "ParsedAction",
    "ParsedDialogue",
    "ParsedEmotionDelta",
    "LLMFallback",
    "DegradationLevel",
    "FallbackStats",
    "LocalLLMAdapter",
    "StateRenderer",
    "IntentClassifier",
    "IntentLevel",
    "IntentKeywordConfig",
    "AdapterRegistry",
]
