"""
极限压力测试: 三体式N体博弈模拟
=====================================

设计原则:
1. 零原著投喂 — 引擎完全自主驱动,不注入任何小说内容
2. 无限轮次 — 直到引擎自身推出自然结局
3. 全子系统激活 — 信念/威胁/策略/机制/渲染全部参与
4. 结果自评 — 结局后自动分析引擎优缺点

架构:
  universe.py      → 宇宙规则/物理法则/黑暗森林公理
  civilizations.py → 文明定义/角色工厂/初始参数
  game_loop.py     → 无限轮次引擎/事件生成器/结局检测
  analyzer.py      → 引擎能力评估/弱点诊断/极限报告
  main.py          → 入口/配置/执行
"""

from .universe import UniverseRules, CosmicEnvironment, DarkForestAxiom
from .civilizations import CivilizationFactory, CivilizationProfile, PlayerRole
from .game_loop import GameLoop, RoundResult, GameState, EndingType
from .analyzer import StressTestAnalyzer, EngineCapabilityReport

__all__ = [
    "UniverseRules",
    "CosmicEnvironment",
    "DarkForestAxiom",
    "CivilizationFactory",
    "CivilizationProfile",
    "PlayerRole",
    "GameLoop",
    "RoundResult",
    "GameState",
    "EndingType",
    "StressTestAnalyzer",
    "EngineCapabilityReport",
]
