"""事件弹窗应复用手动暂停状态与界面同步逻辑。"""

import unittest
from unittest.mock import patch

import engine
import main
import v2_events
import ui_v4 as U
from i18n import t


class _FakePopup:
    """弹窗桩：除 open/dismiss 外，还需支持 bind（弹窗关闭时清「活跃弹窗」标记）。

    2026-09-14：ui_popups.show_choice_popup 增加了 bind(on_dismiss=_clear_active)
    （关闭弹窗时复位 _active_popup），原桩缺 bind 会 AttributeError。
    """

    def __init__(self):
        self._binds = {}

    def open(self):
        pass

    def dismiss(self, *_args):
        pass

    def bind(self, **kwargs):
        self._binds.update(kwargs)

    def unbind(self, **kwargs):
        for k in kwargs:
            self._binds.pop(k, None)


class EventPauseTests(unittest.TestCase):
    @staticmethod
    def _find(widget, cls):
        if isinstance(widget, cls):
            return widget
        for child in getattr(widget, 'children', ()):
            found = EventPauseTests._find(child, cls)
            if found is not None:
                return found
        return None

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

    def test_selecting_event_resumes_when_event_paused_running_game(self):
        engine.init_game()
        game = main.GameUI()
        event = next(evt for evt in v2_events.EVENTS if len(evt.options) > 1)
        popup = _FakePopup()

        def _modal(content, **_kwargs):
            popup.content = content
            return popup

        with patch('ui_popups.make_modal', side_effect=_modal):
            game.show_choice_popup(event)
        self._find(popup.content, U.OptButton)._on_click(0)

        self.assertFalse(game.paused)
        self.assertIsNotNone(game.tick_event)

    def test_selecting_event_preserves_preexisting_manual_pause(self):
        engine.init_game()
        game = main.GameUI()
        game.toggle_pause()
        event = next(evt for evt in v2_events.EVENTS if len(evt.options) > 1)
        popup = _FakePopup()

        def _modal(content, **_kwargs):
            popup.content = content
            return popup

        with patch('ui_popups.make_modal', side_effect=_modal):
            game.show_choice_popup(event)
        self._find(popup.content, U.OptButton)._on_click(0)

        self.assertTrue(game.paused)


if __name__ == '__main__':
    unittest.main()
