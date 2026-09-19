"""帮助页世界旗林使用较紧凑的旗帜尺寸。"""

import unittest

import main  # noqa: F401  # 注册项目字体后再构建 Kivy 页面
from flag_draw import FlagWidget
from ui_v4_syspages import HelpPage


class HelpFlagSizeTests(unittest.TestCase):
    def test_help_flags_are_compact(self):
        page = HelpPage()
        flags = [w for w in page.walk() if isinstance(w, FlagWidget)]

        self.assertEqual(len(flags), 20)
        self.assertTrue(all(tuple(flag.size) == (160, 104) for flag in flags))


if __name__ == '__main__':
    unittest.main()
