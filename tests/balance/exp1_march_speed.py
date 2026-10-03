#!/usr/bin/env python3
"""实验 1+2：行军速度单变量对照（4/ 6 / 8 / 10 四档）+ 基线复现。

严格单变量：只有 `game.constants.ARMY_MARCH_SPEED` 变化，其余（seed 列表、
max_turns、地图数据、CLIPlayer 策略）全部固定。max_turns 默认沿用生产值 192，
另用 --max-turns 可切到 24/36/48 做实验 3。

**对照组设计**：
  - 基线档 speed=4 即「当前生产配置」，作为对照基准（不是额外变量）。
  - 每档使用**完全相同**的 seed 列表 → 配对设计（paired design），
    消除地图/初始布局的随机干扰，使档间差异可归因于行军速度。
  - 每档默认 5 局（--games），远大于随机噪声需求；实跑 26s/局，
    用 12 核进程池并发，约 1~2 分钟出全部 20 局。

运行：
    python tests/balance/exp1_march_speed.py                # 4/6/8/10 × 5 局, max_turns=192
    python tests/balance/exp1_march_speed.py --games 8      # 每档 8 局
    python tests/balance/exp1_march_speed.py --max-turns 36 # 顺带做回合数对照
    python tests/balance/exp1_march_speed.py --out tests/balance/data/exp1_march_speed.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P  # noqa: E402

SPEEDS = [4, 6, 8, 10]


def _worker(payload) -> Dict[str, Any]:
    """子进程：跑一局。必须在子进程内设速度（进程隔离，避免模块状态串扰）。"""
    speed, seed, max_turns = payload
    P.set_march_speed(speed)
    row = P.run_one_game(seed, max_turns)
    row["march_speed"] = speed
    return row


def run_config(speed: int, seeds: List[int], max_turns: int, workers: int) -> List[Dict[str, Any]]:
    """在一个速度档下并发跑 N 局。"""
    payloads = [(speed, s, max_turns) for s in seeds]
    rows: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for row in ex.map(_worker, payloads):
            rows.append(row)
    rows.sort(key=lambda r: r["seed"])
    return rows


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验1+2：行军速度单变量对照")
    ap.add_argument("--speeds", type=int, nargs="+", default=SPEEDS)
    ap.add_argument("--games", type=int, default=5, help="每档局数（默认 5）")
    ap.add_argument("--seed-base", type=int, default=91001, help="首个 seed（各档共用，配对设计）")
    ap.add_argument("--max-turns", type=int, default=192, help="回合上限（默认沿用生产值 192）")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--baseline", action="store_true",
                    help="把 P0 相关属性锁定为修复前取值（对抗并发修改，保证对照有效）")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()
    if args.baseline:  # 对抗并发修改：把 P0 属性锁回"修复前"
        _ok = P.use_pristine_baseline(True)
        print("  [基线锁定] " + ("已还原为修复前取值" if _ok else "失败（继续用工作区）"))

    seeds = [args.seed_base + i for i in range(args.games)]

    print("=" * 96)
    print("  实验 1+2：ARMY_MARCH_SPEED 单变量对照（headless / CLIPlayer / 无 LLM）")
    print("=" * 96)
    print(f"  变量          : game.constants.ARMY_MARCH_SPEED ∈ {args.speeds}")
    print(f"  固定项        : max_turns={args.max_turns}, 每档 seeds={seeds}（配对设计）")
    print(f"  每档局数      : {args.games}    并发: {args.workers} 进程")
    print(f"  玩家          : players.cli_player.CLIPlayer × 12 方（非LLM）")
    print("=" * 96)

    all_rows: List[Dict[str, Any]] = []
    summaries: Dict[str, Dict[str, Any]] = {}
    t_start = time.time()

    for sp in args.speeds:
        P.print_config_header(sp, args.max_turns, seeds)
        rows = run_config(sp, seeds, args.max_turns, args.workers)
        for r in rows:
            print(f"    seed={r['seed']} turns={r['turns']:>3} battles={r['battles']:>3} "
                  f"first_battle={str(r['first_battle_turn']):>4} armies={r['armies_launched']:>4} "
                  f"neutral={r['neutral_taken']:>2} first_neutral={str(r['first_neutral_turn']):>4} "
                  f"survivors={r['surviving_factions']:>2} top={r['top_faction_share']:.2f} "
                  f"winner={r['winner']} ({r['elapsed_s']}s)")
        summaries[f"{sp}@{args.max_turns}"] = P.summarize(rows)
        summaries[f"{sp}@{args.max_turns}"]["march_speed"] = sp
        all_rows.extend(rows)
        print()

    P.print_summary_table(summaries, [f"{sp}@{args.max_turns}" for sp in args.speeds])

    # ---- 逐档明细：战斗密度 + 胜率分布 ----
    print("\n  战斗密度（回合越短→密度越高）与统一度:")
    print(f"    {'speed':>6}{'战斗/局(中位)':>14}{'战斗/回合':>11}{'首战回合':>10}"
          f"{'结束回合':>10}{'存活势力':>10}{'HHI':>8}{'最大占比':>10}")
    for sp in args.speeds:
        s = summaries[f"{sp}@{args.max_turns}"]
        b, fb, tn = s["battles"], s["first_battle_turn"], s["turns"]
        per_turn = (b["mean"] / tn["mean"]) if tn["mean"] else 0.0
        print(f"    {sp:>6}{b['median']:>14.1f}{per_turn:>11.3f}"
              f"{(fb['median'] if fb['max'] else 0):>10.0f}{tn['median']:>10.0f}"
              f"{s['surviving_factions']['median']:>10.1f}"
              f"{s['hhi']['median']:>8.3f}{s['top_faction_share']['median']:>10.3f}")

    print("\n  各档 0 战斗局数 / 崩溃局数（数据可信度检查）:")
    for sp in args.speeds:
        s = summaries[f"{sp}@{args.max_turns}"]
        print(f"    speed={sp:>2}: 0战斗局={s['games_without_battle']}/{s['completed']}"
              f"  崩溃={len(s['crashes'])}  有明确胜者={s['decided_games']}/{s['completed']}")

    print("\n  各档胜率分布（检测碾压）:")
    for sp in args.speeds:
        s = summaries[f"{sp}@{args.max_turns}"]
        top = sorted(s["win_rate"].items(), key=lambda kv: -kv[1])[:5]
        opp = s["op_suspects"]
        print(f"    speed={sp:>2}: " + ", ".join(f"{k}={v*100:.0f}%" for k, v in top)
              + f"  | 0胜势力数={len(s['zero_win_factions'])}"
              + (f"  | 🔴OP嫌疑: {opp}" if opp else "  | 无OP嫌疑"))

    print(f"\n  总耗时: {time.time() - t_start:.1f}s")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "config": {"speeds": args.speeds, "games": args.games,
                               "seeds": seeds, "max_turns": args.max_turns,
                               "player": "CLIPlayer", "llm": False},
                    "summaries": summaries,
                    "raw_rows": all_rows,
                },
                fh, ensure_ascii=False, indent=2,
            )
        print(f"  [已写出 JSON: {args.out}]")

        # 同步落CSV，便于直接做表
        csv_path = os.path.splitext(args.out)[0] + ".csv"
        _write_csv(csv_path, all_rows)
        print(f"  [已写出 CSV: {csv_path}]")
    print("=" * 96)
    return 0


def _write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    import csv
    cols = ["march_speed", "seed", "turns", "max_turns", "battles", "first_battle_turn",
            "armies_launched", "neutral_taken", "first_neutral_turn",
            "surviving_factions", "top_faction_share", "hhi", "winner", "crashed", "elapsed_s"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    sys.exit(main())
