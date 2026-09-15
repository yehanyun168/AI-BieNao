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
import preferences
import achievements as achievements_mod
import ui_v4 as U
import ui_v4_screens as S
from ui_shared import COLORS
from ui_modal import (make_button, make_modal, modal_header, auto_h_label)
from ui_v4 import hline


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
        # 「暂停态设置页」被关闭 = 离开暂停面 → 顺带恢复对局。
        # 放这里（而非 _close_page_user）可覆盖三条关页路径：返回按钮 /
        # Esc 关页 / open_page 切页；其它页与普通设置页不受影响。
        was_pause_menu = (isinstance(self._page, S.SettingsPage)
                          and getattr(self, '_pause_menu', False))
        if self._page is not None:
            self.remove_widget(self._page)
            self._page = None
        self.rail.set_active('none')
        if was_pause_menu:
            self._leave_pause_menu()

    def _close_page_user(self) -> None:
        """用户主动退出页面（点返回 / Esc）—— 补一个返回音。

        ⚠️ 不能直接写在 close_page() 里：open_page() 切换页面时会先内部
        close_page() 再建新页，那样「切页」也会响返回音，语义就乱了。
        因此只在真正的用户退出路径（返回按钮）上挂这个包装。
        """
        sfx.play('page')
        self.close_page()

    def _build_page(self, name: str):
        if name == 'skills':
            p = S.SkillPage(on_action=self._skill_page_action,
                            on_sort=self._refresh_skill_page)
            p.ensure_cards(SKILL_ORDER)
            p.set_back_button(t('k_esc'), self._close_page_user)
            return p
        if name == 'tech':
            p = S.TechPage(on_unlock=self.on_unlock_t0,
                           on_level=self.on_upgrade_branch,
                           on_reset=self._reset_tech,
                           on_select=self._on_tech_node_select)
            p.ensure_slots(TECH_TREE)
            p.set_back_button(t('k_esc'), self._close_page_user)
            return p
        if name == 'ach':
            p = S.AchPage(on_filter=self._refresh_ach_page)
            p.set_back_button(t('k_esc'), self._close_page_user)
            return p
        if name == 'help':
            p = S.HelpPage()
            p.set_back_button(t('k_esc'), self._close_page_user)
            return p
        if name == 'settings':
            p = S.SettingsPage(
                on_lang=self._set_lang_idx,
                on_speed=self.set_speed_idx, on_grid=self._set_grid,
                on_a11y=self._set_a11y_idx, on_motion=self._set_motion_idx,
                on_sound=self._set_sound_idx,
                on_music=self._set_music_idx,
                values=preferences.get(),
                on_tutorial=self.tutorial.replay,
                slot_actions=self._slot_actions,
                on_reset=lambda: self._notify(t('set_restore')))
            p.set_back_button(t('k_esc'), self._close_page_user)
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
                        self._key_hint(sid), [],
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
        # P1-2：底部这一行从「算力 X → Y」升级成真实预览
        # （走 engine.preview_skill，与 tick 结算同源同式；不可用时给原因）
        foot = self._skill_preview_foot(sid)
        card.update(skill, self.SKILL_ICON[sid], self._skill_name(sid),
                    self._key_hint(sid), chips,
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
        lang = get_lang()
        for slot in TECH_TREE:
            done = pt.t0_unlocked.get(slot.slot_id, False)
            # --- T0 节点 ---
            tk = f"t0:{slot.slot_id}"
            if tk in page.canvas_view.nodes:
                page.canvas_view.nodes[tk].name = slot.name_for(lang)
            if done:
                t_state, t_sub = 'done', t('tt_picked')
            elif pt.can_unlock_t0(slot.slot_id):
                t_state = ('can' if engine.player.compute >= slot.t0_cost
                           else 'poor')
                t_sub = f"{slot.t0_cost:.0f}"
            else:
                t_state = 'lock'
                pre = SLOT_MAP.get(slot.prereq_slot) if slot.prereq_slot else None
                t_sub = (t('tt_need_pre').format(n=pre.name_for(lang)) if pre
                         else f"{slot.t0_cost:.0f}")
            states[tk] = {'state': t_state, 'level': 1 if done else 0,
                          'cost': 0.0 if done else slot.t0_cost, 'sub': t_sub}
            # --- 分支节点 ---
            for br in slot.branches:
                lv = pt.branch_levels.get(br.branch_id, 0)
                bk = f"br:{br.branch_id}"
                if bk in page.canvas_view.nodes:
                    page.canvas_view.nodes[bk].name = br.name_for(lang)
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
                nd.desc = (slot.description_for(lang) if slot else '')
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
            # ⚠️ 这里曾是 ``\\n``（双反斜杠）→ 源码里是字面量「反斜杠+n」，
            #    描述与「n/3 · 效果」被粘成一行、屏幕上还印出一个可见的 \n。
            #    必须是单反斜杠才是真换行。
            return f"{br.description_for(get_lang())}\n{lv}/3 · {eff}"
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
        """把分支的 L{n} 效果压成一行**本地化**短文案。

        ⚠️ 旧实现遍历 ``eff.items()`` 取前两个键，把**键名当文案**拼出来
        （`type；value ×1.10`），中文环境照样是英文 —— 这就是「科技描述显示
        英文」的根因。现在统一走 ``_effect_text`` 查 i18n。
        """
        try:
            eff = branch.effects_per_level[idx]
        except Exception:
            return '--'          # 等级越界/结构异常 → 占位符，不崩科技页
        if not isinstance(eff, dict):
            return str(eff)
        return PagesMixin._effect_text(eff) or '--'

    # 效果 dict['type'] → i18n 文案键。
    # ⚠️ tech_tree 里新增效果类型时必须在这里同步登记，否则会退化成
    #    tt_fx_unknown（宁可显示「效果」也不能漏英文键名给玩家）。
    #    守卫：test_tech_effect_i18n.py 会遍历 TECH_TREE 校验覆盖完整。
    _FX_TYPE_KEYS = {
        'block_resist': 'tt_fx_block_resist',
        'compute_per_user_mult': 'tt_fx_compute_per_user_mult',
        'downloads_mult': 'tt_fx_downloads_mult',
        'event_weight': 'tt_fx_event_weight',
        'global_downloads_mult': 'tt_fx_global_downloads_mult',
        'stealth_ratio_bonus': 'tt_fx_stealth_ratio_bonus',
        'suspicion_mult': 'tt_fx_suspicion_mult',
        'unlock_regions': 'tt_fx_unlock_regions',
        'unlock_function': 'tt_fx_unlock_function',
    }
    # 加法型效果（引擎里是 += 绝对值）→ 用「+N%」；其余乘法型用「×N.NN」
    _FX_ADDITIVE = ('block_resist', 'stealth_ratio_bonus')

    @staticmethod
    def _effect_text(eff) -> str:
        """把一个效果 dict 压成一行本地化文案（名称 + 数值 + 作用范围）。"""
        if not isinstance(eff, dict):
            return str(eff)
        ftype = eff.get('type', '')
        key = PagesMixin._FX_TYPE_KEYS.get(ftype)
        name = t(key) if key else t('tt_fx_unknown')
        val = eff.get('value')
        if not isinstance(val, (int, float)):
            return name
        if ftype in PagesMixin._FX_ADDITIVE:
            txt = f"{name} +{val * 100:.0f}%"
        else:
            txt = f"{name} ×{val:.2f}"
        scope = eff.get('scope')
        # scope='unlocked' 表示「所有已解锁国家」，是默认口径，不必标注
        if scope and scope != 'unlocked':
            txt += t('tt_fx_scope_fmt').format(s=scope)
        return txt

    # ---- S10 成就页 ----
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
            return '■' if v else '…'
        except Exception:
            return '…'  # 条件求值异常（数据组合边界）→ 显示未完成，不崩成就页

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
                except Exception as e:
                    # 摘要读不出（多半存档损坏）：不能无声装作"空槽"——玩家会
                    # 误以为可覆盖。留痕，槽位仍按空槽显示（行为不变）。
                    print(f'[slots] !️ {name}.json 摘要读取失败（可能损坏）：{e!r}')
                    summary = t('slot_empty')
            else:
                summary = t('slot_empty')
            rows.append((title, summary, name == 'slot1'))
        return rows

    def _slot_actions(self, title):
        """按槽位名生成 保存/读取/删除 三个动作。

        保存按钮指向 ``_save_slot_confirm``：槽位已有档时先弹覆盖确认，
        空槽直接保存。删除按钮用 i18n 的「删除」文案（不再用 × 符号）。
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
        preferences.update(language=get_lang())
        self._rebuild_lang()

    def _set_grid(self, idx: int) -> None:
        import ui_shared as ST
        ST.GRID_MODE = max(0, min(int(idx), 2))
        preferences.update(grid_mode=ST.GRID_MODE)
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

    def _refresh_lang_panels(self) -> None:
        """语言切换后刷新**缓存在 map_stage 上的浮层**文案。

        检视卡 / 投放预览 / 日志抽屉都是「首次打开时建、关闭才销毁」的常驻
        浮层，语言切换走的 ``_rebuild_lang()`` 只重建带页码的页面，碰不到它们
        —— 不显式重查，中英切换后这三块会继续显示旧语种（实测：EN 下左列仍是
        「政府状态」「邻国」）。面板自带 ``refresh_lang()``，这里只负责派发。
        """
        for attr in ('_inspector', '_drop_preview', '_log_drawer'):
            panel = getattr(self, attr, None)
            fn = getattr(panel, 'refresh_lang', None)
            if callable(fn):
                fn()

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
        # 落到持久化目录（冻结态下 __file__ 指向 _MEIPASS，退出即删，必须用
        # save_manager 的持久化根目录），保证导出文件重启后仍在
        path = os.path.join(os.path.dirname(save_manager.CRASH_LOG),
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
