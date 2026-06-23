#!/usr/bin/env python3
"""LLM三国志 - 程序入口

运行方式：
    python main.py                          # CLI自动对战
    python main.py --mode ai-vs-ai          # AI对战
    python main.py --mode human-vs-ai       # 人机对战（TODO）
    python main.py --mode replay --file x.json  # 观看回放（TODO）

参考设计文档：
    - docs/design/architecture.md
    - docs/specs/deployment-guide.md
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.engine import GameEngine
from game.data_loader import load_game_data
from game.constants import FACTIONS
from game.random import GameRandom
from players.cli_player import CLIPlayer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="LLM三国志 - 多模型策略对战平台"
    )
    parser.add_argument(
        "--mode",
        choices=["ai-vs-ai", "human-vs-ai", "replay"],
        default="ai-vs-ai",
        help="运行模式",
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--file", type=str, help="回放文件路径")
    parser.add_argument("--max-turns", type=int, default=24, help="最大回合数")
    return parser.parse_args()


def run_ai_vs_ai(seed: int = 42, max_turns: int = 24) -> None:
    """运行 AI vs AI 自动对战

    Args:
        seed: 随机种子
        max_turns: 最大回合数
    """
    print("=" * 60)
    print("  LLM三国志 - AI vs AI 自动对战")
    print("=" * 60)

    # 初始化引擎
    engine = GameEngine(seed=seed)
    engine.max_turns = max_turns
    data = load_game_data()
    if not data["cities"]:
        logger.error("无法加载游戏数据，请确保 data/ 目录下有 cities.json 和 generals.json")
        sys.exit(1)
    engine.init_game(data)

    # 创建 AI 玩家
    rng = GameRandom(seed + 1)
    players = {
        faction: CLIPlayer(faction=faction, rng=GameRandom(seed + hash(faction) % 10000))
        for faction in FACTIONS
    }

    print(f"\n初始状态: {len(engine.cities)} 城市, {len(engine.generals)} 将领")
    print(f"势力分布:")
    for f_name, f_label in FACTIONS.items():
        count = engine.map.get_faction_cities(f_name)
        print(f"  {f_label}: {len(count)} 城")

    print("\n--- 战斗开始 ---\n")

    # 游戏主循环
    while not engine.game_over:
        turn = engine.turn
        print(f"\n📅 第 {turn} 回合")

        # 每个玩家轮流执行命令
        for faction in FACTIONS:
            obs = engine.get_observation(faction)
            player = players[faction]
            commands = player.get_commands(obs)

            for cmd in commands:
                result = engine.execute_command(cmd)
                if result.success:
                    print(f"  [{FACTIONS[faction]}] {result.description}")
                else:
                    logger.debug("命令失败: %s - %s", cmd.type, result.description)

        # 处理回合
        turn_result = engine.process_turn()
        print(f"  → 回合结束: "
              f"🏙️{sum(1 for c in engine.cities.values() if c.faction=='wei')}魏 "
              f"{sum(1 for c in engine.cities.values() if c.faction=='shu')}蜀 "
              f"{sum(1 for c in engine.cities.values() if c.faction=='wu')}吴 "
              f"⚔️{turn_result['battles_fought']}场战斗"
        )

        if engine.game_over:
            break

    # 游戏结束
    print("\n" + "=" * 60)
    print(f"  🏆 游戏结束！第 {engine.turn} 回合")
    if engine.winner:
        winner_name = FACTIONS.get(engine.winner, engine.winner)
        print(f"  胜利者: {winner_name}")
    else:
        print("  结果: 平局！")

    # 最终统计
    print("\n最终势力分布:")
    for f_name, f_label in FACTIONS.items():
        count = engine.map.get_faction_cities(f_name)
        print(f"  {f_label}: {len(count)} 城")
    print("=" * 60)


def main() -> None:
    """主入口"""
    args = parse_args()

    if args.mode == "ai-vs-ai":
        run_ai_vs_ai(seed=args.seed, max_turns=args.max_turns)
    elif args.mode == "human-vs-ai":
        print("人机对战模式尚在开发中...")
    elif args.mode == "replay":
        print("回放模式尚在开发中...")


if __name__ == "__main__":
    main()
