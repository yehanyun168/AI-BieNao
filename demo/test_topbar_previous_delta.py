"""顶栏先显示上一周期实际增量，再显示近期趋势。"""

import unittest

import engine
import i18n
import main


class TopbarPreviousDeltaTests(unittest.TestCase):
    def test_suffix_uses_last_two_actual_samples(self):
        engine.init_game()
        game = main.GameUI()
        game.stats.global_compute.extend((100.0, 125.0))
        game.stats.global_downloads.extend((1000.0, 1120.0))
        game.stats.global_suspicion.extend((20.0, 18.5))
        game._refresh_spark_deltas()

        self.assertIn('[color=4ec9b0]+25[/color]',
                      game._stat_suffix['stats_compute'])
        self.assertIn(f"[color=4ec9b0]+0.12{i18n.t('unit_b')}[/color]",
                      game._stat_suffix['stats_downloads'])
        self.assertIn('[color=4ec9b0]-1.5%[/color]',
                      game._stat_suffix['stats_suspicion'])
        for suffix in game._stat_suffix.values():
            self.assertLess(suffix.index('[color=4ec9b0]'),
                            suffix.index('↑'))

    def test_actual_delta_is_zero_before_two_samples_exist(self):
        engine.init_game()
        game = main.GameUI()
        game.stats.sample(engine.player_countries, engine.player)
        game._refresh_spark_deltas()

        self.assertIn('[color=4ec9b0]+0[/color]',
                      game._stat_suffix['stats_compute'])
        self.assertIn(f"[color=4ec9b0]+0.00{i18n.t('unit_b')}[/color]",
                      game._stat_suffix['stats_downloads'])
        self.assertIn('[color=4ec9b0]+0.0%[/color]',
                      game._stat_suffix['stats_suspicion'])


if __name__ == '__main__':
    unittest.main()
