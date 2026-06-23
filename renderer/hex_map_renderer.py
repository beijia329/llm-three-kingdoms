"""六角格地图渲染器

在 Pygame Surface 上绘制六角格地图、地形颜色和城市标记。

参考: https://www.redblobgames.com/grids/hexagons/
"""

from __future__ import annotations

import json
import math
import os
from typing import Optional

from game.hex_grid import HexCoord, axial_to_pixel
from game.tile import TerrainType

# Pygame is only imported for type hints — actual import happens at render time
try:
    import pygame
except ImportError:
    pygame = None  # type: ignore


class HexMapRenderer:
    """六角格地图渲染器

    在 Pygame Surface 上绘制六角格地形。

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

    def render(
        self,
        surface: object,
        camera_offset: tuple = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """渲染所有地块

        Args:
            surface: Pygame Surface 对象
            camera_offset: 相机偏移 (dx, dy)
            camera_zoom: 缩放倍率
        """
        if pygame is None:
            return

        for tile in self.hex_map.iter_tiles():
            self._draw_hex(surface, tile, camera_offset, camera_zoom)

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
        camera_offset: tuple = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """渲染城市标记

        Args:
            surface: Pygame Surface
            cities: 城市字典 {id: City}
            camera_offset: 相机偏移
            camera_zoom: 缩放
        """
        if pygame is None:
            return

        faction_colors = {
            "wei": (0, 85, 164),
            "shu": (204, 0, 0),
            "wu": (0, 170, 85),
        }

        for city in cities.values():
            x, y = axial_to_pixel(city.position, self.hex_size * camera_zoom)
            x += camera_offset[0]
            y += camera_offset[1]
            color = faction_colors.get(city.faction, (136, 136, 136))
            radius = int(8 * camera_zoom)
            pygame.draw.circle(surface, color, (int(x), int(y)), max(radius, 3))
            pygame.draw.circle(surface, (255, 255, 255), (int(x), int(y)), max(radius, 3), 1)

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
