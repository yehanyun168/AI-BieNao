"""游戏年月从设备年月开始，随周期推进并写入存档。"""

import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

import engine
import main
import save_manager


class GameCalendarTests(unittest.TestCase):
    def test_new_game_uses_device_month_and_crosses_year(self):
        with patch('engine.datetime') as clock:
            clock.now.return_value = datetime(2026, 11, 20)
            player = engine.init_game()

        self.assertEqual((player.start_year, player.start_month), (2026, 11))
        self.assertEqual(engine.game_year_month(), (2026, 11))
        player.tick_count = 2
        self.assertEqual(engine.game_year_month(), (2027, 1))

    def test_calendar_start_is_saved_and_restored(self):
        player = engine.init_game()
        player.start_year, player.start_month, player.tick_count = 2031, 7, 8
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'calendar.json')
            save_manager.save(path)
            with open(path, encoding='utf-8') as stream:
                saved = json.load(stream)
            self.assertEqual(saved['player']['start_year'], 2031)
            self.assertEqual(saved['player']['start_month'], 7)

            engine.init_game()
            self.assertTrue(save_manager.load(path))

        self.assertEqual((engine.player.start_year, engine.player.start_month),
                         (2031, 7))
        self.assertEqual(engine.game_year_month(), (2032, 3))

    def test_tick_box_shows_calendar_left_of_tick(self):
        player = engine.init_game()
        player.start_year, player.start_month, player.tick_count = 2026, 12, 1
        game = main.GameUI()
        game.refresh_all()

        self.assertEqual(game.lbl_game_date.text, '2027-01')
        children = list(reversed(game.tick_box.children))
        self.assertLess(children.index(game.lbl_game_date),
                        children.index(game.lbl_tick_cap))


if __name__ == '__main__':
    unittest.main()
