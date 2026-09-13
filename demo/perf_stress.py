"""
perf_stress.py - P1-3 自动压测脚本（构造高压场景 + 三场景分段采样）
=================================================================

**为什么需要它**
只测"空转"没有意义 —— 卡顿几乎都发生在「周期推进那一刻」和「抽屉/列表
重建那一刻」。本脚本把一次运行切成 4 段，每段自动打场景标签，跑完直接
得到一张对照表：

    A-空闲     ：进游戏后暂停、抽屉关      → 纯渲染成本（基线）
    B-周期推进 ：×1 速 + 每 2s 强制推进一次 → tick + refresh_all 的尖峰成本
    C-高压     ：20 国全解锁 + 日志抽屉打开(120 行) + ×4 速 + 动效全开
                 + 每 1.5s 强制推进一次     → 最坏情况
    D-收尾     ：停止推进后的回落情况

**用法（铁律：从 demo/ 目录跑、带 KIVY_NO_FILELOG=1）**

    cd demo
    KIVY_NO_FILELOG=1 python perf_stress.py

跑约 26 秒，窗口会自动开关，结束后自动退出；结果同时打到 stdout 和
``demo/perf.log``（追加，用 ``# ====`` 分隔每次会话）。

**可调**（改下面常量即可）
    IDLE_S / TICK_S / STRESS_S   各段时长（秒）
    TICK_FORCE / STRESS_FORCE    强制推进间隔（秒）
    WIN_W / WIN_H                窗口尺寸（宽度需能被 4 整除）

!️ 真实节奏是 30s/周期（balance.TUNE['base_tick_seconds']）。脚本把推进
压缩到 2s / 1.5s 一次，**是为了在可测时间窗内取到多次 tick 样本**；
因此 B/C 段的"长帧"密度高于真实游玩，只用于**横向对比**，不代表真实节奏。

!️ 本脚本只构造场景（解锁/开抽屉/提速），**不改任何游戏数值**：
不碰 balance.TUNE、不碰 COUNTRIES 配置、不改掉落/公式。
"""
import os
import sys

os.environ.setdefault('KIVY_NO_FILELOG', '1')
os.environ.setdefault('KIVY_WINDOW', 'sdl2')
os.environ.setdefault('AI_PERF', '1')          # 打开探针（等价于 --perf）
os.environ.setdefault('AI_PERF_EVERY', '3')    # 3s 一段，颗粒度更细

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 窗口尺寸必须在 import kivy 之前定好（宽度能被 4 整除，否则 RGBA 行错位）
WIN_W, WIN_H = '1440', '880'
from kivy.config import Config                 # noqa: E402
Config.set('graphics', 'width', WIN_W)
Config.set('graphics', 'height', WIN_H)

from kivy.clock import Clock                   # noqa: E402

import main as M                               # noqa: E402
import engine                                  # noqa: E402
import perf                                    # noqa: E402
import ui_shared as ST                         # noqa: E402

# ---- 各段时长（秒）----
IDLE_S = 6.0
TICK_S = 8.0
STRESS_S = 10.0
HEAT_S = 8.0              # C2 段：热力层叠加时长（T10）
TICK_FORCE = 2.0          # B 段强制推进间隔
STRESS_FORCE = 1.5        # C 段强制推进间隔

_state = {'game': None, 'forced': None}
_app = {'ref': None}


def _log(msg: str) -> None:
    print(msg, flush=True)


def _game():
    rv = _app['ref'].root
    if rv is None:
        return None
    return rv.game


# ============================================================
# A 段：空闲（暂停 · 抽屉关）
# ============================================================
def _phase_boot(_dt):
    rv = _app['ref'].root
    if rv.game is None:
        rv.start_new_game()
    # 引导遮罩会冻结周期推进（game_tick 首行直接 return），压测必须先关掉
    try:
        engine.player.seen_tutorial = True
    except Exception as e:
        _log(f'!️ 关引导失败（tick 将被冻结，本段数据无效）：{e!r}')
    g = _game()
    if g is not None:
        try:
            g.tutorial.finish()
        except Exception as e:
            _log(f'!️ tutorial.finish 失败（遮罩未关，tick 冻结）：{e!r}')
        g.paused = True
        g.stop_ticking()
    _state['game'] = g
    _log('[A] 空闲：暂停 · 抽屉关 · 无推进   (%.0fs)' % IDLE_S)
    perf.set_scene('A-idle 空闲(暂停)')
    Clock.schedule_once(_phase_tick, IDLE_S)


# ============================================================
# B 段：周期推进（×1 速 + 每 2s 强制推进一次）
# ============================================================
def _force_tick(g) -> None:
    try:
        if g is None or engine.player is None or engine.player.game_over:
            return
        g.game_tick(0)
    except Exception:
        pass  # 强推 tick 属压测驱动：个别边界异常不打断采样节奏


def _phase_tick(_dt):
    g = _state['game']
    if g is not None and not engine.player.game_over:
        g.paused = False
        try:
            g._reschedule_tick()
        except Exception as e:
            _log(f'!️ _reschedule_tick 失败（自然推进停止，仅剩强推）：{e!r}')
    _state['forced'] = Clock.schedule_interval(lambda dt: _force_tick(g),
                                               TICK_FORCE)
    _log('[B] 周期推进：×1 速 + 每 %.1fs 强制推进   (%.0fs)'
         % (TICK_FORCE, TICK_S))
    perf.set_scene('B-tick 周期推进(x1)')
    Clock.schedule_once(_phase_stress, TICK_S)


# ============================================================
# C 段：高压（20 国全解锁 + 抽屉打开 + ×4 速 + 动效全开）
# ============================================================
def _phase_stress(_dt):
    g = _state['game']
    if _state['forced'] is not None:
        _state['forced'].cancel()
        _state['forced'] = None
    if g is not None:
        # 20 国全解锁（只改运行时状态，不改任何配置表）
        try:
            for c in engine.player_countries:
                c.unlocked = True
                if c.downloads_m <= 0:
                    c.downloads_m = max(1.0, c.config.population_m * 0.05)
        except Exception as e:
            _log(f'!️ 20 国解锁失败（C 段高压场景不完整）：{e!r}')
        # 日志塞满 200 条 → 抽屉 rebuild 会建满 120 行（已知热点）
        try:
            for i in range(200):
                g.stats.push_log(i, 'perf stress log %03d %s' % (i, '·' * 18),
                                 'i')
        except Exception as e:
            _log(f'!️ 日志塞压失败（抽屉热点未构造）：{e!r}')
        ST.REDUCE_MOTION = False          # 动效全开
        try:
            g.set_speed_idx(3)            # ×4 速
        except Exception as e:
            _log(f'!️ set_speed_idx(3) 失败（C 段非 ×4 速）：{e!r}')
        try:
            if g._log_drawer is None:
                g.toggle_log()            # 日志抽屉打开
        except Exception as e:
            _log(f'!️ 打开日志抽屉失败（抽屉热点未构造）：{e!r}')
        try:
            g.refresh_all()
        except Exception as e:
            _log(f'!️ refresh_all 失败（首次全量重建未触发）：{e!r}')
    _state['forced'] = Clock.schedule_interval(
        lambda dt: _force_tick(_state['game']), STRESS_FORCE)
    _log('[C] 高压：20 国全解锁 + 抽屉开 + ×4 速 + 动效全开 + 每 %.1fs 推进 '
         '(%.0fs)' % (STRESS_FORCE, STRESS_S))
    perf.set_scene('C-stress 高压(x4·抽屉)')
    Clock.schedule_once(_phase_heat, STRESS_S)


# ============================================================
# C2 段：T10 热力层叠加（相同高压条件下切到 heat 图层）
# ------------------------------------------------------------
# 目的：把「热力层自身的渲染成本」单独量出来 —— 与 C 段条件完全一致，
# 唯一变量是 active_layer。若 C2 相比 C 帧时明显恶化，说明同心环
# 数量需要下调（HEAT_MAX_RINGS）或改成分帧更新。
# ============================================================
def _phase_heat(_dt):
    g = _state['game']
    if g is not None:
        try:
            # 全部拉到中高渗透度，构造最坏情况（每国 4~7 环全亮）
            for i, c in enumerate(engine.player_countries):
                c.downloads_m = c.config.population_m * min(
                    0.95, 0.30 + (i % 7) * 0.10)
            g.set_layer('heat')
            g.refresh_all()
        except Exception as e:
            _log(f'!️ 切热力层失败（C2 段场景不完整）：{e!r}')
    _log('[C2] 热力层叠加：同 C 条件 + active_layer=heat（20 国中高渗透）(%.0fs)'
         % HEAT_S)
    perf.set_scene('C2-heat 热力层(x4·抽屉)')
    Clock.schedule_once(_phase_end, HEAT_S)


# ============================================================
# D 段：收尾
# ============================================================
def _phase_end(_dt):
    if _state['forced'] is not None:
        _state['forced'].cancel()
        _state['forced'] = None
    perf.set_scene('D-end 收尾')
    try:
        perf.stop()
    except Exception:
        pass  # 探针收尾失败安全（perf 自身亦失败安全）；日志读取另有独立报告
    path = perf.log_path()
    _log('[D] 结束。日志：%s' % path)
    try:
        with open(path, encoding='utf-8') as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        # 打印本次会话（最后一个 banner 之后）的全部内容
        start = 0
        for i, ln in enumerate(lines):
            if ln.startswith('# ==== perf 会话开始'):
                start = i
        _log('---- 本次 perf.log ----')
        for ln in lines[start:]:
            print(ln)
    except Exception as e:                       # noqa: BLE001
        _log('（读取日志失败：%r）' % (e,))
    _app['ref'].stop()


def main() -> int:
    app = M.AIBienaoApp()
    _app['ref'] = app
    _log('压测开始：窗口 %sx%s，约 %.0f 秒后自动结束…'
         % (WIN_W, WIN_H, IDLE_S + TICK_S + STRESS_S))
    Clock.schedule_once(_phase_boot, 0.5)
    app.run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
