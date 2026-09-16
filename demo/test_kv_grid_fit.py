"""test_kv_grid_fit.py - 键值表（KvGrid）左列文案「不省略」回归守卫

背景 bug（本轮修复）：
    检视卡 / 投放预览的左列是 i18n 键名，右列是值。左列宽 = 面板固定宽的一
    半，英文文案普遍比中文长 30~70% —— 例如 ``doubt_thr``：
        中文 '怀疑度 / 阈值'   108px   ✔
        英文 'Suspicion / threshold' 181px   ✘（列宽仅 153px）
    超宽时 KvGrid 用 shorten 打省略号，玩家看到 'Suspicion / thre…'。
    省略号不是裁字（不丢字形），但信息确实残缺 —— 用户诉求是「文字完整可见」，
    所以英文文案必须收进列宽。

本测试的做法：
    1. 造真面板（InspectorPanel / DropPreview），钉死尺寸，强制布局收敛；
    2. 对每个左列标签：临时关掉 shorten 量**自然宽度**，与它的格子宽比较；
    3. 中英两语 × 三档 UI 缩放都必须放得下。

⚠️ 只读 label.texture_size[0] 是测不出问题的：shorten=True 时 Kivy 会把纹理
   宽度截到可用宽，读出来永远「刚好放得下」。必须关掉 shorten 再量。

跑法：
    python test_kv_grid_fit.py
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
from kivy.uix.label import Label

for _fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(_fp):
        try:
            LabelBase.register(name='MicrosoftYaHei', fn_regular=_fp)
            LabelBase.register(name='Roboto', fn_regular=_fp)
        except Exception:
            pass

import i18n
import ui_v4 as U
import ui_v4_panels as P

# 自动 UI 缩放档位：面板宽与字号同倍缩，比值应保持
SCALES = (0.8, 1.0, 1.3)

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


def _settle(w, times: int = 4) -> None:
    for _ in range(times):
        _force_layout(w)
        Clock.tick()


def _scale_fonts(w, scale: float, depth: int = 0) -> None:
    """把面板内所有标签字号按缩放倍数调整（等价 main._apply_scale 的语义）。"""
    if depth > 16:
        return
    if isinstance(w, Label):
        w.font_size = getattr(w, '_base_fs', None) or w.font_size
        if not hasattr(w, '_base_fs'):
            w._base_fs = w.font_size
        w.font_size = w._base_fs * scale
    for ch in list(getattr(w, 'children', ()) or ()):
        _scale_fonts(ch, scale, depth + 1)


def _natural_w(label) -> float:
    """量标签「不打省略号」时的真实像素宽。"""
    saved = (label.text_size, label.shorten)
    try:
        label.shorten = False
        label.max_lines = 0
        label.text_size = (None, None)
        label.texture_update()
        return float(label.texture_size[0])
    finally:
        label.text_size, label.shorten = saved


def _assert_kv_fits(kv, tag: str) -> None:
    for key, lbl in kv._labels.items():
        natural = _natural_w(lbl)
        avail = float(lbl.width)
        if avail <= 0:
            raise AssertionError(f'{tag}/{key}: 格子宽为 0，布局没收敛')
        if natural > avail + 0.5:
            raise AssertionError(
                f'{tag}/{key}: 文案 {lbl.text!r} 自然宽 {natural:.0f}px > '
                f'可用 {avail:.0f}px（会打省略号，信息残缺）')


def test_inspector_kv_fits_both_languages():
    for scale in SCALES:
        for lang in (i18n.LANG_ZH, i18n.LANG_EN):
            i18n.set_lang(lang)
            panel = P.InspectorPanel()
            panel.size_hint = (None, 1)
            panel.width = P.InspectorPanel.WIDTH * scale
            panel.height = 900 * scale
            panel.pos = (0, 0)
            _settle(panel)
            if scale != 1.0:
                _scale_fonts(panel, scale)
                _settle(panel)
            _assert_kv_fits(panel.kv, f'检视卡/{lang}/×{scale}')


def test_drop_preview_kv_fits_both_languages():
    for scale in SCALES:
        for lang in (i18n.LANG_ZH, i18n.LANG_EN):
            i18n.set_lang(lang)
            pv = P.DropPreview()
            pv.size_hint = (None, None)
            pv.width = P.DropPreview.WIDTH * scale
            pv.height = 600 * scale
            pv.pos = (0, 0)
            _settle(pv)
            if scale != 1.0:
                _scale_fonts(pv, scale)
                _settle(pv)
            _assert_kv_fits(pv.kv, f'投放预览/{lang}/×{scale}')


def test_all_kv_keys_exist_in_both_languages():
    """左列查表失败会回落成键名本身 —— 那也是一种「显示英文代码」。"""
    keys = set()
    for panel in (P.InspectorPanel(), P.DropPreview()):
        keys |= set(panel.kv._labels.keys())
    assert keys, '没收集到任何 KvGrid 键名'
    for key in sorted(keys):
        for lang in (i18n.LANG_ZH, i18n.LANG_EN):
            i18n.set_lang(lang)
            assert i18n.t(key) != key, f'{key} 在 {lang} 下缺翻译（会显示键名原文）'


def main() -> int:
    print('=' * 66)
    print('KvGrid 左列文案宽度守卫（中英 × 三档缩放）')
    print('=' * 66)
    check('检视卡 KvGrid 中英双语不省略', test_inspector_kv_fits_both_languages)
    check('投放预览 KvGrid 中英双语不省略', test_drop_preview_kv_fits_both_languages)
    check('KvGrid 键名中英词典齐备', test_all_kv_keys_exist_in_both_languages)
    print()
    if FAILED:
        print(f'■ {len(FAILED)} 项未通过：{FAILED}')
        return 1
    print('■ KvGrid 左列在中英双语与三档缩放下均完整可见')
    return 0


if __name__ == '__main__':
    sys.exit(main())
