"""事件日志行应按换行后的文本高度自动扩展。"""

import unittest

from kivy.clock import Clock

import main  # 注册项目字体
from ui_v4 import LogRow


def pump_clock(frames=8):
    for _ in range(frames):
        Clock.tick()


class LogRowHeightTests(unittest.TestCase):
    def test_long_wrapped_log_is_taller_than_short_log(self):
        short = LogRow('Short event')
        short.width = 300
        long = LogRow('A long event description that must wrap across multiple lines '
                      'so every part remains readable in the event log drawer.')
        long.width = 180
        pump_clock()

        self.assertGreaterEqual(short.height, 32)
        self.assertGreater(long.height, short.height)
        self.assertGreaterEqual(long.height, long.lbl.texture_size[1] + 12)


if __name__ == '__main__':
    unittest.main()
