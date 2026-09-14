"""事件弹窗应复用手动暂停状态与界面同步逻辑。"""

import unittest
from unittest.mock import patch

import engine
import main
import v2_events
from i18n import t


class _FakePopup:
    def open(self):
        pass

    def dismiss(self, *_args):
        pass


class EventPauseTests(unittest.TestCase):
    def _assert_manual_pause_state(self, game):
        self.assertTrue(game.paused)
        self.assertGreaterEqual(game._paused_remaining, 0.0)
        self.assertIn(t('quick_resume'), game.btn_pause.text)

    def test_v2_event_uses_manual_pause_state(self):
        engine.init_game()
        game = main.GameUI()
        event = next(evt for evt in v2_events.EVENTS if evt.options)
        with patch('ui_popups.make_modal', return_value=_FakePopup()):
            game.show_choice_popup(event)
        self._assert_manual_pause_state(game)

    def test_crisis_event_uses_manual_pause_state(self):
        engine.init_game()
        game = main.GameUI()
        with patch('ui_popups.make_modal', return_value=_FakePopup()):
            game.show_crisis_popup()
        self._assert_manual_pause_state(game)


if __name__ == '__main__':
    unittest.main()
