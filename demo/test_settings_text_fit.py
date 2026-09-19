"""设置与存档页的按钮和快捷键文字不应被裁切或互相覆盖。"""

import unittest

import main  # 注册字体并完成 Kivy 配置
from i18n import get_lang, set_lang, t
from ui_v4 import KeyBox, PageScreen, SaveSlotRow
from ui_v4_syspages import SettingsPage


class SettingsTextFitTests(unittest.TestCase):
    def setUp(self):
        self.old_lang = get_lang()

    def tearDown(self):
        set_lang(self.old_lang)

    def test_back_button_fits_full_text(self):
        set_lang('zh')
        page = PageScreen()
        page.set_back_button(t('k_esc'), lambda: None)
        page.btn_back.texture_update()

        self.assertGreaterEqual(page.btn_back.width,
                                page.btn_back.texture_size[0] + 28)

    def test_save_action_labels_are_short(self):
        set_lang('zh')
        self.assertEqual(t('slot_overwrite'), '覆盖')
        self.assertEqual(t('slot_new_game'), '开始')
        set_lang('en')
        self.assertEqual(t('slot_overwrite'), 'Overwrite')
        self.assertEqual(t('slot_new_game'), 'Start')

    def test_slot_buttons_fit_their_text(self):
        row = SaveSlotRow(actions=[('Overwrite', 'danger', None),
                                   ('Start', 'primary', None)])
        for button in row._btns:
            button.texture_update()
            self.assertGreaterEqual(button.width,
                                    button.texture_size[0] + 20)

    def test_key_rows_are_tall_enough_for_text(self):
        box = KeyBox('快捷键速查', [('Space', '暂停 / 继续')])
        row = box.children[0]
        self.assertGreaterEqual(row.height, row._lbl.texture_size[1])
        self.assertGreaterEqual(row._kbd.height, row._kbd.texture_size[1])

    def test_key_description_stays_to_the_right_of_keycap(self):
        box = KeyBox('快捷键速查', [('Space', '暂停 / 继续')])
        row = box.children[0]
        row.pos = (20, 30)
        row.size = (360, 30)
        row._layout()
        row.do_layout()

        self.assertGreaterEqual(row._lbl.x, row._kbd.right + 7)

    def test_settings_key_descriptions_are_translated(self):
        set_lang('zh')
        page = SettingsPage()
        box = next(w for w in page.walk() if isinstance(w, KeyBox))
        descriptions = [w._lbl.text for w in box.children
                        if hasattr(w, '_lbl')]

        self.assertIn(t('k_pause'), descriptions)
        self.assertNotIn('k_pause', descriptions)

    def test_settings_has_no_replay_tutorial_button(self):
        page = SettingsPage(on_tutorial=lambda: None)
        texts = [getattr(w, 'text', '') for w in page.walk()]

        self.assertNotIn('重看教程', texts)


if __name__ == '__main__':
    unittest.main()
