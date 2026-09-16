"""区域筛选栏应从地图顶部稍微下沉。"""

import unittest

import engine
import main


class RegionHudOffsetTests(unittest.TestCase):
    def test_region_hud_is_inset_from_map_top(self):
        engine.init_game()
        game = main.GameUI()
        hud = game.region_hud
        hud._layout_hud()

        self.assertEqual(hud._top_inset, 8)
        self.assertEqual(hud.top, game.map_stage.top - 6 - 8)


if __name__ == '__main__':
    unittest.main()
