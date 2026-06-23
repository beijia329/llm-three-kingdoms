"""2D 相机系统

支持平移（WASD/方向键/中键拖拽）和缩放（滚轮/加减键）。
"""

from __future__ import annotations


class Camera:
    """2D 相机：平移 + 缩放

    Attributes:
        x, y: 相机偏移（世界坐标原点在屏幕上的位置）
        zoom: 缩放倍率
    """

    def __init__(self, x: float = 0, y: float = 0, zoom: float = 1.0) -> None:
        self.x = x
        self.y = y
        self.zoom = zoom
        self.min_zoom = 0.2
        self.max_zoom = 4.0

        # 平移速度
        self.pan_speed: float = 10.0

    def move(self, dx: float, dy: float) -> None:
        """平移相机

        Args:
            dx: 水平移动量（屏幕像素）
            dy: 垂直移动量（屏幕像素）
        """
        self.x += dx / self.zoom
        self.y += dy / self.zoom

    def zoom_at(self, factor: float, screen_x: float, screen_y: float) -> None:
        """以屏幕某点为中心缩放

        Args:
            factor: 缩放因子（>1 放大，<1 缩小）
            screen_x: 锚点屏幕 x 坐标
            screen_y: 锚点屏幕 y 坐标
        """
        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        if new_zoom == self.zoom:
            return

        # 以锚点为中心缩放
        wx = (screen_x - self.x) / self.zoom
        wy = (screen_y - self.y) / self.zoom
        self.x = screen_x - wx * new_zoom
        self.y = screen_y - wy * new_zoom
        self.zoom = new_zoom

    def world_to_screen(self, wx: float, wy: float) -> tuple:
        """世界坐标 → 屏幕坐标

        Args:
            wx: 世界 x
            wy: 世界 y

        Returns:
            (screen_x, screen_y)
        """
        return (
            wx * self.zoom + self.x,
            wy * self.zoom + self.y,
        )

    def screen_to_world(self, sx: float, sy: float) -> tuple:
        """屏幕坐标 → 世界坐标

        Args:
            sx: 屏幕 x
            sy: 屏幕 y

        Returns:
            (world_x, world_y)
        """
        return (
            (sx - self.x) / self.zoom,
            (sy - self.y) / self.zoom,
        )

    def handle_event(self, event) -> bool:
        """处理 Pygame 输入事件

        Args:
            event: Pygame 事件

        Returns:
            True 表示事件已被处理
        """
        try:
            import pygame

            # 滚轮缩放
            if event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                factor = 1.1 if event.y > 0 else 0.9
                self.zoom_at(factor, mouse_x, mouse_y)
                return True

            # 中键拖拽平移
            if event.type == pygame.MOUSEMOTION and event.buttons[1]:
                self.move(-event.rel[0], -event.rel[1])
                return True

            # 键盘平移
            if event.type == pygame.KEYDOWN:
                step = self.pan_speed
                if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    self.move(step, 0)
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    self.move(-step, 0)
                elif event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.move(0, step)
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    self.move(0, -step)
                elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    self.zoom_at(1.1, 400, 300)
                elif event.key == pygame.K_MINUS:
                    self.zoom_at(0.9, 400, 300)
                else:
                    return False
                return True
        except ImportError:
            pass
        return False
