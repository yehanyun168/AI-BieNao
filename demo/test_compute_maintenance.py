"""算力维护费结算回归测试。"""

import engine
from unittest.mock import patch


def _quiet_game(compute: float, completed_ticks: int):
    player = engine.init_game(seed=1)
    player.compute = compute
    player.compute_peak = max(player.compute_peak, compute)
    player.tick_count = completed_ticks
    for country in engine.player_countries:
        country.downloads_m = 0.0
        country.unlocked = True
    return player


def test_maintenance_equals_current_tick():
    player = _quiet_game(compute=100.0, completed_ticks=9)

    with patch.dict(engine.TUNE, {'growth_base': 0.0,
                                  'event_prob_base': 0.0,
                                  'event_prob_country': 0.0,
                                  'event_prob_v2': 0.0}):
        report = engine.tick_one_round()

    assert report['tick'] == 10
    assert report['maintenance_fee'] == 10.0
    assert report['compute_gain'] == -10.0
    assert player.compute == 90.0


def test_maintenance_cannot_make_compute_negative():
    player = _quiet_game(compute=3.0, completed_ticks=9)

    with patch.dict(engine.TUNE, {'growth_base': 0.0,
                                  'event_prob_base': 0.0,
                                  'event_prob_country': 0.0,
                                  'event_prob_v2': 0.0}):
        report = engine.tick_one_round()

    assert report['maintenance_fee'] == 10.0
    assert report['compute_gain'] == -3.0
    assert player.compute == 0.0


if __name__ == '__main__':
    test_maintenance_equals_current_tick()
    test_maintenance_cannot_make_compute_negative()
    print('2/2 maintenance tests passed')
