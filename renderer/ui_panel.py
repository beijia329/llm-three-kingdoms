"""UI面板

显示游戏信息：势力概览、城市详情、事件日志、外交消息。
位于地图右侧。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pygame

from game.constants import MAP_WIDTH, FACTIONS, FACTION_COLORS
from game.engine import GameEngine


# 面板区域
PANEL_X = MAP_WIDTH + 10
PANEL_WIDTH = 280
PANEL_Y = 10

# 颜色
COLOR_BG = (25, 25, 35)
COLOR_HEADER = (200, 180, 100)
COLOR_TEXT = (220, 220, 220)
COLOR_SUBTEXT = (150, 150, 150)
COLOR_BORDER = (60, 60, 70)
COLOR_HIGHLIGHT = (100, 150, 200)


class UIPanel:
    """UI信息面板

    显示势力信息、城市详情、事件日志等。
    """

    def __init__(self, engine: GameEngine, renderer) -> None:
        """初始化UI面板

        Args:
            engine: 游戏引擎
            renderer: 主渲染器引用
        """
        self.engine = engine
        self.renderer = renderer

        # 字体
        self.font_small = pygame.font.Font(None, 12)
        self.font_medium = pygame.font.Font(None, 14)
        self.font_header = pygame.font.Font(None, 16)

        # 尝试加载中文字体
        for font_name in ["simsun", "SimSun", "Noto Sans CJK SC", "PingFang SC", "STHeiti"]:
            try:
                test_font = pygame.font.SysFont(font_name, 12)
                if test_font and test_font.render("测", True, (255, 255, 255)).get_width() > 0:
                    self.font_small = pygame.font.SysFont(font_name, 12)
                    self.font_medium = pygame.font.SysFont(font_name, 14)
                    self.font_header = pygame.font.SysFont(font_name, 16)
                    break
            except Exception:
                continue

        # 状态
        self.active_tab = "info"  # info / city / log
        self.scroll_offset = 0

        # 缓存的日志
        self._cached_logs: List[str] = []

    # ============================================================
    # 主渲染入口
    # ============================================================

    def render(
        self,
        surface: pygame.Surface,
        selected_city_id: Optional[str] = None,
    ) -> None:
        """渲染UI面板

        Args:
            surface: 目标表面
            selected_city_id: 选中的城市ID
        """
        # 背景
        pygame.draw.rect(
            surface, COLOR_BG,
            (MAP_WIDTH, 0, PANEL_WIDTH, surface.get_height()),
        )
        pygame.draw.line(
            surface, COLOR_BORDER,
            (MAP_WIDTH, 0), (MAP_WIDTH, surface.get_height()), 2,
        )

        # 回合信息（顶部）
        self._render_turn_info(surface)

        # 标签页按钮
        self._render_tabs(surface)

        # 标签内容
        if self.active_tab == "info":
            self._render_faction_info(surface)
        elif self.active_tab == "city" and selected_city_id:
            self._render_city_detail(surface, selected_city_id)
        elif self.active_tab == "log":
            self._render_event_log(surface)

        # 底部状态栏
        self._render_status_bar(surface)

    # ============================================================
    # 回合信息
    # ============================================================

    def _render_turn_info(self, surface: pygame.Surface) -> None:
        """渲染回合信息

        Args:
            surface: 目标表面
        """
        y = PANEL_Y

        # 季节与年份
        if hasattr(self.engine, 'season') and hasattr(self.engine, 'year'):
            season_names = {"spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬"}
            season_cn = season_names.get(
                self.engine.season.value if hasattr(self.engine.season, 'value')
                else str(self.engine.season), ""
            )
            year_text = f"{self.engine.year}年"
            self._draw_text(surface, year_text, (PANEL_X, y), COLOR_SUBTEXT, self.font_small)
        else:
            season_cn = ""

        # 回合数
        if hasattr(self.engine, 'game_mode') and str(self.engine.game_mode) == "infinite":
            turn_text = f"第 {self.engine.turn} 回合 {season_cn}"
        else:
            turn_text = f"第 {self.engine.turn}/{self.engine.max_turns} 回合 {season_cn}"
        self._draw_text(surface, turn_text.strip(), (PANEL_X, y + 16), COLOR_HEADER, self.font_header)

        if self.engine.game_over:
            if self.engine.winner:
                winner_name = FACTIONS.get(self.engine.winner, self.engine.winner)
                self._draw_text(
                    surface, f"🏆 {winner_name} 胜利!",
                    (PANEL_X, y + 40), (255, 215, 0), self.font_medium,
                )
            else:
                self._draw_text(
                    surface, "平局!", (PANEL_X, y + 40),
                    (200, 200, 100), self.font_medium,
                )

    # ============================================================
    # 标签页
    # ============================================================

    def _render_tabs(self, surface: pygame.Surface) -> None:
        """渲染标签页按钮

        Args:
            surface: 目标表面
        """
        y = 55
        tabs = [("info", "势力"), ("city", "城市"), ("log", "日志")]
        x = PANEL_X

        for tab_id, tab_name in tabs:
            is_active = self.active_tab == tab_id
            color = COLOR_HIGHLIGHT if is_active else COLOR_BORDER
            text_color = COLOR_HEADER if is_active else COLOR_SUBTEXT

            rect = pygame.Rect(x, y, 85, 24)
            pygame.draw.rect(surface, color, rect, 1 if not is_active else 0)
            if is_active:
                pygame.draw.rect(surface, color, rect)

            self._draw_text_centered(surface, tab_name, rect, text_color, self.font_small)
            x += 92

    def handle_click(self, x: int, y: int) -> None:
        """处理面板内的点击

        Args:
            x: 横坐标
            y: 纵坐标
        """
        # 标签页切换
        tab_y = 55
        if tab_y <= y <= tab_y + 24:
            if PANEL_X <= x <= PANEL_X + 85:
                self.active_tab = "info"
            elif PANEL_X + 92 <= x <= PANEL_X + 177:
                self.active_tab = "city"
            elif PANEL_X + 184 <= x <= PANEL_X + 269:
                self.active_tab = "log"

    # ============================================================
    # 势力概览
    # ============================================================

    def _render_faction_info(self, surface: pygame.Surface) -> None:
        """渲染势力信息

        Args:
            surface: 目标表面
        """
        y = 90

        for f_id, f_name in FACTIONS.items():
            cities = [
                c for c in self.engine.cities.values()
                if c.faction == f_id
            ]
            generals = [
                g for g in self.engine.generals.values()
                if g.faction == f_id and not g.is_captured
            ]

            if not cities:
                text = f"{f_name}: ❌ 已灭亡"
                self._draw_text(surface, text, (PANEL_X, y), (150, 50, 50), self.font_medium)
                y += 22
                continue

            # 势力名+城市数
            color_hex = FACTION_COLORS.get(f_id, "#888888")
            color_rgb = self._hex_to_rgb(color_hex)
            stats = f"{f_name}: {len(cities)}城 {sum(c.garrison for c in cities)}兵"
            self._draw_text(surface, stats, (PANEL_X, y), color_rgb, self.font_medium)
            y += 20

            # 细节
            total_gold = sum(c.gold for c in cities)
            total_food = sum(c.food for c in cities)
            total_pop = sum(c.population for c in cities)
            detail = f"💰{total_gold} 🌾{total_food} 👥{total_pop}"
            self._draw_text(surface, detail, (PANEL_X + 5, y), COLOR_SUBTEXT, self.font_small)
            y += 16

            # 将领
            gen_names = ", ".join(g.name for g in generals[:3])
            if gen_names:
                self._draw_text(
                    surface, f"将: {gen_names}",
                    (PANEL_X + 5, y), COLOR_SUBTEXT, self.font_small,
                )
                y += 16

            y += 8

    # ============================================================
    # 城市详情
    # ============================================================

    def _render_city_detail(
        self, surface: pygame.Surface, city_id: str,
    ) -> None:
        """渲染城市详情

        Args:
            surface: 目标表面
            city_id: 城市ID
        """
        city = self.engine.cities.get(city_id)
        if city is None:
            self._draw_text(surface, "城市不存在", (PANEL_X, 90), COLOR_TEXT, self.font_medium)
            return

        y = 90

        # 城市名+势力
        color_hex = FACTION_COLORS.get(city.faction, "#888888")
        color_rgb = self._hex_to_rgb(color_hex)
        self._draw_text(surface, f"🏙️ {city.name}", (PANEL_X, y), color_rgb, self.font_header)
        y += 28

        # 基本信息
        items = [
            (f"等级: {city.level}级", ""),
            (f"城墙: {city.wall_hp}/{city.wall_max_hp}", ""),
            (f"金钱: {city.gold}", "💰"),
            (f"粮草: {city.food}", "🌾"),
            (f"人口: {city.population}", "👥"),
            (f"民心: {city.morale}", "❤️"),
            (f"守军: {city.garrison}", "🛡️"),
        ]

        for label, icon in items:
            text = f"{icon} {label}" if icon else label
            self._draw_text(surface, text, (PANEL_X + 5, y), COLOR_TEXT, self.font_small)
            y += 18

        # 将领
        if city.generals:
            self._draw_text(surface, "驻守将领:", (PANEL_X + 5, y), COLOR_HEADER, self.font_small)
            y += 16
            for gen_id in city.generals[:5]:
                gen = self.engine.generals.get(gen_id)
                if gen:
                    self._draw_text(
                        surface, f"  {gen.name} (忠:{gen.loyalty})",
                        (PANEL_X + 10, y), COLOR_SUBTEXT, self.font_small,
                    )
                    y += 14

        # 围城信息
        if city.is_besieged:
            y += 4
            self._draw_text(
                surface, "⚠️ 被围困中!",
                (PANEL_X + 5, y), (200, 100, 50), self.font_small,
            )

    # ============================================================
    # 事件日志
    # ============================================================

    def _render_event_log(self, surface: pygame.Surface) -> None:
        """渲染事件日志

        Args:
            surface: 目标表面
        """
        y = 90

        # 获取最近的turn_logs
        logs = self.engine.turn_logs[-20:] if self.engine.turn_logs else []

        if not logs:
            self._draw_text(surface, "暂无事件", (PANEL_X, y), COLOR_SUBTEXT, self.font_small)
            return

        for log in reversed(logs):
            turn = log.turn
            self._draw_text(
                surface, f"=== 第{turn}回合 ===",
                (PANEL_X, y), COLOR_HEADER, self.font_small,
            )
            y += 16

            # 显示回合摘要
            # 显示回合摘要
            for event in log.events:
                if isinstance(event, dict):
                    battles = event.get("battles_fought", 0)
                    armies_moved = event.get("armies_moved", 0)
                    game_over = event.get("game_over", False)
                    winner = event.get("winner")

                    if battles > 0:
                        self._draw_text(
                            surface, f"  ⚔️ {battles}场战斗",
                            (PANEL_X + 5, y), (200, 150, 100), self.font_small,
                        )
                        y += 14
                    if armies_moved > 0:
                        self._draw_text(
                            surface, f"  🚩 {armies_moved}支军队移动",
                            (PANEL_X + 5, y), (150, 150, 150), self.font_small,
                        )
                        y += 14
                    if game_over and winner:
                        winner_name = FACTIONS.get(winner, winner)
                        self._draw_text(
                            surface, f"  🏆 {winner_name}获胜!",
                            (PANEL_X + 5, y), (255, 215, 0), self.font_small,
                        )
                        y += 14

            y += 6
            if y > 560:
                break

    def _render_status_bar(self, surface: pygame.Surface) -> None:
        """渲染底部状态栏

        Args:
            surface: 目标表面
        """
        bar_y = surface.get_height() - 24
        pygame.draw.line(
            surface, COLOR_BORDER,
            (MAP_WIDTH, bar_y), (MAP_WIDTH + PANEL_WIDTH, bar_y), 1,
        )

        # 自动推进状态
        if self.renderer.auto_advance:
            status_text = "▶ 自动推进 (A关)"
            status_color = (50, 200, 50)
        else:
            status_text = "⏸ 手动模式 (A开)"
            status_color = (150, 150, 150)

        self._draw_text(
            surface, status_text,
            (PANEL_X + 5, bar_y + 4), status_color, self.font_small,
        )

    # ============================================================
    # 工具方法
    # ============================================================

    def _draw_text(
        self, surface: pygame.Surface, text: str,
        pos: tuple, color: tuple, font: pygame.font.Font,
    ) -> None:
        """绘制文本

        Args:
            surface: 目标表面
            text: 文本
            pos: (x, y)
            color: RGB颜色
            font: 字体
        """
        text_surface = font.render(text, True, color)
        surface.blit(text_surface, pos)

    def _draw_text_centered(
        self, surface: pygame.Surface, text: str,
        rect: pygame.Rect, color: tuple, font: pygame.font.Font,
    ) -> None:
        """居中绘制文本

        Args:
            surface: 目标表面
            text: 文本
            rect: 矩形区域
            color: RGB颜色
            font: 字体
        """
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect(center=rect.center)
        surface.blit(text_surface, text_rect)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        """十六进制颜色转RGB

        Args:
            hex_color: #RRGGBB格式

        Returns:
            (R, G, B)元组
        """
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
