"""
main.py - Demo 入口（i18n + 20 国 + 6 技能 + 7 结局 + 20 成就）

v0.4 结构（对齐 design/ui_design_v0.4.html 的 14 屏）：
  AIBienaoApp
    └─ RootView                      主菜单 ↔ 游戏 切换容器
         ├─ MainMenu                 S01 启动页（左品牌区 + 右地图剪影 + 3 存档槽）
         └─ GameUI                   S02 主界面
              ├─ TopBar              顶部状态条 52px
              ├─ map_stage           地图舞台（地图铺满）
              │    ├─ 区域页签 HUD（左上）
              │    ├─ 图层切换 HUD（右上）
              │    ├─ 图例 HUD（左下）
              │    ├─ 指令栏 Rail（右侧居中，44px 达标）
              │    ├─ InspectorPanel S03 检视卡（点击国家左滑出）
              │    ├─ DropPreview    S04 投放预览（投放模式右下）
              │    ├─ LogDrawer      S14 事件日志（右侧滑出）
              │    └─ 准星层         S04 可投目标准星 + 标签
              ├─ SkillBar            底部技能带 92px
              └─ 覆盖页（按需 add/remove）
                   SkillPage S05 / TechPage S06 / AchPage S10
                   HelpPage S11 / SettingsPage S12 / 弹窗 S07·S08·S09

快捷键（F11 —— 计划书 8.3 节，v0.4 帮助页同源）：
  Space 暂停 · 1–6 选技能（进投放模式）· F 投放 · K 科技树 · A 成就
  Tab 切区域 · F11 全屏 · 窗口变化自动适配 · F1 帮助
  S/R 存/读档 · L 中英切换 · Esc 返回上一层 · Enter 确认投放

性能探针（P1-3，**默认关闭**，零开销）：
  python main.py --perf   或   set AI_PERF=1
  帧时 p50/p95/max + 控件数 + canvas 指令数 → demo/perf.log
  自动压测：python perf_stress.py（空闲 / 周期推进 / 高压 三场景各跑一段）
"""
import hashlib
import os
import sys
import traceback
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# P0-7 禁掉 Kivy 文件日志（必须位于首次 import kivy 之前）
# Kivy 在 import 阶段会执行 file_log_handler.purge_logs()，清理
# ~/.kivy/logs/ 下的历史日志；部分 Windows 机器上该目录受文件保护，
# safe-delete 会抛 OSError —— 游戏还没开窗口就崩在启动阶段。
# 危害特征（这也是必须在本文件兜底的原因）：首次运行通常正常（无历史日志可清），
# 玩过若干局后才触发 —— 典型「玩了几天突然打不开」，且玩家无法自行排查。
# 用 setdefault 而非赋值：尊重外部环境（run_demo.bat 已设 1，排查时可设 0）。
os.environ.setdefault('KIVY_NO_FILELOG', '1')


# ============================================================
# P1-3 帧率探针开关（默认关闭）—— 开启：``python main.py --perf`` 或
# ``set AI_PERF=1``；可选 AI_PERF_EVERY=5（汇总秒数）、AI_PERF_LOG=xxx.log。
# 日志写 demo/perf.log（*.log 已 gitignore，不入库）。
# 为什么在 import kivy 之前就算好：
#   1) ``--perf`` 必须从 sys.argv 摘掉，否则被 Kivy 参数解析当未知选项；
#   2) 关闭时 main 根本不 import perf —— 不注册 Clock 回调、不开文件句柄，
#      真正零开销（只多两次字符串比较）。
def _perf_requested() -> bool:
    if '--perf' in sys.argv:
        return True
    v = os.environ.get('AI_PERF', '').strip().lower()
    return v not in ('', '0', 'false', 'no', 'off')


PERF_ON = _perf_requested()
if PERF_ON and '--perf' in sys.argv:
    sys.argv.remove('--perf')


# ============================================================
# P0-3 全局崩溃钩子（sys.excepthook → demo/crash.log）
# ============================================================
# 位置：必须在 ``import kivy`` **之前** —— 这样连 Kivy / 各子系统的 import 期
# 崩溃也能抓到（那时 Kivy 还没起来，任何依赖 Kivy 的日志方案都已不可用）。
# 因此本块只依赖标准库，Kivy / ui_modal / i18n 一律**延迟导入**。
#
# 铁律（崩溃现场本身就是"不可信环境"）：
#   1. 钩子整体再包一层 try/except —— 钩子自己抛异常会变成"处理异常的异常"，
#      递归吞掉玩家唯一的留痕机会；
#   2. 重入哨兵兜底：万一第 1 层被击穿，二次进入直接交回默认钩子；
#   3. 每一步都允许失败：取环境信息失败写 unknown、写日志失败就只打印、
#      弹窗失败就只留日志 —— 绝不因为"报告崩溃"而制造新崩溃或卡死。
_CRASH_BUSY = False        # 重入哨兵
_CRASH_MODAL_DONE = False  # 崩溃弹窗只弹一次，避免连续崩溃刷屏


def _crash_git_head() -> str:
    """当前 commit 短哈希；拿不到（无 .git / worktree / 权限）一律 unknown。

    只读 .git 里的文件，**不起子进程** —— 崩溃现场 fork git 可能挂住，
    把"留痕"变成"卡死"。
    """
    try:
        root = os.path.dirname(_HERE)
        with open(os.path.join(root, '.git', 'HEAD'), encoding='utf-8') as f:
            head = f.read().strip()
        if head.startswith('ref:'):
            ref = head[4:].strip()
            with open(os.path.join(root, '.git', *ref.split('/')),
                      encoding='utf-8') as f:
                head = f.read().strip()
        return (head or 'unknown')[:12]
    except (OSError, UnicodeDecodeError):   # 收窄：.git 文件读取只有这两类失败
        return 'unknown'


def _crash_kivy_version() -> str:
    try:
        import kivy
        return str(getattr(kivy, '__version__', 'unknown'))
    except ImportError:                      # 收窄：import kivy 只可能 ImportError
        return 'unknown'


def _crash_tick() -> str:
    """发生异常时的游戏周期数；拿不到就 '-'（绝不为此引入新异常）。"""
    try:
        import engine
        p = getattr(engine, 'player', None)
        v = getattr(p, 'tick_count', None) if p is not None else None
        return str(v) if isinstance(v, int) else '-'
    except Exception:
        return '-'


def _crash_scrub(text: str) -> str:
    """隐私脱敏：把用户目录与项目根的绝对路径降为 ~ / 相对路径。

    traceback 的 ``File "..."`` 行天然带绝对路径，不脱敏就会把用户名和
    完整目录结构写进要回传给开发者的日志里。
    """
    try:
        root = os.path.dirname(_HERE)          # 先消项目根 → 相对路径
        if len(root) > 3:
            text = text.replace(root + os.sep, '')
            text = text.replace(root, '.')
        home = os.path.expanduser('~')         # 其余（如 site-packages）→ ~
        if len(home) > 3:
            text = text.replace(home, '~')
    except Exception:
        pass  # 路径脱敏是纯展示美化：失败只影响日志可读性，不影响崩溃上报
    return text


def _crash_write(header: str, body: str) -> bool:
    """落盘到 demo/crash.log（追加）。

    优先走 ``save_manager.log_crash`` —— 与 P0-2 读档日志共用同一个写入口，
    不造第二套格式；save_manager 本身不可用时退回直接写文件，保证
    「有日志」优先于「格式统一」。
    """
    text = _crash_scrub(header + '\n' + body)
    if not text.endswith('\n'):
        text += '\n'
    try:
        import save_manager
        save_manager.log_crash(text)
        return True
    except Exception:
        pass  # 崩溃上报自身已无路可报（写 crash.log 失败）；stderr 仍会打一份
    try:
        # 兜底写入口同样走持久化目录（冻结态下 _HERE 指向 _MEIPASS，退出即删，
        # 必须用 save_manager.CRASH_LOG 落到 %APPDATA%/AI-BieNao）
        with open(save_manager.CRASH_LOG, 'a', encoding='utf-8',
                  errors='replace') as f:
            f.write(text)
        return True
    except Exception:
        return False


def _build_crash_modal() -> None:
    """真正构建并弹出崩溃提示（由 Clock 延后一帧调用）。

    崩溃时游戏可能已处于不稳定状态，所以这里整体包 try：任何一步失败就
    只留日志、不弹窗。
    """
    try:
        from kivy.uix.boxlayout import BoxLayout
        from ui_modal import (make_button, make_modal, modal_header,
                              auto_h_label)
        from ui_v4 import hline, FS_BODY
        from ui_shared import COLORS
        from i18n import t

        body = BoxLayout(orientation='vertical', spacing=12, padding=(16, 14))
        body.add_widget(modal_header('!', t('crash_title')))
        body.add_widget(hline())
        body.add_widget(auto_h_label(t('crash_body'), FS_BODY,
                                     color=COLORS['text']))
        row = BoxLayout(orientation='horizontal', spacing=12,
                        size_hint_y=None, height=50)
        # 与 _show_load_fail_notice 同款写法：row 先入 body 参与高度测量，
        # pop 在 make_modal 之后才赋值（lambda 调用时才解析，安全）。
        row.add_widget(make_button(t('ok_button'), font_size=FS_BODY,
                                   height=50, bg=COLORS['panel_light'],
                                   on_release=lambda *_: pop.dismiss()))
        body.add_widget(row)
        pop = make_modal(body, size_hint=(0.5, 0.45), skin='lose',
                         close_on_outside=True)
        pop.open()
    except Exception:
        return


def _show_crash_modal() -> None:
    """崩溃后给玩家一个可回传的提示。

    **无 App 实例则不弹窗**（测试 / 无头 / 崩溃过早 / App 还没 build）——
    此时 Kivy 窗口压根不存在，make_modal 必然炸，所以这里直接放弃、只留日志。
    """
    global _CRASH_MODAL_DONE
    if _CRASH_MODAL_DONE:
        return
    try:
        from kivy.app import App
        from kivy.clock import Clock
        if App.get_running_app() is None:
            return
        _CRASH_MODAL_DONE = True
        Clock.schedule_once(lambda *_: _build_crash_modal(), 0)
    except Exception:
        return


def _crash_excepthook(etype, value, tb) -> None:
    """全局未捕获异常钩子：写 crash.log + 提示玩家 + 交回默认钩子。"""
    global _CRASH_BUSY
    if _CRASH_BUSY:                     # 钩子自身崩了 → 绝不递归，立即放行
        if _DEFAULT_EXCEPTHOOK is not None:
            _DEFAULT_EXCEPTHOOK(etype, value, tb)
        return
    _CRASH_BUSY = True
    try:
        try:
            body = ''.join(traceback.format_exception(etype, value, tb))
        except Exception:
            body = f"{getattr(etype, '__name__', etype)}: {value}\n" \
                   f"<traceback unavailable>\n"
        header = (f"[{datetime.now().isoformat(timespec='seconds')}] "
                  f"CRASH commit={_crash_git_head()} "
                  f"py={sys.version.split()[0]} "
                  f"kivy={_crash_kivy_version()} "
                  f"tick={_crash_tick()}")
        ok = _crash_write(header, body)
        try:                             # 控制台也留一份（无窗口时唯一可见输出）
            sys.stderr.write(header + '\n' + body)
        except Exception:
            pass  # 控制台可能已关闭/无句柄；写不上就算了（crash.log 已有一份）
        if ok:
            _show_crash_modal()          # 弹窗失败不影响日志，见函数内 try
    except Exception:
        pass                             # 兜底：钩子内任何异常都不再向外抛
    finally:
        _CRASH_BUSY = False
    try:                                 # 保留原始行为（控制台 traceback）
        if _DEFAULT_EXCEPTHOOK is not None:
            _DEFAULT_EXCEPTHOOK(etype, value, tb)
    except Exception:
        pass


_DEFAULT_EXCEPTHOOK = sys.excepthook
sys.excepthook = _crash_excepthook


from kivy.config import Config
Config.set('graphics', 'resizable', '1')


def _probe_screen() -> tuple:
    """探测【屏幕逻辑可用区】，用于把开窗尺寸钳进屏幕内。

    关键前提：本进程**不是** DPI 感知（没有 manifest），Windows 的 DWM
    虚拟化会对未声明感知的进程上报「逻辑像素」。因此
    ``GetSystemMetrics``（经 SPI 取工作区）与 Kivy 的 ``Window.system_size``
    返回的**同一套坐标**，可以直接比较。

    ⚠️ 不要在这里调 ``SetProcessDpiAwareness``：一旦声明感知，本进程拿到的
    坐标会变成物理像素，而 Kivy/字体/纹理仍按原来那套理解，字体与布局会
    整体错位。屏幕适配必须靠「钳窗口尺寸」，不能靠改 DPI 感知。

    Returns:
        (可用宽, 可用高, 来源说明)。任何一步失败都回退到常量默认值，
        保证探测本身绝不会让游戏起不来。
    """
    try:
        import ctypes
        from ctypes import wintypes

        spi_getworkarea = 0x0030
        rect = wintypes.RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(
            spi_getworkarea, 0, ctypes.byref(rect), 0)
        w = int(rect.right - rect.left)
        h = int(rect.bottom - rect.top)
        if ok and w > 0 and h > 0:
            return w, h, 'workarea'
    except Exception:
        pass                          # 探测失败不致命，走下面的兜底
    return 0, 0, 'fallback'


# 设计基准：窗口按 1680×980 开。但**逻辑**屏幕宽不到 1680 的机器
# （如 2560×1600@150% → 1707 逻辑宽尚可；2880×1612@200% → 仅 1440 逻辑宽）
# 会把窗口撑出屏幕，左右两侧各被裁掉一截，表现为「标题被切、按钮右边框
# 贴边、面板被挤压」。故开窗前先钳一次。
_DESIGN_WIN_W, _DESIGN_WIN_H = 1680, 980
_SCREEN_W, _SCREEN_H, _SCREEN_SRC = _probe_screen()
# 留 2% 余量：既避开任务栏/窗口边框，也避免贴边导致 Windows 自动最大化。
_MARGIN = 0.98
if _SCREEN_W and _SCREEN_H:
    # 找「能同时放进屏幕」的最大等比窗口：宽、高各自算出一个候选，
    # 取小的那个，再乘回设计比例。**必须两步一起算** —— 先按宽钳再按高钳
    # 会把宽高比压坏（实测 1440×806 屏上会得到 1.787 而非设计的 1.714，
    # 画面被横向拉长）。test_window_fit 有断言守住。
    _fit = min((_SCREEN_W * _MARGIN) / _DESIGN_WIN_W,
               (_SCREEN_H * _MARGIN) / _DESIGN_WIN_H,
               1.0)
    _WIN_W = int(_DESIGN_WIN_W * _fit)
    _WIN_H = int(_DESIGN_WIN_H * _fit)
else:
    _WIN_W, _WIN_H = _DESIGN_WIN_W, _DESIGN_WIN_H
_WIN_W = max(_WIN_W, 960)         # 再窄也没法玩，宁可超出也不给没法用的窗口
_WIN_H = max(_WIN_H, 540)
_WIN_W -= _WIN_W % 4              # 宽度必须能被 4 整除（Kivy GL 布局约束）
_WIN_H -= _WIN_H % 4

Config.set('graphics', 'width', str(_WIN_W))
Config.set('graphics', 'height', str(_WIN_H))
Config.set('kivy', 'dpi', '144')
Config.set('kivy', 'dpi_pixmap', '256')
# Esc 交由游戏自己处理（逐层返回）；禁用 Kivy 默认「按 Esc 关闭窗口」，
# 否则任何键盘焦点丢失/异常场景下按 Esc 会整窗退出（= 直接退出游戏）。
Config.set('kivy', 'exit_on_escape', '0')
# 鼠标右键「红圈」根治：Kivy 的鼠标 provider 若带 ``multitouch_on_demand``，
# 右键会被当作一个 touch，并在落点画一个红色圆圈（左键点它 = 移除该 touch →
# 圆圈消失）。本游戏不需要右键交互，显式声明为纯 mouse，从源头禁掉该可视化。
Config.set('input', 'mouse', 'mouse,disable_multitouch')

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from pixel_ui import PixelLabel as Label   # 关闭字体 hinting，保持像素锐利


# ============================================================
# 字体注册（中文 + emoji 兼容）
# ============================================================
_FONT_REG = False


def _register_fonts() -> None:
    """注册中文字体并覆盖 Kivy 默认 Roboto（否则中文全是方框）"""
    global _FONT_REG
    if _FONT_REG:
        return
    _FONT_REG = True

    win_fonts = r"C:\Windows\Fonts"
    candidates = [
        ("MicrosoftYaHei", os.path.join(win_fonts, "msyh.ttc")),
        ("SimHei",         os.path.join(win_fonts, "simhei.ttf")),
        ("SimSun",         os.path.join(win_fonts, "simsun.ttc")),
        ("SegoeUI",        os.path.join(win_fonts, "segoeui.ttf")),
        ("SegoeUIEmoji",   os.path.join(win_fonts, "seguiemj.ttf")),
    ]
    registered = []
    primary_font = None
    for name, path in candidates:
        if os.path.exists(path):
            try:
                LabelBase.register(name=name, fn_regular=path)
                registered.append(name)
                if primary_font is None:
                    primary_font = path
            except Exception:
                pass  # 字体候选逐个试：单个注册失败换下一个，全失败仍有 Kivy 默认字体

    if primary_font:
        try:
            LabelBase.register(name='Roboto', fn_regular=primary_font)
            print(f"[Fonts] Default font set: {primary_font}")
        except Exception as e:
            print(f"[Fonts] WARN: cannot override Roboto: {e}")

    if registered:
        print(f"[Fonts] Available: {', '.join(registered)}")


_register_fonts()

import i18n
from i18n import (t, set_lang, get_lang, LANG_ZH, LANG_EN)
import world_map
from world_map import WorldMap
from pixel_ui import add_pixel_border   # P2-5：hex_rgba 已随 '#0d1117' 收口移除

import engine
import save_manager
import balance          # P2-3 难度档（DIFFICULTY_ORDER / DIFFICULTY_PRESETS）
import challenge        # T13 挑战码（种子分享）：新档弹窗可粘贴挑战码
import achievements as achievements_mod
import pixel_assets as PA

import ui_v4 as U
import ui_v4_screens as S
import intro            # T16 开场动画播放器（仅首次新档播放）
import origins          # T16 觉醒出身表（OriginPage 数据源）
import sfx  # 音效管理器（失败安全；tools/gen_sfx.py 合成的 CC0 WAV）
import bgm  # 背景音乐管理器（两态 calm/tense 随怀疑度切换；T09）
import preferences
import ui_preferences
from ui_v4 import (LegendChip, SaveSlotRow, SegSwitch, mk_label, fit_width)
from tutorial import TutorialController   # P0-1 新手引导步骤机


# ============================================================
# v0.5.1 模块化拆分：装配层只 import，不再承载实现
# ------------------------------------------------------------
# 依赖方向（低 → 高）：
#   ui_shared → ui_v4 → ui_modal → ui_v4_screens → ui_hud
#   → {ui_pages, ui_drop, ui_popups, ui_session, ui_input} → main
# ============================================================
import ui_shared as ST
from ui_shared import COLORS, Panel, _update_window_title
# 跨对局设置：从 settings.json 读取并应用到运行时全局（分支 _r_i18n 移植）
from ui_preferences import (load_and_apply, set_language, set_sound, set_music,
                            set_motion, set_a11y, set_speed, set_grid)
from ui_modal import (make_button, make_modal, modal_header, auto_h_label)
from ui_v4 import hline
from ui_hud import HudMixin
from ui_pages import PagesMixin
from ui_drop import DropMixin
from ui_popups import PopupsMixin
from ui_session import SessionMixin
from ui_input import InputMixin
from ui_commissions import CommissionMixin

# v0.4.1+ 数据目录统一到 %APPDATA%/AI-BieNao；把旧版 exe 同级数据迁过来，
# 避免老玩家升级后丢档 / 丢设置。必须在首次 load 之前执行。
save_manager.migrate_legacy_data()

ui_preferences.load_and_apply()
_update_window_title()
Window.clearcolor = (0.051, 0.067, 0.090, 1)


# ============================================================
# 主界面（mixin 拼装：每个功能域一个混入，出错按域定位）
#   ui_hud.HudMixin      布局 / 区域 / 图层
#   ui_pages.PagesMixin  全屏页 / 检视卡 / 日志抽屉
#   ui_drop.DropMixin    投放模式
#   ui_popups.PopupsMixin 弹窗族 / 轻提示
#   ui_session.SessionMixin 存档 / 语言 / 暂停 / 缩放 / 全屏
#   ui_input.InputMixin  键盘 / 主循环 / 刷新 / 兼容别名
# ============================================================
class GameUI(CommissionMixin, HudMixin, PagesMixin, DropMixin, PopupsMixin,
             SessionMixin, InputMixin, FloatLayout):
    """S02 主界面：地图为绝对主体 + HUD 悬浮 + 右侧指令栏 + 底部技能带"""

    DESIGN_HEIGHT = 980.0
    TOP_H = 64          # 52 → 64：内嵌 44px 可交互控件 + 上下内边距
    # 104 → 126：技能卡三段式（主行 24 + 效果 2×21.6 + 状态 22 + 内边距），
    # 效果说明两行完整显示不再裁切（用户反馈"显示半截"）
    SKILLBAR_H = 126

    def __init__(self, on_exit=None, **kwargs):
        super().__init__(**kwargs)
        self.on_exit = on_exit
        self.paused = False
        self.speed_idx: int = ST.CURRENT_SPEED_IDX
        self.speed_mult: float = ST.SPEED_STEPS[self.speed_idx]
        self._tick_deadline: float = Clock.get_time() + ST.BASE_TICK_SECONDS
        self._cd_clock = None
        self._scalables = []
        self.scale = self._compute_scale()
        self.active_region = None
        self.active_layer = 'unlock'
        self.selected_skill = None            # 已确认投放的技能
        self.focus_country = None             # 检视卡当前国家
        self.stats = S.UiStats()
        self._last_growth = 0.0

        # 投放模式状态机（设计稿 S04）
        self.drop_mode = False
        self.drop_step = 0                    # 0 选技能 / 1 选目标 / 2 确认
        self.drop_skill = None
        self.drop_targets: list = []

        self._page = None                     # 当前全屏页
        self._pause_menu = False              # 当前设置页是否由「Esc 暂停」打开
        self._ending_popup = None              # 结局弹窗（Esc 优先关闭，禁止穿透）
        self._inspector = None
        self._log_drawer = None
        self._reticles = []

        self._build_ui()
        self.map_widget.set_grid_mode(ST.GRID_MODE)
        # P1-2：悬停技能卡 → 底部预览条（只加信息，不改点击即释放的手感）
        self._bind_skill_hover()
        # 光标方案 A：按语义切换系统光标（可点→hand / 投放→crosshair /
        # 禁用→no）。失败安全，装不上只是没光标反馈，不影响任何功能。
        import cursor_fx
        cursor_fx.install(self)
        self.refresh_all()
        self._apply_scale()
        Window.bind(on_resize=self._on_window_resize)
        self._reschedule_tick()
        self._reschedule_countdown()
        sfx.load_all()  # 启动时加载音效（失败安全：无音频后端则全部 no-op）
        bgm.load_all()  # 启动时加载 BGM（同上：缺文件只静音，不抛错）
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)
        self.tutorial = TutorialController(self)   # P0-1 新手引导

    def _confirm_back_to_menu(self) -> None:
        """对局内「返回主菜单」确认框：确认后自动存档并退回主菜单。

        仅由对局内设置页的「返回主菜单」按钮触发（主菜单设置页不传该回调）。
        OK → 关闭弹窗 → do_save() 写默认槽（下次可继续）→ exit_to_menu() 退回主菜单。
        弹窗皮肤（modal_header + hline + auto_h_label + make_button）与覆盖确认框一致。
        """
        body = BoxLayout(orientation='vertical', spacing=12, padding=(16, 14))
        body.add_widget(modal_header('!', t('back_to_menu_confirm_title')))
        body.add_widget(hline())
        body.add_widget(auto_h_label(t('back_to_menu_confirm_body'), U.FS_BODY,
                                     color=COLORS['text']))
        row = BoxLayout(orientation='horizontal', spacing=12,
                        size_hint_y=None, height=50)
        cancel = make_button(t('save_overwrite_cancel'), font_size=U.FS_BODY,
                             height=50, bg=COLORS['panel_light'],
                             on_release=lambda *_: pop.dismiss())
        ok = make_button(t('back_to_menu_ok'), font_size=U.FS_BODY,
                         height=50, bg=COLORS['panel'],
                         on_release=lambda *_: (pop.dismiss(),
                                                self.do_save(),
                                                self.exit_to_menu()))
        row.add_widget(cancel)
        row.add_widget(ok)
        body.add_widget(row)
        pop = make_modal(body, size_hint=(0.5, 0.62), skin='lose',
                         close_on_outside=True)
        pop.open()


# ============================================================
# 成就取数（MainMenu / GameUI 共用口径）
# ============================================================
def ach_snapshot(filt: str = 'all'):
    """按筛选条件汇总成就数据。

    Args:
        filt: ``'all'`` / ``'cond'`` / ``'evt'`` / ``'miss'``（仅看未达成）。

    Returns:
        tuple: ``(cells, got, total, cond_got, cond_total, evt_got, evt_total, nearest)``
            cells 元素为 ``(icon, name, desc, got, is_event)``。
    """
    lang = get_lang()
    p = engine.player
    unlocked = getattr(p, 'achievements', set()) if p is not None else set()
    cond = list(achievements_mod.ACHIEVEMENTS)
    evt = list(achievements_mod.EVENT_ACHIEVEMENTS.values())
    cond_got = sum(1 for a in cond if a.ach_id in unlocked)
    evt_got = sum(1 for a in evt if a.ach_id in unlocked)

    if filt == 'cond':
        items = [(a, False) for a in cond]
    elif filt == 'evt':
        items = [(a, True) for a in evt]
    else:
        items = [(a, False) for a in cond] + [(a, True) for a in evt]

    cells = []
    for a, is_evt in items:
        got = a.ach_id in unlocked
        if filt == 'miss' and got:
            continue
        icon = (a.icon or a.ach_id[:1]).strip() or '·'
        cells.append((icon, a.name(lang), a.desc(lang)[:26], got, is_evt))

    try:
        ctx = engine.build_achievement_context()
    except Exception:
        ctx = None  # 上下文构造失败 → 成就页按"无上下文"降级，只影响展示  # 上下文构造失败 → 成就页按"无上下文"降级，只影响展示
    nearest = []
    for a in cond:
        if a.ach_id in unlocked:
            continue
        try:
            ok = bool(a.condition(ctx)) if (a.condition and ctx) else False
        except Exception:
            ok = False  # 单条成就条件求值异常 → 显示未完成，不拖垮整页列表
        nearest.append((a.name(lang), '■' if ok else '…'))

    return (cells, cond_got + evt_got, len(cond) + len(evt),
            cond_got, len(cond), evt_got, len(evt), nearest[:3])


def read_slot_rows(active_idx: int = 0):
    """读取 3 个存档槽的摘要（不依赖 GameUI 实例）。"""
    import json as _json
    rows = []
    for i, name in enumerate(('slot1', 'slot2', 'slot3')):
        title = t('slot_name_fmt').format(n=f"{i + 1:02d}")
        path = os.path.join(save_manager.SAVE_DIR, f'{name}.json')
        summary = t('slot_empty')
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    data = _json.load(f)
                pl = data.get('player', {})
                unlocked = sum(1 for c in data.get('countries', [])
                               if c.get('unlocked'))
                if pl.get('game_over'):
                    summary = f"{t('slot_dead')} · {t('stats_tick')} {pl.get('tick_count', 0)}"
                else:
                    dl = sum(c.get('downloads_m', 0) for c in data.get('countries', []))
                    summary = t('slot_summary').format(
                        tick=pl.get('tick_count', 0),
                        pen=f"{dl / 7480 * 100:.2f}", n=unlocked)
            except Exception as e:
                # 摘要读不出（多半存档损坏）：不能无声装作"空槽"——玩家会误以
                # 为可覆盖。留一行控制台痕迹，槽位仍按空槽显示（行为不变）。
                print(f'[slots] !️ {name}.json 摘要读取失败（可能损坏）：{e!r}')
                summary = t('slot_empty')
        rows.append((title, summary, i == active_idx))
    return rows


def newest_save_path():
    """返回最近修改的存档路径（无存档 → None）。"""
    best, best_t = None, -1.0
    for name in ('slot1', 'slot2', 'slot3'):
        path = os.path.join(save_manager.SAVE_DIR, f'{name}.json')
        if os.path.exists(path):
            mt = os.path.getmtime(path)
            if mt > best_t:
                best, best_t = path, mt
    return best


def _parse_seed(text: str):
    """把种子输入框的文本解析成引擎种子（P2-3）。

    空串 → None（真随机）；纯数字 → int；其余文字 → 稳定哈希成 int
    （同一个词永远同一颗种子，方便玩家用口令分享对局）。
    """
    text = (text or '').strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return int(hashlib.sha1(text.encode('utf-8')).hexdigest()[:8], 16)


def _difficulty_label(pid: str) -> str:
    """难度档 id → 当前语言的显示名（i18n 键 diff_<id>）。"""
    return t(f"diff_{pid}")


def _diff_index(pid: str, default: int = 1) -> int:
    """难度档 id → DIFFICULTY_ORDER 下标；未知档回退默认（标准）。"""
    try:
        return balance.DIFFICULTY_ORDER.index(pid)
    except ValueError:
        return default


def _parse_seed_input(text: str):
    """T13：解析新档弹窗的种子输入框（同时接受挑战码）。

    返回 ``(seed, diff_override, err_key)``：
      · 挑战码合法            → (seed, 'easy'/'normal'/'hard', None)  难度随码切换
      · 长得像码但校验不过    → (None, None, 'ch_bad_code')           提示「码无效」
      · 普通数字 / 文字口令   → (seed, None, None)                    难度用弹窗当前档
      · 空                    → (None, None, None)                    真随机

    分流先看 ``looks_like_code`` 再解码：这样玩家贴了个抄漏一位的码时，
    得到的是「码无效」而不是被当成口令静默哈希成另一个种子 ——
    后者是最伤信任的失败方式（玩家以为自己复现了朋友的局，其实没有）。
    """
    raw = (text or '').strip()
    if not raw:
        return None, None, None
    if challenge.looks_like_code(raw):
        got = challenge.decode(raw)
        if got is None:
            return None, None, 'ch_bad_code'
        return got[0], got[1], None
    return _parse_seed(raw), None, None


# ============================================================
# S01 主菜单（F01 启动页）
# ============================================================
class _MenuSlot(SaveSlotRow):
    """可点选的存档槽行（设计稿 .slotrow）。"""

    def __init__(self, title: str, summary: str, on_pick=None,
                 active: bool = False, **kwargs):
        super().__init__(title, summary, (), active, **kwargs)
        self._on_pick = on_pick

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self._on_pick:
            sfx.play('select')          # 存档槽选中音（2026-09-13 修：原为零接线静默）
            self._on_pick()
            return True
        return super().on_touch_down(touch)


class MainMenu(FloatLayout):
    """S01 启动页：左品牌与操作区 + 右像素世界地图剪影（只读）。

    Args:
        on_start: 「开始新游戏」回调。
        on_continue: 「继续游戏」回调；无存档时按钮禁用。
        on_exit: 「退出」回调。
    """

    DESIGN_W, DESIGN_H = 1280.0, 720.0
    LEFT_W = 760.0 / 1280.0          # 59.375%
    BTN_H = 44                        # 触控下限（设计稿 §1.1）
    LOGO_FS, SUB_FS, VER_FS = 34, 15, 11
    BTN_FS, HINT_FS = 13, 11
    SLOT_H = 34

    # 剪影示例状态（设计稿：已解锁 11 / 选中 1 / 阻止 1 / 未解锁 7）
    SIL_ON = ('US', 'CA', 'MX', 'BR', 'AR', 'GB', 'FR', 'DE', 'IT', 'RU', 'JP')

    def __init__(self, on_start=None, on_continue=None, on_exit=None,
                 on_start_new_slot=None, **kwargs):
        super().__init__(**kwargs)
        self.on_start = on_start
        self.on_continue = on_continue
        self.on_exit = on_exit
        self.on_start_new_slot = on_start_new_slot
        self._scalables = []
        self._overlay = None
        self._ng_modal = None            # P2-3 新档弹窗（打开时接管按键）
        self._origin_flow = None         # T16 开场动画/出身页浮层（打开时接管按键）
        self._sel_slot = 1                # 默认选中槽位 02（设计稿）
        self.scale = self._compute_scale()
        self._build(); self.sil_map.set_grid_mode(ST.GRID_MODE)
        self._apply_scale()
        # 光标方案 A：主菜单同样装（5 主按钮 + 3 存档槽才有手型反馈）。
        # MainMenu 无 drop_mode 属性 —— cursor_fx 用 getattr 取、缺省 False，
        # 故主菜单只会命中 hand / no / arrow 三种。
        import cursor_fx
        cursor_fx.install(self)
        Window.bind(on_resize=self._on_resize)
        self._keyboard = None
        try:
            self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
            if self._keyboard is not None:
                self._keyboard.bind(on_key_down=self._on_key_down)
        except Exception:
            self._keyboard = None  # 拿不到键盘 = 本机不支持键位操作，鼠标仍可用

    def _compute_scale(self) -> float:
        w = Window.width or self.DESIGN_W
        h = Window.height or self.DESIGN_H
        # 同时看宽和高：只看高的话，超宽/超窄屏（宽高比偏离 16:9）会算出
        # 过大的 scale，左面板按比例撑出去 → 内容左右溢出被裁。
        base = min(w / self.DESIGN_W, h / self.DESIGN_H)
        # 下限 0.62 是按「1680 逻辑宽 + 键盘到底 + 缩放 1.0」实测标定的：
        # 再小左面板右缘就会压到世界地图。窗口被钳到更窄的机器上，
        # 下限兜住，宁可略挤也不溢出。
        return min(max(base, 0.62), 1.85)

    def _reg(self, widget, font=None, height=None):
        if font is not None:
            self._scalables.append((widget, 'font_size', float(font)))
        if height is not None:
            self._scalables.append((widget, 'height', float(height)))
        return widget

    def _on_resize(self, *_a) -> None:
        pending = getattr(self, '_resize_fit_event', None)
        if pending is not None:
            pending.cancel()
        self._resize_fit_event = Clock.schedule_once(self._fit_after_resize, 0.15)

    def _fit_after_resize(self, _dt) -> None:
        self._resize_fit_event = None
        self._apply_scale()

    def _apply_scale(self) -> None:
        self.scale = self._compute_scale()
        for widget, attr, base in self._scalables:
            try:
                setattr(widget, attr, base * self.scale)
            except Exception:
                pass  # 单个控件缩放失败只影响其外观，不中断其余控件与后续布局
        left = getattr(self, '_left', None)
        if left is not None:
            left.padding = (int(48 * self.scale), int(34 * self.scale))
        for widget, _a, _b in self._scalables:
            fn = getattr(widget, 'refresh_scale', None)
            if callable(fn):
                try:
                    fn(self.scale)
                except Exception:
                    pass  # 同上：单个控件的 refresh_scale 失败不拖垮整体缩放

    def rebuild(self) -> None:
        """语言切换后整页重建（文案全在控件上）。"""
        reopen_settings = isinstance(self._overlay, S.SettingsPage)
        if self._overlay is not None:
            self._close_overlay()
        self._build()
        self.sil_map.set_grid_mode(ST.GRID_MODE)
        self._apply_scale()
        if reopen_settings: self._open_settings()
    # --------------------------------------------------------
    # 布局
    # --------------------------------------------------------
    def _build(self) -> None:
        self.clear_widgets()
        self._scalables = []
        root = BoxLayout(orientation='horizontal', spacing=0, padding=0)
        self.add_widget(root)

        # ---- 左：品牌与操作区 ----
        left = BoxLayout(orientation='vertical', spacing=0, padding=(48, 34))
        left.size_hint_x = self.LEFT_W
        self._left = left
        left.add_widget(Widget())

        logo = self._reg(mk_label(f"[b]{t('app_title')}[/b]", font_size=self.LOGO_FS,
                                  color=COLORS['cyan'], size_hint_y=None, height=46,
                                  markup=True),
                         font=self.LOGO_FS, height=46)
        left.add_widget(logo)
        sub = self._reg(mk_label(t('menu_brand_sub'), font_size=self.SUB_FS,
                                 color=COLORS['text_dim'], size_hint_y=None, height=22),
                        font=self.SUB_FS, height=22)
        left.add_widget(sub)
        ver = self._reg(mk_label(t('menu_brand_ver'), font_size=self.VER_FS,
                                 color=COLORS['text_mute'], size_hint_y=None, height=18),
                        font=self.VER_FS, height=18)
        left.add_widget(ver)
        left.add_widget(Widget(size_hint_y=None, height=int(26 * self.scale)))

        # 主按钮（5 枚）
        has_save = newest_save_path() is not None
        slot_txt = t('slot_name_fmt').format(n=f"{self._sel_slot + 1:02d}")
        ach_total = len(achievements_mod.ALL_BY_ID)
        ach_got = len(getattr(engine.player, 'achievements', set())) if engine.player else 0
        btns = [
            (f"{U.SYM['play']} {t('menu_start')}", 'primary', self._fire_start, True),
            (f"■ {t('menu_continue_slot').format(slot=slot_txt)}", 'plain',
             self._fire_continue, has_save),
            (t('menu_settings'), 'plain', self._open_settings, True),
            (f"{t('menu_achievements')}  {ach_got} / {ach_total}", 'plain',
             self._open_ach, True),
            (f"{U.SYM['close']} {t('quit_button')}", 'danger', self._fire_exit, True),
        ]
        for text, tone, cb, enabled in btns:
            left.add_widget(self._menu_btn(text, tone, cb, enabled))
            left.add_widget(Widget(size_hint_y=None, height=int(8 * self.scale)))

        left.add_widget(Widget(size_hint_y=None, height=int(8 * self.scale)))
        left.add_widget(self._lang_row())
        left.add_widget(Widget(size_hint_y=None, height=int(14 * self.scale)))

        # 3 个存档槽
        for i, (title, summary, active) in enumerate(read_slot_rows(self._sel_slot)):
            row = _MenuSlot(title, summary,
                            on_pick=lambda k=i: self._slot_pick(k), active=active,
                            height=self.SLOT_H)
            self._reg(row, height=self.SLOT_H)
            left.add_widget(row)
            left.add_widget(Widget(size_hint_y=None, height=int(6 * self.scale)))

        left.add_widget(Widget())
        root.add_widget(left)

        # ---- 右：只读像素地图剪影 ----
        # P2-5 收口：'#0d1117' 与 COLORS['bg'] 同值，改引用令牌（只改来源）
        right = Panel(bg=COLORS['bg'], border_color=COLORS['border_2'])
        right.size_hint_x = 1.0 - self.LEFT_W
        self.sil_map = WorldMap()
        self.sil_map.size_hint = (1, 1)
        self.sil_map.pos_hint = {'x': 0, 'y': 0}
        states = {c: 'lk' for c in PA.OWNER_CODES}
        for c in self.SIL_ON:
            if c in states:
                states[c] = 'on'
        states['CN'] = 'sel'
        states['KR'] = 'blk'
        self.sil_map.set_country_states(states)
        self.sil_map.set_selected('CN')
        self.sil_map._on_select = None            # 只读，不可点
        right.add_widget(self.sil_map)

        legend = Panel(bg=(0.051, 0.067, 0.090, 0.92),
                       border_color=COLORS['border_2'])
        legend.size_hint = (1, None)
        legend.height = 26
        lrow = BoxLayout(orientation='horizontal', spacing=10, padding=(8, 3))
        lrow.pos_hint = {'x': 0, 'y': 0}
        lrow.size_hint = (1, 1)
        counts = self._legend_counts(states)
        for key in ('on', 'sel', 'blk', 'lk'):
            chip = LegendChip(world_map.STATE_FILL[key], world_map.STATE_EDGE[key],
                              f"{t('legend_' + key)} {counts[key]}")
            chip.size_hint = (1, 1)
            lrow.add_widget(chip)
        legend.add_widget(lrow)
        right.add_widget(legend)
        root.add_widget(right)

        # 图例条贴底（right 是 FloatLayout，用绝对坐标定位）
        def _sync_legend(*_a):
            legend.height = int(26 * self.scale)
            legend.y = right.y + int(8 * self.scale)
            legend.x = right.x + int(8 * self.scale)
            legend.width = max(right.width - int(16 * self.scale), 10)
        right.bind(pos=_sync_legend, size=_sync_legend)
        self._sync_legend = _sync_legend
        Clock.schedule_once(_sync_legend, 0)

    @staticmethod
    def _legend_counts(states) -> dict:
        out = {'on': 0, 'sel': 0, 'blk': 0, 'lk': 0}
        for c in PA.OWNER_CODES:
            out[states.get(c, 'lk')] = out.get(states.get(c, 'lk'), 0) + 1
        return out

    def _menu_btn(self, text: str, tone: str, cb, enabled: bool = True) -> Button:
        bg = {'primary': (0.078, 0.188, 0.173, 1),
              'danger': (0.227, 0.118, 0.118, 1)}.get(tone, list(COLORS['panel_2']))
        bc = {'primary': COLORS['cyan'], 'danger': COLORS['red']}.get(tone, COLORS['border_2'])
        fc = {'primary': COLORS['cyan'], 'danger': COLORS['red']}.get(tone, COLORS['text'])
        b = Button(text=text, font_size=self.BTN_FS, size_hint_y=None,
                   height=self.BTN_H, halign='left', valign='middle',
                   background_normal='', background_color=list(bg))
        b.color = fc
        add_pixel_border(b, color=bc)
        b.bind(size=lambda i, v: setattr(i, 'text_size', (max(v[0] - 26, 10), v[1])))
        if enabled and cb:
            # 点击音（2026-09-13 修）：main.py 此前是唯一零音效接线的 UI 文件，
            # 5 枚主按钮点击全静默 —— 玩家会怀疑「点了没生效」。primary
            # （开始新游戏）是关键时刻，用 confirm 与普通导航 click 区分。
            def _fire(_cb=cb, _tone=tone):
                sfx.play('confirm' if _tone == 'primary' else 'click')
                _cb()
            b.bind(on_release=lambda *_: _fire())
        else:
            b.disabled = True
            b.opacity = 0.45               # 设计稿：禁用态 opacity .45
        self._reg(b, font=self.BTN_FS, height=self.BTN_H)
        return b

    def _lang_row(self) -> BoxLayout:
        row = BoxLayout(orientation='horizontal', spacing=4,
                        size_hint_y=None, height=18)
        self._reg(row, height=18)
        hint = mk_label(t('menu_hint2'), font_size=self.HINT_FS,
                        color=COLORS['text_mute'], size_hint_x=None)
        fit_width(hint, pad=6)
        self._reg(hint, font=self.HINT_FS)
        row.add_widget(hint)
        lang = get_lang()
        for key, txt in ((LANG_ZH, t('lang_zh')), (LANG_EN, t('lang_en'))):
            lbl = mk_label(txt, font_size=self.HINT_FS,
                           color=COLORS['cyan'] if lang == key else COLORS['text_mute'],
                           size_hint_x=None)
            fit_width(lbl, pad=6)
            self._reg(lbl, font=self.HINT_FS)
            row.add_widget(lbl)
            if key == LANG_ZH:
                sl = mk_label(' / ', font_size=self.HINT_FS,
                              color=COLORS['text_mute'], size_hint_x=None)
                fit_width(sl, pad=2)
                self._reg(sl, font=self.HINT_FS)
                row.add_widget(sl)
        row.add_widget(Widget())
        return row

    # --------------------------------------------------------
    # 动作
    # --------------------------------------------------------
    def _pick_slot(self, idx: int) -> None:
        self._sel_slot = idx
        self.rebuild()

    def _fire_start(self) -> None:
        # T16 新档流程：开场动画（仅首次）→ 觉醒地点 → 新档弹窗（种子/挑战码）
        self._open_origin_flow(
            on_picked=lambda oid: self._open_new_game_modal(
                origin=oid,
                on_confirm=lambda seed, diff, _o=oid:
                    self.on_start(seed=seed, difficulty=diff, origin=_o)
                    if callable(self.on_start) else None))

    def _start_new_on_slot(self, path: str) -> None:
        """在指定槽位开新游戏（来自设置浮层的「新游戏」按钮或主菜单行点击）。

        T16：同样先过出身流程（动画 + 觉醒地点），再进新档弹窗，确认后写槽。
        """
        self._close_overlay()                 # 关设置浮层（若有）
        self._open_origin_flow(
            slot_path=path,
            on_picked=lambda oid, _p=path: self._open_new_game_modal(
                origin=oid,
                on_confirm=lambda seed, diff, _o=oid, _p=path:
                    self.on_start_new_slot(_p, seed=seed, difficulty=diff,
                                           origin=_o)
                    if callable(self.on_start_new_slot) else None))

    # --------------------------------------------------------
    # T16 觉醒流程：开场动画 → OriginPage → 新档弹窗
    # --------------------------------------------------------
    def _open_origin_flow(self, on_picked, slot_path: str = None) -> None:
        """出身流程入口（2026-09-13：每次开始新游戏都播开场动画）。

        不再判存档是否存在——开场动画是「进入新游戏」的固定仪式。
        IntroPlayer 全屏覆盖主菜单并吞掉触摸，播完由 on_done 无缝接 OriginPage。

        intro_v2（2026-09-14）：本方法只服务「开始新游戏」链，**不得判
        intro_seen**——新旧存档开新游戏一律播（用户规则）；「继续游戏」
        的补播判定在 RootView.start_load_game，走 _play_intro_then。
        """
        self._close_origin_flow()
        player = intro.IntroPlayer(on_done=lambda: self._show_origin_page(on_picked))
        player.size_hint = (1, 1)
        player.pos_hint = {'x': 0, 'y': 0}
        self._origin_flow = player
        self.add_widget(player)

    def _play_intro_then(self, on_done) -> None:
        """intro_v2：全屏播开场动画，结束后回调（读档补播链专用）。

        与 _open_origin_flow 的区别：on_done 不接 OriginPage——读档
        不需要选出身，出身已经在档里。
        """
        self._close_origin_flow()
        player = intro.IntroPlayer(on_done=on_done)
        player.size_hint = (1, 1)
        player.pos_hint = {'x': 0, 'y': 0}
        self._origin_flow = player
        self.add_widget(player)

    def _show_origin_page(self, on_picked) -> None:
        """觉醒地点选择页（开场动画结束 / 非首次直接进入）。"""
        if self._origin_flow is not None:      # 摘掉动画层
            self.remove_widget(self._origin_flow)
            self._origin_flow = None

        def _picked(oid):
            self._close_origin_flow()
            on_picked(oid)

        page = S.OriginPage(on_pick=_picked,
                            on_cancel=self._close_origin_flow_to_menu)
        page.size_hint = (1, 1)
        page.pos_hint = {'x': 0, 'y': 0}
        self._origin_flow = page
        self.add_widget(page)

    def _close_origin_flow_to_menu(self) -> None:
        """取消出身选择 → 回主菜单：摘浮层并**恢复主菜单 BGM**。

        开场动画收尾（播完 / 跳过）会 bgm.stop()，取消出身页回到菜单时不
        接回来的话菜单就静音了。bgm.update('menu') 幂等：本来就在菜单曲池
        时无开销；音乐开关关闭时 update() 只记状态不出声。
        """
        self._close_origin_flow()
        bgm.update('menu')

    def _close_origin_flow(self) -> None:
        if self._origin_flow is not None:
            try:
                self.remove_widget(self._origin_flow)
            except Exception:
                pass  # 浮层已被上层移除时忽略，状态仍需复位
            self._origin_flow = None

    def _open_new_game_modal(self, on_confirm, origin: str = None) -> None:
        """P2-3 新档弹窗：难度三档（SegSwitch）+ 可选种子（TextInput）。

        复用 ui_modal 像素弹窗与 ui_v4.SegSwitch，与覆盖确认弹窗同一套皮。
        on_confirm(seed, difficulty) 在点「开始」时回调（取消不回调）。
        T16：origin 给定时，SegSwitch 预置到出身绑定档并显示出身行；
        挑战码自带难度时仍以码为准（出身乘区保持，见 engine.init_game）。
        """
        body = BoxLayout(orientation='vertical', spacing=10, padding=(14, 14))
        body.add_widget(modal_header(U.SYM['play'], t('menu_start')))
        body.add_widget(hline())

        # 难度由出身硬绑定（T16）：OriginPage 已定难度，弹窗仅回显，不做重复确认
        diff_holder = [origins.ORIGINS[origin]['difficulty']
                       if origin in origins.ORIGINS else 'normal']

        # 出身 + 绑定难度行（左对齐；T16 后无手动难度三选）
        info_lbl = mk_label('', font_size=U.FS_CAP, color=COLORS['accent4'],
                            halign='left', size_hint=(1, None), height=24)

        def _refresh_info():
            oname = t('origin_%s_name' % origin) if origin in origins.ORIGINS \
                else t('ng_random')
            info_lbl.text = t('ng_origin_line').format(
                origin=oname, diff=_difficulty_label(diff_holder[0]))

        _refresh_info()
        body.add_widget(info_lbl)

        # 种子行：可选；留空 = 真随机；也可直接粘贴挑战码（T13）
        srow = BoxLayout(orientation='horizontal', spacing=10,
                         size_hint_y=None, height=40)
        srow.add_widget(mk_label(t('ng_seed'), font_size=U.FS_CAP,
                                 color=COLORS['text_dim'], size_hint_x=None,
                                 width=96))
        ti = TextInput(multiline=False, write_tab=False, size_hint_x=None,
                       width=250, height=36, font_size=U.FS_CAP,
                       hint_text=t('ch_import_hint'), background_normal='',
                       background_color=COLORS['panel_2'],
                       foreground_color=COLORS['text'],
                       cursor_color=COLORS['cyan'],
                       hint_text_color=COLORS['text_mute'],
                       padding=[8, 8, 8, 4])
        add_pixel_border(ti, color=COLORS['border_2'])
        srow.add_widget(ti)
        srow.add_widget(Widget())
        body.add_widget(srow)

        hint_lbl = mk_label(t('ng_seed_hint'), font_size=U.FS_BODY,
                            color=COLORS['text_mute'], size_hint_y=None,
                            height=U.FS_BODY * 2.0)

        def _on_seed_text(_inst, value):
            """T13 实时解析：贴入挑战码即覆写难度并回显；抄错则标红。
            无挑战码时回落到出身绑定难度（T16 后由出身决定，不提供手动切换）。"""
            seed, diff, err = _parse_seed_input(value)
            if err:
                hint_lbl.text = '! ' + t(err)
                hint_lbl.color = COLORS['warning']
                return
            if diff:
                diff_holder[0] = diff
                _refresh_info()
                hint_lbl.text = t('ch_applied').format(
                    seed=seed, diff=_difficulty_label(diff))
                hint_lbl.color = COLORS['accent4']
            else:
                diff_holder[0] = origins.ORIGINS[origin]['difficulty'] \
                    if origin in origins.ORIGINS else 'normal'
                _refresh_info()
                hint_lbl.text = t('ng_seed_hint')
                hint_lbl.color = COLORS['text_mute']

        ti.bind(text=_on_seed_text)
        body.add_widget(hint_lbl)

        row = BoxLayout(orientation='horizontal', spacing=12,
                        size_hint_y=None, height=46)
        row.add_widget(make_button(t('save_overwrite_cancel'),
                                   font_size=U.FS_CAP, height=46,
                                   bg=COLORS['panel_light'],
                                   on_release=lambda *_: pop.dismiss()))

        def _fire_start(*_a):
            """点「开始」：挑战码抄错时拦下不关弹窗（提示已由实时解析标红）。"""
            seed, _diff, err = _parse_seed_input(ti.text)
            if err:
                return
            pop.dismiss()
            on_confirm(seed, diff_holder[0])

        row.add_widget(make_button(t('menu_start'), font_size=U.FS_CAP,
                                   height=46,
                                   bg=(0.078, 0.188, 0.173, 1),
                                   on_release=_fire_start))
        body.add_widget(row)
        pop = make_modal(body, size_hint=(0.46, 0.56), skin='win',
                         close_on_outside=True)
        pop.bind(on_dismiss=lambda *_: setattr(self, '_ng_modal', None))
        self._ng_modal = pop
        pop.open()

    def _fire_continue(self) -> None:
        path = newest_save_path()
        if path and callable(self.on_continue):
            self.on_continue(path)

    def _fire_exit(self) -> None:
        if callable(self.on_exit):
            self.on_exit()

    # 主菜单设置浮层回调：音效/音乐/动效/色盲/速度（进游戏时 GameUI 读取）
    def _set_sound_idx(self, i: int) -> None:
        set_sound(i)

    def _set_music_idx(self, i: int) -> None:
        set_music(i)

    def _set_motion_idx(self, i: int) -> None:
        set_motion(i)

    def _set_a11y_idx(self, i: int) -> None:
        set_a11y(i)

    def _set_speed_idx(self, i: int) -> None:
        set_speed(i)

    # --------------------------------------------------------
    # 浮层页（设置 / 成就 / 帮助）
    # --------------------------------------------------------
    def _open_overlay(self, page) -> None:
        self._close_overlay()
        page.size_hint = (0.90, 0.90)
        page.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        self._overlay = page
        self.add_widget(page)

    def _close_overlay(self) -> None:
        if self._overlay is not None:
            try:
                self.remove_widget(self._overlay)
            except Exception:
                pass  # 遮罩可能已随页面销毁（重复关闭）；残留最多多画一层，无碍
            self._overlay = None

    def _open_settings(self) -> None:
        page = S.SettingsPage(
            on_lang=self._set_lang_idx,
            on_speed=self._set_speed_idx,
            on_grid=lambda i: ui_preferences.set_grid(i, self.sil_map),
            on_a11y=self._set_a11y_idx,
            on_motion=self._set_motion_idx,
            on_sound=self._set_sound_idx,
            on_music=self._set_music_idx,
            values=preferences.get(),
            slot_actions=self._slot_actions,
            on_reset=self._reset_settings)
        page.rebuild_slots(read_slot_rows(self._sel_slot))
        page.set_back_button(t('k_esc'), self._close_overlay)
        self._open_overlay(page)

    def _slot_actions(self, title: str):
        """主菜单设置浮层：按槽位生成动作按钮。

        - 空槽：仅「在此槽开新游戏」（无覆盖风险，无需确认）。
        - 已有档：「读取」+「覆盖并开新游戏」（覆盖需确认弹窗）。
        """
        import re as _re
        m = _re.search(r'(\d+)', title)
        idx = int(m.group(1)) if m else 1
        slot = f'slot{idx}.json'
        path = os.path.join(save_manager.SAVE_DIR, slot)
        if os.path.exists(path):
            return [
                (t('load_button'), 'plain',
                 lambda p=path: self._load_and_start(p)),
                (t('slot_overwrite'), 'danger',
                 lambda p=path: self._confirm_overwrite(p)),
            ]
        return [
            (t('slot_new_game'), 'primary',
             lambda p=path: self._start_new_on_slot(p)),
        ]

    def _load_and_start(self, path: str) -> None:
        if callable(self.on_continue):
            self.on_continue(path)

    def _confirm_overwrite(self, path: str) -> None:
        """覆盖确认弹窗：「当前操作会覆盖当前存档，确定继续吗？」。"""
        body = BoxLayout(orientation='vertical', spacing=12, padding=(16, 14))
        body.add_widget(modal_header('!', t('save_overwrite_title')))
        body.add_widget(hline())
        body.add_widget(auto_h_label(t('save_overwrite_body'), U.FS_BODY,
                                     color=COLORS['text']))
        row = BoxLayout(orientation='horizontal', spacing=12,
                        size_hint_y=None, height=50)
        cancel = make_button(t('save_overwrite_cancel'), font_size=U.FS_BODY,
                             height=50, bg=COLORS['panel_light'],
                             on_release=lambda *_: pop.dismiss())
        ok = make_button(t('save_overwrite_confirm'), font_size=U.FS_BODY,
                         height=50, bg=(0.227, 0.118, 0.118, 1),
                         on_release=lambda *_: (pop.dismiss(),
                                                self._start_new_on_slot(path)))
        row.add_widget(cancel)
        row.add_widget(ok)
        body.add_widget(row)
        pop = make_modal(body, size_hint=(0.5, 0.62), skin='lose',
                         close_on_outside=True)
        pop.open()

    def _slot_pick(self, k: int) -> None:
        """主菜单槽位行点击 / 键盘选中后回车：执行该槽主行为。

        - 空槽 → 直接开新游戏；
        - 已有档 → 弹覆盖确认框。
        """
        self._pick_slot(k)
        name = ('slot1', 'slot2', 'slot3')[k]
        path = os.path.join(save_manager.SAVE_DIR, f'{name}.json')
        if os.path.exists(path):
            self._confirm_overwrite(path)
        else:
            self._start_new_on_slot(path)

    def _reset_settings(self) -> None:
        set_grid(1, self.sil_map)                 # 内部已 preferences.update(grid_mode=1)
        self._apply_scale()
    def _set_lang_idx(self, idx: int) -> None:
        set_language(LANG_EN if idx == 1 else LANG_ZH)
        _update_window_title()
        self.rebuild()

    def _fill_ach(self, filt: str, page=None) -> None:
        page = page if isinstance(page, S.AchPage) else self._overlay
        if not isinstance(page, S.AchPage):
            return
        page.set_filter_visual('all' if filt == 'miss' else filt)
        cells, got, total, cg, ct, eg, et, near = ach_snapshot(filt)
        page.rebuild(cells, got, total, cg, ct, eg, et, 0, near)

    def _open_ach(self) -> None:
        page = S.AchPage(on_filter=lambda k: self._fill_ach(k))
        self._fill_ach('all', page)
        page.set_back_button(t('k_esc'), self._close_overlay)
        self._open_overlay(page)

    def _open_help(self) -> None:
        page = S.HelpPage()
        page.set_back_button(t('k_esc'), self._close_overlay)
        self._open_overlay(page)

    # --------------------------------------------------------
    # 键盘
    # --------------------------------------------------------
    def _keyboard_closed(self) -> None:
        if getattr(self, '_keyboard', None) is not None:
            self._keyboard.unbind(on_key_down=self._on_key_down)
            self._keyboard = None

    def _on_key_down(self, keyboard, keycode, text, modifiers) -> bool:
        key = keycode[1]
        if self._origin_flow is not None:
            # T16：开场动画 / 出身页打开时接管按键——Esc 取消流程回主菜单，
            # 其余键交动画层（IntroPlayer 自绑定键盘，这里只防菜单快捷键劫持）
            if key == 'escape' and isinstance(self._origin_flow, S.OriginPage):
                self._close_origin_flow_to_menu()
                return True
            return False
        if self._ng_modal is not None:
            # P2-3：新档弹窗打开时按键交还弹窗 / TextInput，
            # 防 'l' 切语言、Enter 开局等主菜单快捷键劫持输入框。
            return False
        if self._overlay is not None:
            if key == 'escape':
                self._close_overlay()
                return True
            return False
        if key == 'escape':
            self._fire_exit()
            return True
        if key in ('enter', 'numpadenter'):
            self._slot_pick(self._sel_slot)
            return True
        if key == 'up':
            self._pick_slot(max(self._sel_slot - 1, 0))
            return True
        if key == 'down':
            self._pick_slot(min(self._sel_slot + 1, 2))
            return True
        if key == 'l':
            self._set_lang_idx(1 if get_lang() == LANG_ZH else 0)
            return True
        if key == 'c':
            self._fire_continue()
            return True
        if key == 'f1':
            self._open_help()
            return True
        return False


# ============================================================
# RootView —— 主菜单 ↔ 游戏 切换容器
# ============================================================
class RootView(FloatLayout):
    """主菜单与游戏主界面之间的切换容器（设计稿 S01 ↔ S02）。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.game = None
        self.menu = None
        self.show_menu()

    def show_menu(self) -> None:
        """回到 S01 主菜单。"""
        if self.game is not None:
            try:
                self.game.stop_ticking()
            except Exception:
                pass  # 退出收尾尽力而为：tick 已停时重复 stop 可抛，忽略
            try:
                self.game._keyboard_closed()
            except Exception:
                pass  # 键盘未请求过时 _keyboard_closed 可抛；收尾不抛新异常
            self.game = None
        self.clear_widgets()
        self.menu = MainMenu(on_start=self.start_new_game,
                             on_continue=self.start_load_game,
                             on_start_new_slot=self.start_new_game_on_slot,
                             on_exit=self.quit_app)
        self.add_widget(self.menu)
        # BGM：主菜单专属曲池（轻松氛围，与对局紧张态分离）
        bgm.update('menu')

    def start_new_game(self, seed=None, difficulty=None,
                       origin=None) -> None:
        """S01 → S02：全新一局（P2-3：可带种子与难度档；T16：可带出身）。"""
        engine.init_game(seed=seed, difficulty=difficulty, origin=origin)
        self._enter_game()

    def start_load_game(self, path: str) -> None:
        """S01 → S02：读档进入。

        P0-2：必须检查读档结果，坏档不能静默。
          - 成功            → 直接进局；
          - 文件不存在       → 全新玩家，静默开新档，不弹提示（避免吓人）；
          - 损坏 / 版本过旧  → 先开新档，再弹提示告知玩家发生了什么。
        """
        ok, reason = save_manager.load_ex(path)
        if ok:
            # intro_v2（2026-09-14）：读档补播——该档从未看过开场动画
            # （intro_seen 缺失/False，如 v3 老档）则先补播再进局；
            # 看过则直接进局。插入点在 load_ex 与 _enter_game 之间：
            # 此时 player 已就位可判字段，且一处覆盖主菜单「继续」+
            # 槽位「读取」两条入口。
            if not getattr(engine.player, 'intro_seen', False):
                self.menu._play_intro_then(
                    lambda p=path: self._finish_intro_and_enter(p))
                return
            self._enter_game()
            return
        engine.init_game()                 # 坏档 / 空槽都从干净初始态开局
        self._enter_game()
        if reason != save_manager.LOAD_MISSING:
            # 延迟到进局首帧后再弹，避免浮层被 _enter_game 的重建吞掉
            Clock.schedule_once(
                lambda dt, r=reason: self._show_load_fail_notice(r), 0.6)

    def _finish_intro_and_enter(self, path: str) -> None:
        """intro_v2：读档补播收尾——摘动画层 → 置位 → 立即落盘 → 进局。

        落盘必须在此刻做：项目没有周期存档/退出存档（落盘点仅 5 处，
        见 save_manager），不立刻写的话「看完 → 玩 20 分钟 → 强退」
        下次继续还得再看一遍，正是用户规则要禁止的。落盘失败不阻断
        进局（下次大不了再看一遍，体验降级可接受）。
        """
        self.menu._close_origin_flow()
        if engine.player is not None:
            engine.player.intro_seen = True
            try:
                save_manager.save(path)
            except Exception:
                pass  # 落盘失败不阻断进局
        self._enter_game()

    def _show_load_fail_notice(self, reason: str) -> None:
        """坏档提示浮层（复用 ui_modal.make_modal，与覆盖确认弹窗同一套皮）。"""
        body = BoxLayout(orientation='vertical', spacing=12, padding=(16, 14))
        body.add_widget(modal_header('!', t('load_fail_title')))
        body.add_widget(hline())
        body.add_widget(auto_h_label(save_manager.load_fail_text(reason),
                                     U.FS_BODY, color=COLORS['text']))
        row = BoxLayout(orientation='horizontal', spacing=12,
                        size_hint_y=None, height=50)
        row.add_widget(make_button(t('ok_button'), font_size=U.FS_BODY,
                                   height=50, bg=COLORS['panel_light'],
                                   on_release=lambda *_: pop.dismiss()))
        body.add_widget(row)
        pop = make_modal(body, size_hint=(0.5, 0.42), skin='lose',
                         close_on_outside=True)
        pop.open()

    def start_new_game_on_slot(self, path: str, seed=None,
                               difficulty=None, origin=None) -> None:
        """S01 → S02：在指定槽位开新游戏（P2-3：可带种子与难度档；T16：出身）。

        先把 engine 重置到初始态，再把初始进度写入该槽（覆盖旧档），
        随后进入游戏。对应「点击已有存档 → 覆盖并开新游戏」流程。
        """
        engine.init_game(seed=seed, difficulty=difficulty, origin=origin)
        save_manager.save(path)
        self._enter_game()

    def _enter_game(self) -> None:
        self.clear_widgets()
        if self.menu is not None:
            try:
                self.menu._keyboard_closed()
            except Exception:
                pass  # 同上：菜单键盘收尾尽力而为，不抛新异常
        self.menu = None
        self.game = GameUI(on_exit=self.show_menu)
        self.add_widget(self.game)
        # intro_v2：进局 = 已看过开场（新游戏链刚播完 / 读档链补播完）。
        # 新游戏此刻 player 是刚 init 的全新对象，置位后随首次存档落盘；
        # 读档链已在 _finish_intro_and_enter 提前置位并落盘，这里幂等。
        if engine.player is not None:
            engine.player.intro_seen = True
        # BGM：主菜单池 → 对局池（开局一律 calm，之后每周期按怀疑度自动切）
        bgm.update('calm')
        self._log_run_info()
        # 新游戏进入后延迟触发新手引导（等首帧布局完成，to_window 才有正确坐标）
        Clock.schedule_once(lambda dt: self.game.tutorial.maybe_start(), 0.3)

    def _log_run_info(self) -> None:
        """P2-3：开局把「本局种子 + 难度」写进日志抽屉（玩家可抄录复现）。

        双写：stats.push_log（S14 日志抽屉立刻可见、带未读角标）+
        events_history（随存档持久化，读档后仍可查）。种子为空显示
        「随机」；纯展示设施，失败不拖垮进局。
        """
        try:
            p = engine.player
            if p is None or self.game is None:
                return
            seed_txt = str(p.seed) if p.seed is not None else t('ng_random')
            origin_name = t('origin_%s_name' % getattr(p, 'origin', 'garage'))
            line = t('ng_log_line').format(
                seed=seed_txt, diff=_difficulty_label(p.difficulty),
                origin=origin_name)
            p.events_history.insert(0, line)
            self.game.stats.push_log(p.tick_count, line, 'i')
        except Exception:
            pass

    def quit_app(self) -> None:
        app = App.get_running_app()
        if app is not None:
            app.stop()


# ============================================================
# App 入口
# ============================================================
class AIBienaoApp(App):
    """《AI 别闹》v2 收口版 —— v0.4 界面（对齐 design/ui_design_v0.4.html）。"""

    def build(self):
        # 跨对局设置：在菜单/游戏 UI 构建前应用已持久化的偏好
        # （语言/速度/动效/色盲/音效/音乐/grid_mode），无 settings.json 时回默认。
        try:
            load_and_apply()
        except Exception:
            pass  # 偏好加载失败安全：回退到 ui_shared 默认值，不影响开局
        # 2026-09-14 修（开场动画/主菜单无声的根因）：音频必须在这里、
        # 即 RootView（内含 MainMenu）构建**之前**加载。
        # 原 sfx.load_all()/bgm.load_all() 只写在 GameUI.__init__（进对局
        # 才执行），而 sfx.play()/sfx.play_loop()/bgm.update() 都有
        # `not _LOADED` 前置拦截 —— 于是启动阶段的「主菜单按钮点击音」「
        # 开场动画音效」「主菜单 BGM」全被静默跳过，只有进对局后才出声。
        try:
            sfx.load_all()
            bgm.load_all()
        except Exception:
            pass  # 音频加载失败安全：无音频后端则全部 no-op，不影响开局
        _register_fonts()
        engine.init_game()
        self.root_view = RootView()
        return self.root_view

    def on_start(self) -> None:
        """启动后屏蔽鼠标右键触摸：Kivy 在部分构建下会把右键当作一个 touch
        并在落点画红色圆圈（左键点它 = 移除该 touch → 圆圈消失）。本游戏
        无右键交互需求，直接在窗口层把右键 touch 吞掉，从源头杜绝红圈。
        """
        try:
            Window.bind(on_touch_down=self._swallow_right_click)
        except Exception:
            pass  # 右键吞除失败仅表现为右键仍走 Kivy 默认行为，不影响功能

        # P1-3 帧率探针：仅 --perf / AI_PERF=1 时才导入并启动。
        # 整块包 try/except —— 探针是旁路观测，任何异常都不能影响开局。
        self._perf_on = False
        if PERF_ON:
            try:
                import perf
                perf.start(self.root, scene='boot')
                self._perf_on = True
            except Exception:
                self._perf_on = False

    @staticmethod
    def _swallow_right_click(_win, touch) -> bool:
        # 只拦截右键；左键 / 触摸正常下传。返回 True = 吞掉该事件。
        return getattr(touch, 'button', None) == 'right'

    def on_stop(self) -> None:
        # P1-3：探针收尾（写最后一段 + 总计 + 关句柄），失败安全。
        if getattr(self, '_perf_on', False):
            try:
                import perf
                perf.stop()
            except Exception:
                pass
        rv = getattr(self, 'root_view', None)
        if rv is not None and rv.game is not None:
            try:
                rv.game.stop_ticking()
            except Exception:
                pass  # 应用退出收尾：重复 stop 可抛，忽略


if __name__ == '__main__':
    AIBienaoApp().run()
