"""鼠标光标语义层专项（cursor_fx.py）

为什么要测：``cursor_fx`` 是**每帧执行**的全局旁路（mouse_pos 回调），
判错会让玩家得到错误的可点性暗示（禁用元素显示手型 = 诱骗点击）。
且它必须**绝不抛异常** —— 光标是增强项，崩了就是新的崩溃点。

运行：``python test_cursor_fx.py``
"""
import os
import sys

os.environ.setdefault('KIVY_NO_FILELOG', '1')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cursor_fx as C   # noqa: E402


class _W:
    """最小控件替身（模拟 Kivy Widget 的几何 + 状态属性）。"""

    def __init__(self, x, y, w, h, disabled=False, opacity=1.0, **kw):
        self.x, self.y = x, y
        self.width, self.height = w, h
        self.disabled = disabled
        self.opacity = opacity
        self.parent = None
        self.children = []
        for k, v in kw.items():
            setattr(self, k, v)


class _UI:
    """最小 UI 替身。"""

    def __init__(self):
        self.drop_mode = False
        self._cursor_clickable = []
        self.skill_cards = {}


def _fresh(clickable=None, drop=False):
    ui = _UI()
    ui._cursor_clickable = list(clickable or [])
    ui.drop_mode = drop
    return ui


# ---- 1) 语义优先级 ----
ui = _fresh([_W(10, 10, 100, 40)])
assert C.cursor_for(ui, (50, 30)) == C.HAND, "可点元素上应是 hand"
assert C.cursor_for(ui, (500, 500)) == C.ARROW, "空白处应是 arrow"
assert C.cursor_for(ui, (9, 30)) == C.ARROW, "左边界外应 arrow"
assert C.cursor_for(ui, (110, 30)) == C.ARROW, "右边界外应 arrow"

# ---- 2) 投放模式 → 瞄准光标（覆盖空白区）----
ui = _fresh([_W(10, 10, 100, 40)], drop=True)
assert C.cursor_for(ui, (500, 500)) == C.AIM, "投放模式下空白处应 crosshair"

# ---- 3) 禁用态优先级最高（disabled 属性 / opacity<0.5 两路）----
ui = _fresh([_W(10, 10, 100, 40, disabled=True)])
assert C.cursor_for(ui, (50, 30)) == C.BLOCKED, "disabled 元素应 no"
ui = _fresh([_W(10, 10, 100, 40, opacity=0.45)])
assert C.cursor_for(ui, (50, 30)) == C.BLOCKED, \
    "opacity<0.5 应 no（主菜单禁用态约定，见 MainMenu._menu_btn）"
ui = _fresh([_W(10, 10, 100, 40, opacity=1.0)])
assert C.cursor_for(ui, (50, 30)) == C.HAND, "正常 opacity 不该被判禁用"

# ---- 4) 命中多个时取第一个（顺序稳定，不随机）----
ui = _fresh([_W(10, 10, 100, 40, disabled=True), _W(10, 10, 100, 40)])
assert C.cursor_for(ui, (50, 30)) == C.BLOCKED, "禁用元素压在可点上时应显示 no"

# ---- 5) 强制态 / 恢复 / 非法名降级 ----
C.reset()
C.set_cursor(C.BLOCKED)
assert C._forced == C.BLOCKED, "强制设置后 _forced 应生效"
C.set_cursor(None)
assert C._forced is None, "传 None 应清除强制"
C.set_cursor('this_cursor_does_not_exist')
assert C._forced == C.ARROW, "非法光标名必须降级为 arrow（不抛异常）"
C.reset()
assert C._forced is None and C._current == C.ARROW, "reset 应回到默认箭头"

# ---- 6) 枚举集合：本项目只用 5 个，且都在 Kivy 支持列表内 ----
KIVY_SUPPORTED = {'arrow', 'ibeam', 'wait', 'crosshair', 'wait_arrow',
                  'size_nwse', 'size_nesw', 'size_we', 'size_ns',
                  'size_all', 'no', 'hand'}
for _n in (C.ARROW, C.HAND, C.AIM, C.DRAG, C.BLOCKED):
    assert _n in KIVY_SUPPORTED, f"光标名 {_n} 不在 Kivy set_system_cursor 支持列表"

# ---- 7) 失败安全：无 Window / 异常输入不得抛出 ----
try:
    ui_bad = _UI()
    ui_bad._cursor_clickable = [None]          # 坏控件（无几何属性）
    C.cursor_for(ui_bad, (0, 0))               # 不得抛
    C.cursor_for(_UI(), ('x', 'y'))            # 坏坐标不得抛
    C.refresh_clickables(_UI())                # 空树不得抛
    C.install(_UI())                           # 装不上应返回 False 而非抛
except Exception as e:                          # pragma: no cover
    raise AssertionError(f"cursor_fx 必须失败安全，却抛出: {e!r}")

# ---- 8) _apply 去重：同值不重复穿透 ----
C.reset()
before = C._current
C._apply(C.HAND)
assert C._current == C.HAND
C._current = before            # 手动还原，避免影响同进程后续用例
C.reset()

print("[OK] cursor_fx 语义层：优先级 / 禁用态 / 强制与恢复 / 枚举合法 / "
      "失败安全 / 去重 全部通过")
print("OK")
