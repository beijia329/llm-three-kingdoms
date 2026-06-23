"""回放播放器

从游戏日志加载并播放回放。
支持：播放、暂停、快进、进度条跳转。

参考设计文档：docs/design/architecture.md
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import pygame

from game.constants import MAP_WIDTH, FACTIONS
from game.engine import GameEngine

logger = logging.getLogger(__name__)


class ReplayPlayer:
    """回放播放器

    从保存的游戏日志恢复并播放回放。
    """

    def __init__(self, replay_path: str) -> None:
        """初始化回放播放器

        Args:
            replay_path: 回放文件路径
        """
        self.replay_path = replay_path
        self.engine: Optional[GameEngine] = None
        self.turn_snapshots: List[Dict[str, Any]] = []
        self.current_turn_index: int = 0
        self.playing: bool = False
        self.play_speed: float = 1.0

        self._load_replay()

    def _load_replay(self) -> None:
        """加载回放文件"""
        if not os.path.exists(self.replay_path):
            raise FileNotFoundError(f"回放文件不存在: {self.replay_path}")

        with open(self.replay_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.turn_snapshots = data.get("turns", [])
        logger.info("加载回放: %d 个回合", len(self.turn_snapshots))

    def get_current_turn(self) -> int:
        """获取当前回合数

        Returns:
            当前回合
        """
        if self.current_turn_index < len(self.turn_snapshots):
            return self.turn_snapshots[self.current_turn_index].get("turn", 1)
        return 1

    def get_total_turns(self) -> int:
        """获取总回合数

        Returns:
            总回合数
        """
        return len(self.turn_snapshots)

    def play(self) -> None:
        """开始播放"""
        self.playing = True

    def pause(self) -> None:
        """暂停播放"""
        self.playing = False

    def toggle_play(self) -> None:
        """切换播放/暂停"""
        self.playing = not self.playing

    def next_turn(self) -> bool:
        """前进到下一回合

        Returns:
            是否成功前进
        """
        if self.current_turn_index < len(self.turn_snapshots) - 1:
            self.current_turn_index += 1
            return True
        self.playing = False
        return False

    def prev_turn(self) -> bool:
        """后退到上一回合

        Returns:
            是否成功后退
        """
        if self.current_turn_index > 0:
            self.current_turn_index -= 1
            return True
        return False

    def go_to_turn(self, turn: int) -> bool:
        """跳转到指定回合

        Args:
            turn: 目标回合

        Returns:
            是否成功跳转
        """
        for i, snap in enumerate(self.turn_snapshots):
            if snap.get("turn") == turn:
                self.current_turn_index = i
                return True
        return False

    def get_progress(self) -> float:
        """获取播放进度

        Returns:
            进度 0.0-1.0
        """
        if not self.turn_snapshots:
            return 0.0
        return self.current_turn_index / len(self.turn_snapshots)

    def set_speed(self, speed: float) -> None:
        """设置播放速度

        Args:
            speed: 速度倍率
        """
        self.play_speed = max(0.5, min(4.0, speed))

    def render_controls(self, surface: pygame.Surface) -> None:
        """渲染播放控制条

        Args:
            surface: 目标表面
        """
        y = surface.get_height() - 40
        font = pygame.font.SysFont("simsun", 14)

        # 进度条背景
        bar_width = surface.get_width() - 40
        pygame.draw.rect(surface, (60, 60, 70), (20, y, bar_width, 8))

        # 进度条
        progress = self.get_progress()
        filled_width = int(bar_width * progress)
        pygame.draw.rect(surface, (100, 150, 200), (20, y, filled_width, 8))

        # 控制按钮
        button_text = "⏸" if self.playing else "▶"
        btn = font.render(button_text, True, (200, 200, 200))
        surface.blit(btn, (20, y - 22))

        # 回合信息
        turn_text = f"第 {self.get_current_turn()}/{self.get_total_turns()} 回合"
        text = font.render(turn_text, True, (200, 200, 200))
        surface.blit(text, (50, y - 22))

        # 速度
        speed_text = f"x{self.play_speed:.1f}"
        st = font.render(speed_text, True, (150, 150, 150))
        surface.blit(st, (surface.get_width() - 60, y - 22))
