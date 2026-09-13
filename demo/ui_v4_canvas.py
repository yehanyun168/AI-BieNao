"""
ui_v4_canvas.py - S06 科技树全屏节点网络图（v0.5 重做，参考《瘟疫公司》）

2026-09-13 从 ui_v4_screens.py 拆出。这是本家族里**唯一带自绘坐标系**的
模块：整幅图在一个逻辑画布（CANVAS_W × CANVAS_H）里排布，绘制时统一乘
scale + 偏移，从而「等比缩放铺满可用区、节点不变形」。

内容：
    TechNode   —— 纯数据节点（不继承 Widget，带命中矩形）
    TechCanvas —— FloatLayout 自绘画布（节点/连线/等级点/选中框）
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

        !️ ``size_hint`` 必须关掉 ``(None, None)``：mk_label 默认 (1,1)，
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

        !️ 坐标系真相（已用像素级实验确认）：
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

        !️ 坐标系真相（已用 ``to_window`` + 像素级实验双重确认）：
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
