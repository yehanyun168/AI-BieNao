"""make_cover_assets.py - 从 AI 生成的封面原图加工发行资产。

用法：
  python tools/make_cover_assets.py

输入（AI 生成原图，人工挑选后固定文件名）：
  design/cover_src/cover_main_raw.png    横版主视觉原图（1536x1024）
  design/cover_src/icon_raw.png          正方形图标原图（1024x1024）

输出：
  demo/assets/cover/cover_main_1920x1080.png  主封面 16:9（商店/README 头图）
  demo/assets/cover/cover_main_1536x1024.png  主封面 3:2 原生分辨率备份
  demo/assets/cover/icon_512.png              图标用方形 PNG
  AI别闹.ico                                  PyInstaller exe 图标（16-256 多尺寸）
"""
import os
import sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'design', 'cover_src')
COVER_DIR = os.path.join(ROOT, 'demo', 'assets', 'cover')

MAIN_RAW = os.path.join(SRC, 'cover_main_raw.png')
ICON_RAW = os.path.join(SRC, 'icon_raw.png')


def make_cover():
    img = Image.open(MAIN_RAW).convert('RGB')
    w, h = img.size
    # --- 3:2 原生备份 ---
    img.save(os.path.join(COVER_DIR, 'cover_main_%dx%d.png' % (w, h)))
    # --- 16:9 居中裁切（标题在上部，上下各裁一半高度差） ---
    target_h = int(w * 9 / 16)
    if h > target_h:
        cut = (h - target_h) // 2
        img169 = img.crop((0, cut, w, cut + target_h))
    else:
        img169 = img
    # --- 放大到 1920x1080 ---
    img1920 = img169.resize((1920, 1080), Image.LANCZOS)
    p1920 = os.path.join(COVER_DIR, 'cover_main_1920x1080.png')
    img1920.save(p1920, optimize=True)
    print('[cover] %s (%dx%d)' % (p1920, 1920, 1080))


def make_icon():
    img = Image.open(ICON_RAW).convert('RGBA')
    # 方形图标 PNG 512
    p512 = os.path.join(COVER_DIR, 'icon_512.png')
    img.resize((512, 512), Image.LANCZOS).save(p512, optimize=True)
    print('[icon ] %s' % p512)
    # Windows 多尺寸 ico
    ico_path = os.path.join(ROOT, 'AI别闹.ico')
    img.resize((256, 256), Image.LANCZOS).save(
        ico_path, format='ICO',
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('[icon ] %s (16/32/48/64/128/256)' % ico_path)


if __name__ == '__main__':
    os.makedirs(COVER_DIR, exist_ok=True)
    for p in (MAIN_RAW, ICON_RAW):
        if not os.path.exists(p):
            sys.exit('[make_cover_assets] 缺少输入图：%s（请先把 AI 原图改名放好）' % p)
    make_cover()
    make_icon()
    print('[done ] 封面资产加工完成')
