"""指向技能点击前必须经过与全局技能相同的通用可用性检查。"""

import unittest
from unittest.mock import patch

import engine
import main


class TargetSkillClickGuardTests(unittest.TestCase):
    def setUp(self):
        engine.init_game()
        self.game = main.GameUI()

    def test_target_skill_on_cooldown_does_not_enter_drop_mode(self):
        engine.player.skill_cooldowns['push_song'] = 2
        rejected = []
        self.game._fx_reject = rejected.append

        with patch('ui_input.sfx.play') as play:
            self.game.on_skill_card_click('push_song')

        self.assertFalse(self.game.drop_mode)
        self.assertIsNone(self.game.drop_skill)
        self.assertEqual(rejected, ['push_song'])
        play.assert_called_once_with('error')

    def test_ready_target_skill_still_enters_drop_mode(self):
        with patch('ui_input.sfx.play'):
            self.game.on_skill_card_click('push_song')

        self.assertTrue(self.game.drop_mode)
        self.assertEqual(self.game.drop_skill, 'push_song')


if __name__ == '__main__':
    unittest.main()
