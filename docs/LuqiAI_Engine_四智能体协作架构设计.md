# 🦌 LuqiAI Engine — 四智能体协作架构设计文档

> **版本**: v0.3-draft | **状态**: 设计阶段 | **日期**: 2026-04-30
> 本文档定义了外部LLM与本地模型达成一致性的完整技术方案。
> **v0.3 新增**: 第四智能体 — 氛围/旁白智能体 (Atmosphere Agent)

***

## 目录

1. [核心设计原则](#1-核心设计原则)
2. [问题定义](#2-问题定义)
3. [四智能体角色精确定义](#3-四智能体角色精确定义)
4. [引擎算法至高无上](#4-引擎算法至高无上)
5. [异步协作与间隙预计算](#5-异步协作与间隙预计算)
6. [叙事文档体系](#6-叙事文档体系)
7. [完整数据流](#7-完整数据流)
8. [节奏控制与自动推理](#8-节奏控制与自动推理)
9. [训练数据与蒸馏对齐](#9-训练数据与蒸馏对齐)
10. [降级策略](#10-降级策略)
11. [扩展性：图片/语音生成](#11-扩展性图片语音生成)
12. [实施路线图](#12-实施路线图)

***

## 1. 核心设计原则

### 1.1 铁律

| #  | 原则             | 说明                                                                                   |
| -- | -------------- | ------------------------------------------------------------------------------------ |
| P1 | **引擎算法至高无上**   | OCEAN/PAD/GOAP/MotivationEngine/BehaviorConsistency 的输出是硬约束。四智能体的建议可以修正细节，但不能推翻算法决策。 |
| P2 | **叙事文档为唯一真相源** | 所有智能体（包括引擎算法）读写同一份 NarrativeDocument。不存在"各持己说"的情况。                                   |
| P3 | **异步优先，同步兜底**  | 正常运行时四智能体异步执行，利用用户输入间隙完成后台计算。仅在初始化或关键剧情节点做同步协调。                                      |
| P4 | **增量式，非全量重算**  | 智能体只输出自上次以来的变化量（delta），不重写整个文档。                                                      |
| P5 | **训练数据按角色隔离**  | 不同角色的数据严格分桶存储，防止风格污染。                                                                |

### 1.2 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                                 │
│                                                                 │
│   ┌─────────┐    ┌──────────┐    ┌──────────┐                   │
│   │ DSL IDE │    │ API 接口  │    │ WebSocket│                   │
│   └────┬────┘    └────┬─────┘    └────┬─────┘                   │
│        └──────────────┼───────────────┘                         │
│                       ▼                                         │
│              ┌─────────────────┐                                │
│              │   LuqiEngine     │                                │
│              │   (engine.py)    │                                │
│              └────────┬────────┘                                │
│                       │                                          │
│  ═════════════════════╪════════════════════════════════════     │
│         算法层 (确定性, 至高无上)          │                      │
│  ═════════════════════╪════════════════════════════════════     │
│                       │                                          │
│  ┌────────────────────┼──────────────────────┐                  │
│  │                    ▼                      │                  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────┐│                  │
│  │  │CharacterEnt.│ │NarrativeCtrl│ │Interaction│                │
│  │  │OCEAN/PAD   │ │StoryNode   │ │Coordinator│               │
│  │  │GOAP/Motive │ │BranchWeight│ │SocialRule│                │
│  │  │MemoryStore │ │Regression  │ │Priority  │                │
│  │  │BehavConsist│ │DeadEndCheck│ │Relation  │                │
│  │  └─────┬──────┘ └─────┬──────┘ └────┬───┘│                  │
│  │        │              │             │    │                  │
│  │        └──────────────┼─────────────┘    │                  │
│  │                       ▼                  │                  │
│  │              ┌─────────────────┐        │                  │
│  │              │NarrativeDocument│◄───────┘ 唯一真相源        │
│  │              │(活体叙事文档)    │                            │
│  │              └────────┬────────┘                            │
│  └───────────────────────┼────────────────────────────────────┘
│                          │
│  ════════════════════════╪════════════════════════════════════
│         LLM辅助层 (建议性, 可被算法否决)      │
│  ════════════════════════╪════════════════════════════════════
│                          │
│       ┌──────────────────┼──────────────────────────────┐
│       │                  │                              │
│       ▼                  ▼                              ▼
│  ┌──────────┐     ┌──────────┐      ┌──────────┐      ┌──────────┐
│  │ 对话 Agent│     │ 小说 Agent│      │ 批判 Agent│     │ 氛围 Agent│
│  │(Dialogue)│     │(Novelist)│      │(Critic)  │     │(Atmosphere)│
│  │          │     │          │      │          │     │            │
│  │ "角色怎么说"│    │"世界发生什么"│   │"这样行不行"│   │"感觉如何"   │
│  │          │     │          │      │          │     │            │
│  │ 生成回复  │     │ 维护文档  │      │ 质量门控  │     │ 环境渲染    │
│  │ 角色口吻  │     │ 大纲推进  │      │ 一致性检查│     │ 氛围描写    │
│  │ 情感反应  │     │ 预测走向  │      │ OOC检测  │     │ 旁白叙述    │
│  │ 输出IR    │     │ 记录事实  │      │ 异常处理  │     │ 舞台指示    │
│  │          │     │          │      │          │     │ 感官铺陈    │
│  └─────┬────┘     └─────┬────┘      └─────┬────┘     └─────┬────┘
│        │                │                 │               │
│        └────────────────┴─────────────────┴───────────────┘
│                     │ 写入 delta / 注入输出流
│                     ▼
│            NarrativeDocument.apply_delta()
│              + AtmosphereOutput 注入最终回复
│                     │
│  ════════════════════╪══════════════════════════════════════
│         表达层 (确定性渲染)              │
│  ════════════════════╪══════════════════════════════════════
│                     │
│         ┌─────────────┼───────────────────┐
│         ▼             ▼                   ▼
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐
│  │VoiceRenderer│ │AtmosphereMerge│ │ 最终组装      │
│  │(对话渲染)  │ │(氛围注入器)    │ │ (OutputAssembler)
│  └─────┬────┘  └──────┬───────┘  └──────┬───────┘
│        │                │                  │
│        └────────────────┴──────────────────┘
│                     │
│                     ▼
│              ┌──────────────────┐
│              │  完整回复给用户:    │
│              │                   │
│              │ [氛围/环境段落]   │ ← Atmosphere Agent
│              │ [舞台指示]       │ ← Atmosphere Agent
│              │ ─────────────── │
│              │ "角色台词内容"   │ ← Dialogue + VoiceRenderer
│              │ [动作/神态描写]  │ ← Atmosphere/Dual render
│              │ ─────────────── │
│              │ [氛围过渡]       │ ← Atmosphere Agent
│              └──────────────────┘
```

***

## 2. 问题定义

### 2.1 核心矛盾

```
外部LLM (Cloud) ≠ 本地模型 (Local)

差异维度:
├── 风格层: 外部更华丽/书面化, 本地更口语/简短
├── 行为层: 外部主动推进, 本地倾向被动回应  
├── 记忆层: 外部输出更适合提取高质量记忆条目
└── 能力层: 外部擅长复杂推理, 本地擅长快速响应

后果: 降级时用户感知到"角色变了个人"
```

### 2.2 设计目标

| 目标    | 指标                         |
| ----- | -------------------------- |
| 风格一致性 | 无论哪个模型输出，最终回复的角色口吻偏差 < 15% |
| 剧情连贯性 | 降级后剧情推进方向偏离 < 20%          |
| 成本控制  | 平均每消息 ≤ 1.2x 单模型调用成本       |
| 断连可用性 | 外部完全断连时，功能保持 ≥ 70%         |
| 数据产出  | 每轮交互产生结构化训练样本（用于本地模型迭代）    |
| 节奏自适应 | 自动适配快慢两种用户节奏（停留久 vs 快速推进）  |

***

## 3. 四智能体角色精确定义

### 3.1 角色对比矩阵

| 维度       | 对话 Agent (Dialogue)       | 小说 Agent (Novelist)   | 批判 Agent (Critic)        | 氛围 Agent (Atmosphere)        |
| -------- | ------------------------- | --------------------- | ------------------------ | ------------------------------ |
| **本质**   | 角色的"嘴"                    | 世界的"记忆"               | 质量的"守门人"                 | 场景的"感官"                     |
| **别名**   | Dialogue / Speaker           | Novelist / Chronicler     | Critic / Reviewer            | Narrator / StageDirector        |
| **触发频率** | 每轮必触发                     | 按需/间隙触发               | 抽样/高风险触发                 | 每轮触发(轻量) + 场景切换时(完整)    |
| **输入**   | 用户消息 + 叙事状态 + 角色状态        | 最新事实 + 当前文档 + 世界观     | Dialogue输出 + 叙事文档 + 算法约束 | 场景数据 + 刚发生的事件 + 情感基调    |
| **输出**   | CanonicalIR (意图/行动/情感/要点) | NarrativeDelta (差量更新) | CriticVerdict (通过/修正/否决)   | AtmosphereOutput (环境/旁白/舞台指示) |
| **输出性质** | 建议 → 受算法约束                | 建议 → 受算法约束            | 判定 → 可否决Dialogue但不可改算法   | 装饰性 → 注入最终回复，不影响状态      |
| **可替代性** | 低 (复杂推理需要LLM)             | 中 (大部分可规则化)           | 高 (几乎可全算法化)              | 中-高 (模板可覆盖80%，LLM提升上限)  |
| **降级方案** | Local Model Layer 2       | Local Model Layer 1   | 算法一致性检查器                 | 模板引擎 + PCG扰动                  |
| **Token占比** | ~35%                          | ~25%                      | ~15%                           | ~25%                            |

### 3.2 各角色的精确职责边界

#### 对话 Agent — "角色怎么说"

```
负责: 根据当前情境决定角色的具体回应内容

必须做的事:
  ✓ 解析用户意图 (理解字面+弦外之音)
  ✓ 结合角色人格(OCEAN)决定态度倾向
  ✓ 结合当前情感(PAD)决定情绪表达强度
  ✓ 结合动机优先级决定行动方向
  ✓ 输出结构化的 CanonicalIR (不是自由文本)

不能做的事:
  ✗ 自行修改叙事文档 (那是Novel的事)
  ✗ 自行判断自己的输出是否合规 (那是Critic的事)
  ✗ 推翻 GOAP 规划的结果 (算法至高无上)
  ✗ 改变已确立的事实 (受NarrativeDocument约束)

输出格式: CanonicalIR (JSON)
{
  intent: "greet/inquire/comfort/challenge/negotiate/...",
  confidence: 0.85,
  emotion_delta: {P:+0.1, A:+0.05, D:0.0},
  seven_trigger: "爱",
  action: "smile_nod",           // 必须在GOAP可用行动集合内
  action_params: {"target": "user"},
  key_points: ["确认天气好", "表达想出去", "询问对方计划"],
  tone: "casual",
  length_hint: "medium",
  narrative_signal: null,        // 不主动推动剧情 (留给Novel)
  memory_to_add: null
}
```

#### 小说 Agent — "世界发生了什么"

```
负责: 维护和推进 NarrativeDocument (活体叙事状态文档)

必须做的事:
  ✓ 吸收新事实 (用户动作、角色行动、对话关键信息)
  ✓ 更新章节大纲 (当有足够的新事件时)
  ✓ 预测下一场景可能的发展方向 (2-3个选项)
  ✓ 维护角色弧线 (每个角色在本章的发展轨迹)
  ✓ 标记硬约束 ("小雪还不能知道身世")
  ✓ 检测剧情分支点并评估权重

不能做的事:
  ✗ 直接写角色的台词 (那是Dialogue的事)
  ✗ 修改角色的内部状态 (OCEAN/PAD由算法管理)
  ✗ 否决算法的计算结果 (只能建议)

输出格式: NarrativeDelta (JSON 差量)
{
  version: 42,                   // 文档版本号 (递增)
  
  new_facts: [
    {
      id: "fact_042",
      timestamp: "ch3_scene2_t15",
      source: "user_action",
      content: "用户突然拔出剑指对小雪",
      participants: ["user", "char_xiaoxue"],
      emotional_valence: -0.7,
      tags: ["conflict", "violence", "unexpected"]
    }
  ],
  
  chapter_update: {
    current_beat_progress: 0.65,     // 当前节拍进度 0-1
    new_beat_suggested: {
      name: "对峙升级",
      description: "紧张局势从言语上升到肢体威胁",
      expected_participants: ["user", "char_xiaoxue"],
      tension_delta: +0.3
    },
    character_arcs_update: {
      char_xiaoxue: {
        arc_position: 0.40,           // 角色弧线进度
        development_note: "面对威胁时首次展示防御姿态"
      }
    },
    constraints_added: [],
    constraints_removed: []
  },  // 或 null 表示本轮无需修改大纲
  
  next_prediction: {
    likely_next_scenes: [
      {scene: "雪之庭院_对峙", probability: 0.55,
       description: "双方继续对峙，尝试沟通"},
      {scene: "雪之庭院_战斗", probability: 0.25,
       description: "冲突升级为战斗"},
      {scene: "藏身处_撤离", probability: 0.15,
       description: "一方选择撤退"},
      {scene: "城镇_第三方介入", probability: 0.05,
       description: "守卫或其他NPC介入"}
    ],
    narrative_tension: 0.78,
    suggested_pace: "normal"  // slow/normal/fast/urgent
  },
  
  open_questions_added: ["小雪为何随身带剑？", "用户的真实身份？"],
  open_questions_resolved: [],
  
  narrative_note: "用户突然拔剑打破了之前的轻松氛围，
                   叙事张力急剧上升。需要观察小雪的反应
                   来确定后续走向。"
}
```

#### 批判 Agent — "这样行不行"

```
负责: 审核其他两个Agent的输出是否符合约束

必须做的事:
  ✓ 检查 Dialogue 输出的角色OOC程度
  ✓ 检查是否导致剧情无法继续 (dead end风险)
  ✓ 检查是否与 established_facts 矛盾
  ✓ 检查应对突发事件的合理性
  ✓ 检查情感变化是否违反OCEAN约束
  ✓ 检查行动是否在GOAP允许范围内

不能做的事:
  ✗ 修改引擎算法的内部计算结果
  ✗ 自行创造新的叙事内容 (只能判定已有内容)
  ✗ 否决后自行生成替代方案 (只能给出suggestion)

输出格式: CriticVerdict (JSON)
{
  verdict: "accept",  // accept / minor_fix / major_rewrite / reject
  
  checks: [
    {
      dimension: "ooc_detection",
      severity: "pass",
      score: 0.92,           // 0-1, 越高越符合人设
      detail: "回复符合小雪温柔谨慎的性格"
    },
    {
      dimension: "narrative_coherence",
      severity: "warning",
      score: 0.75,
      detail: "回复较为被动，可能导致剧情停滞;
               建议增加一点主动性"
    },
    {
      dimension: "fact_consistency",
      severity: "pass",
      score: 1.0,
      detail: "无事实矛盾"
    },
    {
      dimension: "emotion_validity",
      severity: "pass",
      score: 0.88,
      detail: "情感变化在OCEAN允许范围内"
    },
    {
      dimension: "action_feasibility",
      severity: "pass",
      score: 0.95,
      detail: "行动在GOAP可用集合中"
    }
  ],
  
  overall_confidence: 0.90,
  
  // 仅当 verdict != "accept" 时填充:
  corrections: {
    suggested_emotion_delta: null,    // 无需修正
    suggested_action: null,
    suggested_key_point_addition: "可考虑表达一丝不安",
    narrative_risk_flag: false
  },
  
  override_recommendation: null  // 仅 reject 时填写替代方案
}
```

#### 氛围 Agent — "感觉如何" (Atmosphere / Narrator)

```
负责: 渲染场景的感官体验、环境氛围、旁白叙述和舞台指示
这是文字冒险/视觉小说产品的灵魂组件——没有它，对话再精彩也像"在真空中聊天"

必须做的事:
  ✓ 环境描写 (视觉: 光线/色彩/天气/空间/物体)
  ✓ 感官铺陈 (听觉: 声音/音乐/寂静; 嗅觉: 气味/温度; 触觉: 质感)
  ✓ 旁白叙述 (第三人称视角的场景过渡/时间流逝/内心独白旁注)
  ✓ 舞台指示 (角色动作提示 [拔剑]、神态变化 [眉头微蹙]、位置移动)
  ✓ 情感基调渲染 (根据当前叙事张力调整描写风格)
  ✓ 场景切换时的过渡段落 (进入新场景的环境建立)

不能做的事:
  ✗ 写角色的台词内容 (那是Dialogue的事)
  ✗ 修改任何游戏状态 (OCEAN/PAD/事实/大纲都不碰)
  ✗ 推进剧情或创建新事实 (那是Novel的事)
  ✗ 判断对错 (那是Critic的事)
  ✗ 输出长度超过合理范围 (需要控制占比, 不能喧宾夺主)

两种工作模式:

  ┌─ Light Mode (每轮触发, 低token) ─────────────────────┐
  │                                                          │
  │  只生成: 一段简短的环境/氛围过渡文本 (1-3句)            │
  │  用途: 嵌入回复头部或尾部, 营造沉浸感                   │
  │  token预算: ~200-400                                    │
  │                                                          │
  └──────────────────────────────────────────────────────────┘

  ┌─ Full Mode (场景切换/关键节点触发) ────────────────────┐
  │                                                          │
  │  完整生成以下全部:                                       │
  │  - 场景建立段 (新场景的完整感官描写, 3-5句)               │
  │  - 过渡段 (从上一场景到当前的场景转换)                    │
  │  - 舞台指示集 (本轮涉及的所有角色动作/表情的位置提示)     │
  │  - 氛围基调声明 (整体情绪色彩的定调句)                     │
  │  token预算: ~800-1500                                   │
  │                                                          │
  └──────────────────────────────────────────────────────────┘

输出格式: AtmosphereOutput (JSON)
{
  mode: "light",              // light / full
  
  // === 环境层 ===
  environment: {
    visual: "庭院中的灯笼在风中摇曳, 映出两人拉长的影子。",
    auditory: "风穿过回廊的呜咽声, 远处传来不知名鸟类的啼鸣。",
    olfactory: "空气中弥漫着松针与初雪的清冽气息。",
    thermal: "寒意顺着衣领无声地渗入, 却不刺骨, 只是提醒着冬夜的存在。",
    spatial: "石板路因年久失修而微微起伏, 积雪在缝隙中结成冰棱。"
  },
  
  // === 旁白层 ===
  narration: {
    transition: null,           // light模式通常无过渡
    inner_voice: null,          // 角色内心旁白(如有)
    omniscient_note: "这一刻, 雪之庭院的宁静被彻底打破了。"  // 全知旁白
  },
  
  // === 舞台指示层 ===
  stage_directions: [
    {character: "char_xiaoxue", action: "hand_on_hilt", 
     detail: "右手按上剑柄, 指节因用力而发白"},
    {character: "user", action: "standing_threaten", 
     detail: "剑尖稳稳指向对方, 姿态显示出训练有素"}
  ],
  
  // === 基调层 ===
  mood_declaration: {
    dominant_emotion: "tension",   // tension/warmth/mystery/sorrow/joy
    intensity: 0.78,               // 0-1
    color_palette: ["#0a0a1a", "#1a2a4a", "#c4a484"],  # 暗蓝+冷金
    pacing_hint: "slow_breath"    // 影响VoiceRenderer的排版节奏
  },
  
  // === 控制字段 ===
  suggested_position: "prefix",   // prefix(回复前) / suffix(回复后) / wrap(包裹) / interleave(穿插)
  length_budget: "short",         // tiny/short/medium/long (控制总字数)
  priority: 0.7                  // 0-1, 多个元素冲突时的取舍权重
}
```

### 3.3 四智能体协作关系图

```
用户消息到达
    │
    ├──→ Dialogue Agent: "角色应该说什么"
    │       ↓ CanonicalIR
    │       ↓ VoiceRenderer → 角色台词 (核心内容)
    │
    ├──→ Novel Agent: "世界发生了什么"
    │       ↓ NarrativeDelta
    │       ↓ NarrativeDocument 更新
    │       ↓ (同时提供给 Atmosphere 作为上下文)
    │
    ├──→ Critic Agent: "这样行不行"
    │       ↓ CriticVerdict
    │       ↓ 校正/通过
    │
    └──→ Atmosphere Agent: "感觉如何"
            ↓ AtmosphereOutput
            ↓ 环境描写 + 旁白 + 舞台指示
            ↓
    ══════════════════╧═════════════
            ↓
    ┌───────────────────────────────┐
    │      OutputAssembler          │
    │                               │
    │ 按 suggested_position 组装:    │
    │                               │
    │ [Atmosphere.environment]      ← 场景铺垫
    │ [Atmosphere.stage_directions]  ← 动作提示
    │ ─────────────────────────     │
    │ "角色台词内容"                 ← Dialogue + VoiceRenderer
    │ [Atmosphere.narration]        ← 旁白收尾
    │ ─────────────────────────     │
    │ [Atmosphere.mood_transition]  ← 情感过渡
    │                               │
    │ → 完整的沉浸式回复             │
    └───────────────────────────────┘
```

### 3.4 Atmosphere Agent 的特殊价值

| 场景 | 没有 Atmosphere Agent | 有 Atmosphere Agent |
|------|---------------------|-------------------|
| **场景初次进入** | "你来到了雪之庭院" (干瘪) | "厚重的木门在你身后缓缓合拢, 将风声隔绝在外。眼前是一座被永恒落雪覆盖的庭院, 四周矗立的石柱上挂着早已熄灭的灯笼, 残余的烛油在寒冷中凝结成白色的泪痕。" |
| **紧张时刻** | 小雪: "你是谁派来的？" | "[剑锋在月光下泛着冷冽的银光, 映出她骤然收缩的瞳孔] ... '......你到底是什么人？' 她的声音压得很低, 带着一丝不易察觉的颤抖。" |
| **安静时刻** | (只有对话, 显得空旷) | "[雪花无声地落在两人的肩头, 庭院中只剩下彼此的呼吸声和远处风铃的轻响。时光仿佛在此刻凝固。]" |
| **场景切换** | "你们来到了城镇" | "[身后的雪之庭院渐渐隐没在风雪中。穿过蜿蜒的山道后, 远处的灯火如星子般亮起——那是一座依山而建的城镇, 屋顶覆着厚厚的积雪, 炊窗透出暖黄色的光。]" |
| **情感高潮** | 只有台词, 缺乏感染力 | "[她的手颤抖着伸向你, 指尖在距离你胸口一寸的地方停住。风雪似乎在这一刻都静止了。] '......带我走。' 这三个字轻得像一片即将融化的雪。" |

**关键洞察**: Atmosphere Agent 不是装饰品——它是**沉浸感的载体**。同样的对话内容，有/无氛围渲染，用户体验天差地别。

***

## 4. 引擎算法至高无上

这是最核心的设计约束。所有LLM输出都必须经过算法层的校验。

### 4.1 约束层级

```
┌─────────────────────────────────────────────────────┐
│                  约束金字塔 (从弱到强)                 │
│                                                     │
│  Level 5: 建议级 (LLM可忽略)                        │
│  ─────────────────────                              │
│  • Novelist 的 narrative_note / suggested_pace       │
│  • Critic 的 suggestion (verdict=accept时)           │
│  • Dialogue 的 tone preference                      │
│                                                     │
│  Level 4: 软约束 (LLM应遵守,算法可微调)              │
│  ─────────────────────────                           │
│  • NarrativeDocument.constraints (软约束)            │
│  • chapter_outline.character_arcs 发展方向           │
│  • Critic 的 minor_fix 修正                          │
│                                                     │
│  Level 3: 硬约束 (LLM必须遵守,违反则被强制修正)       │
│  ─────────────────────────                             │
│  • established_facts (已确立事实,不可矛盾)            │
│  • OCEAN 允许的情感范围 (超出则clamp)                 │
│  • GOAP 可用行动集合 (之外的行动被替换为最近似的)     │
│  • behavior_consistency ≥ 0.95 阈值                  │
│                                                     │
│  Level 2: 物理法则 (不可违反)                         │
│  ─────────────────────                              │
│  • 场景空间约束 (不能穿墙、瞬移)                      │
│  • 时间线性 (不能回到过去,除非叙事明确允许)            │
│  • 因果逻辑 (效果必须有原因)                          │
│                                                     │
│  Level 1: 引擎不变量 (绝对不可触碰)                    │
│  ─────────────────────────                           │
│  • EntityId 唯一性                                   │
│  • EventBus 事件顺序                                  │
│  • Snapshot 协议格式                                  │
│  • PCG 种子链 (不可中途更换种子)                      │
└─────────────────────────────────────────────────────┘
```

### 4.2 算法校验流程

```python
class AlgorithmSupremeCourt:
    """引擎算法最高法院 — 所有LLM输出必须经过此门"""
    
    def validate_dialogue_ir(self, ir: CanonicalIR, 
                              character: CharacterEntity,
                              narrative: NarrativeDocument) -> ValidatedIR:
        
        validated = ir.copy()
        violations = []
        
        # === Level 3: 硬约束检查 ===
        
        # 3a. 情感范围检查
        new_pad = character.emotion.pad_state.apply_delta(ir.emotion_delta)
        if not character.personality.is_emotion_in_range(new_pad):
            clamped = character.personality.clamp_emotion(new_pad)
            validated.emotion_delta = clamped - character.emotion.pad_state
            violations.append(Violation(
                level="hard", type="emotion_out_of_range",
                original=ir.emotion_delta, forced=validated.emotion_delta
            ))
        
        # 3b. 行动可行性检查
        available_actions = character.get_available_actions(narrative.current_world_state)
        if ir.action not in [a.name for a in available_actions]:
            closest = self._find_closest_action(ir.action, available_actions)
            validated.action = closest.name
            validated.action_params = closest.default_params
            violations.append(Violation(
                level="hard", type="action_not_available",
                original=ir.action, forced=closest.name
            ))
        
        # 3c. 行为一致性检查
        consistency = character.validate_behavior_consistency_from_ir(ir)
        if consistency < BEHAVIOR_CONSISTENCY_THRESHOLD:
            # 不降低阈值，而是标记并由Critic进一步审查
            validated.consistency_warning = True
            violations.append(Violation(
                level="hard", type="low_consistency",
                score=consistency, threshold=BEHAVIOR_CONSISTENCY_THRESHOLD
            ))
        
        # === Level 2: 物理法则检查 ===
        
        # 2a. 场景空间合法性
        if ir.action_params.get("target_location"):
            if not narrative.scene_manager.is_accessible(
                ir.action_params["target_location"], 
                character.position
            ):
                # 强制修正为目标可达的最近位置
                validated.action_params["target_location"] = \
                    narrative.scene_manager.nearest_accessible(
                        ir.action_params["target_location"], character.position
                    )
        
        # 2b. 时间连续性
        if ir.narrative_signal == "time_skip":
            max_skip = narrative.config.max_time_skip_per_turn
            if ir.action_params.get("skip_duration", 0) > max_skip:
                validated.action_params["skip_duration"] = max_skip
        
        # === Level 4: 软约束应用 ===
        
        # 4a. 如果Critics给了minor_fix建议，且不违反硬约束，则采纳
        # (这部分在Critic结果合并时处理)
        
        return ValidatedIR(
            ir=validated,
            violations=violations,
            is_clean=len(violations) == 0,
            needs_critic_review=any(v.level == "hard" for v in violations)
        )
    
    def validate_novel_delta(self, delta: NarrativeDelta,
                               narrative: NarrativeDocument) -> ValidatedDelta:
        
        validated = delta.copy()
        violations = []
        
        for fact in delta.new_facts:
            # 不能与已确立事实矛盾
            existing = narrative.find_conflicting_fact(fact)
            if existing:
                # 不是直接丢弃，而是标记冲突让Critic裁决
                validated.flagged_facts.append(fact.id)
                violations.append(Violation(
                    level="hard", type="fact_conflict",
                    new_fact=fact.id, conflicting=existing.id
                ))
        
        for constraint in delta.chapter_update.constraints_added:
            # 新约束不能撤销已确立的事实
            if narrative.is_fact_violating_constraint(constraint):
                validated.rejected_constraints.append(constraint)
                violations.append(Violation(
                    level="hard", type="constraint_invalidates_fact",
                    constraint=constraint
                ))
        
        return ValidatedDelta(delta=validated, violations=violations)
```

***

## 5. 异步协作与间隙预计算

这是你补充的核心机制——利用用户思考时间做后台计算。

### 5.1 生命周期状态机

```
                    ┌─────────────┐
                    │   IDLE      │ ← 等待用户输入
                    │  (空闲)      │
                    └──────┬──────┘
                           │ 用户消息到达
                           ▼
                    ┌─────────────┐
               ┌────→│  SYNC_MODE  │ ← 同步模式 (初始化/关键节点)
               │     │ (同步执行)  │     四智能体串行: N→D→A→C
               │     └──────┬──────┘
               │            │ 同步完成
               │            ▼
               │     ┌─────────────┐
               │     │  RESPONDING │ ← 向用户返回回复
               │     │  (响应中)    │     同时启动异步任务
               │     └──────┬──────┘
               │            │ 回复已发送
               │            ▼
               │     ┌─────────────┐
          ┌────┘     │ASYNC_PREP    │ ◄─── 间隙预计算 (核心!)
          │          │ (异步准备)   │     利用用户阅读/思考的时间
          │          │              │
          │          │ ├─ Novel:    │     更新文档/推测走向
          │          │ │ 更新文档   │
          │          │ │ 推测走向   │
          │          │ ├─ Critic:   │     预检约束/准备预案
          │          │ │ 预检约束   │
          │          │ │ 准备预案   │
          │          │ ├─ Dialogue: │     预分析上下文
          │          │ │ 预分析上下文│
          │          │ └─ Atmos:    │ ★ 新增 ★
          │          │   预渲染环境  │     轻量模式氛围文本
          │          │   缓存场景库  │     场景切换时预生成Full模式
          │          └──────┬──────┘
          │                 │
          │     ┌───────────┤
          │     │           │
          │     ▼           ▼ 用户再次输入前完成?
          │  ┌────────┐ ┌────────┐
          │  │READY   │ │TIMEOUT│ ← 用户等太久 (>30s?)
          │  │(就绪)  │ │(超时)  │    → 进入 AUTO_MODE
          │  └────┬───┘ └────┬───┘
          │       │          │
          │       ▼          ▼
          │  ┌─────────────┐
          └──│  IDLE       │
             │  (等待下一次)│
             └─────────────┘


                    ┌─────────────┐
                    │ AUTO_MODE   │ ← 全自动推理模式
                    │ (自动推理)   │    用户长时间未操作
                    │              │    引擎自主推进剧情
                    │ ├─ Novel:    │
                    │ │ 推进大纲   │
                    │ │ 生成事件   │
                    │ ├─ Critic:   │
                    │ │ 全检       │
                    │ ├─ Dialogue: │
                    │ │ NPC自主行为│
                    │ └─ Engine:   │
                    │   GOAP决策   │
                    └──────┬──────┘
                           │
                           ▼ (循环直到用户回来)
                    ┌─────────────┐
                    │   IDLE      │
                    └─────────────┘
```

### 5.2 间隙预计算的详细流程

```
用户发送消息 → 引擎处理 → 返回回复
    │
    │  (此时用户正在阅读回复, 可能需要 5-60 秒)
    │
    ▼
[间隙窗口开始]  ← async_task 启动
    
    Task A: Novel Agent 后台更新 (优先级: 高)
    │
    ├── 将刚发生的对话吸收为新 fact
    │   fact = {
    │     source: "dialogue",
    │     content: "[小雪] '嗯...确实是个好天气呢~'",
    │     participants: ["char_xiaoxue"],
    │     emotional_valence: +0.4,
    │     tags: ["casual", "agreeable"]
    │   }
    │
    ├── 评估是否需要更新 chapter_outline
    │   ├── 如果距上次更新 > 3轮 → 触发小幅更新
    │   ├── 如果检测到 branch_point → 触发完整重新评估
    │   └── 否则 → 仅更新 character_arc 的进度
    │
    └── 刷新 next_prediction (概率分布)
        (这个预测会在用户下一条消息来临时提供给Dialogue)
    
    
    Task B: Critic Agent 后台预检 (优先级: 中)
    │
    ├── 基于最新的 NarrativeDocument, 预判用户可能的下一步
    │   possible_user_actions = predict_user_actions(
    │       context=narrative, history=recent_exchanges
    │   )
    │
    ├── 对每种可能的用户动作, 预生成 Critic 的约束条件
    │   precomputed_constraints[user_action_pattern] = {
    │       allowed_emotions: [...],
    │       forbidden_actions: [...],
    │       narrative_guards: [...]
    │   }
    │
    └── 这些预计算结果缓存起来, 下轮Dialogue时直接使用
    
    
    Task C: Dialogue Agent 预分析 (优先级: 低)
    │
    ├── 预组装下一轮的 PromptContext
    │   (narrative 已更新, 可以提前构建大部分内容)
    │
    ├── 如果 AUTO_MODE 即将触发, 预生成 NPC 自主行为的候选
    │   npc_autonomy_candidates[char_id] = {
    │       likely_intent: "...",
    │       suggested_action: "...",
    │       precondition_checks: [...]
    │   }
    │
    └── 缓存待用
    
    Task D: Atmosphere Agent 预渲染 (优先级: 中-低)
    │
    ├── Light Mode 预渲染 (每轮都执行)
    │   基于当前场景 + 最新事实 + 情感基调
    │   生成 1-2 句环境过渡文本 (缓存为 atmosphere_cache["light"])
    │   token开销极低 (~150-250), 但大幅提升回复沉浸感
    │
    ├── 场景切换预检测
    │   判断下轮是否可能发生场景切换:
    │   ├─ 用户消息含移动关键词? ("走向"/"离开"/"进入")
    │   ├─ NarrativeDocument.next_prediction 含新场景?
    │   └─ Dialogue IR 的 action 含 scene_transition?
    │
    ├── 如果可能切换 → Full Mode 预生成 (异步)
    │   新场景的完整感官描写 + 过渡段 + 基调声明
    │   缓存为 atmosphere_cache[scene_id]["full"]
    │   用户真的切换时直接使用, 零等待
    │
    └── 舞台指示模板预匹配
        基于 Dialogue IR 的 action 字段, 预选舞台指示模板
        (如 action="step_back_draw_weapon" → 匹配武器相关舞台模板)
    
    │
    ▼
[间隙窗口结束] ← 用户发来新消息 OR 超时进入AUTO_MODE
    
    如果是新消息:
    → 使用 Task A 更新后的 NarrativeDocument (已是最新)
    → 使用 Task B 预计算的约束 (加速Critic)
    → 使用 Task C 预分析的 PromptContext (加速Dialogue)
    → 使用 Task D 预渲染的 atmosphere_cache (零延迟氛围文本)
    → 整体延迟降低 40-60%
    
    如果是超时:
    → 使用 Task C 的 NPC 自主行为候选
    → 使用 Task D 的 Full Mode 氛围缓存 (AUTO_MODE用)
    → 进入 AUTO_MODE 全自动推理
```

### 5.3 初始化时的同步流程

只有以下情况走完全同步：

```
场景A: 世界首次创建
    │
    ├── 1. 用户调用 create_world(content)
    │
    ├── 2. [SYNC] Novel Agent 首次运行
    │   输入: 原始世界观文本
    │   输出: 完整的 NarrativeDocument v1
    │   (包含初始 chapter_outline, facts, predictions)
    │
    ├── 3. [SYNC] Critic Agent 首次审核
    │   输入: NarrativeDocument v1
    │   输出: 初始质量报告 + 约束集
    │
    ├── 4. 引擎算法校验 → 确认无误
    │
    └── 5. 世界就绪, 切换到 ASYNC 模式


场景B: 关键剧情节点 (branch_point / turning_point)
    │
    ├── 1. NarrativeController.detect_branch() → 发现分支点
    │
    ├── 2. [SYNC] Novel Agent 完整评估
    │   输入: 当前状态 + 分支选项
    │   输出: 各分支的详细预测 + 权重建议
    │
    ├── 3. [SYNC] Critic Agent 审核各分支
    │   输出: 每个分支的风险评估
    │
    ├── 4. 引擎算法综合决策 → 选择分支
    │
    └── 5. 应用分支, 更新 NarrativeDocument, 回到 ASYNC


场景C: 用户请求强制刷新
    │
    └── 手动触发 [SYNC] 全部三个 Agent
```

***

## 6. 叙事文档体系

### 6.1 NarrativeDocument 完整数据结构

```python
@dataclass
class Fact:
    """不可变的事实记录"""
    id: str                          # 唯一ID
    sequence_number: int             # 全局序号 (单调递增)
    timestamp: str                   # 叙事时间戳 "ch3_scene2_t15"
    source: Literal["user_action", "dialogue", "character_action",
                       "narrative", "system"]
    content: str                    # 事实描述
    participants: List[str]         # 涉及实体ID列表
    location: Optional[str]         # 发生地点
    emotional_valence: float        # 情感极性 [-1, 1]
    tags: List[str]                 # 标签
    is_retracted: bool = False      # 是否已被撤回 (不删除,标记)


@dataclass
class StoryBeat:
    """叙事节拍"""
    name: str
    description: str
    expected_participants: List[str]
    tension_level: float            # 0-1
    status: Literal["upcoming", "active", "completed", "skipped"]
    progress: float = 0.0           # 0-1 完成度


@dataclass
class CharacterArc:
    """单个角色在本章的发展弧线"""
    character_id: str
    arc_name: str                   # 如 "信任建立之旅"
    starting_state: Dict[str, Any]  # 章节开始时的状态
    current_state: Dict[str, Any]   # 当前状态
    target_state: Dict[str, Any]    # 章节目标状态
    position: float = 0.0           # 弧线位置 0.0-1.0
    key_moments: List[str] = field(default_factory=list)  # 经历的关键时刻ID
    development_notes: List[str] = field(default_factory=list)


@dataclass
class ChapterOutline:
    """章节大纲"""
    chapter_id: int
    title: str
    arc_summary: str                # 本章主线描述
    beats: List[StoryBeat]          # 预期节拍列表
    current_beat_index: int = 0     # 当前进行到的节拍
    character_arcs: Dict[str, CharacterArc]  # 角色ID → 弧线
    hard_constraints: List[str] = field(default_factory=list)  # 硬约束
    soft_constraints: List[str] = field(default_factory=list)  # 软约束
    estimated_scope: str = "medium"  # small/medium/large/epic


@dataclass
class ScenePrediction:
    """下一场景预测"""
    scene_id: str
    scene_name: str
    probability: float
    description: str
    expected_participants: List[str]
    estimated_tension: float
    prerequisites: List[str] = field(default_factory=list)  # 前置条件
    blocking_issues: List[str] = field(default_factory=list)  # 阻塞问题


@dataclass
class NarrativeDocument:
    """活体叙事文档 — 所有智能体共享的唯一真相源"""
    
    # === 元信息 ===
    document_id: str
    world_id: str
    version: int = 0                # 版本号 (每次apply_delta递增)
    created_at: float
    last_updated: float
    
    # === 当前位置 ===
    current_chapter: int = 1
    current_scene: str = ""
    timeline_position: float = 0.0   # 整体故事进度 0.0-1.0
    narrative_tick: int = 0          # 内部时钟 (每次交互+1)
    
    # === 事实库 (只增不减, 支持撤回标记) ===
    established_facts: List[Fact] = field(default_factory=list)
    
    # === 章节大纲 ===
    current_chapter_outline: Optional[ChapterOutline] = None
    
    # === 场景预测 ===
    next_scene_predictions: List[ScenePrediction] = field(default_factory=list)
    active_prediction: Optional[int] = None  # 当前采纳的预测索引
    
    # === 待处理 ===
    pending_absorptions: List[Dict] = field(default_factory=list)  # 待吸收的原始事件
    open_questions: List[str] = field(default_factory=list)
    resolved_questions: List[str] = field(default_factory=list)
    
    # === 节奏状态 ===
    pace_state: PaceState = None  # 见下方 PaceState 定义
    auto_mode_config: AutoModeConfig = None  # 见下方
    
    # === 扩展数据 (高质量模式下) ===
    prose_draft: Optional[str] = None       # 小说草稿文本 (可选)
    scene_descriptions: Dict[str, str] = field(default_factory=dict)  # 场景描写
    dialogue_transcripts: List[Dict] = field(default_factory=list)  # 对话实录
    
    def apply_delta(self, delta: NarrativeDelta) -> None:
        """应用差量更新, 版本号+1"""
        self.version += 1
        self.last_updated = time.time()
        self.narrative_tick += 1
        
        # 吸收新事实
        for fact in delta.new_facts:
            fact.sequence_number = len(self.established_facts) + 1
            self.established_facts.append(fact)
        
        # 更新大纲
        if delta.chapter_update:
            self._apply_chapter_update(delta.chapter_update)
        
        # 更新预测
        if delta.next_prediction:
            self.next_scene_predictions = delta.next_prediction.likely_next_scenes
        
        # 问题追踪
        self.open_questions.extend(delta.open_questions_added)
        for q in delta.open_questions_resolved:
            if q in self.open_questions:
                self.open_questions.remove(q)
            self.resolved_questions.append(q)
    
    def to_prompt_context(self, mode: str = "standard") -> str:
        """
        渲染为可注入 prompt 的文本
        mode: "standard" / "compact" / "detailed" / "prose"
        """
        ...
    
    def find_conflicting_fact(self, new_fact: Fact) -> Optional[Fact]:
        """查找与新事实矛盾的已有事实"""
        ...


@dataclass
class PaceState:
    """节奏控制状态"""
    current_pace: Literal["frozen", "slow", "normal", "fast", "urgent"] = "normal"
    user_pace_preference: float = 0.5   # 0=喜欢慢 1=喜欢快 (自适应学习)
    scenes_per_chapter_target: int = 5  # 目标章节数
    actual_scenes_this_chapter: int = 0
    ticks_since_last_progress: int = 0   # 距上次剧情推进的tick数
    stagnation_detected: bool = False


@dataclass
class AutoModeConfig:
    """全自动推理配置"""
    enabled: bool = True
    trigger_timeout_seconds: float = 30.0   # 多久无输入触发
    max_auto_ticks: int = 10               # 最大自动推理轮数
    npc_autonomy_level: float = 0.5        # NPC自主程度 0-1
    advance_on_timeout: bool = True        # 超时时是否推进剧情
    pause_on_branch_point: bool = True     # 到达分支点时暂停等待用户
```

### 6.2 输出质量级别与文档格式的关系

| 质量级别                | NarrativeDocument 内容                                  | Novel Agent 职责 | Token 开销               |
| ------------------- | ----------------------------------------------------- | -------------- | ---------------------- |
| **Economy** (省流)    | facts + chapter\_outline + predictions                | 只维护最小必要信息      | 低 (\~500 tokens/更新)    |
| **Standard** (标准)   | 以上 + character\_arcs + open\_questions                | 标准维护           | 中 (\~1500 tokens/更新)   |
| **Quality** (高质量)   | 以上 + prose\_draft + scene\_descriptions + transcripts | 生成小说级文本        | 高 (\~4000 tokens/更新)   |
| **Cinematic** (影视级) | Quality全部 + 详细场景描写 + 多视角POV + 音效提示                    | 影视剧本级输出        | 极高 (\~8000+ tokens/更新) |

> 用户可在运行时切换质量级别。Economy 用于日常对话，Quality/Cinematic 用于重要剧情节点或导出。

***

## 7. 完整数据流

### 7.1 标准交互轮次 (ASYNC 模式, 最常见)

```
时间轴 →

[T-5s] 间隙预计算已完成 (来自上一轮的后台任务)
        NarrativeDocument 已更新到最新版本 v42
        Critic 预计算约束已缓存
        
[T0]    用户发送: "小雪突然拔出剑指着你：'你是谁派来的？'"
        │
        ▼
[Phase 0] 预处理 (<5ms, 纯算法)
        │
        IntentClassifier.classify("...")
        → COMPLEX (含冲突关键词 + 动作)
        │
        加载 NarrativeDocument v42 (已在缓存中, 无IO)
        │
        ▼
[Phase 1] Dialogue Agent (同步, 必须等)
        │
        输入构造:
        ├─ NarrativeDocument.to_prompt_context("detailed")
        │  (包含: 当前事实摘要 + 大纲节拍 + 预测 + 角色弧线)
        ├─ CharacterEntity 完整状态快照
        │  (OCEAN: {80,90,30,95,20} + PAD: {+0.4,+0.2,+0.1} + 七情)
        ├─ 用户原始消息
        ├─ 最近5轮对话历史
        └─ Critic 预计算约束 (如果有)
        
        → LLM Call (Cloud / Local, 取决于IntentLevel)
        → CanonicalIR 输出:
        {
          intent: "defend_cautiously",
          confidence: 0.82,
          emotion_delta: {P:-0.3, A:+0.4, D:-0.1},
          seven_trigger: "惧",
          action: "step_back_draw_weapon",
          action_params: {"distance": "2m"},
          key_points: ["表达惊讶", "后退保持距离", 
                       "质问对方身份", "手握剑柄警戒"],
          tone: "cautious",
          length_hint: "medium",
          narrative_signal: null,
          memory_to_add: {who:"用户", what:"突然拔剑对峙", valence:-0.7}
        }
        │
        ▼
[Phase 2] Algorithm Supreme Court 校验 (<10ms)
        │
        validate_dialogue_ir(ir, character, narrative)
        │
        ├── action "step_back_draw_weapon" 在GOAP可用集合? ✓
        ├── emotion_delta {-0.3, +0.4, -0.1} 在OCEAN范围内? ✓
        │  (N=20低神经质 → 允许较大的arousal波动)
        ├── behavior_consistency? 
        │  personality_score × 0.4 + emotion_score × 0.3 + memory_score × 0.3
        │  = 0.91 ≥ 0.95? → ⚠️ 略低于阈值 → 标记needs_critic_review
        └── 事实一致性? 无新增事实声明 → ✓
        
        → ValidatedIR (带有1个warning, 不阻断)
        │
        ▼
[Phase 3] Critic Agent (本次因warning触发了同步调用)
        │
        正常情况下如果Phase 2干净, Critic可以用上一轮缓存的预检结果
        但这次有behavior_consistency warning → 强制实时调用
        
        → CriticVerdict:
        {
          verdict: "minor_fix",
          overall_confidence: 0.87,
          checks: [
            {dimension:"ooc_detection", severity:"pass", score:0.94},
            {dimension:"narrative_coherence", severity:"info", score:0.78,
             detail:"略显被动,建议增加一丝主动性"},
            {dimension:"fact_consistency", severity:"pass", score:1.0},
            {dimension:"emotion_validity", severity:"pass", score:0.91},
            {dimension:"action_feasibility", severity:"pass", score:0.97},
            {dimension:"behavior_consist", severity:"warning", score:0.91,
             detail:"略低于阈值但在可接受范围"}
          ],
          corrections: {
            suggested_key_point_addition: "可增加一丝试探性的反问",
            narrative_risk_flag: false
          }
        }
        │
        ▼
[Phase 4] 合并与后处理 (<5ms)
        │
        合并 Critic 的 minor_fix 建议:
        → key_points 增加 "试探性反问: 你到底想要什么?"
        │
        最终 CanonicalIR 确定:
        → emotion_after = PAD{P:+0.1, A:+0.6, D:0.0}
        → action = step_back_draw_weapon (确认)
        → reply_points = ["惊讶后退", "质问身份", "警戒", "反问目的"]
        │
        ▼
[Phase 4.5] Atmosphere Agent (<300ms, 可异步缓存命中时<5ms)
        │
        检查 atmosphere_cache:
        │
        ├── 命中? (当前场景 + 当前情感基调 有缓存)
        │   └→ 直接使用缓存的 AtmosphereOutput (Light Mode, ~0ms)
        │
        ├── 未命中? → 调用 Atmosphere Agent
        │   输入:
        │   ├─ NarrativeDocument 最新版 (含刚吸收的fact)
        │   ├─ Final CanonicalIR (知道角色要做什么动作/什么情感)
        │   ├─ 场景当前状态 (光照/天气/时间/在场角色位置)
        │   └─ mood_context = {tension: 0.78, dominant: "threat"}
        │
        │   → AtmosphereOutput:
        │   {
        │     mode: "light",
        │     environment: {
        │       visual: "庭院中的灯笼在风中摇曳, 映出两人拉长的影子。",
        │       auditory: "风穿过回廊的呜咽声, 剑锋出鞘的轻响。",
        │     },
        │     stage_directions: [
        │       {character:"char_xiaoxue", action:"hand_on_hilt",
        │        detail:"右手按上剑柄, 指节因用力而发白"},
        │       {character:"user", action:"standing_threaten",
        │        detail:"剑尖稳稳指向对方, 姿态训练有素"}
        │     ],
        │     mood_declaration: {dominant_emotion:"tension", intensity:0.78,
        │                        color_palette:["#0a0a1a","#1a2a4a","#c4a484"],
        │                        pacing_hint:"slow_breath"},
        │     suggested_position: "wrap",
        │     length_budget: "short"
        │   }
        │
        ▼
[Phase 5] VoiceRenderer (<2ms, 确定性)
        │
        render(canonical_ir, character_voice_profile, rng_seed)
        │
        → "她猛地后退一步，右手本能地按上了腰间的剑柄。
           翠绿的眸子瞬间眯起，原本柔和的气息荡然无存。
           
           '......你到底是什么人？'
           她的声音压得很低，带着一丝不易察觉的颤抖。
           '为什么会知道这个地方......'"
        │
        ▼
[Phase 6] OutputAssembler + 状态更新 + 异步任务启动
        │
        === OutputAssembler (输出组装) ===
        │
        按 atmosphere_output.suggested_position 组装最终回复:
        │
        ├─ case "wrap" (包裹模式, 最常用):
        │   [环境氛围段落]
        │   [舞台指示]
        │   ─────────────
        │   "角色台词内容"  ← VoiceRenderer 输出
        │   [神态/动作微描写]
        │   ─────────────
        │   [氛围过渡收尾]
        │
        └→ 最终完整回复:
           "庭院中的灯笼在风中摇曳，映出两人拉长的影子。
            风穿过回廊的呜咽声与剑锋出鞘的轻响交织在一起。
            
            [她猛地后退一步，右手按上剑柄，指节因用力而发白]
            
            '......你到底是什么人？'
            她的声音压得很低，带着一丝不易察觉的颤抖。
            '为什么会知道这个地方......'
            
            [风雪似乎在这一刻都凝滞了，只剩下彼此的呼吸声。]"
        │
        === 并行状态更新 ===
        │
        ├── character.update_emotion(final_emotion_delta)
        │   PAD: {+0.1, +0.6, 0.0} → 七情更新 → 恐惧激活
        │
        ├── memory_service.write_agent(memory_to_add)
        │   存储: "用户突然拔剑对峙" → emotional_memory
        │
        ├── execute_action(action, params)
        │   GOAP: step_back_draw_weapon → 位置更新
        │
        ├── 存储TrainingSample (完整四智能体数据)
        │   {input_context, novel_output, dialogue_output,
        │    critic_verdict, atmosphere_output, final_reply, ...}
        │
        └── ★ 启动后台异步任务 (间隙预计算, 为下一轮准备) ★
            async_task.launch([
                NovelAgent.background_update(fact=this_turn),
                CriticAgent.precompute(next_round_constraints),
                DialogueAgent.preanalyze(next_prompt_context),
                AtmosphereAgent.prerender_light(current_scene)  // ★ 新增 ★
            ])
        │
        ▼
[Return] 最终回复文本给用户 (含氛围渲染的完整沉浸式回复)
        (同时后台任务已经在跑了)
```

### 7.2 初始化同步流程

```
create_world("2077年的东京，霓虹灯永不熄灭。在这座赛博都市的底层巷弄中...")
    │
    ▼
[SYNC Phase 1] Novel Agent — 创建初始文档
    │
    输入: 原始世界观文本
    + 世界观引导 (WorldViewRenderer 提取的结构化要素)
    + 初始配置 (预计角色数、大致类型)
    │
    任务指令:
    "你是叙事管理员。根据以下世界观设定, 创建初始叙事文档:
     
     [世界观要素: geography/society/culture/history/magic_system/
                technology/politics/religion/ecology]
     
     请输出:
     1. 初始 ChapterOutline (第1章的大纲框架)
     2. 3-5个初始 established_facts (世界的基本事实)
     3. 3个 next_scene_predictions (故事可能的开场方向)
     4. 初步的 open_questions (留作后续展开的悬念)
     5. narrative_note (整体基调说明)"
    │
    输出: NarrativeDelta (完整初始化版, 包含上述全部)
    │
    → NarrativeDocument v1 创建完成
    │
    ▼
[SYNC Phase 2] Critic Agent — 初始审核
    │
    输入: NarrativeDocument v1
    │
    任务指令:
    "审核这份初始叙事文档的质量:
     
     [Document v1 内容...]
     
     检查:
     1. 事实之间有无内在矛盾
     2. 大纲是否合理可行 (是否有明显的死胡同)
     3. 预测的场景是否覆盖了足够的多样性
     4. 是否有足够多的 open_questions 驱动后续发展
     5. 基调是否一致"
    │
    输出: CriticVerdict (初始版)
    │
    → 如果 verdict == accept → 继续
    → 如果有 issues → 人工确认或自动修正后继续
    │
    ▼
[SYNC Phase 2.5] Atmosphere Agent — 初始氛围库建立
    │
    输入: NarrativeDocument v1 + 场景列表
    │
    任务指令:
    "为这个世界建立初始的氛围/感官素材库:
     
     [当前场景列表与描述...]
     [整体基调: narrative_note中的基调说明]
     
     为每个初始场景生成:
     1. 环境基准描写 (visual + auditory + olfactory, 各1-2句)
     2. 默认情感基调 (mood_declaration)
     3. 舞台指示模板集 (该场景常见的动作类型提示)
     
     输出格式: AtmosphereOutput (Full Mode, 每个场景一份)"
    │
    输出: Dict[scene_id, AtmosphereOutput]
    │
    → atmosphere_cache 初始化完成
    → 之后场景切换时可直接使用, 无需等待LLM
    │
    ▼
[SYNC Phase 3] 算法校验 + 引擎注册
    │
    validate_novel_delta(initial_delta)
    → 确认无硬约束违反
    │
    engine.register_narrative_document(doc)
    event_bus.publish(NARRATIVE_NODE_REACHED, payload={"node":"world_created"})
    │
    ▼
[Return] WorldResult {elements, guidance, conflicts:[], document:doc}
    │
    之后所有操作切换到 ASYNC 模式
```

***

## 8. 节奏控制与自动推理

这是你特别强调的需求——平衡快慢两种用户。

### 8.1 节奏感知机制

```python
class PaceSensor:
    """感知用户偏好节奏"""
    
    def __init__(self):
        self._response_intervals: deque[float] = deque(maxlen=20)
        self._scenes_per_session: int = 0
        self._total_session_ticks: int = 0
        self._preference_estimate: float = 0.5  # 0=慢 1=快
    
    def record_interaction(self, tick_interval: float):
        """记录一次交互的时间间隔"""
        self._response_intervals.append(tick_interval)
        self._total_session_ticks += 1
        self._update_preference()
    
    def _update_preference(self):
        """滑动窗口估计用户节奏偏好"""
        if len(self._response_intervals) < 5:
            return
        
        recent_avg = sum(list(self._response_intervals)[-10:]) / min(10, len(self._response_intervals))
        overall_avg = sum(self._response_intervals) / len(self._response_intervals))
        
        # 短间隔 → 快节奏用户 → preference趋近1
        # 长间隔 → 慢节奏用户 → preference趋近0
        if recent_avg < 10:   # <10秒一条消息 → 非常快
            self._preference_estimate = min(1.0, self._preference_estimate + 0.05)
        elif recent_avg > 60:  # >60秒 → 很慢
            self._preference_estimate = max(0.0, self._preference_estimate - 0.03)
        else:
            # 向overall_avg回归
            target = 1.0 - min(recent_avg / 120.0, 1.0)
            self._preference_estimate += (target - self._preference_estimate) * 0.1
    
    @property
    def detected_pace(self) -> str:
        if self._preference_estimate > 0.7:
            return "fast"
        elif self._preference_estimate > 0.3:
            return "normal"
        else:
            return "slow"
    
    @property
    def should_advance_narrative(self) -> bool:
        """判断是否应该主动推进剧情"""
        if self.detected_pace == "fast":
            # 快节奏用户: 每2-3轮自动推进一个节拍
            return self._total_session_ticks % 3 == 0
        elif self.detected_pace == "slow":
            # 慢节奏用户: 不主动推进, 让用户自己探索
            return False
        else:
            # 中等: 每5轮左右推进
            return self._total_session_ticks % 5 == 0
```

### 8.2 自动推理 (AUTO\_MODE) 详细流程

```
触发条件: 用户超过 timeout秒 (默认30s) 未输入
    │
    ▼
[AUTO_START]
    │
    pace_sensor.check() → 确认确实是"停顿"而非"慢节奏思考"
    (如果用户平时就慢, timeout 应该更长)
    │
    ▼
[Auto Round 1] Novel Agent — 推进一小步
    │
    输入: NarrativeDocument (当前) + 上轮结束状态
    │
    特殊指令:
    "用户暂时未响应。请基于当前状态, 推进叙事一小步:
     
     注意:
     - 不要替用户做决定 (不要写'用户说了什么')
     - 只推进环境/NPC/氛围的变化
     - 保持当前场景的延续性
     - 如果当前处于高张力状态, 可以维持张力
     
     输出 NarrativeDelta:"
    │
    示例输出:
    {
      new_facts: [
        {source: "narrative", 
         content: "风雪渐渐大了起来,庭院中的灯光在风中摇曳。",
         tags: ["environment", "atmosphere"], valence: -0.2}
      ],
      chapter_update: {
        current_beat_progress: 0.68,  // 微小推进
        // 大纲不变
      },
      next_prediction: null,  // 不改变预测
      narrative_note: "环境变化暗示着某种不确定性在积累..."
    }
    │
    → NarrativeDocument.apply_delta()
    │
    ▼
[Auto Round 2] Engine Algorithm — NPC自主决策
    │
    对每个在场NPC (非用户控制的角色):
    │
    character.decide(context={
        world_state: narrative.current_world_state,
        narrative_context: narrative.latest_note,
        no_user_present: true  # 关键标志: 用户不在场
    })
    │
    → 每个NPC产生自主行动:
    │   小雪: goap_plan → [observe_surroundings, adjust_stance]
    │   → 决策: "收回剑鞘一半,但仍保持警惕地注视着前方"
    │
    ▼
[Auto Round 3] Dialogue Agent — 生成NPC自主发言 (如有)
    │
    仅当 NPC 决策中包含 "speech" 类行动时触发:
    │
    → 小雪的自主发言 (如果她决定说话):
    "'......风变大了。'"
    (短句, 不推进剧情, 只是维持存在感)
    │
    ▼
[Auto Round 3.5] Atmosphere Agent — 环境渲染 (AUTO_MODE专用)
    │
    AUTO_MODE下的Atmosphere使用 Light Mode:
    基于本轮 Novel Agent 推进的环境变化 + NPC行动
    渲染一段简短的氛围过渡文本
    
    → "[风雪似乎感应到了空气中骤增的张力,
       雪花飘落的速度都放慢了几分。]"
    │
    ▼
[Auto Round 4] Critic Agent — 快速检查
    │
    (AUTO_MODE下的Critic使用轻量版prompt, 降低token消耗)
    │
    → verdict: accept (大概率, 因为都是保守的小步推进)
    │
    ▼
[Auto Output] 将本轮自动推理的结果推送给用户
    │
    格式 (含 Atmosphere 渲染):
    ┌──────────────────────────────────────┐
    │ 🌨️ [自动推进] 风雪渐大...              │
    │                                      │
    │ [风雪似乎感应到了空气中骤增的张力,     │ ← Atmosphere Agent
    │   雪花飘落的速度都放慢了几分。]       │
    │                                      │
    │ 小雪缓缓将剑收回一半,目光依然警惕地   │ ← Engine + Dialogue
    │ 锁在你身上,但紧绷的肩膀微微放松了些。  │
    │                                      │
    │ "......风变大了。"                    │
    │                                      │
    │ [庭院中的灯笼在风中晃动了一下,        │ ← Atmosphere 收尾
    │  映出两人之间那道无形的界线]          │
    │                                      │
    │ 💡 继续你的行动,或等待更多发展...     │
    └──────────────────────────────────────┘
    │
    ▼
[Auto Loop Check]
    │
    ├── auto_tick_count < max_auto_ticks?
    │   ├── YES → 等 5-8秒 → 回到 [Auto Round 1]
    │   │         (给用户看到推送后的反应时间)
    │   │
    │   └── NO → 暂停, 回到 IDLE
    │
    └── 检测到 branch_point?
        ├── YES → 暂停AUTO_MODE, 等待用户选择
        │   "剧情到了分岔口, 请你来决定..."
        │
        └── NO → 继续循环
```

### 8.3 快/慢用户的差异化策略

```
┌─────────────────────────────────────────────────────────┐
│                    节奏自适应策略                          │
│                                                         │
│  ┌─────────── 快节奏用户 ───────────┐  ┌───── 慢节奏用户 ──┐
│  │                                   │  │                   │
│  │ 特征: 5-15秒/条消息               │  │ 特征: 60-300秒/条  │
│  │ 行为: 快速推进, 想看剧情发展       │  │ 行为: 仔细品味,   │
│  │                                   │  │   沉浸体验         │
│  │ 策略:                             │  │                   │
│  │ ├─ Novel Agent 更新频率: 每2轮    │  │ ├─ 更新频率: 每5轮  │
│  │ ├─ chapter_outline 进度: 加速     │  │ ├─ 大纲: 更细致    │
│  │ ├─ AUTO_MODE timeout: 45s        │  │ ├─ timeout: 90s    │
│  │ ├─ 每章目标场景数: 8-12 (多)      │  │ ├─ 每章场景数: 3-5  │
│  │ ├─ 预测偏向: forward-looking       │  │ ├─ 预测: 更多细节   │
│  │ └─ prose_draft: Economy模式       │  │ └─ prose: Quality   │
│  │                                   │  │                   │
│  │ 目标: 让剧情跟上用户的速度         │  │ 目标: 让每个场景都   │
│  │       不让用户感到"拖沓"           │  │       充满可发现的细节│
│  └───────────────────────────────────┘  └───────────────────┘
│                                                         │
│  ┌─────────── 自适应调整 ─────────────┐                   │
│  │                                   │                   │
│  │ 实时信号:                          │                   │
│  │ ├─ 用户在某场景停留 > N轮          │                   │
│  │ │   → 自动解锁该场景的隐藏细节     │                   │
│  │ │   → Novel Agent 补充环境描写     │                   │
│  │ │   → 增加NPC的 ambient 行为       │                   │
│  │ │                                   │                   │
│  │ ├─ 用户连续快速跳过多个场景         │                   │
│  │ │   → 自动合并次要场景为概述       │                   │
│  │ │   → chapter_outline 压缩模式     │                   │
│  │ │                                   │                   │
│  │ └─ 用户突然从快转慢 (或反之)        │                   │
│  │     → 平滑过渡 (不突变)            │                   │
│  │     → 过渡期 3-5 轮混合策略         │                   │
│  └───────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

***

## 9. 训练数据与蒸馏对齐

### 9.1 完整训练样本结构

```python
@dataclass
class TrainingSample:
    """一轮完整交互产生的结构化训练样本"""
    
    # === 元数据 ===
    sample_id: str
    world_id: str
    character_id: str
    timestamp: float
    narrative_version: int           # 产生此样本时的文档版本
    
    # === 输入侧 (本地模型需要看到的) ===
    input: TrainingInput
    
    # === 四智能体的原始输出 (监督信号) ===
    agent_outputs: AgentOutputs
    
    # === 算法层的修正 (Ground Truth 的校正来源) ===
    algorithm_corrections: AlgorithmCorrections
    
    # === 最终采纳结果 (最终 Ground Truth) ===
    final_output: FinalOutput
    
    # === 质量标注 ===
    quality: SampleQuality
    
    # === 训练用途分类 ===
    usage_tags: List[str]  # ["layer1_narrative", "layer2_decision", 
                          #  "layer3_voice", "layer4_critic",
                          #  "layer5_atmosphere",        ★ 新增 ★
                          #  "correction_example", "edge_case"]


@dataclass
class TrainingInput:
    """标准化输入 (脱敏后)"""
    
    narrative_summary: str              # NarrativeDocument 压缩摘要
    narrative_facts_recent: List[str]  # 最近10条事实
    chapter_context: str               # 当前章节/节拍上下文
    user_message: str                  # 用户消息 (已脱敏)
    character_state_snapshot: CharacterStateSnapshot
    scene_context: str                 # 场景信息
    recent_exchanges: List[ExchangeSummary]  # 最近5轮摘要
    pace_context: str                  # 当前置节奏信息


@dataclass
class AgentOutputs:
    """四个智能体的原始输出"""
    
    novel: Optional[NarrativeDelta]       # None 如果未触发
    dialogue: CanonicalIR                # 总是有
    critic: Optional[CriticVerdict]      # None 如果未触发
    atmosphere: Optional[AtmosphereOutput]  # None 如果未触发 ★ v0.3 新增 ★
    
    # 元信息
    novel_token_usage: int = 0
    dialogue_token_usage: int = 0
    critic_token_usage: int = 0
    atmosphere_token_usage: int = 0      # ★ v0.3 新增 ★
    total_latency_ms: int = 0


@dataclass
class AlgorithmCorrections:
    """算法层对LLM输出的修正记录"""
    
    dialogue_corrections: List[CorrectionRecord] = field(default_factory=list)
    novel_corrections: List[CorrectionRecord] = field(default_factory=list)
    
    @property
    def was_overridden(self) -> bool:
        return any(c.severity == "override" for c in self.dialogue_corrections)


@dataclass
class CorrectionRecord:
    field: str
    original_value: Any
    corrected_value: Any
    reason: str
    severity: Literal["clamp", "replace", "override", "reject"]


@dataclass
class FinalOutput:
    """最终采纳的结果"""
    
    reply_text: str                   # 用户看到的最终文本
    executed_action: str              # 执行的动作
    final_emotion: PADState            # 最终情感状态
    memory_entries_created: List[str]  # 创建的记忆ID
    narrative_version_after: int       # 更新后的文档版本
    
    # 来源追溯
    dialogue_source: Literal["original", "critic_minor", 
                               "critic_major", "algorithm_override",
                               "fallback_local", "fallback_template"]
    voice_renderer_used: bool


@dataclass
class SampleQuality:
    """样本质量评估"""
    
    overall_score: float               # 0-1
    coherence_score: float            # 内部一致性
    character_faithfulness: float      # 角色还原度
    narrative_alignment: float         # 剧情契合度
    
    grade: Literal["gold", "silver", "bronze", "contaminated", "quarantine"]
    
    # 污染标记
    contamination_flags: List[str] = field(default_factory=list)
    # 例: ["mixed_character_style", "narrative_drift_detected",
    #       "critic_overrode_dialogue", "algorithm_overrode_llm"]
```

### 9.2 分层蒸馏策略

```
┌──────────────────────────────────────────────────────────┐
│                   四层蒸馏架构                             │
│                                                          │
│  ┌────────────────────────────────────────────────┐     │
│  │ Layer 1: Narrative Comprehension (通用)          │     │
│  │ ─────────────────────────────────────────       │     │
│  │                                                  │     │
│  │ 输入: (narrative_summary + user_action + world)  │     │
│  │ 学习目标: 预测 NarrativeDelta                   │     │
│  │                                                  │     │
│  │ 训练数据: 所有角色的 Novel Agent 输出混合         │     │
│  │ 模型: 通用基础模型 (不区分角色)                    │     │
│  │ 损失:                                              │     │
│  │   L = α·L_facts_match                             │     │
│  │     + β·L_chapter_direction                      │     │
│  │     + γ·L_prediction_ranking                     │     │
│  │     + δ·L_constraint_satisfaction                │     │
│  │                                                  │     │
│  │ 用途: DEGRADED 时充当 Novel Agent                 │     │
│  └──────────────────────┬───────────────────────────┘     │
│                         │                                │
│  ┌──────────────────────▼───────────────────────────┐     │
│  │ Layer 2: Decision Making (角色特定)              │     │
│  │ ─────────────────────────────────────────       │     │
│  │                                                  │     │
│  │ 输入: (narrative_doc + character_state + msg)    │     │
│  │ 学习目标: 预测 CanonicalIR (intent/action/emotion)│    │
│  │                                                  │     │
│  │ 训练数据: 按 character_id 分桶存储               │     │
│  │   training_data/{char_id}/layer2/*.json          │     │
│  │                                                  │     │
│  │ 模型架构:                                        │     │
│  │   base_model (通用) + LoRA_adapter(char_id)      │     │
│  │   或: 一个模型 + role-specific prefix embedding  │     │
│  │                                                  │     │
│  │ 损失:                                              │     │
│  │   L = α·L_intent_classification                   │     │
│  │     + β·L_action_matching (必须在GOAP集合内)      │     │
│  │     + γ·L_emotion_cosine (与OCEAN约束一致)        │     │
│  │     + δ·L_keypoints_coverage (ROUGE vs ground)    │     │
│  │     + ε·L_consistency_penalty (违反behavior_check)│    │
│  │                                                  │     │
│  │ 用途: DEGRADED 时充当 Dialogue Agent              │     │
│  └──────────────────────┬───────────────────────────┘     │
│                         │                                │
│  ┌──────────────────────▼───────────────────────────┐     │
│  │ Layer 3: Voice Rendering (角色特定, 风格层)      │     │
│  │ ─────────────────────────────────────────       │     │
│  │                                                  │     │
│  │ 输入: (CanonicalIR + voice_profile + scene)      │     │
│  │ 学习目标: 生成 reply_text                        │     │
│  │                                                  │     │
│  │ 训练数据: 按 character_id 分桶                    │     │
│  │   training_data/{char_id}/layer3/*.json          │     │
│  │                                                  │     │
│  │ 模型: 每个角色独立的 voice model (较小)          │     │
│  │   或: 模板驱动 VoiceRenderer (v1, 无需训练)       │     │
│  │                                                  │     │
│  │ 损失:                                              │     │
│  │   L = α·L_text_similarity (embedding cosine)      │     │
│  │     + β·L_style_match (style_classifier score)    │     │
│  │     + γ·L_length_compliance                       │     │
│  │     + δ·L_keyword_inclusion (key_points覆盖率)    │     │
│  │                                                  │     │
│  │ 用途: 始终使用 (即使云端模式也经过VoiceRenderer)   │     │
│  └──────────────────────┬───────────────────────────┘     │
│                         │                                │
│  ┌──────────────────────▼───────────────────────────┐     │
│  │ Layer 4: Critic Judgment (通用, 带角色感知)      │     │
│  │ ─────────────────────────────────────────       │     │
│  │                                                  │     │
│  │ 输入: (dialogue_output + narrative + char_state) │     │
│  │ 学习目标: 预测 CriticVerdict                     │     │
│  │                                                  │     │
│  │ 训练数据: 所有角色的 Critic 输出混合              │     │
│  │   但按 strictness_level 分桶:                     │     │
│  │     strict_chars (OCEAN极端值) → 高精度要求       │     │
│  │     flexible_chars (中间值) → 宽松要求            │     │
│  │                                                  │     │
│  │ 模型: 轻量分类器 (可下沉到纯规则)                  │     │
│  │                                                  │     │
│  │ 损失:                                              │     │
│  │   L = α·L_verdict_accuracy                         │     │
│  │     + β·L_severity_ranking                        │     │
│  │     + γ·L_check_score_calibration                │     │
│  │                                                  │     │
│  │ 用途: DEGRADED 时替代 Critic Agent                │     │
│  └──────────────────────────────────────────────────┘     │
│                                                          │
│  ═════════════════════════════════════════════════       │
│         污染防护 (Per-Character Data Hygiene)           │
│  ═════════════════════════════════════════════════       │
│                                                          │
│  storage/                                                 │
│  ├── raw/                                                │
│  │   └── {world_id}/{character_id}/                      │
│  │       ├── layer1_narrative/  ← 所有角色共享           │
│  │       ├── layer2_decision/   ← 角色隔离 ⚠️           │
│  │       ├── layer3_voice/      ← 角色隔离 ⚠️⚠️         │
│  │       └── layer4_critic/    ← 按strictness分组        │
│  │                                                      │
│  ├── processed/                                          │
│  │   └── (同上结构, 经过清洗和去标识化)                   │
│  │                                                      │
│  └── quarantine/                                         │
│      └── (污染样本隔离区, 不参与训练)                     │
│                                                          │
│  清洗流水线:                                             │
│  1. 去标识化 (移除用户个人信息, API key等)                │
│  2. 角色ID验证 (确保 sample.character_id 匹配存储路径)     │
│  3. 质量过滤 (score < 0.3 → quarantine)                  │
│  4. 一致性检查 (sample内部不自相矛盾)                     │
│  5. 污染检测 (cross-contamination signature scan)         │
└──────────────────────────────────────────────────────────┘
```

***

## 10. 降级策略

### 10.1 四级降级路径

```
DegradationLevel.NORMAL (正常)
    │
    │  Cloud LLM 可用 → 全部四个Agent都用Cloud (含 Atmosphere)
    │  NarrativeDocument 质量: Quality/Cinematic
    │
    │  连续失败 3 次 ↓
    │
DegradationLevel.DEGRADED (降级-本地LLM)
    │
    │  Cloud 不可用 → 切换到 LocalLLMAdapter
    │
    │  Dialogue Agent → Local Model (Layer 2 + Layer 3)
    │  Novel Agent → Local Model (Layer 1)
    │  Critic Agent → 算法一致性检查器 (Layer 4 下沉到规则)
    │  Atmosphere Agent → 模板引擎 + PCG 扰动     ★ v0.3 新增 ★
    │     Light Mode: 场景名+情感词模板拼接         │
    │     Full Mode: 降级为 Light Mode (跳过完整渲染) │
    │     stage_directions: 从 GOAP action 推断       │

    │  NarrativeDocument 质量: Standard (降一级)
    │  VoiceRenderer: 不变 (确定性, 不依赖模型)
    │
    │  关键保证:
    │  ✓ NarrativeDocument 仍然在更新 (Layer 1 本地模型能跑)
    │  ✓ 角色决策基于最新文档 (不会脱离剧情)
    │  ✓ 表达风格一致 (VoiceRenderer 保证)
    │  ✗ 决策精细度下降 (本地模型不如Cloud)
    │  ✗ 文档更新深度下降 (delta没那么丰富)
    │
    │  连续失败 5 次 (累计) ↓
    │
DegradationLevel.SEVERELY_DEGRADED (严重降级)
    │
    │  LocalLLMAdapter 也不可用
    │
    │  Dialogue Agent → VoiceRenderer 直接渲染
    │     (基于 NarrativeDocument + 算法状态, 无需LLM)
    │     使用预设回复模板 + PCG随机扰动
    │
    │  Novel Agent → 规则引擎 (增量式更新)
    │     只做: 新fact吸收 + 序列号递增 + timeline推进
    │     不做: 大纲重写 + 预测刷新
    │
    │  Critic Agent → 纯算法 (behavior_consistency + fact_check)
    │  Atmosphere Agent → 纯模板 (极简)           ★ v0.3 新增 ★
    │     输出格式: "[{scene_name}] — {mood_word}"  │
    │     无环境描写, 无舞台指示, 无旁白              │
    │     token预算: < 50                           │

    │  NarrativeDocument 质量: Economy (最低可用)
    │
    │  功能保持率: ~60%
    │
    │  连续失败 10 次 (累计) ↓
    │
DegradationLevel.OFFLINE (离线)
    │
    │  完全无法调用任何LLM
    │
    │  所有Agent退化为:
    │  - 纯算法驱动 (GOAP + OCEAN + PAD + Motivation)
    │  - 模板化回复 (VoiceRenderer fallback templates)
    │  - 规则化文档更新 (最小事实记录)
    │  - 氛围降级为极简标记或完全跳过               ★ v0.3 新增 ★

    │  定期探测恢复 (每30s)
    │  恢复条件: 连续成功 2 次 → 回到 SEVERELY → 逐步回升
```

### 10.2 降级时的 NarrativeDocument 保护

```python
class DegradationDocumentProtector:
    """降级期间保护 NarrativeDocument 不退化"""
    
    def __init__(self, doc: NarrativeDocument):
        self.doc = doc
        self._last_good_version = doc.version
        self._degradation_start_version = doc.version
    
    def safe_apply_delta(self, delta: NarrativeDelta, 
                          source: str) -> bool:
        """安全地应用降级期间的delta"""
        
        # 1. 降级期间禁止删除或修改已确立事实
        for fact in delta.new_facts:
            conflicting = self.doc.find_conflicting_fact(fact)
            if conflicting and source != "cloud":
                # 只有Cloud来源的才能覆盖已有事实
                # 降级来源的不允许
                return False
        
        # 2. 降级期间不允许收缩 chapter_outline
        if delta.chapter_update:
            current = self.doc.current_chapter_outline
            if current and delta.chapter_update:
                # 不允许减少beats数量
                if len(delta.chapter_update.beats) < len(current.beats):
                    delta.chapter_update.beats = current.beats
        
        # 3. 降级期间 prediction 置信度打折
        if delta.next_prediction:
            for pred in delta.next_prediction.likely_next_scenes:
                pred.probability *= 0.7  # 降级预测打7折
        
        self.doc.apply_delta(delta)
        return True
```

***

## 11. 扩展性：图片/语音生成

### 11.1 NarrativeDocument 作为多媒体生成源

### 11.1.1 Atmosphere Agent → 多媒体桥接 (v0.3 新增)

Atmosphere Agent 的输出天然是多媒体生成的**前置处理层**:

| Atmosphere 输出字段 | 多媒体用途 | 映射关系 |
|---|---|---|
| `mood_declaration.color_palette` | 场景插图色彩 | 直接作为 image prompt 的 color guide |
| `environment.visual` | 场景插图视觉基础 | 提取实体(灯笼/石柱/积雪)→ 构图元素 |
| `environment.auditory` | BGM/SFX 选择 | 关键词(风声/鸟鸣/寂静)→ 音效库检索 |
| `stage_directions` | 角色肖像姿态 | action字段 → character pose prompt |
| `mood_declaration.dominant_emotion` | 光影风格 | tension→冷光/高对比; warmth→暖光/柔焦 |
| `mood_declaration.pacing_hint` | 镜头语言 | slow_breath→固定长镜头; urgent→快速剪辑 |

数据流增强:
```
AtmosphereOutput
  ├──→ MediaGenerationRequest.style_directives (色彩/光影/构图)
  ├──→ MediaGenerationRequest.composition_hint (角色姿态)
  └──→ MediaGenerationPipeline.preprocess() (氛围预处理)
```

你说得对——让LLM写"小说"的本质目的是为了后期扩展。以下是具体的对接设计：

```python
@dataclass
class MediaGenerationRequest:
    """从叙事文档派生的媒体生成请求"""
    
    source_type: Literal["scene_illustration", "character_portrait", 
                          "event_panel", "emotional_atmosphere",
                          "item_detail", "map_fragment"]
    
    source_ref: str                   # 引用的叙事元素ID
    # 例: fact_042, scene_prediction_2, beat_3
    
    narrative_context: str            # 从 NarrativeDocument 提取的上下文
    # 例: "雪之庭院, 风雪渐大, 小雪拔剑对峙, 绿眸警惕"
    
    style_directives: Dict[str, str]  # 风格指导
    # 例: {"mood": "tense", "lighting": "cold_moonlight", 
    #       "color_palette": "#1a1a2e-#16213e-#0f3460"}
    
    characters_present: List[str]    # 画面中的角色ID列表
    composition_hint: str            # 构图提示
    
    @classmethod
    def from_narrative_element(cls, doc: NarrativeDocument, 
                                element_type: str, element_id: str) -> 'MediaGenerationRequest':
        """从叙事文档元素自动构建生成请求"""
        ...


@dataclass
class MediaGenerationPipeline:
    """多媒体生成管线 (未来扩展点)"""
    
    def __init__(self, config: MediaConfig):
        self.image_generator: Optional[Any] = None  # SD/DALL-E/Midjourney API
        self.voice_generator: Optional[Any] = None   # TTS API
        self.style_transfer: Optional[Any] = None     # 风格迁移
        self.cache: MediaCache = MediaCache()
    
    def generate_scene_image(self, request: MediaGenerationRequest) -> MediaAsset:
        """
        从 NarrativeDocument 的场景描述生成插图
        
        数据流:
        NarrativeDocument.scene_descriptions[scene_id]
            → 提取视觉元素 (天气/光线/物体/角色位置)
            → 构建 image prompt (结合世界观风格)
            → 调用图像生成API
            → 缓存 + 关联到叙事文档
        """
        ...
    
    def generate_character_portrait(self, char_id: str, 
                                     emotion: SevenEmotionType,
                                     scene: str) -> MediaAsset:
        """
        根据角色当前情感状态生成肖像/表情包
        
        数据流:
        CharacterEntity.current_visual_state
            (OCEAN + PAD + 七情 + 场景光照)
            → 渲染为图像生成prompt
            → 保持角色视觉一致性 (固定seed/LoRA)
        """
        ...
    
    def generate_voice_line(self, text: str, 
                            character_voice_profile: VoiceProfile) -> AudioAsset:
        """
        将 VoiceRenderer 的输出转为语音
        
        数据流:
        reply_text (VoiceRenderer输出)
            → TTS with voice profile (音色/语速/语调基于OCEAN)
            → 情感韵律调制 (PAD影响语调起伏)
        """
        ...
    
    def generate_event_panel(self, fact: Fact, 
                              style: str = "manga") -> MediaAsset:
        """
        从关键事实生成漫画式事件面板
        
        用于: 重要剧情节点的可视化回顾/分享
        """
        ...
```

### 11.2 质量级别与媒体输出的关系

| 叙事质量      | 图片生成                | 语音生成             | 用途              |
| --------- | ------------------- | ---------------- | --------------- |
| Economy   | 无                   | 无                | 纯文字交互           |
| Standard  | 场景缩略图 (可选)          | 无                | 带简单插图的文字冒险      |
| Quality   | 场景插图 + 角色表情         | 角色语音             | Visual Novel 风格 |
| Cinematic | CG级场景 + 动态肖像 + 事件CG | 全员配音 + BGM + SFX | 互动电影/游戏级体验      |

> 这意味着用户选择的"输出质量"不仅影响文本丰富度，还决定了多媒体输出的级别。这是一个很好的商业化/体验分层设计。

***

## 12. 实施路线图

### Phase 0: 基础设施 (Week 1-2)

```
目标: 让 NarrativeDocument 能在现有引擎中跑起来

 deliverables:
   [ ] NarrativeDocument 数据结构 (§6.1 全部 dataclass)
   [ ] NarrativeDelta 差量应用逻辑
   [ ] AlgorithmSupreme Court 校验器框架 (§4.2)
   [ ] PaceSensor 节奏感知器 (§8.1)
   [ ] TrainingSample 数据结构与采集管道 (§9.1)
   [ ] AtmosphereOutput 数据结构 (§3.2 Atmosphere Agent 输出格式)  ★ v0.3 新增 ★
   [ ] 降级文档保护器 (§10.2)
   
 验证:
   - 现有 test_engine_integration 通过
   - 新增 test_narrative_document (CRUD + delta + version)
   - 新增 test_algorithm_supreme Court (约束层级)
```

### Phase 1: 四智能体 Prompt 工程 (Week 2-3)

```
目标: 四个Agent能用Prompt产出正确的JSON输出

 deliverables:
   [ ] Dialogue Agent System Prompt (含JSON mode指令)
   [ ] Novel Agent System Prompt (含delta格式指令)
   [ ] Critic Agent System Prompt (含verdict格式指令)
   [ ] Atmosphere Agent System Prompt (含Light/Full模式切换指令)  ★ v0.3 新增 ★
   [ ] PromptBuilder 增强 (支持四种agent的context注入)
   [ ] ResponseParser 增强 (三种JSON格式解析)
   
 验证:
   - 手动测试 20-30 轮 (每个Agent单独)
   - JSON解析成功率 > 95%
   - 输出字段完整性 > 90%
```

### Phase 2: 异步协作引擎 (Week 3-4)

```
目标: 间隙预计算 + AUTO_MODE 能跑通

 deliverables:
   [ ] AsyncTaskScheduler (后台任务调度器)
   [ ] GapPrecomputer (间隙预计算协调器)
   [ ] AutoModeExecutor (全自动推理执行器)
   [ ] 状态机实现 (IDLE ↔ SYNC ↔ RESPONDING ↔ ASYNC_PREP ↔ READY ↔ AUTO)
   [ ] EventBus 事件扩展 (async_task_complete / auto_tick / pace_change)
   
 验证:
   - 间隙预计算在用户输入间隙正确执行
   - AUTO_MODE 能自主推进 5-10 轮不崩溃
   - 分支点处正确暂停等待用户
   - 快/慢用户节奏自适应生效
```

### Phase 3: 端到端集成 (Week 4-5)

```
目标: 完整的四智能体协作能在引擎中运行

 deliverables:
   [ ] engine.py 集成 (chat() 方法改造)
   [ ] create_world() 同步初始化流程
   [ ] VoiceRenderer v1 (模板驱动)
   [ ] 完整数据流打通 (§7.1)
   [ ] 训练数据自动采集 (每轮写入文件)
   
 验证:
   - 10轮手动对话测试, 全程无崩溃
   - NarrativeDocument 版本单调递增
   - 四个Agent输出都能被正确解析和校验
   - 降级路径 (NORMAL → DEGRADED) 可手动触发测试
   - Token成本监控 (目标 ≤ 1.2x)
```

### Phase 4: 本地模型对齐 (Week 5-8)

```
目标: 本地模型能接管 Layer 1-4

 deliverables:
   [ ] 训练数据清洗管道 (去标识/质量过滤/污染检测)
   [ ] Layer 1 Narrative Comprehension 模型训练
   [ ] Layer 2 Decision Making 模型训练 (per-character LoRA)
   [ ] Layer 4 Critic Judgment 模型/规则
   [ ] VoiceRenderer v1 验证 (模板质量达标)
   [ ] DEGRADED 模式端到端测试
   
 验证:
   - 收集 ≥ 1000 条高质量训练样本
   - Layer 1 BLEU > 0.6 (vs Cloud Novel Agent)
   - Layer 2 Intent accuracy > 0.8
   - DEGRADED 模式用户体验评分 ≥ 7/10
   - 断连后 NarrativeDocument 仍在正常更新
```

### Phase 5: 多媒体扩展 (Week 8+)

```
目标: 图片/语音生成管线接入

 deliverables:
   [ ] MediaGenerationRequest 数据结构
   [ ] 图像生成API对接 (SD/DALL-E)
   [ ] TTS API对接 + 角色音色配置
   [ ] NarrativeDocument ↔ MediaAsset 关联
   [ ] 质量级别 → 多媒体级别映射
   
 验证:
   - 场景插图能从叙事文档自动生成
   - 角色语音与OCEAN/PAD状态联动
   - 不同质量级别的多媒体输出差异明显
```

***

## 附录 A: 关键接口签名

```python
# === NarrativeDocument ===
def apply_delta(self, delta: NarrativeDelta) -> None: ...
def to_prompt_context(self, mode: str = "standard") -> str: ...
def find_conflicting_fact(self, new_fact: Fact) -> Optional[Fact]: ...

# === Core Agents (v0.3: +Atmosphere) ===
async def dialogue_agent_run(
    context: DialogueContext,       # narrative + character + user_msg + history
    llm_bridge: LLMBridge,
    cached_constraints: Optional[Dict] = None,  # Critic预计算
) -> CanonicalIR: ...

async def novelist_agent_run(
    context: NovelContext,          # latest events + current doc + worldview
    llm_bridge: LLMBridge,
    mode: Literal["full_update", "incremental", "prediction_only"],
) -> NarrativeDelta: ...

async def critic_agent_run(
    context: CriticContext,         # dialogue_output + narrative + algorithm_results
    llm_bridge: LLMBridge,
    mode: Literal["full", "light"],  # light=AUTO_MODE用
) -> CriticVerdict: ...

# === Atmosphere Agent (v0.3 新增) ===
async def atmosphere_agent_run(
    context: AtmosphereContext,    # scene_data + recent_events + mood_baseline
    llm_bridge: LLMBridge,
    mode: Literal["light", "full"],  # light=每轮, full=场景切换
) -> AtmosphereOutput: ...

async def prerender_atmosphere_light(
    scene_id: str,
    recent_events: List[Fact],
    current_mood: MoodDeclaration,
) -> AtmosphereOutput: ...
    """轻量预渲染 (间隙预计算 Task D)"""

async def prerender_atmosphere_full(
    scene_id: str,
    target_scene_id: str,        # 即将进入的新场景
    transition_type: str,        # abrupt/fade/walk/cut
    characters_present: List[str],
) -> AtmosphereOutput: ...
    """完整渲染 (场景切换时)"""

def assemble_output(
    dialogue_text: str,          # VoiceRenderer 输出
    atmosphere: Optional[AtmosphereOutput],
    assembly_mode: str = "wrap", # prefix/suffix/wrap/interleave
) -> str: ...
    """OutputAssembler: 组装最终沉浸式回复"""

# === Algorithm Supreme Court ===
def validate_dialogue_ir(ir: CanonicalIR, character, narrative) -> ValidatedIR: ...
def validate_novel_delta(delta: NarrativeDelta, narrative) -> ValidatedDelta: ...

# === Async Scheduler ===
async def start_gap_precomputation(latest_sample: TrainingSample) -> None: ...
async def execute_auto_mode(world_id: str, max_ticks: int = 10) -> AutoModeResult: ...

# === Voice Renderer ===
def render(ir: CanonicalIR, voice_profile: VoiceProfile, seed: int) -> str: ...

# === Training Pipeline ===
def collect_sample(interaction_record: InteractionRecord) -> TrainingSample: ...
def sanitize_and_store(sample: TrainingSample, storage_path: Path) -> bool: ...
def train_layer(model_type: str, char_id: Optional[str], epochs: int) -> TrainResult: ...
```

***

## 附录 B: 术语表

| 术语                     | 定义                                       |
| ---------------------- | ---------------------------------------- |
| NarrativeDocument      | 活体叙事状态文档, 所有智能体共享的唯一真相源                  |
| NarrativeDelta         | 叙事文档的差量更新 (只包含变化部分)                      |
| CanonicalIR            | 规范化的中间表示 (对话Agent的结构化输出)                 |
| CriticVerdict          | 批判Agent的质量判定结果                           |
| ValidatedIR            | 经过AlgorithmSupreme Court校验后的IR           |
| VoiceRenderer          | 确定性语音渲染器 (IR→自然语言)                       |
| Gap Precomputation     | 利用用户输入间隙进行的后台计算                          |
| AUTO\_MODE             | 全自动推理模式 (用户无输入时引擎自主推进)                   |
| PaceSensor             | 用户节奏偏好感知器                                |
| AlgorithmSupreme Court | 引擎算法最高校验层                                |
| TrainingSample         | 单轮交互产生的完整训练数据                            |
| Layer 1-5              | 五层蒸馏架构 (Narrative/Decision/Voice/Critic/Atmosphere) |
| AtmosphereOutput      | 氛围Agent的结构化输出 (环境/旁白/舞台指示/基调)             |
| OutputAssembler       | 最终输出组装器 (将 Atmosphere + Dialogue 合并为沉浸式回复)     |
| Light Mode            | Atmosphere Agent 轻量模式 (~200-400 tokens, 每轮触发)        |
| Full Mode             | Atmosphere Agent 完整模式 (~800-1500 tokens, 场景切换时触发)  |
| AtmosphereMerge       | 氛围注入器 (将 AtmosphereOutput 按位置策略注入最终文本)       |

***

*文档结束。本设计整合了用户提出的四智能体协作方案（Dialogue + Novel + Critic + Atmosphere）、异步间隙预计算、引擎算法至高无上、节奏自适应、训练数据防污染等全部需求。*
