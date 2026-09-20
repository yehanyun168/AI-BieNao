"""顶部回合调速按钮必须与设置页共用统一速度入口。"""

import unittest
from unittest.mock import Mock, patch

import balance
import engine
import main
import ui_shared as ST


class TickSpeedControlsTests(unittest.TestCase):
    def test_base_tick_is_four_seconds(self):
        self.assertEqual(balance.TUNE['base_tick_seconds'], 4.0)
        self.assertEqual(ST.BASE_TICK_SECONDS, 4.0)

    def test_countdown_refreshes_at_thirty_fps(self):
        engine.init_game()
        view = main.GameUI()
        with patch.object(ST, 'REDUCE_MOTION', False):
            self.assertAlmostEqual(view._cd_interval(), 1 / 30)
        with patch.object(ST, 'REDUCE_MOTION', True):
            self.assertAlmostEqual(view._cd_interval(), 1 / 30)

    def test_in_flight_tick_callback_cannot_advance_while_paused(self):
        """取消前已入队的 Clock 回调也必须服从暂停状态。"""
        engine.init_game(seed=1)
        view = main.GameUI()
        view.toggle_pause()
        before = engine.player.tick_count

        view.game_tick(0.0)

        self.assertEqual(engine.player.tick_count, before)

    def test_tick_buttons_call_set_speed_idx(self):
        engine.init_game()
        view = main.GameUI()
        view.speed_idx = 1
        view.set_speed_idx = Mock()

        view.btn_speed_down._on_press(view.btn_speed_down)
        view.btn_speed_up._on_press(view.btn_speed_up)

        self.assertEqual(view.set_speed_idx.call_args_list,
                         [unittest.mock.call(0), unittest.mock.call(2)])

    def test_topbar_has_no_help_button_and_speed_buttons_are_centered(self):
        engine.init_game()
        view = main.GameUI()

        self.assertFalse(hasattr(view, 'help_chip'))
        for widget in (view.btn_speed_down, view.lbl_game_date,
                       view.lbl_tick_cap, view.lbl_tick_val,
                       view.btn_speed_up):
            self.assertEqual(widget.pos_hint, {'center_y': 0.5})

    def test_pause_icon_is_leftmost_and_speed_buttons_are_rightmost(self):
        engine.init_game()
        view = main.GameUI()
        children = list(reversed(view.tick_box.children))

        self.assertEqual(children,
                         [view.pause_chip, view.lbl_game_date,
                          view.lbl_tick_cap, view.lbl_tick_val,
                          view.btn_speed_down, view.btn_speed_up])
        self.assertAlmostEqual(view.pause_chip.width, view.pause_chip.height)
        self.assertGreaterEqual(view.pause_chip.width, 40)
        self.assertEqual(view.pause_chip_icon.size, [28, 28])
        self.assertFalse(hasattr(view, 'lang_switch'))

    def test_tick_box_fills_topbar_and_is_flush_right(self):
        engine.init_game()
        view = main.GameUI()
        bar = view.tick_box.parent
        bar.pos = (0, 0)
        bar.size = (1200, view.TOP_H)
        bar.do_layout()

        visible_children = list(reversed(bar.children))
        self.assertIs(visible_children[-1], view.tick_box)
        self.assertAlmostEqual(view.tick_box.y, bar.y)
        self.assertAlmostEqual(view.tick_box.top, bar.top)
        self.assertAlmostEqual(view.tick_box.right, bar.right)

    def test_topbar_bottom_border_sits_below_tick_box(self):
        engine.init_game()
        view = main.GameUI()
        bar = view.tick_box.parent
        holder = bar.parent
        holder.pos = (0, 0)
        holder.size = (1200, (view.TOP_H + 4) * view.scale)
        holder.do_layout()
        bar.do_layout()

        self.assertAlmostEqual(bar.top, holder.top)
        self.assertAlmostEqual(bar.y - holder.y, 4 * view.scale)
        self.assertAlmostEqual(view.tick_box.y, bar.y)

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
        self.assertGreaterEqual(rects[0].pos[1], view.tick_box.y)
        self.assertLessEqual(rects[0].pos[1] + rects[0].size[1],
                             view.tick_box.top)

    def test_countup_fills_forward_without_outer_border(self):
        engine.init_game()
        view = main.GameUI()
        self.assertFalse(hasattr(view, 'cd_label'))
        self.assertFalse(hasattr(view, 'cd_bar'))
        view.speed_idx = 1
        view.speed_mult = 1.0
        view.tick_box.pos = (100, 50)
        view.tick_box.size = (300, 44)
        view._tick_deadline = 104.0

        with patch('ui_session.Clock.get_time', return_value=100.0):
            view._update_countdown(0.0)

        rect = view.tick_box._countdown_rect
        self.assertIsNone(view.tick_box._bd_line)
        self.assertEqual(rect.pos, (100, 50))
        self.assertEqual(rect.size, (0, 44))

        view._tick_deadline = 101.0
        with patch('ui_session.Clock.get_time', return_value=100.0):
            view._update_countdown(0.0)

        self.assertIs(view.tick_box._countdown_rect, rect)
        self.assertEqual(rect.size, (225, 44))


if __name__ == '__main__':
    unittest.main()
