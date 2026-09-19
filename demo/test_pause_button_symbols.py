"""回合控制只保留顶部时间框内的暂停/继续 PNG 图标。"""

import unittest
from unittest.mock import patch

import engine
import main


class PauseButtonSymbolTests(unittest.TestCase):
    def test_button_switches_pause_and_resume_images(self):
        engine.init_game()
        game = main.GameUI()
        self.assertFalse(hasattr(game, 'btn_pause'))
        self.assertFalse(hasattr(game, 'btn_drop'))
        self.assertEqual(game.pause_chip.text, '')
        self.assertTrue(game.pause_chip_icon.source.endswith('pause.png'))

        with patch('ui_session.sfx.play'), patch('ui_session.bgm.pause'):
            game.toggle_pause()
        self.assertTrue(game.pause_chip_icon.source.endswith('resume.png'))

        with patch('ui_session.sfx.play'), patch('ui_session.bgm.resume'):
            game.toggle_pause()
        self.assertTrue(game.pause_chip_icon.source.endswith('pause.png'))


if __name__ == '__main__':
    unittest.main()
