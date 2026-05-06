# 大语言模型集成 (LLM)

多适配器LLM桥接、意图分类、Prompt构建和响应解析。

## 模块概览

```
luqi_engine/llm/
├── bridge.py              — LLMBridge 统一LLM接口
├── adapter_registry.py    — AdapterRegistry 适配器注册表
├── openai_adapter.py      — OpenAIAdapter OpenAI接口
├── anthropic_adapter.py   — AnthropicAdapter Anthropic接口
├── local_llm_adapter.py   — LocalLLMAdapter 本地模型适配
├── intent_classifier.py   — IntentClassifier 意图分类器
├── state_renderer.py      — StateRenderer 状态渲染器
├── prompt_builder.py      — PromptBuilder Prompt构建
├── response_parser.py     — ResponseParser 响应解析
├── dialogue_modes.py      — DialogueModes 对话模式
├── fallback.py            — LLMFallback 降级处理
├── deepseek_optimizer.py  — DeepSeekOptimizer DeepSeek优化
└── output_corrector.py    — OutputCorrector 输出校正
```

## LLMBridge — 统一LLM接口 ⭐ 核心

```python
class LLMBridge(ILLMBridge):
    """统一大语言模型桥接接口

    支持功能:
    - complete(): 同步补全
    - generate(): 异步流式生成
    - embed(): 文本向量化 (可选)
    - fallback: 降级处理器
    """

    def __init__(
        self,
        model_name: str = "",
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> None: ...

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """同步补全请求"""

    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> AsyncIterator[LLMStreamChunk]:
        """异步流式生成"""

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """文本向量化 (可选实现)"""

    @property
    def fallback(self) -> LLMFallback:
        """获取降级处理器"""

    @property
    def model_name(self) -> str: ...
    @property
    def is_available(self) -> bool: ...
```

## AdapterRegistry — 适配器注册表

```python
class AdapterRegistry:
    """LLM适配器注册与管理

    内置适配器:
    - openai: OpenAIAdapter (GPT-4/GPT-3.5)
    - anthropic: AnthropicAdapter (Claude)
    - local: LocalLLMAdapter (本地部署)
    """

    def __init__(self) -> None: ...

    def register(self, name: str, adapter_class: Type[Any]) -> None:
        """注册新适配器"""

    def create(
        self,
        name: str,
        **config,
    ) -> LLMBridge:
        """创建适配器实例"""

    def list_available(self) -> List[str]:
        """列出所有已注册适配器"""

    def get_default(self) -> str:
        """获取默认适配器名称"""
```

## IntentClassifier — 意图分类器

```python
class IntentLevel(Enum):
    SINGLE_TURN = "single_turn"       # 单轮对话
    MULTI_TURN_CONTEXT = "multi_turn_context"  # 多轮上下文
    COMMAND = "command"               # 指令/命令
    META_REQUEST = "meta_request"     # 元请求 (切换角色等)


class IntentClassifier:
    """用户输入意图快速分类

    分类规则 (优先级从高到低):
    1. 命令前缀匹配 (/switch /reset /status ...)
    2. 元请求关键词 (切换/选择/帮助)
    3. 上下文引用 (@角色名 / 上次 / 继续)
    4. 默认单轮对话
    """

    def __init__(self, config: Optional[IntentKeywordConfig] = None) -> None: ...

    def classify(
        self,
        user_input: str,
        num_characters: int = 1,
    ) -> IntentLevel:
        """分类用户意图

        Returns:
          IntentLevel 枚举值
        """
```

## StateRenderer — 状态渲染器

```python
@dataclass
class TokenBudgetProfile:
    system_prompt_max: int = 2000
    character_state_max: int = 1500
    narrative_context_max: int = 1000
    world_state_max: int = 500
    recent_history_max: int = 1500


class StateRenderer:
    """引擎状态 → LLM Prompt 渲染

    功能:
    - render_system_prompt(): 系统提示词
    - render_deep_state(): 深度状态 (含心理分析)
    - render_with_token_budget(): Token预算控制渲染
    """

    def __init__(self, budget: Optional[TokenBudgetProfile] = None) -> None: ...

    def render_system_prompt(
        self,
        character: Any,
        world_state: Optional[Dict[str, Any]] = None,
    ) -> str: ...

    def render_deep_state(
        self,
        character: Any,
        include_psychological: bool = True,
    ) -> str: ...

    def render_with_token_budget(
        self,
        character: Any,
        narrative: Any,
        world_view: Any,
        history: List[Dict[str, str]],
        max_tokens: int = 8000,
    ) -> Tuple[str, int]:
        """返回 (prompt内容, 实际token数)"""
```

## ResponseParser — 响应解析

```python
@dataclass
class ParsedAction:
    action: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDialogue:
    content: str
    inner_thought: str = ""
    tone: str = ""


@dataclass
class ParsedEmotionDelta:
    pleasure: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0


@dataclass
class ParsedResponse:
    action: ParsedAction
    dialogue: ParsedDialogue
    emotion_delta: ParsedEmotionDelta
    narrative_signal: str = ""
    raw_text: str = ""


class ResponseParser:
    """LLM原始响应 → 结构化数据解析

    解析流程:
    1. 提取XML标签 <action> <dialogue> <emotion> <signal>
    2. JSON fallback (无标签时尝试JSON解析)
    3. 兜底正则提取
    4. 字段校验与钳制
    """

    def __init__(self) -> None: ...

    def parse(self, raw_response: str) -> ParsedResponse:
        """解析LLM响应为结构化数据"""

    def validate_action(self, action: ParsedAction) -> bool: ...
    def validate_emotion(self, emotion: ParsedEmotionDelta) -> bool: ...
```

## LLMFallback — 降级处理系统

```python
class DegradationLevel(Enum):
    NONE = "none"                   # 无降级
    LOCAL_ONLY = "local_only"       # 仅本地模型
    RULE_BASED = "rule_based"       # 规则模板
    CACHED_RESPONSE = "cached_response"  # 缓存响应
    ECHO = "echo"                   # 回声模式


class AtmosphereDegradationMode(Enum):
    SKIP = "skip"                   # 跳过氛围渲染
    TEMPLATE = "template"           # 使用固定模板
    MINIMAL = "minimal"             # 最简模式


@dataclass
class FallbackStats:
    total_requests: int = 0
    fallback_count: int = 0
    degradation_level: DegradationLevel = DegradationLevel.NONE
    last_fallback_time: float = 0.0
    error_log: List[str] = field(default_factory=list)


class LLMFallback:
    """多级降级处理

    降级链:
      Cloud API失败 → LocalLLMAdapter → RuleBased → Cached → Echo

    氛围降级:
      FULL → MINIMAL → TEMPLATE → SKIP
    """

    def __init__(self, config: Optional[FallbackConfig] = None) -> None: ...

    async def handle_fallback(
        self,
        request: LLMRequest,
        error: Exception,
    ) -> LLMResponse:
        """执行降级处理"""

    def get_current_level(self) -> DegradationLevel: ...
    def get_stats(self) -> FallbackStats: ...
```

## DialogueModes — 对话模式

```python
class DialogueMode(Enum):
    SINGLE = "single"                 # 单角色对话
    MULTI_TURN = "multi_turn"         # 多轮连续
    MULTI_CHARACTER = "multi_character"  # 多角色群聊
    NARRATIVE = "narrative"           # 叙事驱动


@dataclass
class SingleCharacterConfig:
    character_id: str
    max_history Turns: int = 20
    response_style: str = "immersive"


@dataclass
class MultiCharacterConfig:
    character_ids: List[str]
    turn_allocation: TurnAllocation = TurnAllocation.ROUND_ROBIN
    cross_character_awareness: bool = True


class DialogueModes:
    """对话模式配置管理"""

    def __init__(self) -> None: ...

    def set_mode(self, mode: DialogueMode) -> None: ...
    def configure_single(self, config: SingleCharacterConfig) -> None: ...
    def configure_multi(self, config: MultiCharacterConfig) -> None: ...
    def get_mode(self) -> DialogueMode: ...
```

## DeepSeekOptimizer — DeepSeek优化器

```python
@dataclass
class CompressionResult:
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    compressed_text: str
    preserved_keys: List[str]


class DeepSeekOptimizer:
    """基于DeepSeek的长文本压缩优化

    用途:
    - 压缩历史对话以节省token
    - 提取关键信息保留语义
    - 动态压缩比控制
    """

    def __init__(self, model_name: str = "deepseek-chat") -> None: ...

    async def compress(
        self,
        text: str,
        target_ratio: float = 0.5,
        preserve_keys: Optional[List[str]] = None,
    ) -> CompressionResult:
        """压缩文本并返回结果"""
```

## 使用示例

```python
from luqi_engine.llm.bridge import LLMBridge
from luqi_engine.llm.adapter_registry import AdapterRegistry
from luqi_engine.llm.intent_classifier import IntentClassifier, IntentLevel
from luqi_engine.llm.state_renderer import StateRenderer
from luqi_engine.llm.response_parser import ResponseParser

# 注册和使用适配器
registry = AdapterRegistry()
bridge = registry.create("openai", api_key="sk-...", model_name="gpt-4")

# 意图分类
classifier = IntentClassifier()
intent = classifier.classify("/switch 角色2", num_characters=2)
print(f"意图: {intent.name}")  # COMMAND

# 状态渲染
renderer = StateRenderer()
prompt = renderer.render_system_prompt(character=some_char)

# 响应解析
parser = ResponseParser()
parsed = parser.parse("""<action>attack</action>
<dialogue>我不会放过你！</dialogue>
<emotion>pleasure=-0.3 arousal=0.6 dominance=0.4</emotion>""")
print(f"行动: {parsed.action.action}")
print(f"对话: {parsed.dialogue.content}")
```
