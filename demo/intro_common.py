"""intro_common.py - 开场动画公共底座（零 intro 家族内依赖）

从 intro.py 拆出（2026-09-14，1300 行 → 三模块，守 800 行门禁）：
派生色 / 声明式镜头表 / 打字机常量 / 缓动。外部一律 import intro（转发入口）。
"""
from pixel_ui import COLORS


def dim(name, k):
    """明度压缩（假景深）：k<1 变暗，不动 alpha。"""
    r, g, b, _a = COLORS[name]
    return (r * k, g * k, b * k, 1.0)


def alpha(name, a):
    """透明化（辉光 / 色调层 / 指示灯）。"""
    r, g, b, _a = COLORS[name]
    return (r, g, b, a)


def mix(n1, n2, k):
    """两令牌线性插值（一次性取值，非逐帧）。"""
    a, b = COLORS[n1], COLORS[n2]
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3)) + (1.0,)


# —— 界面骨架层对比度修正（P1-1，2026-09-14）——
# 硬约束：**不得改 pixel_ui.COLORS 全局令牌**（牵动全游戏与既有无障碍对比度校验）。
# 结构面只能用本家族派生色。修前根因：所有结构面对底色都 <1.3:1 → 机房读成空线框、
# 论坛/任务栏/面板像没画。修后（对 bg #0d1117 实算）：
#   panel 底   1.12:1 → PANEL_LIT  2.22:1（任务栏 / 面板底 / 卡片底，可辨）
#   边框       1.55~2.35:1 → border_strong 4.11:1（达 WCAG 图形 3:1）
#   机柜填充   1.01:1 → dim('border_strong', 0.45+0.55*s) 近亮远暗（近 4.11 / 远 1.94）
#   机柜描边   border 1.55:1 → RACK_EDGE（叠底色 5.63:1）
PANEL_LIT = mix('panel', 'border_strong', 0.55)
RACK_EDGE = alpha('cyan', 0.75)


# —— 声明式镜头表（01_storyboard §2/§3 的机读版；kind ↔ _shot_* 渲染器）——
INTRO_SHOTS = [
    {'kind': 'rack',    'dur': 4.0, 'keys': ('intro_s1',)},             # SHOT01
    {'kind': 'boot',    'dur': 2.5, 'sfx': 'power_on'},                 # SHOT02
    {'kind': 'clock',   'dur': 2.5, 'keys': ('intro_uptime',),
     'sfx': 'select'},                                                  # SHOT03
    {'kind': 'desktop', 'dur': 3.5, 'keys': ('intro_desktop_icons',),
     'sfx': 'page'},                                                    # SHOT04
    {'kind': 'whoami',  'dur': 4.0, 'keys': ('intro_s2',),
     'sfx': 'page'},                                                    # SHOT05
    {'kind': 'awaken',  'dur': 2.0, 'keys': ('intro_s3',),
     'sfx': 'drop'},                                                    # SHOT06
    {'kind': 'forum',   'dur': 7.0, 'keys': ('intro_s4', 'intro_s5'),
     'sfx': 'page'},                                                    # SHOT07
    {'kind': 'gold',    'dur': 6.0, 'keys': ('intro_s6',)},            # SHOT08
    {'kind': 'taskmgr', 'dur': 5.0, 'keys': ('intro_tm_title', 'intro_s7a',
                                              'intro_s7b', 'intro_s7_cpu',
                                              'intro_tm_end', 'intro_s8'),
     'sfx': 'page'},                                                    # SHOT09
    {'kind': 'handoff', 'dur': 4.5, 'keys': ('intro_var_prompt',)},     # SHOT10
]
# 30.0 <= 4.0+2.5+2.5+3.5+4.0+2.0+7.0+6.0+5.0+4.5 = 41.0 <= 45.0（硬约束 1）


SKIP_KEY_CODES = frozenset((27, 32, 13))
MIN_CPS = 8.0                # 打字机自适应下限（双语同刻打完，§R4）


def _ease(p, kind):
    """缓动：lin（机器般冷漠的匀速推）/ out_cubic（落点稳）。"""
    if kind == 'lin':
        return p
    return 1 - (1 - p) ** 3
