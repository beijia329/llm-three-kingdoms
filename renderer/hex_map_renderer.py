"""六角格地图渲染器

在 Pygame Surface 上绘制六角格地图、地形颜色和城市标记。

参考: https://www.redblobgames.com/grids/hexagons/
"""

from __future__ import annotations

import json
import math
import os
import time

from game.hex_grid import HexCoord, axial_to_pixel

# Pygame is only imported for type hints — actual import happens at render time
try:
    import pygame
except ImportError:
    pygame = None  # type: ignore


class HexMapRenderer:
    """六角格地图渲染器

    在 Pygame Surface 上绘制六角格地形、城市标记和中国省界。

    Attributes:
        hex_size: 六角格外接圆半径（像素）
        colors: 地形颜色配置
    """

    def __init__(self, hex_map: object, hex_size: int = 32) -> None:
        """初始化渲染器

        Args:
            hex_map: HexMap 对象
            hex_size: 六角格外接圆半径
        """
        self.hex_map = hex_map
        self.hex_size = hex_size
        self.colors = self._load_colors()
        self._boundaries: list = []  # 省界数据

    def _load_colors(self) -> dict:
        """加载地形颜色配置"""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "terrain_colors.json",
        )
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "plain": {"fill": "#7cb342", "border": "#558b2f"},
                "forest": {"fill": "#33691e", "border": "#1b5e20"},
                "hill": {"fill": "#a1887f", "border": "#6d4c41"},
                "mountain": {"fill": "#757575", "border": "#424242"},
                "river": {"fill": "#4fc3f7", "border": "#0288d1"},
                "desert": {"fill": "#e6c075", "border": "#c19a4b"},
            }

    def set_boundaries(self, geojson: dict) -> None:
        """加载中国省界 GeoJSON 数据并转换为屏幕坐标

        Args:
            geojson: GeoJSON FeatureCollection
        """
        self._boundaries = []
        for feature in geojson.get("features", []):
            name = feature.get("name", "")
            coords = feature.get("coordinates", [])
            lines = self._extract_polygon_lines(coords)
            self._boundaries.append({"name": name, "lines": lines})

    def _extract_polygon_lines(self, coordinates: list) -> list:
        """从 GeoJSON 多边形坐标提取屏幕线段列表

        Args:
            coordinates: GeoJSON 坐标数组

        Returns:
            [(x1, y1, x2, y2), ...] 屏幕坐标线段
        """
        lines = []

        def extract_ring(ring):
            for i in range(len(ring) - 1):
                lon1, lat1 = ring[i][0], ring[i][1]
                lon2, lat2 = ring[i + 1][0], ring[i + 1][1]
                if (lon1 < 90 or lon1 > 128 or lat1 < 20 or lat1 > 47):
                    continue
                x1, y1 = self._lonlat_to_screen(lon1, lat1)
                x2, y2 = self._lonlat_to_screen(lon2, lat2)
                lines.append((x1, y1, x2, y2))

        def traverse(coord):
            if len(coord) == 0:
                return
            if isinstance(coord[0], (int, float)):
                return
            if isinstance(coord[0][0], (int, float)):
                extract_ring(coord)
            else:
                for sub in coord:
                    traverse(sub)

        traverse(coordinates)
        return lines

    def _lonlat_to_screen(self, lon: float, lat: float) -> tuple:
        """经纬度 → 六角格屏幕像素坐标

        Args:
            lon: 经度
            lat: 纬度

        Returns:
            (x, y) 像素坐标
        """
        import math
        # 浮点轴向坐标
        q = (lon - 95.0) / 30.0 * (self.hex_map.width - 1)
        r = (45.0 - lat) / 23.0 * (self.hex_map.height - 1)
        # 屏幕像素
        x = self.hex_size * (math.sqrt(3) * q + math.sqrt(3) / 2 * r)
        y = self.hex_size * (3.0 / 2 * r)
        return (x, y)

    def _draw_boundaries(
        self,
        surface: object,
        camera_offset: tuple = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """绘制中国省界线（半透明叠加在六角格地形之上）

        Args:
            surface: Pygame Surface
            camera_offset: 相机偏移
            camera_zoom: 缩放倍率
        """
        if pygame is None or not self._boundaries:
            return

        border_color = (100, 100, 110)  # 暗灰色省界线
        for province in self._boundaries:
            for (x1, y1, x2, y2) in province["lines"]:
                sx1 = x1 * camera_zoom + camera_offset[0]
                sy1 = y1 * camera_zoom + camera_offset[1]
                sx2 = x2 * camera_zoom + camera_offset[0]
                sy2 = y2 * camera_zoom + camera_offset[1]
                sw = surface.get_width() if hasattr(surface, 'get_width') else 800
                sh = surface.get_height() if hasattr(surface, 'get_height') else 600
                if (sx1 < -50 and sx2 < -50) or (sx1 > sw + 50 and sx2 > sw + 50):
                    continue
                if (sy1 < -50 and sy2 < -50) or (sy1 > sh + 50 and sy2 > sh + 50):
                    continue
                try:
                    pygame.draw.line(surface, border_color, (sx1, sy1), (sx2, sy2), 1)
                except Exception:
                    pass

    def render(
        self,
        surface: object,
        camera_offset: tuple = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """渲染所有地块 + 省界线（仅渲染屏幕可见范围）

        Args:
            surface: Pygame Surface 对象
            camera_offset: 相机偏移 (dx, dy)
            camera_zoom: 缩放倍率
        """
        if pygame is None:
            return

        # 计算可见范围
        sw = surface.get_width() if hasattr(surface, 'get_width') else 800
        sh = surface.get_height() if hasattr(surface, 'get_height') else 600
        margin = self.hex_size * camera_zoom * 2
        world_x0 = (-camera_offset[0] - margin) / camera_zoom
        world_y0 = (-camera_offset[1] - margin) / camera_zoom
        world_x1 = (sw - camera_offset[0] + margin) / camera_zoom
        world_y1 = (sh - camera_offset[1] + margin) / camera_zoom

        sqrt3 = math.sqrt(3)
        q_min = max(0, int(world_x0 / (sqrt3 * self.hex_size) - 2))
        q_max = min(self.hex_map.width - 1, int(world_x1 / (sqrt3 * self.hex_size) + 2))
        r_min = max(0, int(world_y0 / (1.5 * self.hex_size) - 2))
        r_max = min(self.hex_map.height - 1, int(world_y1 / (1.5 * self.hex_size) + 2))

        drawn = 0
        for q in range(q_min, q_max + 1):
            for r in range(r_min, r_max + 1):
                tile = self.hex_map.get_tile(HexCoord(q, r))
                if tile is not None:
                    self._draw_hex(surface, tile, camera_offset, camera_zoom)
                    drawn += 1

        # 势力边界
        self._draw_faction_borders(surface, camera_offset, camera_zoom)

        # 叠加省界线
        self._draw_boundaries(surface, camera_offset, camera_zoom)

    def _draw_faction_borders(
        self,
        surface: object,
        camera_offset: tuple = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """绘制势力边界——在异势力邻格之间的边画粗线

        Args:
            surface: Pygame Surface
            camera_offset: 相机偏移
            camera_zoom: 缩放倍率
        """
        if pygame is None:
            return

        from game.constants import FACTION_COLORS

        for tile in self.hex_map.iter_tiles():
            if tile.faction is None:
                continue
            neighbors = self.hex_map.get_neighbors(tile.coord)
            for nb in neighbors:
                if nb.faction is None or nb.faction == tile.faction:
                    continue
                # 只画一次（按坐标排序避免重复）
                if tile.coord.to_tuple() > nb.coord.to_tuple():
                    continue
                # 计算共享边的两个端点
                x1, y1 = axial_to_pixel(tile.coord, self.hex_size * camera_zoom)
                x2, y2 = axial_to_pixel(nb.coord, self.hex_size * camera_zoom)
                mx = (x1 + x2) / 2 + camera_offset[0]
                my = (y1 + y2) / 2 + camera_offset[1]
                # 边方向（垂直平分线）
                dx = (x2 - x1)
                dy = (y2 - y1)
                length = (dx * dx + dy * dy) ** 0.5
                if length < 1:
                    continue
                nx = -dy / length * self.hex_size * camera_zoom * 0.5
                ny = dx / length * self.hex_size * camera_zoom * 0.5
                # 用势力颜色画边界线
                color_hex = FACTION_COLORS.get(tile.faction, "#888888")
                color = self._hex_to_rgb(color_hex)
                try:
                    pygame.draw.line(
                        surface, color,
                        (mx + nx, my + ny),
                        (mx - nx, my - ny),
                        2,
                    )
                except Exception:
                    pass

    def _draw_hex(
        self,
        surface: object,
        tile: object,
        camera_offset: tuple,
        camera_zoom: float,
    ) -> None:
        """绘制单个六角格

        Args:
            surface: Pygame Surface
            tile: Tile 对象
            camera_offset: 相机偏移
            camera_zoom: 缩放
        """
        if pygame is None:
            return

        x, y = axial_to_pixel(tile.coord, self.hex_size * camera_zoom)
        x += camera_offset[0]
        y += camera_offset[1]
        points = self._hex_points(x, y, self.hex_size * camera_zoom)

        terrain_val = tile.terrain.value if hasattr(tile.terrain, 'value') else str(tile.terrain)
        color_cfg = self.colors.get(terrain_val, {})
        fill_color = self._hex_to_rgb(color_cfg.get("fill", "#888888"))
        border_color = self._hex_to_rgb(color_cfg.get("border", "#555555"))

        pygame.draw.polygon(surface, fill_color, points)
        pygame.draw.polygon(surface, border_color, points, 1)

    def render_cities(
        self,
        surface: object,
        cities: dict,
        font: object = None,
        camera_offset: tuple = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """渲染城市标记（圆点 + 名称 + 兵力条）

        Args:
            surface: Pygame Surface
            cities: 城市字典 {id: City}
            font: Pygame 字体（用于城市名）
            camera_offset: 相机偏移
            camera_zoom: 缩放
        """
        if pygame is None:
            return

        from game.constants import FACTION_COLORS, FACTIONS

        for city in cities.values():
            x, y = axial_to_pixel(city.position, self.hex_size * camera_zoom)
            x += camera_offset[0]
            y += camera_offset[1]
            ix, iy = int(x), int(y)

            hex_color = FACTION_COLORS.get(city.faction, "#888888")
            color = self._hex_to_rgb(hex_color)

            # 城市等级 → 圆点大小
            radius = int((4 + city.level * 1.5) * camera_zoom)
            radius = max(3, radius)

            # 被围困时闪烁
            if city.is_besieged:
                if int(time.time() * 4) % 2 == 0:
                    color = (255, 80, 80)

            pygame.draw.circle(surface, color, (ix, iy), radius)
            pygame.draw.circle(surface, (255, 255, 255), (ix, iy), radius, 1)

            # 城市名（缩放 > 0.5 时显示）
            if camera_zoom > 0.5 and font:
                name_text = city.name
                try:
                    txt = font.render(name_text, True, (255, 255, 255))
                    surface.blit(txt, (ix - txt.get_width() // 2, iy - radius - 14))
                except Exception:
                    pass

            # 兵力条
            if city.garrison > 0 and camera_zoom > 0.4:
                max_g = city.level * 1000
                bar_w = int(20 * camera_zoom)
                bar_h = max(2, int(3 * camera_zoom))
                bar_x = ix - bar_w // 2
                bar_y = iy + radius + 2
                ratio = min(1.0, city.garrison / max_g)
                pygame.draw.rect(surface, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h))
                pygame.draw.rect(surface, (0, 200, 100), (bar_x, bar_y, int(bar_w * ratio), bar_h))

    def render_armies(
        self,
        surface: object,
        armies: dict,
        cities: dict,
        camera_offset: tuple = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """渲染军队标记（三角箭头 + 士气条）

        Args:
            surface: Pygame Surface
            armies: 军队字典 {id: Army}
            cities: 城市字典（用于方向判断）
            camera_offset: 相机偏移
            camera_zoom: 缩放
        """
        if pygame is None:
            return

        from game.constants import FACTION_COLORS
        from game.models import ArmyStatus

        for army in armies.values():
            if army.soldiers <= 0:
                continue

            # 确定军队位置
            if army.current_hex is not None:
                hx, hy = axial_to_pixel(army.current_hex, self.hex_size * camera_zoom)
            elif army.to_city in cities:
                tc = cities[army.to_city]
                hx, hy = axial_to_pixel(tc.position, self.hex_size * camera_zoom)
            else:
                continue

            hx += camera_offset[0]
            hy += camera_offset[1]

            hex_color = FACTION_COLORS.get(army.faction, "#888888")
            color = self._hex_to_rgb(hex_color)
            size = int(6 * camera_zoom)

            # 三角箭头
            import math
            points = []
            for i in range(3):
                angle = math.pi * 2 / 3 * i - math.pi / 2
                px = hx + size * math.cos(angle)
                py = hy + size * math.sin(angle)
                points.append((px, py))
            try:
                pygame.draw.polygon(surface, color, points)
            except Exception:
                pass

            # 兵力数字
            if camera_zoom > 0.4:
                try:
                    font_s = pygame.font.Font(None, 10)
                    txt = font_s.render(str(army.soldiers), True, (255, 255, 255))
                    surface.blit(txt, (hx - txt.get_width() // 2, hy - size - 10))
                except Exception:
                    pass

            # 士气条
            if camera_zoom > 0.35:
                bar_w = int(16 * camera_zoom)
                bar_h = max(1, int(2 * camera_zoom))
                bar_x = int(hx) - bar_w // 2
                bar_y = int(hy) + size + 1
                ratio = army.morale / 100
                pygame.draw.rect(surface, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h))
                morale_color = (0, 200, 100) if ratio > 0.5 else (200, 150, 0) if ratio > 0.2 else (200, 50, 50)
                pygame.draw.rect(surface, morale_color, (bar_x, bar_y, int(bar_w * ratio), bar_h))

    @staticmethod
    def _hex_points(x: float, y: float, size: float) -> list:
        """计算六角格的 6 个顶点

        Args:
            x: 中心 x 坐标
            y: 中心 y 坐标
            size: 外接圆半径

        Returns:
            6 个顶点的坐标列表 [(x0, y0), ...]
        """
        points = []
        for i in range(6):
            angle = math.pi / 3 * i - math.pi / 6
            px = x + size * math.cos(angle)
            py = y + size * math.sin(angle)
            points.append((px, py))
        return points

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        """十六进制颜色转 RGB 元组

        Args:
            hex_color: 如 "#7cb342"

        Returns:
            (R, G, B) 元组
        """
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
