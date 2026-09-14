"""所有语言入口应共享状态，并完整刷新当前页面。"""

import unittest
from types import SimpleNamespace

import engine
import i18n
import main
import ui_v4_screens as screens


class UnifiedLanguageSwitchTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang(i18n.LANG_ZH)

    def test_settings_switch_reflects_current_language(self):
        i18n.set_lang(i18n.LANG_EN)
        page = screens.SettingsPage()
        self.assertEqual(page.lbl_lang_val.current, 1)

    def test_game_settings_switch_rebuilds_open_page(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.open_page('settings')

        game._page.lbl_lang_val.set_current(1, notify=True)

        self.assertEqual(i18n.get_lang(), i18n.LANG_EN)
        self.assertIsInstance(game._page, screens.SettingsPage)
        self.assertEqual(game._page.lbl_lang_val.current, 1)
        self.assertEqual(game._page.lbl_title.text, i18n.t('set_page_title'))

    def test_game_top_switch_rebuilds_open_help_page(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.open_page('help')

        game.toggle_lang()

        self.assertIsInstance(game._page, screens.HelpPage)
        self.assertEqual(game._page.lbl_title.text, i18n.t('help_page_title'))

    def test_clicking_game_language_chip_uses_unified_switch(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        touch = SimpleNamespace(pos=game.lang_switch.center)

        handled = game.lang_switch.on_touch_down(touch)

        self.assertTrue(handled)
        self.assertEqual(i18n.get_lang(), i18n.LANG_EN)
        self.assertIn(i18n.t('stats_compute'), game.stats_compute.text)
        self.assertEqual(game.lbl_tick_cap.text, i18n.t('stats_tick'))

    def test_game_language_switch_translates_command_rail(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()

        game.toggle_lang()

        for key in ('drop', 'tech', 'skills', 'log', 'ach'):
            self.assertEqual(game.rail.buttons[key]._caption, i18n.t(f'rail_{key}'))

    def test_menu_settings_switch_keeps_translated_settings_open(self):
        i18n.set_lang(i18n.LANG_ZH)
        menu = main.MainMenu()
        menu._open_settings()

        menu._overlay.lbl_lang_val.set_current(1, notify=True)

        self.assertEqual(i18n.get_lang(), i18n.LANG_EN)
        self.assertIsInstance(menu._overlay, screens.SettingsPage)
        self.assertEqual(menu._overlay.lbl_lang_val.current, 1)
        self.assertEqual(menu._overlay.lbl_title.text, i18n.t('set_page_title'))


if __name__ == '__main__':
    unittest.main()
