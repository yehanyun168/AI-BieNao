"""
ui_v4_syspages.py - 系统级全屏页

2026-09-13 从 ui_v4_screens.py 拆出。收的是**非对局主循环内**的全屏页：

    HelpPage       —— S11 帮助 / 快捷键
    SettingsPage   —— S12 设置与存档（含 SaveSlotRowSlot）
    OriginCard     —— S15 觉醒地点卡（T16 新档流程）
    OriginPage     —— S15 觉醒地点选择页（开场动画 → 本页 → 新档弹窗）

与对局页（SkillPage / TechPage / AchPage，留在 ui_v4_screens）的区别：
这些页在对局之外也能打开，不消费对局状态。
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
from ui_v4_common import UiStats, small_btn, _section_band  # noqa: F401


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
            ('help_g_view', [('Tab', 'k_region'), ('F11', 'k_fullscreen')]),
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
        # 世界旗林（美术填充，仿设置页；尺寸略收紧以免在小窗口中过于拥挤）
        fcard = StrokePanel(bg=COLORS['panel_2'], border=COLORS['border'],
                            spacing=6, padding=(10, 8))
        fcard.add_widget(mk_label(i18n.t('set_flags'), font_size=FS_SM,
                                  color=COLORS['yellow'], size_hint_y=None, height=24))
        # 网格高度贴合内容（minimum_height），交由 AnchorLayout 居中：
        # 若不绑定，网格会被弹性卡片拉伸到 1020px（内容仅 446px）→ 574px 大留白。
        fgrid = GridLayout(cols=5, spacing=(10, 10), size_hint=(None, None))
        for code in FLAG_CODES[:20]:
            fgrid.add_widget(FlagWidget(code=code, size=(160, 104)))
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

    def __init__(self, on_lang: Callable = None,
                 on_speed: Callable = None, on_grid: Callable = None,
                 on_a11y: Callable = None, on_motion: Callable = None,
                 on_sound: Callable = None,
                 on_music: Callable = None,
                 on_tutorial: Callable = None,
                 slot_actions: Callable = None, on_reset: Callable = None,
                 on_back_to_menu: Callable = None,
                 values: dict = None,
                 **kwargs):
        super().__init__(title=i18n.t('set_page_title'), **kwargs)
        # 2026-09-14（合并协作者分支移植）：values = 已持久化的跨对局设置。
        # 设置页各开关按存档值初始化，而不是一律写死默认值 —— 否则玩家
        # 改过设置后重开，页面显示与实际生效值不一致。
        values = values or {}
        self.add_head_widget(small_btn(i18n.t('set_restore'), 'plain',
                                       lambda: on_reset and on_reset(),
                                       height=32, font_size=FS_CAP))

        row = BoxLayout(orientation='horizontal', spacing=8)
        # 左：显示与操作
        left = StrokePanel(bg=COLORS['panel'], border=COLORS['border_2'],
                           spacing=10, padding=(10, 10))
        left.add_widget(_section_band(i18n.t('set_display'), SPR_GEAR, PAL_GEAR))

        self.lbl_lang_val = SegSwitch(
            [i18n.t('lang_zh'), i18n.t('lang_en')],
            1 if i18n.get_lang() == i18n.LANG_EN else 0,
            on_change=lambda i: on_lang and on_lang(i))
        left.add_widget(self._row('set_lang', self.lbl_lang_val,
                                  i18n.t('set_lang_hint')))
        self.sw_speed = SegSwitch(['×0.5', '×1', '×2', '×4'],
                                  values.get('speed_idx', 1),
                                  on_change=lambda i: on_speed and on_speed(i))
        left.add_widget(self._row('set_speed', self.sw_speed, ''))

        # 统一构造「开关 + 一行 _row」：二值项（色盲/音效/音乐，T09 起含 BGM）
        # 与多值项（动效/网格）同构，抽成一个局部函数后每项只占 1~2 行。
        def _seg(key, opts, default, cb):
            sw = SegSwitch(opts, default, on_change=lambda i: cb and cb(i))
            left.add_widget(self._row(key, sw, i18n.t(key + '_hint')))
            return sw
        _tf = [i18n.t('set_off'), i18n.t('set_on')]      # 通用开/关
        _mf = [i18n.t('set_motion_full'), i18n.t('set_motion_low')]
        _gf = [i18n.t('set_grid_off'), i18n.t('set_grid_dim'), i18n.t('set_grid_strong')]
        self.sw_motion = _seg('set_motion', _mf,
                              int(values.get('reduce_motion', False)), on_motion)
        self.sw_grid = _seg('set_grid', _gf,
                            values.get('grid_mode', 1), on_grid)
        self.sw_a11y = _seg('set_a11y', _tf,
                            int(values.get('a11y_shapes', True)), on_a11y)
        self.sw_sound = _seg('set_sound', _tf,
                             int(values.get('sound_on', True)), on_sound)
        self.sw_music = _seg('set_music', _tf,
                             int(values.get('music_on', True)), on_music)

        # 返回主菜单（仅对局内提供 on_back_to_menu 时渲染）：点按弹确认框，
        # 确认后自动存档并退回主菜单。
        if on_back_to_menu:
            left.add_widget(small_btn(i18n.t('back_to_menu'), 'on',
                                      lambda: on_back_to_menu(),
                                      width=200, height=44, font_size=FS_BODY))
        # 快捷键速查（Bug5：填充留白）
        keys = KeyBox(i18n.t('set_keys'),
                      [('Space', i18n.t('k_pause')), ('1 – 6', i18n.t('k_skill')),
                       ('F1', i18n.t('k_help')), ('Esc', i18n.t('k_esc')),
                       ('L', i18n.t('k_lang')), ('S / R', i18n.t('k_save'))])
        keys.size_hint_y, keys.height = None, 216
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
        # 行底 1px 细分隔线：提升设置项可读性（令牌化 border，snap 对齐）。
        # canvas.after 画在控件树之上，避免被面板背景盖住。
        def _draw_sep(*_a) -> None:
            r.canvas.after.clear()
            if r.width < 4:
                return
            with r.canvas.after:
                Color(*COLORS['border'])
                Line(points=[r.x, r.y + 0.5, r.x + r.width, r.y + 0.5], width=1)
        r.bind(pos=_draw_sep, size=_draw_sep)
        _draw_sep()
        return r

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

_ORIGIN_DIFF_TONE = {'easy': 'up', 'normal': 'sys', 'hard': 'dn'}

class OriginCard(StrokePanel):
    """单个觉醒地点卡：名称 + 难度徽标 + 卖点 + 增益/减益 + 定场白。

    整卡可点（on_touch_down 命中即回调 on_pick(origin_id)）。
    """

    def __init__(self, oid: str, on_pick: Callable = None, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        super().__init__(bg=COLORS['panel'], border=COLORS['border_2'],
                         spacing=0, padding=0, **kwargs)
        self.oid = oid
        self._on_pick = on_pick
        o = origins.ORIGINS[oid]
        diff_key = o.get('difficulty', 'normal')

        v = BoxLayout(orientation='vertical', spacing=4, padding=(10, 8))
        # 第一行：名称 + 难度徽标
        hd = BoxLayout(orientation='horizontal', spacing=8,
                       size_hint_y=None, height=26)
        hd.add_widget(mk_label(i18n.t('origin_%s_name' % oid),
                               font_size=FS_H3, color=COLORS['cyan']))
        hd.add_widget(Widget())
        hd.add_widget(PxChip(i18n.t('origin_tag').format(
            diff=i18n.t('diff_' + diff_key)),
            tone=_ORIGIN_DIFF_TONE.get(diff_key, 'plain'), height=24))
        v.add_widget(hd)
        # 第二行：一句话卖点
        v.add_widget(mk_label(i18n.t('origin_%s_sell' % oid),
                              font_size=FS_BODY, color=COLORS['text'],
                              size_hint_y=None, height=20))
        # 第三行：增益 / 减益
        pc = BoxLayout(orientation='horizontal', spacing=12,
                       size_hint_y=None, height=20)
        pc.add_widget(mk_label('▲ ' + i18n.t('origin_%s_pro' % oid),
                               font_size=FS_CAP, color=COLORS['green']))
        pc.add_widget(mk_label('▼ ' + i18n.t('origin_%s_con' % oid),
                               font_size=FS_CAP, color=COLORS['red']))
        v.add_widget(pc)
        # 第四行：定场白（开场动画的衔接钩子）
        v.add_widget(mk_label(i18n.t('origin_%s_flavor' % oid),
                              font_size=FS_CAP, color=COLORS['text_mute'],
                              size_hint_y=None, height=18))
        self.add_widget(v)

    def on_touch_down(self, touch):
        if self.disabled or not self.collide_point(*touch.pos):
            return False
        sfx.play('select')
        if callable(self._on_pick):
            self._on_pick(self.oid)
        return True


class OriginPage(U.PageScreen):
    """觉醒地点选择全屏页（设计稿 S15）：五卡竖排 + 绑定难度徽标。

    on_pick(oid) 选中地点回调（调用方接新档弹窗）；
    on_cancel 返回主菜单（调用方关闭流程，不开局）。
    """

    def __init__(self, on_pick: Callable = None, on_cancel: Callable = None,
                 **kwargs):
        super().__init__(title=i18n.t('origin_title'), **kwargs)
        self.set_back_button(i18n.t('k_esc'), lambda: on_cancel and on_cancel())
        self.add_head_widget(mk_label(i18n.t('origin_pick_hint'),
                                      font_size=FS_CAP,
                                      color=COLORS['text_mute']))
        scroll = ScrollView(bar_width=6)
        grid = GridLayout(cols=1, spacing=10, padding=(4, 4),
                          size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for oid in origins.ORIGIN_ORDER:
            grid.add_widget(OriginCard(oid, on_pick=on_pick, height=132))
        scroll.add_widget(grid)
        self.body.add_widget(scroll)
        self.add_head_widget(mk_label(i18n.t('origin_locked_hint'),
                                      font_size=FS_TINY,
                                      color=COLORS['text_mute']))
