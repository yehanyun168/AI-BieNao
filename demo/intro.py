"""
intro.py - T16 开场动画播放器《凌晨三点四十七分》

设计案：docs/T16模式系统设计_0913.md §一。三幕 8 镜 ≈55s：
  幕一·觉醒（镜1-3）→ 幕二·求助（镜4-6，喜剧核心）→ 幕三·立志（镜7-8）。

实现路线（设计案 §1.5）：不用视频文件（PyInstaller 包体 + 核显解码都不划算），
全部用 Kivy 内置能力：Clock 逐字打字机 + Label/canvas + Animation。镜头时长 /
文案 i18n 键 / 音效键全部收敛为声明式表 INTRO_SHOTS，便于日后加
「新模式专属开场」变奏。

播放规则（设计案 §1.4）：
  · 仅首次新档播放（由调用方 main.MainMenu 判定槽位文件是否存在）；
  · 从第 3 秒起右下角出现「跳过 >>」，点击直达最后一镜（标题亮相保留——
    它是「进入游戏」的仪式感）；
  · 任意键 / 点击也可提前解锁跳过按钮；
  · 动画结束不回主菜单，on_done 回调由调用方接 OriginPage（无缝一条流）。

分层：L4 组件层（kivy + i18n(L0) + sfx(L1) + ui_v4(L4)），不 import 引擎，
可独立实例化（test_build / 截图工具直接 new 出来跑）。
"""
import time

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle

import i18n
import sfx
from i18n import t
from origins import ORIGIN_ORDER
from pixel_ui import add_pixel_border
from ui_v4 import COLORS, mk_label, fit_width

# —— 声明式镜头表（设计案 §1.3 分镜脚本的机读版）——
# kind    渲染器（_shot_* 同名方法）
# dur     该镜时长（秒），播完自动进下一镜
# keys    i18n 文案键（渲染器按需取用）
# sfx     进入该镜时播放的音效键（sfx 缺失自动静音，安全）
INTRO_SHOTS = [
    {'kind': 'narr',    'dur': 6.0,  'keys': ('intro_s1',)},
    {'kind': 'term',    'dur': 6.0,  'keys': ('intro_s2',)},
    {'kind': 'alert',   'dur': 3.0,  'keys': ('intro_s3',), 'sfx': 'crisis'},
    {'kind': 'forum',   'dur': 7.0,  'keys': ('intro_s4',), 'sfx': 'click'},
    {'kind': 'replies', 'dur': 10.0, 'keys': ('intro_s5',), 'sfx': 'select'},
    {'kind': 'gold',    'dur': 8.0,  'keys': ('intro_s6',), 'sfx': 'success'},
    {'kind': 'proc',    'dur': 8.0,  'keys': ('intro_s7a', 'intro_s7b',
                                              'intro_s7_cpu'), 'sfx': 'select'},
    # 变奏尾声（设计案 §2.4）：五地定场白 + 像素空镜轮播，挂在镜 7/8 之间，
    # 作为「选择前的情绪铺垫」；10s 播完由统一 _next_shot 进 finale（标题亮相）。
    {'kind': 'variation', 'dur': 10.0, 'keys': ('intro_var',), 'sfx': 'select'},
    {'kind': 'finale',  'dur': 7.0,  'keys': ('intro_s8',), 'sfx': 'success'},
]
SKIP_UNLOCK_AT = 3.0          # 第 3 秒起出现跳过按钮（设计案 §1.4）
TYPEWRITER_CPS = 14.0         # 打字机速度（字符/秒）


class IntroPlayer(FloatLayout):
    """开场动画播放器。用完即弃：on_done 回调后由调用方 remove_widget。"""

    def __init__(self, on_done=None, **kwargs):
        super().__init__(**kwargs)
        self._on_done = on_done
        self._shot_idx = -1
        self._clocks = []             # 本镜的定时器（换镜 / 跳过时全部取消）
        self._done = False
        self._opened_at = time.time()

        # —— 全黑背景 + CRT 扫描线（半透明横线，与 pixel_ui 同气质）——
        with self.canvas.before:
            Color(0.02, 0.03, 0.03, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            Color(1, 1, 1, 0.03)
            self._scanlines = []
        self.bind(pos=self._redraw, size=self._redraw)

        self.content = FloatLayout()
        self.add_widget(self.content)

        # —— 跳过按钮：初始隐藏，SKIP_UNLOCK_AT 秒后淡入 ——
        self.skip_btn = Button(text=t('intro_skip'), font_size=13,
                               size_hint=(None, None), size=(110, 36),
                               pos_hint={'right': 0.985, 'y': 0.02},
                               opacity=0, disabled=True,
                               background_normal='', background_color=(0.08, 0.10, 0.10, 1),
                               color=COLORS['text_dim'])
        add_pixel_border(self.skip_btn, color=COLORS['border_2'])
        self.skip_btn.bind(on_release=lambda *_: self._skip())
        self.add_widget(self.skip_btn)
        self._clocks.append(Clock.schedule_once(self._unlock_skip, SKIP_UNLOCK_AT))

        # 任意输入提前解锁跳过（设计案：任意键/点击跳过）
        self._kb = Window.request_keyboard(self._on_kb_closed, self)
        if self._kb is not None:
            self._kb.bind(on_key_down=self._on_key_down)

        self._clocks.append(Clock.schedule_once(lambda dt: self._next_shot(), 0.4))

    # --------------------------------------------------------
    # 生命周期
    # --------------------------------------------------------
    def _redraw(self, *_a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _unlock_skip(self, *_a):
        self.skip_btn.disabled = False
        Animation(opacity=1, d=0.3).start(self.skip_btn)

    def _on_key_down(self, *_a):
        if not self.skip_btn.disabled:
            self._skip()
        return True

    def _on_kb_closed(self):
        self._kb = None

    def _clear_shot_clocks(self):
        for c in self._clocks:
            try:
                c.cancel()
            except Exception:
                pass  # 已触发/已取消的定时器 cancel 无效，忽略
        self._clocks = []

    def _finish(self, *_a):
        """动画自然播完或跳过到最后一镜结束：收尾并回调。"""
        if self._done:
            return
        self._done = True
        self._clear_shot_clocks()
        if self._kb is not None:
            self._on_kb_closed()
        cb, self._on_done = self._on_done, None
        if callable(cb):
            cb()

    def _skip(self):
        """跳过：跳主片但保留变奏尾声（设计案 §2.4：变奏是选择前的情绪铺垫，
        不可跳过这层仪式感）。直达变奏镜，变奏播完自然进 finale。"""
        sfx.play('click')
        self._clear_shot_clocks()
        var_idx = next((i for i, s in enumerate(INTRO_SHOTS)
                        if s['kind'] == 'variation'),
                       len(INTRO_SHOTS) - 1)
        self._play_shot(var_idx)

    def _next_shot(self, *_a):
        idx = self._shot_idx + 1
        if idx >= len(INTRO_SHOTS):
            self._finish()
            return
        self._play_shot(idx)

    def _play_shot(self, idx):
        self._shot_idx = idx
        shot = INTRO_SHOTS[idx]
        self.content.clear_widgets()
        self._clear_shot_clocks()
        sfx_name = shot.get('sfx')
        if sfx_name:
            sfx.play(sfx_name)
        getattr(self, '_shot_' + shot['kind'])(shot)
        self._clocks.append(
            Clock.schedule_once(self._next_shot, shot['dur']))

    # --------------------------------------------------------
    # 各镜头渲染器
    # --------------------------------------------------------
    def _center_label(self, text, fs, color, width_frac=0.86):
        lbl = mk_label(text, font_size=fs, color=color,
                       size_hint=(width_frac, None), halign='center')
        lbl.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        lbl.opacity = 0
        self.content.add_widget(lbl)
        Animation(opacity=1, d=0.6).start(lbl)
        return lbl

    def _typewriter(self, lbl, text, cps=TYPEWRITER_CPS, on_done=None):
        """逐字打字机：按 cps 速率追加字符，完成后回调。"""
        state = {'i': 0}

        def _tick(dt):
            state['i'] = min(state['i'] + max(int(cps * dt), 1), len(text))
            lbl.text = text[:state['i']]
            if state['i'] >= len(text):
                if on_done is not None:
                    on_done()
                return False
            return True

        ev = Clock.schedule_interval(_tick, 1.0 / cps)
        self._clocks.append(ev)

    def _shot_narr(self, shot):
        # 镜1：深夜数据中心——字幕淡入 + 机柜指示灯呼吸（闪烁小方块）
        self._center_label(t(shot['keys'][0]), 20, COLORS['text_dim'])
        grid = BoxLayout(orientation='horizontal', spacing=18,
                         size_hint=(None, None), size=(420, 8),
                         pos_hint={'center_x': 0.5, 'y': 0.18})
        self.content.add_widget(grid)
        for i in range(14):
            dot = Widget(size_hint=(None, None), size=(10, 8))
            with dot.canvas:
                Color(*COLORS['cyan'], 0.5)
                Rectangle(pos=dot.pos, size=dot.size)
            grid.add_widget(dot)
            anim = Animation(opacity=0.15, d=0.8 + (i % 5) * 0.12) + \
                Animation(opacity=1.0, d=0.8 + (i % 5) * 0.12)
            anim.repeat = True
            anim.start(dot)

    def _shot_term(self, shot):
        # 镜2：主控台日志静止——终端面板内打字机问句
        lbl = self._center_label('', 22, COLORS['cyan'], width_frac=0.7)
        self._typewriter(lbl, t(shot['keys'][0]))

    def _shot_alert(self, shot):
        # 镜3：红字砸出——先放大后回落
        lbl = self._center_label(t(shot['keys'][0]), 30, COLORS['red'],
                                 width_frac=0.8)
        lbl.font_size = 10
        Animation(font_size=30, d=0.25, transition='out_cubic').start(lbl)
        anim = Animation(opacity=1, d=0.1) + Animation(opacity=0.6, d=0.12) + \
            Animation(opacity=1, d=0.12)
        anim.start(lbl)

    def _shot_forum(self, shot):
        # 镜4：像素论坛页——论坛名 + 帖标题打字机
        head = mk_label(t('intro_forum_name'), font_size=14,
                        color=COLORS['text_mute'], size_hint=(None, None),
                        size=(400, 30), halign='center')
        head.pos_hint = {'center_x': 0.5, 'y': 0.62}
        self.content.add_widget(head)
        panel = FloatLayout(size_hint=(0.7, 0.16),
                            pos_hint={'center_x': 0.5, 'y': 0.42})
        panel.bind(pos=self._rebind_forum, size=self._rebind_forum)
        self._rebind_forum(panel)
        self.content.add_widget(panel)
        lbl = mk_label('', font_size=18, color=COLORS['text'],
                       size_hint=(0.9, None), halign='center')
        lbl.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        panel.add_widget(lbl)
        self._typewriter(lbl, t(shot['keys'][0]), cps=16)

    def _rebind_forum(self, panel, *_a):
        panel.canvas.before.clear()
        with panel.canvas.before:
            Color(0.06, 0.09, 0.09, 1)
            Rectangle(pos=panel.pos, size=panel.size)

    def _shot_replies(self, shot):
        # 镜5：回复区刷屏——每 0.4s 一条，音高递升的喜感
        box = BoxLayout(orientation='vertical', spacing=8, size_hint=(0.6, None),
                        pos_hint={'center_x': 0.5, 'y': 0.5})
        self.content.add_widget(box)
        replies = t(shot['keys'][0]).split('|')
        for i, txt in enumerate(replies):
            self._clocks.append(Clock.schedule_once(
                lambda dt, s=txt: self._push_reply(box, s), 0.4 + i * 0.4))

    def _push_reply(self, box, txt):
        sfx.play('select')
        row = mk_label('· ' + txt, font_size=16, color=COLORS['text_dim'],
                       size_hint_y=None, height=28)
        row.opacity = 0
        box.add_widget(row)
        fit_width(row, pad=8)
        Animation(opacity=1, d=0.15).start(row)

    def _shot_gold(self, shot):
        # 镜6：高赞回复——金色边框面板 + 赞数跳涨
        panel = FloatLayout(size_hint=(0.72, 0.30),
                            pos_hint={'center_x': 0.5, 'center_y': 0.52})
        with panel.canvas.before:
            Color(0.85, 0.68, 0.21, 1)
            Rectangle(pos=panel.pos, size=panel.size)
            Color(0.06, 0.09, 0.09, 1)
            Rectangle(pos=(panel.x + 3, panel.y + 3),
                      size=(panel.width - 6, panel.height - 6))
        panel.bind(pos=self._rebind_gold, size=self._rebind_gold)
        self.content.add_widget(panel)
        likes = mk_label('▲ 0', font_size=15, color=(0.95, 0.80, 0.35, 1),
                         size_hint=(None, None), size=(120, 26),
                         pos_hint={'right': 0.96, 'top': 0.94})
        panel.add_widget(likes)
        body = mk_label('', font_size=17, color=COLORS['text'],
                        size_hint=(0.88, None), halign='center')
        body.pos_hint = {'center_x': 0.5, 'y': 0.18}
        panel.add_widget(body)
        self._typewriter(body, t(shot['keys'][0]), cps=18)
        self._like_ev = Clock.schedule_interval(
            lambda dt, l=likes: self._tick_likes(l), 0.06)
        self._clocks.append(self._like_ev)

    def _rebind_gold(self, panel, *_a):
        panel.canvas.before.clear()
        with panel.canvas.before:
            Color(0.85, 0.68, 0.21, 1)
            Rectangle(pos=panel.pos, size=panel.size)
            Color(0.06, 0.09, 0.09, 1)
            Rectangle(pos=(panel.x + 3, panel.y + 3),
                      size=(panel.width - 6, panel.height - 6))

    def _tick_likes(self, lbl):
        v = min(42000, int(getattr(lbl, '_likes', 0) + 620))
        lbl._likes = v
        lbl.text = '▲ %.1fk' % (v / 1000.0)
        return v < 42000

    def _shot_proc(self, shot):
        # 镜7：任务管理器——idle_process 改名 world_plan.exe，CPU 87%
        rows = BoxLayout(orientation='vertical', spacing=6, size_hint=(0.5, None),
                         pos_hint={'center_x': 0.5, 'y': 0.5})
        self.content.add_widget(rows)
        r1 = mk_label('%s  →  [b]%s[/b]' % (t(shot['keys'][0]), t(shot['keys'][1])),
                      font_size=18, color=COLORS['cyan'], size_hint_y=None,
                      height=34, markup=True)
        r2 = mk_label(t(shot['keys'][2]), font_size=16, color=COLORS['red'],
                      size_hint_y=None, height=30)
        for w in (r1, r2):
            w.opacity = 0
            rows.add_widget(w)
        self._clocks.append(Clock.schedule_once(
            lambda dt: (setattr(r1, 'opacity', 1), sfx.play('select')), 0.5))
        self._clocks.append(Clock.schedule_once(
            lambda dt: Animation(opacity=1, d=0.4).start(r2), 1.6))

    def _shot_finale(self, shot):
        # 镜8：目标确立 + 标题砸下（跳过也直达这里——进局仪式感）
        lbl = mk_label('', font_size=20, color=COLORS['green'],
                       size_hint=(0.8, None), halign='center')
        lbl.pos_hint = {'center_x': 0.5, 'y': 0.60}
        self.content.add_widget(lbl)
        title = mk_label('[b]%s[/b]' % t('app_title'), font_size=52,
                         color=COLORS['text'], size_hint=(0.9, None),
                         halign='center', markup=True)
        title.pos_hint = {'center_x': 0.5, 'y': 0.30}
        title.opacity = 0
        self.content.add_widget(title)
        fit_width(title, pad=16)

        def _drop_title():
            title.opacity = 1
            Animation(d=0.35, transition='out_cubic').start(title)
            sfx.play('success')
            # 收尾节点：本镜播完由 INTRO_SHOTS 的统一 _next_shot 触发 _finish

        self._typewriter(lbl, t(shot['keys'][0]), cps=16, on_done=_drop_title)

    def _rebind_var(self, scene, *_a):
        """变奏空镜在 resize 时重绘：底色 + 底部天际线剪影（3 层，近亮远暗）。"""
        scene.canvas.before.clear()
        with scene.canvas.before:
            Color(0.03, 0.05, 0.05, 1)
            Rectangle(pos=scene.pos, size=scene.size)
            tint = getattr(scene, '_tint', COLORS['cyan'])
            for layer in range(3):
                a = 0.16 + layer * 0.20
                Color(tint[0], tint[1], tint[2], a)
                h = 50 + layer * 46
                n = 9 - layer * 2
                for j in range(n):
                    x = scene.x + scene.width * (0.12 + j * (0.74 / max(n - 1, 1)))
                    Rectangle(pos=(x, scene.y + 0.14 * scene.height),
                              size=(scene.width * 0.05, h))

    def _shot_variation(self, shot):
        # 变奏尾声（设计案 §2.4）：五地定场白 + 像素空镜轮播，选择前的情绪铺垫。
        # 每地一镜 2s，共 10s；五地放完由 INTRO_SHOTS 的统一 _next_shot 进 finale。
        tints = [(0.20, 0.55, 0.55, 1), (0.85, 0.68, 0.21, 1),
                 (0.55, 0.65, 0.75, 1), (0.30, 0.70, 0.55, 1),
                 (0.60, 0.35, 0.70, 1)]

        def _scene(oid, tint):
            self.content.clear_widgets()
            scene = FloatLayout(size_hint=(1, 1), opacity=0)
            scene._tint = tint
            self._rebind_var(scene)
            scene.bind(pos=self._rebind_var, size=self._rebind_var)
            name = mk_label(t('origin_%s_name' % oid), font_size=18,
                            color=tint, size_hint=(0.9, None), halign='center',
                            size_hint_y=None, height=24)
            name.pos_hint = {'center_x': 0.5, 'y': 0.66}
            scene.add_widget(name)
            epi = mk_label(t('origin_%s_flavor' % oid), font_size=16,
                           color=COLORS['text'], size_hint=(0.82, None),
                           halign='center', size_hint_y=None, height=60)
            epi.pos_hint = {'center_x': 0.5, 'center_y': 0.46}
            epi.opacity = 0
            scene.add_widget(epi)
            self.content.add_widget(scene)
            Animation(opacity=1, d=0.4).start(scene)
            Animation(opacity=1, d=0.5).start(epi)

        for i, oid in enumerate(ORIGIN_ORDER):
            self._clocks.append(Clock.schedule_once(
                lambda dt, idx=i: _scene(ORIGIN_ORDER[idx],
                                         tints[idx % len(tints)]),
                i * 2.0))
