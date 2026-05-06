"""
威胁可信度引擎 (ThreatCredibilityEngine) — Phase 4 核心模块之二

评估实体威胁声明的可信程度, 基于:
1. consistency: 声明-行为一致性 (指数移动平均)
2. cost_signal: 执行成本信号 (凸函数映射)
3. recency: 近期行为权重 (指数衰减)
4. pattern: 行为模式稳定性 (变异系数倒数)

学术依据:
- Schelling (1960): 可置信威胁需要执行意愿+执行能力
- Farrell & Rabin (1996): 廉价磋商定理 — 零成本信号不传递信息
- Kreps & Wilson (1982): 重复交互中的声誉效应
- Spence (1973): 信号传递理论 — 高成本信号更可信
"""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from .types import (
    CommitmentLevel,
    CredibilityScore,
    ThreatCredibilityConfig,
    ThreatRecord,
    ThreatType,
)


# ============================================================
# 承诺等级 → 成本乘数映射
# ============================================================

_COMMITMENT_COST_MULTIPLIERS: Dict[CommitmentLevel, float] = {
    CommitmentLevel.NONE: 0.3,
    CommitmentLevel.VERBAL: 0.5,
    CommitmentLevel.MATERIAL: 0.8,
    CommitmentLevel.IRREVERSIBLE: 1.0,
}

# 威胁类型 → 初始可信度偏移
_THREAT_TYPE_BASE_OFFSETS: Dict[ThreatType, float] = {
    ThreatType.BLUFF: -0.15,
    ThreatType.COMMITMENT: 0.10,
    ThreatType.SIGNALING: 0.00,
    ThreatType.RETALIATORY: 0.05,
    ThreatType.DETERRENCE: 0.08,
}


class ThreatCredibilityEngine:
    """
    威胁可信度引擎 — 计算和维护各实体的威胁可信度评分
    
    核心数据结构:
    _records: OrderedDict[str, List[ThreatRecord]]
      key = entity_id (被评估实体ID)
      value = 该实体的所有威胁记录时间序列
    
    _scores_cache: Dict[str, CredibilityScore]
      缓存最近计算的可信度评分
    
    四分量合成算法:
    overall = w_c·consistency + w_cs·cost_signal + w_r·recency + w_p·pattern
    
    各分量计算:
    - consistency: EMA(执行率), smoothing=config.consistency_smoothing
    - cost_signal: Σ(cost_i^power) / N, power=config.cost_credibility_power
    - recency: 加权平均, 权重=exp(-ln(2)·Δt/T_half)
    - pattern: 1 / (CV + ε), CV=σ/μ of execution delays
    """
    
    def __init__(
        self,
        character_id: str,
        config: Optional[ThreatCredibilityConfig] = None,
    ) -> None:
        self._character_id = character_id
        self._config = config or ThreatCredibilityConfig()
        
        self._records: "OrderedDict[str, List[ThreatRecord]]" = OrderedDict()
        self._scores_cache: Dict[str, CredibilityScore] = {}
    
    @property
    def config(self) -> ThreatCredibilityConfig:
        return self._config
    
    # ================================================================
    # 核心 API
    # ================================================================
    
    def record_threat(self, record: ThreatRecord) -> None:
        """
        记录一条新的威胁声明
        
        Args:
            record: 威胁记录 (包含类型/内容/承诺等级/估算成本)
        """
        entity_id = self._extract_entity_id(record)
        
        if entity_id not in self._records:
            if len(self._records) >= self._config.max_tracked_entities:
                self._evict_oldest_entity()
            self._records[entity_id] = []
        
        self._records[entity_id].append(record)
        self._invalidate_score(entity_id)
    
    def mark_executed(
        self,
        target_id: str,
        executed: bool,
        delay_seconds: Optional[float] = None,
    ) -> None:
        """
        标记目标实体最近一条未标记的威胁是否已执行
        
        查找规则: 找到 target_id 下 was_executed=False 的最新记录并更新
        
        Args:
            target_id: 实体ID
            executed: 是否实际执行
            delay_seconds: 执行延迟秒数 (未执行时为None)
        """
        records = self._records.get(target_id)
        if not records:
            return
        
        for r in reversed(records):
            if not r.was_executed:
                r.was_executed = executed
                r.execution_delay = delay_seconds
                break
        
        self._invalidate_score(target_id)
    
    def get_credibility(self, target_id: str) -> CredibilityScore:
        """
        获取指定实体的可信度评分 (带缓存)
        
        首次调用或缓存失效时重新计算四分量合成。
        
        Args:
            target_id: 实体ID
            
        Returns:
            CredibilityScore 对象 (包含四分量和综合分)
            
        Raises:
            KeyError: 如果该实体无任何记录
        """
        cached = self._scores_cache.get(target_id)
        if cached is not None:
            return cached
        
        records = self._records.get(target_id)
        if not records:
            raise KeyError(f"No threat records found for entity={target_id}")
        
        score = self._compute_full_score(target_id, records)
        self._scores_cache[target_id] = score
        return score
    
    def evaluate_threat_plausibility(
        self,
        target_id: str,
        threatened_action: str,
        estimated_cost: float,
        commitment_level: CommitmentLevel = CommitmentLevel.VERBAL,
    ) -> float:
        """
        评估一个新威胁的合理性概率 [0, 1]
        
        综合因素:
        1. 目标实体历史可信度 (overall_score)
        2. 本次威胁的成本信号 (cost^power 映射)
        3. 承诺等级加成 (IRREVERSIBLE > MATERIAL > VERBAL > NONE)
        4. 威胁类型基础偏移
        
        公式:
        plausibility = base_credibility × cost_factor × commitment_multiplier + type_offset
        
        Args:
            target_id: 发出威胁的目标实体ID
            threatened_action: 威胁内容描述
            estimated_cost: 估算执行成本 [0, 1]
            commitment_level: 承诺等级
            
        Returns:
            合理性概率 [0.0, 1.0]
        """
        try:
            existing_score = self.get_credibility(target_id)
            base = existing_score.overall_score
        except KeyError:
            base = self._config.base_credibility
        
        clamped_cost = max(0.0, min(1.0, estimated_cost))
        power = self._config.cost_credibility_power
        cost_factor = math.pow(clamped_cost, power)
        
        commit_mult = _COMMITMENT_COST_MULTIPLIERS.get(commitment_level, 0.5)
        
        type_offset = _THREAT_TYPE_BASE_OFFSETS.get(ThreatType.COMMITMENT, 0.0)
        
        raw = base * cost_factor * commit_mult + type_offset
        return max(0.0, min(1.0, raw))
    
    def get_all_scores(self) -> Dict[str, CredibilityScore]:
        """返回所有已跟踪实体的可信度评分字典"""
        result: Dict[str, CredibilityScore] = {}
        for entity_id in self._records:
            try:
                result[entity_id] = self.get_credibility(entity_id)
            except KeyError:
                continue
        return result
    
    def decay_old_records(self, days_elapsed: float) -> None:
        """
        衰减旧记录的影响 (通过使缓存过期实现)
        
        实际衰减在下次 get_credibility() 时通过 recency 分量自动体现。
        此方法主要用于显式触发批量重算。
        
        Args:
            days_elapsed: 经过的天数
        """
        if days_elapsed <= 0:
            return
        self._scores_cache.clear()
    
    def to_prompt_fragment(self, target_id: str, max_length: int = 150) -> str:
        """生成 LLM prompt 注入文本片段"""
        try:
            score = self.get_credibility(target_id)
        except KeyError:
            return f"[{target_id}]: 无威胁历史数据"
        
        parts = [
            f"总体可信度={self._qualify(score.overall_score)}({score.overall_score:.2f})",
            f"一致性={score.consistency_score:.2f}",
            f"成本信号={score.cost_signal_score:.2f}",
            f"样本数={score.sample_size}",
        ]
        
        status = "可靠" if score.is_reliable else "存疑"
        text = f"[{target_id}威胁评估]: {', '.join(parts)}. 状态:{status}"
        
        if len(text) > max_length:
            text = text[:max_length - 3] + "..."
        
        return text
    
    # ================================================================
    # 内部方法
    # ================================================================
    
    @staticmethod
    def _extract_entity_id(record: ThreatRecord) -> str:
        """从威胁记录提取实体标识 (预留扩展接口)"""
        return getattr(record, 'entity_id', '') or hash(record.content) % 100000
    
    def _evict_oldest_entity(self) -> None:
        """淘汰最久无更新的实体"""
        oldest = None
        oldest_time = float('inf')
        for eid, records in self._records.items():
            if records:
                latest = max(r.timestamp for r in records)
            else:
                latest = 0.0
            if latest < oldest_time:
                oldest_time = latest
                oldest = eid
        if oldest is not None and oldest in self._records:
            del self._records[oldest]
            self._scores_cache.pop(oldest, None)
    
    def _invalidate_score(self, entity_id: str) -> None:
        """清除指定实体的评分缓存"""
        self._scores_cache.pop(entity_id, None)
    
    def _compute_full_score(
        self, entity_id: str, records: List[ThreatRecord]
    ) -> CredibilityScore:
        """
        计算完整的四分量可信度评分
        
        Returns:
            新构建的 CredibilityScore
        """
        n = len(records)
        executed_records = [r for r in records if r.was_executed]
        n_exec = len(executed_records)
        
        consistency = self._compute_consistency(n, n_exec)
        cost_signal = self._compute_cost_signal(records)
        recency = self._compute_recency(records)
        pattern = self._compute_pattern(executed_records)
        
        wc = self._config.weight_consistency
        wcs = self._config.weight_cost_signal
        wr = self._config.weight_recency
        wp = self._config.weight_pattern
        total_w = wc + wcs + wr + wp
        
        overall = (
            wc * consistency
            + wcs * cost_signal
            + wr * recency
            + wp * pattern
        ) / total_w if total_w > 0 else 0.5
        
        overall = max(0.0, min(1.0, overall))
        
        return CredibilityScore(
            entity_id=entity_id,
            overall_score=round(overall, 4),
            consistency_score=round(consistency, 4),
            cost_signal_score=round(cost_signal, 4),
            recency_score=round(recency, 4),
            pattern_score=round(pattern, 4),
            sample_size=n,
            last_updated=time.time(),
        )
    
    def _compute_consistency(self, total: int, executed: int) -> float:
        """
        一致性分量 — EMA 平滑后的执行率
        
        简化版: 直接用执行率作为一致性度量
        完整版应使用 EMA: ema_t = α·rate_t + (1-α)·ema_{t-1}
        
        Args:
            total: 总威胁数
            executed: 已执行数
            
        Returns:
            一致性得分 [0, 1]
        """
        if total == 0:
            return 0.5
        raw_rate = executed / total
        smoothed = (
            self._config.consistency_smoothing * raw_rate
            + (1.0 - self._config.consistency_smoothing) * 0.5
        )
        return smoothed
    
    def _compute_cost_signal(self, records: List[ThreatRecord]) -> float:
        """
        成本信号分量 — 凸函数映射
        
        公式: signal = mean(cost_i ^ power)
        
        凸性保证 (power < 1):
        - 低成本区域变化快 (区分廉价 vs 略有代价)
        - 高成本区域趋近饱和 (避免极端值主导)
        
        Args:
            records: 所有威胁记录
            
        Returns:
            成本信号得分 [0, 1]
        """
        if not records:
            return 0.5
        
        power = self._config.cost_credibility_power
        costs = [r.estimated_cost ** power for r in records]
        return sum(costs) / len(costs)
    
    def _compute_recency(self, records: List[ThreatRecord]) -> float:
        """
        近期性分量 — 指数衰减加权
        
        更近期的记录获得更高权重:
        weight_i = exp(-ln(2) · Δt_i / T_half)
        
        其中 Δt_i 是第i条记录距当前的时间差 (天)
        T_half 由 config.recency_half_life_days 控制
        
        Args:
            records: 所有威胁记录
            
        Returns:
            近期性得分 [0, 1]
        """
        if not records:
            return 0.5
        
        now = time.time()
        half_life_sec = self._config.recency_half_life_days * 86400.0
        
        weighted_sum = 0.0
        weight_total = 0.0
        
        for r in records:
            delta_sec = now - r.timestamp
            delta_days = delta_sec / 86400.0
            weight = math.exp(-math.log(2.0) * delta_days / self._config.recency_half_life_days)
            
            exec_val = 1.0 if r.was_executed else 0.0
            weighted_sum += weight * exec_val
            weight_total += weight
        
        if weight_total < 1e-10:
            return 0.5
        
        raw = weighted_sum / weight_total
        smoothed = (
            self._config.consistency_smoothing * raw
            + (1.0 - self._config.consistency_smoothing) * 0.5
        )
        return smoothed
    
    def _compute_pattern(
        self, executed_records: List[ThreatRecord]
    ) -> float:
        """
        模式稳定性分量 — 变异系数倒数
        
        方法: 分析已执行威胁的延迟分布
        CV = σ / μ (变异系数,越小越稳定)
        stability = 1 / (1 + CV) (归一化到 [0, 1])
        
        特殊情况:
        - 无执行记录 → 返回 0.5 (中性)
        - 只有1条执行记录 → 返回 0.8 (样本太少但非零)
        - 延迟全为0 (即时执行) → 返回 1.0 (完美稳定)
        
        Args:
            executed_records: 已执行的威胁记录列表
            
        Returns:
            稳定性得分 [0, 1]
        """
        n = len(executed_records)
        
        if n == 0:
            return 0.5
        if n == 1:
            return 0.8
        
        delays = [
            d for r in executed_records
            if (d := r.execution_delay) is not None
        ]
        
        if not delays:
            return 0.6
        
        mean_d = sum(delays) / len(delays)
        if mean_d < 1e-10:
            return 1.0
        
        variance = sum((d - mean_d) ** 2 for d in delays) / len(delays)
        std_d = math.sqrt(variance)
        cv = std_d / mean_d
        
        stability = 1.0 / (1.0 + cv)
        return max(0.0, min(1.0, stability))
    
    @staticmethod
    def _qualify(value: float) -> str:
        if value >= 0.80:
            return "极高"
        elif value >= 0.65:
            return "高"
        elif value >= 0.50:
            return "中"
        elif value >= 0.35:
            return "偏低"
        elif value >= 0.20:
            return "低"
        else:
            return "极低"
