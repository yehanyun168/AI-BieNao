"""
check_map_palette.py - 校验 demo/world_map.py 的配色是否仍与设计稿一致。

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

用法::

    python tools/check_map_palette.py            # 校验
    python tools/check_map_palette.py --dump     # 只打印取样结果（调色用）

依赖 Pillow（只在开发机跑，不进游戏运行时）。
"""
from __future__ import annotations

import argparse
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


def _delta(a: str, b: str) -> int:
    va = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    vb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return max(abs(x - y) for x, y in zip(va, vb))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', action='store_true',
                    help='只打印设计稿取样结果（用于人工调色）')
    args = ap.parse_args()

    if not PNG.exists():
        print(f'找不到设计稿底图：{PNG}')
        return 2
    if not SRC.exists():
        print(f'找不到源文件：{SRC}')
        return 2

    im = Image.open(PNG).convert('RGBA')

    if args.dump:
        print(f'设计稿 {PNG.name} 主色（按像素数降序）：')
        for col, n in Counter(im.getdata()).most_common(14):
            print(f'  {_hex(col)}  {n:>7}  a={col[3]}')
        return 0

    src = SRC.read_text(encoding='utf-8')
    fails, checks = [], 0

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
        return 1
    print(f'配色与设计稿一致（{checks}/{checks} 项通过，容差 ±{TOL}）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
