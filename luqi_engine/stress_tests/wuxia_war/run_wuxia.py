"""
武侠战争全链路运行入口

用法:
    python -m luqi_engine.stress_tests.wuxia_war.run_wuxia
    或
    python run_wuxia.py

环境变量(可选):
    LUQI_API_KEY      — API密钥 (必填)
    LUQI_BASE_URL     — API地址 (默认 https://api.luqi.ai/v1)
    LUQI_MODEL        — 模型名  (默认 mimo-v2.5)
    WUXIA_MAX_ROUNDS  — 最大轮次 (默认 5000)
    WUXIA_SEED        — 随机种子 (默认 42)
"""

import os
import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    api_key = os.environ.get("LUQI_API_KEY", "")
    if not api_key:
        print("=" * 60)
        print("错误: 未设置LUQI_API_KEY环境变量")
        print()
        print("请设置API密钥后重试:")
        print("  Windows: $env:LUQI_API_KEY='your-key-here'")
        print("  Linux:   export LUQI_API_KEY='your-key-here'")
        print()
        print("或直接在代码中修改api_key变量")
        print("=" * 60)
        sys.exit(1)
    
    base_url = os.environ.get(
        "LUQI_BASE_URL",
        "https://api.luqi.ai/v1"
    )
    model = os.environ.get("LUQI_MODEL", "mimo-v2.5")
    
    max_rounds = int(os.environ.get("WUXIA_MAX_ROUNDS", "5000"))
    seed = int(os.environ.get("WUXIA_SEED", "42"))
    
    from .wuxia_runner import WuxiaInfiniteLoop
    
    output_dir = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "..", "wuxia_runs"
    )
    output_dir = os.path.abspath(output_dir)
    
    loop = WuxiaInfiniteLoop(
        api_key=api_key,
        base_url=base_url,
        model=model,
        character_count=620,
        seed=seed,
        temperature=0.75,
        max_tokens=800,
        max_rounds=max_rounds,
        save_interval=25,
        output_dir=output_dir,
    )
    
    print("=" * 60)
    print(f"  武侠战争全链路无限循环引擎")
    print(f"  Session: {loop.session_id}")
    print(f"  模型:   {model}")
    print(f"  角色:   {loop.character_count}")
    print(f"  最大轮次: {loop.max_rounds}")
    print(f"  输出目录: {output_dir}")
    print("=" * 60)
    print()
    
    t0 = time.time()
    result = loop.run()
    elapsed = time.time() - t0
    
    print()
    print("=" * 60)
    print(f"  运行完成!")
    print(f"  总轮次:     {result.total_turns}")
    print(f"  总Token:    {result.total_tokens:,}")
    print(f"  总耗时:     {elapsed:.1f}s ({elapsed/60:.1f}min)")
    if result.total_turns > 0:
        print(f"  平均延迟:   {result.total_latency_ms/result.total_turns:.0f}ms/轮")
        print(f"  平均Token:  {result.total_tokens/result.total_turns:.1f}tok/轮")
    if result.ending:
        print(f"  结局类型:   {result.ending.ending_type.value}")
        print(f"  结局原因:   {result.ending.reason}")
    print(f"  最终存活:   {result.final_world_state.get('alive', '?')}")
    print(f"  结果文件:   wuxia_{result.session_id}_FINAL.json")
    print("=" * 60)
    
    return result


if __name__ == "__main__":
    main()
