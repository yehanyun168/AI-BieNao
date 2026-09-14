"""对局缩放栏只保留手动加减按钮。"""

import unittest

import main  # noqa: F401  # 注册项目字体后再构造 HUD
from ui_hud import LayerHud


class ZoomControlsTests(unittest.TestCase):
    def test_layer_hud_has_only_minus_and_plus(self):
        hud = LayerHud()
        zoom_row = hud.col.children[0]

        self.assertFalse(hasattr(hud, 'btn_fit'))
        self.assertEqual(zoom_row.children, [hud.btn_plus, hud.btn_minus])


if __name__ == '__main__':
    unittest.main()
