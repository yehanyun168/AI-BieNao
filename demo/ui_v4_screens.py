"""
ui_v4_screens.py - AI 别闹 v0.4 屏幕级组件

对应设计稿 design/ui_design_v0.4.html 的：
    S03 国家检视卡      InspectorPanel
    S04 投放预览        DropPreview
    S05 技能页          SkillPageCard / build_skill_page
    S06 科技树页        SlotRow / LinkBar / BranchCard / LvRow / build_tech_page
    S10 成就面板        build_ach_grid
    S11 帮助            build_help_body
    S12 设置与存档      build_settings_body
    S14 事件日志抽屉    LogDrawer / UiStats

设计纪律：
    - 组件只负责「画」，数据由 main.py 通过 update()/refresh() 喂进来；
    - 颜色/尺寸全部来自 ui_v4 的令牌，不在此硬编码新色值。
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

from pixel_ui import COLORS, PixelLabel, add_pixel_border, hex_rgba
from flag_draw import FlagWidget

import i18n
import ui_v4 as U
from ui_v4 import (
    AchCell, BlockBar, ChipRow, FS_CAP, FS_H2, FS_H3, FS_SM, FS_BODY, FS_TINY,
    KeyBox, KvGrid, LogRow, PxChip, SaveSlotRow, SegBar, SegSwitch, Spark,
    StatCell, StatsGrid, StrokePanel, mk_label, ST_FILL, ST_EDGE,
    PixelSprite, SPR_TROPHY, PAL_TROPHY, SPR_GEAR, PAL_GEAR,
    SPR_ROBOT, PAL_ROBOT,
)


# ============================================================
# UI 侧运行统计（引擎不记录历史，这里按周期采样）
# ============================================================
class UiStats:
    """UI 层统计缓存 —— 供检视卡趋势柱 / 技能页使用。

    引擎只维护「当前值」，趋势类图表需要历史序列，所以在 UI 层按 tick 采样。
    只保留最近 ``WINDOW`` 个周期，内存恒定。

    Args:
        window: 趋势窗口长度（设计稿用 12 周期）。
    """

    WINDOW = 12

    def __init__(self, window: int = WINDOW):
        self.window = window
        self.country_dl: Dict[str, deque] = {}     # code -> 下载量序列
        self.country_rate: Dict[str, deque] = {}   # code -> 渗透率序列
        self.skill_uses: Dict[str, int] = {}       # sid -> 累计释放次数
        self.skill_contrib: Dict[str, float] = {}  # sid -> 累计贡献下载量（百万）
        self.skill_history: Dict[str, deque] = {}  # sid -> 近 12 周期使用强度
        self.growth_history: deque = deque(maxlen=window)
        # ---- 全局序列（顶栏趋势火花线，玩家反馈 6）----
        # 顶栏 4 个统计各配一根 spark：让"涨了/跌了"一眼可见，而不是只看当前值。
        self.global_downloads: deque = deque(maxlen=window)   # 总下载量（百万）
        self.global_compute: deque = deque(maxlen=window)     # 玩家算力
        self.global_suspicion: deque = deque(maxlen=window)   # 全球怀疑度（0-100）
        self.global_unlocked: deque = deque(maxlen=window)    # 已解锁国家数
        self.logs: List[dict] = []                 # {tick, tone, text}
        self.unread: int = 0

    # ---- 采样 ----
    def sample(self, countries, player, last_growth: float = 0.0) -> None:
        """每周期采一次（在 tick 之后调用）。

        Args:
            countries: ``engine.player_countries``
            player: ``engine.player``
            last_growth: 本周期全球下载量增量（百万）。
        """
        for c in countries:
            code = c.config.code
            dq = self.country_dl.setdefault(code, deque(maxlen=self.window))
            rq = self.country_rate.setdefault(code, deque(maxlen=self.window))
            dq.append(c.downloads_m)
            rq.append(c.penetration_rate)
        self.growth_history.append(max(last_growth, 0.0))
        # 全局序列：总下载 / 算力 / 怀疑度 / 已解锁国家数
        self.global_downloads.append(float(player.total_downloads_m or 0.0))
        self.global_compute.append(float(player.compute or 0.0))
        self.global_suspicion.append(float(player.suspicion or 0.0))
        try:
            self.global_unlocked.append(
                float(sum(1 for c in countries if getattr(c, 'unlocked', False))))
        except Exception:
            self.global_unlocked.append(0.0)

    def mark_skill(self, sid: str, contrib: float = 0.0) -> None:
        """记录一次技能释放（进入投放模式并确认后调用）。"""
        self.skill_uses[sid] = self.skill_uses.get(sid, 0) + 1
        self.skill_contrib[sid] = self.skill_contrib.get(sid, 0.0) + contrib
        hq = self.skill_history.setdefault(sid, deque(maxlen=self.window))
        while len(hq) < self.window:
            hq.append(0.0)
        hq.append(1.0)

    def push_log(self, tick: int, text: str, tone: str = 'i') -> None:
        """写一条日志（tone: i 信息 / w 警告 / e 阻止 / g 成就）。"""
        self.logs.insert(0, {'tick': tick, 'text': text, 'tone': tone})
        self.logs = self.logs[:200]            # 设计稿：只保留最近 200 条
        self.unread += 1

    def clear_unread(self) -> None:
        self.unread = 0

    # ---- 读取 ----
    def spark_values(self, code: str) -> List[float]:
        """某国下载量的归一化趋势（0–1，长度 = 窗口）。"""
        dq = self.country_dl.get(code)
        if not dq:
            return []
        vals = list(dq)
        mx = max(vals) or 1.0
        return [v / mx for v in vals]

    def skill_spark(self, sid: str) -> List[float]:
        hq = self.skill_history.get(sid)
        return list(hq) if hq else [0.0] * self.WINDOW

    @staticmethod
    def _norm(dq: deque) -> List[float]:
        """把一条序列归一化到 0–1（用于像素趋势柱）。

        ⚠️ 用「全局最大值」而非「末值」做分母：顶栏的下载量/算力是单调递增的，
        用末值归一化会让所有柱子都贴着 1.0（看不出增长）。除以序列最大值后，
        增量趋势才显形；全 0 序列返回全 0，避免除零。
        """
        vals = [float(v) for v in dq]
        if not vals:
            return []
        mx = max(vals)
        if mx <= 0:
            return [0.0] * len(vals)
        return [v / mx for v in vals]

    @staticmethod
    def _norm_band(dq: deque, floor: float = 0.0,
                   span: Optional[float] = None) -> List[float]:
        """按「绝对量程」归一化：把 [floor, floor+span] 映射到 0–1。

        玩家反馈 #2：旧的「除以序列最大值」在两种情况下完全读不出信息 ——

          1. 带基线的量（算力）：真实变化 100002 → 100006（+0.004%），
             但 100000 的基线把所有柱子顶到 0.714~1.0，看起来像剧烈抖动。
          2. 阶梯量（已解锁国家数）：解锁后整段恒等，柱子全高、毫无趋势。

        改成「绝对量程」后，柱子高度表示「在合理区间里的位置」，
        与游戏进度直接对应，而不是与自己的历史最大值比较
        （后者会让最后一根永远是满格，形成"永远在涨"的错觉）。

        Args:
            dq: 数据序列。
            floor: 量程下界（例如算力基线 0，怀疑度 0）。
            span: 量程跨度；None 表示用序列自身的 max 作为跨度（旧行为）。
        """
        vals = [float(v) for v in dq]
        if not vals:
            return []
        if span is None:
            span = max(vals) - floor
        if span <= 0:
            return [0.0] * len(vals)
        return [min(max((v - floor) / span, 0.0), 1.0) for v in vals]

    def stat_spark(self, key: str) -> List[float]:
        """顶栏统计的趋势序列（0–1，语义化归一化）。

        Args:
            key: ``'compute'`` / ``'downloads'`` / ``'suspicion'`` / ``'unlocked'``

        每条序列用**各自的语义量程**归一化（玩家反馈 #2）：
          - downloads：相对自身历史最大值（单调增长，看"涨了多少"）
          - compute  ：相对历史峰值（基线不参与，避免空转抖动）
          - suspicion：绝对 0–100（因为怀疑度有明确上限，含义固定）
          - unlocked ：绝对 0–国家总数（阶梯量，看"解锁到什么程度"）
        """
        if key == 'suspicion':
            # 怀疑度有绝对语义（0-100），用固定量程，柱子高度=危险程度
            return self._norm_band(self.global_suspicion, 0.0, 100.0)
        if key == 'unlocked':
            total = len(self.country_dl) or 20
            return self._norm_band(self.global_unlocked, 0.0, float(total))
        if key == 'compute':
            # 算力无上限：用自身峰值做量程，但下界取序列最小值，
            # 让"基线之上的真实波动"成为柱子的差异来源。
            vals = [float(v) for v in self.global_compute]
            if not vals:
                return []
            lo = min(vals)
            hi = max(vals)
            if hi <= lo:
                return [0.5] * len(vals)
            return [(v - lo) / (hi - lo) for v in vals]
        dq = {
            'downloads': self.global_downloads,
        }.get(key)
        return self._norm(dq) if dq is not None else []

    def stat_spark_range(self, key: str) -> tuple:
        """返回某序列火花线的 (下界, 上界) 原始值，供 UI 标注量程。

        玩家反馈 #2：只画柱子不给量程，玩家无法判断「这根柱子算高还是矮」。
        """
        dq = {
            'compute': self.global_compute,
            'downloads': self.global_downloads,
            'suspicion': self.global_suspicion,
            'unlocked': self.global_unlocked,
        }.get(key)
        if not dq:
            return (0.0, 0.0)
        if key == 'suspicion':
            return (0.0, 100.0)
        if key == 'unlocked':
            return (0.0, float(len(self.country_dl) or 20))
        vals = [float(v) for v in dq]
        return (min(vals), max(vals))


# ============================================================
# S03 国家检视卡
# ============================================================
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
        idrow = FloatLayout(size_hint_y=None, height=48)
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
                                halign='right', size_hint_y=None, height=26)
        body.add_widget(self.lbl_pct)
        self.segbar = SegBar(segments=12, filled=0.0, threshold=None,
                             size_hint_y=None, height=14)
        body.add_widget(self.segbar)
        self.lbl_seg_scale = mk_label('', font_size=FS_TINY, color=COLORS['text_mute'],
                                      size_hint_y=None, height=14)
        body.add_widget(self.lbl_seg_scale)
        self.lbl_seg_note = mk_label('', font_size=FS_CAP, markup=True,
                                     size_hint_y=None, height=16)
        body.add_widget(self.lbl_seg_note)
        # --- 里程碑提示（玩家反馈 6：把「还差多少」直接写出来）---
        # 玩家看 12.34% 这个数字无感，但「距解锁还差 7.66%」是可执行的。
        # 里程碑口径来自引擎真实阈值：unlock_penetration_threshold=10%（解锁
        # 新国家）、block_threshold（进入阻止区间）、penetration_saturated=99%。
        self.lbl_milestone = mk_label('', font_size=FS_CAP, markup=True,
                                      size_hint_y=None, height=32)
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
        self.kv = KvGrid(['gov_status', 'doubt_thr', 'block_budget', 'neighbors'])
        body.add_widget(self.kv)

        # --- 阻止强度 ---
        warn = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border_2'],
                           spacing=3, padding=(6, 5), size_hint_y=None, height=56)
        self.lbl_warn = mk_label('', font_size=FS_TINY, color=COLORS['orange'])
        warn.add_widget(self.lbl_warn)
        self.blockbar = BlockBar(0.0, size_hint_y=None, height=10)
        warn.add_widget(self.blockbar)
        self.lbl_block = mk_label('', font_size=FS_TINY, color=COLORS['text_mute'],
                                  size_hint_y=None, height=12)
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
        d = Widget(size_hint_y=None, height=2)
        with d.canvas.before:
            Color(*COLORS['border'])
            d._r = Rectangle(pos=d.pos, size=d.size)
        d.bind(pos=lambda i, v: setattr(i._r, 'pos', v),
               size=lambda i, v: setattr(i._r, 'size', v))
        self.add_widget(d)

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
        ft.add_widget(self._small_btn(i18n.t('drop_cancel'), 'plain', self._cancel))
        self.btn_ok = self._small_btn(i18n.t('drop_confirm'), 'primary', self._confirm)
        ft.add_widget(self.btn_ok)
        self.add_widget(ft)

    def _cancel(self) -> None:
        if self._on_cancel:
            self._on_cancel()

    def _confirm(self) -> None:
        if self._on_confirm:
            self._on_confirm()

    @staticmethod
    def _small_btn(text: str, tone: str, cb: Callable) -> Button:
        return InspectorPanel._small_btn(text, tone, cb)

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
class SkillPageCard(StrokePanel):
    """技能页大卡（设计稿 .skcard）：图标/名字/键位/状态 + 效果 chips +
    3 个统计数字 + 12 周期使用柱 + 底部动作。"""

    def __init__(self, on_action: Callable = None, **kwargs):
        super().__init__(bg=COLORS['panel'], border=COLORS['border_2'],
                         spacing=0, padding=0, **kwargs)
        self._on_action = on_action

        # 标题
        hd = FloatLayout(size_hint_y=None, height=32)
        self.lbl_ico = mk_label('', font_size=FS_SM, color=COLORS['yellow'],
                                halign='center', size_hint=(None, None),
                                size=(26, 26), pos_hint={'x': 0, 'center_y': 0.5})
        self.lbl_nm = mk_label('', font_size=FS_BODY, markup=True,
                               pos_hint={'x': 0, 'center_y': 0.5})
        self.lbl_nm.size_hint = (1, 1)
        self.lbl_nm.padding_x = 66
        self.chip_state = PxChip('', tone='up', height=20)
        self.chip_state.pos_hint = {'right': 1, 'center_y': 0.5}
        hd.add_widget(self.lbl_ico)
        hd.add_widget(self.lbl_nm)
        hd.add_widget(self.chip_state)
        self.add_widget(hd)

        # 正文
        body = BoxLayout(orientation='vertical', spacing=5, padding=(8, 6))
        self.chips = ChipRow([], height=34)
        body.add_widget(self.chips)
        self.lbl_desc = mk_label('', font_size=FS_CAP, color=COLORS['text_mute'],
                                 valign='top', size_hint_y=None, height=48,
                                 markup=True)
        body.add_widget(self.lbl_desc)
        self.lbl_stats = mk_label('', font_size=FS_CAP, markup=True,
                                  size_hint_y=None, height=16)
        body.add_widget(self.lbl_stats)
        self.spark = Spark([0.0] * 12, size_hint_y=None, height=22,
                           fill_hex=ST_FILL['on'])
        body.add_widget(self.spark)
        self.add_widget(body)

        # 底栏
        ft = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None,
                       height=30, padding=(8, 4))
        self.lbl_ft = mk_label('', font_size=FS_CAP, color=COLORS['text_mute'])
        ft.add_widget(self.lbl_ft)
        ft.add_widget(Widget())
        self.btn = Button(text='', font_size=FS_CAP, size_hint=(None, None),
                          size=(96, 24), background_normal='')
        self.btn.background_color = (0.078, 0.188, 0.173, 1)
        self.btn.color = COLORS['cyan']
        add_pixel_border(self.btn, color=COLORS['cyan'])
        self.btn.bind(on_release=lambda *_: self._on_action and self._on_action())
        ft.add_widget(self.btn)
        self._ft = ft
        self.add_widget(ft)

    def update(self, skill, icon: str, name: str, key_hint: str,
               chips: Sequence[Tuple[str, str]], desc: str,
               uses: int, contrib: str, per: str, spark: Sequence[float],
               state: str, state_text: str, action_text: str,
               action_enabled: bool, foot_text: str,
               locked: bool = False, unlock_hint: str = '') -> None:
        """刷新一张技能卡（数据由 main.py 组装，卡片只负责呈现）。

        ``locked`` / ``unlock_hint`` 用于「技能未解锁」态：置灰、显示解锁方式，
        且底部动作按钮禁用（设计稿问题 #4：开局不要 6 技能全开，并标注获取方法）。
        """
        self.lbl_ico.text = icon
        self.lbl_nm.text = (f"{name}  [size={FS_CAP}][color={U.MK['yellow']}]"
                            f"{key_hint}[/color][/size]")
        if locked:
            self.chip_state.set_tone('lock', state_text or i18n.t('sk_state_lock'))
            self.lbl_desc.text = desc
            self.lbl_ft.text = unlock_hint or foot_text
            self.btn.text = f"{U.SYM['lock']} {i18n.t('sk_state_lock')}"
            self.btn.disabled = True
            self.btn.background_color = list(COLORS['panel_2'])
            self.btn.color = COLORS['text_mute']
            add_pixel_border(self.btn, color=COLORS['border_2'])
            self.set_border(border=COLORS['border_2'])
            self.opacity = 0.6
            return
        self.chip_state.set_tone('cost' if state == 'cd' else
                                 ('lock' if state == 'no_compute' else 'up'),
                                 state_text)
        self.chips.set_chips(list(chips))
        self.lbl_desc.text = desc
        self.lbl_stats.text = (
            f"[color={U.MK['mute']}]{i18n.t('sk_uses')}[/color] "
            f"[b]{uses}[/b]    "
            f"[color={U.MK['mute']}]{i18n.t('sk_contrib')}[/color] "
            f"[b][color={U.MK['pink']}]{contrib}[/color][/b]    "
            f"[color={U.MK['mute']}]{i18n.t('sk_per')}[/color] [b]{per}[/b]")
        self.spark.set_values(list(spark))
        self.lbl_ft.text = foot_text
        self.btn.text = action_text
        self.btn.disabled = not action_enabled
        if action_enabled:
            self.btn.background_color = (0.078, 0.188, 0.173, 1)
            self.btn.color = COLORS['cyan']
            add_pixel_border(self.btn, color=COLORS['cyan'])
            self.set_border(border=COLORS['cyan'])
        else:
            self.btn.background_color = list(COLORS['panel_2'])
            self.btn.color = COLORS['text_mute']
            add_pixel_border(self.btn, color=COLORS['border_2'])
            self.set_border(border=COLORS['border_2'])
        self.opacity = 1.0


# ============================================================
# S06 科技树页 —— 子组件
# ============================================================
class SlotRow(Widget):
    """槽位链路的一行（设计稿 .slot）：图标 + 名字 + 状态。

    state: 'done' 已完成 / 'on' 选中 / 'lock' 前置未满足 / '' 普通
    """

    def __init__(self, icon: str = '', name: str = '', status: str = '',
                 state: str = '', on_click: Callable = None, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', 28)
        super().__init__(**kwargs)
        self.state = state
        self._on_click = on_click
        self.lbl = mk_label('', font_size=FS_CAP, markup=True)
        self.add_widget(self.lbl)
        self._icon = icon
        self._name = name
        self._status = status
        self.bind(pos=self._layout, size=self._layout)
        self._sync()

    def set_row(self, icon: str, name: str, status: str, state: str) -> None:
        self._icon, self._name, self._status, self.state = icon, name, status, state
        self._sync()

    def _sync(self) -> None:
        col = {'done': U.MK['susp_low'], 'on': U.MK['cyan'], 'lock': U.MK['lock']}.get(self.state, U.MK['text'])
        self.lbl.text = (f"[b][color={col}]{self._name}[/color][/b]   "
                         f"[size={FS_TINY}][color={U.MK['mute']}]{self._status}[/color][/size]")
        self.opacity = 0.5 if self.state == 'lock' else 1.0
        self._layout()

    def _layout(self, *_args) -> None:
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        self.lbl.pos = (x + 30, y)
        self.lbl.size = (max(w - 34, 1), h)
        self.lbl.text_size = self.lbl.size
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        bd = COLORS['cyan'] if self.state == 'on' else COLORS['border_2']
        bg = (0.118, 0.227, 0.227, 1) if self.state == 'on' else list(COLORS['panel_2'])
        ic = {'done': 'green', 'on': 'cyan'}.get(self.state, 'purple')
        with self.canvas.before:
            Color(*bg)
            Rectangle(pos=(x, y), size=(w, h))
            Color(*bd)
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h], close=True, width=2)
            # 图标框
            ix, iy = x + 4, y + (h - 20) / 2
            Color(*COLORS['panel'])
            Rectangle(pos=(ix, iy), size=(20, 20))
            Color(*COLORS[ic])
            Line(points=[ix, iy, ix + 20, iy, ix + 20, iy + 20, ix, iy + 20],
                 close=True, width=1)

    def on_touch_down(self, touch):
        if self._on_click and self.collide_point(*touch.pos):
            self._on_click()
            return True
        return super().on_touch_down(touch)


class LinkBar(Widget):
    """槽位之间的前置连线（设计稿 .link）：居中 2px 竖线，on = 绿。"""

    def __init__(self, on: bool = False, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', 8)
        super().__init__(**kwargs)
        self.on = on
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_on(self, on: bool) -> None:
        self.on = on
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 2 or h < 2:
            return
        with self.canvas.before:
            Color(*(COLORS['green'] if self.on else COLORS['border_2']))
            Line(points=[x + w / 2, y, x + w / 2, y + h], width=2)


class LvRow(Widget):
    """分支的单个等级行（设计稿 .lv）：L1 · 效果 —— 右侧算力。

    state: 'done' 已升级 / 'can' 可升级 / 'locked' 不可
    """

    def __init__(self, text: str = '', cost: str = '', state: str = 'locked',
                 on_click: Callable = None, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', 22)
        super().__init__(**kwargs)
        self.state = state
        self._on_click = on_click
        self.lbl = mk_label('', font_size=FS_CAP, markup=True)
        self.add_widget(self.lbl)
        self._text, self._cost = text, cost
        self.bind(pos=self._layout, size=self._layout)
        self._sync()

    def set_row(self, text: str, cost: str, state: str) -> None:
        self._text, self._cost, self.state = text, cost, state
        self._sync()

    def _sync(self) -> None:
        col = {'done': U.MK['susp_low'], 'can': U.MK['text']}.get(self.state, U.MK['mute'])
        self.lbl.text = (f"[color={col}]{self._text}[/color]"
                         f"[color={U.MK['yellow']}]   {self._cost}[/color]")
        self.opacity = 0.45 if self.state == 'locked' else 1.0
        self._layout()

    def _layout(self, *_args) -> None:
        self.lbl.pos = (self.x + 6, self.y)
        self.lbl.size = (max(self.width - 12, 1), self.height)
        self.lbl.text_size = self.lbl.size
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 6 or h < 6:
            return
        bd = {'done': COLORS['green'], 'can': COLORS['cyan']}.get(
            self.state, COLORS['border_2'])
        with self.canvas.before:
            Color(0.071, 0.094, 0.122, 1)
            Rectangle(pos=(x, y), size=(w, h))
            Color(*bd)
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h], close=True, width=1)

    def on_touch_down(self, touch):
        if self._on_click and self.state != 'locked' and self.collide_point(*touch.pos):
            self._on_click()
            return True
        return super().on_touch_down(touch)


class BranchCard(StrokePanel):
    """分支卡（设计稿 .branch）：标题 + 描述 + 3 级 + 状态。

    dim=True 表示「互斥灰化」（42% 不透明度）。
    """

    def __init__(self, on_pick: Callable = None, on_level: Callable = None, **kwargs):
        super().__init__(bg=COLORS['panel_2'], border=COLORS['border_2'],
                         spacing=5, padding=(6, 6), **kwargs)
        self._on_pick = on_pick
        self._on_level = on_level

        self.lbl_head = mk_label('', font_size=FS_SM, markup=True,
                                 size_hint_y=None, height=18)
        self.add_widget(self.lbl_head)
        self.lbl_desc = mk_label('', font_size=FS_CAP, color=COLORS['text_mute'],
                                 valign='top', size_hint_y=None, height=30)
        self.add_widget(self.lbl_desc)
        self.lv_rows: List[LvRow] = []
        for i in range(3):
            r = LvRow(on_click=lambda idx=i: self._on_level and self._on_level(idx))
            self.add_widget(r)
            self.lv_rows.append(r)
        self.lbl_foot = mk_label('', font_size=FS_TINY, color=COLORS['orange'],
                                 size_hint_y=None, height=24)
        self.add_widget(self.lbl_foot)

    def update(self, name: str, badge: str, badge_tone: str, code_short: str,
               desc: str, levels: Sequence[Tuple[str, str, str]],
               foot: str, foot_tone: str, picked: bool, dim: bool) -> None:
        """刷新分支卡。

        Args:
            levels: ``[(文案, 算力, state), …]`` 三条。
        """
        bd = f"  [color={U.MK['susp_low'] if badge_tone == 'up' else U.MK['mute']}]「{badge}」[/color]" if badge else ''
        self.lbl_head.text = (f"[b]{name}[/b]{bd}    "
                              f"[size={FS_TINY}][color={U.MK['mute']}]{code_short}[/color][/size]")
        self.lbl_desc.text = desc
        for r, (t, c, st) in zip(self.lv_rows, levels):
            r.set_row(t, c, st)
        self.lbl_foot.text = foot
        self.lbl_foot.color = COLORS[foot_tone]
        self.opacity = 0.42 if dim else 1.0
        if picked:
            self.set_border(border=COLORS['cyan'], bg=(0.118, 0.227, 0.227, 1))
        elif dim:
            self.set_border(border=COLORS['border_2'], bg=COLORS['panel_2'])
        else:
            self.set_border(border=COLORS['border_2'], bg=COLORS['panel_2'])

    def refresh_scale(self, scale: float) -> None:
        self.lbl_desc.height = 30 * scale
        for r in self.lv_rows:
            r.height = 22 * scale


# ============================================================
# S06 科技树 · 全屏节点网络图（v0.5 重做，参考《瘟疫公司》）
# ============================================================
# 布局模型：
#   主链 —— 6 个槽位沿水平方向等距铺开（localization → platform → … → resistance），
#          槽位之间用带箭头的依赖连线串联（数据源 slot.prereq_slot）。
#   扇出 —— 每个槽位节点向下引一条竖线，再水平分叉到 3 条并行分支节点。
#   节点 —— 像素方块（圆角 0、2px 硬边框），内含：图标 + 名称 + 状态副行 +
#          3 格等级点（实心=已达等级，空心=未达；色盲用户可辨）。
#
# 坐标系：整幅图在一个**逻辑画布**（CANVAS_W × CANVAS_H）里排布，
#   绘制时统一乘 scale + 偏移，从而「等比缩放铺满可用区、节点不变形」。
#   所有几何都存节点中心点 (cx, cy)，画的时候按 NODE_W/H 反推左上角。

class TechNode:
    """网络图里的一个节点（纯数据 + 命中矩形，不继承 Widget）。

    kind: 't0' 槽位 T0 节点 / 'branch' 分支节点
    state: 'done' 已完成 / 'can' 可解锁(算力够) / 'poor' 算力不足 / 'lock' 前置未满足
    """

    __slots__ = ('key', 'kind', 'slot_id', 'branch_id', 'name', 'code',
                 'cx', 'cy', 'w', 'h', 'state', 'level', 'max_level', 'cost',
                 'sub', 'desc')

    def __init__(self, key, kind, slot_id, name, code, cx, cy):
        self.key = key
        self.kind = kind
        self.slot_id = slot_id
        self.branch_id = None            # 仅 branch 节点有
        self.name = name
        self.code = code
        self.cx, self.cy = cx, cy
        self.w, self.h = 0.0, 0.0
        self.state = 'lock'
        self.level = 0
        self.max_level = 1 if kind == 't0' else 3
        self.cost = 0.0
        self.sub = ''
        self.desc = ''                   # main 注入的详情描述（详情面板读它）

    def rect(self):
        """返回左上角 + 尺寸 (x, y, w, h)。"""
        return (self.cx - self.w / 2, self.cy - self.h / 2, self.w, self.h)

    def hit(self, px, py) -> bool:
        x, y, w, h = self.rect()
        return x <= px <= x + w and y <= py <= y + h


class TechCanvas(FloatLayout):
    """科技树网络图画布：自绘方块/连线 + Label 承载文字，处理点击命中与等比缩放。

    为什么是 FloatLayout + Label 而不是纯 canvas：
        Kivy 的 ``canvas`` 画不了文本。节点名称/等级点必须用子控件承载，
        所以方块与连线走 ``canvas.before``（在子控件下层），文字走 Label 子控件。

    用法：
        canvas = TechCanvas(on_pick=fn)     # fn(key)
        canvas.rebuild(TECH_TREE)           # 一次性建节点几何
        canvas.set_state(states, sel_key)   # 每帧刷新状态
    """

    # ---- 逻辑画布尺寸（比例接近实际可用区）----
    # 实际 body 可用区约 2504×1238（1440×980 窗口），比例 2.02:1。
    # 这里按 2:1 设计，等比缩放后能铺满而不浪费。
    # ---- 逻辑画布尺寸 ----
    # 实际 body 可用区约 2504×1238（1440×980 窗口）→ 比例 2.02:1。
    # 按 1600:790（≈2.03:1）设计，等比缩放后几乎铺满、不留黑边。
    CANVAS_W = 1600.0
    CANVAS_H = 620.0

    NODE_W = 158.0            # 槽位 / 分支节点统一宽度（像素方块）
    NODE_H = 76.0
    MAIN_Y = 500.0            # 主链节点中心线（画布坐标，y 向上）
    BRANCH_Y = 236.0          # 分支节点中心线
    PAD = 34.0                # 画布四周留白
    BR_GAP = 14.0             # 同槽相邻分支的横向缝隙

    def __init__(self, on_pick: Callable = None, **kwargs):
        kwargs.setdefault('size_hint', (1, 1))
        super().__init__(**kwargs)
        self._on_pick = on_pick
        self.nodes: Dict[str, TechNode] = {}
        self._order: List[str] = []          # 绘制/键盘遍历顺序
        self._links: List[Tuple[str, str, str]] = []   # (from_key, to_key, kind)
        self._labels: Dict[str, List[Label]] = {}      # key → [名称, 副行, 等级]
        self._sel: str = ''
        self._scale = 1.0
        self._ox = 0.0
        self._oy = 0.0
        self._cw = self.CANVAS_W        # 本次 rebuild 实际画布宽（可能被左留白撑大）
        self._ch = self.CANVAS_H
        self._slots: List[str] = []
        self.bind(pos=self._redraw, size=self._redraw)

    # ---------------- 建图（一次） ----------------
    def rebuild(self, tech_tree: Sequence) -> None:
        """按科技树数据算好全部节点坐标与连线、建好文字 Label（只调一次）。

        布局要点（v0.5）：
          * 主链 6 个 T0 节点水平等距铺开；
          * 每槽向下扇出 3 条分支。**分支跨度必须 ≤ 槽位间距**，
            否则相邻槽位的分支会横向重叠、文字糊成一团。
            所以这里先按「分支需要的最小步距」反推画布宽度：
                need_w = PAD*2 + 6*max(NODE_W, 3*BR_STEP)  ...
            简化做法：让 slot_step ≥ 3 条分支的总跨度 + 间隙。
        """
        self.nodes.clear()
        self._order = []
        self._links = []
        for ch in list(self.children):
            self.remove_widget(ch)
        self._labels.clear()
        slots = list(tech_tree)
        self._slots = [s.slot_id for s in slots]
        n = max(len(slots), 1)

        # --- 分支区步距 ---
        # 每条槽位下 3 条分支横向排开；相邻槽位的分支之间必须留出缝隙，
        # 否则会跨槽重叠、文字糊在一起。
        br_step = self.NODE_W + self.BR_GAP             # 同槽分支中心距
        half_fan = br_step                              # 3 条分支 → ±1 个 br_step

        # 槽位步距 ≥ 两条相邻槽最外侧分支的中心距 + 一个节点宽（缝隙）
        min_step = half_fan * 2 + self.NODE_W
        avail = self.CANVAS_W - 2 * self.PAD - self.NODE_W
        step = max(min_step, avail / (n - 1) if n > 1 else 0.0)

        # 左边界要预留「最左槽位的分支外沿」：cx_min - half_fan - NODE_W/2
        # 否则槽位 0 的最左分支会跑到画布外（曾出现 x = -57 被裁切）。
        left_pad = half_fan + self.NODE_W / 2 + self.PAD
        right_pad = left_pad
        total_w = left_pad + step * (n - 1) + right_pad
        # 画布宽度用局部变量，别改类属性（否则二次 rebuild 会持续放大）
        canvas_w = max(self.CANVAS_W, total_w)

        for i, slot in enumerate(slots):
            cx = left_pad + step * i
            key = f"t0:{slot.slot_id}"
            nd = TechNode(key, 't0', slot.slot_id, slot.name,
                          (slot.icon or slot.slot_id[:2]).upper(), cx, self.MAIN_Y)
            nd.w, nd.h = self.NODE_W, self.NODE_H   # 命中矩形（缺省 0×0 = 永远点不中）
            self.nodes[key] = nd
            self._order.append(key)
            self._make_labels(nd)
            # 依赖连线：上游 T0 → 本 T0
            if slot.prereq_slot:
                self._links.append((f"t0:{slot.prereq_slot}", key, 'dep'))
            # 扇出：本 T0 → 3 条分支（居中对称展开）
            m = max(len(slot.branches), 1)
            for j, br in enumerate(slot.branches):
                offset = (j - (m - 1) / 2.0) * br_step
                bkey = f"br:{br.branch_id}"
                bn = TechNode(bkey, 'branch', slot.slot_id, br.name,
                              (br.icon or br.branch_id[:2]).upper(),
                              cx + offset, self.BRANCH_Y)
                bn.branch_id = br.branch_id
                bn.w, bn.h = self.NODE_W, self.NODE_H
                self.nodes[bkey] = bn
                self._order.append(bkey)
                self._make_labels(bn)
                self._links.append((key, bkey, 'fan'))
        # 记录本次实际用的画布尺寸（等比缩放按它算）
        self._cw = canvas_w
        self._ch = self.CANVAS_H
        self._redraw()

    def _make_labels(self, nd: TechNode) -> None:
        """给一个节点建 2 个 Label（名称行 / 状态行），加入画布。

        ⚠️ ``size_hint`` 必须关掉 ``(None, None)``：mk_label 默认 (1,1)，
        在 FloatLayout 里会被撑成整个画布大小，文字跑到画布角落。
        text_size/size 的最终控制权在 ``_layout_labels``（每次重绘都全量回写）。
        """
        name = mk_label('', font_size=FS_SM, color=COLORS['text'],
                        halign='center', valign='middle', markup=True,
                        size_hint=(None, None))
        sub = mk_label('', font_size=FS_CAP, color=COLORS['text_mute'],
                       halign='center', valign='middle', markup=True,
                       size_hint=(None, None))
        self.add_widget(name)
        self.add_widget(sub)
        self._labels[nd.key] = [name, sub]

    # ---------------- 状态刷新（每帧） ----------------
    def set_state(self, states: Dict[str, dict], sel_key: str = '') -> None:
        """states: ``{node_key: {'state','level','cost','sub'}}``"""
        for k, nd in self.nodes.items():
            info = states.get(k)
            if info:
                nd.state = info.get('state', 'lock')
                nd.level = int(info.get('level', 0))
                nd.cost = float(info.get('cost', 0) or 0)
                nd.sub = info.get('sub', '')
        self._sel = sel_key or ''
        self._redraw()

    # ---------------- 几何换算 ----------------
    def _compute_transform(self) -> None:
        """等比缩放铺满可用区（保持长宽比，节点不变形）。

        ⚠️ 坐标系真相（已用像素级实验确认）：
          * ``canvas.before`` 绘制**完全忽略** widget 的 ``self.pos``——
            在 canvas 里画 ``Rectangle(pos=(0,0))``，无论 widget 在哪，
            都会落在窗口 ``(0,0)``。所以方块坐标必须自己带上**绝对**位置：
                box_window = _ox + cx*s     ← _ox 里必须含 self.x
          * Label 是本 widget 的**子控件**，其 ``pos`` 相对 ``self.pos``：
                label_pos = box_window - self.pos
          两者对不上就会出现「方块在 A，文字飘在 A - self.pos」的错位。
        """
        w, h = self.size
        if w < 20 or h < 20:
            self._scale = 1.0
            self._ox, self._oy = self.x, self.y
            return
        s = min(w / self._cw, h / self._ch)
        self._scale = s
        # 绝对坐标居中
        self._ox = self.x + (w - self._cw * s) / 2
        self._oy = self.y + (h - self._ch * s) / 2

    def to_local(self, px: float, py: float) -> Tuple[float, float]:
        """屏幕坐标 → 画布逻辑坐标（用于命中判定）。"""
        s = self._scale or 1.0
        return ((px - self._ox) / s, (py - self._oy) / s)

    def node_at(self, px: float, py: float) -> Optional[TechNode]:
        lx, ly = self.to_local(px, py)
        for k in reversed(self._order):
            nd = self.nodes.get(k)
            if nd and nd.hit(lx, ly):
                return nd
        return None

    # ---------------- 绘制 ----------------
    def _node_palette(self, nd: TechNode) -> Tuple[tuple, tuple, tuple]:
        """返回 (填充色, 边框色, 文字色)。"""
        if nd.state == 'done':
            return (0.086, 0.220, 0.196, 1), COLORS['cyan'], COLORS['text']
        if nd.state == 'can':
            return (0.086, 0.145, 0.196, 1), COLORS['blue'], COLORS['text']
        if nd.state == 'poor':
            return (0.180, 0.110, 0.110, 1), COLORS['red'], COLORS['text_dim']
        return list(COLORS['panel_2']), COLORS['border_2'], COLORS['text_mute']

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        if not self.nodes:
            return
        self._compute_transform()
        s, ox, oy = self._scale, self._ox, self._oy

        def T(cx, cy):
            return (ox + cx * s, oy + cy * s)

        nw, nh = self.NODE_W * s, self.NODE_H * s
        lw = max(1.0, round(2 * s))
        with self.canvas.before:
            # ---- 连线（画在节点下层）----
            for a_key, b_key, kind in self._links:
                a, b = self.nodes.get(a_key), self.nodes.get(b_key)
                if a is None or b is None:
                    continue
                ax, ay = T(a.cx, a.cy)
                bx, by = T(b.cx, b.cy)
                on = (a.state == 'done')
                col = COLORS['cyan'] if on else COLORS['border_2']
                Color(*col)
                if kind == 'dep':
                    x1, x2 = ax + nw / 2, bx - nw / 2
                    Line(points=[x1, ay, x2, by], width=lw)
                    Line(points=[x2 - 11 * s, by + 7 * s, x2, by,
                                 x2 - 11 * s, by - 7 * s], width=lw)
                else:
                    dy = ay - nh / 2
                    top = by + nh / 2
                    midy = (dy + top) / 2
                    Line(points=[ax, dy, ax, midy, bx, midy, bx, top], width=lw)

            # ---- 节点方块 ----
            for k in self._order:
                nd = self.nodes.get(k)
                if nd is None:
                    continue
                fill, edge, tcol = self._node_palette(nd)
                cx, cy = T(nd.cx, nd.cy)
                x, y = cx - nw / 2, cy - nh / 2
                locked = (nd.state == 'lock')
                if locked:
                    Color(fill[0], fill[1], fill[2], 0.45)
                else:
                    Color(*fill)
                Rectangle(pos=(x, y), size=(nw, nh))
                if k == self._sel:
                    Color(*COLORS['yellow'])
                    Line(points=[x - 5, y - 5, x + nw + 5, y - 5,
                                 x + nw + 5, y + nh + 5, x - 5, y + nh + 5],
                         close=True, width=lw + 2)
                if locked:
                    Color(*COLORS['border'])
                    self._dashed_rect(x, y, nw, nh, lw)
                else:
                    Color(*edge)
                    Line(points=[x, y, x + nw, y, x + nw, y + nh, x, y + nh],
                         close=True, width=lw)

        self._layout_labels()

    def _layout_labels(self) -> None:
        """把每个节点的 2 个 Label 摆到方块内。

        ⚠️ 坐标系真相（已用 ``to_window`` + 像素级实验双重确认）：
          * ``canvas.before/after`` 绘制**完全忽略 widget 的 self.pos**——
            在 canvas 里画 ``Rectangle(pos=(0,0))`` 会落到窗口 (0,0)。
          * **子控件也一样**：``cv.to_window(*nm.pos) == nm.pos``，
            说明 TechCanvas 的 pos 不会叠加到子控件上。
          * 结论：方块与 Label 都在**同一个「绝对坐标」空间**里，
            两者都必须用 _ox/_oy（含 self.pos 的绝对坐标），
            **Label 不能减 self.pos**。减了就会整体下移 self.y 像素，
            表现为「文字浮在方块下方/上方一整格」。
          * ``text_size`` 要先于 ``size`` 写，否则 Kivy 按 texture_size
            自动改 size，halign/valign 失效。
        """
        s, ox, oy = self._scale, self._ox, self._oy
        nw, nh = self.NODE_W * s, self.NODE_H * s
        for k, nd in self.nodes.items():
            labs = self._labels.get(k)
            if not labs:
                continue
            name, sub = labs
            cx = ox + nd.cx * s                   # 绝对坐标，不减 self.x
            cy = oy + nd.cy * s
            x, y = cx - nw / 2, cy - nh / 2
            _, _, tcol = self._node_palette(nd)

            # ---- 名称行 ----
            name.color = tcol
            name.text = f"[b]{nd.name}[/b]"
            name.font_size = max(FS_SM * s, 12)
            nsize = (max(nw - 10, 20), max(nh * 0.46, 12))
            name.text_size = nsize                 # text_size 必须先设
            name.size = nsize                      # 再设 size
            name.pos = (x + 5, y + nh * 0.42)

            # ---- 副行：等级点（■/□，形状+颜色双编码）+ 状态文案 ----
            pips = ''.join('■' if i < nd.level else '□'
                           for i in range(nd.max_level))
            sub.color = {'done': COLORS['cyan'], 'can': COLORS['yellow'],
                         'poor': COLORS['red']}.get(nd.state, COLORS['text_mute'])
            sub.text = f"{pips}  {nd.sub}".strip()
            sub.font_size = max(FS_CAP * s, 11)
            ssize = (max(nw - 10, 20), max(nh * 0.34, 10))
            sub.text_size = ssize
            sub.size = ssize
            sub.pos = (x + 5, y + nh * 0.08)

    def _dashed_rect(self, x, y, w, h, lw, dash=7.0, gap=5.0):
        """虚线矩形（Kivy 的 Line 无 dash 支持，手工分段）。"""
        for (x1, y1, x2, y2) in ((x, y, x + w, y), (x + w, y, x + w, y + h),
                                 (x + w, y + h, x, y + h), (x, y + h, x, y)):
            dx, dy = x2 - x1, y2 - y1
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= 0:
                continue
            ux, uy = dx / dist, dy / dist
            t = 0.0
            while t < dist:
                t2 = min(t + dash, dist)
                Line(points=[x1 + ux * t, y1 + uy * t,
                             x1 + ux * t2, y1 + uy * t2], width=lw)
                t = t2 + gap

    # ---------------- 交互 ----------------
    def on_touch_down(self, touch):
        # ⚠️ 坐标系：node_at 的命中表以 _ox/_oy（含 self.x/self.y）为基准，
        # 是**窗口坐标**系；而 collide_point 期望**本地**坐标。旧代码直接
        # collide_point(*touch.pos)（窗口坐标）→ 只有窗口左下一条细带能通过
        # 判定，实机大部分区域点击无效（小窗口下尤其明显）。这里统一：
        # collide 用 touch.pos - self.pos（本地），node_at 用 touch.pos（窗口）。
        if self.collide_point(touch.pos[0] - self.x, touch.pos[1] - self.y):
            nd = self.node_at(*touch.pos)
            if nd is not None and self._on_pick:
                self._on_pick(nd.key)
                return True
        return super().on_touch_down(touch)

    def refresh_scale(self, scale: float) -> None:
        self._redraw()


# ============================================================
# 小按钮工厂（页面里复用）
# ============================================================
def small_btn(text: str, tone: str = 'plain', cb: Callable = None,
              width: float = None, height: float = 26,
              font_size: float = FS_SM) -> Button:
    """页面内的小按钮（设计稿 .px-btn.sm）。

    Args:
        tone: plain / primary / danger / warn。
        width: 指定宽度；缺省按文本长度估算（CJK 按 ~14px/字，留 20px 内边距）。
        height: 指定高度；弹窗页脚建议传 40~42 以满足交互尺寸下限。
        font_size: 字号；弹窗页脚建议传 ``FS_BODY``（13px）以免「字挤不下」。
    """
    auto_w = max(len(text) * 14 + 20, 64)
    b = Button(text=text, font_size=font_size, size_hint=(None, None),
               size=(width or auto_w, height),
               background_normal='')
    tones = {'primary': ((0.078, 0.188, 0.173, 1), 'cyan', 'cyan'),
             'danger': ((0.227, 0.118, 0.118, 1), 'red', 'red'),
             'warn': ((0.227, 0.196, 0.118, 1), 'yellow', 'yellow'),
             'plain': (list(COLORS['panel_2']), 'text', 'border_2')}
    bg, fg, bdc = tones.get(tone, tones['plain'])
    b.background_color = list(bg)
    b.color = COLORS[fg]
    add_pixel_border(b, color=COLORS[bdc])
    if cb:
        b.bind(on_release=lambda *_: cb())
    return b


def head_group(*widgets) -> BoxLayout:
    """把若干小控件打包成页面头部的一个横向组"""
    box = BoxLayout(orientation='horizontal', spacing=6, size_hint_x=None,
                    size_hint_y=None, height=30)
    for w in widgets:
        box.add_widget(w)
    box.width = sum(getattr(w, 'width', 0) + 6 for w in widgets)
    return box


# ============================================================
# S05 技能页面
# ============================================================
class SkillPage(U.PageScreen):
    """全屏技能页（设计稿 S05）：3×2 卡片网格。

    Args:
        on_action: 卡片底部动作回调 ``fn(skill_id, kind)``，
            kind = 'drop'（进入投放模式）/'cast'（立即释放）。
    """

    def __init__(self, on_action: Callable = None, on_sort: Callable = None, **kwargs):
        super().__init__(title=i18n.t('sk_page_title'), **kwargs)
        self._on_action = on_action
        self._sort = 'profit'
        self.sort_btns: Dict[str, Button] = {}

        self.lbl_compute = mk_label('', font_size=FS_CAP, color=COLORS['text_mute'])
        for key, label in (('profit', 'sk_sort_profit'), ('cd', 'sk_sort_cd'),
                           ('cost', 'sk_sort_cost'), ('uses', 'sk_sort_uses')):
            b = small_btn(i18n.t(label), 'primary' if key == 'profit' else 'plain',
                          lambda k=key: self._pick_sort(k))
            self.sort_btns[key] = b
        self.lbl_sort = mk_label(i18n.t('sk_sort_label'), font_size=FS_CAP,
                                 color=COLORS['text_mute'])
        self.btn_only_ready = small_btn(i18n.t('sk_only_ready'), 'plain',
                                        lambda: self._pick_sort('ready'))
        self.add_head_widget(self.lbl_sort)
        for b in self.sort_btns.values():
            self.add_head_widget(b)
        self.add_head_widget(self.btn_only_ready)
        self.add_head_widget(self.lbl_compute)

        grid = GridLayout(cols=3, rows=2, spacing=8)
        self.cards: Dict[str, SkillPageCard] = {}
        self.body.add_widget(grid)
        self._grid = grid

    def _pick_sort(self, key: str) -> None:
        if key == 'ready':
            self._sort = 'ready'
        else:
            self._sort = key
        if self._on_sort:
            self._on_sort(self._sort)

    def ensure_cards(self, skill_ids: Sequence[str]) -> None:
        """按技能 id 列表懒建卡片（数量固定，只建一次）"""
        for sid in skill_ids:
            if sid in self.cards:
                continue
            card = SkillPageCard(
                on_action=lambda s=sid: self._on_action and self._on_action(s, 'auto'))
            self.cards[sid] = card
            self._grid.add_widget(card)

    def set_sort_visual(self, active: str) -> None:
        for key, b in self.sort_btns.items():
            on = (key == active)
            b.background_color = (0.078, 0.188, 0.173, 1) if on else list(COLORS['panel_2'])
            b.color = COLORS['cyan'] if on else COLORS['text']
            add_pixel_border(b, color=COLORS['cyan'] if on else COLORS['border_2'])
        on_ready = (active == 'ready')
        self.btn_only_ready.background_color = (0.078, 0.188, 0.173, 1) if on_ready \
            else list(COLORS['panel_2'])
        self.btn_only_ready.color = COLORS['cyan'] if on_ready else COLORS['text']

    def set_compute(self, value: float) -> None:
        self.lbl_compute.text = (f"{i18n.t('sk_avail_compute')} "
                                 f"[color={U.MK['yellow']}]{value:.0f}[/color]")


# ============================================================
# S06 科技树页面
# ============================================================
class TechPage(U.PageScreen):
    """全屏科技树页（v0.5 重做）：一屏铺开的节点网络图（参考《瘟疫公司》）。

    结构：
        ┌ 顶部工具头：标题 / 统计 chips / 重置按钮 ────────────────┐
        │ 主体：TechCanvas 网络图画布（等比缩放铺满）             │
        │ 底部：选中节点详情面板（名称 / 效果 / 升级按钮 / 算力）   │
        └──────────────────────────────────────────────────────┘

    Args:
        on_unlock: T0 解锁回调 ``fn(slot_id)``。
        on_level: 分支升级回调 ``fn(slot_id, branch_id)``。
        on_reset: 重置回调 ``fn()``。

    与旧版差异：
        - 旧版是「左侧槽位链路 + 右侧 3 分支矩阵」两栏，一次只看一个槽位；
          新版一屏看全 24 个节点与依赖关系，节点间连线表达前置链。
        - 旧版有互斥灰化（dim）；新版取消互斥，同槽位 3 分支可全部点满。
    """

    DETAIL_H = 150            # 底部详情面板高度

    def __init__(self, on_unlock: Callable = None, on_level: Callable = None,
                 on_reset: Callable = None, on_select: Callable = None, **kwargs):
        super().__init__(title=i18n.t('tt_page_title'), **kwargs)
        self._on_unlock = on_unlock
        self._on_level = on_level
        self.on_select = on_select          # main 注入：节点被点选后回灌详情
        self.selected_key: str = ''
        self._cur_node = None            # 选中的 TechNode
        self._built = False

        # ---- 顶部统计 ----
        self.lbl_compute = mk_label('', font_size=FS_CAP, color=COLORS['text_mute'],
                                    markup=True)
        self.chip_t0 = PxChip('', tone='up')
        self.chip_lv = PxChip('', tone='up')
        self.chip_full = PxChip('', tone='sys')
        self.add_head_widget(self.chip_t0)
        self.add_head_widget(self.chip_lv)
        self.add_head_widget(self.chip_full)
        self.add_head_widget(self.lbl_compute)
        self.add_head_widget(small_btn(i18n.t('tt_reset'), 'plain',
                                       lambda: on_reset and on_reset()))

        # ---- 图例（色盲辅助：形状 + 颜色双编码）----
        self.legend = BoxLayout(orientation='horizontal', spacing=10,
                                size_hint_y=None, height=24, padding=(2, 0))
        self._legend_labels = []
        for text, col in ((i18n.t('tt_legend_done'), COLORS['cyan']),
                          (i18n.t('tt_legend_can'), COLORS['blue']),
                          (i18n.t('tt_legend_poor'), COLORS['red']),
                          (i18n.t('tt_legend_lock'), COLORS['text_mute'])):
            lb = mk_label(text, font_size=FS_CAP, color=col, size_hint_x=None)
            U.fit_width(lb, pad=8)
            self.legend.add_widget(lb)
            self._legend_labels.append(lb)
        self.legend.add_widget(Widget())
        self.lbl_hint = mk_label(i18n.t('tt_graph_hint'), font_size=FS_CAP,
                                 color=COLORS['text_mute'], halign='right')
        self.legend.add_widget(self.lbl_hint)
        self.body.add_widget(self.legend)

        # ---- 网络图画布 ----
        self.canvas_view = TechCanvas(on_pick=self._on_node_pick)
        self.body.add_widget(self.canvas_view)

        # ---- 底部详情面板 ----
        self.detail = StrokePanel(bg=COLORS['panel'], border=COLORS['border_2'],
                                  spacing=6, padding=(10, 8),
                                  size_hint_y=None, height=self.DETAIL_H)
        drow = BoxLayout(orientation='horizontal', spacing=10)
        dleft = BoxLayout(orientation='vertical', spacing=4)
        self.lbl_d_title = mk_label('', font_size=FS_H3, color=COLORS['cyan'],
                                    markup=True)
        self.lbl_d_desc = mk_label('', font_size=FS_CAP,
                                   color=COLORS['text_mute'], valign='top')
        dleft.add_widget(self.lbl_d_title)
        dleft.add_widget(self.lbl_d_desc)
        drow.add_widget(dleft)

        # 右侧操作列：算力提示 + 主按钮，整体垂直居中
        dright = BoxLayout(orientation='vertical', spacing=6,
                           size_hint_x=None, width=280)
        dright.add_widget(Widget())                  # 顶弹簧
        self.lbl_d_cost = mk_label('', font_size=FS_CAP,
                                   color=COLORS['text_dim'], halign='right',
                                   size_hint_y=None, height=24)
        self.btn_action = small_btn('', 'primary', self._do_action,
                                    height=44, font_size=FS_BODY)
        self.btn_action.size_hint_y = None
        self.btn_action.height = 44
        dright.add_widget(self.lbl_d_cost)
        dright.add_widget(self.btn_action)
        dright.add_widget(Widget())                  # 底弹簧
        drow.add_widget(dright)
        self.detail.add_widget(drow)
        self.body.add_widget(self.detail)
        self.body.size_hint_y = 1

        self._action_cb: Callable = None
        self._show_detail(None)

    # ---------------- 建图（一次） ----------------
    def ensure_slots(self, tech_tree: Sequence, on_slot_click: Callable = None) -> None:
        """建网络图（只调一次）。

        参数名沿用旧接口（``on_slot_click`` 不再需要——网络图是全屏的，
        点节点即选中，不需要「切换右侧矩阵」）。保留形参只为兼容 main.py 调用。
        """
        if self._built:
            return
        self.canvas_view.rebuild(tech_tree)
        self._built = True

    # ---------------- 节点选中 ----------------
    def _on_node_pick(self, key: str) -> None:
        self.selected_key = key
        # 点选回灌给 main：重算该节点 desc/state 并刷新整图与详情面板
        if callable(self.on_select):
            self.on_select(key)
        else:
            self._sync_detail_from_node()

    def _node(self, key: str):
        return self.canvas_view.nodes.get(key)

    def _sync_detail_from_node(self) -> None:
        """节点状态由 main 喂进来后调用：按当前节点刷新底部详情。"""
        nd = self._node(self.selected_key)
        self._show_detail(nd)

    def _show_detail(self, nd) -> None:
        """按节点渲染底部详情面板（None = 未选中）。"""
        self._cur_node = nd
        self._action_cb = None
        if nd is None:
            self.lbl_d_title.text = f"[b]{i18n.t('tt_pick_node')}[/b]"
            self.lbl_d_desc.text = i18n.t('tt_pick_node_hint')
            self.lbl_d_cost.text = ''
            self.btn_action.text = i18n.t('tt_btn_pick')
            self.btn_action.disabled = True
            self._tone_btn('plain')
            return
        st = {'done': i18n.t('tt_st_done'), 'can': i18n.t('tt_st_can'),
              'poor': i18n.t('tt_st_poor'), 'lock': i18n.t('tt_st_lock')}[nd.state]
        kind = i18n.t('tt_kind_t0') if nd.kind == 't0' else i18n.t('tt_kind_branch')
        self.lbl_d_title.text = f"[b]{nd.name}[/b]  [size={int(FS_CAP)}]{nd.code}[/size]"
        self.lbl_d_desc.text = (f"{kind} · {st}   "
                                f"{i18n.t('tt_level_fmt').format(a=nd.level, b=nd.max_level)}"
                                f"\n{getattr(nd, 'desc', '') or ''}")
        self.lbl_d_cost.text = (i18n.t('tt_cost_fmt').format(n=f"{nd.cost:.0f}")
                                if nd.cost else '')
        if nd.state == 'done' and nd.level >= nd.max_level:
            self.btn_action.text = i18n.t('tt_maxed')
            self.btn_action.disabled = True
            self._tone_btn('plain')
        elif nd.state in ('can',):
            self.btn_action.text = (i18n.t('tt_btn_unlock')
                                    if nd.kind == 't0' else
                                    i18n.t('tt_btn_level'))
            self.btn_action.disabled = False
            self._tone_btn('primary')
        else:
            self.btn_action.text = (i18n.t('tt_btn_need_more')
                                    if nd.state == 'poor' else
                                    i18n.t('tt_btn_locked'))
            self.btn_action.disabled = True
            self._tone_btn('plain')

    def _tone_btn(self, tone: str) -> None:
        tones = {'primary': ((0.078, 0.188, 0.173, 1), 'cyan', 'cyan'),
                 'plain': (list(COLORS['panel_2']), 'text_mute', 'border_2')}
        bg, fg, bdc = tones.get(tone, tones['plain'])
        self.btn_action.background_color = list(bg)
        self.btn_action.color = COLORS[fg]
        add_pixel_border(self.btn_action, color=COLORS[bdc])

    def _do_action(self) -> None:
        if self._action_cb:
            self._action_cb()

    def set_action(self, text: str, callback: Callable, enabled: bool = True,
                   tone: str = 'primary') -> None:
        """由 main 覆盖详情面板的按钮文案与回调（状态机在 main 里）。"""
        self.btn_action.text = text
        self.btn_action.disabled = not enabled
        self._action_cb = callback if enabled else None
        self._tone_btn(tone if enabled else 'plain')

    # 兼容旧接口名（test_ui_v4 仍会调用）
    def set_main_action(self, text: str, callback: Callable, enabled: bool = True,
                        tone: str = 'primary') -> None:
        self.set_action(text, callback, enabled, tone)

    # ---------------- 键盘导航 ----------------
    def move_selection(self, dslot: int = 0, dbranch: int = 0) -> bool:
        """按方向键在图上移动选中节点。

        dslot: 左右在**槽位主链**上移动（同列的分支跟随）。
        dbranch: 在当前槽位的 3 条分支之间移动。
        """
        nodes = self.canvas_view
        order = nodes._order
        if not order:
            return False
        cur = nodes.nodes.get(self.selected_key) if self.selected_key else None
        if cur is None:
            self._on_node_pick(order[0])
            return True
        slots = nodes._slots
        si = slots.index(cur.slot_id) if cur.slot_id in slots else 0
        if dslot:
            si = max(0, min(len(slots) - 1, si + dslot))
            self._on_node_pick(f"t0:{slots[si]}")
            return True
        if dbranch:
            # 在当前槽位内：分支键顺序即 branches 顺序
            bkeys = [k for k in order if k.startswith("br:")
                     and nodes.nodes[k].slot_id == cur.slot_id]
            if cur.kind == 't0':
                if bkeys:
                    self._on_node_pick(bkeys[0])
                return True
            bi = bkeys.index(cur.key) if cur.key in bkeys else 0
            bi = max(0, min(len(bkeys) - 1, bi + dbranch))
            self._on_node_pick(bkeys[bi])
            return True
        return False

    def refresh_scale(self, scale: float) -> None:
        self.detail.height = max(self.DETAIL_H * scale, 108)
        self.legend.height = 24 * scale
        for lb in self._legend_labels:
            lb.font_size = FS_CAP * scale
        self.lbl_hint.font_size = FS_CAP * scale
        self.lbl_d_title.font_size = FS_H3 * scale
        self.lbl_d_desc.font_size = FS_CAP * scale
        self.lbl_d_cost.font_size = FS_CAP * scale
        self.canvas_view.refresh_scale(scale)


# ============================================================
# S10 成就面板
# ============================================================
class AchPage(U.PageScreen):
    """全屏成就面板（设计稿 S10）：4 列网格 + 总进度 + 最接近达成。"""

    def __init__(self, on_filter: Callable = None, **kwargs):
        super().__init__(title=i18n.t('ach_page_title'), **kwargs)
        self._on_filter = on_filter
        self.filter_btns: Dict[str, Button] = {}
        for key, label in (('all', 'ach_f_all'), ('cond', 'ach_f_cond'),
                           ('evt', 'ach_f_evt')):
            b = small_btn(i18n.t(label), 'primary' if key == 'all' else 'plain',
                          lambda k=key: self._set_filter(k),
                          height=32, font_size=FS_CAP)
            self.filter_btns[key] = b
            self.add_head_widget(b)
        self.add_head_widget(small_btn(i18n.t('ach_only_miss'), 'plain',
                                       lambda: self._set_filter('miss'),
                                       height=32, font_size=FS_CAP))

        head = BoxLayout(orientation='vertical', spacing=6,
                         size_hint_y=None, height=76)
        row = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None,
                        height=44)
        self.lbl_total = mk_label('', font_size=FS_H3, color=COLORS['green'])
        U.fit_width(self.lbl_total, pad=10)
        self.lbl_split = mk_label('', font_size=FS_CAP, color=COLORS['text_mute'])
        self.chip_new = PxChip('', tone='up', height=30)
        row.add_widget(PixelSprite(SPR_TROPHY, PAL_TROPHY, scale=3))   # 36×36 美术
        row.add_widget(self.lbl_total)
        row.add_widget(self.lbl_split)
        row.add_widget(Widget())
        row.add_widget(self.chip_new)
        head.add_widget(row)
        self.progress = SegBar(segments=20, filled=0.0, size_hint_y=None, height=18)
        head.add_widget(self.progress)
        self.body.add_widget(head)

        scroll = ScrollView(bar_width=6)
        self.grid = GridLayout(cols=4, spacing=10, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        scroll.add_widget(self.grid)
        self.body.add_widget(scroll)

        ft = BoxLayout(orientation='horizontal', spacing=8,
                       size_hint_y=None, height=44)
        self.lbl_near = mk_label(i18n.t('ach_nearest'), font_size=FS_CAP,
                                 color=COLORS['text_mute'])
        U.fit_width(self.lbl_near, pad=10)
        self.near_chips: List[PxChip] = []
        ft.add_widget(self.lbl_near)
        for _ in range(3):
            c = PxChip('', tone='sys', height=30)
            self.near_chips.append(c)
            ft.add_widget(c)
        ft.add_widget(Widget())
        ft.add_widget(mk_label(i18n.t('ach_evt_note'), font_size=FS_CAP,
                               color=COLORS['text_mute'], halign='right'))
        self.body.add_widget(ft)
        self.body.bind(size=self._refit_cells)

    def _set_filter(self, key: str) -> None:
        if self._on_filter:
            self._on_filter(key)

    def _refit_cells(self, *_args) -> None:
        """Bug5：按 body 可用高度自适应行高，让网格铺满滚动区（消灭大留白）。

        行高 clamp 在 [140, 210]：低于 140 挤、高于 210 空洞。
        """
        n = len(self.grid.children)
        if not n:
            return
        rows = (n + 3) // 4
        avail = self.body.height - 152          # padding16 + spacing16 + head76 + foot44
        if avail < 140:
            return
        h = max(140.0, min((avail - (rows - 1) * 10) / rows, 200.0))
        for ch in self.grid.children:
            ch.height = h

    def set_filter_visual(self, active: str) -> None:
        for key, b in self.filter_btns.items():
            on = (key == active)
            b.background_color = (0.078, 0.188, 0.173, 1) if on else list(COLORS['panel_2'])
            b.color = COLORS['cyan'] if on else COLORS['text']
            add_pixel_border(b, color=COLORS['cyan'] if on else COLORS['border_2'])

    def rebuild(self, cells: Sequence[Tuple[str, str, str, bool, bool]],
                got: int, total: int, cond_got: int, cond_total: int,
                evt_got: int, evt_total: int, new_count: int,
                nearest: Sequence[Tuple[str, str]]) -> None:
        """重建成就网格。

        Args:
            cells: ``[(icon, name, desc, got, is_event), …]``
        """
        self.grid.clear_widgets()
        for icon, name, desc, g, ev in cells:
            self.grid.add_widget(AchCell(icon, name, desc, got=g, event_type=ev,
                                         status_text=(i18n.t('ach_done') if g
                                                      else i18n.t('ach_open'))))
        self.lbl_total.text = (f"{i18n.t('ach_unlocked')} {got} / {total}")
        self.lbl_split.text = (f"{i18n.t('ach_cond')} {cond_got}/{cond_total} · "
                               f"{i18n.t('ach_evt')} {evt_got}/{evt_total}")
        self.chip_new.set_tone('up', f"{i18n.t('ach_new')} {new_count}")
        self.progress.set_value(got * (20.0 / max(total, 1)))
        for i, (name, text) in enumerate(nearest[:3]):
            self.near_chips[i].set_tone('sys', f"{name} {text}")
        self._refit_cells()


# ============================================================
# S11 帮助 / 快捷键
# ============================================================
class HelpPage(U.PageScreen):
    """全屏帮助页（设计稿 S11）：左快捷键栏 + 右玩法目标，填满无留白（参照设置/成就页）。"""

    def __init__(self, **kwargs):
        super().__init__(title=i18n.t('help_page_title'), **kwargs)
        # 头部美术 + 一句话简介
        self.add_head_widget(PixelSprite(SPR_ROBOT, PAL_ROBOT, scale=2))
        self.add_head_widget(mk_label(i18n.t('help_keys_count'), font_size=FS_CAP,
                                      color=COLORS['text_mute']))

        row = BoxLayout(orientation='horizontal', spacing=10)
        # ── 左：操作快捷键（3 组；每组纵向弹性，行高随面板放大，消灭留白）──
        left = StrokePanel(bg=COLORS['panel'], border=COLORS['border_2'],
                           spacing=10, padding=(12, 10))
        lh = BoxLayout(orientation='horizontal', spacing=8, size_hint_y=None, height=34)
        lh.add_widget(PixelSprite(SPR_GEAR, PAL_GEAR, scale=2))    # 24×24 美术
        lh.add_widget(mk_label(i18n.t('help_shortcuts_t'), font_size=FS_BODY,
                               color=COLORS['cyan'], size_hint_y=None, height=32))
        left.add_widget(lh)

        groups = [
            ('help_g_time', [('Space', 'k_pause'), ('↑', 'k_speed_up'),
                             ('↓', 'k_speed_down')]),
            ('help_g_view', [('Tab', 'k_region'), ('+ / =', 'k_zoom_in'),
                             ('- / _', 'k_zoom_out'), ('F11', 'k_fullscreen'),
                             ('F12', 'k_fit')]),
            ('help_g_panel', [('1 – 6', 'k_skill'), ('F', 'k_drop'), ('K', 'k_tech'),
                              ('A', 'k_ach'), ('S / R', 'k_save'), ('L', 'k_lang'),
                              ('Esc', 'k_esc')]),
        ]
        # 三组横向并排，纵向弹性 → 每组按可用高度均分行高，不再挤在顶部
        kg_row = BoxLayout(orientation='horizontal', spacing=10)
        for title_key, rows in groups:
            kg_row.add_widget(self._key_group(i18n.t(title_key), rows))
        left.add_widget(kg_row)
        # 弹性填充：游戏目标卡（美术机器人压阵 + 多行要点，吃掉左侧剩余高度）
        goal = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border'],
                           spacing=8, padding=(12, 10), size_hint_y=None, height=300)
        gcol = BoxLayout(orientation='vertical', spacing=10,
                         size_hint=(None, None), size=(660, 270))
        g0 = AnchorLayout(size_hint_y=None, height=84)
        g0.add_widget(PixelSprite(SPR_ROBOT, PAL_ROBOT, scale=7))   # 84×84
        gt = mk_label(i18n.t('help_goal_t'), font_size=FS_SM,
                      color=COLORS['yellow'], size_hint=(None, None), size=(660, 28))
        gt.text_size = (660, 28); gt.halign = 'center'
        gb = mk_label(i18n.t('help_goal_body'), font_size=FS_CAP,
                      color=COLORS['text_dim'], valign='top',
                      size_hint=(None, None), size=(660, 150))
        gb.text_size = (660, 150)
        gcol.add_widget(g0); gcol.add_widget(gt); gcol.add_widget(gb)
        ghold = AnchorLayout(anchor_x='center', anchor_y='center', padding=(0, 14))
        ghold.add_widget(gcol)
        goal.add_widget(ghold)
        left.add_widget(goal)

        # ── 右：小贴士 + 无障碍 + 世界旗林（旗林弹性吃满剩余高度）──
        right = StrokePanel(bg=COLORS['panel'], border=COLORS['border_2'],
                            spacing=10, padding=(12, 10))
        # 小贴士：纵向弹性 → 正文按可用高度铺满（不再固定 200 只占一半）
        tips = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border'],
                           spacing=6, padding=(10, 10))
        tips.add_widget(mk_label(i18n.t('help_tips_t'), font_size=FS_SM,
                                 color=COLORS['yellow'], size_hint_y=None, height=24))
        tips.add_widget(mk_label(i18n.t('help_tips_body'), font_size=FS_SM,
                                 color=COLORS['text_dim'], valign='top'))
        right.add_widget(tips)
        # 节奏参考（玩家反馈 10：让玩家知道「30 周期 18% 是正常中局」，
        # 而不是以为卡住了）。放在小贴士正下方，是第二个要读的卡片。
        pace = StrokePanel(bg=COLORS['panel_2'], border=COLORS['cyan'],
                           spacing=6, padding=(10, 10))
        pace.add_widget(mk_label(i18n.t('help_pace_t'), font_size=FS_SM,
                                 color=COLORS['cyan'], size_hint_y=None, height=24))
        pace.add_widget(mk_label(i18n.t('help_pace_body'), font_size=FS_SM,
                                 color=COLORS['text_dim'], valign='top'))
        right.add_widget(pace)
        # 无障碍约定：固定高度贴内容（3 行 FS_SM 正文）
        note = StrokePanel(bg=COLORS['panel_2'], border=COLORS['cyan'],
                           spacing=0, padding=(10, 10), size_hint_y=None, height=108)
        note.add_widget(mk_label(i18n.t('help_a11y'), font_size=FS_SM,
                                 color=COLORS['text_dim'], markup=True,
                                 valign='middle'))
        right.add_widget(note)
        # 世界旗林（美术填充，仿设置页；旗子放大让网格吃满卡片宽度/高度）
        fcard = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border'],
                            spacing=6, padding=(10, 8))
        fcard.add_widget(mk_label(i18n.t('set_flags'), font_size=FS_SM,
                                  color=COLORS['yellow'], size_hint_y=None, height=24))
        # 网格高度贴合内容（minimum_height），交由 AnchorLayout 居中：
        # 若不绑定，网格会被弹性卡片拉伸到 1020px（内容仅 446px）→ 574px 大留白。
        fgrid = GridLayout(cols=5, spacing=(10, 10), size_hint=(None, None))
        for code in FLAG_CODES[:20]:
            fgrid.add_widget(FlagWidget(code=code, size=(190, 124)))
        fgrid.bind(minimum_height=fgrid.setter('height'),
                   minimum_width=fgrid.setter('width'))
        fhold = AnchorLayout(anchor_x='center', anchor_y='center', padding=(0, 10))
        fhold.add_widget(fgrid)
        fcard.add_widget(fhold)
        right.add_widget(fcard)

        row.add_widget(left)
        row.add_widget(right)
        self.body.add_widget(row)

    def _key_group(self, title: str, rows) -> StrokePanel:
        """快捷键分组：纵向弹性，行高按可用高度均分（消灭组内下半留白）。

        每组子项（标题 + 若干行）用 size_hint_y=1 均分空间，行高会随帮助页
        高度放大 —— 小屏不挤、大屏不留白；描述文字统一升到 FS_SM 加粗可读。
        """
        box = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border'],
                          spacing=6, padding=(10, 10))
        box.add_widget(mk_label(title, font_size=FS_SM, color=COLORS['purple'],
                                size_hint_y=None, height=24))
        for key, dk in rows:
            r = FloatLayout(size_hint_y=1)          # 弹性行 → 均分剩余高度
            kbd = PxChip(key, tone='plain', height=24)
            kbd.color = COLORS['yellow']
            kbd._edge = list(COLORS['border_2'])
            kbd._bg = list(COLORS['panel'])
            kbd._resize()
            lbl = mk_label(i18n.t(dk), font_size=FS_SM, color=COLORS['text_dim'],
                           valign='middle')
            r.add_widget(kbd)
            r.add_widget(lbl)

            def _lay(*_a, r=r, k=kbd, l=lbl):
                k.pos = (r.x, r.y + (r.height - k.height) / 2)
                l.pos = (r.x + k.width + 8, r.y)
                l.size = (max(r.width - k.width - 8, 1), r.height)
                l.text_size = l.size
                l.valign = 'middle'
            r.bind(pos=_lay, size=_lay)
            _lay()
            box.add_widget(r)
        return box


# ============================================================
# S12 设置与存档
# ============================================================
class SettingsPage(U.PageScreen):
    """全屏设置页（设计稿 S12）：左显示与操作 / 右存档槽位。"""

    def __init__(self, on_lang: Callable = None, on_scale: Callable = None,
                 on_speed: Callable = None, on_grid: Callable = None,
                 on_a11y: Callable = None, on_motion: Callable = None,
                 on_sound: Callable = None,
                 on_tutorial: Callable = None,
                 slot_actions: Callable = None, on_reset: Callable = None,
                 **kwargs):
        super().__init__(title=i18n.t('set_page_title'), **kwargs)
        self.add_head_widget(small_btn(i18n.t('set_restore'), 'plain',
                                       lambda: on_reset and on_reset(),
                                       height=32, font_size=FS_CAP))

        row = BoxLayout(orientation='horizontal', spacing=8)
        # 左：显示与操作
        left = StrokePanel(bg=COLORS['panel'], border=COLORS['border_2'],
                           spacing=10, padding=(10, 10))
        lt = BoxLayout(orientation='horizontal', spacing=8,
                       size_hint_y=None, height=28)
        lt.add_widget(PixelSprite(SPR_GEAR, PAL_GEAR, scale=2))    # 24×24 美术
        lt.add_widget(mk_label(i18n.t('set_display'), font_size=FS_SM,
                               color=COLORS['cyan'], size_hint_y=None, height=28))
        left.add_widget(lt)

        self.lbl_lang_val = SegSwitch([i18n.t('lang_zh'), i18n.t('lang_en')], 0,
                                      on_change=lambda i: on_lang and on_lang(i))
        left.add_widget(self._row('set_lang', self.lbl_lang_val,
                                  i18n.t('set_lang_hint')))
        self.sw_speed = SegSwitch(['×0.5', '×1', '×2', '×4'], 1,
                                  on_change=lambda i: on_speed and on_speed(i))
        left.add_widget(self._row('set_speed', self.sw_speed, ''))
        self.sw_motion = SegSwitch([i18n.t('set_motion_full'), i18n.t('set_motion_low')],
                                   0, on_change=lambda i: on_motion and on_motion(i))
        left.add_widget(self._row('set_motion', self.sw_motion, i18n.t('set_motion_hint')))
        self.sw_grid = SegSwitch([i18n.t('set_grid_off'), i18n.t('set_grid_dim'),
                                  i18n.t('set_grid_strong')], 1,
                                 on_change=lambda i: on_grid and on_grid(i))
        left.add_widget(self._row('set_grid', self.sw_grid, i18n.t('set_grid_hint')))
        self.sw_a11y = SegSwitch([i18n.t('set_off'), i18n.t('set_on')], 1,
                                 on_change=lambda i: on_a11y and on_a11y(i))
        left.add_widget(self._row('set_a11y', self.sw_a11y, i18n.t('set_a11y_hint')))
        self.sw_sound = SegSwitch([i18n.t('set_off'), i18n.t('set_on')], 1,
                                  on_change=lambda i: on_sound and on_sound(i))
        left.add_widget(self._row('set_sound', self.sw_sound, i18n.t('set_sound_hint')))

        # UI 缩放行
        zoom = BoxLayout(orientation='horizontal', spacing=8,
                         size_hint_y=None, height=44)
        zoom.add_widget(mk_label(i18n.t('set_zoom'), font_size=FS_SM,
                                 color=COLORS['text_dim'], size_hint_x=None,
                                 width=200))
        self.lbl_zoom = mk_label('×1.00', font_size=FS_SM,
                                 halign='center', size_hint_x=None, width=72)
        zoom.add_widget(small_btn('－', 'plain',
                                  lambda: on_scale and on_scale(-0.10),
                                  width=44, height=40, font_size=FS_SM))
        zoom.add_widget(self.lbl_zoom)
        zoom.add_widget(small_btn('＋', 'plain',
                                  lambda: on_scale and on_scale(+0.10),
                                  width=44, height=40, font_size=FS_SM))
        zoom.add_widget(Widget())
        zoom.add_widget(mk_label(i18n.t('set_zoom_hint'), font_size=FS_CAP,
                                 color=COLORS['text_mute']))
        left.add_widget(zoom)
        # 重看教程（P0-1）：随时重新走一遍新手引导
        left.add_widget(small_btn('重看教程', 'on',
                                  lambda: on_tutorial and on_tutorial(),
                                  width=200, height=44, font_size=FS_BODY))
        # 快捷键速查（Bug5：填充留白）
        keys = KeyBox(i18n.t('set_keys'), [
            ('Space', 'k_pause'), ('1 – 6', 'k_skill'), ('F1', 'k_help'),
            ('Esc', 'k_esc'), ('L', 'k_lang'), ('S / R', 'k_save'),
        ])
        keys.size_hint_y = None
        keys.height = 190
        left.add_widget(keys)
        # 关于游戏（Bug5：弹性卡片，吃掉面板剩余空间；奖杯像素画压阵）
        about = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border'],
                            spacing=8, padding=(12, 10))
        acol = BoxLayout(orientation='vertical', spacing=10, size_hint=(None, None),
                         size=(620, 300))
        a0 = AnchorLayout(size_hint_y=None, height=84)
        a0.add_widget(PixelSprite(SPR_TROPHY, PAL_TROPHY, scale=7))   # 84×84
        at = mk_label(i18n.t('set_about'), font_size=FS_SM,
                      color=COLORS['yellow'], size_hint=(None, None),
                      size=(620, 28))
        at.text_size = (620, 28)
        at.halign = 'center'
        a1 = mk_label(i18n.t('set_about_body'), font_size=FS_CAP,
                      color=COLORS['text_dim'], valign='top',
                      size_hint=(None, None), size=(620, 150))
        a1.text_size = (620, 150)
        acol.add_widget(a0)
        acol.add_widget(at)
        acol.add_widget(a1)
        ahold = AnchorLayout(anchor_x='center', anchor_y='center', padding=(0, 14))
        ahold.add_widget(acol)
        about.add_widget(ahold)
        left.add_widget(about)

        # 右：存档槽位
        right = StrokePanel(bg=COLORS['panel'], border=COLORS['border_2'],
                            spacing=8, padding=(10, 10))
        hdr = BoxLayout(orientation='horizontal', spacing=8,
                        size_hint_y=None, height=28)
        hdr.add_widget(PixelSprite(SPR_ROBOT, PAL_ROBOT, scale=2))  # 24×24 美术
        hdr.add_widget(mk_label(i18n.t('set_slots'), font_size=FS_SM,
                                color=COLORS['cyan']))
        hdr.add_widget(Widget())
        hdr.add_widget(mk_label(i18n.t('set_slots_hint'), font_size=FS_CAP,
                                color=COLORS['text_mute']))
        right.add_widget(hdr)
        self.slot_box = BoxLayout(orientation='vertical', spacing=8,
                                  size_hint_y=None, height=256)   # 3×80 + 2×8
        right.add_widget(self.slot_box)
        self._slot_actions = slot_actions
        right.add_widget(mk_label(i18n.t('set_slot_note'), font_size=FS_CAP,
                                  color=COLORS['text_mute'], size_hint_y=None,
                                  height=30, valign='top'))
        # 存档小贴士（Bug5：填充留白 + 美术机器人已入标题行）
        tips = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border'],
                           spacing=4, padding=(10, 8),
                           size_hint_y=None, height=180)
        tips.add_widget(mk_label(i18n.t('set_slot_tips'), font_size=FS_SM,
                                 color=COLORS['yellow'], size_hint_y=None,
                                 height=24))
        tips.add_widget(mk_label(i18n.t('set_slot_tips_body'), font_size=FS_CAP,
                                 color=COLORS['text_dim'], valign='top'))
        right.add_widget(tips)
        # 世界旗林（Bug5 美术填充）：20 国像素国旗墙，弹性卡片吃掉剩余空间
        fcard = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border'],
                            spacing=6, padding=(10, 8))
        fcard.add_widget(mk_label(i18n.t('set_flags'), font_size=FS_SM,
                                  color=COLORS['yellow'], size_hint_y=None,
                                  height=24))
        fgrid = GridLayout(cols=5, spacing=(12, 12))
        for code in FLAG_CODES[:20]:
            fgrid.add_widget(FlagWidget(code=code, size=(140, 92)))
        fhold = AnchorLayout(anchor_x='center', anchor_y='center')
        fhold.add_widget(fgrid)
        fcard.add_widget(fhold)
        right.add_widget(fcard)

        row.add_widget(left)
        row.add_widget(right)
        self.body.add_widget(row)

    @staticmethod
    def _row(key: str, control: Widget, hint: str) -> BoxLayout:
        r = BoxLayout(orientation='horizontal', spacing=10,
                      size_hint_y=None, height=48)
        r.add_widget(mk_label(i18n.t(key), font_size=FS_SM,
                              color=COLORS['text_dim'], size_hint_x=None, width=200))
        control.size_hint_x = None
        if isinstance(control, SegSwitch):
            control.width = 280
            control.height = 36        # Bug5: 22→36，开关格子更高更好点
        r.add_widget(control)
        r.add_widget(Widget())
        if hint:
            r.add_widget(mk_label(hint, font_size=FS_CAP,
                                  color=COLORS['text_mute']))
        return r

    def set_zoom_text(self, text: str) -> None:
        self.lbl_zoom.text = text

    def rebuild_slots(self, rows: Sequence[Tuple[str, str, bool]]) -> None:
        """重建 3 个存档槽位行。

        Args:
            rows: ``[(槽位名, 摘要, 是否当前槽) , …]``
        """
        self.slot_box.clear_widgets()
        for title, summary, active in rows:
            acts = []
            if self._slot_actions:
                acts = self._slot_actions(title)
            self.slot_box.add_widget(SaveSlotRowSlot(title, summary, acts, active,
                                                     height=80))


class SaveSlotRowSlot(SaveSlotRow):
    """settings 用的槽位行（保持类名可读性）"""


# ============================================================
# S14 事件日志抽屉
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
