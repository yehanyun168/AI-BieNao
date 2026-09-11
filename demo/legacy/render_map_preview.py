"""
render_map_preview.py - 用 matplotlib 重绘 world_map 生成预览 PNG

说明：
  - matplotlib 版用 polygon 主色填充，避免 bbox 覆盖导致的国旗重叠 bug
  - 实际游戏中 Kivy 使用 Stencil 裁切国旗到 polygon 内部，可正确显示完整国旗底色
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # demo/

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib import font_manager

# 注册中文字体
for fp in [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]:
    if os.path.exists(fp):
        try:
            font_manager.fontManager.addfont(fp)
        except Exception:
            pass
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

import world_map as wm
import i18n


# 配色
SEA = (0.04, 0.10, 0.18)
BORDER = (0.95, 0.97, 0.99)
LABEL_BG = (0.08, 0.10, 0.16)
LABEL_TXT = (0.95, 0.97, 0.99)


def render(out_path, lang='zh'):
    i18n.set_lang(lang)
    fig, ax = plt.subplots(figsize=(20, 9), dpi=100)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')
    ax.set_facecolor(SEA)
    fig.patch.set_facecolor(SEA)

    # 经纬线
    for i in range(1, 10):
        ax.axhline(y=i/10, color=(0.4, 0.6, 0.85), linewidth=0.3, alpha=0.3, zorder=0)
        ax.axvline(x=i/10, color=(0.4, 0.6, 0.85), linewidth=0.3, alpha=0.3, zorder=0)

    # 大洲标签（背景感）
    continents = [
        ('亚洲', 0.78, 0.60), ('欧洲', 0.55, 0.55), ('非洲', 0.55, 0.30),
        ('北美', 0.20, 0.65), ('南美', 0.27, 0.30), ('大洋洲', 0.82, 0.18),
    ]
    for cn, cx, cy in continents:
        cname = i18n.get_continent_name(cn) if hasattr(i18n, 'get_continent_name') else cn
        ax.text(cx, cy, cname,
                ha='center', va='center', fontsize=14,
                color=(0.45, 0.58, 0.72), alpha=0.30, style='italic')

    # 国家：海面底色 → 主色填充 polygon → 白色国境线
    for code, style in wm.COUNTRY_STYLES.items():
        poly_screen = [(gx, 1-gy) for gx, gy in style['polygon']]
        ax.add_patch(MplPolygon(poly_screen, closed=True, facecolor=SEA, edgecolor='none'))
        ax.add_patch(MplPolygon(poly_screen, closed=True,
                                facecolor=style['color'][:3],
                                alpha=style['color'][3],
                                edgecolor='none'))
        ax.add_patch(MplPolygon(poly_screen, closed=True,
                                facecolor=(0, 0, 0, 0),
                                edgecolor=BORDER, linewidth=1.5))

    # 国家代码标签
    for code, (gx, gy) in wm.COUNTRY_CENTERS.items():
        sx, sy = gx, 1-gy
        name = i18n.get_country_name(code)
        ax.text(sx, sy+0.014, code,
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=LABEL_TXT,
                bbox=dict(boxstyle='square,pad=0.35', facecolor=LABEL_BG, edgecolor=BORDER, linewidth=0.8))
        ax.text(sx, sy-0.014, name,
                ha='center', va='top', fontsize=7,
                color=(0.75, 0.82, 0.92))

    title = "AI 别闹 — v4 精细化地图 + 国旗底色" if lang == 'zh' else "AI Bienao — v4 Detailed Map + Flag Background"
    ax.set_title(title, fontsize=16, color=LABEL_TXT, pad=15)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)

    plt.tight_layout()
    plt.savefig(out_path, dpi=100, facecolor=SEA, bbox_inches='tight')
    plt.close()
    print(f"📸 saved: {out_path}")


if __name__ == '__main__':
    out_dir = os.path.dirname(os.path.abspath(__file__))
    render(os.path.join(out_dir, '_preview_map_zh.png'), lang='zh')
    render(os.path.join(out_dir, '_preview_map_en.png'), lang='en')