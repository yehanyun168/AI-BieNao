"""日志打开期间视为已读，关闭后恢复未读累加。"""

import unittest

import engine
import main


class ConsoleLogTests(unittest.TestCase):
    def setUp(self):
        engine.init_game()
        self.game = main.GameUI()

    def test_opening_log_clears_and_pauses_unread_until_close(self):
        self.game.stats.push_log(1, '测试日志')
        self.game.toggle_console()

        self.assertEqual(self.game.stats.unread, 0)
        self.assertIsNotNone(self.game._console)

        self.game.stats.push_log(2, '打开日志期间的新消息')
        self.assertEqual(self.game.stats.unread, 0)

        self.game._close_console()
        self.game.stats.push_log(3, '关闭日志后的新消息')

        self.assertEqual(self.game.stats.unread, 1)
        self.assertIsNone(self.game._console)

    def test_close_without_open_drawer_does_not_discard_unread(self):
        self.game.stats.push_log(1, '尚未查看的日志')

        self.game._close_console()

        self.assertEqual(self.game.stats.unread, 1)

    def test_grave_key_and_middle_dot_toggle_console(self):
        handled = self.game._on_keyboard_down(None, (96, '`'), '`', [])
        self.assertTrue(handled)
        self.assertIsNotNone(self.game._console)

        handled = self.game._on_keyboard_down(None, (0, 'unknown'), '·', [])
        self.assertTrue(handled)
        self.assertIsNone(self.game._console)

    def test_log_button_is_removed_from_game_rail(self):
        self.assertNotIn('log', self.game.rail.buttons)


if __name__ == '__main__':
    unittest.main()
