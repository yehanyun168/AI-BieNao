# -*- coding: utf-8 -*-
"""屏幕适配守卫：开窗尺寸必须钳进屏幕可用区，且不破坏设计比例。

背景（真人反馈）：某台 2880×1612@200% 的机器上，游戏窗口按固定 1680 逻辑宽
开窗，而该机逻辑屏幕只有 1440 宽 → 窗口撑出屏幕 480px（物理），左右各被裁掉
一截（截图里标题只剩「闹」、按钮左边框跑到屏幕外、面板被挤压）。

本测试断言 `main.py` 开窗段的**纯逻辑**（不依赖真实显示器）：
  1. 窄屏机器上窗口宽被钳到屏幕宽的 98% 以内，且能被 4 整除；
  2. 钳窄时高度按 1680:980 设计比例同缩，守住宽高比；
  3. 宽屏机器上仍按设计 1680×980 开窗（不误伤）；
  4. 探测失败（回退常量）时必须仍然开得起窗，不允许因为探测异常起不来。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

os.environ.setdefault('KIVY_NO_FILELOG', '1')

import unittest


DESIGN_WIN_W, DESIGN_WIN_H = 1680, 980
MARGIN = 0.98


def _plan_window(screen_w, screen_h):
    """复刻 main.py 开窗段逻辑（纯函数版），返回最终 (w, h)。"""
    if screen_w and screen_h:
        fit = min((screen_w * MARGIN) / DESIGN_WIN_W,
                  (screen_h * MARGIN) / DESIGN_WIN_H,
                  1.0)
        win_w = int(DESIGN_WIN_W * fit)
        win_h = int(DESIGN_WIN_H * fit)
    else:
        win_w, win_h = DESIGN_WIN_W, DESIGN_WIN_H
    win_w = max(win_w, 960)
    win_h = max(win_h, 540)
    win_w -= win_w % 4
    win_h -= win_h % 4
    return win_w, win_h


class TestWindowFit(unittest.TestCase):

    def test_narrow_screen_gets_clamped(self):
        """解析度 2880×1612@200% → 逻辑 1440×806，窗口必须放得下。"""
        w, h = _plan_window(1440, 806)
        self.assertLessEqual(w, 1440,
                             f'窗口宽 {w} 不应超过逻辑屏幕宽 1440')
        self.assertLessEqual(h, 806,
                             f'窗口高 {h} 不应超过逻辑屏幕高 806')
        self.assertGreater(w, 1200, f'窗口宽 {w} 被钳得过小，玩了会很难受')

    def test_width_divisible_by_4(self):
        """Kivy GL 布局要求宽度能被 4 整除。"""
        for sw, sh in ((1440, 806), (1280, 720), (2560, 1600), (3840, 2160)):
            w, h = _plan_window(sw, sh)
            self.assertEqual(w % 4, 0, f'{sw}x{sh} → 宽 {w} 不是 4 的倍数')
            self.assertEqual(h % 4, 0, f'{sw}x{sh} → 高 {h} 不是 4 的倍数')

    def test_aspect_ratio_preserved_when_clamped(self):
        """宽被钳窄时高度必须同缩，否则画面会被拉伸。"""
        w, h = _plan_window(1440, 806)
        design_ar = DESIGN_WIN_W / DESIGN_WIN_H
        self.assertAlmostEqual(w / h, design_ar, delta=0.02,
                               msg=f'钳窄后宽高比 {w/h:.3f} 偏离设计 {design_ar:.3f}')

    def test_wide_screen_keeps_design_size(self):
        """宽屏机器不受影响，仍按 1680×980 开窗。"""
        w, h = _plan_window(2560, 1600)
        self.assertEqual((w, h), (DESIGN_WIN_W - DESIGN_WIN_W % 4,
                                  DESIGN_WIN_H - DESIGN_WIN_H % 4))

    def test_probe_failure_still_opens(self):
        """探测失败（0×0）必须回退设计尺寸，不能起不来。"""
        w, h = _plan_window(0, 0)
        self.assertEqual(w, DESIGN_WIN_W)
        self.assertEqual(h, DESIGN_WIN_H)

    def test_main_source_wires_the_probe(self):
        """源码层：main.py 必须真的调用探测并钳尺寸（防回归成写死）。"""
        with open(os.path.join(_HERE, 'main.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('_probe_screen()', src, 'main.py 丢失了屏幕探测调用')
        self.assertIn("Config.set('graphics', 'width', str(_WIN_W))", src,
                      'main.py 开窗宽未走钳位后的 _WIN_W')
        self.assertIn("Config.set('graphics', 'height', str(_WIN_H))", src,
                      'main.py 开窗高未走钳位后的 _WIN_H')
        self.assertIn('SystemParametersInfoW', src, '探测实现缺失')

    def test_compute_scale_uses_both_axes(self):
        """_compute_scale 必须宽高同时取 min（只看高会在超宽屏放大过度）。"""
        with open(os.path.join(_HERE, 'main.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('min(w / self.DESIGN_W, h / self.DESIGN_H)', src,
                      '_compute_scale 未同时考虑宽高')


if __name__ == '__main__':
    unittest.main(verbosity=2)
