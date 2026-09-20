"""结局弹窗不展示全结局总览，页脚按钮按实际文本宽度布局。"""

import unittest
from unittest.mock import patch

from kivy.uix.button import Button

import endings
import engine
import main
from i18n import set_lang, t


class _PopupProbe:
    def __init__(self, content):
        self.content = content

    def open(self):
        pass

    def bind(self, **_kwargs):
        pass


def _walk(widget):
    yield widget
    for child in getattr(widget, 'children', []):
        yield from _walk(child)


class EndingPopupLayoutTests(unittest.TestCase):
    def test_overview_removed_and_footer_buttons_fit_text(self):
        set_lang('zh')
        engine.init_game(seed=1)
        game = main.GameUI()
        captured = {}

        def make_probe(content, **_kwargs):
            captured['popup'] = _PopupProbe(content)
            return captured['popup']

        current = endings.ENDINGS[0]
        with patch('ui_popups.make_modal', side_effect=make_probe), \
                patch('ui_popups.sfx.play'):
            game.show_ending_popup(current)

        widgets = list(_walk(captured['popup'].content))
        rendered = '\n'.join(str(getattr(w, 'text', '')) for w in widgets)
        for other in endings.ENDINGS[1:]:
            self.assertNotIn(other.title('zh'), rendered)

        expected = {t('end_gallery'), t('end_again'), t('end_menu')}
        buttons = [w for w in widgets
                   if isinstance(w, Button) and w.text in expected]
        self.assertEqual({b.text for b in buttons}, expected)
        for button in buttons:
            button.texture_update()
            self.assertGreaterEqual(button.width, button.texture_size[0] + 28)


if __name__ == '__main__':
    unittest.main()
