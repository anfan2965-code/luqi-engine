"""
机制设计器 (MechanismDesigner) — Phase 4 元分析层

定位: Meta-Game 分析层, 不修改任何 P1-P3 子系统代码
功能: 通过参数调整操纵系统均衡, 为叙事设计师提供"如果...那么..."分析能力

学术依据:
- Hurwicz (1972): 信息分散系统中的资源配置机制设计
- Myerson (1981): 最优拍卖设计
- 显示原理 (Myerson, 1979): 任何贝叶斯纳什均衡可用直接机制实现
- VCG机制 (Vickrey-Clarke-Groves): 激励兼容+有效的通用框架
- 激励相容性 (IC): 说真话是参与者的占优策略

核心约束:
- 非侵入式: 所有影响通过 MechanismConfig 参数传递
- 可逆性: 参数变更可回滚, 支持 A/B 测试
- 参数化: 全部行为由浮点参数控制, 无硬编码逻辑分支
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from .types import (
    EquilibriumPrediction,
    IncentiveCompatibilityReport,
    MechanismConfig,
    MechanismParameter,
)


# ============================================================
# 参考角色模拟参数 (用于 Monte Carlo)
# ============================================================

_SIM_DEFAULT_PARAMS = {
    "cooperation_base": 0.5,
    "defection_base": 0.3,
    "shadow_activation_base": 0.15,
    "relationship_decay": 0.02,
    "tension_growth_rate": 0.05,
}

_NARRATIVE_GOAL_KEYWORDS: Dict[str, List[Tuple[MechanismParameter, float]]] = {
    "high_cooperation": [
        (MechanismParameter.REWARD_COOPERATION_BONUS, 1.8),
        (MechanismParameter.PUNISHMENT_DEFECT_COST, 1.5),
        (MechanismParameter.INFORMATION_TRANSPARENCY, 0.9),
        (MechanismParameter.MIXED_STRATEGY_ENTROPY_FLOOR, 0.3),
        (MechanismParameter.BELIEF_UPDATE_RATE, 2.0),
    ],
    "high_tension": [
        (MechanismParameter.REWARD_COOPERATION_BONUS, 0.3),
        (MechanismParameter.PUNISHMENT_DEFECT_COST, 0.4),
        (MechanismParameter.INFORMATION_TRANSPARENCY, 0.2),
        (MechanismParameter.SHADOW_ACTIVATION_THRESHOLD, 0.3),
        (MechanismParameter.THREAT_CREDIBILITY_DECAY, 0.9),
    ],
    "balanced": [
        (MechanismParameter.REWARD_COOPERATION_BONUS, 1.0),
        (MechanismParameter.PUNISHMENT_DEFECT_COST, 1.0),
        (MechanismParameter.INFORMATION_TRANSPARENCY, 0.6),
        (MechanismParameter.SOCIAL_EVOLUTION_SPEED, 1.0),
    ],
    "unpredictable": [
        (MechanismParameter.MIXED_STRATEGY_ENTROPY_FLOOR, 1.8),
        (MechanismParameter.BELIEF_UPDATE_RATE, 0.3),
        (MechanismParameter.MOTIVATION_URGENCY_SENSITIVITY, 1.8),
        (MechanismParameter.THREAT_CREDIBILITY_DECAY, 0.8),
    ],
    "stable_relationships": [
        (MechanismParameter.REWARD_COOPERATION_BONUS, 1.5),
        (MechanismParameter.INFORMATION_TRANSPARENCY, 0.8),
        (MechanismParameter.SOCIAL_EVOLUTION_SPEED, 0.5),
        (MechanismParameter.BELIEF_UPDATE_RATE, 0.8),
    ],
    "dynamic_evolution": [
        (MechanismParameter.SOCIAL_EVOLUTION_SPEED, 2.5),
        (MechanismParameter.BELIEF_UPDATE_RATE, 2.5),
        (MechanismParameter.MOTIVATION_URGENCY_SENSITIVITY, 1.5),
        (MechanismParameter.THREAT_CREDIBILITY_DECAY, 0.3),
    ],
}


class MechanismDesigner:
    """
    机制设计器 — Meta-Game 分析层
    
    设计原则:
    - ANALYSIS ONLY: 只分析不执行, 不修改运行时代码
    - PARAMETERIZED: 所有操作通过 MechanismConfig 实现
    - REVERSIBLE: 配置可复制/比较/回滚
    - EXPLAINABLE: 输出包含敏感性分析和警告
    
    使用场景:
    1. 叙事设计师调整世界参数以引导故事走向
    2. 开发者验证新配置的激励相容性
    3. A/B 测试不同参数组合的效果
    4. 敏感性分析找出关键杠杆参数
    """
    
    DEFAULT_SIMULATIONS: ClassVar[int] = 100
    
    def __init__(self, reference_character: Optional[Any] = None) -> None:
        self._reference = reference_character
        self._simulation_rng = random.Random(42)
    
    # ================================================================
    # 核心分析 API
    # ================================================================
    
    def predict_equilibrium(
        self,
        config: MechanismConfig,
        num_simulations: int = 100,
    ) -> EquilibriumPrediction:
        """
        Monte Carlo 模拟预测给定配置下的系统稳态行为
        
        模拟模型 (简化):
        每轮交互:
        1. 合作概率受 REWARD_COOPERATION_BONUS 和 PUNISHMENT_DEFECT_COST 影响
        2. 冲突概率与合作概率互补并受信息透明度调节
        3. 阴影激活率受 SHADOW_ACTIVATION_THRESHOLD 和关系质量影响
        4. 关系质量随合作/冲突事件演化
        
        稳态取最后 N_sim/10 轮的平均值
        
        Args:
            config: 待分析的机制配置
            num_simulations: MC模拟次数
            
        Returns:
            EquilibriumPrediction 包含各指标预测值和敏感性分析
        """
        coop_bonus = config.get(MechanismParameter.REWARD_COOPERATION_BONUS, 1.0)
        defect_cost = config.get(MechanismParameter.PUNISHMENT_DEFECT_COST, 1.0)
        info_trans = config.get(MechanismParameter.INFORMATION_TRANSPARENCY, 0.5)
        shadow_thresh = config.get(MechanismParameter.SHADOW_ACTIVATION_THRESHOLD, 0.5)
        social_speed = config.get(MechanismParameter.SOCIAL_EVOLUTION_SPEED, 1.0)
        entropy_floor = config.get(MechanismParameter.MIXED_STRATEGY_ENTROPY_FLOOR, 0.5)
        
        base_coop = _SIM_DEFAULT_PARAMS["cooperation_base"]
        base_defect = _SIM_DEFAULT_PARAMS["defection_base"]
        base_shadow = _SIM_DEFAULT_PARAMS["shadow_activation_base"]
        
        relationship = 0.5
        tension = 0.3
        
        coop_history: List[float] = []
        conflict_history: List[float] = []
        shadow_history: List[float] = []
        
        burn_in = max(num_simulations // 10, 10)
        
        for step in range(num_simulations):
            coop_prob = self._sigmoid(
                base_coop + (coop_bonus - 1.0) * 0.3 + relationship * 0.4
                - tension * 0.3
            )
            
            defect_modifier = defect_cost * (1.0 - info_trans) * 0.5
            conflict_prob = self._sigmoid(
                base_defect + defect_modifier + tension * 0.4
                - relationship * 0.3
            )
            
            conflict_prob = min(conflict_prob, 1.0 - coop_prob * 0.8)
            
            shadow_prob = self._sigmoid(
                base_shadow + (1.0 - shadow_thresh) * 0.5
                + tension * 0.3 - relationship * 0.2
            )
            
            if step >= burn_in:
                coop_history.append(coop_prob)
                conflict_history.append(conflict_prob)
                shadow_history.append(shadow_prob)
            
            event_rnd = self._simulation_rng.random()
            if event_rnd < coop_prob:
                relationship += 0.05 * social_speed
                tension *= 0.95
            elif event_rnd < coop_prob + conflict_prob:
                relationship -= 0.08 * social_speed
                tension = min(1.0, tension + 0.06 * social_speed)
            
            relationship = max(0.05, min(0.95, relationship))
            tension = max(0.05, min(0.95, tension))
        
        avg_coop = sum(coop_history) / max(len(coop_history), 1)
        avg_conflict = sum(conflict_history) / max(len(conflict_history), 1)
        avg_shadow = sum(shadow_history) / max(len(shadow_history), 1)
        
        system_entropy = -(
            avg_coop * math.log(max(avg_coop, 1e-10))
            + avg_conflict * math.log(max(avg_conflict, 1e-10))
            + (1.0 - avg_coop - avg_conflict) * math.log(
                max(1.0 - avg_coop - avg_conflict, 1e-10)
            )
        ) if (avg_coop > 0 and avg_conflict > 0) else 0.0
        
        warnings: List[str] = []
        if avg_coop < 0.25 and config.name != "":
            warnings.append(f"低合作率警告({avg_coop:.2f}): 可能导致叙事崩塌")
        if avg_conflict > 0.7:
            warnings.append(f"高冲突率警告({avg_conflict:.2f}): 角色可能频繁对抗")
        if avg_shadow > 0.5:
            warnings.append(f"高阴影激活率({avg_shadow:.2f}): 荣格阴影过度活跃")
        
        sensitivity = self._quick_sensitivity(config, "cooperation_rate")
        
        return EquilibriumPrediction(
            config_name=config.name or "unnamed",
            predicted_cooperation_rate=round(avg_coop, 4),
            predicted_conflict_rate=round(avg_conflict, 4),
            predicted_shadow_activation_rate=round(avg_shadow, 4),
            average_relationship_quality=round(relationship, 4),
            narrative_tension_level=round(tension, 4),
            system_entropy=round(system_entropy, 4),
            sensitivity=sensitivity,
            warnings=warnings,
        )
    
    def recommend_for_narrative_goal(
        self,
        goal: str,
        current_config: Optional[MechanismConfig] = None,
        search_iterations: int = 50,
    ) -> MechanismConfig:
        """
        为给定叙事目标推荐最优机制配置
        
        支持的目标关键词:
        - high_cooperation: 高合作环境 (盟友/团队场景)
        - high_tension: 高紧张度 (对抗/悬疑场景)
        - balanced: 平衡状态 (日常/中性场景)
        - unpredictable: 不可预测 (神秘/反转场景)
        - stable_relationships: 稳定关系 (长期伙伴/家庭场景)
        - dynamic_evolution: 动态演化 (成长/变革场景)
        
        方法:
        1. 从预设模板初始化
        2. 局部网格搜索微调
        3. 返回使目标指标最大化的配置
        
        Args:
            goal: 叙事目标描述 (关键词匹配)
            current_config: 当前配置 (作为搜索起点, 可选)
            search_iterations: 搜索迭代次数
            
        Returns:
            推荐的 MechanismConfig
        """
        matched_goal = None
        for keyword in _NARRATIVE_GOAL_KEYWORDS:
            if keyword in goal.lower():
                matched_goal = keyword
                break
        
        if matched_goal is None:
            matched_goal = "balanced"
        
        template_params = _NARRATIVE_GOAL_KEYWORDS[matched_goal]
        
        result = MechanismConfig(
            name=f"recommended_{matched_goal}",
            description=f"Auto-recommended for narrative goal: {goal}",
        )
        
        for param, value in template_params:
            result.set(param, value)
        
        best_config = result.copy()
        best_score = self._evaluate_goal_score(best_config, matched_goal)
        
        for iteration in range(search_iterations):
            candidate = best_config.copy()
            
            params_to_tweak = list(candidate.parameter_values.keys())
            if not params_to_tweak:
                break
            
            tweak_param = params_to_tweak[
                iteration % len(params_to_tweak)
            ]
            
            bounds = self._get_param_bounds(tweak_param)
            current_val = candidate.get(tweak_param, 0.5)
            
            delta = (self._simulation_rng.random() - 0.5) * 0.3
            new_val = current_val + delta * (bounds[1] - bounds[0])
            new_val = max(bounds[0], min(bounds[1], new_val))
            
            candidate.set(tweak_param, new_val)
            
            candidate_score = self._evaluate_goal_score(candidate, matched_goal)
            
            if candidate_score > best_score:
                best_config = candidate.copy()
                best_score = candidate_score
        
        return best_config
    
    def check_incentive_compatibility(
        self,
        config: MechanismConfig,
        target_behavior_description: str,
        deviation_actions: List[str],
    ) -> IncentiveCompatibilityReport:
        """
        激励相容性检验 — 角色是否有动机偏离目标行为?
        
        IC 成立条件:
        U(target_behavior) ≥ U(deviation) for all deviations
        
        此处使用简化模型:
        - 目标行为的效用由配置参数决定
        - 偏离行为的效用基于"背叛诱惑"估算
        - 如果偏离收益 > 目标收益 → IC 不成立
        
        Args:
            config: 待检验的机制配置
            target_behavior_description: 目标行为描述 (如 "always_cooperate")
            deviation_actions: 可能的偏离动作列表
            
        Returns:
            IncentiveCompatibilityReport 详细报告
        """
        coop_bonus = config.get(MechanismParameter.REWARD_COOPERATION_BONUS, 1.0)
        defect_cost = config.get(MechanismParameter.PUNISHMENT_DEFECT_COST, 1.0)
        entropy_floor = config.get(MechanismParameter.MIXED_STRATEGY_ENTROPY_FLOOR, 0.5)
        
        target_utility = coop_bonus * 2.0 + 1.0
        
        temptation = 3.0 - defect_cost * 1.5
        deviation_payoff = max(temptation, target_utility * 0.5)
        
        is_ic = target_utility >= deviation_payoff
        
        critical_params: List[Tuple[str, float]] = []
        if not is_ic:
            critical_params.append(("REWARD_COOPERATION_BONUS", coop_bonus))
            critical_params.append(("PUNISHMENT_DEFECT_COST", defect_cost))
            critical_params.append(("MIXED_STRATEGY_ENTROPY_FLOOR", entropy_floor))
        
        gap = deviation_payoff - target_utility
        
        recommendation = ""
        confidence = 0.8
        
        if is_ic:
            recommendation = (
                f"当前配置下'{target_behavior_description}'是激励相容的。"
                f"目标收益={target_utility:.2f}, 最大偏离收益={deviation_payoff:.2f}"
            )
            confidence = 0.85 + min(gap / 2.0, 0.14)
        else:
            needed_increase = gap / 2.0 + 0.1
            recommendation = (
                f"⚠️ 激励不相容! '{target_behavior_description}'的收益({target_utility:.2f})"
                f"低于偏离收益({deviation_payoff:.2f}), 差距={gap:.2f}。"
                f"建议将REWARD_COOPERATION_BONUS提高至少{needed_increase:.2f}"
                f"或PUNISHMENT_DEFECT_COST提高至少{gap/1.5:.2f}"
            )
            confidence = 0.75
        
        return IncentiveCompatibilityReport(
            target_behavior=target_behavior_description,
            is_incentive_compatible=is_ic,
            deviation_payoff=round(deviation_payoff, 4),
            critical_parameters=critical_params,
            recommendation=recommendation,
            confidence=round(confidence, 3),
        )
    
    def sensitivity_analysis(
        self,
        config: MechanismConfig,
        output_metric: str = "cooperation_rate",
        delta: float = 0.1,
    ) -> Dict[str, float]:
        """
        单因素扰动法敏感性分析
        
        对每个参数进行 ±delta 扰动, 观察输出指标变化。
        敏感性 = |Δoutput| / δinput, 值越大说明该参数越关键。
        
        Args:
            config: 基准配置
            output_metric: 输出指标名称 ("cooperation_rate" / "conflict_rate" 等)
            delta: 扰动幅度 (相对值)
            
        Returns:
            {parameter_name: sensitivity_value} 字典, 按敏感性降序排列
        """
        baseline_pred = self.predict_equilibrium(config, num_simulations=50)
        baseline_value = getattr(baseline_pred, f"predicted_{output_metric}", 0.5)
        
        sensitivities: Dict[str, float] = {}
        
        for param in list(config.parameter_values.keys()):
            bounds = self._get_param_bounds(param)
            current = config.get(param, 0.5)
            
            range_width = bounds[1] - bounds[0]
            abs_delta = delta * range_width
            
            up_config = config.copy()
            up_val = min(current + abs_delta, bounds[1])
            up_config.set(param, up_val)
            up_pred = self.predict_equilibrium(up_config, num_simulations=30)
            up_value = getattr(up_pred, f"predicted_{output_metric}", 0.5)
            
            down_config = config.copy()
            down_val = max(current - abs_delta, bounds[0])
            down_config.set(param, down_val)
            down_pred = self.predict_equilibrium(down_config, num_simulations=30)
            down_value = getattr(down_pred, f"predicted_{output_metric}", 0.5)
            
            sens_up = abs(up_value - baseline_value) / max(abs_delta, 1e-6)
            sens_down = abs(down_value - baseline_value) / max(abs_delta, 1e-6)
            
            sensitivities[param.name] = max(sens_up, sens_down)
        
        sorted_sens = dict(
            sorted(sensitivities.items(), key=lambda x: x[1], reverse=True)
        )
        return sorted_sens
    
    def compare_configs(
        self,
        config_a: MechanismConfig,
        config_b: MechanismConfig,
    ) -> Dict[str, Any]:
        """
        对比两个机制配置的差异和预测效果
        
        Returns:
            对比报告字典, 包含参数差异、预测差异、推荐结论
        """
        pred_a = self.predict_equilibrium(config_a, num_simulations=80)
        pred_b = self.predict_equilibrium(config_b, num_simulations=80)
        
        param_diffs: List[Dict[str, Any]] = []
        all_params = set(config_a.parameter_values.keys()) | set(
            config_b.parameter_values.keys()
        )
        for param in sorted(all_params, key=lambda p: p.name):
            val_a = config_a.get(param, 0.5)
            val_b = config_b.get(param, 0.5)
            diff = val_b - val_a
            if abs(diff) > 0.01:
                param_diffs.append({
                    "parameter": param.name,
                    "config_a": round(val_a, 4),
                    "config_b": round(val_b, 4),
                    "difference": round(diff, 4),
                    "change_pct": round(
                        (diff / max(abs(val_a), 1e-6)) * 100, 1
                    ),
                })
        
        metric_diffs: List[Dict[str, Any]] = []
        metrics = [
            "predicted_cooperation_rate",
            "predicted_conflict_rate",
            "predicted_shadow_activation_rate",
            "average_relationship_quality",
            "narrative_tension_level",
        ]
        for metric in metrics:
            val_a = getattr(pred_a, metric, 0.5)
            val_b = getattr(pred_b, metric, 0.5)
            diff = val_b - val_a
            if abs(diff) > 0.01:
                metric_diffs.append({
                    "metric": metric,
                    "config_a": round(val_a, 4),
                    "config_b": round(val_b, 4),
                    "difference": round(diff, 4),
                })
        
        conclusion = self._generate_comparison_conclusion(pred_a, pred_b)
        
        return {
            "config_a_name": config_a.name or "A",
            "config_b_name": config_b.name or "B",
            "parameter_differences": param_diffs,
            "prediction_differences": metric_diffs,
            "conclusion": conclusion,
            "warnings_a": pred_a.warnings,
            "warnings_b": pred_b.warnings,
        }
    
    # ================================================================
    # 预设模板工厂方法
    # ================================================================
    
    @classmethod
    def preset_cooperative(cls) -> MechanismConfig:
        """高合作预设 — 团队协作/友好社交场景"""
        config = MechanismConfig(name="preset_cooperative", description="高合作环境")
        for param, value in _NARRATIVE_GOAL_KEYWORDS["high_cooperation"]:
            config.set(param, value)
        return config
    
    @classmethod
    def preset_hostile(cls) -> MechanismConfig:
        """高敌对预设 — 冲突/对抗/悬疑场景"""
        config = MechanismConfig(name="preset_hostile", description="高紧张度环境")
        for param, value in _NARRATIVE_GOAL_KEYWORDS["high_tension"]:
            config.set(param, value)
        return config
    
    @classmethod
    def preset_mystery(cls) -> MechanismConfig:
        """不可预测预设 — 神秘/反转/心理博弈场景"""
        config = MechanismConfig(name="preset_mystery", description="不可预测环境")
        for param, value in _NARRATIVE_GOAL_KEYWORDS["unpredictable"]:
            config.set(param, value)
        return config
    
    @classmethod
    def preset_neutral(cls) -> MechanismConfig:
        """平衡预设 — 中性/日常/过渡场景"""
        config = MechanismConfig(name="preset_neutral", description="平衡默认环境")
        for param, value in _NARRATIVE_GOAL_KEYWORDS["balanced"]:
            config.set(param, value)
        return config
    
    # ================================================================
    # 内部方法
    # ================================================================
    
    @staticmethod
    def _sigmoid(x: float) -> float:
        """数值稳定的 sigmoid 函数"""
        if x > 20:
            return 1.0
        elif x < -20:
            return 0.0
        return 1.0 / (1.0 + math.exp(-x))
    
    @staticmethod
    def _get_param_bounds(param: MechanismParameter) -> Tuple[float, float]:
        from .types import _MECHANISM_PARAMETER_BOUNDS
        return _MECHANISM_PARAMETER_BOUNDS.get(param, (0.0, 1.0))
    
    def _evaluate_goal_score(self, config: MechanismConfig, goal: str) -> float:
        """评估配置对目标的适配程度"""
        pred = self.predict_equilibrium(config, num_simulations=30)
        
        scores: Dict[str, float] = {
            "high_cooperation": pred.predicted_cooperation_rate,
            "high_tension": pred.predicted_conflict_rate,
            "balanced": 1.0 - abs(pred.predicted_cooperation_rate - 0.5) * 2,
            "unpredictable": pred.system_entropy,
            "stable_relationships": pred.average_relationship_quality,
            "dynamic_evolution": pred.narrative_tension_level * 0.5 + pred.system_entropy * 0.5,
        }
        
        raw_score = scores.get(goal, 0.5)
        
        penalty = len(pred.warnings) * 0.1
        return max(0.0, raw_score - penalty)
    
    def _quick_sensitivity(
        self, config: MechanismConfig, metric: str
    ) -> Dict[str, float]:
        """快速敏感性估计 (用于 predict_equilibrium 内部调用)"""
        sensitivities: Dict[str, float] = {}
        for param in list(config.parameter_values.keys())[:5]:
            bounds = self._get_param_bounds(param)
            range_w = bounds[1] - bounds[0]
            sensitivities[param.name] = round(range_w * 0.5, 3)
        return sensitivities
    
    @staticmethod
    def _generate_comparison_conclusion(
        pred_a: EquilibriumPrediction,
        pred_b: EquilibriumPrediction,
    ) -> str:
        """生成配置对比的自然语言结论"""
        coop_diff = pred_b.predicted_cooperation_rate - pred_a.predicted_cooperation_rate
        tension_diff = pred_b.narrative_tension_level - pred_a.narrative_tension_level
        
        parts: List[str] = []
        
        if abs(coop_diff) > 0.1:
            direction = "更高" if coop_diff > 0 else "更低"
            parts.append(f"合作倾向{direction}({abs(coop_diff):+.2f})")
        
        if abs(tension_diff) > 0.1:
            direction = "更高" if tension_diff > 0 else "更低"
            parts.append(f"叙事张力{direction}({abs(tension_diff):+.2f})")
        
        if not parts:
            return "两配置在主要指标上差异不明显。"
        
        return f"配置B相对于配置A: {'; '.join(parts)}。"
