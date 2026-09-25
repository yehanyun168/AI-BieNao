import copy
import os

import engine
import save_manager
from skill_state import ActiveSkill, SkillCast


class FinalReviewSkillSaveMixin:
    def test_save_rejects_unreachable_skill_cooldowns(self):
        path = self._path()
        save_manager.save(path)
        with open(path, 'rb') as stream:
            good_bytes = stream.read()

        cases = (
            ('queued_partial', [SkillCast('stealth')], [], 2),
            ('queued_huge', [SkillCast('stealth')], [], 10 ** 1000),
            ('active_wrong', [], [ActiveSkill('stealth', (), 1)], 1),
        )
        for name, queue, active, cooldown in cases:
            with self.subTest(name=name):
                engine.player.skill_queue = queue
                engine.player.active_skill_effects = active
                engine.player.skill_cooldowns = {'stealth': cooldown}

                with self.assertRaisesRegex(
                    ValueError, r'^invalid live skill state$'
                ):
                    save_manager.save(path)

                with open(path, 'rb') as stream:
                    self.assertEqual(stream.read(), good_bytes)
                self.assertFalse(os.path.exists(path + '.tmp'))

    def test_float_cooldown_equal_to_config_is_reachable(self):
        engine.player.skill_queue = [SkillCast('stealth')]
        engine.player.skill_cooldowns = {'stealth': 8.0}
        path = self._path()

        save_manager.save(path)
        engine.init_game(seed=72)

        self.assertEqual(save_manager.load_ex(path),
                         (True, save_manager.LOAD_OK))
        self.assertEqual(engine.player.skill_queue, [SkillCast('stealth')])
        self.assertEqual(engine.player.skill_cooldowns, {'stealth': 8.0})

    def test_v6_rejects_skill_not_in_saved_unlocks_atomically(self):
        _, bad = self._valid_v6()
        bad['player']['skill_queue'] = [
            {'skill_id': 'algo_top', 'targets': []},
        ]
        bad['player']['skill_cooldowns'] = {'algo_top': 5}
        self.assertNotIn('algo_top', bad['player']['unlocked_skills'])

        path = self._path('locked-skill.json')
        original_bytes = self._write(path, bad)
        player_ref = engine.player
        countries_ref = engine.player_countries
        player_before = copy.deepcopy(player_ref)
        countries_before = copy.deepcopy(countries_ref)

        result = save_manager.load_ex(path)
        if result == (True, save_manager.LOAD_OK):
            report = engine.tick_one_round()
            self.assertIn('algo_top', report['skills_activated'])
            self.fail('locked algo_top loaded and activated on the next tick')

        self.assertEqual(result, (False, save_manager.LOAD_BAD_SCHEMA))
        self.assertIs(engine.player, player_ref)
        self.assertEqual(engine.player, player_before)
        self.assertIs(engine.player_countries, countries_ref)
        self.assertEqual(engine.player_countries, countries_before)
        with open(path, 'rb') as stream:
            self.assertEqual(stream.read(), original_bytes)
