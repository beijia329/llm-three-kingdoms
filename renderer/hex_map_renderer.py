"""六角格地图渲染器 v2（文明6风格六层视觉层次）

视觉层次（从下到上）：
1. 中国省份底图（极淡填充 + 3px 白/金色边界）
2. 六角格地形（柔色填充）
3. 势力边界线（势力色，3px）
4. 城市标记（圆点 + 名 + 兵力条）
5. 军队图标（三角箭头 + 数字 + 士气条）
6. UI 覆盖层（由 GameRenderer 处理）

参考: https://www.redblobgames.com/grids/hexagons/
"""

from __future__ import annotations

import json
import math
import os
import time
from typing import Dict, List, Optional, Tuple

from game.constants import FACTION_COLORS, FACTIONS
from game.hex_grid import HexCoord, axial_to_pixel

# Pygame 仅在渲染时导入，便于非 GUI 环境测试
try:
    import pygame
except ImportError:
    pygame = None  # type: ignore


class HexMapRenderer:
    """六角格地图渲染器

    负责绘制 1-5 层视觉元素：省份底图、地形、势力边界、城市、军队。
    """

    def __init__(self, hex_map: object, hex_size: int = 32) -> None:
        """初始化渲染器

        Args:
            hex_map: HexMap 对象
            hex_size: 六角格外接圆半径（像素）
        """
        self.hex_map = hex_map
        self.hex_size = hex_size
        self.colors = self._load_colors()
        self._boundaries: List[dict] = []
        self._province_fills: List[List[Tuple[float, float]]] = []

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
                "plain": {"fill": "#8B9A6E", "border": "#7A8960"},
                "forest": {"fill": "#4A6B3A", "border": "#3D5A30"},
                "hill": {"fill": "#9B8E7A", "border": "#8A7E6C"},
                "mountain": {"fill": "#7A7A7A", "border": "#6A6A6A"},
                "river": {"fill": "#4A8FB8", "border": "#3E7A9E"},
                "desert": {"fill": "#C4B58A", "border": "#B0A27A"},
            }

    # ============================================================
    # 第 1 层：中国省份底图
    # ============================================================

    def set_boundaries(self, geojson: dict) -> None:
        """加载中国省界 GeoJSON 数据并转换为屏幕坐标

        Args:
            geojson: GeoJSON FeatureCollection
        """
        self._boundaries = []
        self._province_fills = []
        for feature in geojson.get("features", []):
            name = feature.get("name", "")
            coords = feature.get("coordinates", [])
            rings = self._extract_polygon_rings(coords)
            screen_rings = []
            for ring in rings:
                pts = [self._lonlat_to_screen(lon, lat) for lon, lat in ring]
                screen_rings.append(pts)
            self._boundaries.append({"name": name, "rings": screen_rings})

    def _extract_polygon_rings(self, coordinates: list) -> List[List[Tuple[float, float]]]:
        """从 GeoJSON 多边形坐标提取经纬度环列表"""
        rings: List[List[Tuple[float, float]]] = []

        def extract_ring(ring):
            valid = []
            for pt in ring:
                lon, lat = pt[0], pt[1]
                if lon < 90 or lon > 128 or lat < 20 or lat > 47:
                    continue
                valid.append((lon, lat))
            if len(valid) >= 3:
                rings.append(valid)

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
        return rings

    def _lonlat_to_screen(self, lon: float, lat: float) -> Tuple[float, float]:
        """经纬度 → 六角格屏幕像素坐标"""
        q = (lon - 95.0) / 30.0 * (self.hex_map.width - 1)
        r = (45.0 - lat) / 23.0 * (self.hex_map.height - 1)
        x = self.hex_size * (math.sqrt(3) * q + math.sqrt(3) / 2 * r)
        y = self.hex_size * (3.0 / 2 * r)
        return (x, y)

    def _draw_boundaries(
        self,
        surface: object,
        camera_offset: Tuple[float, float] = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """绘制中国省界：极淡填充 + 3px 白/金色边界"""
        if pygame is None or not self._boundaries:
            return

        sw = surface.get_width()
        sh = surface.get_height()
        fill_color = (212, 200, 170, 18)  # 极淡金色填充
        border_color = (220, 210, 180)    # 白金色边界

        for province in self._boundaries:
            for ring in province["rings"]:
                pts = [
                    (x * camera_zoom + camera_offset[0], y * camera_zoom + camera_offset[1])
                    for x, y in ring
                ]
                if not pts:
                    continue
                # 简单裁剪：如果全部在屏幕外则跳过
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if max(xs) < -50 or min(xs) > sw + 50 or max(ys) < -50 or min(ys) > sh + 50:
                    continue
                try:
                    if len(pts) >= 3:
                        fill_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
                        pygame.draw.polygon(fill_surf, fill_color, pts)
                        surface.blit(fill_surf, (0, 0))
                    pygame.draw.lines(surface, border_color, True, pts, 3)
                except Exception:
                    pass

    # ============================================================
    # 第 2 层：六角格地形
    # ============================================================

    def render(
        self,
        surface: object,
        camera_offset: Tuple[float, float] = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """渲染 1-4 层：六角格地形+水域、势力填充、province边界、势力边界

        Args:
            surface: Pygame Surface
            camera_offset: 相机偏移 (dx, dy)
            camera_zoom: 缩放倍率
        """
        if pygame is None:
            return

        # 1. 六角格地形 + 水域 + 势力填充
        sw = surface.get_width()
        sh = surface.get_height()
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

        for q in range(q_min, q_max + 1):
            for r in range(r_min, r_max + 1):
                tile = self.hex_map.get_tile(HexCoord(q, r))
                if tile is not None:
                    self._draw_hex(surface, tile, camera_offset, camera_zoom)
                else:
                    self._draw_water_hex(surface, HexCoord(q, r), camera_offset, camera_zoom)

        # 2. Province 边界
        self._draw_province_borders(surface, camera_offset, camera_zoom)

        # 3. 势力边界
        self._draw_faction_borders(surface, camera_offset, camera_zoom)

    def _draw_hex(
        self,
        surface: object,
        tile: object,
        camera_offset: Tuple[float, float],
        camera_zoom: float,
    ) -> None:
        """绘制单个六角格（含地形+势力填充+边框）"""
        if pygame is None:
            return

        x, y = axial_to_pixel(tile.coord, self.hex_size * camera_zoom)
        x += camera_offset[0]
        y += camera_offset[1]
        points = self._hex_points(x, y, self.hex_size * camera_zoom)

        terrain_val = tile.terrain.value if hasattr(tile.terrain, 'value') else str(tile.terrain)
        color_cfg = self.colors.get(terrain_val, {})
        fill_color = self._hex_to_rgb(color_cfg.get("fill", "#888888"))
        border_color = self._hex_to_rgb(color_cfg.get("border", "#3a3a3a"))

        pygame.draw.polygon(surface, fill_color, points)

        # 势力领土填充（20% 透明度叠加）
        if tile.faction and tile.faction != "neutral":
            faction_hex = FACTION_COLORS.get(tile.faction, "#888888")
            faction_rgb = self._hex_to_rgb(faction_hex)
            faction_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(faction_surf, (*faction_rgb, 50), points)
            surface.blit(faction_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        pygame.draw.polygon(surface, border_color, points, max(1, int(2 * camera_zoom)))

    def _draw_water_hex(
        self,
        surface: object,
        coord: HexCoord,
        camera_offset: Tuple[float, float],
        camera_zoom: float,
    ) -> None:
        """绘制水域六角格（空白区域）"""
        if pygame is None:
            return
        x, y = axial_to_pixel(coord, self.hex_size * camera_zoom)
        x += camera_offset[0]
        y += camera_offset[1]
        points = self._hex_points(x, y, self.hex_size * camera_zoom)
        water_color = (26, 42, 74)  # #1a2a4a 深蓝水域
        pygame.draw.polygon(surface, water_color, points)

    # ============================================================
    # 第 2.5 层：Province 边界
    # ============================================================

    def _draw_province_borders(
        self,
        surface: object,
        camera_offset: Tuple[float, float] = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """绘制州边界——同州 hex 外轮廓"""
        if pygame is None:
            return

        # 收集每个 province 的 hex 坐标集合
        province_hexes: Dict[str, List[HexCoord]] = {}
        for tile in self.hex_map.iter_tiles():
            if tile.province_id:
                province_hexes.setdefault(tile.province_id, []).append(tile.coord)

        for prov_id, coords in province_hexes.items():
            if len(coords) < 2:
                continue
            coord_set = set(c.to_tuple() for c in coords)

            # 收集外轮廓边：对于每个 hex，检查 6 个邻居，如果邻居不在同 province，则该边是边界
            border_segments = []
            for c in coords:
                cx, cy = axial_to_pixel(c, self.hex_size * camera_zoom)
                cx += camera_offset[0]
                cy += camera_offset[1]
                size = self.hex_size * camera_zoom
                hex_pts = self._hex_points(cx, cy, size)

                for i in range(6):
                    nb_q = c.q + [1, 1, 0, -1, -1, 0][i]
                    nb_r = c.r + [0, -1, -1, 0, 1, 1][i]
                    if (nb_q, nb_r) not in coord_set:
                        # 这条边是 province 边界
                        p1 = hex_pts[i]
                        p2 = hex_pts[(i + 1) % 6]
                        border_segments.append((p1, p2))

            if not border_segments:
                continue

            # 绘制边界线段
            prov_color = (180, 170, 140)  # 淡金色 province 边界
            for p1, p2 in border_segments:
                try:
                    pygame.draw.line(surface, prov_color, p1, p2, max(1, int(2 * camera_zoom)))
                except Exception:
                    pass

    # ============================================================
    # 第 3 层：势力边界
    # ============================================================

    def _draw_faction_borders(
        self,
        surface: object,
        camera_offset: Tuple[float, float] = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """绘制势力边界——在异势力邻格之间的共享边画 3px 粗线"""
        if pygame is None:
            return

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
                self._draw_shared_edge(
                    surface, tile, nb, tile.faction,
                    camera_offset, camera_zoom,
                )

    def _draw_shared_edge(
        self,
        surface: object,
        tile: object,
        neighbor: object,
        faction: str,
        camera_offset: Tuple[float, float],
        camera_zoom: float,
    ) -> None:
        """绘制两个相邻异势力格子的共享边"""
        x1, y1 = axial_to_pixel(tile.coord, self.hex_size * camera_zoom)
        x2, y2 = axial_to_pixel(neighbor.coord, self.hex_size * camera_zoom)
        x1 += camera_offset[0]
        y1 += camera_offset[1]
        x2 += camera_offset[0]
        y2 += camera_offset[1]

        # 共享边垂直平分线中点
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        dx = x2 - x1
        dy = y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1:
            return
        nx = -dy / length * self.hex_size * camera_zoom * 0.55
        ny = dx / length * self.hex_size * camera_zoom * 0.55

        color_hex = FACTION_COLORS.get(faction, "#888888")
        color = self._hex_to_rgb(color_hex)
        try:
            line_width = max(2, int(4 * camera_zoom))
            pygame.draw.line(
                surface, color,
                (mx + nx, my + ny),
                (mx - nx, my - ny),
                line_width,
            )
        except Exception:
            pass

    # ============================================================
    # 第 4 层：城市标记
    # ============================================================

    def render_cities(
        self,
        surface: object,
        cities: dict,
        font: object = None,
        camera_offset: Tuple[float, float] = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """渲染城市标记（圆点 + 名称 + 兵力条）"""
        if pygame is None:
            return

        for city in cities.values():
            x, y = axial_to_pixel(city.position, self.hex_size * camera_zoom)
            x += camera_offset[0]
            y += camera_offset[1]
            ix, iy = int(x), int(y)

            hex_color = FACTION_COLORS.get(city.faction, "#888888")
            color = self._hex_to_rgb(hex_color)

            # 城市等级 → 圆点大小
            radius = int((5 + city.level * 1.8) * camera_zoom)
            radius = max(4, min(radius, 18))

            # 被围困时闪烁红圈
            if city.is_besieged:
                if int(time.time() * 4) % 2 == 0:
                    pygame.draw.circle(surface, (220, 60, 60), (ix, iy), radius + 3, 2)

            pygame.draw.circle(surface, color, (ix, iy), radius)
            pygame.draw.circle(surface, (232, 224, 208), (ix, iy), radius, 2)

            # 城市名（缩放 > 0.45 时显示）
            if camera_zoom > 0.45 and font:
                try:
                    txt = font.render(city.name, True, (232, 224, 208))
                    surface.blit(txt, (ix - txt.get_width() // 2, iy - radius - txt.get_height() - 3))
                except Exception:
                    pass

            # 兵力条
            if city.garrison > 0 and camera_zoom > 0.35:
                max_g = city.level * 1000
                bar_w = max(16, int(24 * camera_zoom))
                bar_h = max(3, int(4 * camera_zoom))
                bar_x = ix - bar_w // 2
                bar_y = iy + radius + 3
                ratio = min(1.0, city.garrison / max_g)
                pygame.draw.rect(surface, (40, 40, 45), (bar_x, bar_y, bar_w, bar_h))
                hp_color = (60, 200, 90) if ratio > 0.5 else (200, 160, 50) if ratio > 0.2 else (200, 60, 60)
                pygame.draw.rect(surface, hp_color, (bar_x, bar_y, int(bar_w * ratio), bar_h))

    # ============================================================
    # 第 5 层：军队图标
    # ============================================================

    def render_armies(
        self,
        surface: object,
        armies: dict,
        cities: dict,
        font: object = None,
        camera_offset: Tuple[float, float] = (0, 0),
        camera_zoom: float = 1.0,
    ) -> None:
        """渲染军队标记（三角箭头 + 数字 + 士气条）"""
        if pygame is None:
            return

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
            size = int(7 * camera_zoom)
            size = max(4, min(size, 14))

            # 根据状态调整方向/形状
            if army.status == ArmyStatus.RETREATING:
                # 撤退：倒三角
                points = [
                    (hx, hy + size),
                    (hx - size * 0.9, hy - size * 0.6),
                    (hx + size * 0.9, hy - size * 0.6),
                ]
            else:
                # 进攻/围城：正三角箭头
                points = [
                    (hx, hy - size),
                    (hx - size * 0.9, hy + size * 0.6),
                    (hx + size * 0.9, hy + size * 0.6),
                ]

            try:
                pygame.draw.polygon(surface, color, points)
                pygame.draw.polygon(surface, (232, 224, 208), points, 1)
            except Exception:
                pass

            # 兵力数字
            label_font = font or pygame.font.Font(None, 12)
            if camera_zoom > 0.4:
                try:
                    txt = label_font.render(str(army.soldiers), True, (232, 224, 208))
                    surface.blit(txt, (hx - txt.get_width() // 2, hy - size - txt.get_height() - 1))
                except Exception:
                    pass

            # 士气条
            if camera_zoom > 0.3:
                bar_w = max(12, int(18 * camera_zoom))
                bar_h = max(2, int(3 * camera_zoom))
                bar_x = int(hx) - bar_w // 2
                bar_y = int(hy) + size + 2
                ratio = max(0.0, min(1.0, army.morale / 100))
                pygame.draw.rect(surface, (40, 40, 45), (bar_x, bar_y, bar_w, bar_h))
                morale_color = (60, 200, 90) if ratio > 0.5 else (200, 160, 50) if ratio > 0.2 else (200, 60, 60)
                pygame.draw.rect(surface, morale_color, (bar_x, bar_y, int(bar_w * ratio), bar_h))

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _hex_points(x: float, y: float, size: float) -> List[Tuple[float, float]]:
        """计算六角格的 6 个顶点"""
        points = []
        for i in range(6):
            angle = math.pi / 3 * i - math.pi / 6
            px = x + size * math.cos(angle)
            py = y + size * math.sin(angle)
            points.append((px, py))
        return points

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """十六进制颜色转 RGB"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
