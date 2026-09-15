"""对局界面不再提供手动缩放控件。"""

import unittest

import main  # noqa: F401  # 注册项目字体后再构造 HUD
from ui_hud import LayerHud


class ZoomControlsTests(unittest.TestCase):
    def test_layer_hud_has_no_manual_zoom_controls(self):
        hud = LayerHud()

        self.assertFalse(hasattr(hud, 'btn_fit'))
        self.assertFalse(hasattr(hud, 'btn_plus'))
        self.assertFalse(hasattr(hud, 'btn_minus'))
        self.assertEqual(hud.col.children, [hud.seg])


if __name__ == '__main__':
    unittest.main()
