#!/usr/bin/env python3
"""稳定性测试（headless, 无渲染）。

连续跑 10 局完整对局（192 回合），断言：每局都能正常结束（game_over=True）、
无崩溃、无卡死/超时；并记录每局是否有明确胜者、耗时与任何异常。

运行方式：
    python tests/stability/run_10_games.py
    python tests/stability/run_10_games.py --games 10 --seed-base 20261001

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
from game.constants import FACTIONS  # noqa: E402


def run_stability(games: int, seed_base: int) -> dict:
    rows = []
    crashes = 0
    timeouts = 0
    no_winner = 0
    not_over = 0

    for i in range(games):
        seed = seed_base + i
        res = sim_lib.run_one_game(seed)
        winner_label = FACTIONS.get(res["winner"], res["winner"]) if res["winner"] else "（平局/无明确胜者）"
        row = {
            "seed": seed,
            "turns": res["turns"],
            "game_over": res["game_over"],
            "winner": res["winner"],
            "winner_label": winner_label,
            "crashed": res["crashed"],
            "elapsed_s": res["elapsed_s"],
        }
        rows.append(row)

        if res["crashed"]:
            crashes += 1
        if not res["game_over"]:
            not_over += 1
        if res["winner"] is None:
            no_winner += 1

    ok = (crashes == 0) and (not_over == 0)
    return {
        "games": games,
        "rows": rows,
        "crashes": crashes,
        "not_over": not_over,
        "no_winner": no_winner,
        "ok": ok,
    }


def print_report(st: dict) -> None:
    print("=" * 78)
    print("  稳定性测试报告（headless, 10 局完整对局）")
    print("=" * 78)
    print(f"  {'种子':>12} {'回合':>5} {'正常结束':>8} {'胜者':<22}{'耗时(s)':>10} {'状态':>8}")
    print("-" * 78)
    for r in st["rows"]:
        over = "是" if r["game_over"] else "否"
        if r["crashed"]:
            status = "💥崩溃"
        elif not r["game_over"]:
            status = "⏱未结束"
        elif r["winner"] is None:
            status = "平局"
        else:
            status = "OK"
        print(f"  {r['seed']:>12} {r['turns']:>5} {over:>8} {r['winner_label']:<22}{r['elapsed_s']:>10} {status:>8}")
    print("-" * 78)
    print(f"  崩溃局数        : {st['crashes']}")
    print(f"  未正常结束局数  : {st['not_over']}")
    print(f"  平局/无明确胜者 : {st['no_winner']}")
    verdict = "PASS" if st["ok"] else "FAIL"
    print(f"  稳定性判定      : {verdict}（无崩溃 & 全部正常结束）")
    print("=" * 78)


def main() -> int:
    ap = argparse.ArgumentParser(description="稳定性测试（headless）")
    ap.add_argument("--games", type=int, default=10, help="对局数（默认 10）")
    ap.add_argument("--seed-base", type=int, default=20261001, help="起始种子")
    args = ap.parse_args()

    st = run_stability(args.games, args.seed_base)
    print_report(st)
    return 0 if st["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
