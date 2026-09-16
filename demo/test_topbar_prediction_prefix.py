"""顶栏的下周期预测只显示正号和数值，不显示“下”字前缀。"""

import unittest

import engine
import main


class TopbarPredictionPrefixTests(unittest.TestCase):
    def test_prediction_suffix_has_no_down_character(self):
        engine.init_game()
        game = main.GameUI()
        game.stats.sample(engine.player_countries, engine.player)
        game._refresh_spark_deltas()

        for suffix in game._stat_suffix.values():
            self.assertNotIn('下+', suffix)
            self.assertIn('+', suffix)


if __name__ == '__main__':
    unittest.main()
