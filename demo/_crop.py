import os
from PIL import Image
SRC = r"C:/users/tianm/Pictures/Screenshots"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_crops")
os.makedirs(OUT, exist_ok=True)

def crop(fn, tag, box, scale=1.6):
    p = os.path.join(SRC, fn)
    im = Image.open(p).convert("RGB")
    W, H = im.size
    x0, y0, x1, y1 = box
    x0 = int(x0*W/1092); x1 = int(x1*W/1092)
    y0 = int(y0*H/660); y1 = int(y1*H/660)
    im2 = im.crop((x0, y0, x1, y1))
    if scale != 1.0:
        im2 = im2.resize((int(im2.width*scale), int(im2.height*scale)), Image.LANCZOS)
    op = os.path.join(OUT, f"{tag}.png")
    im2.save(op)
    print("saved", op, im2.size)

# 归一化到 1092x660 的预览坐标系
crop("屏幕截图 2026-09-11 132346.png", "A_tut_full",     (0, 0, 1092, 660), 1.5)
crop("屏幕截图 2026-09-11 132346.png", "A_center",       (360, 215, 730, 460), 2.2)
crop("屏幕截图 2026-09-11 132346.png", "A_bottomleft",   (0, 440, 340, 640), 2.6)
crop("屏幕截图 2026-09-11 132527.png", "B_help_left",    (0, 25, 370, 640), 1.8)
crop("屏幕截图 2026-09-11 132527.png", "B_help_mid",     (360, 25, 740, 640), 1.8)
crop("屏幕截图 2026-09-11 132527.png", "B_help_right",   (720, 25, 1092, 640), 1.8)
crop("屏幕截图 2026-09-11 132634.png", "C_topright",     (820, 15, 1092, 115), 3.2)
crop("屏幕截图 2026-09-11 132634.png", "C_botright",     (820, 530, 1092, 645), 3.2)
crop("屏幕截图 2026-09-11 132734.png", "D_topright",     (900, 15, 1092, 120), 3.2)
crop("屏幕截图 2026-09-11 132734.png", "D_botright",     (820, 530, 1092, 645), 3.2)
