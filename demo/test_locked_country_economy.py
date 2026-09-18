"""未解锁国家经济口径的无头回归。"""
import copy
import json
import os
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KIVY_NO_FILELOG', '1')
import balance
import data
import engine
import commissions
import save_manager
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


class LockedCountrySaveMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.save_dir_patch = patch.object(save_manager, 'SAVE_DIR', self.tmp.name)
        self.log_patch = patch.object(save_manager, 'CRASH_LOG',
                                      os.path.join(self.tmp.name, 'crash.log'))
        self.save_dir_patch.start()
        self.log_patch.start()
        self.addCleanup(self.save_dir_patch.stop)
        self.addCleanup(self.log_patch.stop)
        balance.apply_difficulty('normal')
        engine.init_game(seed=23)
        self.addCleanup(balance.apply_difficulty, 'normal')

    def _saved_data(self, name='slot.json'):
        path = os.path.join(self.tmp.name, name)
        save_manager.save(path)
        with open(path, encoding='utf-8') as f:
            return path, json.load(f)

    def test_v4_load_repairs_locked_downloads_and_active_download_commission(self):
        locked = next(c for c in engine.player_countries if not c.unlocked)
        locked.downloads_m = 55.0
        engine.player.tick_count = 3
        active = commissions.CommissionState(
            uid=101, template_id='C2', goal='downloads', icon='[D]',
            name_zh='拉新冲刺', name_en='Growth Sprint', window=6,
            reward_mult=1.0, status='active', accepted_tick=1,
            deadline_tick=2, snap_downloads=555.0, reward=42.0)
        offered = commissions.CommissionState(
            uid=102, template_id='C2', goal='downloads', icon='[D]',
            name_zh='拉新冲刺', name_en='Growth Sprint', window=6,
            reward_mult=1.0, deadline_tick=None, snap_downloads=777.0)
        compute = commissions.CommissionState(
            uid=103, template_id='C3', goal='compute', icon='[C]',
            name_zh='算力冲刺', name_en='Compute Sprint', window=8,
            reward_mult=1.0, status='active', accepted_tick=2,
            deadline_tick=20, snap_compute=19.0)
        engine.player.commissions = [active, offered, compute]
        expected_total = engine.player.total_downloads_m
        path, saved = self._saved_data()
        saved['version'] = 4
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(saved, f, ensure_ascii=False)
        with open(path, 'rb') as f:
            original_bytes = f.read()

        self.assertEqual(save_manager.load_ex(path), (True, save_manager.LOAD_OK))
        self.assertEqual(next(c.downloads_m for c in engine.player_countries
                              if c.config.code == locked.config.code), 0.0)
        self.assertEqual(engine.player.total_downloads_m, expected_total)
        by_uid = {c.uid: c for c in engine.player.commissions}
        self.assertEqual(set(by_uid), {101, 102, 103})
        self.assertEqual((by_uid[101].snap_downloads, by_uid[101].accepted_tick,
                          by_uid[101].deadline_tick, by_uid[101].reward),
                         (expected_total, 3, 9, 42.0))
        self.assertEqual((by_uid[102].deadline_tick, by_uid[102].snap_downloads),
                         (None, 777.0))
        self.assertEqual((by_uid[103].deadline_tick, by_uid[103].snap_compute),
                         (20, 19.0))
        with open(path, 'rb') as f:
            self.assertEqual(f.read(), original_bytes)
        self.assertFalse(os.path.exists(save_manager.CRASH_LOG))

    def test_migration_chain_is_idempotent_and_preserves_finished_game(self):
        _, base = self._saved_data()
        base['player']['game_over'] = True
        base['player']['ending_id'] = 'survivor'
        base['player']['achievements'] = ['first_steps', 'survivor']
        for version in range(1, 5):
            with self.subTest(version=version):
                old = copy.deepcopy(base)
                old['version'] = version
                old['player'].pop('seed', None)
                old['player'].pop('difficulty', None)
                old['player'].pop('origin', None)
                old['player'].pop('intro_seen', None)
                migrated = save_manager._migrate(old, version)
                self.assertEqual(migrated['version'], 5)
                self.assertEqual(migrated['player']['ending_id'], 'survivor')
                self.assertEqual(migrated['player']['achievements'],
                                 ['first_steps', 'survivor'])
                self.assertEqual(save_manager._v4_to_v5(copy.deepcopy(migrated)),
                                 migrated)
                self.assertEqual(save_manager._migrate(migrated, 5), migrated)

    def test_native_v5_dirty_locked_downloads_log_code_and_leave_file_intact(self):
        locked = next(c for c in engine.player_countries if not c.unlocked)
        locked.downloads_m = 99.0
        path, _ = self._saved_data()
        with open(path, 'rb') as f:
            original_bytes = f.read()

        self.assertEqual(save_manager.load_ex(path), (True, save_manager.LOAD_OK))
        self.assertEqual(next(c.downloads_m for c in engine.player_countries
                              if c.config.code == locked.config.code), 0.0)
        with open(save_manager.CRASH_LOG, encoding='utf-8') as f:
            self.assertIn(locked.config.code, f.read())
        with open(path, 'rb') as f:
            self.assertEqual(f.read(), original_bytes)

if __name__ == '__main__':
    unittest.main()
