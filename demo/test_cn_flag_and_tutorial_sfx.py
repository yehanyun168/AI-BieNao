# -*- coding: utf-8 -*-
"""守卫：2026-09-14 三个显示/音效缺陷的修复不被回退。

1) 中国国旗大五角星：旧数据的「大星」实为菱形（lozenge），4 小星只是单点，
   无法辨认五角星。现数据由栅格化重算为真五角星。
   判定五角星 vs 菱形的关键特征：五角星底部有两个独立下角、中间带缺口
   （同一行出现 ≥2 段水平游程）；菱形每一行都只有 1 段。
2) 新手教程「跳过教程」「下一步」按钮：此前无任何音效接线（点击全静默）。

不依赖 Kivy GUI，纯数据/源码断言，可 headless 跑。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pixel_assets as PA  # noqa: E402

GOLD = 'ffde00'
BIG_MAX_X = 8          # 大星占 x≤8；4 小星在 x≥9


def _gold_cells():
    cells = set()
    for hexstr, gx, gy, gw, gh in PA.FLAGS['CN']:
        if hexstr != GOLD:
            continue
        for y in range(gy, gy + gh):
            for x in range(gx, gx + gw):
                cells.add((x, y))
    return cells


def _runs_in_row(cells, y):
    """返回该行从左到右的连续水平段数。"""
    xs = sorted(x for (x, yy) in cells if yy == y)
    if not xs:
        return 0
    runs, prev = 1, xs[0]
    for x in xs[1:]:
        if x != prev + 1:
            runs += 1
        prev = x
    return runs


def test_cn_big_star_has_notch():
    """大星必须存在「底部两角 + 中间缺口」的行（≥2 段）→ 是真五角星，非菱形。"""
    big = {(x, y) for (x, y) in _gold_cells() if x <= BIG_MAX_X}
    assert big, 'CN 国旗缺少大星金色像素'
    rows = sorted({y for (_, y) in big})
    notches = [y for y in rows if _runs_in_row(big, y) >= 2]
    assert notches, (
        '大星没有任何一行出现 ≥2 段游程 —— 这是菱形（旧缺陷），不是五角星。'
        ' 大星行=%s' % rows)


def test_cn_big_star_extent():
    """大星应有足够尺寸：宽 ≥7、高 ≥8（30×20 网格的旗面区）。"""
    big = [(x, y) for (x, y) in _gold_cells() if x <= BIG_MAX_X]
    xs = [x for x, _ in big]
    ys = [y for _, y in big]
    w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    assert w >= 7 and h >= 8, '大星尺寸异常：%dx%d（应 ≥7x8）' % (w, h)


def test_cn_has_four_small_stars():
    """右侧应有 4 颗小星（4 个连通块）。"""
    small = {(x, y) for (x, y) in _gold_cells() if x > BIG_MAX_X}
    seen, comps = set(), 0
    for cell in small:
        if cell in seen:
            continue
        comps += 1
        stack = [cell]
        while stack:
            c = stack.pop()
            if c in seen:
                continue
            seen.add(c)
            x, y = c
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in small and n not in seen:
                    stack.append(n)
    assert comps == 4, '小星连通块数应为 4，实际 %d' % comps


def test_tutorial_buttons_have_click_sfx():
    """教程「跳过教程」「下一步」按钮必须有点击音效接线。"""
    src = io.open(os.path.join(HERE, 'tutorial.py'), encoding='utf-8').read()
    assert 'import sfx' in src, 'tutorial.py 未 import sfx（点击会 NameError）'
    assert 'sfx.play(' in src, 'tutorial.py 缺少 sfx.play 接线'
    # 接线必须落在 _px_btn 内（该工厂同时造「跳过教程」与「下一步」）
    seg = src.split('def _px_btn')[1].split('return btn')[0]
    assert 'sfx.play(' in seg, '_px_btn 内没有触发音效 —— 跳过/下一步仍会静默'


def test_menu_buttons_have_click_sfx():
    """主菜单按钮必须继续有点击音效（防回退）。"""
    src = io.open(os.path.join(HERE, 'main.py'), encoding='utf-8').read()
    seg = src.split('def _menu_btn')[1].split('def _lang_row')[0]
    assert 'sfx.play(' in seg, 'main.py _menu_btn 丢失点击音效接线'


def _method_src(path, cls, func):
    """取指定类方法的源码（AST 定位，避免文本误伤同名片段）。"""
    src = io.open(os.path.join(HERE, path), encoding='utf-8').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == func:
                    return ast.get_source_segment(src, sub) or ''
    return None


def test_v4_ui_controls_have_click_sfx():
    """v4 UI 交互控件 + 右侧指令栏必须有点击音效接线（防回归）。

    这些控件原本全部零接线：RailButton 只 bind on_release 转发，玩家点右侧
    指令栏「技能/科技/成就/帮助/设置/日志」与区域页签/开关时全程静默。
    """
    targets = [
        ('ui_v4.py', 'PxChip', 'on_touch_down'),        # 区域页签 RegionTab 基类
        ('ui_v4.py', 'SegSwitch', 'on_touch_down'),     # 分段开关
        ('ui_v4.py', 'OptButton', 'on_touch_down'),     # 事件选项按钮
        ('ui_v4_cards.py', 'SlotRow', 'on_touch_down'),
        ('ui_v4_cards.py', 'LvRow', 'on_touch_down'),
        ('ui_hud.py', 'RailBar', '_fire'),              # 右侧指令栏 6 枚菜单按钮
    ]
    for path, cls, func in targets:
        seg = _method_src(path, cls, func)
        assert seg is not None, '找不到 %s.%s（%s）' % (cls, func, path)
        assert 'sfx.play(' in seg, '%s.%s 缺少点击音效接线 —— 点了会静默' % (cls, func)
    # 三个文件都必须 import sfx，否则运行期直接 NameError
    for path in ('ui_v4.py', 'ui_v4_cards.py', 'ui_hud.py'):
        src = io.open(os.path.join(HERE, path), encoding='utf-8').read()
        assert 'import sfx' in src, '%s 未 import sfx' % path


if __name__ == '__main__':
    cases = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failed = 0
    for c in cases:
        try:
            c()
            print('  [OK]   %s' % c.__name__)
        except AssertionError as e:
            failed += 1
            print('  [FAIL] %s — %s' % (c.__name__, e))
    print('=' * 60)
    if failed:
        print('存在未通过项：%d/%d' % (failed, len(cases)))
        sys.exit(1)
    print('全部通过 —— %d/%d（中国国旗五角星 + 教程/菜单音效守卫）'
          % (len(cases), len(cases)))
