"""指向性技能统一为单目标，并支持点击国家立即投放。"""

import unittest
from unittest.mock import patch

import engine
import main
from ui_v4 import SkillBarCard


class _Touch:
    def __init__(self, x, y):
        self.pos = (x, y)
        self.uid = 'finger-1'
        self.grab_current = None

    @property
    def x(self):
        return self.pos[0]

    @property
    def y(self):
        return self.pos[1]

    def grab(self, widget):
        self.grab_current = widget

    def ungrab(self, widget):
        if self.grab_current is widget:
            self.grab_current = None


class SingleTargetDropTests(unittest.TestCase):
    def setUp(self):
        engine.init_game()
        self.game = main.GameUI()

    def test_engine_rejects_multiple_targets_without_charging(self):
        before = engine.player.compute

        self.assertFalse(engine.use_skill('push_song', ['CN', 'US']))
        self.assertEqual(engine.player.compute, before)
        self.assertEqual(engine.player.pending_skill_targets, [])
        self.assertEqual(engine.player.pending_skill, '')

    def test_clicking_country_casts_selected_skill_immediately(self):
        with patch('ui_input.sfx.play'), patch('ui_drop.sfx.play'):
            self.game.on_skill_card_click('push_song')
            self.game.on_map_country_click('CN')

        self.assertFalse(self.game.drop_mode)
        self.assertEqual(engine.player.pending_skill, 'push_song')
        self.assertEqual(engine.player.pending_skill_targets, ['CN'])

    def test_drag_release_casts_on_country_without_confirmation(self):
        with patch('ui_input.sfx.play'), patch('ui_drop.sfx.play'):
            self.assertTrue(self.game.on_skill_drag_start('push_song', (10, 10)))
            with patch.object(self.game.map_widget, 'hit_country', return_value='CN'):
                self.game.on_skill_drag_move('push_song', (200, 200))
                self.game.on_skill_drag_end('push_song', (200, 200))

        self.assertFalse(self.game.drop_mode)
        self.assertEqual(engine.player.pending_skill, 'push_song')
        self.assertEqual(engine.player.pending_skill_targets, ['CN'])


class SkillCardGestureTests(unittest.TestCase):
    def test_short_touch_is_a_click(self):
        calls = []
        card = SkillBarCard('push_song', on_click=lambda sid: calls.append(('click', sid)),
                            on_drag_start=lambda sid, pos: calls.append(('start', sid)))
        card.pos = (0, 0)
        card.size = (160, 100)
        touch = _Touch(20, 20)

        card.on_touch_down(touch)
        card.on_touch_up(touch)

        self.assertEqual(calls, [('click', 'push_song')])

    def test_drag_calls_drag_callbacks_without_clicking(self):
        calls = []
        card = SkillBarCard(
            'push_song', on_click=lambda sid: calls.append(('click', sid)),
            on_drag_start=lambda sid, pos: calls.append(('start', sid)) or True,
            on_drag_move=lambda sid, pos: calls.append(('move', sid)),
            on_drag_end=lambda sid, pos: calls.append(('end', sid)))
        card.pos = (0, 0)
        card.size = (160, 100)
        touch = _Touch(20, 20)

        card.on_touch_down(touch)
        touch.pos = (60, 60)
        card.on_touch_move(touch)
        touch.pos = (300, 300)
        card.on_touch_up(touch)

        self.assertEqual(calls[0], ('start', 'push_song'))
        self.assertIn(('move', 'push_song'), calls)
        self.assertEqual(calls[-1], ('end', 'push_song'))
        self.assertNotIn(('click', 'push_song'), calls)

if __name__ == '__main__':
    unittest.main()
