"""未解锁国家经济口径的无头回归。"""
import os
import unittest
os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KIVY_NO_FILELOG', '1')
import balance
import data
import engine
class LockedCountryTickTests(unittest.TestCase):
    def setUp(self):
        balance.apply_difficulty('normal')
        engine.init_game(seed=17)
    def tearDown(self):
        balance.apply_difficulty('normal')
    def test_locked_countries_stay_zero_for_three_ticks(self):
        from unittest.mock import patch
        with patch.dict(balance.TUNE, {'unlock_per_tick_cap': 0}):
            with patch.object(data, 'UNLOCK_PENETRATION_THRESHOLD', 999.0):
                for _ in range(3):
                    engine.tick_one_round()
                    self.assertTrue(all(c.downloads_m == 0.0 for c in engine.player_countries if not c.unlocked))
    def test_hidden_downloads_do_not_count_toward_global_total(self):
        locked = next(c for c in engine.player_countries if not c.unlocked)
        before = engine.player.total_downloads_m
        locked.downloads_m = 123.0
        self.assertEqual(engine.player.total_downloads_m, before)
        self.assertAlmostEqual(engine.player.global_penetration, before / data.POTENTIAL_USERS_M)
    def test_unlock_gets_seed_only_and_never_reduces_total(self):
        locked = next(c for c in engine.player_countries if not c.unlocked)
        locked.downloads_m = data.UNLOCK_SEED_DOWNLOADS_M + 100.0
        before = engine.player.total_downloads_m
        from unittest.mock import patch
        with patch.object(engine.onboarding, 'try_unlock', side_effect=lambda c, *_: c is locked):
            engine.tick_one_round()
        self.assertTrue(locked.unlocked)
        self.assertEqual(locked.downloads_m, data.UNLOCK_SEED_DOWNLOADS_M)
        self.assertGreaterEqual(engine.player.total_downloads_m, before)
if __name__ == '__main__':
    unittest.main()
