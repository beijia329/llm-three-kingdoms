#!/usr/bin/env python3
"""平衡性模拟（headless, 无渲染）。

运行 N 局（默认 100）ai-vs-ai 完整对局，用固定 seed 序列保证可复现，
统计 12 方每局胜率，判断各势力是否在健康区间，并标记胜率异常高（OP 策略嫌疑）。

运行方式：
    python tests/balance/run_simulation.py                 # 默认 100 局
    python tests/balance/run_simulation.py --games 50      # 50 局（更快）
    python tests/balance/run_simulation.py --seed-base 7 --json out.json

注意：本脚本不 import pygame / renderer，只走 engine + players.cli_player。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# 让 `tests/sim_lib` 可被直接运行方式导入。
_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS_DIR = os.path.dirname(_HERE)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import sim_lib  # noqa: E402

# 验收文档里的「25%-40% 健康区间」是按 3 方设计写的；当前游戏 12 方，
# 均匀公平份额 = 1/12 ≈ 8.33%，25%-40% 在数学上不可达（仅 2.5~4 方能赢）。
# 因此我们用「2×公平份额」作为 OP 嫌疑阈值，并在报告里标注这一文档口径差异。
FAIR_SHARE = 1.0 / sim_lib.NUM_FACTIONS
OP_THRESHOLD = 2.0 * FAIR_SHARE  # 12 方 ≈ 16.67%


def simulate(games: int, seed_base: int) -> dict:
    wins = {f: 0 for f in sim_lib.FACTION_KEYS}
    draws = 0
    crashes = []
    completed = 0
    total_elapsed = 0.0

    for i in range(games):
        seed = seed_base + i
        res = sim_lib.run_one_game(seed)
        total_elapsed += res["elapsed_s"]
        if res["crashed"]:
            crashes.append({"seed": seed, "reason": res["crashed"], "error": res["error"]})
            continue
        completed += 1
        w = res["winner"]
        if w is None:
            draws += 1
        elif w in wins:
            wins[w] += 1
        else:
            # 理论上 winner 必属 12 方之一；防御性处理
            wins[w] = wins.get(w, 0) + 1

    denom = completed if completed > 0 else 1
    rates = {f: wins[f] / denom for f in sim_lib.FACTION_KEYS}

    # 统计显著性（二项 95% 置信半宽）
    ci = {}
    for f in sim_lib.FACTION_KEYS:
        p = rates[f]
        half = 1.96 * (p * (1 - p) / denom) ** 0.5 if denom > 0 else 0.0
        ci[f] = half

    op_suspects = [f for f in sim_lib.FACTION_KEYS if rates[f] > OP_THRESHOLD]

    return {
        "games_requested": games,
        "completed": completed,
        "crashes": crashes,
        "draws": draws,
        "wins": wins,
        "win_rate": rates,
        "ci_half_width": ci,
        "fair_share": FAIR_SHARE,
        "op_threshold": OP_THRESHOLD,
        "op_suspects": op_suspects,
        "avg_game_seconds": round(total_elapsed / max(1, games), 3),
        "total_elapsed_seconds": round(total_elapsed, 2),
    }


def print_report(stats: dict) -> None:
    from game.constants import FACTIONS  # 本地导入避免污染
    fr = stats["fair_share"]
    print("=" * 72)
    print("  平衡性模拟报告（headless, CLI AI, 非 LLM 基线）")
    print("=" * 72)
    print(f"  请求局数        : {stats['games_requested']}")
    print(f"  完成局数        : {stats['completed']}")
    print(f"  崩溃局数        : {len(stats['crashes'])}")
    print(f"  平局/无明确胜者 : {stats['draws']}")
    print(f"  平均单局耗时    : {stats['avg_game_seconds']} s")
    print(f"  总耗时          : {stats['total_elapsed_seconds']} s")
    print(f"  公平份额(1/12)  : {fr*100:.2f}%    OP 嫌疑阈值(2×): {stats['op_threshold']*100:.2f}%")
    print("-" * 72)
    print(f"  {'势力':<10}{'名称':<8}{'胜场':>5}{'胜率':>9}{'95%CI±':>9}{'状态':>14}")
    print("-" * 72)
    # 按胜率降序
    order = sorted(sim_lib.FACTION_KEYS, key=lambda f: -stats["win_rate"][f])
    for f in order:
        label = FACTIONS.get(f, f)
        rate = stats["win_rate"][f]
        wins = stats["wins"][f]
        cih = stats["ci_half_width"][f]
        if f in stats["op_suspects"]:
            status = "🔴 OP嫌疑"
        elif rate == 0:
            status = "⚪ 0胜(偏弱)"
        else:
            status = "🟢 正常"
        print(f"  {f:<10}{label:<8}{wins:>5}{rate*100:>8.1f}%{cih*100:>8.1f}%{status:>14}")
    print("-" * 72)
    if stats["op_suspects"]:
        names = ", ".join(FACTIONS.get(f, f) for f in stats["op_suspects"])
        print(f"  OP 策略嫌疑势力 : {names}")
    else:
        print("  OP 策略嫌疑势力 : 无")
    print("=" * 72)

    # 验收判定（供 acceptance 报告引用）
    if len(stats["crashes"]) > 0:
        verdict = "FAIL（模拟过程出现崩溃，无法得出可信平衡结论）"
    elif stats["op_suspects"]:
        verdict = "CONCERNS（存在胜率异常高的势力，疑似 OP 策略）"
    else:
        verdict = "PASS（无 OP 策略嫌疑，12 方胜率分布未出现霸主）"
    print(f"  平衡性判定      : {verdict}")
    print("=" * 72)
    print("  说明：验收文档「三方胜率25%-40%」按 3 方设计撰写，对 12 方不可达；")
    print("        本报告以「胜率 > 2×公平份额(16.67%) 即 OP 嫌疑」作为适配判据。")
    print("=" * 72)


def main() -> int:
    ap = argparse.ArgumentParser(description="平衡性模拟（headless）")
    ap.add_argument("--games", type=int, default=100, help="对局数（默认 100；太慢可降到 50）")
    ap.add_argument("--seed-base", type=int, default=20261001, help="起始种子")
    ap.add_argument("--json", type=str, default="", help="可选：把统计结果写成 JSON")
    args = ap.parse_args()

    stats = simulate(args.games, args.seed_base)
    print_report(stats)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(stats, fh, ensure_ascii=False, indent=2)
        print(f"\n[已写出 JSON: {args.json}]")

    # 退出码：崩溃或 OP 嫌疑 → 非 0，便于 CI 门控
    if stats["crashes"] or stats["op_suspects"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
