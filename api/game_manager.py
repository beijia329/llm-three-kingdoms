"""游戏会话管理器

管理一个 GameEngine 实例，处理前端命令与状态序列化。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from game.constants import FACTIONS
from game.data_loader import load_game_data
from game.engine import GameEngine
from game.models import (
    AttackCommand,
    Command,
    DevelopCommand,
    ExploreCommand,
    MessageCommand,
    RecruitCommand,
    RewardCommand,
    RumorCommand,
)
from game.random import GameRandom
from players.cli_player import CLIPlayer

logger = logging.getLogger(__name__)


@dataclass
class GameConfig:
    """游戏配置"""

    seed: int = 42
    max_turns: int = 192
    game_mode: str = "standard"
    human_faction: Optional[str] = None


class GameManager:
    """游戏会话管理器

    封装单个 GameEngine 实例，提供前端友好的接口：
    - 初始化游戏
    - 执行命令
    - 推进回合
    - 获取可序列化状态
    """

    def __init__(self, config: Optional[GameConfig] = None) -> None:
        """初始化游戏管理器

        Args:
            config: 游戏配置，默认标准模式 seed=42
        """
        self.config = config or GameConfig()
        self.engine: Optional[GameEngine] = None
        self._players: Dict[str, CLIPlayer] = {}
        self._events: List[Dict[str, Any]] = []
        self._init_engine()

    def _init_engine(self) -> None:
        """初始化游戏引擎与 AI 玩家"""
        self.engine = GameEngine(seed=self.config.seed)
        self.engine.max_turns = self.config.max_turns

        if self.config.game_mode == "infinite":
            from game.game_mode import GameMode
            self.engine.game_mode = GameMode.INFINITE
            self.engine.max_turns = 9999

        data = load_game_data()
        if not data.get("cities"):
            raise RuntimeError("无法加载游戏数据")
        self.engine.init_game(data)

        # 创建 CLI AI 玩家（人类势力如有则不创建 AI）
        self._players = {}
        for faction in FACTIONS:
            if faction == self.config.human_faction:
                continue
            self._players[faction] = CLIPlayer(
                faction=faction,
                rng=GameRandom(self.config.seed + hash(faction) % 10000),
            )

        self._add_event("游戏开始：184年 黄巾之乱", "info")
        logger.info("GameManager 初始化完成: seed=%s, mode=%s", self.config.seed, self.config.game_mode)

    # ============================================================
    # 状态序列化
    # ============================================================

    def get_state(self) -> Dict[str, Any]:
        """获取当前游戏状态（JSON 可序列化）

        Returns:
            包含 cities、armies、generals、turn、game_over 等字段的字典
        """
        if self.engine is None:
            return {}

        snapshot = self.engine.get_state_snapshot()
        data = snapshot.model_dump(mode="json")

        # 补充 factions 列表与统计
        faction_stats = {}
        for fid, fname in FACTIONS.items():
            cities = [c for c in self.engine.cities.values() if c.faction == fid]
            faction_stats[fid] = {
                "name": fname,
                "cities": len(cities),
                "garrison": sum(c.garrison for c in cities),
                "gold": sum(c.gold for c in cities),
                "food": sum(c.food for c in cities),
                "population": sum(c.population for c in cities),
            }

        # 补充六角格地图（用于前端地形渲染）
        hex_tiles = []
        if self.engine.hex_map is not None:
            for tile in self.engine.hex_map.iter_tiles():
                hex_tiles.append({
                    "q": tile.coord.q,
                    "r": tile.coord.r,
                    "terrain": tile.terrain.value if hasattr(tile.terrain, 'value') else str(tile.terrain),
                    "faction": tile.faction,
                    "owner_city_id": tile.owner_city_id,
                })

        # max_turns / year 现在由 GameState 模型自动序列化（B-03 修复后）
        data["faction_stats"] = faction_stats
        data["events"] = list(self._events[-20:])
        data["human_faction"] = self.config.human_faction
        data["hex_map"] = {
            "width": self.engine.hex_map.width if self.engine.hex_map else 0,
            "height": self.engine.hex_map.height if self.engine.hex_map else 0,
            "tiles": hex_tiles,
        }
        return data

    # ============================================================
    # 命令执行
    # ============================================================

    def execute_command(self, cmd_dict: Dict[str, Any]) -> Dict[str, Any]:
        """执行一个命令

        Args:
            cmd_dict: 前端传来的命令字典，必须包含 type/faction/turn/params

        Returns:
            执行结果摘要
        """
        if self.engine is None:
            return {"success": False, "error": "引擎未初始化"}

        try:
            command = self._deserialize_command(cmd_dict)
            result = self.engine.execute_command(command)
            return {
                "success": result.success,
                "type": result.command_type,
                "description": result.description,
                "data": result.data,
            }
        except Exception as e:
            logger.exception("命令执行失败: %s", cmd_dict)
            return {"success": False, "error": str(e)}

    @staticmethod
    def _deserialize_command(cmd_dict: Dict[str, Any]) -> Command:
        """将前端命令字典反序列化为 Command 对象"""
        cmd_type = cmd_dict.get("type", "")
        faction = cmd_dict.get("faction", "")
        turn = cmd_dict.get("turn", 1)
        params = cmd_dict.get("params", {})

        if cmd_type == "develop":
            return DevelopCommand(
                faction=faction, turn=turn,
                city=params["city"], develop_type=params["develop_type"],
            )
        elif cmd_type == "recruit":
            return RecruitCommand(
                faction=faction, turn=turn,
                city=params["city"], troops=params["troops"],
            )
        elif cmd_type == "attack":
            return AttackCommand(
                faction=faction, turn=turn,
                from_city=params["from_city"], to_city=params["to_city"],
                troops=params["troops"], general=params["general"],
            )
        elif cmd_type == "reward":
            return RewardCommand(
                faction=faction, turn=turn,
                general=params["general"], gold=params["gold"],
            )
        elif cmd_type == "explore":
            return ExploreCommand(
                faction=faction, turn=turn,
                city=params["city"], general=params.get("general"),
            )
        elif cmd_type == "message":
            return MessageCommand(
                faction=faction, turn=turn,
                to=params["to"], content=params["content"],
            )
        elif cmd_type == "rumor":
            return RumorCommand(
                faction=faction, turn=turn,
                city=params["city"],
                target_general=params.get("target_general"),
                spy_general=params.get("spy_general"),
            )
        else:
            return Command(type=cmd_type, faction=faction, turn=turn, params=params)

    # ============================================================
    # 回合推进
    # ============================================================

    def process_turn(self) -> Dict[str, Any]:
        """推进一回合（执行 AI 命令 + 引擎回合处理）

        Returns:
            回合结果摘要
        """
        if self.engine is None:
            return {"error": "引擎未初始化"}

        # 执行 AI 玩家命令
        ai_events = []
        for faction, player in self._players.items():
            obs = self.engine.get_observation(faction)
            for cmd in player.get_commands(obs):
                result = self.engine.execute_command(cmd)
                if result.success:
                    ai_events.append({
                        "faction": faction,
                        "type": cmd.type,
                        "description": result.description,
                    })

        # 推进引擎回合
        turn_result = self.engine.process_turn()

        # 记录建国事件
        ks = getattr(self.engine, '_kingdom_system', None)
        if ks:
            for f, k in ks.get_all_kingdoms().items():
                self._add_event(f"🏰 {FACTIONS.get(f, f)} 称{k['type']}！国号【{k['name']}】", "kingdom")

        if turn_result.get("battles_fought", 0) > 0:
            self._add_event(f"第 {turn_result['turn']} 回合: {turn_result['battles_fought']} 场战斗", "battle")

        if self.engine.game_over:
            if self.engine.winner:
                w = FACTIONS.get(self.engine.winner, self.engine.winner)
                self._add_event(f"🏆 {w} 一统天下！", "victory")
            else:
                self._add_event("游戏结束：平局", "victory")

        return {
            "turn": turn_result.get("turn"),
            "battles_fought": turn_result.get("battles_fought", 0),
            "game_over": self.engine.game_over,
            "winner": self.engine.winner,
            "ai_events": ai_events,
        }

    def run_ai_only_turns(self, max_turns: int = 1) -> List[Dict[str, Any]]:
        """连续运行若干纯 AI 回合（观战/回放模式用）

        Args:
            max_turns: 最大执行回合数

        Returns:
            每回合结果列表
        """
        results = []
        for _ in range(max_turns):
            if self.engine is None or self.engine.game_over:
                break
            results.append(self.process_turn())
        return results

    def _add_event(self, text: str, event_type: str = "info") -> None:
        """添加事件日志"""
        self._events.append({
            "turn": self.engine.turn if self.engine else 0,
            "type": event_type,
            "text": text,
        })
