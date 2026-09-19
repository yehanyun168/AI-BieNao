"""底部技能栏保持等宽，并通过字号变化完整显示名称。"""

import unittest

import main  # noqa: F401  # 注册项目字体
from ui_v4 import SkillBarCard


class SkillbarDynamicWidthTests(unittest.TestCase):
    def test_skill_cards_keep_equal_horizontal_weight(self):
        long_card = SkillBarCard('stealth', '3', 'Deep Disguise', '', 0)
        short_card = SkillBarCard('bypass', '5', 'Bypass', '', 0)

        self.assertEqual(long_card.size_hint_x, short_card.size_hint_x)

    def test_long_name_fits_narrow_card_without_clipping(self):
        card = SkillBarCard('stealth', '3', 'Deep Disguise', '', 0)
        card.size = (120, 110)
        card._layout()
        label = card.lbl_name
        saved = label.text_size
        label.text_size = (None, None)
        label.texture_update()
        natural_width = label.texture_size[0]
        label.text_size = saved

        self.assertLessEqual(natural_width, label.width)

    def test_longer_language_text_uses_smaller_font_in_same_width(self):
        card = SkillBarCard('stealth', '3', '伪装', '', 0)
        card.size = (140, 110)
        card._layout()
        short_font = card.lbl_name.font_size

        card.set_texts(name='Deep Disguise')

        self.assertEqual(card.size_hint_x, 1)
        self.assertLess(card.lbl_name.font_size, short_font)


if __name__ == '__main__':
    unittest.main()
