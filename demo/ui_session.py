"""
ui_session.py - SessionMixin（拆分自 main.py）

会话级操作：存/读/删档、语言切换与界面重建、暂停/节奏与倒计时、
速度档/动效/色盲/音效设置、全屏、退回主菜单与重开一局。
"""
import os

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.widget import Widget

import i18n
from i18n import (t, set_lang, get_lang, get_country_name, get_continent_name,
                  LANG_ZH, LANG_EN)
import engine
import save_manager
import sfx
import ui_v4 as U
import ui_v4_screens as S
import ui_shared as ST
from ui_shared import COLORS, Panel, _update_window_title
from ui_modal import (make_button, make_modal, modal_header, auto_h_label,
                      hline, _purge_lingering_modals, _wire_close)
from ui_hud import LANG_CHIP_TAG, LAYER_KEYS, LAYER_LABEL_KEY, REGIONS
from ui_v4 import (PxChip, RailButton, RegionTab, SegSwitch, LegendChip,
                   ChipRow, SkillBarCard, Steps, Reticle, TgtLabel, StatsGrid,
                   StrokePanel, SaveSlotRow, mk_label, ST_FILL, ST_EDGE,
                   MIN_TOUCH, fit_width)


# ============================================================
# SessionMixin —— GameUI 的会话操作（存档/语言/暂停/缩放）
# ============================================================
class SessionMixin:
    def _compute_scale(self) -> float:
        h = Window.height or self.DESIGN_HEIGHT
        base = min(max(h / self.DESIGN_HEIGHT, 0.68), 1.45)
        return base * getattr(self, 'user_scale', 1.0)

    def _register(self, widget, font=None, height=None):
        if font is not None:
            self._scalables.append((widget, 'font_size', float(font)))
        if height is not None:
            self._scalables.append((widget, 'height', float(height)))
        if font is None and height is None:
            # 仅登记：让它进入全树 refresh_scale 遍历（自绘控件用自己的 scale）
            self._scalables.append((widget, 'scale', 1.0))
        return widget

    def _apply_scale(self) -> None:
        self.scale = self._compute_scale()
        for widget, attr, base in self._scalables:
            try:
                setattr(widget, attr, base * self.scale)
            except Exception:
                pass
        # 全树刷新：任何实现了 refresh_scale 的控件按当前 scale 自排
        # （比逐个登记更可靠 —— 新增控件不会漏）
        self._walk_refresh(self)

    def _walk_refresh(self, widget, depth: int = 0) -> None:
        if depth > 12:
            return
        fn = getattr(widget, 'refresh_scale', None)
        if callable(fn):
            try:
                fn(self.scale)
            except Exception:
                pass
        for ch in getattr(widget, 'children', ()) or ():
            self._walk_refresh(ch, depth + 1)

    def _on_window_resize(self, window, w, h) -> None:
        self._apply_scale()

    def _zoom_btn(self, delta: float) -> None:
        if delta == 0.0:
            self.user_scale = 1.0
        else:
            self.user_scale = min(max(self.user_scale + delta, 0.70), 1.60)
        self._apply_scale()
        self._notify(f"{t('scale_label')} ×{self.user_scale:.2f}")

    def adjust_scale(self, delta: float) -> None:
        self._zoom_btn(delta)

    # ========================================================
    # 区域高亮（设计稿 S02 左上 HUD）
    # ========================================================
    REGION_KEYS = [k for k, _ in REGIONS]



    def toggle_fullscreen(self) -> None:
        Window.fullscreen = 'auto' if not Window.fullscreen else False
        Clock.schedule_once(lambda *_: self._apply_scale(), 0.2)



    def _save_slot(self, slot: str) -> None:
        path = os.path.join(save_manager.SAVE_DIR, slot)
        save_manager.save(path)
        self._notify(f"{t('save_button')} → {slot}")
        if isinstance(self._page, S.SettingsPage):
            self._page.rebuild_slots(self._slot_rows())

    def _load_slot(self, slot: str) -> None:
        path = os.path.join(save_manager.SAVE_DIR, slot)
        if save_manager.load(path):
            self._notify(t('load_ok'))
            self.close_page()
            self.paused = False
            self.stop_ticking()
            self._reschedule_tick()
            self.refresh_all()
        else:
            self._notify(t('load_fail'))

    def _delete_slot(self, slot: str) -> None:
        path = os.path.join(save_manager.SAVE_DIR, slot)
        if os.path.exists(path):
            os.remove(path)
            self._notify(f"{U.SYM['close']} {slot}")
        if isinstance(self._page, S.SettingsPage):
            self._page.rebuild_slots(self._slot_rows())



    def do_save(self) -> None:
        path = save_manager.save()
        self._notify(f"{t('save_button')} → {os.path.basename(path)}")

    def do_load(self) -> None:
        if save_manager.load():
            self._notify(t('load_ok'))
            self.paused = False
            self.stop_ticking()
            self._reschedule_tick()
            self.refresh_all()
        else:
            self._notify(t('load_fail'))

    def toggle_lang(self) -> None:
        set_lang(LANG_EN if get_lang() == LANG_ZH else LANG_ZH)
        self._rebuild_lang()

    def _rebuild_lang(self) -> None:
        """切换语言后重建所有带文案的控件"""
        _update_window_title()
        self.lang_switch.set_tone('plain', LANG_CHIP_TAG[get_lang()])
        self.help_chip.set_tone('plain', '? ' + t('rail_help'))
        for sid, card in self.skill_cards.items():
            card.set_texts(self._skill_name(sid), self._skill_desc(sid))
        for sid, btn in self.rail.buttons.items():
            pass
        self.lbl_logo.text = f"[b]{t('app_title')}[/b]"
        self.lbl_grey.text = t('drop_grey_note')
        self.drop_hint.set_tone('on', t('drop_click_hint'))
        self.layer_hud.seg.set_options([t(LAYER_LABEL_KEY[k]) for k in LAYER_KEYS])
        self.steps.set_labels([t('drop_step1'), t('drop_step2'), t('drop_step3')])
        self.btn_pause.text = f"{U.SYM['pause']} {t('quick_pause')}"
        self._sync_region_tabs()
        self._apply_layer()
        self.refresh_all()

    def toggle_pause(self) -> None:
        if self.paused:
            self.paused = False
            self._reschedule_tick()
        else:
            self.paused = True
            self.stop_ticking()
        self.refresh_all()

    def stop_ticking(self) -> None:
        ev = getattr(self, 'tick_event', None)
        if ev is not None and ev.is_triggered:
            ev.cancel()

    # ---- 节奏系统（P0-1：所有 tick 重建统一走这里）----
    def _tick_interval(self) -> float:
        """当前速度档下的 tick 间隔（秒）= BASE_TICK_SECONDS / speed_mult。"""
        return ST.BASE_TICK_SECONDS / self.speed_mult

    def _reschedule_tick(self) -> None:
        """取消旧调度并按当前速度/暂停状态重建。"""
        self.stop_ticking()
        if not self.paused and not engine.player.game_over:
            self.tick_event = Clock.schedule_interval(self.game_tick, self._tick_interval())
        self._tick_deadline = Clock.get_time() + self._tick_interval()

    def _update_countdown(self, dt: float) -> None:
        """倒计时 UI：剩余秒数 + 细进度条（P0-4）。"""
        if getattr(self, 'cd_bar', None) is None:
            return
        remaining = max(0.0, self._tick_deadline - Clock.get_time())
        interval = max(0.001, self._tick_interval())
        frac = remaining / interval if not self.paused else 1.0
        self.cd_bar.set_value(frac)
        if self.cd_label is not None:
            if self.paused:
                self.cd_label.text = f"[color={U.MK['dim']}]{t('pause')}[/color]"
            else:
                self.cd_label.text = (f"[color={U.MK['cyan']}]"
                                      f"{int(remaining + 0.999)}s[/color]")

    def set_speed_idx(self, i: int) -> None:
        """设置速度档位（0=×0.5 … 3=×4），越界自动 clamp，立即生效。"""
        self.speed_idx = max(0, min(int(i), len(ST.SPEED_STEPS) - 1))
        self.speed_mult = ST.SPEED_STEPS[self.speed_idx]
        ST.CURRENT_SPEED_IDX = self.speed_idx
        self._reschedule_tick()
        self.refresh_all()

    def _set_motion_idx(self, i: int) -> None:
        """动效开关：0=完整 / 1=减弱（P0-5）。"""
        ST.REDUCE_MOTION = bool(int(i))
        self._reschedule_countdown()

    def _cd_interval(self) -> float:
        """倒计时刷新间隔：动效减弱时降到 1.0s（减少每帧重绘 = 缓解卡顿）。"""
        return 1.0 if ST.REDUCE_MOTION else 0.25

    def _reschedule_countdown(self) -> None:
        """按当前动效偏好重建倒计时刷新时钟。"""
        if getattr(self, '_cd_clock', None) is not None:
            self._cd_clock.cancel()
        self._cd_clock = Clock.schedule_interval(
            self._update_countdown, self._cd_interval())

    def _set_a11y_idx(self, i: int) -> None:
        """色盲辅助开关：0=关 / 1=开（P0-5）。"""
        ST.A11Y_SHAPES = bool(int(i))
        if getattr(self, 'legend_hud', None) is not None:
            self.legend_hud.apply_a11y()

    def _set_sound_idx(self, i: int) -> None:
        """音效开关：0=关 / 1=开（P0-5）。"""
        sfx.set_enabled(bool(int(i)))

    def exit_to_menu(self) -> None:
        self.stop_ticking()
        if callable(self.on_exit):
            self.on_exit()

    def restart_game(self) -> None:
        engine.init_game()
        self.stats = S.UiStats()
        self.selected_skill = None
        self.paused = False
        self.focus_country = None
        self._cancel_drop()
        self._close_inspector()
        self._close_log()
        self.close_page()
        self.refresh_all()
        self._reschedule_tick()

    # ========================================================
    # 主循环
    # ========================================================
