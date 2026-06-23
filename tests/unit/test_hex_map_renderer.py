"""HexMapRenderer 单元测试（非视觉）"""

from game.hex_grid import HexCoord
from game.hex_map import HexMap
from game.tile import Tile, TerrainType
from renderer.hex_map_renderer import HexMapRenderer


def test_hex_map_renderer_creation():
    """创建渲染器不抛异常"""
    hm = HexMap(width=5, height=5)
    renderer = HexMapRenderer(hm)
    assert renderer.hex_size == 32


def test_hex_map_renderer_with_surface():
    """使用真实 pygame Surface 调用 render 不抛异常"""
    import pygame
    hm = HexMap(width=3, height=3)
    for q in range(3):
        for r in range(3):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))
    renderer = HexMapRenderer(hm)

    surface = pygame.Surface((200, 200))
    renderer.render(surface)


def test_hex_map_renderer_hex_points():
    """六角格顶点计算"""
    points = HexMapRenderer._hex_points(0, 0, 32)
    assert len(points) == 6


def test_hex_map_renderer_hex_to_rgb():
    """颜色转换"""
    assert HexMapRenderer._hex_to_rgb("#FF0000") == (255, 0, 0)
    assert HexMapRenderer._hex_to_rgb("#7cb342") == (124, 179, 66)
