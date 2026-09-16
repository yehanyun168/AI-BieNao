"""地图左侧指令栏应使用横向按钮，并避免与国家检视面板冲突。"""

import unittest

import engine
import main  # 注册字体并完成 Kivy 配置
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from ui_hud import RailBar
from ui_v4 import RailButton


class RailLayoutTests(unittest.TestCase):
    def test_button_uses_horizontal_left_aligned_layout(self):
        button = RailButton('◆', '科技')

        self.assertEqual(button.size, [128, 56])
        self.assertEqual(button.halign, 'left')
        self.assertEqual(button.valign, 'middle')
        self.assertEqual(button.padding, [12, 0, 12, 0])
        self.assertEqual(button.CAPTION_FS, 18)
        self.assertEqual(button.text_size, [128, 56])
        self.assertNotIn('\n', button.text)
        self.assertIn('◆', button.text)
        self.assertIn('科技', button.text)
        Clock.tick()
        self.assertLessEqual(button.texture_size[1], button.height)

    def test_rail_is_left_centered_and_scales_together(self):
        items = [(str(i), '◆', f'按钮{i}') for i in range(6)]
        rail = RailBar(items)
        stage = FloatLayout(size=(1000, 600))
        stage.add_widget(rail)
        rail._layout_hud()

        self.assertEqual(rail.box.spacing, 6)
        self.assertEqual((rail._content_w, rail._content_h), (140, 378))
        self.assertEqual(rail.x, stage.x + 6)
        self.assertEqual(rail.center_y, stage.center_y)

        rail.refresh_scale(1.25)

        self.assertEqual(rail.box.spacing, 7.5)
        self.assertEqual((rail._content_w, rail._content_h), (172, 469.5))
        for button in rail.buttons.values():
            self.assertEqual(button.size, [160, 70])
            self.assertEqual(button.text_size, [160, 70])
            self.assertEqual(button.padding, [15, 0, 15, 0])

    def test_country_inspector_temporarily_hides_rail(self):
        engine.init_game()
        game = main.GameUI()

        game._open_inspector('CN')

        self.assertEqual(game.rail.opacity, 0)
        self.assertTrue(all(button.disabled for button in game.rail.buttons.values()))

        game._close_inspector()

        self.assertEqual(game.rail.opacity, 1)
        self.assertTrue(all(not button.disabled for button in game.rail.buttons.values()))


if __name__ == '__main__':
    unittest.main()
