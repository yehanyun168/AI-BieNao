"""对局顶栏不显示品牌标题，统计参数从左侧开始排列。"""

import unittest

import engine
import main


class TopbarWithoutLogoTests(unittest.TestCase):
    def test_stats_are_first_group_and_language_switch_still_works(self):
        engine.init_game()
        game = main.GameUI()
        bar = game._root_box.children[-1].children[0]
        first = list(reversed(bar.children))[0]

        self.assertFalse(hasattr(game, 'lbl_logo'))
        self.assertIn(game.stats_compute, first.children)
        game.toggle_lang()


if __name__ == '__main__':
    unittest.main()
