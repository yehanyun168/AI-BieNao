"""Esc 应打开带设置、存档、退出三项的暂停菜单。"""

import unittest
from unittest.mock import Mock

from kivy.clock import Clock

import engine
import main
import save_manager
from i18n import t
from ui_v4_screens import SavePage, SettingsPage


class EscPauseMenuTests(unittest.TestCase):
    def setUp(self):
        engine.init_game(seed=1)
        self.game = main.GameUI()

    def tearDown(self):
        popup = getattr(self.game, '_pause_menu_popup', None)
        if popup is not None:
            popup.dismiss()

    def test_esc_menu_pauses_and_has_three_vertical_actions(self):
        self.game.pause_menu()

        self.assertTrue(self.game.paused)
        self.assertIsNotNone(self.game._pause_menu_popup)
        buttons = self.game._pause_menu_buttons
        self.assertEqual([button.text for button in buttons],
                         [t('pause_menu_settings'), t('pause_menu_save'),
                          t('pause_menu_exit')])
        self.assertTrue(buttons[0].disabled is False)
        self.assertFalse(buttons[1].disabled)
        self.assertFalse(buttons[2].disabled)
        self.assertTrue(all(button.height >= 72 for button in buttons))
        self.assertTrue(all(button.font_size >= 20 for button in buttons))
        self.assertGreaterEqual(self.game._pause_menu_body.spacing, 14)

    def test_pause_menu_intrinsic_height_includes_padding_and_spacing(self):
        self.game.pause_menu()
        body = self.game._pause_menu_body
        fixed = sum(child.height for child in body.children
                    if child.size_hint_y is None)
        vertical_padding = body.padding[1] + body.padding[3]
        required = fixed + body.spacing * (len(body.children) - 1) + vertical_padding

        self.assertGreaterEqual(self.game._pause_menu_panel.height, required)

    def test_closing_pause_menu_resumes_owned_pause(self):
        self.game.pause_menu()
        self.game._pause_menu_popup.dismiss()

        self.assertFalse(self.game.paused)

    def test_settings_back_returns_to_paused_menu(self):
        self.game.pause_menu()
        self.game._open_pause_settings()

        self.assertTrue(self.game.paused)
        self.assertIsInstance(self.game._page, SettingsPage)

        self.game._close_page_user()
        Clock.tick()

        self.assertTrue(self.game.paused)
        self.assertIsNone(self.game._page)
        self.assertIsNotNone(self.game._pause_menu_popup)

    def test_manual_pause_survives_menu_and_settings(self):
        self.game.toggle_pause()
        self.game.pause_menu()
        self.game._open_pause_settings()
        self.game._close_page_user()
        Clock.tick()

        self.assertTrue(self.game.paused)
        self.assertIsNotNone(self.game._pause_menu_popup)

    def test_save_action_opens_separate_save_page_and_keeps_pause(self):
        self.game.pause_menu()
        self.game._open_pause_saves()

        self.assertTrue(self.game.paused)
        self.assertIsInstance(self.game._page, SavePage)
        self.assertEqual(len(self.game._page.slot_box.children),
                         len(save_manager.slot_names()) + 2)

        self.game._close_page_user()
        Clock.tick()

        self.assertTrue(self.game.paused)
        self.assertIsNone(self.game._page)
        self.assertIsNotNone(self.game._pause_menu_popup)

    def test_exit_action_uses_existing_back_to_menu_confirmation(self):
        self.game._confirm_back_to_menu = Mock()
        self.game.pause_menu()

        self.game._pause_menu_buttons[2].dispatch('on_release')

        self.game._confirm_back_to_menu.assert_called_once()
        self.assertTrue(self.game.paused)

    def test_cancel_exit_confirmation_returns_to_paused_menu(self):
        self.game.pause_menu()
        self.game._open_pause_exit()

        self.assertTrue(self.game.paused)
        self.assertIsNotNone(self.game._back_to_menu_popup)
        self.game._back_to_menu_popup.dismiss()
        Clock.tick()

        self.assertTrue(self.game.paused)
        self.assertIsNotNone(self.game._pause_menu_popup)


if __name__ == '__main__':
    unittest.main()
