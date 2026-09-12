"""
tutorial.py — 新手引导步骤机（P0-1：解决"首局懵、无上手路径"）

设计原则（轻量、非侵入）：
- 在 GameUI 上叠一层遮罩 + 高亮目标控件 + 讲解气泡，不改动任何游戏逻辑。
- 引导期间冻结回合推进（game_tick 里有 overlay 守卫），用户不被倒计时催促。
- 引导状态持久化到 engine.player.seen_tutorial，存盘后新游戏不再重复弹；
  设置页「重看教程」可随时 replay（即使已看过）。
- 为避免与 main.py 循环依赖，本模块只依赖 pixel_ui / ui_v4 / engine / save_manager / kivy。

坐标说明：GameUI 是充满窗口的 FloatLayout（pos=(0,0)），overlay 作为其子控件，
其画布坐标系 == 窗口坐标系。目标控件的窗口坐标用 widget.to_window(0,0) 取得。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.widget import Widget

from pixel_ui import COLORS, PixelPanel, hex_rgba, add_pixel_border
from ui_v4 import mk_label, FS_H3, FS_BODY, FS_CAP, MK, ST_FILL
from ui_modal import auto_h_label    # 自增高正文（text_size=(w,None)，绝不裁切）
import engine
import save_manager

if TYPE_CHECKING:
    from main import GameUI

# 遮罩色（青黑半透明）。step.dim 控制每步透明度；演示步骤设 0.0 让背后面板可见。
_DIM = (0.020, 0.035, 0.055, 0.62)
_HILITE = COLORS['cyan']


@dataclass
class TutorialStep:
    """单步引导。

    Attributes:
        title: 气泡标题。
        body: 气泡正文（支持 Kivy markup）。
        target: GameUI 属性名（高亮该控件）；支持 'skill:<id>' 取 skill_cards；
                None 表示不高亮（居中讲解）。
        anchor: 气泡位置：'bottom'（技能带上方）/ 'top'（目标上方）/ 'center'。
        dim: 遮罩透明度；0.0 让背后的游戏面板可见（用于演示检视卡）。
        action: 进入该步时执行的演示，'select_cn' = 自动选中中国并打开检视卡。
    """

    title: str
    body: str
    target: Optional[str] = None
    anchor: str = 'bottom'
    dim: float = 0.62
    action: Optional[str] = None


class TutorialController:
    """控制新手引导的显示与推进。"""

    @staticmethod
    def _force_layout(w, depth: int = 0) -> None:
        """递归重排 bubble 子树。

        ⚠️ Kivy 布局时序坑：bubble 在 inner 还是默认 100×100 时建立，
        子控件（含 ScrollView 里的正文 Label）全按 100 基准布局；之后
        inner 变 720×400，但 ScrollView→wrap→body 的深层布局链的延迟
        trigger 不会再执行 → 正文停在 100×10 纹理（= 看不见），按钮挤在
        左下角（文字与面板"分离"）。逐层 do_layout 强制全树归位。

        ⚠️⚠️ 遍历顺序必须是「先父后子」：父容器（bubble/inner）挪动后，
        子控件的 pos_hint 是相对**父的新坐标**算的。若先递归子节点再
        `do_layout(父)`，子节点会按父的**旧坐标**归位，于是出现"面板已到
        新位置、标题/按钮还停在上一步位置"的滞后（实测 step2/step3 各错一
        帧）。因此这里先 `do_layout(self)`，再递归子节点。
        """
        if depth > 8:
            return
        do = getattr(w, 'do_layout', None)
        if callable(do):
            try:
                do()
            except Exception:
                pass
        for ch in getattr(w, 'children', ()) or ():
            TutorialController._force_layout(ch, depth + 1)

    STEPS = [
        TutorialStep(
            '欢迎来到《AI 别闹》',
            '你是一个想征服全球舆论的 AI。\n'
            '目标：让更多国家「下载」你的内容，同时别被监管方关停。\n'
            '下面用 40 秒带你走一遍[color={on}]核心循环[/color]与关键参数。'.replace(
                '{on}', MK['st_on']),
            target=None, anchor='center', dim=0.62),
        TutorialStep(
            '先记住这个循环',
            '[b]选国家 → 放技能 → 攒算力 → 点科技 → 再扩张[/b]\n\n'
            '每一「周期」你可以：\n'
            '· 选 1 个国家，投 1 个技能\n'
            '· 用算力研发科技（科技是最大的加速器）\n'
            '· 控制怀疑度，别让监管盯上你\n\n'
            '周期会自动推进——不是回合制，所以别急着点。',
            target=None, anchor='center', dim=0.62),
        TutorialStep(
            '这是世界地图',
            '每个色块是一个国家市场。\n'
            f'[color={MK["st_on"]}]青色[/color] = 已渗透 · '
            f'[color={MK["st_blk"]}]红色[/color] = 被监管封锁 · '
            '灰色 = 尚未解锁。\n'
            '点地图上的国家可以查看它的详情。',
            target='map_widget', anchor='bottom', dim=0.62),
        TutorialStep(
            '点国家 → 看检视卡',
            f'看，左侧弹出了[color={MK["st_on"]}]检视卡[/color]：\n'
            '· 渗透率（你在该国的覆盖）\n'
            '· 怀疑度（监管对你的警惕）\n'
            '· 下载量（你的影响力）\n\n'
            '底部会写「距解锁还差 X%」——照着这个目标推就行。',
            target='map_widget', anchor='center', dim=0.0, action='select_cn'),
        TutorialStep(
            '认识 3 个核心参数',
            '[b]渗透率[/b]：该国下载量 ÷ 人口。≥10% 解锁周边国家，\n'
            '   99% 为饱和。这是你的「进度条」。\n'
            '[b]怀疑度[/b]：≥80% 触发危机弹窗，逼你在三条生路里选\n'
            '   一条（通常损失算力或渗透）。所以别在一国猛推。\n'
            '[b]算力[/b]：技能消耗 + 科技研发都要花。技能里的\n'
            '   「偷算力」类可以回血，但会推高怀疑度。',
            target='map_widget', anchor='center', dim=0.0, action='select_cn'),
        TutorialStep(
            '盯紧「怀疑度」',
            f'怀疑度涨太高（≥80）会触发[color={MK["st_blk"]}]危机弹窗[/color]。\n'
            '两条降怀疑的路：\n'
            f'· [color={MK["st_on"]}]深度伪装[/color]技能（0 算力，冷却 8 周期）\n'
            '· 停止在该国投放，让它自然衰减\n\n'
            '记住：推得越猛，监管盯得越紧。',
            target='map_widget', anchor='center', dim=0.0, action='select_cn'),
        TutorialStep(
            '6 个技能（快捷键 1–6）',
            '底部 6 张技能卡，冷却单位是[color={on}]「周期」[/color]，不是秒。\n'
            '· 主动推送：0 算力，下载 ×1.1，冷却 3\n'
            '· 算法霸榜：50 算力，下载 ×1.3，但怀疑 +3\n'
            '· 深度伪装：0 算力，降怀疑，冷却 8\n'
            '· 爆款制造：100 算力，下载 ×1.5，怀疑 +5\n'
            '· 限流绕过：30 算力，解封锁，冷却 4\n'
            '· 算力抽成：80 算力，偷算力，怀疑 +6\n\n'
            '绿色高亮 = 可用；灰色 = 冷却中或算力不足。'.replace(
                '{on}', MK['st_on']),
            target='skill:push_song', anchor='bottom', dim=0.62),
        TutorialStep(
            '投放流程',
            '右侧指令栏是你的操作中枢：\n'
            f'[color={MK["st_on"]}]投放[/color] → 选技能+选目标 → 确认；\n'
            '科技 / 技能 / 日志 / 成就 / 帮助 也都在这。\n'
            '记住三步：选国家 → 选技能 → 确认投放。',
            target='rail', anchor='bottom', dim=0.62),
        TutorialStep(
            '科技才是最大加速器',
            '这是[color={on}]科技树[/color]（右侧「科技」）。为什么最该先点它？\n'
            '· 6 个 T0 各 20–50 算力，[b]全部解锁仅 200 算力[/b]\n'
            '· 光「平台渗透」+「病毒传播」就能把全局下载 ×1.4\n'
            '· 「本地化」解锁亚洲/欧洲市场（否则你只有少数国家可推）\n'
            '· 「算力效率」让每用户偷的算力更多 → 更快回本\n\n'
            '先打通 T0，收益立刻翻倍——比埋头推流快得多。'.replace(
                '{on}', MK['st_on']),
            target='rail', anchor='bottom', dim=0.62,
            action='open_tech_page'),
        TutorialStep(
            '周期倒计时',
            '顶部的细条 = 一个「周期」的剩余时间。\n'
            '周期结束，游戏自动推进一回合（渗透增长、事件触发）。\n'
            '已减速到 30 秒/周期，你有充足时间思考。\n\n'
            '顶栏每个数字下方的趋势线，能看出它在涨还是在跌。',
            target='cd_bar', anchor='top', dim=0.62),
        TutorialStep(
            '随时暂停 / 帮助 / 设置',
            '右上角：暂停（Space）、切语言（L）、看帮助（F1）。\n'
            '设置里还能调速、减弱动效、开色盲辅助，以及「重看教程」。',
            target='pause_chip', anchor='top', dim=0.62),
        TutorialStep(
            '上手路线（照着推）',
            '1️⃣ 先攒算力，把 6 个 T0 科技点出来（约 200 算力）\n'
            '2️⃣ 选一个人口多、怀疑度低的国家开始推\n'
            '3️⃣ 每周期放 1 个技能，盯着怀疑度别过 80\n'
            '4️⃣ 渗透到 10% 会自动解锁周边国家，顺势扩张\n'
            '5️⃣ 怀疑度高了就放「深度伪装」压一压\n\n'
            '操作得当约 80 周期可通关。祝你统治全球舆论 😏',
            target=None, anchor='center', dim=0.62),
    ]

    def __init__(self, game: 'GameUI'):
        self.game = game
        self.index = 0
        self.overlay: Optional[FloatLayout] = None
        self._hl: Optional[FloatLayout] = None
        self._dim_color = None
        self._dim_rect = None
        self.bubble: Optional[PixelPanel] = None
        self._bubble_title = None
        self._bubble_body = None
        self._bubble_next = None
        self._was_paused = False

    # ----------------------------------------------------------
    # 触发
    # ----------------------------------------------------------
    def maybe_start(self) -> None:
        """新游戏进入时调用：看过则不再弹。"""
        if engine.player is None or engine.player.seen_tutorial:
            return
        self._begin()

    def replay(self) -> None:
        """设置页「重看教程」：即使看过也重来。"""
        if self.overlay is not None:
            self._teardown()
        self._begin()

    def _begin(self) -> None:
        if self.overlay is not None:
            return
        self._was_paused = self.game.paused
        self.game.paused = True
        self.index = 0
        self._build_overlay()
        self._show(0)

    # ----------------------------------------------------------
    # 构建遮罩 / 高亮 / 气泡
    # ----------------------------------------------------------
    def _build_overlay(self) -> None:
        ov = FloatLayout(size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        # 半透明遮罩（吃点击，阻止误触游戏）
        dim = Widget(size_hint=(1, 1))
        with dim.canvas:
            self._dim_color = Color(*_DIM)
            self._dim_rect = Rectangle(pos=(0, 0), size=(ov.width, ov.height))
        dim.bind(pos=lambda i, v: self._redraw(),
                 size=lambda i, v: self._redraw())
        ov.add_widget(dim)
        # 高亮层（画目标控件的亮边框）
        self._hl = FloatLayout(size_hint=(1, 1))
        ov.add_widget(self._hl)
        # 讲解气泡
        self.bubble = self._build_bubble()
        ov.add_widget(self.bubble)
        # 空白点击 = 下一步
        ov.bind(on_touch_down=self._on_touch)
        # overlay 尺寸变化时（窗口缩放 / 首帧布局）重新定位气泡，避免越界
        ov.bind(size=lambda i, v: self._redraw())
        self.overlay = ov
        self.game.add_widget(ov)
        # ⚠️ Kivy 布局时序坑：bubble 子树建立时 inner 还是默认 100×100，
        # 子控件全按 100 基准布局；inner 变 720×400 后深层布局链不再执行
        # → 文字/按钮整体缩在左下角（与面板分离）。显式递归补全树布局。
        self._force_layout(self.bubble)
        Clock.schedule_once(lambda *_: self._force_layout(self.bubble), 0)
        self._redraw()

    def _build_bubble(self) -> PixelPanel:
        bw, bh = 720, 400            # 字号放大后气泡同步放大，避免正文被挤没
        panel = PixelPanel(size_hint=(None, None), size=(bw, bh),
                           bg=COLORS['panel'], border_color=_HILITE)
        # ⚠️ 必须给 inner 显式 pos_hint=(0,0)。
        # Kivy 的 FloatLayout.do_layout 只重排「声明了 pos_hint」的子控件
        # （见 floatlayout.py：pos 循环 `for key, value in c.pos_hint.items()`），
        # 没写 pos_hint 的子控件 pos 永远停在默认 (0,0) —— 而 Widget.pos 是
        # **窗口绝对坐标**。于是气泡面板挪到屏幕中央后，inner 仍钉在窗口左下角，
        # 于是正文/按钮整片渲染到左下角、与气泡框"分离"（新手教程错位的根因）。
        # make_modal 里的 content 正是靠 pos_hint={'x':0,'y':0} 才对齐，这里对齐同一约定。
        inner = FloatLayout(size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        self._bubble_title = mk_label('', font_size=FS_H3, color=COLORS['cyan'],
                                      halign='left', valign='top',
                                      markup=True,      # 标题含 [b] 标签，必须开 markup
                                      pos_hint={'x': 0.03, 'y': 0.84},
                                      size_hint=(0.94, 0.14))
        inner.add_widget(self._bubble_title)
        # 正文：auto_h_label 自增高（text_size=(w,None)），放进 ScrollView
        # 长文本绝不溢出气泡框；mk_label+手绑 texture_size 的旧写法会与
        # _bind_text_size 的 text_size=(w,h) 互锁在 10px 高（文字不可见）
        self._bubble_body = auto_h_label('', FS_BODY, COLORS['text'],
                                         markup=True)
        _wrap = BoxLayout(orientation='vertical')
        _wrap.add_widget(self._bubble_body)
        sv = ScrollView(bar_width=6, bar_color=COLORS['border_2'],
                        pos_hint={'x': 0.03, 'y': 0.16}, size_hint=(0.94, 0.66))
        sv.add_widget(_wrap)
        inner.add_widget(sv)
        # 底部按钮行
        self._bubble_skip = self._px_btn('跳过教程', 'plain', self.skip)
        self._bubble_skip.pos_hint = {'right': 0.60, 'y': 0.03}
        self._bubble_skip.size_hint = (None, None)
        inner.add_widget(self._bubble_skip)
        self._bubble_next = self._px_btn('下一步 →', 'on', self.next)
        self._bubble_next.pos_hint = {'right': 0.97, 'y': 0.03}
        self._bubble_next.size_hint = (None, None)
        inner.add_widget(self._bubble_next)
        panel.add_widget(inner)
        return panel

    @staticmethod
    def _px_btn(text: str, tone: str, cb) -> Button:
        """像素风按钮（避免反向 import main.make_button）。"""
        btn = Button(text=text, font_size=FS_CAP,
                     size_hint=(None, None), height=38,
                     width=120 if tone == 'plain' else 132)
        btn.background_normal = ''
        btn.background_color = (COLORS.get('panel_light', COLORS['panel'])
                                if tone == 'plain'
                                else hex_rgba(ST_FILL['on']))   # P2-5 收口：'on' 态填充令牌
        btn.color = (COLORS['text_mute'] if tone == 'plain' else COLORS['cyan'])
        add_pixel_border(btn, color=(COLORS['border_2']
                                     if tone == 'plain' else _HILITE))
        btn.bind(on_release=cb)
        return btn

    # ----------------------------------------------------------
    # 显示单步
    # ----------------------------------------------------------
    def _show(self, i: int) -> None:
        self.index = i
        step = self.STEPS[i]
        # 清理上一步可能打开的演示面板
        self._cleanup_panels()
        # 遮罩透明度
        if self._dim_color is not None:
            self._dim_color.rgba = (*_DIM[:3], step.dim)
        # 演示动作
        if step.action == 'select_cn':
            try:
                self.game.on_map_country_click('CN')
            except Exception:
                pass
        elif step.action == 'open_tech_page':
            # 让玩家在引导里就看到科技树（诊断结论：科技是第一加速器，
            # 但旧版引导完全没提，导致玩家 30 周期渗透仍 <20%）。
            try:
                self.game.open_page('tech')
            except Exception:
                pass
        # 文本
        self._bubble_title.text = f"[b]{step.title}[/b]"
        self._bubble_body.text = step.body
        self._bubble_next.text = ('开始游戏 →'
                                  if i == len(self.STEPS) - 1 else '下一步 →')
        # 每步都补一次气泡全树布局（见 _build_overlay 的时序注释）
        if self.bubble is not None:
            self._force_layout(self.bubble)
            Clock.schedule_once(lambda *_: self._force_layout(self.bubble), 0)
        self._redraw()

    def _redraw(self) -> None:
        if self.overlay is None or self._hl is None or self.bubble is None:
            return
        ov = self.overlay
        step = self.STEPS[self.index]
        # 遮罩铺满
        if self._dim_rect is not None:
            self._dim_rect.pos = (0, 0)
            self._dim_rect.size = (ov.width, ov.height)
        # 高亮目标边框
        self._hl.canvas.clear()
        rect = self._target_rect(step.target)
        if rect is not None:
            x, y, w, h = rect
            pad = 6
            with self._hl.canvas:
                Color(*_HILITE)
                Line(points=[x - pad, y - pad, x + w + pad, y - pad,
                            x + w + pad, y + h + pad, x - pad, y + h + pad],
                     close=True, width=3)
        # 气泡定位
        self._place_bubble(step, rect)

    def _target_rect(self, target: Optional[str]):
        """返回目标控件在 **overlay 局部坐标系** 下的 (x, y, w, h)。

        ⚠️ Kivy 的 ``Widget.pos`` 是**窗口绝对坐标**（不是父控件相对坐标），
        所以取窗口坐标应当直接读 ``w.pos``。旧写法 ``w.to_window(0, 0)``
        语义是「把**父坐标** (0,0) 换算到窗口」→ 返回的是父链偏移（≈(0,0)），
        等于每次都把高亮框画到屏幕左下角。这里改为直接用 ``w.pos`` 再转局部。
        """
        if not target:
            return None
        if target.startswith('skill:'):
            w = self.game.skill_cards.get(target.split(':', 1)[1])
        else:
            w = getattr(self.game, target, None)
        if w is None:
            return None
        lx, ly = self.overlay.to_local(w.x, w.y)   # 绝对(窗口) → overlay 局部
        return (lx, ly, w.width, w.height)

    def _place_bubble(self, step: TutorialStep,
                      rect: Optional[tuple]) -> None:
        """把气泡放进 overlay 可视区内（绝不出画面）。

        - 横向：居中；若窗口比气泡窄则贴边并夹紧（气泡不会超出右沿）。
        - 纵向：top 锚点放目标上方，放不下就翻到目标下方；bottom 锚点放技能带上方。
        - 所有坐标都在 overlay 局部系（与 _target_rect 一致）。

        ⚠️ 布局时序坑（教程"文字在左下、面板在中"的根因）：
        ``_redraw`` 可能在 overlay 尺寸尚未定稿时被调用（首帧 overlay 仍是
        默认值），此时若直接按错误尺寸摆放会把气泡钉到 (12,12)；而随后
        overlay 尺寸变化只触发 ``_redraw`` 重设 ``bubble.pos``——``bubble`` 是
        FloatLayout，**直接改 pos 不会重新布局它的子控件**（inner/标题/按钮
        仍停在旧坐标），于是出现"面板已居中、文字却留在左下角"的分离现象。
        对策：①overlay 无有效尺寸时**延后一帧**再摆；②每次摆完强制
        ``_force_layout(bubble)``，让子树跟着面板一起归位。
        """
        W, H = self.overlay.width, self.overlay.height
        if W < 1 or H < 1:
            # 尺寸还没定稿 → 下一帧重试（Clock 已在 _redraw 的调用链上）
            Clock.schedule_once(lambda *_: self._redraw(), 0)
            return
        bw, bh = self.bubble.size
        margin = 12
        # 横向：默认居中，贴近目标时向目标对齐
        if rect is not None:
            cx = rect[0] + rect[2] / 2.0
            x = cx - bw / 2.0
        else:
            x = (W - bw) / 2.0
        x = max(margin, min(W - bw - margin, x))
        # 纵向
        if step.anchor == 'top' and rect is not None:
            y = rect[1] + rect[3] + margin          # 目标上方
            if y + bh > H - margin:                  # 上方放不下 → 翻到下方
                y = rect[1] - bh - margin
        elif step.anchor == 'bottom':
            y = margin + self.game.SKILLBAR_H + margin
        else:
            y = (H - bh) / 2.0
        y = max(margin, min(H - bh - margin, y))
        if tuple(self.bubble.pos) != (x, y):
            self.bubble.pos = (x, y)
        # 关键：面板挪位后强制重排子树，避免 inner/标题/按钮与面板分离
        self._force_layout(self.bubble)
        Clock.schedule_once(lambda *_: self._force_layout(self.bubble), 0)

    # ----------------------------------------------------------
    # 交互
    # ----------------------------------------------------------
    def _on_touch(self, instance, touch) -> bool:
        # 只处理左/右键；点气泡区域内不前进（交给按钮）
        if touch.button not in ('left', 'right'):
            return False
        if self.bubble.collide_point(*touch.pos):
            return False
        self.next()
        return True

    def next(self, *args) -> None:
        if self.overlay is None:
            return
        if self.index >= len(self.STEPS) - 1:
            self.finish()
        else:
            self._show(self.index + 1)

    def skip(self, *args) -> None:
        # ⚠️ on_release 会把按钮实例作为首个参数传入（Kivy 标准行为），
        # 必须接 *args，否则点击会抛 TypeError 导致「跳过」按钮失效。
        self.finish()

    def finish(self) -> None:
        if engine.player is not None:
            engine.player.seen_tutorial = True
            try:
                save_manager.save()
            except Exception:
                pass
        self._teardown()

    def _teardown(self) -> None:
        self._cleanup_panels()
        if self.overlay is not None:
            self.game.remove_widget(self.overlay)
            self.overlay = None
        self.game.paused = self._was_paused

    def _cleanup_panels(self) -> None:
        """关闭引导演示打开的面板（检视卡 / 科技树页），避免残留。"""
        try:
            if getattr(self.game, '_inspector', None) is not None:
                self.game._close_inspector()
        except Exception:
            pass
        try:
            # 科技树演示步会打开全屏页；不关掉会盖在后续步骤上。
            page = getattr(self.game, '_page', None)
            if page is not None and getattr(page, 'page_name', '') == 'tech':
                self.game.close_page()
        except Exception:
            pass
