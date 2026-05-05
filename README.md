# 鹿栖AI引擎 (LuqiAI Engine)

离线优先的拟人化对话引擎，面向移动端设计。采用**四智能体协作 + 编排层委托 + 三级LLM路由**架构，实现无需持续网络连接的沉浸式角色互动体验。

## 架构概览

```
LuqiEngine (Facade 门面)
│
├── Orchestration (编排层) — 新增
│   ├── ChatOrchestrator     — 6阶段对话流水线编排
│   ├── EngineInitializer    — 7阶段初始化编排
│   └── CharacterExtractor   — 角色信息统一提取
│
├── Agents (智能体层) — 新增
│   ├── DialogueAgent        — 意图识别 + 情感判断 + 行动提议
│   ├── AlgorithmSupremeCourt— 纯算法一致性校验
│   ├── CriticAgent          — 对话质量审查（可跳过）
│   ├── NovelistAgent        — 叙事增量生成
│   └── AtmosphereAgent      — 氛围渲染
│
├── LLM (语言模型层)
│   ├── LLMBridge            — 统一调用抽象
│   ├── LocalLLMAdapter      — 本地模型(Qwen2.5-0.5B GGUF)
│   └── IntentClassifier     — 三级路由(SIMPLE/MODERATE/COMPLEX)
│
└── Core (核心基础设施)
    ├── OCEAN人格向量化(0-100分制)
    ├── Lorenz混沌情感引擎(PAD三维空间)
    ├── GOAP规划器(A*搜索)
    ├── DesireEngine(17维欲望向量)
    ├── PCG-XSH-RR随机数(64位确定性)
    ├── DistributionToolkit(5种分布,零依赖)
    ├── 认知记忆系统(3层简单 + 6层认知)
    ├── EventBus事件总线
    └── NarrativeSeedHierarchy(五级种子派生, SHA-256)
```

## 核心特性

- **四智能体协作** — Dialogue → SupremeCourt → Critic → Novelist → Atmosphere → Voice → Assemble
- **OCEAN五维人格** — 开放性/尽责性/外向性/宜人性/神经质(0-100)，可量化验证，支持缓慢演化
- **Lorenz混沌情感** — PAD三维空间 + 七情权重矩阵 + RK4求解器耦合
- **17维欲望向量** — 情感→欲望→驱动链排序→GOAP规划，饱和度衰减机制
- **GOAP规划器** — A\*搜索(1000节点上限)，PAD/OCEAN驱动的7阈值目标选择
- **认知记忆系统** — 简单3层(SHORT/LONG/EMOTIONAL) + 认知6层(SENSORY/WORKING/SHORT/LONG/EMOTIONAL/PROCEDURAL)，晋升机制(≥3次/≥0.7效价)
- **世界观渲染** — 五步流水线: 提取→9维分类→Jaccard关联→冲突检测→Markdown渲染
- **叙事控制器** — NarrativeDocument活体文档，版本递增
- **场景构建器** — 天气系统 + 场景管理
- **交互协调器** — 弹簧模型关系势能 + ContextFidelity语境保真度
- **四级降级容错** — NORMAL → DEGRADED → SEVERE → OFFLINE，永不停止响应
- **模块化架构** — EngineCore/EngineChat/EngineWorld + ChatOrchestrator/EngineInitializer/CharacterExtractor

## 安装

### 从源码安装

```bash
git clone https://github.com/luqiai/luqi-engine.git
cd luqi-engine
python -m venv env

# Windows:
env\Scripts\activate

# Linux/macOS:
source env/bin/activate

pip install -e .
```

### 开发环境

```bash
pip install -e ".[dev]"
```

## 快速上手

```python
import asyncio
from luqi_engine.engine import LuqiEngine
from luqi_engine.core.config import EngineConfig

async def main():
    config = EngineConfig()
    engine = LuqiEngine(config=config)

    await engine.initialize()

    # 创建角色（6种模板: guard/merchant/scholar/warrior/mage/assassin）
    char_id = await engine.create_character({
        "name": "小雪",
        "template": "scholar",
    })

    # 对话
    result = await engine.chat(
        user_input="你好！今天天气真好",
        character_id=char_id,
    )

    print(result["reply"])           # 最终回复文本
    print(result["latency_ms"])       # 响应延迟(ms)
    print(result["critic_verdict"])   # 审查结论
    print(result["pace"])             # 当前节奏

    await engine.shutdown()

asyncio.run(main())
```

## 配置文件

引擎支持通过 YAML 配置文件进行自定义，无需修改代码。

### 使用方法

**方式一：启动时指定配置文件**
```python
from luqi_engine.engine import LuqiEngine

engine = LuqiEngine(config_path="luqi_engine.yaml")
await engine.initialize()
```

**方式二：程序化配置**
```python
from luqi_engine.engine import LuqiEngine
from luqi_engine.core.config import EngineConfig

config = EngineConfig()
config.llm.model = "deepseek-chat"
config.narrative.max_branch_depth = 15
engine = LuqiEngine(config=config)
await engine.initialize()
```

**方式三：加载后修改**
```python
from luqi_engine.core.config_loader import load_config

config = load_config("luqi_engine.yaml")
config.llm.temperature = 0.9
engine = LuqiEngine(config=config)
await engine.initialize()
```

### 配置文件模板

默认模板位于 `luqi_engine/config/luqi_engine.yaml`，可复制到项目根目录进行自定义。
完整参数说明参见 [API 文档](docs/api/config.md)。

## 项目结构

```
luqi_engine/
├── core/              # 核心基础设施（类型、配置、RNG、混沌、分布、事件总线）
├── orchestration/      # 编排层（ChatOrchestrator/EngineInitializer/CharacterExtractor）
├── agents/            # 智能体（Dialogue/Critic/Novelist/Atmosphere）
├── character/         # 角色系统（OCEAN/PAD/Desire/GOAP/记忆/社交感知）
├── cognitive_memory/  # 认知记忆系统（6层 + MemoryStore）
├── llm/               # LLM集成层（桥接、适配器、降级、意图分类、状态渲染）
├── local_model/       # 本地模型管线（分词、向量化、分类、纠正、安全检查）
├── worldview/         # 世界观渲染器（要素提取/分类/关联/冲突检测）
├── narrative/         # 叙事控制器 + 活体文档
├── scene/             # 场景构建器
├── interaction/       # 交互协调器（TurnScheduler/UserTracker）
├── voice/             # 语音渲染器
├── scheduler/         # 异步任务调度器
├── training/          # 训练样本采集与数据存储
├── performance/       # 性能管理（对象池、资源管理器）
├── config/            # YAML配置模板 + GBNF格式约束
└── tests/             # 测试套件（868项测试）
```

## 测试

```bash
# 全量测试
pytest luqi_engine/tests/ -v

# 仅运行单元测试（排除集成测试）
pytest luqi_engine/tests/ --ignore=luqi_engine/tests/test_engine_integration.py -v

# 运行30轮全链路测试
python test_30round_fullchain.py
```

## 文档

| 文档 | 内容 |
|------|------|
| [API 参考文档](docs/index.md) | 全模块 API 参考 |
| [Phase1: 世界观构建体系](Phase1_世界观构建体系.md) | 要素提取→9维分类→关联→冲突检测 |
| [Phase2: 动态动机生成机制](Phase2_动态动机生成机制.md) | OCEAN→PAD→七情→Desire→GOAP完整链路 |
| [Phase3: 随机性控制算法](Phase3_随机性控制算法.md) | PCG→多流→种子层级→分布工具包→Lorenz混沌 |
| [Phase4: AI模型分层架构](Phase4_独立AI模型分层架构.md) | 四智能体+三级路由+降级+编排层 |
| [角色/人格/关系链运行机制](docs/角色人格关系链运行机制.md) | NPC工厂→决策循环→关系链→四智能体连接点 |
| [宣发文档](docs/鹿栖AI引擎_宣发文档.md) | 技术亮点、竞品对比、市场定位 |

## 许可证

[Apache License 2.0](LICENSE)
