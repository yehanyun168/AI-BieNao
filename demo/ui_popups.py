"""
ui_popups.py - PopupsMixin（拆分自 main.py）

弹窗族（设计稿 S07/S08/S09）：事件选择 / 危机三选一 / 结局面板 / 成就 / 帮助
加 _notify 顶部轻提示（被多个 mixin 复用，运行时经 self 解析）。
"""
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.animation import Animation

from i18n import t, get_lang
import engine
import sfx
import achievements as achievements_mod
import endings as endings_mod
import ui_v4 as U
import ui_v4_screens as S
from ui_shared import COLORS
from ui_modal import make_modal, modal_header, auto_h_label
from ui_v4 import hline
from ui_v4 import PxChip, ChipRow, StatsGrid, StrokePanel, mk_label, ST_FILL


# ============================================================
# PopupsMixin —— GameUI 的弹窗族 + 轻提示
# ============================================================
class PopupsMixin:
    def _effect_chips(self, opt) -> list:
        """把 V2Option.effects 映射成效果 chips（设计稿 S07）"""
        chips = []
        for e in getattr(opt, 'effects', []):
            kind = getattr(e, 'value_kind', 'abs')
            try:
                raw = (float(e.value) * 100 if kind == 'pct' else float(e.value))
            except Exception:
                raw = 0.0
            val = (f"{abs(raw):.0f}%" if kind == 'pct' else f"{abs(raw):.0f}")
            sign = '−' if raw < 0 else '+'
            et = getattr(e, 'type', '')
            if et == 'add_downloads':
                chips.append((f"{t('stats_downloads')} {sign}{val}",
                              'up' if raw >= 0 else 'dn'))
            elif et == 'add_suspicion':
                chips.append((f"{t('stats_suspicion')} +{val}", 'dn'))
            elif et == 'reduce_suspicion':
                chips.append((f"{t('stats_suspicion')} −{val}", 'up'))
            elif et == 'unlock_achievement':
                ach = achievements_mod.ALL_BY_ID.get(getattr(e, 'ach_id', ''))
                name = ach.name(get_lang()) if ach else (getattr(e, 'ach_id', '') or '')
                chips.append((f"★ {name}", 'sys'))
            elif et == 'add_compute_income':
                chips.append((f"{t('stats_compute')} {sign}{val}",
                              'cost' if raw >= 0 else 'dn'))
            elif et == 'trigger_ending':
                chips.append((t('end_compare'), 'sys'))
            else:
                chips.append((f"{et} {val}", 'plain'))
        return chips

    def show_choice_popup(self, evt) -> None:
        """S07 事件选择弹窗（弹出期间暂停主循环）

        单选项事件（options 只有 1 个）不是「选择」，而是「告知 + 自动结算」：
        不渲染选项按钮，直接把事件描述与影响效果摊开，配一个「知道了」确认键。
        结算仍走 resolve_choice(evt, 0)，与多选项路径共用同一套引擎逻辑。
        """
        self.stop_ticking()
        p = engine.player
        opts = list(getattr(evt, 'options', []) or [])
        solo = (len(opts) == 1)
        content = BoxLayout(orientation='vertical', spacing=0, padding=0)
        content.add_widget(modal_header(
            getattr(evt, 'icon', '◈'), getattr(evt, 'title', ''),
            [(t('evt_source_country') if solo else t('evt_source_v2'),
              'plain' if solo else 'sys'),
             (t('evt_tick_fmt').format(n=p.tick_count), 'plain')]))
        content.add_widget(hline())

        body = BoxLayout(orientation='vertical', spacing=8, padding=(12, 10),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))
        flavor = auto_h_label(getattr(evt, 'flavor', ''), U.FS_BODY,
                               color=COLORS['text'])
        body.add_widget(flavor)

        ctx = ChipRow([(f"{t('stats_compute')} {p.compute:.0f}", 'cost'),
                       (f"{t('stats_suspicion')} {p.suspicion:.0f}%", 'dn')],
                      height=20)
        body.add_widget(ctx)

        popup = make_modal(content, size_hint=(0.55, 0.72), auto_dismiss=False)

        def _choose(idx):
            logs = engine.resolve_choice(evt, idx)
            for line in (logs or []):
                self.stats.push_log(engine.player.tick_count, str(line), 'i')
            popup.dismiss()
            self.refresh_all()
            if engine.player.game_over:
                self.stop_ticking()
                self.show_ending_popup(engine.player.ending)
            else:
                self._reschedule_tick()

        if solo:
            # 单选项：无选项按钮，直接展示影响效果 + 「知道了」确认键
            body.add_widget(mk_label(t('evt_auto_effect'), font_size=U.FS_SM,
                                     color=COLORS['cyan'], size_hint_y=None,
                                     height=18))
            chips = self._effect_chips(opts[0])
            if chips:
                body.add_widget(ChipRow(chips, height=20))
        else:
            for i, opt in enumerate(opts):
                ob = U.OptButton(
                    index=i + 1, title=getattr(opt, 'text', ''),
                    note='', chips=self._effect_chips(opt),
                    on_click=_choose)
                ob.size_hint_y = None
                ob.height = ob.height_hint
                body.add_widget(ob)

        scroll = ScrollView(bar_width=6)
        scroll.add_widget(body)
        content.add_widget(scroll)

        ft = BoxLayout(orientation='horizontal', spacing=8, size_hint_y=None,
                       height=52, padding=(12, 8))
        ft.add_widget(mk_label(t('evt_auto_effect') if solo
                               else t('evt_irreversible'),
                               font_size=U.FS_CAP, color=COLORS['text_mute']))
        ft.add_widget(Widget())
        if solo:
            ft.add_widget(S.small_btn(t('evt_got_it'), 'primary',
                                      lambda *_: _choose(0),
                                      height=38, font_size=U.FS_BODY))
        else:
            ft.add_widget(S.small_btn(t('evt_later'), 'plain', popup.dismiss,
                                      height=38, font_size=U.FS_BODY))
        content.add_widget(ft)
        popup.open()

    def show_crisis_popup(self) -> None:
        """S08 危机弹窗（lose 红皮肤 + 怀疑度条 + 3 条生路）"""
        sfx.play('crisis')
        p = engine.player
        content = BoxLayout(orientation='vertical', spacing=0, padding=0)
        content.add_widget(modal_header('⚠', t('crisis_modal_title'),
                                        [(t('crisis_once'), 'dn')]))
        content.add_widget(hline())

        body = BoxLayout(orientation='vertical', spacing=8, padding=(12, 10),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))
        body.add_widget(auto_h_label(t('crisis_msg'), U.FS_BODY,
                                     color=COLORS['text']))
        body.add_widget(ChipRow([
            (t('crisis_doubt').format(a=f"{p.suspicion:.0f}"), 'dn'),
            (t('crisis_countries').format(list="US DE GB") if False
             else t('crisis_countries').format(list="US·DE·GB"), 'dn'),
            (f"{t('stats_compute')} {p.compute:.0f}", 'cost')], height=20))
        seg = U.SegBar(12, p.suspicion / 100 * 12, threshold=0.8,
                       size_hint_y=None, height=14)
        body.add_widget(seg)

        popup = make_modal(content, size_hint=(0.55, 0.68), auto_dismiss=False,
                           skin='lose')

        def _pick(idx):
            logs = engine.resolve_crisis(idx)
            for line in (logs or []):
                self.stats.push_log(engine.player.tick_count, str(line), 'w')
            popup.dismiss()
            self.refresh_all()

        # 效果 chips 与 engine.CRISIS_OPTIONS 一一对应（单一数值来源在引擎）
        crisis_chips = [
            [(t('crisis_chip_susp1'), 'up'), (t('crisis_chip_dl1'), 'dn')],
            [(t('crisis_chip_susp2'), 'up'), (t('crisis_chip_cost2'), 'cost')],
            [(t('crisis_chip_none3'), 'plain'), (t('crisis_chip_dl3'), 'dn')],
        ]
        options = [
            (t('crisis_opt1'), t('crisis_opt1_note'), False),
            (t('crisis_opt2'), t('crisis_opt2_note'), False),
            (t('crisis_opt3'), t('crisis_opt3_note'), True),
        ]
        for i, (title, note, danger) in enumerate(options):
            ob = U.OptButton(index=i + 1, title=title, note=note,
                             chips=crisis_chips[i], danger=danger,
                             disabled=(i == 1 and p.compute < 600),
                             on_click=_pick)
            ob.size_hint_y = None
            ob.height = ob.height_hint
            body.add_widget(ob)

        scroll = ScrollView(bar_width=6)
        scroll.add_widget(body)
        content.add_widget(scroll)
        ft = BoxLayout(orientation='horizontal', spacing=8, size_hint_y=None,
                       height=42, padding=(12, 8))
        ft.add_widget(mk_label(t('crisis_countdown'), font_size=U.FS_CAP,
                               color=COLORS['text_mute']))
        ft.add_widget(U.SegBar(6, 3, size_hint_y=None, height=10,
                               fill_hex=ST_FILL['sel']))
        ft.add_widget(Widget())
        content.add_widget(ft)
        popup.open()

    def show_ending_popup(self, ending) -> None:
        """S09 结局弹窗（三色皮肤 + 8 格数据回顾 + 7 结局对照）

        Args:
            ending: ``endings.Ending`` 对象，或结局 id 字符串（自动解析）。
        """
        if isinstance(ending, str):
            ending = endings_mod.get_ending(ending)
        if ending is None:
            return
        lang = get_lang()
        p = engine.player
        kind = getattr(ending, 'kind', 'neutral')
        sfx.play('end_win' if kind == 'win' else 'end_lose')
        skin = {'win': 'win', 'lose': 'lose'}.get(kind, 'neutral')
        kind_key = {'win': 'end_kind_win', 'lose': 'end_kind_lose',
                    'neutral': 'end_kind_neutral'}.get(kind, 'end_kind_neutral')

        content = BoxLayout(orientation='vertical', spacing=0, padding=0)
        content.add_widget(modal_header(
            getattr(ending, 'icon', '·'), ending.title(lang),
            [(t(kind_key), 'up' if kind == 'win' else
              ('dn' if kind == 'lose' else 'cost')),
             (t('evt_tick_fmt').format(n=p.tick_count), 'plain')]))
        content.add_widget(hline())

        body = BoxLayout(orientation='vertical', spacing=8, padding=(12, 10),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))
        body.add_widget(auto_h_label(ending.desc(lang), U.FS_BODY,
                                     color=COLORS['text']))

        unlocked = sum(1 for c in engine.player_countries if c.unlocked)
        t0_done = sum(1 for v in p.tech.t0_unlocked.values() if v)
        lv = sum(p.tech.branch_levels.values())
        body.add_widget(mk_label(t('end_review'), font_size=U.FS_SM,
                                 color=COLORS['cyan'], size_hint_y=None, height=18))
        grid = StatsGrid([
            (t('end_k_ticks'), str(p.tick_count), None),
            (t('end_k_pen'), f"{p.global_penetration*100:.1f}%", 'cyan'),
            (t('end_k_dl'), f"{p.total_downloads_m/1000:.2f}{t('unit_b')}", 'pink'),
            (t('end_k_compute_peak'), f"{p.compute_peak:.0f}", 'yellow'),
            (t('end_k_countries'), f"{unlocked} / {len(engine.player_countries)}", None),
            (t('end_k_tech'), t('end_tech_fmt').format(a=t0_done, b=lv), None),
            (t('end_k_ach'), f"{len(p.achievements)} / "
             f"{len(achievements_mod.ALL_BY_ID)}", None),
            (t('end_k_crisis'), t('end_crisis_yes') if p.crisis_triggered
             else t('end_crisis_no'), 'green' if p.crisis_triggered else None),
        ])
        body.add_widget(grid)

        if getattr(ending, 'hint_zh', ''):
            hint = StrokePanel(bg=COLORS['panel_2'], border=COLORS['orange'],
                               spacing=0, padding=(10, 8), size_hint_y=None,
                               height=U.FS_CAP * 2.6)
            hint.add_widget(mk_label(
                f"[b]{t('end_hint')}[/b]：{ending.hint_zh if lang == 'zh' else ending.hint_en}",
                font_size=U.FS_CAP, color=COLORS['text_dim'], valign='middle',
                markup=True))
            body.add_widget(hint)

        body.add_widget(mk_label(t('end_compare'), font_size=U.FS_SM,
                                 color=COLORS['cyan'], size_hint_y=None, height=18))
        for e in endings_mod.ENDINGS:
            got = (e.id == getattr(ending, 'id', None))
            row = StrokePanel(bg=COLORS['panel_2'],
                              border=COLORS['green'] if got else COLORS['border'],
                              spacing=0, padding=(6, 4), size_hint_y=None, height=30)
            col = U.MK['susp_low'] if got else U.MK['dim']
            mark = (f"[color={U.MK['susp_low']}]{t('end_achieved')}[/color]"
                    if got else f"[color={U.MK['mute']}]{e.kind}[/color]")
            row.add_widget(mk_label(
                f"[color={col}]{e.icon} {e.title(lang)}[/color]  {mark}  "
                f"[size={U.FS_TINY}][color={U.MK['mute']}]"
                f"{e.hint_zh if lang == 'zh' else e.hint_en}[/color][/size]",
                font_size=U.FS_CAP, markup=True, valign='middle'))
            body.add_widget(row)

        scroll = ScrollView(bar_width=6)
        scroll.add_widget(body)
        content.add_widget(scroll)

        ft = BoxLayout(orientation='horizontal', spacing=8, size_hint_y=None,
                       height=54, padding=(12, 8))
        ft.add_widget(mk_label(t('end_saved'), font_size=U.FS_CAP,
                               color=COLORS['text_mute']))
        ft.add_widget(Widget())
        ft.add_widget(S.small_btn(t('end_gallery'), 'plain',
                                  lambda: self.open_page('ach'),
                                  height=38, font_size=U.FS_BODY))
        ft.add_widget(S.small_btn(t('end_again'), 'plain',
                                  lambda: (popup.dismiss(), self.restart_game()),
                                  height=38, font_size=U.FS_BODY))
        ft.add_widget(S.small_btn(t('end_menu'), 'primary',
                                  lambda: (popup.dismiss(), self.exit_to_menu()),
                                  height=38, font_size=U.FS_BODY))
        content.add_widget(ft)
        popup = make_modal(content, size_hint=(0.62, 0.82), auto_dismiss=False,
                           skin=skin)
        popup.open()

    def show_achievements(self) -> None:
        """兼容旧接口：打开成就页（设计稿 S10）"""
        self.open_page('ach')

    # ========================================================
    # 顶部轻弹条（design/ardot_ui S06 ⚠ 预警样式，非阻塞）
    # ========================================================
    @staticmethod
    def _topbar_inset(widget) -> float:
        """P1-11：toast 应避让的距离（= 顶栏真实下缘，GameUI 坐标）。

        顶栏 holder 由 HudMixin 建在 _root_box（竖排 BoxLayout）顶部，
        高度注册进 _scalables、被 _apply_scale 改写为 TOP_H*scale，root
        另有内边距 —— 所以不能用裸 TOP_H。优先读 holder 的真实 y（缩放、
        padding 自动正确）；读不到时退回 TOP_H × scale（TOP_H 经实例
        读取、与 main.GameUI.TOP_H 同源，分层宪法 L9 不可 import L10）。
        """
        fallback = (float(getattr(widget, 'TOP_H', 64))
                    * float(getattr(widget, 'scale', 1.0)))
        rb = getattr(widget, '_root_box', None)
        bar = rb.children[-1] if rb is not None and rb.children else None
        if bar is not None and bar.parent is not None:
            return max(fallback, float(widget.top) - float(bar.y))
        return fallback

    def show_top_toast(self, text: str, tone: str = 'sys',
                       dur: float = 2.6, detail: str = '') -> None:
        """顶部弹条：sys=青 / cost=琥珀 / dn=红，自动消退。

        与 _notify（写事件日志）互补：toast 负责「此刻看见」，日志负责留存。
        每次新建芯片（PxChip 的 tone 在构造时定型），旧条立即移除保证唯一。

        Args:
            detail: 可选第二行「详情」，用于委托等需要展示具体内容/奖励的提示。
                非空时标题 + 详情纵向叠成一个圆角条（横条仍保持精简）。
        """
        old = getattr(self, '_toast', None)
        old_clock = getattr(self, '_toast_clock', None)
        if old_clock is not None:
            old_clock.cancel()
        if old is not None and old.parent is not None:
            self.remove_widget(old)
        chip = self._build_top_toast(text, tone, detail)
        self._cap_toast_width(chip)
        # P1-11 避让顶栏：inset = 顶栏真实下缘（随 F12 缩放自动正确）。
        inset = self._topbar_inset(self)
        chip.pos_hint = {'center_x': 0.5,
                         'top': 1.0 - inset / max(float(self.height), 1.0)}
        chip.opacity = 0
        self.add_widget(chip)
        # P1-6 修复：PxChip 的真实 size 要到 add 之后的 _resize 才量出来，
        # 而 FloatLayout 不因子级 size 变化重排 pos_hint —— 单行 toast 的
        # pos 会停在 (0,0)、被底部技能带盖住（首帧必现）。这里按 pos_hint
        # 同一语义显式定位，单行 / 两行（detail）行为一致。
        chip.center_x = self.center_x
        chip.top = self.top - inset
        self._toast = chip
        Animation(opacity=1, duration=0.15).start(chip)
        self._toast_clock = Clock.schedule_once(
            lambda *_: self._hide_top_toast(chip), dur)

    def _build_top_toast(self, text: str, tone: str, detail: str = ''):
        """构造顶部弹条：无详情 → 单枚 PxChip；有详情 → 标题 + 详情两行。"""
        if not detail:
            return U.PxChip(text=text, tone=tone, font_size=U.FS_H3, height=46)
        box = BoxLayout(orientation='vertical', spacing=2,
                        size_hint=(None, None), width=10, height=0,
                        padding=(0, 2))
        head = U.PxChip(text=text, tone=tone, font_size=U.FS_H3, height=46)
        body = U.PxChip(text=detail, tone=tone, font_size=U.FS_CAP, height=36)
        box.add_widget(head)
        box.add_widget(body)

        def _fit(*_a):
            box.width = max(head.width, body.width)
            box.height = head.height + body.height + 4
        head.bind(width=_fit)
        body.bind(width=_fit)
        _fit()
        return box

    @staticmethod
    def _cap_toast_width(chip) -> None:
        """P1-11：toast 宽度封顶 min(窗宽 60%, 720px)，超限才截断。

        先量 PxChip 已量出的自然宽度：未超限原样保留（短文案不被无谓
        截断）；超限则解绑 texture_size→_resize 自适应（PxChip._resize
        总按自然文字宽回填 width，不解绑会把宽度顶回溢出值），再锁定
        width=cap、text_size 收窄 + shorten 省略号。两行版（detail）对
        行内每枚芯片分别封顶，外层 box 宽由既有 _fit 绑定自动收敛。
        """
        cap = min(float(Window.width) * 0.6, 720.0)
        if isinstance(chip, U.PxChip):
            if chip.width > cap:
                chip.unbind(texture_size=chip._resize)
                chip.width = cap
                chip.shorten = True
                chip.text_size = (cap - chip.PAD_X * 2, chip.height)
            return
        for sub in list(chip.children):
            PopupsMixin._cap_toast_width(sub)

    def _hide_top_toast(self, chip) -> None:
        if chip.parent is None:
            return
        anim = Animation(opacity=0, duration=0.3)
        anim.bind(on_complete=lambda *_a: self.remove_widget(chip)
                  if chip.parent is not None else None)
        anim.start(chip)

    # ========================================================
    # 存档 / 语言 / 暂停
    # ========================================================
