"""verify_popup_fix.py —— 弹窗系列修复验证（关闭/字号/换行/无回环）。

覆盖本轮 3 组修复：
  1. ✕ 关闭按钮 + 点遮罩空白关闭（两条关闭路径）
  2. 全局字号放大（正文 20 / 小字 16）+ 标题不再出现字面 [b]
  3. 事件弹窗「不停打印换行」根因 = make_modal 布局无限回环 → 已断环，
     断言渲染期间无 'too much iteration' 刷屏，且面板高度贴合内容不裁切

用法：
    python verify_popup_fix.py
"""
import logging
import os
import sys
import time

os.environ.setdefault('KIVY_NO_FILELOG', '1')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from kivy.config import Config  # noqa: E402

Config.set('graphics', 'width', '1440')
Config.set('graphics', 'height', '880')
Config.set('graphics', 'resizable', '0')

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.uix.button import Button  # noqa: E402
from kivy.uix.modalview import ModalView  # noqa: E402
from kivy.uix.popup import Popup  # noqa: E402
from kivy.uix.scrollview import ScrollView  # noqa: E402

_ = Window.size  # 触发窗口创建

import main as M  # noqa: E402
import ui_v4 as U  # noqa: E402
import v2_events  # noqa: E402

# ---- 捕获 Clock 的无限回环告警 ----
SPIN = [0]


class _SpinHandler(logging.Handler):
    def emit(self, rec):
        if 'too much iteration' in rec.getMessage():
            SPIN[0] += 1


logging.getLogger('Clock').addHandler(_SpinHandler())

FAILS = []


def check(name: str, cond: bool, detail: str = '') -> None:
    print(f"  [{'OK' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ''))
    if not cond:
        FAILS.append(name)


def find(root, cls):
    out = [root] if isinstance(root, cls) else []
    for ch in getattr(root, 'children', []):
        out += find(ch, cls)
    return out


def pump(n: int = 120) -> None:
    for _ in range(n):
        Clock.tick()


def pump_anim(seconds: float = 0.8) -> None:
    """推进真实时间以驱动 ModalView 的淡出动画并处理其回调。

    ⚠️ Kivy 2.3.1 的 ``Clock.tick()`` 不接受 dt 参数，也不推进由真实时钟
    驱动的 Animation（Popup.dismiss 的淡出 0.4s）。只 tick 不 sleep 会让
    Popup 永远留在窗口树上 —— 这是测试"点击关闭不生效"的唯一根因（功能本身
    正常）。这里 sleep + tick 交替，让动画完成并触达 _real_remove_widget。
    """
    t0 = time.time()
    while time.time() - t0 < seconds:
        Clock.tick()
        time.sleep(0.005)


def top_popup():
    pops = find(Window, Popup)
    return pops[0] if pops else None


def main() -> int:
    rv = M.RootView()
    rv.start_new_game()
    g = rv.game

    # ---------- 1. 字号阶梯 ----------
    # ⚠️ 不硬编码具体数值：字号是 ui_v4 的单一来源（FS_SCALE 控制），
    # 这里只校验「阶梯关系成立 + 达到可读性下限」，调系数时无需改测试。
    print("\n[1] 字号阶梯")
    check('字号单一来源 FS_SCALE 已生效', U.FS_SCALE >= 1.0,
          f"FS_SCALE={U.FS_SCALE}")
    check('正文 ≥ 20（可读性下限）', U.FS_BODY >= 20, f"FS_BODY={U.FS_BODY}")
    check('小字 ≥ 16（可读性下限）', U.FS_CAP >= 16, f"FS_CAP={U.FS_CAP}")
    check('阶梯单调：DISPLAY>H1>H2>H3>BODY>SM>CAP>TINY',
          U.FS_DISPLAY > U.FS_H1 > U.FS_H2 > U.FS_H3 > U.FS_BODY
          > U.FS_SM > U.FS_CAP > U.FS_TINY,
          f"{U.FS_DISPLAY}>{U.FS_H1}>{U.FS_H2}>{U.FS_H3}"
          f">{U.FS_BODY}>{U.FS_SM}>{U.FS_CAP}>{U.FS_TINY}")
    check('markup [size=] 用整数（避免 int() ValueError）',
          isinstance(U.FS_CAP, int) and isinstance(U.FS_TINY, int),
          f"FS_CAP={type(U.FS_CAP).__name__} FS_TINY={type(U.FS_TINY).__name__}")

    # ---------- 2. 事件弹窗：打开 / 无回环 / 不裁切 / ✕ / 点外关闭 ----------
    print("\n[2] 事件弹窗（S07）")
    evt = next(e for e in v2_events.EVENTS if len(getattr(e, 'options', [])) >= 2)
    g.show_choice_popup(evt)
    pump(120)
    pop = top_popup()
    check('弹窗已打开', pop is not None)
    rb = SPIN[0]
    check('无布局回环（too much iteration == 0）', rb == 0, f"spin={rb}")

    root = pop.content
    panel = root.children[0]
    sv = find(root, ScrollView)[0]
    body = sv.children[0]
    check('面板高度贴合内容（< 上限 0.98）',
          panel.height < 0.72 * root.height * 0.98,
          f"panel={panel.height:.0f} cap={0.72 * root.height:.0f}")
    # 强断言：面板高度 == 内容自然高度 + 16 余量（±3px 容差）。
    # 回归"watchdog 过早停止 → 面板停在虚高值（曾 579，实际 364）"这一 bug：
    # 若布局定稿后仍残留虚高值，此处必然失败。
    # header / footer 的高度由各自 minimum_height 决定，这里从树里实测。
    cbox = panel.children[0]          # PixelPanel 内的内容 BoxLayout
    hdr = cbox.children[-1]           # BoxLayout children 是反序：末位=最先加的 header
    ftr = cbox.children[0]            # 首位=最后加的 footer
    hdr_h = float(getattr(hdr, 'minimum_height', None) or hdr.height)
    ftr_h = float(getattr(ftr, 'minimum_height', None) or ftr.height)
    want = hdr_h + body.minimum_height + 2 + ftr_h + 16   # header+body+hline+footer+16
    check('面板高度精确贴合（== 内容 + 16，±3px）',
          abs(panel.height - want) <= 3,
          f"panel={panel.height:.0f} want={want:.0f}")
    check('ScrollView 完整容纳 body（不裁切）',
          sv.height + 0.5 >= body.minimum_height,
          f"sv={sv.height:.0f} body.minh={body.minimum_height:.0f}")

    # 标题无字面 [b]（markup 生效）
    labels = find(root, type(U.mk_label('x')))
    titled = [l for l in labels if '[b]' in getattr(l, 'text', '')]
    check('标题 markup=True', all(getattr(l, 'markup', False) for l in titled),
          f"n={len(titled)}")

    # ✕ 关闭按钮存在且可触发关闭
    cbtns = [w for w in find(root, Button) if w.text == U.SYM['close']]
    check('含关闭按钮', len(cbtns) >= 1, f"found={len(cbtns)}")
    cbtns[0].dispatch('on_release')
    pump_anim(0.9)
    check('点关闭按钮生效', top_popup() is None)

    # 点遮罩空白关闭
    g.show_choice_popup(evt)
    pump(120)
    pop = top_popup()
    root = pop.content
    panel = root.children[0]
    # 造一个「面板外」的触摸（面板居中，四角必在面板外，除非面板铺满）
    tx, ty = 4.0, 4.0
    if panel.collide_point(tx, ty):
        tx, ty = root.width - 4.0, root.height - 4.0
    touch = type('T', (), {'pos': (tx, ty), 'grab_current': None})()
    root.dispatch('on_touch_down', touch)
    pump_anim(0.9)
    check('点面板外遮罩关闭生效', top_popup() is None)

    # ---------- 3. 连续弹窗不叠加遮罩（回归 _purge_lingering_modals） ----------
    print("\n[3] 连续弹窗不叠加遮罩")
    # 上一个弹窗刚 dismiss（仍在 0.4s 淡出期，旧遮罩仍挂在窗口上），
    # 这时立刻弹新窗 —— 若不做清理，两层 0.55 黑遮罩叠加会把面板压成近纯黑
    # （曾致 S08/S09 主色 rgb(0,1,1)，脱离调色板）。
    g.show_choice_popup(evt)
    pump(5)                                   # 只泵几帧（淡出尚未完成）
    g.show_crisis_popup()                     # 立即叠第二个弹窗
    pump(120)
    modals = find(Window, ModalView)
    check('连续弹窗后窗口上只有 1 个 ModalView', len(modals) == 1,
          f"n={len(modals)}")
    for m in list(modals):
        m.dismiss()

    # ---------- 4. 危机 / 结局弹窗同样合规 ----------
    print("\n[4] 危机 / 结局弹窗")
    for name, opener, hint in (
        ('危机', g.show_crisis_popup, 0.68),
        ('结局', lambda: g.show_ending_popup('regulated'), 0.82),
    ):
        opener()
        pump(120)
        pop = top_popup()
        check(f'{name}弹窗打开', pop is not None)
        root = pop.content
        panel = root.children[0]
        sv = find(root, ScrollView)[0]
        body = sv.children[0]
        check(f'{name}面板贴合内容（< 上限 0.98）',
              panel.height < hint * root.height * 0.98,
              f"panel={panel.height:.0f} cap={hint * root.height:.0f}")
        check(f'{name}含关闭按钮',
              len([w for w in find(root, Button)
                   if w.text == U.SYM['close']]) >= 1)
        pop.dismiss()
        pump(5)

    print()
    check('全程无布局回环', SPIN[0] == 0, f"spin={SPIN[0]}")
    if FAILS:
        print(f"POPUP_FIX_FAIL: {len(FAILS)} 项未通过 -> {FAILS}")
        return 1
    print("POPUP_FIX_OK: 全部通过")
    return 0


if __name__ == '__main__':
    sys.exit(main())
