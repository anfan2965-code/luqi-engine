# 引擎 (Engine)

LuqiEngine 是鹿栖AI引擎的主入口类，整合所有子系统并提供统一的高级API。

## 架构概述

LuqiEngine 采用 **Facade + 委托编排** 模式：

- **LuqiEngine** 作为门面（Facade），对外暴露统一API
- **ChatOrchestrator** 负责 `chat()` 的6阶段流水线编排
- **EngineInitializer** 负责 `initialize()` 的7阶段初始化编排
- **CharacterExtractor** 统一角色信息提取（OCEAN/PAD/状态）
- **_USE_ORCHESTRATOR** 开关控制新旧路径切换，便于灰度发布

```
LuqiEngine (Facade)
  ├── ChatOrchestrator    ← chat() 委托
  ├── EngineInitializer   ← initialize() 委托
  └── CharacterExtractor  ← 角色信息提取委托
```

### 架构权衡记录

| 决策 | 原因 | 风险 | 缓解 |
|------|------|------|------|
| chat()委托给ChatOrchestrator | 原210行10+职责，任何单阶段修改需理解全部代码 | 委托层增加间接调用开销 | _USE_ORCHESTRATOR开关可回退到原始逻辑 |
| initialize()委托给EngineInitializer | 原161行7+职责，快照恢复和常规路径有~40行重复代码 | 快照恢复需完整初始化所有子系统 | _reset_partial_init()确保回退干净 |
| atmosphere_context只构建一次 | 原始代码构建两次(L533-543和L570-584)是BUG | 行为变更 | 修复后更正确，测试覆盖 |
| CharacterExtractor统一提取 | _extract_personality等5方法在3处重复 | 委托增加一层调用 | 边界防御：所有方法对None/缺失属性安全降级 |
| _engine_initializer在__init__创建 | initialize()需要_initializer在初始化前就存在 | 无显著风险 | 仅依赖logger，无重资源 |

## LuqiEngine 主类

::: luqi_engine.engine.LuqiEngine
    options:
      show_root_heading: true
      show_root_toc_entry: true

## 核心方法

### 初始化与生命周期

| 方法 | 说明 | 异步 | 前置条件 | 后置条件 | 可能异常 |
|------|------|------|----------|----------|----------|
| `initialize()` | 初始化所有子系统（委托给EngineInitializer） | ✅ | _config已就绪 | 所有子系统已初始化，_initialized=True | 快照恢复失败时降级到常规初始化 |
| `shutdown()` | 关闭引擎，释放资源 | ✅ | _initialized=True | _initialized=False | 自动保存快照失败不影响关闭 |

### 对话功能

| 方法 | 说明 | 异步 | 前置条件 | 后置条件 | 可能异常 |
|------|------|------|----------|----------|----------|
| `chat()` | 四智能体协作对话（委托给ChatOrchestrator） | ✅ | 引擎已初始化，角色存在 | 返回含reply/character_id/narrative_version等字段的Dict | 引擎未初始化返回error Dict |
| `chat_stream()` | 流式对话（三级路由） | ✅ | 引擎已初始化，角色存在 | AsyncIterator[LLMStreamChunk] | 角色不存在抛ValueError |
| `start_dialogue()` | 多角色交互对话 | ✅ | 引擎已初始化 | List[Dict]含轮次/发言者/优先级 | 交互协调器未初始化抛RuntimeError |

### 世界构建

| 方法 | 说明 | 异步 |
|------|------|------|
| `create_world()` | 从输入创建世界观 | ✅ |
| `create_scene()` | 创建场景 | ✅ |

### 状态与快照

| 方法 | 说明 | 异步 |
|------|------|------|
| `get_engine_status()` | 获取引擎状态 | ❌ |
| `get_performance_report()` | 获取性能报告 | ❌ |
| `save_snapshot()` | 保存快照 | ❌ |
| `load_snapshot()` | 从快照恢复 | ❌ |

## 使用示例

### 基础用法

```python
import asyncio
from luqi_engine.engine import LuqiEngine
from luqi_engine.core.config import EngineConfig

async def main():
    # 创建并初始化引擎
    config = EngineConfig()
    engine = LuqiEngine(config=config)
    await engine.initialize()

    # 创建角色
    char_id = await engine.create_character({
        "name": "小雪",
        "template": "scholar",
    })

    # 对话
    response = await engine.chat(
        character_id=char_id,
        user_message="你好！",
    )
    print(response.content)

    # 查询状态
    status = engine.get_engine_status()
    print(status)

    # 关闭引擎
    await engine.shutdown()

asyncio.run(main())
```

### 使用上下文管理器

```python
import asyncio
from luqi_engine.engine import LuqiEngine

async def main():
    async with LuqiEngine() as engine:
        char_id = await engine.create_character({"name": "AI助手"})
        response = await engine.chat(char_id, "你好")
        print(response.content)

asyncio.run(main())
```

### 从快照恢复

```python
async def restore_engine():
    engine = LuqiEngine()
    await engine.initialize(snapshot_path="backup.json")
    # 引擎已从快照恢复，可以继续使用
    status = engine.get_engine_status()
    print(f"已恢复，角色数: {len(engine.character_manager.list_characters())}")
```

## 三级路由架构

引擎的对话功能采用**三级意图路由**：

```
用户消息 → IntentClassifier.classify()
                ↓
        ┌───────┼────────┐
        ↓       ↓        ↓
     SIMPLE  MODERATE  COMPLEX
        ↓       ↓        ↓
   本地LLM  本地LLM   云端LLM
   (快速)   (中等)   (完整)
```

- **SIMPLE**: 简单问候、短句 → 本地小模型快速响应
- **MODERATE**: 中等复杂度 → 本地模型处理
- **COMPLEX**: 复杂推理、长文本 → 云端大模型（离线时降级到本地）

## 属性访问

引擎提供对所有子系统的属性访问：

```python
engine.character_manager      # CharacterManager 实例
engine.narrative_controller  # NarrativeController 实例
engine.scene_builder         # SceneBuilder 实例
engine.worldview             # WorldViewRenderer 实例
engine.interaction_coordinator  # InteractionCoordinator 实例
engine.llm_bridge            # LLMBridge 实例
engine.state_renderer        # StateRenderer 实例
engine.intent_classifier     # IntentClassifier 实例
engine.config                # EngineConfig 配置对象
engine.event_bus             # EventBus 事件总线
```

## 编排层组件

### ChatOrchestrator

四智能体协作数据流编排器，从LuqiEngine.chat()提取的6阶段流水线。

**6阶段流水线：**
1. Phase 1: DialogueAgent → 生成CanonicalIR
2. Phase 2: SupremeCourt → 校验CanonicalIR
3. Phase 3: CriticAgent → 审查（本地LLM快速路径跳过）
4. Phase 4: NovelistAgent + AtmosphereAgent → 叙事增量+氛围
5. Phase 5: VoiceRenderer → 语音渲染
6. Phase 6: OutputAssembler → 组装最终输出

| 方法 | 说明 | 前置条件 | 后置条件 | 可能异常 |
|------|------|----------|----------|----------|
| `orchestrate()` | 执行完整6阶段流水线 | dialogue_agent/llm_bridge非None | 返回含reply/latency_ms等字段的Dict | 各Phase内部异常被捕获降级 |

**修复记录：** atmosphere_context原构建两次（L533-543和L570-584），现合并为一次。

### EngineInitializer

引擎初始化编排器，从LuqiEngine.initialize()提取的7阶段初始化。

**7阶段初始化：**
1. Seed Hierarchy → 种子层级和RNG管理器
2. Core → 事件总线
3. Modules → 世界观/场景/角色/叙事/交互
4. LLM → 对话模式/降级/桥接/输出校正
5. Local Model → 本地模型管线
6. Performance → 对象池/资源管理
7. Agents & Schedulers → 智能体和调度器

| 方法 | 说明 | 前置条件 | 后置条件 | 可能异常 |
|------|------|----------|----------|----------|
| `initialize()` | 初始化引擎所有子系统 | engine._config已就绪 | engine所有子系统属性已设置 | 快照恢复失败时降级到常规初始化 |

**修复记录：** 快照恢复路径原仅初始化seed/core/modules三层，导致LLM/agents全部为None。现补齐全部初始化步骤后再load_snapshot()。

### CharacterExtractor

角色信息提取器，统一提取OCEAN/PAD/角色状态。

| 方法 | 说明 | 前置条件 | 后置条件 | 可能异常 |
|------|------|----------|----------|----------|
| `extract_personality()` | 提取OCEAN性格分数 | character具有personality属性 | 返回5维OCEAN分数Dict | 缺失字段不包含在返回值中 |
| `extract_emotion_pad()` | 提取PAD情感状态 | character具有emotion属性 | 返回3维PAD Dict | 缺失字段不包含在返回值中 |
| `extract_character_state()` | 提取完整角色状态 | character可以是任意对象 | 返回包含可用字段的Dict | 无异常抛出 |
| `render_system_prompt()` | 渲染本地LLM系统提示词 | state_renderer已初始化 | 返回系统提示词字符串 | state_renderer不可用返回空字符串 |
| `build_prompt_context()` | 构建LLM PromptContext | character具有name/personality/emotion | 返回PromptContext对象 | 无异常抛出 |
