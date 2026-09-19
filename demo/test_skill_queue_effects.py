import copy
import random
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
