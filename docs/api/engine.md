# 引擎门面 (Engine)

LuqiAI引擎的主入口类，整合所有子系统并提供统一的高级API。

> **v1.3.0 更新**: 架构重构为组合模式（非继承），chat()委托给ChatOrchestrator，initialize()委托给EngineInitializer。支持三种初始化方式：配置对象/YAML文件/默认值。

## 架构

```
LuqiEngine (主入口 - 组合模式)
  ├── EngineInitializer      ← initialize() 委托 (7阶段初始化)
  ├── ChatOrchestrator       ← chat() 委托 (6阶段流水线)
  ├── CharacterExtractor     ← 角色信息提取委托
  │
  ├── 子系统实例:
  │   ├── EventBus           — 事件总线
  │   ├── LLMBridge          — LLM桥接器
  │   ├── WorldViewRenderer  — 世界观渲染
  │   ├── SceneBuilder       — 场景构建
  │   ├── CharacterManager   — 角色管理
  │   ├── NarrativeController— 叙事控制器
  │   ├── InteractionCoordinator — 交互协调
  │   ├── LocalModelPipeline — 本地模型管线
  │   ├── LocalLLMAdapter    — 本地LLM适配器
  │   ├── StateRenderer      — 状态渲染器
  │   ├── IntentClassifier   — 意图分类器
  │   ├── LLMFallback        — 降级处理器
  │   ├── PoolManager        — 对象池管理
  │   ├── ResourceManager    — 资源管理
  │   ├── DialogueModes      — 对话模式
  │   ├── AsyncTaskScheduler — 异步任务调度
  │   ├── GapPrecomputer     — 间隔预计算
  │   ├── AutoModeExecutor   — 自动模式执行
  │   ├── PaceSensor         — 节奏传感器
  │   ├── SampleCollector    — 样本采集器
  │   ├── DegradationDocumentProtector — 文档保护器
  │   └── 四智能体:
  │       ├── DialogueAgent
  │       ├── CriticAgent
  │       ├── NovelistAgent
  │       └── AtmosphereAgent
  │
  └── 编排组件:
      ├── AlgorithmSupremeCourt — 算法最高法院
      ├── VoiceRenderer         — 语音渲染
      └── OutputAssembler       — 输出组装
```

## LuqiEngine — 主类

```python
class LuqiEngine:
    """鹿栖AI引擎主入口

    整合三层混合架构: LLM核心层 + 算法控制层 + 本地兜底层
    四智能体协作数据流: Dialogue → SupremeCourt → Critic → Novelist → Atmosphere → Voice → Assemble

    设计模式: 组合模式（非继承），通过委托实现功能解耦
    """

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        config_path: Optional[str] = None,
        default_snapshot_path: Optional[str] = None,
    ) -> None:
        """增强版构造函数，支持三种初始化方式：

        方式1: LuqiEngine(config=my_config)              # 传入配置对象
        方式2: LuqiEngine(config_path="config.yaml")      # 从YAML加载
        方式3: LuqiEngine()                               # 全部使用默认值

        优先级: config参数 > config_path > 默认值
        Args:
            config: EngineConfig配置对象
            config_path: YAML配置文件路径
            default_snapshot_path: 默认快照保存路径
        """

    async def __aenter__(self) -> 'LuqiEngine':
        """异步上下文管理器入口"""

    async def __aexit__(self, *args) -> None:
        """异步上下文管理器出口（自动调用shutdown）"""
```

## 核心API

### 初始化与生命周期

| 方法 | 异步 | 说明 |
|------|------|------|
| `initialize(snapshot_path, **kwargs)` | ✅ | 初始化所有子系统（委托EngineInitializer，支持快照恢复） |
| `shutdown()` | ✅ | 关闭引擎释放资源（自动保存快照如果配置了路径） |
| `save_snapshot(path)` | ❌ | 保存快照到文件（返回实际保存路径） |
| `load_snapshot(snapshot_path)` | ❌/✅ | 从快照恢复引擎状态 |

### 对话功能

| 方法 | 异步 | 说明 |
|------|------|------|
| `chat(user_input, character_id)` | ✅ | 四智能体协作对话（委托ChatOrchestrator.orchestrate） |
| `chat_stream(character_id, user_message, mode, history)` | ✅ | 流式对话（三级路由：SIMPLE→本地/MODERATE→本地/COMPLEX→云端） |
| `start_dialogue(participants, ...)` | ✅ | 多角色交互对话（委托InteractionCoordinator） |

### 世界构建

| 方法 | 异步 | 说明 |
|------|------|------|
| `create_world(raw_content, ...)` | ✅ | 从文本创建世界观（委托WorldViewRenderer.render） |
| `create_scene(scene_config)` | ✅ | 创建场景（委托SceneBuilder） |
| `create_character(char_config)` | ✅ | 创建角色（委托CharacterManager） |

### 性能与诊断

| 方法 | 异步 | 说明 |
|------|------|------|
| `_extract_personality(character)` | ❌ | 提取OCEAN人格5维Dict（委托CharacterExtractor） |
| `_extract_emotion_pad(character)` | ❌ | 提取PAD情感3维Dict（委托CharacterExtractor） |
| `_extract_character_state(character)` | ❌ | 提取完整状态Dict（委托CharacterExtractor） |

## 使用示例

### 基础用法

```python
import asyncio
from luqi_engine.engine import LuqiEngine

async def main():
    async with LuqiEngine() as engine:
        char_id = await engine.create_character({"name": "小雪"})
        response = await engine.chat(char_id, "你好！")
        print(response["content"])

asyncio.run(main())
```

### 从快照恢复

```python
engine = LuqiEngine()
await engine.initialize(snapshot_path="backup.json")
status = engine.get_engine_status()
print(f"已恢复，角色数: {len(status['characters'])}")
```

## 子组件属性访问

```python
engine.character_manager      # CharacterManager → CharacterEntity列表
engine.llm_bridge             # LLMBridge 实例
engine.narrative_controller   # NarrativeEngine 实例
engine.scene_builder          # SceneBuilder 实例
engine.worldview              # WorldViewRenderer 实例
engine.event_bus              # EventBus 事件总线
engine.config                 # EngineConfig 配置对象
```

## 编排层详情

### ChatOrchestrator — 6阶段流水线

```
用户输入
  Phase 1: DialogueAgent     → CanonicalIR (意图/情感/动作)
  Phase 2: SupremeCourt      → 纯算法一致性校验
  Phase 3: CriticAgent       → 质量审查 (可跳过)
  Phase 4: NovelistAgent     → 叙事增量生成
           AtmosphereAgent   → 氛围渲染
  Phase 5: VoiceRenderer     → 语音风格化
  Phase 6: OutputAssembler   → 最终组装输出
```

**降级行为**: 每阶段独立try/except，失败时降级不中断。DEGRADED模式下CriticAgent自动跳过。

### EngineInitializer — 7阶段初始化

```
Phase 1: Seed Hierarchy    → RNG种子层级
Phase 2: Core              → EventBus + Config
Phase 3: Modules           → WorldView/Scene/Character/Narrative/Interaction
Phase 4: LLM               → Bridge/Fallback/Adapter/StateRenderer
Phase 5: Local Model       → Pipeline (离线管线)
Phase 6: Performance       → ObjectPool/ResourceManager
Phase 7: Agents            → 四智能体 + Scheduler
```

### CharacterExtractor — 角色信息提取

| 方法 | 输入 | 输出 |
|------|------|------|
| `extract_personality()` | character | OCEAN 5维Dict |
| `extract_emotion_pad()` | character | PAD 3维Dict |
| `extract_character_state()` | character | 完整状态Dict |
| `render_system_prompt()` | state | System Prompt字符串 |
| `build_prompt_context()` | character | PromptContext对象 |

## 三级意图路由

```
用户消息 → IntentClassifier.classify()
                ↓
        ┌───────┼────────┐
        ↓       ↓        ↓
     SIMPLE  MODERATE  COMPLEX
        ↓       ↓        ↓
   本地模型  本地模型   云端LLM
   (<20字)  (21-100字) (>100字)
```
