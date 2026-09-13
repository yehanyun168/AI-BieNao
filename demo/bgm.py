# -*- coding: utf-8 -*-
"""bgm.py —— 《AI 别闹》背景音乐管理器（失败安全，绝不因缺音频后端而崩）。

与 sfx.py 的关系：同一套「多后缀探测 + 打包路径解析 + 静默降级」
范式，但 BGM 有四点不同：
  1. **循环播放**（loop=True），不是一次性音效；
  2. **两态切换**：calm（平稳）/ tense（紧张），由怀疑度驱动 ——
     BGM 本身即压力反馈设计（任务清单 T09），玩家不用管数字就能听出
     「快出事了」；
  3. 切换采用**交叉淡出**（旧曲音量降到 0 再停、新曲淡入），避免硬切；
  4. 每态有**主选 + 备选**两首（风格同源、听感微调），可在设置页切换。

素材来源（2026-09-13 更新）：Abstraction / Tallbeard Studios 的
*Free Music Loop Bundle*（CC0 公有领域，可商用可修改，署名非强制）。
现用曲目由**真人试听裁决**选定，弃用了早期 tools/gen_bgm.py 的 12 秒
合成片段（过短、循环痕迹重，仅作离线备份保留生成脚本）。

使用：
    import bgm
    bgm.load_all()            # 启动时一次
    bgm.update('calm')        # 每周期按当前怀疑度调用（内部判重，无重复开销）
    bgm.set_enabled(False)    # 设置页「音乐」开关
    bgm.set_track_variant(1)  # 设置页「曲目」主选/备选切换
    bgm.stop()                # 返回主菜单 / 退出对局
"""
import os
import sys

from kivy.clock import Clock
from kivy.core.audio import SoundLoader

# 两态名（主选文件 calm.ogg / tense.ogg）
STATES = ('calm', 'tense')

# 候选后缀（按优先级）。⚠️ 顺序**不能**沿用 sfx 的 (.wav, .ogg)：
# BGM 已由真人试听换成 CC0 OGG 长曲，目录里不再有同名 wav；若日后有人
# 误留同名 wav，让它盖掉长曲会瞬间退化回 12 秒合成片段。故 BGM 优先 .ogg。
SUFFIXES = ('.ogg', '.wav', '.mp3')

# 每态的候选曲目（真人试听裁决，可在设置页切换）
VARIANTS = {
    # calm（正常经营）：Penguin Town（主·最顽皮）/ Rabbit Town（备）/ I am not clumsy（备2）
    'calm':  ('calm', 'calm_alt', 'calm_alt2'),
    # tense（被封锁被抵制）：Rumble at the Gates（主·更富希望）/ Save the City（备·压迫感强）
    'tense': ('tense', 'tense_alt'),
}

BGM_ON = True
VOLUME = 0.45
_LOADED = False
_SOUNDS = {}
_current = None            # 当前正在播放的态名（None = 未播放）
_variant = 0               # 当前曲目变体（0=主选，1=备选）


def _resolve(d: str, name: str):
    """按 SUFFIXES 优先级找第一个存在的文件；找不到返回 None。"""
    for suf in SUFFIXES:
        p = os.path.join(d, name + suf)
        if os.path.exists(p):
            return p
    return None


def _base_dir() -> str:
    """BGM 目录：打包态走 _MEIPASS，开发态走 demo/assets/bgm。"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', 'bgm')
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'assets', 'bgm')


# 变体序号 → 显示名（设置页「曲目」标签用；改曲目时同步维护这里）
TRACK_LABELS = {
    0: 'A · 主选',
    1: 'B · 备选',
    2: 'C · 备选二',
}


def get_track_label(state: str, variant=None) -> str:
    """某态当前曲目的可读标签（供设置页/调试显示）。

    越界时显示实际生效的主选（与 `get_sound` 的回落行为保持一致，
    否则界面会显示一个并不存在的档位）。
    """
    v = _variant if variant is None else variant
    names = VARIANTS.get(state, (state,))
    if not (0 <= v < len(names)):
        v = 0
    return '%s [%s]' % (TRACK_LABELS.get(v, str(v)), names[v])


def variant_count(state: str) -> int:
    """某态的候选曲目数量（设置页判断是否显示切换控件）。"""
    return len(VARIANTS.get(state, (state,)))


def _key(state: str, variant: int) -> str:
    """内部加载表的键：态名 + 变体序号（同一态的主选/备选共存不冲突）。"""
    return '%s#%d' % (state, variant)


def load_all() -> None:
    """加载两态 × 全部变体的 BGM（幂等；失败的单条置 None，不影响其它）。

    一次性把主选与备选都载入，是为了让设置页切换曲目时**零等待、零卡顿**
    ——若切的时候才去解码几十 MB 的 OGG，游戏会明显卡一下。
    """
    global _LOADED
    _LOADED = True
    d = _base_dir()
    for state in STATES:
        names = VARIANTS.get(state, (state,))
        for vi, stem in enumerate(names):
            key = _key(state, vi)
            if key in _SOUNDS and _SOUNDS[key] is not None:
                continue
            try:
                p = _resolve(d, stem)
                if p is None:
                    _SOUNDS[key] = None
                    print('[bgm] 警告：BGM 缺失 %s{.ogg/.wav/.mp3}，已静音跳过'
                          '（查找目录: %s）' % (stem, d))
                    continue
                snd = SoundLoader.load(p)
                if snd is not None:
                    snd.loop = True
                    try:
                        snd.volume = VOLUME
                    except Exception:
                        pass
                _SOUNDS[key] = snd
            except Exception as e:
                _SOUNDS[key] = None
                print('[bgm] 警告：BGM 加载失败 %s，已静音跳过：%s' % (stem, e))


def get_sound(state: str, variant=None):
    """取某态当前生效的音频对象（variant 为 None 时用全局当前变体）。

    ⚠️ 越界必须回落主选，不能返回 None：各态候选数不同（calm 3 / tense 2），
    当玩家把变体切到 2 再进入 tense 态时，`tense#2` 不存在 —— 若返回 None，
    `_fade_in(None)` 会静默跳过，玩家会听到「切到紧张态后音乐没了」。
    """
    v = _variant if variant is None else variant
    snd = _SOUNDS.get(_key(state, v))
    if snd is None and v != 0:
        snd = _SOUNDS.get(_key(state, 0))
    return snd


def set_track_variant(vi: int) -> None:
    """设置页「曲目」切换：0=主选，1=备选，2=备选二…（超界自动钳位）。

    正在播放时立即热切：旧曲淡出、同态另一变体淡入，**不打断当前情绪态**。

    ⚠️ 钳位必须以**该态自己的候选数**为准，不能取各态最小值：
    calm 有 3 首、tense 有 2 首，若按 min 钳，calm 的第三首永远切不到。
    各态候选数不一致是**允许且有意**的（用户听感裁决只给了 2 首 tense
    候选），越界时 `get_sound()` 会自动回落到该态主选，不会静音。
    """
    global _variant
    vi = max(0, int(vi))
    if vi == _variant:
        return
    old = get_sound(_current) if _current else None
    _variant = vi
    if _current and BGM_ON:
        _fade_out(old)
        _fade_in(get_sound(_current))


def get_track_variant() -> int:
    """当前曲目变体（设置页回显用）。"""
    return _variant


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
    old = get_sound(_current) if _current else None
    _current = state
    new = get_sound(state)
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
