# -*- coding: utf-8 -*-
"""bgm.py —— 《AI 别闹》背景音乐管理器（失败安全，绝不因缺音频后端而崩）。

与 sfx.py 的关系：同一套「多后缀探测 + 打包路径解析 + 静默降级」范式，
但 BGM 有几点不同：
  1. **播放列表式随机循环**：不再是单曲 `loop=True` 无限重复，而是把
     同一曲池的曲目**随机排序、逐首播放**，每首放完停顿 `GAP_SECONDS`
     秒再放下一首（见 `_advance`）。单曲无限循环听久了会有明显疲劳感，
     换曲能维持长时间游玩的新鲜度。
  2. **三态曲池**：calm（平稳）/ tense（紧张）/ menu（主菜单）——
     calm 与 tense 由怀疑度驱动，BGM 本身即压力反馈设计（任务清单 T09），
     玩家不用管数字就能听出「快出事了」；menu 是主菜单专属的轻松池，
     与对局池分离，避免主菜单响起紧张曲。
  3. **池间切换用交叉淡出**（旧曲音量降到 0 再停、新曲淡入），避免硬切；
     池内换曲则走「自然放完 → 停 1 秒 → 下一首」。
  4. 每态的曲目由**真人试听裁决**选定，见 `POOLS` 与 `assets/bgm/CREDITS.md`。

素材来源（2026-09-13）：Abstraction / Tallbeard Studios 的 *Free Music
Loop Bundle* 与 HydroGene 的 8-bit 曲集，**均为 CC0 公有领域**，可商用、
可修改、署名非强制。已弃用早期 tools/gen_bgm.py 的 12 秒合成片段
（过短、循环痕迹重；生成脚本保留作无素材时的兜底）。

使用：
    import bgm
    bgm.load_all()          # 启动时一次
    bgm.update('menu')      # 主菜单：进菜单时调一次
    bgm.update('calm')      # 对局中：每周期按怀疑度调（内部判重，无重复开销）
    bgm.set_enabled(False)  # 设置页「音乐」开关
    bgm.stop()              # 彻底停播（退出游戏）
"""
import os
import random
import sys

from kivy.clock import Clock
from kivy.core.audio import SoundLoader

# 三个曲池名：calm / tense 为对局态（怀疑度驱动），menu 为主菜单态
STATES = ('calm', 'tense', 'menu')

# 候选后缀（按优先级）。⚠️ 顺序**不能**沿用 sfx 的 (.wav, .ogg)：
# BGM 已由真人试听换成 CC0 OGG 长曲，目录里不再有同名 wav；若日后有人
# 误留同名 wav，让它盖掉长曲会瞬间退化回 12 秒合成片段。故 BGM 优先 .ogg。
SUFFIXES = ('.ogg', '.wav', '.mp3')

# 各曲池的曲目（文件名去掉后缀）。同一池内随机播放、互不重复直到轮完。
# 池子大小的判据是「**单局内总重复次数**」，不是「够不够多」：
# 单局 30-50 周期 × 30s ≈ 15-25 分钟，若某池总时长只有 2-3 分钟，
# 一局内每首要响 8-13 遍，随机打乱也救不回重复感（它只消除相邻重复）。
# 故 calm 池特意混入 HydroGene 的长曲（83-111s），拉高总时长。
POOLS = {
    # calm（正常经营）：顽皮向 3 短曲 + 沉稳向 2 长曲，总时长约 312s ≈ 5.2 分钟
    'calm':  ('calm', 'calm_alt', 'calm_alt2', 'calm_alt3', 'calm_alt4'),
    # tense（被封锁被抵制）：Rumble at the Gates（更富希望）/ Save the City（压迫感强）
    'tense': ('tense', 'tense_alt'),
    # menu（主菜单）：**专属曲**，不与对局池共用 ——
    # 这是听觉上的「状态边界」：菜单是上帝视角谋划，局内是执行扩张。
    # 若 menu 复用 calm 池，玩家进菜单听到的是对局里那首，就分不清
    # 「我在配置」还是「我在打」。（The Quiet Spy：冷感谍战，贴合谋划视角）
    'menu':  ('menu',),
}

# 曲目结束后到下曲开始的停顿（秒）。用户指定 1 秒。
GAP_SECONDS = 1.0

BGM_ON = True
VOLUME = 0.45
_LOADED = False
_SOUNDS = {}               # stem -> Sound 对象（None = 缺失/加载失败）
_current = None            # 当前曲池名（None = 未播放）
_order = {}                # 池名 -> 打乱后的待播队列（stem 列表）
_playing = None            # 当前正在播放的 stem
_advance_ev = None         # 下一次换曲的 Clock 事件
_gap_ev = None             # 停顿期间的 Clock 事件
_paused = False            # 游戏暂停态：与音乐开关 BGM_ON 独立，pause()/resume() 用


def _base_dir() -> str:
    """BGM 目录：打包态走 _MEIPASS，开发态走 demo/assets/bgm。"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', 'bgm')
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'assets', 'bgm')


def _resolve(d: str, name: str):
    """按 SUFFIXES 优先级找第一个存在的文件；找不到返回 None。"""
    for suf in SUFFIXES:
        p = os.path.join(d, name + suf)
        if os.path.exists(p):
            return p
    return None


def pool_stems(state: str):
    """某曲池的曲目名元组（去重后的，供外部查询/测试）。"""
    seen, out = set(), []
    for stem in POOLS.get(state, (state,)):
        if stem not in seen:
            seen.add(stem)
            out.append(stem)
    return tuple(out)


def pool_count(state: str) -> int:
    """某曲池可用曲目数。"""
    return len(pool_stems(state))


def load_all() -> None:
    """加载全部曲池的曲目（幂等；失败的单条置 None，不影响其它）。

    一次性把三个池的曲目都载入，是为了换池/换曲时**零等待、零卡顿**
    —— 若换的时候才去解码几十 MB 的 OGG，游戏会明显卡一下。
    ⚠️ 注意载入的音效**不设 loop=True**：本项目是播放列表式换曲，
    靠 `_advance` 在曲末调度下一首，而不是让单曲无限重复。
    """
    global _LOADED
    _LOADED = True
    d = _base_dir()
    stems = []
    for state in STATES:
        for stem in pool_stems(state):
            if stem not in stems:
                stems.append(stem)
    for stem in stems:
        if stem in _SOUNDS and _SOUNDS[stem] is not None:
            continue
        try:
            p = _resolve(d, stem)
            if p is None:
                _SOUNDS[stem] = None
                print('[bgm] 警告：BGM 缺失 %s{.ogg/.wav/.mp3}，已静音跳过'
                      '（查找目录: %s）' % (stem, d))
                continue
            snd = SoundLoader.load(p)
            if snd is not None:
                snd.loop = False          # 播放列表模式：不单曲循环
                try:
                    snd.volume = VOLUME
                except Exception:
                    pass
            _SOUNDS[stem] = snd
        except Exception as e:
            _SOUNDS[stem] = None
            print('[bgm] 警告：BGM 加载失败 %s，已静音跳过：%s' % (stem, e))


def _available(state: str):
    """某池中真正可用（加载成功）的曲目名列表，按池序返回。"""
    return [s for s in pool_stems(state) if _SOUNDS.get(s) is not None]


def _shuffle(state: str):
    """生成该池的随机播放队列并存入 `_order[state]`。

    ⚠️ 只在池刚被激活时打乱一次，之后按队列顺序依次播完再重打乱 ——
    这样能保证同一池的曲目在一轮内**不重复**（纯 `random.choice` 每首独立
    抽取，可能出现连放两首同曲，听感上像卡带）。
    """
    q = _available(state)
    random.shuffle(q)
    _order[state] = q
    return q


def _cancel_timers() -> None:
    """取消所有待触发的换曲/停顿定时器（切池、关音乐、停止时必调）。"""
    global _advance_ev, _gap_ev
    for attr in ('_advance_ev', '_gap_ev'):
        ev = globals()[attr]
        if ev is not None:
            try:
                ev.cancel()
            except Exception:
                pass
            globals()[attr] = None


def _start_stem(stem: str, fade: bool) -> None:
    """开始播放某曲，并调度「曲末 → 停顿 → 下一首」。

    Args:
        stem: 曲目名（必须已在 _SOUNDS 中且可用）
        fade: True = 淡入（切池用）；False = 直接起播（池内换曲用，
              因为前一首已经放完并静止，再淡入反而听感突兀）
    """
    global _playing, _advance_ev
    snd = _SOUNDS.get(stem)
    if snd is None:
        return
    _playing = stem
    if fade:
        _fade_in(snd)
    else:
        try:
            if getattr(snd, 'state', 'stop') != 'play':
                snd.play()
            snd.volume = VOLUME
        except Exception:
            pass
    # 曲末调度：用音频真实 length 算，而不是固定延时
    try:
        length = float(getattr(snd, 'length', 0.0) or 0.0)
    except Exception:
        length = 0.0
    if length <= 0:
        length = 30.0            # 取不到时长时的兜底（避免定时器永不触发）
    # 留一点余量，确保 settle 在音频真正播完之后
    delay = max(1.0, length - float(getattr(snd, 'position', 0.0) or 0.0) + 0.3)
    _advance_ev = Clock.schedule_once(lambda _dt: _on_track_end(), delay)


def _on_track_end() -> None:
    """曲目播完：停 1 秒（GAP_SECONDS）再播下一首。"""
    global _gap_ev, _advance_ev
    _advance_ev = None
    # ⚠️ 停顿期间必须显式 stop() 当前曲：Kivy 音频播完后 state 会自动变
    # 'stop'，但为防后端在边界上仍持有声道，这里统一收干净，保证「停 1 秒」
    # 是真的静音，而不是听起来还在响。
    snd = _SOUNDS.get(_playing)
    if snd is not None:
        try:
            snd.stop()
        except Exception:
            pass
    _gap_ev = Clock.schedule_once(lambda _dt: _advance(), GAP_SECONDS)


def _advance() -> None:
    """播下一首：取池内队列的下一项，队列空则重新打乱。"""
    global _gap_ev
    _gap_ev = None
    if not BGM_ON or not _current:
        return
    q = _order.get(_current) or []
    if not q:
        q = _shuffle(_current)
    if not q:
        return                    # 该池无可用曲目（全缺失）：静默等待
    stem = q.pop(0)
    _start_stem(stem, fade=False)


def update(state: str) -> None:
    """切换曲池（幂等：同池重复调用无开销）。

    切池时若正在放另一池的曲，交叉淡出；若同池，什么都不做
    （池内换曲由 `_advance` 自动负责，不受本函数影响）。

    Args:
        state: 'calm' / 'tense' / 'menu'（非法值静默忽略）
    """
    global _current
    if state not in STATES:
        return
    if not BGM_ON:
        _current = state          # 记住状态，等开关打开时补播
        return
    if not _LOADED:
        # 自举（2026-09-14 修）：与 sfx 同构 —— 主菜单阶段 update('menu')
        # 先于 load_all() 执行，被 `not _LOADED` 拦下 → 主菜单/开场无音乐。
        load_all()
    if state == _current:
        return
    old_stem = _playing
    old = _SOUNDS.get(old_stem) if old_stem else None
    _cancel_timers()
    _current = state
    if old is not None:
        _fade_out(old)
    q = _shuffle(state)
    if q:
        _start_stem(q.pop(0), fade=True)


def set_enabled(on: bool) -> None:
    """设置页「音乐」开关。关闭时立即停播，开启时按需恢复。

    ⚠️ 关闭时保留 `_current`，这样再打开时能立刻回到该放的池；
    否则一旦关过音乐，要等下一个周期才会重新出声（等于开关失效一次）。
    """
    global BGM_ON
    BGM_ON = bool(on)
    if not BGM_ON:
        _cancel_timers()
        _pause()
    elif _current and not _paused:
        # 暂停态下重新开音乐：保持静音，等 resume() 续播，避免「暂停中却响起 BGM」
        state = _current
        globals()['_current'] = None
        update(state)


def pause() -> None:
    """暂停 BGM（保留当前曲池与正在播放的曲目，供 resume 续播）。失败安全。

    游戏「暂停按钮」调用 —— 与 set_enabled 的音乐开关相互独立：
    暂停游戏时停 BGM，恢复游戏时由 resume() 接着播同一首（从头）。
    """
    global _paused
    if _paused or not _current or not _LOADED:
        return
    _paused = True
    _cancel_timers()
    _pause()                        # 停掉当前曲目，_current / _playing 保留


def resume() -> None:
    """从 pause() 续播当前曲池（同一首从头，或池内下一首）。失败安全。"""
    global _paused
    if not _paused:
        return
    _paused = False
    if not _current or not _LOADED or not BGM_ON:
        return                      # 暂停期间被关音乐 / 未加载：保持静音
    stem = _playing
    if stem and _SOUNDS.get(stem) is not None:
        _start_stem(stem, fade=True)
    else:
        q = _shuffle(_current)
        if q:
            _start_stem(q.pop(0), fade=True)


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
                snd.volume = VOLUME
            except Exception:
                pass


def _fade_out(snd) -> None:
    """旧曲 0.6s 内音量降到 0 再停（切池用，避免硬切）。

    ⚠️ 已停的 Sound 直接跳过：若旧曲恰好刚播完（state='stop'），
    对它做 0.6s 淡出是「对着空气调音量」—— 听起来不是过渡，
    而是「旧曲早就没了、新曲却还在慢慢淡入」，反而比硬切更突兀。
    这种情况直接让新曲起播（fade=False 的观感）。
    """
    if snd is None:
        return
    if getattr(snd, 'state', 'stop') != 'play':
        return                    # 已经不在播了，没有可淡出的对象
    try:
        steps = [5, 4, 3, 2, 1, 0]

        def _step(dt, i=[0]):
            if i[0] >= len(steps):
                try:
                    snd.stop()
                except Exception:
                    pass
                return False
            try:
                level = steps[i[0]]
                i[0] += 1
                snd.volume = VOLUME * (level / 6.0)
                if level == 0:
                    snd.stop()
                    return False
            except Exception:
                return False
            return True

        Clock.schedule_interval(_step, 0.1)
    except Exception:
        pass


def _fade_in(snd) -> None:
    """新曲 0.6s 内音量升到 VOLUME。"""
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
    """停止全部 BGM（退出游戏 / 手动关闭）。"""
    global _current, _playing
    _cancel_timers()
    for snd in _SOUNDS.values():
        if snd is not None:
            try:
                snd.stop()
            except Exception:
                pass
    _current = None
    _playing = None


# 上行 / 下行双阈值（滞回窗口）：
# 只用一个 70% 阈值会出大事 —— 怀疑度是**每周期**重算并调 update() 的，
# 当它恰好在 70% 线上下抖动（策略游戏里极常见：这周期放个降疑技能、
# 下周期又涨回去），update() 会 calm→tense→calm→tense 每周期切一次；
# 每次切池都 _cancel_timers + _shuffle + 淡入淡出，结果是 BGM
# **永远只播得出开头 0.6 秒**，听感像「音乐一直在抽搐」。
# 所以必须留滞回带：上穿 70% 才进 tense，要跌回 55% 以下才回 calm。
_TENSE_ENTER = 0.70
_TENSE_EXIT = 0.55


def state_for_suspicion(suspicion: float, crisis_line: float) -> str:
    """把怀疑度映射到 BGM 池（供游戏侧一行调用）。

    阈值取危机线的 70%（上行）—— 比危机线早一步开始紧张，玩家有
    「预警感」，但不会一有怀疑度就全程紧张（那会让切换失去信息量）。

    ⚠️ 带滞回：当前态是 tense 时要跌破 55% 才回 calm。判据用 `_current`，
    所以本函数不是纯函数 —— 但调用方（每周期一次）正是希望它记住上一态。
    """
    try:
        line = float(crisis_line)
        sus = float(suspicion)
        if _current == 'tense':
            return 'calm' if sus < line * _TENSE_EXIT else 'tense'
        if sus >= line * _TENSE_ENTER:
            return 'tense'
    except Exception:
        pass
    return 'calm'


def now_playing() -> str:
    """当前播放的曲目名（''=未播放）。供调试/设置页显示。"""
    return _playing or ''


def current_state():
    """当前曲池名（None=未播放）。"""
    return _current
