"""
ui_v4_common.py - UI 侧运行统计与小按钮工厂

2026-09-13 从 ui_v4_screens.py（2327 行，长期占据行数白名单）拆出。
本模块是 ui_v4_* 家族的**公共底座**：不依赖任何其他 ui_v4_* 模块，
因此可被 panels / cards / canvas / syspages / screens 任意引用而无循环。

内容：
    UiStats   —— UI 层趋势采样缓存（引擎只维护当前值，图表需要历史序列）
    small_btn —— 页面内小按钮工厂（设计稿 .px-btn.sm）

设计纪律：
    - 只画，不决策；数值由 main.py 通过 update()/refresh() 喂进来；
    - 颜色/尺寸全部来自 ui_v4 令牌，不在此硬编码新色值。
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
            self.global_unlocked.append(0.0)  # 计数异常 → 记 0：曲线缺一点好过崩溃

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

        !️ 用「全局最大值」而非「末值」做分母：顶栏的下载量/算力是单调递增的，
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


# ============================================================
# S05 技能页面
# ============================================================
