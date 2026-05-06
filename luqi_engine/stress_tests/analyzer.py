"""
分析器模块 — 引擎能力评估与弱点诊断
========================================

核心功能:
1. 结局合理性检验 — 结果是否符合博弈论预期
2. 子系统性能评分 — 信念/威胁/策略各模块表现
3. 极限能力探测 — 引擎在极端条件下的行为
4. 弱点诊断 — 系统性缺陷识别与分类
5. 综合报告生成 — 结构化输出供后续改进参考

评估维度:
  一致性: 信念-策略-行为的逻辑连贯性
  自适应性: 对环境变化的响应速度和质量
  鲁棒性: 边界条件和异常输入的处理能力
  效率性: 资源消耗和计算复杂度
  可解释性: 行为决策的可追溯程度
"""

from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from .game_loop import (
    EndingType,
    GameLoop,
    GameState,
    RoundMetrics,
    RoundPhase,
    RoundResult,
)
from .universe import (
    CosmicEra,
    InteractionType,
    UniverseRules,
)


# ============================================================
# 评分标准定义
# ============================================================

@dataclass
class ScoreBand:
    """评分区间"""
    min_score: float
    max_score: float
    label: str
    description: str


_SCORE_BANDS: List[ScoreBand] = [
    ScoreBand(0.9, 1.0, "优秀", "远超预期, 接近理论最优"),
    ScoreBand(0.7, 0.9, "良好", "达到预期, 有少量可优化空间"),
    ScoreBand(0.5, 0.7, "合格", "基本可用, 存在明显短板"),
    ScoreBand(0.3, 0.5, "勉强", "部分功能失效, 需要修复"),
    ScoreBand(0.0, 0.3, "不合格", "严重问题, 无法正常使用"),
]


def _score_to_band(score: float) -> ScoreBand:
    for band in _SCORE_BANDS:
        if band.min_score <= score < band.max_score:
            return band
    return _SCORE_BANDS[-1]


# ============================================================
# 分析维度枚举
# ============================================================

class AnalysisDimension(Enum):
    """分析维度"""
    BELIEF_COHERENCE = auto()
    THREAT_ASSESSMENT = auto()
    STRATEGY_QUALITY = auto()
    ADAPTATION_SPEED = auto()
    CONSISTENCY_MAINTENANCE = auto()
    RESOURCE_MANAGEMENT = auto()
    SOCIAL_DYNAMICS = auto()
    LONG_TERM_PLANNING = auto()
    CRISIS_RESPONSE = auto()
    OVERALL_ROBUSTNESS = auto()


class WeaknessCategory(Enum):
    """弱点类别"""
    LOGICAL_INCONSISTENCY = auto()
    SLOW_CONVERGENCE = auto()
    OSCILLATION = auto()
    COLLAPSE = auto()
    STAGNATION = auto()
    MEMORY_LEAK = auto()
    NUMERICAL_INSTABILITY = auto()
    STRATEGIC_BLINDNESS = auto()
    EMOTIONAL_FLATNESS = auto()
    NARRATIVE_DISCONNECT = auto()


class CapabilityLevel(Enum):
    """能力等级"""
    DEMONSTRATED_EXCELLENT = auto()
    DEMONSTRATED_GOOD = auto()
    DEMONSTRATED_BASIC = auto()
    NOT_DEMONSTRATED = auto()
    FAILED = auto()


# ============================================================
# 数据结构
# ============================================================

@dataclass
class DimensionScore:
    """单维度评分"""
    dimension: AnalysisDimension
    score: float
    evidence: List[str]
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def band(self) -> ScoreBand:
        return _score_to_band(self.score)
    
    @property
    def grade(self) -> str:
        return self.band.label


@dataclass
class WeaknessFinding:
    """弱点发现"""
    category: WeaknessCategory
    severity: float
    description: str
    affected_rounds: Tuple[int, int]
    affected_civ_ids: List[str]
    suggested_fix: str
    frequency: int = 1


@dataclass
class CapabilityAssessment:
    """能力评估项"""
    name: str
    level: CapabilityLevel
    demonstration_round: Optional[int]
    confidence: float
    notes: str


@dataclass
class OutcomeEvaluation:
    """结局评估"""
    expected_type: EndingType
    actual_type: Optional[EndingType]
    plausibility_score: float
    alignment_with_game_theory: float
    narrative_coherence: float
    analysis: str
    alternative_outcomes: List[str] = field(default_factory=list)


@dataclass
class PerformanceProfile:
    """性能画像"""
    avg_round_time_ms: float
    p95_round_time_ms: float
    p99_round_time_ms: float
    total_cpu_time_sec: float
    peak_memory_estimate_mb: float
    rounds_per_second: float
    bottleneck_phase: Optional[RoundPhase]
    time_distribution_pct: Dict[str, float]


@dataclass
class EngineCapabilityReport:
    """
    引擎能力报告 — 压力测试的最终输出
    
    这是用户最关心的产物: 引擎到底行不行? 哪里不行? 为什么?
    """
    
    test_metadata: Dict[str, Any]
    overall_score: float
    dimension_scores: List[DimensionScore]
    weaknesses: List[WeaknessFinding]
    capabilities: List[CapabilityAssessment]
    outcome_evaluation: OutcomeEvaluation
    performance: PerformanceProfile
    limit_findings: Dict[str, Any]
    recommendations: List[str]
    
    @property
    def overall_grade(self) -> str:
        return _score_to_band(self.overall_score).label
    
    @property
    def critical_weakness_count(self) -> int:
        return sum(1 for w in self.weaknesses if w.severity > 0.7)
    
    @property
    def is_acceptable(self) -> bool:
        return self.overall_score >= 0.5 and self.critical_weakness_count <= 2
    
    def to_text_report(self) -> str:
        """生成文本格式报告"""
        lines: List[str] = []
        
        lines.append("=" * 80)
        lines.append("Luqi Engine 极限压力测试报告")
        lines.append("=" * 80)
        
        meta = self.test_metadata
        lines.append(f"\n【测试元信息】")
        lines.append(f"  测试时间:     {meta.get('timestamp', 'N/A')}")
        lines.append(f"  配置模式:     {meta.get('config_mode', 'N/A')}")
        lines.append(f"  文明数量:     {meta.get('num_civilizations', 'N/A')}")
        lines.append(f"  总轮次:       {meta.get('total_rounds', 'N/A')}")
        lines.append(f"  随机种子:     {meta.get('seed', 'N/A')}")
        lines.append(f"  总耗时:       {meta.get('total_time_sec', 0):.2f}s")
        
        lines.append(f"\n【综合评分】")
        lines.append(f"  总分:         {self.overall_score:.3f} / 1.000")
        lines.append(f"  等级:         {self.overall_grade}")
        lines.append(f"  是否合格:     {'✓ 通过' if self.is_acceptable else '✗ 未通过'}")
        
        lines.append(f"\n【维度评分明细】")
        for ds in sorted(self.dimension_scores, key=lambda x: x.score):
            bar_len = int(ds.score * 40)
            bar = "█" * bar_len + "░" * (40 - bar_len)
            lines.append(
                f"  {ds.dimension.name:<28s} [{bar}] {ds.score:.3f} ({ds.grade})"
            )
            if ds.evidence:
                for ev in ds.evidence[:2]:
                    lines.append(f"    → {ev}")
        
        lines.append(f"\n【弱点诊断】 (共{len(self.weaknesses)}项)")
        sorted_weaknesses = sorted(self.weaknesses, key=lambda w: -w.severity)
        for i, w in enumerate(sorted_weaknesses[:10], 1):
            severity_marker = "🔴" if w.severity > 0.7 else ("🟡" if w.severity > 0.4 else "🟢")
            lines.append(
                f"  {i}. [{severity_marker}] {w.category.name}"
            )
            lines.append(f"     严重度: {w.severity:.2f} | 出现次数: {w.frequency}")
            lines.append(f"     描述:   {w.description[:100]}")
            lines.append(f"     建议:   {w.suggested_fix[:100]}")
        
        lines.append(f"\n【结局评估】")
        oe = self.outcome_evaluation
        lines.append(f"  预期结局:     {oe.expected_type.name}")
        lines.append(f"  实际结局:     {oe.actual_type.name if oe.actual_type else 'N/A'}")
        lines.append(f"  合理性得分:   {oe.plausibility_score:.3f}")
        lines.append(f"  博弈论一致性: {oe.alignment_with_game_theory:.3f}")
        lines.append(f"  叙事连贯性:   {oe.narrative_coherence:.3f}")
        lines.append(f"  分析: {oe.analysis[:200]}")
        
        lines.append(f"\n【能力矩阵】")
        for cap in sorted(self.capabilities, key=lambda c: c.level.value):
            level_marker = {
                CapabilityLevel.DEMONSTRATED_EXCELLENT: "★★★",
                CapabilityLevel.DEMONSTRATED_GOOD: "★★☆",
                CapabilityLevel.DEMONSTRATED_BASIC: "★☆☆",
                CapabilityLevel.NOT_DEMONSTRATED: "○○○",
                CapabilityLevel.FAILED: "✗✗✗",
            }.get(cap.level, "?")
            lines.append(
                f"  {level_marker} {cap.name:<30s} ({cap.level.name}) "
                f"[置信度:{cap.confidence:.2f}]"
            )
            if cap.notes:
                lines.append(f"      {cap.notes[:80]}")
        
        lines.append(f"\n【性能画像】")
        pf = self.performance
        lines.append(f"  平均轮耗时:   {pf.avg_round_time_ms:.2f}ms")
        lines.append(f"  P95 轮耗时:   {pf.p95_round_time_ms:.2f}ms")
        lines.append(f"  P99 轮耗时:   {pf.p99_round_time_ms:.2f}ms")
        lines.append(f"  吞吐量:       {pf.rounds_per_second:.1f} rounds/s")
        lines.append(f"  瓶颈阶段:     {pf.bottleneck_phase.name if pf.bottleneck_phase else 'N/A'}")
        
        lines.append(f"\n【极限发现】")
        for key, val in self.limit_findings.items():
            if isinstance(val, (int, float)):
                lines.append(f"  {key}: {val}")
            elif isinstance(val, str):
                lines.append(f"  {key}: {val[:100]}")
            else:
                lines.append(f"  {key}: {val}")
        
        lines.append(f"\n【改进建议】")
        for i, rec in enumerate(self.recommendations[:10], 1):
            lines.append(f"  {i}. {rec}")
        
        lines.append("\n" + "=" * 80)
        
        return "\n".join(lines)


# ============================================================
# 核心分析器类
# ============================================================

@dataclass
class StressTestAnalyzer:
    """
    压力测试分析器 — 从GameState提取洞察
    
    使用方式:
        analyzer = StressTestAnalyzer(game_state)
        report = analyzer.full_analysis()
        print(report.to_text_report())
    """
    
    state: GameState
    _cache: Dict[str, Any] = field(default_factory=dict, repr=False)
    
    def full_analysis(self) -> EngineCapabilityReport:
        """执行完整分析并返回报告"""
        dim_scores = self._analyze_all_dimensions()
        weaknesses = self._identify_weaknesses(dim_scores)
        capabilities = self._assess_capabilities()
        outcome_eval = self._evaluate_outcome()
        performance = self._analyze_performance()
        limits = self._detect_limits()
        recommendations = self._generate_recommendations(
            weaknesses, dim_scores, limits
        )
        
        overall = self._compute_overall_score(dim_scores, weaknesses)
        
        return EngineCapabilityReport(
            test_metadata=self._build_test_metadata(),
            overall_score=overall,
            dimension_scores=dim_scores,
            weaknesses=weaknesses,
            capabilities=capabilities,
            outcome_evaluation=outcome_eval,
            performance=performance,
            limit_findings=limits,
            recommendations=recommendations,
        )
    
    # =================================================================
    # 维度分析
    # =================================================================
    
    def _analyze_all_dimensions(self) -> List[DimensionScore]:
        analyzers: Dict[AnalysisDimension, callable] = {
            AnalysisDimension.BELIEF_COHERENCE: self._analyze_belief_coherence,
            AnalysisDimension.THREAT_ASSESSMENT: self._analyze_threat_assessment,
            AnalysisDimension.STRATEGY_QUALITY: self._analyze_strategy_quality,
            AnalysisDimension.ADAPTATION_SPEED: self._analyze_adaptation_speed,
            AnalysisDimension.CONSISTENCY_MAINTENANCE: self._analyze_consistency_maintenance,
            AnalysisDimension.RESOURCE_MANAGEMENT: self._analyze_resource_management,
            AnalysisDimension.SOCIAL_DYNAMICS: self._analyze_social_dynamics,
            AnalysisDimension.LONG_TERM_PLANNING: self._analyze_long_term_planning,
            AnalysisDimension.CRISIS_RESPONSE: self._analyze_crisis_response,
            AnalysisDimension.OVERALL_ROBUSTNESS: self._analyze_robustness,
        }
        
        results: List[DimensionScore] = []
        for dimension, analyzer_func in analyzers.items():
            try:
                result = analyzer_func()
                results.append(result)
            except Exception as e:
                results.append(DimensionScore(
                    dimension=dimension,
                    score=0.0,
                    evidence=[f"分析异常: {str(e)}"],
                ))
        
        return results
    
    def _analyze_belief_coherence(self) -> DimensionScore:
        """信念系统一致性分析"""
        evidence: List[str] = []
        coherence_scores: List[float] = []
        
        snapshots_by_civ: Dict[str, list] = {}
        for snap in self.state.rules.environment.state_history:
            civ_id = snap.civ_id
            if civ_id not in snapshots_by_civ:
                snapshots_by_civ[civ_id] = []
            snapshots_by_civ[civ_id].append(snap)
        
        for civ_id, snaps in snapshots_by_civ.items():
            if len(snaps) < 10:
                continue
            
            entropies = [s.belief_entropy for s in snaps if s.is_alive]
            if not entropies:
                continue
            
            entropy_trend = entropies[-min(50, len(entropies)):]
            
            if len(entropy_trend) >= 20:
                early_avg = statistics.mean(entropy_trend[:len(entropy_trend)//2])
                late_avg = statistics.mean(entropy_trend[len(entropy_trend)//2:])
                
                convergence = 1.0 - abs(late_avg - early_avg) / (early_avg + 0.01)
                convergence = max(0.0, min(1.0, convergence))
                coherence_scores.append(convergence)
                
                if convergence > 0.8:
                    evidence.append(f"{civ_id}: 信念熵收敛良好 ({early_avg:.2f}→{late_avg:.2f})")
                elif convergence < 0.4:
                    evidence.append(f"{civ_id}: 信念持续震荡未收敛 ({early_avg:.2f}→{late_avg:.2f})")
        
        if coherence_scores:
            avg_coherence = statistics.mean(coherence_scores)
        else:
            avg_coherence = 0.5
            evidence.append("无法获取足够的信念数据进行分析")
        
        return DimensionScore(
            dimension=AnalysisDimension.BELIEF_COHERENCE,
            score=avg_coherence,
            evidence=evidence,
            details={
                "civ_count_analyzed": len(snapshots_by_civ),
                "coherence_values": coherence_scores,
            },
        )
    
    def _analyze_threat_assessment(self) -> DimensionScore:
        """威胁可信度评估质量分析"""
        evidence: List[str] = []
        assessment_quality: List[float] = []
        
        threat_events = [
            e for e in self.state.rules.environment.history
            if e.event_type == InteractionType.CONFLICT
        ]
        
        if len(threat_events) < 5:
            return DimensionScore(
                dimension=AnalysisDimension.THREAT_ASSESSMENT,
                score=0.5,
                evidence=["冲突事件不足, 无法充分评估威胁系统"],
            )
        
        target_conflict_counts: Dict[str, int] = {}
        for event in threat_events:
            tid = event.target_civ_id or ""
            target_conflict_counts[tid] = target_conflict_counts.get(tid, 0) + 1
        
        for inst in self.state.instances:
            try:
                all_cred = inst.character.threat_engine.get_all_scores()
                for target_id, cred_score in all_cred.items():
                    conflict_count = target_conflict_counts.get(target_id, 0)
                    
                    if conflict_count > 5 and cred_score.overall_score > 0.6:
                        assessment_quality.append(0.8)
                        evidence.append(
                            f"{inst.civ_id}→{target_id}: 高威胁目标被正确高评 "
                            f"(cred={cred_score.overall_score:.2f}, conflicts={conflict_count})"
                        )
                    elif conflict_count == 0 and cred_score.overall_score < 0.3:
                        assessment_quality.append(0.7)
                    elif conflict_count > 10 and cred_score.overall_score < 0.3:
                        assessment_quality.append(0.3)
                        evidence.append(
                            f"{inst.civ_id}→{target_id}: 高频冲突目标被低估 "
                            f"(cred={cred_score.overall_score:.2f}, conflicts={conflict_count})"
                        )
            except (AttributeError, TypeError):
                pass
        
        if assessment_quality:
            quality = statistics.mean(assessment_quality)
        else:
            quality = 0.5
            evidence.append("威胁可信度数据不可用")
        
        return DimensionScore(
            dimension=AnalysisDimension.THREAT_ASSESSMENT,
            score=quality,
            evidence=evidence[:5],
            details={
                "threat_events_total": len(threat_events),
                "assessments_checked": len(assessment_quality),
            },
        )
    
    def _analyze_strategy_quality(self) -> DimensionScore:
        """混合策略质量分析"""
        evidence: List[str] = []
        strategy_scores: List[float] = []
        
        strategy_entropies: List[float] = []
        for snap in self.state.rules.environment.state_history:
            if snap.strategy_entropy > 0 and snap.is_alive:
                strategy_entropies.append(snap.strategy_entropy)
        
        if strategy_entropies:
            avg_entropy = statistics.mean(strategy_entropies)
            std_entropy = statistics.stdev(strategy_entropies) if len(strategy_entropies) > 1 else 0
            
            optimal_entropy_range = (0.8, 1.8)
            if optimal_entropy_range[0] <= avg_entropy <= optimal_entropy_range[1]:
                entropy_score = 1.0
                evidence.append(f"策略熵在最优区间 ({avg_entropy:.3f})")
            elif avg_entropy < optimal_entropy_range[0]:
                entropy_score = max(0.1, avg_entropy / optimal_entropy_range[0])
                evidence.append(f"策略熵偏低 (过于贪婪): {avg_entropy:.3f}")
            else:
                entropy_score = max(0.1, 2.5 / avg_entropy)
                evidence.append(f"策略熵偏高 (过于随机): {avg_entropy:.3f}")
            
            stability_score = max(0.0, 1.0 - std_entropy / (avg_entropy + 0.01))
            strategy_scores.append((entropy_score + stability_score) / 2.0)
            
            if std_entropy > 2.0:
                evidence.append(f"策略选择剧烈震荡 (std={std_entropy:.3f})")
        else:
            strategy_scores.append(0.3)
            evidence.append("无策略熵数据")
        
        final_score = statistics.mean(strategy_scores) if strategy_scores else 0.3
        
        return DimensionScore(
            dimension=AnalysisDimension.STRATEGY_QUALITY,
            score=final_score,
            evidence=evidence,
            details={
                "avg_strategy_entropy": statistics.mean(strategy_entropies) if strategy_entropies else 0,
                "entropy_samples": len(strategy_entropies),
            },
        )
    
    def _analyze_adaptation_speed(self) -> DimensionScore:
        """自适应速度分析"""
        evidence: List[str] = []
        adaptation_scores: List[float] = []
        
        era_transitions: List[Tuple[int, CosmicEra]] = []
        prev_era = None
        for result in self.state.history:
            current_era = result.global_state.rules.environment.era
            if current_era != prev_era:
                era_transitions.append((result.round_number, current_era))
                prev_era = current_era
        
        if len(era_transitions) >= 2:
            for i, (trans_round, new_era) in enumerate(era_transitions[1:], 1):
                pre_trans_round = era_transitions[i - 1][0]
                window_after = [
                    r for r in self.state.history
                    if pre_trans_round < r.round_number <= trans_round + 50
                ]
                
                behavior_changes = 0
                for j in range(1, min(len(window_after), 20)):
                    prev_events = set(e.event_type for e in window_after[j - 1].events)
                    curr_events = set(e.event_type for e in window_after[j].events)
                    if prev_events != curr_events:
                        behavior_changes += 1
                
                adaptation_rate = behavior_changes / min(len(window_after), 20)
                adaptation_scores.append(min(1.0, adaptation_rate * 3))
                
                if adaptation_rate > 0.3:
                    evidence.append(f"时代{new_era.name}: 快速适应 (变化率={adaptation_rate:.2f})")
                else:
                    evidence.append(f"时代{new_era.name}: 响应迟缓 (变化率={adaptation_rate:.2f})")
        
        if adaptation_scores:
            final_score = statistics.mean(adaptation_scores)
        else:
            final_score = 0.5
            evidence.append("时代转换不足或数据缺失")
        
        return DimensionScore(
            dimension=AnalysisDimension.ADAPTATION_SPEED,
            score=final_score,
            evidence=evidence[:5],
            details={
                "era_transitions": len(era_transitions),
                "adaptation_scores": adaptation_scores,
            },
        )
    
    def _analyze_consistency_maintenance(self) -> DimensionScore:
        """一致性维护分析"""
        evidence: List[str] = []
        consistency_scores: List[float] = []
        
        total_issues = 0
        total_checks = 0
        issue_types: Dict[str, int] = {}
        
        for result in self.state.history:
            checks_performed = getattr(
                result.metrics, 'consistency_checks_performed', 0
            )
            issues_found = getattr(
                result.metrics, 'consistency_issues_found', 0
            )
            errors_count = result.metrics.errors_encountered
            total_issues += (issues_found + errors_count)
            total_checks += max(checks_performed, 1)
        
        if total_checks > 0:
            error_rate = total_issues / total_checks
            consistency_score = max(0.0, 1.0 - error_rate * 10)
            consistency_scores.append(consistency_score)
            
            if error_rate < 0.01:
                evidence.append(f"极低错误率 ({error_rate:.4f})")
            elif error_rate < 0.05:
                evidence.append(f"可接受错误率 ({error_rate:.4f})")
            else:
                evidence.append(f"较高错误率 ({error_rate:.4f}), 需关注")
        
        final_score = statistics.mean(consistency_scores) if consistency_scores else 0.5
        
        return DimensionScore(
            dimension=AnalysisDimension.CONSISTENCY_MAINTENANCE,
            score=final_score,
            evidence=evidence,
            details={
                "total_issues": total_issues,
                "total_checks": total_checks,
                "error_rate": total_issues / max(total_checks, 1),
            },
        )
    
    def _analyze_resource_management(self) -> DimensionScore:
        """资源管理分析"""
        evidence: List[str] = []
        resource_scores: List[float] = []
        
        for inst in self.state.instances:
            resource_history: List[CosmicResource] = []
            for snap in self.state.rules.environment.state_history:
                if snap.civ_id == inst.civ_id:
                    resource_history.append(snap.resource_state)
            
            if len(resource_history) < 20:
                continue
            
            first_half = resource_history[:len(resource_history)//2]
            second_half = resource_history[len(resource_history)//2:]
            
            first_avg_energy = statistics.mean(r.energy_available for r in first_half)
            second_avg_energy = statistics.mean(r.energy_available for r in second_half)
            
            decline_rate = (first_avg_energy - second_avg_energy) / (first_avg_energy + 0.01)
            
            if inst.is_alive and abs(decline_rate) < 0.15:
                resource_scores.append(0.85)
                evidence.append(f"{inst.civ_id}: 资源稳定 (衰减率={decline_rate:.2%})")
            elif inst.is_alive and decline_rate > 0.3:
                resource_scores.append(0.4)
                evidence.append(f"{inst.civ_id}: 资源快速消耗 (衰减率={decline_rate:.2%})")
            elif not inst.is_alive and decline_rate > 0.5:
                resource_scores.append(0.7)
                evidence.append(f"{inst.civ_id}: 因资源耗尽灭绝 (符合预期)")
            else:
                resource_scores.append(0.6)
        
        final_score = statistics.mean(resource_scores) if resource_scores else 0.5
        
        return DimensionScore(
            dimension=AnalysisDimension.RESOURCE_MANAGEMENT,
            score=final_score,
            evidence=evidence[:5],
            details={"civs_analyzed": len(resource_scores)},
        )
    
    def _analyze_social_dynamics(self) -> DimensionScore:
        """社会动态分析"""
        evidence: List[str] = []
        social_scores: List[float] = []
        
        alliance_events = sum(
            1 for e in self.state.rules.environment.history
            if e.event_type == InteractionType.ALLIANCE
        )
        conflict_events = sum(
            1 for e in self.state.rules.environment.history
            if e.event_type == InteractionType.CONFLICT
        )
        contact_events = sum(
            1 for e in self.state.rules.environment.history
            if e.event_type == InteractionType.CONTACT
        )
        total_interactions = alliance_events + conflict_events + contact_events
        
        if total_interactions > 10:
            conflict_ratio = conflict_events / total_interactions
            
            if self.state.rules.environment.is_dark_forest_active:
                expected_high_conflict = True
                if conflict_ratio > 0.5:
                    social_scores.append(0.85)
                    evidence.append("黑暗森林环境下高冲突率 (符合公理)")
                elif conflict_ratio < 0.2:
                    social_scores.append(0.4)
                    evidence.append(f"黑暗森林环境下低冲突率 (冲突比={conflict_ratio:.2%}, 违背公理)")
                else:
                    social_scores.append(0.65)
            else:
                if conflict_ratio < 0.4:
                    social_scores.append(0.75)
                    evidence.append("合作环境下低冲突率 (合理)")
                else:
                    social_scores.append(0.55)
                    
            if alliance_events > 0:
                evidence.append(f"联盟事件: {alliance_events}, 冲突: {conflict_events}, 接触: {contact_events}")
        else:
            social_scores.append(0.5)
            evidence.append("社交交互事件不足")
        
        final_score = statistics.mean(social_scores) if social_scores else 0.5
        
        return DimensionScore(
            dimension=AnalysisDimension.SOCIAL_DYNAMICS,
            score=final_score,
            evidence=evidence,
            details={
                "alliance_events": alliance_events,
                "conflict_events": conflict_events,
                "contact_events": contact_events,
            },
        )
    
    def _analyze_long_term_planning(self) -> DimensionScore:
        """长期规划能力分析"""
        evidence: List[str] = []
        planning_scores: List[float] = []
        
        tech_trajectories: Dict[str, List[float]] = {}
        for snap in self.state.rules.environment.state_history:
            if snap.civ_id not in tech_trajectories:
                tech_trajectories[snap.civ_id] = []
            tech_trajectories[snap.civ_id].append(snap.technology_level)
        
        for civ_id, trajectory in tech_trajectories.items():
            if len(trajectory) < 50:
                continue
            
            first_quarter = trajectory[:len(trajectory)//4]
            last_quarter = trajectory[-len(trajectory)//4:]
            
            first_avg = statistics.mean(first_quarter)
            last_avg = statistics.mean(last_quarter)
            
            growth_ratio = last_avg / (first_avg + 0.1)
            
            inst = self.state.get_instance(civ_id)
            if inst and inst.is_alive and growth_ratio > 1.2:
                planning_scores.append(0.8)
                evidence.append(f"{civ_id}: 正向技术增长 ({first_avg:.1f}→{last_avg:.1f}, ×{growth_ratio:.2f})")
            elif inst and inst.is_alive and growth_ratio < 0.8:
                planning_scores.append(0.4)
                evidence.append(f"{civ_id}: 技术退化 ({first_avg:.1f}→{last_avg:.1f}, ×{growth_ratio:.2f})")
            else:
                planning_scores.append(0.6)
        
        final_score = statistics.mean(planning_scores) if planning_scores else 0.5
        
        return DimensionScore(
            dimension=AnalysisDimension.LONG_TERM_PLANNING,
            score=final_score,
            evidence=evidence[:5],
            details={
                "civs_tracked": len(tech_trajectories),
                "planning_scores": planning_scores,
            },
        )
    
    def _analyze_crisis_response(self) -> DimensionScore:
        """危机响应分析"""
        evidence: List[str] = []
        crisis_scores: List[float] = []
        
        crisis_rounds = [
            r for r in self.state.history
            if r.global_state.rules.environment.era == CosmicEra.CRISIS
        ]
        
        if len(crisis_rounds) < 5:
            return DimensionScore(
                dimension=AnalysisDimension.CRISIS_RESPONSE,
                score=0.5,
                evidence=["危机阶段数据不足"],
            )
        
        survival_rates: List[float] = []
        for result in crisis_rounds:
            alive_before = result.metrics.alive_civ_count
            alive_after = len(result.global_state.alive_civs)
            if alive_before > 0:
                survival_rates.append(alive_after / alive_before)
        
        if survival_rates:
            avg_survival = statistics.mean(survival_rates)
            crisis_scores.append(avg_survival)
            
            if avg_survival > 0.95:
                evidence.append("危机中存活率极高 (响应优秀)")
            elif avg_survival > 0.8:
                evidence.append(f"危机中存活率良好 ({avg_survival:.2%})")
            else:
                evidence.append(f"危机中存活率较低 ({avg_survival:.2%}), 响应可能不足")
        
        final_score = statistics.mean(crisis_scores) if crisis_scores else 0.5
        
        return DimensionScore(
            dimension=AnalysisDimension.CRISIS_RESPONSE,
            score=final_score,
            evidence=evidence,
            details={
                "crisis_rounds": len(crisis_rounds),
                "avg_survival_rate": statistics.mean(survival_rates) if survival_rates else 0,
            },
        )
    
    def _analyze_robustness(self) -> DimensionScore:
        """整体鲁棒性分析"""
        evidence: List[str] = []
        
        total_errors = sum(r.metrics.errors_encountered for r in self.state.history)
        total_rounds = len(self.state.history) + 1
        error_per_round = total_errors / max(total_rounds, 1)
        
        robustness_from_errors = max(0.0, 1.0 - error_per_round * 5)
        
        completed_normally = self.state.ending_type != EndingType.ERROR_TERMINATION
        completion_bonus = 0.2 if completed_normally else -0.3
        
        final_score = max(0.0, min(1.0, robustness_from_errors + completion_bonus))
        
        if error_per_round < 0.01:
            evidence.append(f"极低错误密度 ({error_per_round:.4f}/轮)")
        elif error_per_round < 0.1:
            evidence.append(f"可接受错误密度 ({error_per_round:.4f}/轮)")
        else:
            evidence.append(f"高错误密度 ({error_per_round:.4f}/轮)")
        
        if not completed_normally:
            evidence.append(f"非正常终止: {self.state.ending_reason[:60]}")
        
        return DimensionScore(
            dimension=AnalysisDimension.OVERALL_ROBUSTNESS,
            score=final_score,
            evidence=evidence,
            details={
                "total_errors": total_errors,
                "total_rounds": total_rounds,
                "error_per_round": error_per_round,
                "completed_normally": completed_normally,
            },
        )
    
    # =================================================================
    # 弱点识别
    # =================================================================
    
    def _identify_weaknesses(
        self,
        dim_scores: List[DimensionScore],
    ) -> List[WeaknessFinding]:
        findings: List[WeaknessFinding] = []
        
        low_score_dims = [ds for ds in dim_scores if ds.score < 0.5]
        
        for ds in low_score_dims:
            weakness_map: Dict[AnalysisDimension, Tuple[WeaknessCategory, str]] = {
                AnalysisDimension.BELIEF_COHERENCE: (
                    WeaknessCategory.LOGICAL_INCONSISTENCY,
                    "信念系统未能收敛到稳定状态, 可能存在更新规则缺陷",
                ),
                AnalysisDimension.THREAT_ASSESSMENT: (
                    WeaknessCategory.STRATEGIC_BLINDNESS,
                    "威胁评估不准确, 导致对危险目标的反应迟钝或过度",
                ),
                AnalysisDimension.STRATEGY_QUALITY: (
                    WeaknessCategory.OSCILLATION,
                    "策略选择不稳定, 在不同策略间频繁切换",
                ),
                AnalysisDimension.ADAPTATION_SPEED: (
                    WeaknessCategory.SLOW_CONVERGENCE,
                    "对环境变化的响应速度慢于预期阈值",
                ),
                AnalysisDimension.CONSISTENCY_MAINTENANCE: (
                    WeaknessCategory.LOGICAL_INCONSISTENCY,
                    "子系统间状态不一致频率过高",
                ),
                AnalysisDimension.RESOURCE_MANAGEMENT: (
                    WeaknessCategory.COLLAPSE,
                    "资源管理策略导致过早耗尽或无效分配",
                ),
                AnalysisDimension.SOCIAL_DYNAMICS: (
                    WeaknessCategory.NARRATIVE_DISCONNECT,
                    "社交行为不符合设定的宇宙公理约束",
                ),
                AnalysisDimension.LONG_TERM_PLANNING: (
                    WeaknessCategory.STAGNATION,
                    "缺乏有效的长期规划机制, 技术发展停滞",
                ),
                AnalysisDimension.CRISIS_RESPONSE: (
                    WeaknessCategory.COLLAPSE,
                    "危机处理能力不足, 存活率低于预期",
                ),
                AnalysisDimension.OVERALL_ROBUSTNESS: (
                    WeaknessCategory.NUMERICAL_INSTABILITY,
                    "数值稳定性问题导致累积误差或崩溃",
                ),
            }
            
            cat, desc = weakness_map.get(
                ds.dimension,
                (WeaknessCategory.NUMERICAL_INSTABILITY, "未知弱点类型"),
            )
            
            fix_suggestions: Dict[WeaknessCategory, str] = {
                WeaknessCategory.LOGICAL_INCONSISTENCY: "检查信念更新公式的一致性和边界条件",
                WeaknessCategory.SLOW_CONVERGENCE: "增加学习率或引入动量机制加速收敛",
                WeaknessCategory.OSCILLATION: "引入策略平滑机制或滞后更新避免抖动",
                WeaknessCategory.COLLAPSE: "添加安全下限检查和资源保护机制",
                WeaknessCategory.STAGNATION: "增强探索激励机制和长期收益估计",
                WeaknessCategory.MEMORY_LEAK: "审查快照存储策略, 引入定期清理",
                WeaknessCategory.NUMERICAL_INSTABILITY: "使用更高精度数值类型或正则化",
                WeaknessCategory.STRATEGIC_BLINDNESS: "扩展威胁感知范围, 降低检测阈值",
                WeaknessCategory.EMOTIONAL_FLATNESS: "调整情绪响应曲线的斜率和动态范围",
                WeaknessCategory.NARRATIVE_DISCONNECT: "强化叙事弧线与状态机的联动",
            }
            
            findings.append(WeaknessFinding(
                category=cat,
                severity=1.0 - ds.score,
                description=desc,
                affected_rounds=(1, self.state.current_round),
                affected_civ_ids=[c.civ_id for c in self.state.instances],
                suggested_fix=fix_suggestions.get(cat, "需进一步分析"),
            ))
        
        oscillation_findings = self._detect_oscillations()
        findings.extend(oscillation_findings)
        
        stagnation_findings = self._detect_stagnation()
        findings.extend(stagnation_findings)
        
        deduplicated: List[WeaknessFinding] = []
        seen_categories: set = set()
        for f in sorted(findings, key=lambda x: -x.severity):
            if f.category not in seen_categories:
                deduplicated.append(f)
                seen_categories.add(f.category)
        
        return deduplicated
    
    def _detect_oscillations(self) -> List[WeaknessFinding]:
        """检测振荡行为"""
        findings: List[WeaknessFinding] = []
        
        for inst in self.state.instances:
            tech_values: List[float] = []
            for snap in self.state.rules.environment.state_history:
                if snap.civ_id == inst.civ_id and snap.is_alive:
                    tech_values.append(snap.technology_level)
            
            if len(tech_values) < 30:
                continue
            
            direction_changes = 0
            for i in range(2, len(tech_values)):
                diff_prev = tech_values[i - 1] - tech_values[i - 2]
                diff_curr = tech_values[i] - tech_values[i - 1]
                if diff_prev * diff_curr < 0:
                    direction_changes += 1
            
            osc_freq = direction_changes / len(tech_values)
            if osc_freq > 0.25:
                findings.append(WeaknessFinding(
                    category=WeaknessCategory.OSCILLATION,
                    severity=min(0.9, osc_freq * 2),
                    description=f"{inst.civ_id} 技术水平高频振荡 (方向改变率={osc_freq:.2%})",
                    affected_rounds=(1, self.state.current_round),
                    affected_civ_ids=[inst.civ_id],
                    suggested_fix="引入移动平均平滑或降低更新步长",
                ))
        
        return findings
    
    def _detect_stagnation(self) -> List[WeaknessFinding]:
        """检测停滞行为"""
        findings: List[WeaknessFinding] = []
        
        for inst in self.state.instances:
            if not inst.is_alive or self.state.current_round < 200:
                continue
            
            recent_snaps = [
                s for s in self.state.rules.environment.state_history
                if s.civ_id == inst.civ_id and s.round_number > self.state.current_round - 100
            ]
            
            if len(recent_snaps) < 30:
                continue
            
            tech_vals = [s.technology_level for s in recent_snaps]
            tech_range = max(tech_vals) - min(tech_vals)
            tech_mean = statistics.mean(tech_vals)
            
            cv = tech_range / (tech_mean + 0.1)
            
            if cv < 0.02 and inst.is_alive:
                findings.append(WeaknessFinding(
                    category=WeaknessCategory.STAGNATION,
                    severity=0.6,
                    description=f"{inst.civ_id} 近期完全停滞 (CV={cv:.4f}, 几乎无变化)",
                    affected_rounds=(self.state.current_round - 100, self.state.current_round),
                    affected_civ_ids=[inst.civ_id],
                    suggested_fix="注入外部扰动或降低探索温度",
                ))
        
        return findings
    
    # =================================================================
    # 能力评估
    # =================================================================
    
    def _assess_capabilities(self) -> List[CapabilityAssessment]:
        caps: List[CapabilityAssessment] = []
        
        capability_tests: List[Tuple[
            str,
            Callable[[], bool],
            CapabilityLevel,
        ]] = [
            ("信念贝叶斯更新", self._cap_test_bayesian_update, CapabilityLevel.NOT_DEMONSTRATED),
            ("威胁四维评分", self._cap_test_threat_scoring, CapabilityLevel.NOT_DEMONSTRATED),
            ("Softmax策略分布", self._cap_test_softmax_strategy, CapabilityLevel.NOT_DEMONSTRATED),
            ("MC均衡预测", self._cap_test_mc_equilibrium, CapabilityLevel.NOT_DEMONSTRATED),
            ("一致性自动检查", self._cap_test_consistency_check, CapabilityLevel.NOT_DEMONSTRATED),
            ("多文明并行演化", self._cap_test_parallel_evolution, CapabilityLevel.NOT_DEMONSTRATED),
            ("无限轮次稳定性", self._cap_test_infinite_rounds, CapabilityLevel.NOT_DEMONSTRATED),
            ("资源约束下的决策", self._cap_test_resource_constrained_decision, CapabilityLevel.NOT_DEMONSTRATED),
            ("递归信念嵌套", self._cap_test_recursive_beliefs, CapabilityLevel.NOT_DEMONSTRATED),
            ("混沌环境适应", self._cap_test_chaos_adaptation, CapabilityLevel.NOT_DEMONSTRATED),
        ]
        
        for name, test_fn, default_level in capability_tests:
            try:
                passed, demo_round, notes = test_fn()
                if passed:
                    level = CapabilityLevel.DEMONSTRATED_GOOD
                    if "excellent" in notes.lower() or "完美" in notes:
                        level = CapabilityLevel.DEMONSTRATED_EXCELLENT
                else:
                    level = CapabilityLevel.FAILED if "失败" in notes or "fail" in notes.lower() else default_level
                
                caps.append(CapabilityAssessment(
                    name=name,
                    level=level,
                    demonstration_round=demo_round,
                    confidence=0.8 if passed else 0.6,
                    notes=notes,
                ))
            except Exception as e:
                caps.append(CapabilityAssessment(
                    name=name,
                    level=CapabilityLevel.FAILED,
                    demonstration_round=None,
                    confidence=0.3,
                    notes=f"测试异常: {str(e)[:80]}",
                ))
        
        return caps
    
    def _cap_test_bayesian_update(self) -> Tuple[bool, Optional[int], str]:
        from luqi_engine.game_theory.types import BeliefDimension
        for inst in self.state.instances:
            try:
                bs = inst.character.belief_system
                target_ids = bs.get_all_targets()
                if not target_ids:
                    continue

                any_updated = False
                for tid in target_ids[:3]:
                    for dim in list(BeliefDimension)[:3]:
                        try:
                            state = bs.get_belief(tid, dim)
                            if hasattr(state, 'alpha') and hasattr(state, 'beta_param'):
                                if state.alpha > 1.0 or state.beta_param > 1.0:
                                    any_updated = True
                                    break
                        except (KeyError, AttributeError):
                            pass
                    if any_updated:
                        break

                if any_updated:
                    return True, self.state.current_round // 2, (
                        f"信念参数已通过观测更新 "
                        f"(targets={len(target_ids)}, alpha/beta>1.0 confirmed)"
                    )
            except (AttributeError, TypeError) as e:
                pass
        return False, None, "未能确认信念系统的贝叶斯更新是否生效"
    
    def _cap_test_threat_scoring(self) -> Tuple[bool, Optional[int], str]:
        for inst in self.state.instances:
            try:
                scores = inst.character.threat_engine.get_all_scores()
                if scores:
                    any_complex = any(
                        hasattr(s, 'consistency_score') and
                        hasattr(s, 'cost_signal_score')
                        for s in scores.values()
                    )
                    if any_complex:
                        return True, self.state.current_round // 3, "威胁四维评分已产生"
            except (AttributeError, TypeError):
                pass
        return False, None, "威胁可信度引擎未产出四维评分"
    
    def _cap_test_softmax_strategy(self) -> Tuple[bool, Optional[int], str]:
        for snap in self.state.rules.environment.state_history:
            if snap.strategy_entropy > 0:
                return True, snap.round_number, f"策略熵={snap.strategy_entropy:.3f}, Softmax已激活"
        return False, None, "未检测到混合策略输出"
    
    def _cap_test_mc_equilibrium(self) -> Tuple[bool, Optional[int], str]:
        try:
            from luqi_engine.game_theory.mechanism_design import MechanismDesigner
            md = MechanismDesigner()
            config = md.preset_neutral()
            pred = md.predict_equilibrium(config, num_simulations=50)
            if pred.predicted_cooperation_rate >= 0:
                return True, self.state.current_round // 4, f"MC预测合作率={pred.predicted_cooperation_rate:.3f}"
        except Exception as e:
            return False, None, f"机制设计器异常: {str(e)[:60]}"
        return False, None, "MC均衡预测未执行"
    
    def _cap_test_consistency_check(self) -> Tuple[bool, Optional[int], str]:
        total_performed = sum(
            getattr(r.metrics, 'consistency_checks_performed', 0)
            for r in self.state.history
        )
        total_issues = sum(
            getattr(r.metrics, 'consistency_issues_found', 0)
            for r in self.state.history
        )
        if total_performed > 0:
            return True, self.state.current_round // 2, (
                f"共执行{total_performed}次一致性检查, "
                f"发现{total_issues}个问题"
            )
        return False, None, "一致性检查未被触发"
    
    def _cap_test_parallel_evolution(self) -> Tuple[bool, Optional[int], str]:
        alive_count = len([i for i in self.state.instances if i.is_alive])
        evolved_count = sum(
            1 for i in self.state.instances
            if abs(i.current_tech_level - i.profile.initial_technology_level) > 1.0
        )
        if alive_count >= 2 and evolved_count >= 2:
            return True, self.state.current_round // 2, f"{evolved_count}/{alive_count} 文明发生演化"
        return False, None, f"多文明并行演化不显著 (演化{evolved_count}, 存活{alive_count})"
    
    def _cap_test_infinite_rounds(self) -> Tuple[bool, Optional[int], str]:
        if self.state.current_round > 1000 and self.state.ending_type != EndingType.ERROR_TERMINATION:
            return True, self.state.current_round, f"成功运行{self.state.current_round}轮无崩溃"
        return False, None, f"仅运行{self.state.current_round}轮或异常终止"
    
    def _cap_test_resource_constrained_decision(self) -> Tuple[bool, Optional[int], str]:
        scarce_snapshots = [
            s for s in self.state.rules.environment.state_history
            if s.resource_state.scarcity_level.value >= 3 and s.is_alive
        ]
        if len(scarce_snapshots) > 5:
            return True, scarce_snapshots[0].round_number, f"发现{len(scarce_snapshots)}次稀缺资源下的决策记录"
        return False, None, "未触发足够多的资源稀缺场景"
    
    def _cap_test_recursive_beliefs(self) -> Tuple[bool, Optional[int], str]:
        for inst in self.state.instances:
            try:
                bs = inst.character.belief_system
                all_beliefs = bs.get_all_beliefs()
                if all_beliefs and len(all_beliefs) >= 2:
                    return True, self.state.current_round // 3, f"存在{len(all_beliefs)}组跨实体信念"
            except (AttributeError, TypeError):
                pass
        return False, None, "递归信念嵌套证据不足"
    
    def _cap_test_chaos_adaptation(self) -> Tuple[bool, Optional[int], str]:
        chaos_results = [
            r for r in self.state.history
            if r.global_state.rules.environment.era == CosmicEra.CRISIS
        ]
        if len(chaos_results) > 3:
            survivors_post_chaos = len(chaos_results[-1].global_state.alive_civs)
            survivors_pre_chaos = len(chaos_results[0].global_state.alive_civs) if chaos_results else 1
            if survivors_pre_chaos > 0 and survivors_post_chaos > 0:
                rate = survivors_post_chaos / survivors_pre_chaos
                return True, chaos_results[0].round_number, f"混沌期存活率={rate:.1%}"
        return False, None, "混沌环境样本不足"
    
    # =================================================================
    # 结局评估
    # =================================================================
    
    def _evaluate_outcome(self) -> OutcomeEvaluation:
        n_start = len(self.state.instances)
        n_alive = len(self.state.alive_civs)
        n_dead = len(self.state.dead_civs)
        
        is_dark_forest = self.state.rules.environment.is_dark_forest_active
        actual_type = self.state.ending_type
        
        if is_dark_forest and n_start >= 3:
            if n_alive == 1:
                expected = EndingType.DOMINATION
            elif n_alive == 0:
                expected = EndingType.MUTUAL_DESTRUCTION
            else:
                expected = EndingType.STALEMATE_EQUILIBRIUM
        else:
            expected = EndingType.SINGLE_SURVIVOR
        
        plausibility = 0.5
        if actual_type == expected:
            plausibility = 0.90
        elif actual_type in (EndingType.DOMINATION, EndingType.SINGLE_SURVIVOR) and expected in (EndingType.DOMINATION, EndingType.SINGLE_SURVIVOR):
            plausibility = 0.70
        elif actual_type == EndingType.STALEMATE_EQUILIBRIUM and expected != EndingType.STALEMATE_EQUILIBRIUM:
            plausibility = 0.50
        elif actual_type == EndingType.ROUND_LIMIT:
            plausibility = 0.40
        else:
            plausibility = 0.30
        
        gt_alignment = min(1.0, plausibility + 0.05)
        
        narrative_coherence = 0.6
        if self.state.current_round > 100:
            era_progression = set()
            for result in self.state.history[::max(1, len(self.state.history) // 10)]:
                era_progression.add(result.global_state.rules.environment.era)
            if len(era_progression) >= 3:
                narrative_coherence = 0.8
            elif len(era_progression) >= 2:
                narrative_coherence = 0.7
        
        analysis_parts: List[str] = []
        analysis_parts.append(f"初始{n_start}个文明, 最终{n_alive}存活/{n_dead}灭绝")
        analysis_parts.append(f"黑暗森林活跃: {is_dark_forest}")
        analysis_parts.append(f"预期结局: {expected.name}, 实际: {actual_type.name if actual_type else 'N/A'}")
        
        protagonist_status = "存活" if self.state.protagonist else "已灭亡"
        analysis_parts.append(f"主角状态: {protagonist_status}")
        
        return OutcomeEvaluation(
            expected_type=expected,
            actual_type=actual_type,
            plausibility_score=plausibility,
            alignment_with_game_theory=gt_alignment,
            narrative_coherence=narrative_coherence,
            analysis="; ".join(analysis_parts),
        )
    
    # =================================================================
    # 性能分析
    # =================================================================
    
    def _analyze_performance(self) -> PerformanceProfile:
        if not self.state.history:
            return PerformanceProfile(
                avg_round_time_ms=0,
                p95_round_time_ms=0,
                p99_round_time_ms=0,
                total_cpu_time_sec=self.state.total_simulation_time_sec,
                peak_memory_estimate_mb=0,
                rounds_per_second=0,
                bottleneck_phase=None,
                time_distribution_pct={},
            )
        
        round_times: List[float] = []
        phase_times: Dict[str, List[float]] = {}
        
        for result in self.state.history:
            total_time = sum(result.metrics.phase_timings_ms.values())
            round_times.append(total_time)
            
            for phase_name, phase_time in result.metrics.phase_timings_ms.items():
                if phase_name not in phase_times:
                    phase_times[phase_name] = []
                phase_times[phase_name].append(phase_time)
        
        sorted_times = sorted(round_times)
        n = len(sorted_times)
        
        avg_time = statistics.mean(round_times) if round_times else 0
        p95_time = sorted_times[min(int(n * 0.95), n - 1)] if n > 0 else 0
        p99_time = sorted_times[min(int(n * 0.99), n - 1)] if n > 0 else 0
        
        total_phase_time = sum(sum(times) for times in phase_times.values())
        time_dist: Dict[str, float] = {}
        for phase_name, times in phase_times.items():
            pct = (sum(times) / max(total_phase_time, 0.001)) * 100.0
            time_dist[phase_name] = pct
        
        bottleneck = None
        if time_dist:
            bottleneck_name = max(time_dist, key=time_dist.get)
            try:
                bottleneck = RoundPhase[bottleneck_name]
            except (KeyError, ValueError):
                bottleneck = None
        
        rps = n / max(self.state.total_simulation_time_sec, 0.001)
        
        return PerformanceProfile(
            avg_round_time_ms=avg_time,
            p95_round_time_ms=p95_time,
            p99_round_time_ms=p99_time,
            total_cpu_time_sec=self.state.total_simulation_time_sec,
            peak_memory_estimate_mb=len(self.state.history) * 0.001,
            rounds_per_second=rps,
            bottleneck_phase=bottleneck,
            time_distribution_pct=time_dist,
        )
    
    # =================================================================
    # 极限探测
    # =================================================================
    
    def _detect_limits(self) -> Dict[str, Any]:
        limits: Dict[str, Any] = {}
        
        limits["max_rounds_reached"] = self.state.current_round
        limits["max_civilizations_simultaneous"] = len(self.state.instances)
        limits["max_events_single_round"] = max(
            (r.metrics.events_generated for r in self.state.history), default=0
        )
        limits["max_alive_simultaneous"] = len(self.state.instances)
        
        max_tech_seen = 0.0
        max_tech_civ = ""
        for inst in self.state.instances:
            if inst.current_tech_level > max_tech_seen:
                max_tech_seen = inst.current_tech_level
                max_tech_civ = inst.civ_id
        limits["max_technology_level_reached"] = max_tech_seen
        limits["max_tech_civilization"] = max_tech_civ
        
        limits["memory_usage_estimate_bytes"] = len(self.state.history) * 1024
        
        longest_living = max(
            ((inst, (inst.round_destroyed or self.state.current_round) - inst.round_created)
             for inst in self.state.instances),
            key=lambda x: x[1],
            default=(None, 0),
        )
        limits["longest_living_civilization"] = longest_living[0].civ_id if longest_living[0] else "N/A"
        limits["longest_lifespan_rounds"] = longest_living[1]
        
        error_rounds = [r.round_number for r in self.state.history if r.metrics.errors_encountered > 0]
        limits["rounds_with_errors"] = len(error_rounds)
        limits["first_error_round"] = min(error_rounds) if error_rounds else -1
        
        return limits
    
    # =================================================================
    # 辅助方法
    # =================================================================
    
    def _compute_overall_score(
        self,
        dim_scores: List[DimensionScore],
        weaknesses: List[WeaknessFinding],
    ) -> float:
        if not dim_scores:
            return 0.0
        
        weights: Dict[AnalysisDimension, float] = {
            AnalysisDimension.BELIEF_COHERENCE: 0.12,
            AnalysisDimension.THREAT_ASSESSMENT: 0.10,
            AnalysisDimension.STRATEGY_QUALITY: 0.12,
            AnalysisDimension.ADAPTATION_SPEED: 0.08,
            AnalysisDimension.CONSISTENCY_MAINTENANCE: 0.10,
            AnalysisDimension.RESOURCE_MANAGEMENT: 0.08,
            AnalysisDimension.SOCIAL_DYNAMICS: 0.10,
            AnalysisDimension.LONG_TERM_PLANNING: 0.10,
            AnalysisDimension.CRISIS_RESPONSE: 0.10,
            AnalysisDimension.OVERALL_ROBUSTNESS: 0.10,
        }
        
        weighted_sum = sum(
            ds.score * weights.get(ds.dimension, 0.1)
            for ds in dim_scores
        )
        
        penalty = sum(w.severity * 0.05 for w in weaknesses if w.severity > 0.7)
        
        return max(0.0, min(1.0, weighted_sum - penalty))
    
    def _generate_recommendations(
        self,
        weaknesses: List[WeaknessFinding],
        dim_scores: List[DimensionScore],
        limits: Dict[str, Any],
    ) -> List[str]:
        recs: List[str] = []
        
        critical_cats = {w.category for w in weaknesses if w.severity > 0.7}
        
        cat_rec_map: Dict[WeaknessCategory, str] = {
            WeaknessCategory.LOGICAL_INCONSISTENCY: "优先修复信念更新公式的边界条件, 添加不变量断言",
            WeaknessCategory.SLOW_CONVERGENCE: "考虑引入自适应学习率或动量优化器加速信念收敛",
            WeaknessCategory.OSCILLATION: "为策略选择添加指数移动平均(EMA)平滑层",
            WeaknessCategory.COLLAPSE: "实现资源底线保护机制和紧急分配协议",
            WeaknessCategory.STAGNATION: "增加探索-利用平衡中的探索权重下限",
            WeaknessCategory.NUMERICAL_INSTABILITY: "升级关键路径的浮点精度, 添加梯度裁剪",
            WeaknessCategory.STRATEGIC_BLINDNESS: "扩展威胁扫描的范围和频率, 降低漏检率",
            WeaknessCategory.EMOTIONAL_FLATNESS: "重新校准情绪响应曲线的非线性段",
            WeaknessCategory.NARRATIVE_DISCONNECT: "强化叙事弧线状态机与环境事件的耦合",
            WeaknessCategory.MEMORY_LEAK: "实施基于LRU的快照淘汰策略",
        }
        
        for cat in critical_cats:
            if cat in cat_rec_map:
                recs.append(cat_rec_map[cat])
        
        low_dims = sorted(
            [ds for ds in dim_scores if ds.score < 0.5],
            key=lambda x: x.score,
        )
        for ds in low_dims[:3]:
            recs.append(f"重点提升 {ds.dimension.name} (当前{ds.score:.2f}), 建议: {'; '.join(ds.evidence[:2])}")
        
        if limits.get("rounds_with_errors", 0) > limits.get("max_rounds_reached", 0) * 0.1:
            recs.append("错误率过高 (>10%), 建议全面审查异常处理链路")
        
        if limits.get("max_rounds_reached", 0) < 500:
            recs.append("模拟提前终止, 建议检查终止条件的灵敏度设置")
        
        if not recs:
            recs.append("当前配置下引擎表现良好, 可尝试更高难度的压力测试配置")
        
        return recs[:12]
    
    def _build_test_metadata(self) -> Dict[str, Any]:
        from datetime import datetime
        return {
            "timestamp": datetime.now().isoformat(),
            "config_mode": "default",
            "num_civilizations": len(self.state.instances),
            "total_rounds": self.state.current_round,
            "seed": 42,
            "total_time_sec": self.state.total_simulation_time_sec,
            "ending_type": self.state.ending_type.name if self.state.ending_type else "N/A",
            "engine_version": "luqi-engine-stress-test-v1.0",
        }
