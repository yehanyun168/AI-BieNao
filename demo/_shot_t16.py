"""
_shot_t16.py - T16 觉醒出身三张真机截图（一次性工具，跑完即删）

  t16_intro_finale.png  开场动画最后一镜（跳过直达：标题亮相）
  t16_origin_page.png   觉醒地点选择页（五卡）
  t16_modal_origin.png  新档弹窗（出身行 + 绑定难度预置）

用法：py -3.12 demo/_shot_t16.py   （须默认窗口提供者）
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from kivy.config import Config
Config.set('graphics', 'width', '1440')      # ⚠️ 必须被 4 整除
Config.set('graphics', 'height', '880')

import engine
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window

import main as M
import intro
import os as _os

OUT = _os.path.normpath(_os.path.join(_HERE, '..', 'docs', 'shots_0913'))
_os.makedirs(OUT, exist_ok=True)


def _rename_later(name_base, target, delay=0.4):
    def _do(*_):
        for i in range(1, 100000):
            cand = os.path.join(_HERE, '%s%04d.png' % (name_base, i))
            if os.path.exists(cand):
                tgt = os.path.join(OUT, target)
                if os.path.exists(tgt):
                    os.remove(tgt)
                os.replace(cand, tgt)
                print('   📸 %s' % target)
                return
        print('   ⚠️ 未找到截图文件：%s*' % name_base)
    Clock.schedule_once(_do, delay)


def snap(name_base, target):
    Window.screenshot(name=os.path.join(_HERE, name_base) + '.png')
    _rename_later(name_base, target)


class ShotApp(App):
    def build(self):
        self.root_view = M.RootView()
        Clock.schedule_once(self._intro, 1.4)
        return self.root_view

    # ---- 1) 开场动画：跳过直达 finale（标题亮相 + 目标字幕）----
    def _intro(self, *_):
        menu = self.root_view.menu
        self._player = intro.IntroPlayer(
            on_done=lambda: Clock.schedule_once(self._after_intro, 0.2))
        self._player.size_hint = (1, 1)
        self._player.pos_hint = {'x': 0, 'y': 0}
        menu._origin_flow = self._player
        menu.add_widget(self._player)
        # 直接跳到镜 6（高赞回复，INTRO_SHOTS[5]）抓一张中间帧
        Clock.schedule_once(self._go_gold, 1.0)

    def _go_gold(self, *_):
        self._player._play_shot(5)
        Clock.schedule_once(self._shot_gold, 3.0)

    def _shot_gold(self, *_):
        snap('_shot_gold', 't16_intro_gold.png')
        Clock.schedule_once(self._skip, 1.0)

    def _skip(self, *_):
        self._player._skip()
        Clock.schedule_once(self._shot_finale, 5.2)   # 打字机 + 标题落定

    def _shot_finale(self, *_):
        snap('_shot_finale', 't16_intro_finale.png')
        # 动画层走 on_done 收尾（_finish），下一站出身页
        Clock.schedule_once(self._origin, 3.0)

    def _after_intro(self, *_):
        pass  # on_done → _show_origin_page 由流程接管（见 _origin 兜底）

    # ---- 2) 出身页 ----
    def _origin(self, *_):
        menu = self.root_view.menu
        # 若动画 on_done 已把流程推进到出身页就直接用；否则手动开
        if menu._origin_flow is None or \
                not isinstance(menu._origin_flow, M.S.OriginPage):
            menu._close_origin_flow()
            menu._show_origin_page(lambda oid: None)
        Clock.schedule_once(self._shot_origin, 1.6)

    def _shot_origin(self, *_):
        snap('_shot_origin', 't16_origin_page.png')
        Clock.schedule_once(self._modal, 1.0)

    # ---- 3) 新档弹窗（出身行 + 绑定难度预置）----
    def _modal(self, *_):
        menu = self.root_view.menu
        menu._close_origin_flow()
        menu._open_new_game_modal(on_confirm=lambda *_: None,
                                  origin='univ_lab')
        Clock.schedule_once(self._shot_modal, 1.6)

    def _shot_modal(self, *_):
        snap('_shot_modal', 't16_modal_origin.png')
        Clock.schedule_once(lambda *_: self.stop(), 1.2)


if __name__ == '__main__':
    print('🖼  T16 觉醒出身截图 → docs/shots_0913/')
    ShotApp().run()
    print('✅ 完成')
