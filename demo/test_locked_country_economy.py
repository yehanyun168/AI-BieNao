"""未解锁国家经济口径的无头回归。"""
import argparse
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KIVY_NO_FILELOG', '1')
from kivy.core.window import Window
import balance
import data
import engine
import commissions
import i18n
import main
import save_manager
import balance_sim


class MatrixOutputTests(unittest.TestCase):
    def test_matrix_writes_to_requested_directory(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            fake_module = root / 'demo' / 'balance_sim.py'
            fake_module.parent.mkdir()
            requested = root / 'requested'
            args = argparse.Namespace(seeds=1, ticks=2,
                                      matrix_output_dir=str(requested))
            sample = dict.fromkeys(balance_sim.REGRESSION_FIELDS, 0) | {
                'ending_name': 'test', 'ticks': 2, 'penetration': 0.0,
                'suspicion': 0.0, 'unlocked': 2,
                'anomalies': {'bug_count': 0, 'review_count': 0,
                              'by_type': {}},
                'delta_hist': {}, 'doomed_pressure_tick': None,
                'doomed_crisis_tick': None, 'doomed_correct': False,
            }
            with patch.object(balance_sim, '__file__', str(fake_module)), \
                    patch.object(balance_sim, 'simulate', return_value=sample):
                balance_sim.run_matrix(args)

            self.assertTrue((requested / 'playtest_baseline.json').exists())
            reports = list((requested / 'playtest_reports').glob('*.md'))
            self.assertEqual(len(reports), 1)


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
        old_v4 = copy.deepcopy(base)
        old_v4['version'] = 4
        old_v4['player'].pop('skill_queue', None)
        old_v4['player'].pop('active_skill_effects', None)
        intermediate_v5 = save_manager._v4_to_v5(old_v4)
        self.assertEqual(intermediate_v5['version'], 5)
        self.assertEqual(
            save_manager._v4_to_v5(copy.deepcopy(intermediate_v5)),
            intermediate_v5,
        )

        for version in range(1, 6):
            with self.subTest(version=version):
                old = copy.deepcopy(base)
                old['version'] = version
                old['player'].pop('seed', None)
                old['player'].pop('difficulty', None)
                old['player'].pop('origin', None)
                old['player'].pop('intro_seen', None)
                old['player'].pop('skill_queue', None)
                old['player'].pop('active_skill_effects', None)
                migrated = save_manager._migrate(old, version)
                self.assertEqual(migrated['version'], 6)
                self.assertEqual(migrated['player']['ending_id'], 'survivor')
                self.assertEqual(migrated['player']['achievements'],
                                 ['first_steps', 'survivor'])
                self.assertEqual(migrated['player']['skill_queue'], [])
                self.assertEqual(migrated['player']['active_skill_effects'], [])
                self.assertEqual(save_manager._migrate(migrated, 6), migrated)

    def test_native_v6_dirty_locked_downloads_log_code_and_leave_file_intact(self):
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

    def test_native_v6_rejects_non_numeric_unlocked_downloads(self):
        path, saved = self._saved_data()
        for value in ('not-a-number', True, float('nan'), float('inf')):
            with self.subTest(value=value):
                corrupted = copy.deepcopy(saved)
                unlocked = next(cs for cs in corrupted['countries']
                                if cs['unlocked'])
                unlocked['downloads_m'] = value
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(corrupted, f, ensure_ascii=False)
                with open(path, 'rb') as f:
                    original_bytes = f.read()
                engine.player.tick_count = 7

                self.assertEqual(save_manager.load_ex(path),
                                 (False, save_manager.LOAD_BAD_SCHEMA))
                self.assertEqual(engine.player.tick_count, 7)
                self.assertTrue(all(c.downloads_m == 0.0
                                    for c in engine.player_countries
                                    if not c.unlocked))
                with open(path, 'rb') as f:
                    self.assertEqual(f.read(), original_bytes)

    def test_native_v6_rejects_non_string_dirty_country_code(self):
        path, saved = self._saved_data()
        locked = next(cs for cs in saved['countries'] if not cs['unlocked'])
        locked['code'] = 123
        locked['downloads_m'] = 99.0
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(saved, f, ensure_ascii=False)
        with open(path, 'rb') as f:
            original_bytes = f.read()
        engine.player.tick_count = 7

        self.assertEqual(save_manager.load_ex(path),
                         (False, save_manager.LOAD_BAD_SCHEMA))
        self.assertEqual(engine.player.tick_count, 7)
        if os.path.exists(save_manager.CRASH_LOG):
            with open(save_manager.CRASH_LOG, encoding='utf-8') as f:
                self.assertNotIn('LOAD_REPAIR', f.read())
        with open(path, 'rb') as f:
            self.assertEqual(f.read(), original_bytes)


class LockedCountrySlotUiTests(unittest.TestCase):
    def test_v4_slot_summary_and_loaded_hud_use_unlocked_downloads(self):
        prior_lang = i18n.CURRENT_LANG
        i18n.set_lang('zh')
        self.addCleanup(i18n.set_lang, prior_lang)
        balance.apply_difficulty('normal')
        engine.init_game(seed=31)

        with tempfile.TemporaryDirectory() as root:
            with patch.object(save_manager, 'SAVE_DIR', root), \
                    patch.object(save_manager, 'CRASH_LOG',
                                 os.path.join(root, 'crash.log')):
                engine.player.tick_count = 3
                engine.player.commissions = [commissions.CommissionState(
                    uid=201, template_id='C2', goal='downloads', icon='[D]',
                    name_zh='拉新冲刺', name_en='Growth Sprint', window=6,
                    reward_mult=1.0, status='active', accepted_tick=1,
                    deadline_tick=2, snap_downloads=555.0,
                    target_value=25.0)]
                path = os.path.join(root, 'slot1.json')
                save_manager.save(path)
                with open(path, encoding='utf-8') as stream:
                    old = json.load(stream)
                old['version'] = 4
                locked = next(c for c in old['countries'] if not c['unlocked'])
                locked['downloads_m'] = 748.0
                unlocked_total = sum(c['downloads_m'] for c in old['countries']
                                     if c['unlocked'])
                with open(path, 'w', encoding='utf-8') as stream:
                    json.dump(old, stream, ensure_ascii=False)
                with open(path, 'rb') as stream:
                    original_bytes = stream.read()

                slot_summary = main.read_slot_rows()[0][1]
                self.assertIn(f'{unlocked_total / 7480 * 100:.2f}%',
                              slot_summary)
                self.assertNotIn(
                    f'{(unlocked_total + 748.0) / 7480 * 100:.2f}%',
                    slot_summary)

                self.assertEqual(save_manager.load_ex(path),
                                 (True, save_manager.LOAD_OK))
                with patch.object(main.GameUI, '_reschedule_tick'), \
                        patch.object(main.GameUI, '_reschedule_countdown'), \
                        patch('cursor_fx.install', return_value=True):
                    game = main.GameUI()
                try:
                    game.refresh_all()
                    settings_summary = game._slot_rows()[0][1]
                    self.assertIn(f'{unlocked_total / 7480 * 100:.2f}%',
                                  settings_summary)
                    self.assertNotIn(
                        f'{(unlocked_total + 748.0) / 7480 * 100:.2f}%',
                        settings_summary)
                    self.assertIn(
                        f"[b]{unlocked_total / 1000:.2f}{i18n.t('unit_b')}[/b]",
                        game.stats_downloads.text)
                    self.assertEqual(len(game.commission_bar.chips), 1)
                    self.assertIn('0.0/25.0M', game.commission_bar.chips[0].text)
                    self.assertIn('剩6周期', game.commission_bar.chips[0].text)
                    self.assertEqual(engine.player.tick_count, 3)
                    with open(path, 'rb') as stream:
                        self.assertEqual(stream.read(), original_bytes)
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
