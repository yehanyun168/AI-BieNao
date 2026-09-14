"""显示、声音和回合速度偏好应跨启动持久化。"""

import os
import tempfile
import unittest

import bgm
import i18n
import main  # 注册 Kivy 中文字体后再实例化设置页
import preferences
import ui_preferences
import sfx
import ui_shared as ST
from ui_v4_screens import SettingsPage


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = preferences.SETTINGS_PATH
        preferences.SETTINGS_PATH = os.path.join(self.tmp.name, 'settings.json')

    def tearDown(self):
        preferences.SETTINGS_PATH = self.old_path
        self.tmp.cleanup()

    def test_all_settings_round_trip_and_apply(self):
        expected = {
            'language': 'en', 'speed_idx': 3, 'reduce_motion': True,
            'grid_mode': 2, 'a11y_shapes': False, 'sound_on': False,
            'music_on': False, 'ui_scale': 1.3,
        }
        preferences.save(expected)

        loaded = ui_preferences.load_and_apply()

        self.assertEqual(loaded, expected)
        self.assertEqual(i18n.get_lang(), 'en')
        self.assertEqual(ST.CURRENT_SPEED_IDX, 3)
        self.assertTrue(ST.REDUCE_MOTION)
        self.assertEqual(ST.GRID_MODE, 2)
        self.assertFalse(ST.A11Y_SHAPES)
        self.assertFalse(sfx.SFX_ON)
        self.assertFalse(bgm.BGM_ON)
        self.assertEqual(preferences.get('ui_scale'), 1.3)

    def test_invalid_file_falls_back_to_defaults(self):
        with open(preferences.SETTINGS_PATH, 'w', encoding='utf-8') as f:
            f.write('{broken')

        loaded = preferences.load()

        self.assertEqual(loaded, preferences.DEFAULTS)

    def test_settings_page_reflects_saved_choices(self):
        values = dict(preferences.DEFAULTS, speed_idx=3, grid_mode=2,
                      reduce_motion=True, sound_on=False, ui_scale=1.3)
        page = SettingsPage(values=values)

        self.assertEqual(page.sw_speed.current, 3)
        self.assertEqual(page.sw_grid.current, 2)
        self.assertEqual(page.sw_motion.current, 1)
        self.assertEqual(page.sw_sound.current, 0)


if __name__ == '__main__':
    unittest.main()
