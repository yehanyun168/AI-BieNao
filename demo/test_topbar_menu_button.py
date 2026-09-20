"""顶部齿轮按钮应复用 Esc 的暂停菜单入口。"""

import unittest
from unittest.mock import Mock

import engine
import main
from ui_v4 import SPR_GEAR


class TopbarMenuButtonTests(unittest.TestCase):
    def setUp(self):
        engine.init_game()
        self.view = main.GameUI()

    def test_gear_button_is_before_compute_stat(self):
        bar = self.view.menu_chip.parent
        children = list(reversed(bar.children))

        self.assertIs(children[0], self.view.menu_chip)
        self.assertIn(self.view.stats_compute, children[1].children)
        self.assertAlmostEqual(self.view.menu_chip.width,
                               self.view.menu_chip.height)
        self.assertEqual(tuple(self.view.menu_chip_icon._rows), SPR_GEAR)

    def test_gear_button_uses_esc_fallback(self):
        self.view._esc_fallback = Mock()

        self.view.menu_chip._on_press(self.view.menu_chip)

        self.view._esc_fallback.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
