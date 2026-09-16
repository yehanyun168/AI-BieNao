"""科技页按钮应适配文字，并复用事件暂停的所有权规则。"""

import unittest

import engine
import main
from ui_v4_screens import TechPage


class TechPagePauseTests(unittest.TestCase):
    def test_action_button_fits_current_text(self):
        page = TechPage()
        page.btn_action.texture_update()

        self.assertGreaterEqual(page.btn_action.width,
                                page.btn_action.texture_size[0] + 28)
        self.assertEqual(page.btn_action.halign, 'center')

    def test_opening_and_closing_tech_page_pauses_then_resumes(self):
        engine.init_game()
        game = main.GameUI()
        self.assertFalse(game.paused)

        game.open_page('tech')
        self.assertTrue(game.paused)

        game.close_page()
        self.assertFalse(game.paused)

    def test_manually_paused_game_stays_paused_after_tech_page(self):
        engine.init_game()
        game = main.GameUI()
        game.toggle_pause()

        game.open_page('tech')
        game.close_page()

        self.assertTrue(game.paused)

    def test_achievement_page_pauses_and_resumes(self):
        engine.init_game()
        game = main.GameUI()

        game.open_page('ach')
        self.assertTrue(game.paused)

        game.close_page()
        self.assertFalse(game.paused)

    def test_help_page_pauses_and_resumes(self):
        engine.init_game()
        game = main.GameUI()

        game.open_page('help')
        self.assertTrue(game.paused)

        game.close_page()
        self.assertFalse(game.paused)

    def test_skill_page_pauses_and_resumes(self):
        engine.init_game()
        game = main.GameUI()

        game.open_page('skills')
        self.assertTrue(game.paused)

        game.close_page()
        self.assertFalse(game.paused)

    def test_manual_pause_survives_achievement_and_help_pages(self):
        engine.init_game()
        game = main.GameUI()
        game.toggle_pause()

        for name in ('skills', 'ach', 'help'):
            game.open_page(name)
            game.close_page()
            self.assertTrue(game.paused)


if __name__ == '__main__':
    unittest.main()
