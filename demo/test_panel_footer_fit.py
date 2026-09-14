"""test_panel_footer_fit.py - 浮层面板「页脚 / 标题栏」文案宽度守卫

背景 bug（本轮修复）：
    1) 页脚按钮横向 size_hint 是默认的 (1,1) → 参与 BoxLayout 均分。检视卡页脚
       3 个弹性子控件均分 312px，每枚只有 104px，而 '⊕ 向该国投放技能' 真实要
       145px、'⊕ Drop skill here' 要 143px → 两种语言下按钮文字都溢出自己的盒子；
    2) 日志抽屉页脚把说明和两枚按钮塞一行：中文需求 348px、英文 408px，
       可用仅 316px（small_btn 还按 len*14+20 估算，英文给到 412/202）→ 压字；
    3) 面板 refresh_scale 只缩面板宽、不缩页脚 → 窗口一缩，定宽按钮顶出面板。

修法：
    - 页脚按钮改**定宽**（size_hint_x=None），宽度由 ``fit_footer`` 按真实字形宽算；
    - ``fit_footer`` 把字号/行高/内边距/spacing 也按 scale 一起算（等比，不溢出）；
    - 日志抽屉的说明挪到标题栏第二行（FS_TINY），独占整行。

本测试断言（中英 × 五档 UI 缩放 0.68~1.45）：
    A. 页脚定宽子控件之和 + 间距 ≤ 页脚内宽（不会被 BoxLayout 挤出）；
    B. 每枚按钮的文字自然宽 ≤ 按钮自身宽度（按钮内不打省略号/不折行）；
    C. 标题栏说明文字自然宽 ≤ 标题栏宽度（不折行被裁）。

跑法：
    python test_panel_footer_fit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.config import Config
Config.set('graphics', 'resizable', '1')
Config.set('graphics', 'width', '1600')
Config.set('graphics', 'height', '900')

from kivy.core.text import LabelBase
from kivy.clock import Clock

for _fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(_fp):
        try:
            LabelBase.register(name='MicrosoftYaHei', fn_regular=_fp)
            LabelBase.register(name='Roboto', fn_regular=_fp)
        except Exception:
            pass

import i18n
import ui_v4_panels as P

# _compute_scale 的钳位区间是 0.68~1.45（再乘用户 F12 缩放），两端都要过
SCALES = (0.68, 0.8, 1.0, 1.3, 1.45)
FAILED = []


def check(name, fn):
    try:
        fn()
        print(f"  [OK]   {name}")
    except Exception as e:
        import traceback
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        FAILED.append(name)


def _force_layout(w, depth: int = 0) -> None:
    if depth > 16:
        return
    if hasattr(w, 'do_layout'):
        try:
            w.do_layout()
        except Exception:
            pass
    for ch in list(getattr(w, 'children', ()) or ()):
        _force_layout(ch, depth + 1)


def _settle(w, times: int = 5) -> None:
    for _ in range(times):
        _force_layout(w)
        Clock.tick()


def _natural_w(label) -> float:
    """量标签「不打省略号、不折行」时的真实像素宽。"""
    saved = (label.text_size, label.shorten, label.max_lines)
    try:
        label.shorten = False
        label.max_lines = 0
        label.text_size = (None, None)
        label.texture_update()
        return float(label.texture_size[0])
    finally:
        label.text_size, label.shorten, label.max_lines = saved


def _build(panel, scale: float) -> None:
    """按真机路径排一次：refresh_scale（main._apply_scale 的全树遍历会调到它）。"""
    panel.size_hint = (None, 1)
    panel.height = 900
    panel.pos = (0, 0)
    panel.refresh_scale(scale)
    _settle(panel)


def _footer(panel):
    for ch in panel.children:
        if (ch.__class__.__name__ == 'BoxLayout'
                and getattr(ch, 'orientation', None) == 'horizontal'):
            return ch
    raise AssertionError('没找到页脚 BoxLayout')


def _assert_footer(panel, tag: str) -> None:
    ft = _footer(panel)
    inner = ft.width - ft.padding[0] - ft.padding[2]
    if inner <= 0:
        raise AssertionError(f'{tag}: 页脚内宽 {inner:.0f} ≤ 0，布局没收敛')
    fixed = [c for c in ft.children if getattr(c, 'size_hint_x', None) is None]
    need = sum(c.width for c in fixed) + ft.spacing * max(len(ft.children) - 1, 0)
    if need > inner + 0.5:
        raise AssertionError(
            f'{tag}: 定宽子控件合计 {need:.0f}px > 内宽 {inner:.0f}px（会压字/溢出）')
    for c in ft.children:
        txt = getattr(c, 'text', '')
        if not txt:
            continue
        natural = _natural_w(c)
        if natural > float(c.width) + 0.5:
            raise AssertionError(
                f'{tag}: 按钮 {txt!r} 自然宽 {natural:.0f} > 控件宽 {c.width:.0f}')


def _run_panels(cls, name: str, extra=None):
    for scale in SCALES:
        for lang in (i18n.LANG_ZH, i18n.LANG_EN):
            i18n.set_lang(lang)
            panel = cls()
            _build(panel, scale)
            tag = f'{name}/{lang}/×{scale}'
            _assert_footer(panel, tag)
            if extra is not None:
                extra(panel, tag)


def _assert_row(row, tag: str) -> None:
    """横向行：定宽子控件之和 ≤ 内宽，且每个有文字的控件都放得下自己的文字。"""
    inner = row.width - row.padding[0] - row.padding[2]
    if inner <= 0:
        raise AssertionError(f'{tag}: 内宽 {inner:.0f} ≤ 0，布局没收敛')
    fixed = [c for c in row.children if getattr(c, 'size_hint_x', None) is None]
    need = sum(c.width for c in fixed) + row.spacing * max(len(row.children) - 1, 0)
    if need > inner + 0.5:
        raise AssertionError(
            f'{tag}: 定宽子控件合计 {need:.0f}px > 内宽 {inner:.0f}px')
    for c in row.children:
        txt = getattr(c, 'text', '')
        if not txt:
            continue
        natural = _natural_w(c)
        if natural > float(c.width) + 0.5:
            raise AssertionError(
                f'{tag}: {txt!r} 自然宽 {natural:.0f} > 控件宽 {c.width:.0f}')


def test_log_drawer_footer_fits():
    def extra(d, tag):
        _assert_row(d._hd_top, tag + '/标题栏')
        # 未读芯片与关闭按钮必须各占各的位置（旧版都锚 right:1 → 互相重叠，
        # 「0 未读」的尾巴被关闭按钮盖掉）
        chip, x = d.chip_unread, d.btn_x
        if chip.right > x.x + 1:
            raise AssertionError(
                f'{tag}: 未读芯片右边界 {chip.right:.0f} 压到关闭按钮 '
                f'x={x.x:.0f}（重叠）')
        natural = _natural_w(d.lbl_note)
        if natural > float(d.lbl_note.width) + 0.5:
            raise AssertionError(
                f'{tag}: 说明 {d.lbl_note.text!r} 自然宽 {natural:.0f}px > '
                f'标题栏 {d.lbl_note.width:.0f}px（会折行被裁）')
    _run_panels(P.LogDrawer, '日志抽屉', extra)


def test_inspector_footer_fits():
    _run_panels(P.InspectorPanel, '检视卡')


def test_drop_preview_footer_fits():
    _run_panels(P.DropPreview, '投放预览')


def test_inspector_fit_width_scales_with_panel():
    """自适应测量的基准宽必须跟着面板缩，否则按 292px 量的行数 ≠ 实际行数。"""
    p = P.InspectorPanel()
    p.refresh_scale(0.5)
    for attr, w in p.FIT_WIDTH.items():
        base = p._FIT_W_BASE[attr]
        if abs(w - base * 0.5) > 0.51:
            raise AssertionError(f'{attr}: 缩放后基准宽 {w} ≠ {base}×0.5')
    p.refresh_scale(1.0)
    if p.FIT_WIDTH != p._FIT_W_BASE:
        raise AssertionError('回到 ×1.0 时基准宽未复原')


def test_footer_refit_on_language_switch():
    """切语言后按钮文字变宽/变窄，必须重新贴合（否则新语言下又溢出）。"""
    i18n.set_lang(i18n.LANG_ZH)
    d = P.DropPreview()
    _build(d, 1.0)
    zh_w = d.btn_ok.width
    d.refresh_lang()          # i18n 已是 zh，先拿基准
    zh_w = max(zh_w, d.btn_ok.width)
    i18n.set_lang(i18n.LANG_EN)
    d.refresh_lang()
    _settle(d)
    _assert_footer(d, '投放预览/切语言后/en')
    if abs(d.btn_ok.width - zh_w) < 1.0:
        raise AssertionError(
            f'切语言后按钮宽度没变（{zh_w:.0f}），可能没重新贴合')


def main() -> int:
    print('=' * 66)
    print('浮层面板页脚/标题栏宽度守卫（中英 × 五档缩放 0.68~1.45）')
    print('=' * 66)
    check('日志抽屉页脚不溢出、按钮不压字', test_log_drawer_footer_fits)
    check('检视卡页脚不溢出、按钮不压字', test_inspector_footer_fits)
    check('投放预览页脚不溢出、按钮不压字', test_drop_preview_footer_fits)
    check('检视卡自适应基准宽随面板缩放', test_inspector_fit_width_scales_with_panel)
    check('切换语言后页脚重新贴合', test_footer_refit_on_language_switch)
    print()
    if FAILED:
        print(f'■ {len(FAILED)} 项未通过：{FAILED}')
        return 1
    print('■ 页脚/标题栏在中英双语与五档缩放下均不溢出、不压字')
    return 0


if __name__ == '__main__':
    sys.exit(main())
