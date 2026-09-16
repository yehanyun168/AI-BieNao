"""日志打开期间视为已读，关闭后恢复未读累加。"""

import unittest

import engine
import main


class LogUnreadStateTests(unittest.TestCase):
    def setUp(self):
        engine.init_game()
        self.game = main.GameUI()

    def test_opening_log_clears_and_pauses_unread_until_close(self):
        self.game.stats.push_log(1, '测试日志')
        self.game.rail.buttons['log'].set_badge(self.game.stats.unread)

        self.game.toggle_log()

        self.assertEqual(self.game.stats.unread, 0)
        self.assertEqual(self.game.rail.buttons['log']._badge, 0)

        self.game.stats.push_log(2, '打开日志期间的新消息')
        self.assertEqual(self.game.stats.unread, 0)

        self.game._close_log()
        self.game.stats.push_log(3, '关闭日志后的新消息')

        self.assertEqual(self.game.stats.unread, 1)
        self.assertIsNone(self.game._log_drawer)

    def test_close_without_open_drawer_does_not_discard_unread(self):
        self.game.stats.push_log(1, '尚未查看的日志')

        self.game._close_log()

        self.assertEqual(self.game.stats.unread, 1)


if __name__ == '__main__':
    unittest.main()
