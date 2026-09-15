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
            'music_on': False,
        }
        preferences.save(dict(expected, ui_scale=1.3))

        loaded = ui_preferences.load_and_apply()

        self.assertEqual(loaded, expected)
        self.assertEqual(i18n.get_lang(), 'en')
        self.assertEqual(ST.CURRENT_SPEED_IDX, 3)
        self.assertTrue(ST.REDUCE_MOTION)
        self.assertEqual(ST.GRID_MODE, 2)
        self.assertFalse(ST.A11Y_SHAPES)
        self.assertFalse(sfx.SFX_ON)
        self.assertFalse(bgm.BGM_ON)
        self.assertNotIn('ui_scale', loaded)

    def test_invalid_file_falls_back_to_defaults(self):
        with open(preferences.SETTINGS_PATH, 'w', encoding='utf-8') as f:
            f.write('{broken')

        loaded = preferences.load()

        self.assertEqual(loaded, preferences.DEFAULTS)

    def test_default_language_is_zh(self):
        """守卫：全新安装（无 settings.json）默认语言必须是简体中文。

        2026-09-15 用户指令「启动/登录界面默认语言改简体中文」的防回归锚点。
        preferences.DEFAULTS['language'] 曾一度被设为 'en' 的风险在此拦截；
        遗留的 settings.json 里 'en' 仍会被尊重（用户主动切换过的选择），
        本测试只锁「缺省回落」这一个行为。
        """
        self.assertEqual(preferences.DEFAULTS['language'], 'zh')

        loaded = preferences.load()   # setUp 已把路径指向不存在的临时文件
        self.assertEqual(loaded['language'], 'zh')

    def test_settings_page_reflects_saved_choices(self):
        values = dict(preferences.DEFAULTS, speed_idx=3, grid_mode=2,
                      reduce_motion=True, sound_on=False)
        page = SettingsPage(values=values)

        self.assertEqual(page.sw_speed.current, 3)
        self.assertEqual(page.sw_grid.current, 2)
        self.assertEqual(page.sw_motion.current, 1)
        self.assertEqual(page.sw_sound.current, 0)


if __name__ == '__main__':
    unittest.main()
