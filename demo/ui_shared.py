"""
ui_shared.py - UI 层共享配置与运行时全局（模块化拆分的最低层）

内容：
  COLORS / Panel   —— 16 色调色板别名表（原 main.py 顶部定义）
  BASE_TICK_SECONDS —— 一个周期的真实秒数（单一来源 balance.TUNE）
  SPEED_STEPS 等    —— 跨 GameUI / MainMenu / HUD 共享的运行时全局。
                       ⚠️ bool/int 不可变对象不能 from-import 共享写，
                       跨模块读写必须走 ``import ui_shared as ST; ST.XXX = …``
"""
from pixel_ui import COLORS as PIXEL_COLORS, PixelPanel
from balance import TUNE, SPEED_STEPS

from kivy.core.window import Window
from i18n import t

# ---- 配色（直接复用 pixel_ui 的 16 色 + 语义别名）----
COLORS = dict(PIXEL_COLORS)
COLORS.update({
    'accent':  PIXEL_COLORS['cyan'],
    'accent2': PIXEL_COLORS['pink'],
    'accent3': PIXEL_COLORS['yellow'],
    'accent4': PIXEL_COLORS['green'],
    'warning': PIXEL_COLORS['orange'],
    'danger':  PIXEL_COLORS['red'],
    'success': PIXEL_COLORS['green'],
    'panel_dark':  PIXEL_COLORS['bg'],
    'panel_light': PIXEL_COLORS['panel_2'],
})

Panel = PixelPanel

# ---- 节奏系统（P0-1：周期 30s，速度档 ×0.5/×1/×2/×4）----
BASE_TICK_SECONDS: float = TUNE['base_tick_seconds']
DEFAULT_SPEED_IDX: int = 1
CURRENT_SPEED_IDX: int = DEFAULT_SPEED_IDX   # 跨 GameUI / 主菜单共享的速度档
REDUCE_MOTION: bool = False                   # 动效减弱（设置页 on_motion）
A11Y_SHAPES: bool = False                     # 色盲辅助 ○●▲✖（设置页 on_a11y）


def _update_window_title() -> None:
    """窗口标题跟随语言（main 装配时与切语言时都会调用）。"""
    Window.title = f"{t('app_title')} · {t('app_subtitle')}"
