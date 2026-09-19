"""
ui_drop.py - DropMixin（拆分自 main.py）

投放模式状态机：选技能 → 点击或拖到单个国家后立即投放
"""
from kivy.uix.floatlayout import FloatLayout

from i18n import t, get_country_name
import engine
import sfx
import pixel_assets as PA
from data import SKILLS
from ui_v4 import Reticle, TgtLabel


# ============================================================
# DropMixin —— GameUI 的投放模式（S04）
# ============================================================
class DropMixin:
    def toggle_drop_mode(self) -> None:
        if self.drop_mode:
            self._cancel_drop()
        else:
            self.start_drop(None)

    def start_drop(self, skill_id) -> None:
        """进入投放模式。

        Args:
            skill_id: 已选技能（None = 停在步骤 ①）
        """
        self.drop_mode = True
        self.drop_skill = skill_id
        # 单目标即时投放不保留预选目标，选好技能后等待一次点击/松手。
        self.drop_targets = []
        self.drop_step = 0 if not skill_id else 1
        self._close_inspector()
        self.steps_hud.opacity = 1
        self.drop_hud.opacity = 1
        self.region_hud.opacity = 0
        self.reason_hud.opacity = 1
        self.rail.set_active('drop')
        self._ensure_reticle_layer()
        sfx.play('drop')                  # 进入投放模式的发射音
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
        self._hide_skill_drag_ghost()
        # 退出投放：图层HUD 归位到顶右角
        self.layer_hud._base_top_inset = 0
        self.layer_hud._sync()
        self.layer_hud._layout_hud()
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
        """点击国家后立即执行单目标投放（保留旧方法名供地图回调使用）。"""
        ok, reason, _disc = engine.target_availability(code, self.drop_skill)
        if not ok:
            sfx.play('error')             # 目标不可选（算力不足/该国不适格）—— 与文字原因配对
            self._notify(f"{get_country_name(code)}: {self._reason_text(reason, code)}")
            return
        self._cast_target_skill(self.drop_skill, code)

    def _cast_target_skill(self, skill_id: str, code: str) -> bool:
        """投放一个国家并立即退出投放态；不经过二次确认。"""
        ok = engine.use_skill(skill_id, [code])
        sfx.play('deploy' if ok else 'error')
        if ok:
            self.stats.mark_skill(skill_id, 0.0)
            self.selected_skill = skill_id
            self._notify(f"{self._skill_name(skill_id)} → {code}")
            self._fx_cast(skill_id, [code])
        self._cancel_drop()
        return ok

    def on_skill_drag_start(self, skill_id: str, pos) -> bool:
        """技能卡拖动开始：复用点击入口的可用性检查并进入投放态。"""
        if not self._skill_needs_target(skill_id):
            return False
        if self.drop_mode:
            self._cancel_drop()
        self.on_skill_card_click(skill_id)
        accepted = bool(self.drop_mode and self.drop_skill == skill_id)
        if accepted:
            self._show_skill_drag_ghost(skill_id, pos)
        return accepted

    def on_skill_drag_move(self, skill_id: str, pos) -> None:
        """拖动时只高亮指针下的一个有效国家。"""
        if not self.drop_mode or self.drop_skill != skill_id:
            return
        self._move_skill_drag_ghost(pos)
        code = self.map_widget.hit_country(*pos)
        targets = []
        if code:
            ok, _reason, _discount = engine.target_availability(code, skill_id)
            if ok:
                targets = [code]
        if targets != self.drop_targets:
            self.drop_targets = targets
            self.drop_step = 1
            self._sync_drop_ui()

    def on_skill_drag_end(self, skill_id: str, pos) -> None:
        """在有效国家上松手立即投放，其他位置取消。"""
        if not self.drop_mode or self.drop_skill != skill_id:
            return
        code = self.map_widget.hit_country(*pos)
        if code:
            ok, reason, _discount = engine.target_availability(code, skill_id)
            if ok:
                self._cast_target_skill(skill_id, code)
                return
            self._notify(f"{get_country_name(code)}: {self._reason_text(reason, code)}")
            sfx.play('error')
        self._cancel_drop()

    def _show_skill_drag_ghost(self, skill_id: str, pos) -> None:
        """显示跟随鼠标/手指的轻量技能图标。"""
        ghost = getattr(self, '_skill_drag_ghost', None)
        if ghost is None:
            ghost = TgtLabel('', tone='ok')
            ghost.size_hint = (None, None)
            ghost.size = (150, 34)
            self._skill_drag_ghost = ghost
        ghost.set_state(f"{SKILLS[skill_id].icon}  {self._skill_name(skill_id)}", 'ok')
        if ghost.parent is None:
            self.add_widget(ghost)
        self._move_skill_drag_ghost(pos)

    def _move_skill_drag_ghost(self, pos) -> None:
        ghost = getattr(self, '_skill_drag_ghost', None)
        if ghost is not None and ghost.parent is not None:
            ghost.pos = (pos[0] - ghost.width / 2, pos[1] + 18)

    def _hide_skill_drag_ghost(self) -> None:
        ghost = getattr(self, '_skill_drag_ghost', None)
        if ghost is not None and ghost.parent is not None:
            self.remove_widget(ghost)

    def _reason_text(self, reason: str, code: str = '') -> str:
        if reason == engine.TARGET_NO_COMPUTE:
            skill = SKILLS.get(self.drop_skill)
            need = engine.skill_cost_for(self.drop_skill)
            return t('reason_no_compute').format(n=f"{need - engine.player.compute:.0f}")
        if reason == engine.TARGET_SATURATED:
            return t('reason_saturated')
        if reason == engine.TARGET_BLOCKED:
            cs = self._country_state(code)
            pct = (cs.current_block_intensity * 100) if cs else 0
            return t('reason_blocked').format(n=f"{pct:.0f}")
        return t('reason_locked')

    def _sync_drop_ui(self) -> None:
        """刷新投放模式的全部 UI（步骤条 / 准星 / 原因条）。"""
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
            cost = engine.skill_cost_for(self.drop_skill)
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
                ok, reason, _ = engine.target_availability(code, self.drop_skill)
                if code in self.drop_targets:
                    targets.append(code)
                elif ok and code not in targets:
                    targets.append(code)
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

    def _update_reticles(self) -> None:
        """在可投国家上画准星 + 预估标签"""
        self._clear_reticles()
        if not self.drop_skill or not hasattr(self, '_reticle_layer'):
            return
        skill = SKILLS[self.drop_skill]
        for c in engine.player_countries:
            code = c.config.code
            ok, reason, _d = engine.target_availability(code, self.drop_skill)
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
                text = "■ " + text
            lbl.set_state(text, 'ok')
            lbl.pos = (x - lbl.width / 2, y + 10)
            self._reticle_layer.add_widget(lbl)
            self._reticles.append(lbl)

    def _country_screen_pos(self, code: str):
        """国家锚点的窗口坐标（准星/标签定位用）

        !️ world_map 的 canvas 用的是**父容器坐标系**，这里用同一套 _map_rect()
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

    def _cast_skill_direct(self, sid: str) -> None:
        """全局技能（偷算力类）直接释放"""
        if engine.use_skill(sid, None):
            sfx.play('cast')
            self.stats.mark_skill(sid, 0.0)
            self.selected_skill = sid
            self._notify(f"{self._skill_name(sid)}")
            self._fx_cast(sid, [])
        else:
            sfx.play('error')             # 算力不足/条件不满足 —— 与 _fx_reject 视觉配对
            self._notify(t('no_compute'))
            self._fx_reject(sid)

    # ---- 动效反馈（玩家反馈 5：让"这一下生效了"看得见）----
    def _fx_cast(self, sid: str, targets) -> None:
        """技能释放成功的视觉反馈：技能卡脉冲 + 目标国信标光环。

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
            pass  # 动效失败安全（同 _fx_cast）：反馈动效不能成为新崩溃点
