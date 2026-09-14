"""
ui_v4_cards.py - 技能页 / 科技树的行与卡

2026-09-13 从 ui_v4_screens.py 拆出。收的是「页面内部的重复单元」：

    SkillPageCard —— S05 技能页大卡
    SlotRow       —— S06 槽位链路的一行
    LinkBar       —— S06 槽位之间的前置连线
    LvRow         —— S06 分支的单个等级行
    BranchCard    —— S06 分支卡

这些单元被 SkillPage / TechPage 组合使用，自身不含页面级布局。
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
class SkillPageCard(StrokePanel):
    """技能页大卡（设计稿 .skcard）：图标/名字/键位/状态 + 效果 chips +
    3 个统计数字 + 12 周期使用柱 + 底部动作。

    ⚠️ 卡片内部分段高度全部走下面的类常量（单一来源），refresh_scale 按同一
    组常量缩放；技能页把卡片放进 ScrollView 并给固定高，故这里必须有确定的
    高度，不能再依赖父容器均分。
    """

    # 分段高度（单一来源）。内容最小高 = HEAD 32 + body 183 + FOOT 30 = 245
    #   其中 body 183 = padding 12 + CHIPS 34 + DESC 84 + STATS 16 + SPARK 22
    #                  + spacing 5×3 = 15
    # DESC_H=84 是 2026-09-14 上调（原 72）：英文 detail + benefit/cost 行在
    #   1680×980 窄卡片下需要 4 行（≈76px），原 72 触发 test_skill_card_geom
    #   「裁字」断言。中英文 i18n 都保持同等文案密度，扩 12px 收口所有语种
    #   的窄窗口溢出，并保证几何测试的「不裁字」契约。
    CARD_H = 252        # 整卡基础高（≥ 内容最小高 245，留 7px 呼吸）
    HEAD_H = 32         # 标题行（图标 + 名称 + 状态芯片）
    CHIPS_H = 34        # 效果 chips 行
    DESC_H = 84         # 说明区：detail 3 行 + 数值行 1 行（英文窄窗口 4 行）
    STATS_H = 16        # 统计行（释放/累计贡献/单次均值）
    SPARK_H = 22        # 12 周期使用柱
    FOOT_H = 30         # 底栏（预览文案 + 动作按钮）

    def __init__(self, on_action: Callable = None, **kwargs):
        super().__init__(bg=COLORS['panel'], border=COLORS['border_2'],
                         spacing=0, padding=0, **kwargs)
        self._on_action = on_action

        # 标题
        self._hd = hd = FloatLayout(size_hint_y=None, height=self.HEAD_H)
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

        # 名称避让：左留 66px 给图标、右留 ~80px 给状态芯片（chip_state 在
        # right:1 叠在名称上方）。把文字框收进这段区间，超长省略而非被芯片遮。
        def _fit_name(*_a) -> None:
            avail = self._hd.width - 66 - 80
            if avail > 24:
                self.lbl_nm.text_size = (avail, self._hd.height)
        self._hd.bind(size=_fit_name)
        _fit_name()

        # 正文
        body = BoxLayout(orientation='vertical', spacing=5, padding=(8, 6))
        self._body = body
        self.chips = ChipRow([], height=self.CHIPS_H)
        body.add_widget(self.chips)
        self.lbl_desc = mk_label('', font_size=FS_CAP, color=COLORS['text_mute'],
                                 valign='top', size_hint_y=None,
                                 height=self.DESC_H, markup=True)
        body.add_widget(self.lbl_desc)
        self.lbl_stats = mk_label('', font_size=FS_CAP, markup=True,
                                  size_hint_y=None, height=self.STATS_H)
        body.add_widget(self.lbl_stats)
        self.spark = Spark([0.0] * 12, size_hint_y=None, height=self.SPARK_H,
                           fill_hex=ST_FILL['on'])
        body.add_widget(self.spark)
        self.add_widget(body)

        # 底栏
        # ⚠️ 这里**不能**再放全弹性 Widget() spacer：旧写法让它与 lbl_ft 平分
        # 宽度（cardW=549 时 lbl_ft 只剩 212px），预览文案「怀疑 0→0 · 算力
        # 100→104 · 距危机 80」约 250px 被折成 2 行塞进 22px 盒高 → 上下被裁成
        # 「半截字」。改为 lbl_ft 独占剩余宽度 + 单行 shorten（放不下用省略号）。
        ft = BoxLayout(orientation='horizontal', spacing=6, size_hint_y=None,
                       height=self.FOOT_H, padding=(8, 4))
        self.lbl_ft = mk_label('', font_size=FS_CAP, color=COLORS['text_mute'],
                               shorten=True, max_lines=1)
        ft.add_widget(self.lbl_ft)
        self.btn = Button(text='', font_size=FS_CAP, size_hint=(None, None),
                          size=(96, 24), background_normal='')
        self.btn.background_color = (0.078, 0.188, 0.173, 1)
        self.btn.color = COLORS['cyan']
        add_pixel_border(self.btn, color=COLORS['cyan'])
        self.btn.bind(on_release=lambda *_: self._on_action and self._on_action())
        ft.add_widget(self.btn)
        self._ft = ft
        self.add_widget(ft)

    def refresh_scale(self, scale: float) -> None:
        """F12/窗口缩放：卡片「分段高度 + 字号」按同一系数整体同步缩放。

        ⚠️ 必须整体同步：只缩 self.height 会让内部固定高控件溢出、只缩字号
        会裁字 —— 两者一起走才等价于整卡等比。技能页把卡片放进 ScrollView
        并给固定高，所以这里缩放 self.height 后，网格 minimum_height 会自动
        跟着重算，滚动条随之适配。
        """
        s = float(scale)
        self.height = self.CARD_H * s
        self._hd.height = self.HEAD_H * s
        self.lbl_ico.font_size = FS_SM * s
        self.lbl_nm.font_size = FS_BODY * s
        self.chip_state.refresh_scale(s)
        self.chips.height = self.CHIPS_H * s
        self.chips.refresh_scale(s)
        self.lbl_desc.font_size = FS_CAP * s
        self.lbl_desc.height = self.DESC_H * s
        self.lbl_stats.font_size = FS_CAP * s
        self.lbl_stats.height = self.STATS_H * s
        self.spark.height = self.SPARK_H * s
        self._ft.height = self.FOOT_H * s
        self.lbl_ft.font_size = FS_CAP * s
        self.btn.font_size = FS_CAP * s

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
#   大类 —— 6 个平行槽位沿水平方向等距铺开；若数据配置 prereq_slot，
#          才在对应槽位之间绘制依赖连线。
#   扇出 —— 每个槽位节点向下引一条竖线，再水平分叉到 3 条并行分支节点。
#   节点 —— 像素方块（圆角 0、2px 硬边框），内含：图标 + 名称 + 状态副行 +
#          3 格等级点（实心=已达等级，空心=未达；色盲用户可辨）。
#
# 坐标系：整幅图在一个**逻辑画布**（CANVAS_W × CANVAS_H）里排布，
#   绘制时统一乘 scale + 偏移，从而「等比缩放铺满可用区、节点不变形」。
#   所有几何都存节点中心点 (cx, cy)，画的时候按 NODE_W/H 反推左上角。
