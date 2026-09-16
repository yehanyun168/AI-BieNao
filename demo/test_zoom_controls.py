"""对局界面必须提供手动缩放控件（守卫：合并协作者分支时不得丢失）。

背景：协作者张博文的分支在 ui_hud.LayerHud 里移除了手动缩放控件，并附了一个
断言「对局界面不再提供手动缩放控件」的测试（assertFalse(hasattr(hud, 'btn_plus'))）。
但缩放是本地已验收的既有功能（用户此前验收过），用户「全按他的来」仅指回合
档位设计。因此本文件被改写为**反向守卫**：锁死缩放控件必须存在、且点击真的
会改变 user_scale —— 防止后续合并/重构把它删掉。
"""

import unittest

import engine
import main  # noqa: F401  # 注册项目字体后再构造 HUD
from ui_hud import LayerHud


class ZoomControlsTests(unittest.TestCase):
    def test_layer_hud_exposes_minus_and_plus(self):
        hud = LayerHud()
        zoom_row = hud.col.children[0]

        self.assertTrue(hasattr(hud, 'btn_minus'))
        self.assertTrue(hasattr(hud, 'btn_plus'))
        self.assertEqual(zoom_row.children, [hud.btn_plus, hud.btn_minus])

    def test_zoom_buttons_drive_user_scale(self):
        """+ / - 按钮点击必须真的改变 user_scale（而非只挂个壳）。"""
        engine.init_game()
        main.preferences.update(ui_scale=1.0)
        view = main.GameUI()
        view.user_scale = 1.0

        before = view.user_scale
        view.layer_hud.btn_plus._on_press(view.layer_hud.btn_plus)
        after_plus = view.user_scale
        view.layer_hud.btn_minus._on_press(view.layer_hud.btn_minus)
        after_minus = view.user_scale

        self.assertGreater(after_plus, before)          # + 增大
        self.assertLess(after_minus, after_plus)        # - 减小


if __name__ == '__main__':
    unittest.main()
