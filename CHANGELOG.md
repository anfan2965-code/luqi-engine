# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0.12-beta] - 2026-05-06

### Added

#### 五层叙事引擎架构 (Narrative Engine v1)
- **Layer5 - StoryArcController**: 叙事弧控制器，起承转合四阶段生命周期管理
  - `ArcPhase` 枚举: 起(EXPOSITION)/承(RISING_ACTION)/转(CLIMAX)/合(RESOLUTION)
  - 阶段感知指令集: 场景节奏、主线权重、冲突强度、角色引入率
  - 阶段转换记录与历史追踪
- **Layer5 - StoryformEngine**: Storyform核心不平等均衡算法
  - 5个默认不平等维度: 强弱势力差距 / 真相隐藏程度 / 忠诚与背叛张力 / 资源稀缺程度 / 正邪界限模糊度
  - 加权综合张力计算 (权重可自定义)
  - `StoryformInequality` 支持完全自定义不平等维度
- **Layer5 - DramatisSuspenseModel**: Dramatis悬念模型
  - 基于主角可用逃生计划数量的悬念计算
  - 威胁等级 + 时间压力 + 可用计划数 三维输入
  - 悬念值范围 [0, 1]，无逃生计划时趋向1.0

#### Layer4 - PlotThreadManager (主线/支线管理器)
- **PlotThread** 数据结构: 主线(MAIN_PLOT)/支线(SIDE_QUEST)/涌现(EMERGENT)三种类型
- **5个主线剧情点** (武侠战争主题):
  1. 杀父线索浮现 → 2. 朝廷阴谋揭露 → 3. 门派内部背叛 → 4. 真相大白 → 5. 最终决战
- **Storylet触发系统**: 自然语言条件定义的叙事事件自动激活
- 线程优先级动态调整: 主线 > 高优先级支线 > 涌现线程
- 张力计算: `calculate_main_plot_tension()` / `calculate_side_plot_tension()`

#### Layer3 - SceneResidencyEngine (场景驻留引擎)
- **Beat序列管理**: BeatSequence / Beat数据结构，6种Beat类型
- **动态Beat粒度算法**:
  - 输入: 主线张力(60%权重) + 支线张力(40%权重) + 叙事弧阶段乘数 + 当前场景张力
  - 输出: 每个Beat包含的对话轮次 (1~4轮)
  - 低张力→4轮/Beat, 中等→3轮/Beat, 高张力→2轮/Beat, 极高→1轮/Beat
- **场景驻留决策**: `should_continue_scene()` 综合判断
  - 未解决冲突 + 主角在场 + 推进主线 → 驻留
  - 无冲突且无主角 → 切换场景
- **场景切换通知**: start_scene() / end_scene() 完整生命周期

#### Layer2 - CharacterStratifier (角色分层器)
- **三层分层体系**: 核心层(CORE) / 活跃层(ACTIVE) / 背景层(BACKGROUND)
- **突出度衰减机制**: prominence_score每轮衰减0.02，事件提升+0.15
- **动态升降级**: 每25轮重新分类，基于突出度和事件参与度
- **分组轮换**: rotate_faction_focus() 按阵营轮流聚焦
- **NarrativeMemory**: 分层叙事记忆，记录重要事件和关系变化

#### Layer1 - EmergenceDetector (涌现检测器)
- **三预选敏感度方案** (脚本设计师可选):
  | 方案 | SI阈值 | CS阈值 | II阈值 | 最小交互次数 | 冷却轮次 |
  |------|--------|--------|--------|-------------|----------|
  | CONSERVATIVE(保守型) | ≥0.75 | ≥0.65 | ≥0.55 | 8次 | 30轮 |
  | BALANCED(均衡型) | ≥0.60 | ≥0.50 | ≥0.40 | 5次 | 20轮 |
  | AGGRESSIVE(激进型) | ≥0.40 | ≥0.35 | ≥0.25 | 3次 | 10轮 |
- **完全自定义接口**: `EmergenceThresholds(si_threshold, cs_threshold, ii_threshold, min_interaction_count, cooldown_rounds)`
- **MACIE论文指标体系**:
  - SI (Structural Importance): 结构重要性 — 角色在交互网络中的中心性
  - CS (Character Salience): 角色显著性 — 近期活跃度和影响力
  - II (Interaction Intensity): 交互强度 — 动作类型频率和强度分布
- **EmergenceSignal**: 检测到涌现时返回综合评分 + 建议线程类型 + 叙事潜力评估
- 涌现信号自动注册为新的EMERGENT类型PlotThread

#### 武侠战争全链路测试模块 (stress_tests/wuxia_war)
- **WuxiaWorld**: 80维角色状态体系
  - 武术域(12维): 内功/外功/轻功/兵器/暗器/医术/毒术/阵法/音律/易容/机关/御兽
  - 人格域(10维): OCEAN五维 + 冲动/谨慎/正义感/野心/忠诚
  - 社交域(8维): 威望/人脉/门派地位/朝廷关系/江湖声望/情报网/恩怨值/号召力
  - 战斗域(8维): 攻击/防御/闪避/命中/暴击/抗暴/连击/反击
  - 资源域(6维): 金银/药材/兵器谱/秘籍/地盘/信物
  - 信念域(6维): 正邪倾向/复仇执念/权力欲望/情义观/生存哲学/武学追求
  - 额外维度: 健康/精力/士气/饥饿/口渴/体温/伤势/中毒/疲劳/内伤/情绪稳定/专注/恐惧/愤怒/悲伤/愉悦/羞耻/内疚/惊讶/厌恶/信任/期待/总战力/表字/秘密/成就/当前目标/当前地点/所属门派/所属阵营/阵营好感度/关系图谱/武功列表/持有物品/装备/特殊能力/弱点/禁忌/性格描述/外貌描述/背景故事/口头禅/行为模式/战斗风格偏好/社交策略
- **CharacterPool**: 支持620+角色的角色池管理
  - 6级角色层级: LEGENDARY(传说级) / EPIC(史诗级) / RARE(稀有级) / UNCOMMON(优秀级) / COMMON(普通级) / MORTAL(凡人级)
  - 角色模板: protagonist_a / protagonist_b / user_player / faction_leader / elite_fighter / merchant / scholar / wanderer / spy / assassin / healer / craftsman / noble / monk / bandit / guard / civilian
  - NameGenerator: 中文姓名生成（姓氏库+名字库+表字生成）
  - 地理位置约束: at_location() / move_to() / nearby_characters()
- **SceneRegistry**: 142个场景模板
  - 7大场景类别: TOWN(城镇)/TEMPLE(寺庙)/MOUNTAIN(山林)/PALACE(宫殿)/BATTLEFIELD(战场)/SECRET_BASE(秘境)/NEUTRAL(中立)
  - 场景容量控制: min_chars / max_chars / preferred_tiers
  - 场景分类摘要统计
- **GeographySystem**: 52个地理位置点
  - 区域类型: FACTION_TERRITORY / NEUTRAL_ZONE / BORDERLAND / HIDDEN_AREA
  - 门派领地映射: FACTION_LOCATIONS
  - 中立地点集合: NEUTRAL_LOCATIONS
  - 距离计算和邻近查询
- **WuxiaInfiniteLoop**: 无限轮次对话主循环
  - LLM集成: OpenAI兼容API调用，支持temperature/max_tokens配置
  - 对话动作分类: DialogueActionClassifier (AGGRESSIVE/FRIENDLY/NEUTRAL/DEFENSIVE)
  - OOC检测: OutOfCharacterDetector (角色崩坏检测)
  - 事件引擎: EventEngine (COMBAT/ALLIANCE/BETRAYAL/DISCOVERY/TRADE/TRAVEL/DEATH)
  - 结局检测: EndingDetector (FACTION_DOMINATION/PROTAGONIST_VICTORY/BALANCE_OF_POWER/NATURAL_CALAMITY/PEACE_TREATY/MYSTERY_SOLVED/NATURAL_CONCLUSION)
  - 存档系统: JSON格式完整世界状态快照，可配置保存间隔
  - 历史对话窗口: 动态大小 = BASE_PER_CHAR * char_count + GROWTH_PER_HUNDRED_ROUNDS * round_num/100
  - 场景管理器: SceneManager (上下文感知的场景选择)
  - 世界状态: WorldState (全局状态跟踪)

#### NarrativeEngine 总控类
- `initialize(pool)`: 初始化所有五层组件
- `process_round(round_num, pool, world_state, speaker_id, action_type, event_outcome)`:
  - 返回完整叙事报告: phase/directives/tensions/granularity/cast/emergence/storylets
- `get_narrative_context_for_prompt(round_num, char_id)`: 为LLM Prompt注入叙事上下文
- `get_full_report()`: 获取引擎完整状态报告
- `should_continue_scene(...)`: 场景驻留决策
- `start_scene(scene_id, round_num)` / `end_scene()`: 场景生命周期管理

### Changed
- WuxiaInfiniteLoop 新增参数支持叙事引擎集成:
  - `emergence_preset`: EmergencePreset枚举 (CONSERVATIVE/BALANCED/AGGRESSIVE/CUSTOM)
  - `custom_emergence_thresholds`: 自定义涌现阈值
  - `custom_storyform_inequalities`: 自定义Storyform不平等维度
  - `narrative_arc_enabled`: 叙事引擎开关 (默认True)
- _select_speaker(): 集成角色分层，优先选择active_cast中的角色
- _build_prompt(): 注入叙事上下文到system prompt
- _update_world_state(): 每轮调用narrative_engine.process_round()
- run(): 集成场景驻留引擎决策逻辑
- _save_checkpoint(): 存档中包含narrative_engine完整报告

### Fixed
- 循环引用错误: GeographySystem中SceneCategory未定义 → 重排类定义顺序
- 方法缺失: _process_neutral未实现 → 添加完整信息收集和观察机制
- 参数名错误: total_count → target_count
- 属性名错误: achievements → notable_achievements
- NEUTRAL动作直接return None无任何世界状态变化 → 完整实现观察和信息收集逻辑
- 角色永远没有成就记录 → 集成notable_achievements系统
- 地理系统完全不存在 → 完整实现GeographySystem 52位置点
- 秘密揭露机制空转 → 集成到EventEngine
- 无故事主线/频繁场景切换 → 五层叙事引擎解决

## [0.1.0] - 2026-05-05

### Added
- 初始版本发布
- 四智能体协作架构（Dialogue/Critic/Novelist/Atmosphere）
- OCEAN五维人格系统
- Lorenz混沌情感引擎
- GOAP规划器
- 认知记忆系统
- 世界观渲染器
- 场景构建器
- 交互协调器
- 本地LLM支持
- 快照系统

[Unreleased]: https://github.com/luqiai/luqi-engine/compare/v1.3.0.12-beta...HEAD
[1.3.0.12-beta]: https://github.com/luqiai/luqi-engine/releases/tag/v1.3.0.12-beta
[0.1.0]: https://github.com/luqiai/luqi-engine/releases/tag/v0.1.0
