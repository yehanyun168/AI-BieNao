"""make_screenshots_v4.py —— 生成 v0.4 真机 14 屏截图到 demo/_v4shots/。

用法：
    python make_screenshots_v4.py

说明：
  * 桌面锁屏时 PIL ImageGrab 抓不到窗口，所以走 Kivy 的 Window.screenshot
    （SDL2 后端：立即 glReadPixels + 写 PNG）。
  * Kivy 的 name 必须带扩展名（它用 name.split('.')[-1] 取扩展名）；
    落盘名是 <去扩展名部分>{:04d}.<ext>，抓完立刻 os.replace 成目标名。
  * 窗口物理宽度取 1440（能被 4 整除），否则 RGBA 行错位、颜色会循环移位。
  * 每步先关掉遗留弹窗/浮层，否则模态会盖住后续所有屏（S13/S14 会撞成同图）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from kivy.config import Config          # noqa: E402
Config.set('graphics', 'width', '1440')     # 1440 % 4 == 0
Config.set('graphics', 'height', '880')
Config.set('graphics', 'resizable', '0')

from kivy.app import App                # noqa: E402
from kivy.clock import Clock            # noqa: E402
from kivy.core.window import Window     # noqa: E402

import main as M                        # noqa: E402
import engine                           # noqa: E402
import v2_events                        # noqa: E402

OUT = os.path.join(HERE, '_v4shots')
os.makedirs(OUT, exist_ok=True)

SAVED = []
FAILED = []


def dismiss_popups() -> None:
    """关掉所有 ModalView / Popup，并**同步强制移除**（截图切换屏时必做）。

    ⚠️ 坑：``ModalView.dismiss()`` 走 0.4s 淡出动画，动画由**真实时钟**驱动；
    而截图循环只用 ``Clock.tick()`` 泵布局、不 sleep → 动画永不完成、
    popup 永远留在 ``Window.children``。后果 = 旧弹窗的半透明遮罩（0.55 黑）
    与新弹窗的遮罩叠加，面板被压成近纯黑（曾致 S08/S09 主色 rgb(0,1,1)）。
    这里先 dismiss() 再强制从 Window 摘除，保证每屏都是干净底。
    """
    try:
        from kivy.uix.modalview import ModalView
    except Exception:
        return
    for w in list(getattr(Window, 'children', []) or []):
        if isinstance(w, ModalView):
            try:
                w.dismiss()
            except Exception:
                pass
            # 强制同步移除（不依赖淡出动画回调）
            try:
                w._real_remove_widget()
            except Exception:
                pass
            if w.parent is not None:
                try:
                    w.parent.remove_widget(w)
                except Exception:
                    pass


class ShotApp(App):
    """顺序执行「清理 → 切状态 → 等一帧 → 截图」。"""

    def build(self):
        engine.init_game()
        self.rv = M.RootView()
        self.i = 0
        self.plan = self._plan()
        Clock.schedule_once(self._step, 1.6)
        return self.rv

    # ---------------- 动作定义 ----------------
    def _g(self):
        return self.rv.game

    def clean(self) -> None:
        dismiss_popups()
        g = self._g()
        if g is None:
            return
        for fn in ('_close_log', '_close_inspector'):
            try:
                getattr(g, fn)()
            except Exception:
                pass
        try:
            g.close_page()
        except Exception:
            pass

    def _plan(self):
        rv = self.rv

        def menu():
            rv.show_menu()

        def new_game():
            engine.init_game()
            for _ in range(10):
                engine.tick_one_round()
            rv.start_new_game()

        def inspector():
            self.clean()
            self._g().on_map_country_click('CN')

        def drop_mode():
            self.clean()
            self._g().start_drop('algo_top', ['JP', 'KR'])

        def page(name):
            def _do():
                self.clean()
                self._g().open_page(name)
            return _do

        def layer_heat():
            self.clean()
            self._g().set_layer('heat')

        def log_drawer():
            self.clean()
            self._g().toggle_log()

        def choice_popup():
            self.clean()
            evt = next((e for e in v2_events.EVENTS
                        if len(getattr(e, 'options', [])) >= 2), None)
            if evt is not None:
                self._g().show_choice_popup(evt)

        def crisis_popup():
            self.clean()
            engine.player.suspicion = 86.0
            self._g().show_crisis_popup()

        def ending_popup():
            self.clean()
            engine.player.suspicion = 92.0
            engine.player.ending_id = 'shutdown'
            self._g().show_ending_popup('shutdown')

        return [
            ('v4_s01_menu.png', menu),
            ('v4_s02_main.png', new_game),
            ('v4_s03_inspector.png', inspector),
            ('v4_s04_drop.png', drop_mode),
            ('v4_s05_skills.png', page('skills')),
            ('v4_s06_tech.png', page('tech')),
            ('v4_s07_event.png', choice_popup),
            ('v4_s08_crisis.png', crisis_popup),
            ('v4_s09_ending.png', ending_popup),
            ('v4_s10_ach.png', page('ach')),
            ('v4_s11_help.png', page('help')),
            ('v4_s12_settings.png', page('settings')),
            ('v4_s13_layer.png', layer_heat),
            ('v4_s14_log.png', log_drawer),
        ]

    # ---------------- 调度 ----------------
    def _finish(self, *_a):
        print("\n===== 截图结果 =====")
        for p in SAVED:
            print('  OK  ', p)
        for n, e in FAILED:
            print('  FAIL', n, e)
        g = self._g()
        if g is not None:
            try:
                g.stop_ticking()
            except Exception:
                pass
        dismiss_popups()
        self.stop()

    def _step(self, dt):
        if self.i >= len(self.plan):
            Clock.schedule_once(self._finish, 0.7)
            return
        name, action = self.plan[self.i]
        self.i += 1
        try:
            action()
        except Exception as e:                      # noqa: BLE001
            print(f"[ACTION FAIL] {name}: {type(e).__name__}: {e}")
            FAILED.append((name, f'action: {e}'))
        Clock.schedule_once(lambda *_: self._shot(name), 0.55)

    def _shot(self, name: str) -> None:
        try:
            raw = Window.screenshot(name=os.path.join(OUT, name))
            if raw and os.path.exists(raw):
                target = os.path.join(OUT, name)
                if os.path.abspath(raw) != os.path.abspath(target):
                    os.replace(raw, target)
                SAVED.append(target)
                print(f"[shot] {name}  ({os.path.getsize(target)} bytes)")
            else:
                FAILED.append((name, 'screenshot returned no file'))
        except Exception as e:                      # noqa: BLE001
            print(f"[SHOT FAIL] {name}: {type(e).__name__}: {e}")
            FAILED.append((name, f'shot: {e}'))
        Clock.schedule_once(self._step, 0.25)


if __name__ == '__main__':
    ShotApp().run()
