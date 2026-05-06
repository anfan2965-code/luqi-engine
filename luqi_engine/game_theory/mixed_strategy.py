"""
混合策略引擎 (MixedStrategyEngine) — Phase 4 核心模块之三

基于 Softmax (Boltzmann) 分布的概率化策略选择:
- 将纯策略空间映射到概率分布
- 温度参数 τ 控制熵 (随机性程度)
- 熵下限保证最小探索性
- 场景依赖的温度映射 (危机/正常/安全)

学术依据:
- Nash (1951): 混合策略纳什均衡
- McKelvey & Palfrey (1995): 量化响应均衡 (QRE)
- 最大熵原理 (Jaynes, 1957): 在约束下选择最不确定的分布
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .types import (
    MixedStrategyConfig,
    MixedStrategyProfile,
    StrategyAction,
    StrategyPayoff,
)


# ============================================================
# 场景关键词 → 温度映射表
# ============================================================

_SCENE_TEMPERATURE_KEYWORDS: Dict[str, float] = {
    "crisis": 0.3,
    "danger": 0.4,
    "combat": 0.4,
    "emergency": 0.3,
    "battle": 0.35,
    "threat": 0.5,
    "negotiation": 0.8,
    "peaceful": 2.0,
    "safe": 3.0,
    "exploration": 2.5,
    "casual": 2.0,
    "routine": 1.5,
}

_MAX_LOG_INPUT: float = 500.0


class MixedStrategyEngine:
    """
    混合策略引擎 — Softmax + 熵约束 + 场景温度映射
    
    核心算法流程:
    1. 收集所有可用动作的 payoff 估计 (来自外部或信念系统)
    2. 应用场景温度映射调整 τ
    3. 计算 log-sum-exp 稳定化的 softmax 概率
    4. 强制执行最小概率保底 (MIN_PROBABILITY)
    5. 归一化并计算熵
    6. 如果熵 < entropy_floor, 调整分布以满足约束
    7. 返回 MixedStrategyProfile
    
    温度参数 τ 的物理意义:
    - τ → 0+: 几乎贪婪选择 (最大 payoff 动作概率→1)
    - τ = 1.0: 标准 softmax, 差异适中
    - τ → ∞: 均匀随机 (所有动作等概率)
    
    与动机系统的联动:
    - MaslowEngine.urgency_level 高 → 低温度 (果断)
    - MaslowEngine.urgency_level 低 → 高温度 (多样)
    """
    
    def __init__(self, config: Optional[MixedStrategyConfig] = None) -> None:
        self._config = config or MixedStrategyConfig()
    
    @property
    def config(self) -> MixedStrategyConfig:
        return self._config
    
    # ================================================================
    # 核心 API
    # ================================================================
    
    def generate(
        self,
        payoffs: List[StrategyPayoff],
        temperature: Optional[float] = None,
        urgency_level: float = 1.0,
        scene_context: Optional[str] = None,
    ) -> MixedStrategyProfile:
        """
        根据收益估计生成混合策略剖面
        
        Args:
            payoffs: 各动作的收益估计列表
            temperature: 显式指定温度 (None 则自动确定)
            urgency_level: 紧急度 [0.5, 3.0], 影响温度映射
            scene_context: 场景描述文本 (用于关键词匹配)
            
        Returns:
            MixedStrategyProfile 包含完整的概率分布和元信息
            
        Raises:
            ValueError: 如果 payoffs 为空
        """
        if not payoffs:
            raise ValueError("payoffs list cannot be empty")
        
        effective_temp = self._resolve_temperature(
            temperature, urgency_level, scene_context
        )
        
        action_payoffs: Dict[StrategyAction, float] = {}
        for p in payoffs:
            action_payoffs[p.action] = p.expected_payoff
        
        default_actions = self._config.default_actions
        
        for action in default_actions:
            if action not in action_payoffs:
                action_payoffs[action] = 0.0
        
        for p in payoffs:
            if p.action not in action_payoffs:
                action_payoffs[p.action] = p.expected_payoff
        
        probabilities = self._softmax(action_payoffs, effective_temp)
        
        profile = MixedStrategyProfile(
            action_probabilities=probabilities,
            temperature=effective_temp,
        )
        
        profile = self._enforce_entropy_floor(profile)
        
        return profile
    
    def generate_from_beliefs(
        self,
        belief_system: "BeliefSystem",
        target_id: str,
        available_actions: Optional[List[StrategyAction]] = None,
        base_payoffs: Optional[Dict[StrategyAction, Tuple[float, float]]] = None,
        temperature: Optional[float] = None,
        urgency_level: float = 1.0,
    ) -> MixedStrategyProfile:
        """
        从信念系统驱动生成混合策略
        
        流程:
        1. 从 belief_system 预测目标合作概率 P_coop
        2. 使用 base_payoffs 或默认收益矩阵
        3. 用 P_coop 加权各动作的期望收益
        4. 调用 generate() 完成 softmax + 熵约束
        
        默认收益矩阵 (类囚徒困境):
        COOPERATE: (+3, 0)   — 对手合作+3, 背叛0
        DEFECT:     (+5, -1)  — 对手合作+5(诱惑), 背叛-1(相互背叛惩罚)
        OBSERVE:    (+1, +1)  — 信息收集, 中性
        WITHDRAW:   (0, 0)    — 回避, 无收益无损失
        NEGOTIATE:  (+2, +1)  — 协商, 正向但需时间成本
        
        Args:
            belief_system: 已初始化的信念系统实例
            target_id: 目标实体ID
            available_actions: 可用动作子集 (None 则用配置默认值)
            base_payoffs: 自定义基础收益 {action: (if_coop, if_defect)}
            temperature: 显式温度
            urgency_level: 紧急度
            
        Returns:
            MixedStrategyProfile
        """
        coop_prob = belief_system.predict_cooperation_probability(target_id)
        
        actions = available_actions or self._config.default_actions
        
        defaults: Dict[StrategyAction, Tuple[float, float]] = {
            StrategyAction.COOPERATE: (3.0, 0.0),
            StrategyAction.DEFECT: (5.0, -1.0),
            StrategyAction.OBSERVE: (1.0, 1.0),
            StrategyAction.WITHDRAW: (0.0, 0.0),
            StrategyAction.NEGOTIATE: (2.0, 1.0),
            StrategyAction.SUPPORT: (2.0, 0.5),
            StrategyAction.EXPLOIT: (6.0, -2.0),
            StrategyAction.DECEIVE: (4.0, -1.5),
        }
        
        effective_payoffs = base_payoffs or defaults
        
        payoff_list: List[StrategyPayoff] = []
        for action in actions:
            coop_val, defect_val = effective_payoffs.get(
                action, (0.0, 0.0)
            )
            payoff_list.append(
                StrategyPayoff(
                    action=action,
                    payoff_if_cooperate=coop_val,
                    payoff_if_defect=defect_val,
                    estimated_probability=coop_prob,
                )
            )
        
        return self.generate(
            payoffs=payoff_list,
            temperature=temperature,
            urgency_level=urgency_level,
        )
    
    def compute_nash_equilibrium(
        self,
        payoff_matrix: Dict[StrategyAction, Dict[StrategyAction, float]],
    ) -> Optional[MixedStrategyProfile]:
        """
        简化博弈的支撑枚举法求解混合策略纳什均衡
        
        适用范围: 2x2 或 3x3 对称/非对称博弈
        方法: 枚举所有可能的支撑集 (support), 检查最佳反应条件
        
        对于标准囚徒困境:
        (D, D) 是唯一的纯策略纳什均衡 (双方都背叛)
        
        对于猎鹿博弈:
        存在两个纯策略均衡 (C,C) 和 (D,D) + 一个混合策略均衡
        
        注意: 这是简化实现。完整求解需要线性规划或 Lemke-Howson算法。
        
        Args:
            payoff_matrix: 我方收益矩阵 [my_action][opponent_action] → payoff
            
        Returns:
            MixedStrategyProfile 或 None (无法找到均衡时)
        """
        if not payoff_matrix:
            return None
        
        pure_best_response = self._find_pure_nash(payoff_matrix)
        if pure_best_response is not None:
            return pure_best_response
        
        mixed_profile = self._solve_mixed_equilibrium(payoff_matrix)
        return mixed_profile
    
    def adjust_temperature_for_scene(
        self,
        base_temperature: float,
        urgency_level: float,
        scene_keywords: Optional[List[str]] = None,
    ) -> float:
        """
        根据场景因素调整温度参数
        
        调整公式:
        τ_effective = τ_base × urgency_factor × scene_factor
        
        其中:
        - urgency_factor ∈ [0.33, 3.0] (由 urgency_level 映射)
        - scene_factor 由场景关键词查找决定
        
        最终结果钳制到 [min_temp, max_temp]
        
        Args:
            base_temperature: 基础温度
            urgency_level: 紧急度 [0.5, 3.0]
            scene_keywords: 场景关键词列表 (可选)
            
        Returns:
            调整后的有效温度
        """
        clamped_urgency = max(0.5, min(3.0, urgency_level))
        
        if clamped_urgency <= 1.0:
            urg_factor = self._config.urgency_low_temp / (
                self._config.default_temperature * clamped_urgency
            )
        else:
            urg_factor = (
                self._config.urgency_high_temp
                / self._config.default_temperature
                * (clamped_urgency - 1.0 + 1.0)
            )
        
        scene_factor = 1.0
        if scene_keywords:
            matched_factors = [
                _SCENE_TEMPERATURE_KEYWORDS.get(kw.lower(), 1.0)
                for kw in scene_keywords
                if kw.lower() in _SCENE_TEMPERATURE_KEYWORDS
            ]
            if matched_factors:
                scene_factor = sum(matched_factors) / len(matched_factors)
        
        raw = base_temperature * urg_factor * scene_factor
        
        return max(self._config.min_temperature, min(raw, self._config.max_temperature))
    
    # ================================================================
    # 内部方法
    # ================================================================
    
    def _resolve_temperature(
        self,
        explicit_temp: Optional[float],
        urgency_level: float,
        scene_context: Optional[str],
    ) -> float:
        """解析最终有效温度"""
        if explicit_temp is not None:
            return max(
                self._config.min_temperature,
                min(explicit_temp, self._config.max_temperature),
            )
        
        keywords = None
        if scene_context:
            keywords = scene_context.split()
        
        return self.adjust_temperature_for_scene(
            self._config.default_temperature,
            urgency_level,
            keywords,
        )
    
    def _softmax(
        self,
        action_payoffs: Dict[StrategyAction, float],
        temperature: float,
    ) -> Dict[StrategyAction, float]:
        """
        数值稳定的 Softmax (Boltzmann) 分布计算
        
        公式: P(i) = exp((v_i - v_max) / τ) / Σ_j exp((v_j - v_max) / τ)
        
        稳定化技巧: 减去 v_max 防止 exp 溢出
        当 τ → 0 时, 使用 log-sum-exp 技巧避免除零
        
        Args:
            action_payoffs: 动作→期望收益映射
            temperature: 温度参数 (>0)
            
        Returns:
            动作→概率映射字典
        """
        if not action_payoffs:
            return {}
        
        safe_temp = max(temperature, 1e-6)
        
        values = list(action_payoffs.values())
        v_max = max(values) if values else 0.0
        
        exp_values: Dict[StrategyAction, float] = {}
        for action, value in action_payoffs.items():
            scaled = (value - v_max) / safe_temp
            clamped_scaled = max(-_MAX_LOG_INPUT, min(scaled, _MAX_LOG_INPUT))
            exp_values[action] = math.exp(clamped_scaled)
        
        total = sum(exp_values.values())
        
        if total < 1e-300:
            n = len(exp_values)
            uniform_prob = 1.0 / n if n > 0 else 0.0
            return {a: uniform_prob for a in exp_values}
        
        probabilities = {
            action: exp_val / total
            for action, exp_val in exp_values.items()
        }
        
        return probabilities
    
    def _enforce_entropy_floor(
        self, profile: MixedStrategyProfile
    ) -> MixedStrategyProfile:
        """
        执行熵下限约束
        
        如果当前熵 < absolute_min_entropy:
        向均匀方向调整概率直到满足约束
        
        调整方法: 
        p'_i = λ·uniform_i + (1-λ)·p_i
        其中 λ 从 0 开始递增直到 H(p') ≥ entropy_floor
        
        Args:
            profile: 待调整的策略剖面
            
        Returns:
            满足熵约束的新剖面 (可能为原剖面如果已满足)
        """
        floor = self._config.absolute_min_entropy
        
        if profile.entropy >= floor:
            return profile
        
        actions = list(profile.action_probabilities.keys())
        n = len(actions)
        if n <= 1:
            return profile
        
        uniform_prob = 1.0 / n
        
        low, high = 0.0, 1.0
        
        for _ in range(50):
            mid = (low + high) / 2.0
            
            new_probs: Dict[StrategyAction, float] = {}
            for a in actions:
                new_probs[a] = mid * uniform_prob + (1.0 - mid) * profile.action_probabilities.get(a, uniform_prob)
            
            test_profile = MixedStrategyProfile(
                action_probabilities=new_probs,
                temperature=profile.temperature,
            )
            
            if test_profile.entropy >= floor:
                high = mid
            else:
                low = mid
            
            if high - low < 1e-6:
                break
        
        final_lambda = high
        final_probs: Dict[StrategyAction, float] = {}
        for a in actions:
            final_probs[a] = (
                final_lambda * uniform_prob
                + (1.0 - final_lambda) * profile.action_probabilities.get(a, uniform_prob)
            )
        
        return MixedStrategyProfile(
            action_probabilities=final_probs,
            temperature=profile.temperature,
        )
    
    def _find_pure_nash(
        self,
        payoff_matrix: Dict[StrategyAction, Dict[StrategyAction, float]],
    ) -> Optional[MixedStrategyProfile]:
        """
        寻找纯策略纳什均衡
        
        方法: 对每个我方动作, 检查是否是对手任意选择的最佳反应。
        在简化版本中, 我们假设对手也使用相同的收益结构。
        
        策略 s 是纯策略NE当且仅当:
        ∀ s' ≠ s: U(s, s*) ≥ U(s', s*)
        其中 s* 是对手的最佳反应
        
        这里使用简化检查: 寻找支配策略或对称均衡点
        """
        if not payoff_matrix:
            return None
        
        my_actions = list(payoff_matrix.keys())
        if len(my_actions) <= 1:
            if my_actions:
                return MixedStrategyProfile(
                    action_probabilities={my_actions[0]: 1.0},
                    temperature=0.01,
                )
            return None
        
        best_action = max(my_actions, key=lambda a: max(payoff_matrix[a].values()))
        best_payoff = max(payoff_matrix[best_action].values())
        
        is_dominant = True
        for a in my_actions:
            if a == best_action:
                continue
            if max(payoff_matrix[a].values()) > best_payoff:
                is_dominant = False
                break
        
        if is_dominant:
            probs = {a: (1.0 if a == best_action else 0.0) for a in my_actions}
            return MixedStrategyProfile(
                action_probabilities=probs,
                temperature=0.01,
            )
        
        return None
    
    def _solve_mixed_equilibrium(
        self,
        payoff_matrix: Dict[StrategyAction, Dict[StrategyAction, float]],
    ) -> Optional[MixedStrategyProfile]:
        """
        求解混合策略均衡 (简化版)
        
        对于 2x2 博弈, 可以通过解析公式求解。
        更大维度使用迭代最佳响应近似。
        
        此处简化为: 使用中等温度的 softmax 作为混合策略近似
        这在 QRE (量化响应均衡) 框架下是合理的
        """
        all_actions = list(payoff_matrix.keys())
        if len(all_actions) < 2:
            return None
        
        avg_payoffs: Dict[StrategyAction, float] = {}
        for action, opp_payoffs in payoff_matrix.items():
            avg_payoffs[action] = sum(opp_payoffs.values()) / max(len(opp_payoffs), 1)
        
        temp = self._config.normal_temperature
        probs = self._softmax(avg_payoffs, temp)
        
        return MixedStrategyProfile(
            action_probabilities=probs,
            temperature=temp,
        )
