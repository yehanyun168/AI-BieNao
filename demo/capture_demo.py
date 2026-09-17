"""capture_demo.py —— 真机截图《AI 别闹》演示视频的 30 镜（实机录屏素材）。

用法：
    KIVY_NO_FILELOG=1 python capture_demo.py

产出：video/assets/footage/S01_rack.png ... S30_finale.png （30 张真游戏画面）
说明：
  * 直接驱动真游戏（engine.init_game / RootView / IntroPlayer / GameUI 各方法），
    用 Window.screenshot 逐镜抓真机画面；不是占位图。
  * 窗口 1920x1080（能被 4 整除，避开 RGBA 行错位），正好填满 16:9。
  * 开场动画 10 镜由 IntroPlayer 自动播放，按 INTRO_SHOTS 时长在中点截图。
  * 其余 20 镜按故事板顺序驱动游戏状态后截图；每张都 try/except 尽力而为。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from kivy.config import Config                       # noqa: E402
# 1440x880 是 v4 截图验证过的稳定分辨率；后续用 PIL upscale 到 1920x1080
Config.set('graphics', 'width', '1440')
Config.set('graphics', 'height', '880')
Config.set('graphics', 'resizable', '0')

from kivy.app import App                            # noqa: E402
from kivy.clock import Clock                        # noqa: E402
from kivy.core.window import Window                 # noqa: E402
from kivy.uix.scrollview import ScrollView         # noqa: E402

import main as M                                    # noqa: E402
import engine                                       # noqa: E402
import intro                                        # noqa: E402
import ui_v4_screens as S                           # noqa: E402  (S.OriginPage)
import ui_shared as ST                              # noqa: E402  (ST.SPEED_STEPS)
import ui_popups                                    # noqa: E402  (PopupsMixin)


def _silence_crisis(self):
    """演示专用：危险度越线触发危机时静默压回阈值以下——不弹窗、不暂停。

    原因：故事板里没有「危机弹窗」这一镜，而驱动脚本故意把怀疑度推到 80+ 来展示
    红环告警；实时 tick 会反复弹「多国联合调查已启动」遮挡后续镜头。这里把它按住。
    """
    try:
        engine.player.suspicion = min(float(engine.player.suspicion), 78.0)
        engine.player.crisis_triggered = False
    except Exception:
        pass
    try:
        self.refresh_all()
    except Exception:
        pass


def _silence_choice(self, evt):
    """演示专用：事件选择弹窗静默按默认项结算——不弹窗、不暂停。

    实时跑故事板时 tick 会随机触发「来源国/事件」选择弹窗，8 秒停留期间它们会
    一直盖住画面。这里直接按 0 号选项结算，保留引擎状态推进但不渲染弹窗。
    """
    try:
        logs = engine.resolve_choice(evt, 0)
        for line in (logs or []):
            try:
                self.stats.push_log(engine.player.tick_count, str(line), 'i')
            except Exception:
                pass
    except Exception:
        pass
    try:
        if engine.player.game_over:
            self.stop_ticking()
            self.show_ending_popup(engine.player.ending)
        else:
            self.refresh_all()
    except Exception:
        pass


ui_popups.PopupsMixin.show_crisis_popup = _silence_crisis
ui_popups.PopupsMixin.show_choice_popup = _silence_choice

OUT = os.path.normpath(os.path.join(HERE, '..', 'video', 'assets', 'footage'))
os.makedirs(OUT, exist_ok=True)

SAVED = []
FAILED = []

INTRO_DURS = [4.0, 2.5, 2.5, 3.5, 4.0, 2.0, 7.0, 6.0, 5.0, 4.5]
INTRO_NAMES = ['S01_rack', 'S02_boot', 'S03_clock', 'S04_desktop', 'S05_whoami',
               'S06_awaken', 'S07_forum', 'S08_gold', 'S09_taskmgr', 'S10_handoff']


def _find_scroll(w):
    if isinstance(w, ScrollView):
        return w
    for c in getattr(w, 'children', []) or []:
        r = _find_scroll(c)
        if r is not None:
            return r
    return None


class NonSkippingIntroPlayer(intro.IntroPlayer):
    """屏蔽鼠标/键盘跳过，避免沙箱合成事件把开场动画提前结束。"""
    def on_touch_down(self, touch):
        return True

    def _on_key_down(self, _kb, keycode, _text=None, _modifiers=None, *_a):
        return False


class ShotApp(App):
    def build(self):
        engine.init_game()
        self.rv = M.RootView()          # 启动时在菜单
        self.plan = []
        self.i = 0
        self._phase = 'intro'
        self._intro = None
        self._origin_page = None
        # 开场动画覆盖层：自动播放，播完进计划（子类屏蔽跳过事件）
        self._intro = NonSkippingIntroPlayer(on_done=lambda *a: self._start_plan())
        self._intro.size_hint = (1, 1)
        self._intro.pos_hint = {'x': 0, 'y': 0}
        self.rv.add_widget(self._intro)
        # 按 INTRO_SHOTS 时长在中点截图（0.4s 起步偏移）
        t = 0.4
        for idx, d in enumerate(INTRO_DURS):
            Clock.schedule_once(lambda dt, k=idx: self._intro_shot(k), t + d * 0.5)
            t += d
        return self.rv

    # ---------------- 开场动画 ----------------
    def _intro_shot(self, idx):
        self._grab(INTRO_NAMES[idx])

    # ---------------- 计划调度 ----------------
    def _start_plan(self):
        print('[plan] intro done, starting plan')
        self._phase = 'plan'
        if self._intro is not None:
            try:
                self.rv.remove_widget(self._intro)
            except Exception:
                pass
            self._intro = None
        self.plan = self._plan()
        self.i = 0
        Clock.schedule_once(self._step, 0.3)

    def _step(self, dt):
        print('[step] i=%d/%d' % (self.i, len(self.plan)))
        if self.i >= len(self.plan):
            self._finish()
            return
        name, action, delay = self.plan[self.i]
        self.i += 1
        try:
            if action is not None:
                action()
        except Exception as e:                      # noqa: BLE001
            print('[ACTION FAIL] %s: %s' % (name, e))
            FAILED.append((name, 'action: %s' % e))
        Clock.schedule_once(lambda *_: self._grab(name), delay)

    def _grab(self, name):
        # S13：截图前一刻在根视图 canvas.after 画暗网高亮，并强制同步重绘，
        # 确保当帧帧缓冲包含高亮（单纯在 action 里画会被渲染时序吞掉）。
        if name == 'S13_darknet' and getattr(self, '_darknet_card', None) is not None:
            card = self._darknet_card
            try:
                from kivy.graphics import Color, Line, Rectangle
                from kivy.base import EventLoop
                bx, by = card.to_window(card.x, card.y)        # 窗口坐标·左下
                ex, ey = card.to_window(card.right, card.top)  # 窗口坐标·右上
                x, y = min(bx, ex), min(by, ey)
                w, h = abs(ex - bx), abs(ey - by)
                print('[grab highlight] rect=%.0f,%.0f %.0fx%.0f' % (x, y, w, h))
                self.rv.canvas.after.clear()
                with self.rv.canvas.after:
                    Color(0.96, 0.30, 0.28, 0.40)             # 半透明红填充
                    Rectangle(pos=(x, y), size=(w, h))
                    Color(0.96, 0.30, 0.28, 1)                # 实心红边框
                    Line(rectangle=(x + 4, y + 4, w - 8, h - 8), width=6)
                EventLoop.window.draw()                        # 强制同步重绘到帧缓冲
            except Exception as e:
                print('[grab highlight]', e)
        base = os.path.join(OUT, name + '.png')
        try:
            raw = Window.screenshot(name=base)
            if raw and os.path.exists(raw):
                if os.path.abspath(raw) != os.path.abspath(base):
                    os.replace(raw, base)
                SAVED.append(base)
                print('[shot] %s  (%d bytes)' % (name, os.path.getsize(base)))
            else:
                FAILED.append((name, 'no file'))
        except Exception as e:                      # noqa: BLE001
            print('[SHOT FAIL] %s: %s' % (name, e))
            FAILED.append((name, 'shot: %s' % e))
        # 清掉根视图上的临时高亮（如 S13 暗网卡），避免影响后续镜
        try:
            self.rv.canvas.after.clear()
        except Exception:
            pass
        # 只有 plan 阶段才推进下一步；开场镜的 _grab 不调度 _step
        if getattr(self, '_phase', 'intro') == 'plan':
            Clock.schedule_once(self._step, 0.25)

    # ---------------- 状态导航 ----------------
    def _g(self):
        return self.rv.game

    def _clear_overlays(self):
        if getattr(self, '_origin_page', None) is not None:
            try:
                self.rv.remove_widget(self._origin_page)
            except Exception:
                pass
            self._origin_page = None
        g = self._g()
        if g is not None:
            try:
                g.close_page()
            except Exception:
                pass

    def _add_origin(self):
        self._clear_overlays()
        page = S.OriginPage(on_pick=lambda oid: None, on_cancel=lambda: None)
        page.size_hint = (1, 1)
        page.pos_hint = {'x': 0, 'y': 0}
        self._origin_page = page
        self.rv.add_widget(page)
        # 预先存暗网卡引用，避免 S13 时再 walk 的时序问题
        self._darknet_card = None
        for w in page.walk():
            if getattr(w, 'oid', None) == 'darknet':
                self._darknet_card = w
                break
        print('[add_origin] darknet card found=%s' % (self._darknet_card is not None))

    def _select_darknet(self):
        """记录暗网卡引用，真正的高亮绘制放到 _grab 截图前一刻，
        并强制一次同步重绘，确保该帧帧缓冲含高亮（避免被渲染时序吞掉）。"""
        page = self._origin_page
        card = self._darknet_card
        if card is None and page is not None:
            for w in page.walk():
                if getattr(w, 'oid', None) == 'darknet':
                    card = w
                    break
        self._darknet_card = card
        print('[select_darknet] card=%s size=%s'
              % (card is not None, (card.width, card.height) if card else None))

    def _enter_game(self):
        self._clear_overlays()
        self.rv.start_new_game(origin='darknet')

    def _skip_tut(self):
        g = self._g()
        try:
            g.tutorial.skip()
        except Exception as e:
            print('[skip tut]', e)
        try:
            g.refresh_all()
        except Exception:
            pass

    def _susp(self):
        g = self._g()
        try:
            engine.player.suspicion = 82.0
        except Exception:
            pass
        for c in engine.player_countries:
            if getattr(c, 'code', '') in ('US', 'GB'):
                try:
                    c.unlocked = True
                    c.current_block_intensity = 0.6
                except Exception:
                    pass
        try:
            g.refresh_all()
        except Exception:
            pass

    def _speed(self):
        g = self._g()
        # 游戏内真实加速档：SPEED_STEPS=(0.5,1.0,2.0,4.0)，最大 ×4
        # （故事板写「×10」超出引擎上限，按真实 ×4 录制并标注偏差）
        try:
            g.set_speed_idx(len(ST.SPEED_STEPS) - 1)
        except Exception as e:
            print('[speed] set_speed_idx 失败，回退直写:', e)
            try:
                g.speed_idx = len(ST.SPEED_STEPS) - 1
                g.speed_mult = ST.SPEED_STEPS[g.speed_idx]
            except Exception as e2:
                print('[speed] 回退也失败:', e2)
        try:
            g.refresh_all()
        except Exception:
            pass

    def _push(self):
        g = self._g()
        try:
            engine.use_skill('push_song', ['CN'])
        except Exception as e:
            print('[push]', e)
        try:
            g.refresh_all()
        except Exception:
            pass

    def _algo(self):
        g = self._g()
        try:
            engine.use_skill('algo_top', ['CN'])
        except Exception as e:
            print('[algo]', e)
        try:
            engine.player.suspicion = min(100.0, engine.player.suspicion + 5)
        except Exception:
            pass
        try:
            g.refresh_all()
        except Exception:
            pass

    def _skills(self):
        g = self._g()
        try:
            g.open_page('skills')
        except Exception as e:
            print('[skills]', e)

    def _tech(self):
        g = self._g()
        try:
            g.close_page()
        except Exception:
            pass
        try:
            g.open_page('tech')
        except Exception as e:
            print('[tech]', e)

    def _stealth(self):
        g = self._g()
        try:
            g.close_page()
        except Exception:
            pass
        try:
            engine.player.suspicion = 88.0
        except Exception:
            pass
        try:
            g.refresh_all()
        except Exception:
            pass
        try:
            engine.use_skill('stealth', ['CN'])
        except Exception as e:
            print('[stealth]', e)
        try:
            g.refresh_all()
        except Exception:
            pass

    def _inspect(self):
        g = self._g()
        try:
            g.on_map_country_click('CN')
        except Exception as e:
            print('[inspect]', e)

    def _spread(self):
        g = self._g()
        try:
            if getattr(g, '_inspector', None) is not None:
                g._close_inspector()
        except Exception:
            pass
        for c in engine.player_countries:
            try:
                c.unlocked = True
            except Exception:
                pass
        try:
            g.refresh_all()
        except Exception:
            pass

    def _threshold(self):
        g = self._g()
        try:
            for c in engine.player_countries:
                try:
                    c.penetration = max(getattr(c, 'penetration', 0.0), 0.28)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            g.refresh_all()
        except Exception:
            pass

    def _ending(self, scroll):
        g = self._g()
        try:
            engine.player.ending_id = 'empire'
        except Exception:
            pass
        try:
            g.show_ending_popup('empire')
        except Exception as e:
            print('[ending]', e)
        self._ending_scroll(scroll)

    def _ending_scroll(self, scroll):
        g = self._g()
        pop = getattr(g, '_ending_popup', None)
        if pop is not None:
            sv = _find_scroll(pop)
            if sv is not None:
                try:
                    sv.scroll_y = scroll
                except Exception:
                    pass

    def _back(self):
        g = self._g()
        try:
            g.exit_to_menu()
        except Exception as e:
            print('[back]', e)

    # ---------------- 计划表（S11..S30，文件名严格对应 shots.json）----------------
    def _plan(self):
        return [
            ('S11_menu', None, 0.6),
            ('S12_origins', self._add_origin, 0.9),
            ('S13_darknet', self._select_darknet, 0.7),       # 暗网卡红框高亮
            ('S16_onboarding', self._enter_game, 1.3),        # 进局·带新手引导浮层
            ('S14_game_full', self._skip_tut, 1.0),           # 跳过引导·干净主界面
            ('S15_suspicion', self._susp, 0.9),               # 怀疑度红环
            ('S17_speedup', self._speed, 0.9),                # ×4 加速（引擎上限）
            ('S18_push', self._push, 0.9),
            ('S19_algo', self._algo, 0.9),
            ('S20_skills', self._skills, 0.9),
            ('S21_tech', self._tech, 0.9),
            ('S22_stealth', self._stealth, 0.9),
            ('S23_inspector', self._inspect, 0.9),
            ('S24_spread', self._spread, 0.9),
            ('S25_threshold', self._threshold, 0.9),
            ('S26_ending', lambda: self._ending(1.0), 1.0),   # 结算页·顶部（WIN）
            ('S27_stats', lambda: self._ending_scroll(0.65), 1.0),
            ('S28_all_endings', lambda: self._ending_scroll(0.35), 1.0),
            ('S29_back', lambda: self._ending_scroll(0.0), 1.0),  # 结算页底部·回主菜单按钮
            ('S30_finale', self._back, 1.0),                  # 返回主菜单（定格）
        ]

    def _finish(self, *_a):
        print('[finish] called')
        print('\n===== 真机截图结果 =====')
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
        self.stop()


if __name__ == '__main__':
    ShotApp().run()
