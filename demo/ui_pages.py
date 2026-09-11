"""
ui_pages.py - PagesMixin（拆分自 main.py）

覆盖：右侧指令栏路由 / 6 个全屏页装配与刷新（技能/科技/成就/帮助/设置/日志）
      国家检视卡 / 事件日志抽屉
"""
import os

from kivy.uix.boxlayout import BoxLayout

import i18n
from i18n import (t, set_lang, get_lang, get_country_name, LANG_ZH, LANG_EN)
import engine
import sfx
from tech_tree import TECH_TREE, SLOT_MAP
from balance import TUNE
from data import SKILLS, SKILL_ORDER, SKILL_UNLOCK
import save_manager
import achievements as achievements_mod
import ui_v4 as U
import ui_v4_screens as S
from ui_shared import COLORS
from ui_modal import (make_button, make_modal, modal_header, auto_h_label,
                      hline)


# ============================================================
# PagesMixin —— GameUI 的全屏页 / 检视卡 / 日志抽屉
# ============================================================
class PagesMixin:
    def _on_rail(self, key: str) -> None:
        if key == 'drop':
            self.toggle_drop_mode()
        elif key == 'log':
            self.toggle_log()
        else:
            self.open_page(key)

    def open_page(self, name: str) -> None:
        """打开全屏页（同名再点则关闭）"""
        sfx.play('click')
        if self._page is not None and getattr(self._page, 'page_name', '') == name:
            self.close_page()
            return
        self.close_page()
        page = self._build_page(name)
        if page is None:
            return
        page.page_name = name
        self._page = page
        page.size_hint = (1, 1)
        page.pos_hint = {'x': 0, 'y': 0}
        self.add_widget(page)
        self.rail.set_active(name)
        self._refresh_page(name, page)

    def close_page(self) -> None:
        if self._page is not None:
            self.remove_widget(self._page)
            self._page = None
        self.rail.set_active('none')

    def _build_page(self, name: str):
        if name == 'skills':
            p = S.SkillPage(on_action=self._skill_page_action,
                            on_sort=self._refresh_skill_page)
            p.ensure_cards(SKILL_ORDER)
            p.set_back_button(t('k_esc'), self.close_page)
            return p
        if name == 'tech':
            p = S.TechPage(on_unlock=self.on_unlock_t0,
                           on_level=self.on_upgrade_branch,
                           on_reset=self._reset_tech,
                           on_select=self._on_tech_node_select)
            p.ensure_slots(TECH_TREE)
            p.set_back_button(t('k_esc'), self.close_page)
            return p
        if name == 'ach':
            p = S.AchPage(on_filter=self._refresh_ach_page)
            p.set_back_button(t('k_esc'), self.close_page)
            return p
        if name == 'help':
            p = S.HelpPage()
            p.set_back_button(t('k_esc'), self.close_page)
            return p
        if name == 'settings':
            p = S.SettingsPage(
                on_lang=self._set_lang_idx, on_scale=self._zoom_btn,
                on_speed=self.set_speed_idx, on_grid=self._set_grid,
                on_a11y=self._set_a11y_idx, on_motion=self._set_motion_idx,
                on_sound=self._set_sound_idx,
                on_tutorial=self.tutorial.replay,
                slot_actions=self._slot_actions,
                on_reset=lambda: self._notify(t('set_restore')))
            p.set_back_button(t('k_esc'), self.close_page)
            return p
        return None

    def _refresh_page(self, name: str, page) -> None:
        """打开页面后按类型刷新一次"""
        if name == 'skills':
            self._refresh_skill_page(page)
        elif name == 'tech':
            self._refresh_tech_page(page, None, False)
        elif name == 'ach':
            self._refresh_ach_page(None, page)
        elif name == 'settings':
            page.set_zoom_text(f"×{self.user_scale:.2f}")
            page.rebuild_slots(self._slot_rows())

    # ---- S05 技能页 ----
    def _skill_page_action(self, sid: str, kind: str) -> None:
        if not self._skill_needs_target(sid):
            self.close_page()
            self._cast_skill_direct(sid)
            return
        code = engine.player.selected_country or 'CN'
        self.close_page()
        self.start_drop(sid, [code])

    def _refresh_skill_page(self, page=None, sort=None) -> None:
        page = page if page is not None else self._page
        if not isinstance(page, S.SkillPage):
            return
        if sort:
            page.set_sort_visual(sort)
            self._skill_sort = sort
        p = engine.player
        page.set_compute(p.compute)
        order = list(SKILL_ORDER)
        cur = getattr(self, '_skill_sort', 'profit')
        if cur == 'cost':
            order.sort(key=lambda s: SKILLS[s].cost)
        elif cur == 'cd':
            order.sort(key=lambda s: -p.skill_cooldowns.get(s, 0))
        elif cur == 'uses':
            order.sort(key=lambda s: -self.stats.skill_uses.get(s, 0))
        for sid in order:
            card = page.cards.get(sid)
            if card is None:
                continue
            self._fill_skill_card(card, sid)
        for i, sid in enumerate(order):
            page._grid.remove_widget(page.cards[sid])
        for i, sid in enumerate(order):
            page._grid.add_widget(page.cards[sid])

    def _fill_skill_card(self, card, sid: str) -> None:
        p = engine.player
        skill = SKILLS[sid]
        cd = p.skill_cooldowns.get(sid, 0)
        needs = self._skill_needs_target(sid)
        locked = sid not in p.unlocked_skills

        # ---- 收益 / 消耗文案（问题 #4：把收益和消耗写清楚）----
        benefit = []
        if skill.downloads_mult > 1.0:
            benefit.append(f"下载 ×{skill.downloads_mult:.2f}")
        if skill.compute_mult > 1.0:
            benefit.append(f"偷算力 ×{skill.compute_mult:.1f}")
        if skill.stealth_ratio_mult > 1.0 or skill.stealth_ratio_bonus > 0:
            bonus = skill.stealth_ratio_bonus
            mult = skill.stealth_ratio_mult
            if mult > 1.0:
                benefit.append(f"偷算力比 ×{mult:.1f}")
            if bonus > 0:
                benefit.append(f"偷算力比 +{bonus*100:.0f}%")
        if skill.suspicion_mult < 1.0:
            benefit.append(f"怀疑增速 ×{skill.suspicion_mult:.1f}")
        cost = f"算力 {skill.cost:.0f}"
        if skill.suspicion_delta > 0:
            cost += f" · 怀疑 +{skill.suspicion_delta:.0f}%"
        detail = t(f'sk_detail_{sid}')
        bc = (f"[color={U.MK['cyan']}]{t('sk_benefit')}[/color] "
              f"{' · '.join(benefit) or '—'}    "
              f"[color={U.MK['red']}]{t('sk_cost')}[/color] {cost}")
        rich_desc = f"{detail}\n{bc}"

        if locked:
            req = SKILL_UNLOCK.get(sid)
            unlock_hint = (t('sk_unlock_hint').format(
                tech=SLOT_MAP[req['slot']].name) if req else t('sk_starter_hint'))
            card.update(skill, self.SKILL_ICON[sid], self._skill_name(sid),
                        str(SKILL_ORDER.index(sid) + 1), [],
                        rich_desc, 0, "0.0M", "0.00M",
                        self.stats.skill_spark(sid), 'lock',
                        t('sk_state_lock'), '', False, '',
                        locked=True, unlock_hint=unlock_hint)
            return

        if cd > 0:
            state, state_text = 'cd', f"{t('sk_state_cd')} {cd}"
        elif p.compute < skill.cost:
            state, state_text = 'no_compute', t('sk_state_no_compute')
        else:
            state, state_text = 'ready', t('sk_state_ready')
        chips = [(t('cost') + f" {skill.cost:.0f}", 'cost'),
                 (f"{t('sk_sort_cd')} {skill.cooldown}", 'plain')]
        if skill.downloads_mult > 1.0:
            chips.append((f"×{skill.downloads_mult:.2f}", 'up'))
        if skill.suspicion_delta > 0:
            chips.append((f"{t('stats_suspicion')} +{skill.suspicion_delta:.0f}%", 'dn'))
        if skill.stealth_ratio_mult > 1.0 or skill.stealth_ratio_bonus > 0:
            chips.append((f"steal ×{skill.stealth_ratio_mult:.1f}", 'sys'))
        if skill.compute_mult > 1.0:
            chips.append((f"compute ×{skill.compute_mult:.1f}", 'sys'))
        uses = self.stats.skill_uses.get(sid, 0)
        contrib = self.stats.skill_contrib.get(sid, 0.0)
        if needs:
            act, enabled = t('sk_action_drop').format(
                code=engine.player.selected_country or 'CN'), (cd == 0 and p.compute >= skill.cost)
            foot = t('targets') + f": {engine.player.selected_country or '--'}"
        else:
            act, enabled = t('sk_action_cast'), (cd == 0 and p.compute >= skill.cost)
            foot = f"{t('stats_compute')} {p.compute:.0f} → {p.compute - skill.cost:.0f}"
        card.update(skill, self.SKILL_ICON[sid], self._skill_name(sid),
                    str(SKILL_ORDER.index(sid) + 1), chips,
                    rich_desc, uses, f"{contrib:.1f}M",
                    f"{(contrib / uses if uses else 0):.2f}M",
                    self.stats.skill_spark(sid), state, state_text,
                    act, enabled, foot)

    # ---- S06 科技树页 ----
    def _refresh_tech_page(self, page=None, slot_id=None, from_click=False) -> None:
        """刷新科技树网络图：算好每个节点的状态喂给 TechCanvas，并同步详情面板。

        v0.5：一次算全 24 个节点（6 T0 + 18 分支），不再有「当前槽位」概念。
        ``slot_id`` / ``from_click`` 仅为兼容旧调用签名保留。
        """
        page = page if page is not None else self._page
        if not isinstance(page, S.TechPage):
            return
        pt = engine.player.tech
        t0_done = sum(1 for v in pt.t0_unlocked.values() if v)
        invested = len(pt.active_branches())
        levels = sum(pt.branch_levels.values())
        page.chip_t0.set_tone('up', f"{t('tt_t0_unlocked').format(a=t0_done, b=6)}")
        page.chip_lv.set_tone('up', f"{t('tt_levels').format(a=levels, b=54)}")
        page.chip_full.set_tone('sys',
                                t('tt_branch_progress').format(a=invested, b=18))
        page.lbl_compute.text = (f"{t('sk_avail_compute')} "
                                 f"[color={U.MK['yellow']}]{engine.player.compute:.0f}[/color]")

        states = {}
        for slot in TECH_TREE:
            done = pt.t0_unlocked.get(slot.slot_id, False)
            # --- T0 节点 ---
            tk = f"t0:{slot.slot_id}"
            if done:
                t_state, t_sub = 'done', t('tt_picked')
            elif pt.can_unlock_t0(slot.slot_id):
                t_state = ('can' if engine.player.compute >= slot.t0_cost
                           else 'poor')
                t_sub = f"{slot.t0_cost:.0f}"
            else:
                t_state = 'lock'
                pre = SLOT_MAP.get(slot.prereq_slot) if slot.prereq_slot else None
                t_sub = (t('tt_need_pre').format(n=pre.name) if pre
                         else f"{slot.t0_cost:.0f}")
            states[tk] = {'state': t_state, 'level': 1 if done else 0,
                          'cost': 0.0 if done else slot.t0_cost, 'sub': t_sub}
            # --- 分支节点 ---
            for br in slot.branches:
                lv = pt.branch_levels.get(br.branch_id, 0)
                bk = f"br:{br.branch_id}"
                if not done:
                    b_state, b_sub = 'lock', ''
                elif lv >= 3:
                    b_state, b_sub = 'done', ''
                elif engine.player.compute >= br.costs[lv]:
                    b_state, b_sub = 'can', f"{br.costs[lv]:.0f}"
                else:
                    b_state, b_sub = 'poor', f"{br.costs[lv]:.0f}"
                states[bk] = {'state': b_state, 'level': lv,
                              'cost': 0.0 if lv >= 3 else br.costs[lv],
                              'sub': b_sub}

        page.canvas_view.set_state(states, page.selected_key)

        # 选中节点 → 把描述写进 node（详情面板读它）并给底部按钮挂回调
        nd = page.canvas_view.nodes.get(page.selected_key)
        if nd is not None:
            if nd.kind == 't0':
                slot = SLOT_MAP.get(nd.slot_id)
                nd.desc = (slot.description if slot else '')
            else:
                nd.desc = self._branch_desc(nd.slot_id, nd.branch_id)
        page._sync_detail_from_node()

    def _branch_desc(self, slot_id: str, branch_id: str) -> str:
        """分支节点的详情描述：名称 + 三级效果摘要。"""
        slot = SLOT_MAP.get(slot_id)
        if slot is None:
            return ''
        for br in slot.branches:
            if br.branch_id != branch_id:
                continue
            lv = engine.player.tech.branch_levels.get(branch_id, 0)
            eff = self._branch_effect(br, min(lv, 2))
            return f"{br.description}\\n{lv}/3 · {eff}"
        return ''

    def _reset_tech(self) -> None:
        """重置科技树（本局不可逆）。"""
        engine.player.tech.reset()
        self._notify(t('tt_reset'))
        self._refresh_tech_page()
        self.refresh_all()

    def _tech_do_action(self) -> None:
        """键盘回车：对当前选中节点执行「解锁 T0」或「升级分支」。"""
        page = self._page
        if not isinstance(page, S.TechPage):
            return
        nd = page.canvas_view.nodes.get(page.selected_key)
        if nd is None:
            return
        if nd.kind == 't0':
            self.on_unlock_t0(nd.slot_id)
        else:
            self.on_upgrade_branch(nd.slot_id, nd.branch_id)

    def _on_tech_node_select(self, key: str) -> None:
        """网络图上点选节点后由 TechPage 回调：重算状态 + 刷新详情面板。"""
        page = self._page
        if not isinstance(page, S.TechPage):
            return
        page.selected_key = key
        self._refresh_tech_page()

    @staticmethod
    def _branch_effect(branch, idx: int) -> str:
        """把分支的 L{n} 效果 dict 压成一行短文案"""
        try:
            eff = branch.effects_per_level[idx]
        except Exception:
            return '--'
        if not isinstance(eff, dict):
            return str(eff)[:18]
        parts = []
        for k, v in list(eff.items())[:2]:
            if isinstance(v, (int, float)):
                parts.append(f"{k} ×{v:.2f}")
            else:
                parts.append(f"{k}")
        return "；".join(parts)[:22] or '--'

    # ---- S10 成就页 ----
    ACH_ICONS = {}

    def _refresh_ach_page(self, filt=None, page=None) -> None:
        page = page if page is not None else self._page
        if not isinstance(page, S.AchPage):
            return
        if filt:
            self._ach_filter = filt
            page.set_filter_visual('all' if filt == 'miss' else filt)
        cur = getattr(self, '_ach_filter', 'all')
        p = engine.player
        lang = get_lang()
        cond = list(achievements_mod.ACHIEVEMENTS)
        evt = list(achievements_mod.EVENT_ACHIEVEMENTS.values())
        cond_got = sum(1 for a in cond if a.ach_id in p.achievements)
        evt_got = sum(1 for a in evt if a.ach_id in p.achievements)

        items = []
        if cur in ('all', 'miss'):
            items = [(a, False) for a in cond] + [(a, True) for a in evt]
        elif cur == 'cond':
            items = [(a, False) for a in cond]
        else:
            items = [(a, True) for a in evt]
        cells = []
        for a, is_evt in items:
            got = a.ach_id in p.achievements
            if cur == 'miss' and got:
                continue
            icon = (a.icon or a.ach_id[:1]).strip() or '·'
            cells.append((icon, a.name(lang), a.desc(lang)[:26], got, is_evt))

        nearest = [(a.name(lang), self._ach_progress(a))
                   for a in cond if a.ach_id not in p.achievements][:3]
        page.rebuild(cells, cond_got + evt_got, len(cond) + len(evt),
                     cond_got, len(cond), evt_got, len(evt),
                     getattr(self, '_ach_new_count', 0), nearest)

    def _ach_progress(self, ach) -> str:
        """给「最接近达成」的成就估算一个进度文案"""
        try:
            ctx = engine.build_achievement_context()
            v = ach.condition(ctx) if ach.condition else False
            return '✓' if v else '…'
        except Exception:
            return '…'

    # ---- S12 设置：存档槽位 ----
    def _slot_rows(self):
        rows = []
        for i, name in enumerate(('slot1', 'slot2', 'slot3')):
            title = t('slot_name_fmt').format(n=f"{i+1:02d}")
            path = os.path.join(save_manager.SAVE_DIR, f'{name}.json')
            if os.path.exists(path):
                try:
                    import json
                    with open(path, encoding='utf-8') as f:
                        data = json.load(f)
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
            else:
                summary = t('slot_empty')
            rows.append((title, summary, name == 'slot1'))
        return rows

    def _slot_actions(self, title):
        """按槽位名生成 保存/读取/删除 三个动作。

        保存按钮指向 ``_save_slot_confirm``：槽位已有档时先弹覆盖确认，
        空槽直接保存。删除按钮用 i18n 的「删除」文案（不再用 ✕ 符号）。
        """
        import re
        m = re.search(r'(\d+)', title)
        idx = int(m.group(1)) if m else 1
        slot = f'slot{idx}.json'
        return [
            (t('save_button'), 'primary', lambda s=slot: self._save_slot_confirm(s)),
            (t('load_button'), 'plain', lambda s=slot: self._load_slot(s)),
            (t('delete_button'), 'danger', lambda s=slot: self._delete_slot(s)),
        ]

    def _save_slot_confirm(self, slot: str) -> None:
        """保存到槽位：空槽直接存；已有档先弹覆盖确认弹窗。"""
        path = os.path.join(save_manager.SAVE_DIR, slot)
        if not os.path.exists(path):
            self._save_slot(slot)
            return
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
                                                self._save_slot(slot)))
        row.add_widget(cancel)
        row.add_widget(ok)
        body.add_widget(row)
        pop = make_modal(body, size_hint=(0.5, 0.62), skin='lose',
                         close_on_outside=True)
        pop.open()



    def _set_lang_idx(self, idx: int) -> None:
        set_lang(LANG_EN if idx == 1 else LANG_ZH)
        self._rebuild_lang()

    def _set_grid(self, idx: int) -> None:
        self.map_widget.set_grid_mode(idx)

    # ========================================================
    # 检视卡（S03）
    # ========================================================
    def on_map_country_click(self, code: str) -> None:
        """地图点击分发：投放模式 → 切换目标；否则 → 打开检视卡"""
        sfx.play('select')
        if self.drop_mode and self.drop_step >= 1:
            self.toggle_target(code)
            return
        engine.select_country(code)
        self.focus_country = code
        self._open_inspector(code)
        self.refresh_all()

    def _open_inspector(self, code: str) -> None:
        if self._inspector is None:
            self._inspector = S.InspectorPanel(
                on_close=self._close_inspector,
                on_drop=self._on_inspector_drop,
                on_focus=self._on_inspector_focus)
            self._inspector.pos_hint = {'x': 0, 'y': 0}
            self.map_stage.add_widget(self._inspector)
        self._inspector.update(
            self._country_state(code), self.stats,
            engine.player.total_downloads_m, engine.player.suspicion,
            TUNE['unlock_penetration_threshold'])

    def _close_inspector(self) -> None:
        if self._inspector is not None:
            self.map_stage.remove_widget(self._inspector)
            self._inspector = None

    def _on_inspector_focus(self, code: str) -> None:
        self.map_widget.set_selected(code)
        self._notify(f"★ {get_country_name(code)}")

    def _on_inspector_drop(self, code: str) -> None:
        self.start_drop(None, [code])

    @staticmethod
    def _country_state(code: str):
        return next((c for c in engine.player_countries
                     if c.config.code == code), None)

    # ========================================================
    # 事件日志抽屉（S14）
    # ========================================================
    def toggle_log(self) -> None:
        if self._log_drawer is not None:
            self._close_log()
            return
        self._log_drawer = S.LogDrawer(
            on_close=self._close_log,
            on_clear=self._mark_logs_read,
            on_export=self._export_log)
        self._log_drawer.pos_hint = {'right': 1, 'y': 0}
        self.map_stage.add_widget(self._log_drawer)
        self._log_drawer.rebuild(self.stats.logs, self.stats.unread)
        self.rail.set_active('log')

    def _close_log(self) -> None:
        if self._log_drawer is not None:
            self.map_stage.remove_widget(self._log_drawer)
            self._log_drawer = None
        self.rail.set_active('none')

    def _mark_logs_read(self) -> None:
        self.stats.clear_unread()
        if self._log_drawer is not None:
            self._log_drawer.rebuild(self.stats.logs, 0)

    def _export_log(self) -> None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'event_log.txt')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for item in reversed(self.stats.logs):
                    f.write(f"[{item.get('tick', 0)}] {item.get('text', '')}\n")
            self._notify(f"{t('log_export')} → event_log.txt")
        except Exception:
            self._notify(t('load_fail'))

    # ========================================================
    # 投放模式（S04 三步状态机）
    # ========================================================
