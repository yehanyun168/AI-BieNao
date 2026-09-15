"""窗口尺寸变化结束后应自动执行一次“适配窗口”。"""

import unittest
from unittest.mock import patch

import engine
import main


class AutoFitResizeTests(unittest.TestCase):
    def _assert_auto_fit(self, view, resize_method):
        resize_method(None, 1200, 800)
        event = getattr(view, '_resize_fit_event', None)
        self.assertIsNotNone(event)
        event.cancel()

        with patch.object(view, '_apply_scale') as apply_scale:
            view._fit_after_resize(0)

        apply_scale.assert_called_once_with()

        self.assertFalse(hasattr(view, 'user_scale'))

    def test_game_ui_auto_fits_after_resize(self):
        engine.init_game()
        view = main.GameUI()
        self._assert_auto_fit(view, view._on_window_resize)

    def test_main_menu_auto_fits_after_resize(self):
        view = main.MainMenu()
        self._assert_auto_fit(view, view._on_resize)


if __name__ == '__main__':
    unittest.main()
