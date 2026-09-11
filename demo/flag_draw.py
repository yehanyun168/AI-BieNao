"""
flag_draw.py - 像素国旗绘制（30 x 20 像素网格）

数据来源：demo/pixel_assets.py 的 `FLAGS`，由 tools/gen_pixel_map.py 从
          design/ui_design_v0.3.html 的 SVG 雪碧图里反解出来（单一数据源）。
          每面旗是一串 (颜色, x, y, w, h) 矩形，**原点在左上角**（y 向下）。

与 v2 的手写形状（正圆/多边形近似）相比，这里逐矩形落笔，20 面旗在任意
尺寸下都是同一套像素形状：中国红底大五角星 + 四小星、韩国太极 + 四卦、
美式条纹 + 星区、米字旗斜十字、巴西菱形 + 星穹、南非 Y 形六色……

公共 API（被 main.py / world_map.py 使用，保持不变）：
    draw_flag(canvas, code, x, y, w, h)   —— 在任意 canvas 上绘制
    FlagWidget(code=..., size=...)        —— Kivy 组件，支持 set_code()
"""
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Rectangle, Line

import pixel_assets as PA
from pixel_ui import hex_rgba as _rgba


FLAG_W = PA.FLAG_W      # 30
FLAG_H = PA.FLAG_H      # 20

# 旗面描边（设计稿 .flag{border:1px solid var(--border-2)}）
# 白底旗（JP/KR/CA/AR）在深色面板上没有描边会“融进背景”
FRAME_COLOR = '#484f58'

# 未知代码（'UN' 等）的兜底样式：深蓝底 + 浅色横条
_FALLBACK = (
    ('2b3a55', 0, 0, 30, 20),
    ('7f8fa6', 0, 0, 30, 3),
    ('7f8fa6', 0, 17, 30, 3),
    ('7f8fa6', 0, 8, 30, 2),
)


def flag_rects(code):
    """取某国国旗的矩形表（含兜底），供外部（如工具栏图标）复用"""
    if not code:
        return _FALLBACK
    return PA.FLAGS.get(code.upper()) or _FALLBACK


def _clamp_rects(rects):
    """把出界矩形裁剪到旗面内（SVG 靠 viewBox 裁剪，Kivy 的 Rectangle 不会）

    例：米字旗斜十字在角上用 gy=-1 表示「被画布边缘切掉」；
    这里手动 clamp，保证 Kivy 像素结果与设计稿 SVG 完全一致。
    """
    out = []
    for hexstr, gx, gy, gw, gh in rects:
        x0 = gx if gx > 0 else 0
        y0 = gy if gy > 0 else 0
        x1 = gx + gw
        y1 = gy + gh
        if x1 > FLAG_W:
            x1 = FLAG_W
        if y1 > FLAG_H:
            y1 = FLAG_H
        if x0 >= x1 or y0 >= y1:
            continue                       # 完全在旗面外 → 丢弃
        out.append((hexstr, x0, y0, x1 - x0, y1 - y0))
    return out


def draw_flag(canvas, code, x, y, w, h):
    """在 canvas 上以 (x, y, w, h) 为区域绘制像素国旗

    ⚠️ Kivy 的 y 轴向上、国旗数据 y 轴向下，所以纵向要翻转：
       屏幕 y = y + (FLAG_H - gy - gh) * sy
    ⚠️ Kivy 的 widget canvas 使用**父坐标**（不是本组件的局部坐标），
       调用方传入的 x/y 必须已经是绝对坐标。
    """
    if w < 1 or h < 1:
        return
    rects = _clamp_rects(flag_rects(code))
    sx = w / float(FLAG_W)
    sy = h / float(FLAG_H)

    last_hex, color_inst = None, None
    for hexstr, gx, gy, gw, gh in rects:
        # 相邻同色矩形共用一个 Color 指令，减少 canvas 指令数（南非旗约省 1/3）
        if hexstr != last_hex:
            color_inst = Color(*_rgba(hexstr))
            canvas.add(color_inst)
            last_hex = hexstr
        px = x + gx * sx
        py = y + (FLAG_H - gy - gh) * sy
        rect = Rectangle(pos=(px, py), size=(gw * sx, gh * sy))
        canvas.add(rect)


def draw_flag_frame(canvas, x, y, w, h):
    """旗面 1px 描边（跟国旗分开，便于 FlagWidget 只在需要时叠加）"""
    canvas.add(Color(*_rgba(FRAME_COLOR)))
    canvas.add(Line(points=[x, y, x + w, y, x + w, y + h, x, y + h],
                    close=True, width=1))


def flag_instruction_count(code):
    """某个国旗的 canvas 指令数（color + rect），自检用"""
    rects = _clamp_rects(flag_rects(code))
    n = 1
    for i in range(1, len(rects)):
        if rects[i][0] != rects[i - 1][0]:
            n += 1
    return n + len(rects)


# ============================================================
# FlagWidget（Kivy 组件版）
# ============================================================
class FlagWidget(FloatLayout):
    """像素国旗小组件；尺寸变化或 set_code() 时重绘"""

    def __init__(self, code='UN', size_hint=(None, None), size=(32, 24),
                 frame=True, **kwargs):
        super().__init__(size_hint=size_hint, size=size, **kwargs)
        self.code = (code or 'UN').upper()
        self.frame = frame
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_code(self, code):
        code = (code or 'UN').upper()
        if code == self.code:
            return                     # 同一面旗不重绘（国家列表每 tick 都会调）
        self.code = code
        self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        draw_flag(self.canvas, self.code, self.x, self.y, self.width, self.height)
        if self.frame:
            draw_flag_frame(self.canvas, self.x, self.y, self.width, self.height)


if __name__ == '__main__':
    from kivy.config import Config
    Config.set('graphics', 'width', '1280')
    Config.set('graphics', 'height', '720')
    from kivy.app import App
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label

    CODES = ['CN', 'IN', 'JP', 'US', 'DE', 'GB', 'FR', 'AU', 'KR', 'ID',
             'RU', 'IT', 'CA', 'MX', 'BR', 'AR', 'NG', 'ZA', 'EG', 'NZ']

    class FlagGridApp(App):
        def build(self):
            root = GridLayout(cols=4, spacing=12, padding=20)
            for code in CODES:
                cell = BoxLayout(orientation='vertical', spacing=4,
                                 size_hint_y=None, height=120)
                cell.add_widget(FlagWidget(code=code, size_hint=(None, None),
                                           size=(100, 68)))
                cell.add_widget(Label(text=code, font_size=16,
                                      size_hint_y=None, height=24))
                root.add_widget(cell)
            return root

    FlagGridApp().run()
