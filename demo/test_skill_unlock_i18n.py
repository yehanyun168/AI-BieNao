"""技能解锁条件中的科技名称应跟随界面语言。"""

import unittest

import engine
import main
from i18n import get_lang, set_lang


class SkillUnlockI18nTests(unittest.TestCase):
    def setUp(self):
        self.old_lang = get_lang()
        engine.init_game()
        self.game = main.GameUI()

    def tearDown(self):
        set_lang(self.old_lang)

    def test_unlock_hint_uses_english_tech_name(self):
        set_lang('en')

        text = self.game._skill_unlock_text('algo_top')

        self.assertIn('Platform Reach', text)
        self.assertNotIn('平台渗透', text)

    def test_unlock_hint_uses_chinese_tech_name(self):
        set_lang('zh')

        text = self.game._skill_unlock_text('algo_top')

        self.assertIn('平台渗透', text)


if __name__ == '__main__':
    unittest.main()
