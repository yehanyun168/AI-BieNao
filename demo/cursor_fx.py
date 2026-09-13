"""鼠标光标语义层（方案 A：SDL 系统光标映射）

设计动机
--------
项目此前**完全没有光标反馈** —— 指针在按钮上、地图国家上、技能卡上、
禁用元素上全是一根默认箭头。玩家只能靠「点了有没有反应」来判断可点性，
对「这个国家能投放吗」「这张卡还能用吗」这类问题毫无预判。

为什么用系统光标（而不是自定义光标图）
--------------------------------------
Kivy 原生**不支持自定义光标图片**：
- ``Window.set_system_cursor(name)`` 只接受字符串枚举（SDL 预定义）；
- ``Window.set_custom_cursor()`` 依赖后端且跨平台不一致。

而本项目 UI 是 100% 代码绘制、不进配色令牌的纯图元系统 —— 自绘一个跟随
鼠标的 Widget 成本明显更高（要处理层级/穿透/裁剪/缩放吸附）。因此方案 A
（系统光标语义映射）是**零素材成本、跨平台一致**的正解；12 个枚举在
Windows 上全部原生映射（部分平台缺项会自动回退，见 Kivy 文档表格）。

失败安全
--------
本模块所有对外函数**不抛异常**。拿不到 Window / 后端不支持光标 / 名字非法，
一律静默降级为「不改变光标」—— 光标是增强项，绝不能成为新的崩溃点。
（与 ``sfx.py`` 的失败安全设计同源。）

用法
----
    import cursor_fx
    cursor_fx.install(ui)        # 绑定 mouse_pos，按语义自动切换
    cursor_fx.set('crosshair')   # 局部强制（如投放模式），None = 交回自动
"""
from __future__ import annotations

# ---- 语义 → Kivy/SDL 系统光标名 ----
# Kivy 支持的完整枚举：arrow / ibeam / wait / crosshair / wait_arrow /
# size_nwse / size_nesw / size_we / size_ns / size_all / no / hand
# 本项目只用其中 4 个，语义清晰且各平台都支持：
#   hand      —— 可点（按钮 / 卡片 / 存档槽 / 地图国家）
#   crosshair —— 投放瞄准（精确指向某个国家，比箭头更有「瞄准」感）
#   size_all  —— 按住拖拽中（移动/搬运的通用隐喻）
#   no        —— 明确不可用（禁用态 / 算力不足 / 该国家不适格）
ARROW = 'arrow'
HAND = 'hand'
AIM = 'crosshair'
DRAG = 'size_all'
BLOCKED = 'no'

_ALLOWED = frozenset((ARROW, HAND, AIM, DRAG, BLOCKED))

_current: str = ARROW        # 当前已设置的光标（避免重复调用，见 _apply）
_forced: str | None = None   # 局部强制覆盖（投放模式等），None = 自动判定
_last_auto: str = ARROW      # 最近一次自动判定结果（供恢复用）


def _apply(name: str) -> None:
    """真正调用 Kivy 设置光标。只在变化时调用，且永不抛异常。

    为什么去重：``mouse_pos`` 每帧触发，无条件调用会每秒几十次穿透到
    SDL —— 纯浪费。SDL 侧本就做了去重，但我们省掉的是 Python → C 的调用。
    """
    global _current
    if name == _current:
        return
    try:
        from kivy.core.window import Window
        Window.set_system_cursor(name)
        _current = name
    except Exception:
        # 无 Window（headless / 测试）/ 后端不支持光标 / 名字非法 → 静默降级。
        # 记下 _current 以免每帧重试同一个失败调用。
        _current = name


def set_cursor(name: str | None) -> None:
    """设置光标。``name`` 传 None 表示清除强制、交回自动判定。

    非法名字一律降级为 arrow（不抛异常）。
    """
    global _forced, _last_auto
    if name is None:
        _forced = None
        _apply(_last_auto)
        return
    safe = name if name in _ALLOWED else ARROW
    _forced = safe
    _apply(safe)


def reset() -> None:
    """恢复默认箭头并清除强制（离开对局 / 回主菜单时用）。"""
    global _forced, _last_auto, _current
    _forced = None
    _last_auto = ARROW
    _current = ARROW
    _apply(ARROW)


# ---------------------------------------------------------------
# 自动判定：按命中优先级从「最具体」到「最泛」
# ---------------------------------------------------------------
def _walk(root, out, depth=0):
    """深度遍历控件树，收集「可点」控件。

    为什么用遍历而不是让每个创建点自己登记：
    创建点分散在 main / ui_pages / ui_v4 / ui_modal 等 8 个文件里，逐个改造
    是侵入式的、且以后新增控件很容易漏登记。遍历控件树是**零侵入**的 ——
    新增控件自动被覆盖，代价是每帧一次遍历（实测树规模数百节点，可忽略）。

    「可点」判据（任一即算）：
      * 是 Button 且有 on_release / on_press 绑定
      * 显式带 on_click 属性（本项目 StrokePanel 系卡片的约定）
      * 显式带 _cursor_hand 标记（给自绘控件留的手动入口）
    """
    if depth > 12:          # 防御：异常深树（正常 <8 层）
        return
    try:
        kids = root.children
    except Exception:
        return
    for w in kids:
        try:
            is_btn = w.__class__.__name__.endswith('Button') or \
                hasattr(w, 'on_release')
            has_handler = bool(getattr(w, 'on_release', None)) or \
                bool(getattr(w, 'on_press', None)) or \
                bool(getattr(w, '_on_pick', None)) or \
                bool(getattr(w, 'on_click', None)) or \
                bool(getattr(w, '_cursor_hand', False))
            if is_btn and has_handler:
                out.append(w)
            _walk(w, out, depth + 1)
        except Exception:
            continue


def refresh_clickables(ui) -> int:
    """重扫控件树，刷新 ``ui._cursor_clickable``。返回收集到的数量。

    在「页面/弹窗切换后」调用即可（不必每帧）—— 控件树变动远低于帧率。
    """
    try:
        out = []
        _walk(ui, out)
        ui._cursor_clickable = out
        return len(out)
    except Exception:
        return 0


def _hit(w, pos) -> bool:
    """窗口坐标是否落在控件矩形内（沿 parent 链累加，与 ui_input 同口径）。

    不用 to_window/to_widget：其 ``relative`` 语义各版本有差异，而本应用
    控件树是纯布局容器（无 scatter / 无旋转缩放），累加即窗口坐标。

    上界取**开区间**（``< x + width``）：相邻控件的右边界与下一个的左边界
    是同一个数，若两边都闭合就会「同时命中」两个控件，光标语义会飘。
    """
    try:
        x, y = w.x, w.y
        p = w.parent
        while p is not None:
            x += p.x
            y += p.y
            p = p.parent
        return x <= pos[0] < x + w.width and y <= pos[1] < y + w.height
    except Exception:
        return False        # 控件树中途销毁/重建 → 视为未命中


def _is_disabled(w) -> bool:
    """控件是否处于「明确不可用」态。

    判定用 disabled 属性（Kivy 标准）+ 主菜单自己用的 opacity<0.5 约定。
    """
    try:
        if bool(getattr(w, 'disabled', False)):
            return True
        return float(getattr(w, 'opacity', 1.0)) < 0.5
    except Exception:
        return False


def _any_hit(widgets, pos) -> bool:
    for w in widgets:
        if _hit(w, pos):
            return True
    return False


def cursor_for(ui, pos) -> str:
    """算出 ``pos`` 处应显示的光标名（纯函数，不写状态，便于测试）。

    优先级（高 → 低）：
      1. 禁用元素          → BLOCKED（no）
      2. 投放模式下的地图   → AIM（crosshair）
      3. 可点元素（按钮/技能卡/存档槽/国家）
                          → 但禁用则 BLOCKED，否则 HAND
      4. 其它              → ARROW
    """
    # 1) 禁用态最优先：哪怕压在别的可点元素上也应显示「不可用」
    for attr in ('_cursor_disabled', '_disabled_widgets'):
        w = getattr(ui, attr, None)
        if isinstance(w, (list, tuple, set)) and _any_hit(w, pos):
            return BLOCKED
    one = getattr(ui, '_cursor_disabled', None)
    if not isinstance(one, (list, tuple, set)) and one is not None and _hit(one, pos):
        return BLOCKED

    # 2) 投放模式：瞄准某个国家
    if getattr(ui, 'drop_mode', False):
        return AIM

    # 3) 可点元素
    for attr in ('_cursor_clickable', 'skill_cards'):
        coll = getattr(ui, attr, None)
        if isinstance(coll, dict):
            for w in coll.values():
                if _hit(w, pos):
                    return BLOCKED if _is_disabled(w) else HAND
        elif isinstance(coll, (list, tuple, set)):
            for w in coll:
                if _hit(w, pos):
                    return BLOCKED if _is_disabled(w) else HAND

    return ARROW


_refresh_counter = 0


def _on_mouse_pos(ui, _win, pos) -> None:
    """``mouse_pos`` 回调：每帧算一次语义并应用（强制态优先）。

    顺带低频重扫控件树（每 30 帧 ≈ 0.5s 一次）：页面/弹窗切换后新控件
    需要进集合，但又不必每帧遍历。比在 8 个创建点手动登记更不易漏。
    """
    global _last_auto, _refresh_counter
    try:
        _refresh_counter += 1
        if _refresh_counter % 30 == 1:
            refresh_clickables(ui)
        if _forced is not None:
            return                    # 强制态生效中，不覆盖
        want = cursor_for(ui, pos)
        if want != _last_auto:
            _last_auto = want
            _apply(want)
    except Exception:
        pass        # 纯展示增强路径：失败只表现为本帧光标不更新


def install(ui) -> bool:
    """给 ``ui`` 装上鼠标光标语义层。返回是否装成功（失败不影响功能）。"""
    try:
        from kivy.core.window import Window
        refresh_clickables(ui)        # 先扫一次，避免首帧空集合
        Window.bind(mouse_pos=lambda w, p: _on_mouse_pos(ui, w, p))
        return True
    except Exception:
        return False
