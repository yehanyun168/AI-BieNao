"""
check_map_palette.py - 校验 demo/world_map.py 的配色是否仍与设计稿一致，
并守住 P1-5 无障碍令牌门槛（对比度 / 色盲 ΔE）。

背景
----
``world_map.py`` 的颜色常量是从设计稿位图
``design/ardot_ui/pixel_world_map_880x484.png`` 直接取样得到的，不是手调的
近似值。但"取样"这个事实本身容易随时间失真 —— 有人改了常量、或换了设计稿，
两边就悄悄对不上了，而肉眼看地图只是"稍微有点不一样"，很难发现。

本脚本把这条隐式约定变成可执行的检查：
  1. 重新从设计稿取样（海面 / 陆地 / 已占 / 选中 / 海岸）；
  2. 与 ``world_map.py`` 里的常量逐个比对；
  3. 不一致就报错并给出 delta，退出码非 0。

P1-5 新增（无障碍守卫，纯标准库、不依赖 Kivy/Pillow 之外的东西）：
  4. 令牌期望表：demo/pixel_ui.py 的 COLORS 与 demo/ui_v4.py 的 MK/ST_EDGE
     必须与 A11Y_EXPECT 一致（改令牌要连期望表一起改，是有意识的动作）；
  5. WCAG 对比度门槛：正文 ≥4.5、大字/图形 ≥3.0，逐配对打印实测与差距；
  6. 色盲可辨门槛：红/琥珀在绿色盲与红色盲模拟下 ΔE(CIE76) ≥ 25；
  7. 设计稿偏离对照（信息项）：P1-5 有意让部分令牌偏离设计稿 :root
     （无障碍优先），偏离项在这里显式列出，不留暗改。

用法::

    python tools/check_map_palette.py            # 全部校验
    python tools/check_map_palette.py --dump     # 只打印设计稿取样结果（调色用）

依赖 Pillow（只在开发机跑，不进游戏运行时）。
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from pathlib import Path

try:
    from PIL import Image
except ImportError:                                     # pragma: no cover
    print('需要 Pillow：pip install pillow')
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
PNG = ROOT / 'design' / 'ardot_ui' / 'pixel_world_map_880x484.png'
SRC = ROOT / 'demo' / 'world_map.py'
PIXEL_UI = ROOT / 'demo' / 'pixel_ui.py'
UI_V4 = ROOT / 'demo' / 'ui_v4.py'
DESIGN_HTML = ROOT / 'design' / 'ui_design_v0.4.html'

# 取样点：(设计稿像素坐标, world_map 常量名, 说明)
# 坐标是在 880x484 原图上人工确认过的稳定区域（避开边界/文字）。
SAMPLES = [
    ((2, 2),       'SEA',       '海面（左上角）'),
    ((500, 300),   'LAND',      '无名陆地（撒哈拉内陆，非 20 国领土）'),
]

# 需要从源码里读出来的常量 → 期望值来源
STATE_SAMPLES = [
    ((640, 120), 'on',  '已占'),
    ((770, 370), 'lk',  '未解锁'),
]

TOL = 2      # 允许每通道 ±2 的误差（位图压缩/抗锯齿）


# ============================================================
# P1-5 无障碍门槛配置（改令牌 = 连这里一起改，两层都要过）
# ============================================================
# 期望表：令牌唯一来源仍是 pixel_ui.COLORS / ui_v4.MK / ui_v4.ST_EDGE。
A11Y_EXPECT = {
    ('pixel_ui', 'text_mute'): ('#8b9099', '静音文本（P1-5 提亮，AA 达标）'),
    ('pixel_ui', 'orange'):    ('#ffbe5c', '警告琥珀（P1-5 色盲可辨版）'),
    ('pixel_ui', 'red'):       ('#ff7b72', '警示红（未改动）'),
    ('pixel_ui', 'bg'):        ('#0d1117', '主底'),
    ('pixel_ui', 'panel'):     ('#161b22', '主面板'),
    ('pixel_ui', 'panel_2'):   ('#1f2630', '次面板'),
    ('ui_v4_mk', 'lock'):      ('#6e7681', '锁定/禁用文字（P1-5 提亮）'),
    # 令牌名 st_blk（ui_v4.MK['st_blk'] 语义）；源码解析落在 ST_EDGE 字典键 'blk'
    ('ui_v4_edge', 'st_blk'):  ('#ef4444', '地图封锁红（未改动）'),
}

# 对比度门槛：(前景令牌, 背景令牌, 下限, 说明)
# WCAG 2.1：正文 ≥4.5；大字（≥24px）/图形 ≥3.0。
CONTRAST_CHECKS = [
    ('text_mute', 'bg',      4.5, '静音文本 / 主底'),
    ('text_mute', 'panel',   4.5, '静音文本 / 主面板'),
    ('text_mute', 'panel_2', 4.5, '静音文本 / 次面板'),
    ('lock',      'bg',      3.0, '锁定/禁用文字 / 主底'),
    ('lock',      'panel_2', 3.0, '锁定/禁用文字 / 次面板'),
    ('orange',    'bg',      4.5, '警告琥珀文字 / 主底'),
    ('orange',    'panel_2', 4.5, '警告琥珀文字 / 次面板'),
]

# 色盲可辨门槛：(色A令牌, 色B令牌, 模拟, ΔE 下限, 说明)
# ΔE 用 CIE76；模拟用 Machado et al. 2009 severity 1.0 矩阵（线性 RGB 域）。
CVD_CHECKS = [
    ('st_blk', 'orange', 'deutan', 25.0, '封锁红 vs 警告琥珀（绿色盲）'),
    ('red',    'orange', 'deutan', 25.0, '警示红 vs 警告琥珀（绿色盲）'),
    ('st_blk', 'orange', 'protan', 25.0, '封锁红 vs 警告琥珀（红色盲）'),
    ('red',    'orange', 'protan', 25.0, '警示红 vs 警告琥珀（红色盲）'),
]

_CVD_MATRIX = {
    'deutan': ((0.367322, 0.860646, -0.227968),
               (0.280085, 0.672501, 0.047413),
               (-0.011820, 0.042940, 0.968881)),
    'protan': ((0.152286, 1.052583, -0.204868),
               (0.114503, 0.786281, 0.099216),
               (-0.003882, -0.048116, 1.051998)),
}

# 设计稿 :root 变量 → 本工具令牌名（信息项：列出有意的无障碍取舍，不判失败）
DESIGN_VARS = {'--text-mute': 'text_mute', '--orange': 'orange',
               '--red': 'red', '--border-strong': 'lock'}


def _hex(rgb) -> str:
    return '#%02x%02x%02x' % tuple(rgb[:3])


def _parse_const(src: str, name: str):
    """从源码文本里取 ``NAME = '#rrggbb'`` 的值（不做 import，避免拉 kivy）。"""
    m = re.search(rf"^{name}\s*=\s*'(#[0-9a-fA-F]{{6}})'", src, re.M)
    return m.group(1).lower() if m else None


def _parse_state_fill(src: str, key: str):
    m = re.search(r"STATE_FILL\s*=\s*\{([^}]*)\}", src, re.S)
    if not m:
        return None
    m2 = re.search(rf"'{key}'\s*:\s*'(#[0-9a-fA-F]{{6}})'", m.group(1))
    return m2.group(1).lower() if m2 else None


def _parse_color(src: str, name: str):
    """pixel_ui.py 的 ``'name': (r, g, b, a),`` → '#rrggbb'（按元组真值换算，
    不读行尾注释 —— 注释只是文档，元组才是运行时真值）。"""
    m = re.search(rf"'{name}'\s*:\s*\(([\d.\s,]+)\)", src)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(',') if p.strip()]
    if len(parts) < 3:
        return None
    return '#%02x%02x%02x' % tuple(
        min(max(int(round(float(p) * 255)), 0), 255) for p in parts[:3])


def _parse_mk(src: str, key: str):
    """ui_v4.py 的 ``MK['key'] = 'rrggbb'``（MK 字面量按惯例不带 #）。"""
    m = re.search(rf"MK\['{key}'\]\s*=\s*'(?:#)?([0-9a-fA-F]{{6}})'", src)
    return ('#' + m.group(1).lower()) if m else None


def _parse_edge(src: str, key: str):
    """ui_v4.py 的 ST_EDGE 字典里的 ``'key': '#rrggbb'``。"""
    m = re.search(r"ST_EDGE[^=]*=\s*\{(.*?)\}", src, re.S)
    if not m:
        return None
    m2 = re.search(rf"'{key}'\s*:\s*'(#[0-9a-fA-F]{{6}})'", m.group(1))
    return m2.group(1).lower() if m2 else None


def _parse_design_var(html: str, var: str):
    m = re.search(rf"{var}\s*:\s*#([0-9a-fA-F]{{6}})", html)
    return ('#' + m.group(1).lower()) if m else None


def _delta(a: str, b: str) -> int:
    va = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    vb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return max(abs(x - y) for x, y in zip(va, vb))


# ---- WCAG 对比度（纯标准库）----
def _s2l(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _wcag_lum(h: str) -> float:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return (0.2126 * _s2l(r) + 0.7152 * _s2l(g) + 0.0722 * _s2l(b))


def _contrast(h1: str, h2: str) -> float:
    l1, l2 = sorted((_wcag_lum(h1), _wcag_lum(h2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


# ---- 色盲模拟 + CIE76 ΔE（纯标准库）----
def _lab(h: str):
    r, g, b = (_s2l(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b

    def f(t):
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _l2s(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _cvd(h: str, m) -> str:
    """Machado 2009 模拟矩阵作用在线性 RGB，再重编码回 sRGB hex。"""
    lin = [_s2l(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5)]
    out = [min(max(sum(c * x for c, x in zip(row, lin)), 0.0), 1.0) for row in m]
    return '#%02x%02x%02x' % tuple(round(_l2s(v) * 255) for v in out)


def _dE76(h1: str, h2: str, m=None) -> float:
    a, b = (_cvd(x, m) if m else x for x in (h1, h2))
    (L1, a1, b1), (L2, a2, b2) = _lab(a), _lab(b)
    return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)


def check_a11y(fails: list):
    """P1-5 无障碍门槛：期望表 → 对比度 → 色盲 ΔE → 设计稿偏离对照。

    返回 (检查项数, 失败项数)；失败项已追加进 fails。
    """
    checks, a11y_fails = 0, 0
    if not PIXEL_UI.exists():
        fails.append('demo/pixel_ui.py 缺失，无障碍门槛无法校验')
        print('  [MISS] demo/pixel_ui.py 缺失')
        return 0, 1
    pu = PIXEL_UI.read_text(encoding='utf-8')
    uv = UI_V4.read_text(encoding='utf-8') if UI_V4.exists() else None

    # 1) 期望表：源码值必须与 A11Y_EXPECT 一致
    print('  令牌期望表（改令牌请同步 A11Y_EXPECT）：')
    tok = {}
    for (src_name, key), (want, desc) in A11Y_EXPECT.items():
        checks += 1
        if src_name == 'pixel_ui':
            got = _parse_color(pu, key)
        elif src_name == 'ui_v4_mk':
            got = _parse_mk(uv, key) if uv else None
        else:
            # ui_v4_edge：令牌名 st_blk → ST_EDGE 字典键 'blk'
            got = _parse_edge(uv, 'blk') if uv else None
        tok[key] = got
        if got is None:
            a11y_fails += 1
            fails.append(f'{key}: 源码缺令牌（{src_name}）')
            print(f'  [MISS] {key:<10} 源码缺令牌（{desc}）')
        elif got != want:
            a11y_fails += 1
            fails.append(f'{key}: 源码 {got} vs 期望 {want}')
            print(f'  [FAIL] {key:<10} 源码 {got} != 期望 {want} '
                  f'(Δ{_delta(got, want)})  （{desc}）')
        else:
            print(f'  [OK]   {key:<10} {want}  （{desc}）')

    # 2) WCAG 对比度门槛
    print('  对比度门槛（正文 ≥4.5 / 图形 ≥3.0）：')
    for fg, bg, floor, desc in CONTRAST_CHECKS:
        checks += 1
        if tok.get(fg) is None or tok.get(bg) is None:
            a11y_fails += 1
            fails.append(f'contrast({fg},{bg}): 令牌缺失')
            print(f'  [MISS] {fg} on {bg}  令牌缺失（{desc}）')
            continue
        c = _contrast(tok[fg], tok[bg])
        if c >= floor:
            print(f'  [OK]   {fg} on {bg:<8} {c:.2f}:1 ≥ {floor}  （{desc}）')
        else:
            a11y_fails += 1
            fails.append(f'contrast({fg} on {bg}): {c:.2f} < {floor}')
            print(f'  [FAIL] {fg} on {bg:<8} {c:.2f}:1 < {floor} '
                  f'(差 {c - floor:+.2f})  （{desc}）')

    # 3) 色盲可辨门槛（ΔE CIE76 ≥ 25）
    print('  色盲可辨门槛（ΔE CIE76 ≥ 25，Machado 2009 模拟）：')
    for ka, kb, kind, floor, desc in CVD_CHECKS:
        checks += 1
        if tok.get(ka) is None or tok.get(kb) is None:
            a11y_fails += 1
            fails.append(f'cvd({ka},{kb},{kind}): 令牌缺失')
            print(f'  [MISS] {ka} vs {kb} [{kind}]  令牌缺失（{desc}）')
            continue
        de = _dE76(tok[ka], tok[kb], _CVD_MATRIX[kind])
        if de >= floor:
            print(f'  [OK]   {ka} vs {kb} [{kind}]  ΔE {de:.1f} ≥ {floor:.0f} '
                  f'(余量 {de - floor:+.1f})  （{desc}）')
        else:
            a11y_fails += 1
            fails.append(f'cvd({ka} vs {kb}, {kind}): ΔE {de:.1f} < {floor:.0f}')
            print(f'  [FAIL] {ka} vs {kb} [{kind}]  ΔE {de:.1f} < {floor:.0f} '
                  f'(差 {de - floor:+.1f})  （{desc}）')

    # 4) 设计稿偏离对照（信息项，不判失败 —— P1-5 有意的无障碍取舍）
    if DESIGN_HTML.exists():
        html = DESIGN_HTML.read_text(encoding='utf-8')
        for var, key in DESIGN_VARS.items():
            dv = _parse_design_var(html, var)
            if dv and tok.get(key) and dv != tok[key]:
                print(f'  [偏离] {key} {tok[key]} != 设计稿 {var}:{dv}'
                      f'  （P1-5 有意取舍：无障碍优先，记录在案）')
    return checks, a11y_fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', action='store_true',
                    help='只打印设计稿取样结果（用于人工调色）')
    args = ap.parse_args()

    im = None
    if PNG.exists():
        im = Image.open(PNG).convert('RGBA')
    else:
        print(f'[SKIP] 找不到设计稿底图，跳过取样比对：{PNG}')
    if not SRC.exists():
        print(f'[SKIP] 找不到源文件，跳过取样比对：{SRC}')

    if args.dump:
        if im is None:
            print('无设计稿底图，--dump 不可用')
            return 2
        print(f'设计稿 {PNG.name} 主色（按像素数降序）：')
        for col, n in Counter(im.getdata()).most_common(14):
            print(f'  {_hex(col)}  {n:>7}  a={col[3]}')
        return 0

    fails, checks = [], 0
    if im is not None and SRC.exists():
        src = SRC.read_text(encoding='utf-8')
        print(f'取样源：{PNG.name}   比对源：{SRC.name}')
        print('-' * 62)

        for (px, py), const, desc in SAMPLES:
            if const is None:
                continue
            got_design = _hex(im.getpixel((px, py)))
            want = _parse_const(src, const)
            checks += 1
            if want is None:
                fails.append(f'{const} 在源码里没找到')
                print(f'  [MISS] {const:<10} 源码缺该常量（{desc}）')
            elif _delta(got_design, want) <= TOL:
                print(f'  [OK]   {const:<10} {want}  == 设计稿 {got_design}  ({desc})')
            else:
                fails.append(f'{const}: 源码 {want} vs 设计稿 {got_design}')
                print(f'  [FAIL] {const:<10} 源码 {want} != 设计稿 {got_design} '
                      f'(Δ{_delta(got_design, want)})  ({desc})')

        for (px, py), key, desc in STATE_SAMPLES:
            got_design = _hex(im.getpixel((px, py)))
            want = _parse_state_fill(src, key)
            checks += 1
            if want is None:
                fails.append(f'STATE_FILL[{key}] 缺失')
                print(f'  [MISS] STATE_FILL[{key}] 源码缺该键（{desc}）')
            elif _delta(got_design, want) <= TOL:
                print(f'  [OK]   STATE_FILL[{key}] {want}  == 设计稿 {got_design}  ({desc})')
            else:
                fails.append(f'STATE_FILL[{key}]: {want} vs {got_design}')
                print(f'  [FAIL] STATE_FILL[{key}] {want} != 设计稿 {got_design} '
                      f'(Δ{_delta(got_design, want)})  ({desc})')

        print('-' * 62)
        if fails:
            print(f'配色与设计稿不一致（{len(fails)} 项）：')
            for f in fails:
                print(f'  - {f}')
            print('\n若设计稿已更新，请以设计稿为准同步 world_map.py 的常量；')
            print('若是误改，请还原常量后重跑。')
        else:
            print(f'配色与设计稿一致（{checks}/{checks} 项通过，容差 ±{TOL}）')

    # ---- P1-5 无障碍守卫（不依赖设计稿位图，令牌改动在这里被拦）----
    print('-' * 62)
    print(f'无障碍门槛：比对源 {PIXEL_UI.name} / {UI_V4.name}')
    print('-' * 62)
    n_checks, n_fails = check_a11y(fails)
    if n_fails:
        print('\n无障碍门槛未达标（见上方 [FAIL]/[MISS]，已计入失败清单）。')
        print('令牌以无障碍达标为准：确要改令牌时，请同步 A11Y_EXPECT，')
        print('并保证对比度 / ΔE 门槛全部通过。')
    elif n_checks:
        print(f'无障碍门槛全部通过（{n_checks}/{n_checks} 项）')

    if fails:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
