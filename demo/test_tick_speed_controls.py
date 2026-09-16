"""顶部回合调速按钮必须与设置页共用统一速度入口。"""

import unittest
from unittest.mock import Mock

import balance
import engine
import main
import ui_shared as ST


class TickSpeedControlsTests(unittest.TestCase):
    def test_base_tick_is_sixteen_seconds(self):
        self.assertEqual(balance.TUNE['base_tick_seconds'], 16.0)
        self.assertEqual(ST.BASE_TICK_SECONDS, 16.0)

    def test_tick_buttons_call_set_speed_idx(self):
        engine.init_game()
        view = main.GameUI()
        view.speed_idx = 1
        view.set_speed_idx = Mock()

        view.btn_speed_down._on_press(view.btn_speed_down)
        view.btn_speed_up._on_press(view.btn_speed_up)

        self.assertEqual(view.set_speed_idx.call_args_list,
                         [unittest.mock.call(0), unittest.mock.call(2)])

    def test_topbar_has_help_button_and_speed_buttons_are_centered(self):
        engine.init_game()
        view = main.GameUI()

        # 我们保留了顶栏帮助按钮（缩放功能同批验收，不可因合并丢失）。
        self.assertTrue(hasattr(view, 'help_chip'))
        for widget in (view.btn_speed_down, view.lbl_game_date,
                       view.lbl_tick_cap, view.lbl_tick_val,
                       view.btn_speed_up):
            self.assertEqual(widget.pos_hint, {'center_y': 0.5})

    def test_settings_speed_uses_same_entry_point(self):
        engine.init_game()
        view = main.GameUI()
        view.set_speed_idx = Mock()
        page = view._build_page('settings')

        page.sw_speed._on_change(3)

        view.set_speed_idx.assert_called_once_with(3)

    def test_speed_indicator_lights_one_to_four_blocks(self):
        engine.init_game()
        view = main.GameUI()

        for idx in range(4):
            view.set_speed_idx(idx)
            self.assertEqual(view._speed_bar_states,
                             [block <= idx for block in range(4)])

    def test_speed_indicator_spans_tick_box_width(self):
        engine.init_game()
        view = main.GameUI()
        view.tick_box.pos = (120, 80)
        view.tick_box.width = 360

        view._refresh_speed_indicator()

        rects = view._speed_bar_rects
        self.assertAlmostEqual(rects[0].pos[0], view.tick_box.x)
        self.assertAlmostEqual(rects[-1].pos[0] + rects[-1].size[0],
                               view.tick_box.right, delta=0.01)
        self.assertTrue(all(abs(rect.size[0] - rects[0].size[0]) < 1e-6
                            for rect in rects))
        self.assertAlmostEqual(rects[0].pos[1],
                               view.tick_box.top + 3 * view.scale,
                               delta=0.01)


if __name__ == '__main__':
    unittest.main()
