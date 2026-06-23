"""文明风格游戏渲染器 v2

布局 (1400×850):
┌──────────────────────────────┬──────────┐
│  顶部信息栏 (半透明叠加)      │  势力    │
│                              │  总览    │
│  六角格地图主区域             │  城市    │
│  (1100×850)                  │  详情    │
│                              │  武将    │
│  底部事件滚动条              │  列表    │
└──────────────────────────────┴──────────┘
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import pygame

from game.constants import FACTIONS, FACTION_COLORS
from game.engine import GameEngine

logger = logging.getLogger(__name__)

WINDOW_W, WINDOW_H = 1400, 850
MAP_W, MAP_H = 1100, 850
PANEL_X = MAP_W + 10
PANEL_W = 290
FPS = 30

COLOR_BG = (20, 20, 30)
COLOR_PANEL_BG = (28, 28, 40)
COLOR_TEXT = (220, 220, 220)
COLOR_GOLD = (255, 215, 0)
COLOR_DIM = (120, 120, 130)
COLOR_RED = (220, 60, 60)
COLOR_GREEN = (60, 200, 60)
COLOR_BLUE = (80, 140, 220)
COLOR_WHITE = (255, 255, 255)
COLOR_OVERLAY = (0, 0, 0, 140)

# 中文字体
FONT_CJK = None
FONT_CJK_SM = None
FONT_CJK_LG = None


def _init_cjk_font():
    global FONT_CJK, FONT_CJK_SM, FONT_CJK_LG
    for name in ["PingFang SC", "STHeiti", "Heiti SC", "SimSun", "Noto Sans CJK SC"]:
        try:
            test = pygame.font.SysFont(name, 16)
            if test.render("测试", True, (255, 255, 255)).get_width() > 10:
                FONT_CJK_SM = pygame.font.SysFont(name, 13)
                FONT_CJK = pygame.font.SysFont(name, 16)
                FONT_CJK_LG = pygame.font.SysFont(name, 22)
                logger.info("中文字体: %s", name)
                return
        except Exception:
            continue
    FONT_CJK_SM = pygame.font.Font(None, 13)
    FONT_CJK = pygame.font.Font(None, 16)
    FONT_CJK_LG = pygame.font.Font(None, 22)
    logger.warning("未找到中文字体")


def draw_text(surf, text, x, y, color=COLOR_TEXT, font=None, center=False):
    """绘制文字，返回渲染后的Surface"""
    f = font or FONT_CJK
    try:
        s = f.render(str(text), True, color)
        if center:
            surf.blit(s, (x - s.get_width() // 2, y))
        else:
            surf.blit(s, (x, y))
        return s
    except Exception:
        return None


class GameRenderer:
    """文明风格游戏渲染器"""

    def __init__(self, engine: GameEngine, title: str = "LLM三国志") -> None:
        pygame.init()
        _init_cjk_font()
        self.engine = engine
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.clock = pygame.time.Clock()
        pygame.display.set_caption(title)

        # 相机
        from renderer.camera import Camera
        self.camera = Camera(x=-900, y=-500, zoom=0.3)
        self.camera.min_zoom = 0.08
        self.camera.max_zoom = 1.5
        self.camera.pan_speed = 15

        # 子渲染器
        self._hex_renderer = None
        self._init_hex_renderer()

        # 状态
        self.running = False
        self._players: Optional[dict] = None
        self._turn_counter = 0
        self.turn_delay = 45
        self.auto_advance = True
        self.selected_city_id: Optional[str] = None
        self.selected_faction: Optional[str] = None
        self.panel_tab = "factions"  # factions / city / generals / log

        # 事件日志
        self._events: list = []

    def _init_hex_renderer(self):
        try:
            from renderer.hex_map_renderer import HexMapRenderer
            self._hex_renderer = HexMapRenderer(self.engine.hex_map)
            from game.data_loader import load_china_geojson
            gj = load_china_geojson()
            self._hex_renderer.set_boundaries(gj)
            logger.info("HexMapRenderer + 中国边界 初始化完成")
        except Exception as e:
            logger.warning("HexMapRenderer 失败: %s", e)

    def add_event(self, text: str, color=COLOR_TEXT):
        self._events.append((time.time(), text, color))
        if len(self._events) > 50:
            self._events = self._events[-50:]

    # ============================================================
    # 主循环
    # ============================================================
    def run(self, players: dict = None, auto_run: bool = True):
        self.running = True
        self._players = players
        self.auto_advance = auto_run

        while self.running:
            for event in pygame.event.get():
                self._handle_event(event)

            if self.auto_advance and not self.engine.game_over and players:
                self._turn_counter += 1
                if self._turn_counter >= self.turn_delay:
                    self._turn_counter = 0
                    self._run_turn(players)

            # ——— 渲染 ———
            self.screen.fill(COLOR_BG)

            # 六角格地图
            if self._hex_renderer:
                off = (self.camera.x, self.camera.y)
                z = self.camera.zoom
                self._hex_renderer.render(self.screen, off, z)
                self._hex_renderer.render_cities(self.screen, self.engine.cities, FONT_CJK_SM, off, z)
                self._hex_renderer.render_armies(self.screen, self.engine.armies, self.engine.cities, off, z)

            # 顶部覆盖栏
            self._draw_top_bar()

            # 底部事件
            self._draw_event_ticker()

            # 右侧面板
            self._draw_panel()

            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()

    # ============================================================
    # 顶部信息栏
    # ============================================================
    def _draw_top_bar(self):
        overlay = pygame.Surface((MAP_W, 42), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        e = self.engine
        season_cn = {"spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬"}
        sn = season_cn.get(str(e.season.value) if hasattr(e.season, 'value') else str(e.season), "")

        mode = "∞" if str(getattr(e, 'game_mode', '')) == "infinite" else f"/{e.max_turns}"
        info = f"第{e.turn}{mode}回合 | {e.year}年 {sn} | 184年 黄巾之乱"
        draw_text(self.screen, info, 10, 4, COLOR_GOLD, FONT_CJK_LG)

        # 城市统计
        counts = {}
        for c in e.cities.values():
            if c.faction != "neutral":
                counts[c.faction] = counts.get(c.faction, 0) + 1
        top5 = sorted(counts.items(), key=lambda x: -x[1])[:5]
        parts = [f"{FACTIONS.get(f,f)}{n}城" for f, n in top5]
        stats = " | ".join(parts)
        draw_text(self.screen, stats, 10, 26, COLOR_DIM, FONT_CJK_SM)

        if e.game_over:
            if e.winner:
                w = FACTIONS.get(e.winner, e.winner)
                draw_text(self.screen, f"🏆 {w} 一统天下！", MAP_W // 2, 6, COLOR_GOLD, FONT_CJK_LG, center=True)
            else:
                draw_text(self.screen, "平局", MAP_W // 2, 6, COLOR_DIM, FONT_CJK_LG, center=True)

        # 操作提示
        hint = "WASD平移 | 滚轮缩放 | 空格推回合 | A自动 | Tab切换面板 | ESC退出"
        draw_text(self.screen, hint, MAP_W - 10, 26, COLOR_DIM, FONT_CJK_SM)

    # ============================================================
    # 底部事件滚动
    # ============================================================
    def _draw_event_ticker(self):
        now = time.time()
        recent = [(t, txt, c) for t, txt, c in self._events if now - t < 8]

        if not recent:
            return

        overlay = pygame.Surface((MAP_W, 32), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, MAP_H - 32))

        y = MAP_H - 28
        x = 10
        for _, txt, color in recent[:3]:
            s = draw_text(self.screen, f"▸ {txt}", x, y, color, FONT_CJK_SM)
            x += (s.get_width() if s else 0) + 10
            if x > MAP_W - 100:
                break

    # ============================================================
    # 右侧面板
    # ============================================================
    def _draw_panel(self):
        # 面板背景
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, (PANEL_X, 0, PANEL_W, WINDOW_H))
        pygame.draw.line(self.screen, (50, 50, 60), (PANEL_X, 0), (PANEL_X, WINDOW_H), 2)

        # 标签按钮
        tabs = [("factions", "势力"), ("log", "战报"), ("city", "城市"), ("generals", "武将")]
        bx = PANEL_X + 6
        for key, label in tabs:
            c = COLOR_GOLD if self.panel_tab == key else COLOR_DIM
            pygame.draw.rect(self.screen, (40, 40, 55) if self.panel_tab == key else COLOR_PANEL_BG,
                             (bx, 6, 65, 24), border_radius=4)
            draw_text(self.screen, label, bx + 8, 10, c, FONT_CJK_SM)
            bx += 70

        # 分割线
        pygame.draw.line(self.screen, (50, 50, 60), (PANEL_X, 34), (PANEL_X + PANEL_W, 34))

        # 内容
        if self.panel_tab == "factions":
            self._draw_faction_list()
        elif self.panel_tab == "city" and self.selected_city_id:
            self._draw_city_detail()
        elif self.panel_tab == "generals":
            self._draw_general_list()
        elif self.panel_tab == "log":
            self._draw_event_log()

    def _draw_faction_list(self):
        y = 42
        for fid, fname in FACTIONS.items():
            cities = [c for c in self.engine.cities.values() if c.faction == fid]
            if not cities:
                draw_text(self.screen, f"  {fname} — 已灭亡", PANEL_X + 6, y, (100, 60, 60), FONT_CJK_SM)
                y += 18
                continue
            hex_c = FACTION_COLORS.get(fid, "#888")
            rgb = tuple(int(hex_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            pygame.draw.rect(self.screen, rgb, (PANEL_X + 6, y + 2, 10, 10), border_radius=2)
            gold = sum(c.gold for c in cities)
            army = sum(c.garrison for c in cities)
            info = f"{fname}  {len(cities)}城  💰{gold}  🗡{army}"
            draw_text(self.screen, info, PANEL_X + 22, y, COLOR_WHITE if fid == self.selected_faction else COLOR_TEXT, FONT_CJK_SM)
            y += 19
            if y > WINDOW_H - 40:
                break

    def _draw_city_detail(self):
        city = self.engine.cities.get(self.selected_city_id or "")
        if not city:
            return
        y = 42
        hex_c = FACTION_COLORS.get(city.faction, "#888")
        rgb = tuple(int(hex_c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        draw_text(self.screen, city.name, PANEL_X + 6, y, rgb, FONT_CJK_LG)
        y += 26
        lines = [
            f"势力: {FACTIONS.get(city.faction, city.faction)}",
            f"等级: {'⭐' * city.level}",
            f"城墙: {city.wall_hp}/{city.wall_max_hp}",
            f"守军: {city.garrison}",
            f"金钱: {city.gold}  粮草: {city.food}",
            f"人口: {city.population}  民心: {city.morale}",
        ]
        for line in lines:
            draw_text(self.screen, line, PANEL_X + 6, y, COLOR_DIM, FONT_CJK_SM)
            y += 18

        # 驻守武将
        gens = [g for g in self.engine.generals.values() if g.location == city.id]
        if gens:
            y += 6
            draw_text(self.screen, "驻守武将:", PANEL_X + 6, y, COLOR_GOLD, FONT_CJK_SM)
            y += 18
            for g in gens[:5]:
                draw_text(self.screen, f"  {g.name} 统{g.command}武{g.bravery}智{g.intelligence}",
                          PANEL_X + 6, y, COLOR_TEXT, FONT_CJK_SM)
                y += 16

    def _draw_general_list(self):
        y = 42
        for g in self.engine.generals.values():
            if g.is_captured:
                continue
            fname = FACTIONS.get(g.faction, g.faction)
            draw_text(self.screen, f"{g.name} [{fname}]", PANEL_X + 6, y, COLOR_TEXT, FONT_CJK_SM)
            y += 16
            draw_text(self.screen, f"  统{g.command} 政{g.politics} 武{g.bravery} 智{g.intelligence} 忠{g.loyalty}",
                      PANEL_X + 6, y, COLOR_DIM, FONT_CJK_SM)
            y += 18
            if y > WINDOW_H - 20:
                break

    def _draw_event_log(self):
        y = 42
        for _, txt, color in reversed(self._events[-20:]):
            h = draw_text(self.screen, txt, PANEL_X + 6, y, color, FONT_CJK_SM)
            y += h + 4
            if y > WINDOW_H - 20:
                break

    # ============================================================
    # 事件处理
    # ============================================================
    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif hasattr(self, 'camera') and self.camera.handle_event(event):
            pass
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_SPACE and self._players:
                self._run_turn(self._players)
            elif event.key == pygame.K_a:
                self.auto_advance = not self.auto_advance
                self.add_event(f"自动推进: {'开' if self.auto_advance else '关'}", COLOR_DIM)
            elif event.key == pygame.K_TAB:
                tabs = ["factions", "log", "city", "generals"]
                i = tabs.index(self.panel_tab)
                self.panel_tab = tabs[(i + 1) % len(tabs)]
            elif event.key == pygame.K_1:
                self.panel_tab = "factions"
            elif event.key == pygame.K_2:
                self.panel_tab = "log"
            elif event.key == pygame.K_3:
                self.panel_tab = "city"
            elif event.key == pygame.K_4:
                self.panel_tab = "generals"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            if x < MAP_W:
                self._handle_map_click(x, y)
            else:
                self._handle_panel_click(x, y)

    def _handle_map_click(self, mx, my):
        """点击地图选中城市"""
        if not self._hex_renderer:
            return
        from game.hex_grid import pixel_to_axial
        wx = (mx - self.camera.x) / self.camera.zoom
        wy = (my - self.camera.y) / self.camera.zoom
        coord = pixel_to_axial(wx, wy, self._hex_renderer.hex_size)
        tile = self.engine.hex_map.get_tile(coord) if self.engine.hex_map else None
        if tile and tile.owner_city_id:
            self.selected_city_id = tile.owner_city_id
            self.selected_faction = tile.faction
            self.panel_tab = "city"
            city = self.engine.cities.get(tile.owner_city_id)
            if city:
                self.add_event(f"选中 {city.name} ({FACTIONS.get(city.faction, '')})", COLOR_GOLD)

    def _handle_panel_click(self, mx, my):
        """处理面板点击（Tab切换）"""
        if 6 <= my <= 30:
            tabs_x = [PANEL_X + 6 + i * 70 for i in range(4)]
            for i, tx in enumerate(tabs_x):
                if tx <= mx <= tx + 65:
                    self.panel_tab = ["factions", "log", "city", "generals"][i]
                    return

    # ============================================================
    # 回合执行
    # ============================================================
    def _run_turn(self, players: dict):
        for faction in FACTIONS:
            obs = self.engine.get_observation(faction)
            player = players.get(faction)
            if player:
                for cmd in player.get_commands(obs):
                    result = self.engine.execute_command(cmd)
                    if result.success and cmd.type in ("attack", "recruit", "message"):
                        self.add_event(f"{FACTIONS.get(faction, faction)}: {result.description}", COLOR_TEXT)

        result = self.engine.process_turn()
        turn = result.get("turn", 0)
        battles = result.get("battles_fought", 0)
        if battles > 0:
            self.add_event(f"第{turn}回合: ⚔️ {battles}场战斗", COLOR_RED)

        # 建国检测
        ks = getattr(self.engine, '_kingdom_system', None)
        if ks:
            for f, k in ks.get_all_kingdoms().items():
                self.add_event(f"🏰 {FACTIONS.get(f,f)} 称{k['type']}！国号【{k['name']}】", COLOR_GOLD)
