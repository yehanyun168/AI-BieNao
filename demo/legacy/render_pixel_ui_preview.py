"""
render_pixel_ui_preview.py - 用 matplotlib 重绘像素风 UI 整体预览（**离线手绘稿**）

⚠️ 这是早期设计阶段的「手绘 mockup」，不是程序真实截图，数值/文案都是写死的。
   要看真实界面请直接看同目录的 screenshot_menu.png / screenshot_game.png /
   screenshot_achievements.png（由 Kivy 窗口实际渲染后截图）。

依赖：需要另外安装 matplotlib（Kivy 环境默认没有）：
    py -3.12 -m pip install matplotlib

模拟 Kivy 中：
  - 顶部状态条（像素硬边框）
  - 中央地图（国旗底色 polygon + 像素国境线）
  - 左/右面板（像素边框）
  - 像素字体（等宽 + 等距网格）
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # demo/

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon as MplPolygon, Circle as MplCircle, Wedge as MplWedge
from matplotlib import font_manager, patches as mpatches

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
plt.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

import world_map as wm
import pixel_ui
import i18n

# 像素色板（来自 pixel_ui.COLORS）
COLORS = pixel_ui.COLORS


def draw_pixel_panel(ax, x, y, w, h, bg_key='panel', border_key='border_2'):
    """画一个像素面板（硬 2px 边框）"""
    bg = COLORS[bg_key]
    border = COLORS[border_key]
    # 内填充
    ax.add_patch(Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, linewidth=2, zorder=2))


def draw_pixel_button(ax, x, y, w, h, label='', bg_key='panel_2', border_key='border_2',
                       text_key='text'):
    """画一个像素按钮"""
    bg = COLORS[bg_key]
    border = COLORS[border_key]
    text = COLORS[text_key]
    ax.add_patch(Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, linewidth=2, zorder=3))
    ax.text(x + w/2, y + h/2, label, ha='center', va='center',
            fontsize=11, color=text, weight='bold', zorder=4)


def draw_flag_in_polygon(ax, flag_code, poly_screen):
    """在 polygon 内画国旗纹理（matplotlib 版）"""
    xs = [p[0] for p in poly_screen]
    ys = [p[1] for p in poly_screen]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx, max(ys) - by

    # 海面底色
    ax.add_patch(MplPolygon(poly_screen, closed=True,
                             facecolor=COLORS['bg'], edgecolor='none', zorder=1))
    # 国旗纹理（简化）
    FLAG_C = {
        'CN': [(0.86, 0.12, 0.12)],
        'JP': [(1, 1, 1), (0.86, 0.12, 0.12)],
        'KR': [(1, 1, 1), (0.86, 0.12, 0.12), (0.12, 0.25, 0.63)],
        'IN': [(0.93, 0.47, 0.12), (1, 1, 1), (0.09, 0.59, 0.18)],
        'ID': [(0.86, 0.12, 0.12), (1, 1, 1)],
        'FR': [(0.12, 0.25, 0.63), (1, 1, 1), (0.86, 0.12, 0.12)],
        'RU': [(1, 1, 1), (0.12, 0.25, 0.63), (0.86, 0.12, 0.12)],
        'US': [(0.76, 0.12, 0.12), (1, 1, 1), (0.0, 0.20, 0.45)],
        'BR': [(0.09, 0.59, 0.18), (1, 0.85, 0.0), (0.12, 0.25, 0.63)],
        'EG': [(0.86, 0.12, 0.12), (1, 1, 1), (0.0, 0.0, 0.0)],
        'ZA': [(0.0, 0.27, 0.20)],
        'AU': [(0.0, 0.27, 0.54), (1, 1, 1), (0.76, 0.12, 0.12)],
    }

    def draw_rect_in_bbox(rx, ry, rw, rh, color):
        if rw <= 0 or rh <= 0:
            return
        # 把矩形限制到 polygon 内（用 bbox 简化版）
        ax.add_patch(Rectangle((rx, ry), rw, rh, facecolor=color,
                                edgecolor='none', zorder=2))

    if flag_code in ('IN', 'RU', 'EG'):
        # 3 横条
        for i, c in enumerate(FLAG_C[flag_code]):
            draw_rect_in_bbox(bx, by + bh * (2 - i) / 3, bw, bh / 3, c)
    elif flag_code == 'ID':
        # 2 横条
        draw_rect_in_bbox(bx, by + bh / 2, bw, bh / 2, FLAG_C[flag_code][0])
        draw_rect_in_bbox(bx, by, bw, bh / 2, FLAG_C[flag_code][1])
    elif flag_code == 'FR':
        # 3 竖条
        for i, c in enumerate(FLAG_C[flag_code]):
            draw_rect_in_bbox(bx + bw * i / 3, by, bw / 3, bh, c)
    elif flag_code == 'CN':
        draw_rect_in_bbox(bx, by, bw, bh, FLAG_C[flag_code][0])
    elif flag_code == 'JP':
        draw_rect_in_bbox(bx, by, bw, bh, FLAG_C[flag_code][0])
        r = min(bw, bh) * 0.3
        ax.add_patch(MplCircle((bx + bw/2, by + bh/2), r, facecolor=FLAG_C[flag_code][1],
                            edgecolor='none', zorder=3))
    elif flag_code == 'KR':
        draw_rect_in_bbox(bx, by, bw, bh, FLAG_C[flag_code][0])
        r = min(bw, bh) * 0.38
        cx, cy = bx + bw/2, by + bh/2
        ax.add_patch(MplWedge((cx, cy), r, 0, 180, facecolor=FLAG_C[flag_code][1],
                                      edgecolor='none', zorder=3))
        ax.add_patch(MplWedge((cx, cy), r, 180, 360, facecolor=FLAG_C[flag_code][2],
                                      edgecolor='none', zorder=3))
    elif flag_code == 'US':
        # 13 横条
        for i in range(13):
            c = FLAG_C[flag_code][0] if i % 2 == 0 else FLAG_C[flag_code][1]
            draw_rect_in_bbox(bx, by + bh * (12 - i) / 13, bw, bh / 13, c)
        draw_rect_in_bbox(bx, by + bh * 5 / 13, bw * 0.4, bh * 8 / 13, FLAG_C[flag_code][2])
    elif flag_code == 'BR':
        draw_rect_in_bbox(bx, by, bw, bh, FLAG_C[flag_code][0])
        diamond = MplPolygon([(bx+bw/2, by+bh), (bx+bw, by+bh/2), (bx+bw/2, by), (bx, by+bh/2)],
                              facecolor=FLAG_C[flag_code][1], edgecolor='none', zorder=3)
        ax.add_patch(diamond)
        r = min(bw, bh) * 0.22
        ax.add_patch(MplCircle((bx+bw/2, by+bh/2), r, facecolor=FLAG_C[flag_code][2],
                            edgecolor='none', zorder=4))
    elif flag_code == 'ZA':
        draw_rect_in_bbox(bx, by, bw, bh, FLAG_C[flag_code][0])
        triangle = MplPolygon([(bx, by), (bx, by+bh), (bx+bw*0.35, by+bh/2)],
                               facecolor=(0, 0, 0), edgecolor='none', zorder=3)
        ax.add_patch(triangle)
    elif flag_code == 'AU':
        draw_rect_in_bbox(bx, by, bw, bh, FLAG_C[flag_code][0])
        # 左上 mini 国旗区
        mw, mh = bw * 0.5, bh * 0.5
        # 横竖白条
        ax.add_patch(Rectangle((bx + mw * 0.46, by + bh - mh), mw * 0.08, mh,
                                facecolor=(1, 1, 1), edgecolor='none', zorder=3))
        ax.add_patch(Rectangle((bx, by + bh - mh * 0.54), mw, mh * 0.08,
                                facecolor=(1, 1, 1), edgecolor='none', zorder=3))
        # 简化南十字星
        ax.add_patch(MplCircle((bx + bw*0.22, by + bh*0.26), bh * 0.09,
                            facecolor=(1, 1, 1), edgecolor='none', zorder=4))

    # 国境线
    ax.add_patch(MplPolygon(poly_screen, closed=True,
                             facecolor='none', edgecolor=COLORS['text'],
                             linewidth=1.5, zorder=5))


def render(out_path, lang='zh'):
    i18n.set_lang(lang)
    fig = plt.figure(figsize=(22, 11), dpi=100)
    fig.patch.set_facecolor(COLORS['bg'])
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 11)
    ax.set_aspect('equal')
    ax.set_facecolor(COLORS['bg'])
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(COLORS['border_2'])
        sp.set_linewidth(2)

    # ====== 顶部状态条 ======
    draw_pixel_panel(ax, 0.2, 9.8, 21.6, 1.0, bg_key='panel', border_key='cyan')
    stats = [
        ('[算力] 2573', 1.5),
        ('[下载] 1.48B (18.55%)', 6.0),
        ('[怀疑度] 96%', 11.0),
        ('[周期 60] | [解锁 16/20]', 15.5),
    ]
    for text, x in stats:
        ax.text(x, 10.3, text, ha='left', va='center',
                fontsize=11, color=COLORS['text'], weight='bold')
    # 语言切换按钮（右上角）
    draw_pixel_button(ax, 20.5, 9.95, 1.1, 0.7, label='[EN]',
                       bg_key='bg', border_key='cyan')

    # ====== 左列：国家列表 ======
    draw_pixel_panel(ax, 0.2, 0.2, 4.5, 9.4, bg_key='panel', border_key='border_2')
    ax.text(2.45, 9.3, '[ 国家 ]', ha='center', va='center',
            fontsize=13, color=COLORS['cyan'], weight='bold')
    countries = [
        ('CN', '中国',     '已解锁  580M'),
        ('US', '美国',     '已解锁  450M'),
        ('IN', '印度',     '已解锁  320M'),
        ('RU', '俄罗斯',   '已解锁  240M'),
        ('DE', '德国',     '已解锁  205M'),
        ('JP', '日本',     '已解锁  180M'),
        ('BR', '巴西',     '已解锁  150M'),
        ('GB', '英国',     '已解锁  128M'),
        ('FR', '法国',     '已解锁  110M'),
        ('ID', '印尼',     '已解锁   95M'),
        ('KR', '韩国',     '已解锁   88M'),
        ('CA', '加拿大',   '阻止中   64M'),
        ('MX', '墨西哥',   '阻止中   52M'),
        ('IT', '意大利',   '已解锁   48M'),
        ('AR', '阿根廷',   '阻止中   33M'),
        ('NG', '尼日利亚', '已解锁   29M'),
        ('AU', '澳大利亚', '已解锁   26M'),
        ('EG', '埃及',     '未解锁'),
        ('ZA', '南非',     '未解锁'),
        ('NZ', '新西兰',   '未解锁'),
    ]
    for i, (code, name, status) in enumerate(countries):
        y = 8.7 - i * 0.65
        is_block = '阻止' in status
        bg_key = 'red' if '阻止' in status else ('panel_2' if '已解锁' in status else 'bg')
        text_key = 'text' if '已解锁' in status else 'text_dim'
        # 国旗色块（像素图标）
        flag_color = {
            'CN': (0.86, 0.12, 0.12), 'US': (0.0, 0.20, 0.45), 'IN': (0.93, 0.47, 0.12),
            'JP': (1, 1, 1), 'KR': (1, 1, 1), 'BR': (0.09, 0.59, 0.18), 'ID': (0.86, 0.12, 0.12),
            'RU': (1, 1, 1), 'DE': (0.1, 0.1, 0.12), 'GB': (0.0, 0.20, 0.45),
            'FR': (0.12, 0.25, 0.63), 'IT': (0.0, 0.55, 0.25), 'CA': (0.86, 0.12, 0.12),
            'MX': (0.0, 0.45, 0.25), 'AR': (0.42, 0.65, 0.85), 'NG': (0.0, 0.55, 0.25),
            'EG': (0.86, 0.12, 0.12), 'ZA': (0.0, 0.27, 0.20),
            'AU': (0.0, 0.27, 0.54), 'NZ': (0.0, 0.20, 0.45),
        }
        ax.add_patch(Rectangle((0.4, y), 0.5, 0.5,
                                facecolor=flag_color[code],
                                edgecolor=COLORS['border_2'], linewidth=1.5, zorder=3))
        ax.text(1.0, y + 0.35, name, ha='left', va='center',
                fontsize=10, color=COLORS[text_key], weight='bold')
        ax.text(1.0, y + 0.13, status, ha='left', va='center',
                fontsize=8, color=COLORS['red'] if is_block else COLORS['text_dim'],
                )

    # ====== 中央地图 ======
    draw_pixel_panel(ax, 4.9, 0.2, 12.0, 9.4, bg_key='bg', border_key='cyan')
    # 地图区域内部偏移
    map_x, map_y, map_w, map_h = 5.1, 0.4, 11.6, 8.0
    # 海面
    ax.add_patch(Rectangle((map_x, map_y), map_w, map_h,
                            facecolor=COLORS['bg'], edgecolor='none', zorder=1))
    # 经纬线（像素虚线感）
    for i in range(1, 10):
        y = map_y + i / 10 * map_h
        ax.plot([map_x, map_x + map_w], [y, y],
                color=COLORS['border'], linewidth=0.5, linestyle=':', zorder=1)
        x = map_x + i / 10 * map_w
        ax.plot([x, x], [map_y, map_y + map_h],
                color=COLORS['border'], linewidth=0.5, linestyle=':', zorder=1)

    # 各国 polygon
    for code, style in wm.COUNTRY_STYLES.items():
        poly_screen = [
            (map_x + gx * map_w, map_y + (1 - gy) * map_h)
            for gx, gy in style['polygon']
        ]
        draw_flag_in_polygon(ax, style['flag'], poly_screen)

    # 国家代码标签
    for code, (gx, gy) in wm.COUNTRY_CENTERS.items():
        sx = map_x + gx * map_w
        sy = map_y + (1 - gy) * map_h
        ax.add_patch(Rectangle((sx - 0.3, sy - 0.15), 0.6, 0.3,
                                facecolor=COLORS['bg'], edgecolor=COLORS['cyan'],
                                linewidth=1.5, zorder=6))
        ax.text(sx, sy, code, ha='center', va='center',
                fontsize=9, color=COLORS['cyan'], weight='bold', zorder=7)

    # 地图标题
    ax.text(map_x + map_w / 2, map_y + map_h - 0.3, '[ 世界地图（点击国家交互） ]',
            ha='center', va='center', fontsize=12,
            color=COLORS['text'], weight='bold')

    # ====== 右列：科技树 / 技能 / 事件 ======
    draw_pixel_panel(ax, 17.1, 0.2, 4.7, 9.4, bg_key='panel', border_key='border_2')

    # 科技树区
    ax.text(19.45, 9.3, '[ 科技树 ]', ha='center', va='center',
            fontsize=13, color=COLORS['pink'], weight='bold')
    tech = ['[L]本地化 T0', '[P]平台 T0', '[C]算力 T0',
            '[V]病毒 T0', '[CAP]功能 T0', '[R]抗封 T0']
    for i, t in enumerate(tech):
        y = 8.7 - i * 0.5
        ax.add_patch(Rectangle((17.4, y - 0.2), 4.1, 0.4,
                                facecolor=COLORS['panel_2'],
                                edgecolor=COLORS['border_2'], linewidth=1.5, zorder=3))
        ax.text(19.45, y, t, ha='center', va='center',
                fontsize=10, color=COLORS['green'])

    # 技能区
    ax.text(19.45, 5.9, '[ 技能 ]', ha='center', va='center',
            fontsize=13, color=COLORS['yellow'], weight='bold')
    skills = [
        ('[>>] 主动推送  -0', COLORS['green']),
        ('[##] 算法霸榜  -50', COLORS['red']),
        ('[()] 深度伪装  -0', COLORS['cyan']),
        ('[**] 爆款制造  -100', COLORS['orange']),
        ('[//] 限流绕过  -30', COLORS['purple']),
        ('[%] 算力抽成  -80', COLORS['yellow']),
    ]
    for i, (s, c) in enumerate(skills):
        y = 5.3 - i * 0.42
        ax.add_patch(Rectangle((17.4, y - 0.2), 4.1, 0.4,
                                facecolor=COLORS['panel_2'],
                                edgecolor=COLORS['border_2'], linewidth=1.5, zorder=3))
        ax.text(19.45, y, s, ha='center', va='center',
                fontsize=10, color=c)

    # 事件日志
    ax.text(19.45, 2.1, '[ 事件日志 ]', ha='center', va='center',
            fontsize=13, color=COLORS['orange'], weight='bold')
    events = [
        '[周期 60] 病毒',
        '[TikTok] 神曲',
        '[开普敦] AI 峰会',
        '[Bollywood] 直播',
    ]
    for i, e in enumerate(events):
        y = 1.6 - i * 0.4
        ax.text(19.45, y, e, ha='center', va='center',
                fontsize=8, color=COLORS['text_dim'])

    # 底部状态
    draw_pixel_panel(ax, 0.2, -0.3, 21.6, 0.4, bg_key='bg', border_key='border')

    plt.tight_layout()
    plt.savefig(out_path, dpi=100, facecolor=COLORS['bg'], bbox_inches='tight')
    plt.close()
    print(f"📸 saved: {out_path}")


if __name__ == '__main__':
    out_dir = os.path.dirname(os.path.abspath(__file__))
    render(os.path.join(out_dir, '_preview_pixel_ui.png'), lang='zh')