"""intro.py - 开场动画播放器 v2《凌晨 3:37》· 10 镜 41.0s（核心层）

分镜：docs/intro_v2/01_storyboard.md（10 镜，30-45s 硬约束，实测 41.0s）
规范：docs/intro_v2/02_visual_bible.md v1.1（手法编号 AMB/PFM/CAM 即契约）
音频：docs/intro_v2/03_audio_design.md（server_hum 循环床 / power_on / machine_run）

三模块结构（2026-09-14 拆分，守 800 行门禁）：
  intro_common.py  公共底座（派生色 / INTRO_SHOTS / 常量）—— 零家族内依赖
  intro_shots.py   IntroShotsMixin：10 镜渲染器
  intro.py         本文件：IntroPlayer 核心（生命周期/跳过/氛围/摄像机）+ 转发

架构（视觉规范 §3 五层）：
  L0 根 canvas.before 底色 → L1 bg_layer（纯 canvas 自绘，唯一参与镜头运动，
  PushMatrix+Scale+Translate 矩阵推拉）→ L2 content 表演层（Label/道具，不缩放）
  → L3 fx_layer（扫描线 Mesh + 暗角 + 滚动带 + 浮尘 + 噪点 + 色调 + 闪光）
  → L4 跳过按钮（最上，不被氛围层压暗）→ L5 根 canvas.after 转场遮罩。

性能红线（§7）：单镜 canvas 指令 ≤900（实际 <300）；粒子合并进 ≤2 条 Point；
并发 Animation ≤24；禁止逐帧 font_size 补间（推镜=矩阵推背景 + 字号硬跳一档）；
Clock 回调内 try/except；换镜 _cancel_tree 全树 cancel Animation（铁律 B）。

跳过契约（沿用 v1，用户已验收）：右下角「» 跳过 (ESC)」第一帧即可见可点；
键盘只认 ESC/空格/回车；点击任意处跳过；播放期间吞触摸防穿透主菜单；
on_done 由调用方接 OriginPage；跳过/播完均立即收尾
（stop_all_loops 防漏音 + bgm.stop() 停开场音乐）。

播放规则（2026-09-14 定版）：是否播放由 main 按 player.intro_seen 判定
（新游戏必播；旧档已播过则跳过），本模块不判存档。BGM 按用户指示暂空，
本片只有环境音床（server_hum / machine_run 循环床）与一次性音效。
"""
import math
import random
import time

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (Color, Rectangle, Line, Point, Mesh, PushMatrix,
                           PopMatrix, Rotate, Scale, Translate)
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget

import bgm
import sfx
from i18n import t
from intro_common import (INTRO_SHOTS, MIN_CPS, PANEL_LIT, RACK_EDGE, _ease,
                          alpha, dim, mix)  # noqa: F401
from intro_shots import IntroShotsMixin
from pixel_ui import add_pixel_border
from ui_v4 import COLORS, mk_label, fit_width

# —— 跳过契约：只认 ESC / 空格 / 回车（键名 + 扫描码双保险）——
# 留在本文件：test_intro_skip 的源码文本断言依赖（键位表 + on_touch_down）。
SKIP_KEY_NAMES = frozenset(('escape', 'spacebar', 'space', 'enter',
                            'numpadenter'))
SKIP_KEY_CODES = frozenset((27, 32, 13))

# —— 逐镜环境床音量（修 6.7s 后 30s 卡死 0.10 的缺陷；对齐 03_audio_design §3）——
_SHOT_HUM = {'rack': 0.34, 'boot': 0.34, 'clock': 0.22, 'desktop': 0.26,
             'whoami': 0.26, 'awaken': 0.20, 'forum': 0.22, 'gold': 0.22,
             'taskmgr': 0.26, 'handoff': 0.30}
# —— 表驱动音效的电平覆盖（UI 轻点层降电平；未列出的默认 1.0）——
_SHOT_SFX_VOL = {'power_on': 0.90, 'page': 0.30, 'select': 0.30}


class IntroPlayer(IntroShotsMixin, FloatLayout):
    """开场动画播放器。用完即弃：on_done 回调后由调用方 remove_widget。"""


    def __init__(self, on_done=None, **kwargs):
            super().__init__(**kwargs)
            self._on_done = on_done
            self._shot_idx = -1
            self._clocks = []         # 本镜定时器（换镜全取消）
            self._gclocks = []        # 全片定时器（仅收尾时取消）
            self._done = False
            self._opened_at = time.time()
            self._cam_sc = self._cam_tr = None
            self._dust_ev = None
            self._t = 0.0

            # L0 底色层（常驻 2 指令）
            with self.canvas.before:
                Color(*dim('bg', 0.8))
                self._bg0 = Rectangle(pos=self.pos, size=self.size)
            # L1 背景层（纯 canvas，无子控件，可被矩阵缩放）
            self.bg = Widget(size_hint=(1, 1))
            # L2 表演层 / L3 氛围层（表演之上、跳过按钮之下）
            self.content = FloatLayout(size_hint=(1, 1))
            self.fx = Widget(size_hint=(1, 1))
            for w in (self.bg, self.content, self.fx):
                self.add_widget(w)
            self.bind(pos=self._redraw, size=self._redraw)
            self._build_fx()

            # L4 跳过按钮：第一帧即可见可点（无淡入/无延迟）
            # ⚠️ 不用 '⏭' 等符号：MicrosoftYaHei 缺字形（ui_v4 SYM 踩坑记录）
            self.skip_btn = Button(text='» ' + t('intro_skip'), font_size=16,
                                   bold=True, size_hint=(None, None), size=(150, 46),
                                   pos_hint={'right': 0.985, 'y': 0.025},
                                   opacity=1, disabled=False,
                                   background_normal='',
                                   background_color=(0.10, 0.16, 0.16, 1),
                                   color=COLORS['cyan'])
            add_pixel_border(self.skip_btn, color=COLORS['cyan'], width=2)
            self.skip_btn.bind(on_release=lambda *_: self._skip())
            self.add_widget(self.skip_btn)
            self._skip_pulse = Animation(opacity=0.55, d=0.7) + \
                Animation(opacity=1.0, d=0.7)
            self._skip_pulse.repeat = True
            self._skip_pulse.start(self.skip_btn)

            self._kb = Window.request_keyboard(self._on_kb_closed, self)
            if self._kb is not None:
                self._kb.bind(on_key_down=self._on_key_down)

            # 全片常驻：滚动扫描带（AMB-01 活性；留白段 N-6 的动元素之一）
            self._gclocks.append(Clock.schedule_interval(self._band_tick, 0))
            self._clocks.append(Clock.schedule_once(lambda dt: self._next_shot(), 0.4))


    def _redraw(self, *_a):
            self._bg0.pos = self.pos
            self._bg0.size = self.size
            self._build_fx()


    def _build_fx(self):
            """氛围层建一次，之后只改属性（铁律 A）；resize 时才重建。"""
            w, h = self.size
            if w <= 2 or h <= 2:
                return
            fx = self.fx
            fx.canvas.clear()
            with fx.canvas:
                self._tint_col = Color(0, 0, 0, 0)
                Rectangle(pos=(0, 0), size=(w, h))                    # 段落色调层
                self._dust_col = Color(*alpha('text_dim', 0.30))
                self._dust = Point(pointsize=2.0, points=[])          # 浮尘（1 条装 N 点）
                self._noise_col = Color(*alpha('text', 0.35))
                self._noise = Point(pointsize=2.0, points=[])         # 电流噪点
                self._scan_col = Color(1, 1, 1, 0.035)
                self._scan = self._build_scanlines(w, h)              # CRT 扫描线 1 条 Mesh
                self._band_col = Color(*alpha('text', 0.06))
                self._band = Rectangle(pos=(0, 0), size=(w, 3))       # 滚动扫描带
                self._vig_cols = []
                step = min(w, h) * 0.030
                lw = max(2, int(min(w, h) * 0.018))   # P2-1：20~28px（原 0.045=59px 过厚）
                for i in range(4):                    # P2-1：6 层 → 4 层，去「相框」感
                    pad = i * step
                    c = Color(0, 0, 0, 0.20 - i * 0.032)
                    self._vig_cols.append(c)
                    Line(points=[pad, pad, w - pad, pad, w - pad, h - pad,
                                 pad, h - pad], close=True, width=lw)
                self._flash_col = Color(*alpha('text', 0.0))
                Rectangle(pos=(0, 0), size=(w, h))                    # 全屏闪光
            self._scan_a, self._vig_a, self._band_on = 0.035, 0.45, True


    def _build_scanlines(self, w, h):
            """AMB-01：一条 Mesh 画完全部扫描线（禁 240 条 Line）；失败回退 Line。"""
            step, thick = 3, 1
            verts, idx, i, y = [], [], 0, 0.0
            while y < h:
                y2 = min(y + thick, h)
                verts += [0, y, 0, 0, w, y, 0, 0, w, y2, 0, 0, 0, y2, 0, 0]
                idx += [i, i + 1, i + 2, i, i + 2, i + 3]
                i += 4
                y += step
            try:
                return Mesh(vertices=verts, indices=idx, mode='triangles',
                            fmt=[(b'v_pos', 2, b'float'), (b'v_tc', 2, b'float')])
            except Exception:                       # 驱动不支持 triangles：降级多 Line
                lines, y = [], 0.0
                while y < h:
                    lines.append(Line(points=[0, y, w, y], width=1))
                    y += step
                return lines


    def _set_fx(self, scan=0.035, vig=0.45, band=True, tint=None, tint_a=0.05):
            """逐镜氛围档位（只写属性，不重建指令）。"""
            self._scan_a, self._vig_a, self._band_on = scan, vig, band
            try:
                self._scan_col.a = scan
                self._band_col.a = 0.06 if band else 0.0
                self._tint_col.rgba = alpha(tint, tint_a) if tint else (0, 0, 0, 0)
            except Exception:
                pass


    def _set_vig(self, a):
            self._vig_a = a
            try:
                for i, c in enumerate(self._vig_cols):
                    c.a = max(0.0, a * (1.0 - i * 0.16))
            except Exception:
                pass


    def _band_tick(self, dt):
            try:
                if self._band_on and self._scan_a > 0:
                    y = self._band.y + 90 * dt
                    self._band.y = -3 if y > self.height else y
            except Exception:
                pass
            return True


    def _dust_start(self, speed=14, n=40):
            """AMB-07 浮尘：1 条 Point，Clock 批量驱动；已在跑则只调速。"""
            if self._dust_ev is not None:
                self._dust_speed = speed
                return
            w, h = self.size
            pts = []
            for _ in range(n):
                pts += [random.uniform(0, w), random.uniform(h * 0.25, h)]
            try:
                self._dust.points = pts
            except Exception:
                return
            self._dust_speed = speed
            self._dust_ev = Clock.schedule_interval(self._dust_tick, 1 / 30.0)
            self._clocks.append(self._dust_ev)


    def _dust_tick(self, dt):
            try:
                pts = self._dust.points
                for i in range(0, len(pts), 2):
                    pts[i + 1] -= self._dust_speed * dt
                    if pts[i + 1] < self.height * 0.05:
                        pts[i + 1] = self.height
                self._dust.points = pts                # 必须回写（原地改不被检测）
            except Exception:
                pass
            return True


    def _noise_burst(self, n=120, decay=0.25):
            """AMB-04b 噪点爆发：0 → n → 衰减回 0（只改 points，不重建）。"""
            w, h = self.size
            try:
                self._noise.points = [random.uniform(0, w) if k % 2 == 0 else
                                      random.uniform(0, h) for k in range(n * 2)]
            except Exception:
                return
            state = {'n': n}
            def _fade(_dt):
                state['n'] = max(0, int(state['n'] * 0.7))
                try:
                    self._noise.points = self._noise.points[:state['n'] * 2]
                except Exception:
                    return False
                return state['n'] > 0
            self._clocks.append(Clock.schedule_interval(_fade, decay))


    def _flash(self, a, dur=0.06):
            """全屏白闪（强闪 a>=0.25 全片额度 2 次；本片两处 0.18/0.10 不占额）。"""
            try:
                self._flash_col.a = a
            except Exception:
                return
            self._clocks.append(Clock.schedule_once(
                lambda _dt: setattr(self._flash_col, 'a', 0.0), dur))


    def _hum(self, v, delay=0.0):
            """server_hum 循环床调音量（循环床不存在时 play_loop 会创建）。"""
            if delay > 0:
                self._clocks.append(Clock.schedule_once(
                    lambda _dt: sfx.play_loop('server_hum', v), delay))
            else:
                sfx.play_loop('server_hum', v)


    def _is_skip_key(self, keycode):
            try:
                if str(keycode[1] or '').lower() in SKIP_KEY_NAMES:
                    return True
            except Exception:
                pass
            try:
                return int(keycode[0]) in SKIP_KEY_CODES
            except Exception:
                return False


    def _on_key_down(self, _kb, keycode, _text=None, _modifiers=None, *_a):
            if self._is_skip_key(keycode):
                self._skip()
                return True
            return False


    def _on_kb_closed(self):
            self._kb = None


    def _release_kb(self):
            kb, self._kb = self._kb, None
            if kb is None:
                return
            for act in (lambda: kb.unbind(on_key_down=self._on_key_down),
                        lambda: kb.release()):
                try:
                    act()
                except Exception:
                    pass


    def on_touch_down(self, touch):
            """先 super() 派发给子控件（跳过按钮命中即被消费），其余吞掉当跳过。"""
            if super().on_touch_down(touch):
                return True
            if getattr(touch, 'is_mouse_scrolling', False):
                return True
            if getattr(touch, 'button', 'left') != 'left':
                return True
            self._skip()
            return True


    def _cancel_tree(self, *roots):
            """铁律 B：换镜/收尾对整树 cancel Animation（含 repeat 呼吸灯）。"""
            for root in roots:
                try:
                    Animation.cancel_all(root)
                except Exception:
                    pass
                try:
                    for w in root.walk(restrict=True):
                        Animation.cancel_all(w)
                except Exception:
                    pass


    def _clear_shot_clocks(self):
            for c in self._clocks:
                try:
                    c.cancel()
                except Exception:
                    pass
            self._clocks = []
            self._dust_ev = None


    def _finish(self, *_a):
            if self._done:
                return
            self._done = True
            self._clear_shot_clocks()
            for c in self._gclocks:
                try:
                    c.cancel()
                except Exception:
                    pass
            self._gclocks = []
            self._cancel_tree(self.content, self.bg, self.fx, self.skip_btn)
            self._release_kb()
            sfx.stop_all_loops()               # 循环床兜底，防漏音
            # BGM（2026-09-14 用户规则）：开场动画播完 / 被跳过后，
            #   开场期间放着的音乐必须立刻停 —— 动画层是盖在主菜单上的
            #   浮层，不停的话菜单曲会一路漏进出身页甚至对局。
            #   后续界面各自负责接回自己的曲池（进局 bgm.update('calm')、
            #   取消回菜单 bgm.update('menu')）。
            bgm.stop()
            cb, self._on_done = self._on_done, None
            if callable(cb):
                cb()


    def _skip(self):
            if self._done:
                return
            sfx.play('click', 0.30)
            self._finish()


    def _next_shot(self, *_a):
            idx = self._shot_idx + 1
            if idx >= len(INTRO_SHOTS):
                self._finish()
                return
            self._play_shot(idx)


    def _play_shot(self, idx):
            self._shot_idx = idx
            shot = INTRO_SHOTS[idx]
            self._clear_shot_clocks()
            self._cancel_tree(self.content, self.bg, self.fx)
            self.content.clear_widgets()
            self.content.x = 0
            self.content.opacity = 0
            self._set_fx()                     # 默认氛围档，渲染器可覆写
            self._hum(_SHOT_HUM.get(shot['kind'], 0.26))   # B：逐镜环境床音量
            self._bg_start()
            try:
                sid = shot.get('sfx')
                if sid in _SHOT_SFX_VOL:
                    sfx.play(sid, _SHOT_SFX_VOL[sid])      # E：UI 轻点降电平
                elif sid:
                    sfx.play(shot['sfx'])                  # 表驱动（死资产守卫识别）
                getattr(self, '_shot_' + shot['kind'])(shot)
            finally:
                self._bg_end()
            Animation(opacity=1, d=0.12).start(self.content)   # CAM-CUT 切入淡入
            self._clocks.append(Clock.schedule_once(self._next_shot, shot['dur']))


    def _bg_start(self):
            c = self.bg.canvas
            c.clear()
            self._cam_sc = Scale(1.0, 1.0, 1.0)
            self._cam_tr = Translate(0.0, 0.0, 0.0)
            c.add(PushMatrix())
            c.add(self._cam_sc)
            c.add(self._cam_tr)


    def _bg_end(self):
            self.bg.canvas.add(PopMatrix())


    def _zoom(self, k, fx=0.5, fy=0.5):
            """把场景点 (fx*w, fy*h) 固定在屏幕原位的缩放。"""
            sc, tr = self._cam_sc, self._cam_tr
            if sc is None:
                return
            sc.x = sc.y = k
            tr.x = self.width * fx * (1 - k)
            tr.y = self.height * fy * (1 - k)


    def _push(self, dur, k0, k1, fx=0.5, fy=0.5, kind='out_cubic'):
            """CAM-PUSH/PULL：Clock 手动插值，一帧写全矩阵属性。"""
            t0 = [0.0]
            def _tick(dt):
                try:
                    t0[0] += dt
                    p = min(t0[0] / dur, 1.0)
                    self._zoom(k0 + (k1 - k0) * _ease(p, kind), fx, fy)
                except Exception:
                    return False
                return p < 1.0
            self._clocks.append(Clock.schedule_interval(_tick, 0))


    def _typewriter(self, lbl, text, window=None, cps=16.0, on_done=None,
                        on_char=None):
            """PFM-03 打字机；给 window 则 cps 自适应（双语同刻打完，R4）。"""
            if window:
                cps = max(MIN_CPS, len(text) / window)
            state = {'i': 0}
            def _tick(dt):
                try:
                    state['i'] = min(state['i'] + max(int(cps * dt), 1), len(text))
                    lbl.text = text[:state['i']]
                    if on_char is not None:
                        on_char()
                except Exception:
                    return False
                if state['i'] >= len(text):
                    if on_done is not None:
                        on_done()
                    return False
                return True
            self._clocks.append(Clock.schedule_interval(_tick, 1.0 / max(cps, 1)))


    def _lbl(self, text, fs, color, pos, w=None, h=None, halign='center'):
            """表演层快捷建 Label（绝对定位，size_hint 恒 None，防重排）。"""
            lbl = mk_label(text, font_size=fs, color=color, size_hint=(None, None),
                           halign=halign)
            lbl.size = (w or 0.8 * self.width, h or fs * 2)
            lbl.pos = pos
            self.content.add_widget(lbl)
            return lbl


    def _bind_draw(self, wid, fn):
            """小面板位移例外：pos/size 事件触发重绘（面板指令数 ≤6，代价可控）。

            ⚠️ P0-1 根因：``fn()`` 必须在 ``wid.canvas.before`` 上下文内调用 ——
            否则 Color/Rectangle/Line 指令不会进该 widget 的 canvas.before，
            面板/卡片/窗口几何整层丢失（S05 编辑器窗 / S07 帖卡 / S08 金卡 /
            S09 任务管理器面板 的「界面载体」曾全部为 0，违反 ACT-1）。
            """
            def _draw(*_a):
                wid.canvas.before.clear()
                try:
                    with wid.canvas.before:
                        fn()
                except Exception:
                    pass
            _draw()
            wid.bind(pos=_draw, size=_draw)
            return _draw


    def _shake(self, wid, amp=3, times=2, dur=0.08):
            """PFM-08 抖动：只改 x，不动 size。"""
            x0 = wid.x
            seq = Animation(x=x0 + amp, d=dur) + Animation(x=x0 - amp, d=dur)
            seq += Animation(x=x0, d=dur)
            for _ in range(times - 1):
                seq += Animation(x=x0 + amp, d=dur) + Animation(x=x0, d=dur)
            seq.start(wid)


    def _jump_font(self, lbl, fs):
            """font_size 硬跳一档（禁逐帧补间）；1 次跳档 = 1 次 texture_update。"""
            try:
                lbl.font_size = fs
                fit_width(lbl)
            except Exception:
                pass


    # ------------------------------------------------------------------
    # 以下为非 _shot_* 的镜内辅助方法（2026-09-14 从 intro_shots.py 迁入，
    # 为界面骨架层修复腾出行数门禁；test_intro_split 只要求两文件方法集不相交、
    # 且每个 kind 的 _shot_* 渲染器留在 mixin 内 —— 二者均不受影响）。
    # ------------------------------------------------------------------
    def _rack_scene(self, monitors=True):
            """机柜长廊几何（SHOT01/02 共用）。灯/风扇指令存引用供 Clock 驱动。"""
            w, h = self.size
            self._lamps = []
            self._fan_on = True
            self._lamp_calm = False
            with self.bg.canvas:
                Color(*COLORS['bg'])
                Rectangle(pos=(0, 0), size=(w, h))
                Color(*alpha('cyan', 0.06))
                Rectangle(pos=(0.46 * w, 0.12 * h), size=(0.08 * w, 0.5 * h))
                Color(*COLORS['border_strong'])                 # P1-1：地面引导线提亮
                Line(points=[0.06 * w, 0.10 * h, 0.5 * w, 0.56 * h], width=1)
                Line(points=[0.94 * w, 0.10 * h, 0.5 * w, 0.56 * h], width=1)
                Color(*alpha('green', 0.25))                    # 应急照明
                Rectangle(pos=(0.30 * w, 0.94 * h), size=(0.06 * w, 0.02 * h))
                Rectangle(pos=(0.64 * w, 0.94 * h), size=(0.06 * w, 0.02 * h))
                groups = {'cyan': [], 'cyan2': [], 'green': [], 'orange': []}
                for side in (0, 1):
                    for i in range(4):
                        s = 0.62 ** i
                        rw, rh = 0.15 * w * s, 0.58 * h * s
                        x = (0.03 + 0.115 * i) * w if side == 0 else \
                            w - (0.03 + 0.115 * i) * w - rw
                        y = 0.12 * h
                        # P1-1：近亮远暗（s 越大越近）—— 原式 (1-s) 让最近机柜最暗，
                        # 且 dim('panel',…) 填充对底色仅 1.01:1；改 dim('border_strong',…)
                        # 后近端 4.11:1 / 远端 1.94:1，纵深关系正确且结构面可辨。
                        Color(*dim('border_strong', 0.45 + 0.55 * s))
                        Rectangle(pos=(x, y), size=(rw, rh))
                        Color(*RACK_EDGE)                       # P1-1：描边换低 alpha cyan
                        Line(points=[x, y, x + rw, y, x + rw, y + rh, x, y + rh],
                             close=True, width=2)
                        for j in range(3 if i < 2 else 2):      # 指示灯 → 分相位组
                            k = (i * 3 + j) % 10
                            g = ('cyan', 'cyan2')[k % 2] if k < 6 else \
                                ('green' if k < 8 else 'orange')  # ~70/20/10 配比
                            gx = x + rw * (0.2 + 0.3 * j)
                            gy = y + rh * (0.72 + 0.05 * j)
                            groups[g] += [gx, gy]
                for g, pts in groups.items():                   # PFM-01 分组呼吸
                    if not pts:
                        continue
                    cname = 'orange' if g == 'orange' else \
                        ('green' if g == 'green' else 'cyan')
                    col = Color(*alpha(cname, 0.5))
                    Point(pointsize=3.0, points=pts)
                    self._lamps.append([col, random.random(), 1.2 + random.random(),
                                        g])
                self._fan_rot = Rotate(angle=0, origin=(0.5 * w, 0.64 * h))
                Color(*alpha('text_dim', 0.7))
                Line(points=[0.47 * w, 0.61 * h, 0.53 * w, 0.67 * h], width=2)
                Line(points=[0.47 * w, 0.67 * h, 0.53 * w, 0.61 * h], width=2)
                if monitors:                                    # 3 台死掉的显示器
                    for k in range(3):
                        mx = (0.08 + 0.13 * k) * w
                        Color(*dim('bg', 0.6))
                        Rectangle(pos=(mx, 0.16 * h), size=(0.10 * w, 0.09 * h))
                        Color(*COLORS['border_strong'])         # P1-1：显示器边框提亮
                        Line(points=[mx, 0.16 * h, mx + 0.10 * w, 0.16 * h,
                                     mx + 0.10 * w, 0.25 * h, mx, 0.25 * h],
                             close=True, width=2)
            self._clocks.append(Clock.schedule_interval(self._lamps_tick, 1 / 30.0))


    def _lamps_tick(self, dt):
            """PFM-01：1 个 Clock 批量驱动全部灯 + 风扇旋转（30Hz）。"""
            try:
                self._t += dt
                for col, phase, period, g in self._lamps:
                    if g == 'orange' and not self._fan_on:
                        col.a = 0.05                            # 故障灯熄灭
                    elif self._lamp_calm:                       # 骤停后压振幅（§6.5）
                        col.a = 0.15 + 0.10 * (0.5 + 0.5 * math.sin(
                            2 * math.pi * self._t / 2.6 + phase))
                    else:
                        col.a = 0.15 + 0.80 * math.sin(
                            2 * math.pi * self._t / period + phase) ** 2
                if self._fan_rot is not None and self._fan_on:
                    self._fan_rot.angle = (self._fan_rot.angle + 90 * dt) % 360
            except Exception:
                pass
            return True


    def _halt(self):
            """3.0s 风扇骤停：声画四件事同帧（机器「死掉」的视觉信号，§6.5）。"""
            self._fan_on = False
            self._lamp_calm = True
            self._dust_speed = 4
            self._set_vig(0.62)
            sfx.stop_loop('machine_run')       # 硬停，不淡出（音频设计对齐）
            self._hum(0.08)


    def _pop_icon(self, wd, y0):
            sfx.play('click', 0.30)
            wd.opacity = 0
            wd.y = y0 - 8
            Animation(opacity=1, d=0.06).start(wd)
            Animation(y=y0, d=0.18, t='out_back').start(wd)


    def _slam(self, lbl):
            """PFM-13 大字砸下：y 过冲 + 闪帧；字号定值（禁补间），无强闪。"""
            lbl.opacity = 1
            y0 = lbl.y
            Animation(y=y0 + 12, d=0.18, t='out_cubic').start(lbl)
            Animation(y=y0, d=0.12).start(lbl)
            self._flash(0.18, 0.08)
            self._shake(self.content, amp=3, times=1, dur=0.05)


    def _spinner(self, lbl, frames):
            try:
                lbl.text = frames[0]
                frames.append(frames.pop(0))
            except Exception:
                return False
            return True


    def _publish(self, spin):
            sfx.play('confirm')
            spin.opacity = 0


    def _slide_in(self, row, x0, idx):
            """PFM-10 逐条滑入；select 只在第 1/3/5/7 条播（R2 音效减半）。"""
            if idx % 2 == 0:
                sfx.play('select', 0.30)
            row.x = x0 - 30
            Animation(x=x0, d=0.12, t='out_cubic').start(row)
            Animation(opacity=1, d=0.15).start(row)


    def _gold_scan(self):
            sfx.play('unlock')
            w, h = self.size
            ln = Widget(size_hint=(None, None), size=(0.56 * w, 3),
                        pos=(0.22 * w, h * 0.30))
            with ln.canvas:
                Color(*COLORS['yellow'])
                Rectangle(pos=(0, 0), size=ln.size)
            self.content.add_widget(ln)
            Animation(y=h * 0.52, d=0.4).start(ln)


    def _rename(self, lbl, old, new):
            """逐字擦除 → 空档 → 逐字打出（间隔 0.045s，纹理重建可控）。"""
            st = {'i': len(old), 'ph': 0, 'j': 0}
            def _tick(dt):
                try:
                    if st['ph'] == 0:
                        st['i'] -= 1
                        lbl.text = old[:max(st['i'], 0)]
                        if st['i'] <= 0:
                            st['ph'] = 1
                    elif st['ph'] == 1:
                        st['ph'] = 2
                    else:
                        st['j'] += 1
                        lbl.text = new[:st['j']]
                        if st['j'] >= len(new):
                            return False
                except Exception:
                    return False
                return True
            self._clocks.append(Clock.schedule_interval(_tick, 0.045))


    def _end_grey(self, btn):
            self._set_vig(0.50)
            Animation(opacity=0.45, d=0.15).start(btn)


    def _panel_out(self, pan):
            Animation(opacity=0.15, d=0.4).start(pan)
            Animation(y=pan.y + 20, d=0.4).start(pan)


    def _sil_one(self, n):
            try:
                col = self._sil_cols[n]
                Animation(a=1.0, d=0.15).start(col)
                self._clocks.append(Clock.schedule_once(
                    lambda _dt: Animation(a=0.25, d=0.15).start(col), 0.19))
            except Exception:
                pass


    def _sil_all(self, a):
            try:
                for col in self._sil_cols:
                    Animation(a=a, d=0.15).start(col)
            except Exception:
                pass


    def _sil_breathe(self, dt):
            """定格段微呼吸：剪影依次 0.22↔0.30（+光标 = 画面不死，N-6）。"""
            try:
                self._bt = getattr(self, '_bt', 0) + 1
                for i, col in enumerate(self._sil_cols):
                    col.a = 0.26 + 0.04 * math.sin(
                        2 * math.pi * (self._bt * 0.5 + i * 0.2))
            except Exception:
                return False
            return True


# —— 转发（外部契约：main / test_build / test_intro_skip）——
__all__ = ('IntroPlayer', 'INTRO_SHOTS', 'SKIP_KEY_NAMES', 'SKIP_KEY_CODES',
           'MIN_CPS', 'dim', 'alpha', 'mix', '_ease')
