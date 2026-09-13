"""算力维护费结算回归测试。

来源：协作者 273978c《修改算力机制，加入维护费》附带测试，2026-09-13 合入时
适配两点：① maintenance_per_tick 由测试显式 patch（TUNE 默认 0.0 = 关闭，
不改动已标定经济）；② 断言按「费用 = tick × 系数」动态对齐。
"""

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


_QUIET = {'growth_base': 0.0,
          'event_prob_base': 0.0,
          'event_prob_country': 0.0,
          'event_prob_v2': 0.0,
          'maintenance_per_tick': 1.0}


def test_maintenance_equals_current_tick():
    player = _quiet_game(compute=100.0, completed_ticks=9)

    with patch.dict(engine.TUNE, _QUIET):
        report = engine.tick_one_round()

    assert report['tick'] == 10
    assert report['maintenance_fee'] == 10.0      # tick 10 × 系数 1.0
    assert report['compute_gain'] == -10.0        # 无收入，纯扣费
    assert player.compute == 90.0


def test_maintenance_cannot_make_compute_negative():
    player = _quiet_game(compute=3.0, completed_ticks=9)

    with patch.dict(engine.TUNE, _QUIET):
        report = engine.tick_one_round()

    assert report['maintenance_fee'] == 10.0
    assert report['compute_gain'] == -3.0         # 下限钳到 0
    assert player.compute == 0.0


def test_maintenance_disabled_by_default():
    """TUNE 默认 0.0：不改变已标定经济（本回合收支与旧版一致）。"""
    player = _quiet_game(compute=100.0, completed_ticks=9)

    with patch.dict(engine.TUNE, {'growth_base': 0.0,
                                  'event_prob_base': 0.0,
                                  'event_prob_country': 0.0,
                                  'event_prob_v2': 0.0}):
        report = engine.tick_one_round()

    assert report['maintenance_fee'] == 0.0
    assert player.compute == 100.0


if __name__ == '__main__':
    test_maintenance_equals_current_tick()
    test_maintenance_cannot_make_compute_negative()
    test_maintenance_disabled_by_default()
    print('3/3 maintenance tests passed')
