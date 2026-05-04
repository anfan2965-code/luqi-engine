# Phase 4: 独立 AI 模型分层架构

## 概述

鹿栖引擎的 AI 模型架构采用**四智能体协作 + 三级路由 + 编排层委托**的设计：

```
用户输入
    │
    ▼
┌──────────────────────────────────────────────────┐
│              LuqiEngine (Facade)                  │
│                                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │         ChatOrchestrator (编排器)             │  │
│  │                                             │  │
│  │  Phase 1: DialogueAgent    → CanonicalIR    │  │
│  │  Phase 2: SupremeCourt      → ValidatedIR    │  │
│  │  Phase 3: CriticAgent       → CriticVerdict  │  │
│  │  Phase 4: NovelistAgent      → NarrativeDelta│  │
│  │          AtmosphereAgent     → AtmosphereOut │  │
│  │  Phase 5: VoiceRenderer      → VoiceOutput   │  │
│  │  Phase 6: OutputAssembler    → Final Reply   │  │
│  └─────────────────────────────────────────────┘  │
│                                                    │
│  ┌─────────────┐  ┌──────────────────────────┐   │
│  │ EngineInit   │  │ CharacterExtractor        │   │
│  │ (初始化编排) │  │ (角色信息统一提取)          │   │
│  └─────────────┘  └──────────────────────────┘   │
│                                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │         LLM Bridge (三级路由)                │  │
│  │                                             │  │
│  │  SIMPLE   → LocalLLM (Qwen2.5-0.5B GGUF)    │  │
│  │  MODERATE → LocalLLM (Qwen2.5-0.5B GGUF)    │  │
│  │  COMPLEX  → Cloud API (DeepSeek 等)          │  │
│  └─────────────────────────────────────────────┘  │
│                                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │     Degradation Manager (四级降级)            │  │
│  │                                             │  │
│  │  NORMAL → DEGRADED → SEVERE → OFFLINE       │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## 一、四智能体协作架构

### 1.1 数据流总览

```
用户输入(user_input) + 角色(character_id)
    │
    ▼
[Phase 1] DialogueAgent.run(context)
    │  输入: user_input + character_state + narrative_context + world_guidance
    │  输出: CanonicalIR {intent, confidence, emotion_delta, action, key_points, tone, length_hint}
    │
    ▼
[Phase 2] AlgorithmSupremeCourt.validate(canonical_ir)
    │  校验: intent有效性、emotion合理性、action可行性
    │  输出: ValidatedIR {canonical_ir, is_valid, warnings, corrections}
    │  如果校验失败: 自动修正或降级处理
    │
    ▼
[Phase 3] CriticAgent.run(validated_ir, context)
    │  ★ 本地LLM快速路径可跳过此阶段
    │  输出: CriticVerdict {verdict, checks, overall_confidence, corrections}
    │  verdict: ACCEPT / REVISE / REJECT
    │
    ▼
[Phase 4a] NovelistAgent.run(validated_ir, critic_verdict, context)
    │  输出: NarrativeDelta {new_facts: [NewFact(...)]}
    │  新事实: {content, source, timestamp, importance}
    │
    ▼
[Phase 4b] AtmosphereAgent.run(character_state, scene_info)
    │  输出: AtmosphereOutput {environment: AtmosphereEnvironment}
    │  环境: {weather, lighting, sounds, ambient_description}
    │  ★ 注意: atmosphere_context只构建一次（修复原双重构建BUG）
    │
    ▼
[Phase 5] VoiceRenderer.render(final_text, tone, atmosphere)
    │  输出: 渲染后的语音文本（含内心独白括号等风格标记）
    │
    ▼
[Phase 6] OutputAssembler.assemble(all_phase_outputs)
    │  输出: {
    │    reply: str,              // 最终回复文本
    │    character_id: str,       // 角色ID
    │    narrative_version: int,  // 叙事文档版本号
    │    atmosphere_mode: str,    // 氛围模式
    │    critic_verdict: str,     // 审查结论
    │    pace: str,               // 当前节奏
    │    latency_ms: int,         // 响应延迟
    │  }
```

### 1.2 各智能体职责

| 智能体 | 输入 | 输出 | 核心职责 |
|--------|------|------|----------|
| **DialogueAgent** | 用户输入+角色状态+叙事上下文 | CanonicalIR | 意图识别+情感判断+行动提议 |
| **AlgorithmSupremeCourt** | CanonicalIR | ValidatedIR | 一致性校验（规则+算法） |
| **CriticAgent** | ValidatedIR+上下文 | CriticVerdict | 对话质量审查（LLM驱动） |
| **NovelistAgent** | IR+审查结果+上下文 | NarrativeDelta | 叙事增量生成（新事实/剧情推进） |
| **AtmosphereAgent** | 角色状态+场景 | AtmosphereOutput | 氛围渲染（环境描写+感官细节） |
| **VoiceRenderer** | 文本+基调+氛围 | 文本 | 语音风格渲染（内心独白/语气词） |
| **OutputAssembler** | 所有阶段输出 | Dict | 最终响应组装+字段补全 |

### 1.3 SupremeCourt 算法校验

SupremeCourt 是**纯算法**的校验层（不调用LLM），检查内容包括：

- Intent 有效性：意图是否在预定义集合中
- Emotion 合理性：情感增量是否超出合理范围
- Action 可行性：行动是否符合角色当前能力
- Tone 一致性：语调是否与当前情感状态匹配

校验失败时有三种处理策略：ACCEPT（通过）、REVISE（自动修正）、REJECT（降级回退）。

## 二、三级 LLM 路由

### 2.1 路由规则

```
IntentClassifier.classify(user_input)
    │
    ├── SIMPLE (≤20字, 日常寒暄)
    │   └──→ LocalLLMAdapter (Qwen2.5-0.5B GGUF)
    │
    ├── MODERATE (20-100字, 含情感/叙事词)
    │   └──→ LocalLLMAdapter (Qwen2.5-0.5B GGUF)
    │
    └── COMPLEX (>100字, 多角色/世界观/长篇)
        └──→ Cloud API (DeepSeek / OpenAI 兼容)
```

**分类依据**：
- 输入长度阈值
- 32个情感关键词命中
- 16个叙事关键词命中
- 7个多角色指示词命中

### 2.2 LLMBridge 桥接层

LLMBridge 是统一的 LLM 调用抽象，屏蔽底层差异：

```python
class LLMBridge:
    async def chat(messages, mode, options) -> LLMResponse:
        # 根据 mode 选择路由
        # 处理超时/重试/降级
        # 统一错误处理
        # 返回标准化响应
```

**本地 LLM 配置**（LocalLLMConfig）：
- 模型路径: Qwen2.5-0.5B-Instruct GGUF
- 上下文窗口: 默认根据模型配置
- 温度: 可配置
- 最大Token: 可配置

### 2.3 Fallback 降级策略

当首选 LLM 不可用时，自动降级：

```
Cloud API 失败 → 重试 2 次 → 降级到 LocalLLM
LocalLLM 失败 → 重试 2 次 → 降级到模板响应
```

## 三、四级降级容错

### 3.1 降级等级

| 等级 | 名称 | 触发条件 | 行为 |
|------|------|----------|------|
| NORMAL | 正常 | 默认 | 全功能运行 |
| DEGRADED | 降级 | 云端连续3次失败 | 优先本地LLM，探测云端 |
| SEVERELY_DEGRADED | 严重降级 | 降级后累计5次失败 | 仅本地LLM+模板，减少探测频率 |
| OFFLINE | 离线 | 严重降级后10次失败 | 纯本地+模板，30秒一次探测请求 |

### 3.2 恢复机制

- NORMAL ← DEGRADED: 连续2次成功
- DEGRADED ← SEVERE: 可尝试使用本地LLM
- 任何等级都可以尝试一次探测请求来评估云端可用性

**核心原则**：引擎永远不会完全停止响应。

## 四、编排层架构 (Orchestration Layer)

### 4.1 为什么需要编排层？

LuqiEngine 原本是一个**上帝类**（God Class）：
- `chat()` 方法 210 行，承担 10+ 职责
- `initialize()` 方法 161 行，承担 7+ 职责
- 22+ 公共方法，跨越 8+ 领域

这导致：
- 任何单阶段修改需要理解全部代码
- 无法独立测试单个阶段
- 新增智能体必须修改核心类

### 4.2 三个编排组件

#### ChatOrchestrator — 对话编排器

从 LuqiEngine.chat() 提取的 6 阶段流水线：

| 方法 | 职责 |
|------|------|
| `orchestrate()` | 主入口，协调6个阶段 |
| `_phase1_dialogue()` | 调用 DialogueAgent |
| `_phase2_supreme_court()` | 调用 SupremeCourt 校验 |
| `_phase3_critic()` | 调用 CriticAgent（可跳过） |
| `_phase4_novelist/atmosphere()` | 并行/串行调用叙事+氛围 |
| `_phase5_voice()` | 调用 VoiceRenderer |
| `_phase6_assemble()` | 调用 OutputAssembler |
| `_post_orchestrate()` | 训练样本采集 + 预计算 |

**关键修复**：原代码中 atmosphere_context 被构建并执行两次（Phase 4a 和 Phase 4b 各一次），ChatOrchestrator 中合并为一次构建。

#### EngineInitializer — 初始化编排器

从 LuqiEngine.initialize() 提取的 7 阶段初始化：

| 阶段 | 方法 | 内容 |
|------|------|------|
| Stage 1 | `_init_seed_hierarchy()` | 种子层级 + RNG管理器 |
| Stage 2 | `_init_core()` | 事件总线 |
| Stage 3 | `_init_modules()` | 世界观/场景/角色/叙事/交互 |
| Stage 4 | `_init_llm()` | 对话模式/降级/桥接/校正 |
| Stage 5 | `_init_local_model()` | 本地模型管线 |
| Stage 6 | `_init_performance()` | 对象池/资源管理 |
| Stage 7 | `_init_agents_and_schedulers()` | 智能体 + 调度器 |

**关键修复**：快照恢复路径原仅初始化前3层（seed/core/modules），导致 LLM/agents/schedulers 全部为 None。现已补齐全部7个阶段后再 load_snapshot()。

#### CharacterExtractor — 角色信息提取器

统一提取角色信息的组件，消除 engine.py 中 5 个重复方法：

| 方法 | 来源 | 输出 |
|------|------|------|
| `extract_personality()` | engine._extract_personality() | Dict[str, float] OCEAN |
| `extract_emotion_pad()` | engine._extract_emotion_pad() | Dict[str, float] PAD |
| `extract_character_state()` | engine._extract_character_state() | Dict[str, Any] 完整状态 |
| `render_system_prompt()` | engine._render_system_prompt() | str 系统提示词 |
| `build_prompt_context()` | engine._build_prompt_context() | PromptContext LLM上下文 |

**边界防御**：所有方法对 None/缺失属性安全降级，不会因角色对象缺少某属性而崩溃。

### 4.3 灰度发布开关

```python
_USE_ORCHESTRATOR: bool = True
```

- `True`: chat()/initialize() 委托给编排组件
- `False`: 使用原始内联逻辑（回退路径）

这允许在生产环境中逐步切换，一旦发现问题可以立即回退。

## 五、辅助系统

### 5.1 AsyncTaskScheduler 异步任务调度

协调异步任务的调度器：
- start_sync(): 同步启动（chat()中使用）
- 任务队列管理
- 资源池协调

### 5.2 GapPrecomputer 预计算器

在用户思考间隙进行后台预计算：
- 预加载下一轮可能的上下文
- 预计算角色状态变更
- 减少 perceived latency

### 5.3 PaceSensor 节奏感知

追踪用户交互节奏：
- 更新间隔 → pace level (SLOW/NORMAL/FAST/RUSH)
- 影响 LLM temperature 和回复长度

### 5.4 SampleCollector 训练样本采集

收集四智能体的中间产物用于未来训练：

```python
TrainingInput(user_message, narrative_summary)
AgentOutputs(novel, dialogue, critic, atmosphere)
AlgorithmCorrections(...)
FinalOutput(reply_text, executed_action, final_emotion, ...)
```

### 5.5 DegradationDocumentProtector 降级文档保护

在降级模式下保护 NarrativeDocument 不被损坏：
- 降级期间暂停文档版本递增
- 恢复后自动同步

## 六、API 入口

### 6.1 chat()

```python
result = await engine.chat(
    user_input="你好",           # 用户消息（第一参数）
    character_id="char_xxx",     # 角色ID（可选，默认第一个角色）
)
# 返回: Dict 含 reply/character_id/narrative_version/
#       atmosphere_mode/critic_verdict/pace/latency_ms
```

### 6.2 chat_stream()

流式输出，三级路由同样适用。

### 6.3 create_character()

```python
char_id = await engine.create_character({
    "name": "小雪",
    "template": "scholar",       # guard/merchant/scholar/warrior/mage/assassin
})
```

## 七、设计权衡

| 决策 | 原因 | 风险 | 缓解 |
|------|------|------|------|
| 四智能体串行而非并行 | 各阶段依赖前一阶段输出 | 延迟较高 | 本地LLM快速路径跳过Critic |
| 编排层委托 | 降低LuqiEngine复杂度 | 增加一层间接调用 | _USE_ORCHESTRATOR开关回退 |
| atmosphere_context单次构建 | 原代码构建两次是BUG | 行为变更 | 修复后更正确 |
| CharacterExtractor统一提取 | 消除5处重复代码 | 委托增加调用 | 边界防御None安全降级 |
| 快照恢复全7阶段初始化 | 原仅3层导致chat()不可用 | 恢复变慢 | 仅多几ms，换来正确性 |
