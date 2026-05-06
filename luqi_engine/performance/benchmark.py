"""
Phase 4 博弈论子系统性能基准测试
覆盖: 信念系统/威胁可信度/混合策略/机制设计/集成开销/渲染性能
输出: 各模块耗时(ms)/吞吐量(ops/s)/内存占用估算
"""

from __future__ import annotations

import math
import statistics
import time
import tracemalloc
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from luqi_engine.game_theory.belief_system import (
    BeliefDimension,
    BeliefState,
    BeliefSystem,
    Observation,
)
from luqi_engine.game_theory.mechanism_design import (
    EquilibriumPrediction,
    MechanismConfig,
    MechanismDesigner,
    MechanismParameter,
)
from luqi_engine.game_theory.mixed_strategy import (
    MixedStrategyEngine,
    MixedStrategyProfile,
    StrategyAction,
    StrategyPayoff,
)
from luqi_engine.game_theory.threat_credibility import (
    CommitmentLevel,
    ThreatCredibilityEngine,
    ThreatRecord,
    ThreatType,
)
from luqi_engine.game_theory.types import CredibilityScore

from luqi_engine.character.deep_character import DeepCharacter
from luqi_engine.llm.state_renderer import StateRenderer, TokenBudgetProfile


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    ops_per_sec: float
    memory_peak_kb: Optional[float] = None


def _run_benchmark(
    name: str,
    fn: Callable[[], Any],
    iterations: int = 100,
    warmup: int = 5,
) -> BenchmarkResult:
    times: List[float] = []
    
    for _ in range(warmup):
        fn()
    
    tracemalloc.start()
    
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        elapsed = (time.perf_counter() - start) * 1000.0
        times.append(elapsed)
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    sorted_times = sorted(times)
    n = len(sorted_times)
    total = sum(times)
    mean = total / n
    median = sorted_times[n // 2]
    p95_idx = min(int(n * 0.95), n - 1)
    p99_idx = min(int(n * 0.99), n - 1)
    
    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_ms=total,
        mean_ms=mean,
        median_ms=median,
        p95_ms=sorted_times[p95_idx],
        p99_ms=sorted_times[p99_idx],
        ops_per_sec=(iterations / total * 1000.0) if total > 0 else float("inf"),
        memory_peak_kb=peak / 1024.0,
    )


def _format_result(r: BenchmarkResult) -> str:
    mem_str = f"{r.memory_peak_kb:.1f}KB" if r.memory_peak_kb else "N/A"
    return (
        f"  {r.name:<45s} "
        f"mean={r.mean_ms:>7.2f}ms "
        f"p95={r.p95_ms:>7.2f}ms "
        f"p99={r.p99_ms:>7.2f}ms "
        f"ops/s={r.ops_per_sec:>8.0f} "
        f"mem={mem_str}"
    )


class BeliefSystemBenchmark:
    """信念系统性能基准"""
    
    def __init__(self) -> None:
        self.bs = BeliefSystem(character_id="bench_char")
    
    def bench_observe_single(self) -> BenchmarkResult:
        counter = [0]
        
        def _run() -> None:
            self.bs.observe(
                target_id=f"target_{counter[0] % 50}",
                dimension=BeliefDimension.COOPERATIVITY,
                observation=Observation(evidence_value=0.8),
            )
            counter[0] += 1
        
        return _run_benchmark("belief_observe_single", _run, iterations=200)
    
    def bench_get_belief(self) -> BenchmarkResult:
        for i in range(20):
            self.bs.observe(
                target_id="bench_target",
                dimension=BeliefDimension.HONESTY,
                observation=Observation(evidence_value=0.6 + i * 0.02),
            )
        
        def _run() -> None:
            self.bs.get_belief("bench_target", BeliefDimension.HONESTY)
        
        return _run_benchmark("belief_get_belief", _run, iterations=500)
    
    def bench_apply_decay(self) -> BenchmarkResult:
        for i in range(10):
            self.bs.observe(
                target_id="decay_target",
                dimension=BeliefDimension.THREAT_LEVEL,
                observation=Observation(evidence_value=0.9 - i * 0.05),
            )
        
        def _run() -> None:
            belief = self.bs.get_belief("decay_target", BeliefDimension.THREAT_LEVEL)
            belief.apply_decay(days_elapsed=30.0)
        
        return _run_benchmark("belief_apply_decay", _run, iterations=200)
    
    def bench_batch_observe_100(self) -> BenchmarkResult:
        def _run() -> None:
            for i in range(100):
                dim = list(BeliefDimension)[i % len(BeliefDimension)]
                self.bs.observe(
                    target_id=f"batch_{i % 10}",
                    dimension=dim,
                    observation=Observation(evidence_value=0.5 + (i % 10) * 0.05),
                )
        
        return _run_benchmark("belief_batch_observe_100", _run, iterations=50)


class ThreatCredibilityBenchmark:
    """威胁可信度引擎性能基准"""
    
    def __init__(self) -> None:
        self.engine = ThreatCredibilityEngine(character_id="bench_tc")
    
    def bench_record_threat(self) -> BenchmarkResult:
        counter = [0]
        
        def _run() -> None:
            tr = ThreatRecord(
                content=f"威胁声明 #{counter[0]}",
                threat_type=list(ThreatType)[counter[0] % len(ThreatType)],
                commitment_level=list(CommitmentLevel)[counter[0] % len(CommitmentLevel)],
                estimated_cost=0.3 + (counter[0] % 7) * 0.1,
            )
            self.engine.record_threat(tr)
            counter[0] += 1
        
        return _run_benchmark("threat_record", _run, iterations=200)
    
    def bench_evaluate_plausibility(self) -> BenchmarkResult:
        counter = [0]
        
        def _run() -> None:
            self.engine.evaluate_threat_plausibility(
                target_id=f"entity_{counter[0] % 20}",
                threatened_action="报复行为",
                estimated_cost=0.2 + (counter[0] % 9) * 0.08,
                commitment_level=list(CommitmentLevel)[counter[0] % len(CommitmentLevel)],
            )
            counter[0] += 1
        
        return _run_benchmark("threat_eval_plausibility", _run, iterations=300)
    
    def bench_get_credibility_with_records(self) -> BenchmarkResult:
        for i in range(30):
            tr = ThreatRecord(
                content=f"cred_test_{i}",
                commitment_level=CommitmentLevel.IRREVERSIBLE if i % 3 == 0 else CommitmentLevel.VERBAL,
                estimated_cost=0.1 + (i % 10) * 0.08,
            )
            self.engine.record_threat(tr)
        
        scores = self.engine.get_all_scores()
        if not scores:
            return BenchmarkResult("threat_get_credibility", 0, 0, 0, 0, 0, 0, 0)
        
        entity_id = list(scores.keys())[0]
        
        def _run() -> None:
            self.engine.get_credibility(entity_id)
        
        return _run_benchmark("threat_get_credibility", _run, iterations=300)


class MixedStrategyBenchmark:
    """混合策略引擎性能基准"""
    
    def __init__(self) -> None:
        self.engine = MixedStrategyEngine()
    
    def _make_payoffs(self, n: int = 4) -> List[StrategyPayoff]:
        actions = list(StrategyAction)[:n]
        payoffs: List[StrategyPayoff] = []
        for idx, action in enumerate(actions):
            coop_payoff = 5.0 + idx * 2.0
            defect_payoff = -3.0 + idx * 0.5
            payoffs.append(StrategyPayoff(
                action=action,
                payoff_if_cooperate=coop_payoff,
                payoff_if_defect=defect_payoff,
            ))
        return payoffs
    
    def bench_generate_4_actions(self) -> BenchmarkResult:
        payoffs = self._make_payoffs(4)
        
        def _run() -> None:
            self.engine.generate(payoffs, temperature=1.0)
        
        return _run_benchmark("mixed_generate_4actions", _run, iterations=500)
    
    def bench_generate_low_temp(self) -> BenchmarkResult:
        payoffs = self._make_payoffs(4)
        
        def _run() -> None:
            self.engine.generate(payoffs, temperature=0.01)
        
        return _run_benchmark("mixed_generate_lowtemp", _run, iterations=500)
    
    def bench_nash_equilibrium(self) -> BenchmarkResult:
        payoffs = self._make_payoffs(4)
        
        def _run() -> None:
            profile = self.engine.generate(payoffs, temperature=0.001)
            _ = profile.dominant_action
            _ = profile.entropy
        
        return _run_benchmark("mixed_nash_equilibrium", _run, iterations=500)


class MechanismDesignBenchmark:
    """机制设计引擎性能基准"""
    
    def __init__(self) -> None:
        self.designer = MechanismDesigner()
    
    def bench_predict_baseline(self) -> BenchmarkResult:
        config = MechanismConfig(name="baseline")
        
        def _run() -> None:
            self.designer.predict_equilibrium(config, num_simulations=100)
        
        return _run_benchmark("mechanism_predict_100sim", _run, iterations=30)
    
    def bench_predict_heavy(self) -> BenchmarkResult:
        config = MechanismConfig(name="heavy")
        config.set(MechanismParameter.REWARD_COOPERATION_BONUS, 1.5)
        config.set(MechanismParameter.PUNISHMENT_DEFECT_COST, 2.0)
        
        def _run() -> None:
            self.designer.predict_equilibrium(config, num_simulations=500)
        
        return _run_benchmark("mechanism_predict_500sim", _run, iterations=15)
    
    def bench_incentive_check(self) -> BenchmarkResult:
        config = MechanismConfig(name="compat_check")
        
        def _run() -> None:
            self.designer.check_incentive_compatibility(
                config=config,
                target_behavior_description="cooperate",
                deviation_actions=["defect", "withdraw"],
            )
        
        return _run_benchmark("mechanism_incentive_check", _run, iterations=100)


class IntegrationBenchmark:
    """DeepCharacter 集成开销基准"""
    
    def __init__(self) -> None:
        pass
    
    def bench_lazy_init_all_subsystems(self) -> BenchmarkResult:
        def _run() -> None:
            dc = DeepCharacter(character_id=f"integ_{id(_run) % 10000}")
            _ = dc.belief_system
            _ = dc.threat_engine
            _ = dc.strategy_engine
        
        return _run_benchmark("integration_lazy_init_all", _run, iterations=50)
    
    def bench_event_dispatch_dialogue(self) -> BenchmarkResult:
        dc = DeepCharacter(character_id="event_bench")
        _ = dc.belief_system
        counter = [0]
        
        def _run() -> None:
            dc.on_event(
                event_type="dialogue_input",
                intensity=0.6 + (counter[0] % 5) * 0.08,
                metadata={
                    "content": "测试对话内容用于基准测试",
                    "speaker_id": f"speaker_{counter[0] % 10}",
                    "action_type": "DIALOGUE",
                },
            )
            counter[0] += 1
        
        return _run_benchmark("integration_event_dialogue", _run, iterations=100)
    
    def bench_state_snapshot_p4(self) -> BenchmarkResult:
        dc = DeepCharacter(character_id="snapshot_bench")
        _ = dc.belief_system
        _ = dc.strategy_engine
        dc.on_event(event_type="social_action", intensity=0.7,
                     metadata={"action_type": "THREATEN", "content": "测试"})
        
        def _run() -> None:
            _ = dc.get_state_snapshot()
        
        return _run_benchmark("integration_state_snapshot", _run, iterations=200)
    
    def bench_consistency_rules(self) -> BenchmarkResult:
        dc = DeepCharacter(character_id="rules_bench")
        _ = dc.belief_system
        _ = dc.strategy_engine
        
        def _run() -> None:
            _ = dc.check_consistency()
        
        return _run_benchmark("integration_consistency_rules", _run, iterations=200)


class RendererBenchmark:
    """StateRenderer v3 渲染性能基准"""
    
    def __init__(self) -> None:
        self.renderer = StateRenderer()
        self.dc = DeepCharacter(character_id="render_bench")
        _ = self.dc.belief_system
        _ = self.dc.strategy_engine
        self.dc.on_event(event_type="dialogue_input", intensity=0.8,
                          metadata={"speaker_id": "npc_1", "action_type": "DIALOGUE",
                                    "content": "渲染基准测试对话"})
    
    def bench_render_deep_state_v3(self) -> BenchmarkResult:
        snapshot = self.dc.get_state_snapshot()
        
        def _run() -> None:
            self.renderer.render_deep_state(snapshot, max_tokens=2000)
        
        return _run_benchmark("renderer_render_balanced", _run, iterations=100)
    
    def bench_render_compact(self) -> BenchmarkResult:
        snapshot = self.dc.get_state_snapshot()
        
        def _run() -> None:
            self.renderer.render_deep_state(snapshot, max_tokens=800)
        
        return _run_benchmark("renderer_render_compact", _run, iterations=100)


def run_all_benchmarks() -> Dict[str, List[BenchmarkResult]]:
    results: Dict[str, List[BenchmarkResult]] = {}
    
    print("=" * 90)
    print("Phase 4 Game Theory Subsystem Performance Benchmarks")
    print("=" * 90)
    
    print("\n--- Belief System ---")
    bs_bench = BeliefSystemBenchmark()
    results["belief"] = [
        bs_bench.bench_observe_single(),
        bs_bench.bench_get_belief(),
        bs_bench.bench_apply_decay(),
        bs_bench.bench_batch_observe_100(),
    ]
    for r in results["belief"]:
        print(_format_result(r))
    
    print("\n--- Threat Credibility Engine ---")
    tc_bench = ThreatCredibilityBenchmark()
    results["threat"] = [
        tc_bench.bench_record_threat(),
        tc_bench.bench_evaluate_plausibility(),
        tc_bench.bench_get_credibility_with_records(),
    ]
    for r in results["threat"]:
        print(_format_result(r))
    
    print("\n--- Mixed Strategy Engine ---")
    ms_bench = MixedStrategyBenchmark()
    results["mixed"] = [
        ms_bench.bench_generate_4_actions(),
        ms_bench.bench_generate_low_temp(),
        ms_bench.bench_nash_equilibrium(),
    ]
    for r in results["mixed"]:
        print(_format_result(r))
    
    print("\n--- Mechanism Design Engine ---")
    md_bench = MechanismDesignBenchmark()
    results["mechanism"] = [
        md_bench.bench_predict_baseline(),
        md_bench.bench_predict_heavy(),
        md_bench.bench_incentive_check(),
    ]
    for r in results["mechanism"]:
        print(_format_result(r))
    
    print("\n--- Integration Overhead ---")
    int_bench = IntegrationBenchmark()
    results["integration"] = [
        int_bench.bench_lazy_init_all_subsystems(),
        int_bench.bench_event_dispatch_dialogue(),
        int_bench.bench_state_snapshot_p4(),
        int_bench.bench_consistency_rules(),
    ]
    for r in results["integration"]:
        print(_format_result(r))
    
    print("\n--- StateRenderer V3 ---")
    rend_bench = RendererBenchmark()
    results["renderer"] = [
        rend_bench.bench_render_deep_state_v3(),
        rend_bench.bench_render_compact(),
    ]
    for r in results["renderer"]:
        print(_format_result(r))
    
    return results


def print_summary(results: Dict[str, List[BenchmarkResult]]) -> None:
    all_results: List[BenchmarkResult] = []
    for group_results in results.values():
        all_results.extend(group_results)
    
    if not all_results:
        return
    
    print("\n" + "=" * 90)
    print("Summary Statistics")
    print("=" * 90)
    
    slowest = max(all_results, key=lambda r: r.mean_ms)
    fastest = min(all_results, key=lambda r: r.mean_ms if r.mean_ms > 0 else float("inf"))
    
    means = [r.mean_ms for r in all_results if r.mean_ms > 0]
    if means:
        avg_mean = statistics.mean(means)
        print(f"\n  Average latency across all benchmarks: {avg_mean:.3f}ms")
    
    print(f"\n  Slowest operation: {slowest.name} ({slowest.mean_ms:.2f}ms mean)")
    print(f"  Fastest operation: {fastest.name} ({fastest.mean_ms:.2f}ms mean)")
    
    mem_results = [r for r in all_results if r.memory_peak_kb is not None]
    if mem_results:
        max_mem = max(mem_results, key=lambda r: r.memory_peak_kb or 0)
        print(f"  Peak memory: {max_mem.name} ({max_mem.memory_peak_kb:.1f}KB)")
    
    ops_results = [r for r in all_results if r.ops_per_sec != float("inf")]
    if ops_results:
        min_ops = min(ops_results, key=lambda r: r.ops_per_sec)
        print(f"  Lowest throughput: {min_ops.name} ({min_ops.ops_per_sec:.0f} ops/s)")
    
    print("\n  Performance Tier Classification:")
    for r in sorted(all_results, key=lambda x: x.mean_ms):
        if r.mean_ms < 0.5:
            tier = "EXCELLENT (<0.5ms)"
        elif r.mean_ms < 2.0:
            tier = "GOOD (<2ms)"
        elif r.mean_ms < 10.0:
            tier = "ACCEPTABLE (<10ms)"
        elif r.mean_ms < 50.0:
            tier = "SLOW (<50ms) - review recommended"
        else:
            tier = "CRITICAL (>50ms) - optimization required"
        print(f"    {r.name:<45s} {tier}")


if __name__ == "__main__":
    results = run_all_benchmarks()
    print_summary(results)
