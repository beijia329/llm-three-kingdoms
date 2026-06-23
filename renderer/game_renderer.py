"""游戏主渲染器

Pygame GUI 主框架，管理窗口、主循环、事件处理和帧率控制。
负责协调地图渲染和UI面板的显示。
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
WINDOW_WIDTH = MAP_WIDTH + 300
WINDOW_HEIGHT = MAP_HEIGHT
FPS = 30

# 颜色
COLOR_BG = (20, 20, 30)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_GRAY = (100, 100, 100)
COLOR_DARK_GRAY = (40, 40, 50)
COLOR_GOLD = (255, 215, 0)
COLOR_RED = (200, 50, 50)
COLOR_GREEN = (50, 200, 50)


class GameRenderer:
    """游戏主渲染器"""

    def __init__(self, engine: GameEngine, title: str = "LLM三国志") -> None:
        pygame.init()
        self.engine = engine
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.Font(None, 14)
        self.font_medium = pygame.font.Font(None, 18)
        self.font_large = pygame.font.Font(None, 24)

        for font_name in ["PingFang SC", "STHeiti", "Noto Sans CJK SC", "SimSun"]:
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

        # 子渲染器
        self._map_renderer = None
        self._ui_panel = None
        self._hex_map_renderer = None

        # 相机
        from renderer.camera import Camera
        self.camera = Camera(x=0, y=0, zoom=1.0)

        # 中国边界
        self._china_boundaries: Optional[dict] = None
        self._load_china_boundaries()

        # 状态
        self.running = False
        self.selected_city_id: Optional[str] = None
        self.selected_faction: Optional[str] = None
        self.auto_advance: bool = False
        self.turn_delay: int = 60
        self._turn_counter: int = 0
        self._players: Optional[dict] = None

    def _load_china_boundaries(self) -> None:
        try:
            from game.data_loader import load_china_geojson
            self._china_boundaries = load_china_geojson()
            logger.info("中国边界: %d 省", len(self._china_boundaries.get("features", [])))
        except Exception as e:
            logger.warning("边界加载失败: %s", e)
            self._china_boundaries = None

    @property
    def map_renderer(self):
        if self._map_renderer is None:
            if getattr(self.engine, 'hex_map', None) is not None:
                try:
                    from renderer.hex_map_renderer import HexMapRenderer
                    self._hex_map_renderer = HexMapRenderer(self.engine.hex_map)
                    if self._china_boundaries:
                        self._hex_map_renderer.set_boundaries(self._china_boundaries)
                    self._map_renderer = self._hex_map_renderer
                    logger.info("使用 HexMapRenderer")
                    return self._map_renderer
                except Exception as e:
                    logger.warning("HexMapRenderer 失败: %s", e)
            from renderer.map_renderer import MapRenderer
            self._map_renderer = MapRenderer(self.engine)
        return self._map_renderer

    @property
    def ui_panel(self):
        if self._ui_panel is None:
            from renderer.ui_panel import UIPanel
            self._ui_panel = UIPanel(self.engine, self)
        return self._ui_panel

    def run(self, players: Optional[dict] = None, auto_run: bool = True) -> None:
        self.running = True
        self._players = players

        while self.running:
            for event in pygame.event.get():
                self._handle_event(event)

            should_auto = (auto_run or self.auto_advance)
            if should_auto and not self.engine.game_over and players:
                self._turn_counter += 1
                if self._turn_counter >= self.turn_delay:
                    self._turn_counter = 0
                    self._run_turn(players)

            self.screen.fill(COLOR_BG)

            if self._hex_map_renderer is not None:
                self._hex_map_renderer.render(
                    self.screen,
                    camera_offset=(self.camera.x, self.camera.y),
                    camera_zoom=self.camera.zoom,
                )
                self._hex_map_renderer.render_cities(
                    self.screen, self.engine.cities,
                    font=self.font_small,
                    camera_offset=(self.camera.x, self.camera.y),
                    camera_zoom=self.camera.zoom,
                )
                self._hex_map_renderer.render_armies(
                    self.screen, self.engine.armies, self.engine.cities,
                    camera_offset=(self.camera.x, self.camera.y),
                    camera_zoom=self.camera.zoom,
                )

            self.ui_panel.render(self.screen, selected_city_id=self.selected_city_id)

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

    def _run_turn(self, players: dict) -> None:
        for faction in FACTIONS:
            obs = self.engine.get_observation(faction)
            player = players.get(faction)
            if player:
                for cmd in player.get_commands(obs):
                    self.engine.execute_command(cmd)
        result = self.engine.process_turn()
        logger.info("第%d回合完成", result.get("turn"))

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif hasattr(self, 'camera') and self.camera.handle_event(event):
            pass
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_SPACE:
                if self._players:
                    self._run_turn(self._players)
            elif event.key == pygame.K_a:
                self.auto_advance = not self.auto_advance
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._handle_click(event.pos)

    def _handle_click(self, pos: tuple) -> None:
        x, y = pos
        if x < MAP_WIDTH:
            if hasattr(self, '_hex_map_renderer') and self._hex_map_renderer:
                # TODO: hex click detection via pixel_to_axial
                pass
            else:
                clicked_city = self.map_renderer.get_city_at_pos(x, y)
                if clicked_city:
                    self.selected_city_id = clicked_city
        else:
            self.ui_panel.handle_click(x, y)

    def update_engine(self, engine: GameEngine) -> None:
        self.engine = engine
        self._map_renderer = None
        self._ui_panel = None

    def render_text(self, surface, text, pos, color=COLOR_WHITE, font=None):
        if font is None:
            font = self.font_medium
        text_surface = font.render(text, True, color)
        rect = text_surface.get_rect(topleft=pos)
        surface.blit(text_surface, rect)
        return rect
