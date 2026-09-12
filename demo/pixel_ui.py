"""
pixel_ui.py - 像素风 UI 组件库

设计稿：ui_design_v0.1.html
- 16 色硬调色板（深色 GitHub 风格 + 8 高对比强调色）
- 硬 2px 边框，无圆角
- 等宽字体（MicrosoftYaHei，中英兼容）
- font_hinting='None' 保证像素边缘锐利

组件：
  - COLORS              16 色调色板（rgba 0-1）
  - PixelPanel          硬边框面板（替代原 Panel）
  - PixelLabel          像素风标签（字体 hinting 关闭）
"""
from math import floor

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, Line


# ============================================================
# 16 色硬调色板
# ============================================================
COLORS = {
    'bg':         (0.051, 0.067, 0.090, 1),  # #0d1117  深底
    'panel':      (0.086, 0.106, 0.133, 1),  # #161b22  主面板
    'panel_2':    (0.122, 0.149, 0.188, 1),  # #1f2630  次面板
    'border':     (0.188, 0.212, 0.239, 1),  # #30363d  边框 1
    'border_2':   (0.282, 0.310, 0.345, 1),  # #484f58  边框 2
    'text':       (0.902, 0.929, 0.953, 1),  # #e6edf3  主文本
    'text_dim':   (0.545, 0.580, 0.620, 1),  # #8b949e  暗文本
    # P1-5 无障碍整改：#6e7681 在 bg 仅 4.12:1、panel_2 仅 3.32:1（AA 正文需 4.5），
    # 提亮到 #8b9099（bg 5.90 / panel 5.39 / panel_2 4.75，全 ≥4.5）。
    # ⚠️ 有意偏离设计稿 --text-mute:#6e7681（设计稿自己标注「仅大字可用」，
    # 但代码里一直当小字用）—— 偏离清单见 tools/check_map_palette.py。
    'text_mute':  (0.545, 0.565, 0.600, 1),  # #8b9099  静音文本（AA 达标版）
    'cyan':       (0.306, 0.788, 0.690, 1),  # #4ec9b0  青
    'pink':       (0.976, 0.459, 0.514, 1),  # #f97583  粉
    'yellow':     (0.863, 0.804, 0.667, 1),  # #dcdcaa  黄
    'green':      (0.416, 0.600, 0.333, 1),  # #6a9955  绿
    'purple':     (0.773, 0.525, 0.753, 1),  # #c586c0  紫
    # P1-5 无障碍整改：#ffa657 与封锁红 #ef4444 / 警示红 #ff7b72 在绿色盲
    # （deuteranopia, Machado2009 模拟 + CIE76）下 ΔE 仅 20.7 / 22.1（<25 不可辨）。
    # 提亮到 #ffbe5c 后四个配对全部 ≥26（deutan 26.5/26.7, protan 45.3/41.8），
    # 且与 cost 黄 #dcdcaa 的区分度保持充足。仍是「琥珀警告」色相族。
    'orange':     (1.000, 0.745, 0.361, 1),  # #ffbe5c  橙（色盲可辨版）
    'red':        (1.000, 0.482, 0.447, 1),  # #ff7b72  红
    'blue':       (0.306, 0.580, 0.788, 1),  # #4e94c9  蓝（第 16 色）
}

# ⚠️ 语义边框令牌（设计稿 ui_design_v0.3.html §2.2 新增）
# border #30363d 对面板底仅 1.55:1、border_2 #484f58 仅 2.28:1，
# 都低于 WCAG 1.4.11 对「可交互控件边界 / 焦点指示」要求的 3:1。
# 需要达标的场合（焦点环、选中态、可点击边界）一律用这个 #6e7681（4.12:1）。
COLORS['border_strong'] = (0.431, 0.463, 0.502, 1)   # #6e7681

# 颜色类别映射（兼容旧 main.py 的 keys）
_ALIASES = {
    'text_dim': 'text_dim', 'text_mute': 'text_mute',
    'accent': 'cyan', 'accent2': 'pink', 'accent3': 'yellow',
    'accent4': 'green', 'warning': 'orange', 'danger': 'red',
    'success': 'green',
    'panel_dark': 'bg', 'panel_light': 'panel_2',
}


def color(name: str):
    """获取颜色（兼容旧 keys）"""
    return COLORS.get(name) or COLORS.get(_ALIASES.get(name, name), COLORS['text'])


_hex_cache = {}


def hex_rgba(hexstr, alpha=1.0):
    """'#4ec9b0' / '4ec9b0' -> (0.306, 0.788, 0.690, alpha)

    像素地图 / 国旗的数据源都是设计稿里的十六进制色值（单一来源），
    这里统一做一次转换并缓存。
    """
    key = (hexstr, alpha)
    v = _hex_cache.get(key)
    if v is None:
        h = hexstr.lstrip('#')
        if len(h) == 3:                      # 3 位短 hex（'fff' -> 'ffffff'）
            h = ''.join(ch * 2 for ch in h)
        v = (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0,
             int(h[4:6], 16) / 255.0, alpha)
        _hex_cache[key] = v
    return v


# ============================================================
# 像素栅格吸附（P2-2：修 1px 线 / 矩形的半像素糊）
# ============================================================
# 背景：窗口缩放、DPI≠1（如 1.5×）或布局均分会给 canvas 坐标带来小数
#（最典型是 .5 半像素）。GPU 落在半像素上的 1px Line/Rectangle 会被
# 双线性采样摊成 2px 的糊边 —— 像素风的"锐利"就没了。
# 约定：凡 1px 线、硬边矩形，**落笔前**必须吸附；吸附会让个别元素
# 整体偏移 ≤0.5px，属预期，不要为"完美对齐"反过来重排布局。
def snap(v: float) -> int:
    """逻辑坐标 → 整数像素（四舍五入，.5 恒向上；负坐标安全）。

    用 floor(v+0.5) 而非 int(v+0.5)：后者对负数是截断，
    snap(-1.6) 会错成 -1（应为 -2）。
    """
    return int(floor(v + 0.5))


def snap_pt(pt) -> tuple:
    """坐标点/尺寸 (a, b) 整体吸附，返回 int 元组（可直接喂 pos/size）。"""
    a, b = pt
    return (snap(a), snap(b))


# ============================================================
# 像素风字体设置
# ============================================================
PIXEL_FONT_NAME = 'MicrosoftYaHei'   # 中英兼容，等宽感


# ============================================================
# PixelPanel - 硬边框面板
# ============================================================
class PixelPanel(FloatLayout):
    """像素风面板：硬 2px 边框，无圆角

    用法：
        panel = PixelPanel(bg=COLORS['panel'], border_color=COLORS['border_2'])
        panel.add_widget(widget)

    运行时改色：
        panel.update_color(bg=COLORS['red'], border=COLORS['red'])

    设计令牌：``shadow=True`` 时按设计稿 --shadow 画硬投影（6px 6px 0），
    让面板从背景里「浮起来」——弹窗 / 检视卡统一用它，风格一致。
    """
    def __init__(self, bg=None, border_color=None, border_width=2,
                 shadow: bool = False, **kwargs):
        super().__init__(**kwargs)
        self._bg_color = list(bg) if bg else list(COLORS['panel'])
        self._border_color = list(border_color) if border_color else list(COLORS['border_2'])
        self._border_width = border_width
        self._shadow = shadow
        self.bind(pos=self._rebuild, size=self._rebuild)
        self._rebuild()

    def _rebuild(self, *args):
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w < 1 or h < 1:
            return
        with self.canvas.before:
            if self._shadow:
                # 设计稿 --shadow：硬投影 6px 6px 0（右下偏移一条暗带）
                Color(0, 0, 0, 0.55)
                self._sh_rect = Rectangle(pos=(x + 6, y - 6), size=(w, h))
                Color(*self._bg_color)
                self._sh_cover = Rectangle(pos=(x, y), size=(w, h))
            else:
                Color(*self._bg_color)
                self._sh_rect = None
                self._sh_cover = None
                self._rect = Rectangle(pos=(x, y), size=(w, h))
            # 硬边框（2px Line，四段闭合）
            Color(*self._border_color)
            self._border = Line(
                points=[x, y, x+w, y, x+w, y+h, x, y+h],
                close=True, width=self._border_width
            )

    def update_color(self, bg=None, border=None):
        """运行时改色（不重建 widget 树）"""
        if bg is not None:
            self._bg_color = list(bg)
        if border is not None:
            self._border_color = list(border)
        self._rebuild()


# ============================================================
# PixelLabel - 像素风标签
# ============================================================
class PixelLabel(Label):
    """像素风标签：等宽字体，关闭 hinting 保持锐利"""
    def __init__(self, **kwargs):
        kwargs.setdefault('font_name', PIXEL_FONT_NAME)
        kwargs.setdefault('font_hinting', None)   # Python None = 关闭 hinting
        super().__init__(**kwargs)


# ============================================================
# add_pixel_border - 给任意 widget 加 2px 硬边框
# ============================================================
def add_pixel_border(widget, color=None, width=2):
    """在 widget 的 canvas.after 上画 2px 硬边框（用于普通 Button/其他 widget）

    用法：
        class MyButton(Button):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                add_pixel_border(self, color=PIXEL_COLORS['cyan'])
    """
    border_color = list(color) if color else list(COLORS['border_2'])

    def _redraw(*_):
        # 移除旧的边框 Line（如果存在）
        old = getattr(widget, '_pixel_border_line', None)
        if old is not None:
            try:
                widget.canvas.after.remove(old)
            except Exception:
                pass
        # 画新边框
        with widget.canvas.after:
            Color(*border_color)
            x, y = widget.x, widget.y
            w, h = widget.width, widget.height
            if w >= 1 and h >= 1:
                widget._pixel_border_line = Line(
                    points=[x, y, x+w, y, x+w, y+h, x, y+h],
                    close=True, width=width
                )

    widget.bind(pos=_redraw, size=_redraw)
    _redraw()


if __name__ == '__main__':
    # 自测：调色板展示
    from kivy.app import App
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.boxlayout import BoxLayout
    from kivy.core.text import LabelBase
    import os as _os
    # 注册中文字体（避免 .ttf not found）
    for fp in [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]:
        if _os.path.exists(fp):
            try:
                LabelBase.register(name='MicrosoftYaHei', fn_regular=fp)
                LabelBase.register(name='Roboto', fn_regular=fp)
            except Exception:
                pass

    class PaletteApp(App):
        def build(self):
            root = GridLayout(cols=4, spacing=8, padding=12)
            for name, rgba in COLORS.items():
                hexv = '#{:02x}{:02x}{:02x}'.format(int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255))
                cell = BoxLayout(orientation='vertical', spacing=4, size_hint_y=None, height=100)
                block = PixelPanel(bg=rgba, border_color=COLORS['border_2'])
                block.size_hint = (1, None)
                block.height = 60
                cell.add_widget(block)
                lbl = PixelLabel(text=f'[b]{name}[/b]\n{hexv}', font_size=12,
                                 color=COLORS['text'], markup=True)
                cell.add_widget(lbl)
                root.add_widget(cell)
            return root

    PaletteApp().run()