"""结局弹窗打开时，Esc 应只关闭弹窗，不能穿透到后方页面。"""

import unittest
from unittest.mock import patch

import endings
import engine
import main


class _PopupProbe:
    def __init__(self):
        self.dismissed = False
        self._binds = {}

    def open(self):
        pass

    def bind(self, **kwargs):
        self._binds.update(kwargs)

    def dismiss(self, *_args):
        self.dismissed = True
        callback = self._binds.get('on_dismiss')
        if callback is not None:
            callback(self)


class EndingEscapeTests(unittest.TestCase):
    def test_escape_closes_ending_without_closing_background_page(self):
        engine.init_game()
        game = main.GameUI()
        game.open_page('help')
        background_page = game._page
        popup = _PopupProbe()

        with patch('ui_popups.make_modal', return_value=popup):
            game.show_ending_popup(endings.ENDINGS[0])

        handled = game._on_keyboard_down(None, (27, 'escape'), '', [])

        self.assertTrue(handled)
        self.assertTrue(popup.dismissed)
        self.assertIs(game._page, background_page)


if __name__ == '__main__':
    unittest.main()
