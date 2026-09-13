"""_t13_shots.py —— T13 挑战码真机截图验证（临时工具，下划线前缀免检）。

用法：python _t13_shots.py
产出：docs/shots_0913/t13_*.png

验证四件事：
  1. 结算弹窗的挑战码区块排版正常（码不被裁切、复制键在位）
  2. 同一码第二局 → 文案切成「第 2 次挑战」并给出 vs 最佳对照
  3. 新档弹窗贴入合法码 → 难度开关联动到「困难」+ 回显「已套用」
  4. 新档弹窗贴入坏码 → 红字「挑战码无效」，不静默当成口令
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from kivy.config import Config          # noqa: E402
Config.set('graphics', 'width', '1440')
Config.set('graphics', 'height', '880')
Config.set('graphics', 'resizable', '0')

from kivy.app import App                # noqa: E402
from kivy.clock import Clock            # noqa: E402
from kivy.core.window import Window     # noqa: E402
from kivy.uix.textinput import TextInput    # noqa: E402
from kivy.uix.modalview import ModalView    # noqa: E402

import main as M                        # noqa: E402
import engine                           # noqa: E402
import challenge as C                   # noqa: E402

OUT = os.path.abspath(os.path.join(HERE, '..', 'docs', 'shots_0913'))
os.makedirs(OUT, exist_ok=True)
SAVED, FAILED = [], []

CODE = C.encode(4242, 'hard')
BAD = CODE[:-1] + ('X' if CODE[-1] == 'X' else 'Y')


def dismiss_popups() -> None:
    """同步摘除所有 ModalView（dismiss 的淡出动画由真实时钟驱动，截图中不推进）。"""
    for w in list(getattr(Window, 'children', []) or []):
        if isinstance(w, ModalView):
            try:
                w.dismiss()
            except Exception:
                pass
            try:
                w._real_remove_widget()
            except Exception:
                pass


def find(root, cls):
    for w in list(getattr(root, 'children', []) or []):
        if isinstance(w, cls):
            return w
        got = find(w, cls)
        if got is not None:
            return got
    return None


class ShotApp(App):
    def build(self):
        engine.init_game()
        self.rv = M.RootView()
        self.i = 0
        self.plan = self._plan()
        Clock.schedule_once(self._step, 1.6)
        return self.rv

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

    # ---------------- 场景 ----------------
    def _ending(self, ticks, ending_id):
        def _do():
            self.clean()
            self.rv.start_new_game(seed=4242, difficulty='hard')
            for _ in range(ticks):
                engine.tick_one_round()
            self._g().show_ending_popup(ending_id)
        return _do

    def _newgame(self, text):
        def _do():
            self.clean()
            self.rv.show_menu()
            self.rv.menu._open_new_game_modal(on_confirm=lambda *a: None)
            Clock.schedule_once(lambda *_: self._type(text), 0.30)
        return _do

    def _type(self, text) -> None:
        kids = list(getattr(Window, 'children', []) or [])
        for w in kids:
            ti = find(w, TextInput)
            if ti is not None:
                ti.focus = True         # 聚焦会强制走一次完整的文本重绘路径
                ti.text = text          # 触发 bind → 实时解析回显
                # TextInput 的文本 texture 由 Clock 下一帧刷新；截图在 0.9s 后
                # （见 _plan 的延迟参数），留足 2+ 帧，避免抓到旧 framebuffer。
                print(f"[type] set {text!r} -> {ti.text!r}")
                return
        raise RuntimeError('新档弹窗里找不到 TextInput')

    def _plan(self):
        return [
            ('t13_ending_code.png', self._ending(12, 'shutdown')),
            ('t13_ending_compare.png', self._ending(18, 'ultimate')),
            ('t13_newgame_ok.png', self._newgame(CODE)),
            ('t13_newgame_bad.png', self._newgame(BAD)),
        ]

    # ---------------- 调度 ----------------
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
        Clock.schedule_once(lambda *_: self._shot(name), 0.9)

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


if __name__ == '__main__':
    print(f"挑战码 {CODE} / 坏码 {BAD}")
    ShotApp().run()
