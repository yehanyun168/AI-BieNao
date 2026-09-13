# -*- coding: utf-8 -*-
"""
sfx.py —— 《AI 别闹》音效管理器（失败安全，绝不因缺音频后端而崩）。

设计要点：
- 音效分两批来源，Kivy 对两者都能直接加载（实测 44.1kHz 立体声 OGG/WAV 均 OK）：
    1. 本地合成 CC0 WAV（tools/gen_sfx.py 生成到 demo/assets/sfx/）—— 波表音色；
    2. Kenney CC0 OGG / Atelier Magicae 像素 WAV（demo/assets/sfx/）—— 拟音音色。
  因此本模块按**候选后缀依次探测**（.wav → .ogg），同名时优先 .wav，
  保持「合成音为基线、外部素材为可选覆盖」的可回退性。
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

# 音效名（与 tools/gen_sfx.py / demo/assets/sfx 目录内容对应）
# 前 12 个为合成基线；其后为「语义补充分层」——2026-09-13 分三批加入：
#   第 1 批（Kenney interface-sounds CC0）：区分原本共用 click 的各类交互；
#   第 2 批（同上，同批素材）：补齐「技能投放」与「科技分支升级」的缺口，
#     并把过短的 hover 换成听感更清晰的版本。
#   第 3 批（Kenney sci-fi-sounds + interface-sounds CC0）：补**系统层反馈**——
#     原实现把 UI 层做得不错（hover/page/toggle/…），但游戏世界「对玩家回话」
#     的时刻几乎全静默：敌人反制没声、成就解锁没声、委托接拒没声。
#     这批专治这个结构性失衡。
NAMES = ('click', 'select', 'cast', 'success', 'fail', 'crisis',
        'end_win', 'end_lose', 'tech', 'pause', 'drop', 'unlock',
        # —— 语义补充分层（第 1 批）——
        'hover', 'page', 'toggle', 'error', 'confirm',
        # —— 语义补充分层（第 2 批：投放/分支）——
        'deploy', 'branch', 'confirm_cast',
        # —— 系统层反馈（第 3 批）——
        'counter_warn', 'counter_hit', 'achieve', 'commission',
        # —— 开场动画环境床 / 重音（第 4 批，2026-09-14）——
        # Kenney sci-fi-sounds CC0 选材 + tools/make_intro_sfx.py 加工，
        # power_on 为自产合成（三层复合，见该脚本 docstring）。
        # server_hum 以 play_loop 循环床方式使用，其余一次性播放。
        'server_hum', 'power_on', 'machine_run', 'impact_low')

# 候选后缀（按优先级；同名多后缀时取靠前者）
SUFFIXES = ('.wav', '.ogg')

SFX_ON = True
_LOADED = False
_SOUNDS = {}


def _base_dir() -> str:
    """音效目录：打包态走 _MEIPASS，开发态走 demo/assets/sfx。"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', 'sfx')
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'assets', 'sfx')


def _resolve(d: str, name: str):
    """按 SUFFIXES 优先级找第一个存在的文件；找不到返回 None。"""
    for suf in SUFFIXES:
        p = os.path.join(d, name + suf)
        if os.path.exists(p):
            return p
    return None


def load_all() -> None:
    """加载全部音效（幂等；失败的单条置 None，不影响其它）。"""
    global _LOADED
    _LOADED = True
    d = _base_dir()
    for name in NAMES:
        if name in _SOUNDS and _SOUNDS[name] is not None:
            continue
        try:
            p = _resolve(d, name)
            if p is not None:
                _SOUNDS[name] = SoundLoader.load(p)
            else:
                _SOUNDS[name] = None
                print('[sfx] 警告：音效缺失 %s{.wav/.ogg}，已静音跳过（查找目录: %s）'
                      % (name, d))
        except Exception as e:
            _SOUNDS[name] = None
            print('[sfx] 警告：音效加载失败 %s，已静音跳过：%s' % (name, e))


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


# ============================================================
# 循环床接口（2026-09-14，开场动画）
# ------------------------------------------------------------
# server_hum 这类环境床需要 loop 播放 + 运行中调音量（电涌掉压包络）。
# 刻意**不复用** play() 的 _SOUNDS 实例：play() 有「同名先 stop 再 play」
# 互斥语义，循环床会被任何一次同名 play() 打断。循环床用独立加载的
# Sound 实例，与 play() 互不干扰 —— 代价是多一路可能的漏音点，所以配
# stop_all_loops() 兜底（跳过/收尾时必须调用）。
# ============================================================
_LOOP_SOUNDS = {}


def play_loop(name: str, volume: float = 1.0) -> None:
    """循环播放一个音效（失败安全）。已在循环则只调整音量。

    音量包络（如 server_hum 的电涌掉压 0.34→0.08→渐起）由调用方用
    Animation(snd.volume) 或 Clock 驱动 —— Kivy Sound.volume 是可动画属性。
    """
    if not SFX_ON or not _LOADED:
        return
    cur = _LOOP_SOUNDS.get(name)
    if cur is not None:
        try:
            cur.volume = max(0.0, min(1.0, volume))
        except Exception:
            pass
        return
    try:
        p = _resolve(_base_dir(), name)
        snd = SoundLoader.load(p) if p else None
        if snd is None:
            return
        snd.loop = True
        snd.volume = max(0.0, min(1.0, volume))
        snd.play()
        _LOOP_SOUNDS[name] = snd
    except Exception:
        pass


def stop_loop(name: str) -> None:
    """停掉指定循环床（幂等，未在循环则 no-op）。"""
    snd = _LOOP_SOUNDS.pop(name, None)
    if snd is None:
        return
    try:
        snd.stop()
        snd.loop = False
        snd.unload()
    except Exception:
        pass


def stop_all_loops() -> None:
    """停掉全部循环床 —— 跳过开场 / 退出动画时的兜底，防漏音。"""
    for name in list(_LOOP_SOUNDS):
        stop_loop(name)
