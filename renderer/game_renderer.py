"""游戏主渲染器

Pygame GUI 主框架，管理窗口、主循环、事件处理和帧率控制。
负责协调地图渲染和UI面板的显示。

参考设计文档：docs/design/architecture.md
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

import pygame

from game.constants import MAP_WIDTH, MAP_HEIGHT, FACTIONS, FACTION_COLORS
from game.engine import GameEngine

logger = logging.getLogger(__name__)

# 窗口尺寸
WINDOW_WIDTH = MAP_WIDTH + 300  # 地图 + 侧边栏
WINDOW_HEIGHT = MAP_HEIGHT
FPS = 30

# 颜色
COLOR_BG = (20, 20, 30)  # 深色背景
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_GRAY = (100, 100, 100)
COLOR_DARK_GRAY = (40, 40, 50)
COLOR_GOLD = (255, 215, 0)
COLOR_RED = (200, 50, 50)
COLOR_GREEN = (50, 200, 50)


class GameRenderer:
    """游戏主渲染器

    管理Pygame窗口和主循环，协调地图渲染器和UI面板。
    """

    def __init__(self, engine: GameEngine, title: str = "LLM三国志") -> None:
        """初始化渲染器

        Args:
            engine: 游戏引擎实例
            title: 窗口标题
        """
        pygame.init()
        self.engine = engine
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.Font(None, 14)
        self.font_medium = pygame.font.Font(None, 18)
        self.font_large = pygame.font.Font(None, 24)

        # 尝试加载中文字体
        for font_name in ["simsun", "SimSun", "Noto Sans CJK SC", "PingFang SC", "STHeiti"]:
            try:
                test_font = pygame.font.SysFont(font_name, 14)
                if test_font and test_font.render("测", True, (255, 255, 255)).get_width() > 0:
                    self.font_small = pygame.font.SysFont(font_name, 14)
                    self.font_medium = pygame.font.SysFont(font_name, 18)
                    self.font_large = pygame.font.SysFont(font_name, 24)
                    break
            except Exception:
                continue

        pygame.display.set_caption(title)

        # 子渲染器（懒加载）
        self._map_renderer = None
        self._ui_panel = None

        # 状态
        self.running = False
        self.selected_city_id: Optional[str] = None
        self.selected_faction: Optional[str] = None
        self.auto_advance: bool = False
        self.turn_delay: int = 60  # 自动推进的帧数延迟
        self._turn_counter: int = 0
        self._players: Optional[dict] = None  # 玩家字典（用于SPACE/A键触发回合）

    @property
    def map_renderer(self):
        """地图渲染器（懒加载）"""
        if self._map_renderer is None:
            from renderer.map_renderer import MapRenderer
            self._map_renderer = MapRenderer(self.engine)
        return self._map_renderer

    @property
    def ui_panel(self):
        """UI面板（懒加载）"""
        if self._ui_panel is None:
            from renderer.ui_panel import UIPanel
            self._ui_panel = UIPanel(self.engine, self)
        return self._ui_panel

    # ============================================================
    # 主循环
    # ============================================================

    def run(
        self,
        players: Optional[dict] = None,
        auto_run: bool = True,
    ) -> None:
        """运行游戏主循环

        Args:
            players: 玩家字典 {faction: player}
            auto_run: 是否自动运行（非交互式）
        """
        self.running = True
        self._players = players

        while self.running:
            for event in pygame.event.get():
                self._handle_event(event)

            # 自动推进（auto_run 参数 或 A键切换的 auto_advance）
            should_auto = (auto_run or self.auto_advance)
            if should_auto and not self.engine.game_over and players:
                self._turn_counter += 1
                if self._turn_counter >= self.turn_delay:
                    self._turn_counter = 0
                    self._run_turn(players)

            # 清屏
            self.screen.fill(COLOR_BG)

            # 渲染地图
            self.map_renderer.render(
                self.screen,
                selected_city_id=self.selected_city_id,
                auto_advance=self.auto_advance,
            )

            # 渲染UI面板
            self.ui_panel.render(
                self.screen,
                selected_city_id=self.selected_city_id,
            )

            # 更新显示
            pygame.display.flip()

            self.clock.tick(FPS)

        pygame.quit()

    def _run_turn(self, players: dict) -> None:
        """执行一个回合

        Args:
            players: 玩家字典
        """
        for faction in FACTIONS:
            obs = self.engine.get_observation(faction)
            player = players.get(faction)
            if player:
                commands = player.get_commands(obs)
                for cmd in commands:
                    self.engine.execute_command(cmd)

        result = self.engine.process_turn()
        logger.info("第%d回合完成", result.get("turn"))

    def _handle_event(self, event: pygame.event.Event) -> None:
        """处理输入事件

        Args:
            event: Pygame事件
        """
        if event.type == pygame.QUIT:
            self.running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_SPACE:
                # 空格键手动推进一回合
                if self._players:
                    self._run_turn(self._players)
            elif event.key == pygame.K_a:
                # A键切换自动推进
                self.auto_advance = not self.auto_advance
                logger.info("自动推进: %s", "开" if self.auto_advance else "关")

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # 左键
                self._handle_click(event.pos)

    def _handle_click(self, pos: tuple) -> None:
        """处理鼠标点击

        Args:
            pos: 点击坐标 (x, y)
        """
        x, y = pos

        # 检查是否点击了地图区域
        if x < MAP_WIDTH:
            clicked_city = self.map_renderer.get_city_at_pos(x, y)
            if clicked_city:
                self.selected_city_id = clicked_city
                logger.debug("选中城市: %s", clicked_city)
            else:
                self.selected_city_id = None
        else:
            # 侧边栏点击由UIPanel处理
            self.ui_panel.handle_click(x, y)

    def update_engine(self, engine: GameEngine) -> None:
        """更新引擎引用（外部调用）

        Args:
            engine: 新的游戏引擎实例
        """
        self.engine = engine
        self._map_renderer = None
        self._ui_panel = None

    # ============================================================
    # 渲染
    # ============================================================

    def render(self, surface: pygame.Surface = None) -> None:
        """每帧渲染"""
        # 清屏
        self.screen.fill(COLOR_BG)

        # 渲染地图
        self.map_renderer.render(
            self.screen,
            selected_city_id=self.selected_city_id,
        )

        # 渲染UI面板
        self.ui_panel.render(
            self.screen,
            selected_city_id=self.selected_city_id,
        )

        # 更新显示
        pygame.display.flip()

    def render_text(
        self,
        surface: pygame.Surface,
        text: str,
        pos: tuple,
        color: tuple = COLOR_WHITE,
        font=None,
    ) -> pygame.Rect:
        """渲染文本

        Args:
            surface: 目标表面
            text: 文本内容
            pos: 位置 (x, y)
            color: 颜色
            font: 字体（默认使用medium）

        Returns:
            文本矩形区域
        """
        if font is None:
            font = self.font_medium
        text_surface = font.render(text, True, color)
        rect = text_surface.get_rect(topleft=pos)
        surface.blit(text_surface, rect)
        return rect
