"""已打开的 V2 事件弹窗应随局内语言切换立即刷新。"""

import unittest

import engine
import i18n
import main
import v2_events


class OpenEventLanguageSwitchTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang(i18n.LANG_ZH)

    def test_open_choice_popup_rebuilds_in_new_language(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        evt = v2_events.EVENTS[0]

        game.show_choice_popup(evt)
        old_popup = game._active_choice_popup
        self.assertEqual(game._active_choice_event.title_for('zh'), evt.title)

        game.toggle_lang()

        self.assertEqual(i18n.get_lang(), i18n.LANG_EN)
        self.assertIs(game._active_choice_event, evt)
        self.assertIsNot(game._active_choice_popup, old_popup)
        self.assertEqual(evt.title_for('en'), evt.title_en)
        self.assertNotEqual(evt.title_for('en'), evt.title)
        game._active_choice_popup.dismiss()


if __name__ == '__main__':
    unittest.main()
