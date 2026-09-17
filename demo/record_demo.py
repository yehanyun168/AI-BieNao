"""record_demo.py —— 真·动态录屏：实时跑故事板，同时用 ffmpeg gdigrab 抓游戏窗口。

与 capture_demo.py 的区别：
  * 不截图，而是让游戏按 shots.json 的每镜时长真实停留，全程实时渲染；
  * 用 ffmpeg gdigrab 录整屏，同时在进程内用 ctypes 取窗口客户区矩形写入 JSON，
    供后期精确裁剪（避免 DPI/多窗口干扰）。
  * 开场动画（S01-S10）是真正播放的动效，不再是 10 张静帧。

用法（在 demo/ 目录下）：
    KIVY_NO_FILELOG=1 python record_demo.py
产出：
    video/out/_raw_capture.mp4   原始全屏录像
    video/out/_raw_rect.json     游戏窗口客户区矩形（x,y,w,h）
"""
import ctypes
import json
import os
import subprocess
import sys
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

# 进程 DPI 感知：让 GetClientRect 返回物理像素，与 gdigrab 抓屏坐标一致
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from kivy.config import Config                       # noqa: E402
Config.set('graphics', 'width', '1440')
Config.set('graphics', 'height', '880')
Config.set('graphics', 'resizable', '0')
Config.set('graphics', 'position', 'custom')
Config.set('graphics', 'left', '0')
Config.set('graphics', 'top', '0')

from kivy.app import App                             # noqa: E402
from kivy.clock import Clock                         # noqa: E402
from kivy.core.window import Window                  # noqa: E402

import main as M                                     # noqa: E402
import engine                                        # noqa: E402
import capture_demo as CD                            # noqa: E402  (复用动作方法)

OUT = os.path.normpath(os.path.join(HERE, '..', 'video', 'out'))
os.makedirs(OUT, exist_ok=True)
RAW = os.path.join(OUT, '_raw_capture.mp4')
RECT_JSON = os.path.join(OUT, '_raw_rect.json')

FF = r"C:\Users\tianm\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
if not os.path.exists(FF):
    FF = 'ffmpeg'

SHOTS_JSON = os.path.normpath(os.path.join(HERE, '..', 'video', 'shots.json'))
with open(SHOTS_JSON, encoding='utf-8') as f:
    _SHOTS = json.load(f)['shots']
_DUR = {s['id']: float(s['dur']) for s in _SHOTS}
TOTAL = sum(_DUR.values())
REC_SECONDS = int(round(TOTAL)) + 4          # 多录 4s 容错

# 故事板顺序（S11..S30，动作复用 capture_demo）
PLAN = [
    ('S11', None, 0.0),
    ('S12', 'add_origin', 0.0),
    ('S13', 'select_darknet', 0.0),
    ('S16', 'enter_game', 0.0),
    ('S14', 'skip_tut', 0.0),
    ('S15', 'susp', 0.0),
    ('S17', 'speed', 0.0),
    ('S18', 'push', 0.0),
    ('S19', 'algo', 0.0),
    ('S20', 'skills', 0.0),
    ('S21', 'tech', 0.0),
    ('S22', 'stealth', 0.0),
    ('S23', 'inspect', 0.0),
    ('S24', 'spread', 0.0),
    ('S25', 'threshold', 0.0),
    ('S26', 'ending', 0.0),
    ('S27', 'ending_65', 0.0),
    ('S28', 'ending_35', 0.0),
    ('S29', 'ending_00', 0.0),
    ('S30', 'back', 0.0),
]


def _find_window_rect():
    """找属于本进程的最大可见窗口，返回客户区屏幕矩形 (x, y, w, h)。

    按 PID 匹配而非窗口标题：Kivy 窗口标题可能被改/被吞，PID 永远可靠。
    """
    u32 = ctypes.windll.user32
    mypid = os.getpid()
    hits = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _l):
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != mypid or not u32.IsWindowVisible(hwnd):
            return True
        r = wintypes.RECT()
        u32.GetClientRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w > 200 and h > 200:
            pt = wintypes.POINT(0, 0)
            u32.ClientToScreen(hwnd, ctypes.byref(pt))
            n = u32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            hits.append({'title': buf.value, 'x': pt.x, 'y': pt.y, 'w': w, 'h': h})
        return True

    u32.EnumWindows(_cb, 0)
    # 取面积最大的那个（排除隐藏/辅助窗口）
    hits.sort(key=lambda d: d['w'] * d['h'], reverse=True)
    return hits[0] if hits else None


class RecordApp(CD.ShotApp):
    """继承 capture_demo 的全部动作方法，但改为「按镜时长停留 + 全屏录制」。"""

    def build(self):
        engine.init_game()
        CD.mute_game_bgm()              # 录制期只留音效，BGM 由后期统一配
        if '--probe' in sys.argv:
            # 只探测窗口矩形：开窗后取一次矩形即退出，用于裁剪已有录像
            Clock.schedule_once(lambda *_: self._probe_rect(0), 2.0)
            Clock.schedule_once(lambda *_: self.stop(), 10.0)   # 兜底退出
            return M.RootView()
        self.rv = M.RootView()
        self.plan = []
        self.i = 0
        self._phase = 'intro'
        self._intro = None
        self._origin_page = None
        self._darknet_card = None
        self._rec = None
        self._intro = CD.NonSkippingIntroPlayer(on_done=lambda *a: self._start_plan())
        self._intro.size_hint = (1, 1)
        self._intro.pos_hint = {'x': 0, 'y': 0}
        self.rv.add_widget(self._intro)
        Clock.schedule_once(self._spawn_recorder, 0.05)   # 与开场动画同时开录
        return self.rv

    def _spawn_recorder(self, *_a):
        cmd = [FF, '-hide_banner', '-loglevel', 'error', '-f', 'gdigrab',
               '-framerate', '30', '-i', 'desktop', '-t', str(REC_SECONDS),
               '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '20',
               '-pix_fmt', 'yuv420p', '-y', RAW]
        self._rec = subprocess.Popen(cmd)
        sys.stdout.write('[record] gdigrab 已启动，录制 %ds\n' % REC_SECONDS)
        sys.stdout.flush()
        # 窗口要等应用起来才存在，延后 2.5s 再取矩形，并多次重试
        Clock.schedule_once(lambda *_: self._probe_rect(0), 2.5)

    def _probe_rect(self, attempt):
        try:
            rect = _find_window_rect()
        except Exception as e:
            rect = None
            sys.stdout.write('[record] rect 异常: %s\n' % e)
        if rect:
            with open(RECT_JSON, 'w', encoding='utf-8') as f:
                json.dump(rect, f, ensure_ascii=False)
            sys.stdout.write('[record] window rect = %s\n' % rect)
            sys.stdout.flush()
            if '--probe' in sys.argv:
                Clock.schedule_once(lambda *_: self.stop(), 0.2)
            return
        if attempt < 12:
            Clock.schedule_once(lambda *_: self._probe_rect(attempt + 1), 0.5)
        else:
            sys.stdout.write('[record] WARN 未找到窗口矩形\n')
            sys.stdout.flush()

    def _start_plan(self):
        print('[record] intro done, 开始按故事板时长实时推进')
        self._phase = 'plan'
        if self._intro is not None:
            try:
                self.rv.remove_widget(self._intro)
            except Exception:
                pass
            self._intro = None
        self.plan = self._build_plan()
        self.i = 0
        try:
            g = self._g()
            if g is not None:
                g.stop_ticking()
        except Exception:
            pass
        Clock.schedule_once(self._step, 0.3)

    def _build_plan(self):
        # 每镜用 shots.json 的真实时长；动作复用 capture_demo
        acts = {
            'S11': None,
            'S12': self._add_origin,
            'S13': self._select_darknet,
            'S16': self._enter_game,
            'S14': self._skip_tut,
            'S15': self._susp,
            'S17': self._speed,
            'S18': self._push,
            'S19': self._algo,
            'S20': self._skills,
            'S21': self._tech,
            'S22': self._stealth,
            'S23': self._inspect,
            'S24': self._spread,
            'S25': self._threshold,
            'S26': lambda: self._ending(1.0),
            'S27': lambda: self._ending_scroll(0.65),
            'S28': lambda: self._ending_scroll(0.35),
            'S29': lambda: self._ending_scroll(0.0),
            'S30': self._back,
        }
        plan = []
        for sid, _name, _x in PLAN:
            plan.append((sid, acts.get(sid), _DUR.get(sid, 5.0)))
        return plan

    def _step(self, dt):
        if self.i >= len(self.plan):
            self._finish()
            return
        sid, action, dur = self.plan[self.i]
        self.i += 1
        if action is not None:
            try:
                action()
            except Exception as e:
                print('[action fail] %s: %s' % (sid, e))
        # 冻结游戏 tick：否则 8 秒停留期间状态会漂移、还会弹事件窗，
        # 画面与字幕对不上。UI 自身动效（Clock）不受影响，仍会动。
        try:
            g = self._g()
            if g is not None:
                g.stop_ticking()
        except Exception:
            pass
        print('[hold] %-4s %.1fs' % (sid, dur))
        Clock.schedule_once(self._step, dur)

    def _finish(self, *_a):
        print('[record] 故事板结束，停止录制')
        try:
            g = self._g()
            if g is not None:
                g.stop_ticking()
        except Exception:
            pass
        if self._rec is not None:
            try:
                self._rec.wait(timeout=8)
            except Exception:
                try:
                    self._rec.kill()
                except Exception:
                    pass
        print('[record] 录像：', RAW, '存在=', os.path.exists(RAW))
        self.stop()


if __name__ == '__main__':
    RecordApp().run()
