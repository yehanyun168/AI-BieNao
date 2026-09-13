"""回合边界统一事件判定的回归测试。"""

from unittest.mock import Mock, patch

import engine


def _effects():
    return engine.aggregate_effects(engine.player.tech)


def test_crisis_has_highest_priority():
    player = engine.init_game(seed=1)
    player.suspicion = 80.0
    player.crisis_triggered = False

    with patch.object(engine.v2_events, 'pick_event') as pick_v2, \
            patch.object(engine, '_tick_country_event_trigger') as pick_country, \
            patch.object(engine, '_tick_event_trigger') as pick_global:
        kind, event = engine._pick_boundary_event(_effects())

    assert (kind, event) == ('crisis', None)
    pick_v2.assert_not_called()
    pick_country.assert_not_called()
    pick_global.assert_not_called()


def test_v2_stops_lower_priority_checks():
    player = engine.init_game(seed=1)
    player.tick_count = 20
    chosen = Mock(id='v2-test')

    with patch.object(engine.random, 'random', return_value=0.0), \
            patch.object(engine.v2_events, 'pick_event', return_value=chosen), \
            patch.object(engine, '_tick_country_event_trigger') as pick_country, \
            patch.object(engine, '_tick_event_trigger') as pick_global:
        kind, event = engine._pick_boundary_event(_effects())

    assert (kind, event) == ('v2', chosen)
    pick_country.assert_not_called()
    pick_global.assert_not_called()


def test_country_follows_v2_and_stops_global_check():
    player = engine.init_game(seed=1)
    player.tick_count = 20
    chosen = Mock(id='country-test')

    with patch.object(engine.random, 'random', return_value=0.0), \
            patch.object(engine.v2_events, 'pick_event', return_value=None), \
            patch.object(engine, '_tick_country_event_trigger', return_value=chosen), \
            patch.object(engine, '_tick_event_trigger') as pick_global:
        kind, event = engine._pick_boundary_event(_effects())

    assert (kind, event) == ('country', chosen)
    pick_global.assert_not_called()


if __name__ == '__main__':
    test_crisis_has_highest_priority()
    test_v2_stops_lower_priority_checks()
    test_country_follows_v2_and_stops_global_check()
    print('3/3 boundary event tests passed')
