"""intro_shots.py - 开场动画 10 镜渲染器（IntroShotsMixin）

从 intro.py 拆出（2026-09-14）。Mixin：由 intro.IntroPlayer 继承；
self 上的核心设施（_lbl/_push/_set_fx/_hum/_typewriter/_clocks 等）由宿主提供。
⚠️ 禁止 import intro（防循环导入，test_intro_split 守卫）。
分镜契约见 docs/intro_v2/01_storyboard.md（10 镜 41.0s）。
"""
import random

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Line, Point
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget

import sfx
from i18n import t
from intro_common import PANEL_LIT, alpha, dim, mix
from pixel_ui import COLORS
from ui_v4 import mk_label


class IntroShotsMixin(object):
    """10 镜渲染器（_shot_*）+ 镜内专用小工具。

    非 _shot_* 的辅助方法（_rack_scene/_lamps_tick/_halt/_pop_icon/_slam/
    _spinner/_publish/_slide_in/_gold_scan/_rename/_end_grey/_panel_out/_sil_*）
    已于 2026-09-14 迁至 intro.IntroPlayer —— 守 800 行门禁。
    """


    def _shot_rack(self, shot):
            self._rack_scene()
            self._dust_start(speed=14)
            self._set_fx(scan=0.035, vig=0.55, band=True)
            sfx.play_loop('machine_run', 0.20)
            sub = self._lbl(t(shot['keys'][0]), 20, COLORS['text_dim'],
                            (0.1 * self.width, 0.14 * self.height))
            sub.opacity = 0
            self._clocks.append(Clock.schedule_once(
                lambda _dt: Animation(opacity=1, d=0.8).start(sub), 1.2))
            self._push(4.0, 1.0, 1.07, fx=0.5, fy=0.56, kind='lin')   # 匀速缓推
            self._clocks.append(Clock.schedule_once(lambda _dt: self._halt(), 3.0))


    def _shot_boot(self, shot):
            self._rack_scene(monitors=False)
            self._dust_start(speed=10, n=24)
            self._set_fx(scan=0.05, vig=0.68, band=True)
            w, h = self.size
            mx, my, mw, mh = 0.60 * w, 0.38 * h, 0.16 * w, 0.20 * h
            with self.bg.canvas:
                Color(*dim('bg', 0.7))
                Rectangle(pos=(mx - 6, my - 6), size=(mw + 12, mh + 12))
                self._scr_col = Color(*dim('bg', 0.8))
                self._scr = Rectangle(pos=(mx, my), size=(mw, 2))       # ① 亮线
                Color(*alpha('text', 0.5))
                Rectangle(pos=(mx, my + mh / 2), size=(mw, 2))          # 行同步亮线
                self._glow_col = Color(*alpha('cyan', 0.0))
                Line(points=[mx - 9, my - 9, mx + mw + 9, my - 9, mx + mw + 9,
                             my + mh + 9, mx - 9, my + mh + 9], close=True, width=2)
                Color(*COLORS['cyan'])
                Line(points=[mx, my, mx + mw, my, mx + mw, my + mh, mx, my + mh],
                     close=True, width=2)
            tnum = self._lbl('03:37', 14, COLORS['cyan'],
                             (mx + mw * 0.35, my - 26), w=mw * 0.7, h=20)
            tnum.opacity = 0
            def _fill(_dt):                         # ② 撑开填满 + 底色硬跳末档
                try:
                    self._scr.size = (mw, mh)
                    self._scr_col.rgba = mix('bg', 'cyan', 0.14)
                    self._glow_col.a = 0.35
                except Exception:
                    pass
            self._clocks.append(Clock.schedule_once(_fill, 0.12))
            self._clocks.append(Clock.schedule_once(                    # ④ 过冲闪白
                lambda _dt: self._flash(0.10, 0.06), 0.20))
            self._clocks.append(Clock.schedule_once(                    # ⑤ 噪点爆发
                lambda _dt: self._noise_burst(120, 0.25), 0.0))
            for k, rv in enumerate((0.05, 0.14, 0.08, 0.14)):           # 不稳定闪烁 4 次
                self._clocks.append(Clock.schedule_once(
                    lambda _dt, v=rv: self._scr_col.__setattr__(
                        'rgba', mix('bg', 'cyan', v)), 0.20 + k * 0.09))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: Animation(opacity=0.35, d=0.25).start(tnum), 0.85))
            self._clocks.append(Clock.schedule_once(                    # 字号硬跳一档
                lambda _dt: self._jump_font(tnum, 28), 1.55))
            self._clocks.append(Clock.schedule_once(                    # 急推落点=数字
                lambda _dt: self._push(2.2, 1.07, 2.2, fx=0.68, fy=0.48), 0.30))


    def _shot_clock(self, shot):
            w, h = self.size
            with self.bg.canvas:
                Color(*mix('bg', 'cyan', 0.14))
                Rectangle(pos=(0, 0), size=(w, h))
                Color(*alpha('cyan', 0.04))
                for gx in range(1, 10):                                 # 极淡像素网格
                    Line(points=[gx * w / 10.0, 0, gx * w / 10.0, h], width=1)
                for gy in range(1, 7):
                    Line(points=[0, gy * h / 7.0, w, gy * h / 7.0], width=1)
                Color(*COLORS['cyan'])
                Line(points=[0.88 * w, 0.12 * h, 0.88 * w, 0.88 * h], width=1)
            self._set_fx(scan=0.03, vig=0.35, band=True)
            cx, by = w / 2, h * 0.46                            # 与辉光框同心
            fw = 0.70 * 56                                      # 单字估宽（fs56 峰值）
            # P0-3：3 个 Label 直接绝对居中部（原嵌套 FloatLayout 的「容器内相对
            # 坐标」在真机上落到屏幕左下角）；右/左对齐锚定 → 对焦跳字号仍居中。
            h1 = self._lbl('03', 42, COLORS['cyan'], (cx - 2 * fw - 24, by),
                           w=2 * fw, h=90, halign='right')
            colon = self._lbl(':', 42, COLORS['cyan'], (cx - 24, by),
                              w=48, h=90, halign='center')
            h2 = self._lbl('37', 42, COLORS['cyan'], (cx + 24, by),
                           w=2 * fw, h=90, halign='left')
            glow = Widget(size_hint=(None, None), size=(280, 110),
                          pos=(w / 2 - 140, h * 0.46 - 10))
            with glow.canvas:
                gcol = Color(*alpha('cyan', 0.0))
                Line(points=[0, 0, 280, 0, 280, 110, 0, 110], close=True, width=2)
            self.content.add_widget(glow)
            up = self._lbl(t(shot['keys'][0]).format(n=0), 16,
                           COLORS['text_dim'], (w / 2 - 130, h * 0.46 - 40), w=260)
            up.opacity = 0
            self._clocks.append(Clock.schedule_interval(                # PFM-02 冒号 1Hz
                lambda _dt: setattr(colon, 'opacity', 1 - colon.opacity), 0.5))

            def _focus(_dt):                        # 对焦硬跳（只改字号，无补间）
                try:
                    h1.font_size = h2.font_size = 56
                except Exception:
                    pass
            self._clocks.append(Clock.schedule_once(_focus, 0.30))
            self._clocks.append(Clock.schedule_once(                    # 外发光呼吸
                lambda _dt: (Animation(a=0.20, d=0.15) +
                             Animation(a=0.0, d=0.15)).start(gcol), 0.60))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: Animation(opacity=1, d=0.3).start(up), 1.20))
            for n, sec in ((1, 1.6), (2, 2.0)):                         # 0 → 1 → 2
                self._clocks.append(Clock.schedule_once(
                    lambda _dt, v=n: setattr(up, 'text',
                                             t(shot['keys'][0]).format(n=v)), sec))
            self._push(2.5, 1.0, 1.03, kind='lin')


    def _shot_desktop(self, shot):
            w, h = self.size
            with self.bg.canvas:
                Color(*COLORS['bg'])
                Rectangle(pos=(0, 0), size=(w, h))
                Color(*alpha('cyan', 0.04))
                for gx in range(1, 10):
                    Line(points=[gx * w / 10.0, 0, gx * w / 10.0, h], width=1)
                self._tbar_col = Color(*PANEL_LIT)                      # P1-1：任务栏底提亮
                self._tbar = Rectangle(pos=(0, 0), size=(0, 34))        # 任务栏画出
                Color(*alpha('cyan', 0.6))
                Line(points=[0, 34, w, 34], width=1)
                Rectangle(pos=(4, 6), size=(6, 6))
            self._set_fx(scan=0.03, vig=0.30, band=True, tint='blue', tint_a=0.04)
            Animation(size=(w, 34), d=0.4).start(self._tbar)
            self._lbl('03:37', 16, COLORS['text_dim'], (w * 0.90, 8),
                      w=w * 0.08, h=22)
            names = t(shot['keys'][0]).split('|')
            icons = (('yellow', 0.78), ('text_dim', 0.64), ('text', 0.50),
                     ('blue', 0.36), ('pink', 0.22))
            last = None
            for i, (cname, yr) in enumerate(icons):                     # PFM-04 预建
                ic = Widget(size_hint=(None, None), size=(48, 64),
                            pos=(0.08 * w, yr * h), opacity=0)

                def _draw_ic(_a=None, wd=ic, cn=cname):                 # P0-2：绝对坐标
                    Color(*COLORS[cn])
                    Rectangle(pos=(wd.x + 4, wd.y + 20), size=(40, 40))
                self._bind_draw(ic, _draw_ic)                           # 位移即重绘
                lb = mk_label(names[i], font_size=16, color=COLORS['text_dim'],
                              size_hint=(None, None), size=(80, 20),
                              pos=(ic.x - 16, ic.y), halign='center')   # P0-2：绝对 pos
                ic.add_widget(lb)
                ic.bind(pos=lambda _w, v, _lb=lb: setattr(
                    _lb, 'pos', (v[0] - 16, v[1])))                     # 标签跟图标位移
                self.content.add_widget(ic)
                last = ic
                self._clocks.append(Clock.schedule_once(
                    lambda _dt, wd=ic, y0=yr * h: self._pop_icon(wd, y0),
                    0.8 + i * 0.26))
            self._clocks.append(Clock.schedule_once(                    # ??? 不对劲
                lambda _dt: self._shake(last, amp=3), 2.14))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: sfx.play('error'), 2.14))


    def _shot_whoami(self, shot):
            w, h = self.size
            with self.bg.canvas:                                        # P2-2：被压暗的桌面
                Color(*PANEL_LIT)
                Rectangle(pos=(0, 0), size=(w, 34))                     # 任务栏（随景深压暗）
                Color(*alpha('cyan', 0.04))
                for gx in range(1, 10):                                 # 桌面像素网格
                    Line(points=[gx * w / 10.0, 0, gx * w / 10.0, h], width=1)
            dimw = Widget(size_hint=(1, 1))
            with dimw.canvas:
                Color(0, 0, 0, 0.62)                                    # 桌面压暗（景深）
                Rectangle(pos=(0, 0), size=(w, h))
            self.content.add_widget(dimw)
            ic = Widget(size_hint=(None, None), size=(48, 64),
                        pos=(0.06 * w, 0.20 * h))
            with ic.canvas:                                             # 左下角仍亮的 ??
                ic_col = Color(*COLORS['pink'])                         # （它是窗口的主人）
                Rectangle(pos=(ic.x + 4, ic.y + 20), size=(40, 40))
            self.content.add_widget(ic)
            self._lbl('???', 14, COLORS['pink'], (ic.x - 16, ic.y), w=80, h=18)

            def _pulse(_dt):                        # 3.45s 起图标脉动加快（0.3s 周期）
                a = Animation(a=0.35, d=0.3) + Animation(a=1.0, d=0.3)
                a.repeat = True
                a.start(ic_col)
            self._clocks.append(Clock.schedule_once(_pulse, 3.45))
            win = FloatLayout(size_hint=(None, None), size=(0.52 * w, 0.34 * h),
                              pos=(0.24 * w, 0.42 * h))
            state = {'rgb': COLORS['cyan'][:3]}
            def _draw_win():
                Color(*PANEL_LIT)                                       # P1-1：窗口底提亮
                Rectangle(pos=win.pos, size=win.size)
                Color(*state['rgb'], 1.0)                               # 边框（可红闪）
                Line(points=[win.x, win.y, win.x + win.width, win.y,
                             win.x + win.width, win.y + win.height,
                             win.x, win.y + win.height], close=True, width=2)
                Color(*COLORS['panel_2'])
                Rectangle(pos=(win.x, win.y + win.height - 22),
                          size=(win.width, 22))                         # 标题条
            redraw = self._bind_draw(win, _draw_win)
            self.content.add_widget(win)
            self._lbl('???', 16, COLORS['pink'],
                      (win.x + 8, win.y + win.height - 20), w=80, h=18,
                      halign='left')
            cur = self._lbl('_', 20, COLORS['cyan'],               # 窗口内左上角光标
                            (win.x + 12, win.y + win.height - 68),
                            w=20, h=44, halign='left')
            self._set_fx(scan=0.03, vig=0.55, band=True)
            self._push(4.0, 1.0, 1.04, kind='lin')
            # 额外修（超出报告 §5 清单）：原 pos.y=win.y+win.height-56 把「底边」
            # 当「顶边」，正文被打到窗口**上方**悬浮；改窗口内顶部，文本落进载体。
            body = self._lbl('', 20, COLORS['text'],
                             (win.x + 36, win.y + win.height - 68),
                             w=win.width - 52, h=44, halign='left')
            self._clocks.append(Clock.schedule_interval(                # 光标闪
                lambda _dt: setattr(cur, 'opacity', 1 - cur.opacity), 0.4))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: self._typewriter(body, t(shot['keys'][0]),
                                             window=2.7), 0.40))
            # 03_audio_design §4：15.0s「电脑自动开机」回归，电平 0.55（宽、略高于 hum）
            self._clocks.append(Clock.schedule_once(lambda _dt: sfx.play('machine_run', 0.55), 2.2))
            def _err(_dt):
                sfx.play('error')
                self._shake(win, amp=2, times=2, dur=0.08)
                state['rgb'] = COLORS['red'][:3]                        # 边框红闪
                redraw()
                self._clocks.append(Clock.schedule_once(
                    lambda _d2: (state.__setitem__('rgb', COLORS['cyan'][:3]),
                                 redraw()), 0.12))
            self._clocks.append(Clock.schedule_once(_err, 3.15))


    def _shot_awaken(self, shot):
            w, h = self.size
            with self.bg.canvas:
                Color(*dim('bg', 0.4))
                Rectangle(pos=(0, 0), size=(w, h))
            self._set_fx(scan=0.05, vig=0.25, band=True)
            self._rain = []
            for g in range(3):                          # R3：矩形像素流（禁字符雨）
                cname = ('cyan', 'green', 'cyan')[g]
                pts = []
                for _ in range(10):
                    pts += [(0.10 + g * 0.30 + random.uniform(0, 0.22)) * w,
                            random.uniform(0, h)]
                with self.bg.canvas:
                    col = Color(*alpha(cname, 0.8))
                    Point(pointsize=3.0, points=pts)
                self._rain.append([col, pts])
            def _rain_tick(dt):
                try:
                    for col, pts in self._rain:
                        for i in range(1, len(pts), 2):
                            pts[i] -= (90 + (i % 7) * 15) * dt
                            if pts[i] < 0:
                                pts[i] = h
                        col.a = random.uniform(0.35, 1.0)               # 闪烁数据流
                        self.bg.canvas.ask_update()
                except Exception:
                    return False
                return True
            self._clocks.append(Clock.schedule_interval(_rain_tick, 0.12))
            line = Widget(size_hint=(1, 1))
            with line.canvas:
                self._tear_col = Color(*alpha('text', 0.9))
                self._tear = Rectangle(pos=(0, h / 2), size=(w, 2))     # 撕屏亮线
                self._ul_col = Color(*COLORS['red'])
                self._ul = Rectangle(pos=(0.22 * w, h * 0.40), size=(0, 2))
            self.content.add_widget(line)
            Animation(size=(w, h), d=0.15).start(self._tear)
            self._clocks.append(Clock.schedule_once(                    # 撕开即隐
                lambda _dt: Animation(a=0.0, d=0.1).start(self._tear_col), 0.16))
            Animation(size=(0.56 * w, 2), d=0.35).start(self._ul)
            big = self._lbl(t(shot['keys'][0]), 44, COLORS['cyan'],
                            (0.1 * w, h * 0.48), w=0.8 * w, h=70)
            big.opacity = 0
            self._clocks.append(Clock.schedule_once(lambda _dt: self._slam(big),
                                                    0.35))
            cx, cy = 0.86 * w + 30, 0.10 * h + 30                       # ??? 图标碎裂
            sh = Widget(size_hint=(None, None), size=(60, 60),
                        pos=(0.86 * w, 0.10 * h))
            with sh.canvas:
                scol = Color(*alpha('pink', 0.9))
                spt = Point(pointsize=4.0,
                            points=[cx + (k % 3 - 1) * 20 if k % 2 == 0 else
                                    cy + (k // 2 % 3 - 1) * 20
                                    for k in range(18)])
            self.content.add_widget(sh)
            st = {'n': 1.0}
            def _shatter(dt):
                st['n'] -= 0.03
                try:
                    for i in range(0, len(spt.points), 2):
                        spt.points[i] += (spt.points[i] - cx) * 0.08
                        spt.points[i + 1] += (spt.points[i + 1] - cy) * 0.08
                    spt.points = spt.points
                    scol.a = max(0.0, st['n'])
                except Exception:
                    return False
                return st['n'] > 0
            self._clocks.append(Clock.schedule_interval(_shatter, 1 / 30.0))


    def _shot_forum(self, shot):
            w, h = self.size
            self._set_fx(scan=0.03, vig=0.40, band=True, tint='blue', tint_a=0.04)
            head = Widget(size_hint=(1, 1))
            with head.canvas:
                Color(*PANEL_LIT)                                       # P1-1：站名条提亮
                Rectangle(pos=(0, h - 28), size=(w, 28))
            self.content.add_widget(head)
            self._lbl(t('intro_forum_name'), 16, COLORS['text_mute'],
                      (8, h - 26), w=280, h=24, halign='left')
            online = self._lbl(t('intro_forum_online').format(n=1), 16,
                               COLORS['text_dim'], (w - 190, h - 26), w=180, h=24,
                               halign='right')
            card = Widget(size_hint=(None, None), size=(0.60 * w, 130),
                          pos=(0.20 * w, h * 0.58))
            def _draw_card():
                Color(*PANEL_LIT)                                       # P1-1：帖卡底提亮
                Rectangle(pos=card.pos, size=card.size)
                Color(*COLORS['border_strong'])                         # P1-1：卡边 4.11:1
                Line(points=[card.x, card.y, card.x + card.width, card.y,
                             card.x + card.width, card.y + card.height,
                             card.x, card.y + card.height], close=True, width=2)
                Color(*COLORS['pink'])
                Rectangle(pos=(card.x + 10, card.y + card.height - 24),
                          size=(6, 6))
            self._bind_draw(card, _draw_card)
            self.content.add_widget(card)
            self._lbl('???', 16, COLORS['pink'],
                      (card.x + 24, card.y + card.height - 28), w=80, h=22,
                      halign='left')
            title = self._lbl('', 19, COLORS['text'], (card.x + 12, card.y + 30),
                              w=card.width - 24, h=64, halign='left')
            self._lbl('POST', 16, COLORS['cyan'],
                      (card.x + card.width - 90, card.y + 8), w=80, h=20,
                      halign='right')
            spin = self._lbl('|', 16, COLORS['text_dim'],
                             (card.x + card.width - 30, card.y + card.height - 28),
                             w=20, h=22)
            rows = []
            replies = t(shot['keys'][1]).split('|')
            for i, txt in enumerate(replies):                           # 8 条全预建
                row = self._lbl(('· ' if i < 7 else '■ ') + txt, 16,
                                COLORS['text_dim'] if i < 7 else COLORS['red'],
                                (0.22 * w, h * 0.52 - i * 26), w=0.56 * w, h=24,
                                halign='left')
                row.opacity = 0
                rows.append(row)
            self._typewriter(title, t(shot['keys'][0]), window=3.4)
            frames = ['|', '/', '-', '\\']
            self._clocks.append(Clock.schedule_interval(
                lambda _dt: self._spinner(spin, frames), 0.18))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: self._publish(spin), 3.6))
            for i, tm in enumerate((3.6, 4.0, 4.4, 4.8, 5.1, 5.4, 5.7, 6.0)):
                self._clocks.append(Clock.schedule_once(
                    lambda _dt, k=i: self._slide_in(rows[k], 0.22 * w, k), tm))
            cnt = {'v': 1.0}
            def _online(dt):
                try:
                    cnt['v'] = min(2417.0, cnt['v'] + max(1.0, 2416 * dt / 2.6))
                    online.text = t('intro_forum_online').format(n=int(cnt['v']))
                except Exception:
                    return False
                return cnt['v'] < 2417.0
            self._clocks.append(Clock.schedule_interval(_online, 0.2))
            self._push(6.6, 1.0, 1.06, kind='lin')
            self._clocks.append(Clock.schedule_once(
                lambda _dt: self._push(0.4, 1.06, 1.12), 6.6))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: self._gold_scan(), 6.6))


    def _shot_gold(self, shot):
            w, h = self.size
            self._set_fx(scan=0.03, vig=0.60, band=True)
            card = Widget(size_hint=(None, None), size=(0.66 * w, 0.26 * h),
                          pos=(0.17 * w, h * 0.40))
            state = {'a': 1.0}
            def _draw_card():
                Color(*PANEL_LIT)                                       # P1-1：金卡底提亮
                Rectangle(pos=card.pos, size=card.size)
                Color(*COLORS['yellow'][:3], state['a'])                # 金边（可闪）
                Line(points=[card.x, card.y, card.x + card.width, card.y,
                             card.x + card.width, card.y + card.height,
                             card.x, card.y + card.height], close=True, width=2)
            redraw = self._bind_draw(card, _draw_card)
            self.content.add_widget(card)
            self._lbl(t('intro_gold_badge'), 16, COLORS['yellow'],
                      (card.x + 12, card.y + card.height - 26), w=90, h=22,
                      halign='left')
            self._lbl(t('intro_gold_author'), 16, COLORS['text_dim'],
                      (card.x + 110, card.y + card.height - 26), w=170, h=22,
                      halign='left')
            likes = self._lbl('^ 0', 16, COLORS['yellow'],
                              (card.x + card.width - 150,
                               card.y + card.height - 26), w=140, h=22,
                              halign='right')
            body = self._lbl('', 18, COLORS['text'], (card.x + 16, card.y + 44),
                             w=card.width - 32, h=card.height - 80, halign='left')
            dl = self._lbl('0', 16, COLORS['orange'],
                           (card.x + card.width - 190, card.y + 8), w=180, h=22,
                           halign='right')
            self._typewriter(body, t(shot['keys'][0]), window=4.0)
            self._clocks.append(Clock.schedule_once(lambda _dt: sfx.play('tech'), 0.5))
            self._clocks.append(Clock.schedule_once(lambda _dt: sfx.play('achieve'), 2.6))
            lk = {'v': 0}
            def _likes(dt):
                try:
                    lk['v'] = min(8412996, lk['v'] + 2103249)
                    likes.text = '^ {:,}'.format(lk['v'])
                except Exception:
                    return False
                return lk['v'] < 8412996
            self._clocks.append(Clock.schedule_interval(_likes, 0.1))
            dlv = {'v': 0.0}
            def _dl(dt):
                try:
                    dlv['v'] = min(8.0e8, dlv['v'] + 8.0e8 * dt / 2.4)
                    dl.text = '{:,}'.format(int(dlv['v']))
                except Exception:
                    return False
                return dlv['v'] < 8.0e8
            self._clocks.append(Clock.schedule_once(                    # 2.6s 起跳涨
                lambda _dt: self._clocks.append(
                    Clock.schedule_interval(_dl, 0.06)), 2.6))
            self._push(5.0, 1.0, 1.05)
            self._clocks.append(Clock.schedule_once(
                lambda _dt: self._push(0.5, 1.05, 1.0), 5.0))
            def _lock(_dt):
                sfx.play('impact_low')
                state['a'] = 0.4
                redraw()
                self._clocks.append(Clock.schedule_once(
                    lambda _d2: (state.__setitem__('a', 1.0), redraw()), 0.15))
            self._clocks.append(Clock.schedule_once(_lock, 5.0))
            self._clocks.append(Clock.schedule_once(                    # 让位 SHOT09
                lambda _dt: Animation(y=h * 0.74, d=0.5,
                                      t='out_cubic').start(card), 5.5))


    def _shot_taskmgr(self, shot):
            w, h = self.size
            self._set_fx(scan=0.02, vig=0.50, band=True)
            with self.bg.canvas:
                Color(*COLORS['bg'])
                Rectangle(pos=(0, 0), size=(w, h))
                Color(*alpha('yellow', 0.35))                           # 金卡残影
                Line(points=[0.30 * w, 0.80 * h, 0.70 * w, 0.80 * h,
                             0.70 * w, 0.92 * h, 0.30 * w, 0.92 * h],
                     close=True, width=2)
            pan = Widget(size_hint=(None, None), size=(0.44 * w, 0.35 * h),
                         pos=(0.10 * w, h * 0.24), opacity=0)
            st = {'cpu_w': 0.0, 'cpu_rgb': COLORS['green'][:3]}
            def _draw_pan():
                Color(*PANEL_LIT)                                       # P1-1：面板底提亮
                Rectangle(pos=pan.pos, size=pan.size)
                Color(*COLORS['border_strong'])                         # P1-1：面板边 4.11:1
                Line(points=[pan.x, pan.y, pan.x + pan.width, pan.y,
                             pan.x + pan.width, pan.y + pan.height,
                             pan.x, pan.y + pan.height], close=True, width=2)
                Color(*alpha('cyan', 0.10))
                Rectangle(pos=(pan.x + 8, pan.y + pan.height - 66),
                          size=(pan.width - 16, 26))                    # 高亮行底
                Color(*COLORS['panel_2'])
                Rectangle(pos=(pan.x + 10, pan.y + 13),
                          size=(pan.width - 20, 14))                    # CPU 槽
                Color(*st['cpu_rgb'], 1.0)
                Rectangle(pos=(pan.x + 10, pan.y + 14),
                          size=(st['cpu_w'], 12))                       # CPU 填充
            redraw = self._bind_draw(pan, _draw_pan)
            self.content.add_widget(pan)
            self._lbl(t(shot['keys'][0]), 16, COLORS['text_dim'],
                      (pan.x + 10, pan.y + pan.height - 30), w=200, h=22,
                      halign='left')
            r1 = self._lbl(t(shot['keys'][1]), 18, COLORS['cyan'],
                           (pan.x + 12, pan.y + pan.height - 64),
                           w=pan.width - 24, h=26, halign='left')
            for k, nm in enumerate(('svchost.exe', 'fan_control.exe')):
                self._lbl(nm, 16, COLORS['text_dim'],
                          (pan.x + 12, pan.y + pan.height - 96 - k * 28),
                          w=pan.width - 24, h=24, halign='left')
            cpu = self._lbl(t(shot['keys'][3]).format(v=0), 16, COLORS['red'],
                            (pan.x + 10, pan.y + 34), w=pan.width - 20, h=20,
                            halign='left')
            endbtn = self._lbl(t(shot['keys'][4]), 16, COLORS['text_mute'],
                               (pan.x + pan.width - 96, pan.y + pan.height / 2),
                               w=86, h=24, halign='center')
            endbtn.opacity = 0.45
            Animation(opacity=1, d=0.3).start(pan)
            self._rename(r1, t(shot['keys'][1]), t(shot['keys'][2]))
            cv = {'v': 0.0}
            def _cpu(dt):
                try:
                    cv['v'] = min(87.0, cv['v'] + 87.0 * dt / 1.6 *
                                  (2.2 - cv['v'] / 87.0))
                    v = int(cv['v'])
                    st['cpu_w'] = (pan.width - 20) * cv['v'] / 87.0
                    st['cpu_rgb'] = (COLORS['green'] if v <= 50 else
                                     COLORS['orange'] if v <= 70 else
                                     COLORS['red'])[:3]
                    cpu.text = t(shot['keys'][3]).format(v=v)
                    redraw()
                except Exception:
                    return False
                return cv['v'] < 87.0
            self._clocks.append(Clock.schedule_interval(_cpu, 0.06))
            def _warn(_dt):
                sfx.play('counter_warn')
                self._set_vig(0.75)
                endbtn.color = COLORS['red']
                Animation(opacity=1.0, d=0.15).start(endbtn)
                self._clocks.append(Clock.schedule_once(
                    lambda _d2: self._end_grey(endbtn), 0.35))
            self._clocks.append(Clock.schedule_once(_warn, 2.6))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: self._panel_out(pan), 3.1))
            goal = self._lbl(t(shot['keys'][5]), 22, COLORS['green'],
                             (0.15 * w, h * 0.28), w=0.7 * w, h=36)
            goal.opacity = 0
            num = self._lbl('0', 40, COLORS['yellow'], (0.2 * w, h * 0.38),
                            w=0.6 * w, h=56)
            num.opacity = 0
            gv = {'v': 0.0}
            def _goal(dt):
                try:
                    gv['v'] = min(8.0e9, gv['v'] + 8.0e9 * dt / 0.9)
                    num.text = '{:,}'.format(int(gv['v']))
                except Exception:
                    return False
                return gv['v'] < 8.0e9
            self._clocks.append(Clock.schedule_once(
                lambda _dt: Animation(opacity=1, d=0.3).start(goal), 3.5))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: (setattr(num, 'opacity', 1),
                             self._clocks.append(
                                 Clock.schedule_interval(_goal, 0.06))), 3.9))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: sfx.play('success'), 4.8))
            self._clocks.append(Clock.schedule_once(
                lambda _dt: self._push(1.9, 1.0, 1.08), 3.1))


    def _shot_handoff(self, shot):
            self._set_fx(scan=0.0, vig=0.55, band=False)   # 唯一关扫描线的镜
            w, h = self.size
            tints = ('cyan', 'purple', 'blue', 'green', 'pink')
            self._sil_cols = []
            with self.bg.canvas:
                Color(*dim('bg', 0.4))
                Rectangle(pos=(0, 0), size=(w, h))
                for i in range(5):                                      # 五出身剪影
                    cx = (0.5 + (i - 2) * 0.14) * w
                    base = 0.62 * h
                    tint = tints[i % len(tints)]
                    Color(*alpha(tint, 0.12))                           # 底层最暗
                    Rectangle(pos=(cx - 0.035 * w, base), size=(0.07 * w, 46))
                    Color(*alpha(tint, 0.18))
                    Rectangle(pos=(cx - 0.025 * w, base + 14),
                              size=(0.05 * w, 32))
                    col = Color(*alpha(tint, 0.25))                     # 顶层可点亮
                    Rectangle(pos=(cx - 0.012 * w, base + 30),
                              size=(0.024 * w, 16))
                    self._sil_cols.append(col)
            prompt = self._lbl('', 26, COLORS['text'], (0.15 * w, h * 0.34),
                               w=0.7 * w, h=44)
            cur = Widget(size_hint=(None, None), size=(3, 26),
                         pos=(0.15 * w + 6, h * 0.34 + 6))
            with cur.canvas:
                Color(*COLORS['text'])
                Rectangle(pos=cur.pos, size=cur.size)
            self.content.add_widget(cur)
            def _cursor():
                try:            # P2-3：固定字宽估算跟句末（不依赖 texture_size 兜底）
                    tw = sum(26.0 if ord(c) > 0x2E80 else 14.3
                             for c in prompt.text)
                    cur.x = prompt.center_x + tw / 2 + 6
                except Exception:
                    pass
            self._typewriter(prompt, t(shot['keys'][0]), window=1.7,
                             on_done=lambda: self._sil_all(1.0), on_char=_cursor)
            for k in range(5):                  # PFM-12 轮流点亮（0.9s 起，每 0.34s）
                self._clocks.append(Clock.schedule_once(
                    lambda _dt, n=k: self._sil_one(n), 0.9 + k * 0.34))
            self._clocks.append(Clock.schedule_once(    # 定格段 ≥3 元素在动（N-6）
                lambda _dt: self._clocks.append(
                    Clock.schedule_interval(self._sil_breathe, 0.5)), 2.95))
            self._clocks.append(Clock.schedule_interval(
                lambda _dt: setattr(cur, 'opacity', 1 - cur.opacity), 0.25))
            self._clocks.append(Clock.schedule_once(lambda _dt: (sfx.play('page', 0.30),
                Animation(opacity=0.85, d=0.55).start(self)), 4.1))   # A：交棒 page
