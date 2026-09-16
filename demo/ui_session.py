"""
ui_session.py - SessionMixin（拆分自 main.py）

会话级操作：存/读/删档、语言切换与界面重建、暂停/节奏与倒计时、
速度档/动效/色盲/音效设置、全屏、退回主菜单与重开一局。
"""
import os

from kivy.clock import Clock
from kivy.core.window import Window

from i18n import (t, set_lang, get_lang, LANG_ZH, LANG_EN)
import engine
import save_manager
import sfx
import bgm
import preferences
import ui_v4 as U
import ui_v4_screens as S
import ui_shared as ST
from ui_shared import _update_window_title
from ui_hud import REGIONS, LANG_CHIP_TAG, LAYER_KEYS, LAYER_LABEL_KEY


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
                pass  # 单个控件缩放失败只影响其外观，不中断其余控件与后续布局
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
                pass  # 同上：单个控件的 refresh_scale 失败不拖垮整体缩放
        for ch in getattr(widget, 'children', ()) or ():
            self._walk_refresh(ch, depth + 1)

    def _on_window_resize(self, window, w, h) -> None:
        pending = getattr(self, '_resize_fit_event', None)
        if pending is not None:
            pending.cancel()
        self._resize_fit_event = Clock.schedule_once(self._fit_after_resize, 0.15)

    def _fit_after_resize(self, _dt) -> None:
        self._resize_fit_event = None
        self._apply_scale()

    def _zoom_btn(self, delta: float) -> None:
        if delta == 0.0:
            self.user_scale = 1.0
        else:
            self.user_scale = min(max(self.user_scale + delta, 0.70), 1.60)
        self._apply_scale()
        preferences.update(ui_scale=self.user_scale)
        self._notify(f"{t('scale_label')} ×{self.user_scale:.2f}")

    def adjust_scale(self, delta: float) -> None:
        self._zoom_btn(delta)

    # ========================================================
    # 区域高亮（设计稿 S02 左上 HUD）
    # ========================================================
    REGION_KEYS = [k for k, _ in REGIONS]



    def toggle_fullscreen(self) -> None:
        # 用 True 而不是 'auto'：'auto' 会按「显示器与窗口重叠面积」挑显示器，
        # 多显示器且 DPI 不一致时容易选中副屏、或选到后分辨率与缩放对不上，
        # 表现为按 F11 后画面糊/错位/跑到别块屏。True = 固定选当前那块。
        Window.fullscreen = True if not Window.fullscreen else False
        # 0.2s 后重算缩放：全屏切换是异步的，立刻读 Window.width/height
        # 拿到的还是旧值，算出来的 scale 会错一档。
        Clock.schedule_once(lambda *_: self._apply_scale(), 0.2)



    def _save_slot(self, slot: str) -> None:
        path = os.path.join(save_manager.SAVE_DIR, slot)
        save_manager.save(path)
        self._notify(f"{t('save_button')} → {slot}")
        if isinstance(self._page, S.SettingsPage):
            self._page.rebuild_slots(self._slot_rows())

    def _load_slot(self, slot: str) -> None:
        path = os.path.join(save_manager.SAVE_DIR, slot)
        ok, reason = save_manager.load_ex(path)
        if ok:
            self._notify(t('load_ok'))
            self.close_page()
            self.paused = False
            self.stop_ticking()
            self._reschedule_tick()
            self.refresh_all()
        else:
            # P0-2：区分「没存档」和「存档坏了」，别一律说"没有可用存档"
            self._notify(save_manager.load_fail_text(reason))

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
        ok, reason = save_manager.load_ex()
        if ok:
            self._notify(t('load_ok'))
            self.paused = False
            self.stop_ticking()
            self._reschedule_tick()
            self.refresh_all()
        else:
            # P0-2：坏档要说清是损坏还是版本过旧
            self._notify(save_manager.load_fail_text(reason))

    def toggle_lang(self) -> None:
        self._set_lang_idx(1 if get_lang() == LANG_ZH else 0)

    def _rebuild_lang(self) -> None:
        """切换语言后重建所有带文案的控件"""
        page_name = getattr(self._page, 'page_name', None)
        # 科技页是「选节点 → 看描述」，重建会丢选中项 → 切完语言详情面板
        # 变成「未选中任何节点」。记住 key 重开后补回去（其它页无此属性）。
        page_sel = getattr(self._page, 'selected_key', None)
        _update_window_title()
        self.lang_switch.set_tone('plain', LANG_CHIP_TAG[get_lang()])
        self.help_chip.set_tone('plain', '? ' + t('rail_help'))
        for sid, card in self.skill_cards.items():
            card.set_texts(self._skill_name(sid), self._skill_desc(sid))
        for sid, btn in self.rail.buttons.items():
            btn._caption = '' if sid == 'help' else t(f'rail_{sid}')
            btn._sync_text()
        self.lbl_tick_cap.text = t('stats_tick')
        U.fit_width(self.lbl_tick_cap, pad=6)
        self.lbl_grey.text = t('drop_grey_note')
        self.drop_hint.set_tone('on', t('drop_click_hint'))
        self.layer_hud.seg.set_options([t(LAYER_LABEL_KEY[k]) for k in LAYER_KEYS])
        self.steps.set_labels([t('drop_step1'), t('drop_step2'), t('drop_step3')])
        self._sync_pause_button()
        self._sync_region_tabs()
        self._apply_layer()
        self._stat_prev.clear()
        self.refresh_all()
        self._refresh_tech_page()
        self._refresh_lang_panels()
        if page_name:
            self.close_page()
            self.open_page(page_name)
            if page_sel and hasattr(self._page, 'selected_key'):
                self._page.selected_key = page_sel
                self._refresh_page(page_name, self._page)
        evt = getattr(self, '_active_choice_event', None)
        popup = getattr(self, '_active_choice_popup', None)
        if evt is not None and popup is not None:
            popup.dismiss()
            self.show_choice_popup(evt)

    def _sync_pause_button(self) -> None:
        """底部暂停按钮文案的唯一来源（玩家反馈 #1）。

        暂停时按钮应写「继续 / 恢复」，运行时才写「暂停」——
        旧实现只在 _apply_lang 里赋一次「暂停」，点下去文案从不变化，
        玩家无法判断当前到底停没停。
        """
        btn = getattr(self, 'btn_pause', None)
        if btn is None:
            return
        sym = getattr(U, 'SYM', {})
        if self.paused:
            btn.text = f"{sym.get('play', '■')} {t('quick_resume')}"
        else:
            btn.text = f"{sym.get('pause', '■')} {t('quick_pause')}"

    def toggle_pause(self) -> None:
        """暂停 / 恢复（玩家反馈 #1）。

        !️ 旧实现只是 cancel 掉时钟，恢复时走 _reschedule_tick() 把
        _tick_deadline 重置为「现在 + 整个周期」—— 于是暂停前已经过去的
        那几秒被丢掉，倒计时从 30s 重新开始，玩家感知为「暂停不真」。

        现在：暂停时把「剩余秒数」冻结进 _paused_remaining；恢复时按这个
        剩余量重建一次性计时，周期进度从暂停处接着走。
        """
        sfx.play('pause')                 # 点击暂停/继续的个性化音效
        if self.paused:
            self.paused = False
            self._event_pause_owned = False
            self._resume_from_pause()
            bgm.resume()                 # 随游戏一同恢复 BGM
        else:
            self.paused = True
            # 冻结剩余时间（下限 0，防止负值导致立即触发）
            self._paused_remaining = max(
                0.0, self._tick_deadline - Clock.get_time())
            self.stop_ticking()
            bgm.pause()                  # 随游戏一同暂停 BGM
        self.refresh_all()

    def _pause_for_event(self) -> None:
        """事件弹窗复用手动暂停流程；已暂停时保持原状态。"""
        if not self.paused:
            self.toggle_pause()
            self._event_pause_owned = True

    def _resume_after_event(self) -> None:
        """只恢复由事件造成的暂停；玩家原本手动暂停则保持不变。"""
        owned = bool(getattr(self, '_event_pause_owned', False))
        self._event_pause_owned = False
        if owned and self.paused and not engine.player.game_over:
            self.toggle_pause()

    def _resume_from_pause(self) -> None:
        """按暂停前冻结的剩余秒数恢复周期进度（而非重置为整周期）。"""
        self.stop_ticking()
        if engine.player is None or engine.player.game_over:
            return
        remaining = max(0.0, getattr(self, '_paused_remaining', 0.0))
        interval = self._tick_interval()
        if remaining <= 0.0 or remaining > interval:
            # 没有可用的冻结值（旧档 / 首次）→ 退回整周期
            self._reschedule_tick()
            return
        # 先排一次「剩余时间后」的周期推进，之后自动转回等间隔节奏
        self._tick_deadline = Clock.get_time() + remaining

        def _first_tick(dt):
            # 第一次触发后立刻切回常规等间隔调度，避免节拍漂移
            self.tick_event = None
            self.game_tick(dt)
            if not self.paused and not engine.player.game_over:
                self.tick_event = Clock.schedule_interval(
                    self.game_tick, self._tick_interval())

        self.tick_event = Clock.schedule_once(_first_tick, remaining)

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
        preferences.update(speed_idx=self.speed_idx)
        self._reschedule_tick()
        self._refresh_speed_indicator()
        self.refresh_all()

    def _set_motion_idx(self, i: int) -> None:
        """动效开关：0=完整 / 1=减弱（P0-5）。"""
        ST.REDUCE_MOTION = bool(int(i))
        preferences.update(reduce_motion=ST.REDUCE_MOTION)
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
        preferences.update(a11y_shapes=ST.A11Y_SHAPES)
        if getattr(self, 'legend_hud', None) is not None:
            self.legend_hud.apply_a11y()

    def _set_sound_idx(self, i: int) -> None:
        """音效开关：0=关 / 1=开（P0-5）。

        注意播放顺序：**先按新状态切换、再播 toggle**。若先播再切，
        关闭音效时这一声会成为绝响（set_enabled(False) 之后 play() 被拦），
        玩家会觉得「点了没反应」；反过来则开启时也一定听得见。
        """
        sfx.set_enabled(bool(int(i)))
        sfx.play('toggle')
        preferences.update(sound_on=sfx.SFX_ON)

    def _set_music_idx(self, i: int) -> None:
        """音乐开关：0=关 / 1=开（T09）。关闭停播，开启按当前怀疑度补播。"""
        bgm.set_enabled(bool(int(i)))
        sfx.play('toggle')
        preferences.update(music_on=bgm.BGM_ON)

    def exit_to_menu(self) -> None:
        self.stop_ticking()
        # BGM：**不再 stop()**。原先停播是为了「避免主菜单还在放紧张曲」，
        # 现在主菜单有自己的 menu 曲池（RootView.show_menu 会切过去），
        # 若这里仍 stop()，会出现「静音一拍 → 菜单曲淡入」的空档，
        # 听感上像音乐被掐断。交给 show_menu 做池间交叉淡出即可。
        if callable(self.on_exit):
            self.on_exit()

    def restart_game(self) -> None:
        engine.init_game()
        # intro_v2：对局内重开必然已经历过开场（新游戏进来的刚看完 /
        # 读档进来的补播链已保证），置位防「重开→保存→退出→继续又补播」。
        engine.player.intro_seen = True
        self.stats = S.UiStats()
        self.selected_skill = None
        self.paused = False
        self.focus_country = None
        self._cancel_drop()
        self._close_inspector()
        self._close_log()
        self.close_page()
        self.refresh_all()
        # BGM：重开一局怀疑度归零，从 tense 池切回 calm。
        # bgm.update 幂等，已是 calm 时无开销；若上局结束在 tense 态，
        # 这里若不切，新局会带着「上局的紧张音乐」开局。
        bgm.update('calm')
        self._reschedule_tick()

    # ========================================================
    # Esc 兜底：暂停 + 设置页（替代原先的「直接回主菜单」）
    # --------------------------------------------------------
    # 语义：Esc 逐层退出保持不变（投放 → 全屏页 → 日志抽屉 → 检视卡），
    # 只把最外层兜底改成「暂停并打开设置页」，避免误按 Esc 直接弃局。
    # 回主菜单仍保留两条路径：① 结算弹窗「返回主菜单」按钮；
    #                       ② game_over 状态下按 Esc（不再暂停，直接 exit）。
    # ========================================================
    def pause_menu(self) -> None:
        """暂停（未暂停时）+ 打开设置页。pause 音由 toggle_pause 自带。"""
        if not self.paused:
            self.toggle_pause()          # 冻结剩余秒数 + 停 tick + 播音效
        self._pause_menu = True
        self.open_page('settings')

    def _leave_pause_menu(self) -> None:
        """离开「暂停态设置页」→ 恢复对局（仅当仍处于 paused，避免二次恢复）。"""
        if not getattr(self, '_pause_menu', False):
            return
        self._pause_menu = False
        if self.paused:
            self.toggle_pause()          # 从冻结处续走 + 播音效

    def _esc_fallback(self) -> None:
        """Esc 最外层兜底：对局进行中 → 暂停 + 设置页；已结束 → 回主菜单。"""
        if engine.player is not None and not engine.player.game_over:
            self.pause_menu()
        elif callable(self.on_exit):
            self.exit_to_menu()

    # ========================================================
    # 主循环
    # ========================================================
