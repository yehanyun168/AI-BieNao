"""
ui_v4_panels.py - 浮层/抽屉类面板

2026-09-13 从 ui_v4_screens.py 拆出。收的是「叠在对局画面之上」的面板：

    InspectorPanel —— S03 国家检视卡（左侧滑出，宽 328px）
    DropPreview    —— S04 投放预览面板（右下角，宽 322px）
    LogDrawer      —— S14 事件日志抽屉（右侧，宽 340px）

共同点：都有 WIDTH 常量 + refresh_scale()（跟随 UI 缩放档位）。
"""
from collections import deque
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from kivy.graphics import Color, Line, Rectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from flag_draw import FlagWidget
from pixel_assets import OWNER_CODES as FLAG_CODES

from pixel_ui import COLORS, PixelLabel, add_pixel_border
from ui_v4 import hline

import i18n
import origins
import sfx
import ui_v4 as U
from ui_v4 import (
    AchCell, BlockBar, ChipRow, FS_CAP, FS_H2, FS_H3, FS_SM, FS_BODY, FS_TINY,
    KeyBox, KvGrid, LogRow, PxChip, SaveSlotRow, SegBar, SegSwitch, Spark,
    StrokePanel, mk_label, ST_FILL,
    PixelSprite, SPR_TROPHY, PAL_TROPHY, SPR_GEAR, PAL_GEAR,
    SPR_ROBOT, PAL_ROBOT,
)
from ui_v4_common import UiStats, small_btn  # noqa: F401
class InspectorPanel(StrokePanel):
    """左侧滑出的国家检视卡（设计稿 S03，宽 328px）。

    回答两个问题：这个国家被渗透到什么程度？它贡献了多少下载量？
    底部直接挂「向该国投放技能」，把查看与操作放在同一上下文里。

    Args:
        on_close: 关闭回调。
        on_drop: 点击「向该国投放技能」的回调 ``fn(code)``。
    """

    WIDTH = 328

    def __init__(self, on_close: Callable = None, on_drop: Callable = None,
                 on_focus: Callable = None, **kwargs):
        kwargs.setdefault('size_hint', (None, 1))
        kwargs.setdefault('width', self.WIDTH)
        super().__init__(bg=COLORS['panel'], border=COLORS['border_2'],
                         spacing=0, padding=0, **kwargs)
        self._code: Optional[str] = None
        self._on_close = on_close
        self._on_drop = on_drop
        self._on_focus = on_focus

        # --- 标题栏 ---
        hd = FloatLayout(size_hint_y=None, height=30)
        self.lbl_hd = mk_label(i18n.t('insp_title'), font_size=FS_SM,
                               color=COLORS['cyan'])
        self.lbl_hd.pos_hint = {'x': 0, 'center_y': 0.5}
        self.lbl_hd.size_hint = (1, 1)
        self.lbl_hd.padding_x = 8
        self.btn_x = PxChip(U.SYM['close'], tone='plain', height=20, on_press=lambda *_: self._close())
        self.btn_x.pos_hint = {'right': 1, 'center_y': 0.5}
        hd.add_widget(self.lbl_hd)
        hd.add_widget(self.btn_x)
        self.add_widget(hd)
        self._make_divider()

        # --- 正文（可滚动，内容比 328px 宽时要能滚） ---
        body = BoxLayout(orientation='vertical', spacing=8, padding=(8, 8),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))
        self._body = body
        scroll = ScrollView(bar_width=4)
        scroll.add_widget(body)
        self.add_widget(scroll)

        # --- 身份行 ---
        idrow = FloatLayout(size_hint_y=None, height=56)
        self.flag = FlagWidget(code='CN', size_hint=(None, None), size=(64, 43),
                               pos_hint={'x': 0, 'top': 1})
        self.lbl_name = mk_label('', font_size=FS_H3, markup=True,
                                 valign='top', pos_hint={'x': 0, 'top': 1})
        self.lbl_name.size_hint = (1, 1)
        self.lbl_name.padding_x = 72
        idrow.add_widget(self.flag)
        idrow.add_widget(self.lbl_name)
        body.add_widget(idrow)

        self.chips_id = ChipRow([], height=20)
        body.add_widget(self.chips_id)

        # --- 感染进度 ---
        body.add_widget(self._section_label(i18n.t('insp_infection')))
        self.lbl_pct = mk_label('--', font_size=FS_H2, color=COLORS['cyan'],
                                halign='right', size_hint_y=None, height=28)
        body.add_widget(self.lbl_pct)
        self.segbar = SegBar(segments=12, filled=0.0, threshold=None,
                             size_hint_y=None, height=14)
        body.add_widget(self.segbar)
        self.lbl_seg_scale = mk_label('', font_size=FS_TINY, color=COLORS['text_mute'],
                                      size_hint_y=None, height=16)
        body.add_widget(self.lbl_seg_scale)
        self.lbl_seg_note = mk_label('', font_size=FS_CAP, markup=True,
                                     size_hint_y=None, height=22)
        body.add_widget(self.lbl_seg_note)
        # --- 里程碑提示（玩家反馈 6：把「还差多少」直接写出来）---
        # 玩家看 12.34% 这个数字无感，但「距解锁还差 7.66%」是可执行的。
        # 里程碑口径来自引擎真实阈值：unlock_penetration_threshold=10%（解锁
        # 新国家）、block_threshold（进入阻止区间）、penetration_saturated=99%。
        self.lbl_milestone = mk_label('', font_size=FS_CAP, markup=True,
                                      size_hint_y=None, height=44)
        body.add_widget(self.lbl_milestone)

        # --- 本国下载量 ---
        body.add_widget(self._section_label(i18n.t('insp_downloads')))
        dlrow = FloatLayout(size_hint_y=None, height=28)
        self.lbl_dl_big = mk_label('--', font_size=22, color=COLORS['pink'],
                                   size_hint=(None, None), size=(120, 28),
                                   pos_hint={'x': 0, 'center_y': 0.5})
        self.lbl_dl_share = mk_label('', font_size=FS_CAP,
                                     color=COLORS['text_mute'],
                                     pos_hint={'x': 0, 'center_y': 0.5})
        self.lbl_dl_share.size_hint = (1, 1)
        self.lbl_dl_share.padding_x = 124
        self.lbl_dl_rate = mk_label('', font_size=FS_CAP, color=COLORS['green'],
                                    halign='right', size_hint=(None, None),
                                    size=(110, 28), pos_hint={'right': 1, 'center_y': 0.5})
        dlrow.add_widget(self.lbl_dl_big)
        dlrow.add_widget(self.lbl_dl_share)
        dlrow.add_widget(self.lbl_dl_rate)
        body.add_widget(dlrow)
        self.spark = Spark([], size_hint_y=None, height=26)
        body.add_widget(self.spark)

        # --- 政府状态键值表 ---
        self.kv = KvGrid(['gov_status', 'doubt_thr', 'block_budget', 'neighbors'],
                      row_h=22)
        body.add_widget(self.kv)

        # --- 阻止强度 ---
        warn = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border_2'],
                           spacing=3, padding=(6, 5), size_hint_y=None, height=56)
        self.lbl_warn = mk_label('', font_size=FS_TINY, color=COLORS['orange'])
        warn.add_widget(self.lbl_warn)
        self.blockbar = BlockBar(0.0, size_hint_y=None, height=10)
        warn.add_widget(self.blockbar)
        self.lbl_block = mk_label('', font_size=FS_TINY, color=COLORS['text_mute'],
                                  size_hint_y=None, height=16)
        warn.add_widget(self.lbl_block)
        body.add_widget(warn)

        # --- 底栏动作 ---
        self._make_divider()
        ft = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None,
                       height=36, padding=(8, 6))
        ft.add_widget(Widget())
        self.btn_focus = self._small_btn(i18n.t('insp_focus'), 'plain',
                                         lambda: self._on_focus and self._on_focus(self._code))
        self.btn_drop = self._small_btn(i18n.t('insp_drop'), 'primary',
                                        lambda: self._on_drop and self._on_drop(self._code))
        ft.add_widget(self.btn_focus)
        ft.add_widget(self.btn_drop)
        self.add_widget(ft)

    # ---- 小工具 ----
    def _make_divider(self) -> None:
        self.add_widget(hline())

    @staticmethod
    def _section_label(text: str) -> PixelLabel:
        return mk_label(text, font_size=FS_CAP, color=COLORS['text_mute'],
                        size_hint_y=None, height=15)

    @staticmethod
    def _small_btn(text: str, tone: str, cb: Callable) -> Button:
        b = Button(text=text, font_size=FS_CAP, size_hint_y=None, height=24,
                   background_normal='')
        b.background_color = (0.078, 0.188, 0.173, 1) if tone == 'primary' \
            else list(COLORS['panel_2'])
        b.color = COLORS['cyan'] if tone == 'primary' else COLORS['text']
        add_pixel_border(b, color=COLORS['cyan'] if tone == 'primary'
                         else COLORS['border_2'])
        b.bind(on_release=lambda *_: cb())
        return b

    def _close(self) -> None:
        if self._on_close:
            self._on_close()

    # ---- 数据刷新 ----
    def update(self, cs, stats: UiStats, total_dl: float,
               player_doubt: float, unlock_thr: float = 0.10) -> None:
        """按国家状态刷新整卡。

        Args:
            cs: ``engine.CountryState``
            stats: UI 统计缓存（趋势柱数据源）
            total_dl: 全球下载量（百万），用于算占比
            player_doubt: 全局怀疑度（%）
            unlock_thr: 解锁新国家的渗透率阈值（来自 balance.TUNE，默认 10%）。
                由调用方注入而非本模块 import engine —— 保持本模块纯「画」。
        """
        cfg = cs.config
        self._code = cfg.code
        self.flag.set_code(cfg.code)
        lang = i18n.get_lang()
        age_key = {'young': 'age_young', 'mature': 'age_mature',
                   'aging': 'age_aging'}.get(cfg.age_structure, 'age_mature')
        self.lbl_name.text = (
            f"[b]{i18n.get_country_name(cfg.code)}[/b] "
            f"[color={U.MK['dim']}][size={FS_CAP}]{cfg.code}[/size][/color]\n"
            f"[size={FS_CAP}][color={U.MK['dim']}]"
            f"{i18n.get_continent_name(cfg.continent)} · "
            f"{i18n.t('insp_population')} {cfg.population_m:.0f}M · "
            f"{i18n.t(age_key)}[/color][/size]")

        # 身份 chips
        chips = []
        if cs.current_block_intensity > 0.01:
            chips.append((i18n.t('insp_chip_blocking'), 'dn'))
        elif cs.unlocked:
            chips.append((i18n.t('insp_chip_unlocked'), 'up'))
        else:
            chips.append((i18n.t('insp_chip_locked'), 'lock'))
        chips.append((f"{i18n.t('insp_tech_adopt')} {cfg.tech_adoption:.2f}", 'sys'))
        self.chips_id.set_chips(chips)

        # 感染进度：12 段 = 0–100%，阈值位画黄线
        pct = cs.penetration_rate
        thr = cfg.block_threshold / 100.0
        filled = pct * 12
        hl = {i for i in range(12) if i >= thr * 12}       # 越阈值段换亮青
        self.segbar.set_value(filled, highlight=hl, threshold=thr)
        self.lbl_pct.text = f"{pct * 100:.2f}%"
        self.lbl_seg_scale.text = (f"0%        {i18n.t('insp_thr')} "
                                   f"{cfg.block_threshold:.0f}%        100%")
        delta = 0.0
        dq = stats.country_rate.get(cfg.code)
        if dq and len(dq) >= 2:
            delta = (dq[-1] - dq[-2]) * 100
        self.lbl_seg_note.text = (
            f"[color={U.MK['dim']}]{i18n.t('insp_seg_note')}[/color] "
            f"[color={U.MK['susp_low'] if delta >= 0 else U.MK['red']}]"
            f"{i18n.t('insp_this_tick')} {delta:+.2f}%[/color]")

        # --- 里程碑：把「还差多少」写成可执行目标（玩家反馈 6）---
        # 玩家对裸百分比无感，对「距解锁还差 7.7%」有感。
        self.lbl_milestone.text = self._milestone_text(
            pct, cfg.block_threshold / 100.0, cs.unlocked, unlock_thr)

        # 本国下载量
        self.lbl_dl_big.text = f"{cs.downloads_m:.1f}M"
        share = (cs.downloads_m / total_dl * 100) if total_dl > 0 else 0.0
        self.lbl_dl_share.text = f"{i18n.t('insp_share')} {share:.1f}%"
        rate = 0.0
        dq2 = stats.country_dl.get(cfg.code)
        if dq2 and len(dq2) >= 2:
            rate = dq2[-1] - dq2[-2]
        self.lbl_dl_rate.text = f"{rate:+.2f}M/{i18n.t('per_tick')}"
        self.spark.set_values(stats.spark_values(cfg.code))

        # 政府状态
        if cs.current_block_intensity > 0.01:
            gov, gc = i18n.t('gov_blocking'), U.MK['red']
        elif player_doubt >= 40:
            gov, gc = i18n.t('gov_watching'), U.MK['orange']
        else:
            gov, gc = i18n.t('gov_idle'), U.MK['susp_low']
        self.kv.set_value('gov_status', f"[color={gc}]{gov}[/color]")
        self.kv.set_value('doubt_thr', f"{player_doubt:.0f}% / {cfg.block_threshold:.0f}%")
        if cs.current_block_intensity > 0.01:
            self.kv.set_value('block_budget',
                              f"[color={U.MK['red']}]{cs.block_budget_remaining:.0f}[/color]")
        else:
            self.kv.set_value('block_budget',
                              f"[color={U.MK['susp_low']}]{cs.block_budget_remaining:.0f}[/color]")
        self.kv.set_value('neighbors', " ".join(cfg.neighbors) or '--')

        # 阻止强度
        self.lbl_warn.text = i18n.t('insp_block_warn').format(
            thr=f"{cfg.block_threshold:.0f}")
        self.blockbar.set_ratio(cs.current_block_intensity)
        self.lbl_block.text = (f"{i18n.t('insp_block_strength')} "
                               f"{cs.current_block_intensity * 100:.0f}%")

    @staticmethod
    def _milestone_text(pct: float, block_thr: float, unlocked: bool,
                        unlock_thr: float) -> str:
        """把当前渗透率翻译成「下一个目标 + 还差多少」。

        按引擎真实阈值分档（不是拍脑袋的档位）：
        - 未解锁：距 unlock_thr（10%）还差 X% → 达标后会解锁周边国家
        - 已解锁但未饱和：展示下一个里程碑（25% / 50% / 99%）
        - 越过阻止阈值：警告已进入政府阻止区间
        - ≥ 99%：已饱和

        Returns:
            Kivy markup 字符串（最多两行）。
        """
        p = max(pct, 0.0)
        thr_pct = block_thr * 100.0
        # 档 1：还没解锁 —— 最该给的目标
        if not unlocked:
            need = max(unlock_thr - p, 0.0) * 100.0
            if need <= 0.01:
                return (f"[color={U.MK['st_on']}]{i18n.t('insp_ms_ready')}"
                        f"[/color]")
            return (f"[color={U.MK['yellow']}]{i18n.t('insp_ms_unlock')}[/color]\n"
                    f"[color={U.MK['dim']}]{i18n.t('insp_ms_need')} "
                    f"[b][color={U.MK['st_on']}]{need:.2f}%[/color][/b][/color]")
        # 档 2：已解锁，找下一个里程碑
        marks = [0.25, 0.50, 0.99]
        nxt = next((m for m in marks if p < m - 1e-9), None)
        if nxt is None:
            return (f"[color={U.MK['st_on']}]{i18n.t('insp_ms_saturated')}"
                    f"[/color]")
        need = (nxt - p) * 100.0
        line2 = (f"[color={U.MK['dim']}]{i18n.t('insp_ms_need')} "
                 f"[b][color={U.MK['pink']}]{need:.2f}%[/color][/b][/color]")
        if p >= block_thr - 1e-9:
            return (f"[color={U.MK['red']}]{i18n.t('insp_ms_blocked')} "
                    f"{thr_pct:.0f}%[/color]\n{line2}")
        return (f"[color={U.MK['text']}]{i18n.t('insp_ms_next')} "
                f"[b]{nxt * 100:.0f}%[/b][/color]\n{line2}")

    def refresh_scale(self, scale: float) -> None:
        self.width = self.WIDTH * scale


# ============================================================
# S04 投放预览面板
# ============================================================

class DropPreview(StrokePanel):
    """右下角投放预览（设计稿 S04，宽 322px）。

    实时汇总：目标 / 算力消耗 / 剩余算力 / 效果 chips / 各国下载量预估 / 副作用。
    """

    WIDTH = 322

    def __init__(self, on_confirm: Callable = None, on_cancel: Callable = None,
                 **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('width', self.WIDTH)
        super().__init__(bg=COLORS['panel'], border=COLORS['border_2'],
                         spacing=0, padding=0, **kwargs)
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel

        hd = FloatLayout(size_hint_y=None, height=28)
        self.lbl_hd = mk_label('', font_size=FS_SM, color=COLORS['cyan'])
        self.lbl_hd.pos_hint = {'x': 0, 'center_y': 0.5}
        self.lbl_hd.size_hint = (1, 1)
        self.lbl_hd.padding_x = 8
        x = PxChip(U.SYM['close'], tone='plain', height=20, on_press=lambda *_: self._cancel())
        x.pos_hint = {'right': 1, 'center_y': 0.5}
        hd.add_widget(self.lbl_hd)
        hd.add_widget(x)
        self.add_widget(hd)

        body = BoxLayout(orientation='vertical', spacing=7, padding=(8, 8),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))
        self._body = body
        scroll = ScrollView(bar_width=4)
        scroll.add_widget(body)
        self.add_widget(scroll)

        self.kv = KvGrid(['targets', 'cost', 'remain'], row_h=17)
        body.add_widget(self.kv)
        self.chips = ChipRow([], height=40)
        body.add_widget(self.chips)

        self.lbl_est_hd = mk_label(i18n.t('drop_est'), font_size=FS_CAP,
                                   color=COLORS['text_mute'],
                                   size_hint_y=None, height=15)
        body.add_widget(self.lbl_est_hd)
        self.segbar = SegBar(segments=12, filled=0.0, size_hint_y=None, height=10)
        body.add_widget(self.segbar)
        self.lbl_est = mk_label('', font_size=FS_TINY, color=COLORS['text_mute'],
                                size_hint_y=None, height=16)
        body.add_widget(self.lbl_est)

        self.warn_box = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border_2'],
                                    spacing=0, padding=(6, 5),
                                    size_hint_y=None, height=30)
        self.lbl_warn = mk_label('', font_size=FS_TINY, color=COLORS['orange'])
        self.warn_box.add_widget(self.lbl_warn)
        body.add_widget(self.warn_box)

        ft = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None,
                       height=36, padding=(8, 6))
        ft.add_widget(Widget())
        ft.add_widget(InspectorPanel._small_btn(i18n.t('drop_cancel'), 'plain',
                                                self._cancel))
        self.btn_ok = InspectorPanel._small_btn(i18n.t('drop_confirm'), 'primary',
                                                self._confirm)
        ft.add_widget(self.btn_ok)
        self.add_widget(ft)

    def _cancel(self) -> None:
        if self._on_cancel:
            self._on_cancel()

    def _confirm(self) -> None:
        if self._on_confirm:
            self._on_confirm()

    def update(self, skill_id: str, skill_name: str, codes: Sequence[str],
               cost_each: float, compute: float, effects: Sequence[Tuple[str, str]],
               ests: Sequence[Tuple[str, float, float]],
               warn: str = '') -> None:
        """刷新预览。

        Args:
            skill_id: 技能 id。
            skill_name: 技能显示名。
            codes: 已选目标国家代码。
            cost_each: 单目标算力消耗。
            compute: 当前算力。
            effects: 效果 chips ``[(文本, 语气), …]``。
            ests: 各国预估 ``[(code, 现值, 预估值), …]``。
            warn: 副作用提示文案。
        """
        self.lbl_hd.text = f"{i18n.t('drop_title')} · {skill_name}"
        n = len(codes)
        total = cost_each * max(n, 1)
        self.kv.set_value('targets', " · ".join(codes) if codes else '--')
        self.kv.set_value('cost', f"[color={U.MK['yellow']}]{cost_each:.0f} ×{max(n,1)} = {total:.0f}[/color]")
        remain = compute - total
        rc = U.MK['red'] if remain < 0 else U.MK['text']
        self.kv.set_value('remain', f"[color={rc}]{compute:.0f} → {remain:.0f}[/color]")
        self.chips.set_chips(list(effects))

        # 预估：用「已选国家占全球比例」推进分段条，给玩家一个直观的推进感
        filled = min(n * 2, 12)
        self.segbar.set_value(filled, highlight={0} if n else set())
        if ests:
            parts = []
            for code, before, after in ests[:3]:
                parts.append(f"{code} {before:.1f}M → "
                             f"[color={U.MK['susp_low']}]{after:.1f}M[/color]")
            self.lbl_est.text = "   ".join(parts)
        else:
            self.lbl_est.text = '--'

        if warn:
            self.lbl_warn.text = warn
            self.warn_box.opacity = 1
            self.warn_box.height = 30
        else:
            self.warn_box.opacity = 0
            self.warn_box.height = 0
        self.btn_ok.disabled = (n == 0 or remain < 0)

    def refresh_scale(self, scale: float) -> None:
        self.width = self.WIDTH * scale


# ============================================================
# S05 技能页 —— 卡片
# ============================================================

class LogDrawer(StrokePanel):
    """右侧事件日志抽屉（设计稿 S14，宽 340px）。"""

    WIDTH = 340

    def __init__(self, on_close: Callable = None, on_clear: Callable = None,
                 on_export: Callable = None, **kwargs):
        kwargs.setdefault('size_hint', (None, 1))
        kwargs.setdefault('width', self.WIDTH)
        super().__init__(bg=COLORS['panel'], border=COLORS['border_2'],
                         spacing=0, padding=0, **kwargs)
        hd = FloatLayout(size_hint_y=None, height=30)
        self.lbl_hd = mk_label(i18n.t('log_title'), font_size=FS_SM,
                               color=COLORS['cyan'])
        self.lbl_hd.pos_hint = {'x': 0, 'center_y': 0.5}
        self.lbl_hd.size_hint = (1, 1)
        self.lbl_hd.padding_x = 8
        self.chip_unread = PxChip('', tone='sys', height=18)
        self.chip_unread.pos_hint = {'right': 1, 'center_y': 0.5}
        x = PxChip(U.SYM['close'], tone='plain', height=20, on_press=lambda *_: on_close and on_close())
        x.pos_hint = {'right': 1, 'center_y': 0.5}
        hd.add_widget(self.lbl_hd)
        hd.add_widget(x)
        self.add_widget(hd)

        self.scroll = ScrollView(bar_width=4)
        self.box = BoxLayout(orientation='vertical', spacing=3, size_hint_y=None,
                             padding=(6, 6))
        self.box.bind(minimum_height=self.box.setter('height'))
        self.scroll.add_widget(self.box)
        self.add_widget(self.scroll)

        ft = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None,
                       height=34, padding=(8, 6))
        self.lbl_note = mk_label(i18n.t('log_limit'), font_size=FS_CAP,
                                 color=COLORS['text_mute'])
        ft.add_widget(self.lbl_note)
        ft.add_widget(Widget())
        ft.add_widget(small_btn(i18n.t('log_export'), 'plain',
                                lambda: on_export and on_export()))
        ft.add_widget(small_btn(i18n.t('log_read_all'), 'plain',
                                lambda: on_clear and on_clear()))
        self.add_widget(ft)

    def rebuild(self, logs: Sequence[dict], unread: int) -> None:
        """重建日志列表（设计稿：只保留最近 200 条）。"""
        self.box.clear_widgets()
        for item in logs[:120]:
            text = f"[color={U.MK['mute']}][{item.get('tick', 0)}][/color] {item.get('text', '')}"
            self.box.add_widget(LogRow(text, item.get('tone', 'i')))
        self.chip_unread.set_tone('sys', f"{unread} {i18n.t('log_unread')}")


# ============================================================
# S15 觉醒地点选择页（T16：新档流程 = 开场动画 → 本页 → 新档弹窗）
# ============================================================
