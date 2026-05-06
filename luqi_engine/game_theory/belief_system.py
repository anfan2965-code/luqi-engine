"""
信念系统 (BeliefSystem) — Phase 4 核心模块之一

基于贝叶斯推断的多维概率信念管理:
- 每个被观察实体维护 {BeliefDimension → BeliefState} 映射
- BeliefState 使用 Beta(α, β) 分布参数化, 支持闭式贝叶斯更新
- 观测通过 ObservationType 分类, 不同类型有不同可靠性折扣
- 旧信念随时间指数衰减 (向无信息先验回归)
- 维度间存在耦合传播规则

学术依据:
- 贝叶斯推断: P(θ|D) ∝ P(D|θ)P(θ)
- Harsanyi 转换: 不完全信息博弈 → 类型空间上的概率分布
- Beta-Bernoulli 共轭: 后验 = 先验 + 数据计数
"""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from .types import (
    BeliefDimension,
    BeliefState,
    BeliefSystemConfig,
    BeliefUpdateOutcome,
    Observation,
    ObservationType,
)


# ============================================================
# 维度耦合传播表 — 单向传播, 深度=1
# ============================================================

_DIMENSION_COUPLING_RULES: List[Tuple[BeliefDimension, float, BeliefDimension, float]] = [
    (BeliefDimension.COOPERATIVITY, 0.30, BeliefDimension.HONESTY),
    (BeliefDimension.COOPERATIVITY, -0.20, BeliefDimension.THREAT_LEVEL),
    (BeliefDimension.THREAT_LEVEL, -0.30, BeliefDimension.STABILITY),
    (BeliefDimension.HONESTY, -0.40, BeliefDimension.COOPERATIVITY),
    (BeliefDimension.ALIGNMENT, 0.25, BeliefDimension.COOPERATIVITY),
    (BeliefDimension.COMPETENCE, 0.15, BeliefDimension.THREAT_LEVEL),
]

# 观测类型可靠性映射 (从配置中获取默认值, 此处为后备)
_OBSERVATION_TYPE_RELIABILITY_DEFAULTS: Dict[ObservationType, float] = {
    ObservationType.DIRECT_ACTION: 1.0,
    ObservationType.REPORTED_INFO: 0.7,
    ObservationType.SIGNAL_SENT: 0.6,
    ObservationType.ABSENCE_OF_ACTION: 0.5,
    ObservationType.CONTEXTUAL_CUE: 0.3,
}

_STRONG_EVIDENCE_THRESHOLD: float = 0.3


class BeliefSystem:
    """
    信念系统主类 — 管理角色对所有其他实体的多维概率信念
    
    核心数据结构:
    _beliefs: OrderedDict[str, Dict[BeliefDimension, BeliefState]]
      外层 key = target_id (被观察实体ID)
      内层 key = dimension (信念维度)
      value = 该维度上的 Beta 分布参数化信念状态
    
    设计约束:
    - 最大跟踪目标数由 config.max_tracked_targets 控制 (默认20)
    - 超限时按 LRU (最近更新时间) 淘汰最旧目标
    - 所有数值操作使用钳制防止溢出/下溢
    
    线程安全说明:
    本实现非线程安全。如需并发访问，调用方需加锁。
    """
    
    MAX_TRACKED_TARGETS: ClassVar[int] = 20
    
    def __init__(
        self,
        character_id: str,
        config: Optional[BeliefSystemConfig] = None,
    ) -> None:
        """
        初始化信念系统
        
        Args:
            character_id: 所属角色实体ID
            config: 配置对象 (None 时使用默认值)
        """
        self._character_id = character_id
        self._config = config or BeliefSystemConfig()
        
        self._beliefs: "OrderedDict[str, Dict[BeliefDimension, BeliefState]]" = (
            OrderedDict()
        )
    
    @property
    def config(self) -> BeliefSystemConfig:
        """返回当前配置的只读引用"""
        return self._config
    
    # ================================================================
    # 核心 API: observe / get_belief / predict / forget
    # ================================================================
    
    def observe(
        self,
        target_id: str,
        dimension: BeliefDimension,
        observation: Observation,
    ) -> BeliefUpdateOutcome:
        """
        记录一次观测并更新对应维度的信念状态
        
        更新算法 (Beta-Bernoulli 共轭闭式解):
        1. 计算有效证据强度:
           effective = evidence_value × type_reliability × source_reliability × strength_weight
        2. 更新 Beta 参数:
           α_new = α_old + effective
           β_new = β_old + (1 - effective)
        3. 钳制到 [MIN_ALPHA, MAX_ALPHA_BETA] 范围
        4. 判定更新结果分类 (STRENGTHENED / WEAKENED / REVERSED / UNCHANGED)
        5. 执行维度间耦合传播 (深度=1, 仅影响同 target 的其他维度)
        
        Args:
            target_id: 被观察目标实体ID
            dimension: 被更新的信念维度
            observation: 观测记录
            
        Returns:
            BeliefUpdateOutcome 枚举值, 描述更新的性质
            
        Raises:
            ValueError: 如果 evidence_value 或 source_reliability 超出 [0, 1]
        """
        state = self._get_or_create_state(target_id, dimension)
        
        old_ev = state.expected_value
        
        effective_evidence = self._compute_effective_evidence(observation)
        
        is_strong = abs(observation.evidence_value - 0.5) > _STRONG_EVIDENCE_THRESHOLD
        
        state.alpha += effective_evidence
        state.beta_param += (1.0 - effective_evidence)
        
        state.alpha = max(state.alpha, state._MIN_ALPHA)
        state.alpha = min(state.alpha, state._MAX_ALPHA_BETA)
        state.beta_param = max(state.beta_param, state._MIN_BETA)
        state.beta_param = min(state.beta_param, state._MAX_ALPHA_BETA)
        
        state.last_updated = time.time()
        state.total_observations += 1
        if is_strong:
            state.strong_evidences += 1
        
        new_ev = state.expected_value
        
        outcome = self._classify_update(old_ev, new_ev, state.confidence)
        
        self._propagate_coupling(target_id, dimension, outcome, effective_evidence)
        
        return outcome
    
    def get_belief(
        self, target_id: str, dimension: BeliefDimension
    ) -> BeliefState:
        """
        获取指定目标和维度的信念状态副本
        
        Args:
            target_id: 目标实体ID
            dimension: 信念维度
            
        Returns:
            BeliefState 副本 (修改不影响内部状态)
            
        Raises:
            KeyError: 如果该目标+维度组合不存在
        """
        dim_map = self._beliefs.get(target_id)
        if not dim_map or dimension not in dim_map:
            raise KeyError(
                f"No belief found for target={target_id}, dimension={dimension.name}"
            )
        existing = dim_map[dimension]
        return BeliefState(
            target_id=existing.target_id,
            dimension=existing.dimension,
            alpha=existing.alpha,
            beta_param=existing.beta_param,
            last_updated=existing.last_updated,
            total_observations=existing.total_observations,
            strong_evidences=existing.strong_evidences,
            half_life_days=existing.half_life_days,
        )
    
    def get_target_summary(self, target_id: str) -> Dict[str, Any]:
        """
        全维度信念摘要 — 综合评估 + 置信度轮廓
        
        Returns:
            包含以下字段的字典:
            - target_id: 目标ID
            - dimensions: 各维度期望值和置信度
            - overall_cooperation_estimate: 加权合作倾向估计
            - trust_level: 总体信任等级 (low/medium/high)
            - has_decisive_beliefs: 是否有任何决定性信念
            - last_observed_any_dim: 最近观测时间戳
            - total_observations_all_dims: 全维度总观测数
        """
        dim_map = self._beliefs.get(target_id)
        if not dim_map:
            return {
                "target_id": target_id,
                "dimensions": {},
                "overall_cooperation_estimate": 0.5,
                "trust_level": "unknown",
                "has_decisive_beliefs": False,
                "last_observed_any_dim": 0.0,
                "total_observations_all_dims": 0,
            }
        
        dims_info: List[Dict[str, Any]] = []
        coop_sum = 0.0
        weight_total = 0.0
        any_decisive = False
        latest_ts = 0.0
        total_obs = 0
        coop_weight = {
            BeliefDimension.COOPERATIVITY: 0.35,
            BeliefDimension.HONESTY: 0.25,
            BeliefDimension.ALIGNMENT: 0.20,
            BeliefDimension.COMPETENCE: 0.10,
            BeliefDimension.STABILITY: 0.10,
        }
        
        for dim in BeliefDimension:
            state = dim_map.get(dim)
            if state is None:
                continue
            entry = {
                "dimension": dim.name,
                "expected_value": round(state.expected_value, 4),
                "confidence": round(state.confidence, 4),
                "is_decisive": state.is_decisive,
                "total_observations": state.total_observations,
            }
            dims_info.append(entry)
            
            w = coop_weight.get(dim, 0.05)
            coop_sum += w * state.expected_value
            weight_total += w
            
            if state.is_decisive:
                any_decisive = True
            if state.last_updated > latest_ts:
                latest_ts = state.last_updated
            total_obs += state.total_observations
        
        overall_coop = coop_sum / max(weight_total, 1e-6)
        
        if overall_coop >= 0.7:
            trust = "high"
        elif overall_coop <= 0.35:
            trust = "low"
        else:
            trust = "medium"
        
        return {
            "target_id": target_id,
            "dimensions": dims_info,
            "overall_cooperation_estimate": round(overall_coop, 4),
            "trust_level": trust,
            "has_decisive_beliefs": any_decisive,
            "last_observed_any_dim": latest_ts,
            "total_observations_all_dims": total_obs,
        }
    
    def get_all_targets(self) -> List[str]:
        """返回当前所有已跟踪的目标ID列表"""
        return list(self._beliefs.keys())
    
    def decay_all(self, days_elapsed: float) -> None:
        """
        对所有目标的全部维度应用时间衰减
        
        Args:
            days_elapsed: 经过的天数 (非负)
        """
        if days_elapsed <= 0:
            return
        for dim_map in self._beliefs.values():
            for state in dim_map.values():
                state.apply_decay(days_elapsed)
    
    def forget_target(self, target_id: str) -> bool:
        """移除对指定目标的全部信念"""
        if target_id in self._beliefs:
            del self._beliefs[target_id]
            return True
        return False
    
    # ================================================================
    # 高级查询 API
    # ================================================================
    
    def predict_cooperation_probability(
        self,
        target_id: str,
        scenario_weights: Optional[Dict[BeliefDimension, float]] = None,
    ) -> float:
        """
        加权组合各维度信念预测合作概率
        
        默认权重方案:
        COOPERATIVITY: 0.35 (直接反映合作倾向)
        HONESTY:       0.25 (诚实度影响可信承诺)
        ALIGNMENT:     0.20 (目标一致性驱动合作意愿)
        COMPETENCE:    0.10 (能力辅助但不决定)
        STABILITY:     0.10 (稳定性降低不确定性风险)
        
        THREAT_LEVEL 作为抑制因子:
        当威胁水平高时, 合作概率被压低
        
        Args:
            target_id: 目标实体ID
            scenario_weights: 自定义维度权重 (None 则用默认)
            
        Returns:
            合作概率估计 [0.0, 1.0], 无记录时返回 0.5
        """
        dim_map = self._beliefs.get(target_id)
        if not dim_map:
            return 0.5
        
        default_weights = {
            BeliefDimension.COOPERATIVITY: 0.35,
            BeliefDimension.HONESTY: 0.25,
            BeliefDimension.ALIGNMENT: 0.20,
            BeliefDimension.COMPETENCE: 0.10,
            BeliefDimension.STABILITY: 0.10,
        }
        weights = scenario_weights or default_weights
        
        weighted_sum = 0.0
        weight_total = 0.0
        threat_suppression = 1.0
        
        for dim, state in dim_map.items():
            w = weights.get(dim, 0.0)
            if w > 0 and state is not None:
                weighted_sum += w * state.expected_value
                weight_total += w
                
                if dim == BeliefDimension.THREAT_LEVEL:
                    threat_suppression = max(0.1, 1.0 - 0.5 * state.expected_value)
        
        base_prob = weighted_sum / max(weight_total, 1e-6)
        return base_prob * threat_suppression
    
    def detect_belief_change(
        self,
        target_id: str,
        dimension: BeliefDimension,
        window_size: int = 5,
    ) -> Optional[float]:
        """
        检测信念的显著变化趋势
        
        方法: 返回最近 window_size 次观测的平均变化方向
        正值表示信念在增强, 负值表示减弱
        
        注意: 当前简化实现, 基于 expected_value 与 0.5 的距离变化率
        完整版本需要维护观测历史队列
        
        Args:
            target_id: 目标实体ID
            dimension: 信念维度
            window_size: 观察窗口大小 (预留参数)
            
        Returns:
            变化幅度 [-1, 1], 或 None (无足够数据)
        """
        try:
            state = self.get_belief(target_id, dimension)
        except KeyError:
            return None
        
        if state.total_observations < 3:
            return None
        
        direction = state.expected_value - 0.5
        confidence_factor = min(state.confidence, 1.0)
        
        return direction * confidence_factor
    
    def to_prompt_fragment(
        self, target_id: str, max_length: int = 200
    ) -> str:
        """
        生成 LLM prompt 注入文本片段
        
        格式示例:
        "[关于Alice]: 合作倾向=高(0.82,conf=0.91), 威胁感知=低(0.18), 
         诚实度=中(0.65). 总评: 高信任盟友."
         
        Args:
            target_id: 目标实体ID
            max_length: 最大字符长度限制
            
        Returns:
            格式化的信念描述字符串
        """
        summary = self.get_target_summary(target_id)
        
        parts: List[str] = []
        for dinfo in summary.get("dimensions", []):
            dim_name = dinfo["dimension"]
            ev = dinfo["expected_value"]
            conf = dinfo["confidence"]
            qual = self._qualify(ev)
            parts.append(f"{dim_name}={qual}({ev:.2f},c={conf:.2f})")
        
        trust = summary.get("trust_level", "unknown")
        decisive = "✓" if summary.get("has_decisive_beliefs") else ""
        
        text = f"[关于{target_id}]: {', '.join(parts)}. 总评: {trust}信任{decisive}."
        
        if len(text) > max_length:
            text = text[:max_length - 3] + "..."
        
        return text
    
    # ================================================================
    # 内部方法 (私有)
    # ================================================================
    
    def _get_or_create_state(
        self, target_id: str, dimension: BeliefDimension
    ) -> BeliefState:
        """获取或创建指定目标+维度的 BeliefState"""
        if target_id not in self._beliefs:
            if len(self._beliefs) >= self._config.max_tracked_targets:
                self._evict_lru_target()
            self._beliefs[target_id] = {}
        
        dim_map = self._beliefs[target_id]
        if dimension not in dim_map:
            dim_map[dimension] = BeliefState(
                target_id=target_id,
                dimension=dimension,
                alpha=self._config.prior_alpha,
                beta_param=self._config.prior_beta,
                half_life_days=self._config.default_half_life_days,
            )
        
        return dim_map[dimension]
    
    def _evict_lru_target(self) -> None:
        """LRU淘汰: 移除最久未更新的目标"""
        oldest_target = None
        oldest_time = float('inf')
        for tid, dim_map in self._beliefs.items():
            latest_in_target = 0.0
            for state in dim_map.values():
                if state.last_updated > latest_in_target:
                    latest_in_target = state.last_updated
            if latest_in_target < oldest_time:
                oldest_time = latest_in_target
                oldest_target = tid
        
        if oldest_target is not None:
            del self._beliefs[oldest_target]
    
    def _compute_effective_evidence(self, obs: Observation) -> float:
        """
        计算有效证据强度 [0, 1]
        
        公式: effective = evidence × type_reliability × source_reliability × strength_weight
        其中 strength_weight 根据 |evidence - 0.5| 决定:
          |e-0.5| > 0.3 → strong (weight=config.strong_evidence_weight)
          否则              → weak   (weight=config.weak_evidence_weight)
        """
        type_rel = getattr(
            self._config, f"{obs.observation_type.name.lower()}_reliability", None
        ) or _OBSERVATION_TYPE_RELIABILITY_DEFAULTS.get(
            obs.observation_type, 0.8
        )
        
        raw = obs.evidence_value * type_rel * obs.source_reliability
        
        strength = self._config.strong_evidence_weight if (
            abs(obs.evidence_value - 0.5) > _STRONG_EVIDENCE_THRESHOLD
        ) else self._config.weak_evidence_weight
        
        effective = raw * strength
        return max(0.0, min(1.0, effective))
    
    def _classify_update(
        self,
        old_ev: float,
        new_ev: float,
        confidence: float,
    ) -> BeliefUpdateOutcome:
        """
        将信念更新分类为四种结果之一
        
        判定逻辑:
        - UNCHANGED: |new - old| < 0.01 且 confidence < threshold
        - STRENGTHENED: 新旧在同一侧且距离0.5更远
        - WEAKENED: 新旧在同一侧但距离0.5更近
        - REVERSED: 跨越了 0.5 分界线且置信度够高
        """
        delta = new_ev - old_ev
        
        if abs(delta) < 0.01 and confidence < self._config.confidence_threshold:
            return BeliefUpdateOutcome.UNCHANGED
        
        crossed_zero_point = (old_ev < 0.5 <= new_ev) or (old_ev > 0.5 >= new_ev)
        
        if crossed_zero_point and confidence > self._config.confidence_threshold:
            return BeliefUpdateOutcome.REVERSED
        
        if delta > 0:
            return BeliefUpdateOutcome.STRENGTHENED
        else:
            return BeliefUpdateOutcome.WEAKENED
    
    def _propagate_coupling(
        self,
        target_id: str,
        source_dim: BeliefDimension,
        outcome: BeliefUpdateOutcome,
        effective_evidence: float,
    ) -> None:
        """
        执行维度间单向耦合传播 (深度=1)
        
        传播规则定义在 _DIMENSION_COUPLING_RULES 中:
        (source_dim, coupling_strength, affected_dim)
        
        传播量 = coupling_strength × effective_evidence × direction_sign
        direction_sign 由 outcome 决定 (+1 for STRENGTHENED, -1 for WEAKENED)
        """
        dim_map = self._beliefs.get(target_id)
        if not dim_map:
            return
        
        direction = 1.0 if outcome == BeliefUpdateOutcome.STRENGTHENED else -1.0
        
        for rule_src, strength, rule_dst in _DIMENSION_COUPLING_RULES:
            if rule_src != source_dim:
                continue
            affected_state = dim_map.get(rule_dst)
            if affected_state is None:
                continue
            
            propagation = strength * effective_evidence * direction
            
            if propagation > 0:
                affected_state.alpha += propagation
            elif propagation < 0:
                affected_state.beta_param += abs(propagation)
            
            affected_state.alpha = max(affected_state.alpha, affected_state._MIN_ALPHA)
            affected_state.alpha = min(affected_state.alpha, affected_state._MAX_ALPHA_BETA)
            affected_state.beta_param = max(affected_state.beta_param, affected_state._MIN_BETA)
            affected_state.beta_param = min(affected_state.beta_param, affected_state._MAX_ALPHA_BETA)
    
    @staticmethod
    def _qualify(value: float) -> str:
        """将 [0,1] 值映射为中文定性标签"""
        if value >= 0.80:
            return "极高"
        elif value >= 0.65:
            return "高"
        elif value >= 0.50:
            return "中偏高"
        elif value >= 0.35:
            return "中偏低"
        elif value >= 0.20:
            return "低"
        else:
            return "极低"
