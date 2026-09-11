# -*- coding: utf-8 -*-
"""
sfx.py —— 《AI 别闹》音效管理器（失败安全，绝不因缺音频后端而崩）。

设计要点：
- 全部音效为本地合成的 CC0 WAV（tools/gen_sfx.py 生成到 demo/assets/sfx/）。
- 打包后走 sys._MEIPASS 解析路径（与 v2_events 同款多候选解析）。
- 任何一步出错都静默降级为 no-op：无音频后端 / 文件缺失 / 播放异常都不影响游戏。

使用：
    import sfx
    sfx.load_all()              # 启动时一次
    sfx.play('select')          # 任意事件点
    sfx.set_enabled(False)      # 设置页「音效」开关
"""
import os
import sys

from kivy.core.audio import SoundLoader

# 音效名（与 gen_sfx.py 输出一一对应）
NAMES = ('click', 'select', 'cast', 'success', 'fail', 'crisis',
        'end_win', 'end_lose')

SFX_ON = True
_LOADED = False
_SOUNDS = {}


def _base_dir() -> str:
    """音效目录：打包态走 _MEIPASS，开发态走 demo/assets/sfx。"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', 'sfx')
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'assets', 'sfx')


def load_all() -> None:
    """加载全部音效（幂等；失败的单条置 None，不影响其它）。"""
    global _LOADED
    _LOADED = True
    d = _base_dir()
    for name in NAMES:
        if name in _SOUNDS and _SOUNDS[name] is not None:
            continue
        p = os.path.join(d, name + '.wav')
        try:
            if os.path.exists(p):
                _SOUNDS[name] = SoundLoader.load(p)
            else:
                _SOUNDS[name] = None
        except Exception:
            _SOUNDS[name] = None


def set_enabled(on: bool) -> None:
    """设置页「音效」开关。"""
    global SFX_ON
    SFX_ON = bool(on)


def play(name: str, volume: float = 1.0) -> None:
    """播放一个音效；关闭 / 未加载 / 异常时静默 no-op。"""
    if not SFX_ON or not _LOADED:
        return
    snd = _SOUNDS.get(name)
    if snd is None:
        return
    try:
        snd.volume = max(0.0, min(1.0, volume))
        if getattr(snd, 'state', 'stop') == 'play':
            snd.stop()
        snd.play()
    except Exception:
        pass
