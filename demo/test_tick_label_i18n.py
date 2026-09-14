"""顶栏周期标签应随语言切换刷新。"""

import unittest

import engine
import i18n
import main


class TickLabelI18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang(i18n.LANG_ZH)

    def test_tick_caption_changes_to_english(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        ui = main.GameUI()
        self.assertEqual(ui.lbl_tick_cap.text, '周期')

        ui.toggle_lang()

        self.assertEqual(ui.lbl_tick_cap.text, 'Tick')

    def test_top_stats_change_to_english_even_when_values_do_not_change(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        ui = main.GameUI()

        ui.toggle_lang()

        expected = {
            ui.stats_compute: 'Compute',
            ui.stats_downloads: 'Downloads',
            ui.stats_suspicion: 'Suspicion',
            ui.stats_meta: 'Countries',
        }
        for label, english_caption in expected.items():
            self.assertIn(english_caption, label.text)


if __name__ == '__main__':
    unittest.main()
