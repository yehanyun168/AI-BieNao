import copy
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import Mock, patch

from kivy.core.window import Window

import engine
import balance
import balance_sim
import commissions
import save_manager
import skill_state
import i18n
import main
from balance import TUNE, apply_difficulty
from data import SKILLS
from skill_state import (
    ActiveSkill,
    SkillCast,
    validate_skill_table,
)
from test_skill_save_review import FinalReviewSkillSaveMixin


class SkillTimingTests(unittest.TestCase):
    def test_import_rejects_invalid_product_skill_table(self):
        script = """
from dataclasses import replace

import data

data.SKILLS["stealth"] = replace(
    data.SKILLS["stealth"], duration=3, cooldown=2
)
import skill_state
"""

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "ValueError: invalid skill duration/cooldown: stealth",
            result.stderr,
        )

    def test_product_skill_table_is_valid(self):
        validate_skill_table()

    def test_duration_may_equal_cooldown(self):
        skills = dict(SKILLS)
        skills["stealth"] = replace(
            skills["stealth"], duration=2, cooldown=2
        )

        validate_skill_table(skills)

    def test_invalid_duration_and_cooldown_are_rejected(self):
        invalid_timings = (
            (3, 2),
            (0, 2),
            (True, 2),
            (1.5, 2),
            (1, False),
        )

        for duration, cooldown in invalid_timings:
            with self.subTest(duration=duration, cooldown=cooldown):
                skills = dict(SKILLS)
                skills["stealth"] = replace(
                    skills["stealth"],
                    duration=duration,
                    cooldown=cooldown,
                )

                with self.assertRaisesRegex(
                    ValueError,
                    r"^invalid skill duration/cooldown: stealth$",
                ):
                    validate_skill_table(skills)


class SkillStateTests(unittest.TestCase):
    def test_skill_cast_defaults_to_empty_tuple_and_is_frozen(self):
        cast = SkillCast("stealth")

        self.assertEqual(cast.targets, ())
        with self.assertRaises(FrozenInstanceError):
            cast.skill_id = "push_song"

    def test_active_skill_tracks_mutable_remaining_ticks(self):
        active = ActiveSkill("stealth", ("CN",), remaining_ticks=2)

        active.remaining_ticks -= 1

        self.assertEqual(active.remaining_ticks, 1)
        self.assertIsInstance(active.targets, tuple)


class SkillQueueCastTests(unittest.TestCase):
    def setUp(self):
        apply_difficulty('normal')
        self.player = engine.init_game(seed=41)
        self.player.unlocked_skills.update({'algo_top', 'stealth'})

    def tearDown(self):
        apply_difficulty('normal')

    def _cast_state(self):
        return (
            self.player.compute,
            tuple(
                (skill_id, type(value), repr(value))
                for skill_id, value in self.player.skill_cooldowns.items()
            ),
            dict(self.player.skill_uses),
            list(self.player.skill_queue),
            self.player.selected_country,
            tuple(
                (active.skill_id, active.targets, active.remaining_ticks)
                for active in self.player.active_skill_effects
            ),
            tuple(
                (
                    country.config.code,
                    country.unlocked,
                    country.downloads_m,
                    country.current_block_intensity,
                    country.block_budget_remaining,
                )
                for country in engine.player_countries
            ),
        )

    def _assert_atomic_failure(self, skill_id, targets=None, reason=None):
        before = self._cast_state()
        if reason is not None:
            self.assertEqual(
                engine.skill_cast_reason(skill_id, targets),
                reason,
            )
            self.assertEqual(self._cast_state(), before)
        self.assertFalse(engine.use_skill(skill_id, targets))
        self.assertEqual(self._cast_state(), before)

    def test_successive_casts_append_in_order_and_charge_once_each(self):
        compute_before = self.player.compute

        self.assertTrue(engine.use_skill('algo_top'))
        self.assertTrue(engine.use_skill('stealth'))

        self.assertEqual(
            [cast.skill_id for cast in self.player.skill_queue],
            ['algo_top', 'stealth'],
        )
        self.assertEqual(self.player.compute, compute_before - 50)
        self.assertEqual(self.player.skill_uses['algo_top'], 1)
        self.assertEqual(self.player.skill_uses['stealth'], 1)

    def test_mixed_valid_and_unknown_targets_fail_atomically(self):
        self._assert_atomic_failure(
            'algo_top', ['CN', 'UNKNOWN'], 'invalid_target'
        )

    def test_second_reservation_of_same_skill_has_no_side_effects(self):
        self.assertTrue(engine.use_skill('stealth', 'CN'))
        before = self._cast_state()

        self.assertEqual(engine.skill_cast_reason('stealth', 'CN'), 'cooldown')
        self.assertEqual(self._cast_state(), before)
        self.assertFalse(engine.use_skill('stealth', 'CN'))
        self.assertEqual(self._cast_state(), before)

    def test_invalid_cooldown_states_fail_atomically(self):
        for cooldown in (-1, float('nan'), '0', True):
            with self.subTest(cooldown=cooldown):
                self.player.skill_cooldowns['algo_top'] = cooldown
                self._assert_atomic_failure(
                    'algo_top', reason='cooldown'
                )

    def test_huge_integer_cooldown_fails_atomically(self):
        self.player.skill_cooldowns['algo_top'] = 10 ** 1000

        self._assert_atomic_failure('algo_top', reason='cooldown')

    def test_use_skill_reads_stateful_target_container_only_once(self):
        class ChangingTargets(list):
            def __init__(self):
                super().__init__()
                self.iterations = 0

            def __iter__(self):
                self.iterations += 1
                if self.iterations == 1:
                    return iter(['CN'])
                return iter(['UNKNOWN'])

        targets = ChangingTargets()

        self.assertTrue(engine.use_skill('algo_top', targets))
        self.assertEqual(targets.iterations, 1)
        self.assertEqual(self.player.skill_queue[-1].targets, ('CN',))

    def test_explicit_skill_tick_is_rejected_before_any_state_change(self):
        player_before = copy.deepcopy(engine.player)
        countries_before = copy.deepcopy(engine.player_countries)
        rng_before = random.getstate()

        with self.assertRaisesRegex(
            ValueError,
            r'^explicit skill tick path is retired$',
        ):
            engine.tick_one_round('stealth')

        self.assertEqual(engine.player, player_before)
        self.assertEqual(engine.player_countries, countries_before)
        self.assertEqual(random.getstate(), rng_before)

    def test_all_rejection_reasons_leave_cast_state_unchanged(self):
        self.player.game_over = True
        self._assert_atomic_failure('algo_top', reason='game_over')
        self.player.game_over = False

        self._assert_atomic_failure('missing_skill', reason='locked')
        self._assert_atomic_failure('hit_maker', reason='locked')

        self.player.skill_cooldowns['algo_top'] = 1
        self._assert_atomic_failure('algo_top', reason='cooldown')
        self.player.skill_cooldowns['algo_top'] = 0

        self.player.active_skill_effects.append(
            ActiveSkill('algo_top', (), remaining_ticks=1)
        )
        self._assert_atomic_failure('algo_top', reason='cooldown')
        self.player.active_skill_effects.clear()

        for targets in ({'CN'}, {'CN': True}, True, ['']):
            with self.subTest(targets=targets):
                self._assert_atomic_failure(
                    'algo_top', targets, 'invalid_target'
                )

        self._assert_atomic_failure(
            'algo_top', ['CN', 'UNKNOWN'], 'invalid_target'
        )

        locked = next(c for c in engine.player_countries if not c.unlocked)
        self._assert_atomic_failure('algo_top', locked.config.code, 'locked')

        cn = next(c for c in engine.player_countries if c.config.code == 'CN')
        old_downloads = cn.downloads_m
        cn.downloads_m = cn.config.population_m * TUNE['penetration_saturated']
        self._assert_atomic_failure('algo_top', 'CN', 'saturated')
        cn.downloads_m = old_downloads

        self.player.compute = 49
        self._assert_atomic_failure('algo_top', reason='no_compute')

    def test_blocked_target_remains_castable_and_targets_are_deduplicated(self):
        cn = next(c for c in engine.player_countries if c.config.code == 'CN')
        cn.current_block_intensity = 0.8

        self.assertEqual(
            engine.skill_cast_reason('algo_top', ['CN', 'CN']),
            'ok',
        )
        self.assertTrue(engine.use_skill('algo_top', ['CN', 'CN']))
        self.assertEqual(self.player.skill_queue[-1].targets, ('CN',))
        self.assertEqual(self.player.compute, 50)

    def test_normalize_targets_accepts_supported_forms_and_rejects_others(self):
        self.assertEqual(skill_state.normalize_targets(None), ())
        self.assertEqual(skill_state.normalize_targets(''), ())
        self.assertEqual(skill_state.normalize_targets('CN'), ('CN',))
        self.assertEqual(
            skill_state.normalize_targets(['CN', 'US', 'CN']),
            ('CN', 'US'),
        )
        self.assertEqual(skill_state.normalize_targets(('CN',)), ('CN',))

        for value in (True, {'CN'}, {'CN': True}, [''], [1]):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    skill_state.normalize_targets(value)


class SkillCycleTests(unittest.TestCase):
    def setUp(self):
        apply_difficulty('normal')
        self.player = engine.init_game(seed=73)
        self.player.unlocked_skills.update(SKILLS)
        self.patchers = [
            patch.object(engine.onboarding, 'try_unlock', return_value=False),
            patch.object(engine, '_pick_boundary_event', return_value=(None, None)),
            patch.object(engine, '_tick_counterplay', return_value=None),
            patch.object(engine, '_tick_commissions', return_value=(None, None, None)),
            patch.object(engine, 'check_achievements', return_value=[]),
            patch.object(engine, 'check_ending', return_value=None),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        apply_difficulty('normal')

    def _reset(self):
        self.player = engine.init_game(seed=73)
        self.player.unlocked_skills.update(SKILLS)
        return self.player

    def _country(self, code):
        return next(
            country for country in engine.player_countries
            if country.config.code == code
        )

    def _zero_downloads(self):
        for country in engine.player_countries:
            country.downloads_m = 0.0

    def _tick_state(self):
        return (
            copy.deepcopy(engine.player),
            copy.deepcopy(engine.player_countries),
            random.getstate(),
        )

    def test_drains_fifo_queue_and_keeps_only_persistent_effect(self):
        self.assertTrue(engine.use_skill('algo_top'))
        self.assertTrue(engine.use_skill('stealth'))

        report = engine.tick_one_round()

        self.assertEqual(report['skills_activated'], ['algo_top', 'stealth'])
        self.assertEqual(self.player.skill_queue, [])
        self.assertEqual(
            [(a.skill_id, a.remaining_ticks)
             for a in self.player.active_skill_effects],
            [('stealth', 1)],
        )

    def test_stealth_settles_twice_and_cooldown_stays_positive_while_active(self):
        self.assertTrue(engine.use_skill('stealth'))

        engine.tick_one_round()
        self.assertEqual(self.player.active_skill_effects[0].remaining_ticks, 1)
        self.assertGreater(self.player.skill_cooldowns['stealth'], 0)

        engine.tick_one_round()
        self.assertEqual(self.player.active_skill_effects, [])
        self.assertGreater(self.player.skill_cooldowns['stealth'], 0)

    def test_equal_duration_and_cooldown_expire_together(self):
        original = SKILLS['stealth']
        SKILLS['stealth'] = replace(original, duration=2, cooldown=2)
        self.addCleanup(SKILLS.__setitem__, 'stealth', original)
        self.assertTrue(engine.use_skill('stealth'))

        engine.tick_one_round()
        self.assertEqual(self.player.active_skill_effects[0].remaining_ticks, 1)
        self.assertEqual(self.player.skill_cooldowns['stealth'], 1)

        engine.tick_one_round()
        self.assertEqual(self.player.active_skill_effects, [])
        self.assertNotIn('stealth', self.player.skill_cooldowns)

    def test_global_instant_deltas_apply_once(self):
        self._zero_downloads()
        self.assertTrue(engine.use_skill('open_bait'))

        with patch.dict(TUNE, {'growth_base': 0.0}):
            first = engine.tick_one_round()
            second = engine.tick_one_round()

        self.assertEqual(first['suspicion_breakdown']['skill'], 8.0)
        self.assertEqual(first['suspicion_gain'], 8.0)
        self.assertEqual(first['compute_gain'], 150.0)
        self.assertNotIn('skill', second['suspicion_breakdown'])
        self.assertEqual(second['suspicion_gain'], 0.0)
        self.assertEqual(second['compute_gain'], 0.0)

    def test_targeted_instant_deltas_scale_by_distinct_target_count(self):
        gains = []
        for targets in (['CN', 'CN'], ['CN', 'US', 'CN']):
            self._reset()
            self._zero_downloads()
            self.assertTrue(engine.use_skill('open_bait', targets))

            with patch.dict(TUNE, {'growth_base': 0.0}):
                report = engine.tick_one_round()
            gains.append((report['compute_gain'], report['suspicion_gain']))

        self.assertEqual(gains, [(150.0, 8.0), (300.0, 16.0)])

    def test_download_multipliers_compose_for_same_country(self):
        for country in engine.player_countries:
            country.unlocked = country.config.code == 'CN'
        before = self._country('CN').downloads_m
        baseline = engine.tick_one_round()['download_growth']
        self._reset()
        for country in engine.player_countries:
            country.unlocked = country.config.code == 'CN'
        self.assertTrue(engine.use_skill('push_song'))
        self.assertTrue(engine.use_skill('algo_top'))

        combined = engine.tick_one_round()['download_growth']

        self.assertGreater(before, 0)
        self.assertAlmostEqual(combined, baseline * 1.10 * 1.30)

    def test_targeted_download_multiplier_only_affects_target_country(self):
        cn = self._country('CN')
        us = self._country('US')
        cn.downloads_m = us.downloads_m = 1.0
        before = {'CN': cn.downloads_m, 'US': us.downloads_m}
        with patch.dict(TUNE, {'growth_network': 0.0}):
            engine.tick_one_round()
        baseline = {
            code: self._country(code).downloads_m - before[code]
            for code in ('CN', 'US')
        }

        self._reset()
        cn = self._country('CN')
        us = self._country('US')
        cn.downloads_m = us.downloads_m = 1.0
        before = {'CN': cn.downloads_m, 'US': us.downloads_m}
        self.assertTrue(engine.use_skill('algo_top', 'CN'))
        with patch.dict(TUNE, {'growth_network': 0.0}):
            engine.tick_one_round()
        skilled = {
            code: self._country(code).downloads_m - before[code]
            for code in ('CN', 'US')
        }

        self.assertAlmostEqual(skilled['CN'], baseline['CN'] * 1.30)
        self.assertAlmostEqual(skilled['US'], baseline['US'])

    def test_anon_cdn_settles_three_times_then_expires(self):
        self.assertTrue(engine.use_skill('anon_cdn'))
        skilled_gains = []
        remaining = []
        for _ in range(3):
            skilled_gains.append(engine.tick_one_round()['suspicion_gain'])
            remaining.append(
                self.player.active_skill_effects[0].remaining_ticks
                if self.player.active_skill_effects else 0
            )

        self._reset()
        baseline_gains = [
            engine.tick_one_round()['suspicion_gain'] for _ in range(3)
        ]

        self.assertEqual(remaining, [2, 1, 0])
        for skilled, baseline in zip(skilled_gains, baseline_gains):
            self.assertAlmostEqual(skilled, baseline * 0.55)

    def test_stealth_ratio_caps_only_after_bonus_and_multiplier(self):
        original = SKILLS['stealth']
        bonus = engine.data.MAX_STEALTH_RATIO
        SKILLS['stealth'] = replace(
            original,
            stealth_ratio_bonus=bonus,
            stealth_ratio_mult=0.5,
        )
        self.addCleanup(SKILLS.__setitem__, 'stealth', original)
        for country in engine.player_countries:
            country.unlocked = country.config.code == 'CN'
            country.downloads_m = 1.0 if country.unlocked else 0.0
        self.assertTrue(engine.use_skill('stealth'))

        expected_ratio = min(
            (engine.data.BASE_STEALTH_RATIO + bonus) * 0.5,
            engine.data.MAX_STEALTH_RATIO,
        )
        expected_compute = (
            TUNE['active_user_ratio']
            * TUNE['compute_per_user']
            * expected_ratio
            * TUNE['compute_scale']
        )
        with patch.dict(TUNE, {'growth_base': 0.0}):
            report = engine.tick_one_round()

        self.assertAlmostEqual(report['compute_gain'], expected_compute)

    def test_malformed_live_state_is_rejected_atomically(self):
        class ListSubclass(list):
            pass

        class DictSubclass(dict):
            pass

        corruptions = {
            'queue_not_plain_list': lambda p: setattr(
                p, 'skill_queue', ListSubclass()
            ),
            'active_not_plain_list': lambda p: setattr(
                p, 'active_skill_effects', ListSubclass()
            ),
            'cooldowns_not_plain_dict': lambda p: setattr(
                p, 'skill_cooldowns', DictSubclass()
            ),
            'duplicate_queue_id': lambda p: p.skill_queue.extend([
                SkillCast('push_song'), SkillCast('push_song')
            ]),
            'cross_list_duplicate_id': lambda p: (
                p.skill_queue.append(SkillCast('stealth')),
                p.active_skill_effects.append(ActiveSkill('stealth', (), 1)),
                p.skill_cooldowns.__setitem__('stealth', 2),
            ),
            'remaining_equals_duration': lambda p: (
                p.active_skill_effects.append(ActiveSkill('stealth', (), 2)),
                p.skill_cooldowns.__setitem__('stealth', 2),
            ),
            'remaining_exceeds_cooldown': lambda p: (
                p.active_skill_effects.append(ActiveSkill('anon_cdn', (), 2)),
                p.skill_cooldowns.__setitem__('anon_cdn', 1),
            ),
            'unknown_id': lambda p: p.skill_queue.append(SkillCast('missing')),
            'invalid_cooldown': lambda p: p.skill_cooldowns.__setitem__(
                'stealth', float('inf')
            ),
            'queued_cooldown_shorter_than_duration': lambda p: (
                p.skill_queue.append(SkillCast('anon_cdn')),
                p.skill_cooldowns.__setitem__('anon_cdn', 1),
            ),
            'duplicate_targets': lambda p: (
                p.skill_queue.append(SkillCast('open_bait', ('CN', 'CN'))),
                p.skill_cooldowns.__setitem__('open_bait', 9),
            ),
            'non_tuple_targets': lambda p: (
                p.skill_queue.append(SkillCast('open_bait', None)),
                p.skill_cooldowns.__setitem__('open_bait', 9),
            ),
            'unknown_target': lambda p: (
                p.skill_queue.append(SkillCast('open_bait', ('UNKNOWN',))),
                p.skill_cooldowns.__setitem__('open_bait', 9),
            ),
        }
        for name, corrupt in corruptions.items():
            with self.subTest(name=name):
                self._reset()
                corrupt(self.player)
                before = self._tick_state()

                with self.assertLogs('skill_state', level='ERROR'):
                    with self.assertRaisesRegex(
                        ValueError, r'^invalid live skill state$'
                    ):
                        engine.tick_one_round()

                self.assertEqual(self._tick_state(), before)

    def test_stateful_cast_is_rejected_before_queue_is_cleared(self):
        class StatefulCast:
            def __init__(self):
                self.skill_id_reads = 0

            @property
            def skill_id(self):
                self.skill_id_reads += 1
                return ('open_bait' if self.skill_id_reads <= 3
                        else 'missing')

            @property
            def targets(self):
                return ()

            def __eq__(self, other):
                return (
                    type(other) is type(self)
                    and other.skill_id_reads == self.skill_id_reads
                )

        cast = StatefulCast()
        self.player.skill_queue.append(cast)
        self.player.skill_cooldowns['open_bait'] = 9
        before = self._tick_state()
        error = None

        with self.assertLogs('skill_state', level='ERROR'):
            try:
                engine.tick_one_round()
            except Exception as exc:
                error = exc
            self.assertEqual(self.player.skill_queue, before[0].skill_queue)

        self.assertIs(type(error), ValueError)
        self.assertEqual(str(error), 'invalid live skill state')
        self.assertEqual(self._tick_state(), before)

    def test_report_always_contains_skills_activated(self):
        report = engine.tick_one_round()
        self.assertEqual(report['skills_activated'], [])

        self.player.game_over = True
        report = engine.tick_one_round()
        self.assertEqual(report['skills_activated'], [])


class ComboSimulationTests(unittest.TestCase):
    def setUp(self):
        balance.apply_difficulty('normal')
        engine.init_game(seed=61)
        self.addCleanup(balance.apply_difficulty, 'normal')

    def test_combo_strategy_queues_push_song_then_algo_top(self):
        player = engine.player
        player.compute = 1000
        player.unlocked_skills.update({'push_song', 'algo_top'})

        with patch.object(engine, 'unlock_t0'), patch.object(
            engine, 'upgrade_branch'
        ):
            balance_sim.auto_play(strategy='combo')

        self.assertEqual(
            [cast.skill_id for cast in player.skill_queue],
            ['push_song', 'algo_top'],
        )

    def test_simulate_counts_pair_from_real_settlement_not_strategy_label(self):
        queued = False

        def queue_pair_once(strategy='default', **_kwargs):
            nonlocal queued
            if queued:
                return
            queued = True
            player = engine.player
            player.compute = 1000
            player.unlocked_skills.update({'push_song', 'algo_top'})
            self.assertTrue(engine.use_skill('push_song'))
            self.assertTrue(engine.use_skill('algo_top'))

        with patch.object(balance_sim, 'auto_play', side_effect=queue_pair_once):
            result = balance_sim.simulate(
                seed=61, max_ticks=3, strategy='default', inspect=False
            )

        self.assertEqual(result['combo_pair_activations'], 1)


class SkillSaveTests(FinalReviewSkillSaveMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.save_dir = patch.object(save_manager, 'SAVE_DIR', self.tmp.name)
        self.crash_log = patch.object(
            save_manager, 'CRASH_LOG', os.path.join(self.tmp.name, 'crash.log')
        )
        self.save_dir.start()
        self.crash_log.start()
        self.addCleanup(self.save_dir.stop)
        self.addCleanup(self.crash_log.stop)
        balance.apply_difficulty('normal')
        engine.init_game(seed=71)
        self.addCleanup(balance.apply_difficulty, 'normal')

    def _path(self, name='slot.json'):
        return os.path.join(self.tmp.name, name)

    def _valid_v6(self):
        path = self._path()
        save_manager.save(path)
        with open(path, encoding='utf-8') as stream:
            return path, json.load(stream)

    def _write(self, path, data):
        with open(path, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, allow_nan=True)
        with open(path, 'rb') as stream:
            return stream.read()

    def _handwritten_v5(self):
        countries = []
        for cfg in engine.COUNTRIES:
            countries.append({
                'code': cfg.code,
                'unlocked': cfg.code in {'CN', 'US'},
                'downloads_m': 1.0 if cfg.code in {'CN', 'US'} else 0.0,
                'current_block_intensity': 0.0,
                'block_budget_remaining': cfg.block_budget,
            })
        return {
            'version': 5,
            'saved_at': '2026-01-01T00:00:00',
            'player': {
                'compute': 123.0, 'compute_peak': 123.0,
                'suspicion': 4.0, 'suspicion_peak': 4.0,
                'tick_count': 2, 'start_year': 2026, 'start_month': 1,
                'events_history': [], 'skill_cooldowns': {},
                'selected_country': 'CN', 'crisis_triggered': False,
                'game_over': False, 'ending_id': None,
                'v2_cooldowns': {}, 'v2_seen': [], 'achievements': [],
                'seen_tutorial': False, 'intro_seen': False,
                'unlocked_skills': ['push_song', 'stealth'],
                'commissions': [], 'commissions_done': 0,
                'commissions_failed': 0, 'last_commission_tick': 0,
                'compute_earned_total': 0.0, 'skill_uses': {},
                'seed': None, 'difficulty': 'normal', 'origin': 'garage',
            },
            'tech': {
                't0_unlocked': {}, 'branch_levels': {}, 'chosen_branch': {},
            },
            'countries': countries,
        }

    def _assert_load_bad_unchanged(self, data):
        path = self._path()
        original_bytes = self._write(path, data)
        player_ref = engine.player
        countries_ref = engine.player_countries
        player_before = copy.deepcopy(player_ref)
        countries_before = copy.deepcopy(countries_ref)
        engine._counterplay_cooldown.clear()
        engine._counterplay_cooldown['sentinel'] = 17
        engine._counterplay_pending.clear()
        engine._counterplay_pending['sentinel'] = 19
        engine._recent_commission_templates[:] = ['sentinel']
        cooldown_ref = engine._counterplay_cooldown
        pending_ref = engine._counterplay_pending
        recent_ref = engine._recent_commission_templates
        tune_ref = balance.TUNE
        tune_before = copy.deepcopy(balance.TUNE)
        difficulty_before = balance.ACTIVE_DIFFICULTY
        origin_before = balance.ACTIVE_ORIGIN
        next_uid_before = commissions._next_uid
        rng_before = random.getstate()

        self.assertEqual(
            save_manager.load_ex(path),
            (False, save_manager.LOAD_BAD_SCHEMA),
        )
        self.assertIs(engine.player, player_ref)
        self.assertEqual(engine.player, player_before)
        self.assertIs(engine.player_countries, countries_ref)
        self.assertEqual(engine.player_countries, countries_before)
        self.assertIs(engine._counterplay_cooldown, cooldown_ref)
        self.assertEqual(engine._counterplay_cooldown, {'sentinel': 17})
        self.assertIs(engine._counterplay_pending, pending_ref)
        self.assertEqual(engine._counterplay_pending, {'sentinel': 19})
        self.assertIs(engine._recent_commission_templates, recent_ref)
        self.assertEqual(engine._recent_commission_templates, ['sentinel'])
        self.assertIs(balance.TUNE, tune_ref)
        self.assertEqual(balance.TUNE, tune_before)
        self.assertEqual(balance.ACTIVE_DIFFICULTY, difficulty_before)
        self.assertEqual(balance.ACTIVE_ORIGIN, origin_before)
        self.assertEqual(commissions._next_uid, next_uid_before)
        self.assertEqual(random.getstate(), rng_before)
        with open(path, 'rb') as stream:
            self.assertEqual(stream.read(), original_bytes)

    def test_handwritten_v5_migrates_with_empty_skill_state(self):
        legacy = self._handwritten_v5()
        self.assertNotIn('skill_queue', legacy['player'])
        self.assertNotIn('active_skill_effects', legacy['player'])
        legacy_before = copy.deepcopy(legacy)
        migrated = save_manager._v5_to_v6(legacy)
        self.assertEqual(legacy, legacy_before)
        self.assertIsNot(migrated, legacy)
        self.assertIsNot(migrated['player'], legacy['player'])
        self.assertEqual(migrated['version'], 6)
        self.assertEqual(migrated['player']['skill_queue'], [])
        self.assertEqual(migrated['player']['active_skill_effects'], [])
        path = self._path()
        original_bytes = self._write(path, legacy)

        self.assertEqual(save_manager.load_ex(path), (True, save_manager.LOAD_OK))
        self.assertEqual(engine.player.skill_queue, [])
        self.assertEqual(engine.player.active_skill_effects, [])
        with open(path, 'rb') as stream:
            self.assertEqual(stream.read(), original_bytes)

    def test_v5_migration_discards_noncontract_skill_fields(self):
        legacy = self._handwritten_v5()
        legacy['player']['skill_queue'] = [
            {'skill_id': 'missing', 'targets': 'not-a-list'},
        ]
        legacy['player']['active_skill_effects'] = 'not-a-list'
        legacy_before = copy.deepcopy(legacy)

        migrated = save_manager._v5_to_v6(legacy)

        self.assertEqual(legacy, legacy_before)
        self.assertEqual(migrated['player']['skill_queue'], [])
        self.assertEqual(migrated['player']['active_skill_effects'], [])

    def test_v6_roundtrip_preserves_fifo_targets_cooldowns_and_uses(self):
        engine.player.unlocked_skills.update({'open_bait', 'algo_top'})
        engine.player.skill_queue = [
            SkillCast('push_song'), SkillCast('open_bait', ('CN', 'US')),
        ]
        engine.player.skill_cooldowns = {'push_song': 3, 'open_bait': 9}
        engine.player.skill_uses = {'push_song': 4, 'open_bait': 2}
        path = self._path()
        save_manager.save(path)

        engine.init_game(seed=72)
        self.assertEqual(save_manager.load_ex(path), (True, save_manager.LOAD_OK))
        self.assertEqual(
            engine.player.skill_queue,
            [SkillCast('push_song'), SkillCast('open_bait', ('CN', 'US'))],
        )
        self.assertEqual(engine.player.skill_cooldowns,
                         {'push_song': 3, 'open_bait': 9})
        self.assertEqual(engine.player.skill_uses,
                         {'push_song': 4, 'open_bait': 2})

        engine.player.skill_queue = [SkillCast('algo_top'), SkillCast('stealth')]
        engine.player.skill_cooldowns = {'algo_top': 5, 'stealth': 8}
        engine.tick_one_round()
        save_manager.save(path)
        engine.init_game(seed=73)
        self.assertEqual(save_manager.load_ex(path), (True, save_manager.LOAD_OK))
        self.assertEqual(
            [(a.skill_id, a.remaining_ticks)
             for a in engine.player.active_skill_effects],
            [('stealth', 1)],
        )

    def test_save_rejects_invalid_live_state_without_replacing_good_file(self):
        path = self._path()
        save_manager.save(path)
        with open(path, 'rb') as stream:
            good_bytes = stream.read()

        cases = (
            ('nan_cooldown', [], {'stealth': float('nan')}, 100.0),
            ('fake_cast', [object()], {}, 100.0),
            ('infinite_cooldown', [SkillCast('stealth')],
             {'stealth': float('inf')}, 100.0),
            ('non_skill_nan', [], {}, float('nan')),
        )
        for name, queue, cooldowns, compute in cases:
            with self.subTest(name=name):
                engine.player.skill_queue = queue
                engine.player.active_skill_effects = []
                engine.player.skill_cooldowns = cooldowns
                engine.player.compute = compute

                with self.assertRaises(ValueError):
                    save_manager.save(path)

                with open(path, 'rb') as stream:
                    self.assertEqual(stream.read(), good_bytes)
                self.assertFalse(os.path.exists(path + '.tmp'))

    def test_bad_v6_skill_shapes_are_rejected_without_mutation(self):
        _, valid = self._valid_v6()
        variants = {}

        def variant(name, queue=None, active=None, cooldowns=None):
            bad = copy.deepcopy(valid)
            if queue is not None:
                bad['player']['skill_queue'] = queue
            if active is not None:
                bad['player']['active_skill_effects'] = active
            if cooldowns is not None:
                bad['player']['skill_cooldowns'] = cooldowns
            variants[name] = bad

        variant('unknown', [{'skill_id': 'missing', 'targets': []}], [],
                {'missing': 2})
        variant('item_not_dict', ['stealth'], [], {'stealth': 8})
        variant('queue_not_list', {}, [], {})
        variant('active_not_list', [], {}, {})
        variant('item_extra_field',
                [{'skill_id': 'stealth', 'targets': [], 'extra': 1}], [],
                {'stealth': 8})
        variant('targets_not_list',
                [{'skill_id': 'stealth', 'targets': 'CN'}], [],
                {'stealth': 8})
        variant('duplicate_targets',
                [{'skill_id': 'stealth', 'targets': ['CN', 'CN']}], [],
                {'stealth': 8})
        variant('empty_target',
                [{'skill_id': 'stealth', 'targets': ['']}], [],
                {'stealth': 8})
        variant('unknown_target',
                [{'skill_id': 'stealth', 'targets': ['XX']}], [],
                {'stealth': 8})
        locked = next(c['code'] for c in valid['countries'] if not c['unlocked'])
        variant('locked_target',
                [{'skill_id': 'stealth', 'targets': [locked]}], [],
                {'stealth': 8})
        variant('duplicate_id', [
            {'skill_id': 'stealth', 'targets': []},
            {'skill_id': 'stealth', 'targets': []},
        ], [], {'stealth': 8})
        variant('cross_duplicate',
                [{'skill_id': 'stealth', 'targets': []}],
                [{'skill_id': 'stealth', 'targets': [], 'remaining_ticks': 1}],
                {'stealth': 8})
        for remaining in (True, 1.0, '1', 0, -1, 2, 9):
            variant(f'remaining_{remaining!r}', [], [{
                'skill_id': 'stealth', 'targets': [],
                'remaining_ticks': remaining,
            }], {'stealth': 8})
        for cooldown in (None, 0, -1, True, float('nan'), float('inf'), '8'):
            cooldowns = {} if cooldown is None else {'stealth': cooldown}
            variant(f'cooldown_{cooldown!r}',
                    [{'skill_id': 'stealth', 'targets': []}], [], cooldowns)
        variant('queue_cooldown_short',
                [{'skill_id': 'stealth', 'targets': []}], [], {'stealth': 1})
        variant('queue_cooldown_partial',
                [{'skill_id': 'stealth', 'targets': []}], [], {'stealth': 2})
        variant('queue_cooldown_huge',
                [{'skill_id': 'stealth', 'targets': []}], [],
                {'stealth': 10 ** 1000})
        variant('active_cooldown_unreachable', [], [{
            'skill_id': 'stealth', 'targets': [], 'remaining_ticks': 1,
        }], {'stealth': 1})
        variant('active_exceeds_cooldown', [], [{
            'skill_id': 'anon_cdn', 'targets': [], 'remaining_ticks': 2,
        }], {'anon_cdn': 1})
        for key in ('skill_queue', 'active_skill_effects'):
            bad = copy.deepcopy(valid)
            bad['player'].pop(key, None)
            variants[f'missing_{key}'] = bad

        # Already-saturated targets are historical state and remain loadable.
        saturated = copy.deepcopy(valid)
        saturated['player']['skill_queue'] = [
            {'skill_id': 'open_bait', 'targets': ['CN']},
        ]
        saturated['player']['unlocked_skills'].append('open_bait')
        saturated['player']['skill_cooldowns'] = {'open_bait': 9}
        cn = next(c for c in saturated['countries'] if c['code'] == 'CN')
        cn['downloads_m'] = 1e12
        path = self._path('saturated.json')
        self._write(path, saturated)
        self.assertEqual(save_manager.load_ex(path), (True, save_manager.LOAD_OK))
        self.assertEqual(engine.player.skill_queue,
                         [SkillCast('open_bait', ('CN',))])

        for name, bad in variants.items():
            with self.subTest(name=name):
                engine.init_game(seed=80)
                self._assert_load_bad_unchanged(bad)

    def test_apply_failure_restores_exact_preload_global_state(self):
        _, bad = self._valid_v6()
        previous_next_uid = commissions._next_uid
        self.addCleanup(setattr, commissions, '_next_uid', previous_next_uid)
        commissions._next_uid = 23
        valid_high_uid = commissions.CommissionState(
            uid=9001, template_id='C2', goal='downloads', icon='[D]',
            name_zh='拉新冲刺', name_en='Growth Sprint', window=8,
            reward_mult=1.0,
        )
        bad['player']['commissions'] = [
            commissions.to_dict(valid_high_uid),
            {'not': 'a commission'},
        ]
        self._assert_load_bad_unchanged(bad)


class SkillUiTests(unittest.TestCase):
    def setUp(self):
        self.old_lang = i18n.get_lang()
        self.addCleanup(i18n.set_lang, self.old_lang)
        balance.apply_difficulty('normal')
        self.addCleanup(balance.apply_difficulty, 'normal')
        self.games = []
        self.addCleanup(self._cleanup_games)

    def _make_game(self):
        with patch.object(main.GameUI, '_reschedule_tick'), \
                patch.object(main.GameUI, '_reschedule_countdown'), \
                patch('cursor_fx.install', return_value=True):
            game = main.GameUI()
        self.games.append(game)
        return game

    def _cleanup_games(self):
        for game in reversed(self.games):
            game.stop_ticking()
            keyboard = getattr(game, '_keyboard', None)
            game._keyboard_closed()
            if keyboard is not None:
                keyboard.release()
            game.commission_bar._unbind_window()
            Window.unbind(on_resize=game._on_window_resize,
                          mouse_pos=game._on_skill_hover)

    def _init_queue(self):
        player = engine.init_game(seed=41)
        player.compute = 1000
        player.seen_tutorial = True
        player.unlocked_skills.update({'algo_top', 'stealth'})
        self.assertTrue(engine.use_skill('algo_top'))
        self.assertTrue(engine.use_skill('stealth'))
        return player

    def test_queue_and_active_status_are_localized_and_follow_engine(self):
        expected = {
            'zh': ('下周期结算', '算法霸榜', '深度伪装', '持续中', '剩余1周期'),
            'en': ('Next cycle', 'Algo Boost', 'Deep Disguise', 'Active', '1 cycle left'),
        }
        for lang, phrases in expected.items():
            with self.subTest(lang=lang):
                i18n.set_lang(lang)
                player = self._init_queue()
                game = self._make_game()
                game.refresh_all()
                queued = game.skill_state_label.text
                self.assertEqual(game.skill_state_hud.opacity, 1)
                for phrase in phrases[:3]:
                    self.assertIn(phrase, queued)
                self.assertLess(queued.index(phrases[1]), queued.index(phrases[2]))

                game.game_tick(0)

                self.assertEqual(player.skill_queue, [])
                self.assertEqual(
                    [(a.skill_id, a.remaining_ticks)
                     for a in player.active_skill_effects],
                    [('stealth', 1)],
                )
                active = game.skill_state_label.text
                self.assertNotIn(phrases[0], active)
                self.assertIn(phrases[3], active)
                self.assertIn(phrases[2], active)
                self.assertIn(phrases[4], active)

    def test_status_compacts_each_section_without_reordering(self):
        i18n.set_lang('en')
        player = engine.init_game(seed=41)
        player.compute = 1000
        player.seen_tutorial = True
        ids = ['push_song', 'algo_top', 'stealth', 'hit_maker']
        player.unlocked_skills.update(ids)
        for sid in ids:
            self.assertTrue(engine.use_skill(sid))
        game = self._make_game()

        text = game._skill_state_text()

        names = [game._skill_name(sid) for sid in ids]
        self.assertLess(text.index(names[0]), text.index(names[1]))
        self.assertLess(text.index(names[1]), text.index(names[2]))
        self.assertNotIn(names[3], text)
        self.assertIn('1 more', text)

    def test_max_queue_and_active_status_fits_two_lines_at_target_sizes(self):
        player = engine.init_game(seed=41)
        player.compute = 1000
        player.seen_tutorial = True
        queued_ids = ['push_song', 'algo_top', 'hit_maker']
        active_ids = ['stealth', 'anon_cdn', 'arbitrage']
        player.skill_queue = [SkillCast(sid) for sid in queued_ids]
        player.active_skill_effects = [
            ActiveSkill(sid, (), remaining_ticks=1) for sid in active_ids
        ]
        game = self._make_game()

        for lang in ('zh', 'en'):
            with self.subTest(lang=lang):
                i18n.set_lang(lang)
                game.refresh_all()
                game.skill_state_label.texture_update()
                lines = game.skill_state_label.text.splitlines()
                self.assertEqual(len(lines), 2)
                self.assertIn(game._skill_name(queued_ids[0]), lines[0])
                self.assertIn(game._skill_name(queued_ids[1]), lines[0])
                self.assertNotIn(game._skill_name(queued_ids[2]), lines[0])
                self.assertIn(i18n.t('sk_more').format(n=1), lines[0])
                self.assertIn(game._skill_name(active_ids[0]), lines[1])
                self.assertIn(game._skill_name(active_ids[1]), lines[1])
                self.assertNotIn(game._skill_name(active_ids[2]), lines[1])
                self.assertIn(i18n.t('sk_more').format(n=1), lines[1])
                tw, th = game.skill_state_label.texture_size
                self.assertLessEqual(tw, game.skill_state_label.width)
                self.assertLessEqual(th, game.skill_state_label.height)

        for width, height in ((1280, 720), (1680, 980)):
            with self.subTest(size=(width, height)):
                game.map_stage.pos = (0, 0)
                game.map_stage.size = (width, height)
                game.skill_state_hud._layout_hud()
                game.skill_pv_hud._layout_hud()
                self.assertAlmostEqual(game.skill_state_hud.center_x,
                                       game.map_stage.center_x)
                self.assertAlmostEqual(game.skill_pv_hud.center_x,
                                       game.map_stage.center_x)
                self.assertLessEqual(game.skill_state_hud.top + 4,
                                     game.skill_pv_hud.y)

    def test_direct_cast_refreshes_queue_hud_immediately(self):
        player = engine.init_game(seed=41)
        player.compute = 1000
        player.seen_tutorial = True
        player.unlocked_skills.add('stealth')
        game = self._make_game()
        self.assertEqual(game.skill_state_hud.opacity, 0)

        game._cast_skill_direct('stealth')

        self.assertEqual([cast.skill_id for cast in player.skill_queue],
                         ['stealth'])
        self.assertEqual(game.skill_state_hud.opacity, 1)
        self.assertIn(game._skill_name('stealth'), game.skill_state_label.text)

    def test_reconstruction_pause_refresh_and_restart_use_engine_state(self):
        self._init_queue()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
            path = os.path.join(root, 'queue.json')
            save_manager.save(path)
            engine.init_game(seed=99)
            self.assertEqual(save_manager.load_ex(path), (True, save_manager.LOAD_OK))

            game = self._make_game()
            before = list(engine.player.skill_queue)
            self.assertIn(i18n.t('sk_queue_next').split('{')[0],
                          game.skill_state_label.text)
            for paused in (True, False):
                game.paused = paused
                game.refresh_all()
                self.assertEqual(engine.player.skill_queue, before)

            with patch.object(game, '_reschedule_tick'):
                game.restart_game()
            self.assertEqual(engine.player.skill_queue, [])
            self.assertEqual(engine.player.active_skill_effects, [])
            self.assertEqual(game.skill_state_hud.opacity, 0)

    def test_preview_surfaces_are_static_and_never_call_engine_preview_apis(self):
        i18n.set_lang('en')
        player = engine.init_game(seed=41)
        player.compute = 1000
        player.seen_tutorial = True
        player.unlocked_skills.update({'algo_top', 'stealth'})
        game = self._make_game()
        preview_skill = Mock(side_effect=AssertionError('preview_skill called'))
        preview_cycle = Mock(side_effect=AssertionError('preview_next_cycle called'))

        with patch.object(engine, 'preview_skill', preview_skill), \
                patch.object(engine, 'preview_next_cycle', preview_cycle):
            game._render_skill_preview('stealth')
            foot = game._skill_preview_foot('stealth')
            game.start_drop('algo_top', ['CN'])
            game._show_drop_preview()
            game.refresh_all()

        preview_skill.assert_not_called()
        preview_cycle.assert_not_called()
        hover = ' '.join(chip.text for chip in game.skill_pv_chips)
        self.assertIn('Deep Disguise', hover)
        self.assertIn(f"{i18n.t('cost')} 0", hover)
        self.assertIn('Cooldown 8', hover)
        self.assertIn(i18n.t('sk_preview_static'), hover)
        self.assertIn(i18n.t('sk_preview_static'), foot)
        self.assertEqual(game._drop_preview.lbl_est.text, '--')
        self.assertNotRegex(hover + foot, r'\d+(?:\.\d+)?\s*(?:M|B)?\s*[→+]')

    def test_failed_direct_cast_reports_specific_reason(self):
        i18n.set_lang('en')
        player = engine.init_game(seed=41)
        player.compute = 1000
        player.seen_tutorial = True
        player.unlocked_skills.add('stealth')
        player.skill_cooldowns['stealth'] = 2
        game = self._make_game()

        game._cast_skill_direct('stealth')

        self.assertIn(i18n.t('sk_fail_cooldown'), player.events_history[0])


if __name__ == "__main__":
    unittest.main()
