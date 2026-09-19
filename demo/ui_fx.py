"""
ui_fx.py - 统一动效层（P0-6：让每个周期"有东西在动"，玩家反馈 5）

设计原则（**绝不破坏游戏逻辑**）：
- 本模块只做「视觉表现」，不读写任何游戏状态；调用方给目标控件与数值，
  动效跑完即自动清理，不留下绑在控件上的定时器。
- 全部动效尊重 ``ui_shared.REDUCE_MOTION``：开启「动效减弱」时退化为
  **1 帧状态切换**（不产生任何 Animation / Clock 调度），既满足无障碍
  需求，也顺带解决低配机卡顿。
- 动效必须**可重入**：同一个控件被连续触发（例如快速连点技能）时，
  前一个动效先被取消再开新的，避免 Animation 叠加把 opacity/pos 撞坏。

与项目既有约定的关系：
- ``ui_popups.show_top_toast`` 已自带淡入淡出（不重复造）；
- ``ui_commissions`` 芯片条自带重建；本模块专注「数值变化 + 操作反馈」。
"""
from __future__ import annotations

from typing import Callable, Optional

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

import ui_shared as ST
from ui_shared import COLORS
from pixel_ui import hex_rgba


# 动效时长统一在这里收口（减弱模式下一律走 _disabled 分支）
# P2-6 光敏安全（WCAG 2.3.1：闪烁 ≤3 次/秒）：单脉冲 = 降 + 回两程，
# 旧值 0.16s → 单脉冲 0.32s ≈ 3.1Hz 贴红线；0.22s → 0.44s ≈ 2.3Hz，留足余量。
DUR_PULSE = 0.22
DUR_COUNT = 0.45
DUR_SHAKE = 0.22


def motion_on() -> bool:
    """动效是否启用（读全局开关，不缓存 —— 设置页可随时切换）。"""
    return not ST.REDUCE_MOTION


def _cancel(widget: Widget, *props: str) -> None:
    """取消 widget 上进行中的 Animation（避免连续触发时属性互相覆盖）。

    Kivy 的 ``Animation.cancel_all`` 会连同其他库绑定的动画一起取消，
    所以这里只针对调用方关心的属性做 ``stop_all`` 之外的精确清理：
    直接调 ``Animation.cancel_all(w, *props)``。
    """
    try:
        Animation.cancel_all(widget, *props)
    except Exception:
        pass  # 控件可能已被销毁；动效层永不影响游戏逻辑


def _rgba(color, alpha: Optional[float] = None):
    """把颜色统一成 Kivy 的 RGBA 四元组。

    !️ 项目里颜色有两种形态，混用会直接抛 AttributeError：
    - ``COLORS['cyan']`` 等调色板值 **已经是 RGBA 元组**；
    - ``'#4ec9b0'`` 这类字面量是 **hex 字符串**（要用 hex_rgba 转）。
    动效层会被两边的调用方喂色，所以这里做一次归一化。
    """
    if color is None:
        color = COLORS['cyan']
    if isinstance(color, str):
        return hex_rgba(color, 1.0 if alpha is None else alpha)
    try:
        r, g, b = color[0], color[1], color[2]
        a = color[3] if len(color) > 3 else 1.0
        return (r, g, b, a if alpha is None else alpha)
    except Exception:
        return COLORS['cyan']


# ============================================================
# 基础原语
# ============================================================
def pulse(widget: Widget, color=None, scale_alpha: float = 0.35,
          duration: float = DUR_PULSE) -> None:
    """亮度脉冲：快速降低再恢复 opacity（用于「这一下生效了」的确认感）。

    用 opacity 而非缩放：Kivy 的 Widget 没有 scale 属性，改 size 会触发
    重新布局（顶栏/技能带会跳动），opacity 是唯一安全且廉价的脉冲通道。

    Args:
        widget: 目标控件。
        color: 备用（Kivy 无 tint 通道，保留参数以便日后换实现）。
        scale_alpha: 最低透明度（0.35 = 降到 35% 再回弹）。
        duration: 单程时长。
    """
    if not motion_on():
        return
    _cancel(widget, 'opacity')
    base = 1.0
    anim = (Animation(opacity=max(0.05, scale_alpha), duration=duration,
                      t='out_quad')
            + Animation(opacity=base, duration=duration, t='in_quad'))
    anim.start(widget)


def shake(widget: Widget, dx: float = 4.0, rounds: int = 1,
          duration: float = DUR_SHAKE) -> None:
    """左右抖动：用于「操作被拒绝」（算力不足 / 技能冷却中）。

    P2-6 光敏安全：rounds 2→1。rounds=2 时每段 0.055s、方向反转约
    15 次/秒，属高频抖动；rounds=1 单次抖动 4 段 × 0.11s（总 0.44s，
    约 7 次反转/秒），拒绝感仍在且明显温和。

    !️ 改 pos 会与 FloatLayout 的 pos_hint 打架（下一帧布局会拉回去），
    所以这里抖动的是 ``x`` 相对量并**显式恢复原值**，且只用于
    size_hint=(None,None) 的固定尺寸控件（芯片/按钮）。
    """
    if not motion_on():
        return
    _cancel(widget, 'x')
    x0 = widget.x
    anim = Animation(x=x0 - dx, duration=duration / (rounds * 2), t='in_out_quad')
    for _ in range(rounds):
        anim += Animation(x=x0 + dx, duration=duration / (rounds * 2),
                          t='in_out_quad')
        anim += Animation(x=x0 - dx, duration=duration / (rounds * 2),
                          t='in_out_quad')
    anim += Animation(x=x0, duration=duration / (rounds * 2), t='in_out_quad')
    anim.start(widget)


def count_up(label: Label, from_value: float, to_value: float,
             fmt: Callable[[float], str],
             duration: float = DUR_COUNT) -> None:
    """数值滚动：从 from 平滑滚到 to（顶栏统计用）。

    Args:
        label: 目标 Label（直接改 .text）。
        from_value / to_value: 起止数值。
        fmt: 数值 → 文本的格式化函数（各统计单位不同，由调用方决定）。
        duration: 滚动时长。

    !️ 用 Clock 每帧改 text 会触发 texture_update，长时间高频会掉帧；
    因此滚动只在 motion_on() 且**数值确有变化**时才跑，且时长很短（0.45s）。
    """
    if not motion_on():
        label.text = fmt(to_value)
        return
    _cancel(label, 'opacity')
    label.text = fmt(to_value)          # 先落终值，避免 finally 缺失时停在中间
    if abs(to_value - from_value) < 1e-9:
        return
    steps = 12
    state = {'i': 0}

    def _tick(_dt):
        state['i'] += 1
        i = state['i']
        if i >= steps:
            label.text = fmt(to_value)
            return False
        t = i / steps
        # ease-out：前快后慢，收尾更"稳"
        e = 1 - (1 - t) * (1 - t)
        label.text = fmt(from_value + (to_value - from_value) * e)
        return True

    Clock.schedule_interval(_tick, max(duration / steps, 1 / 60.0))


# ============================================================
# 组合动效（业务语义）
# ============================================================
# P2-5 同屏信标并发上限：纯表现层参数（只影响"光环动画同时最多几个"），
# 不参与任何玩法数值运算，因此**不进 balance.TUNE** —— 表现层参数进
# 数值调参表会让平衡同学误以为是可调玩法变量，放模块常量并在此注明。
# 20 国同时触发时旧实现会叠 20 个动画 Widget（每帧都在改 size/pos/opacity），
# 上限 6 个：超出时挤掉最旧的（反馈永远是最新的，且并发有界）。
BEACON_MAX_LIVE = 6
_beacons = []          # 活跃信标登记 [(ring, host, anim)，完成/被挤掉即摘除]


def _beacon_forget(ring, host, anim) -> None:
    """信标自然播完时从登记表摘除（配合 on_complete）。"""
    try:
        _beacons.remove((ring, host, anim))
    except ValueError:
        pass


def _beacon_kill(entry) -> None:
    """强制终止一个信标：取消动画并从宿主摘除（cancel 不触发 on_complete）。"""
    ring, host, anim = entry
    try:
        anim.cancel(ring)
    except Exception:
        pass  # 信标可能已被 on_complete 清理，二次 cancel 属预期竞态
    try:
        host.remove_widget(ring)
    except Exception:
        pass  # 宿主可能已销毁，移除失败即无事可做


def beacon(target: Widget, code: str,
           container: Optional[Widget] = None) -> None:
    """在地图上给某国打一个脉冲光环。

    需要 ``target`` 暴露 ``country_center(code)``（返回**容器局部坐标**）。
    光环挂在 ``container``（默认 = ``target`` 自身）上。

    !️ 注意：求坐标的对象与承载光环的容器**通常是两个不同的东西** ——
    前者是 GameUI（有 country_center 方法），后者是地图舞台/准星层
    （FloatLayout）。早期版本把二者混为一谈，导致光环永远挂不上去。
    """
    if not motion_on() or target is None:
        return
    fn = getattr(target, 'country_center', None)
    if not callable(fn):
        return
    try:
        center = fn(code)
    except Exception:
        return
    if not center:
        return
    host = container if container is not None else target
    ring = Widget(size_hint=(None, None))
    ring.size = (18, 18)
    ring.pos = (center[0] - 9, center[1] - 9)
    with ring.canvas:
        Color(*_rgba(COLORS['cyan']))
        _r = Rectangle(pos=ring.pos, size=ring.size)
    host.add_widget(ring)

    def _clean(*_a):
        _beacon_forget(ring, host, anim)
        try:
            host.remove_widget(ring)
        except Exception:
            pass  # 同上：清理竞态下失败即无事可做

    anim = (Animation(size=(56, 56), pos=(center[0] - 28, center[1] - 28),
                      opacity=0.0, duration=0.6, t='out_quad'))
    anim.bind(on_complete=_clean)
    # P2-5 并发上限：登记新信标后，把最旧的挤掉（cancel + 摘除）
    entry = (ring, host, anim)
    _beacons.append(entry)
    while len(_beacons) > BEACON_MAX_LIVE:
        _beacon_kill(_beacons.pop(0))
    anim.start(ring)
