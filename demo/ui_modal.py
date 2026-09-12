"""
ui_modal.py - 通用弹窗 / 小件构建器（拆分自 main.py）

内容：make_button / _purge_lingering_modals / make_modal / _wire_close /
      auto_h_label / modal_header
只依赖 ui_v4 与 ui_shared（更低层），禁止反向 import。
（2026-09-11：``hline`` 已下移到 ui_v4，因 ui_v4_screens L5 不能引 L7 的 ui_modal。）
"""
from typing import Callable

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

from pixel_ui import PixelPanel, add_pixel_border
import ui_v4 as U
from ui_v4 import PxChip, mk_label
from ui_shared import COLORS


# ============================================================
# 通用小件
# ============================================================
def make_button(text: str, font_size: float = 16, height: float = 48,
                bg=None, on_release=None) -> Button:
    """统一像素风按钮（弹窗 / 页面里用）"""
    btn = Button(text=text, font_size=font_size, size_hint_y=None, height=height)
    btn.background_normal = ''
    btn.background_color = bg or COLORS['panel_light']
    btn.color = COLORS['text']
    add_pixel_border(btn, color=COLORS['border_2'])
    if on_release is not None:
        btn.bind(on_release=on_release)
    return btn


def _purge_lingering_modals() -> None:
    """同步强制移除窗口上所有残留的 ModalView（含淡出动画中的）。

    ``ModalView.dismiss()`` 只启动 0.4s 淡出动画，真正的移除发生在动画结束
    回调里。动画期间旧弹窗（及其半透明遮罩）仍在 ``Window.children`` 上，
    会导致：①连续弹窗时遮罩叠加成近纯黑；②无头/截图环境（只 ``Clock.tick``
    不 sleep）动画永不完成、旧窗永久残留。这里直接摘除，幂等安全。
    """
    # 三个清理步骤逐项吞错：单个旧弹窗清理失败不阻塞其余（本函数幂等，重复清理无副作用）
    for w in list(getattr(Window, 'children', []) or []):
        if isinstance(w, ModalView):
            try:
                w.dismiss()
            except Exception:
                pass
            try:
                w._real_remove_widget()
            except Exception:
                pass
            if w.parent is not None:
                try:
                    w.parent.remove_widget(w)
                except Exception:
                    pass


def make_modal(content: Widget, size_hint=(0.6, 0.7), auto_dismiss: bool = True,
               skin: str = '', on_close: Callable = None,
               close_on_outside: bool = True) -> Popup:
    """像素风模态弹窗（设计稿 .modal：半透明遮罩 + 硬投影浮起面板）。

    Args:
        content: 内容 widget（自绘面板，纵向 BoxLayout）。
        size_hint: 面板相对**窗口**的尺寸**上限**比例（遮罩铺满全窗）。
        auto_dismiss: 预留参数（当前点遮罩由 close_on_outside 控制）。
        skin: 'win' / 'lose' / 'neutral' / ''（决定边框色，设计稿 .modal.*）。
        on_close: 关闭按钮回调；缺省时关闭按钮直接 ``popup.dismiss()``。
        close_on_outside: True 时点击面板外的遮罩空白处也能关闭（✕ 之外的
            第二条关闭路径，符合通用弹窗习惯）。事件类弹窗可传 False 防误关。
    """
    # 先清掉窗口上残留的旧弹窗：dismiss() 的 0.4s 淡出期间旧遮罩仍在树上，
    # 若此时又弹一个新窗，两层 0.55 黑遮罩叠加会把面板压成近纯黑（难看且
    # 像是"面板没画出来"）。这里同步强制移除，保证任意时刻只有一层遮罩。
    _purge_lingering_modals()

    border = {'win': COLORS['cyan'], 'lose': COLORS['red'],
              'neutral': COLORS['yellow']}.get(skin, COLORS['border_2'])
    panel = PixelPanel(bg=COLORS['panel'], border_color=border, shadow=True)
    content.size_hint = (1, 1)
    content.pos_hint = {'x': 0, 'y': 0}
    panel.add_widget(content)

    # 遮罩层：铺满整个弹窗区域（=全窗），让面板从背景「浮起」，
    # 与 v0.2/v0.3 的可视化设计风格一致（之前缺遮罩 + 缺硬投影 = 风格割裂）。
    root = FloatLayout()
    with root.canvas.before:
        Color(0, 0, 0, 0.55)
        root._dim = Rectangle(pos=root.pos, size=root.size)
    root.bind(pos=lambda i, v: setattr(i._dim, 'pos', v),
              size=lambda i, v: setattr(i._dim, 'size', v))

    # 点击「面板外」的遮罩空白 → 关闭。用面板矩形碰撞判定，不干扰面板内交互。
    _outside = {'enabled': bool(close_on_outside), 'popup': None, 'panel': None}

    def _on_root_touch(_inst, touch):
        if not _outside['enabled'] or getattr(touch, 'grab_current', None):
            return False                    # 已被面板内控件接管 → 不处理
        pop = _outside['popup']
        pnl = _outside['panel']
        if pop is None or pnl is None:
            return False
        if pnl.collide_point(*touch.pos):
            return False                    # 点在面板内 → 交给面板处理
        # 点在面板外的遮罩上：关闭弹窗（吞掉该触摸，避免穿透到下层）。
        # 立即关闭 enabled，防止 0.4s 淡出动画期间连点触发重复 dismiss。
        _outside['enabled'] = False
        pop.dismiss()
        return True

    root.bind(on_touch_down=_on_root_touch)

    panel.size_hint = (None, None)

    # 内容侧合计高度：header + hline + body + footer。
    # body 包在 ScrollView 里（size_hint_y=1 弹性），其「自然高度」要从内部
    # BoxLayout 的 minimum_height 取，否则量到 0 → 高度按上限铺满 = 留白。
    def _scroll_intrinsic_h(scroll: Widget) -> float:
        for ch in scroll.children:                 # ScrollView 通常只有一个子
            mh = getattr(ch, 'minimum_height', None)
            if mh:
                return float(mh)
        return 0.0

    def _content_h() -> float:
        """内容自然高度：只读「需求侧」尺寸（minimum_height / texture），
        绝不读 ``height``（那是被父容器分配的旧值，会引入反馈与滞后）。
        """
        total = 0.0
        for ch in content.children:
            if ch.size_hint_y is None:
                mh = getattr(ch, 'minimum_height', None)
                if mh:
                    total += float(mh)
                else:
                    # 非 BoxLayout 的定高控件（Widget 分割线 / 定高 Label）
                    total += float(getattr(ch, 'height', 0) or 0)
            else:                                   # 弹性子（ScrollView）
                total += _scroll_intrinsic_h(ch)
        return total

    def _apply_height() -> None:
        """按内容重算并设置面板高度（幂等、无副作用回环）。

        ⚠️ 绝不在 panel.size 变化后再反过来触发本函数：那会和 BoxLayout 的
        do_layout / minimum_height 形成无限回环（曾导致 480 次
        'too much iteration' 刷屏、弹窗卡死、✕ 点不动）。改用「一次性收敛」：
        只在 layout 定时器里调用有限次数，稳定即停。
        """
        rw, rh = root.width or 1, root.height or 1
        max_w, max_h = rw * size_hint[0], rh * size_hint[1]
        want = _content_h() + 16                # +16 余量吸收边框/字体舍入
        fit_h = max(150.0, want)
        if max_h > 120.0:                       # 上限已就绪才应用上限
            fit_h = min(max_h, fit_h)
        panel.size = (max(220.0, max_w), fit_h)

    panel.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
    root.add_widget(panel)

    popup = Popup(title="", content=root, size_hint=(1, 1),
                  auto_dismiss=auto_dismiss, background='',
                  background_color=(0, 0, 0, 0), separator_height=0, padding=0)

    # 关闭按钮接线：modal_header 把 set_close 挂在自己身上，这里在 content 子树里
    # 找到它并注入 popup.dismiss（缺省 = 直接关弹窗，避免各调用点重复接线）。
    cb = on_close if on_close is not None else popup.dismiss
    _wire_close(content, cb)
    # 点遮罩空白关闭所需的引用（root 的 on_touch_down 回调里用）
    _outside['popup'] = popup
    _outside['panel'] = panel

    # 收敛策略：body（ScrollView 内 BoxLayout）的 minimum_height 是唯一可靠的
    # 「内容真实高度」信号。做法 —— 绑定它触发重算，但用**重入哨兵**保证
    # 同一次重算不会再被自己触发（避免 panel.size→重排→minimum_height→重算 回环）。
    _busy = {'on': False}

    def _recompute(*_a) -> None:
        if _busy['on']:
            return                                  # 重入 → 直接丢弃，断环
        _busy['on'] = True
        try:
            _apply_height()
        finally:
            _busy['on'] = False

    def _hook_body(node: Widget) -> None:
        mh = getattr(node, 'minimum_height', None)
        if mh is not None:
            node.bind(minimum_height=lambda *_: _recompute())
        for ch in node.children:
            _hook_body(ch)

    _hook_body(content)
    # 多帧补算：字体 texture / 换行 / BoxLayout 需要几帧才定稿，且要在 popup
    # open()（root 拿到真实尺寸）之后。
    #
    # ⚠️ 判「稳定」必须看**输入信号 `_content_h()`**，不能只看 `panel.height`：
    # 布局定稿前 body 宽度还是默认值（100px）→ 文本疯狂换行 → minh 虚高（曾达
    # 463），随后 panel 被设为真实宽度，minh 需**再过几帧**才回落到真值（248）。
    # 若只比较 panel.height，它在这几帧里恰好连续相等 → watchdog 误判「已稳定」
    # 提前停摆，面板永久停在虚高的 579（弹窗留白 bug 的根因）。
    # 因此：①以 content_h 为判据；②强制最少 MIN_FRAMES 帧（让布局定稿）；
    # ③超帧上限兜底。
    MIN_FRAMES = 6          # 布局定稿所需的最少帧数（实测 5 帧后 content_h 才稳）
    _wd = {'n': 0, 'prev': None, 'stable': 0}

    def _watchdog(_dt: float) -> bool:
        _wd['n'] += 1
        _recompute()
        cur = round(_content_h(), 1)            # 用输入信号判稳定，而非输出
        if cur == _wd['prev']:
            _wd['stable'] += 1
        else:
            _wd['stable'] = 0
            _wd['prev'] = cur
        if _wd['n'] >= MIN_FRAMES and _wd['stable'] >= 2:
            return False                        # 内容定稿且连续稳定 → 停止
        if _wd['n'] >= 40:
            return False                        # 超帧上限兜底，避免永不停摆
        return True

    Clock.schedule_once(lambda *_: _recompute(), 0)
    Clock.schedule_interval(_watchdog, 1 / 60.0)
    return popup


def _wire_close(node: Widget, cb: Callable) -> bool:
    """在 widget 子树里找到第一个带 ``set_close`` 的节点并注入回调。

    Returns:
        True 表示接线成功（找到并注入了 set_close）。
    """
    setter = getattr(node, 'set_close', None)
    if setter is not None:
        setter(cb)
        return True
    for ch in node.children:
        if _wire_close(ch, cb):
            return True
    return False


# ``fit_width`` 由 ``ui_v4`` 导入（见上方 from ui_v4 import）。
# 这里不再重复定义 —— 全项目只有一份文本宽度测量逻辑，避免再次写出
# ``bind(texture_size → width)`` 那种正反馈回环。


def auto_h_label(text: str, font_size: float, color=None,
                 markup: bool = False) -> Widget:
    """自增高 Label：放进 ScrollView 的纵向 BoxLayout 时按内容撑高，绝不裁切。

    固定 height 的 mk_label 在长文案下会纵向裁切（弹窗文字"显示不清"的根因
    之一），这里把 height 绑定到 texture_size，随文字增长。

    ⚠️ 只绑 ``texture_size``，**不绑 text_size**：绑 text_size 会在
    「设高度 → BoxLayout 重排 → 宽度变 → text_size 变 → 再设高度」之间形成
    无限回环（曾导致弹窗刷屏卡死）。texture_size 由 Kivy 在宽度确定后自行
    重算，绑定它即可安全自增高。
    """
    line_h = font_size * 1.6            # 单行行高下限（含行距）
    lbl = mk_label(text, font_size=font_size, color=color, valign='top',
                   size_hint_y=None, height=line_h, markup=markup)

    # ⚠️ mk_label._bind_text_size 会把 text_size 设成「宽+高」。对自增高 Label，
    # 高度由 texture 反推，若 text_size 的高度 = 自身高度 会形成
    # 「text_size.h↑ → 换行计算变 → texture↑ → height↑ → text_size.h↑」正反馈，
    # 实测把一行 20px 文案撑到 348px（≈17 行）→ 弹窗炸开、选项被挤出可见区。
    # 解决：把 text_size 的高度置为 None（只按宽度换行，高度自由增长）。
    def _fix_wrap(inst, size) -> None:
        inst.text_size = (size[0], None)
    lbl.bind(size=_fix_wrap)
    lbl.text_size = (lbl.width, None)

    def _resize(inst, val) -> None:
        # texture_size[1] 是当前宽度下换行后的真实高度；下限单行高度。
        new_h = max(float(val[1]) + 4, line_h)
        if abs(inst.height - new_h) > 0.5:      # 只在真正变化时赋值，避免抖动
            inst.height = new_h

    lbl.bind(texture_size=_resize)
    return lbl


def modal_header(icon: str, title: str, chips=()) -> BoxLayout:
    """弹窗标题栏（设计稿 .modal__hd）：图标 + 标题 + chips + 右侧 ✕ 关闭按钮。

    返回的 BoxLayout 带 ``set_close(cb)``：``make_modal`` 构建时会把弹窗的
    dismiss 回调注入进来，授权 ✕ 按钮关窗（弹窗此前没有任何关闭入口）。
    """
    # 高度 48 让 32×32 的 ✕ 按钮放得下且不易误触（像素规范交互 ≥44px）
    hd = BoxLayout(orientation='horizontal', spacing=8, size_hint_y=None, height=48,
                   padding=(12, 8))
    hd.add_widget(mk_label(icon, font_size=15, color=COLORS['cyan'],
                           halign='center', size_hint=(None, None), size=(28, 28)))
    # markup=True：mk_label 默认 markup=False，否则 [b] 会原样显示成字面量
    lbl = mk_label(f"[b]{title}[/b]", font_size=U.FS_H3, color=COLORS['cyan'],
                   markup=True)
    hd.add_widget(lbl)
    for text, tone in chips:
        hd.add_widget(PxChip(text, tone=tone, height=20))
    hd.add_widget(Widget())

    # ✕ 关闭按钮：32×48 点击热区（宽度受限，纵向撑满 header 高度）
    close_btn = Button(text=U.SYM['close'], font_size=U.FS_H3, color=COLORS['text_mute'],
                       size_hint=(None, 1), width=32,
                       background_normal='', background_down='',
                       background_color=(0, 0, 0, 0))
    add_pixel_border(close_btn, color=COLORS['border_2'])

    _cb = {'fn': None}

    def _bind_close(cb: Callable) -> None:
        """由 make_modal 注入关闭回调（幂等：重复调用只保留最后一次）。"""
        _cb['fn'] = cb

    def _on_close(*_a) -> None:
        fn = _cb['fn']
        if fn:
            # 只关一次：淡出动画期间按钮仍可点，避免重复 dismiss 造成抖动
            _cb['fn'] = None
            fn()

    close_btn.bind(on_release=_on_close)
    hd.add_widget(close_btn)
    hd.set_close = _bind_close        # 挂到 header 容器上供 make_modal 发现
    return hd

