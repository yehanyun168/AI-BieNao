"""设置与存档页的按钮和快捷键文字不应被裁切或互相覆盖。"""

import unittest

import main  # 注册字体并完成 Kivy 配置
from i18n import get_lang, set_lang, t
from ui_v4 import KeyBox, PageScreen, SaveSlotRow


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


if __name__ == '__main__':
    unittest.main()
