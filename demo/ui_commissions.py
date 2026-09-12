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
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout

import engine
import commissions as C
from balance import TUNE
from data import SKILLS
import ui_v4 as U
from ui_v4 import PxChip, mk_label
from ui_shared import COLORS
from ui_hud import HudBox, LayerHud
from ui_modal import make_button, make_modal, modal_header
from ui_v4 import hline
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
# 宽度封顶常量（P0-5）
# 芯片条内容宽上限 = 窗口宽 − 边距。留白口径复用 ui_hud.HudBox 的既有数值，
# 不另造一套：HudBox.PAD = 面板内边距；HUD_INSET = _layout_hud 的锚点内缩。
BAR_EDGE_MARGIN = 32                 # 窗口左右安全边距（整数像素）
HUD_INSET = 6                        # 与 ui_hud.HudBox._layout_hud 的 par.x + 6 一致
BAR_TAIL = 2 + HudBox.PAD * 2        # content_size 的 +2 + HudBox 两侧内边距
BAR_MIN_W = 46                       # 极窄窗口下也至少放得下一个「+N」芯片
CHIP_H = 34


class CommissionBar(HudBox):
    """横向委托芯片条：待接受（琥珀）+ 进行中（青），点击弹详情。

    P0-5：总宽封顶到「窗口宽 − 边距」，装不下的委托折叠成「+N」芯片
    （点击弹出完整列表），信息不会因为出屏而丢失。
    """

    def __init__(self, on_open=None, **kwargs):
        super().__init__(anchor='tl', **kwargs)
        # P1-6：整体下沉到左上区域页签（高 32）之下，二者同锚点不同行，
        # 委托条不再盖住页签（间隙 8）。
        self._top_inset = 40
        self._on_open = on_open or (lambda com: None)
        self._hidden = False
        self.chips = []           # 全部芯片（含被折叠的），只用于量宽
        self._items = []          # 与 self.chips 一一对应的委托对象
        self._folded = []         # 当前被折叠的委托对象
        self._plus = None         # 「+N」折叠芯片（按需创建并缓存）
        self._last_cap = -1.0     # 上次量宽时的可用宽（用于 resize 检测）
        self._measuring = False   # _measure ⇄ _layout_hud 的递归闸
        self._win_bound = False
        self._measure_ev = None
        self.row = BoxLayout(orientation='horizontal', spacing=6,
                             size_hint=(None, None), height=CHIP_H)
        self.add_widget(self.row)
        # 生命周期：只有挂在树上才监听 Window，脱离父容器立即解绑，
        # 避免回调打到已销毁的 widget（Kivy 常见崩溃源）。
        self.bind(parent=self._on_parent_change)

    # ---- Window 监听的挂载 / 卸载 ----
    def _on_parent_change(self, _inst, parent) -> None:
        if parent is not None:
            self._bind_window()
        else:
            self._unbind_window()

    def _bind_window(self) -> None:
        if self._win_bound:
            return
        try:
            Window.bind(size=self._on_window_size)
            Window.bind(on_resize=self._on_window_size)
            self._win_bound = True
        except Exception:
            self._win_bound = False  # 绑定失败 = 不随窗口缩放，面板静态布局仍可用

    def _unbind_window(self) -> None:
        if self._measure_ev is not None:
            self._measure_ev.cancel()
            self._measure_ev = None
        if not self._win_bound:
            return
        try:
            Window.unbind(size=self._on_window_size)
            Window.unbind(on_resize=self._on_window_size)
        except Exception:
            pass  # 解绑失败无碍：面板已关闭，多余回调不写游戏状态
        self._win_bound = False

    def _on_window_size(self, *_args) -> None:
        """窗口拖拽 / 缩放 → 重新量宽并重新折叠。"""
        if self._hidden or not self.chips:
            return
        self._measure()

    # -- HudBox 布局钩子：隐藏时收成 0 尺寸（不动 _content_w 声明） --
    def _layout_hud(self, *_args) -> None:
        if self._hidden:
            self.size = (0, 0)
            # P1-6：0 尺寸面板不裁剪子级，row 里残留的旧芯片仍会按绝对
            # 坐标画出来（残影）——隐藏时连 row 一起透明。
            self.row.opacity = 0
            self._redraw()
            return
        self.row.opacity = 1
        # 安全网：可用宽变了（窗口 resize / 换父容器）就重量一次，
        # 兜住 Window 事件没打到、或父容器比 Window 事件先变的场景。
        if (self.parent is not None and self.chips and not self._measuring):
            if abs(self._avail_w() - self._last_cap) > 0.5:
                self._measure()
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
        self._items = list(items)     # 与 chips 同序，折叠时用来取委托对象
        self._folded = []
        for com in items:
            if com.status == 'offered':
                ttl = TUNE['commission_offer_ttl'] - (tick - com.offered_tick)
                est = C.compute_reward(tick, com.reward_mult)
                txt = (f"{com.icon} {_name_of(com)} · "
                       f"~{est:.0f}{t('com_reward_unit')} · "
                       f"{t('com_left_short')}{max(ttl, 0)}{t('com_left_unit')}")
                chip = PxChip(text=txt, tone='cost', height=CHIP_H,
                              on_press=(lambda *_a, cm=com: self._on_open(cm)))
            else:
                left = (com.deadline_tick - tick) if com.deadline_tick else 0
                txt = (f"{com.icon} {_name_of(com)} · {_progress(com)} · "
                       f"{t('com_left_short')}{max(left, 0)}{t('com_left_unit')}")
                chip = PxChip(text=txt, tone='on', height=CHIP_H,
                              on_press=(lambda *_a, cm=com: self._on_open(cm)))
            # 先不挂到 row 上：由 _measure 决定哪些放得下（放不下的折叠）
            self.chips.append(chip)
        # 同步量一次 → 首帧就是最终宽度（原来延后一帧，会闪一下 ~40px 的窄条）
        self._measure()
        # 若字体/纹理在首帧之后才就绪，再校一次（一次性，不常驻）
        if self._measure_ev is not None:
            self._measure_ev.cancel()
        self._measure_ev = Clock.schedule_once(self._remeasure, 0)

    def _remeasure(self, *_dt) -> None:
        self._measure_ev = None
        if self.parent is None or self._hidden or not self.chips:
            return
        self._measure()

    # ---- 宽度封顶 / 折叠（P0-5）----
    def _avail_w(self) -> int:
        """内容区可用宽度上限（整数像素）。

        口径：面板右边缘 = par.x + HUD_INSET + 内容宽 + BAR_TAIL，
        必须 ≤ 窗口宽 − BAR_EDGE_MARGIN，同时不超出父容器右边。
        """
        win = float(Window.width or 0)
        if win <= 1:                       # 无窗口环境（CI/截图）兜底
            win = 1280.0
        par = self.parent
        left = HUD_INSET + BAR_TAIL
        if par is not None:
            left += float(par.x)
        cap = win - BAR_EDGE_MARGIN - left
        if par is not None and float(par.width) > 1:
            cap = min(cap, float(par.width) - HUD_INSET - BAR_TAIL)
        # P1-6：避让右上 LayerHud（同层常驻 HUD）——宽委托条此前会从
        # 它身上压过去。要求面板右缘距 LayerHud 左缘至少 12px。
        if par is not None:
            for sib in par.children:
                if isinstance(sib, LayerHud) and sib.x > self.x:
                    cap = min(cap, float(sib.x) - 12.0 - float(par.x)
                              - HUD_INSET - BAR_TAIL)
        return int(max(cap, BAR_MIN_W))

    def _ensure_plus(self, n: int) -> PxChip:
        """取得写着「+n」的折叠芯片（数量变了才重建）。

        PxChip.__init__ 会同步跑 _resize()，所以新建后 .width 立刻可用，
        不用等下一帧——否则 _measure 量到的会是旧宽度。
        """
        txt = f"+{int(n)}"
        if self._plus is None or self._plus.text != txt:
            if self._plus is not None and self._plus.parent is not None:
                self._plus.parent.remove_widget(self._plus)
            self._plus = PxChip(text=txt, tone='sys', height=CHIP_H,
                                on_press=self._show_folded)
        return self._plus

    def _measure(self) -> None:
        """量总宽 → 封顶 → 放不下的折叠成「+N」芯片。"""
        chips = self.chips
        if not chips:
            self._folded = []
            return
        gap = int(self.row.spacing)
        cap = self._avail_w()
        self._last_cap = cap
        widths = [int(round(c.width)) for c in chips]
        n = len(widths)

        def _total(k: int) -> int:
            return sum(widths[:k]) + gap * max(k - 1, 0)

        k = n
        while k > 0 and _total(k) > cap:      # 先尽可能多放
            k -= 1
        plus_w = 0
        if k < n:                             # 要折叠 → 给「+N」芯片留位
            while True:
                pw = int(round(self._ensure_plus(n - k).width))
                if k == 0 or _total(k) + gap + pw <= cap:
                    plus_w = pw
                    break
                k -= 1
        # ---- 落地：只把放得下的芯片挂上行 ----
        self.row.clear_widgets()
        for c in chips[:k]:
            self.row.add_widget(c)
        if k < n:
            self.row.add_widget(self._plus)
            self._folded = list(self._items[k:])
        else:
            self._folded = []
        w = _total(k) + (gap + plus_w if k < n else 0)
        w = min(max(int(w), 40), cap)         # 整数像素，且永不越过封顶
        self.row.width = w
        self.row.height = CHIP_H
        self._measuring = True
        try:
            self.content_size(w + 2, CHIP_H)
        finally:
            self._measuring = False

    def _show_folded(self, *_args) -> None:
        """点「+N」→ 弹出被折叠委托的完整列表（可继续点进详情）。"""
        items = list(self._folded)
        if not items:
            return
        body = BoxLayout(orientation='vertical', spacing=8, padding=(14, 10))
        body.add_widget(modal_header(
            '+', t('com_folded_title'), chips=[(f"{len(items)}", 'cost')]))
        holder = {}

        def _close(*_a):
            m = holder.get('m')
            if m is not None and m.parent is not None:
                m.dismiss()

        for com in items:
            tag = (t('com_offer_tag') if com.status == 'offered'
                   else t('com_active_tag'))
            body.add_widget(make_button(
                f"{com.icon} {_name_of(com)} · {tag}", font_size=14, height=44,
                on_release=lambda *_a, cm=com: (_close(), self._on_open(cm))))
        body.add_widget(BoxLayout())            # 弹性占位
        body.add_widget(make_button(t('com_close'), on_release=_close))
        holder['m'] = make_modal(body, size_hint=(0.5, 0.6))
        holder['m'].open()


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
            chips=[(f"{com.template_id} · {tag}", 'cost' if offered else 'on')]))
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
        holder['m'].open()

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
