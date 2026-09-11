"""
world_map.py - 像素世界地图（120 x 60 网格 / Miller 投影 / Natural Earth 真实海岸线）

设计稿：design/ui_design_v0.3.html §5「界面二：像素世界地图」
数据源：demo/pixel_assets.py（由 tools/gen_pixel_map.py 从 Natural Earth 110m 生成）

与 v3 旧版的区别
----------------
旧版手写了 20 个简化经纬度多边形（8-33 顶点），再用 Stencil 把国旗纹理裁进
多边形 —— 形状严重失真（巴西比宽还高、非洲缩成一坨），而且每个国家要
7 条 canvas 指令 + 一次 stencil push/pop，重绘成本高。

新版直接画 **像素格**：
  海面 → 经纬网 → 陆地底 #16323c → 海岸线高亮 #27505b
  → 20 国填充（状态色）→ 20 国国界（1 格宽独立游程）→ 引导线 + 标签框
国家不再是多边形，而是一组横向游程 (x, y, w)，用 Rectangle 落笔；
国界是**独立的一圈格子**（不是 stroke —— stroke 会在游程内部画出网格线）。

坐标系统
--------
网格坐标：grid x ∈ [0, 120]（西→东），grid y ∈ [0, 60]（**上→下**，row 0 最北）。
屏幕映射走一个 PushMatrix + Translate + Scale(cw, -ch) 矩阵：
    screen = (ox + gx·cw,  oy + mh − gy·ch)
所以 1300+ 个矩形只需在初始化时写一次坐标，窗口缩放只改 Translate/Scale
两个指令 —— resize 是 O(1) 而不是 O(格子数)。

⚠️ Kivy 的 widget canvas 使用**父坐标**（实测：在子组件 canvas 里画 (200,200)
   会落在父容器的 (200,200)，不是本组件的 (200,200)），所以所有绝对坐标
   都要自己加上 self.x / self.y。

公共 API（data.py / main.py 依赖，保持兼容）：
    COUNTRY_STYLES / COUNTRY_CENTERS
    WorldMap.set_on_select / set_selected / set_continent_highlight
    WorldMap.set_country_states   ← 新增：{code: 'lk'|'on'|'blk'}
"""
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import (
    Color, Rectangle, Line,
    InstructionGroup, PushMatrix, PopMatrix, Translate, Scale,
)

import pixel_assets as PA
from pixel_ui import PIXEL_FONT_NAME, PixelLabel, hex_rgba


# ============================================================
# 配色（严格对齐设计稿 §5）
# ============================================================
SEA        = '#0a1828'   # 海面
SEA_LINE   = '#12293c'   # 经纬网（每 4 格一条）
LAND       = '#16323c'   # 陆地底
COAST      = '#27505b'   # 海岸线高亮
CHIP_BG    = '#0b1218'   # 标签框底

# 国家四态：fill 填充 / edge 国界 / text 标签文字
STATE_FILL = {'lk': '#232a30', 'on': '#1f6f63', 'blk': '#5c2323', 'sel': '#4ec9b0'}
STATE_EDGE = {'lk': '#4a5560', 'on': '#3ec9ac', 'blk': '#ef4444', 'sel': '#eafffb'}
STATE_TEXT = {'lk': '#b6c2cd', 'on': '#8ff0da', 'blk': '#ffb4b4', 'sel': '#eafffb'}
# v0.4 追加色调（同一份设计令牌：--yellow / 更暗的底）
TARGET_EDGE = '#dcdcaa'   # 可投放目标描边
DIM_FILL = '#141a20'      # 不可投放（投放模式变暗）
DIM_EDGE = '#2a3138'
DIM_TEXT = '#5a646e'
# Tab 键大洲高亮：国界与标签框描边换成琥珀（同上个版本的行为，但更醒目）
CONT_EDGE  = '#dca30a'
CONT_TEXT  = '#ffe9a8'

# 兼容旧常量名（render_*.py / 外部脚本）
SEA_COLOR    = hex_rgba(SEA)
GRID_COLOR   = hex_rgba(SEA_LINE)
BORDER_COLOR = hex_rgba(STATE_EDGE['on'])

# ============================================================
# data.py 依赖的兼容接口
# ============================================================
# COUNTRY_STYLES[code]['polygon'] = 国界外轮廓折线（格坐标，Moore 追踪得来）；
# 已不是手写多边形 —— 几何单一来源依旧是 Natural Earth 栅格。
COUNTRY_STYLES = {
    code: {
        'flag': code,
        'color': hex_rgba(STATE_FILL['on']),
        'polygon': list(PA.OUTLINES.get(code, ())),
    }
    for code in PA.OWNER_CODES
}
COUNTRY_CENTERS = {code: PA.ANCHORS[code] for code in PA.OWNER_CODES}

MAP_ASPECT = PA.GRID_W / float(PA.GRID_H)      # 2:1 内接等比


def point_in_polygon(px, py, polygon):
    """射线法（保留：外部脚本 / 旧逻辑偶尔会用到）"""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


# ============================================================
# 世界地图 Widget
# ============================================================
class WorldMap(FloatLayout):
    GRID_W = PA.GRID_W
    GRID_H = PA.GRID_H
    MAP_ASPECT = PA.GRID_W / float(PA.GRID_H)   # 2:1 内接等比
    CHIP_W, CHIP_H = 4.6, 3.4        # 标签框尺寸（格）；同设计稿
    CHIP_STROKE = 0.3                # 标签框描边宽度（格）
    LABEL_FONT = 2.2                 # 标签字号（格）
    DOT = 1.1                        # 锚点方块边长（格）

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.country_labels = {}
        self.selected_code = None
        self._continent_codes = set()
        self._states = {c: 'lk' for c in PA.OWNER_CODES}
        self._on_select = None

        self._colors = {}            # code -> (fill Color, edge Color)
        self._chip_gfx = {}          # code -> (stroke Color, Rect, bg Color, Rect,
                                     #          dot Color, Rect, lead Color, Line)
        self._grid_lines = []        # [(axis, grid_pos, Line)]
        self._labels_built = False
        # v0.4 图层覆盖色：{code: (fill_hex, edge_hex, text_hex)}，空 = 用四态
        self._layer_fills = {}
        # v0.4 投放模式：可投目标集合（描黄边）+ 变暗集合（不可投）
        self._target_codes = set()
        self._dim_codes = set()
        # v0.4 S12「地图网格」开关：关闭后隐藏每 4 格一条的经纬网
        self._grid_on = True

        self._build()
        self._apply_colors()
        self.bind(pos=self._layout, size=self._layout)
        self._layout()

    # --------------------------------------------------------
    # 构建（只做一次；之后只改属性，不重建 canvas 指令）
    # --------------------------------------------------------
    def _build(self):
        before = self.canvas.before
        self._static = InstructionGroup()     # 海面 + 经纬网（绝对坐标）
        self._geo = InstructionGroup()        # 陆地/海岸/国界（受网格矩阵控制）
        self._overlay = InstructionGroup()    # 引导线 + 标签框（绝对坐标）
        before.add(self._static)
        before.add(self._geo)
        before.add(self._overlay)

        self._build_static()
        self._build_geo()
        self._build_overlay()
        self._build_labels()

    def _build_static(self):
        self._sea_color = Color(*hex_rgba(SEA))
        self._sea_rect = Rectangle()
        self._static.add(self._sea_color)
        self._static.add(self._sea_rect)

        self._static.add(Color(*hex_rgba(SEA_LINE)))
        for gx in range(4, self.GRID_W, 4):
            ln = Line(width=1)
            self._static.add(ln)
            self._grid_lines.append(('v', gx, ln))
        for gy in range(4, self.GRID_H, 4):
            ln = Line(width=1)
            self._static.add(ln)
            self._grid_lines.append(('h', gy, ln))

    def _build_geo(self):
        # 网格矩阵：先平移到地图内接矩形的左下角，再缩放（y 取负 → 行号向下增长）
        self._translate = Translate(0, 0, 0)
        self._scale = Scale(1, 1, 1)
        self._geo.add(PushMatrix())
        self._geo.add(self._translate)
        self._geo.add(self._scale)

        # 陆地底
        self._geo.add(Color(*hex_rgba(LAND)))
        for gx, gy, gw in PA.LAND_RUNS:
            self._geo.add(Rectangle(pos=(gx, gy), size=(gw, 1)))
        # 海岸线高亮（1 格宽游程）
        self._geo.add(Color(*hex_rgba(COAST)))
        for gx, gy, gw in PA.COAST_RUNS:
            self._geo.add(Rectangle(pos=(gx, gy), size=(gw, 1)))

        # 20 国：填充 + 国界（颜色可变 → 保留 Color 指令引用）
        for code in PA.OWNER_CODES:
            fill = Color(*hex_rgba(STATE_FILL['lk']))
            self._geo.add(fill)
            for gx, gy, gw in PA.FILL_RUNS[code]:
                self._geo.add(Rectangle(pos=(gx, gy), size=(gw, 1)))
            edge = Color(*hex_rgba(STATE_EDGE['lk']))
            self._geo.add(edge)
            for gx, gy, gw in PA.BORDER_RUNS[code]:
                self._geo.add(Rectangle(pos=(gx, gy), size=(gw, 1)))
            self._colors[code] = (fill, edge)

        self._geo.add(PopMatrix())

    def _build_overlay(self):
        for code in PA.OWNER_CODES:
            stroke = Color(1, 1, 1, 0)
            self._overlay.add(stroke)
            chip = Rectangle()
            self._overlay.add(chip)
            bg = Color(*hex_rgba(CHIP_BG))
            self._overlay.add(bg)
            inner = Rectangle()
            self._overlay.add(inner)
            lead = Color(1, 1, 1, 0)
            self._overlay.add(lead)
            line = Line(width=1)
            self._overlay.add(line)
            dot = Color(1, 1, 1, 0)
            self._overlay.add(dot)
            mark = Rectangle()
            self._overlay.add(mark)
            self._chip_gfx[code] = (stroke, chip, bg, inner, lead, line, dot, mark)

    def _build_labels(self):
        for code in PA.OWNER_CODES:
            lbl = PixelLabel(
                text=code, bold=True, halign='center', valign='middle',
                size_hint=(None, None), color=hex_rgba(STATE_TEXT['lk']),
            )
            lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
            self.add_widget(lbl)
            self.country_labels[code] = lbl
        self._labels_built = True

    # --------------------------------------------------------
    # 布局
    # --------------------------------------------------------
    def _map_rect(self):
        """面板内保持 2:1 的内接矩形 (abs_x, abs_y, w, h) —— 绝对坐标"""
        W, H = self.width, self.height
        if W <= 1 or H <= 1:
            return self.x, self.y, max(W, 1.0), max(H, 1.0)
        w = W
        h = W / self.MAP_ASPECT
        if h > H:
            w, h = H * self.MAP_ASPECT, H
        return self.x + (W - w) / 2.0, self.y + (H - h) / 2.0, w, h

    def _layout(self, *args):
        self._sea_rect.pos = (self.x, self.y)
        self._sea_rect.size = (self.width, self.height)

        ox, oy, mw, mh = self._map_rect()
        cw = mw / float(self.GRID_W)
        ch = mh / float(self.GRID_H)

        for axis, g, ln in self._grid_lines:
            if not self._grid_on:
                # 关闭网格：清空点列（Line width=0 在部分后端会报警）
                ln.points = []
                continue
            if axis == 'v':
                x = ox + g * cw
                ln.points = [x, oy, x, oy + mh]
            else:
                y = oy + mh - g * ch
                ln.points = [ox, y, ox + mw, y]

        self._translate.xy = (ox, oy + mh)
        self._scale.xyz = (cw, -ch, 1.0)

        self._layout_labels(ox, oy, mw, mh, cw, ch)

    def _layout_labels(self, ox, oy, mw, mh, cw, ch):
        g2x = lambda gx: ox + gx * cw
        g2y = lambda gy: oy + mh - gy * ch

        for code, lbl in self.country_labels.items():
            lx, ly = PA.LABELS[code]
            ax, ay = PA.ANCHORS[code]
            x0, x1 = g2x(lx - self.CHIP_W / 2), g2x(lx + self.CHIP_W / 2)
            y0, y1 = g2y(ly + self.CHIP_H / 2), g2y(ly - self.CHIP_H / 2)
            stroke_px = max(1.0, self.CHIP_STROKE * ch)

            lbl.pos = (x0, y0)
            lbl.size = (x1 - x0, y1 - y0)
            lbl.font_size = max(8.5, self.LABEL_FONT * ch)

            stroke, chip, _bg, inner, lead, line, dot, mark = self._chip_gfx[code]
            chip.pos, chip.size = (x0, y0), (x1 - x0, y1 - y0)
            inner.pos = (x0 + stroke_px, y0 + stroke_px)
            inner.size = (max(x1 - x0 - 2 * stroke_px, 0.1),
                          max(y1 - y0 - 2 * stroke_px, 0.1))

            # 锚点方块 + 到标签框边缘的引导线
            hw, hh = self.DOT * cw / 2.0, self.DOT * ch / 2.0
            acx, acy = g2x(ax), g2y(ay)
            mark.pos, mark.size = (acx - hw, acy - hh), (self.DOT * cw, self.DOT * ch)

            # 引导线终点 = 锚点→框心连线与外框的交点（不侵入框内）
            cxp, cyp = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            ex, ey = self._edge_hit(acx, acy, x0, y0, x1, y1, cxp, cyp)
            line.points = [acx, acy, ex, ey]

    @staticmethod
    def _edge_hit(ax, ay, x0, y0, x1, y1, cx, cy):
        """线段 (a→c) 与矩形 [x0,x1]×[y0,y1] 的首个交点（用于引导线收尾）"""
        dx, dy = cx - ax, cy - ay
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return cx, cy
        best = None
        for t in ([ (x0 - ax) / dx, (x1 - ax) / dx ] if abs(dx) > 1e-9 else []) + \
                 ([ (y0 - ay) / dy, (y1 - ay) / dy ] if abs(dy) > 1e-9 else []):
            if t <= 0:
                continue
            px, py = ax + dx * t, ay + dy * t
            if x0 - 0.75 <= px <= x1 + 0.75 and y0 - 0.75 <= py <= y1 + 0.75:
                if best is None or t < best[0]:
                    best = (t, px, py)
        return (best[1], best[2]) if best else (cx, cy)

    # --------------------------------------------------------
    # 状态着色
    # --------------------------------------------------------
    def _state_of(self, code):
        if code == self.selected_code:
            return 'sel'
        return self._states.get(code, 'lk')

    def _layer_tone(self, code):
        """当前显示色 (fill_hex, edge_hex, text_hex, lead_alpha) —— 图层覆盖优先。

        Returns:
            tuple | None: 图层强制着色时的三元组；图层关闭（四态模式）返回 None。
        """
        ov = self._layer_fills.get(code)
        if ov is not None:
            return ov[0], ov[1], ov[2]
        # 投放模式：不可投目标整体变暗（设计稿「不可投国家变暗」）
        if code in self._dim_codes:
            return DIM_FILL, DIM_EDGE, DIM_TEXT
        return None

    def _apply_colors(self):
        for code, (fill, edge) in self._colors.items():
            st = self._state_of(code)
            tone = self._layer_tone(code)
            if tone is not None:
                fill.rgba = hex_rgba(tone[0])
                edge.rgba = hex_rgba(tone[1])
                continue
            fill.rgba = hex_rgba(STATE_FILL[st])
            cont = code in self._continent_codes and st != 'sel'
            # 投放模式：可投目标描黄边（设计稿「描黄边 + 准星」）
            if code in self._target_codes:
                edge.rgba = hex_rgba(TARGET_EDGE)
            else:
                edge.rgba = hex_rgba(CONT_EDGE if cont else STATE_EDGE[st])

        for code, lbl in self.country_labels.items():
            st = self._state_of(code)
            tone = self._layer_tone(code)
            if tone is not None:
                lbl.color = hex_rgba(tone[2])
                edge_rgba = hex_rgba(tone[1])
            else:
                cont = code in self._continent_codes and st != 'sel'
                lbl.color = hex_rgba(CONT_TEXT if cont else STATE_TEXT[st])
                if code in self._target_codes:
                    edge_rgba = hex_rgba(TARGET_EDGE)
                else:
                    edge_rgba = hex_rgba(CONT_EDGE if cont else STATE_EDGE[st])
            stroke, _chip, _bg, _inner, lead, _line, dot, _mark = self._chip_gfx[code]
            stroke.rgba = edge_rgba
            dot.rgba = edge_rgba
            lead.rgba = (edge_rgba[0], edge_rgba[1], edge_rgba[2], 0.7)

    def set_grid_mode(self, idx: int) -> None:
        """地图经纬网开关（设计稿 S12「地图网格」）。

        Args:
            idx: ``0`` = 隐藏经纬网，非 0 = 显示。
        """
        self._grid_on = bool(idx)
        self._layout()

    def set_layer_fills(self, fills):
        """图层着色覆盖（设计稿 S13）。

        Args:
            fills: ``{code: (fill_hex, edge_hex, text_hex)}``；传 ``None`` / ``{}``
                则退回四态着色。
        """
        new = dict(fills or {})
        if new == self._layer_fills:
            return
        self._layer_fills = new
        self._apply_colors()

    def set_target_mode(self, targets=None, dim=None):
        """投放模式：可投目标描黄边，不可投目标变暗（设计稿 S04）。

        Args:
            targets: 可投放国家集合；``None``/空 → 退出投放模式。
            dim: 需要变暗的国家集合（不可投放）。
        """
        new_t = set(targets or ())
        new_d = set(dim or ())
        if new_t == self._target_codes and new_d == self._dim_codes:
            return
        self._target_codes = new_t
        self._dim_codes = new_d
        self._apply_colors()

    def set_country_states(self, states):
        """{code: 'lk'|'on'|'blk'} —— 由 main.refresh_all 每 tick 调用"""
        changed = False
        for code, st in (states or {}).items():
            if code in self._states and self._states[code] != st:
                self._states[code] = st
                changed = True
        if changed:
            self._apply_colors()

    # --------------------------------------------------------
    # 外部接口
    # --------------------------------------------------------
    def set_on_select(self, callback):
        self._on_select = callback

    def set_selected(self, code):
        """高亮选中的国家（换色，不重建 canvas）"""
        if code == self.selected_code:
            return
        self.selected_code = code
        self._apply_colors()

    def set_continent_highlight(self, codes):
        """Tab 键高亮某大洲的国家（codes=None / 空集合 → 取消）"""
        new = set(codes or ())
        if new == self._continent_codes:
            return
        self._continent_codes = new
        self._apply_colors()

    def _refresh_label_colors(self):
        """兼容旧接口名"""
        self._apply_colors()

    def label_bg(self, code):
        """标签框描边色（供外部复用同一套状态色）"""
        st = self._state_of(code)
        if code in self._continent_codes and st != 'sel':
            return hex_rgba(CONT_EDGE)
        return hex_rgba(STATE_EDGE[st])

    # --------------------------------------------------------
    # 点击命中：归属格查表 O(1)
    # --------------------------------------------------------
    def _grid_at(self, px, py):
        ox, oy, mw, mh = self._map_rect()
        if mw <= 1 or mh <= 1:
            return None
        cw, ch = mw / float(self.GRID_W), mh / float(self.GRID_H)
        return (int((px - ox) // cw) if cw > 0 else -1,
                int((oy + mh - py) // ch) if ch > 0 else -1)

    def hit_country(self, px, py):
        """屏幕坐标（绝对）→ 国家代码；未命中返回 None"""
        g = self._grid_at(px, py)
        if g is None:
            return None
        gx, gy = g
        code = PA.owner_at(gx, gy)
        if code:
            return code
        # 1 格容错环：小国在低分辨率下只有几个格子，给一点手感余量
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            code = PA.owner_at(gx + dx, gy + dy)
            if code:
                return code
        return None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            code = self.hit_country(touch.x, touch.y)
            if code and self._on_select:
                self._on_select(code)
                return True
        return super().on_touch_down(touch)


# ============================================================
# 自测：单开地图（Tab 键切大洲，点击选国）
# ============================================================
if __name__ == '__main__':
    from kivy.config import Config
    Config.set('graphics', 'width', '1200')
    Config.set('graphics', 'height', '760')
    from kivy.app import App
    from kivy.core.window import Window

    STATES = ['lk', 'on', 'blk']

    class MapApp(App):
        def build(self):
            root = WorldMap()
            root._states['CN'] = 'on'
            root._states['US'] = 'on'
            root._states['BR'] = 'on'
            root._states['RU'] = 'on'
            root._states['DE'] = 'blk'
            root._states['JP'] = 'on'
            root.set_selected('CN')
            root.set_on_select(lambda c: root.set_selected(c))
            Window.bind(on_key_down=lambda *a: root.set_continent_highlight({'CN', 'JP'}))
            return root

    MapApp().run()
