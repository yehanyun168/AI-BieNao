"""
ui_commissions.py - CommissionMixin（P0-3 动态委托的 UI 层）

设计语言：design/ardot_ui/（S05 HUD 组件库 / S06 状态芯片 / ⚠ 预警样式）
- CommissionBar：地图左上委托芯片条（待接受=琥珀 / 进行中=青色进度）
- show_commission_modal：委托详情弹窗（目标 / 时限 / 奖励 / 接受 / 放弃）
- 引擎接线：engine.accept_commission / engine.decline_commission（纯函数在 commissions.py）

职责边界：本模块只读引擎状态 + 调引擎纯接口，不碰数值；布局挂在
HudMixin 建好的 map_stage 上（GameUI MRO 中 CommissionMixin 先于 HudMixin）。
"""
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout

import engine
import commissions as C
from balance import TUNE
from data import SKILLS
import ui_v4 as U
from ui_v4 import PxChip, mk_label
from ui_shared import COLORS
from ui_hud import HudBox
from ui_modal import make_button, make_modal, modal_header, hline
from i18n import t, get_lang, get_country_name


# ============================================================
# 文案辅助（委托 → 人类可读）
# ============================================================
def _name_of(com) -> str:
    """委托名（按当前语言取模板中英名）。"""
    return com.name_zh if get_lang() == 'zh' else com.name_en


def _goal_text(com) -> str:
    """把委托目标翻译成带参数的完整文案（弹窗正文用）。"""
    if com.goal == 'pen':
        return t('com_goal_pen').format(
            country=get_country_name(com.target_country) or com.target_country,
            target=com.target_value)
    if com.goal == 'downloads':
        return t('com_goal_downloads').format(target=com.target_value)
    if com.goal == 'compute':
        return t('com_goal_compute').format(target=com.target_value)
    if com.goal == 'skill':
        sk = SKILLS.get(com.skill_id)
        return t('com_goal_skill').format(
            skill=(sk.name if sk else (com.skill_id or '?')),
            target=int(com.target_value))
    if com.goal == 'stealth':
        return t('com_goal_stealth').format(target=com.target_value)
    return t('com_goal_unlock').format(target=com.target_value)


def _progress(com) -> str:
    """进行中委托的进度短文案（芯片用），读引擎增量 ctx（只读）。"""
    ctx = engine.build_commission_ctx(com)
    if com.goal == 'pen':
        return f"{ctx['target_pen_delta']:.1f}/{com.target_value:.1f}"
    if com.goal == 'downloads':
        return f"{ctx['downloads_delta']:.1f}/{com.target_value:.1f}M"
    if com.goal == 'compute':
        return f"{ctx['compute_earned_delta']:.0f}/{com.target_value:.0f}"
    if com.goal == 'skill':
        uses = ctx['skill_uses_delta'].get(com.skill_id, 0)
        return f"{uses}/{int(com.target_value)}"
    if com.goal == 'stealth':
        return f"{t('com_sus_short')} {ctx['suspicion']:.0f}/{com.target_value:.0f}"
    return f"{ctx['unlocked_delta']:.0f}/1"


# ============================================================
# CommissionBar —— 地图左上委托芯片条
# ============================================================
class CommissionBar(HudBox):
    """横向委托芯片条：待接受（琥珀）+ 进行中（青），点击弹详情。"""

    def __init__(self, on_open=None, **kwargs):
        super().__init__(anchor='tl', **kwargs)
        self._on_open = on_open or (lambda com: None)
        self._hidden = False
        self.chips = []
        self.row = BoxLayout(orientation='horizontal', spacing=6,
                             size_hint=(None, None), height=34)
        self.add_widget(self.row)

    # -- HudBox 布局钩子：隐藏时收成 0 尺寸（不动 _content_w 声明） --
    def _layout_hud(self, *_args) -> None:
        if self._hidden:
            self.size = (0, 0)
            self._redraw()
            return
        super()._layout_hud(*_args)

    def set_hidden(self, hidden: bool) -> None:
        self._hidden = bool(hidden)
        self._layout_hud()

    def refresh(self, items) -> None:
        """按引擎当前委托列表重建芯片（每周期经 refresh_all 调用）。"""
        p = engine.player
        if p is None:
            return
        tick = p.tick_count
        self.row.clear_widgets()
        self.chips = []
        for com in items:
            if com.status == 'offered':
                ttl = TUNE['commission_offer_ttl'] - (tick - com.offered_tick)
                est = C.compute_reward(tick, com.reward_mult)
                txt = (f"{com.icon} {_name_of(com)} · "
                       f"~{est:.0f}{t('com_reward_unit')} · "
                       f"{t('com_left_short')}{max(ttl, 0)}{t('com_left_unit')}")
                chip = PxChip(text=txt, tone='cost', height=34,
                              on_press=(lambda *_a, cm=com: self._on_open(cm)))
            else:
                left = (com.deadline_tick - tick) if com.deadline_tick else 0
                txt = (f"{com.icon} {_name_of(com)} · {_progress(com)} · "
                       f"{t('com_left_short')}{max(left, 0)}{t('com_left_unit')}")
                chip = PxChip(text=txt, tone='on', height=34,
                              on_press=(lambda *_a, cm=com: self._on_open(cm)))
            self.row.add_widget(chip)
            self.chips.append(chip)
        # PxChip 宽度随纹理自适应，下一帧再量总宽
        Clock.schedule_once(lambda *_dt: self._measure(), 0)

    def _measure(self) -> None:
        if not self.chips:
            return
        w = sum(c.width for c in self.chips) + \
            self.row.spacing * max(len(self.chips) - 1, 0)
        self.content_size(max(w, 40) + 2, 34)


# ============================================================
# CommissionMixin —— GameUI 装配层
# ============================================================
class CommissionMixin:
    """委托 UI：建条 / 刷新 / 弹窗 / 接受与放弃。"""

    # MRO 中先于 HudMixin：先建完标准 HUD，再把委托条挂上地图舞台
    def _build_ui(self) -> None:
        super()._build_ui()
        self.commission_bar = CommissionBar(on_open=self.show_commission_modal)
        self.commission_bar.set_hidden(True)
        self.map_stage.add_widget(self.commission_bar)

    def refresh_commissions(self) -> None:
        """同步引擎委托状态到芯片条（空列表时整条隐藏）。"""
        bar = getattr(self, 'commission_bar', None)
        p = engine.player
        if bar is None or p is None:
            return
        items = list(p.commissions)
        bar.set_hidden(not items)
        if items:
            bar.refresh(items)

    # ---- 详情弹窗 ----
    def show_commission_modal(self, com) -> None:
        p = engine.player
        if p is None or com is None:
            return
        offered = (com.status == 'offered')
        est = C.compute_reward(p.tick_count, com.reward_mult)

        body = BoxLayout(orientation='vertical', spacing=10, padding=(14, 10))
        tag = t('com_offer_tag') if offered else t('com_active_tag')
        body.add_widget(modal_header(
            com.icon, _name_of(com),
            chips=[PxChip(text=f"{com.template_id} · {tag}",
                          tone='cost' if offered else 'on')]))
        body.add_widget(mk_label(_goal_text(com), font_size=U.FS_BODY,
                                 color=COLORS['text'], size_hint_y=None,
                                 height=56))
        body.add_widget(hline())
        if com.goal == 'pen' and com.target_country:
            body.add_widget(mk_label(
                f"{get_country_name(com.target_country) or com.target_country}"
                f" · {com.window}{t('com_left_unit')}",
                font_size=U.FS_CAP, color=U.MK['dim'], size_hint_y=None,
                height=30))
        else:
            body.add_widget(mk_label(
                f"{t('com_left_short')}{com.window}{t('com_left_unit')}",
                font_size=U.FS_CAP, color=U.MK['dim'], size_hint_y=None,
                height=30))
        if offered:
            body.add_widget(mk_label(
                f"{t('com_reward_est')} ~{est:.0f}{t('com_reward_unit')}",
                font_size=U.FS_CAP, color=COLORS['yellow'], size_hint_y=None,
                height=30))
        if com.sus_relief:
            body.add_widget(mk_label(
                t('com_c5_bonus').format(relief=com.sus_relief),
                font_size=U.FS_CAP, color=COLORS['cyan'], size_hint_y=None,
                height=30))
        body.add_widget(BoxLayout())    # 弹性占位

        btns = BoxLayout(orientation='horizontal', spacing=10,
                         size_hint_y=None, height=52)
        holder = {}

        def _close(*_a):
            m = holder.get('m')
            if m is not None and m.parent is not None:
                m.dismiss()

        if offered:
            btns.add_widget(make_button(
                t('com_accept'),
                on_release=lambda *_a: (self._accept_commission(com.uid),
                                        _close())))
            btns.add_widget(make_button(
                t('com_decline'),
                on_release=lambda *_a: (self._decline_commission(com.uid),
                                        _close())))
        else:
            btns.add_widget(make_button(t('com_close'), on_release=_close))
        body.add_widget(btns)

        holder['m'] = make_modal(body, size_hint=(0.5, 0.62))

    # ---- 引擎调用（纯接口，无 UI 逻辑）----
    def _accept_commission(self, uid: int) -> None:
        if engine.accept_commission(uid):
            com = next((c for c in engine.player.commissions
                        if c.uid == uid), None)
            if com is not None:
                self._notify(f"{t('com_active_tag')}: {_name_of(com)}")
            self.refresh_commissions()

    def _decline_commission(self, uid: int) -> None:
        com = next((c for c in engine.player.commissions
                    if c.uid == uid and c.status == 'offered'), None)
        nm = _name_of(com) if com is not None else '?'
        if engine.decline_commission(uid):
            self._notify(f"{t('com_declined_log')}: {nm}")
            self.refresh_commissions()
