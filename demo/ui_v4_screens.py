"""
ui_v4_screens.py - AI 别闹 v0.4 对局内全屏页 + 家族统一入口

2026-09-13 拆分（2327 行 → 6 个模块）：
    ui_v4_common.py  —— UiStats / small_btn（公共底座）
    ui_v4_panels.py  —— InspectorPanel / DropPreview / LogDrawer
    ui_v4_cards.py   —— SkillPageCard / SlotRow / LinkBar / LvRow / BranchCard
    ui_v4_canvas.py  —— TechNode / TechCanvas
    ui_v4_syspages.py—— HelpPage / SettingsPage / OriginPage
    ui_v4_screens.py —— SkillPage / TechPage / AchPage（本文件保留）

本文件同时**转发**上述全部符号，外部仍可只 `import ui_v4_screens as S`
拿到所有组件，历史调用点（main.py / ui_*.py / 测试）零改动。

留在本地的对局页：
    SkillPage —— S05 技能页
    TechPage  —— S06 科技树页
    AchPage   —— S10 成就面板

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

# ============================================================
# 兼容性转发：拆分前的符号全部可继续从本模块取（外部调用点零改动）
# ============================================================
from ui_v4_common import UiStats, small_btn                     # noqa: F401
from ui_v4_panels import InspectorPanel, DropPreview, LogDrawer  # noqa: F401
from ui_v4_cards import (SkillPageCard, SlotRow, LinkBar,        # noqa: F401
                         LvRow, BranchCard)
from ui_v4_canvas import TechNode, TechCanvas                    # noqa: F401
from ui_v4_syspages import (HelpPage, SettingsPage,              # noqa: F401
                            SaveSlotRowSlot, OriginCard,
                            OriginPage, _ORIGIN_DIFF_TONE)

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

        # T11：技能扩容 6→10 后固定 3×2 网格会抛 GridLayoutException
        #（"Too many children"）。改为 3 列 + 行数按技能总数动态计算
        #（3 列 10 张 = 4 行），并在 ensure_cards 里补足行数 ——
        # 以后再扩技能只需改 SKILL_ORDER，不用回来改这里。
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
        """按技能 id 列表懒建卡片（数量固定，只建一次）。

        T11：卡片总数超过初始 3×2 时自动补行（10 张 → 4 行），
        避免 GridLayoutException("Too many children")。
        """
        # 先按最终卡片数把行数撑够（向上取整），再建卡
        want = len(set(skill_ids) | set(self.cards))
        if want > self._grid.cols * self._grid.rows:
            self._grid.rows = -(-want // self._grid.cols)   # 向上取整
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
          新版一屏看全 24 个节点；当前6个大类平行，类内分支从 T0 扇出。
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
        sfx.play('tech')                  # 点击科技树节点的个性化音效
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
