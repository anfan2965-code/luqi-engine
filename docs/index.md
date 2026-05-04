# 鹿栖AI引擎 (LuqiAI Engine)

移动优先、离线优先的拟人化对话引擎。四智能体协作架构 + OCEAN人格内化 + Lorenz混沌情感 + 三级LLM路由。

## 快速开始

```python
import asyncio
from luqi_engine.engine import LuqiEngine
from luqi_engine.core.config import EngineConfig

async def main():
    config = EngineConfig()
    engine = LuqiEngine(config=config)

    await engine.initialize()

    char_id = await engine.create_character({
        "name": "小雪",
        "template": "scholar",
    })

    response = await engine.chat(
        user_input="你好！",
        character_id=char_id,
    )

    print(response["reply"])
    await engine.shutdown()

asyncio.run(main())
```

## 核心特性

- 🧠 **四智能体协作** — Dialogue → SupremeCourt → Critic → Novelist → Atmosphere → Voice → Assemble
- 💫 **Lorenz混沌情感引擎** — PAD三维空间 + 七情权重矩阵 + 混沌动力学耦合
- 📖 **OCEAN五维人格内化** — 0-100分制，可量化验证，支持缓慢演化
- 🌍 **动态世界观渲染** — 五步流水线：提取→分类→关联→冲突检测→渲染
- 👥 **GOAP目标导向行动规划** — A*搜索 + 情感/人格驱动的目标选择
- 🔄 **四级降级容错** — NORMAL → DEGRADED → SEVERE → OFFLINE，永不停止响应
- 🎭 **17维欲望向量驱动链** — 情感→欲望→动机排序→GOAP规划→行动执行
- 🔀 **编排层架构** — ChatOrchestrator / EngineInitializer / CharacterExtractor 委托模式

## 架构概览

```
LuqiEngine (Facade 门面)
├── Orchestration (编排层)
│   ├── ChatOrchestrator     — 6阶段对话流水线
│   ├── EngineInitializer    — 7阶段初始化编排
│   └── CharacterExtractor   — 角色信息统一提取
├── Agents (智能体层)
│   ├── DialogueAgent        — 意图识别+情感判断
│   ├── SupremeCourt         — 算法一致性校验
│   ├── CriticAgent          — 对话质量审查
│   ├── NovelistAgent        — 叙事增量生成
│   └── AtmosphereAgent      — 氛围渲染
├── LLM (语言模型层)
│   ├── LLMBridge            — 统一调用抽象
│   ├── LocalLLMAdapter      — 本地模型(Qwen2.5-0.5B)
│   └── IntentClassifier     — 三级路由(SIMPLE/MODERATE/COMPLEX)
└── Core (核心基础设施)
    ├── PCGRandom            — 确定性随机数(PCG-XSH-RR)
    ├── LorenzAttractor       — 混沌动力学(RK4积分)
    ├── DistributionToolkit   — 5种概率分布(零依赖)
    ├── EventBus              — 事件驱动总线
    └── NarrativeSeedHierarchy — 五级种子派生(SHA256)
```

## 模块说明

| 模块 | 说明 | 文档链接 |
|------|------|----------|
| **Engine** | 引擎主类（门面+编排委托） | [API Reference](api/engine.md) |
| **Orchestration** | 编排层（ChatOrchestrator/EngineInitializer/CharacterExtractor） | [API Reference](api/engine.md#编排层组件) |
| **Agents** | 四智能体（Dialogue/Critic/Novelist/Atmosphere） | 见 Phase4 文档 |
| **Character** | OCEAN人格、PAD情感、GOAP规划、DesireEngine、记忆系统 | [API Reference](api/character.md) |
| **LLM** | LLM桥接、三级路由、意图分类、状态渲染 | [API Reference](api/llm.md) |
| **WorldView** | 世界观要素提取、9维分类、Jaccard关联、冲突检测 | [API Reference](api/worldview.md) |
| **Core** | RNG/混沌/分布/事件总线/快照/配置 | [API Reference](api/core.md) |
| **Narrative** | 叙事控制器、活体文档 | [API Reference](api/narrative.md) |
| **Scene** | 场景构建、天气系统 | [API Reference](api/scene.md) |
| **Interaction** | 多角色交互协调、社交关系(弹簧模型) | [API Reference](api/interaction.md) |
| **Config** | 全局配置（12个dataclass） | [API Reference](api/config.md) |

## 设计文档

| 文档 | 内容 |
|------|------|
| [Phase1: 世界观构建体系](../Phase1_世界观构建体系.md) | 要素提取→9维分类→Jaccard关联→冲突检测→渲染输出 |
| [Phase2: 动态动机生成机制](../Phase2_动态动机生成机制.md) | OCEAN→PAD基线→七情映射→DesireEngine→GOAP→效用评分 |
| [Phase3: 随机性控制算法](../Phase3_随机性控制算法.md) | PCG-XSH-RR→多流管理→五级种子→分布工具包→Lorenz混沌 |
| [Phase4: AI模型分层架构](../Phase4_独立AI模型分层架构.md) | 四智能体协作+三级路由+四级降级+编排层架构 |
| [角色/人格/关系链运行机制](./角色人格关系链运行机制.md) | NPC工厂→OCEAN→PAD→七情→关系势能→决策循环→四智能体连接点 |

## API 参考

详见各模块 API 文档。

## 许可证

[MIT License](https://opensource.org/licenses/MIT)
