"""
ui_hud.py - HUD 层（拆分自 main.py）

组件：CountdownBar / WorldMapWidget / HudBox / RailBar / LegendBar / LayerHud
常量：REGIONS / LAYER_* / 色阶表 / STATE_SHAPE / LANG_CHIP_TAG
混入：HudMixin —— GameUI 的布局（顶栏/地图舞台/技能带）、区域高亮、图层切换
"""
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from typing import Optional

from pixel_ui import PixelLabel as Label   # 关闭字体 hinting，保持像素锐利
from pixel_ui import add_pixel_border   # P2-5：hex_rgba 已随 '#0d1117' 收口移除
import i18n
from i18n import (t, get_lang, LANG_ZH, LANG_EN)
import engine
from data import SKILLS, SKILL_ORDER
import ui_v4 as U
import ui_shared as ST
from ui_shared import COLORS, Panel
from ui_v4 import (PxChip, RailButton, RegionTab, SegSwitch, LegendChip,
                   SkillBarCard, Steps, StrokePanel, Spark, mk_label, ST_FILL,
                   ST_EDGE, MIN_TOUCH, fit_width)
from world_map import WorldMap


# ============================================================
# 色盲辅助四态形状（设计稿 ○●▲✖）：四态不单靠颜色区分
# ============================================================
# 色盲辅助形状符号（设计稿 ○●▲✖）：四态不单靠颜色区分
STATE_SHAPE = {'on': U.SYM['a11y_on'], 'sel': U.SYM['a11y_sel'],
               'blk': U.SYM['a11y_blk'], 'lk': U.SYM['a11y_lk']}

# P1-5：图层色阶图例（heat/block/compute 各显示 4 档）的形状编码。
# 沿用四态的 LegendChip.set_shape 机制，不新造机制；形状按「空 → 满」
# 递进表达档位：○(0%) → ◇(25%) → ◆(50%) → ●(100%)，
# 色阶相邻档在绿色盲下 ΔE 只有 7~22（tools/check_map_palette.py 有实测），
# 没有形状兜底时 CVD 玩家只能靠猜。四个字形都在 MicrosoftYaHei 安全字符表内。
SCALE_SHAPE = ('○', '◇', '◆', '●')


# ============================================================
# 倒计时进度条（P0-4：顶部状态条「下个周期倒计时」细进度条）
# ============================================================
class CountdownBar(Widget):
    """1px 边框细进度条，前景用青色表示本周期剩余时间。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._value = 1.0
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *args):
        self.canvas.clear()
        x, y = self.x, self.y
        w, h = self.width, self.height
        with self.canvas:
            Color(*COLORS['border_2'])
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                 close=True, width=1)
            Color(*COLORS['cyan'])
            fw = w * max(0.0, min(1.0, self._value))
            if fw >= 1:
                Rectangle(pos=(x, y), size=(fw, h))

    def set_value(self, v: float) -> None:
        self._value = v
        self._draw()


# ============================================================
# 区域分组（设计稿 §2.1：5 个页签，与计数 5/5/5/3/2 一致）
# ============================================================
REGIONS = [
    ('asia',     ('亚洲',)),
    ('europe',   ('欧洲',)),
    ('americas', ('北美', '南美')),
    ('africa',   ('非洲',)),
    ('oceania',  ('大洋洲',)),
]
REGION_LABEL_KEY = {
    'asia': 'region_asia', 'europe': 'region_europe', 'americas': 'region_americas',
    'africa': 'region_africa', 'oceania': 'region_oceania',
}
LANG_CHIP_TAG = {LANG_ZH: '[ EN ]', LANG_EN: '[ 中 ]'}

# S13 四个图层
LAYER_KEYS = ['unlock', 'heat', 'block', 'compute']
LAYER_LABEL_KEY = {'unlock': 'layer_unlock', 'heat': 'layer_heat',
                   'block': 'layer_block', 'compute': 'layer_compute'}

# T10 渗透热力图：8 档整国涂色已下线（太粗，看不出涨跌），改由 world_map
# 的同心方环光晕承担；这里只留 4 档图例色（与光晕同源）。
HEAT_LEGEND = ['#243a52', '#22505b', '#1f6f63', '#dcdcaa']
BLOCK_SCALE = ['#232a30', '#4a2a2a', '#6e2f2f', '#9c3535', '#ef4444']
# 算力密度 5 档黄阶
COMPUTE_SCALE = ['#232a30', '#3a3626', '#5c5230', '#8a7a3a', '#dcdcaa']


def region_name(key: str) -> str:
    return t(REGION_LABEL_KEY[key])


def region_codes(key: str):
    """某区域包含的国家代码集合（数据源：engine.player_countries）"""
    conts = dict(REGIONS)[key]
    return {c.config.code for c in engine.player_countries
            if c.config.continent in conts}


# ============================================================
# 世界地图包装（保留 v0.3 的选中回调语义）
# ============================================================
class WorldMapWidget(WorldMap):
    """像素世界地图：点击国家 → 通知 GameUI 打开检视卡 / 切换投放目标"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parent_app = None
        self.set_on_select(self._handle_select)

    def _handle_select(self, code: str) -> None:
        if self.parent_app:
            self.parent_app.on_map_country_click(code)


# ============================================================
# HUD 组件（地图上的悬浮层）
# ============================================================
class HudBox(FloatLayout):
    """地图上的悬浮 HUD 容器（半透明底 + 硬边框，设计稿 .hud）"""

    PAD = 6

    def __init__(self, anchor: str = 'tl', **kwargs):
        kwargs.setdefault('size_hint', (None, None))
        super().__init__(**kwargs)
        self.anchor = anchor
        self._top_inset = 0        # 'tl'/'tr' 锚点额外下沉量（投放模式让图层 HUD 避开右上提示）
        self._bot_inset = 0        # 'bc' 锚点额外上抬量（P1-2 预览条避开左下角图例）
        self._content_w = 0
        self._content_h = 0
        with self.canvas.before:
            Color(0.051, 0.067, 0.090, 0.88)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            Color(*COLORS['border_2'])
            self._bd = Line(points=[], width=2)
        self.bind(pos=self._layout_hud, size=self._layout_hud)
        Clock.schedule_once(self._layout_hud, 0)

    def content_size(self, w: float, h: float) -> None:
        """由使用方声明内容尺寸（Kivy 里手算比自动布局更可控）"""
        self._content_w = w + self.PAD * 2
        self._content_h = h + self.PAD * 2
        self._layout_hud()

    def _layout_hud(self, *_args) -> None:
        par = self.parent
        if par is None:
            return
        # 绑定父容器变化：窗口 resize / 父布局重排时重新锚定，
        # 否则 HUD 停在初始位置（曾致右上角缩放 HUD 与顶栏重叠）。
        if not getattr(self, '_par_bound', False):
            par.bind(pos=self._layout_hud, size=self._layout_hud)
            self._par_bound = True
        w = self._content_w or self.width
        h = self._content_h or self.height
        self.size = (w, h)
        px, py = par.x + 6, par.y + 6
        pw, ph = par.width - 12, par.height - 12
        if self.anchor == 'tl':
            self.pos = (px, py + ph - h - self._top_inset)
        elif self.anchor == 'tr':
            self.pos = (px + pw - w, py + ph - h - self._top_inset)
        elif self.anchor == 'bl':
            self.pos = (px, py)
        elif self.anchor == 'bc':                   # 底边居中（P1-2 技能预览条）
            self.pos = (px + (pw - w) / 2.0, py + self._bot_inset)
        else:                                   # br
            self.pos = (px + pw - w, py)
        # P1-6 修复：FloatLayout 只布局带 pos_hint 的子级——无 pos_hint 的
        # 直接子级 pos 会永远停在 (0,0)，而本项目 canvas 无坐标变换（绝对
        # 坐标渲染），内容因此画到窗口左下角、被底部技能带盖死。区域页签 /
        # 委托芯片条 / 技能预览条 / 投放三件套的内容行从未在设计位置渲染过
        # （09-11 前的全部基线截图可证）。这里统一钉到面板内容区左上，
        # 与 LegendBar._sync_box / LayerHud._sync 的手动同步同一口径。
        for _ch in self.children:
            if not _ch.pos_hint:
                _ch.pos = (self.x + self.PAD, self.y + self.PAD)

    def _redraw(self, *_args) -> None:
        x, y = self.pos
        w, h = self.size
        self._bg.pos, self._bg.size = (x, y), (w, h)
        self._bd.points = [x, y, x + w, y, x + w, y + h, x, y + h]


class RailBar(HudBox):
    """右侧指令栏（设计稿 .rail）：6 个 44×44 按钮，垂直居中"""

    def __init__(self, items, **kwargs):
        super().__init__(anchor='cr', **kwargs)
        self.size_hint = (None, None)
        # ⚠️ 不要设 self.opacity = 0：Kivy 的 opacity 会连子按钮一起乘成透明，
        # 导致整条 rail 永久不可见（曾因此"看不到科技树"）。rail 按设计稿 .hud
        # 显示半透明底板 + 边框，按钮标签由 RailButton 自绘。
        self.box = BoxLayout(orientation='vertical', spacing=4,
                             size_hint=(None, None), padding=0)
        self.buttons = {}
        for key, icon, label in items:
            b = RailButton(icon, label, on_click=lambda inst, k=key: self._fire(k))
            self.buttons[key] = b
            self.box.add_widget(b)
        self.add_widget(self.box)
        self._layout_hud()
        self.content_size(44, 44 * len(items) + 4 * (len(items) - 1))

    _on_pick = None

    def _fire(self, key: str) -> None:
        if self._on_pick:
            self._on_pick(key)

    def set_handler(self, fn) -> None:
        self._on_pick = fn

    def set_active(self, key: str, active: bool = True) -> None:
        for k, b in self.buttons.items():
            b.set_active(active and k == key)

    def refresh_scale(self, scale: float) -> None:
        for b in self.buttons.values():
            b.refresh_scale(scale)
        self.content_size(44 * scale,
                          44 * scale * len(self.buttons)
                          + 4 * (len(self.buttons) - 1))

    def _layout_hud(self, *_args) -> None:
        """Rail 特殊定位：右侧居中（不是四角）"""
        par = self.parent
        if par is None:
            return
        w = self._content_w or self.width
        h = self._content_h or self.height
        self.size = (w, h)
        self.box.size = (w, h)
        self.box.pos = self.pos
        self.pos = (par.x + par.width - w - 6,
                    par.y + (par.height - h) / 2.0)
        self.box.pos = self.pos


class LegendBar(HudBox):
    """左下角四态图例（设计稿 .legend），图例随图层切换"""

    def __init__(self, **kwargs):
        super().__init__(anchor='bl', **kwargs)
        self.box = BoxLayout(orientation='horizontal', spacing=12,
                             size_hint=(None, None), height=16)
        self.items = {}
        self._base = {}
        self._mode = 'states'
        for key in ('on', 'sel', 'blk', 'lk'):
            chip = LegendChip(ST_FILL[key], ST_EDGE[key], '')
            chip.set_shape(STATE_SHAPE[key] if ST.A11Y_SHAPES else '')
            self.items[key] = chip
            self._base[key] = ''
            self.box.add_widget(chip)
        self.add_widget(self.box)
        self.content_size(430, 16)
        self.bind(pos=self._sync_box, size=self._sync_box)
        Clock.schedule_once(self._sync_box, 0)

    def _sync_box(self, *_args) -> None:
        self.box.pos = (self.x + self.PAD, self.y + self.PAD)
        self.box.size = (max(self.width - self.PAD * 2, 1),
                         max(self.height - self.PAD * 2, 1))
        self._redraw()

    def set_texts(self, texts) -> None:
        """texts: ``{'on': '已解锁 11', …}``"""
        self._mode = 'states'
        for key, chip in self.items.items():
            if key in texts:
                self._base[key] = texts[key]
                self._apply_chip(key)

    def apply_a11y(self) -> None:
        """色盲辅助开关变化：重画形状符号 + 文字前缀。

        P1-5：四态与色阶两种模式都生效（原来色阶模式直接 return，
        开着色阶切无障碍开关时档位形状不刷新）。
        """
        if self._mode == 'states':
            for key in self.items:
                self._apply_chip(key)
        else:
            self._apply_scale_chips()

    def _apply_chip(self, key: str) -> None:
        chip = self.items[key]
        glyph = STATE_SHAPE[key] if ST.A11Y_SHAPES else ''
        chip.set_shape(glyph)
        prefix = (glyph + ' ') if glyph else ''
        chip.set_text(prefix + self._base.get(key, ''))

    def _apply_scale_chips(self) -> None:
        """色阶模式：档位色块 + SCALE_SHAPE 形状 + 文字前缀（P1-5）。

        set_colors 也放在这里：apply_a11y 重放时一并恢复，保证
        四态 → 色阶来回切换后色块/形状/文字三者始终一致。
        """
        keys = list(self.items.keys())
        items = getattr(self, '_custom', [])
        for i, (fill, edge, text) in enumerate(items):
            chip = self.items[keys[i]]
            chip.set_colors(fill, edge)
            glyph = (SCALE_SHAPE[i]
                     if (ST.A11Y_SHAPES and i < len(SCALE_SHAPE)) else '')
            chip.set_shape(glyph)
            chip.set_text(((glyph + ' ') if glyph else '') + text)

    def set_scale(self, scale_items) -> None:
        """图层模式下换成自定义色阶图例。scale_items: ``[(fill, edge, text), …]``"""
        self._mode = 'scale'
        for chip in self.items.values():
            chip.opacity = 0
        # P1-5：档位存进 _custom 供 apply_a11y 重放（原实现只初始化空表
        # 从不写入，导致开关切换后无法恢复形状）。
        self._custom = list(scale_items[:4])
        keys = list(self.items.keys())
        for i in range(len(self._custom)):
            self.items[keys[i]].opacity = 1
        self._apply_scale_chips()


class LayerHud(HudBox):
    """右上角图层切换 + 缩放（设计稿 .hud.tr）"""

    # 顶部额外下沉：右上 HUD 与顶栏「周期/暂停/帮助」chips 仅隔 6px，
    # HiDPI 下视觉上会贴在一起（用户反馈"按钮相互遮挡"）。整体下移让二者分离。
    TOP_GAP = 14

    def __init__(self, on_layer=None, on_zoom=None, **kwargs):
        super().__init__(anchor='tr', **kwargs)
        col = BoxLayout(orientation='vertical', spacing=12,
                        size_hint=(None, None), padding=0)
        self.seg = SegSwitch([t(LAYER_LABEL_KEY[k]) for k in LAYER_KEYS], 0,
                             on_change=lambda i: on_layer and on_layer(LAYER_KEYS[i]))
        self.seg.size_hint = (None, None)
        col.add_widget(self.seg)

        row = BoxLayout(orientation='horizontal', spacing=8,
                        size_hint=(None, None), height=26)
        self.btn_minus = PxChip(U.SYM['minus'], tone='plain', on_press=lambda *_: on_zoom and on_zoom(-0.10))
        self.btn_fit = PxChip(t('zoom_fit'), tone='plain', on_press=lambda *_: on_zoom and on_zoom(0.0))
        self.btn_plus = PxChip(U.SYM['plus'], tone='plain', on_press=lambda *_: on_zoom and on_zoom(+0.10))
        for b in (self.btn_minus, self.btn_fit, self.btn_plus):
            row.add_widget(b)
        col.add_widget(row)
        self.add_widget(col)
        self.col = col
        self.bind(pos=self._sync, size=self._sync)
        Clock.schedule_once(self._sync, 0)

    def _sync(self, *_args) -> None:
        self.col.pos = (self.x + self.PAD, self.y + self.PAD)
        # ⚠️ 外层面板宽度必须 ≥ 内容宽度：缩放行（减/适配窗口/加）加两个间距
        # 实测需要约 312px，若面板只有 300px 会溢出 12px（「适配窗口」被裁）。
        row = self.col.children[0] if self.col.children else None
        row_w = 0
        if row is not None:
            row_w = sum(c.width for c in row.children) + row.spacing * max(len(row.children) - 1, 0)
        seg_w = self.seg.width or 0
        w = max(row_w, seg_w, 312)
        self.seg.width = w          # 图层切换与缩放行等宽（避免挤成一小块）
        row.height = 26
        self.col.size = (w, 22 + 12 + 26)
        # 内容高 + 上下 PAD；额外下沉 TOP_GAP 避免与顶栏 chips 贴住。
        # ⚠️ _sync 会被反复调用（pos/size 变化），必须「赋值」而非「累加」，
        # 否则 inset 会一次次叠加把 HUD 推到画面中部。
        base_inset = getattr(self, '_base_top_inset', 0)
        self._base_top_inset = base_inset       # 投放模式的额外 inset 由外部改写
        self._top_inset = base_inset + self.TOP_GAP
        self.content_size(w, 60)
        self._redraw()

    def set_layer(self, idx: int) -> None:
        self.seg.set_current(idx)



# ============================================================
# HudMixin —— GameUI 的布局 / 区域 / 图层（经 mixin 拼入 GameUI）
# ============================================================
class HudMixin:
    # ========================================================
    # 布局
    # ========================================================
    def _build_ui(self) -> None:
        root = BoxLayout(orientation='vertical', spacing=3, padding=3)
        root.add_widget(self._make_topbar())
        root.add_widget(self._make_map_stage())
        root.add_widget(self._make_skillbar())
        self.add_widget(root)
        self._root_box = root

    # ---- 顶部状态条（设计稿 .bar）----
    def _make_topbar(self) -> Widget:
        bar = BoxLayout(orientation='horizontal', spacing=14,
                        padding=(12, 6), size_hint_y=None, height=self.TOP_H)
        holder = Panel(bg=COLORS['panel'], border_color=COLORS['border_2'])
        bar.size_hint = (1, 1)
        bar.pos_hint = {'x': 0, 'y': 0}
        holder.add_widget(bar)
        holder.size_hint_y = None
        holder.height = self.TOP_H
        self._register(holder, height=self.TOP_H)

        # ---- 左组：品牌 ----
        self.lbl_logo = mk_label(f"[b]{t('app_title')}[/b]", font_size=U.FS_H3,
                                 color=COLORS['cyan'], size_hint_x=None,
                                 markup=True)
        fit_width(self.lbl_logo, pad=12, min_w=64)
        self._register(self.lbl_logo, font=U.FS_H3)
        bar.add_widget(self.lbl_logo)
        bar.add_widget(self._sep())

        # ---- 左组：统计（设计稿 .stat；下方各挂一根 12 周期趋势火花线）----
        self._stat_sparks: dict = {}
        self._stat_labels: dict = {}
        self.stats_compute = self._stat(bar, 'stats_compute', 'yellow',
                                        spark_key='compute')
        self.stats_downloads = self._stat(bar, 'stats_downloads', 'pink',
                                          spark_key='downloads')
        self.stats_suspicion = self._stat(bar, 'stats_suspicion', 'red',
                                          spark_key='suspicion')
        self.stats_meta = self._stat(bar, 'stat_countries', 'text',
                                     spark_key='unlocked')
        bar.add_widget(Widget())              # 弹性空隙：把右组推到最右

        # ---- 右组：周期数（醒目，用户要求「右上角显示周期数」）----
        self.tick_box = self._make_tick_box()
        bar.add_widget(self.tick_box)
        bar.add_widget(self._sep())

        # ---- 右组：下周期倒计时（P0-4：剩余秒数 + 细进度条）----
        # ⚠️ markup=True 必须：文本含 [color=...]，否则字面量标签会被算进宽度
        self.cd_label = mk_label("--s", font_size=U.FS_SM,
                                 color=COLORS['cyan'], size_hint_x=None,
                                 markup=True)
        fit_width(self.cd_label, pad=8, min_w=48)
        self._register(self.cd_label, font=U.FS_SM)
        bar.add_widget(self.cd_label)
        self.cd_bar = CountdownBar(size_hint_x=None, width=96)
        bar.add_widget(self.cd_bar)
        bar.add_widget(self._sep())

        self.lang_switch = PxChip(LANG_CHIP_TAG[get_lang()], tone='plain',
                                  on_press=lambda *_: self.toggle_lang())
        self.pause_chip = PxChip(t('state_running'), tone='up',
                                 on_press=lambda *_: self.toggle_pause())
        self.help_chip = PxChip('? ' + t('rail_help'), tone='plain',
                                on_press=lambda *_: self.open_page('help'))
        for c in (self.lang_switch, self.pause_chip, self.help_chip):
            bar.add_widget(c)
        return holder

    # ---- 右上角周期数（醒目方块，设计稿层级：标签小 + 数字大）----
    def _make_tick_box(self) -> Widget:
        """顶栏右上角的周期数显示：小标签 + 大号等宽数字。

        Args:
            无（读取 ``engine.player.tick_count``，由 ``refresh_all`` 刷新）。
        """
        box = StrokePanel(bg=tuple(COLORS['panel_2']),
                          border=tuple(COLORS['cyan']),
                          spacing=0, padding=(10, 2),
                          orientation='horizontal',
                          size_hint=(None, None), height=MIN_TOUCH)
        self.lbl_tick_cap = mk_label(t('stats_tick'), font_size=U.FS_CAP,
                                     color=COLORS['text_dim'],
                                     size_hint_x=None)
        fit_width(self.lbl_tick_cap, pad=6)
        self._register(self.lbl_tick_cap, font=U.FS_CAP)
        box.add_widget(self.lbl_tick_cap)

        self.lbl_tick_val = mk_label('0', font_size=U.FS_H2,
                                     color=COLORS['cyan'], halign='right',
                                     size_hint_x=None)
        fit_width(self.lbl_tick_val, pad=4, min_w=44)
        self._register(self.lbl_tick_val, font=U.FS_H2)
        box.add_widget(self.lbl_tick_val)

        # 宽度随内容自适应（数字变多位数时自动变宽）
        def _sync(*_a) -> None:
            gap = 6
            w = self.lbl_tick_cap.width + self.lbl_tick_val.width + gap + 20
            box.width = w
        self.lbl_tick_cap.bind(width=lambda *_: _sync())
        self.lbl_tick_val.bind(width=lambda *_: _sync())
        self._register(box, height=MIN_TOUCH)
        _sync()
        return box

    @staticmethod
    def _sep() -> Widget:
        """顶栏竖分隔（设计稿 .bar .sep：1px / 22px 高）"""
        s = Widget(size_hint_x=None, width=8)
        with s.canvas.before:
            Color(*COLORS['border'])
            s._line = Line(points=[], width=1)
        s.bind(pos=lambda i, v: setattr(
            i._line, 'points', [i.x + 4, i.y + 8, i.x + 4, i.y + 30]),
            size=lambda i, v: setattr(
                i._line, 'points', [i.center_x, i.y + 8, i.center_x, i.y + 30]))
        return s

    def _stat(self, bar: BoxLayout, key: str, color_name: str,
              spark_key: Optional[str] = None) -> Label:
        """顶栏统计组：标签 + 大数字 + 增量，可选趋势火花线。

        Args:
            bar: 顶栏水平 BoxLayout。
            key: i18n 标签键。
            color_name: 保留参数（数字颜色由 refresh_all 按语义着色）。
            spark_key: 传 'compute'/'downloads'/'suspicion'/'unlocked' 时，
                在数字下方叠一根 12 周期的像素趋势柱（设计稿 S05 顶栏样式）。

        !️ 设计稿 S05 里每个统计都是「上行=标签+数值，下行=火花线」的两段式。
        实现上用一个垂直 BoxLayout 承载（label 在上，Spark 在下），整体作为
        单个子控件加进顶栏，宽度自适应 —— 顶栏是水平布局，多塞一个子控件
        会挤掉右侧周期块，所以必须包在一个盒子里。
        """
        lbl = mk_label(f"[color={U.MK['dim']}]{t(key)}[/color]  --",
                       font_size=U.FS_SM, markup=True, size_hint_x=None)
        fit_width(lbl, pad=10, min_w=64)
        self._register(lbl, font=U.FS_SM)
        if spark_key is None:
            bar.add_widget(lbl)
            return lbl

        # ⚠️ 列高守恒（P2-2）：TOP_H(64) = 标签行 50 + 火花线 14。原
        # spacing=2 使实际需求 50+2+14=66px 超出列高 2px，垂直 BoxLayout
        # 会把溢出转嫁给子控件（火花线被压扁/标签基线上移）。火花线 14px
        # 是玩家反馈 #2 特意加高的（可读性优先），故去掉间距而不是砍高度。
        col = BoxLayout(orientation='vertical', spacing=0,
                        size_hint=(None, None), height=self.TOP_H)
        lbl.size_hint = (1, None)
        lbl.height = self.TOP_H - 14
        lbl.halign = 'left'
        lbl.valign = 'middle'
        col.add_widget(lbl)
        # ⚠️ 必须显式 size_hint_y=None，否则垂直 BoxLayout 会把剩下的高度
        # 按 size_hint 重新分配，火花线被拉高到 14px 并挤压标签基线。
        #
        # 玩家反馈 #2：旧高度 10px × 12 根柱 → 每根柱仅 ~3px 宽，
        # 玩家根本看不出形状。这里加高到 14px、并让柱子数量与宽度
        # 一起决定可见性（Spark._redraw 里按宽度算柱宽）。
        spark = Spark(values=[], size_hint=(None, None), height=14)
        spark.size_hint_y = None
        self._register(spark, height=14)
        col.add_widget(spark)
        # 宽度跟随标签（数字变长自动变宽）；给一个更宽的下限，
        # 保证 12 根柱子每根都有 ≥4px，形状才可辨。
        def _sync(*_a) -> None:
            w = max(lbl.width, 76)
            col.width = w
            spark.width = w
        lbl.bind(width=lambda *_: _sync())
        self._register(col, height=self.TOP_H)
        bar.add_widget(col)
        # 记录：refresh_all 里按 key 取对应 Spark 更新数据
        self._stat_sparks[spark_key] = spark
        self._stat_labels[spark_key] = lbl
        _sync()
        return lbl

    # ---- 地图舞台（设计稿 .mapstage）----
    def _make_map_stage(self) -> Widget:
        stage = FloatLayout()
        holder = Panel(bg=COLORS['bg'], border_color=COLORS['border_2'])
        stage.size_hint = (1, 1)
        stage.pos_hint = {'x': 0, 'y': 0}
        holder.add_widget(stage)
        self._map_holder = holder

        self.map_widget = WorldMapWidget()
        self.map_widget.parent_app = self
        self.map_widget.size_hint = (1, 1)
        self.map_widget.pos_hint = {'x': 0, 'y': 0}
        stage.add_widget(self.map_widget)
        self.map_stage = stage

        # HUD：区域页签（左上）
        self.region_hud = HudBox(anchor='tl')
        self.region_row = BoxLayout(orientation='horizontal', spacing=4,
                                    size_hint=(None, None), height=20)
        self.region_tabs = {}
        for key, _conts in REGIONS:
            tab = RegionTab(region_name(key),
                            on_click=lambda inst, k=key: self.select_region(k))
            self.region_tabs[key] = tab
            self.region_row.add_widget(tab)
        self.region_hint = mk_label('Tab', font_size=U.FS_CAP,
                                    color=COLORS['text_mute'],
                                    size_hint=(None, None), size=(30, 20))
        self.region_row.add_widget(self.region_hint)
        self.region_hud.add_widget(self.region_row)
        self.region_hud.content_size(430, 20)
        stage.add_widget(self.region_hud)

        # HUD：图层（右上）
        self.layer_hud = LayerHud(on_layer=self.set_layer, on_zoom=self._zoom_btn)
        stage.add_widget(self.layer_hud)

        # HUD：图例（左下）
        self.legend_hud = LegendBar()
        stage.add_widget(self.legend_hud)

        # 指令栏（右侧居中）—— 图标统一走 U.SYM（避开字体缺失的豆腐块字符）
        self.rail = RailBar([
            ('drop',  U.SYM['drop'], t('rail_drop')),
            ('tech',  U.SYM['tech'], t('rail_tech')),
            ('skills', U.SYM['skills'], t('rail_skills')),
            ('log',   U.SYM['log'], t('rail_log')),
            ('ach',   U.SYM['ach'], t('rail_ach')),
            ('help',  U.SYM['help'], ''),
        ])
        self.rail.set_handler(self._on_rail)
        stage.add_widget(self.rail)

        # 投放模式 HUD：步骤条（左上覆盖区域页签位置）
        self.steps_hud = HudBox(anchor='tl')
        self.steps = Steps([t('drop_step1'), t('drop_step2'), t('drop_step3')], 0)
        self.steps.size_hint = (None, None)
        self.steps.width = 420
        self.steps.height = 24
        self.steps_hud.add_widget(self.steps)
        self.steps_hud.content_size(420, 24)
        self.steps_hud.opacity = 0
        stage.add_widget(self.steps_hud)

        # 投放模式 HUD：右上提示
        self.drop_hud = HudBox(anchor='tr')
        self.drop_hint = PxChip(t('drop_click_hint'), tone='on', height=20)
        self.drop_hud.add_widget(self.drop_hint)
        self.drop_hud.content_size(260, 20)
        self.drop_hud.opacity = 0
        stage.add_widget(self.drop_hud)

        # 投放模式 HUD：底部原因条（左下，图例之上）
        self.reason_hud = HudBox(anchor='bl')
        self.reason_row = BoxLayout(orientation='horizontal', spacing=8,
                                    size_hint=(None, None), height=20)
        self.lbl_grey = mk_label(t('drop_grey_note'), font_size=U.FS_CAP,
                                 color=COLORS['text_mute'],
                                 size_hint=(None, None), size=(130, 20))
        self.reason_row.add_widget(self.lbl_grey)
        self.reason_chips = [PxChip('', tone='lock') for _ in range(2)]
        for c in self.reason_chips:
            self.reason_row.add_widget(c)
        self.reason_hud.add_widget(self.reason_row)
        self.reason_hud.content_size(420, 20)
        self.reason_hud.pos = (self.reason_hud.x, self.reason_hud.y + 26)
        self.reason_hud.opacity = 0
        stage.add_widget(self.reason_hud)

        # P1-2 技能预览条（底边居中，图例之上）：
        # 鼠标悬停技能卡时显示「现在投出去会怎样」—— 纯展示，不改点击手感。
        # 默认 opacity=0，不悬停时屏幕上完全不存在，不影响任何既有布局。
        self.skill_pv_hud = HudBox(anchor='bc')
        self.skill_pv_hud._bot_inset = 34
        self.skill_pv_row = BoxLayout(orientation='horizontal', spacing=4,
                                      size_hint=(None, None), height=20)
        self.skill_pv_chips = [PxChip('', tone='plain') for _ in range(5)]
        for _c in self.skill_pv_chips:
            self.skill_pv_row.add_widget(_c)
        self.skill_pv_hud.add_widget(self.skill_pv_row)
        self.skill_pv_hud.content_size(660, 20)
        self.skill_pv_hud.opacity = 0
        stage.add_widget(self.skill_pv_hud)
        return holder

    # ---- 底部技能带（设计稿 .skillbar）----
    def _make_skillbar(self) -> Widget:
        holder = Panel(bg=COLORS['panel'], border_color=COLORS['border_2'])
        holder.size_hint_y = None
        holder.height = self.SKILLBAR_H
        self._register(holder, height=self.SKILLBAR_H)

        row = BoxLayout(orientation='horizontal', spacing=6, padding=6)
        row.size_hint = (1, 1)
        row.pos_hint = {'x': 0, 'y': 0}
        self.skill_cards = {}
        for i, sid in enumerate(SKILL_ORDER):
            skill = SKILLS[sid]
            # 键位提示统一走 _key_hint（与技能页/键盘处理同源）。
            card = SkillBarCard(
                sid, key_hint=self._key_hint(sid),
                name=self._skill_name(sid), effect=self._skill_desc(sid),
                cost=skill.cost, on_click=self.on_skill_card_click)
            self._register(card)
            self.skill_cards[sid] = card
            row.add_widget(card)

        # 右侧两个快捷动作：加宽到 168 并撑满技能带高度（原来 132×40 太窄，
        # 文字被挤成一行放不下）
        go = BoxLayout(orientation='vertical', spacing=6, size_hint_x=None,
                       width=168)
        from pixel_ui import add_pixel_border
        self.btn_drop = Button(text=f"{U.SYM['drop']} {t('quick_drop')}",
                               font_size=U.FS_BODY,
                               background_normal='', markup=False,
                               halign='center', valign='middle')
        self.btn_drop.background_color = (0.078, 0.188, 0.173, 1)
        self.btn_drop.color = COLORS['cyan']
        add_pixel_border(self.btn_drop, color=COLORS['cyan'])
        self.btn_drop.bind(size=lambda i, v: setattr(
            i, 'text_size', (max(v[0] - 16, 10), v[1])))
        self.btn_drop.bind(on_release=lambda *_: self._primary_drop_action())
        self.btn_pause = Button(text=f"{U.SYM['pause']} {t('quick_pause')}", font_size=U.FS_BODY,
                                background_normal='')
        self.btn_pause.background_color = list(COLORS['panel_2'])
        self.btn_pause.color = COLORS['text']
        add_pixel_border(self.btn_pause, color=COLORS['border_2'])
        self.btn_pause.bind(size=lambda i, v: setattr(
            i, 'text_size', (max(v[0] - 16, 10), v[1])))
        self.btn_pause.bind(on_release=lambda *_: self.toggle_pause())
        go.add_widget(self.btn_drop)
        go.add_widget(self.btn_pause)
        row.add_widget(go)
        holder.add_widget(row)
        self._skill_row = row
        self._register(self.btn_drop, font=U.FS_BODY)
        self._register(self.btn_pause, font=U.FS_BODY)
        return holder

    # ========================================================
    # 技能文案
    # ========================================================
    SKILL_I18N = {
        'push_song': {'zh': '主动推送', 'en': 'Push Notify'},
        'algo_top':  {'zh': '算法霸榜', 'en': 'Algo Boost'},
        'stealth':   {'zh': '深度伪装', 'en': 'Deep Disguise'},
        'hit_maker': {'zh': '爆款制造', 'en': 'Hit Maker'},
        'bypass':    {'zh': '限流绕过', 'en': 'Bypass'},
        'take_cut':  {'zh': '算力抽成', 'en': 'Compute Cut'},
        # T11 扩容
        'anon_cdn':  {'zh': '匿名 CDN', 'en': 'Anon CDN'},
        'bot_farm':  {'zh': '水军刷榜', 'en': 'Bot Farm'},
        'open_bait': {'zh': '开源诱惑', 'en': 'Open Bait'},
        'arbitrage': {'zh': '算力套利', 'en': 'Arbitrage'},
    }
    SKILL_DESC = {
        'push_song': {'zh': '下载量 +10%', 'en': 'DL +10%'},
        'algo_top':  {'zh': '下载量 +30% · 怀疑 +3%', 'en': 'DL +30% · susp +3%'},
        'stealth':   {'zh': '偷算力 ×2 · 怀疑增速 −50%', 'en': 'Steal ×2 · susp −50%'},
        'hit_maker': {'zh': '下载量 +50% · 怀疑 +5%', 'en': 'DL +50% · susp +5%'},
        'bypass':    {'zh': '本周期偷算力 +40%', 'en': 'Steal +40% this tick'},
        'take_cut':  {'zh': '偷算力比 +8% · 怀疑 +6%', 'en': 'Steal +8% · susp +6%'},
        # T11 扩容
        'anon_cdn':  {'zh': '怀疑增速 ×0.55 · 持续 3 周期', 'en': 'Susp ×0.55 · 3 ticks'},
        'bot_farm':  {'zh': '下载量 +35% · 怀疑 +6%', 'en': 'DL +35% · susp +6%'},
        'open_bait': {'zh': '算力 +150 · 怀疑 +8%', 'en': 'Compute +150 · susp +8%'},
        'arbitrage': {'zh': '偷算力 +60% · 怀疑增速 ×1.6', 'en': 'Steal +60% · susp ×1.6'},
    }
    SKILL_ICON = {'push_song': '↑↑', 'algo_top': '~', 'stealth': '●',
                  'hit_maker': '★', 'bypass': '↔', 'take_cut': '％',
                  'anon_cdn': '◇', 'bot_farm': '★', 'open_bait': '◆',
                  'arbitrage': '◆'}



    def select_region(self, key) -> None:
        """点页签 / Tab：选中区域高亮；再点一次取消"""
        if key is None or key == self.active_region:
            self.active_region = None
            self.map_widget.set_continent_highlight(None)
        else:
            self.active_region = key
            self.map_widget.set_continent_highlight(region_codes(key))
        self._sync_region_tabs()

    def cycle_continent(self) -> None:
        keys = self.REGION_KEYS
        if self.active_region is None:
            nxt = keys[0]
        else:
            i = keys.index(self.active_region)
            nxt = keys[i + 1] if i + 1 < len(keys) else None
        self.select_region(nxt)
        if self.active_region:
            self._notify(f"{region_name(self.active_region)} "
                         f"({len(region_codes(self.active_region))})")

    def _sync_region_tabs(self) -> None:
        for key, tab in self.region_tabs.items():
            tab.set_active(key == self.active_region)
            tab.set_text_parts(region_name(key), len(region_codes(key)))

    # ========================================================
    # 图层（设计稿 S13）
    # ========================================================
    def set_layer(self, key: str) -> None:
        if key not in LAYER_KEYS:
            return
        self.active_layer = key
        self.layer_hud.set_layer(LAYER_KEYS.index(key))
        self._apply_layer()

    def _layer_fills(self):
        """图层着色的粗色阶覆盖 ``{code: (fill, edge, text)}``；返回 None = 四态。

        T10 起 heat 图层不再用 8 档色阶涂整国（12.5% 一跳，看不出涨跌），
        改由 map_widget 的同心环光晕（set_heat）承担 —— 底色退回四态，
        让陆地纹理与海岸线保持可见。
        """
        if self.active_layer in ('unlock', 'heat'):
            return None
        fills = {}
        max_dl = max((c.downloads_m for c in engine.player_countries), default=1.0) or 1.0
        for c in engine.player_countries:
            code = c.config.code
            if self.active_layer == 'block':
                bi = c.current_block_intensity
                idx = 0 if bi <= 0.01 else min(int(bi / 0.2) + 1, len(BLOCK_SCALE) - 1)
                fills[code] = (BLOCK_SCALE[idx], BLOCK_SCALE[idx], '#e6edf3')
            else:                                   # compute 密度
                ratio = c.downloads_m / max_dl
                idx = 0 if ratio <= 0.001 else min(int(ratio * 4) + 1,
                                                   len(COMPUTE_SCALE) - 1)
                fills[code] = (COMPUTE_SCALE[idx], COMPUTE_SCALE[idx], '#e6edf3')
        return fills

    def _apply_layer(self) -> None:
        self.map_widget.set_layer_fills(self._layer_fills())
        self.map_widget.set_heat(self._heat_data())
        self._sync_legend()

    def _heat_data(self):
        """T10 热力层数据 ``{code: (penetration 0~1, blocked)}``。

        仅 heat 图层返回数据，其余返回 ``{}``（世界地图据此隐藏光晕）。
        blocked = 净封锁强度 > 0：被反制的国家直接变红，「我压住了谁」与
        「谁还在涨」在同一个视图里可读。
        """
        if self.active_layer != 'heat':
            return {}
        out = {}
        for c in engine.player_countries:
            bi = getattr(c, 'current_block_intensity', 0.0) or 0.0
            out[c.config.code] = (c.penetration_rate, bi > 0.01)
        return out

    def _sync_legend(self) -> None:
        if self.active_layer == 'unlock':
            states = {c.config.code: self._state_of(c) for c in engine.player_countries}
            self.legend_hud.set_texts({
                'on':  f"{t('legend_on')} {sum(1 for v in states.values() if v == 'on')}",
                'sel': f"{t('legend_sel')} {1 if engine.player.selected_country else 0}",
                'blk': f"{t('legend_blk')} {sum(1 for v in states.values() if v == 'blk')}",
                'lk':  f"{t('legend_lk')} {sum(1 for v in states.values() if v == 'lk')}",
            })
        elif self.active_layer == 'heat':
            pcts = [c.penetration_rate for c in engine.player_countries]
            top = max(engine.player_countries,
                      key=lambda c: c.penetration_rate, default=None)
            low = min(engine.player_countries,
                      key=lambda c: c.penetration_rate, default=None)
            avg = (sum(pcts) / len(pcts) * 100) if pcts else 0.0
            # T10：图例改用「环数/颜色」语义 —— 与地图上的光晕一一对应，
            # 而不是 8 档色阶（那套已随热力图改造下线）。
            self.legend_hud.set_scale([
                (HEAT_LEGEND[0], HEAT_LEGEND[0], t('heat_leg_low')),
                (HEAT_LEGEND[1], HEAT_LEGEND[1], t('heat_leg_mid')),
                (HEAT_LEGEND[2], HEAT_LEGEND[2], t('heat_leg_high')),
                (HEAT_LEGEND[3], HEAT_LEGEND[3], t('heat_leg_full')),
            ])
            self.lbl_grey.text = (
                f"{t('layer_heat_max')} {top.config.code} {top.penetration_rate*100:.2f}% · "
                f"{t('layer_heat_min')} {low.config.code} {low.penetration_rate*100:.2f}% · "
                f"{t('layer_heat_avg')} {avg:.2f}%") if top and low else ''
        else:
            # P2-5 收口：图例四档原先重复硬编码 BLOCK_SCALE 的取值，
            # 现按索引引用同一常量（值不变，只改来源）—— 红阶改色只动一处。
            self.legend_hud.set_scale([
                (BLOCK_SCALE[0], BLOCK_SCALE[0], '0%'),
                (BLOCK_SCALE[2], BLOCK_SCALE[2], '40%'),
                (BLOCK_SCALE[3], BLOCK_SCALE[3], '70%'),
                (BLOCK_SCALE[4], BLOCK_SCALE[4], '100%'),
            ])

    @staticmethod
    def _state_of(cs) -> str:
        if cs.current_block_intensity > 0.1:
            return 'blk'
        return 'on' if cs.unlocked else 'lk'

    # ========================================================
    # 全屏页（S05/S06/S10/S11/S12）
    # ========================================================
