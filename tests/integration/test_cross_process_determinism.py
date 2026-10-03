"""跨进程确定性守卫测试（进 CI）

背景
----
本项目把「同 seed + 同输入 = 同结果」当作支柱（ADR-0002），但该性质在
2026 年三个月内被 3 个人、在不同位置各发现坏过一次：

  1. `api/game_manager.py` 玩家种子用内置 `hash()`（受 PYTHONHASHSEED 随机加盐）
  2. `game/data_loader.py` 构造 `map_topology` 用 `set`（迭代序不稳）
  3. `players/cli_player.py` 外交目标来源 `list({...})` 喂给 `_rng.choice()`

共同根因：**依赖集合迭代序**。人肉实测守不住，只能靠自动化——本文件即是那把尺子。

做法
----
用 `subprocess` 起两个（或多个）`PYTHONHASHSEED` 不同的子进程，各自跑同一局
（engine + CLIPlayer，纯逻辑，不 import pygame / renderer / llm），逐回合打印
状态指纹（md5），比对两端指纹序列是否**逐字节一致**。

设计约束
--------
- 必须能在 CI 的 Linux 环境跑：不依赖本机绝对路径、不访问网络、不读 .env。
- 运行时间可控：回合数取小（12）。
- 不 import `players.llm`（避免 httpx / json_repair / 网络依赖拖慢或失败）。

附带的「敏感性」自检：换一个 game seed 后指纹必须**不同**——否则测试可能因
「指纹写死/退化为常量」而永远通过（假绿）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# tests/integration/xxx.py → parents[2] = 仓库根
ROOT = Path(__file__).resolve().parents[2]

TURNS = 12
"""探针回合一数（保持 CI 快速；足够覆盖资源/行军/忠诚/外交/战斗多阶段）"""


# ============================================================
# 子进程探针：跑一局并逐回合打印指纹
# ============================================================
_PROBE = r'''
import hashlib
import os
import sys

sys.path.insert(0, os.getcwd())

from game.constants import FACTIONS
from game.data_loader import load_game_data
from game.engine import GameEngine
from game.random import GameRandom, stable_hash
from players.cli_player import CLIPlayer

SEED = int(os.environ["PROBE_SEED"])
TURNS = int(os.environ["PROBE_TURNS"])


def fingerprint(engine, players):
    """整局状态指纹：按 id 排序拼接后 md5。

    🔴 必须覆盖**所有会随集合迭代序变化的状态**，否则守卫测试会「假绿」：
    - 城池/军队/将领：核心状态
    - 外交关系 / 外交消息：`_rng.choice(enemy_factions)` 的差异最先只体现在这里，
      若指纹不含它们，则「宣战/外交目标因 hash 序变了」这类分叉会被漏检
    - 各玩家 RNG 调用总数：最能早期暴露「随机数消耗序列分叉」的信号
      （哪怕分歧暂未传播进城市状态）
    """
    parts = []
    for cid in sorted(engine.cities):
        c = engine.cities[cid]
        parts.append(
            f"C|{cid}|{c.faction}|{c.garrison}|{c.gold}|{c.food}|"
            f"{c.population}|{c.morale}|{c.wall_hp}"
        )
    for aid in sorted(engine.armies):
        a = engine.armies[aid]
        parts.append(
            f"A|{aid}|{a.faction}|{a.general_id}|{a.soldiers}|"
            f"{a.morale}|{a.status.value}|{a.progress:.4f}"
        )
    for gid in sorted(engine.generals):
        g = engine.generals[gid]
        parts.append(f"G|{gid}|{g.faction}|{g.loyalty}|{g.location}|{int(g.is_captured)}")

    rel_sys = getattr(engine, "_diplomacy_relation_system", None)
    if rel_sys is not None:
        for (fa, fb), rel in sorted(rel_sys.get_all_relations().items()):
            parts.append(
                f"R|{fa}|{fb}|{rel.status.value}|{rel.trust}|"
                f"{rel.truce_end_turn}|{rel.alliance_end_turn}"
            )

    for m in engine._messages:
        parts.append(f"M|{m.id}|{m.from_faction}|{m.to_faction}|{m.turn}|{int(m.is_read)}")

    rng_calls = sum(p._rng.call_count for p in players.values())
    parts.append(f"RNG|{rng_calls}")

    return hashlib.md5(";".join(parts).encode("utf-8")).hexdigest()


def main():
    engine = GameEngine(seed=SEED)
    engine.max_turns = TURNS
    engine.init_game(load_game_data())

    players = {
        f: CLIPlayer(faction=f, rng=GameRandom(SEED + stable_hash(f) % 10000))
        for f in FACTIONS
    }

    n = 0
    while not engine.game_over and n < TURNS * 2:  # 上限仅为防呆
        # 🔴 与 main.py run_ai_vs_ai 的循环**逐句一致**（含 receive_message 传播），
        #    否则探针覆盖不到「外交消息 → 对方 _pending_alliance → 结盟提议」这条
        #    会把 hash 序分歧放大成整局分叉的链路。
        for faction in FACTIONS:
            obs = engine.get_observation(faction)
            for cmd in players[faction].get_commands(obs):
                result = engine.execute_command(cmd)
                if result.success and cmd.type == "message" and hasattr(cmd, "to"):
                    target_player = players.get(cmd.to)
                    if target_player:
                        target_player.receive_message(faction, str(getattr(cmd, "content", "")))
        engine.process_turn()
        n += 1
        print(f"T{engine.turn}|{fingerprint(engine, players)}")

    print(f"END|turns={n}|game_over={engine.game_over}|winner={engine.winner}")


main()
'''


def _run_probe(pythonhashseed: str, seed: int = 42, turns: int = TURNS) -> str:
    """在指定 PYTHONHASHSEED 下跑探针，返回 stdout（逐回合指纹）。"""
    env = {
        **os.environ,
        "PYTHONHASHSEED": pythonhashseed,
        "PROBE_SEED": str(seed),
        "PROBE_TURNS": str(turns),
    }
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"探针退出码 {proc.returncode}\n--- stderr ---\n{proc.stderr[-3000:]}"
    )
    return proc.stdout


class TestCrossProcessDeterminism:
    """同 seed 在不同 PYTHONHASHSEED 进程下，逐回合指纹必须一致。"""

    def test_two_pythonhashseeds_identical(self):
        """PS=0 vs PS=1：整局指纹序列逐字节一致"""
        out_a = _run_probe("0")
        out_b = _run_probe("1")
        assert out_a.strip(), "探针无输出——未真正跑局"
        assert out_a == out_b, (
            "跨进程不一致：同 seed 在 PYTHONHASHSEED=0/1 下指纹分叉\n"
            f"--- PS=0 ---\n{out_a}\n--- PS=1 ---\n{out_b}"
        )

    def test_third_pythonhashseed_identical(self):
        """PS=0 vs PS=12345：再加一个种子值巩固"""
        out_a = _run_probe("0")
        out_c = _run_probe("12345")
        assert out_a == out_c, (
            "跨进程不一致：PYTHONHASHSEED=0 vs 12345 指纹分叉\n"
            f"--- PS=0 ---\n{out_a}\n--- PS=12345 ---\n{out_c}"
        )

    def test_probe_actually_ran_full_game(self):
        """探针确实跑满回合（防止空跑导致上面的等式平凡成立）"""
        out = _run_probe("0")
        lines = [ln for ln in out.splitlines() if ln.startswith("T")]
        assert len(lines) == TURNS, f"预期 {TURNS} 条回合指纹，实得 {len(lines)}"
        assert "END|" in out

    def test_fingerprint_is_sensitive_to_seed(self):
        """🔴 自检：换 game seed 后指纹必须不同（否则守卫测试是假绿）"""
        out_42 = _run_probe("0", seed=42)
        out_43 = _run_probe("0", seed=43)
        assert out_42 != out_43, (
            "不同 seed 得到相同指纹——指纹退化为常量，守卫测试无效"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
