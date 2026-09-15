"""科技详情按钮应与 Enter 使用同一个解锁动作。"""
import unittest

import engine
import main


class TechMouseActionTests(unittest.TestCase):
    def test_unlock_button_unlocks_selected_t0(self):
        engine.init_game()
        engine.player.compute = 10000
        game = main.GameUI()
        game.open_page('tech')
        page = game._page
        page._on_node_pick('t0:localization')

        self.assertFalse(page.btn_action.disabled)
        page.btn_action.trigger_action(duration=0)

        self.assertTrue(engine.player.tech.t0_unlocked['localization'])


if __name__ == '__main__':
    unittest.main()
