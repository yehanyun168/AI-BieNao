"""
main.py - Demo 入口（i18n + 20 国 + 6 技能 + 7 结局 + 20 成就）

v0.4 结构（对齐 design/ui_design_v0.4.html 的 14 屏）：
  AIBienaoApp
    └─ RootView                      主菜单 ↔ 游戏 切换容器
         ├─ MainMenu                 S01 启动页（左品牌区 + 右地图剪影 + 3 存档槽）
         └─ GameUI                   S02 主界面
              ├─ TopBar              顶部状态条 52px
              ├─ map_stage           地图舞台（地图铺满）
              │    ├─ 区域页签 HUD（左上）
              │    ├─ 图层切换 HUD（右上）
              │    ├─ 图例 HUD（左下）
              │    ├─ 指令栏 Rail（右侧居中，44px 达标）
              │    ├─ InspectorPanel S03 检视卡（点击国家左滑出）
              │    ├─ DropPreview    S04 投放预览（投放模式右下）
              │    ├─ LogDrawer      S14 事件日志（右侧滑出）
              │    └─ 准星层         S04 可投目标准星 + 标签
              ├─ SkillBar            底部技能带 92px
              └─ 覆盖页（按需 add/remove）
                   SkillPage S05 / TechPage S06 / AchPage S10
                   HelpPage S11 / SettingsPage S12 / 弹窗 S07·S08·S09

快捷键（F11 —— 计划书 8.3 节，v0.4 帮助页同源）：
  Space 暂停 · 1–6 选技能（进投放模式）· F 投放 · K 科技树 · A 成就
  Tab 切区域 · +/- 缩放 · F11 全屏 · F12 适配 · F1 帮助
  S/R 存/读档 · L 中英切换 · Esc 返回上一层 · Enter 确认投放
"""
from kivy.config import Config
Config.set('graphics', 'resizable', '1')
Config.set('graphics', 'width', '1680')
Config.set('graphics', 'height', '980')
Config.set('kivy', 'dpi', '144')
Config.set('kivy', 'dpi_pixmap', '256')
# Esc 交由游戏自己处理（逐层返回）；禁用 Kivy 默认「按 Esc 关闭窗口」，
# 否则任何键盘焦点丢失/异常场景下按 Esc 会整窗退出（= 直接退出游戏）。
Config.set('kivy', 'exit_on_escape', '0')
# 鼠标右键「红圈」根治：Kivy 的鼠标 provider 若带 ``multitouch_on_demand``，
# 右键会被当作一个 touch，并在落点画一个红色圆圈（左键点它 = 移除该 touch →
# 圆圈消失）。本游戏不需要右键交互，显式声明为纯 mouse，从源头禁掉该可视化。
Config.set('input', 'mouse', 'mouse')

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget

from pixel_ui import PixelLabel as Label   # 关闭字体 hinting，保持像素锐利


# ============================================================
# 字体注册（中文 + emoji 兼容）
# ============================================================
_FONT_REG = False


def _register_fonts() -> None:
    """注册中文字体并覆盖 Kivy 默认 Roboto（否则中文全是方框）"""
    global _FONT_REG
    if _FONT_REG:
        return
    _FONT_REG = True

    win_fonts = r"C:\Windows\Fonts"
    candidates = [
        ("MicrosoftYaHei", os.path.join(win_fonts, "msyh.ttc")),
        ("SimHei",         os.path.join(win_fonts, "simhei.ttf")),
        ("SimSun",         os.path.join(win_fonts, "simsun.ttc")),
        ("SegoeUI",        os.path.join(win_fonts, "segoeui.ttf")),
        ("SegoeUIEmoji",   os.path.join(win_fonts, "seguiemj.ttf")),
    ]
    registered = []
    primary_font = None
    for name, path in candidates:
        if os.path.exists(path):
            try:
                LabelBase.register(name=name, fn_regular=path)
                registered.append(name)
                if primary_font is None:
                    primary_font = path
            except Exception:
                pass

    if primary_font:
        try:
            LabelBase.register(name='Roboto', fn_regular=primary_font)
            print(f"[Fonts] Default font set: {primary_font}")
        except Exception as e:
            print(f"[Fonts] WARN: cannot override Roboto: {e}")

    if registered:
        print(f"[Fonts] Available: {', '.join(registered)}")


_register_fonts()

import i18n
from i18n import (t, set_lang, get_lang, LANG_ZH, LANG_EN)
import world_map
from world_map import WorldMap
from pixel_ui import (hex_rgba, add_pixel_border)   # 只留本文件实际使用的符号

import engine
import save_manager
import achievements as achievements_mod
import pixel_assets as PA

import ui_v4 as U
import ui_v4_screens as S
import sfx  # 音效管理器（失败安全；tools/gen_sfx.py 合成的 CC0 WAV）
from ui_v4 import (LegendChip, SaveSlotRow, mk_label, fit_width)
from tutorial import TutorialController   # P0-1 新手引导步骤机


# ============================================================
# v0.5.1 模块化拆分：装配层只 import，不再承载实现
# ------------------------------------------------------------
# 依赖方向（低 → 高）：
#   ui_shared → ui_v4 → ui_modal → ui_v4_screens → ui_hud
#   → {ui_pages, ui_drop, ui_popups, ui_session, ui_input} → main
# ============================================================
import ui_shared as ST
from ui_shared import COLORS, Panel, _update_window_title
from ui_modal import (make_button, make_modal, modal_header, auto_h_label,
                      hline)
from ui_hud import HudMixin
from ui_pages import PagesMixin
from ui_drop import DropMixin
from ui_popups import PopupsMixin
from ui_session import SessionMixin
from ui_input import InputMixin
from ui_commissions import CommissionMixin

_update_window_title()
Window.clearcolor = (0.051, 0.067, 0.090, 1)


# ============================================================
# 主界面（mixin 拼装：每个功能域一个混入，出错按域定位）
#   ui_hud.HudMixin      布局 / 区域 / 图层
#   ui_pages.PagesMixin  全屏页 / 检视卡 / 日志抽屉
#   ui_drop.DropMixin    投放模式
#   ui_popups.PopupsMixin 弹窗族 / 轻提示
#   ui_session.SessionMixin 存档 / 语言 / 暂停 / 缩放 / 全屏
#   ui_input.InputMixin  键盘 / 主循环 / 刷新 / 兼容别名
# ============================================================
class GameUI(CommissionMixin, HudMixin, PagesMixin, DropMixin, PopupsMixin,
             SessionMixin, InputMixin, FloatLayout):
    """S02 主界面：地图为绝对主体 + HUD 悬浮 + 右侧指令栏 + 底部技能带"""

    DESIGN_HEIGHT = 980.0
    TOP_H = 64          # 52 → 64：内嵌 44px 可交互控件 + 上下内边距
    SKILLBAR_H = 104

    def __init__(self, on_exit=None, **kwargs):
        super().__init__(**kwargs)
        self.on_exit = on_exit
        self.paused = False
        self.speed_idx: int = ST.CURRENT_SPEED_IDX
        self.speed_mult: float = ST.SPEED_STEPS[self.speed_idx]
        self._tick_deadline: float = Clock.get_time() + ST.BASE_TICK_SECONDS
        self._cd_clock = None
        self.user_scale = 1.0
        self._scalables = []
        self.scale = self._compute_scale()
        self.active_region = None
        self.active_layer = 'unlock'
        self.selected_skill = None            # 已确认投放的技能
        self.focus_country = None             # 检视卡当前国家
        self.stats = S.UiStats()
        self._last_growth = 0.0

        # 投放模式状态机（设计稿 S04）
        self.drop_mode = False
        self.drop_step = 0                    # 0 选技能 / 1 选目标 / 2 确认
        self.drop_skill = None
        self.drop_targets: list = []

        self._page = None                     # 当前全屏页
        self._inspector = None
        self._log_drawer = None
        self._reticles = []

        self._build_ui()
        self.refresh_all()
        self._apply_scale()
        Window.bind(on_resize=self._on_window_resize)
        self._reschedule_tick()
        self._reschedule_countdown()
        sfx.load_all()  # 启动时加载音效（失败安全：无音频后端则全部 no-op）
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)
        self.tutorial = TutorialController(self)   # P0-1 新手引导


# ============================================================
# 成就取数（MainMenu / GameUI 共用口径）
# ============================================================
def ach_snapshot(filt: str = 'all'):
    """按筛选条件汇总成就数据。

    Args:
        filt: ``'all'`` / ``'cond'`` / ``'evt'`` / ``'miss'``（仅看未达成）。

    Returns:
        tuple: ``(cells, got, total, cond_got, cond_total, evt_got, evt_total, nearest)``
            cells 元素为 ``(icon, name, desc, got, is_event)``。
    """
    lang = get_lang()
    p = engine.player
    unlocked = getattr(p, 'achievements', set()) if p is not None else set()
    cond = list(achievements_mod.ACHIEVEMENTS)
    evt = list(achievements_mod.EVENT_ACHIEVEMENTS.values())
    cond_got = sum(1 for a in cond if a.ach_id in unlocked)
    evt_got = sum(1 for a in evt if a.ach_id in unlocked)

    if filt == 'cond':
        items = [(a, False) for a in cond]
    elif filt == 'evt':
        items = [(a, True) for a in evt]
    else:
        items = [(a, False) for a in cond] + [(a, True) for a in evt]

    cells = []
    for a, is_evt in items:
        got = a.ach_id in unlocked
        if filt == 'miss' and got:
            continue
        icon = (a.icon or a.ach_id[:1]).strip() or '·'
        cells.append((icon, a.name(lang), a.desc(lang)[:26], got, is_evt))

    try:
        ctx = engine.build_achievement_context()
    except Exception:
        ctx = None
    nearest = []
    for a in cond:
        if a.ach_id in unlocked:
            continue
        try:
            ok = bool(a.condition(ctx)) if (a.condition and ctx) else False
        except Exception:
            ok = False
        nearest.append((a.name(lang), '✓' if ok else '…'))

    return (cells, cond_got + evt_got, len(cond) + len(evt),
            cond_got, len(cond), evt_got, len(evt), nearest[:3])


def read_slot_rows(active_idx: int = 0):
    """读取 3 个存档槽的摘要（不依赖 GameUI 实例）。"""
    import json as _json
    rows = []
    for i, name in enumerate(('slot1', 'slot2', 'slot3')):
        title = t('slot_name_fmt').format(n=f"{i + 1:02d}")
        path = os.path.join(save_manager.SAVE_DIR, f'{name}.json')
        summary = t('slot_empty')
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    data = _json.load(f)
                pl = data.get('player', {})
                unlocked = sum(1 for c in data.get('countries', [])
                               if c.get('unlocked'))
                if pl.get('game_over'):
                    summary = f"{t('slot_dead')} · {t('stats_tick')} {pl.get('tick_count', 0)}"
                else:
                    dl = sum(c.get('downloads_m', 0) for c in data.get('countries', []))
                    summary = t('slot_summary').format(
                        tick=pl.get('tick_count', 0),
                        pen=f"{dl / 7480 * 100:.2f}", n=unlocked)
            except Exception:
                summary = t('slot_empty')
        rows.append((title, summary, i == active_idx))
    return rows


def newest_save_path():
    """返回最近修改的存档路径（无存档 → None）。"""
    best, best_t = None, -1.0
    for name in ('slot1', 'slot2', 'slot3'):
        path = os.path.join(save_manager.SAVE_DIR, f'{name}.json')
        if os.path.exists(path):
            mt = os.path.getmtime(path)
            if mt > best_t:
                best, best_t = path, mt
    return best


# ============================================================
# S01 主菜单（F01 启动页）
# ============================================================
class _MenuSlot(SaveSlotRow):
    """可点选的存档槽行（设计稿 .slotrow）。"""

    def __init__(self, title: str, summary: str, on_pick=None,
                 active: bool = False, **kwargs):
        super().__init__(title, summary, (), active, **kwargs)
        self._on_pick = on_pick

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self._on_pick:
            self._on_pick()
            return True
        return super().on_touch_down(touch)


class MainMenu(FloatLayout):
    """S01 启动页：左品牌与操作区 + 右像素世界地图剪影（只读）。

    Args:
        on_start: 「开始新游戏」回调。
        on_continue: 「继续游戏」回调；无存档时按钮禁用。
        on_exit: 「退出」回调。
    """

    DESIGN_W, DESIGN_H = 1280.0, 720.0
    LEFT_W = 760.0 / 1280.0          # 59.375%
    BTN_H = 44                        # 触控下限（设计稿 §1.1）
    LOGO_FS, SUB_FS, VER_FS = 34, 15, 11
    BTN_FS, HINT_FS = 13, 11
    SLOT_H = 34

    # 剪影示例状态（设计稿：已解锁 11 / 选中 1 / 阻止 1 / 未解锁 7）
    SIL_ON = ('US', 'CA', 'MX', 'BR', 'AR', 'GB', 'FR', 'DE', 'IT', 'RU', 'JP')

    def __init__(self, on_start=None, on_continue=None, on_exit=None,
                 on_start_new_slot=None, **kwargs):
        super().__init__(**kwargs)
        self.on_start = on_start
        self.on_continue = on_continue
        self.on_exit = on_exit
        self.on_start_new_slot = on_start_new_slot
        self.user_scale = 1.0
        self._scalables = []
        self._overlay = None
        self._sel_slot = 1                # 默认选中槽位 02（设计稿）
        self.scale = self._compute_scale()
        self._build()
        self._apply_scale()
        Window.bind(on_resize=self._on_resize)
        self._keyboard = None
        try:
            self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
            if self._keyboard is not None:
                self._keyboard.bind(on_key_down=self._on_key_down)
        except Exception:
            self._keyboard = None

    # --------------------------------------------------------
    # 缩放
    # --------------------------------------------------------
    def _compute_scale(self) -> float:
        w = Window.width or self.DESIGN_W
        h = Window.height or self.DESIGN_H
        base = min(w / self.DESIGN_W, h / self.DESIGN_H)
        return min(max(base, 0.62), 1.85) * self.user_scale

    def _reg(self, widget, font=None, height=None):
        if font is not None:
            self._scalables.append((widget, 'font_size', float(font)))
        if height is not None:
            self._scalables.append((widget, 'height', float(height)))
        return widget

    def _on_resize(self, *_a) -> None:
        self._apply_scale()

    def _apply_scale(self) -> None:
        self.scale = self._compute_scale()
        for widget, attr, base in self._scalables:
            try:
                setattr(widget, attr, base * self.scale)
            except Exception:
                pass
        left = getattr(self, '_left', None)
        if left is not None:
            left.padding = (int(48 * self.scale), int(34 * self.scale))
        for widget, _a, _b in self._scalables:
            fn = getattr(widget, 'refresh_scale', None)
            if callable(fn):
                try:
                    fn(self.scale)
                except Exception:
                    pass
        if isinstance(self._overlay, S.SettingsPage):
            self._overlay.set_zoom_text(f"×{self.user_scale:.2f}")

    def rebuild(self) -> None:
        """语言切换后整页重建（文案全在控件上）。"""
        keep_overlay = self._overlay is not None
        if keep_overlay:
            self._close_overlay()
        self._build()
        self._apply_scale()

    # --------------------------------------------------------
    # 布局
    # --------------------------------------------------------
    def _build(self) -> None:
        self.clear_widgets()
        self._scalables = []
        root = BoxLayout(orientation='horizontal', spacing=0, padding=0)
        self.add_widget(root)

        # ---- 左：品牌与操作区 ----
        left = BoxLayout(orientation='vertical', spacing=0, padding=(48, 34))
        left.size_hint_x = self.LEFT_W
        self._left = left
        left.add_widget(Widget())

        logo = self._reg(mk_label(f"[b]{t('app_title')}[/b]", font_size=self.LOGO_FS,
                                  color=COLORS['cyan'], size_hint_y=None, height=46,
                                  markup=True),
                         font=self.LOGO_FS, height=46)
        left.add_widget(logo)
        sub = self._reg(mk_label(t('menu_brand_sub'), font_size=self.SUB_FS,
                                 color=COLORS['text_dim'], size_hint_y=None, height=22),
                        font=self.SUB_FS, height=22)
        left.add_widget(sub)
        ver = self._reg(mk_label(t('menu_brand_ver'), font_size=self.VER_FS,
                                 color=COLORS['text_mute'], size_hint_y=None, height=18),
                        font=self.VER_FS, height=18)
        left.add_widget(ver)
        left.add_widget(Widget(size_hint_y=None, height=int(26 * self.scale)))

        # 主按钮（5 枚）
        has_save = newest_save_path() is not None
        slot_txt = t('slot_name_fmt').format(n=f"{self._sel_slot + 1:02d}")
        ach_total = len(achievements_mod.ALL_BY_ID)
        ach_got = len(getattr(engine.player, 'achievements', set())) if engine.player else 0
        btns = [
            (f"{U.SYM['play']} {t('menu_start')}", 'primary', self._fire_start, True),
            (f"⏵ {t('menu_continue_slot').format(slot=slot_txt)}", 'plain',
             self._fire_continue, has_save),
            (t('menu_settings'), 'plain', self._open_settings, True),
            (f"{t('menu_achievements')}  {ach_got} / {ach_total}", 'plain',
             self._open_ach, True),
            (f"{U.SYM['close']} {t('quit_button')}", 'danger', self._fire_exit, True),
        ]
        for text, tone, cb, enabled in btns:
            left.add_widget(self._menu_btn(text, tone, cb, enabled))
            left.add_widget(Widget(size_hint_y=None, height=int(8 * self.scale)))

        left.add_widget(Widget(size_hint_y=None, height=int(8 * self.scale)))
        left.add_widget(self._lang_row())
        left.add_widget(Widget(size_hint_y=None, height=int(14 * self.scale)))

        # 3 个存档槽
        for i, (title, summary, active) in enumerate(read_slot_rows(self._sel_slot)):
            row = _MenuSlot(title, summary,
                            on_pick=lambda k=i: self._slot_pick(k), active=active,
                            height=self.SLOT_H)
            self._reg(row, height=self.SLOT_H)
            left.add_widget(row)
            left.add_widget(Widget(size_hint_y=None, height=int(6 * self.scale)))

        left.add_widget(Widget())
        root.add_widget(left)

        # ---- 右：只读像素地图剪影 ----
        right = Panel(bg=hex_rgba('#0d1117'), border_color=COLORS['border_2'])
        right.size_hint_x = 1.0 - self.LEFT_W
        self.sil_map = WorldMap()
        self.sil_map.size_hint = (1, 1)
        self.sil_map.pos_hint = {'x': 0, 'y': 0}
        states = {c: 'lk' for c in PA.OWNER_CODES}
        for c in self.SIL_ON:
            if c in states:
                states[c] = 'on'
        states['CN'] = 'sel'
        states['KR'] = 'blk'
        self.sil_map.set_country_states(states)
        self.sil_map.set_selected('CN')
        self.sil_map._on_select = None            # 只读，不可点
        right.add_widget(self.sil_map)

        legend = Panel(bg=(0.051, 0.067, 0.090, 0.92),
                       border_color=COLORS['border_2'])
        legend.size_hint = (1, None)
        legend.height = 26
        lrow = BoxLayout(orientation='horizontal', spacing=10, padding=(8, 3))
        lrow.pos_hint = {'x': 0, 'y': 0}
        lrow.size_hint = (1, 1)
        counts = self._legend_counts(states)
        for key in ('on', 'sel', 'blk', 'lk'):
            chip = LegendChip(world_map.STATE_FILL[key], world_map.STATE_EDGE[key],
                              f"{t('legend_' + key)} {counts[key]}")
            chip.size_hint = (1, 1)
            lrow.add_widget(chip)
        legend.add_widget(lrow)
        right.add_widget(legend)
        root.add_widget(right)

        # 图例条贴底（right 是 FloatLayout，用绝对坐标定位）
        def _sync_legend(*_a):
            legend.height = int(26 * self.scale)
            legend.y = right.y + int(8 * self.scale)
            legend.x = right.x + int(8 * self.scale)
            legend.width = max(right.width - int(16 * self.scale), 10)
        right.bind(pos=_sync_legend, size=_sync_legend)
        self._sync_legend = _sync_legend
        Clock.schedule_once(_sync_legend, 0)

    @staticmethod
    def _legend_counts(states) -> dict:
        out = {'on': 0, 'sel': 0, 'blk': 0, 'lk': 0}
        for c in PA.OWNER_CODES:
            out[states.get(c, 'lk')] = out.get(states.get(c, 'lk'), 0) + 1
        return out

    def _menu_btn(self, text: str, tone: str, cb, enabled: bool = True) -> Button:
        bg = {'primary': (0.078, 0.188, 0.173, 1),
              'danger': (0.227, 0.118, 0.118, 1)}.get(tone, list(COLORS['panel_2']))
        bc = {'primary': COLORS['cyan'], 'danger': COLORS['red']}.get(tone, COLORS['border_2'])
        fc = {'primary': COLORS['cyan'], 'danger': COLORS['red']}.get(tone, COLORS['text'])
        b = Button(text=text, font_size=self.BTN_FS, size_hint_y=None,
                   height=self.BTN_H, halign='left', valign='middle',
                   background_normal='', background_color=list(bg))
        b.color = fc
        add_pixel_border(b, color=bc)
        b.bind(size=lambda i, v: setattr(i, 'text_size', (max(v[0] - 26, 10), v[1])))
        if enabled and cb:
            b.bind(on_release=lambda *_: cb())
        else:
            b.disabled = True
            b.opacity = 0.45               # 设计稿：禁用态 opacity .45
        self._reg(b, font=self.BTN_FS, height=self.BTN_H)
        return b

    def _lang_row(self) -> BoxLayout:
        row = BoxLayout(orientation='horizontal', spacing=4,
                        size_hint_y=None, height=18)
        self._reg(row, height=18)
        hint = mk_label(t('menu_hint2'), font_size=self.HINT_FS,
                        color=COLORS['text_mute'], size_hint_x=None)
        fit_width(hint, pad=6)
        self._reg(hint, font=self.HINT_FS)
        row.add_widget(hint)
        lang = get_lang()
        for key, txt in ((LANG_ZH, t('lang_zh')), (LANG_EN, t('lang_en'))):
            lbl = mk_label(txt, font_size=self.HINT_FS,
                           color=COLORS['cyan'] if lang == key else COLORS['text_mute'],
                           size_hint_x=None)
            fit_width(lbl, pad=6)
            self._reg(lbl, font=self.HINT_FS)
            row.add_widget(lbl)
            if key == LANG_ZH:
                sl = mk_label(' / ', font_size=self.HINT_FS,
                              color=COLORS['text_mute'], size_hint_x=None)
                fit_width(sl, pad=2)
                self._reg(sl, font=self.HINT_FS)
                row.add_widget(sl)
        row.add_widget(Widget())
        return row

    # --------------------------------------------------------
    # 动作
    # --------------------------------------------------------
    def _pick_slot(self, idx: int) -> None:
        self._sel_slot = idx
        self.rebuild()

    def _fire_start(self) -> None:
        if callable(self.on_start):
            self.on_start()

    def _fire_continue(self) -> None:
        path = newest_save_path()
        if path and callable(self.on_continue):
            self.on_continue(path)

    def _fire_exit(self) -> None:
        if callable(self.on_exit):
            self.on_exit()

    def _scale_delta(self, d: float) -> None:
        if d == 0.0:
            self.user_scale = 1.0
        else:
            self.user_scale = min(max(self.user_scale + d, 0.70), 1.60)
        self._apply_scale()

    def _set_speed_idx(self, i: int) -> None:
        """主菜单设置浮层：只更新全局速度档，进游戏时 GameUI 读取。"""
        ST.CURRENT_SPEED_IDX = max(0, min(int(i), len(ST.SPEED_STEPS) - 1))

    def _set_motion_idx(self, i: int) -> None:
        ST.REDUCE_MOTION = bool(int(i))

    def _set_a11y_idx(self, i: int) -> None:
        ST.A11Y_SHAPES = bool(int(i))

    def _set_sound_idx(self, i: int) -> None:
        """主菜单设置浮层：音效开关（进游戏时 GameUI 读取 sfx.SFX_ON）。"""
        sfx.set_enabled(bool(int(i)))

    # --------------------------------------------------------
    # 浮层页（设置 / 成就 / 帮助）
    # --------------------------------------------------------
    def _open_overlay(self, page) -> None:
        self._close_overlay()
        page.size_hint = (0.90, 0.90)
        page.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        self._overlay = page
        self.add_widget(page)

    def _close_overlay(self) -> None:
        if self._overlay is not None:
            try:
                self.remove_widget(self._overlay)
            except Exception:
                pass
            self._overlay = None

    def _open_settings(self) -> None:
        page = S.SettingsPage(
            on_lang=self._set_lang_idx,
            on_scale=self._scale_delta,
            on_speed=self._set_speed_idx,
            on_grid=lambda i: self.sil_map.set_grid_mode(i),
            on_a11y=self._set_a11y_idx,
            on_motion=self._set_motion_idx,
            on_sound=self._set_sound_idx,
            slot_actions=self._slot_actions,
            on_reset=self._reset_settings)
        page.rebuild_slots(read_slot_rows(self._sel_slot))
        page.set_zoom_text(f"×{self.user_scale:.2f}")
        page.set_back_button(t('k_esc'), self._close_overlay)
        self._open_overlay(page)

    def _slot_actions(self, title: str):
        """主菜单设置浮层：按槽位生成动作按钮。

        - 空槽：仅「在此槽开新游戏」（无覆盖风险，无需确认）。
        - 已有档：「读取」+「覆盖并开新游戏」（覆盖需确认弹窗）。
        """
        import re as _re
        m = _re.search(r'(\d+)', title)
        idx = int(m.group(1)) if m else 1
        slot = f'slot{idx}.json'
        path = os.path.join(save_manager.SAVE_DIR, slot)
        if os.path.exists(path):
            return [
                (t('load_button'), 'plain',
                 lambda p=path: self._load_and_start(p)),
                (t('slot_overwrite'), 'danger',
                 lambda p=path: self._confirm_overwrite(p)),
            ]
        return [
            (t('slot_new_game'), 'primary',
             lambda p=path: self._start_new_on_slot(p)),
        ]

    def _load_and_start(self, path: str) -> None:
        if callable(self.on_continue):
            self.on_continue(path)

    def _start_new_on_slot(self, path: str) -> None:
        """在指定槽位开新游戏（来自设置浮层的「新游戏」按钮或主菜单行点击）。"""
        self._close_overlay()                 # 关设置浮层（若有）
        if callable(self.on_start_new_slot):
            self.on_start_new_slot(path)

    def _confirm_overwrite(self, path: str) -> None:
        """覆盖确认弹窗：「当前操作会覆盖当前存档，确定继续吗？」。"""
        body = BoxLayout(orientation='vertical', spacing=12, padding=(16, 14))
        body.add_widget(modal_header('!', t('save_overwrite_title')))
        body.add_widget(hline())
        body.add_widget(auto_h_label(t('save_overwrite_body'), U.FS_BODY,
                                     color=COLORS['text']))
        row = BoxLayout(orientation='horizontal', spacing=12,
                        size_hint_y=None, height=50)
        cancel = make_button(t('save_overwrite_cancel'), font_size=U.FS_BODY,
                             height=50, bg=COLORS['panel_light'],
                             on_release=lambda *_: pop.dismiss())
        ok = make_button(t('save_overwrite_confirm'), font_size=U.FS_BODY,
                         height=50, bg=(0.227, 0.118, 0.118, 1),
                         on_release=lambda *_: (pop.dismiss(),
                                                self._start_new_on_slot(path)))
        row.add_widget(cancel)
        row.add_widget(ok)
        body.add_widget(row)
        pop = make_modal(body, size_hint=(0.5, 0.62), skin='lose',
                         close_on_outside=True)
        pop.open()

    def _slot_pick(self, k: int) -> None:
        """主菜单槽位行点击 / 键盘选中后回车：执行该槽主行为。

        - 空槽 → 直接开新游戏；
        - 已有档 → 弹覆盖确认框。
        """
        self._pick_slot(k)
        name = ('slot1', 'slot2', 'slot3')[k]
        path = os.path.join(save_manager.SAVE_DIR, f'{name}.json')
        if os.path.exists(path):
            self._confirm_overwrite(path)
        else:
            self._start_new_on_slot(path)

    def _reset_settings(self) -> None:
        self.user_scale = 1.0
        self.sil_map.set_grid_mode(1)
        self._apply_scale()

    def _set_lang_idx(self, idx: int) -> None:
        set_lang(LANG_EN if idx == 1 else LANG_ZH)
        _update_window_title()
        self.rebuild()

    def _fill_ach(self, filt: str, page=None) -> None:
        page = page if isinstance(page, S.AchPage) else self._overlay
        if not isinstance(page, S.AchPage):
            return
        page.set_filter_visual('all' if filt == 'miss' else filt)
        cells, got, total, cg, ct, eg, et, near = ach_snapshot(filt)
        page.rebuild(cells, got, total, cg, ct, eg, et, 0, near)

    def _open_ach(self) -> None:
        page = S.AchPage(on_filter=lambda k: self._fill_ach(k))
        self._fill_ach('all', page)
        page.set_back_button(t('k_esc'), self._close_overlay)
        self._open_overlay(page)

    def _open_help(self) -> None:
        page = S.HelpPage()
        page.set_back_button(t('k_esc'), self._close_overlay)
        self._open_overlay(page)

    # --------------------------------------------------------
    # 键盘
    # --------------------------------------------------------
    def _keyboard_closed(self) -> None:
        if getattr(self, '_keyboard', None) is not None:
            self._keyboard.unbind(on_key_down=self._on_key_down)
            self._keyboard = None

    def _on_key_down(self, keyboard, keycode, text, modifiers) -> bool:
        key = keycode[1]
        if self._overlay is not None:
            if key == 'escape':
                self._close_overlay()
                return True
            return False
        if key == 'escape':
            self._fire_exit()
            return True
        if key in ('enter', 'numpadenter'):
            self._slot_pick(self._sel_slot)
            return True
        if key == 'up':
            self._pick_slot(max(self._sel_slot - 1, 0))
            return True
        if key == 'down':
            self._pick_slot(min(self._sel_slot + 1, 2))
            return True
        if key == 'l':
            self._set_lang_idx(1 if get_lang() == LANG_ZH else 0)
            return True
        if key == 'c':
            self._fire_continue()
            return True
        if key == 'f1':
            self._open_help()
            return True
        return False


# ============================================================
# RootView —— 主菜单 ↔ 游戏 切换容器
# ============================================================
class RootView(FloatLayout):
    """主菜单与游戏主界面之间的切换容器（设计稿 S01 ↔ S02）。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.game = None
        self.menu = None
        self.show_menu()

    def show_menu(self) -> None:
        """回到 S01 主菜单。"""
        if self.game is not None:
            try:
                self.game.stop_ticking()
            except Exception:
                pass
            try:
                self.game._keyboard_closed()
            except Exception:
                pass
            self.game = None
        self.clear_widgets()
        self.menu = MainMenu(on_start=self.start_new_game,
                             on_continue=self.start_load_game,
                             on_start_new_slot=self.start_new_game_on_slot,
                             on_exit=self.quit_app)
        self.add_widget(self.menu)

    def start_new_game(self) -> None:
        """S01 → S02：全新一局。"""
        engine.init_game()
        self._enter_game()

    def start_load_game(self, path: str) -> None:
        """S01 → S02：读档进入。"""
        save_manager.load(path)
        self._enter_game()

    def start_new_game_on_slot(self, path: str) -> None:
        """S01 → S02：在指定槽位开新游戏。

        先把 engine 重置到初始态，再把初始进度写入该槽（覆盖旧档），
        随后进入游戏。对应「点击已有存档 → 覆盖并开新游戏」流程。
        """
        engine.init_game()
        save_manager.save(path)
        self._enter_game()

    def _enter_game(self) -> None:
        self.clear_widgets()
        if self.menu is not None:
            try:
                self.menu._keyboard_closed()
            except Exception:
                pass
        self.menu = None
        self.game = GameUI(on_exit=self.show_menu)
        self.add_widget(self.game)
        # 新游戏进入后延迟触发新手引导（等首帧布局完成，to_window 才有正确坐标）
        Clock.schedule_once(lambda dt: self.game.tutorial.maybe_start(), 0.3)

    def quit_app(self) -> None:
        app = App.get_running_app()
        if app is not None:
            app.stop()


# ============================================================
# App 入口
# ============================================================
class AIBienaoApp(App):
    """《AI 别闹》v2 收口版 —— v0.4 界面（对齐 design/ui_design_v0.4.html）。"""

    def build(self):
        _register_fonts()
        engine.init_game()
        self.root_view = RootView()
        return self.root_view

    def on_start(self) -> None:
        """启动后屏蔽鼠标右键触摸：Kivy 在部分构建下会把右键当作一个 touch
        并在落点画红色圆圈（左键点它 = 移除该 touch → 圆圈消失）。本游戏
        无右键交互需求，直接在窗口层把右键 touch 吞掉，从源头杜绝红圈。
        """
        try:
            Window.bind(on_touch_down=self._swallow_right_click)
        except Exception:
            pass

    @staticmethod
    def _swallow_right_click(_win, touch) -> bool:
        # 只拦截右键；左键 / 触摸正常下传。返回 True = 吞掉该事件。
        return getattr(touch, 'button', None) == 'right'

    def on_stop(self) -> None:
        rv = getattr(self, 'root_view', None)
        if rv is not None and rv.game is not None:
            try:
                rv.game.stop_ticking()
            except Exception:
                pass


if __name__ == '__main__':
    AIBienaoApp().run()
