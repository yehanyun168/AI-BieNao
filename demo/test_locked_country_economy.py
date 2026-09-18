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
                    self.assertTrue(any(not c.unlocked for c in engine.player_countries))
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


class LockedCountryPreviewTests(unittest.TestCase):
    def setUp(self):
        balance.apply_difficulty('normal')
        engine.init_game(seed=19)

    def tearDown(self):
        balance.apply_difficulty('normal')

    def test_dirty_locked_downloads_excluded_from_both_previews(self):
        locked = next(c for c in engine.player_countries if not c.unlocked)
        locked.downloads_m = 88.0
        actual = engine.player.total_downloads_m
        from unittest.mock import patch
        with patch.object(data, 'UNLOCK_PENETRATION_THRESHOLD', 999.0):
            plain = engine.preview_next_cycle()
            skill = engine.preview_skill('push_song')
        self.assertTrue(skill['ok'], skill['reason'])
        self.assertEqual(plain['downloads_before'], actual)
        self.assertEqual(skill['downloads_before'], actual)
        self.assertEqual(skill['growth_by_country'][locked.config.code], 0.0)

    def test_preview_unlock_cap_and_seed_match_real_tick(self):
        from unittest.mock import patch
        with patch.dict(balance.TUNE, {'unlock_per_tick_cap': 1,
              'event_prob_global': 0.0, 'event_prob_country': 0.0,
              'event_prob_v2': 0.0, 'counterplay_prob': 0.0}):
            with patch.object(data, 'UNLOCK_PENETRATION_THRESHOLD', -1.0):
                before = {c.config.code for c in engine.player_countries if c.unlocked}
                plain = engine.preview_next_cycle()
                skill = engine.preview_skill('push_song')
                self.assertTrue(skill['ok'], skill['reason'])
                report = engine.tick_one_round()
                newly = [c for c in engine.player_countries if c.unlocked and c.config.code not in before]
                self.assertEqual(len(newly), 1)
                self.assertEqual(len(report['unlocked']), 1)
                self.assertEqual(newly[0].downloads_m, data.UNLOCK_SEED_DOWNLOADS_M)
                self.assertAlmostEqual(plain['downloads_after'], engine.player.total_downloads_m, places=5)
                self.assertEqual(skill['growth_by_country'][newly[0].config.code], data.UNLOCK_SEED_DOWNLOADS_M)
                self.assertEqual(sum(skill['growth_by_country'][c.config.code] > 0 for c in engine.player_countries if c.config.code not in before), 1)

if __name__ == '__main__':
    unittest.main()
