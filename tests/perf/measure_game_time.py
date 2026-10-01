#!/usr/bin/env python3
"""单局耗时测量（headless, 无渲染）。

测量 1 局（默认跑 3 局取统计）完整对局（192 回合）的墙钟时间，
对照里程碑「单局 ≤ 30 分钟」标准。基线使用非 LLM 的 CLI AI；
真实 LLM 玩家因每步需网络推理会显著更慢，需密钥后单独补测。

运行方式：
    python tests/perf/measure_game_time.py
    python tests/perf/measure_game_time.py --runs 3 --seed-base 20261001

注意：本脚本不 import pygame / renderer，只走 engine + players.cli_player。
"""

from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS_DIR = os.path.dirname(_HERE)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import sim_lib  # noqa: E402

LIMIT_SECONDS = 30 * 60  # 30 分钟 = 1800 秒


def measure(runs: int, seed_base: int) -> dict:
    samples = []
    for i in range(runs):
        seed = seed_base + i
        res = sim_lib.run_one_game(seed)
        samples.append({
            "seed": seed,
            "turns": res["turns"],
            "elapsed_s": res["elapsed_s"],
            "crashed": res["crashed"],
            "winner": res["winner"],
        })
    elapsed_list = [s["elapsed_s"] for s in samples if not s["crashed"]]
    return {
        "runs": runs,
        "limit_seconds": LIMIT_SECONDS,
        "samples": samples,
        "min_s": min(elapsed_list) if elapsed_list else None,
        "max_s": max(elapsed_list) if elapsed_list else None,
        "avg_s": (sum(elapsed_list) / len(elapsed_list)) if elapsed_list else None,
        "crashes": sum(1 for s in samples if s["crashed"]),
    }


def print_report(m: dict) -> None:
    print("=" * 72)
    print("  单局耗时测量报告（headless, CLI AI 基线 / 非 LLM）")
    print("=" * 72)
    print(f"  对照标准        : 单局 ≤ {m['limit_seconds']} s (30 分钟)")
    print("-" * 72)
    for s in m["samples"]:
        flag = "💥崩溃" if s["crashed"] else f"{s['elapsed_s']:.2f}s"
        print(f"  seed={s['seed']:<12} turns={s['turns']:<4} 耗时={flag}")
    print("-" * 72)
    if m["avg_s"] is not None:
        print(f"  最小 / 平均 / 最大 : {m['min_s']:.2f}s / {m['avg_s']:.2f}s / {m['max_s']:.2f}s")
        margin = m["limit_seconds"] / m["avg_s"]
        print(f"  相对 30 分钟上限的安全倍数 : 约 {margin:.0f}×")
        verdict = "PASS" if m["avg_s"] <= m["limit_seconds"] else "FAIL"
    else:
        verdict = "FAIL（全部崩溃，无法测量）"
    print(f"  性能判定        : {verdict}（CLI AI 基线；真实 LLM 需密钥后补测）")
    print("=" * 72)
    print("  说明：本测量使用性格驱动的非 LLM CLI AI，每步本地即时决策；")
    print("        真实 LLM 玩家每步有网络往返与推理延迟，单局会更长，")
    print("        需在配置 API Key 后单独补测（本脚本与判定均不替代该补测）。")
    print("=" * 72)


def main() -> int:
    ap = argparse.ArgumentParser(description="单局耗时测量（headless）")
    ap.add_argument("--runs", type=int, default=3, help="测量局数（默认 3，取统计）")
    ap.add_argument("--seed-base", type=int, default=20261001, help="起始种子")
    args = ap.parse_args()

    m = measure(args.runs, args.seed_base)
    print_report(m)
    if m["crashes"] or m["avg_s"] is None or m["avg_s"] > m["limit_seconds"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
