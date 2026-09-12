# -*- coding: utf-8 -*-
"""
生成《AI 别闹》像素风设计稿素材：
  1) 20 面像素国旗 <symbol> 雪碧图（viewBox 0 0 30 20）
  2) 真实海岸线栅格化出的像素世界地图（120 x 60 网格，3 度/经度，Miller 投影）
  3) 20 国按真实国界填充的掩码 + 1 格宽轮廓

用法：
    python tools/gen_pixel_map.py
输出（写到 design/ 与 tools/data/）：
    design/pixel_map_assets.json   设计稿内联用的旗帜 + 地图路径数据
    tools/data/preview_map.png     地图栅格化预览（人工核对用）
    tools/data/preview_flags.png   国旗逐面预览（人工核对用）

依赖数据（已随仓库提供，均取自 Natural Earth 110m，公有领域）：
    tools/data/ne110_land.json             海岸线
    tools/data/ne110_countries.json        各国边界
    https://github.com/nvkelso/natural-earth-vector/tree/master/geojson
"""
import json, math, os, re
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, 'data')
OUT_JSON = os.path.abspath(os.path.join(HERE, '..', 'design', 'pixel_map_assets.json'))
KIVY_OUT = os.path.abspath(os.path.join(HERE, '..', 'demo', 'pixel_assets.py'))

FLAG_RE = re.compile(r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([-\d.]+)" '
                     r'height="([-\d.]+)" fill="([^"]+)"/>')
W, H = 360, 180  # 3x 分辨率（原 120x60 ≈100px 级太粗；360x180 贴合 1024px 目标，比例保持 2:1）
LON0, LON1 = -180.0, 180.0
LAT0, LAT1 = 84.0, -57.0
SS = 8

# Miller 投影：高纬度纵向拉伸，更接近《瘟疫工厂》那种世界地图比例
def _my(lat):
    return 1.25 * math.log(math.tan(math.pi / 4 + 0.4 * math.radians(lat)))
Y0, Y1 = _my(LAT0), _my(LAT1)
YSPAN = Y0 - Y1

# ================================================================ 绘形小工具
def R(x, y, w, h, c):
    if w <= 0 or h <= 0:
        return ''
    return '<rect x="%g" y="%g" width="%g" height="%g" fill="%s"/>' % (x, y, w, h, c)

def disc(cx, cy, r, c, ymin=0, ymax=20):
    """逐行扫描画实心圆"""
    out = []
    for y in range(ymin, ymax):
        dy = y + 0.5 - cy
        if abs(dy) >= r:
            continue
        hw = math.sqrt(max(r * r - dy * dy, 0.0))
        x0, x1 = int(round(cx - hw)), int(round(cx + hw))
        out.append(R(x0, y, x1 - x0, 1, c))
    return ''.join(out)

def diag(x0, x1, y0, y1, thick, c, flip=False):
    """阶梯斜线：从 (x0,y0) 走到 (x1,y1)，竖向厚度 thick"""
    out = []
    n = abs(x1 - x0)
    if n == 0:
        return ''
    for i in range(n):
        t = i / float(n)
        x = x0 + i * (1 if x1 > x0 else -1)
        y = y0 + (y1 - y0) * t
        yy = round(y) - (thick - 1) // 2
        out.append(R(x, yy, 1, thick, c))
    return ''.join(out)

def diamond(cx, cy, hw, hh, c):
    """逐列扫描画实心菱形"""
    out = []
    for x in range(cx - hw, cx + hw + 1):
        t = abs(x - cx) / float(hw)
        h = int(round(hh * (1 - t)))
        if h > 0:
            out.append(R(x, cy - h, 1, h * 2, c))
    return ''.join(out)

# ================================================================ 国旗
FLAGS = {}

# 中国 —— 红底 + 左上大五角星 + 4 颗小星（弧形；修正版）
FLAGS['cn'] = (R(0, 0, 30, 20, '#de2910') +
               R(6, 1, 2, 1, '#ffde00') + R(5, 2, 4, 1, '#ffde00') +
               R(4, 3, 6, 1, '#ffde00') + R(3, 4, 8, 2, '#ffde00') +
               R(4, 6, 6, 1, '#ffde00') + R(5, 7, 4, 1, '#ffde00') +
               R(6, 8, 2, 2, '#ffde00') +
               R(11, 1, 1, 1, '#ffde00') + R(13, 3, 1, 1, '#ffde00') +
               R(13, 6, 1, 1, '#ffde00') + R(11, 8, 1, 1, '#ffde00'))

# 日本 —— 白底 + 正中红日（直径 = 3/5 旗高）
FLAGS['jp'] = R(0, 0, 30, 20, '#ffffff') + disc(15, 10, 6, '#bc002d')

# 韩国 —— 白底 + 太极（上红下蓝）+ 四角卦象
FLAGS['kr'] = (R(0, 0, 30, 20, '#ffffff') +
               disc(15, 10, 5, '#cd2e3a', ymin=5, ymax=10) +
               disc(15, 10, 5, '#0047a0', ymin=10, ymax=15) +
               disc(13, 8.5, 2.2, '#cd2e3a', ymin=5, ymax=9) +
               disc(17, 11.5, 2.2, '#0047a0', ymin=11, ymax=15) +
               R(2, 3, 5, 1, '#222') + R(3, 4, 3, 1, '#222') +
               R(23, 3, 5, 1, '#222') + R(24, 4, 3, 1, '#222') +
               R(2, 16, 5, 1, '#222') + R(3, 15, 3, 1, '#222') +
               R(23, 16, 5, 1, '#222') + R(24, 15, 3, 1, '#222'))

# 印度 —— 橙/白/绿 + 海军蓝法轮
FLAGS['in'] = (R(0, 0, 30, 7, '#ff9933') + R(0, 7, 30, 6, '#ffffff') +
               R(0, 13, 30, 7, '#138808') +
               disc(15, 10, 2.6, '#000080') + disc(15, 10, 1.4, '#ffffff'))

# 印尼 —— 上红下白
FLAGS['id'] = R(0, 0, 30, 10, '#ff0000') + R(0, 10, 30, 10, '#ffffff')

# 美国 —— 13 条纹（像素化 7 条）+ 蓝底白星
FLAGS['us'] = (R(0, 0, 30, 20, '#b22234') +
               R(0, 2, 30, 1, '#fff') + R(0, 5, 30, 1, '#fff') + R(0, 8, 30, 1, '#fff') +
               R(0, 11, 30, 1, '#fff') + R(0, 14, 30, 1, '#fff') + R(0, 17, 30, 1, '#fff') +
               R(0, 0, 13, 11, '#3c3b6e') +
               ''.join(R(x, y, 1, 1, '#fff') for y in (2, 5, 8) for x in (2, 5, 8, 11)))

# 加拿大 —— 红-白-红 + 枫叶
FLAGS['ca'] = (R(0, 0, 30, 20, '#d80621') + R(8, 0, 14, 20, '#ffffff') +
               R(14, 3, 2, 1, '#d80621') + R(13, 4, 4, 1, '#d80621') +
               R(11, 5, 8, 1, '#d80621') + R(12, 6, 6, 1, '#d80621') +
               R(11, 7, 1, 1, '#d80621') + R(18, 7, 1, 1, '#d80621') +
               R(13, 7, 4, 1, '#d80621') + R(13, 8, 4, 1, '#d80621') +
               R(14, 9, 2, 4, '#d80621'))

# 墨西哥 —— 绿-白-红 + 中央徽记
FLAGS['mx'] = (R(0, 0, 10, 20, '#006847') + R(10, 0, 10, 20, '#ffffff') +
               R(20, 0, 10, 20, '#ce1126') +
               R(14, 8, 2, 2, '#6b4226') + R(13, 10, 4, 1, '#6b4226') +
               R(14, 11, 2, 1, '#6b4226'))

# 巴西 —— 绿底 + 黄菱形 + 蓝球
FLAGS['br'] = (R(0, 0, 30, 20, '#009c3b') +
               diamond(15, 10, 14, 8, '#ffdf00') +
               disc(15, 10, 3.5, '#002776') +
               R(14, 8, 3, 4, '#ffffff'))

# 阿根廷 —— 浅蓝-白-浅蓝 + 五月太阳
FLAGS['ar'] = (R(0, 0, 30, 7, '#74acdf') + R(0, 7, 30, 6, '#ffffff') +
               R(0, 13, 30, 7, '#74acdf') +
               disc(15, 10, 2.6, '#f6b40e') +
               R(15, 6, 1, 1, '#f6b40e') + R(15, 13, 1, 1, '#f6b40e') +
               R(11, 10, 1, 1, '#f6b40e') + R(19, 10, 1, 1, '#f6b40e'))

# 英国 —— 米字旗（参数化，可用于 AU/NZ 的旗角）
def union_jack(w, h):
    tdw = max(2, h // 5)
    tdr = max(1, h // 10)
    cw = max(3, int(round(w * 0.20)))
    ch = max(3, int(round(h * 0.20)))
    o = [R(0, 0, w, h, '#012169')]
    o.append(diag(0, w, 0, h, tdw, '#ffffff'))
    o.append(diag(0, w, h - 1, -1, tdw, '#ffffff'))
    o.append(diag(0, w, 0, h, tdr, '#c8102e'))
    o.append(diag(0, w, h - 1, -1, tdr, '#c8102e'))
    o.append(R(w // 2 - cw // 2, 0, cw, h, '#ffffff') + R(0, h // 2 - ch // 2, w, ch, '#ffffff'))
    o.append(R(w // 2 - tdr, 0, max(2, tdr), h, '#c8102e') +
             R(0, h // 2 - max(1, tdr // 2), w, max(2, tdr), '#c8102e'))
    return ''.join(o)
FLAGS['gb'] = union_jack(30, 20)

# 法国 / 德国 / 意大利 / 俄罗斯 / 尼日利亚 / 埃及
FLAGS['fr'] = R(0, 0, 10, 20, '#0055a4') + R(10, 0, 10, 20, '#fff') + R(20, 0, 10, 20, '#ef4135')
FLAGS['de'] = R(0, 0, 30, 7, '#000') + R(0, 7, 30, 6, '#dd0000') + R(0, 13, 30, 7, '#ffce00')
FLAGS['it'] = R(0, 0, 10, 20, '#009246') + R(10, 0, 10, 20, '#fff') + R(20, 0, 10, 20, '#ce2b37')
FLAGS['ru'] = R(0, 0, 30, 7, '#fff') + R(0, 7, 30, 6, '#0039a6') + R(0, 13, 30, 7, '#d52b1e')
FLAGS['ng'] = R(0, 0, 10, 20, '#008751') + R(10, 0, 10, 20, '#fff') + R(20, 0, 10, 20, '#008751')
FLAGS['eg'] = (R(0, 0, 30, 7, '#ce1126') + R(0, 7, 30, 6, '#fff') + R(0, 13, 30, 7, '#000') +
               disc(15, 10, 2.2, '#c09300') + R(13, 9, 4, 1, '#c09300'))

# 南非 —— 绿 Y 形 + 红/蓝横带 + 黑三角黄边（逐列构造）
def south_africa():
    o = []
    for x in range(30):
        h = 0 if x >= 10 else int(round(5 * (10 - x) / 10.0))
        for dy in range(-10, 10):
            y = 10 + dy
            a = abs(dy)
            if h >= 1 and a <= h - 1:
                c = '#000000'
            elif h >= 1 and a <= h:
                c = '#ffb612'
            elif a <= h + 2:
                c = '#007a4d'
            elif a <= h + 3:
                c = '#ffffff'
            else:
                c = '#de3831' if dy < 0 else '#002395'
            o.append(R(x, y, 1, 1, c))
    return ''.join(o)
FLAGS['za'] = south_africa()

FLAGS['au'] = (R(0, 0, 30, 20, '#012169') + union_jack(15, 10) +
               R(22, 3, 1, 1, '#fff') + R(21, 4, 3, 1, '#fff') + R(22, 5, 1, 1, '#fff') +
               R(26, 8, 1, 1, '#fff') + R(25, 9, 3, 1, '#fff') + R(26, 10, 1, 1, '#fff') +
               R(23, 13, 1, 1, '#fff') + R(22, 14, 3, 1, '#fff') + R(23, 15, 1, 1, '#fff') +
               R(26, 17, 1, 1, '#fff') + R(25, 18, 3, 1, '#fff') +
               R(18, 11, 1, 1, '#fff') + R(17, 12, 3, 1, '#fff') + R(18, 13, 1, 1, '#fff'))
FLAGS['nz'] = (R(0, 0, 30, 20, '#012169') + union_jack(15, 10) +
               R(22, 4, 1, 1, '#c8102e') + R(21, 5, 3, 1, '#c8102e') + R(22, 6, 1, 1, '#c8102e') +
               R(26, 9, 1, 1, '#c8102e') + R(25, 10, 3, 1, '#c8102e') + R(26, 11, 1, 1, '#c8102e') +
               R(21, 14, 1, 1, '#c8102e') + R(20, 15, 3, 1, '#c8102e') + R(21, 16, 1, 1, '#c8102e') +
               R(25, 17, 1, 1, '#c8102e') + R(24, 18, 3, 1, '#c8102e'))

ORDER = ['cn', 'jp', 'kr', 'in', 'id', 'us', 'ca', 'mx', 'br', 'ar',
         'gb', 'fr', 'de', 'it', 'ru', 'ng', 'eg', 'za', 'au', 'nz']
sprite = ('<svg width="0" height="0" style="position:absolute" aria-hidden="true">' +
          ''.join('<symbol id="flag-%s" viewBox="0 0 30 20">%s</symbol>' % (k, FLAGS[k]) for k in ORDER) +
          '</svg>')

# ================================================================ 世界地图
def to_px(lon, lat):
    x = (lon - LON0) / (LON1 - LON0) * W * SS
    y = (Y0 - _my(lat)) / YSPAN * H * SS
    return (x, y)

def clip_ring(ring, box):
    xmin, ymin, xmax, ymax = box
    def clip_edge(pts, inside, inter):
        out, n = [], len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            ia, ib = inside(a), inside(b)
            if ia:
                out.append(a)
                if not ib:
                    out.append(inter(a, b))
            elif ib:
                out.append(inter(a, b))
        return out
    def mk(axis, val, gt):
        inside = (lambda p: p[axis] >= val) if gt else (lambda p: p[axis] <= val)
        def inter(a, b):
            t = (val - a[axis]) / (b[axis] - a[axis]) if b[axis] != a[axis] else 0.0
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        return inside, inter
    for axis, val, gt in ((0, xmin, True), (0, xmax, False), (1, ymin, True), (1, ymax, False)):
        inside, inter = mk(axis, val, gt)
        ring = clip_edge(ring, inside, inter)
        if not ring:
            return []
    return ring

def rings_of(geom):
    t, c = geom['type'], geom['coordinates']
    if t == 'Polygon':
        return [c[0]]
    if t == 'MultiPolygon':
        return [poly[0] for poly in c]
    return []

def raster(geom, box=None):
    im = Image.new('1', (W * SS, H * SS), 0)
    d = ImageDraw.Draw(im)
    for ring in rings_of(geom):
        if box:
            ring = clip_ring(ring, box)
            if len(ring) < 3:
                continue
        lons = [p[0] for p in ring]
        parts = []
        if max(lons) - min(lons) > 180:
            # 跨日期变更线：拆成 [-180,180] 与 [180,540]->[-180,180] 两段，避免回绕拉出横贯色带
            for a in (-180.0, 180.0):
                r = clip_ring(ring, (a, -90.0, a + 360.0, 90.0))
                if len(r) >= 3:
                    parts.append([(p[0] - a - 180.0, p[1]) for p in r])
        else:
            parts = [ring]
        for r in parts:
            pts = [to_px(lo, la) for lo, la in r]
            if len(pts) >= 3:
                d.polygon(pts, fill=1)
    small = im.convert('L').resize((W, H), Image.BOX)
    return [[1 if small.getpixel((x, y)) >= 110 else 0 for x in range(W)] for y in range(H)]

def merge(mask):
    out, n = [], 0
    for y in range(H):
        x = 0
        while x < W:
            if mask[y][x]:
                x2 = x
                while x2 + 1 < W and mask[y][x2 + 1]:
                    x2 += 1
                L = x2 - x + 1
                out.append('M%d %dh%dv1h-%dz' % (x, y, L, L))
                n += 1
                x = x2 + 1
            else:
                x += 1
    return ''.join(out)

def outline(mask):
    b = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if mask[y][x]:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < W and 0 <= ny < H) or not mask[ny][nx]:
                        b[y][x] = 1
                        break
    return b

def trace_contour(mask):
    """Moore 邻域边界追踪 → 国界**外轮廓折线**（格中心坐标，闭合）

    像素地图本身不需要多边形，但 data.py 的 Country.polygon 仍要有个真实值
    （旧版是手写经纬度多边形，现已废弃）。这里直接从栅格掩码追出轮廓，
    保证「几何单一来源」依然是 Natural Earth，不需要人工维护第二套坐标。

    返回 [(gx, gy), ...]，含首尾重复的起点（闭合环）。
    """
    cells = [(x, y) for y in range(H) for x in range(W) if mask[y][x]]
    if not cells:
        return []
    # 8 邻域，从"东"开始顺时针（y 轴向下，故 (0,1) 在南）
    dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    inside = lambda p: 0 <= p[0] < W and 0 <= p[1] < H and mask[p[1]][p[0]]
    start = min(cells, key=lambda c: (c[1], c[0]))
    if sum(1 for d in dirs if inside((start[0] + d[0], start[1] + d[1]))) == 0:
        return [(start[0] + .5, start[1] + .5)]        # 孤岛：单格
    contour, p, d = [start], start, 0
    for _ in range(8 * W * H):                          # 防御性上限
        for k in range(8):
            nd = (d + k) % 8
            q = (p[0] + dirs[nd][0], p[1] + dirs[nd][1])
            if inside(q):
                contour.append(q)
                d = (nd + 6) % 8                        # 回退：从上一方向重新搜索
                p = q
                break
        else:
            break
        if p == start and len(contour) > 2:
            break
    if contour[-1] != start:
        contour.append(start)                           # 闭合
    return [(cx + .5, cy + .5) for cx, cy in contour]


def dilate(mask, rings=1):
    """让面积过小的国家至少有一圈可点击的像素"""
    m = [row[:] for row in mask]
    for _ in range(rings):
        n = [row[:] for row in m]
        for y in range(H):
            for x in range(W):
                if m[y][x]:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < W and 0 <= ny < H:
                            n[ny][nx] = 1
        m = n
    return m

land_gj = json.load(open(os.path.join(TMP, 'ne110_land.json'), encoding='utf-8'))
ctry_gj = json.load(open(os.path.join(TMP, 'ne110_countries.json'), encoding='utf-8'))

land_mask = [[0] * W for _ in range(H)]
for f in land_gj['features']:
    m = raster(f['geometry'])
    for y in range(H):
        for x in range(W):
            if m[y][x]:
                land_mask[y][x] = 1
print('陆地格：', sum(sum(r) for r in land_mask))

GAME = [
    ('CN', 'China', '中国', 'sel', None), ('JP', 'Japan', '日本', 'on', None),
    ('KR', 'South Korea', '韩国', 'on', None), ('IN', 'India', '印度', 'on', None),
    ('ID', 'Indonesia', '印尼', 'on', None), ('US', 'United States of America', '美国', 'on', None),
    ('CA', 'Canada', '加拿大', 'on', None), ('MX', 'Mexico', '墨西哥', 'lk', None),
    ('BR', 'Brazil', '巴西', 'on', None), ('AR', 'Argentina', '阿根廷', 'lk', None),
    ('GB', 'United Kingdom', '英国', 'on', (-9, 49, 2, 61)),
    ('FR', 'France', '法国', 'on', (-10, 41, 10, 52)),
    ('DE', 'Germany', '德国', 'blk', None), ('IT', 'Italy', '意大利', 'on', None),
    ('RU', 'Russia', '俄罗斯', 'on', None), ('NG', 'Nigeria', '尼日利亚', 'lk', None),
    ('EG', 'Egypt', '埃及', 'lk', (24, 21, 37, 32)), ('ZA', 'South Africa', '南非', 'lk', None),
    ('AU', 'Australia', '澳大利亚', 'lk', None), ('NZ', 'New Zealand', '新西兰', 'lk', (165, -48, 180, -33)),
]

# ---------------------------------------------------------------- 标签布局
# ANCHORS：国界质心（真实经纬度栅格化后算出来的，美国含阿拉斯加故手工校正到本土）
ANCHORS = {
    'CN': (282.3, 75.0), 'JP': (317.4, 72.9), 'KR': (306.0, 75.0), 'IN': (258.3, 90.0),
    'ID': (295.2, 115.5), 'US': (81.9, 74.1), 'CA': (81.0, 38.4), 'MX': (75.0, 88.2),
    'BR': (125.7, 125.1), 'AR': (113.1, 152.4), 'GB': (175.2, 53.4), 'FR': (180.0, 63.0),
    'DE': (188.7, 56.7), 'IT': (190.2, 67.2), 'RU': (275.7, 39.9), 'NG': (186.3, 104.4),
    'EG': (208.2, 86.4), 'ZA': (204.3, 143.7), 'AU': (313.2, 140.4), 'NZ': (351.3, 157.8),
}
# LABELS：标签落点（手工避让，保证 20 个标签框互不重叠；随网格 3x 等比放大）
LABELS = {
    'CN': (259.5, 84.0), 'JP': (334.5, 58.5), 'KR': (322.5, 82.5), 'IN': (232.5, 88.5),
    'ID': (318.0, 129.0), 'US': (49.5, 64.5), 'CA': (49.5, 27.0), 'MX': (37.5, 97.5),
    'BR': (124.5, 127.5), 'AR': (78.0, 160.5), 'GB': (142.5, 39.0), 'FR': (142.5, 66.0),
    'DE': (211.5, 43.5), 'IT': (211.5, 70.5), 'RU': (255.0, 37.5), 'NG': (154.5, 106.5),
    'EG': (189.0, 72.0), 'ZA': (219.0, 151.5), 'AU': (312.0, 142.5), 'NZ': (322.5, 165.0),
}

by_iso, by_name = {}, {}
for f in ctry_gj['features']:
    p = f['properties']
    iso = (p.get('ISO_A2_EH') or p.get('ISO_A2') or '').upper()
    if iso and iso != '-99':
        by_iso[iso] = f
    by_name[(p.get('NAME') or '').strip()] = f

out_c, masks = [], {}
for code, en, zh, st, box in GAME:
    f = by_iso.get(code) or by_name.get(en)
    if f is None:
        print('!! 未找到', code, en); continue
    m = raster(f['geometry'], box)
    # 过小的国家膨胀一圈，保证在小尺寸下仍可见 / 可点
    if sum(sum(r) for r in m) < 8:
        m = dilate(m, 1)
    masks[code] = m
    cells = [(x, y) for y in range(H) for x in range(W) if m[y][x]]
    cx = round(sum(c[0] for c in cells) / len(cells), 1) if cells else 0
    cy = round(sum(c[1] for c in cells) / len(cells), 1) if cells else 0
    out_c.append({'c': code, 'n': zh, 'st': st, 'x': cx, 'y': cy, 'cells': len(cells)})
    print('%-3s %-10s cells=%-5d centre=(%.1f,%.1f)' % (code, zh, len(cells), cx, cy))

# ---------------------------------------------------------------- 台湾归属修正
# Natural Earth 110m 的 admin_0 把台湾列为独立单元，栅格化后台湾岛的格子
# 不落在中国掩码里 → 地图上成了"无主灰岛"（不归属任何国家、不可点击）。
# 台湾是中国领土不可分割的一部分，地图展示必须完整体现归属：
# 这里把包围盒内的无主陆地格（台湾岛及其附属岛屿）并入中国掩码，
# fill / border / owner / 预览图随掩码自动更新。
TW_BOX = (299, 87, 302, 93)   # 台湾岛覆盖的格坐标包围盒 (x0, y0, x1, y1)，含端点
tw_cells = [(x, y)
            for y in range(TW_BOX[1], TW_BOX[3] + 1)
            for x in range(TW_BOX[0], TW_BOX[2] + 1)
            if land_mask[y][x]
            and not masks['CN'][y][x]
            and not any(masks[c][y][x] for c in masks if c != 'CN')]
for x, y in tw_cells:
    masks['CN'][y][x] = 1
print('台湾归属修正：%d 格并入中国掩码 %s' % (len(tw_cells), tw_cells))
assert len(tw_cells) >= 4, '台湾岛格子数量异常，请人工核对 TW_BOX 包围盒'

assets = {
    'sprite': sprite, 'grid': {'w': W, 'h': H},
    'land': merge(land_mask), 'coast': merge(outline(land_mask)),
    'countries': out_c,
    'fills': {c: merge(m) for c, m in masks.items()},
    'borders': {c: merge(outline(m)) for c, m in masks.items()},
    'contours': {c: trace_contour(m) for c, m in masks.items()},
    'anchors': ANCHORS,
    'labels': LABELS,
}
json.dump(assets, open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False)

# ================================================================ Kivy 运行时素材
# 把游程由 "M{x} {y}h{n}v1h-{n}z" 换成 (x, y, w) 三元组 —— Kivy 直接用 Rectangle 画，
# 不需要在运行时解析 SVG 路径语法。
def pairs(mask):
    return [(x, y, x2 - x + 1)
            for y in range(H) for x, x2 in _runs(mask, y)]

def _runs(mask, y):
    x = 0
    while x < W:
        if mask[y][x]:
            x2 = x
            while x2 + 1 < W and mask[y][x2 + 1]:
                x2 += 1
            yield x, x2
            x = x2 + 1
        else:
            x += 1

# 归属格：'.' = 非游戏国（海面或他国陆地），A..T = OWNER_CODES 里的国家（点击命中用）
OWNER_CODES = [g[0] for g in GAME]
owner_rows = []
for y in range(H):
    row = []
    for x in range(W):
        ch = '.'
        for i, code in enumerate(OWNER_CODES):
            if masks.get(code) and masks[code][y][x]:
                ch = chr(ord('A') + i)
                break
        row.append(ch)
    owner_rows.append(''.join(row))

def runs_body(runs, width=104, indent='    '):
    """把游程列表写成可读的多行字符串字面量（隐式拼接）的**内容**

    ⚠️ 换行必须落在 token 边界，且行尾不能 rstrip —— 否则隐式拼接会把
    两个 token 粘成一个（"...,5" "15,3,4" → "...,515,3,4"）。
    """
    lines, cur = [], ''
    for x, y, w in runs:
        tok = '%d,%d,%d' % (x, y, w)
        piece = tok if not cur else ' ' + tok
        if len(cur) + len(piece) > width:
            lines.append(cur)
            cur = tok
        else:
            cur += piece
    if cur:
        lines.append(cur)
    if not lines:
        lines = ['']
    # 隐式字符串拼接不会补分隔符 → 除最后一行外都要补一个空格
    lines = [l + ' ' for l in lines[:-1]] + [lines[-1]]
    return '\n'.join('%s"%s"' % (indent, l) for l in lines)

def emit_runs(name, runs, width=104):
    return '%s = (\n%s\n)\n' % (name, runs_body(runs, width))

def emit_dict_entry(key, runs, width=100):
    return "    '%s': (\n%s\n    ),\n" % (key, runs_body(runs, width, indent='        '))

kivy = ['# -*- coding: utf-8 -*-',
        '"""',
        'pixel_assets.py - 像素世界地图 / 20 面国旗的运行时素材（**自动生成，请勿手改**）',
        '',
        '来源：tools/gen_pixel_map.py  ←  Natural Earth 110m 真实海岸线 + 各国边界',
        '重新生成：python tools/gen_pixel_map.py',
        '',
        '坐标约定：地图网格 %d x %d（每格 3 度经度，Miller 投影，纬度 84N-57S）；' % (W, H),
        '         国旗为 30 x 20 像素网格，原点在**左上角**（Kivy 绘制时需翻转 y）。',
        '',
        '游程格式：每条 "x,y,w" 表示第 y 行从 x 起连续 w 格，用 parse_runs() 解析。',
        '"""',
        '',
        'GRID_W = %d' % W,
        'GRID_H = %d' % H,
        'FLAG_W = 30',
        'FLAG_H = 20',
        '',
        '# 陆地底 / 海岸线高亮（静态，与游戏状态无关）',
        emit_runs('LAND', pairs(land_mask)),
        emit_runs('COAST', pairs(outline(land_mask))),
        '# 20 国填充 / 国界（国界是 1 格宽的独立游程，不是描边）',
        'FILLS = {',
        ]
for c in OWNER_CODES:
    kivy.append(emit_dict_entry(c, pairs(masks[c])))
kivy.append('}\n')
kivy.append('BORDERS = {')
for c in OWNER_CODES:
    kivy.append(emit_dict_entry(c, pairs(outline(masks[c]))))
kivy.append('}\n')
kivy.append('# 归属格（点击命中）：每行 GRID_W 个字符，A..T = OWNER_CODES 下标')
kivy.append('OWNER_CODES = %r' % (OWNER_CODES,))
kivy.append('OWNER = (')
kivy.append('\n'.join('    "%s",  # row %d' % (r, i) for i, r in enumerate(owner_rows)))
kivy.append(')\n')
kivy.append('# 国界外轮廓折线（L 形折线，格坐标；供 data.Country.polygon 用）')
kivy.append('OUTLINES = {')
for c in OWNER_CODES:
    pts = trace_contour(masks[c])
    body = ',\n'.join('        %s' % ', '.join('(%.1f, %.1f)' % p for p in pts[i:i + 5])
                      for i in range(0, len(pts), 5))
    kivy.append("    '%s': (\n%s,\n    )," % (c, body))
kivy.append('}\n')
kivy.append('# 标签锚点（国界质心，网格坐标）')
kivy.append('ANCHORS = {')
for c in OWNER_CODES:
    kivy.append("    '%s': (%.1f, %.1f)," % (c, ANCHORS[c][0], ANCHORS[c][1]))
kivy.append('}\n')
kivy.append('# 标签落点（手工避让，网格坐标）')
kivy.append('LABELS = {')
for c in OWNER_CODES:
    kivy.append("    '%s': (%.1f, %.1f)," % (c, LABELS[c][0], LABELS[c][1]))
kivy.append('}\n')
kivy.append('# 国旗：30x20 网格上逐矩形绘制，(颜色, x, y, w, h)，左上角原点')
kivy.append('FLAGS = {')
for k in ORDER:
    kivy.append("    '%s': (" % k.upper())
    for m in FLAG_RE.finditer(FLAGS[k]):
        x, y, w, h, col = m.groups()
        kivy.append("        ('%s', %g, %g, %g, %g)," % (col.lstrip('#'), float(x), float(y), float(w), float(h)))
    kivy.append('    ),')
kivy.append('}\n')
kivy.append('''

def parse_runs(text):
    """把 "x,y,w x,y,w ..." 字符串解析成 [(x, y, w), ...]"""
    out = []
    for tok in text.split():
        a, b, c = tok.split(',')
        out.append((int(a), int(b), int(c)))
    return tuple(out)


def parse_all(table):
    """{code: "x,y,w ..."} -> {code: ((x,y,w), ...)}"""
    return {k: parse_runs(v) for k, v in table.items()}


LAND_RUNS = parse_runs(LAND)
COAST_RUNS = parse_runs(COAST)
FILL_RUNS = parse_all(FILLS)
BORDER_RUNS = parse_all(BORDERS)


def owner_at(gx, gy):
    """网格坐标 -> 国家代码；不在任何游戏国家内返回 None"""
    if not (0 <= gx < GRID_W and 0 <= gy < GRID_H):
        return None
    i = ord(OWNER[gy][gx]) - ord('A')
    return OWNER_CODES[i] if 0 <= i < len(OWNER_CODES) else None


if __name__ == '__main__':
    print('grid %dx%d  陆地 %d 段 / 海岸 %d 段 / 填充 %d 段 / 国界 %d 段'
          % (GRID_W, GRID_H, len(LAND_RUNS), len(COAST_RUNS),
             sum(len(v) for v in FILL_RUNS.values()),
             sum(len(v) for v in BORDER_RUNS.values())))
    print('国旗 %d 面，共 %d 个矩形'
          % (len(FLAGS), sum(len(v) for v in FLAGS.values())))
''')

open(KIVY_OUT, 'w', encoding='utf-8').write('\n'.join(kivy))
print('已写出', OUT_JSON)
print('已写出', KIVY_OUT)

# ================================================================ 预览
S = 8
img = Image.new('RGB', (W * S, H * S), (10, 24, 40))
d = ImageDraw.Draw(img)
for y in range(H):
    for x in range(W):
        if land_mask[y][x]:
            d.rectangle([x * S, y * S, x * S + S - 1, y * S + S - 1], fill=(27, 58, 68))
co = outline(land_mask)
for y in range(H):
    for x in range(W):
        if co[y][x]:
            d.rectangle([x * S, y * S, x * S + S - 1, y * S + S - 1], fill=(45, 90, 99))
COL = {'on': (31, 111, 99), 'sel': (79, 201, 176), 'blk': (92, 35, 35), 'lk': (35, 42, 48)}
BOR = {'on': (78, 230, 200), 'sel': (240, 255, 252), 'blk': (239, 68, 68), 'lk': (74, 85, 96)}
for code, m in masks.items():
    st = [g[3] for g in GAME if g[0] == code][0]
    col = COL.get(st, (60, 70, 80))
    for y in range(H):
        for x in range(W):
            if m[y][x]:
                d.rectangle([x * S, y * S, x * S + S - 1, y * S + S - 1], fill=col)
for code, m in masks.items():
    st = [g[3] for g in GAME if g[0] == code][0]
    col = BOR.get(st, (120, 130, 140))
    bm = outline(m)
    for y in range(H):
        for x in range(W):
            if bm[y][x]:
                d.rectangle([x * S, y * S, x * S + S - 1, y * S + S - 1], fill=col)
img.save(os.path.join(TMP, 'preview_map.png'))

RE = re.compile(r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([-\d.]+)" height="([-\d.]+)" fill="([^"]+)"/>')
FS, cols = 10, 5
rows = (len(ORDER) + cols - 1) // cols
fimg = Image.new('RGB', (cols * (30 * FS + 16) + 16, rows * (20 * FS + 34) + 16), (16, 18, 24))
fd = ImageDraw.Draw(fimg)
for i, k in enumerate(ORDER):
    ox = 16 + (i % cols) * (30 * FS + 16)
    oy = 16 + (i // cols) * (20 * FS + 34)
    fd.rectangle([ox - 1, oy - 1, ox + 30 * FS, oy + 20 * FS], fill=(255, 255, 255), outline=(90, 100, 110))
    for m in RE.finditer(FLAGS[k]):
        x, y, w, h, c = m.groups()
        x, y, w, h = float(x), float(y), float(w), float(h)
        fd.rectangle([ox + x * FS, oy + y * FS, ox + (x + w) * FS - 1, oy + (y + h) * FS - 1], fill=c)
    fd.rectangle([ox - 1, oy - 1, ox + 30 * FS, oy + 20 * FS], outline=(90, 100, 110))
    fd.text((ox, oy + 20 * FS + 4), k.upper(), fill=(200, 210, 220))
fimg.save(os.path.join(TMP, 'preview_flags.png'))
print('已写出 %s / preview_map.png / preview_flags.png' % OUT_JSON)
