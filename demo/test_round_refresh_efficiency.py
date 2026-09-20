"""每回合 UI 刷新应跳过状态未变化的昂贵重绘。"""

import unittest
from unittest.mock import Mock

import engine
import main
from ui_v4 import SkillBarCard


class RoundRefreshEfficiencyTests(unittest.TestCase):
    def test_skill_card_same_state_does_not_layout_again(self):
        card = SkillBarCard('push_song')
        card.set_state('ready', 0, 0.0, 'Ready')
        card._layout = Mock()

        card.set_state('ready', 0, 0.0, 'Ready')
        card.set_selected(False)

        card._layout.assert_not_called()

    def test_unchanged_unlock_layer_skips_map_redraw(self):
        engine.init_game(seed=1)
        game = main.GameUI()
        game._apply_layer()
        game.map_widget.set_layer_fills = Mock()
        game.map_widget.set_heat = Mock()
        game.legend_hud.set_texts = Mock()

        game._apply_layer()

        game.map_widget.set_layer_fills.assert_not_called()
        game.map_widget.set_heat.assert_not_called()
        game.legend_hud.set_texts.assert_not_called()

    def test_refresh_all_skips_unchanged_country_states(self):
        engine.init_game(seed=1)
        game = main.GameUI()
        game.refresh_all()
        game.map_widget.set_country_states = Mock()

        game.refresh_all()

        game.map_widget.set_country_states.assert_not_called()

if __name__ == '__main__':
    unittest.main()
