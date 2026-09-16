"""科技树网络图应使用淡化的机房背景，且不遮挡节点交互层。"""

import os
import unittest

import main  # 注册字体并完成 Kivy 配置
from kivy.clock import Clock
from ui_v4_screens import TechPage


class TechBackgroundTests(unittest.TestCase):
    def test_background_asset_and_layer_order(self):
        page = TechPage()

        self.assertTrue(os.path.isfile(page.tech_bg.source))
        self.assertEqual(page.tech_bg.fit_mode, 'cover')
        self.assertAlmostEqual(page._tech_bg_tint.rgba[3], 0.72)
        self.assertIs(page.tech_bg.parent, page.graph_stage)
        self.assertIs(page.tech_bg_overlay.parent, page.graph_stage)
        self.assertIs(page.canvas_view.parent, page.graph_stage)
        # Kivy children 为逆添加顺序：画布在最上，遮罩居中，图片在最下。
        self.assertLess(page.graph_stage.children.index(page.canvas_view),
                        page.graph_stage.children.index(page.tech_bg_overlay))
        self.assertLess(page.graph_stage.children.index(page.tech_bg_overlay),
                        page.graph_stage.children.index(page.tech_bg))

    def test_background_fills_stage_without_stretching_ratio(self):
        page = TechPage()
        page.graph_stage.size = (1200, 500)
        page.graph_stage.pos = (30, 40)
        page.graph_stage.do_layout()
        Clock.tick()

        self.assertEqual(page.tech_bg.pos, page.graph_stage.pos)
        self.assertEqual(page.tech_bg.size, page.graph_stage.size)
        self.assertEqual(page.tech_bg_overlay.pos, page.graph_stage.pos)
        self.assertEqual(page.tech_bg_overlay.size, page.graph_stage.size)
        self.assertEqual(tuple(page._tech_bg_rect.pos),
                         tuple(page.graph_stage.pos))
        self.assertEqual(tuple(page._tech_bg_rect.size),
                         tuple(page.graph_stage.size))
        self.assertEqual(page.tech_bg.fit_mode, 'cover')


if __name__ == '__main__':
    unittest.main()
