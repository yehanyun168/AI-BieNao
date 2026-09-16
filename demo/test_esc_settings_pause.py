"""Esc 设置页应复用事件暂停机制，并保留玩家原有暂停状态。"""

import unittest

import engine
import main
from ui_v4_screens import SettingsPage


class EscSettingsPauseTests(unittest.TestCase):
    def test_esc_settings_pauses_and_closing_resumes(self):
        engine.init_game()
        game = main.GameUI()

        game.pause_menu()

        self.assertTrue(game.paused)
        self.assertIsInstance(game._page, SettingsPage)

        game.close_page()
        self.assertFalse(game.paused)

    def test_manual_pause_survives_esc_settings(self):
        engine.init_game()
        game = main.GameUI()
        game.toggle_pause()

        game.pause_menu()
        game.close_page()

        self.assertTrue(game.paused)


if __name__ == '__main__':
    unittest.main()
