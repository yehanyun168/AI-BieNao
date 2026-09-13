# -*- coding: utf-8 -*-
"""test_ui_v4_split.py - ui_v4_screens 拆分的防回归守卫

背景（2026-09-13）：ui_v4_screens.py 长到 2327 行，长期占据「单文件 800 行」
白名单。按职责拆成 6 个模块：

    ui_v4_common.py    UiStats / small_btn（公共底座，零 ui_v4_* 依赖）
    ui_v4_panels.py    InspectorPanel / DropPreview / LogDrawer
    ui_v4_cards.py     SkillPageCard / SlotRow / LinkBar / LvRow / BranchCard
    ui_v4_canvas.py    TechNode / TechCanvas
    ui_v4_syspages.py  HelpPage / SettingsPage / SaveSlotRowSlot / Origin*
    ui_v4_screens.py   SkillPage / TechPage / AchPage + 家族转发入口

拆分是「纯搬家」，但留下两个真实风险，本测试专门守它们：

  风险 1：转发层漏符号 —— 外部 7 个模块（main.py / ui_*.py / 测试）都写
          `import ui_v4_screens as S` 再 `S.Xxx()`。谁哪天往新模块加了类却
          忘了在 ui_v4_screens 转发，只有运行到那行才 AttributeError。
          → 断言 1：21 个原符号全部可从 S 取到。

  风险 2：新模块反向 import ui_v4_screens —— 会立刻构成循环导入，
          Kivy 应用启动就崩。
          → 断言 2：5 个新模块的源码里不得出现 ui_v4_screens。

  风险 3：同一符号在两个模块各定义一份（拆分时复制粘贴的典型事故）。
          → 断言 3：除转发外，符号归属唯一。
"""
import ast
import io
import os
import sys

os.environ.setdefault('KIVY_NO_FILELOG', '1')
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# 拆分后 6 个模块（含转发入口）
FAMILY = ('ui_v4_common.py', 'ui_v4_panels.py', 'ui_v4_cards.py',
          'ui_v4_canvas.py', 'ui_v4_syspages.py', 'ui_v4_screens.py')

# 拆分前的 21 个顶层符号（2026-09-13 冻结，改名需同步本表）
LEGACY_NAMES = (
    'UiStats', 'InspectorPanel', 'DropPreview', 'SkillPageCard', 'SlotRow',
    'LinkBar', 'LvRow', 'BranchCard', 'TechNode', 'TechCanvas', 'small_btn',
    'SkillPage', 'TechPage', 'AchPage', 'HelpPage', 'SettingsPage',
    'SaveSlotRowSlot', 'LogDrawer', '_ORIGIN_DIFF_TONE', 'OriginCard',
    'OriginPage',
)


def _top_names(path):
    """取模块顶层定义的 class / def / 赋值名。"""
    src = io.open(path, encoding='utf-8').read()
    out = []
    for n in ast.parse(src).body:
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)):
            out.append(n.name)
        elif isinstance(n, ast.Assign):
            out += [t.id for t in n.targets if isinstance(t, ast.Name)]
    return out


def _imported(path):
    """取模块真实 import 的顶层模块名（走 AST，避开 docstring 里的同名文本）。"""
    src = io.open(path, encoding='utf-8').read()
    out = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            out |= {a.name.split('.')[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            if n.module and n.level == 0:
                out.add(n.module.split('.')[0])
    return out


def _ok(msg):
    print('  [OK]   %s' % msg)


def main():
    print('=== ui_v4_screens 拆分守卫 ===')

    # ---- 1) 转发层完整性：21 个符号全部可从 S 取到 ----
    import ui_v4_screens as S
    missing = [n for n in LEGACY_NAMES if not hasattr(S, n)]
    assert not missing, '转发层漏符号: %s' % missing
    _ok('转发层覆盖拆分前全部 %d 个符号' % len(LEGACY_NAMES))

    # ---- 2) 无反向依赖（循环导入）----
    # 走 AST 而非文本匹配：docstring 里会提到 "从 ui_v4_screens.py 拆出"，
    # 纯文本匹配会把这句话误判成 import（2026-09-13 实测踩过）。
    for fn in FAMILY:
        if fn == 'ui_v4_screens.py':
            continue
        assert 'ui_v4_screens' not in _imported(os.path.join(HERE, fn)), \
            '%s 反向 import ui_v4_screens → 循环导入' % fn
    _ok('5 个新模块均无反向依赖（无循环导入）')

    # ---- 3) 符号归属唯一（同一符号不重复定义）----
    owner, dup = {}, []
    for fn in FAMILY:
        for nm in _top_names(os.path.join(HERE, fn)):
            if nm in owner:
                dup.append('%s(%s & %s)' % (nm, owner[nm], fn))
            owner[nm] = fn
    assert not dup, '符号重复定义: %s' % dup
    _ok('%d 个顶层符号归属唯一' % len(owner))

    # ---- 4) 拆分成果保持：每个模块都远低于 800 行 ----
    for fn in FAMILY:
        n = sum(1 for _ in io.open(os.path.join(HERE, fn), encoding='utf-8'))
        assert n <= 800, '%s %d 行 > 800 行上限（拆分失效）' % (fn, n)
    _ok('6 个模块全部 ≤800 行（原 2327 行单文件已解体）')

    # ---- 5) 公共底座零家族内依赖（否则 screens → X → screens 有环）----
    common_deps = _imported(os.path.join(HERE, 'ui_v4_common.py'))
    fam_deps = {fn[:-3] for fn in FAMILY if fn != 'ui_v4_common.py'}
    bad = common_deps & fam_deps
    assert not bad, 'ui_v4_common 不得依赖家族内模块（底座必须零依赖）: %s' % bad
    _ok('ui_v4_common 保持零家族内依赖（底座成立）')

    print('\n[OK] ui_v4_screens 拆分守卫全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
