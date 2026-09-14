"""
ui_v4.py - AI 别闹 v0.4 交互界面组件库

对应设计稿：design/ui_design_v0.4.html（14 屏）
本模块只放**原子组件**（可用在任何屏上），屏幕级组装见 ui_v4_screens.py。

单一数据源纪律：
    颜色一律从 pixel_ui.COLORS / 本文件的地图四态常量取，
    不在这里硬编码新的十六进制值 —— 设计稿改令牌时只需改一处。

像素风纪律（与设计稿 § 一致）：
    光栅 2px / 节奏 8px / 线宽 1·2·3px / 圆角恒 0 /
    硬投影 6px 6px 0 / 字号下限 11px / 交互尺寸下限 44px。

!️ Kivy 坑（项目记忆）：canvas.before/after 全部在**父容器坐标系**绘制，
   所以自绘背景一律用 self.pos / self.size（它们是父坐标系下的绝对坐标），
   绝不能写局部坐标 (0,0)。
"""
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from kivy.graphics import Color, Line, Rectangle
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from pixel_ui import (COLORS, PixelLabel, add_pixel_border, hex_rgba,
                      snap, snap_pt)


# ============================================================
# 设计令牌（与 design/ui_design_v0.4.html 的 :root 一一对应）
# ============================================================
# 地图四态 —— 与 world_map.STATE_FILL / STATE_EDGE 同源（这里只读复用）
ST_FILL: Dict[str, str] = {'on': '#1f6f63', 'sel': '#4ec9b0',
                           'blk': '#5c2323', 'lk': '#232a30'}
ST_EDGE: Dict[str, str] = {'on': '#3ec9ac', 'sel': '#eafffb',
                           'blk': '#ef4444', 'lk': '#4a5560'}
# SegBar 空槽底（设计稿 #1b2129，介于 panel #161b22 与 panel_2 #1f2630 之间的
# 槽位灰）。P2-5 收口：原先以 RGBA 元组内联在 SegBar._redraw 的 canvas 里，
# 现提为令牌常量（值不变，只改来源）—— 空槽色全项目只此一处定义。
RGBA_SLOT_EMPTY = (0.106, 0.129, 0.161, 1)   # = #1b2129

# 字体阶梯（设计稿 --fs-*）
#
# ⚠️ 用户反馈「除开始界面外所有文字太小看不清」→ 在 v0.4 原阶梯（28/22/18/15、
# 13/12/11）基础上整体放大 ~1.5×：正文 13→20、说明 12→17、小字 11→16。
# 这是全项目字号的**单一来源**，改这里即可全局生效（调用点都引用常量）。
#
# v0.5 用户再次反馈「按钮文字要再大些、要清晰可读」→ 引入 FS_SCALE 统一放大，
# 无需逐处改字号。所有字号常量都走这个系数。
FS_SCALE = 1.15                       # 全局字号系数（1.0 = v0.4 基准）

BASE_DISPLAY, BASE_H1, BASE_H2, BASE_H3 = 44, 34, 28, 24
BASE_BODY, BASE_SM, BASE_CAP = 20, 17, 16
BASE_TINY = 14
# min 只用于极小的装饰字（徽标/角标）；交互与正文用 FS_CAP 起步


def _fs(v: float) -> int:
    """基准字号 → 实际字号（统一乘全局系数，取整到 2px 像素栅格）。

    !️ 必须返回 **int**：Kivy 的 markup ``[size=…]`` 只接受整数，
    传 float 会在渲染时抛 ``ValueError: invalid literal for int()``。
    """
    return int(round(float(v) * FS_SCALE / 2.0) * 2)


FS_DISPLAY, FS_H1, FS_H2, FS_H3 = (_fs(BASE_DISPLAY), _fs(BASE_H1),
                                   _fs(BASE_H2), _fs(BASE_H3))
FS_BODY, FS_SM, FS_CAP = _fs(BASE_BODY), _fs(BASE_SM), _fs(BASE_CAP)
FS_TINY = _fs(BASE_TINY)

# 节奏令牌（设计稿 --s1..--s12；S2 有默认参数使用，S1/S3/S4/S6 供 __all__ 导出）
S1, S2, S3, S4, S6 = 4, 8, 12, 16, 24

# 交互尺寸下限（无障碍：触控/鼠标都够用）
MIN_TOUCH = 44


# ------------------------------------------------------------
# 字形符号表 —— 只用 MicrosoftYaHei 真正含有的字符
# ------------------------------------------------------------
# ⚠️ 踩坑：``▶ ⏸ ▦ ⌗ ✖ ✕ ✓ ✗`` 在 MicrosoftYaHei 里**没有字形**，
# 运行时会渲染成「豆腐块」（□）。实测这些码位的 ``getbbox`` 全等于
# ``(0, 8, 17, 26)``（.notdef 的特征值）。而 ``■ □ ● ○ ▲ ▼ ◆ ◇ ★ ☆ ≡
# ※ ← → ↑ ↓ · — … × ÷ ≥ ≤`` 都有真实字形。
#
# 新增图标前请先跑 ``demo/_check_glyphs.py`` 核验；本表是图标符号的单一来源。
SYM: Dict[str, str] = {
    'play': '■',          # 运行/继续（■ 缺失）→ 实心方块
    'pause': '‖',         # 暂停（‖ 缺失）
    'drop': '⊕',          # 投放
    'tech': '◆',          # 科技（◆ 缺失）→ 菱形
    'skills': '◇',        # 技能（▦ 缺失）→ 空心菱形
    'log': '≡',           # 日志
    'ach': '★',           # 成就（★ emoji 在 kivy 里也不稳）
    'help': '?',          # 帮助
    'close': '×',         # 关闭（× 缺失）→ 乘号
    'minus': '－',        # 缩小
    'plus': '＋',         # 放大
    'lock': '□',          # 未解锁等级点
    'done': '■',          # 已解锁等级点
    'a11y_on': '●',       # 色盲辅助四态形状
    'a11y_sel': '▲',
    'a11y_blk': '★',      # （× 缺失）
    'a11y_lk': '○',
}

# 兜底校验：命中豆腐块特征值的符号直接报错，避免再犯
_GLYPH_NOTDEF = {'▶', '⏸', '▦', '⌗', '✖', '✕', '✓', '✗', '⊞', '⊟', '☰', '⌂', '⌘'}
for _k, _v in SYM.items():
    if _v in _GLYPH_NOTDEF:
        raise ValueError(f"SYM['{_k}'] = {_v!r} 在 MicrosoftYaHei 中缺字形（会显示豆腐块）")


# ------------------------------------------------------------
# markup 内联色令牌 —— 让 ``[color=xxx]`` 也走单一来源
# ------------------------------------------------------------
# ⚠️ Kivy 的 markup 只认**十六进制字面量**（``[color=8b949e]``），不认令牌名。
# 过去代码里散落着 36 处硬编码 hex，改配色时要全局搜替换 —— 违反单一来源。
# 这里把「令牌名 → hex 字符串」集中定义一次，正文一律用 ``MK[name]`` 拼接。
#
# 用法：
#     f"[color={MK['dim']}]算力[/color] [b]{v}[/b]"
def _mk(name: str) -> str:
    """令牌名 → markup 用的十六进制串（不带 #）。"""
    r, g, b, _a = COLORS[name]
    return f"{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"


MK: Dict[str, str] = {
    'text': _mk('text'),
    'dim': _mk('text_dim'),          # #8b949e
    'mute': _mk('text_mute'),        # #8b9099（P1-5 提亮，bg/panel/panel_2 全 ≥4.5）
    'strong': _mk('border_strong'),  # #6e7681（对比度达标边框）
    'cyan': _mk('cyan'),
    'pink': _mk('pink'),
    'yellow': _mk('yellow'),
    'green': _mk('green'),
    'purple': _mk('purple'),
    'orange': _mk('orange'),
    'red': _mk('red'),
    'blue': _mk('blue'),
}
# 语义别名（正文里更易读）
MK['ok'] = MK['green']
MK['warn'] = MK['orange']
MK['bad'] = MK['red']
# 怀疑度三档 —— 与 main.refresh_all 的 s_color 同一套语义
MK['susp_low'] = '6df08e'    # 偏低（明亮的绿，与 palette green 区分，用于百分比）
MK['lock'] = '6e7681'        # 锁定/禁用文字（P1-5：#4b5563 对 bg 仅 2.50:1，低于图形 3:1 下限；
                             # 提亮到 #6e7681 = border_strong 同值，最差底 panel_2 也有 3.32:1）
# 地图四态强调色（与 ST_EDGE 同源，供正文里描述「青色=已渗透 / 红色=被封锁」）
MK['st_on'] = ST_EDGE['on'].lstrip('#')
MK['st_blk'] = ST_EDGE['blk'].lstrip('#')
MK['susp_mid'] = MK['warn']
MK['susp_high'] = MK['bad']


def rgba(name: str) -> Tuple[float, float, float, float]:
    """按令牌名取色（'cyan' / 'yellow' …）"""
    return COLORS[name]


def _bind_text_size(label: Label) -> Label:
    """让 Label 的 halign/valign 生效 —— Kivy 必须绑定 text_size 才行"""
    label.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
    return label


def fit_width(label: Label, pad: float = 0.0,
              min_w: float = 0.0, max_w: Optional[float] = None) -> Label:
    """让 ``size_hint_x=None`` 的 Label 宽度**恰好贴合**文字（单行不换行）。

    !️!️ 绝对不要写 ``label.bind(texture_size=lambda i, v: setattr(i, 'width',
    v[0] + pad))`` —— 这是**正反馈回环**，会把标签撑到几千像素宽：

        宽度变 → ``_bind_text_size`` 把 text_size 设成「宽×高」
              → Kivy 按该宽度重排、算 texture
              → 中文无空格断行点 + markup 标签计入纹理宽度
              → texture_size[0] 反而变大（≈ 整段文本不换行时的宽度）
              → width 被赋成 texture_size[0]+pad → 回到第一步，永不收敛

    实测：一行 ``[color=8b949e]算力[/color]  [b]100[/b]`` 的 Label 被撑到
    **3844px**。主界面顶栏 14 个控件的固定宽合计 28744px ≫ 可用 2134px，
    BoxLayout 于是把最右侧控件全部推到 x=28859（屏幕外）—— 这就是
    「右上角那一行文字溢出容器 / chip 集体消失」的真正根因。

    正确做法：先把 ``text_size`` 的宽度解除约束（置 0）→ Kivy 按**单行不换行**
    量出真实文本宽度 ``texture_size[0]`` → 据此设定 width；``text`` 变化时重算。

    Args:
        label: 目标 Label（本函数会强制 ``size_hint_x=None``）。
        pad: 文字两侧留白（总宽 = 文字宽 + pad）。
        min_w: 宽度下限。
        max_w: 宽度上限；超出则允许换行并把 text_size 收到该宽度。
    """
    label.size_hint_x = None

    def _measure(*_a) -> None:
        # 1) 解除两轴约束：``text_size=(None, None)`` 时 Kivy 不做自动换行，
        #    ``texture_size`` 即这段文字的**单行真实宽高**。
        #    ⚠️ 不能用 ``text_size=(0, None)`` —— Kivy 会把它当「宽度 0」竖排，
        #    量出 17×138 这种荒谬值（这是上一版实现失败的原因）。
        label.text_size = (None, None)
        label.texture_update()
        nat_w, nat_h = float(label.texture_size[0]), float(label.texture_size[1])
        w = max(nat_w + pad, float(min_w))
        if max_w is not None and w > float(max_w):
            w = float(max_w)
        if abs(label.width - w) > 0.5:
            label.width = w              # ← 会触发 _bind_text_size(size→text_size)
        # 2) 再显式回写 text_size：宽度贴着文字（留出 pad），高度跟随控件自身，
        #    这样 halign/valign 才生效。必须在 width 之后写，否则被 size 绑定覆盖。
        inner = max(w - pad, 1)
        label.text_size = (inner, label.height if label.height > 1 else None)
        # 3) 若因 max_w 触发换行导致高度不够，把自然高度交回给调用方扩容
        if label.texture_size[1] > nat_h + 0.5:
            label.height = float(label.texture_size[1]) + 2

    label.bind(text=_measure)
    # 字号变化（F12 缩放 / refresh_scale）后必须重测，否则宽度与文字不匹配
    label._fit_width_measure = _measure
    Clock.schedule_once(_measure, 0)     # 首帧尺寸未定，布局后再量一次
    _measure()
    return label


def mk_label(text: str = '', font_size: float = FS_BODY, color=None,
             halign: str = 'left', valign: str = 'middle',
             markup: bool = False, **kwargs) -> PixelLabel:
    """构造一个像素风 Label（自动绑定 text_size）"""
    lbl = PixelLabel(
        text=text, font_size=font_size, markup=markup,
        halign=halign, valign=valign,
        color=color if color is not None else COLORS['text'],
        **kwargs,
    )
    _bind_text_size(lbl)
    return lbl


# ============================================================
# 通用面板底（2px 硬边框 + 深色底）
# ============================================================
class _Bordered:
    """给任意 Widget 混入一个「硬边框 + 底色」背景绘制能力。

    子类调用 ``_init_border(bg, border, shadow)`` 即可；
    之后改色用 ``set_border(bg=…, border=…)``。
    """

    def _init_border(self, bg=None, border=None, shadow: bool = False) -> None:
        self._bg_rgba = list(bg if bg else COLORS['panel'])
        self._bd_rgba = list(border if border else COLORS['border_2'])
        self._shadow = shadow
        self._bg_rect = None
        self._bd_line = None
        self.bind(pos=self._redraw_border, size=self._redraw_border)
        self._redraw_border()

    def set_border(self, bg=None, border=None) -> None:
        """运行时改色（不重建 widget 树）"""
        if bg is not None:
            self._bg_rgba = list(bg)
        if border is not None:
            self._bd_rgba = list(border)
        self._redraw_border()

    def _redraw_border(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 1 or h < 1:
            return
        with self.canvas.before:
            if self._shadow:
                # 设计稿 --shadow：硬投影 6px 6px 0（偏移处只画一条暗带）
                Color(0, 0, 0, 0.5)
                self._sh_rect = Rectangle(pos=(x + 6, y - 6), size=(w, h))
                Color(*self._bg_rgba)
                self._sh_cover = Rectangle(pos=(x, y), size=(w, h))
            else:
                Color(*self._bg_rgba)
                self._sh_rect = None
                self._sh_cover = None
                self._bg_rect = Rectangle(pos=(x, y), size=(w, h))
            Color(*self._bd_rgba)
            self._bd_line = Line(
                points=[x, y, x + w, y, x + w, y + h, x, y + h], close=True, width=2)


class StrokePanel(BoxLayout, _Bordered):
    """竖排容器 + 硬边框底（最常用的面板外壳）"""

    def __init__(self, bg=None, border=None, spacing: int = S2,
                 padding: int | Sequence[int] = S2, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        super().__init__(spacing=spacing, padding=padding, **kwargs)
        # 属性顺序：_Bordered 的 __init__ 不存在（纯 mixin），直接初始化
        self._init_border(bg=bg, border=border, shadow=False)


# ============================================================
# PxChip —— 效果芯片（设计稿 .chip：6 种语气）
# ============================================================
CHIP_TONES: Dict[str, Tuple[str, str]] = {
    # tone -> (边框/文字色, 底色)    底色统一取 panel_2，只有语气色变
    'up':    ('green', 'panel_2'),
    'dn':    ('red', 'panel_2'),
    'cost':  ('yellow', 'panel_2'),
    'lock':  ('text_mute', 'panel_2'),
    'sys':   ('purple', 'panel_2'),
    'plain': ('text_dim', 'panel_2'),
    'on':    ('cyan', 'sel'),
}


class PxChip(PixelLabel):
    """小徽章 / 效果芯片 —— 宽度随文字自适应（设计稿 .chip）。

    Args:
        text: 文案。
        tone: 语气 —— up/dn/cost/lock/sys/plain/on，决定边框与文字色。
        font_size: 字号（默认 11，设计稿 --fs-cap）。
        height: 固定高度（默认 20）。
    """

    PAD_X = 8
    BASE_H = 26          # 20 → 26：芯片内文字升到 FS_CAP(16)，高度要留够

    def __init__(self, text: str = '', tone: str = 'plain', font_size: float = FS_CAP,
                 height: float = None, on_press: Callable = None, **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('halign', 'center')
        kwargs.setdefault('valign', 'middle')
        super().__init__(text=text, font_size=font_size, **kwargs)
        self.tone = tone
        self._fs = font_size
        self._h = height or self.BASE_H
        self._on_press = on_press
        self._syncing = False
        self._apply_tone()
        # 2026-09-14：PxChip 之前在进局后陷入 Clock 过度迭代根因：
        # `texture_size` → `_resize` 是正反馈链——
        #   _resize 改 size/text_size → texture_update 调度
        #   → texture_size 变 → _resize 又跑 → 至少 3 次 texture_update/次，
        #   单帧 12 个 chip 把主循环顶死（HEAD 也复现，pre-existing 严重 bug）。
        # 修法：debounce——所有「可能触发 _resize」的信号（texture_size/size/pos）
        # 汇到一个 Clock.create_trigger 上，每帧最多合并为一次 _resize。
        # _syncing 旗只防同步重入（_resize 内部多次属性写），debounce 防异步循环。
        from kivy.clock import Clock as _KClock
        self._trigger_resize = _KClock.create_trigger(self._resize, 0)
        self.bind(pos=self._on_pos_size, size=self._on_pos_size,
                  texture_size=self._trigger_resize, text=self._trigger_resize)
        self._trigger_resize()

    def _on_pos_size(self, *_args) -> None:
        """pos/size 改变只触发 _redraw（绘制跟随），不必重测量。
        _resize 仅在 pos/size 外部赋值后真需要时才调，由 _trigger_resize 兜底。"""
        self._redraw()

    def _apply_tone(self) -> None:
        fg_name, bg_name = CHIP_TONES.get(self.tone, CHIP_TONES['plain'])
        self.color = COLORS[fg_name]
        self._edge = list(COLORS[fg_name])
        self._bg = (0.055, 0.169, 0.157, 1) if bg_name == 'sel' else list(COLORS['panel_2'])

    def set_tone(self, tone: str, text: Optional[str] = None) -> None:
        self.tone = tone
        if text is not None:
            self.text = text
        self._apply_tone()
        self._resize()

    def set_text(self, text: str) -> None:
        self.text = text

    def _resize(self, *_args) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            # ⚠️ 必须先把 text_size 解除约束再量：若沿用上一轮的 text_size，
            # Kivy 会按那个宽度换行，量出的宽度永远是旧值 → 芯片宽度卡死不变
            # （顶栏 chip 集体塌成 26px 就是这个原因）。
            self.text_size = (None, None)
            self.texture_update()
            w = max(float(self.texture_size[0]) + self.PAD_X * 2, 26)
            if abs(self.width - w) > 0.5 or abs(self.height - self._h) > 0.5:
                self.size = (w, self._h)
            self.text_size = (max(w - self.PAD_X * 2, 1), self._h)
        finally:
            self._syncing = False
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 1 or h < 1:
            return
        with self.canvas.before:
            Color(*self._bg)
            Rectangle(pos=(x, y), size=(w, h))
            Color(*self._edge)
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                 close=True, width=1)

    def refresh_scale(self, scale: float) -> None:
        """F12 自适应：字号随窗口缩放，重新计算宽度"""
        self.font_size = self._fs * scale
        self._h = self.BASE_H * scale
        self._resize()

    def on_touch_down(self, touch):
        if self._on_press and self.collide_point(*touch.pos):
            self._on_press(self)
            return True
        return super().on_touch_down(touch)


class ChipRow(FloatLayout):
    """芯片行 —— 自动横向排列，超宽换行（设计稿 .chips）。

    Args:
        chips: ``[(文本, 语气), …]``
        gap: 芯片间距。
    """

    def __init__(self, chips: Sequence[Tuple[str, str]] = (), gap: int = 4,
                 height: float = 20, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        super().__init__(**kwargs)
        self._gap = gap
        self.height = height
        self._items: List[PxChip] = []
        for text, tone in chips:
            c = PxChip(text=text, tone=tone)
            self.add_widget(c)
            self._items.append(c)
        self.bind(pos=self._layout_chips, size=self._layout_chips)

    def set_chips(self, chips: Sequence[Tuple[str, str]]) -> None:
        """重建芯片（数量也会变，所以直接重建更简单可靠）"""
        for c in self._items:
            self.remove_widget(c)
        self._items = []
        for text, tone in chips:
            c = PxChip(text=text, tone=tone)
            self.add_widget(c)
            self._items.append(c)
        self._layout_chips()

    def _layout_chips(self, *_args) -> None:
        x = self.x
        y = self.y
        for c in self._items:
            if x + c.width > self.x + self.width and x > self.x:
                return  # 放不下就截断（设计稿也是单行 flex-wrap，这里保守处理）
            c.pos = (x, y)
            x += c.width + self._gap

    def refresh_scale(self, scale: float) -> None:
        for c in self._items:
            c.refresh_scale(scale)
        self._layout_chips()


# ============================================================
# SegBar —— 分段进度条（设计稿 .segbar）
# ============================================================
class SegBar(Widget):
    """分段条形进度 —— 用「格数」做非颜色编码（无障碍要点）。

    Args:
        segments: 段数（设计稿用 12 段表示 0–100%）。
        filled: 已填充段数（float，内部四舍五入）。
        threshold: 阈值位置 0–1；不在范围内则不画黄线。
        highlight: 需要换成亮青色的段索引集合。
        fill_hex / hi_hex: 覆盖填充色（图层图例用）。
        show_frame: 是否画外框（图例变体不需要）。
    """

    def __init__(self, segments: int = 12, filled: float = 0.0,
                 threshold: Optional[float] = None,
                 highlight: Optional[Sequence[int]] = None,
                 fill_hex: Optional[str] = None, hi_hex: Optional[str] = None,
                 show_frame: bool = True, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        super().__init__(**kwargs)
        self.segments = max(int(segments), 1)
        self.filled = filled
        self.threshold = threshold
        self.highlight = set(highlight or ())
        self.fill_hex = fill_hex or ST_FILL['on']
        self.hi_hex = hi_hex or ST_FILL['sel']
        self.show_frame = show_frame
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_value(self, filled: float, highlight: Optional[Sequence[int]] = None,
                  threshold: Optional[float] = None) -> None:
        self.filled = filled
        if highlight is not None:
            self.highlight = set(highlight)
        if threshold is not None:
            self.threshold = threshold
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 4:
            return
        n = self.segments
        pad = 1.0
        inner_x, inner_y = x + pad, y + pad
        inner_w, inner_h = w - pad * 2, h - pad * 2
        gap = 1.0
        seg_w = (inner_w - gap * (n - 1)) / n
        filled_n = int(round(self.filled))
        thr_idx = None
        if self.threshold is not None and 0.0 <= self.threshold <= 1.0:
            thr_idx = min(int(self.threshold * n), n - 1)

        with self.canvas.before:
            if self.show_frame:
                Color(*COLORS['border_2'])
                self._frame = Rectangle(pos=(x, y), size=(w, h))
            # 槽底
            Color(0.043, 0.063, 0.090, 1)
            Rectangle(pos=(inner_x, inner_y), size=(inner_w, inner_h))
            for i in range(n):
                sx = inner_x + i * (seg_w + gap)
                if i < filled_n:
                    Color(*hex_rgba(self.hi_hex if i in self.highlight
                                    else self.fill_hex))
                else:
                    Color(*RGBA_SLOT_EMPTY)     # 空槽（令牌见文件头设计令牌区）
                Rectangle(pos=(sx, inner_y), size=(seg_w, inner_h))
            # 阈值黄线（设计稿 inset 2px 左描边）
            if thr_idx is not None and thr_idx > 0:
                Color(*COLORS['yellow'])
                Line(points=[inner_x + thr_idx * (seg_w + gap), inner_y,
                             inner_x + thr_idx * (seg_w + gap), inner_y + inner_h],
                     width=2)


# ============================================================
# Spark —— 像素趋势柱（设计稿 .spark / .spark2）
# ============================================================
class Spark(Widget):
    """近 N 周期的像素柱状趋势。

    Args:
        values: 0–1 的数值列表（长度即柱数）。
        highlight_last: 最后一根是否换亮色。
        fill_hex: 柱色覆盖（图层/技能页变体）。
        show_mid: 是否画一条 50% 基准线（便于判断柱子"算高算矮"）。

    玩家反馈 #2：只画柱子不给基准，玩家无法判断高度含义。这里补一条
    50% 虚线基准 + 保持末柱高亮（表示"当前值"），让趋势可读。
    """

    def __init__(self, values: Sequence[float] = (), highlight_last: bool = True,
                 fill_hex: Optional[str] = None, show_mid: bool = True, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        super().__init__(**kwargs)
        self.values = list(values)
        self.highlight_last = highlight_last
        self.fill_hex = fill_hex or ST_FILL['on']
        self.show_mid = show_mid
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_values(self, values: Sequence[float]) -> None:
        self.values = list(values)
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 4 or not self.values:
            return
        # P2-2 整数吸附：1.5× DPI / 均分布局会给半像素坐标（如 h=14 时
        # 基准线落在 +7.5），不吸附的 1px 线和柱子会被 GPU 采样糊掉。
        # 只吸附落笔坐标，不改 widget 布局本身。
        x, y, w, h = snap(x), snap(y), snap(w), snap(h)
        n = len(self.values)
        gap = 1                                    # 间隙恒 1px（整数栅格）
        bar_w = max((w - gap * (n - 1)) // n, 1)   # 整数柱宽，余数并入右端空隙
        with self.canvas.before:
            # 底轴（设计稿 border-bottom 1px）
            Color(*COLORS['border'])
            Line(points=[x, y, x + w, y], width=1)
            # 50% 基准线（玩家反馈 #2：给个参照，才知道柱子高矮）
            if self.show_mid and h >= 10:
                Color(*COLORS['border_2'])
                my = y + 1 + (h - 1) // 2          # 整数行，替代旧的 .5 半像素
                Line(points=[x, my, x + w, my], width=1)
            for i, v in enumerate(self.values):
                vv = min(max(float(v), 0.0), 1.0)
                bh = max(int(round(vv * (h - 1))), 1)
                if i == n - 1 and self.highlight_last:
                    Color(*hex_rgba(ST_FILL['sel']))
                else:
                    Color(*hex_rgba(self.fill_hex))
                # x/y/w/bar_w 已是整数 → 柱位/柱高天然落格
                Rectangle(pos=(x + i * (bar_w + gap), y + 1), size=(bar_w, bh))


# ============================================================
# BlockBar —— 阻止强度条（设计稿 .blockbar）
# ============================================================
class BlockBar(Widget):
    """阻止强度条：红条按比例推进。"""

    def __init__(self, ratio: float = 0.0, bar_hex: Optional[str] = None, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        super().__init__(**kwargs)
        self.ratio = ratio
        self.bar_hex = bar_hex or ST_EDGE['blk']
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_ratio(self, ratio: float) -> None:
        self.ratio = ratio
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 2:
            return
        r = min(max(float(self.ratio), 0.0), 1.0)
        with self.canvas.before:
            Color(0.043, 0.063, 0.090, 1)
            Rectangle(pos=(x, y), size=(w, h))
            if r > 0:
                Color(*hex_rgba(self.bar_hex))
                Rectangle(pos=(x, y), size=(w * r, h))
            Color(*COLORS['border_2'])
            self._frame = Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                               close=True, width=1)


# ============================================================
# Steps —— 三步状态机（设计稿 .steps）
# ============================================================
class Steps(Widget):
    """横向步骤条：已完成为绿、当前为青、未到为静音。

    Args:
        labels: 步骤文案列表。
        current: 当前步骤下标（0 基）；之前为 done。
    """

    def __init__(self, labels: Sequence[str] = (), current: int = 0, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        super().__init__(**kwargs)
        self.labels = list(labels)
        self.current = current
        self.height = 24
        self._cells: List[PixelLabel] = []
        self.bind(pos=self._rebuild_text, size=self._rebuild_text)
        self._sync_labels()

    def set_current(self, idx: int) -> None:
        self.current = idx
        self._sync_labels()

    def set_labels(self, labels: Sequence[str]) -> None:
        """替换步骤文案（语言切换时用）。"""
        self.labels = list(labels)
        self._sync_labels()

    def _sync_labels(self) -> None:
        while len(self._cells) < len(self.labels):
            lbl = PixelLabel(font_size=FS_CAP, halign='center', valign='middle',
                             markup=True, size_hint=(None, None))
            self.add_widget(lbl)
            self._cells.append(lbl)
        for i, lbl in enumerate(self._cells):
            if i < len(self.labels):
                lbl.opacity = 1
                lbl.text = f"[b]{i + 1}[/b] {self.labels[i]}"
            else:
                lbl.opacity = 0
        self._rebuild_text()

    def _rebuild_text(self, *_args) -> None:
        x, y = self.pos
        w, h = self.size
        if not self._cells or w < 4:
            return
        n = len(self.labels)
        cw = w / n
        for i, lbl in enumerate(self._cells):
            if i >= n:
                continue
            sx = x + i * cw
            lbl.pos = (sx, y)
            lbl.size = (cw, h)
            lbl.text_size = (cw, h)
            if i < self.current:
                lbl.color = COLORS['green']
            elif i == self.current:
                lbl.color = COLORS['cyan']
            else:
                lbl.color = COLORS['text_mute']
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 4:
            return
        n = len(self.labels)
        cw = w / n
        with self.canvas.before:
            for i in range(n):
                sx = x + i * cw
                if i == self.current:
                    bg, bd = (0.055, 0.169, 0.157, 1), COLORS['cyan']
                elif i < self.current:
                    bg, bd = list(COLORS['panel_2']), COLORS['green']
                else:
                    bg, bd = list(COLORS['panel_2']), COLORS['border_2']
                Color(*bg)
                Rectangle(pos=(sx, y), size=(cw, h))
                Color(*bd)
                Line(points=[sx, y, sx + cw, y, sx + cw, y + h, sx, y + h],
                     close=True, width=2)


# ============================================================
# Reticle / TgtLabel —— 投放准星与目标标签（设计稿 .reticle）
# ============================================================
class Reticle(Widget):
    """十字准星（纯装饰，不吃触摸）。"""

    def __init__(self, size_px: float = 66, color_name: str = 'yellow', **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('size', (size_px, size_px))
        super().__init__(**kwargs)
        self._color = color_name
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 4:
            return
        c = COLORS[self._color]
        with self.canvas.before:
            Color(*c)
            # 竖线
            Line(points=[x + w / 2, y, x + w / 2, y + h], width=2)
            # 横线
            Line(points=[x, y + h / 2, x + w, y + h / 2], width=2)

    def on_touch_down(self, touch):
        return False          # 准星永远不吃触摸


class TgtLabel(PixelLabel):
    """目标标签（设计稿 .tgt-label：黄底黄框）。"""

    def __init__(self, text: str = '', tone: str = 'ok', **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('halign', 'center')
        kwargs.setdefault('valign', 'middle')
        super().__init__(text=text, font_size=FS_CAP, **kwargs)
        self._tone = tone
        self._syncing = False
        self._apply_tone()
        self.bind(pos=self._redraw, size=self._redraw, texture_size=self._resize)
        self._resize()

    TONES = {'ok': ('yellow', (0.227, 0.196, 0.118, 1)),
             'bad': ('red', (0.227, 0.137, 0.137, 1))}

    def _apply_tone(self) -> None:
        name, bg = self.TONES.get(self._tone, self.TONES['ok'])
        self.color = COLORS[name]
        self._edge = list(COLORS[name])
        self._bg = list(bg)

    def set_state(self, text: str, tone: str = 'ok') -> None:
        self.text = text
        self._tone = tone
        self._apply_tone()
        self._resize()

    def _resize(self, *_args) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            w = self.texture_size[0] + 12
            h = 18
            if abs(self.width - w) > 0.5:
                self.size = (w, h)
            self.text_size = (w - 12, h)
        finally:
            self._syncing = False
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 4:
            return
        with self.canvas.before:
            Color(*self._bg)
            Rectangle(pos=(x, y), size=(w, h))
            Color(*self._edge)
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                 close=True, width=2)


# ============================================================
# RailButton —— 右侧指令栏按钮（设计稿 .rail button，44×44）
# ============================================================
class RailButton(Button):
    """指令栏按钮：图标 + 小字，触控尺寸 44px 达标。

    Args:
        icon: 图标字符。
        label: 小字说明（无则只显示图标）。
        badge: 右上角未读角标数字（0 = 不显示）。
    """

    BASE = 44

    def __init__(self, icon: str = '', label: str = '', badge: int = 0,
                 on_click: Callable = None, **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('size', (self.BASE, self.BASE))
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0.051, 0.067, 0.090, 0.9)
        self.color = COLORS['text_dim']
        self.markup = True
        self._icon = icon
        # ⚠️ 绝不能叫 self._label —— Kivy 的 Button 继承自 Label，
        #    _label 是它内部持有的 CoreLabel 实例，覆盖成字符串会让
        #    text 的 texture 更新直接崩（AttributeError: 'str' has no 'text'）。
        self._caption = label
        self._badge = badge
        self._active = False
        self._scale = 1.0
        self._edge = list(COLORS['border_2'])
        self.bind(pos=self._redraw_frame, size=self._redraw_frame)
        self._sync_text()
        self._redraw_frame()
        if on_click:
            self.bind(on_release=lambda *_: on_click(self))

    def _sync_text(self) -> None:
        s = self._scale
        if self._caption:
            self.text = (f"[size={int(FS_H3 * s)}]{self._icon}[/size]\n"
                         f"[size={int(FS_TINY * s)}]{self._caption}[/size]")
        else:
            self.text = f"[size={int(FS_H2 * s)}]{self._icon}[/size]"
        if self._badge > 0:
            self.text += (f" [color={MK['red']}]"
                          f"[size={int(FS_TINY * s)}]"
                          f"{self._badge}[/size][/color]")

    def _redraw_frame(self, *_args) -> None:
        """自绘 2px 硬边框。

        不用 add_pixel_border —— 那个 helper 每次调用都会新增一条 Color 指令
        并重复 bind，切选中态时会导致 canvas 指令泄漏。
        """
        self.canvas.after.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 4:
            return
        with self.canvas.after:
            Color(*self._edge)
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                 close=True, width=2)

    def set_badge(self, n: int) -> None:
        if n != self._badge:
            self._badge = n
            self._sync_text()

    def set_active(self, active: bool) -> None:
        """选中态（设计稿 .rail button.on）"""
        self._active = active
        if active:
            self.background_color = (0.055, 0.169, 0.157, 1)
            self.color = COLORS['cyan']
            self._edge = list(COLORS['cyan'])
        else:
            self.background_color = (0.051, 0.067, 0.090, 0.9)
            self.color = COLORS['text_dim']
            self._edge = list(COLORS['border_2'])
        self._redraw_frame()

    def refresh_scale(self, scale: float) -> None:
        self._scale = scale
        self.size = (self.BASE * scale, self.BASE * scale)
        self._sync_text()


# ============================================================
# RegionTab / SegSwitch —— 区域页签 & 分段切换（设计稿 .region / .segsw）
# ============================================================
class RegionTab(PxChip):
    """区域页签：默认静音，选中描青边（设计稿 .region.on）。"""

    def __init__(self, text: str = '', on_click: Callable = None, **kwargs):
        # ⚠️ _active/_n 必须在 super().__init__ 之前设好：
        #    PxChip.__init__ 会立刻调用 self._apply_tone()，而子类重写的
        #    _apply_tone 会读这两个字段。
        self._active = False
        self._n = ''
        super().__init__(text=text, tone='plain', on_press=on_click, **kwargs)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_tone()
        self._redraw()

    def _apply_tone(self) -> None:
        if self._active:
            self.color = COLORS['cyan']
            self._edge = list(COLORS['cyan'])
            self._bg = [0.055, 0.169, 0.157, 1]
        else:
            self.color = COLORS['text_dim']
            self._edge = list(COLORS['border_2'])
            self._bg = list(COLORS['panel_2'])

    def set_text_parts(self, name: str, count: int) -> None:
        """名字用主色、计数用静音色（设计稿 .region .n）"""
        self._n = str(count)
        self.text = f"{name} {count}"


class SegSwitch(FloatLayout):
    """分段切换器（设计稿 .segsw）：相邻格共享边框。

    Args:
        options: 选项文案。
        current: 当前下标。
        on_change: ``fn(idx)``。
    """

    BASE_H = 22

    def __init__(self, options: Sequence[str] = (), current: int = 0,
                 on_change: Callable = None, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        super().__init__(**kwargs)
        self.height = self.BASE_H
        self.options = list(options)
        self.current = current
        self._on_change = on_change
        self._cells: List[PixelLabel] = []
        for i, _opt in enumerate(self.options):
            lbl = PixelLabel(font_size=FS_CAP, halign='center', valign='middle',
                             size_hint=(None, None), markup=True)
            self.add_widget(lbl)
            self._cells.append(lbl)
        self.bind(pos=self._layout_cells, size=self._layout_cells)
        self._sync()

    def set_options(self, options: Sequence[str]) -> None:
        for c in self._cells:
            self.remove_widget(c)
        self._cells = []
        self.options = list(options)
        for _opt in self.options:
            lbl = PixelLabel(font_size=FS_CAP, halign='center', valign='middle',
                             size_hint=(None, None), markup=True)
            self.add_widget(lbl)
            self._cells.append(lbl)
        self._sync()

    def set_current(self, idx: int, notify: bool = False) -> None:
        self.current = idx
        self._sync()
        if notify and self._on_change:
            self._on_change(idx)

    def _sync(self) -> None:
        for i, lbl in enumerate(self._cells):
            if i < len(self.options):
                lbl.text = self.options[i]
                lbl.opacity = 1
                lbl.color = COLORS['cyan'] if i == self.current else COLORS['text_dim']
            else:
                lbl.opacity = 0
        self._layout_cells()

    def _layout_cells(self, *_args) -> None:
        x, y = self.pos
        w, h = self.size
        if not self._cells or w < 4:
            return
        n = len(self.options)
        cw = w / n
        for i, lbl in enumerate(self._cells):
            if i >= n:
                continue
            lbl.pos = (x + i * cw, y)
            lbl.size = (cw, h)
            lbl.text_size = (cw, h)
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 4:
            return
        n = len(self.options)
        cw = w / n
        with self.canvas.before:
            for i in range(n):
                sx = x + i * cw
                on = (i == self.current)
                Color(*((0.055, 0.169, 0.157, 1) if on else COLORS['panel_2']))
                Rectangle(pos=(sx, y), size=(cw, h))
                Color(*(COLORS['cyan'] if on else COLORS['border_2']))
                Line(points=[sx, y, sx + cw, y, sx + cw, y + h, sx, y + h],
                     close=True, width=2)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            n = len(self.options)
            cw = self.width / n if n else 0
            if cw > 0:
                idx = min(int((touch.x - self.x) // cw), n - 1)
                self.set_current(idx, notify=True)
                return True
        return super().on_touch_down(touch)


# ============================================================
# LegendChip —— 图例项（设计稿 .legend）
# ============================================================
class LegendChip(FloatLayout):
    """色块 + 文案（用于地图四态图例）。"""

    def __init__(self, fill_hex: str, edge_hex: str, text: str = '',
                 swatch: int = 9, **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('size', (100, 16))
        super().__init__(**kwargs)
        self._fill = fill_hex
        self._edge = edge_hex
        self._swatch = swatch
        self._shape = ''
        # 色盲辅助：色块上叠一个高对比形状符号（○●▲✖），让四态不单靠颜色区分；
        # A11Y_SHAPES 开启时由 LegendBar.set_shape 触发显示。
        # P1-5：字形盒比 9px 色块大一圈（原 text_size=(9,9) 会把 ○▲★ 裁成残块，
        # 实测 ▲ 自然纹理 18×24 只剩中心 9×9），字号也随色块走而不是 FS_CAP。
        self.shape_lbl = mk_label('', font_size=max(swatch + 5, 11),
                                  color=(1, 1, 1, 1),
                                  halign='center', valign='center',
                                  size_hint=(None, None),
                                  size=(swatch + 8, swatch + 8))
        self.shape_lbl.opacity = 0.0
        self.add_widget(self.shape_lbl)
        self.label = mk_label(text, font_size=FS_CAP, color=COLORS['text_mute'])
        self.add_widget(self.label)
        self.bind(pos=self._layout, size=self._layout)
        self._layout()

    def _layout(self, *_args) -> None:
        s = self._swatch
        sy = self.y + (self.height - s) / 2.0
        # 形状符号盒以色块中心居中（允许溢出色块边界 —— Label 本身透明，
        # 溢出部分落在图例行高内，视觉上仍是「色块上的形状」）
        g = s + 8
        self.shape_lbl.pos = (self.x + s / 2.0 - g / 2.0, sy + s / 2.0 - g / 2.0)
        self.shape_lbl.size = (g, g)
        self.label.pos = (self.x + s + 5, self.y)
        self.label.size = (max(self.width - s - 5, 1), self.height)
        self._redraw()

    def set_text(self, text: str) -> None:
        self.label.text = text

    def set_colors(self, fill_hex: str, edge_hex: str) -> None:
        self._fill, self._edge = fill_hex, edge_hex
        self._redraw()

    def set_shape(self, glyph: str) -> None:
        """色盲辅助：设置色块上的形状符号（空串 = 不显示）。"""
        self._shape = glyph or ''
        self.shape_lbl.text = self._shape
        self.shape_lbl.opacity = 1.0 if self._shape else 0.0
        self._sync_glyph_color()   # 形状显示与字形颜色必须同步决定

    def _sync_glyph_color(self) -> None:
        """P1-5：形状符号颜色跟随色块明度 —— 深块白字、浅块深字。

        原来恒用白色，热力 100% 档（#9ff0da 之类浅色块）上白字形不可见，
        形状机制等于失效。按 WCAG 对比度挑更高的一边。
        """
        if not self._shape:
            return
        fr, fg, fb, _a = hex_rgba(self._fill)

        def _lin(v: float) -> float:
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        lum = 0.2126 * _lin(fr) + 0.7152 * _lin(fg) + 0.0722 * _lin(fb)
        white_vs = 1.05 / (lum + 0.05)          # vs 纯白
        dark_vs = (lum + 0.05) / 0.0555         # vs 深底 #0d1117（L≈0.0055）
        self.shape_lbl.color = ((1, 1, 1, 1) if white_vs >= dark_vs
                                else (0.051, 0.067, 0.090, 1))

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 4:
            return
        s = self._swatch
        sy = y + (h - s) / 2
        self._sync_glyph_color()
        with self.canvas.before:
            Color(*hex_rgba(self._fill))
            Rectangle(pos=(x, sy), size=(s, s))
            Color(*hex_rgba(self._edge))
            Line(points=[x, sy, x + s, sy, x + s, sy + s, x, sy + s],
                 close=True, width=2)


# ============================================================
# KvGrid —— 键值表（设计稿 .kv：左静音右对齐）
# ============================================================
class KvGrid(GridLayout):
    """两列键值表：左列静音、右列主色右对齐。

    Args:
        rows: 键名列表；值用 ``set_value(key, text)`` 更新。
    """

    def __init__(self, rows: Sequence[str] = (), row_h: int = 17, **kwargs):
        super().__init__(cols=2, spacing=2, size_hint_y=None, **kwargs)
        self.row_h = row_h
        self._values: Dict[str, PixelLabel] = {}
        for key in rows:
            k = mk_label(key, font_size=FS_CAP, color=COLORS['text_dim'],
                         size_hint_y=None, height=row_h)
            v = mk_label('--', font_size=FS_CAP, color=COLORS['text'],
                         halign='right', markup=True, size_hint_y=None, height=row_h)
            self.add_widget(k)
            self.add_widget(v)
            self._values[key] = v
        self.bind(minimum_height=self.setter('height'))

    def set_value(self, key: str, text: str) -> None:
        lbl = self._values.get(key)
        if lbl is not None:
            lbl.text = text

    def refresh_scale(self, scale: float) -> None:
        self.row_h = 17 * scale
        for child in self.children:
            child.height = self.row_h
            child.font_size = FS_CAP * scale


# ============================================================
# SkillBarCard —— 底部技能带的一张卡（设计稿 .skill）
# ============================================================
class SkillBarCard(Widget):
    """技能带卡：键位 + 名字 + 消耗 + 效果 + 冷却遮罩 + 目标标记。

    Args:
        code: 技能 id。
        key_hint: 键位字符（'1'…'6'）。
        name: 技能名。
        effect: 效果简述。
        cost: 算力消耗。
    """

    def __init__(self, code: str, key_hint: str = '', name: str = '',
                 effect: str = '', cost: float = 0, on_click: Callable = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.code = code
        self._on_click = on_click
        self.state = 'ready'          # ready / cd / no_compute / sel
        self.cd_ratio = 0.0
        self.cd_left = 0
        self.selected = False
        self.scale = 1.0

        self.lbl_key = mk_label(key_hint, font_size=FS_CAP, color=COLORS['yellow'],
                                size_hint=(None, None))
        self.lbl_name = mk_label(name, font_size=FS_CAP, color=COLORS['text'])
        self.lbl_cost = mk_label(str(int(cost)) if cost else '0',
                                 font_size=FS_CAP, color=COLORS['text_dim'],
                                 halign='right', size_hint=(None, None))
        # ⚠️ 效果说明 / 状态行用 FS_TINY：此前误用 FS_CAP(16px)，而 _layout 只给
        # FS_TINY*1.35≈15px 的行高 → 字形上下被裁（玩家看到"半截字/像错别字"，
        # 例：'楚' 裁后视觉上像别的字），且长说明换行后必然溢出裁切。
        self.lbl_fx = mk_label(effect, font_size=FS_TINY, color=COLORS['text_mute'])
        self.lbl_state = mk_label('', font_size=FS_TINY, color=COLORS['text_dim'],
                                  halign='right', size_hint=(None, None))
        for w in (self.lbl_key, self.lbl_name, self.lbl_cost,
                  self.lbl_fx, self.lbl_state):
            self.add_widget(w)

        self.bind(pos=self._layout, size=self._layout)
        self._layout()

    # ---- 状态 ----
    def set_state(self, state: str, cd_left: int = 0, cd_ratio: float = 0.0,
                  state_text: str = '') -> None:
        self.state = state
        self.cd_left = cd_left
        self.cd_ratio = cd_ratio
        self.lbl_state.text = state_text
        # 未解锁：整体置灰（设计稿问题 #4：开局不要 6 技能全开）
        self.opacity = 0.5 if state == 'lock' else 1.0
        self._layout()

    def set_selected(self, sel: bool) -> None:
        self.selected = sel
        self._layout()

    def set_texts(self, name: str = None, effect: str = None) -> None:
        if name is not None:
            self.lbl_name.text = name
        if effect is not None:
            self.lbl_fx.text = effect
        self._layout()

    # ---- 布局 ----
    def refresh_scale(self, scale: float) -> None:
        """F12 自适应：技能卡内部字号与间距随全局缩放走。"""
        self.scale = scale
        # 效果/状态行与主行不同字号族（FS_TINY），与 __init__ 保持一致
        self.lbl_key.font_size = FS_CAP * scale
        self.lbl_name.font_size = FS_CAP * scale
        self.lbl_cost.font_size = FS_CAP * scale
        self.lbl_fx.font_size = FS_TINY * scale
        self.lbl_state.font_size = FS_TINY * scale
        self._layout()

    def _layout(self, *_args) -> None:
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        s = self.scale
        pad = 8 * s
        # 行高由字号决定（1.35× 行距），不再写死 15px —— 字号放大后
        # 写死行高会把文字挤成两行/被裁切。
        row_h = FS_CAP * 1.35 * s
        top = y + h - pad
        # 顶行：键位 + 名称 + 消耗。名称宽度由「消耗左边界 − 名称左边界」
        # 反推，任何卡宽下都与消耗框严格不相交（旧公式 `w - kw - 46` 在
        # 窄卡上会让名称框伸进消耗区，视觉上文字相互遮挡）。
        self.lbl_key.pos = (x + pad, top - row_h)
        self.lbl_key.size = (FS_CAP * 1.1 * s, row_h)
        self.lbl_key.text_size = self.lbl_key.size
        kw = max(self.lbl_key.width, 10)
        fs_w = FS_CAP * 2.6 * s               # 消耗数字宽（按 4 位数字预估）
        cost_left = x + w - pad - fs_w
        name_left = x + pad + kw + 4 * s
        self.lbl_name.pos = (name_left, top - row_h)
        self.lbl_name.size = (max(cost_left - name_left - 4 * s, 1), row_h)
        self.lbl_name.text_size = self.lbl_name.size
        self.lbl_cost.pos = (cost_left, top - row_h)
        self.lbl_cost.size = (fs_w, row_h)
        self.lbl_cost.text_size = (fs_w, row_h)
        # 底行：状态（1 行 FS_TINY）
        small_h = FS_TINY * 1.35 * s
        self.lbl_state.pos = (x + pad, y + pad)
        self.lbl_state.size = (max(w - pad * 2, 1), small_h)
        self.lbl_state.text_size = self.lbl_state.size
        # 中部：效果说明。吃掉顶行与状态行之间的全部剩余空间（约 2 行
        # FS_TINY），文字在此区内自动换行，既不裁字也不与上下行重叠。
        fx_top = top - row_h - 4 * s
        fx_bottom = y + pad + small_h + 4 * s
        fx_h = max(fx_top - fx_bottom, small_h)
        self.lbl_fx.pos = (x + pad, fx_bottom)
        self.lbl_fx.size = (max(w - pad * 2, 1), fx_h)
        self.lbl_fx.text_size = self.lbl_fx.size
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        self.canvas.after.clear()
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        # 底色 / 边框
        bg = list(COLORS['panel_2'])
        bd = list(COLORS['border_2'])
        if self.state == 'no_compute':
            bg = [0.15, 0.10, 0.12, 1]
            bd = list(COLORS['red'])
        elif self.state == 'cd':
            bg = [0.086, 0.106, 0.133, 1]
        if self.selected:
            bd = list(COLORS['cyan'])
            bg = [0.118, 0.227, 0.227, 1]
        elif self.state == 'ready':
            bd = list(COLORS['cyan'])
        with self.canvas.before:
            Color(*bg)
            Rectangle(pos=(x, y), size=(w, h))
            Color(*bd)
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                 close=True, width=2)
            # 冷却遮罩（设计稿 .skill.cd .mask：自底部覆盖）
            if self.state == 'cd' and self.cd_ratio > 0:
                Color(0, 0, 0, 0.35)
                Rectangle(pos=(x, y), size=(w, h * self.cd_ratio))
        # 目标标记（设计稿 .skill .tgt：顶部 3px 黄条）
        if self.selected:
            with self.canvas.after:
                Color(*COLORS['yellow'])
                Rectangle(pos=(x, y + h - 3), size=(w, 3))

    def on_touch_down(self, touch):
        if self._on_click and self.collide_point(*touch.pos):
            self._on_click(self.code)
            return True
        return super().on_touch_down(touch)


# ============================================================
# OptButton —— 事件/危机的可选项（设计稿 .opt，4 类状态）
# ============================================================
class OptButton(Widget):
    """事件选项：键位 + 标题 + 说明 + 效果 chips。

    Args:
        index: 键位数字（1 基）。
        title: 选项标题。
        note: 副说明。
        chips: 效果 chips ``[(文本, 语气), …]``。
        badge: 标题后的角标（如「推荐」）。
        danger: 高代价项（hover/按下描红边）。
        disabled: 科技门控项。
    """

    def __init__(self, index: int = 1, title: str = '', note: str = '',
                 chips: Sequence[Tuple[str, str]] = (), badge: str = '',
                 badge_tone: str = 'up', danger: bool = False,
                 disabled: bool = False, on_click: Callable = None, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        super().__init__(**kwargs)
        self.index = index
        self.danger = danger
        self.disabled = disabled
        self._on_click = on_click
        self._hover = False

        # 标题用 FS_BODY(13px) 而非 FS_SM(12px)：选项按钮是全屏弹窗的主要
        # 交互目标，字号偏小会「挤在一起看不清」，放大后更易读、更易点。
        self.lbl = mk_label('', font_size=FS_BODY, markup=True,
                            halign='left', valign='top')
        self.add_widget(self.lbl)
        self.chip_row = ChipRow(list(chips), height=18)
        self.add_widget(self.chip_row)

        head = f"[b]{index}[/b]  {title}"
        if badge:
            head += f"  [color={MK['susp_low']}]「{badge}」[/color]"
        if disabled:
            head = f"[color={MK['lock']}]{head}[/color]"
        body = head
        if note:
            body += f"\n[size={FS_CAP}][color={MK['mute']}]{note}[/color][/size]"
        self.lbl.text = body
        self._title = title
        self._note = note

        self.bind(pos=self._layout, size=self._layout)
        self._layout()

    @property
    def height_hint(self) -> float:
        """按内容算高度：标题行 + 说明行 + chips 行（全部随字号缩放）。

        用 FS_BODY/FS_CAP 推算行高，这样字号放大（20/16）后按钮自动变高，
        不会「字变大但按钮没变」导致文字溢出/被裁。
        """
        line = FS_BODY * 1.5                     # 标题行高
        pad_v = FS_BODY * 0.8                    # 上下内边距合计预留
        base = line + pad_v
        if self._note:
            base += FS_CAP * 1.5                 # 说明行
        if self.chip_row._items:
            base += FS_CAP * 1.5 + 6             # chips 行 + 间距
        return max(base, MIN_TOUCH + 12)         # 交互尺寸下限（高于 44px）

    def _layout(self, *_args) -> None:
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        pad = max(int(FS_BODY * 0.8), 10)      # 内边距随字号缩放
        chip_h = int(FS_CAP * 1.4) if self.chip_row._items else 0
        self.chip_row.pos = (x + pad, y + pad * 0.6)
        self.chip_row.size = (max(w - pad * 2, 1), chip_h)
        self.chip_row._layout_chips()
        self.lbl.pos = (x + pad, y + pad * 0.6 + chip_h + 4)
        self.lbl.size = (max(w - pad * 2, 1),
                         max(h - chip_h - pad * 1.2 - 6, 1))
        self.lbl.text_size = self.lbl.size
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        bg = list(COLORS['panel_2'])
        bd = list(COLORS['border_2'])
        if self.disabled:
            bg = [0.075, 0.086, 0.098, 1]
        elif self._hover:
            bd = list(COLORS['red'] if self.danger else COLORS['cyan'])
            bg = [0.165, 0.086, 0.086, 1] if self.danger else [0.118, 0.227, 0.227, 1]
        with self.canvas.before:
            Color(*bg)
            Rectangle(pos=(x, y), size=(w, h))
            Color(*bd)
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                 close=True, width=2)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.disabled:
                return True
            self._hover = True
            self._redraw()
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self._hover:
            self._hover = False
            self._redraw()
            if not self.disabled and self._on_click:
                self._on_click(self.index - 1)
            return True
        self._hover = False
        self._redraw()
        return super().on_touch_up(touch)

    def refresh_scale(self, scale: float) -> None:
        self.chip_row.refresh_scale(scale)
        # 标题字号随窗口缩放同步（下限 12px），否则大窗口下仍显得小
        self.lbl.font_size = max(FS_BODY * scale, 12)
        self._layout()


# ============================================================
# StatCell / StatsGrid —— 结局数据回顾 8 格（设计稿 .stats-grid）
# ============================================================
class StatCell(StrokePanel):
    """单格统计：上标签下数值。"""

    def __init__(self, key: str = '', value: str = '', value_color=None, **kwargs):
        super().__init__(bg=COLORS['panel_2'], border=COLORS['border'],
                         spacing=1, padding=(6, 4), **kwargs)
        self.size_hint_y = None
        self.height = 46
        self.lbl_k = mk_label(key, font_size=FS_CAP, color=COLORS['text_mute'],
                              size_hint_y=None, height=14)
        self.lbl_v = mk_label(value, font_size=FS_H3,
                              color=value_color or COLORS['text'],
                              size_hint_y=None, height=26)
        self.add_widget(self.lbl_k)
        self.add_widget(self.lbl_v)

    def set_value(self, value: str) -> None:
        self.lbl_v.text = value


class StatsGrid(GridLayout):
    """统计格网格（默认 4 列）。

    Args:
        cells: ``[(标签, 值, 颜色名或 None), …]``
    """

    def __init__(self, cells: Sequence[Tuple] = (), cols: int = 4, **kwargs):
        super().__init__(cols=cols, spacing=6, size_hint_y=None, **kwargs)
        self._cells: List[StatCell] = []
        for item in cells:
            key, val = item[0], item[1]
            cname = item[2] if len(item) > 2 else None
            cell = StatCell(key, val, COLORS[cname] if cname else None)
            self.add_widget(cell)
            self._cells.append(cell)
        rows = (len(self._cells) + cols - 1) // cols
        self.height = rows * 46 + max(rows - 1, 0) * 6


# ============================================================
# AchCell —— 成就格（设计稿 .ach）
# ============================================================
# ============================================================
# PixelSprite —— 字符位图像素画（页面装饰用美术元素，Bug5 新增）
# ============================================================
# 设计动机：成就页 / 设置页留白过多，除了放大控件还需要「个性化美术元素」。
# 这里提供一个极轻量的字符位图渲染器：不需要图片文件，直接用字符行 +
# 调色板画成 Rectangle 色块，风格与像素 UI 完全一致。
# ⚠️ 画在 canvas.before（父坐标），Kivy 的 self.pos 对 canvas 不透明，
#    必须显式加上（见科技树坐标系三雷）。

def draw_pixel_sprite(widget, rows: Sequence[str], palette: Dict[str, tuple],
                      scale: float) -> None:
    """把字符位图画到 widget 的 canvas.before 上。'.' 与未知字符 = 透明。"""
    with widget.canvas.before:
        n = len(rows)
        for ry, row in enumerate(rows):
            for rx, ch in enumerate(row):
                col = palette.get(ch)
                if col is None:
                    continue
                Color(*col)
                # 字符行第 0 行是「顶部」，Kivy y 轴向上 → 翻转行序
                Rectangle(pos=(widget.x + rx * scale,
                               widget.y + (n - 1 - ry) * scale),
                          size=(scale, scale))


class PixelSprite(Widget):
    """字符位图像素画装饰。

    Args:
        rows: 字符行列表（每行等宽，'.'=透明）。
        palette: 字符 → RGBA 元组。
        scale: 每格边长（px）。
    """

    def __init__(self, rows: Sequence[str], palette: Dict[str, tuple],
                 scale: float = 3, **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        super().__init__(**kwargs)
        self._rows = list(rows)
        self._pal = dict(palette)
        self._scale = scale
        self.width = max(len(r) for r in self._rows) * scale
        self.height = len(self._rows) * scale
        self.bind(pos=self._draw)
        self._draw()

    def _draw(self, *_args) -> None:
        self.canvas.before.clear()
        draw_pixel_sprite(self, self._rows, self._pal, self._scale)


# —— 内置精灵：奖杯（成就页）/ 齿轮（设置·显示）/ 机器人（设置·存档）——
SPR_TROPHY = (
    'oyyyyyyyyyyo',
    'oyywyyyyyyyo',
    '.oyyyyyyyyo.',
    '..oyyyyyyo..',
    '...oyyyyo...',
    '....oyyo....',
    '....oyyo....',
    '...oyyyyo...',
    '..oooooooo..',
    '.oooooooooo.',
    'oooooooooooo',
)
PAL_TROPHY = {'y': (0.914, 0.725, 0.290, 1),   # 金
              'o': (0.722, 0.525, 0.184, 1),   # 暗金描边
              'w': (0.980, 0.950, 0.840, 1)}   # 高光

SPR_GEAR = (
    '....gggg....',
    '.g..gggg..g.',
    '.gg.gggg.gg.',
    '..gggggggg..',
    'gggg....gggg',
    'ggggg..ggggg',
    'ggggg..ggggg',
    'gggg....gggg',
    '..gggggggg..',
    '.gg.gggg.gg.',
    '.g..gggg..g.',
    '....gggg....',
)
PAL_GEAR = {'g': (0.306, 0.788, 0.690, 1),     # 青
            '.': None}

SPR_ROBOT = (
    '.....yy.....',
    '....gggg....',
    '..gggggggg..',
    '..g.wwww.g..',
    '..g.wwww.g..',
    '..gggggggg..',
    '...gggggg...',
    '..gggggggg..',
    '..g.gggg.g..',
    '..g.gggg.g..',
    '....gggg....',
)
PAL_ROBOT = {'g': (0.306, 0.788, 0.690, 1),    # 青机身
             'w': (0.950, 0.970, 0.980, 1),    # 屏幕/眼
             'y': (0.914, 0.725, 0.290, 1)}    # 天线


class AchCell(Widget):
    """成就格：图标 + 名称 + 描述；已达成绿边、事件型紫边。

    Bug5 放大：高度 52→140，图标框 26→56，名称 FS_CAP→FS_SM，
    让 4 列网格铺满成就页 body（原来 5 行只占 ~1/3 屏，下方全是留白）。
    """

    ICON = 56
    PAD = 12

    def __init__(self, icon: str = '', name: str = '', desc: str = '',
                 got: bool = False, event_type: bool = False,
                 status_text: str = '', **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', 140)
        super().__init__(**kwargs)
        self.got = got
        self.event_type = event_type
        self._icon_text = icon
        self._status_text = status_text
        self.lbl_name = mk_label(name, font_size=FS_SM, color=COLORS['text'])
        self.lbl_desc = mk_label(desc, font_size=FS_CAP, color=COLORS['text_mute'],
                                 valign='top')
        self.add_widget(self.lbl_name)
        self.add_widget(self.lbl_desc)
        self.bind(pos=self._layout, size=self._layout)
        self._layout()

    def _layout(self, *_args) -> None:
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        p, icon = self.PAD, self.ICON
        # 名称：图标右侧，垂直与图标框居中
        self.lbl_name.pos = (x + p + icon + 10, y + h - p - icon + (icon - 30) / 2)
        self.lbl_name.size = (max(w - p * 2 - icon - 10, 1), 30)
        self.lbl_name.text_size = self.lbl_name.size
        # 描述：图标行下方 → 底部状态行上方，占满中层
        status_h = 22
        top = y + h - p - icon - 8
        bot = y + p + status_h + 8
        self.lbl_desc.pos = (x + p, bot)
        self.lbl_desc.size = (max(w - p * 2, 1), max(top - bot, 1))
        self.lbl_desc.text_size = self.lbl_desc.size
        self._redraw()
        # 状态行（Bug5：■ 已达成 / □ 进行中，填充单元格底部）
        if self._status_text:
            if not hasattr(self, '_status_lbl'):
                self._status_lbl = mk_label('', font_size=FS_TINY,
                                            markup=True,
                                            size_hint=(None, None))
                self.add_widget(self._status_lbl)
            sym = '■' if self.got else '□'
            col = MK['green'] if self.got else MK['mute']
            self._status_lbl.text = (f"[color={col}]{sym}[/color] "
                                     f"[color={MK['dim']}]{self._status_text}[/color]")
            self._status_lbl.pos = (x + p + 12, y + p + 8)
            self._status_lbl.size = (max(w - p * 2 - 12, 1), 20)
            self._status_lbl.text_size = self._status_lbl.size

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        p, icon = self.PAD, self.ICON
        bd = COLORS['green'] if self.got else (
            COLORS['purple'] if self.event_type else COLORS['border_2'])
        with self.canvas.before:
            Color(*COLORS['panel_2'])
            Rectangle(pos=(x, y), size=(w, h))
            Color(*bd)
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                 close=True, width=2)
            # 图标框（左上）
            ix, iy = x + p, y + h - p - icon
            Color(*COLORS['panel'])
            Rectangle(pos=(ix, iy), size=(icon, icon))
            Color(*(COLORS['green'] if self.got else COLORS['border_2']))
            Line(points=[ix, iy, ix + icon, iy, ix + icon, iy + icon, ix, iy + icon],
                 close=True, width=1)
            # 底部状态色条（Bug5：填充单元格下部，弱化空腔感）
            Color(*bd)
            Rectangle(pos=(x + p, y + p), size=(max(w - p * 2, 1), 6))
        if not hasattr(self, '_icon_lbl'):
            self._icon_lbl = mk_label(self._icon_text, font_size=FS_H3,
                                      halign='center', valign='middle',
                                      color=COLORS['green'] if self.got
                                      else COLORS['text_mute'],
                                      size_hint=(None, None))
            self.add_widget(self._icon_lbl)
        self._icon_lbl.pos = (ix, iy)
        self._icon_lbl.size = (icon, icon)
        self._icon_lbl.text_size = (icon, icon)
        self._icon_lbl.color = (COLORS['green'] if self.got else COLORS['text_mute'])


# ============================================================
# LogRow —— 事件日志行（设计稿 .logrow：左侧 3px 类型色条）
# ============================================================
LOG_TONE = {'i': 'cyan', 'w': 'orange', 'e': 'red', 'g': 'green'}


class LogRow(Widget):
    """日志行：左色条 + [周期] 文案。"""

    def __init__(self, text: str = '', tone: str = 'i', **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', 22)
        super().__init__(**kwargs)
        self.tone = tone
        self.lbl = mk_label(text, font_size=FS_CAP, color=COLORS['text_dim'])
        self.add_widget(self.lbl)
        self.bind(pos=self._layout, size=self._layout)
        self._layout()

    def _layout(self, *_args) -> None:
        self.lbl.pos = (self.x + 9, self.y)
        self.lbl.size = (max(self.width - 13, 1), self.height)
        self.lbl.text_size = self.lbl.size
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 4 or h < 4:
            return
        with self.canvas.before:
            Color(*COLORS['panel_2'])
            Rectangle(pos=(x, y), size=(w, h))
            Color(*COLORS[LOG_TONE.get(self.tone, 'cyan')])
            Rectangle(pos=(x, y), size=(3, h))


# ============================================================
# KeyBox —— 帮助页的快捷键分组（设计稿 .keybox）
# ============================================================
class KeyBox(StrokePanel):
    """快捷键分组框。

    Args:
        title: 分组标题。
        rows: ``[(键位, 说明), …]``
    """

    def __init__(self, title: str = '', rows: Sequence[Tuple[str, str]] = (), **kwargs):
        super().__init__(bg=COLORS['panel_2'], border=COLORS['border'],
                         spacing=3, padding=(8, 6), **kwargs)
        h = mk_label(title, font_size=FS_CAP, color=COLORS['purple'],
                     size_hint_y=None, height=18)
        self.add_widget(h)
        for key, desc in rows:
            self.add_widget(self._make_row(key, desc))

    @staticmethod
    def _make_row(key: str, desc: str) -> FloatLayout:
        row = FloatLayout(size_hint_y=None, height=18)
        kbd = PxChip(key, tone='plain', height=17)
        kbd.color = COLORS['yellow']
        kbd._edge = list(COLORS['border_2'])
        kbd._bg = list(COLORS['panel'])
        kbd._resize()
        kbd.pos_hint = {'x': 0, 'center_y': 0.5}
        lbl = mk_label(desc, font_size=FS_CAP, color=COLORS['text_dim'])
        lbl.pos_hint = {'x': 0, 'center_y': 0.5}
        row.add_widget(kbd)
        row.add_widget(lbl)
        row._kbd, row._lbl = kbd, lbl

        def _layout(*_a, r=row):
            k = r._kbd
            k.pos = (r.x, r.y + (r.height - k.height) / 2)
            r._lbl.pos = (r.x + k.width + 8, r.y)
            r._lbl.size = (max(r.width - k.width - 8, 1), r.height)
            r._lbl.text_size = r._lbl.size
        row.bind(pos=_layout, size=_layout)
        row._layout = _layout
        return row


# ============================================================
# SaveSlotRow —— 存档槽位行（设计稿 .slotrow）
# ============================================================
class SaveSlotRow(Widget):
    """存档槽：名称 + 摘要 + 右侧动作按钮。

    Args:
        title: 槽位名（如「槽位 01」）。
        summary: 摘要文案。
        actions: ``[(按钮文案, 语气, 回调), …]``
        active: 是否描青边（当前槽位）。
    """

    def __init__(self, title: str = '', summary: str = '',
                 actions: Sequence[Tuple] = (), active: bool = False, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', 60)      # Bug5: 34→60，按钮 52×24→78×34
        super().__init__(**kwargs)
        self._active = active
        self.lbl = mk_label('', font_size=FS_SM, markup=True)
        self.add_widget(self.lbl)
        self._set_text(title, summary)
        self._btns: List[Button] = []
        for text, tone, cb in actions:
            b = Button(text=text, font_size=FS_SM, size_hint=(None, None),
                       size=(78, 34), background_normal='', markup=True)
            b.background_color = list(COLORS['panel_2'])
            b.color = COLORS[{'primary': 'cyan', 'danger': 'red'}.get(tone, 'text')]
            if tone == 'primary':
                b.background_color = (0.078, 0.188, 0.173, 1)
            elif tone == 'danger':
                b.background_color = (0.227, 0.118, 0.118, 1)
            add_pixel_border(b, color=COLORS[{'primary': 'cyan',
                                              'danger': 'red'}.get(tone, 'border_2')])
            if cb:
                b.bind(on_release=lambda *_, f=cb: f())
            self.add_widget(b)
            self._btns.append(b)
        self.bind(pos=self._layout, size=self._layout)
        self._layout()

    def _set_text(self, title: str, summary: str) -> None:
        self.lbl.text = f"[b][color={MK['cyan']}]{title}[/color][/b]  {summary}"

    def _layout(self, *_args) -> None:
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        bw, bh, gap = 78, 34, 8
        total = len(self._btns) * bw + max(len(self._btns) - 1, 0) * gap
        bx = x + w - 10 - total
        for b in self._btns:
            b.pos = (bx, y + (h - bh) / 2)
            bx += bw + gap
        self.lbl.pos = (x + 10, y)
        self.lbl.size = (max(bx - x - 10 - gap - 10, 1), h)
        self.lbl.text_size = self.lbl.size
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 8 or h < 8:
            return
        with self.canvas.before:
            Color(*COLORS['panel'])
            Rectangle(pos=(x, y), size=(w, h))
            Color(*(COLORS['cyan'] if self._active else COLORS['border']))
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                 close=True, width=2 if self._active else 1)


# ============================================================
# PageScreen —— 全屏页外壳（设计稿 .page：44px header + body）
# ============================================================
class PageScreen(StrokePanel):
    """全屏页外壳：顶部 44px 工具头 + 内容区。

    用法：
        page = PageScreen(title='技能库 · SKILLS')
        page.add_header_btn('返回地图（Esc）', cb)
        page.body.add_widget(...)
        page.close_cb = fn
    """

    HEAD_H = 52          # 44 → 52：标题升到 FS_H3(24)，行高要留够

    def __init__(self, title: str = '', on_close: Callable = None, **kwargs):
        super().__init__(bg=COLORS['bg'], border=COLORS['border_2'],
                         spacing=0, padding=0, **kwargs)
        self.on_close = on_close
        self.header = BoxLayout(orientation='horizontal', spacing=10,
                                padding=(12, 8), size_hint_y=None,
                                height=self.HEAD_H)
        # 页面标题用 FS_H3(24)：全屏页的层级锚点，必须明显大于正文
        self.lbl_title = mk_label(title, font_size=FS_H3, color=COLORS['cyan'])
        fit_width(self.lbl_title, pad=12)
        self.header.add_widget(self.lbl_title)
        self.btn_back = Button(text='', font_size=FS_BODY, size_hint=(None, None),
                               size=(0, MIN_TOUCH), background_normal='')
        self.btn_back.background_color = list(COLORS['panel_2'])
        self.btn_back.color = COLORS['text']
        add_pixel_border(self.btn_back, color=COLORS['border_2'])
        self.btn_back.opacity = 0
        self.header.add_widget(self.btn_back)
        self.header.add_widget(Widget())          # spacer

        # 顶部右侧容器（排序 / 统计 / 动作）
        self.head_right = BoxLayout(orientation='horizontal', spacing=6,
                                    size_hint_x=None, width=0)
        self.header.add_widget(self.head_right)

        self.body = GridLayout(cols=1, spacing=8, padding=8, size_hint_y=1)
        self.add_widget(self.header)
        self.add_widget(self.body)

    def set_back_button(self, text: str, callback: Callable) -> None:
        self.btn_back.text = text
        self.btn_back.opacity = 1
        self.btn_back.size = (max(len(text) * FS_BODY * 0.72 + 20, 100),
                              MIN_TOUCH)
        self.btn_back.bind(on_release=lambda *_: callback())

    def add_head_widget(self, w: Widget) -> None:
        """往头部右侧加入控件。

        Label 需要显式宽度（父容器 size_hint_x=None），这里统一按文字宽度自适应，
        否则它会塌成 0 宽 —— 这是 Kivy 里最常见的「标签看不见」原因。
        """
        if isinstance(w, Label) and w.size_hint_x is not None:
            fit_width(w, pad=14, min_w=40)
        self.head_right.add_widget(w)
        self._sync_head_right()

    def _sync_head_right(self) -> None:
        kids = [c for c in self.head_right.children]
        total = sum(max(getattr(c, 'width', 0) or 0, 0) for c in kids)
        n = len(kids)
        self.head_right.width = total + max(n - 1, 0) * self.head_right.spacing

    def refresh_scale(self, scale: float) -> None:
        self.height_header = self.HEAD_H * scale
        self.header.height = self.HEAD_H * scale
        self.lbl_title.font_size = FS_H3 * scale
        self.btn_back.font_size = FS_BODY * scale
        self.btn_back.height = MIN_TOUCH * scale
        # 标题字号变了必须重测宽度，否则会裁字
        measure = getattr(self.lbl_title, '_fit_width_measure', None)
        if callable(measure):
            measure()


def hline() -> Widget:
    """1px 硬分割线 —— 弹窗 / 页面 / 设置项之间的视觉断点。

    2026-09-11 来自 ui_modal.L7 → ui_v4_screens.L5 的反向依赖修复：
    L5 屏组件不允许 import L7 弹窗层，把这个被 6 处共用的视觉小件
    下移到 L4（ui_v4 本就是视觉原语层，StrokePanel/Spark 等同类元素）。
    """
    d = Widget(size_hint_y=None, height=2)
    with d.canvas.before:
        Color(*COLORS['border'])
        d._r = Rectangle(pos=d.pos, size=d.size)
    d.bind(pos=lambda i, v: setattr(i._r, 'pos', v),
           size=lambda i, v: setattr(i._r, 'size', v))
    return d


__all__ = [
    'ST_FILL', 'ST_EDGE', 'FS_DISPLAY', 'FS_H1', 'FS_H2', 'FS_H3',
    'FS_BODY', 'FS_SM', 'FS_CAP', 'S1', 'S2', 'S3', 'S4', 'S6', 'MIN_TOUCH',
    'rgba', 'mk_label', 'fit_width',
    'StrokePanel', 'PxChip', 'ChipRow', 'SegBar', 'Spark',
    'BlockBar', 'Steps', 'Reticle', 'TgtLabel', 'RailButton', 'RegionTab',
    'SegSwitch', 'LegendChip', 'KvGrid', 'SkillBarCard', 'OptButton',
    'StatCell', 'StatsGrid', 'AchCell', 'LogRow', 'LOG_TONE', 'KeyBox',
    'SaveSlotRow', 'PageScreen', 'hline',
]
