"""V2 选择事件的中英文数据与运行时选择。"""

import json
import os
import unittest

import engine
import i18n
import v2_events


EVENTS_PATH = os.path.join(os.path.dirname(__file__), '..', 'v2', 'events.json')


class V2EventI18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang(i18n.LANG_ZH)

    def test_every_event_and_option_has_english_text(self):
        with open(EVENTS_PATH, encoding='utf-8') as f:
            raw_events = json.load(f)

        for evt in raw_events:
            self.assertTrue(evt.get('title_en'), evt['id'])
            self.assertTrue(evt.get('flavor_en'), evt['id'])
            for index, option in enumerate(evt.get('options', [])):
                self.assertTrue(option.get('text_en'), f"{evt['id']} option {index}")

    def test_loaded_event_selects_requested_language(self):
        evt = v2_events.load_events(EVENTS_PATH)[0]

        self.assertEqual(evt.title_for('en'), '🚀 Major US AI Model Launch')
        self.assertEqual(evt.flavor_for('zh'), '美国一家明星 AI 公司发布了新模型，全球 AI 关注度暴涨。')
        self.assertEqual(evt.options[0].text_for('en'), 'Ride the hype and respond now')

    def test_choice_history_uses_current_language(self):
        evt = v2_events.load_events(EVENTS_PATH)[0]
        engine.init_game()
        i18n.set_lang(i18n.LANG_EN)

        engine.resolve_choice(evt, 0)

        self.assertIn(evt.title_for('en'), engine.player.events_history[0])
        self.assertIn(evt.options[0].text_for('en'), engine.player.events_history[0])
        self.assertNotIn(evt.title, engine.player.events_history[0])


if __name__ == '__main__':
    unittest.main()
