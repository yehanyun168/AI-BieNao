"""世界地图横向铺满，并以顶边为锚保持 2:1 比例。"""

import unittest

import main  # noqa: F401 - 注册项目字体后再构建地图标签
from world_map import WorldMap


class WorldMapLayoutTests(unittest.TestCase):
    def test_map_fills_width_and_expands_down_from_top(self):
        world = WorldMap()
        world.pos = (30, 40)
        world.size = (1200, 400)

        x, y, width, height = world._map_rect()

        self.assertEqual(x, world.x)
        self.assertEqual(width, world.width)
        self.assertEqual(height, 600)
        self.assertEqual(y + height, world.top)

    def test_tall_stage_keeps_map_top_aligned(self):
        world = WorldMap()
        world.pos = (10, 20)
        world.size = (1000, 700)

        x, y, width, height = world._map_rect()

        self.assertEqual((x, width, height), (10, 1000, 500))
        self.assertEqual(y + height, world.top)


if __name__ == '__main__':
    unittest.main()
