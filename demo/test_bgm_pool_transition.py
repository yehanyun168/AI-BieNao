"""主菜单进入对局时，旧曲必须在淡出结束后真正停止。"""

import unittest
from unittest.mock import patch

import bgm


class _Sound:
    def __init__(self):
        self.state = 'stop'
        self.volume = bgm.VOLUME
        self.length = 60.0
        self.position = 0.0
        self.stop_calls = 0

    def play(self):
        self.state = 'play'

    def stop(self):
        self.state = 'stop'
        self.stop_calls += 1


class BgmPoolTransitionTests(unittest.TestCase):
    def test_menu_track_stops_after_switching_to_game_pool(self):
        menu = _Sound()
        calm = _Sound()
        menu.play()
        callbacks = []

        old = (bgm.BGM_ON, bgm._LOADED, bgm._SOUNDS, bgm._current,
               bgm._playing, bgm._advance_ev, bgm._gap_ev, bgm._paused)
        try:
            bgm.BGM_ON = True
            bgm._LOADED = True
            bgm._SOUNDS = {'menu': menu, 'calm': calm}
            bgm._current = 'menu'
            bgm._playing = 'menu'
            bgm._advance_ev = None
            bgm._gap_ev = None
            bgm._paused = False

            with patch.object(bgm.Clock, 'schedule_interval',
                              side_effect=lambda cb, _dt: callbacks.append(cb)), \
                    patch.object(bgm.Clock, 'schedule_once', return_value=None):
                bgm.update('calm')
                fade_out = callbacks[0]
                for _ in range(8):
                    if fade_out(0.1) is False:
                        break

            self.assertEqual(menu.state, 'stop')
            self.assertEqual(menu.stop_calls, 1)
            self.assertEqual(bgm.current_state(), 'calm')
            self.assertEqual(calm.state, 'play')
        finally:
            (bgm.BGM_ON, bgm._LOADED, bgm._SOUNDS, bgm._current,
             bgm._playing, bgm._advance_ev, bgm._gap_ev, bgm._paused) = old


if __name__ == '__main__':
    unittest.main()
