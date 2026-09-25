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
    save_manager.migrate_legacy_data() # 把旧版 exe 同级数据迁到 APPDATA

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
import copy
import json
import math
import os
import random
import sys
from datetime import datetime
from typing import List, Tuple

from data import STARTER_SKILLS, SKILLS, SKILL_UNLOCK
from i18n import t
import balance
import commissions
import origins   # T16 觉醒出身（读档兜底 + 白板默认）
from skill_state import ActiveSkill, SkillCast, validate_live_skill_state

# P2-3：SAVE_VERSION 1 → 2。新增 player.seed / player.difficulty 两个
# 可选字段 —— 字段是纯增量，但版本号一起 +1，让存档自描述「带不带
# 难度语义」；v1 老档经 _migrate 的 _v1_to_v2 补默认值（seed=None
# 真随机、difficulty=标准）照常可读，语义与 P2-3 之前的对局完全一致。
# T16：SAVE_VERSION 2 → 3。新增 player.origin（觉醒出身），v2 老档经
# _v2_to_v3 补白板出身（garage，零行为变化——garage 对 TUNE 无修正）。
# intro_v2：SAVE_VERSION 3 → 4。新增 player.intro_seen（该档是否看过/
# 跳过过开场动画），v3 老档经 _v3_to_v4 补 False —— 语义=「没播过」，
# 老玩家下次继续游戏时补播一次新开场，此后不再重复。
# v4（协作方改动）：新增游戏开局年月，日期随周期推进并可跨存档延续。
# v5：清理旧档未解锁国家的下载脏值，并重置受影响的活动下载委托。
# v6：持久化已排队技能与跨周期活动技能。
SAVE_VERSION = 6


from paths import _user_data_dir, migrate_legacy_data


SAVE_DIR = os.path.join(_user_data_dir(), 'saves')
DEFAULT_SLOT = 'slot1.json'
CRASH_LOG = os.path.join(_user_data_dir(), 'crash.log')

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
    validate_live_skill_state(
        p.skill_queue, p.active_skill_effects, p.skill_cooldowns
    )

    data = {
        'version': SAVE_VERSION,
        'saved_at': datetime.now().isoformat(timespec='seconds'),
        'player': {
            'compute': p.compute,
            'compute_peak': p.compute_peak,
            'suspicion': p.suspicion,
            'suspicion_peak': getattr(p, 'suspicion_peak', 0.0),
            'tick_count': p.tick_count,
            'start_year': p.start_year,
            'start_month': p.start_month,
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
            'intro_seen': bool(getattr(p, 'intro_seen', False)),
            'unlocked_skills': sorted(getattr(p, 'unlocked_skills', [])),
            # —— P0-3 委托 / 反制相关计数 ——
            'commissions': [commissions.to_dict(c) for c in
                            getattr(p, 'commissions', [])],
            'commissions_done': getattr(p, 'commissions_done', 0),
            'commissions_failed': getattr(p, 'commissions_failed', 0),
            'last_commission_tick': getattr(p, 'last_commission_tick', 0),
            'compute_earned_total': getattr(p, 'compute_earned_total', 0.0),
            'skill_uses': dict(getattr(p, 'skill_uses', {})),
            'skill_queue': [
                {'skill_id': cast.skill_id, 'targets': list(cast.targets)}
                for cast in p.skill_queue
            ],
            'active_skill_effects': [
                {
                    'skill_id': effect.skill_id,
                    'targets': list(effect.targets),
                    'remaining_ticks': effect.remaining_ticks,
                }
                for effect in p.active_skill_effects
            ],
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
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
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


def _apply_save(
    data: dict,
    skill_state: Tuple[List[SkillCast], List[ActiveSkill]],
) -> None:
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
    p.start_year = ps['start_year']
    p.start_month = ps['start_month']
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
    p.intro_seen = bool(ps.get('intro_seen', False))    # intro_v2：缺键=没播过
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
    p.skill_queue, p.active_skill_effects = skill_state
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
    d['version'] = 2
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
    d['version'] = 3
    return d


_MIGRATIONS[2] = _v2_to_v3


def _v3_to_v4(d: dict) -> dict:
    """v3 → v4：补 intro_seen（开场播放状态）+ 游戏起始年月。

    - intro_seen：v3 档没有该字段，补 False（=「没播过」）—— 与
      seen_tutorial / origin 的「缺键 = 最保守的还没发生过」约定一致；
      老玩家下次继续游戏时补播一次重制开场，播完立刻落盘，此后不再重复。
    - start_year / start_month（协作方改动）：旧档以迁移时的设备年月
      作为游戏起始年月，日期随周期推进并可跨存档延续。
    """
    ps = d.get('player')
    if isinstance(ps, dict):
        ps.setdefault('intro_seen', False)
        now = datetime.now()
        ps.setdefault('start_year', now.year)
        ps.setdefault('start_month', now.month)
    d['version'] = 4
    return d


_MIGRATIONS[3] = _v3_to_v4


def _v4_to_v5(d: dict) -> dict:
    """旧档在内存中清理未解锁下载，并重新起算活动下载委托。"""
    countries = d['countries']
    total = sum(cs['downloads_m'] for cs in countries if cs['unlocked'])
    for cs in countries:
        if not cs['unlocked']:
            cs['downloads_m'] = 0.0

    ps = d['player']
    tick = ps['tick_count']
    for com in ps.get('commissions', []):
        if com['status'] == 'active' and com['goal'] == 'downloads':
            com['snap_downloads'] = total
            com['accepted_tick'] = tick
            com['deadline_tick'] = tick + com['window']
    d['version'] = 5
    return d


_MIGRATIONS[4] = _v4_to_v5


def _v5_to_v6(d: dict) -> dict:
    """v5 → v6：纯复制后补空技能状态，不伪造历史效果。"""
    migrated = copy.deepcopy(d)
    ps = migrated.get('player')
    if isinstance(ps, dict):
        ps['skill_queue'] = []
        ps['active_skill_effects'] = []
    migrated['version'] = 6
    return migrated


_MIGRATIONS[5] = _v5_to_v6


def _parse_skill_state(
    ps: dict,
    countries: list,
) -> Tuple[List[SkillCast], List[ActiveSkill]]:
    """Strictly parse persisted v6 skill state without mutating live state."""
    queue_raw = ps['skill_queue']
    active_raw = ps['active_skill_effects']
    cooldowns = ps['skill_cooldowns']
    if (type(queue_raw) is not list or type(active_raw) is not list
            or type(cooldowns) is not dict):
        raise TypeError('invalid skill state container')

    saved_countries = {}
    for country in countries:
        if type(country) is not dict:
            raise TypeError('invalid country item')
        code = country['code']
        unlocked = country['unlocked']
        if type(code) is not str or not code or type(unlocked) is not bool:
            raise TypeError('invalid saved country')
        saved_countries[code] = unlocked

    def parse_targets(raw):
        if type(raw) is not list:
            raise TypeError('invalid saved skill targets')
        if any(type(code) is not str or not code for code in raw):
            raise TypeError('invalid saved skill target')
        if len(raw) != len(set(raw)):
            raise ValueError('duplicate saved skill target')
        if any(code not in saved_countries or not saved_countries[code]
               for code in raw):
            raise ValueError('unknown or locked saved skill target')
        return tuple(raw)

    queue = []
    for item in queue_raw:
        if type(item) is not dict or set(item) != {'skill_id', 'targets'}:
            raise TypeError('invalid queued skill item')
        skill_id = item['skill_id']
        if type(skill_id) is not str or skill_id not in SKILLS:
            raise ValueError('unknown queued skill')
        queue.append(SkillCast(skill_id, parse_targets(item['targets'])))

    active = []
    for item in active_raw:
        if (type(item) is not dict
                or set(item) != {'skill_id', 'targets', 'remaining_ticks'}):
            raise TypeError('invalid active skill item')
        skill_id = item['skill_id']
        if type(skill_id) is not str or skill_id not in SKILLS:
            raise ValueError('unknown active skill')
        active.append(ActiveSkill(
            skill_id, parse_targets(item['targets']), item['remaining_ticks']
        ))

    persisted_ids = {item.skill_id for item in queue + active}
    if persisted_ids:
        unlocked_raw = ps['unlocked_skills']
        if type(unlocked_raw) is not list:
            raise TypeError('invalid saved unlocked skills')
        if any(type(skill_id) is not str or not skill_id
               or skill_id not in SKILLS for skill_id in unlocked_raw):
            raise ValueError('invalid saved unlocked skill')
        if not persisted_ids.issubset(unlocked_raw):
            raise ValueError('queued or active skill is locked')

    validate_live_skill_state(queue, active, cooldowns)
    return queue, active


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
    解析、版本校验、字段搬运三段全部包在窄异常里；应用失败精确恢复
    加载前的对象与全局状态，并落 crash.log。

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
        except (TypeError, KeyError, OverflowError) as e:
            _log_load_fail(LOAD_BAD_SCHEMA, path, e)
            return False, LOAD_BAD_SCHEMA
        except (NotImplementedError, ValueError) as e:
            # 迁移链缺环 / 版本异常：明确报版本不支持，不静默、不崩
            _log_load_fail(LOAD_BAD_VERSION, path, e)
            return False, LOAD_BAD_VERSION

    # 4) 完整解析后才允许写 live state。v5/v6 锁国脏值只在内存修复。
    try:
        dirty_codes = []
        valid_codes = {c.code for c in engine.COUNTRIES}
        for cs in data['countries']:
            amount = cs['downloads_m']
            if cs['unlocked']:
                if (isinstance(amount, bool)
                        or not isinstance(amount, (int, float))
                        or not math.isfinite(amount)):
                    raise TypeError('invalid unlocked downloads_m')
            elif v >= 5 and (not isinstance(amount, (int, float))
                             or isinstance(amount, bool)
                             or amount != 0.0):
                code = cs['code']
                if not isinstance(code, str) or code not in valid_codes:
                    raise TypeError('invalid locked country code')
                dirty_codes.append(code)
                cs['downloads_m'] = 0.0
        parsed_skill_state = _parse_skill_state(data['player'],
                                                data['countries'])
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as e:
        _log_load_fail(LOAD_BAD_SCHEMA, path, e)
        return False, LOAD_BAD_SCHEMA

    old_player = engine.player
    old_countries = engine.player_countries
    old_counterplay_cooldown = engine._counterplay_cooldown
    old_counterplay_pending = engine._counterplay_pending
    old_recent_templates = engine._recent_commission_templates
    counterplay_cooldown_data = dict(old_counterplay_cooldown)
    counterplay_pending_data = dict(old_counterplay_pending)
    recent_templates_data = list(old_recent_templates)
    tune_data = dict(balance.TUNE)
    active_difficulty = balance.ACTIVE_DIFFICULTY
    active_origin = balance.ACTIVE_ORIGIN
    next_commission_uid = commissions._next_uid
    rng_state = random.getstate()
    try:
        _apply_save(data, parsed_skill_state)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as e:
        engine.player = old_player
        engine.player_countries = old_countries
        old_counterplay_cooldown.clear()
        old_counterplay_cooldown.update(counterplay_cooldown_data)
        engine._counterplay_cooldown = old_counterplay_cooldown
        old_counterplay_pending.clear()
        old_counterplay_pending.update(counterplay_pending_data)
        engine._counterplay_pending = old_counterplay_pending
        old_recent_templates[:] = recent_templates_data
        engine._recent_commission_templates = old_recent_templates
        balance.TUNE.clear()
        balance.TUNE.update(tune_data)
        balance.ACTIVE_DIFFICULTY = active_difficulty
        balance.ACTIVE_ORIGIN = active_origin
        commissions._next_uid = next_commission_uid
        random.setstate(rng_state)
        _log_load_fail(LOAD_BAD_SCHEMA, path, e)
        return False, LOAD_BAD_SCHEMA
    if dirty_codes:
        log_crash(f"[{datetime.now().isoformat(timespec='seconds')}] "
                  f"LOAD_REPAIR locked_downloads countries={','.join(dirty_codes)}")
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
