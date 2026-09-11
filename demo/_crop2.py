import os
from PIL import Image
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_crops")
OUT = SRC
im = Image.open(os.path.join(SRC, "probe_tut0001.png")).convert("RGB")
print("size", im.size)
jobs = {
    "c2_topright": (1620, 0, 2160, 190),
    "c2_topbar_r": (1500, 0, 2160, 100),
    "c2_botright": (1620, 1080, 2160, 1320),
    "c2_skillbar": (0, 1120, 2160, 1320),
}
for tag, box in jobs.items():
    c = im.crop(box)
    c = c.resize((int(c.width*2.0), int(c.height*2.0)), Image.LANCZOS)
    p = os.path.join(OUT, tag + ".png"); c.save(p); print("saved", p, c.size)
