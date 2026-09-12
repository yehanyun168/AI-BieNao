"""
perf.py - 帧率基线与压测探针（P1-3）
=================================================================

**为什么要有这个模块**
真人测试（M1）里玩家只会说"卡"，但"卡"无法定位：是空转就卡、还是推进
周期那一下卡、还是打开日志抽屉才卡；也无法判断是**回归**还是本来就慢。
本模块给出可复现的帧时数字（p50 / p95 / max）与控件·canvas 指令计数，
让"卡"变成一条可以贴进 issue 的日志行。

**分层位置（重要）**
本模块位于 **L0（基础层，低于 engine 的 L3）**：
  - 只 import 标准库 + kivy（Clock / Window），**不 import 任何项目模块**
    （不碰 engine / ui_* / main），因此不可能产生反向依赖或循环 import，
    也不会被 game 状态污染。
  - 它**没有**被登记进 ``verify_tables.py`` 的 ``LAYERS`` 字典 —— 即属于
    "未纳管"模块。这是**有意为之**：LAYERS 只约束业务模块的分层，而 perf
    是旁路观测工具，不参与业务依赖图；且 LAYERS 的检查只遍历字典里已登记
    的模块，未登记不会报错也不会误判（但它同时也**不受**分层保护 —— 所以
    本模块必须永远保持"零项目依赖"，一旦 import 了 ui_* 就请把它加入
    LAYERS 再改）。
  - 唯一挂载点在 ``main.py``(L10)：``main → perf`` 是合法的高层调低层。

**开关（默认关闭）**
  - 命令行：``python main.py --perf``
  - 环境变量：``AI_PERF=1``（Windows: ``set AI_PERF=1``）
  - 可选：``AI_PERF_EVERY=5`` 采样汇总周期（秒，默认 5）
           ``AI_PERF_LOG=xxx.log`` 自定义日志路径
  - 关闭时**零开销**：main.py 根本不 import 本模块，也不注册任何 Clock
    回调、不打开文件句柄（见 ZERO-OVERHEAD 说明）。

**开销控制（打开时）**
  - 每帧只做一次 list.append(dt) + int 自增（约 0.1µs 级）。
  - 昂贵的部分（遍历整棵控件树数 canvas 指令、排序算分位）**只在汇总点**
    执行（默认每 5 秒一次），不在热路径上。
  - 文件句柄常开，只在汇总点写一行并 flush；写失败自动**永久降级为不写**
    （不会每帧重试、不会刷屏）。

**失败安全**
所有对外 API 内部均包 try/except：探针自身抛异常绝不影响游戏主流程。
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from typing import List, Optional, Sequence

from kivy.clock import Clock

# ============================================================
# 常量 / 配置
# ============================================================
LOG_NAME = 'perf.log'
DEFAULT_EVERY = 5.0          # 汇总周期（秒）
SLOW_FRAME_MS = 33.0         # "长帧"阈值：>33ms 即跌破 30fps，人眼可感

_ENV_ENABLED = ('AI_PERF',)
_ENV_EVERY = 'AI_PERF_EVERY'
_ENV_LOG = 'AI_PERF_LOG'

_TRUE = {'1', 'true', 'yes', 'on'}
_FALSE = {'', '0', 'false', 'no', 'off'}


def _env_flag(name: str) -> Optional[bool]:
    v = os.environ.get(name, '').strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None


# ============================================================
# 对外：是否启用
# ============================================================
def enabled() -> bool:
    """探针开关：命令行 ``--perf`` 或环境变量 ``AI_PERF=1``。

    供 main.py 在**导入本模块之前**判断是否要导入；这里也重复实现一次，
    以便直接 import perf 后单独查询。
    """
    try:
        if '--perf' in sys.argv:
            return True
        return bool(_env_flag('AI_PERF'))
    except Exception:
        return False


def log_path() -> str:
    """日志文件绝对路径（默认 ``<demo>/perf.log``；*.log 已被 .gitignore 忽略）"""
    try:
        custom = os.environ.get(_ENV_LOG, '').strip()
        if custom:
            return os.path.abspath(custom)
    except Exception:
        pass  # 环境变量读不出 → 用默认路径；探针配置失败不影响游戏
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_NAME)


# ============================================================
# 统计工具
# ============================================================
def _pct(sorted_vals: Sequence[float], q: float) -> float:
    """线性插值分位数（q ∈ [0,1]）；空序列返回 0。"""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_vals[0])
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac)


def _count_tree(root) -> tuple:
    """统计控件数与 canvas 指令数（**只在汇总点调用**，别放进热路径）。

    返回 ``(widgets, canvas_ops)``：
      - widgets：整棵树的 Widget 数量（含 root）
      - canvas_ops：所有 canvas / canvas.before / canvas.after 的指令总数
        —— 这是查「每帧重建泄漏」的关键指标：正常游玩时应保持稳定，
        若持续单调增长即说明有控件/指令在反复重建而未释放。

    用显式栈而非递归：控件树可能很深，递归有爆栈风险。
    """
    widgets = 0
    ops = 0
    stack = [root]
    while stack:
        w = stack.pop()
        widgets += 1
        try:
            cv = w.canvas
            ops += len(cv.children)
            ops += len(cv.before.children)
            ops += len(cv.after.children)
        except Exception:
            pass  # 个别控件画布不可访问 → 该控件不计入 ops 统计
        ch = getattr(w, 'children', None)
        if ch:
            try:
                stack.extend(ch)
            except Exception:
                pass  # 遍历中控件树被改 → 少数控件不计入，无碍统计
    return widgets, ops


# ============================================================
# 探针主体
# ============================================================
class _Probe:
    """单例探针：按帧采样 dt，按固定周期汇总写日志。"""

    def __init__(self, root, every: float = DEFAULT_EVERY,
                 path: Optional[str] = None):
        self.root = root
        self.every = max(0.5, float(every))
        self.path = path or log_path()
        self.scene = 'boot'
        self.samples: List[float] = []      # 帧时（秒）
        self.slow = 0                       # >33ms 的长帧数
        self._t0 = time.time()              # 当前场景起点（墙钟）
        self._clock0 = 0.0                  # 当前场景起点（Clock）
        self._fh = None
        self._write_enabled = True
        self._ev = None
        self._running = False
        self.total_frames = 0
        self.total_time = 0.0

    # ---------- 生命周期 ----------
    def start(self) -> None:
        try:
            self._open_log()
            self._banner()
            self._clock0 = Clock.get_time()
            self._ev = Clock.schedule_interval(self._on_frame, 0)
            self._running = True
        except Exception:
            # 启动失败 = 探针整体不可用，静默降级
            self._running = False
            self._write_enabled = False

    def stop(self) -> None:
        """收尾：flush 最后一段 + 写总计 + 关文件。

        任何异常都吞掉 —— 探针绝不能把游戏退出流程搞挂。
        """
        try:
            if self._ev is not None:
                self._ev.cancel()
                self._ev = None
            if self._running:
                self._flush('STOP')
            self._write('# ==== 会话结束 %s ====\n'
                        % time.strftime('%Y-%m-%d %H:%M:%S'))
        except Exception:
            pass
        finally:
            self._running = False
            try:
                if self._fh is not None:
                    self._fh.close()
            except Exception:
                pass  # 句柄可能已关；收尾关文件失败无碍
            self._fh = None

    def set_scene(self, name: str) -> None:
        """打场景标签：先结算上一段，再开新一段。

        用法：``perf.set_scene('stress-20国-抽屉开')``。
        这样一次运行就能产出「空闲 / 周期推进 / 高压」的对照数据。
        """
        try:
            if not self._running:
                self.scene = str(name)
                return
            self._flush(self.scene)
            self.scene = str(name)
            self._clock0 = Clock.get_time()
            self._t0 = time.time()
            self.samples = []
            self.slow = 0
        except Exception:
            self.scene = str(name)

    # ---------- 每帧采样（热路径：越轻越好）----------
    def _on_frame(self, dt) -> None:
        try:
            self.samples.append(dt)
            if dt * 1000.0 > SLOW_FRAME_MS:
                self.slow += 1
        except Exception:
            return
        try:
            if Clock.get_time() - self._clock0 >= self.every:
                self._flush(self.scene)
                self._clock0 = Clock.get_time()
                self._t0 = time.time()
                self.samples = []
                self.slow = 0
        except Exception:
            pass  # 分段落盘失败 → 本段少一行样本，绝不影响主循环节奏

    # ---------- 汇总（非热路径）----------
    def _flush(self, scene: str) -> None:
        n = len(self.samples)
        dur = max(1e-6, time.time() - self._t0)
        if n == 0:
            self._write('%-34s | no-frames in %.2fs' % (scene, dur))
            return
        try:
            ms = sorted(v * 1000.0 for v in self.samples)
        except Exception:
            return
        self.total_frames += n
        self.total_time += dur
        try:
            widgets, ops = _count_tree(self.root) if self.root is not None else (0, 0)
        except Exception:
            widgets, ops = -1, -1
        fps = n / dur
        self._write(
            '%-26s | %6.2fs | fps %5.1f | p50 %6.1fms p95 %6.1fms max %7.1fms'
            ' | 帧 %4d 长帧 %3d | 控件 %5d canvas %6d'
            % (scene[:26], dur, fps, _pct(ms, 0.50), _pct(ms, 0.95), ms[-1],
               n, self.slow, widgets, ops))

    # ---------- 落盘 ----------
    def _open_log(self) -> None:
        try:
            self._fh = open(self.path, 'a', encoding='utf-8')
        except Exception:
            self._fh = None
            self._write_enabled = False

    def _banner(self) -> None:
        try:
            import kivy
            kv = kivy.__version__
        except Exception:
            kv = '?'
        try:
            from kivy.core.window import Window
            size = '%dx%d' % (Window.width, Window.height)
        except Exception:
            size = '?'
        self._write('# ==== perf 会话开始 %s | py %s | kivy %s | window %s '
                    '| 汇总周期 %.1fs ===='
                    % (time.strftime('%Y-%m-%d %H:%M:%S'),
                       sys.version.split()[0], kv, size, self.every))
        self._write('# 列：场景 | 时长 | fps | p50/p95/max 帧时 | 帧数 长帧(>%dms) '
                    '| 控件数 canvas指令数' % int(SLOW_FRAME_MS))
        self._write('# 长帧 = 帧时 > %dms（跌破 30fps，人眼可感）；'
                    'canvas 指令数持续单调增长 = 有每帧重建泄漏'
                    % int(SLOW_FRAME_MS))

    def _write(self, line: str) -> None:
        if not self._write_enabled or self._fh is None:
            return
        try:
            self._fh.write(line + '\n')
            self._fh.flush()
        except Exception:
            # 写日志失败（磁盘/权限）→ 永久关闭写盘，绝不每帧重试刷屏
            self._write_enabled = False
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None


# ============================================================
# 模块级单例与对外 API（全部失败安全）
# ============================================================
_PROBE: Optional[_Probe] = None


def start(root=None, scene: str = 'boot',
          every: Optional[float] = None) -> Optional[_Probe]:
    """启动探针。**默认关闭**：未被显式开启时直接返回 None（零开销）。"""
    global _PROBE
    try:
        if not enabled():
            return None
        if root is None:
            try:
                from kivy.app import App
                root = App.get_running_app().root
            except Exception:
                root = None
        if every is None:
            try:
                every = float(os.environ.get(_ENV_EVERY, '').strip()
                              or DEFAULT_EVERY)
            except Exception:
                every = DEFAULT_EVERY
        _PROBE = _Probe(root, every=every)
        _PROBE.scene = str(scene)
        _PROBE.start()
        return _PROBE
    except Exception:
        _PROBE = None
        return None


def set_scene(name: str) -> None:
    """切换/标记场景（见 ``_Probe.set_scene``）。未启动时无操作。"""
    global _PROBE
    if _PROBE is None:
        return
    try:
        _PROBE.set_scene(name)
    except Exception:
        pass  # 场景标签打不上只影响日志分组，不影响采样


def stop() -> None:
    """停止并收尾。未启动时无操作。"""
    global _PROBE
    if _PROBE is None:
        return
    try:
        _PROBE.stop()
    except Exception:
        traceback.print_exc()
    finally:
        _PROBE = None


def probe() -> Optional[_Probe]:
    """取当前探针实例（压测脚本用；未启用返回 None）。"""
    return _PROBE
