"""普通事件随全局语言切换的回归测试。"""

from unittest.mock import patch

import data
import engine
import i18n


def test_all_generic_events_have_bilingual_text():
    for evt in data.EVENTS:
        assert evt.text('title', 'zh')
        assert evt.text('title', 'en')
        assert evt.text('description', 'zh')
        assert evt.text('description', 'en')
        assert evt.text('message', 'zh')
        assert evt.text('message', 'en')
        assert evt.text('title', 'zh') != evt.text('title', 'en')


def test_event_log_uses_current_language():
    evt = data.EVENTS[0]
    player = engine.init_game(seed=1)
    i18n.set_lang('en')
    try:
        with patch.object(engine, '_pick_boundary_event',
                          return_value=('global', evt)):
            engine.tick_one_round(auto_choice=False)
        assert evt.text('message', 'en') in player.events_history[0]
        assert evt.text('message', 'zh') not in player.events_history[0]
    finally:
        i18n.set_lang('zh')


if __name__ == '__main__':
    test_all_generic_events_have_bilingual_text()
    test_event_log_uses_current_language()
    print('2/2 generic event i18n tests passed')
