"""
ui_input.py - InputMixin（拆分自 main.py）

键盘映射 / 主循环 game_tick / 技能文案三件套 / refresh_all 总刷新 /
兼容旧接口的回调别名。
"""
import os

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.widget import Widget

import i18n
from i18n import (t, set_lang, get_lang, get_country_name, get_continent_name,
                  LANG_ZH, LANG_EN)
import engine
import commissions as C
from balance import TUNE
import tech_tree
from tech_tree import TECH_TREE, SLOT_MAP
from data import SKILLS, SKILL_ORDER, SUSPICION_CRISIS
import achievements as achievements_mod
import endings as endings_mod
import country_events as ce
import ui_v4 as U
import ui_v4_screens as S
import ui_shared as ST
from ui_shared import COLORS, Panel
from ui_modal import (make_button, make_modal, modal_header, auto_h_label,
                      hline, _purge_lingering_modals, _wire_close)
from ui_hud import (REGIONS, region_name, region_codes, LANG_CHIP_TAG,
                    LAYER_KEYS, LAYER_LABEL_KEY, HEAT_SCALE, BLOCK_SCALE,
                    COMPUTE_SCALE, STATE_SHAPE)
from ui_commissions import _name_of as _com_name, _goal_text as _com_goal
from ui_v4 import (PxChip, RailButton, RegionTab, SegSwitch, LegendChip,
                   ChipRow, SkillBarCard, Steps, Reticle, TgtLabel, StatsGrid,
                   StrokePanel, SaveSlotRow, mk_label, ST_FILL, ST_EDGE,
                   MIN_TOUCH, fit_width)


# ============================================================
# InputMixin —— GameUI 的键盘 / 主循环 / 刷新
# ============================================================
class InputMixin:
    def _skill_name(self, sid: str) -> str:
        return self.SKILL_I18N[sid].get(get_lang(), sid)

    def _skill_desc(self, sid: str) -> str:
        return self.SKILL_DESC[sid].get(get_lang(), '')

    def _skill_needs_target(self, sid: str) -> bool:
        """下载量类技能需要在地图上选目标（设计稿 S04）；
        偷算力类技能是全局的，直接释放（设计稿 S05「立即释放」）。"""
        s = SKILLS.get(sid)
        return bool(s and abs(s.downloads_mult - 1.0) > 1e-9)

    # ========================================================
    # 缩放
    # ========================================================


    def on_skill_card_click(self, sid: str) -> None:
        """点技能带卡片：下载类 → 进投放模式；偷算力类 → 直接释放"""
        if sid not in engine.player.unlocked_skills:
            self._notify(t('sk_state_lock'))
            return
        if self.drop_mode and self.drop_skill == sid:
            self._cancel_drop()
            return
        if self._skill_needs_target(sid):
            self.start_drop(sid, None)
        else:
            self._cast_skill_direct(sid)
            self.refresh_all()

    def _skill_page_action_alias(self, sid: str, kind: str) -> None:
        self._skill_page_action(sid, kind)

    # 兼容旧接口（test_build / make_screenshots 仍会调用）
    def on_skill_click(self, skill_id: str) -> None:
        self.on_skill_card_click(skill_id)

    def on_country_click(self, code: str) -> None:
        self.on_map_country_click(code)

    def on_unlock_t0(self, slot_id: str) -> None:
        if engine.unlock_t0(slot_id):
            self.refresh_all()
            if isinstance(self._page, S.TechPage):
                self._page.selected_key = f"t0:{slot_id}"
                self._refresh_tech_page()

    def on_pick_branch(self, slot_id: str, branch_id: str) -> None:
        """v0.5 起**取消互斥**：点选分支仅作选中（不锁定、不排他），升级由 upgrade 流程负责。

        保留该入口以兼容旧测试与截图脚本；真正的行为等价于「在网络图上选中该分支节点」。
        """
        if not engine.player.tech.t0_unlocked.get(slot_id):
            self._notify(t('need_t0'))
            return
        if isinstance(self._page, S.TechPage):
            self._page.selected_key = f"br:{branch_id}"
            self._refresh_tech_page()

    def on_upgrade_branch(self, slot_id: str, branch_id: str, level: int = None) -> None:
        if engine.upgrade_branch(slot_id, branch_id):
            self.refresh_all()
            if isinstance(self._page, S.TechPage):
                self._page.selected_key = f"br:{branch_id}"
                self._refresh_tech_page()

    # ========================================================
    # 状态刷新
    # ========================================================
    def _stat_text(self, key: str, mcolor: str, value: float,
                   unit: str = '', digits: int = 0) -> str:
        """拼一条顶栏统计的 markup 文本（值单独着色 + 标签灰）。

        抽出来是为了让「数值滚动动效」能复用同一套格式 —— 动效每帧只改
        中间的数字，标签与颜色不变。

        Args:
            key: i18n 标签键。
            mcolor: MK 色键（yellow/pink/red/...）。
            value: 数值。
            unit: 后缀单位（如 'B' / '%'）。
            digits: 小数位。
        """
        v = f"{value:.{digits}f}{unit}"
        return (f"[color={U.MK['dim']}]{t(key)}[/color]  "
                f"[color={U.MK[mcolor]}][b]{v}[/b][/color]")

    def _animate_stat(self, label, key: str, mcolor: str, new_value: float,
                      unit: str = '', digits: int = 0,
                      pulse_tone: str = 'up') -> None:
        """顶栏统计的「滚动 + 脉冲」刷新（玩家反馈 5：让数字动起来）。

        与静态写法相比只多做两件事：数值跳变时滚一下、并按涨跌脉冲一次。
        第一次渲染（``_stat_prev`` 里没有记录）直接落值，不产生动效 ——
        否则开局所有数字会一起从 0 滚上来，喧宾夺主。

        Args:
            label: 目标 Label。
            key / mcolor / unit / digits: 传给 ``_stat_text``。
            new_value: 新数值。
            pulse_tone: 保留（脉冲用 opacity，无 tint 通道）。
        """
        prev = self._stat_prev.get(key)
        self._stat_prev[key] = new_value
        if prev is None:
            label.text = self._stat_text(key, mcolor, new_value, unit, digits)
            return
        if abs(new_value - prev) < (10 ** -digits) / 2:
            return                       # 四舍五入后没变，不做无意义动效
        import ui_fx
        ui_fx.count_up(label, prev, new_value,
                       fmt=lambda v: self._stat_text(key, mcolor, v, unit, digits))
        # 数值有实际变化才脉冲一次（确认感）
        ui_fx.pulse(label, scale_alpha=0.55, duration=0.12)

    def refresh_all(self) -> None:
        p = engine.player
        if p is None:
            return

        # --- 委托芯片条（P0-3；无委托时自动隐藏）---
        self.refresh_commissions()

        # --- 顶栏（设计稿 .bar）---
        unlocked = sum(1 for c in engine.player_countries if c.unlocked)
        total = len(engine.player_countries)
        # 首次进入才建缓存（不可放在 __init__：那时还没有 stats_* 控件）
        if not hasattr(self, '_stat_prev'):
            self._stat_prev = {}
        self._animate_stat(self.stats_compute, 'stats_compute', 'yellow',
                           float(p.compute), digits=0)
        self._animate_stat(self.stats_downloads, 'stats_downloads', 'pink',
                           p.total_downloads_m / 1000.0,
                           unit=t('unit_b'), digits=2)
        self._animate_stat(self.stats_suspicion, 'stats_suspicion',
                           'bad' if p.suspicion >= SUSPICION_CRISIS else
                           ('warn' if p.suspicion >= 50 else 'susp_low'),
                           float(p.suspicion), unit='%', digits=0)
        # 国家数用整数直写（走 _stat_text 以保持与其它统计同构）
        _meta_prev = self._stat_prev.get('stat_countries')
        self._stat_prev['stat_countries'] = float(unlocked)
        if _meta_prev is None or abs(_meta_prev - unlocked) > 0.5:
            self.stats_meta.text = (f"[color={U.MK['dim']}]{t('stat_countries')}"
                                    f"[/color]  [b]{unlocked}/{total}[/b]")
        # --- 顶栏趋势火花线（玩家反馈 6：让"涨没涨"一眼可见）---
        # 数据源是 UiStats 的全局序列（每周期采样），首周期只有 1 根柱属正常。
        for sk, spark in getattr(self, '_stat_sparks', {}).items():
            try:
                spark.set_values(self.stats.stat_spark(sk))
            except Exception:
                pass
        # 右上角周期数（大号数字，仅数字变化，不重建文本）
        self.lbl_tick_val.text = f"{p.tick_count}"

        if self.paused:
            self.pause_chip.set_tone('cost', t('pause'))
        else:
            self.pause_chip.set_tone('up', t('state_running'))

        # --- 地图四态 ---
        states = {c.config.code: self._state_of(c) for c in engine.player_countries}
        self.map_widget.set_country_states(states)
        self.map_widget.set_selected(p.selected_country)
        self._sync_region_tabs()
        self._apply_layer()

        # --- 技能带 ---
        for sid, card in self.skill_cards.items():
            if sid not in p.unlocked_skills:
                card.set_state('lock', 0, 0.0,
                               f"{U.SYM['lock']} {t('sk_state_lock')}")
                card.set_selected(False)
                continue
            cd = p.skill_cooldowns.get(sid, 0)
            skill = SKILLS[sid]
            if cd > 0:
                card.set_state('cd', cd, min(cd / max(skill.cooldown, 1), 1.0),
                               f"{t('sk_state_cd')} {cd}")
            elif p.compute < skill.cost:
                card.set_state('no_compute', 0, 0.0, t('sk_state_no_compute'))
            else:
                card.set_state('ready', 0, 0.0, t('sk_state_ready'))
            card.set_selected(self.drop_mode and sid == self.drop_skill)

        # --- 日志未读角标 ---
        self.rail.buttons['log'].set_badge(self.stats.unread)

        # --- 检视卡 / 日志抽屉 / 投放预览 ---
        if self._inspector is not None and self.focus_country:
            cs = self._country_state(self.focus_country)
            if cs is not None:
                self._inspector.update(cs, self.stats, p.total_downloads_m,
                                       p.suspicion,
                                       TUNE['unlock_penetration_threshold'])
        if self._log_drawer is not None:
            self._log_drawer.rebuild(self.stats.logs, self.stats.unread)
        if self.drop_mode:
            self._sync_drop_ui()

        # --- 打开中的页面也要跟着刷新 ---
        if self._page is not None:
            self._refresh_page(getattr(self._page, 'page_name', ''), self._page)

    def _notify(self, text: str) -> None:
        """写一条信息日志（设计稿 S14 的青色分类）"""
        p = engine.player
        if p is None:
            return
        p.events_history.insert(0, f"[{p.tick_count}] {text}")
        p.events_history = p.events_history[:20]
        self.stats.push_log(p.tick_count, text, 'i')
        if self._log_drawer is not None:
            self._log_drawer.rebuild(self.stats.logs, self.stats.unread)
        self.rail.buttons['log'].set_badge(self.stats.unread)

    # ========================================================
    # 弹窗
    # ========================================================


    def game_tick(self, dt) -> None:
        # 引导进行中：冻结回合推进（即使误触空格取消暂停也不推进）
        if self.tutorial is not None and self.tutorial.overlay is not None:
            self._tick_deadline = Clock.get_time() + self._tick_interval()
            return
        self._tick_deadline = Clock.get_time() + self._tick_interval()
        if engine.player.game_over:
            self.stop_ticking()
            return
        report = engine.tick_one_round(skill_in_use=self.selected_skill,
                                       auto_choice=False,
                                       dt_seconds=self._tick_interval())
        self.selected_skill = None
        self._last_growth = report.get("download_growth", 0.0)
        self.stats.sample(engine.player_countries, engine.player, self._last_growth)

        # 把引擎报告里的关键事件写进日志（设计稿 S14 的四种分类）
        for name in report.get("unlocked", []) or []:
            self.stats.push_log(engine.player.tick_count,
                                f"{t('legend_on')}: {name}", 'i')
        # 引擎里该字段叫 blocking_countries（设计稿 S14 的红色「阻止」分类）
        blocked = report.get("blocking_countries") or report.get("blocked") or []
        if isinstance(blocked, (list, tuple, set)):
            for name in blocked:
                self.stats.push_log(engine.player.tick_count,
                                    f"{t('log_tone_e')}: {name}", 'e')
        got = report.get("achievements") or []
        if isinstance(got, (list, tuple, set)):
            for item in got:
                # 引擎给的是 Achievement 对象；兼容旧版传 id 字符串
                if hasattr(item, 'name'):
                    ach_name = item.name(get_lang())
                else:
                    a = achievements_mod.ALL_BY_ID.get(item)
                    ach_name = a.name(get_lang()) if a else str(item)
                self.stats.push_log(engine.player.tick_count,
                                    f"{t('log_tone_g')}: {ach_name}", 'g')

        # --- P0-3 委托事件（toast + 日志；芯片条随 refresh_all 重建）---
        offered = report.get("commission_offered")
        if offered is not None:
            est = C.compute_reward(engine.player.tick_count, offered.reward_mult)
            left = max(TUNE['commission_offer_ttl'] - (
                engine.player.tick_count - offered.offered_tick), 0)
            self.show_top_toast(
                f"{offered.icon} {t('com_offer_new')} · {_com_name(offered)}",
                tone='cost',
                detail=f"{_com_goal(offered)} · "
                       f"{t('com_reward_est')} ~{est:.0f}{t('com_reward_unit')} · "
                       f"{t('com_left_short')}{left}{t('com_left_unit')}")
            self._notify(f"{t('com_offer_new')}: {_com_name(offered)}")
        done = report.get("commission_done")
        if done is not None:
            self.show_top_toast(
                f"{done.icon} {t('com_done_toast')} · {_com_name(done)}",
                tone='up',
                detail=f"{_com_goal(done)} · "
                       f"+{done.reward:.0f}{t('com_reward_unit')}")
            self._notify(f"{t('com_done_toast')}: {_com_name(done)} "
                         f"+{done.reward:.0f}{t('com_reward_unit')}")
        failed = report.get("commission_failed")
        if failed is not None:
            self.show_top_toast(
                f"{t('com_failed_toast')} · {_com_name(failed)}", tone='dn',
                detail=_com_goal(failed))
            self._notify(f"{t('com_failed_toast')}: {_com_name(failed)}")

        # --- P0-3 政府反制（ardot_ui S06 ⚠ 预警样式）---
        cp_events = report.get("counterplay")
        if cp_events:
            for ev in cp_events:
                cname = (get_country_name(ev.get('country', ''))
                         or ev.get('name', ''))
                if ev.get('phase') == 'warn':
                    self.show_top_toast(
                        t('cp_warn_toast').format(name=cname), tone='cost')
                    self._notify(t('cp_warn_log').format(name=cname))
                elif ev.get('phase') == 'strike':
                    body = t(f"cp_type_{ev.get('type', '')}").format(
                        detail=ev.get('detail', ''))
                    self.show_top_toast(
                        f"{t('cp_strike_toast').format(name=cname)} {body}",
                        tone='dn')
                    self._notify(
                        f"{t('cp_strike_toast').format(name=cname)} {body}")

        self.refresh_all()
        # 周期推进的视觉提示（玩家反馈 5）：倒计时条脉冲一次，
        # 让「新周期开始了」这件事有存在感。动效失败不影响逻辑。
        try:
            import ui_fx
            ui_fx.tick_pulse(getattr(self, 'cd_bar', None))
        except Exception:
            pass

        if report.get("crisis"):
            self.show_crisis_popup()
        if report.get("choice_event") is not None:
            self.show_choice_popup(report["choice_event"])
        if report.get("ending") is not None:
            self.stop_ticking()
            save_manager.save()
            self.show_ending_popup(report["ending"])

    # ========================================================
    # 键盘
    # ========================================================
    def _keyboard_closed(self) -> None:
        if getattr(self, '_keyboard', None) is not None:
            self._keyboard.unbind(on_key_down=self._on_keyboard_down)
            self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers) -> bool:
        """F11 快捷键表（与设计稿 S11 帮助页同源）"""
        key = keycode[1]

        # ── 科技树全屏页打开时，方向键/回车改作节点导航（优先于全局速度档）──
        if isinstance(self._page, S.TechPage):
            if key == 'left':
                self._page.move_selection(dslot=-1)
                self._refresh_tech_page()
                return True
            if key == 'right':
                self._page.move_selection(dslot=+1)
                self._refresh_tech_page()
                return True
            if key == 'up':
                self._page.move_selection(dbranch=-1)
                self._refresh_tech_page()
                return True
            if key == 'down':
                self._page.move_selection(dbranch=+1)
                self._refresh_tech_page()
                return True
            if key in ('enter', 'numpadenter', 'kp_enter'):
                self._tech_do_action()
                return True

        if key == 'spacebar':
            self.toggle_pause()
            return True
        if key in ('1', '2', '3', '4', '5', '6'):
            idx = int(key) - 1
            if idx < len(SKILL_ORDER):
                self.on_skill_card_click(SKILL_ORDER[idx])
            return True
        if key == 'f':
            self.toggle_drop_mode()
            return True
        if key in ('k',):
            self.open_page('tech')
            return True
        if key == 'a':
            self.open_page('ach')
            return True
        if key == 'tab':
            self.cycle_continent()
            return True
        if key == 'up':
            self.set_speed_idx(self.speed_idx + 1)
            return True
        if key == 'down':
            self.set_speed_idx(self.speed_idx - 1)
            return True
        if key in ('+', '=', 'kp_add', 'numpadadd'):
            self.adjust_scale(+0.10)
            return True
        if key in ('-', '_', 'kp_subtract', 'numpadsubtract'):
            self.adjust_scale(-0.10)
            return True
        if key == 'f11':
            self.toggle_fullscreen()
            return True
        if key == 'f12':
            self.user_scale = 1.0
            self._apply_scale()
            return True
        if key == 'f1':
            self.open_page('help')
            return True
        if key == 'l':
            self.toggle_lang()
            return True
        if key == 's':
            self.do_save()
            return True
        if key == 'r':
            self.do_load()
            return True
        if key == 'enter':
            if self.drop_mode and self.drop_targets:
                self._confirm_drop()
            return True
        if key == 'escape':
            # Esc 逐层退出：投放模式 → 全屏页 → 浮层 → 主菜单
            if self.drop_mode:
                self._cancel_drop()
                return True
            if self._page is not None:
                self.close_page()
                return True
            if self._log_drawer is not None:
                self._close_log()
                return True
            if self._inspector is not None:
                self._close_inspector()
                return True
            if callable(self.on_exit):
                self.exit_to_menu()
            return True
        return False


