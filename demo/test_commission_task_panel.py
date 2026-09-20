"""委托应集中在左侧任务按钮打开的弹窗中。"""

import unittest

from kivy.uix.button import Button

import engine
import main
from commissions import CommissionState


def _button_texts(root):
    texts = []
    stack = [root]
    while stack:
        widget = stack.pop()
        if isinstance(widget, Button):
            texts.append(widget.text)
        stack.extend(getattr(widget, 'children', ()))
    return texts


class CommissionTaskPanelTests(unittest.TestCase):
    def setUp(self):
        engine.init_game(seed=1)
        self.game = main.GameUI()

    def tearDown(self):
        popup = getattr(self.game, '_commission_list_popup', None)
        if popup is not None:
            popup.dismiss()

    def test_rail_has_task_button_and_old_map_bar_is_gone(self):
        self.assertIn('tasks', self.game.rail.buttons)
        self.assertFalse(hasattr(self.game, 'commission_bar'))

    def test_task_popup_lists_every_current_commission(self):
        engine.player.commissions = [
            CommissionState(101, 'a', 'compute', '◆', '算力委托',
                            'Compute job', 5, 1.0),
            CommissionState(102, 'b', 'downloads', '◇', '下载委托',
                            'Download job', 4, 1.0, status='active'),
        ]

        self.game.show_commission_list()

        texts = _button_texts(self.game._commission_list_popup.content)
        self.assertTrue(any('算力委托' in text for text in texts))
        self.assertTrue(any('下载委托' in text for text in texts))

    def test_task_popup_uses_event_pause_ownership(self):
        self.assertFalse(self.game.paused)

        self.game.show_commission_list()
        self.assertTrue(self.game.paused)

        self.game._commission_list_popup.dismiss()
        self.assertFalse(self.game.paused)

    def test_manual_pause_survives_task_popup(self):
        self.game.toggle_pause()

        self.game.show_commission_list()
        self.game._commission_list_popup.dismiss()

        self.assertTrue(self.game.paused)


if __name__ == '__main__':
    unittest.main()
