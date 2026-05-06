# 智能体层 (Agents)

四智能体协作架构的核心组件，负责意图识别、质量审查、叙事生成和氛围渲染。

> **v1.3.0 更新**: 所有智能体实现 `IAgentRunner` 接口，支持统一编排调用。

## 模块概览

```
luqi_engine/agents/
├── dialogue_agent.py     — 对话智能体（意图识别 + 情感判断 + 行动提议）
├── critic_agent.py       — 审查智能体（对话质量审查，可跳过）
├── novelist_agent.py     — 叙事智能体（叙事增量生成）
└── atmosphere_agent.py   — 氛围智能体（环境氛围渲染）
```

## DialogueAgent — 对话智能体

```python
class DialogueAgent(IAgentRunner):
    """将用户输入解析为 CanonicalIR（规范中间表示）

    职责链: context构建 → PromptBuilder → LLM推理(chat) → ResponseParser → CanonicalIR输出
    支持两种模式:
    - 标准模式: 通过LLM解析生成结构化IR
    - LocalLLM直接模式: 跳过JSON解析，直接生成角色台词包装为IR
    降级策略: LLM不可用时返回基于规则的默认CanonicalIR
    """

    def __init__(
        self,
        prompt_builder: Optional[PromptBuilder] = None,
        response_parser: Optional[ResponseParser] = None,
    ) -> None: ...

    async def run(
        self,
        context: Dict[str, Any],
        llm_bridge: Any,
        **kwargs: Any,
    ) -> CanonicalIR:
        """执行对话分析，返回 CanonicalIR 格式的结构化响应

        Args:
            context: Dict 必需字段:
                - user_message: str — 用户输入文本
            context 可选字段:
                - character_name: str — 角色名
                - personality: Dict[str, float] — OCEAN性格
                - emotion_pad: Dict[str, float] — PAD情感
                - memories: List[Dict] — 相关记忆
                - worldview_summary: str — 世界观摘要
                - narrative_rules: List[str] — 叙事规则
                - recent_exchanges: List[Dict] — 近期对话
            llm_bridge: LLMBridge实例（支持get_sdk_type()/chat()）
        Returns:
            CanonicalIR 包含 intent/emotion_delta/action/key_points/tone/length_hint
        """

    async def _run_direct(
        self,
        context: Dict[str, Any],
        llm_bridge: Any,
    ) -> CanonicalIR:
        """LocalLLM直接对话模式：跳过JSON解析，直接生成角色台词
        将自然语言回复包装为CanonicalIR的key_points供下游使用"""

    def get_name(self) -> str:
        """返回智能体名称: 'dialogue'"""

    def get_output_type(self) -> str:
        """返回输出类型: 'CanonicalIR'"""

    @staticmethod
    def _build_fallback_ir(context: Dict[str, Any]) -> CanonicalIR:
        """降级模式：返回规则默认值（intent=unknown, confidence=0.0）"""
```

**输入/输出**:
- 输入: `LLMRequest` (用户消息 + 上下文 + 角色状态)
- 输出: `LLMResponse` 包含 `CanonicalIR` (intent/emotion/action/narrative_signal)

## CriticAgent — 审查智能体

```python
class CriticAgent(IAgentRunner):
    """对话质量审查器，检测OOC、逻辑矛盾、风格漂移

    支持两种运行模式:
    - FULL模式: 6维度全量检查 (consistency/emotion_plausibility/narrative_alignment/character_faithfulness/action_reasonableness/tone_appropriateness)
    - LIGHT模式: 仅2维度快速检查 (consistency/emotion_plausibility)

    可通过配置跳过（性能敏感场景），不影响主流程
    """

    def __init__(
        self,
        prompt_builder: Optional[PromptBuilder] = None,
        response_parser: Optional[ResponseParser] = None,
    ) -> None: ...

    async def run(
        self,
        context: Dict[str, Any],
        llm_bridge: Any,
        mode: CriticMode = CriticMode.FULL,
    ) -> CriticVerdict:
        """执行质量审查，返回 CriticVerdict

        Args:
            context: Dict 必需字段:
                - canonical_ir: Dict — 待审查的CanonicalIR
            context 可选字段:
                - narrative_delta: Dict — 待审查的NarrativeDelta
                - character_state: Dict — 角色当前状态
                - narrative_context: str — 叙事上下文
            llm_bridge: LLMBridge实例
            mode: CriticMode — FULL(全量) / LIGHT(轻量)
        Returns:
            CriticVerdict 包含 verdict/checks/overall_confidence/corrections/override_recommendation
        """

    def get_name(self) -> str:
        """返回智能体名称: 'critic'"""

    def get_output_type(self) -> str:
        """返回输出类型: 'CriticVerdict'"""

    @staticmethod
    def _apply_mode_filter(verdict: CriticVerdict, mode: str) -> CriticVerdict:
        """根据模式过滤CriticVerdict - LIGHT仅保留consistency+emotion_plausibility"""

    @staticmethod
    def _build_fallback_verdict(context: Dict[str, Any], mode: str) -> CriticVerdict:
        """降级模式：默认ACCEPT，置信度降低"""
```

**审查维度**:
| 维度 | 说明 | 阈值 |
|------|------|------|
| OOC检测 | 角色行为是否偏离人设 | 配置可控 |
| 逻辑一致性 | 前后回复是否存在矛盾 | SupremeCourt委托 |
| 风格一致性 | 语言风格是否与角色匹配 | ToneType校验 |

## NovelistAgent — 叙事智能体

```python
class NovelistAgent(IAgentRunner):
    """叙事增量生成器，基于当前剧情上下文生成叙事差量 NarrativeDelta

    支持三种运行模式:
    - FULL_UPDATE模式: 保留全部字段 (new_facts/chapter_update/open_questions/next_prediction)
    - INCREMENTAL模式: 仅保留增量字段 (new_facts + chapter_update + open_questions)
    - PREDICTION_ONLY模式: 仅保留预测字段 (next_prediction)

    与五层叙事引擎(Layer5 StoryArcController)协同工作
    接收 phase_directives + beat_granularity 参数控制输出粒度
    """

    def __init__(
        self,
        prompt_builder: Optional[PromptBuilder] = None,
        response_parser: Optional[ResponseParser] = None,
    ) -> None: ...

    async def run(
        self,
        context: Dict[str, Any],
        llm_bridge: Any,
        **kwargs: Any,
    ) -> NarrativeDelta:
        """执行叙事增量生成，返回 NarrativeDelta

        Args:
            context: Dict 必需字段:
                - narrative_context: str — 当前叙事上下文
            context 可选字段:
                - chapter_outline: Dict — 章节大纲
                - character_arcs: Dict — 角色弧线
                - open_questions: List[str] — 开放问题
                - recent_facts: List[Dict] — 近期事实
                - canonical_ir: Dict — 对话智能体输出
            llm_bridge: LLMBridge实例
            kwargs:
                - mode: str — full_update / incremental / prediction_only
        Returns:
            NarrativeDelta 包含 version/new_facts/chapter_update/open_questions_added/open_questions_resolved/next_prediction/narrative_note
        """

    def get_name(self) -> str:
        """返回智能体名称: 'novelist'"""

    def get_output_type(self) -> str:
        """返回输出类型: 'NarrativeDelta'"""

    @staticmethod
    def _apply_mode_filter(delta: NarrativeDelta, mode: str) -> NarrativeDelta:
        """根据模式过滤NarrativeDelta字段"""

    @staticmethod
    def _build_fallback_delta(context: Dict[str, Any], mode: str) -> NarrativeDelta:
        """降级模式：返回最小有效NarrativeDelta"""
```

## AtmosphereAgent — 氛围智能体

```python
class AtmosphereAgent(IAgentRunner):
    """环境氛围渲染器，生成场景描述和环境感知文本 AtmosphereOutput

    支持两种运行模式:
    - FULL模式: 完整环境渲染 (visual/auditory/olfactory/thermal/spatial + narration + stage_directions + mood)
    - LIGHT模式: 轻量模板拼接 (场景名+情感词模板)

    降级策略: LLM失败时使用模板引擎（Full降级为Light）
    输入来源: SceneResidencyEngine 的 current_scene + weather_system
    支持 AtmosphereMode 枚举切换渲染风格
    """

    def __init__(
        self,
        prompt_builder: Optional[PromptBuilder] = None,
        response_parser: Optional[ResponseParser] = None,
    ) -> None: ...

    async def run(
        self,
        context: Dict[str, Any],
        llm_bridge: Any,
        **kwargs: Any,
    ) -> AtmosphereOutput:
        """执行氛围渲染，返回 AtmosphereOutput

        Args:
            context: Dict 必需字段:
                - scene_name: str — 场景名称
            context 可选字段:
                - dominant_emotion: str — 主导情感
                - emotion_intensity: float — 情感强度
                - characters_present: List[str] — 在场角色
                - narrative_context: str — 叙事上下文
                - time_of_day: str — 时间段
            llm_bridge: LLMBridge实例
            kwargs:
                - mode: str — light / full
        Returns:
            AtmosphereOutput 包含 mode/environment/narration/stage_directions/mood_declaration/suggested_position/length_budget/priority
        """

    def get_name(self) -> str:
        """返回智能体名称: 'atmosphere'"""

    def get_output_type(self) -> str:
        """返回输出类型: 'AtmosphereOutput'"""

    @staticmethod
    def _build_template_output(context: Dict[str, Any], mode: str) -> AtmosphereOutput:
        """模板引擎降级 - Light模式使用场景名+情感词模板拼接"""
```

## 编排调用顺序

```
用户输入
  → DialogueAgent (意图+情感+动作)
  → AlgorithmSupremeCourt (纯算法一致性校验)
  → CriticAgent (质量审查, 可跳过)
  → NovelistAgent (叙事增量)
  → AtmosphereAgent (氛围渲染)
  → OutputAssembler (最终组装)
```

## 降级行为

| 状态 | DialogueAgent | CriticAgent | NovelistAgent | AtmosphereAgent |
|------|--------------|-------------|---------------|-----------------|
| NORMAL | LLM完整推理 | 全量审查 | 增量生成 | 完整渲染 |
| DEGRADED | 缓存+规则回退 | 跳过 | 简化模板 | 基础描述 |
| SEVERE | 纯规则 | 跳过 | 跳过 | 跳过 |
| OFFLINE | 默认IR | 跳过 | 跳过 | 跳过 |

## 相关文档

- [核心接口](core.md) — `IAgentRunner` 接口定义
- [LLM层](llm.md) — `PromptBuilder` / `ResponseParser` / `LLMBridge`
- [叙事引擎](narrative.md) — 五层叙事引擎与NovelistAgent协作
- [引擎门面](engine.md) — `ChatOrchestrator` 编排调度
