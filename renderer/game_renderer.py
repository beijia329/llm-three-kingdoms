"""文明风格游戏渲染器 v3

布局 (1400×850):
┌──────────────────────────────┬──────────┐
│  顶部信息栏 (半透明叠加)      │  1.势力  │
│                              │  2.城市  │
│  六角格地图主区域 1100×850   │  3.武将  │
│                              │  4.战报  │
│  底部事件滚动条              │          │
│  右下角[下一回合]按钮        │          │
└──────────────────────────────┴──────────┘

配色（文明6风格低饱和度）:
- 背景    #1A1A2E
- 面板    #2A2A3E
- 文字    #E8E0D0
- 金色    #D4A84B
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import pygame

from game.constants import FACTIONS, FACTION_COLORS
from game.engine import GameEngine

logger = logging.getLogger(__name__)

# 窗口与布局
WINDOW_W, WINDOW_H = 1400, 850
MAP_W, MAP_H = 1100, 850
PANEL_X = MAP_W
PANEL_W = WINDOW_W - MAP_W  # 300
PANEL_CONTENT_W = PANEL_W - 20
FPS = 30

# 文明6风格配色
COLOR_BG = (26, 26, 46)
COLOR_PANEL_BG = (42, 42, 62)
COLOR_PANEL_HEADER = (60, 60, 80)
COLOR_TEXT = (232, 224, 208)
COLOR_GOLD = (212, 168, 75)
COLOR_DIM = (150, 145, 135)
COLOR_RED = (200, 80, 70)
COLOR_GREEN = (90, 180, 100)
COLOR_BLUE = (100, 160, 210)
COLOR_WHITE = (232, 224, 208)

# 中文字体
FONT_CJK = None
FONT_CJK_SM = None
FONT_CJK_LG = None
FONT_CJK_XS = None  # 面板小型说明文字（比 FONT_CJK_SM 更小）


def _init_cjk_font() -> None:
    """初始化中文字体"""
    global FONT_CJK, FONT_CJK_SM, FONT_CJK_LG, FONT_CJK_XS
    for name in ["PingFang SC", "STHeiti", "Heiti SC", "SimSun", "Noto Sans CJK SC"]:
        try:
            test = pygame.font.SysFont(name, 16)
            if test.render("测试", True, COLOR_WHITE).get_width() > 10:
                FONT_CJK_SM = pygame.font.SysFont(name, 13)
                FONT_CJK = pygame.font.SysFont(name, 16)
                FONT_CJK_LG = pygame.font.SysFont(name, 22)
                FONT_CJK_XS = pygame.font.SysFont(name, 11)
                logger.info("中文字体: %s", name)
                return
        except Exception:
            continue
    FONT_CJK_SM = pygame.font.Font(None, 14)
    FONT_CJK = pygame.font.Font(None, 16)
    FONT_CJK_LG = pygame.font.Font(None, 22)
    FONT_CJK_XS = pygame.font.Font(None, 11)
    logger.warning("未找到中文字体，使用默认字体")


def draw_text(
    surf,
    text: str,
    x: float,
    y: float,
    color: tuple = COLOR_TEXT,
    font=None,
    center: bool = False,
    right: bool = False,
) -> Optional[pygame.Surface]:
    """绘制文字，返回渲染后的 Surface"""
    f = font or FONT_CJK
    try:
        s = f.render(str(text), True, color)
        if center:
            surf.blit(s, (x - s.get_width() // 2, y))
        elif right:
            surf.blit(s, (x - s.get_width(), y))
        else:
            surf.blit(s, (x, y))
        return s
    except Exception:
        return None


def hex_to_rgb(hex_color: str) -> tuple:
    """十六进制颜色转 RGB"""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


class GameRenderer:
    """文明风格游戏渲染器"""

    def __init__(self, engine: GameEngine, title: str = "乱斗三国") -> None:
        """初始化渲染器

        Args:
            engine: 游戏引擎
            title: 窗口标题
        """
        pygame.init()
        _init_cjk_font()
        self.engine = engine
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.clock = pygame.time.Clock()
        pygame.display.set_caption(title)

        # 相机
        from renderer.camera import Camera
        self.camera = Camera(x=-900, y=-500, zoom=0.6)
        self.camera.min_zoom = 0.15
        self.camera.max_zoom = 1.5
        self.camera.pan_speed = 18

        # 子渲染器
        self._hex_renderer = None
        self._init_hex_renderer()

        # 状态
        self.running = False
        self._players: Optional[dict] = None
        self._turn_counter = 0
        self.turn_delay = 90          # 自动模式下帧数间隔
        self.auto_advance = False     # 默认手动推进
        self.turn_pending = False     # 等待玩家点"下一回合"
        self.selected_city_id: Optional[str] = None
        self.selected_faction: Optional[str] = None
        self.panel_tab = "factions"   # factions / city / generals / diplomacy / data / events / log
        self._turn_just_executed = False

        # 事件日志
        self._events: List[tuple] = []

    def _init_hex_renderer(self) -> None:
        """初始化六角格渲染器与中国边界"""
        try:
            from renderer.hex_map_renderer import HexMapRenderer
            self._hex_renderer = HexMapRenderer(self.engine.hex_map)
            from game.data_loader import load_china_geojson
            gj = load_china_geojson()
            self._hex_renderer.set_boundaries(gj)
            logger.info("HexMapRenderer + 中国边界 初始化完成")
        except Exception as e:
            logger.warning("HexMapRenderer 失败: %s", e)

    def add_event(self, text: str, color: tuple = COLOR_TEXT) -> None:
        """添加事件到滚动日志"""
        self._events.append((time.time(), text, color))
        if len(self._events) > 100:
            self._events = self._events[-100:]

    # ============================================================
    # 主循环
    # ============================================================

    def run(self, players: dict = None, auto_run: bool = False) -> None:
        """运行 GUI 主循环

        Args:
            players: 玩家字典 {faction: player}
            auto_run: 是否自动推进
        """
        self.running = True
        self._players = players
        self.auto_advance = auto_run

        while self.running:
            for event in pygame.event.get():
                self._handle_event(event)

            # 自动模式：计时器触发回合
            if self.auto_advance and not self.engine.game_over and self._players:
                self._turn_counter += 1
                if self._turn_counter >= self.turn_delay:
                    self._turn_counter = 0
                    self._execute_player_turns(self._players)
                    self._turn_just_executed = True

            # ——— 渲染 ———
            self.screen.fill(COLOR_BG)

            # 地图区域背景
            pygame.draw.rect(self.screen, (22, 22, 36), (0, 0, MAP_W, MAP_H))

            # 六角格地图（1-3 层）
            if self._hex_renderer:
                off = (self.camera.x, self.camera.y)
                z = self.camera.zoom
                self._hex_renderer.render(self.screen, off, z)
                self._hex_renderer.render_cities(self.screen, self.engine.cities, FONT_CJK_SM, off, z)
                self._hex_renderer.render_armies(self.screen, self.engine.armies, self.engine.cities, FONT_CJK_SM, off, z)

            # UI 层
            self._draw_top_bar()
            if not self.auto_advance and not self.engine.game_over:
                self._draw_next_turn_button()
            self._draw_event_ticker()
            self._draw_panel()

            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()

    # ============================================================
    # 顶部信息栏
    # ============================================================

    def _draw_top_bar(self) -> None:
        """绘制顶部信息栏"""
        overlay = pygame.Surface((MAP_W, 46), pygame.SRCALPHA)
        overlay.fill((18, 18, 34, 220))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.line(self.screen, (60, 60, 75), (0, 46), (MAP_W, 46), 1)

        e = self.engine
        season_cn = {"spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬"}
        season_value = e.season.value if hasattr(e.season, 'value') else str(e.season)
        sn = season_cn.get(str(season_value), "")

        mode = "∞" if str(getattr(e, 'game_mode', '')) == "infinite" else f"/{e.max_turns}"
        info = f"第 {e.turn}{mode} 回合  |  {e.year}年 {sn}  |  184年 黄巾之乱"
        draw_text(self.screen, info, 12, 6, COLOR_GOLD, FONT_CJK_LG)

        # 城市统计（前 5）
        counts: Dict[str, int] = {}
        for c in e.cities.values():
            if c.faction != "neutral":
                counts[c.faction] = counts.get(c.faction, 0) + 1
        top5 = sorted(counts.items(), key=lambda x: -x[1])[:5]
        parts = [f"{FACTIONS.get(f, f)}{n}城" for f, n in top5]
        stats = "  |  ".join(parts)
        draw_text(self.screen, stats, 12, 28, COLOR_DIM, FONT_CJK_SM)

        # 游戏结束提示
        if e.game_over:
            if e.winner:
                w = FACTIONS.get(e.winner, e.winner)
                draw_text(self.screen, f"🏆 {w} 一统天下！", MAP_W // 2, 8, COLOR_GOLD, FONT_CJK_LG, center=True)
            else:
                draw_text(self.screen, "平局", MAP_W // 2, 8, COLOR_DIM, FONT_CJK_LG, center=True)

        # 操作提示
        if self.auto_advance:
            hint = "自动推进中 | 按 A 切换手动"
        else:
            hint = "点击右下角[下一回合] 或按空格键  |  A 自动"
        draw_text(self.screen, hint, MAP_W - 12, 28, COLOR_DIM, FONT_CJK_SM, right=True)

    # ============================================================
    # 底部事件滚动
    # ============================================================

    def _draw_event_ticker(self) -> None:
        """绘制底部事件滚动条"""
        now = time.time()
        recent = [(t, txt, c) for t, txt, c in self._events if now - t < 12]

        if not recent:
            return

        overlay = pygame.Surface((MAP_W, 34), pygame.SRCALPHA)
        overlay.fill((18, 18, 34, 200))
        self.screen.blit(overlay, (0, MAP_H - 34))
        pygame.draw.line(self.screen, (60, 60, 75), (0, MAP_H - 34), (MAP_W, MAP_H - 34), 1)

        y = MAP_H - 28
        x = 12
        for _, txt, color in recent[:4]:
            s = draw_text(self.screen, f"▸ {txt}", x, y, color, FONT_CJK_SM)
            x += (s.get_width() if s else 0) + 16
            if x > MAP_W - 120:
                break

    # ============================================================
    # 右侧面板
    # ============================================================

    def _draw_panel(self) -> None:
        """绘制右侧面板框架与当前标签内容"""
        # 面板背景
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, (PANEL_X, 0, PANEL_W, WINDOW_H))
        pygame.draw.line(self.screen, (55, 55, 70), (PANEL_X, 0), (PANEL_X, WINDOW_H), 2)

        # 标签按钮：1-势力 2-城市 3-武将 4-外交 5-数据 6-事件 7-战报
        tabs = [
            ("factions", "1.势力"),
            ("city", "2.城市"),
            ("generals", "3.武将"),
            ("diplomacy", "4.外交"),
            ("data", "5.数据"),
            ("events", "6.事件"),
            ("log", "7.战报"),
        ]
        tab_w = PANEL_CONTENT_W // 7
        bx = PANEL_X + 10
        for key, label in tabs:
            is_active = self.panel_tab == key
            c = COLOR_GOLD if is_active else COLOR_DIM
            bg = (55, 55, 75) if is_active else COLOR_PANEL_BG
            pygame.draw.rect(self.screen, bg, (bx, 8, tab_w - 2, 26), border_radius=4)
            pygame.draw.rect(self.screen, (70, 70, 90) if is_active else (45, 45, 60), (bx, 8, tab_w - 2, 26), 1, border_radius=4)
            draw_text(self.screen, label, bx + (tab_w - 2) // 2, 12, c, FONT_CJK_XS, center=True)
            bx += tab_w

        # 分割线
        pygame.draw.line(self.screen, (55, 55, 70), (PANEL_X, 42), (PANEL_X + PANEL_W, 42), 1)

        # 内容
        if self.panel_tab == "factions":
            self._draw_faction_list()
        elif self.panel_tab == "city":
            self._draw_city_detail()
        elif self.panel_tab == "generals":
            self._draw_general_list()
        elif self.panel_tab == "diplomacy":
            self._draw_diplomacy_panel()
        elif self.panel_tab == "data":
            self._draw_data_panel()
        elif self.panel_tab == "events":
            self._draw_events_panel()
        elif self.panel_tab == "log":
            self._draw_event_log()

    def _draw_faction_list(self) -> None:
        """绘制势力总览（按城市数排序）"""
        y = 52
        # 表头
        draw_text(self.screen, "势力", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_SM)
        draw_text(self.screen, "城", PANEL_X + 90, y, COLOR_DIM, FONT_CJK_SM)
        draw_text(self.screen, "兵", PANEL_X + 130, y, COLOR_DIM, FONT_CJK_SM)
        draw_text(self.screen, "金", PANEL_X + 180, y, COLOR_DIM, FONT_CJK_SM)
        y += 22

        # 按城市数排序
        faction_rows = []
        for fid, fname in FACTIONS.items():
            cities = [c for c in self.engine.cities.values() if c.faction == fid]
            if not cities:
                faction_rows.append((0, fid, fname, cities))
            else:
                faction_rows.append((len(cities), fid, fname, cities))
        faction_rows.sort(key=lambda x: (-x[0], x[2]))

        for _, fid, fname, cities in faction_rows:
            if y > WINDOW_H - 30:
                break
            if not cities:
                draw_text(self.screen, f"{fname} — 已灭亡", PANEL_X + 12, y, (120, 60, 60), FONT_CJK_SM)
                y += 20
                continue

            hex_c = FACTION_COLORS.get(fid, "#888888")
            rgb = hex_to_rgb(hex_c)
            pygame.draw.rect(self.screen, rgb, (PANEL_X + 12, y + 3, 10, 10), border_radius=2)

            is_selected = fid == self.selected_faction
            text_color = COLOR_WHITE if is_selected else COLOR_TEXT

            total_garrison = sum(c.garrison for c in cities)
            total_gold = sum(c.gold for c in cities)
            draw_text(self.screen, fname, PANEL_X + 28, y, text_color, FONT_CJK_SM)
            draw_text(self.screen, str(len(cities)), PANEL_X + 90, y, text_color, FONT_CJK_SM)
            draw_text(self.screen, str(total_garrison), PANEL_X + 130, y, text_color, FONT_CJK_SM)
            draw_text(self.screen, str(total_gold), PANEL_X + 180, y, text_color, FONT_CJK_SM)
            y += 20

    def _draw_city_detail(self) -> None:
        """绘制城市详情"""
        city = self.engine.cities.get(self.selected_city_id or "")
        if not city:
            draw_text(self.screen, "点击地图城市查看详情", PANEL_X + 12, 52, COLOR_DIM, FONT_CJK_SM)
            return

        y = 52
        hex_c = FACTION_COLORS.get(city.faction, "#888888")
        rgb = hex_to_rgb(hex_c)
        draw_text(self.screen, city.name, PANEL_X + 12, y, rgb, FONT_CJK_LG)
        y += 28

        lines = [
            f"势力: {FACTIONS.get(city.faction, city.faction)}",
            f"等级: {'★' * city.level}",
            f"城墙: {city.wall_hp} / {city.wall_max_hp}",
            f"守军: {city.garrison}",
            f"金钱: {city.gold}    粮草: {city.food}",
            f"人口: {city.population}    民心: {city.morale}",
        ]
        for line in lines:
            draw_text(self.screen, line, PANEL_X + 12, y, COLOR_DIM, FONT_CJK_SM)
            y += 20

        if city.is_besieged:
            draw_text(self.screen, "⚠ 被围困中", PANEL_X + 12, y, COLOR_RED, FONT_CJK_SM)
            y += 22

        # 驻守武将
        gens = [g for g in self.engine.generals.values() if g.location == city.id]
        if gens:
            y += 8
            draw_text(self.screen, "驻守武将", PANEL_X + 12, y, COLOR_GOLD, FONT_CJK_SM)
            y += 20
            for g in gens[:6]:
                draw_text(
                    self.screen,
                    f"  {g.name}  统{g.command} 政{g.politics} 武{g.bravery} 智{g.intelligence}",
                    PANEL_X + 12, y, COLOR_TEXT, FONT_CJK_SM,
                )
                y += 18

    def _draw_general_list(self) -> None:
        """绘制武将列表（按势力分组）"""
        y = 52
        # 按势力分组
        by_faction: Dict[str, List[Any]] = {}
        for g in self.engine.generals.values():
            if g.is_captured:
                continue
            by_faction.setdefault(g.faction, []).append(g)

        # 按势力城市数排序
        faction_order = sorted(
            FACTIONS.keys(),
            key=lambda f: -len([c for c in self.engine.cities.values() if c.faction == f]),
        )

        for fid in faction_order:
            if y > WINDOW_H - 40:
                break
            gens = by_faction.get(fid, [])
            if not gens:
                continue
            fname = FACTIONS.get(fid, fid)
            hex_c = FACTION_COLORS.get(fid, "#888888")
            rgb = hex_to_rgb(hex_c)
            draw_text(self.screen, f"■ {fname}", PANEL_X + 12, y, rgb, FONT_CJK_SM)
            y += 20
            for g in gens[:4]:
                draw_text(
                    self.screen,
                    f"  {g.name} 统{g.command} 政{g.politics} 武{g.bravery} 智{g.intelligence} 忠{g.loyalty}",
                    PANEL_X + 12, y, COLOR_DIM, FONT_CJK_SM,
                )
                y += 18
            y += 6

    def _draw_event_log(self) -> None:
        """绘制战报日志（最近 20 条）"""
        y = 52
        for _, txt, color in reversed(self._events[-20:]):
            s = draw_text(self.screen, txt, PANEL_X + 12, y, color, FONT_CJK_SM)
            y += (s.get_height() if s else 16) + 6
            if y > WINDOW_H - 30:
                break

    def _draw_diplomacy_panel(self) -> None:
        """绘制外交面板：势力关系矩阵 + 最新消息"""
        y = 52
        drs = self.engine._diplomacy_relation_system
        if drs is None:
            draw_text(self.screen, "外交系统未初始化", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_SM)
            return

        # 标题
        draw_text(self.screen, "势力外交关系", PANEL_X + 12, y, COLOR_GOLD, FONT_CJK_SM)
        y += 22

        # 关系列表
        relations = drs.get_all_relations()
        status_colors = {
            "war": (200, 80, 70),
            "neutral": (150, 150, 150),
            "alliance": (90, 180, 100),
            "truce": (212, 168, 75),
        }
        for rel in list(relations.values())[:12]:
            fa_name = FACTIONS.get(rel.faction_a, rel.faction_a)
            fb_name = FACTIONS.get(rel.faction_b, rel.faction_b)
            status_color = status_colors.get(rel.status.value, COLOR_DIM)
            draw_text(self.screen, f"{fa_name}↔{fb_name}", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)
            draw_text(self.screen, rel.status.value, PANEL_X + 160, y, status_color, FONT_CJK_XS)
            draw_text(self.screen, str(rel.trust), PANEL_X + 240, y, COLOR_DIM, FONT_CJK_XS)
            y += 16
            if y > WINDOW_H - 80:
                break

        # 最新消息
        y += 6
        draw_text(self.screen, "最新消息", PANEL_X + 12, y, COLOR_GOLD, FONT_CJK_SM)
        y += 20
        for msg in self.engine.messages[-5:]:
            from_name = FACTIONS.get(msg.from_faction, msg.from_faction)
            to_name = FACTIONS.get(msg.to_faction, msg.to_faction)
            draw_text(self.screen, f"{from_name}→{to_name}: {msg.content[:20]}", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)
            y += 14
            if y > WINDOW_H - 30:
                break

    def _draw_data_panel(self) -> None:
        """绘制数据面板：武将排行榜 + 城池统计"""
        y = 52
        draw_text(self.screen, "武将排行榜", PANEL_X + 12, y, COLOR_GOLD, FONT_CJK_SM)
        y += 22

        all_gens = [g for g in self.engine.generals.values() if not g.is_captured]
        # 统帅 Top 5
        draw_text(self.screen, "统帅 Top 5", PANEL_X + 12, y, (150, 150, 150), FONT_CJK_XS)
        y += 14
        for g in sorted(all_gens, key=lambda x: -x.command)[:5]:
            draw_text(self.screen, f"  {g.name}: {g.command}", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)
            y += 12
        y += 6

        # 政治 Top 5
        draw_text(self.screen, "政治 Top 5", PANEL_X + 12, y, (150, 150, 150), FONT_CJK_XS)
        y += 14
        for g in sorted(all_gens, key=lambda x: -x.politics)[:5]:
            draw_text(self.screen, f"  {g.name}: {g.politics}", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)
            y += 12
        y += 6

        # 勇武 Top 5
        draw_text(self.screen, "勇武 Top 5", PANEL_X + 12, y, (150, 150, 150), FONT_CJK_XS)
        y += 14
        for g in sorted(all_gens, key=lambda x: -x.bravery)[:5]:
            draw_text(self.screen, f"  {g.name}: {g.bravery}", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)
            y += 12
        y += 6

        # 城池统计
        draw_text(self.screen, "城池统计", PANEL_X + 12, y, COLOR_GOLD, FONT_CJK_SM)
        y += 18
        cities = list(self.engine.cities.values())
        draw_text(self.screen, f"总城池: {len(cities)}  总武将: {len(all_gens)}", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)
        y += 14
        draw_text(self.screen, f"总兵力: {sum(c.garrison for c in cities)}  总人口: {sum(c.population for c in cities)}", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)

    def _draw_events_panel(self) -> None:
        """绘制事件面板：回合日志"""
        y = 52
        draw_text(self.screen, "回合事件", PANEL_X + 12, y, COLOR_GOLD, FONT_CJK_SM)
        y += 22

        for tl in self.engine.turn_logs[-10:]:
            draw_text(self.screen, f"第 {tl.turn} 回合", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)
            y += 12
            battle_count = sum(1 for e in tl.events if isinstance(e, dict) and e.get("type") == "battle")
            if battle_count:
                draw_text(self.screen, f"  战斗: {battle_count} 场", PANEL_X + 12, y, (200, 80, 70), FONT_CJK_XS)
                y += 12
            # 显示前3个事件
            for ev in tl.events[:3]:
                if isinstance(ev, dict) and "text" in ev:
                    draw_text(self.screen, f"  {ev['text'][:30]}", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)
                    y += 12
                elif isinstance(ev, str):
                    draw_text(self.screen, f"  {ev[:30]}", PANEL_X + 12, y, COLOR_DIM, FONT_CJK_XS)
                    y += 12
            y += 4
            if y > WINDOW_H - 30:
                break

    # ============================================================
    # 事件处理
    # ============================================================

    def _handle_event(self, event) -> None:
        """处理输入事件"""
        if event.type == pygame.QUIT:
            self.running = False
        elif hasattr(self, 'camera') and self.camera.handle_event(event):
            pass
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_SPACE:
                if self.engine.game_over:
                    self.add_event("游戏已结束，关闭窗口或按 ESC 退出", COLOR_DIM)
                elif self._players and not self.auto_advance:
                    self._execute_player_turns(self._players)
            elif event.key == pygame.K_a:
                self.auto_advance = not self.auto_advance
                self.add_event(f"自动推进: {'开' if self.auto_advance else '关（手动）'}", COLOR_DIM)
            elif event.key == pygame.K_TAB:
                tabs = ["factions", "city", "generals", "diplomacy", "data", "events", "log"]
                i = tabs.index(self.panel_tab)
                self.panel_tab = tabs[(i + 1) % len(tabs)]
            elif event.key == pygame.K_1:
                self.panel_tab = "factions"
            elif event.key == pygame.K_2:
                self.panel_tab = "city"
            elif event.key == pygame.K_3:
                self.panel_tab = "generals"
            elif event.key == pygame.K_4:
                self.panel_tab = "diplomacy"
            elif event.key == pygame.K_5:
                self.panel_tab = "data"
            elif event.key == pygame.K_6:
                self.panel_tab = "events"
            elif event.key == pygame.K_7:
                self.panel_tab = "log"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            if x < MAP_W:
                self._handle_map_click(x, y)
            else:
                self._handle_panel_click(x, y)

    def _handle_map_click(self, mx: int, my: int) -> None:
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

    def _handle_panel_click(self, mx: int, my: int) -> None:
        """处理面板点击（Tab 切换）"""
        if 8 <= my <= 34:
            tabs = ["factions", "city", "generals", "diplomacy", "data", "events", "log"]
            tab_w = PANEL_CONTENT_W // 7
            for i, key in enumerate(tabs):
                tx = PANEL_X + 10 + i * tab_w
                if tx <= mx <= tx + tab_w - 2:
                    self.panel_tab = key
                    return

        # 势力列表点击选中势力
        if self.panel_tab == "factions" and 52 <= my <= WINDOW_H - 30:
            # 简单估算行位置
            row = (my - 52) // 20
            faction_rows = sorted(
                FACTIONS.items(),
                key=lambda x: -len([c for c in self.engine.cities.values() if c.faction == x[0]]),
            )
            if 0 <= row < len(faction_rows):
                self.selected_faction = faction_rows[row][0]

    def _draw_next_turn_button(self) -> None:
        """绘制'下一回合'按钮（右下角）"""
        btn_w, btn_h = 150, 40
        btn_x = MAP_W - btn_w - 16
        btn_y = MAP_H - btn_h - 50

        # 半透明背景
        overlay = pygame.Surface((btn_w + 10, btn_h + 10), pygame.SRCALPHA)
        overlay.fill((18, 18, 34, 200))
        self.screen.blit(overlay, (btn_x - 5, btn_y - 5))

        color = COLOR_GOLD if not self.engine.game_over else COLOR_DIM
        pygame.draw.rect(self.screen, (45, 45, 60), (btn_x, btn_y, btn_w, btn_h), border_radius=6)
        pygame.draw.rect(self.screen, color, (btn_x, btn_y, btn_w, btn_h), 2, border_radius=6)

        label = "下一回合" if not self.engine.game_over else "游戏结束"
        draw_text(self.screen, label, btn_x + btn_w // 2, btn_y + 7, color, FONT_CJK_LG, center=True)
        draw_text(self.screen, "[ 空格键 ]", btn_x + btn_w // 2, btn_y + 26, COLOR_DIM, FONT_CJK_SM, center=True)

    def _execute_player_turns(self, players: dict) -> None:
        """执行所有玩家的命令和引擎回合处理"""
        if self.engine.game_over:
            return

        # 清除旧事件（保留 60 秒内）
        now = time.time()
        self._events = [(t, txt, c) for t, txt, c in self._events if now - t < 60]

        for faction in FACTIONS:
            obs = self.engine.get_observation(faction)
            player = players.get(faction)
            if player:
                for cmd in player.get_commands(obs):
                    result = self.engine.execute_command(cmd)
                    if result.success:
                        fname = FACTIONS.get(faction, faction)
                        if cmd.type == "attack":
                            self.add_event(f"⚔ {fname} 从 {cmd.from_city} 出兵 {cmd.troops} → {cmd.to_city}", COLOR_RED)
                        elif cmd.type == "message":
                            self.add_event(f"✉ {fname} → {FACTIONS.get(cmd.to, cmd.to)}: {str(cmd.content)[:30]}", COLOR_BLUE)
                            # 推送外交消息给目标势力
                            target_player = players.get(cmd.to)
                            if target_player:
                                target_player.receive_message(faction, str(getattr(cmd, 'content', '')))
                        elif cmd.type == "recruit":
                            self.add_event(f"🔧 {fname} {cmd.city} 征兵 {cmd.troops}", COLOR_GREEN)

        result = self.engine.process_turn()
        turn = result.get("turn", 0)
        battles = result.get("battles_fought", 0)

        if battles > 0:
            self.add_event(f"⚔ 第 {turn} 回合: {battles} 场战斗", COLOR_RED)

        # 建国检测
        ks = getattr(self.engine, '_kingdom_system', None)
        if ks:
            for f, k in ks.get_all_kingdoms().items():
                self.add_event(f"🏰 {FACTIONS.get(f, f)} 称{k['type']}！国号【{k['name']}】", COLOR_GOLD)

        self._turn_just_executed = True
        logger.info("第%d回合完成 (战斗:%d)", turn, battles)
