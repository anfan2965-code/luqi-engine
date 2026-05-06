"""
极限压力测试主入口
==================

使用方式:
    # 默认配置 (3文明, 标准黑暗森林)
    python -m luqi_engine.stress_tests.main
    
    # 高混沌模式
    python -m luqi_engine.stress_tests.main --mode high_chaos
    
    # 合作模式 (弱化黑暗森林)
    python -m luqi_engine.stress_tests.main --mode cooperative
    
    # 扩展场景 (4文明, 含WILDCARD)
    python -m luqi_engine.stress_tests.main --extended
    
    # 指定最大轮次 (用于快速测试)
    python -m luqi_engine.stress_tests.main --max-rounds 1000

输出:
    1. 控制台实时日志 (每100轮)
    2. 完整引擎能力报告 (文本格式)
    3. 可选: JSON格式详细数据
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def setup_logging(verbose: bool = True) -> None:
    """配置日志系统"""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "[%(asctime)s] %(name)-20s %(levelname)-8s %(message)s"
    datefmt = "%H:%M:%S"
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    
    root = logging.getLogger("luqi_engine")
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Luqi Engine 极限压力测试 — N体博弈模拟",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m luqi_engine.stress_tests.main                    # 默认3文明测试
  python -m luqi_engine.stress_tests.main --mode high_chaos   # 高混沌模式
  python -m luqi_engine.stress_tests.main --mode cooperative  # 弱黑暗森林模式
  python -m luqi_engine.stress_tests.main --extended           # 4文明扩展场景
  python -m luqi_engine.stress_tests.main --max-rounds 5000   # 限制轮次
  python -m luqi_engine.stress_tests.main --output report.json # 输出JSON
        """,
    )
    
    parser.add_argument(
        "--mode", "-m",
        choices=["default", "high_chaos", "cooperative"],
        default="default",
        help="宇宙规则配置模式 (默认: default)",
    )
    
    parser.add_argument(
        "--extended", "-e",
        action="store_true",
        default=False,
        help="使用4文明扩展场景 (含WILDCARD角色)",
    )
    
    parser.add_argument(
        "--max-rounds", "-r",
        type=int,
        default=None,
        help="最大轮次上限 (不设置则运行到自然结局)",
    )
    
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="随机种子 (默认: 42, 用于可复现性)",
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="JSON报告输出路径 (可选)",
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="静默模式 (仅输出最终报告)",
    )
    
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=100,
        help="进度日志间隔轮数 (默认: 100)",
    )
    
    parser.add_argument(
        "--dialogue", "-d",
        type=str,
        nargs="?",
        const="auto",
        default=None,
        help=(
            "运行LLM对话验证 (需设置LLM_API_KEY环境变量)。"
            "可指定场景描述, 或使用'auto'自动生成。"
            "支持后端: openai/ollama/custom (通过LLM_BACKEND环境变量)"
        ),
    )
    
    parser.add_argument(
        "--dialogue-turns",
        type=int,
        default=6,
        help="对话最大轮数 (默认: 6)",
    )
    
    return parser.parse_args()


def run_stress_test(args: argparse.Namespace) -> Dict[str, Any]:
    """
    执行完整的压力测试流程
    
    Returns:
        包含结果和元数据的字典
    """
    from .civilizations import DefaultScenario
    from .game_loop import GameLoop
    from .analyzer import StressTestAnalyzer
    
    print("=" * 70)
    print("  Luqi Engine 极限压力测试")
    print(f"  模式: {args.mode} | 文明数: {'4(扩展)' if args.extended else '3(标准)'} | 种子: {args.seed}")
    print("=" * 70)
    print()
    
    start_time = time.perf_counter()
    
    profiles = (
        DefaultScenario.extended_scenario() if args.extended
        else DefaultScenario.all_profiles()
    )
    
    loop = GameLoop.create_default(
        scenario_profiles=profiles,
        seed=args.seed,
        universe_config=args.mode,
        verbose=not args.quiet,
    )
    
    loop._log_interval = args.progress_interval
    
    def progress_callback(result) -> None:
        pass
    
    state = loop.run_with_callback(
        callback=progress_callback,
        max_rounds_override=args.max_rounds,
    )
    
    simulation_time = time.perf_counter() - start_time
    
    print("\n" + "=" * 70)
    print("  开始分析...")
    print("=" * 70 + "\n")
    
    analyzer = StressTestAnalyzer(state=state)
    report = analyzer.full_analysis()
    
    text_report = report.to_text_report()
    print(text_report)

    dialogue_result = None
    if args.dialogue is not None:
        print("\n" + "=" * 70)
        print("  LLM对话验证")
        print("=" * 70 + "\n")

        try:
            from .llm_dialogue import run_dialogue_test, LLMConfig

            llm_cfg = LLMConfig.from_env()

            scenario_text = None
            if args.dialogue and args.dialogue != "auto":
                scenario_text = args.dialogue
            else:
                alive = state.alive_civs
                if len(alive) >= 2:
                    top_tech = max(alive, key=lambda c: c.current_tech_level)
                    others = [c for c in alive if c.civ_id != top_tech.civ_id]
                    if others:
                        opponent = max(others, key=lambda c: c.current_tech_level)
                        scenario_text = (
                            f"{top_tech.profile.display_name}检测到"
                            f"{opponent.profile.display_name}的信号, "
                            f"决定发起首次接触。"
                        )

            print(f"  LLM后端: {llm_cfg.backend.value}")
            print(f"  模型: {llm_cfg.model}")
            print(f"  端点: {llm_cfg.base_url or '(默认)'}")
            print(f"  场景: {scenario_text or '自动'}")
            print(f"  最大轮次: {args.dialogue_turns}")
            print()

            dialogue_result = run_dialogue_test(
                game_state=state,
                max_turns=args.dialogue_turns,
                scenario=scenario_text or "",
            )

            dialogue_report = dialogue_result.to_text_report()
            print(dialogue_report)

        except ImportError as e:
            print(f"  [跳过] 缺少依赖: {e}")
            print("  提示: pip install httpx")
        except Exception as e:
            print(f"  [错误] 对话验证失败: {e}")

    result_data: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "configuration": {
            "mode": args.mode,
            "extended": args.extended,
            "max_rounds": args.max_rounds,
            "seed": args.seed,
            "num_civilizations": len(profiles),
        },
        "simulation_result": {
            "total_rounds": state.current_round,
            "ending_type": state.ending_type.name if state.ending_type else None,
            "ending_reason": state.ending_reason,
            "simulation_time_sec": round(simulation_time, 3),
            "total_events": len(state.rules.environment.history),
            "total_snapshots": len(state.rules.environment.state_history),
            "final_alive_civs": [c.civ_id for c in state.alive_civs],
            "final_dead_civs": [c.civ_id for c in state.dead_civs],
            "protagonist_survived": state.protagonist is not None,
        },
        "engine_assessment": {
            "overall_score": round(report.overall_score, 4),
            "overall_grade": report.overall_grade,
            "is_acceptable": report.is_acceptable,
            "critical_weakness_count": report.critical_weakness_count,
            "dimension_scores": {
                ds.dimension.name: round(ds.score, 4)
                for ds in report.dimension_scores
            },
            "weakness_categories": [w.category.name for w in report.weaknesses],
            "capabilities_summary": [
                {"name": c.name, "level": c.level.name, "confidence": round(c.confidence, 2)}
                for c in report.capabilities
            ],
        },
        "performance": {
            "avg_round_time_ms": round(report.performance.avg_round_time_ms, 3),
            "p95_round_time_ms": round(report.performance.p95_round_time_ms, 3),
            "rounds_per_second": round(report.performance.rounds_per_second, 2),
            "bottleneck_phase": report.performance.bottleneck_phase.name if report.performance.bottleneck_phase else None,
        },
        "outcome_evaluation": {
            "expected": report.outcome_evaluation.expected_type.name,
            "actual": report.outcome_evaluation.actual_type.name if report.outcome_evaluation.actual_type else None,
            "plausibility": round(report.outcome_evaluation.plausibility_score, 3),
            "game_theory_alignment": round(report.outcome_evaluation.alignment_with_game_theory, 3),
        },
        "limit_findings": report.limit_findings,
        "recommendations": report.recommendations,
    }

    if dialogue_result is not None:
        result_data["dialogue_verification"] = dialogue_result.to_dict()
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n📄 详细报告已保存至: {output_path.absolute()}")
    
    return result_data


def main() -> int:
    """主入口函数"""
    try:
        args = parse_args()
        setup_logging(verbose=not args.quiet)
        
        result = run_stress_test(args)
        
        acceptable = result.get("engine_assessment", {}).get("is_acceptable", False)
        score = result.get("engine_assessment", {}).get("overall_score", 0)
        
        if acceptable:
            print(f"\n✅ 压力测试通过 (评分: {score:.3f})")
            return 0
        else:
            print(f"\n⚠️ 压力测试发现问题 (评分: {score:.3f}) — 请查看上方报告")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⚙️ 用户中断测试")
        return 130
        
    except Exception as e:
        print(f"\n\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
