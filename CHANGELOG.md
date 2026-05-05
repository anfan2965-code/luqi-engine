# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 配置ruff检查 - CI中添加ruff check和ruff format
- 配置测试覆盖率 - 添加pytest-cov，目标覆盖率80%
- 性能基准测试 - 添加pytest-benchmark测试关键路径
- 依赖安全扫描 - 配置dependabot和safety
- 添加CHANGELOG - 使用keepachangelog格式
- 文档版本化 - 为所有设计文档添加版本号和更新日期
- `_safe_enum()` 辅助函数 — 将LLM输出字符串安全解析为对应枚举成员
- `CriticMode` 枚举 — 审查模式专用枚举(FULL/LIGHT)
- `ConsolidationReport.merged_entries` 字段 — 返回合并后的记忆条目
- `CharacterExtractor.set_state_renderer()` 公开方法 — 替代私有属性注入
- `core/constants.py` — 引擎级命名常量集中管理模块

### Changed
- 配置加载失败不再静默降级，抛出具体异常
- 删除所有死代码和回退路径（~400行）
- 使用constants.py中的常量替代魔法数字（engine.py 15个）
- 修复私有属性跨类访问问题
- `MemoryType` 从 `auto()` 整数值改为 `str, Enum` 字符串值
- `PADState.update()` 带范围钳制[-1,1]替代直接 `+=` 操作
- `character_entity.py` on_event() 完全重写：emotion使用PADState.update()，desire使用async事件循环检测
- `response_parser.py` 所有枚举字段通过 `_safe_enum()` 还原（tone/severity/verdict/mode/pacing_hint）
- `dialogue_agent.py` 常量从字符串改为枚举（`ToneType.NEUTRAL`/`LengthHint.MEDIUM`）
- `prompt_builder.py` critic_mode默认值从 `AtmosphereMode.LIGHT` 改为 `CriticMode.LIGHT`
- `_DEFAULT_PACING_HINT` 从字符串 `"normal"` 改为 `PaceLevel.NORMAL` 枚举
- `_FALLBACK_TONE`/`_FALLBACK_LENGTH_HINT` 从字符串改为枚举默认值
- `ChatOrchestrator._update_character_emotion` 优先使用 `PADState.update()` 确保范围钳制
- `dominant_emotion` 引用添加 `callable()` 检测，兼容方法和属性

### Removed
- `_USE_ORCHESTRATOR` 开关 — 编排器已稳定，不再需要灰度开关
- `_chat_via_local_llm()` — 未使用的死方法
- `_chat_via_cloud_llm()` — 未使用的死方法
- `_collect_training_sample()` — 空方法体死代码
- `_apply_critic_corrections()` — 重复方法死代码
- `_INIT_PHASE_*` 常量从engine.py移除（仅保留在engine_initializer.py）
- 10个未使用的import（LLMResponse, CanonicalIR, CriticVerdict, Path, PCGRandom等）

### Fixed
- SSL验证根据base_url自动检测
- 路径遍历漏洞防护
- 远程代码执行风险（trust_remote_code默认禁用）
- PyYAML依赖缺失
- 用户输入长度限制
- API密钥序列化脱敏
- EventBus串行发布改为并行执行
- 记忆聚类O(n²)复杂度优化
- SSE缓冲区字符串拼接优化
- 日志脱敏机制
- _logger未定义问题（character_entity.py, response_parser.py, bridge.py, fallback.py, local_llm_adapter.py）
- print语句替换为logger
- `MemoryStore.store()` 多传参数mtype → memory_type移入MemoryEntry构造
- `PADState.update_from_dict()` 不存在 → 改用 `PADState.update(dp,da,dd)`
- `async update_desires()` 未await → 添加事件循环检测
- `dominant_emotion` 传入float而非string → 改用 `_DEFAULT_DOMINANT_EMOTION`
- `MemoryStore.size` property被当方法调用 → 移除括号
- `dominant_emotion` 方法引用缺少括号 → 添加callable()检测
- PAD值直接加减未做范围钳制 → 优先使用PADState.update()
- MemoryType枚举值类型不匹配(字符串vs整数) → 统一为str,Enum
- `_merge_cluster` 返回值被丢弃 → 收集到ConsolidationReport.merged_entries
- SURPRISE PAD向量不一致 → 统一为(0.1, 0.7, -0.1)
- `goap.py select_goal()` 重复构造 → 引用_GOAP_DEFAULT_GOALS常量
- `except (SnapshotError, Exception)` 冗余写法 → 简化为 `except Exception`
- fallback.py/local_llm_adapter.py 异常吞没 → 添加日志记录
- deepseek_optimizer.py CoT标签闭合符 `}` → `>`（9处）
- response_parser.py 7处 `str()` 降级枚举 → `_safe_enum()` 正确还原

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

[Unreleased]: https://github.com/luqiai/luqi-engine/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/luqiai/luqi-engine/releases/tag/v0.1.0
