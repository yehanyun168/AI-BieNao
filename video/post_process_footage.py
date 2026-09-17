"""post_process_footage.py — 为 30 镜实机截图做最后的人工修正覆盖层。

当前由自动截图解决不掉的两个问题：
  1. S13_darknet：Kivy Window.screenshot 不强制重绘，canvas.after 的红框永远落不到帧缓冲，
     导致 S13 与 S12 完全相同；这里用 PIL 在已保存的 PNG 上直接画上暗网卡高亮。
  2. S25_threshold：自动脚本运行到 S24/S25 时游戏被「多国联合调查已启动」危机弹窗遮挡，
     两次操作都没改变弹窗像素，导致 S25 与 S24 完全相同；这里给 S25 加一个阈值提示高亮。

坐标从 1440×880 的实机截图上人工估算，只修改这两张 PNG，其余 28 张保持原样。
"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
FOOTAGE = os.path.join(HERE, 'assets', 'footage')

# 像素风高亮色（与 UI 中 suspicion/警告色一致）
HIGHLIGHT = (245, 78, 72)       # #F54E48 偏橙红
HIGHLIGHT_FILL = (245, 78, 72, 65)  # 约 25% 不透明度


def _overlay_box(path, box, border=4, corner_radius=0):
    """在 PNG 上画一个半透明填充 + 实心边框的高亮框，保存覆盖原文件。"""
    im = Image.open(path).convert('RGBA')
    overlay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x1, y1, x2, y2 = box
    if corner_radius:
        draw.rounded_rectangle(box, radius=corner_radius, fill=HIGHLIGHT_FILL)
        draw.rounded_rectangle(box, radius=corner_radius, outline=HIGHLIGHT, width=border)
    else:
        draw.rectangle(box, fill=HIGHLIGHT_FILL)
        draw.rectangle(box, outline=HIGHLIGHT, width=border)
    im = Image.alpha_composite(im, overlay)
    im.save(path, 'PNG')
    print('[post] %s -> overlay %s' % (os.path.basename(path), box))


def main():
    # S13：暗网卡是高亮框。从 S12_origins.png 目测，5 张出身卡竖排，
    # 最下方「地下暗网」卡约占 y=615~755（PIL 顶向下），左右贴边留 12px 边距。
    s13 = os.path.join(FOOTAGE, 'S13_darknet.png')
    _overlay_box(s13, (12, 615, 1428, 755), border=5, corner_radius=6)

    # S25：危机弹窗底部进度条/倒计时区域，强调「阈值」概念。
    # 弹窗居中，底部进度条约在 x=320~1060, y=520~555（PIL 顶向下）。
    s25 = os.path.join(FOOTAGE, 'S25_threshold.png')
    _overlay_box(s25, (320, 522, 1060, 553), border=4, corner_radius=0)

    print('[post] done')


if __name__ == '__main__':
    main()
