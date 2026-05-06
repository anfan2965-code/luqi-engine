# 鹿栖AI引擎 (LuqiAI Engine) v1.3.0.12-Beta

离线优先的拟人化对话引擎，面向移动端设计。采用**四智能体协作 + 编排层委托 + 三级LLM路由 + 五层叙事引擎**架构，实现无需持续网络连接的沉浸式角色互动体验。

## 架构概览

```
LuqiEngine (Facade 门面)
│
├── Orchestration (编排层)
│   ├── ChatOrchestrator     — 6阶段对话流水线编排
│   ├── EngineInitializer    — 7阶段初始化编排
│   └── CharacterExtractor   — 角色信息统一提取
│
├── Agents (智能体层)
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
├── Narrative Engine (五层叙事引擎) ★ v1.3.0 新增
│   ├── Layer5: StoryArcController  — 叙事弧(起承转合) + Storyform均衡 + Dramatis悬念
│   ├── Layer4: PlotThreadManager   — 主线/支线/涌现线程管理 + Storylet触发
│   ├── Layer3: SceneResidencyEngine— 场景驻留 + Beat序列 + 动态粒度算法
│   ├── Layer2: CharacterStratifier — 角色分层(核心/活跃/背景) + 分组轮换
│   └── Layer1: EmergenceDetector   — 涌现检测(SI/CS/II三指标) 三方案+自定义
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

┌─────────────────────────────────────────────┐
│         Stress Tests (压力测试模块)          │
│  stress_tests/wuxia_war/                    │
│  ├── world.py           — 80维武侠世界观     │
│  ├── character_pool.py  — 620+角色池         │
│  ├── narrative_engine.py— 五层叙事引擎       │
│  ├── wuxia_runner.py    — 无限轮次对话主循环  │
│  └── run_wuxia.py       — 运行入口           │
└─────────────────────────────────────────────┘
```

## 核心特性

### 基础引擎特性

- **四智能体协作** — Dialogue → SupremeCourt → Critic → Novelist → Atmosphere → Voice → Assemble
- **OCEAN五维人格** — 开放性/尽责性/外向性/宜人性/神经质(0-100)，可量化验证，支持缓慢演化
- **Lorenz混沌情感** — PAD三维空间 + 七情权重矩阵 + RK4求解器耦合
- **17维欲望向量** — 情感→欲望→驱动链排序→GOAP规划，饱和度衰减机制
- **GOAP规划器** — A\*搜索(1000节点上限)，PAD/OCEAN驱动的7阈值目标选择
- **认知记忆系统** — 简单3层(SHORT/LONG/EMOTIONAL) + 认知6层(SENSORY/WORKING/SHORT/LONG/EMOTIONAL/PROCEDURAL)，晋升机制(≥3次/≥0.7效价)
- **世界观渲染** — 五步流水线: 提取→9维分类→Jaccard关联→冲突检测→Markdown渲染
- **场景构建器** — 天气系统 + 场景管理
- **交互协调器** — 弹簧模型关系势能 + ContextFidelity语境保真度
- **四级降级容错** — NORMAL → DEGRADED → SEVERE → OFFLINE，永不停止响应

### v1.3.0 新增：五层叙事引擎

- **Layer1 涌现检测** — MACIE论文SI/CS/II指标体系，三预选方案(保守/均衡/激进)+完全自定义接口
- **Layer2 角色分层** — 核心/活跃/背景三层动态升降，突出度衰减+事件提升机制，阵营分组轮换
- **Layer3 场景驻留** — Beat序列管理，**动态Beat粒度算法**(主线张力60%+支线张力40%→1~4轮/Beat)，冲突感知驻留决策
- **Layer4 剧情线程** — 主线5剧情点(杀父线索→朝廷阴谋→门派背叛→真相大白→最终决战)，Storylet自然语言条件触发，涌现信号自动注册支线
- **Layer5 叙事弧控制** — 起承转合四阶段生命周期，Storyform核心不平等均衡算法(5维度加权)，Dramatis悬念模型(逃生计划数驱动)

### v1.3.0 新增：武侠战争压力测试模块

- **80维角色状态体系** — 武术域12维+人格域10维+社交域8维+战斗域8维+资源域6维+信念域6维+额外30维
- **620+角色支持** — 6级角色层级(传说~凡人)，18种角色模板，中文姓名生成(含表字)
- **142个场景模板** — 7大类别(城镇/寺庙/山林/宫殿/战场/秘境/中立)，容量和层级约束
- **52个地理位置点** — 区域类型(门派领地/中立区/边境/隐藏地)，距离计算和邻近查询
- **无限轮次对话循环** — LLM集成、动作分类(OOC检测)、7种事件类型、7种结局类型、JSON存档

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

### 基础对话引擎

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

### 武侠战争全链路测试 (v1.3.0 新增)

```python
from luqi_engine.stress_tests.wuxia_war import WuxiaInfiniteLoop, EmergencePreset
from luqi_engine.stress_tests.wuxia_war.narrative_engine import (
    EmergenceThresholds, StoryformInequality,
)

loop = WuxiaInfiniteLoop(
    api_key="your-api-key",
    base_url="https://api.example.com/v1",
    model="mimo-v2.5",
    character_count=620,
    seed=42,
    max_rounds=5000,

    # 叙事引擎配置 (v1.3.0)
    emergence_preset=EmergencePreset.BALANCED,  # 保守/均衡/激进/自定义

    # 可选: 自定义涌现阈值
    custom_emergence_thresholds=EmergenceThresholds(
        si_threshold=0.55,
        cs_threshold=0.45,
        ii_threshold=0.35,
        min_interaction_count=4,
    ),

    # 可选: 自定义Storyform不平等维度
    custom_storyform_inequalities=[
        StoryformInequality(
            name="power_gap", description="强弱差距",
            weight=1.0, current_value=0.5,
            target_direction="increase",
        ),
    ],

    narrative_arc_enabled=True,
)

loop.initialize()
result = loop.run()

print(f"总轮次: {result.total_turns}")
print(f"结局: {result.ending.ending_type.value}")
print(f"存活角色: {result.final_world_state.get('alive')}")
```

### 涌现敏感度选择 (v1.3.0)

```python
from luqi_engine.stress_tests.wuxia_war import EmergencePreset

# 方式一: 使用预选方案
preset = EmergencePreset.CONSERVATIVE  # 高门槛，少但精确的涌现
preset = EmergencePreset.BALANCED      # 平衡模式 (推荐)
preset = EmergencePreset.AGGRESSIVE    # 低门槛，频繁涌现

# 方式二: 完全自定义
custom = EmergenceThresholds(
    si_threshold=0.70,      # 结构重要性阈值
    cs_threshold=0.60,      # 角色显著性阈值
    ii_threshold=0.50,      # 交互强度阈值
    min_interaction_count=6, # 最小交互次数
    cooldown_rounds=25,      # 检测冷却轮次
)
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
luqi_engine/                          # v1.3.0.12-Beta (182 .py, 22 modules)
├── core/              # 核心基础设施（类型、配置、RNG、混沌、分布、事件总线、最高法院）
├── orchestration/      # 编排层（ChatOrchestrator/EngineInitializer/CharacterExtractor）
├── agents/            # 智能体（Dialogue/Critic/Novelist/Atmosphere）
├── character/         # 角色系统（OCEAN/PAD/Desire/GOAP/记忆/社交感知/深层角色/荣格模型）
├── memory/            # 记忆系统（MemorySystem）
├── motivation/        # 动机引擎（MaslowEngine）
├── llm/               # LLM集成层（桥接、适配器、降级、意图分类、状态渲染）
├── local_model/       # 本地模型管线（分词、向量化、分类、纠正、安全检查）
├── narrative/         # 叙事控制器 + 活体文档
├── scene/             # 场景构建器 + 感知类型
├── interaction/       # 交互协调器（TurnScheduler/UserTracker）
├── game_theory/       # 博弈论模块（信念系统/机制设计/混合策略/威胁可信度）
├── voice/             # 语音渲染器
├── scheduler/         # 异步任务调度器（GapPrecomputer/PaceSensor/AutoMode）
├── training/          # 训练样本采集与数据存储
├── performance/       # 性能管理（对象池、资源管理器、基准测试）
├── config/            # YAML配置模板 + GBNF格式约束
├── worldview/         # 世界观渲染器（要素提取/分类/关联/冲突检测）
├── stress_tests/      # ★ v1.3.0 压力测试模块
│   ├── wuxia_war/     # 武侠战争全链路测试
│   │   ├── world.py              # 80维世界观定义
│   │   ├── character_pool.py     # 620+角色池管理
│   │   ├── narrative_engine.py   # 五层叙事引擎
│   │   ├── wuxia_runner.py       # 无限轮次对话主循环
│   │   ├── run_wuxia.py          # 运行入口
│   │   └── __init__.py           # 模块导出
│   ├── analyzer.py      # 分析器
│   ├── civilizations.py # 文明模拟
│   ├── game_loop.py     # 游戏循环
│   ├── llm_dialogue.py  # LLM对话测试
│   ├── main.py          # 测试主入口
│   └── universe.py      # 宇宙生成
└── tests/             # 测试套件 (62 tests)
```

## 测试

```bash
# 全量测试
pytest luqi_engine/tests/ -v

# 仅运行单元测试（排除集成测试）
pytest luqi_engine/tests/ --ignore=luqi_engine/tests/test_engine_integration.py -v

# 运行30轮全链路测试
python test_30round_fullchain.py

# v1.3.0: 验证叙事引擎模块导入
python -c "from luqi_engine.stress_tests.wuxia_war.narrative_engine import NarrativeEngine; print('OK')"
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

## 版本历史

详见 [CHANGELOG.md](CHANGELOG.md)

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| **v1.3.0.12-beta** | 2026-05-06 | 五层叙事引擎、80维角色体系、620+角色压力测试模块、涌现检测三方案 |
| v0.1.0 | 2026-05-05 | 初始版本：四智能体协作架构、OCEAN人格、Lorenz情感、GOAP规划器 |

## 许可证

[Apache License 2.0](LICENSE)
