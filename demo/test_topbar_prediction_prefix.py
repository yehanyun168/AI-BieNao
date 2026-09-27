"""顶栏只显示历史趋势，不展示不可信的精确未来数值。"""

import unittest
from unittest.mock import Mock, patch

from kivy.core.window import Window
import engine
import main


class TopbarPredictionPrefixTests(unittest.TestCase):
    def test_suffix_keeps_history_arrow_without_cycle_prediction(self):
        player = engine.init_game(seed=41)
        player.seen_tutorial = True
        with patch.object(main.GameUI, '_reschedule_tick'), \
                patch.object(main.GameUI, '_reschedule_countdown'), \
                patch('cursor_fx.install', return_value=True):
            game = main.GameUI()
        try:
            game.stats.sample(engine.player_countries, engine.player)
            player.compute += 7
            game.stats.sample(engine.player_countries, player)
            preview = Mock(side_effect=AssertionError('must not predict'))
            with patch.object(engine, 'preview_next_cycle', preview):
                game._refresh_spark_deltas()

            preview.assert_not_called()
            for suffix in game._stat_suffix.values():
                self.assertRegex(suffix, '[↑↓→]')
                self.assertNotIn(main.U.MK['cyan'], suffix)
            player.game_over = True
            game._refresh_spark_deltas()
            self.assertTrue(all('—' not in suffix
                                for suffix in game._stat_suffix.values()))
        finally:
            game.stop_ticking()
            keyboard = game._keyboard
            game._keyboard_closed()
            if keyboard is not None:
                keyboard.release()
            game.commission_bar._unbind_window()
            Window.unbind(on_resize=game._on_window_resize,
                          mouse_pos=game._on_skill_hover)


if __name__ == '__main__':
    unittest.main()
