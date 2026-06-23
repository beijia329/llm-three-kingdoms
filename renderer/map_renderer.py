"""地图渲染器

绘制游戏地图：城市、连接线、军队、行军动画。
不同势力使用不同颜色。

参考设计文档：docs/design/architecture.md
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Set, Tuple

import pygame

from game.constants import (
    MAP_WIDTH, MAP_HEIGHT, CITY_RENDER_RADIUS,
    FACTIONS, FACTION_COLORS,
)
from game.engine import GameEngine
from game.models import Army, ArmyStatus


class MapRenderer:
    """地图渲染器

    负责绘制游戏地图的可视化元素。
    """

    def __init__(self, engine: GameEngine, auto_advance: bool = False) -> None:
        """初始化地图渲染器

        Args:
            engine: 游戏引擎
            auto_advance: 是否自动推进模式
        """
        self.engine = engine
        self.font = pygame.font.Font(None, 12)
        self.font_city = pygame.font.Font(None, 14)
        self.font_banner = pygame.font.Font(None, 20)

        # 城市位置缓存
        self._city_positions: Dict[str, Tuple[int, int]] = {}
        self._update_city_positions()

        # 动画状态
        self._flash_tick: int = 0

    def _update_city_positions(self) -> None:
        """更新城市位置缓存"""
        for city_id, city in self.engine.cities.items():
            if hasattr(city, 'position') and len(city.position) >= 2:
                self._city_positions[city_id] = (
                    int(city.position[0]),
                    int(city.position[1]),
                )

    def render(
        self,
        surface: pygame.Surface,
        selected_city_id: Optional[str] = None,
        auto_advance: bool = False,
    ) -> None:
        """渲染地图

        Args:
            surface: 目标表面
            selected_city_id: 选中的城市ID
            auto_advance: 是否自动推进模式
        """
        self._flash_tick = (self._flash_tick + 1) % 60

        # 背景
        surface.fill((16, 16, 24))

        # 绘制连接线
        self._draw_connections(surface)

        # 绘制军队
        self._draw_armies(surface)

        # 绘制城市
        self._draw_cities(surface, selected_city_id)

        # 绘制顶部横幅
        self._draw_banner(surface, auto_advance)

        # 绘制图例
        self._draw_legend(surface)

    # ============================================================
    # 横幅
    # ============================================================

    def _draw_banner(self, surface: pygame.Surface, auto_advance: bool) -> None:
        """绘制顶部信息横幅

        Args:
            surface: 目标表面
            auto_advance: 是否自动推进
        """
        banner_y = 8
        turn_text = f"第 {self.engine.turn}/{self.engine.max_turns} 回合"

        if self.engine.game_over:
            if self.engine.winner:
                winner_name = "魏" if self.engine.winner == "wei" else "蜀" if self.engine.winner == "shu" else "吴"
                turn_text = f"🏆 {winner_name} 获胜！共{self.engine.turn}回合"
            else:
                turn_text = "⚖️ 平局！"

        text_surf = self.font_banner.render(turn_text, True, (255, 215, 0))
        text_rect = text_surf.get_rect(center=(MAP_WIDTH // 2, banner_y + 14))
        # 背景框
        bg_rect = text_rect.inflate(20, 6)
        pygame.draw.rect(surface, (10, 10, 20), bg_rect, border_radius=4)
        pygame.draw.rect(surface, (60, 60, 80), bg_rect, 1, border_radius=4)
        surface.blit(text_surf, text_rect)

        # 自动推进指示
        if auto_advance and not self.engine.game_over:
            auto_color = (50, 200, 50) if (self._flash_tick // 15) % 2 == 0 else (30, 120, 30)
            auto_text = self.font.render("▶ 自动推进中", True, auto_color)
            surface.blit(auto_text, (MAP_WIDTH - 100, banner_y + 4))

    # ============================================================
    # 连接线
    # ============================================================

    def _draw_connections(self, surface: pygame.Surface) -> None:
        """绘制城市间的连接线

        Args:
            surface: 目标表面
        """
        drawn: Set[Tuple[str, str]] = set()

        for city_id, city in self.engine.cities.items():
            pos = self._city_positions.get(city_id)
            if pos is None:
                continue

            for neighbor_id in city.neighbors:
                # 避免重复绘制
                pair = tuple(sorted([city_id, neighbor_id]))
                if pair in drawn:
                    continue
                drawn.add(pair)

                neighbor_pos = self._city_positions.get(neighbor_id)
                if neighbor_pos is None:
                    continue

                # 线路颜色基于两端势力
                color = self._get_connection_color(city_id, neighbor_id)
                pygame.draw.line(surface, color, pos, neighbor_pos, 1)

    def _get_connection_color(self, city_a: str, city_b: str) -> Tuple[int, int, int]:
        """获取连接线颜色

        同势力=浅色，不同势力=暗色

        Args:
            city_a: 城市A的ID
            city_b: 城市B的ID

        Returns:
            RGB颜色值
        """
        city_a_obj = self.engine.cities.get(city_a)
        city_b_obj = self.engine.cities.get(city_b)

        if city_a_obj and city_b_obj and city_a_obj.faction == city_b_obj.faction:
            return (80, 80, 100)  # 同势力
        return (50, 50, 60)  # 不同势力

    # ============================================================
    # 城市
    # ============================================================

    def _draw_cities(
        self,
        surface: pygame.Surface,
        selected_city_id: Optional[str] = None,
    ) -> None:
        """绘制城市

        Args:
            surface: 目标表面
            selected_city_id: 选中的城市ID
        """
        for city_id, city in self.engine.cities.items():
            pos = self._city_positions.get(city_id)
            if pos is None:
                continue

            x, y = pos
            is_selected = city_id == selected_city_id

            # 势力颜色
            color_hex = FACTION_COLORS.get(city.faction, FACTION_COLORS["neutral"])
            color = self._hex_to_rgb(color_hex)

            # 城市半径（基于等级）
            radius = CITY_RENDER_RADIUS + city.level * 3

            # 绘制圆形
            if is_selected:
                pygame.draw.circle(surface, (255, 255, 100), pos, radius + 4, 2)
            pygame.draw.circle(surface, color, pos, radius)

            # 被围困城市：闪烁红色边框
            if city.is_besieged and (self._flash_tick // 15) % 2 == 0:
                pygame.draw.circle(surface, (255, 80, 30), pos, radius + 3, 2)

            # 城市名称
            text = self.font_city.render(city.name, True, (255, 255, 255))
            text_rect = text.get_rect(center=(x, y - radius - 12))
            surface.blit(text, text_rect)

            # 守军数量
            garrison_text = self.font.render(
                f"🛡️{city.garrison}", True, (200, 200, 200),
            )
            garrison_rect = garrison_text.get_rect(center=(x, y + radius + 8))
            surface.blit(garrison_text, garrison_rect)

    # ============================================================
    # 军队
    # ============================================================

    def _draw_armies(self, surface: pygame.Surface) -> None:
        """绘制军队

        Args:
            surface: 目标表面
        """
        for army_id, army in self.engine.armies.items():
            if army.soldiers <= 0:
                continue

            pos = self._get_army_position(army)
            if pos is None:
                continue

            x, y = pos
            color_hex = FACTION_COLORS.get(army.faction, "#888888")
            color = self._hex_to_rgb(color_hex)

            # 军队图标（方形）
            size = max(6, int(math.sqrt(army.soldiers) / 5))
            rect = pygame.Rect(x - size, y - size, size * 2, size * 2)

            if army.status == ArmyStatus.MARCHING:
                pygame.draw.rect(surface, color, rect, 2)
                # 箭头指示行军方向
                self._draw_direction_arrow(surface, army, x, y, color, size)
            elif army.status == ArmyStatus.BESIEGING:
                pygame.draw.rect(surface, color, rect)
                # 围城闪烁效果
                if (self._flash_tick // 20) % 2 == 0:
                    pygame.draw.rect(surface, (255, 100, 50), rect, 2)
            elif army.status == ArmyStatus.RETREATING:
                pygame.draw.rect(surface, (150, 150, 150), rect, 1)
            else:
                pygame.draw.rect(surface, color, rect)

            # 士气条
            if army.morale >= 50:
                bar_color = (50, 200, 50)
            elif army.morale >= 30:
                bar_color = (200, 200, 50)
            else:
                bar_color = (200, 50, 50)
            bar_width = max(4, int(size * 2 * army.morale / 100))
            pygame.draw.line(
                surface, bar_color,
                (x - size, y + size + 2),
                (x - size + bar_width, y + size + 2),
                2,
            )

            # 兵力数字标签
            label = self.font.render(f"{army.soldiers}", True, (220, 220, 200))
            label_rect = label.get_rect(midtop=(x, y + size + 5))
            surface.blit(label, label_rect)

    def _draw_direction_arrow(
        self, surface: pygame.Surface, army: Army,
        x: int, y: int, color: tuple, size: int,
    ) -> None:
        """绘制行军方向箭头

        Args:
            surface: 目标表面
            army: 军队
            x: 当前x
            y: 当前y
            color: 箭头颜色
        """
        from_pos = self._city_positions.get(army.from_city)
        to_pos = self._city_positions.get(army.to_city)
        if not from_pos or not to_pos:
            return

        # 计算方向向量
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return

        # 单位方向
        dx, dy = dx / length, dy / length

        # 箭头位置（军队前方一点）
        arrow_size = 6
        tip_x = x + dx * (size + 2)
        tip_y = y + dy * (size + 2)

        # 箭头三角
        angle = math.atan2(dy, dx)
        p1 = (tip_x, tip_y)
        p2 = (tip_x - arrow_size * math.cos(angle - 0.5),
              tip_y - arrow_size * math.sin(angle - 0.5))
        p3 = (tip_x - arrow_size * math.cos(angle + 0.5),
              tip_y - arrow_size * math.sin(angle + 0.5))

        pygame.draw.polygon(surface, color, [p1, p2, p3])

    def _get_army_position(self, army: Army) -> Optional[Tuple[int, int]]:
        """计算军队在地图上的位置

        根据行军进度在出发城市和目标城市之间插值。

        Args:
            army: 军队对象

        Returns:
            坐标 (x, y)，无法计算返回None
        """
        from_pos = self._city_positions.get(army.from_city)
        to_pos = self._city_positions.get(army.to_city)

        if from_pos and to_pos:
            progress = army.progress
            x = int(from_pos[0] + (to_pos[0] - from_pos[0]) * progress)
            y = int(from_pos[1] + (to_pos[1] - from_pos[1]) * progress)
            return (x, y)

        # 驻守或围城军队在目标城市位置
        if army.status == ArmyStatus.GARRISONED and to_pos:
            x = to_pos[0] + 25
            y = to_pos[1] - 25
            return (x, y)

        if army.status == ArmyStatus.BESIEGING and to_pos:
            x = to_pos[0] + 30
            y = to_pos[1]
            return (x, y)

        return None

    # ============================================================
    # 图例
    # ============================================================

    def _draw_legend(self, surface: pygame.Surface) -> None:
        """绘制势力图例

        Args:
            surface: 目标表面
        """
        x, y = 10, 10
        self._draw_text(surface, "图例", (x, y), (200, 200, 200), bold=True)
        y += 20

        for f_id, f_name in FACTIONS.items():
            color_hex = FACTION_COLORS.get(f_id, "#888888")
            color = self._hex_to_rgb(color_hex)

            city_count = self.engine.map.get_faction_cities(f_id)
            text = f"{f_name}: {len(city_count)}城"

            pygame.draw.circle(surface, color, (x + 8, y + 6), 6)
            self._draw_text(surface, text, (x + 20, y), (200, 200, 200))
            y += 20

        # 操作提示
        y = MAP_HEIGHT - 70
        self._draw_text(surface, "[空格] 下一回合", (x, y), (150, 150, 150))
        self._draw_text(surface, "[A] 自动推进", (x, y + 16), (150, 150, 150))
        self._draw_text(surface, "[ESC] 退出", (x, y + 32), (150, 150, 150))

    # ============================================================
    # 工具方法
    # ============================================================

    def get_city_at_pos(self, x: int, y: int) -> Optional[str]:
        """获取指定坐标处的城市ID

        Args:
            x: 横坐标
            y: 纵坐标

        Returns:
            城市ID，未找到返回None
        """
        for city_id, pos in self._city_positions.items():
            cx, cy = pos
            distance = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if distance <= CITY_RENDER_RADIUS + 10:
                return city_id
        return None

    def _draw_text(
        self, surface: pygame.Surface, text: str,
        pos: Tuple[int, int], color: Tuple[int, int, int],
        bold: bool = False,
    ) -> None:
        """绘制文本

        Args:
            surface: 目标表面
            text: 文本
            pos: 位置
            color: 颜色
            bold: 是否加粗
        """
        font = self.font
        if bold:
            font = pygame.font.Font(None, 14)
            font.set_bold(True)
        text_surface = font.render(text, True, color)
        surface.blit(text_surface, pos)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """十六进制颜色转RGB

        Args:
            hex_color: #RRGGBB格式

        Returns:
            (R, G, B)元组
        """
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
