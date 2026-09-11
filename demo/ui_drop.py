"""
ui_drop.py - DropMixin（拆分自 main.py）

投放模式状态机（设计稿 S04）：选技能 → 选目标（准星层）→ 确认投放
"""
from kivy.uix.floatlayout import FloatLayout

from i18n import t, get_country_name
import engine
import sfx
import pixel_assets as PA
from data import SKILLS
import ui_v4_screens as S
from ui_hud import region_codes
from ui_v4 import Reticle, TgtLabel


# ============================================================
# DropMixin —— GameUI 的投放模式（S04）
# ============================================================
class DropMixin:
    def toggle_drop_mode(self) -> None:
        if self.drop_mode:
            self._cancel_drop()
        else:
            self.start_drop(None, None)

    def _primary_drop_action(self) -> None:
        """底部大按钮的统一行为（文案与行为保持一致）：
        投放中且有目标 → 确认投放；投放中无目标 → 取消；否则进入投放。"""
        if self.drop_mode:
            if self.drop_targets:
                self._confirm_drop()
            else:
                self._cancel_drop()
        else:
            self.start_drop(None, None)

    def start_drop(self, skill_id, codes) -> None:
        """进入投放模式。

        Args:
            skill_id: 已选技能（None = 停在步骤 ①）
            codes: 初始目标（None = 空）
        """
        self.drop_mode = True
        self.drop_skill = skill_id
        self.drop_targets = list(codes or [])
        self.drop_step = 0 if not skill_id else (1 if not self.drop_targets else 2)
        self._close_inspector()
        self.steps_hud.opacity = 1
        self.drop_hud.opacity = 1
        self.region_hud.opacity = 0
        self.reason_hud.opacity = 1
        self.rail.set_active('drop')
        self._ensure_reticle_layer()
        # 投放模式下右上角提示(drop_hud)与图层HUD(layer_hud)同锚'tr'，
        # 让 layer_hud 下沉避开，消除右上角两层 HUD 叠在一起（问题 #5）。
        # 写 _base_top_inset（LayerHud._sync 会在此基础上再加 TOP_GAP）。
        self.layer_hud._base_top_inset = 46
        self.layer_hud._sync()
        self.layer_hud._layout_hud()
        self._sync_drop_ui()

    def _cancel_drop(self) -> None:
        self.drop_mode = False
        self.drop_skill = None
        self.drop_targets = []
        self.drop_step = 0
        self.steps_hud.opacity = 0
        self.drop_hud.opacity = 0
        self.reason_hud.opacity = 0
        self.region_hud.opacity = 1
        self.rail.set_active('none')
        self.map_widget.set_target_mode(None, None)
        self._clear_reticles()
        # 退出投放：图层HUD 归位到顶右角
        self.layer_hud._base_top_inset = 0
        self.layer_hud._sync()
        self.layer_hud._layout_hud()
        # 按钮文案必须在这里复位（玩家反馈 #3b）——
        # refresh_all() 里对按钮的同步受 drop_mode 门控，而此处刚把它置假，
        # 不显式同步就会残留「确认投放」。
        self._sync_drop_button()
        self.refresh_all()

    def _ensure_reticle_layer(self) -> None:
        if not hasattr(self, '_reticle_layer'):
            self._reticle_layer = FloatLayout(size_hint=(1, 1),
                                              pos_hint={'x': 0, 'y': 0})
            self._reticle_layer.opacity = 1
            self.map_stage.add_widget(self._reticle_layer)
        else:
            if self._reticle_layer.parent is None:
                self.map_stage.add_widget(self._reticle_layer)

    def _clear_reticles(self) -> None:
        for w in self._reticles:
            if w.parent is not None:
                w.parent.remove_widget(w)
        self._reticles = []

    def toggle_target(self, code: str) -> None:
        ok, reason, _disc = engine.target_availability(
            code, self.drop_skill, len(self.drop_targets))
        if not ok:
            self._notify(f"{get_country_name(code)}: {self._reason_text(reason, code)}")
            return
        if code in self.drop_targets:
            self.drop_targets.remove(code)
        else:
            self.drop_targets.append(code)
        self.drop_step = 2 if self.drop_targets else 1
        self._sync_drop_ui()

    def _select_region_targets(self) -> None:
        """「按区域全选」：把当前区域所有可投国家加入/移出目标"""
        if not self.active_region or not self.drop_skill:
            return
        codes = [c for c in region_codes(self.active_region)
                 if engine.target_availability(c, self.drop_skill,
                                               len(self.drop_targets))[0]]
        if all(c in self.drop_targets for c in codes) and codes:
            for c in codes:
                self.drop_targets.remove(c)
        else:
            for c in codes:
                if c not in self.drop_targets:
                    self.drop_targets.append(c)
        self.drop_step = 2 if self.drop_targets else 1
        self._sync_drop_ui()

    def _reason_text(self, reason: str, code: str = '') -> str:
        if reason == engine.TARGET_NO_COMPUTE:
            skill = SKILLS.get(self.drop_skill)
            need = engine.skill_cost_for(self.drop_skill, len(self.drop_targets) + 1)
            return t('reason_no_compute').format(n=f"{need - engine.player.compute:.0f}")
        if reason == engine.TARGET_SATURATED:
            return t('reason_saturated')
        if reason == engine.TARGET_BLOCKED:
            cs = self._country_state(code)
            pct = (cs.current_block_intensity * 100) if cs else 0
            return t('reason_blocked').format(n=f"{pct:.0f}")
        return t('reason_locked')

    def _sync_drop_ui(self) -> None:
        """刷新投放模式的全部 UI（步骤条 / 准星 / 预览 / 原因条）"""
        self.steps.set_current(self.drop_step)
        p = engine.player
        # 顶栏提示
        #
        # 玩家反馈 #4：「算力明明够，却投不出去」。根因是算力按目标数**线性
        # 叠加**（cost × N），而顶栏只写「已选 N 国」，玩家无法预判总价。
        # 这里把「已选数 / 总消耗 / 现有算力」一并显示，投不出去时立刻
        # 看得到差在哪，而不是反复点确认却没反应。
        if self.drop_skill:
            n = len(self.drop_targets)
            cost = engine.skill_cost_for(self.drop_skill, max(n, 1))
            if p.compute >= cost:
                self.drop_hint.set_tone('on', t('drop_selected_cost').format(
                    n=n, cost=f"{cost:.0f}", have=f"{p.compute:.0f}"))
            else:
                self.drop_hint.set_tone('cost', t('drop_short_cost').format(
                    n=n, cost=f"{cost:.0f}", have=f"{p.compute:.0f}",
                    short=f"{cost - p.compute:.0f}"))
        else:
            self.drop_hint.set_tone('on', t('drop_click_hint'))

        # 技能带高亮
        for sid, card in self.skill_cards.items():
            card.set_selected(sid == self.drop_skill)

        # 地图目标态 + 准星
        targets, dims = [], []
        if self.drop_skill:
            for c in engine.player_countries:
                code = c.config.code
                ok, reason, _ = engine.target_availability(
                    code, self.drop_skill, len(self.drop_targets))
                if code in self.drop_targets:
                    targets.append(code)
                elif ok:
                    targets.append(code) if code not in targets else None
                else:
                    dims.append(code)
        if self.drop_skill:
            self.map_widget.set_target_mode(
                {c for c in targets if c in self.drop_targets} or None,
                None)
        self._update_reticles()

        # 原因条
        locked = [c for c in dims
                  if self._country_state(c) and not self._country_state(c).unlocked]
        if locked:
            self.reason_chips[0].opacity = 1
            self.reason_chips[0].set_tone('lock', "·".join(locked[:8]) + " " + t('reason_locked'))
        else:
            self.reason_chips[0].opacity = 0
        if self.drop_targets and self.drop_skill:
            self.reason_chips[1].opacity = 1
            self.reason_chips[1].set_tone('lock',
                                          f"{'+'.join(self.drop_targets[:4])} {t('drop_sel_mark')}")
        else:
            self.reason_chips[1].opacity = 0

        # 右下预览
        if self.drop_skill and self.drop_targets:
            self._show_drop_preview()
        else:
            self._hide_drop_preview()

        # 底部按钮
        #
        # ⚠️ 修复（玩家反馈 #3b）：旧写法只在 drop_mode 为真时调用本函数，
        #    投放成功后 _cancel_drop() 立刻把 drop_mode 置假，导致
        #    refresh_all() 再也不会同步按钮文案 —— 按钮上残留的
        #    「✔ 确认投放」要等玩家再手点一次才消失。
        #    现在文案完全由状态推导（_sync_drop_button），并由
        #    _cancel_drop / refresh_all 无条件调用，杜绝残留。
        self._sync_drop_button()

    def _sync_drop_button(self) -> None:
        """底部主按钮文案的唯一来源（与 drop_mode / drop_targets 严格同源）。

        玩家反馈 #3b：投放结束后按钮仍显示「确认投放」需再点一次才复位；
        且全局技能点击后也被显示成「确认投放」—— 根因都是按钮文案由
        瞬时路径分别赋值、而非由状态统一推导。这里收敛成一处。
        """
        btn = getattr(self, 'btn_drop', None)
        if btn is None:
            return
        actionable = bool(getattr(self, 'drop_mode', False)
                          and self.drop_skill and self.drop_targets)
        btn.text = (f"✔ {t('drop_confirm')}" if actionable
                    else f"⊕ {t('quick_drop')}")
        btn.disabled = False

    def _show_drop_preview(self) -> None:
        if not hasattr(self, '_drop_preview'):
            self._drop_preview = S.DropPreview(
                on_confirm=self._confirm_drop, on_cancel=self._cancel_drop)
            self._drop_preview.pos_hint = {'right': 1, 'y': 0}
            self.map_stage.add_widget(self._drop_preview)
        skill = SKILLS[self.drop_skill]
        p = engine.player
        effects = []
        if skill.downloads_mult > 1.0:
            effects.append((f"{t('stats_downloads')} ×{skill.downloads_mult:.2f}"
                            f" ×{len(self.drop_targets)}", 'up'))
        if skill.suspicion_delta > 0:
            effects.append((f"{t('stats_suspicion')} +{skill.suspicion_delta:.0f}%"
                            f" ×{len(self.drop_targets)}", 'dn'))
        if skill.compute_mult > 1.0:
            effects.append((f"steal ×{skill.compute_mult:.1f}", 'sys'))
        effects.append((f"{t('sk_sort_cd')} {skill.cooldown}", 'cost'))
        ests = []
        for code in self.drop_targets[:3]:
            cs = self._country_state(code)
            if cs:
                before = cs.downloads_m
                ests.append((code, before, before * skill.downloads_mult))
        warn = ''
        if skill.suspicion_delta > 0:
            after = p.suspicion + skill.suspicion_delta * len(self.drop_targets)
            warn = (f"⚠ {t('stats_suspicion')} {p.suspicion:.0f}% → {after:.0f}%")
        self._drop_preview.update(
            self.drop_skill, self._skill_name(self.drop_skill),
            self.drop_targets, skill.cost, p.compute, effects, ests, warn)

    def _hide_drop_preview(self) -> None:
        if hasattr(self, '_drop_preview') and self._drop_preview.parent is not None:
            self.map_stage.remove_widget(self._drop_preview)

    def _update_reticles(self) -> None:
        """在可投国家上画准星 + 预估标签"""
        self._clear_reticles()
        if not self.drop_skill or not hasattr(self, '_reticle_layer'):
            return
        skill = SKILLS[self.drop_skill]
        for c in engine.player_countries:
            code = c.config.code
            ok, reason, _d = engine.target_availability(
                code, self.drop_skill, len(self.drop_targets))
            if not ok:
                continue
            x, y = self._country_screen_pos(code)
            size = 66 if code in self.drop_targets else 48
            ret = Reticle(size, color_name='yellow')
            ret.pos = (x - size / 2, y - size / 2)
            self._reticle_layer.add_widget(ret)
            self._reticles.append(ret)
            lbl = TgtLabel('', tone='ok')
            boost = f"+{(skill.downloads_mult - 1) * 100:.0f}%" \
                if skill.downloads_mult > 1.0 else f"×{skill.stealth_ratio_mult:.1f}"
            text = f"{get_country_name(code)} {code} · {boost}"
            if code in self.drop_targets:
                text = "✔ " + text
            lbl.set_state(text, 'ok')
            lbl.pos = (x - lbl.width / 2, y + 10)
            self._reticle_layer.add_widget(lbl)
            self._reticles.append(lbl)

    def _country_screen_pos(self, code: str):
        """国家锚点的窗口坐标（准星/标签定位用）

        ⚠️ world_map 的 canvas 用的是**父容器坐标系**，这里用同一套 _map_rect()
        换算，保证准星与地图块严丝合缝。
        """
        ox, oy, mw, mh = self.map_widget._map_rect()
        cw = mw / float(self.map_widget.GRID_W)
        ch = mh / float(self.map_widget.GRID_H)
        ax, ay = PA.ANCHORS[code]
        return ox + ax * cw, oy + mh - ay * ch

    def country_center(self, code: str):
        """国家锚点在 ``_reticle_layer`` 局部坐标系下的中心点。

        供 ``ui_fx.beacon``（动效层）回调使用 —— 动效层不 import 本模块，
        只 duck-typing 调用 ``stage.country_center(code)``，避免反向依赖。

        Returns:
            (x, y) 元组；**布局尚未完成或坐标缺失时返回 None**（动效层安全跳过）。
            注意必须在布局完成后调用：未布局时 ``_map_rect()`` 会退化为
            1×1 兜底矩形，换算出的坐标会飞到屏幕外（宁可不动效也不要错位）。
        """
        if not hasattr(self, '_reticle_layer'):
            return None
        # 布局未完成时 _map_rect() 会退化成一个小的兜底矩形（例如 100×50），
        # 换算出的坐标会飞出舞台 —— 这里用最小尺寸门槛拦掉，宁可不动效也别错位。
        if self.map_widget.width < 32 or self.map_widget.height < 32:
            return None
        try:
            ox, oy, mw, mh = self.map_widget._map_rect()
        except Exception:
            return None
        if mw < 32 or mh < 32:
            return None
        try:
            x, y = self._country_screen_pos(code)
        except Exception:
            return None
        # 舞台局部坐标 → _reticle_layer 局部坐标（动效控件挂在准星层上）
        try:
            return self._reticle_layer.to_local(x, y)
        except Exception:
            return None

    def _confirm_drop(self) -> None:
        if not (self.drop_skill and self.drop_targets):
            return
        skill_id = self.drop_skill
        targets = list(self.drop_targets)
        try:
            if engine.use_skill(skill_id, targets):
                sfx.play('cast')
                self.stats.mark_skill(skill_id, 0.0)
                self.selected_skill = skill_id
                self._notify(f"{self._skill_name(skill_id)} → {'+'.join(targets)}")
                self._fx_cast(skill_id, targets)
        finally:
            # 无论投放成功与否，都回到正常游戏内（不退出会话）
            self._cancel_drop()

    def _cast_skill_direct(self, sid: str) -> None:
        """全局技能（偷算力类）直接释放"""
        if engine.use_skill(sid, None):
            self.stats.mark_skill(sid, 0.0)
            self.selected_skill = sid
            self._notify(f"{self._skill_name(sid)}")
            self._fx_cast(sid, [])
        else:
            self._notify(t('no_compute'))
            self._fx_reject(sid)

    # ---- 动效反馈（玩家反馈 5：让"这一下生效了"看得见）----
    def _fx_cast(self, sid: str, targets) -> None:
        """技能释放成功的视觉反馈：技能卡脉冲 + 目标国信标光环 + 浮字。

        全部走 ui_fx（尊重「动效减弱」开关）；动效失败绝不影响游戏逻辑，
        因此整段包在 try 里 —— 动效是锦上添花，不能成为新的崩溃点。
        """
        try:
            import ui_fx
            card = self.skill_cards.get(sid)
            if card is not None:
                ui_fx.pulse(card, scale_alpha=0.5)
            if targets:
                # 首次释放可能早于任何一次进入投放模式，准星层尚未创建 ——
                # 这里按需补建，避免动效丢失（动效层只 duck-typing，不 import 本模块）。
                self._ensure_reticle_layer()
            for code in (targets or []):
                # 求坐标用 self（GameUI 才有 country_center），
                # 挂控件用准星层（与地图同坐标系）。
                ui_fx.beacon(self, code, container=self._reticle_layer)
        except Exception:
            pass

    def _fx_reject(self, sid: str) -> None:
        """技能释放失败（算力不足）的抖动反馈。"""
        try:
            import ui_fx
            card = self.skill_cards.get(sid)
            if card is not None:
                ui_fx.shake(card)
        except Exception:
            pass

