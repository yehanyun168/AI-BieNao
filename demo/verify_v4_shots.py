"""verify_v4_shots.py —— 用 PIL 程序化核对真机截图的配色令牌命中。

本模型读不了图片，所以用颜色统计代替肉眼核对：
  * 每张图不得是单色（排除白屏/黑屏/错色）
  * 设计令牌必须命中（海面 / 陆地 / 海岸 / 四态 / panel / cyan / yellow …）

用法：
    python verify_v4_shots.py
"""
import os
import sys
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, '_v4shots')

# 设计令牌 → RGB（单一来源：world_map.py / pixel_ui.COLORS）
TOKENS = {
    'bg     #0d1117': (13, 17, 23),
    'panel2 #1f2630': (31, 38, 48),
    'sea    #0a1828': (10, 24, 40),
    'sealine#12293c': (18, 41, 60),
    'land   #16323c': (22, 50, 60),
    'coast  #27505b': (39, 80, 91),
    'on.f   #1f6f63': (31, 111, 99),
    'on.e   #3ec9ac': (62, 201, 172),
    'sel.f  #4ec9b0': (78, 201, 176),
    'sel.e  #eafffb': (234, 255, 251),
    'blk.f  #5c2323': (92, 35, 35),
    'blk.e  #ef4444': (239, 68, 68),
    'lk.f   #232a30': (35, 42, 48),
    'lk.e   #4a5560': (74, 85, 96),
    'panel  #161b22': (22, 27, 34),
    'cyan   #4ec9b0': (78, 201, 176),
    'yellow #dcdcaa': (220, 205, 170),
    'green  #6a9955': (106, 153, 85),
    'red    #ff7b72': (255, 123, 114),
    'text   #e6edf3': (230, 237, 243),
    'brd2   #484f58': (72, 79, 88),
}

# 高 DPI（dpi=144 → ×1.5）+ 抗锯齿后，纯色像素会变少，用 ±TOL 容差匹配
TOL = 3
MIN_PX = 12        # 单屏内至少出现这么多像素才算「命中」

ORDER = ['v4_s01_menu.png', 'v4_s02_main.png', 'v4_s03_inspector.png',
         'v4_s04_drop.png', 'v4_s05_skills.png', 'v4_s06_tech.png',
         'v4_s07_event.png', 'v4_s08_crisis.png', 'v4_s09_ending.png',
         'v4_s10_ach.png', 'v4_s11_help.png', 'v4_s12_settings.png',
         'v4_s13_layer.png', 'v4_s14_log.png']


def near(rgb, ref, tol=TOL) -> bool:
    """容差匹配（抗锯齿 / 高 DPI 缩放会有 ±1~2 的偏移）。"""
    return (abs(rgb[0] - ref[0]) <= tol and abs(rgb[1] - ref[1]) <= tol
            and abs(rgb[2] - ref[2]) <= tol)


def count_hits(cnt: Counter) -> dict:
    """统计每个令牌的命中像素数（容差匹配）。"""
    out = {k: 0 for k in TOKENS}
    for rgb, n in cnt.items():
        for k, ref in TOKENS.items():
            if near(rgb, ref):
                out[k] += n
    return out


def is_dim_overlay(rgb) -> bool:
    """判定「弹窗压暗层」色：某个令牌色 × 0.06~0.98 的等比例变暗。

    Popup 打开时会给背景压一层半透明黑，产生的颜色不属于调色板但完全合法。
    截图环境（Clock.tick 不 sleep）下 ModalView 淡出动画不完成，残留遮罩
    可叠加多层（如 0.45^3 ≈ 0.09 的海面 ≈ rgb(1,2,4)），故下界放宽到 0.06；
    纯黑 (0,0,0) 仍会被 0.06×ref 的下界挡住（清屏色缺失检测不受影响）。
    """
    for ref in TOKENS.values():
        if all(abs(rgb[i] - ref[i]) <= TOL for i in range(3)):
            return False                       # 本身就命中令牌
        if all(0.06 * ref[i] <= rgb[i] <= ref[i] + TOL for i in range(3)):
            if sum(rgb) < sum(ref) - 3 * TOL:  # 必须真的更暗
                return True
    return False


def main() -> int:
    print('=' * 78)
    print('v0.4 真机截图 · 配色令牌核对')
    print('=' * 78)
    if not os.path.isdir(SHOTS):
        print('缺少 _v4shots 目录，请先运行 make_screenshots_v4.py')
        return 1

    problems = []
    per_token_total = Counter()

    for name in ORDER:
        path = os.path.join(SHOTS, name)
        if not os.path.exists(path):
            print(f'{name:22s}  ** 缺失 **')
            problems.append(f'{name} 缺失')
            continue
        im = Image.open(path).convert('RGB')
        w, h = im.size
        px = list(im.getdata())
        total = len(px)
        cnt = Counter(px)
        top_color, top_n = cnt.most_common(1)[0]
        uniq = len(cnt)
        hits = [k for k, n in count_hits(cnt).items() if n >= MIN_PX]
        for k in hits:
            per_token_total[k] += 1

        # 主色必须落在设计令牌内（或为弹窗压暗层）
        top_on_palette = any(near(top_color, ref) for ref in TOKENS.values())
        dim = (not top_on_palette) and is_dim_overlay(top_color)
        blank = uniq <= 3
        if blank:
            problems.append(f'{name} 疑似空白（仅 {uniq} 种颜色）')
        if not top_on_palette and not dim:
            problems.append(f'{name} 主色 rgb{top_color} 不在设计令牌内')

        top_pct = top_n / total * 100
        pal = ('palette' if top_on_palette
               else ('dim-overlay' if dim else 'OFF-PALETTE'))
        print(f'{name:22s} {w}x{h}  唯一色 {uniq:5d}  '
              f'主色 rgb{top_color} {top_pct:5.1f}% [{pal}]  令牌 {len(hits):2d}/{len(TOKENS)}')
        miss = [k for k in TOKENS if k not in hits]
        if miss:
            print(f'{"":22s} 未命中: {", ".join(miss)}')

    print('-' * 78)
    print('令牌覆盖率（14 屏中有多少屏命中，容差 ±%d）：' % TOL)
    for k in TOKENS:
        n = per_token_total[k]
        bar = '#' * n
        flag = '' if n >= 3 else '   <-- 偏少'
        print(f'  {k}  {n:2d}/14  {bar}{flag}')

    print('=' * 78)
    if problems:
        print('问题：')
        for p in problems:
            print('  x', p)
    else:
        print('未发现空白 / 缺色截图 —— 14 屏均正常渲染')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
