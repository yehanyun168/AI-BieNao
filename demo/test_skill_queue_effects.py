import copy
import random
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

import engine
import skill_state
from balance import TUNE, apply_difficulty
from data import SKILLS
from skill_state import (
    ActiveSkill,
    SkillCast,
    validate_skill_table,
)


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


if __name__ == "__main__":
    unittest.main()
