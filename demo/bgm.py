# -*- coding: utf-8 -*-
"""bgm.py —— 《AI 别闹》背景音乐管理器（失败安全，绝不因缺音频后端而崩）。

与 sfx.py 的关系：同一套「本地合成 CC0 WAV + 打包路径解析 + 静默降级」
范式，但 BGM 有三点不同：
  1. **循环播放**（loop=True），不是一次性音效；
  2. **两态切换**：calm（平稳）/ tense（紧张），由怀疑度驱动 ——
     BGM 本身即压力反馈设计（任务清单 T09），玩家不用盯数字就能听出
     「快出事了」；
  3. 切换采用**交叉淡出**（旧曲音量降到 0 再停、新曲淡入），避免硬切。

设计意图（评审报告：无 BGM 是商店页硬伤）：氛围音是「产品完成度」的
最廉价信号，而本项目已有成熟的合成链路（tools/gen_bgm.py），
不需要外部素材、无版权风险。

使用：
    import bgm
    bgm.load_all()            # 启动时一次
    bgm.update('calm')        # 每周期按当前怀疑度调用（内部判重，无重复开销）
    bgm.set_enabled(False)    # 设置页「音乐」开关
    bgm.stop()                # 返回主菜单 / 退出对局
"""
import os
import sys

from kivy.clock import Clock
from kivy.core.audio import SoundLoader

# 两态名（与 tools/gen_bgm.py 输出一一对应）
STATES = ('calm', 'tense')

BGM_ON = True
VOLUME = 0.45
_LOADED = False
_SOUNDS = {}
_current = None            # 当前正在播放的态名（None = 未播放）


def _base_dir() -> str:
    """BGM 目录：打包态走 _MEIPASS，开发态走 demo/assets/bgm。"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', 'bgm')
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'assets', 'bgm')


def load_all() -> None:
    """加载两态 BGM（幂等；失败的单条置 None，不影响其它 / 不影响游戏）。"""
    global _LOADED
    _LOADED = True
    d = _base_dir()
    for name in STATES:
        if name in _SOUNDS and _SOUNDS[name] is not None:
            continue
        p = os.path.join(d, name + '.wav')
        try:
            if os.path.exists(p):
                snd = SoundLoader.load(p)
                if snd is not None:
                    snd.loop = True
                    try:
                        snd.volume = VOLUME
                    except Exception:
                        pass
                _SOUNDS[name] = snd
            else:
                _SOUNDS[name] = None
                print('[bgm] 警告：BGM 缺失 %s.wav，已静音跳过（查找目录: %s）'
                      % (name, d))
        except Exception as e:
            _SOUNDS[name] = None
            print('[bgm] 警告：BGM 加载失败 %s.wav，已静音跳过：%s' % (name, e))


def set_enabled(on: bool) -> None:
    """设置页「音乐」开关。关闭时立即停播，开启时按需恢复。

    !️ 关闭时用 _pause()（保留 _current）而不用 stop()（清空 _current）——
    否则一旦关过音乐，再打开时就不知道「此刻该放哪一态」，
    要等下一个 tick 才会重新出声（等于开关失效一次）。
    """
    global BGM_ON
    BGM_ON = bool(on)
    if not BGM_ON:
        _pause()
    elif _current:
        name = _current           # 记住该放的态，然后强制重播
        globals()['_current'] = None
        update(name)


def _pause() -> None:
    """停播但保留 _current（供开关恢复用，与 stop() 区分）。"""
    for snd in _SOUNDS.values():
        if snd is not None:
            try:
                snd.stop()
            except Exception:
                pass


def set_volume(v: float) -> None:
    """设置页音量滑条（0.0 ~ 1.0）。"""
    global VOLUME
    VOLUME = max(0.0, min(1.0, float(v)))
    for snd in _SOUNDS.values():
        if snd is not None:
            try:
                snd.volume = VOLUME * _state_gain(globals()['_current'])
            except Exception:
                pass


def _state_gain(state) -> float:
    """该态当前应有的音量系数（交叉淡入淡出用）。"""
    if state == globals()['_current']:
        return 1.0
    return 0.0


def update(state: str) -> None:
    """按游戏状态切换 BGM（幂等：同态重复调用无开销）。

    Args:
        state: 'calm' 或 'tense'（非法值静默忽略）
    """
    global _current
    if state not in STATES:
        return
    if not BGM_ON or not _LOADED:
        _current = state          # 记住状态，等开关打开时补播
        return
    if state == _current:
        return
    old = _SOUNDS.get(_current) if _current else None
    _current = state
    new = _SOUNDS.get(state)
    # 交叉淡出：旧曲 0.6s 内降到 0 再停；新曲 0.6s 内升到 VOLUME
    _fade_out(old)
    _fade_in(new)


def _fade_out(snd) -> None:
    if snd is None:
        return
    try:
        steps = [6, 5, 4, 3, 2, 1, 0]

        def _step(dt, i=0):
            if i >= len(steps):
                try:
                    snd.stop()
                except Exception:
                    pass
                return False
            try:
                snd.volume = VOLUME * (steps[i] / 6.0)
            except Exception:
                return False
            return True

        Clock.schedule_interval(_step, 0.1)
    except Exception:
        pass


def _fade_in(snd) -> None:
    if snd is None:
        return
    try:
        if getattr(snd, 'state', 'stop') != 'play':
            snd.play()
        snd.volume = 0.0

        def _step(dt, i=[0]):
            i[0] += 1
            if i[0] > 6:
                try:
                    snd.volume = VOLUME
                except Exception:
                    pass
                return False
            try:
                snd.volume = VOLUME * (i[0] / 6.0)
            except Exception:
                return False
            return True

        Clock.schedule_interval(_step, 0.1)
    except Exception:
        pass


def stop() -> None:
    """停止全部 BGM（返回主菜单 / 退出对局 / 手动关闭）。"""
    global _current
    for snd in _SOUNDS.values():
        if snd is not None:
            try:
                snd.stop()
            except Exception:
                pass
    _current = None


def state_for_suspicion(suspicion: float, crisis_line: float) -> str:
    """把怀疑度映射到 BGM 态（供游戏侧一行调用）。

    阈值取危机线的 70% —— 比危机线早一步开始紧张，玩家有「预警感」，
    但不会一有怀疑度就全程紧张（那会让切换失去信息量）。
    """
    try:
        if float(suspicion) >= float(crisis_line) * 0.7:
            return 'tense'
    except Exception:
        pass
    return 'calm'
