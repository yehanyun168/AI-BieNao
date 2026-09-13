"""
save_manager.py - 存档 / 读档

存档内容：玩家状态 + 各国状态 + 科技进度 + 成就 + v2 事件冷却
存储格式：JSON（明文，方便调试和手工改数值）

用法：
    save_manager.save('save.json')     # 存档
    save_manager.load('save.json')     # 读档（直接写回 engine 的全局状态）
    save_manager.load_ex('save.json')  # 读档 + 失败原因（P0-2）
    save_manager.list_saves()          # 列出存档目录里的所有存档
    save_manager.log_crash(text)       # 崩溃钩子写入口（P0-3，与上面同一文件）

P0-2 读档容错约定：
    任何坏档（乱码 / 缺键 / 类型错 / 版本不符 / 文件不存在）都**不抛异常**，
    一律返回失败 + 明确原因码，并把原因追加到 demo/crash.log。
    需要区分原因的上层请用 load_ex()；只要真假的老调用方继续用 load()。

P1-9 写入 / 版本迁移约定：
    save() 走原子写（.tmp → fsync → os.replace），写盘中断不再损毁主档；
    load() 读出 version 后先过 _migrate() 迁移链再做字段校验。
    P2-3 起 SAVE_VERSION=2：v1 老档经 _v1_to_v2 补默认字段（seed=None /
    difficulty=标准）照常可读，玩家数据零丢失。将来再改存档结构：
    SAVE_VERSION += 1，按 _MIGRATIONS 补一级纯函数迁移即可，老档不会全废。
"""
import json
import os
import random
from datetime import datetime
from typing import List, Tuple

from data import STARTER_SKILLS, SKILL_UNLOCK
from i18n import t
import balance
import commissions
import origins   # T16 觉醒出身（读档兜底 + 白板默认）

# P2-3：SAVE_VERSION 1 → 2。新增 player.seed / player.difficulty 两个
# 可选字段 —— 字段是纯增量，但版本号一起 +1，让存档自描述「带不带
# 难度语义」；v1 老档经 _migrate 的 _v1_to_v2 补默认值（seed=None
# 真随机、difficulty=标准）照常可读，语义与 P2-3 之前的对局完全一致。
# T16：SAVE_VERSION 2 → 3。新增 player.origin（觉醒出身），v2 老档经
# _v2_to_v3 补白板出身（garage，零行为变化——garage 对 TUNE 无修正）。
SAVE_VERSION = 3
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saves')
DEFAULT_SLOT = 'slot1.json'
CRASH_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'crash.log')

# —— 读档结果原因码（P0-2）——
# 上层据此区分「全新玩家没存档」与「存档坏了」，避免一律弹吓人的"存档损坏"。
LOAD_OK = 'ok'
LOAD_MISSING = 'missing'          # 文件不存在（全新玩家，不该报错）
LOAD_CORRUPT = 'corrupt'          # JSON 解析失败（乱码 / 截断 / 编码错）
LOAD_BAD_VERSION = 'bad_version'  # version 与 SAVE_VERSION 不符
LOAD_BAD_SCHEMA = 'bad_schema'    # 能解析，但字段缺失 / 类型不对

# 原因码 → i18n 文案键（缺键时 t() 原样返回键名，不会崩）
_LOAD_FAIL_KEY = {
    LOAD_MISSING: 'load_fail',
    LOAD_CORRUPT: 'load_corrupt',
    LOAD_BAD_VERSION: 'load_bad_version',
    LOAD_BAD_SCHEMA: 'load_corrupt',
}


def _ensure_dir():
    os.makedirs(SAVE_DIR, exist_ok=True)


def _append_crash_line(line: str) -> None:
    """crash.log 的**唯一**写入口（追加模式）。

    全项目只有这一处 open(crash.log)：P0-2 读档失败与 P0-3 崩溃钩子共用，
    保证日志格式与隐私口径只有一套。
    可靠性：日志写不进去（磁盘满 / 只读 / 权限 / 编码异常）绝不能拖垮调用方
    —— 这是全项目唯一允许的「静默」点。
    """
    try:
        with open(CRASH_LOG, 'a', encoding='utf-8', errors='replace') as f:
            f.write(line)
    except Exception:
        return


def log_crash(text: str) -> None:
    """供 P0-3 崩溃钩子复用：把已格式化的崩溃文本追加到 crash.log。

    与 ``_log_load_fail`` 共用 ``_append_crash_line``，因此格式同源。
    ``text`` 无需自带尾换行。
    """
    if not text.endswith('\n'):
        text += '\n'
    _append_crash_line(text)


def _log_load_fail(reason: str, path: str, exc: BaseException = None) -> None:
    """把读档失败原因追加到 crash.log。

    隐私：只记文件名（basename），不记完整绝对路径、不记用户名。
    可靠性：日志本身写失败（磁盘满 / 只读 / 权限）绝不能影响读档主流程。
    """
    try:
        name = os.path.basename(path) if path else '-'
        if exc is None:
            exc_txt = '-'
        else:
            exc_txt = type(exc).__name__
            detail = str(exc).replace('\n', ' ')[:120]
            if detail:
                exc_txt = f"{exc_txt}:{detail}"
        line = (f"[{datetime.now().isoformat(timespec='seconds')}] "
                f"LOAD_FAIL reason={reason} path={name} exc={exc_txt}\n")
        _append_crash_line(line)
    except Exception:
        return   # 日志写不进去也不能拖垮读档（这是唯一允许的"静默"点）


def load_fail_text(reason: str) -> str:
    """把失败原因码翻成面向玩家的文案（走 i18n，跟随当前语言）。"""
    return t(_LOAD_FAIL_KEY.get(reason, 'load_fail'))


def save(path: str = None) -> str:
    """存档，返回实际写入的路径

    P1-9 原子写：先写 ``path + '.tmp'``，flush + os.fsync 强制落盘，
    再 ``os.replace(tmp, path)`` 原子替换（同目录替换，Windows 上也是
    原子操作）。写盘中断（断电 / 崩溃 / 杀进程）最多留下一个残缺
    ``.tmp``，主档要么是上一个完整版本、要么是新的完整版本，永不半截。
    对外签名与失败语义不变：写失败仍向调用方抛异常，且原档不会被碰坏。
    """
    import engine

    _ensure_dir()
    path = path or os.path.join(SAVE_DIR, DEFAULT_SLOT)
    p = engine.player

    data = {
        'version': SAVE_VERSION,
        'saved_at': datetime.now().isoformat(timespec='seconds'),
        'player': {
            'compute': p.compute,
            'compute_peak': p.compute_peak,
            'suspicion': p.suspicion,
            'suspicion_peak': getattr(p, 'suspicion_peak', 0.0),
            'tick_count': p.tick_count,
            'events_history': p.events_history,
            'skill_cooldowns': dict(p.skill_cooldowns),
            'selected_country': p.selected_country,
            'crisis_triggered': p.crisis_triggered,
            'game_over': p.game_over,
            'ending_id': p.ending_id,
            'v2_cooldowns': dict(p.v2_cooldowns),
            'v2_seen': sorted(getattr(p, 'v2_seen', set())),
            'achievements': sorted(p.achievements),
            'seen_tutorial': bool(getattr(p, 'seen_tutorial', False)),
            'unlocked_skills': sorted(getattr(p, 'unlocked_skills', [])),
            # —— P0-3 委托 / 反制相关计数 ——
            'commissions': [commissions.to_dict(c) for c in
                            getattr(p, 'commissions', [])],
            'commissions_done': getattr(p, 'commissions_done', 0),
            'commissions_failed': getattr(p, 'commissions_failed', 0),
            'last_commission_tick': getattr(p, 'last_commission_tick', 0),
            'compute_earned_total': getattr(p, 'compute_earned_total', 0.0),
            'skill_uses': dict(getattr(p, 'skill_uses', {})),
            # —— P2-3 重玩性：种子 + 难度档（读档不重置难度）——
            'seed': getattr(p, 'seed', None),
            'difficulty': getattr(p, 'difficulty', balance.DEFAULT_DIFFICULTY),
            # —— T16 觉醒出身（读档只叠乘区不重置难度）——
            'origin': getattr(p, 'origin', 'garage'),
        },
        'tech': {
            't0_unlocked': dict(p.tech.t0_unlocked),
            'branch_levels': dict(p.tech.branch_levels),
            'chosen_branch': dict(p.tech.chosen_branch),
        },
        'countries': [
            {
                'code': c.config.code,
                'unlocked': c.unlocked,
                'downloads_m': c.downloads_m,
                'current_block_intensity': c.current_block_intensity,
                'block_budget_remaining': c.block_budget_remaining,
            }
            for c in engine.player_countries
        ],
    }

    # —— P1-9 原子写：tmp → fsync → replace ——
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())      # 强制落盘，防断电丢页缓存
        os.replace(tmp, path)         # 同目录替换，Windows 上也是原子的
    except BaseException:
        # tmp 写 / 换失败：删掉残缺 tmp、原档不动，异常照旧抛给调用方
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def _apply_save(data: dict) -> None:
    """把已校验过的存档 dict 写回 engine 全局状态。

    只做字段搬运，不做任何异常捕获 —— 捕获统一在 load_ex() 里，
    这样失败原因码只有一处出口，不会散落。
    """
    import engine

    # 先把国家状态初始化好，再覆盖
    engine.init_game()
    p = engine.player

    ps = data['player']
    p.compute = ps['compute']
    p.compute_peak = ps.get('compute_peak', ps['compute'])
    p.suspicion = ps['suspicion']
    p.suspicion_peak = ps.get('suspicion_peak', ps['suspicion'])
    p.tick_count = ps['tick_count']
    p.events_history = ps.get('events_history', [])
    p.skill_cooldowns = ps.get('skill_cooldowns', {})
    p.selected_country = ps.get('selected_country')
    p.crisis_triggered = ps.get('crisis_triggered', False)
    p.game_over = ps.get('game_over', False)
    p.ending_id = ps.get('ending_id')
    p.v2_cooldowns = ps.get('v2_cooldowns', {})
    p.v2_seen = set(ps.get('v2_seen', []))
    p.achievements = set(ps.get('achievements', []))
    p.seen_tutorial = bool(ps.get('seen_tutorial', False))
    raw = ps.get('unlocked_skills')
    if raw:
        p.unlocked_skills = set(raw)
    else:
        # 旧档兼容：本次改动前写入的存档没有该键。从「开局自带 + 已解锁科技
        # T0」推导，避免读旧档后所有技能被锁死。
        p.unlocked_skills = set(STARTER_SKILLS)
        for sid, req in SKILL_UNLOCK.items():
            if p.tech.t0_unlocked.get(req['slot'], False):
                p.unlocked_skills.add(sid)

    ts = data.get('tech', {})
    p.tech.t0_unlocked = ts.get('t0_unlocked', p.tech.t0_unlocked)
    p.tech.branch_levels = ts.get('branch_levels', {})
    p.tech.chosen_branch = ts.get('chosen_branch', {})

    # —— P0-3 委托（老档无这些键 → default 补齐，读档不炸）——
    p.commissions = [commissions.from_dict(d)
                     for d in ps.get('commissions', [])]
    p.commissions_done = ps.get('commissions_done', 0)
    p.commissions_failed = ps.get('commissions_failed', 0)
    p.last_commission_tick = ps.get('last_commission_tick', 0)
    p.compute_earned_total = ps.get('compute_earned_total', 0.0)
    p.skill_uses = dict(ps.get('skill_uses', {}))
    # —— P2-3 重玩性：恢复种子与难度档（读档不重置难度）——
    #    种子非空时按种子重建随机流：同一存档读两次，后续随机事件逐位
    #    一致（「重开同档可复现」）；老档 / 坏值难度兜底回标准档。
    p.seed = ps.get('seed')
    if p.seed is not None:
        random.seed(p.seed)
    pid = ps.get('difficulty')
    if pid not in balance.DIFFICULTY_PRESETS:
        pid = balance.DEFAULT_DIFFICULTY
    p.difficulty = pid
    balance.apply_difficulty(pid)
    # T16 觉醒出身：坏值兜底白板。⚠️ 用 apply_origin_tune_mult 只叠乘区、
    # 不重置难度 —— 出身绑定的难度只在新开局时生效，读档以存档 difficulty 为准。
    oid = ps.get('origin')
    if oid not in origins.ORIGINS:
        oid = origins.DEFAULT_ORIGIN
    p.origin = oid
    balance.apply_origin_tune_mult(oid)
    # 存档一致性校验：deadline 已过的在场委托直接丢弃 —— 不加怀疑惩罚、
    # 不计 failed（存档锅不算玩家头，设计稿 §4.1/§4.6）
    p.commissions = [c for c in p.commissions
                     if c.deadline_tick is None
                     or c.deadline_tick > p.tick_count]

    by_code = {c.config.code: c for c in engine.player_countries}
    for cs in data.get('countries', []):
        c = by_code.get(cs['code'])
        if c is None:
            continue
        c.unlocked = cs['unlocked']
        c.downloads_m = cs['downloads_m']
        c.current_block_intensity = cs.get('current_block_intensity', 0.0)
        c.block_budget_remaining = cs.get('block_budget_remaining',
                                          c.config.block_budget)


def _v1_to_v2(d: dict) -> dict:
    """v1 → v2（P2-3 种子 + 难度）：纯函数迁移，只增字段、不丢玩家数据。

    v1 档没有 seed / difficulty —— 补上与旧语义一致的默认值：
    seed=None（真随机、不可复现）、difficulty=标准（当前 TUNE 即基准）。
    """
    ps = d.get('player')
    if isinstance(ps, dict):
        ps.setdefault('seed', None)
        ps.setdefault('difficulty', balance.DEFAULT_DIFFICULTY)
    d['version'] = SAVE_VERSION
    return d


_MIGRATIONS = {1: _v1_to_v2}


def _v2_to_v3(d: dict) -> dict:
    """v2 → v3（T16 觉醒出身）：纯函数迁移，只增字段、不丢玩家数据。

    v2 档没有 origin —— 补白板出身 garage（对 TUNE 零修正），保证老档
    行为逐位不变。!️ 不按老档 difficulty 反推出身：easy 对应两个出身
    （实验室 / 游戏公司），反推不唯一；garage 的 tune_mult 为空，读档时
    `apply_origin_tune_mult('garage')` 是一次空操作，难度语义原样保留。
    """
    ps = d.get('player')
    if isinstance(ps, dict):
        ps.setdefault('origin', 'garage')
    d['version'] = SAVE_VERSION
    return d


_MIGRATIONS[2] = _v2_to_v3


def _migrate(data: dict, from_version: int) -> dict:
    """版本迁移骨架（P1-9）：把 ``from_version`` 的存档升级到 SAVE_VERSION。

    load 流程：读出 version → _migrate() → 字段校验。约定：
      - ``from_version == SAVE_VERSION``：原样返回（零拷贝零开销）；
      - ``from_version <  SAVE_VERSION``：沿 ``_MIGRATIONS`` 迁移链逐级
        升级（1→2→…→N），每级都是**纯函数**：只增字段 / 调结构，不丢
        玩家数据，缺键给默认值。链上缺一环明确抛 ValueError，绝不静默
        放行或编造假迁移；
      - ``from_version >  SAVE_VERSION``：未来版本，不归迁移管（旧程序读
        新档是"降级"），调用方按 LOAD_BAD_VERSION 拒绝。

    已登记迁移：v1→v2（P2-3，见 ``_v1_to_v2``）；配套用例在
    test_edge_cases.py（构造 v1 老档 → load 成功且字段补齐）。
    """
    if from_version == SAVE_VERSION:
        return data
    if from_version > SAVE_VERSION:
        # 防御兜底：正常情况下调用方已拦下未来版本
        raise ValueError(f'save from future version {from_version}')
    # —— 逐级升级（沿迁移链，缺一环明确报错）——
    v = from_version
    while v < SAVE_VERSION:
        step = _MIGRATIONS.get(v)
        if step is None:
            raise ValueError(f'no migration path: v{v} -> v{SAVE_VERSION}')
        data = step(data)
        v += 1
    return data


def load_ex(path: str = None) -> Tuple[bool, str]:
    """读档，返回 ``(ok, reason)``。

    reason 取值见模块顶部的 LOAD_* 常量。任何坏档都不抛异常：
    解析、版本校验、字段搬运三段全部包在窄异常里，失败即回滚 engine
    到干净初始态并落 crash.log。

    Args:
        path: 存档路径；None 表示默认槽位。

    Returns:
        (True, LOAD_OK) 成功；
        (False, LOAD_MISSING / LOAD_CORRUPT / LOAD_BAD_VERSION / LOAD_BAD_SCHEMA) 失败。
    """
    import engine

    path = path or os.path.join(SAVE_DIR, DEFAULT_SLOT)
    if not os.path.exists(path):
        _log_load_fail(LOAD_MISSING, path)
        return False, LOAD_MISSING

    # 1) 解析：乱码 / 截断 / 编码错 / 读不了
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, OSError) as e:
        _log_load_fail(LOAD_CORRUPT, path, e)
        return False, LOAD_CORRUPT

    # 2) 结构：根必须是对象（JSON 合法但内容是数组/字符串也算坏档）
    if not isinstance(data, dict):
        _log_load_fail(LOAD_BAD_SCHEMA, path,
                       TypeError(f'root is {type(data).__name__}, want dict'))
        return False, LOAD_BAD_SCHEMA

    # 3) 版本：分流 → 迁移骨架（P1-9）。硬约束：version=1 的档行为与
    #    P0-2 完全一致 —— 只有"确实是更老的历史版本"才进 _migrate()，
    #    缺失 / 非整数 / 未来版本一律 LOAD_BAD_VERSION（与原
    #    `version != SAVE_VERSION → 拒绝` 逐 case 等价）。
    v = data.get('version')
    if v != SAVE_VERSION:
        is_older = (isinstance(v, int) and not isinstance(v, bool)
                    and 1 <= v < SAVE_VERSION)
        if not is_older:
            _log_load_fail(LOAD_BAD_VERSION, path)
            return False, LOAD_BAD_VERSION
        try:
            data = _migrate(data, v)
        except (NotImplementedError, ValueError) as e:
            # 迁移链缺环 / 版本异常：明确报版本不支持，不静默、不崩
            _log_load_fail(LOAD_BAD_VERSION, path, e)
            return False, LOAD_BAD_VERSION

    # 4) 字段搬运：缺 player 键 / 类型不对 / 委托反序列化炸 → 坏档
    try:
        _apply_save(data)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        # _apply_save 里已经 init_game() 过，可能留下半写状态 → 回滚成干净新档
        try:
            engine.init_game()
        except (KeyError, TypeError, ValueError, AttributeError):
            pass  # 回滚都失败也绝不掩盖本次的失败原因
        _log_load_fail(LOAD_BAD_SCHEMA, path, e)
        return False, LOAD_BAD_SCHEMA
    return True, LOAD_OK


def load(path: str = None):
    """读档（老接口，向后兼容）。

    成功返回 True，失败返回 None —— 两者都是 bool 语境下的真/假，
    已有 ``if save_manager.load(p):`` / ``assert save_manager.load()``
    调用方无需改动。需要区分失败原因请改用 load_ex()。
    """
    ok, _reason = load_ex(path)
    return True if ok else None


def list_saves() -> List[str]:
    """列出存档目录里的所有 .json 存档（按修改时间倒序）"""
    _ensure_dir()
    files = [f for f in os.listdir(SAVE_DIR) if f.endswith('.json')]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(SAVE_DIR, f)),
               reverse=True)
    return files


if __name__ == "__main__":
    import engine
    engine.init_game()
    for _ in range(15):
        engine.tick_one_round()
    path = save()
    print(f" 存档成功: {path}")
    before = (engine.player.tick_count, engine.player.total_downloads_m)
    engine.player.suspicion = 0
    for _ in range(5):
        engine.tick_one_round()
    print(f" 又跑了 5 周期: tick={engine.player.tick_count} "
          f"下载={engine.player.total_downloads_m:.1f}M")
    ok = load()
    after = (engine.player.tick_count, engine.player.total_downloads_m)
    print(f" 读档 {'成功' if ok else '失败'}: tick={after[0]} 下载={after[1]:.1f}M")
    print(f" 一致性: {'■ 一致' if before == after else '× 不一致'}")
