"""
Phase 2 性能基准测试 — MemorySystem & MaslowEngine (修正版)

基于实际 API 接口:
- MemorySystem.store() / retrieve() / decay() / get_statistics()
- MaslowEngine.get_prioritized_motives() / detect_conflicts() / generate_report()
"""

import time
import statistics
from typing import List, Dict, Any, Tuple, Optional
from luqi_engine.memory.memory_system import (
    MemorySystem, MemoryType, MemoryEmotion,
)
from luqi_engine.motivation.maslow_engine import (
    MotivationEngine, NeedLevel, ContextType, ConflictStrategy,
)


class PerformanceBenchmark:
    """性能基准测试工具类"""

    def __init__(self, warmup_runs: int = 3, measure_runs: int = 10):
        self.warmup_runs = warmup_runs
        self.measure_runs = measure_runs
        self.results: Dict[str, Dict[str, float]] = {}

    def _run_benchmark(
        self,
        name: str,
        func,
        *args,
        **kwargs
    ) -> Dict[str, float]:
        """运行标准基准测试: warmup → measure → 统计"""

        for _ in range(self.warmup_runs):
            func(*args, **kwargs)

        times = []
        for _ in range(self.measure_runs):
            start = time.perf_counter()
            func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        stats = {
            "mean_ms": statistics.mean(times) * 1000,
            "median_ms": statistics.median(times) * 1000,
            "min_ms": min(times) * 1000,
            "max_ms": max(times) * 1000,
            "std_ms": statistics.stdev(times) * 1000 if len(times) > 1 else 0,
            "p95_ms": sorted(times)[int(len(times) * 0.95)] * 1000 if len(times) > 1 else times[0] * 1000,
        }
        self.results[name] = stats
        return stats


class MemorySystemBenchmark(PerformanceBenchmark):
    """MemorySystem 性能测试"""

    def __init__(self):
        super().__init__(warmup_runs=3, measure_runs=10)
        self.system: Optional[MemorySystem] = None

    def _generate_test_content(self, n: int) -> List[str]:
        """生成测试用记忆内容"""
        contents = []
        templates = [
            "在{}遇到了一位{}",
            "{}给了我一个关于{}的建议",
            "我们一起去了{}, 看到了{}",
            "那天{}发生了{}, 让我感到很{}",
            "{}告诉我{}的秘密, 这让我{}",
            "在{}的{}上, 我发现了{}",
            "{}和{}一起讨论了关于{}的问题",
        ]
        entities_list = [
            ["图书馆", "学者", "书籍", "知识"],
            ["市场", "商人", "商品", "交易"],
            ["酒馆", "冒险者", "任务", "金币"],
            ["森林", "猎人", "野兽", "生存"],
            ["城堡", "骑士", "荣誉", "责任"],
            ["村庄", "农夫", "丰收", "希望"],
        ]

        emotions = list(MemoryEmotion)

        for i in range(n):
            tpl = templates[i % len(templates)]
            ents = entities_list[i % len(entities_list)]
            content = tpl.format(ents[0], ents[1], ents[2], ents[3], ents[0])
            contents.append(content)

        return contents

    def benchmark_store_batch(self, batch_size: int) -> Dict[str, float]:
        """测试批量存储性能"""
        system = MemorySystem(character_id="perf_test")
        contents = self._generate_test_content(batch_size)

        memory_types = list(MemoryType)
        emotion_list = list(MemoryEmotion)

        def store_all():
            for i, content in enumerate(contents):
                system.store(
                    content=content,
                    memory_type=memory_types[i % len(memory_types)],
                    emotions=[emotion_list[i % len(emotion_list)]],
                    emotional_intensity=0.3 + (i % 7) * 0.1,
                    associated_entities=content[:20].split(),
                )

        name = f"store_batch_{batch_size}"
        stats = self._run_benchmark(name, store_all)
        stats["ops_per_sec"] = batch_size / (stats["mean_ms"] / 1000)
        stats["avg_us_per_op"] = stats["mean_ms"] / batch_size * 1000
        self.system = system
        return stats

    def benchmark_retrieve(self, query_words: List[str], max_results: int = 10) -> Dict[str, float]:
        """测试检索性能"""
        if not self.system or len(self.system._memories) == 0:
            self.benchmark_store_batch(1000)

        def do_retrieve():
            self.system.retrieve(query=query_words, max_results=max_results, min_importance=0.01)

        name = f"retrieve_{''.join(query_words[:2])}_top{max_results}"
        return self._run_benchmark(name, do_retrieve)

    def benchmark_decay(self, memory_count: int) -> Dict[str, float]:
        """测试衰减性能"""
        system = MemorySystem(character_id="perf_decay")
        contents = self._generate_test_content(memory_count)

        for i, content in enumerate(contents):
            system.store(
                content=content,
                memory_type=MemoryType.EPISODIC,
                emotions=[MemoryEmotion.NEUTRAL],
                emotional_intensity=0.5,
            )

        def do_decay():
            system.decay(force=True)

        name = f"decay_{memory_count}_memories"
        stats = self._run_benchmark(name, do_decay)
        stats["us_per_memory"] = stats["mean_ms"] / memory_count * 1000
        return stats

    def benchmark_statistics(self, memory_count: int) -> Dict[str, float]:
        """测试统计信息获取性能"""
        system = MemorySystem(character_id="perf_stats")
        contents = self._generate_test_content(memory_count)

        for content in contents:
            system.store(content=content, emotional_intensity=0.5)

        def do_stats():
            system.get_statistics()

        name = f"statistics_{memory_count}"
        return self._run_benchmark(name, do_stats)


class MaslowEngineBenchmark(PerformanceBenchmark):
    """MaslowEngine 性能测试"""

    def __init__(self):
        super().__init__(warmup_runs=5, measure_runs=20)

    def benchmark_prioritize_default(self) -> Dict[str, float]:
        """测试默认情境下的动机排序"""
        engine = MotivationEngine(character_id="perf_maslow")

        def do_prioritize():
            engine.calculate_all_motivations()

        stats = self._run_benchmark("prioritize_default", do_prioritize)
        stats["us_per_call"] = stats["mean_ms"]
        return stats

    def benchmark_prioritize_with_context(self) -> Dict[str, float]:
        """测试带情境的动机排序"""
        engine = MotivationEngine(character_id="perf_context")

        contexts = [
            ContextType.COMBAT,
            ContextType.SOCIAL,
            ContextType.CRISIS,
            ContextType.CREATIVE,
        ]

        def do_prioritize_context():
            for ctx in contexts:
                engine.set_context(ctx)
                engine.calculate_all_motivations()

        stats = self._run_benchmark("prioritize_4contexts", do_prioritize_context)
        stats["us_per_context"] = stats["mean_ms"] / 4
        return stats

    def benchmark_conflict_detection(self) -> Dict[str, float]:
        """测试冲突检测性能"""
        engine = MotivationEngine(character_id="perf_conflict")
        engine._profile.update_need_value(NeedLevel.SAFETY, delta=-0.6)
        engine._profile.update_need_value(NeedLevel.PHYSIOLOGICAL, delta=-0.65)
        engine._profile.needs[NeedLevel.SAFETY].priority = 0.6
        engine._profile.needs[NeedLevel.ESTEEM].value = 0.25

        def do_detect():
            engine.detect_conflicts()

        stats = self._run_benchmark("conflict_detection", do_detect)
        stats["us_per_call"] = stats["mean_ms"]
        return stats

    def benchmark_report_generation(self) -> Dict[str, float]:
        """测试报告生成性能"""
        engine = MotivationEngine(character_id="perf_report")

        def do_report():
            engine.generate_report()

        stats = self._run_benchmark("report_generation", do_report)
        stats["us_per_call"] = stats["mean_ms"]
        return stats

    def benchmark_update_need(self, iterations: int = 100) -> Dict[str, float]:
        """测试批量更新需求性能"""
        engine = MotivationEngine(character_id="perf_update")
        levels = list(NeedLevel)

        def do_updates():
            for i in range(iterations):
                level = levels[i % len(levels)]
                engine._profile.update_need_value(level, delta=0.01 if i % 2 == 0 else -0.01)

        name = f"update_need_{iterations}x"
        stats = self._run_benchmark(name, do_updates)
        stats["us_per_op"] = stats["mean_ms"] / iterations
        return stats


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_stats(name: str, stats: Dict[str, float], targets: Dict[str, float] = None):
    """打印性能统计"""
    print(f"\n📊 {name}")
    print(f"   平均: {stats['mean_ms']:.3f} ms | "
          f"中位数: {stats['median_ms']:.3f} ms | "
          f"P95: {stats['p95_ms']:.3f} ms")
    print(f"   最小: {stats['min_ms']:.3f} ms | "
          f"最大: {stats['max_ms']:.3f} ms | "
          f"标准差: {stats['std_ms']:.3f} ms")

    if "ops_per_sec" in stats:
        print(f"   吞吐: {stats['ops_per_sec']:,.0f} ops/s")

    if "avg_us_per_op" in stats:
        print(f"   单操作: {stats['avg_us_per_op']:.1f} μs/op")

    if "us_per_call" in stats:
        print(f"   单调用: {stats['us_per_call']:.1f} μs/call")

    if targets:
        for metric, target in targets.items():
            actual = stats.get(metric, 0)
            status = "✅" if actual <= target else "❌"
            print(f"   {status} {metric}: {actual:.3f} (目标: ≤{target})")


def run_memory_system_benchmarks():
    """运行 MemorySystem 基准测试"""
    print_section("MemorySystem 性能基准测试")

    bench = MemorySystemBenchmark()

    targets_store = {"mean_ms": 500}
    targets_retrieve = {"mean_ms": 5}
    targets_decay = {"mean_ms": 50}

    sizes = [100, 500, 1000]

    print("\n📦 批量存储测试:")
    for size in sizes:
        stats = bench.benchmark_store_batch(size)
        print_stats(f"存储 {size} 条记忆", stats, targets_store)

    print("\n🔍 检索测试 (基于1000条记忆):")
    bench.benchmark_store_batch(1000)

    queries = [
        (["图书馆", "学者"], 5),
        (["商人", "商品"], 10),
        (["冒险者", "任务"], 20),
        (["骑士", "荣誉"], 10),
    ]

    for query, limit in queries:
        stats = bench.benchmark_retrieve(query, limit)
        print_stats(f"检索 {'+'.join(query)} (top-{limit})", stats, targets_retrieve)

    print("\n⏰ 衰减测试:")
    for size in [500, 1000, 5000]:
        stats = bench.benchmark_decay(size)
        print_stats(f"衰减 {size} 条记忆", stats, targets_decay)

    print("\n📈 统计信息测试:")
    for size in [500, 1000, 5000]:
        stats = bench.benchmark_statistics(size)
        print_stats(f"获取统计 ({size}条)", stats)

    return bench.results


def run_maslow_engine_benchmarks():
    """运行 MaslowEngine 基准测试"""
    print_section("MaslowEngine 性能基准测试")

    bench = MaslowEngineBenchmark()

    targets_prioritize = {"mean_ms": 0.1}

    print("\n⚡ 动机排序测试:")
    stats = bench.benchmark_prioritize_default()
    print_stats("默认情境排序", stats, targets_prioritize)

    stats = bench.benchmark_prioritize_with_context()
    print_stats("4种情境切换排序", stats)

    print("\n🔥 冲突检测测试:")
    stats = bench.benchmark_conflict_detection()
    print_stats("冲突检测", stats)

    print("\n📄 报告生成测试:")
    stats = bench.benchmark_report_generation()
    print_stats("报告生成", stats)

    print("\n🔄 批量更新测试:")
    for iters in [100, 1000]:
        stats = bench.benchmark_update_need(iters)
        print_stats(f"更新 {iters} 次", stats)

    return bench.results


def main():
    """主入口"""
    print("=" * 60)
    print(" Phase 2 性能基准测试套件")
    print(" MemorySystem + MaslowEngine")
    print("=" * 60)

    all_results = {}

    print("\n▶ MemorySystem 测试...")
    mem_results = run_memory_system_benchmarks()
    all_results.update(mem_results)

    print("\n▶ MaslowEngine 测试...")
    maslow_results = run_maslow_engine_benchmarks()
    all_results.update(maslow_results)

    print_section("总结")

    failures = []
    passes = []

    spec_targets = {
        "store_batch_1000_mean_ms": 500,
        "retrieve_top10_mean_ms": 5,
        "decay_5000_memories_mean_ms": 50,
        "prioritize_default_mean_ms": 0.1,
    }

    for name, target in spec_targets.items():
        if name in all_results:
            actual = all_results[name]["mean_ms"]
            if actual <= target:
                passes.append((name, actual, target))
            else:
                failures.append((name, actual, target))

    print(f"\n✅ 通过 SPEC 目标 ({len(passes)}/{len(spec_targets)}):")
    for name, actual, target in passes:
        print(f"   {name}: {actual:.3f}ms ≤ {target}ms")

    if failures:
        print(f"\n❌ 未达到 SPEC 目标 ({len(failures)}):")
        for name, actual, target in failures:
            ratio = actual / target
            print(f"   {name}: {actual:.3f}ms > {target}ms (超 {ratio:.1f}x)")

    print(f"\n总计测试项: {len(all_results)}")
    print(f"通过率: {len(passes)/max(len(spec_targets),1)*100:.0f}%")

    return all_results


if __name__ == "__main__":
    results = main()
