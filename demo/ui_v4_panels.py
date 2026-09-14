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
    StrokePanel, mk_label, line_h, ST_FILL,
    PixelSprite, SPR_TROPHY, PAL_TROPHY, SPR_GEAR, PAL_GEAR,
    SPR_ROBOT, PAL_ROBOT,
)
from ui_v4_common import UiStats, small_btn  # noqa: F401


# ============================================================
# 页脚几何：面板整体缩放时，页脚必须**一起缩**
# ============================================================
def fit_footer(scale: float, box: BoxLayout,
               buttons: Sequence[Button], pad_base: float = 20.0,
               min_w_base: float = 64.0) -> None:
    """把面板页脚按 ``scale`` 等比排好。

    三件事一起做，缺一个都会挤出面板右边界：

    1. 按钮字号 / 行高按 scale 走（面板缩而字不缩，文字就顶出按钮）；
    2. 按钮宽度 = **真实字形宽 + 内边距**（不是均分、也不是
       ``len(text)*14+20`` 估算 —— 该估算对英文高估 ~60%，中文反而低估）；
    3. 页脚 padding / spacing / 按钮内边距也按 scale 走 —— 这些是「固定开销」，
       若只有文字在缩，挡位越小学得越吃亏（实测 DropPreview 在 ×0.68 溢出 7px）。

    ``scale=1.0`` 即设计基准，所以构造时也应调用一次。

    ⚠️ 不使用 ``ui_v4.fit_width``：它会 ``bind(text=...)``，每次缩放都新增一个
    回调闭包（缩放 N 次 = 布局回调 N 个）。这里直接用 ``text_size=(None,None)``
    现量现算，可反复调用。
    """
    s = float(scale)
    pad = max(round(pad_base * s), 8)
    min_w = max(round(min_w_base * s), 40)
    # 基准 padding/spacing 只在首次调用时记下 —— 否则反复缩放会连乘（0.8→1.2
    # 会把 8px 算成 8×0.8×1.2=7.68 而不是 9.6）。
    if not hasattr(box, '_base_spacing'):
        box._base_spacing = float(box.spacing)
        box._base_padding = tuple(box.padding)
    box.spacing = max(round(box._base_spacing * s), 3)
    box.padding = (max(round(box._base_padding[0] * s), 4),
                   max(round(box._base_padding[1] * s), 3))
    box.height = line_h(FS_CAP * s) + 12
    for b in buttons:
        b.font_size = FS_CAP * s
        b.height = line_h(FS_CAP * s)
        b.text_size = (None, None)          # 解除约束 → texture 即单行真实宽
        b.texture_update()
        w = max(float(b.texture_size[0]) + pad, min_w)
        b.width = w
        b.text_size = (max(w - pad, 1), b.height)


class InspectorPanel(StrokePanel):
    """左侧滑出的国家检视卡（设计稿 S03，宽 328px）。

    回答两个问题：这个国家被渗透到什么程度？它贡献了多少下载量？
    底部直接挂「向该国投放技能」，把查看与操作放在同一上下文里。

    Args:
        on_close: 关闭回调。
        on_drop: 点击「向该国投放技能」的回调 ``fn(code)``。
    """

    WIDTH = 328

    # 面板宽固定 328（不随分辨率/缩放变），所以内部文字可用宽是个定值：
    #   body 内容宽 = 328 - 2×8(panel padding) - 4(滚动条) - 2×8(body padding)
    BODY_W = 292
    WARN_W = 280                       # warn 面板左右各 6px padding

    # 需要「按文本自适应高度」的标签 -> 该标签自身的宽（CoreLabel 内部再扣 padding）
    # 基准口径见 WIDTH/BODY_W/WARN_W；refresh_scale 会把整张表等比缩放。
    _FIT_W_BASE: Dict[str, int] = {
        'lbl_name': BODY_W,             # padding=[72,0,0,0] → 文字区 220
        'lbl_seg_scale': BODY_W,
        'lbl_seg_note': BODY_W,
        'lbl_milestone': BODY_W,
        'lbl_warn': WARN_W,
    }
    FIT_WIDTH: Dict[str, float] = dict(_FIT_W_BASE)

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
        self._fit_cache: Dict[str, tuple] = {}   # 文案缓存：没变就不重量
        self._fit_need: Dict[str, float] = {}    # 量出来的真实需要高度

        # --- 标题栏 ---
        hd = FloatLayout(size_hint_y=None, height=line_h(FS_SM) + 8)
        self.lbl_hd = mk_label(i18n.t('insp_title'), font_size=FS_SM,
                               color=COLORS['cyan'])
        self.lbl_hd.pos_hint = {'x': 0, 'center_y': 0.5}
        self.lbl_hd.size_hint = (1, 1)
        self.lbl_hd.padding = [8, 0, 0, 0]      # 四元组！见 lbl_name 处的说明
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
        # 高度交给 _sync_row_heights()：国名两行（名称 + 大洲/人口/年龄结构）
        # 在英文下还要折行，写死 56 会把第二行整行裁掉。
        idrow = FloatLayout(size_hint_y=None, height=line_h(FS_H3) + line_h(FS_CAP))
        self._idrow = idrow
        self.flag = FlagWidget(code='CN', size_hint=(None, None), size=(64, 43),
                               pos_hint={'x': 0, 'top': 1})
        self.lbl_name = mk_label('', font_size=FS_H3, markup=True,
                                 valign='top', pos_hint={'x': 0, 'top': 1})
        self.lbl_name.size_hint = (1, 1)
        # ⚠️ 必须用四元组 padding，不能用 ``padding_x = 72``：
        #    Kivy 的 ``padding_x`` 是**单个数值**，会同时作为左右内边距，
        #    于是文字可用宽被砍掉 2×72=144 → 国名第二行（大洲/人口/年龄结构）
        #    被折成 3 行还塞进 56px 的行里 → 整行看不见（截图实证）。
        self.lbl_name.padding = [72, 0, 0, 0]
        idrow.add_widget(self.flag)
        idrow.add_widget(self.lbl_name)
        body.add_widget(idrow)

        # 行高要与 PxChip.BASE_H 一致（= line_h(FS_CAP)）：芯片自身 26px，
        # 容器只给 20px 会让芯片压到下一段文字上。
        self.chips_id = ChipRow([], height=line_h(FS_CAP))
        body.add_widget(self.chips_id)

        # --- 感染进度 ---
        # ⚠️ 以下所有 height 都走 line_h(字号)：以前写死 28/15/16/22/44，
        #    全都**小于该字号的实际行高**（FS_H2=32.2 需要 43px，却被塞进
        #    28px）→ 字形上下被裁。实测数据见 line_h 的文档。
        self.lbl_sec_infection = self._section_label(i18n.t('insp_infection'))
        body.add_widget(self.lbl_sec_infection)
        self.lbl_pct = mk_label('--', font_size=FS_H2, color=COLORS['cyan'],
                                halign='right', size_hint_y=None,
                                height=line_h(FS_H2))
        body.add_widget(self.lbl_pct)
        self.segbar = SegBar(segments=12, filled=0.0, threshold=None,
                             size_hint_y=None, height=14)
        body.add_widget(self.segbar)
        self.lbl_seg_scale = mk_label('', font_size=FS_TINY, color=COLORS['text_mute'],
                                      size_hint_y=None, height=line_h(FS_TINY))
        body.add_widget(self.lbl_seg_scale)
        self.lbl_seg_note = mk_label('', font_size=FS_CAP, markup=True,
                                     size_hint_y=None, height=line_h(FS_CAP))
        body.add_widget(self.lbl_seg_note)
        # --- 里程碑提示（玩家反馈 6：把「还差多少」直接写出来）---
        # 玩家看 12.34% 这个数字无感，但「距解锁还差 7.66%」是可执行的。
        # 里程碑口径来自引擎真实阈值：unlock_penetration_threshold=10%（解锁
        # 新国家）、block_threshold（进入阻止区间）、penetration_saturated=99%。
        self.lbl_milestone = mk_label('', font_size=FS_CAP, markup=True,
                                      size_hint_y=None, height=line_h(FS_CAP, 2))
        body.add_widget(self.lbl_milestone)

        # --- 本国下载量 ---
        # ⚠️ 三个数字（大数 120 + 占比 ~104 + 每周期 ~108）合计 332 > 可用 292，
        #    硬塞一行必然互相压字。改为两行：
        #        第一行  84.7M                +2.91M/周期
        #        第二行  占全球 0.7%
        self.lbl_sec_downloads = self._section_label(i18n.t('insp_downloads'))
        body.add_widget(self.lbl_sec_downloads)
        dlrow = BoxLayout(orientation='vertical', spacing=2, size_hint_y=None,
                          height=line_h(22) + 2 + line_h(FS_CAP))
        self._dlrow = dlrow
        dl_top = FloatLayout(size_hint_y=None, height=line_h(22))
        self.lbl_dl_big = mk_label('--', font_size=22, color=COLORS['pink'],
                                   size_hint=(None, None),
                                   size=(120, line_h(22)),
                                   pos_hint={'x': 0, 'center_y': 0.5})
        self.lbl_dl_rate = mk_label('', font_size=FS_CAP, color=COLORS['green'],
                                    halign='right', size_hint=(None, None),
                                    size=(170, line_h(FS_CAP)),
                                    pos_hint={'right': 1, 'center_y': 0.5})
        dl_top.add_widget(self.lbl_dl_big)
        dl_top.add_widget(self.lbl_dl_rate)
        self.lbl_dl_share = mk_label('', font_size=FS_CAP,
                                     color=COLORS['text_mute'],
                                     size_hint_y=None, height=line_h(FS_CAP))
        dlrow.add_widget(dl_top)
        dlrow.add_widget(self.lbl_dl_share)
        body.add_widget(dlrow)
        self.spark = Spark([], size_hint_y=None, height=26)
        body.add_widget(self.spark)

        # --- 政府状态键值表（KvGrid 自己按 FS_CAP 算行高，不再传魔数）---
        self.kv = KvGrid(['gov_status', 'doubt_thr', 'block_budget', 'neighbors'])
        body.add_widget(self.kv)

        # --- 阻止强度 ---
        # 内容高 = padding(2×5) + 间距(2×3) + blockbar(10) + lbl_block 行高
        #          + lbl_warn 行高（弹性，占剩余）  → 常量项合计 26
        # 高度交给 _sync_row_heights()：警告句在中文下要 3 行、英文 2 行，
        # 写死高度必然裁字。
        warn = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border_2'],
                           spacing=3, padding=(6, 5), size_hint_y=None,
                           height=line_h(FS_TINY) * 2 + 26)
        self._warn = warn
        self.lbl_warn = mk_label('', font_size=FS_TINY, color=COLORS['orange'],
                                 size_hint_y=None, height=line_h(FS_TINY))
        warn.add_widget(self.lbl_warn)
        self.blockbar = BlockBar(0.0, size_hint_y=None, height=10)
        warn.add_widget(self.blockbar)
        self.lbl_block = mk_label('', font_size=FS_TINY, color=COLORS['text_mute'],
                                  size_hint_y=None, height=line_h(FS_TINY))
        warn.add_widget(self.lbl_block)
        body.add_widget(warn)

        # --- 底栏动作 ---
        self._make_divider()
        ft = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None,
                       height=line_h(FS_CAP) + 12, padding=(8, 6))
        self._ft = ft
        ft.add_widget(Widget())
        self.btn_focus = self._small_btn(i18n.t('insp_focus'), 'plain',
                                         lambda: self._on_focus and self._on_focus(self._code))
        self.btn_drop = self._small_btn(i18n.t('insp_drop'), 'primary',
                                        lambda: self._on_drop and self._on_drop(self._code))
        ft.add_widget(self.btn_focus)
        ft.add_widget(self.btn_drop)
        self.add_widget(ft)
        fit_footer(1.0, ft, (self.btn_focus, self.btn_drop))

    # ---- 小工具 ----
    def _make_divider(self) -> None:
        self.add_widget(hline())

    @staticmethod
    def _section_label(text: str) -> PixelLabel:
        return mk_label(text, font_size=FS_CAP, color=COLORS['text_mute'],
                        size_hint_y=None, height=line_h(FS_CAP))

    @staticmethod
    def _small_btn(text: str, tone: str, cb: Callable) -> Button:
        """页脚小按钮：宽度交给 ``fit_footer`` 按**真实字形宽**算。

        ⚠️ 旧实现只给 ``size_hint_y=None``，横向 size_hint 是默认的 (1,1) →
        按钮参与 BoxLayout 均分。检视卡页脚 3 个弹性子控件均分 312px，每枚只有
        104px，而 '⊕ 向该国投放技能' 真实要 145px、'⊕ Drop skill here' 要
        143px —— 两种语言下「投放」按钮文字都溢出自己的盒子，与相邻控件叠在
        一起（用户报告的「文字被遮挡」）。现在必须是定宽（size_hint_x=None）。
        """
        b = Button(text=text, font_size=FS_CAP, size_hint=(None, None),
                   height=line_h(FS_CAP), background_normal='')
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
        self._fit_labels()

    # ---- 自适应行高 ----
    def _fit_labels(self) -> None:
        """把长句标签的高度调成它**当前文本真实需要**的高度。

        检视卡里好几段是「固定句式 + 动态数字」，中英长度差一大截
        （英文 'Suspicion / threshold' 比中文宽 70%，警告句中文 3 行、英文 2 行），
        写死 height 必然在某种语言下裁字。这里只约束宽度、放开高度量出真实
        排版高度再回写 —— body 是 ScrollView，长高了只是多滚一点，绝不裁。

        只在文本真变了时重量，避免同一周期重复 texture_update。
        """
        for attr, wid in self.FIT_WIDTH.items():
            lbl = getattr(self, attr, None)
            if lbl is None:
                continue
            key = (lbl.text, wid)
            if self._fit_cache.get(attr) == key:
                continue
            self._fit_cache[attr] = key
            lbl.text_size = (wid, None)      # 高度放开 → 量出换行后的真实高
            lbl.texture_update()
            need = lbl.texture_size[1]
            if need > 0:
                need = max(need, line_h(lbl.font_size))
                self._fit_need[attr] = need
                lbl.height = need
        self._sync_row_heights()

    def _sync_row_heights(self) -> None:
        """行容器高度跟着**量出来的需要值**走。

        ⚠️ 不能用 `容器高 = 子标签当前高 + 余量`：lbl_name 在 FloatLayout 里
        size_hint=(1,1)，高度由容器反推 —— 那样每次 update 都会 +6px 无限长高。
        必须用 _fit_need 里记的「文本真实需要高」。
        """
        name_need = self._fit_need.get('lbl_name', self.lbl_name.height)
        self._idrow.height = max(name_need + 6, self.flag.height + 6)
        self._dlrow.height = self.lbl_dl_share.height + 2 + line_h(22)
        self._warn.height = (self.lbl_warn.height + self.lbl_block.height
                             + self.blockbar.height + 16)

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

    def refresh_lang(self) -> None:
        """语言切换后重查所有**静态**文案。

        本面板被 PagesMixin 缓存在 ``self._inspector`` 并挂在 map_stage 上，
        语言切换走的是整页 ``rebuild()``（只重建根节点，不动 map_stage），
        所以这些「构造时查表一次」的标签会残留旧语种 —— 必须显式重查。
        动态文案（国名/百分比/警告句）走 ``update()``，此处不碰。
        """
        self.lbl_hd.text = i18n.t('insp_title')
        self.lbl_sec_infection.text = i18n.t('insp_infection')
        self.lbl_sec_downloads.text = i18n.t('insp_downloads')
        self.btn_focus.text = i18n.t('insp_focus')
        self.btn_drop.text = i18n.t('insp_drop')
        self.kv.refresh_lang()
        # 换了语种 → 按钮文字宽变 → 重新贴合；行高缓存作废待 update() 重量
        fit_footer(getattr(self, '_scale', 1.0), self._ft,
                   (self.btn_focus, self.btn_drop))
        self._fit_cache.clear()

    def refresh_scale(self, scale: float) -> None:
        self._scale = scale
        self.width = self.WIDTH * scale
        # ⚠️ 正文可用宽跟着面板缩，自适应的「测量基准宽」必须同步 —— 否则仍按
        #    292px 量出的行数 ≠ 实际在更窄宽度下排出的行数，矮的那份高度就会裁字。
        self.FIT_WIDTH = {k: max(v * scale, 50.0)
                          for k, v in self._FIT_W_BASE.items()}
        self._fit_cache.clear()
        fit_footer(scale, self._ft, (self.btn_focus, self.btn_drop))


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
        self.lbl_hd.padding = [8, 0, 0, 0]      # 四元组！padding_x 会左右同时生效
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

        # row_h 用 KvGrid 默认值（按 FS_CAP 的实际行高算）。以前写死 17px，
        # 而 FS_CAP=18.4 的一行字要 24px → 每行文字上下都被裁。
        self.kv = KvGrid(['targets', 'cost', 'remain'])
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
        self._ft = ft
        ft.add_widget(Widget())
        self.btn_cancel = InspectorPanel._small_btn(i18n.t('drop_cancel'), 'plain',
                                                    self._cancel)
        ft.add_widget(self.btn_cancel)
        self.btn_ok = InspectorPanel._small_btn(i18n.t('drop_confirm'), 'primary',
                                                self._confirm)
        ft.add_widget(self.btn_ok)
        self.add_widget(ft)
        fit_footer(1.0, ft, (self.btn_cancel, self.btn_ok))

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

    def refresh_lang(self) -> None:
        """语言切换后重查静态文案（本面板缓存在 ``_drop_preview`` 上）。

        ``lbl_hd`` 的动态部分（标题 + 技能名）由 ``update()`` 重写，此处只管
        静态小标题与按钮；KvGrid 左列键名交给它自己的 ``refresh_lang()``。
        """
        self.lbl_est_hd.text = i18n.t('drop_est')
        self.btn_cancel.text = i18n.t('drop_cancel')
        self.btn_ok.text = i18n.t('drop_confirm')
        self.kv.refresh_lang()
        fit_footer(getattr(self, '_scale', 1.0), self._ft,
                   (self.btn_cancel, self.btn_ok))

    def refresh_scale(self, scale: float) -> None:
        self._scale = scale
        self.width = self.WIDTH * scale
        fit_footer(scale, self._ft, (self.btn_cancel, self.btn_ok))

class LogDrawer(StrokePanel):
    """右侧事件日志抽屉（设计稿 S14，宽 340px）。"""

    WIDTH = 340

    def __init__(self, on_close: Callable = None, on_clear: Callable = None,
                 on_export: Callable = None, **kwargs):
        kwargs.setdefault('size_hint', (None, 1))
        kwargs.setdefault('width', self.WIDTH)
        super().__init__(bg=COLORS['panel'], border=COLORS['border_2'],
                         spacing=0, padding=0, **kwargs)
        # 标题栏两行：第一行「标题 | 未读芯片 | 关闭」，第二行「只保留最近 N 条」。
        # ⚠️ 旧版是 FloatLayout + 三个控件都锚 right:1 —— 未读芯片与关闭按钮互相
        #    重叠，「0 未读」的尾巴被关闭按钮盖掉（截图实证，中英皆然）。
        #    改用横向 BoxLayout 顺序排布，芯片宽度由 PxChip 自己贴合文字。
        # ⚠️ 说明原先挤在页脚同一行：抽屉总宽 340，实测中文需求 348px / 英文
        #    408px > 可用 316px → 按钮压字、说明被挤没。挪到第二行后说明独占整行。
        hd = BoxLayout(orientation='vertical', spacing=0, size_hint_y=None,
                       height=line_h(FS_SM) + line_h(FS_TINY))
        self._hd = hd
        top = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None,
                        height=line_h(FS_SM))
        self._hd_top = top
        self.lbl_hd = mk_label(i18n.t('log_title'), font_size=FS_SM,
                               color=COLORS['cyan'])
        self.lbl_hd.padding = [8, 0, 0, 0]      # 四元组！padding_x 会左右同时生效
        self.chip_unread = PxChip('', tone='sys', height=18)
        self.btn_x = PxChip(U.SYM['close'], tone='plain', height=20,
                            on_press=lambda *_: on_close and on_close())
        top.add_widget(self.lbl_hd)             # 默认 size_hint → 吃掉剩余宽
        top.add_widget(self.chip_unread)
        top.add_widget(self.btn_x)
        hd.add_widget(top)
        self.lbl_note = mk_label(i18n.t('log_limit'), font_size=FS_TINY,
                                 color=COLORS['text_mute'],
                                 size_hint_y=None, height=line_h(FS_TINY))
        self.lbl_note.padding = [8, 0, 0, 0]
        hd.add_widget(self.lbl_note)
        self.add_widget(hd)

        self.scroll = ScrollView(bar_width=4)
        self.box = BoxLayout(orientation='vertical', spacing=3, size_hint_y=None,
                             padding=(6, 6))
        self.box.bind(minimum_height=self.box.setter('height'))
        self.scroll.add_widget(self.box)
        self.add_widget(self.scroll)

        # 页脚：只放两枚动作按钮，宽度由 fit_footer 按**真实字形宽**算
        # （small_btn 的 len*14+20 估算对英文高估 ~60%、对中文反而低估 ~10%）。
        ft = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None,
                       height=line_h(FS_SM) + 12, padding=(8, 6))
        self._ft = ft
        ft.add_widget(Widget())
        self.btn_export = small_btn(i18n.t('log_export'), 'plain',
                                    lambda: on_export and on_export())
        self.btn_read_all = small_btn(i18n.t('log_read_all'), 'plain',
                                      lambda: on_clear and on_clear())
        ft.add_widget(self.btn_export)
        ft.add_widget(self.btn_read_all)
        self.add_widget(ft)
        fit_footer(1.0, ft, (self.btn_export, self.btn_read_all), min_w_base=56)

    def refresh_lang(self) -> None:
        """语言切换后重查静态文案。

        抽屉被缓存在 ``_log_drawer`` 上并挂在 map_stage，语言切换只重建
        带页码的页面 → 不显式重查，标题/页脚会停在旧语种。
        """
        self.lbl_hd.text = i18n.t('log_title')
        self.lbl_note.text = i18n.t('log_limit')
        self.btn_export.text = i18n.t('log_export')
        self.btn_read_all.text = i18n.t('log_read_all')
        fit_footer(getattr(self, '_scale', 1.0), self._ft,
                   (self.btn_export, self.btn_read_all), min_w_base=56)

    def refresh_scale(self, scale: float) -> None:
        self._scale = scale
        self.width = self.WIDTH * scale
        # 标题栏两行跟着缩：说明文字是「整行宽度」约束，面板缩而字不缩会在窄挡折行，
        # 折出来的第二行塞不进 line_h(FS_TINY) 的盒高 → 被裁（实测 ×0.68 英文差 1px）。
        s_sm, s_tiny = FS_SM * scale, FS_TINY * scale
        self.lbl_hd.font_size = s_sm
        self._hd_top.height = line_h(s_sm)
        self.lbl_note.font_size = s_tiny
        self.lbl_note.height = line_h(s_tiny)
        self._hd.height = line_h(s_sm) + line_h(s_tiny)
        fit_footer(scale, self._ft, (self.btn_export, self.btn_read_all),
                   min_w_base=56)

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
