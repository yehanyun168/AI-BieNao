"""
commissions.py - 动态委托系统（P0-3，设计稿 §1）

分层定位：数据层（engine 层 3 → 本模块层 2 → conditions/balance/data 层 0-1），
**不 import engine / 任何 UI** —— 生成与判定都是纯函数，
需要玩家状态的地方一律由调用方（engine）传参。

设计要点（对应设计稿）：
  1. 目标值全部按接单时刻的实际经济**自标定**：
     目标 = 预期自然增长 × 时限窗口 × margin（margin 每单随机，
     uniform(margin-spread, margin+spread) → 同模板天然有难有易）。
     不写死绝对数，天然免疫科技 / 难度改动造成的失衡。
  2. 时限窗口是**内容参数**放模板表；节奏类可调参数（间隔/上限/TTL/margin…）
     进 balance.TUNE（见 §1.1 表）。
  3. 判定条件全部用 conditions.py 的 cond 语法（``_cond_for`` 统一构造，
     生成路径与 verify_tables 的静态校验共享同一函数，字段名不可能漂移）。
"""
import dataclasses
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from conditions import evaluate as _eval_cond
from balance import TUNE, AGE_STRUCTURE_BONUS
from data import SKILLS


# ============================================================
# 模板表（6 条；内容参数：时限窗口 / 奖励系数 / C5 专有项）
# ============================================================
COMMISSION_TEMPLATES: List[Dict[str, Any]] = [
    dict(id='C1', icon='[P]', name_zh='渗透攻坚', name_en='Deep Push',
         goal='pen', window=12, reward_mult=1.0),
    dict(id='C2', icon='[D]', name_zh='拉新冲刺', name_en='Growth Sprint',
         goal='downloads', window=8, reward_mult=1.0),
    dict(id='C3', icon='[C]', name_zh='算力冲刺', name_en='Compute Sprint',
         goal='compute', window=8, reward_mult=1.0),
    dict(id='C4', icon='[K]', name_zh='技能特训', name_en='Skill Drill',
         goal='skill', window=6, reward_mult=1.2),
    dict(id='C5', icon='[S]', name_zh='隐身行动', name_en='Quiet Run',
         goal='stealth', window=8, reward_mult=1.5,
         # C5 专有：怀疑度上限在 [cap-range, cap] 随难度浮动；完成额外减免
         stealth_cap=50.0, stealth_range=10.0, sus_relief=4.0),
    dict(id='C6', icon='[N]', name_zh='开疆拓土', name_en='New Frontier',
         # R17 回退：reward_mult 1.0 使合规之王 6.7→3.3%（注入仍过敏），
         #   维持 0.8。
         goal='unlock', window=15, reward_mult=0.8),
]

TEMPLATE_BY_ID = {t['id']: t for t in COMMISSION_TEMPLATES}

# 委托判定 ctx 可能出现的全部字段（供 verify_tables 交叉校验；
# skill_uses_delta 的子键由生成时的技能选择决定，这里登记「父键」）
COND_CTX_KEYS: Set[str] = {
    'suspicion', 'target_pen_delta', 'downloads_delta',
    'compute_earned_delta', 'skill_uses_delta', 'unlocked_delta',
}

# goal 类型 → 判定 ctx 字段
_GOAL_FIELD = {
    'pen': 'target_pen_delta',
    'downloads': 'downloads_delta',
    'compute': 'compute_earned_delta',
    'skill': 'skill_uses_delta',
    'stealth': 'suspicion',
    'unlock': 'unlocked_delta',
}


# ============================================================
# 委托实例状态
# ============================================================
@dataclass
class CommissionState:
    uid: int                          # 局内唯一 id（同模板可多单在场）
    template_id: str
    goal: str                         # pen / downloads / compute / skill / stealth / unlock
    icon: str
    name_zh: str
    name_en: str
    window: int                       # 时限（周期数，内容参数）
    reward_mult: float
    status: str = 'offered'           # offered（待接受）/ active（进行中）
    offered_tick: int = 0             # 生成周期
    accepted_tick: Optional[int] = None
    deadline_tick: Optional[int] = None   # accepted_tick + window
    target_country: Optional[str] = None  # C1 目标国 code
    skill_id: Optional[str] = None        # C4 指定技能
    target_value: float = 0.0             # 生成时算好的目标值（展示/调试用）
    cond: Optional[Dict[str, Any]] = None  # 判定条件（conditions 语法，纯数据）
    reward: float = 0.0                   # 完成奖励算力（接受时结算）
    sus_relief: float = 0.0               # C5 完成额外怀疑度减免
    # —— 接单快照（判定用增量 = 当前值 − 快照）——
    snap_pen: float = 0.0
    snap_downloads: float = 0.0
    snap_compute: float = 0.0
    snap_skill_uses: int = 0
    snap_unlocked: int = 0


# —— uid 管理（读档后从存档 uid 续号，避免局内冲突）——
_next_uid = 1


def _new_uid() -> int:
    global _next_uid
    v = _next_uid
    _next_uid += 1
    return v


def bump_uid(v: int) -> None:
    """读档时推进 uid 计数器，保证之后新生成的 uid 不与存档实例冲突。"""
    global _next_uid
    if v >= _next_uid:
        _next_uid = v + 1


# ============================================================
# 存档序列化（save_manager 调用；老档缺字段时 dataclass 默认值兜底）
# ============================================================
_STATE_FIELDS = [f.name for f in dataclasses.fields(CommissionState)]


def to_dict(com: CommissionState) -> Dict[str, Any]:
    return {k: getattr(com, k) for k in _STATE_FIELDS}


def from_dict(d: Dict[str, Any]) -> CommissionState:
    kw = {k: d[k] for k in _STATE_FIELDS if k in d}
    com = CommissionState(**kw)
    bump_uid(com.uid)
    return com


# ============================================================
# cond 构造（生成路径与 verify_tables 共享，杜绝字段名漂移）
# ============================================================
def _cond_for(t: Dict[str, Any], target_value: float,
              skill_id: Optional[str] = None) -> Dict[str, Any]:
    """按模板 goal 构造判定条件（设计稿 §1.3 的六种形状）。"""
    g = t['goal']
    if g == 'pen':
        return {'target_pen_delta': round(target_value, 6)}
    if g == 'downloads':
        return {'downloads_delta': round(target_value, 3)}
    if g == 'compute':
        return {'compute_earned_delta': round(target_value, 3)}
    if g == 'skill':
        return {f'skill_uses_delta.{skill_id}': int(target_value)}
    if g == 'stealth':
        return {'suspicion': {'lte': round(target_value, 1)}}
    return {'unlocked_delta': {'gte': 1}}


def sample_cond(t: Dict[str, Any]) -> Dict[str, Any]:
    """每模板给出一个代表 cond（verify_tables 静态校验用）。"""
    g = t['goal']
    if g == 'pen':
        return _cond_for(t, 0.01)
    if g == 'downloads':
        return _cond_for(t, 100.0)
    if g == 'compute':
        return _cond_for(t, 100.0)
    if g == 'skill':
        return _cond_for(t, 1, skill_id='hit_maker')
    if g == 'stealth':
        return _cond_for(t, 45.0)
    return _cond_for(t, 1)


def evaluate_commission(cond: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    """委托判定统一入口（engine 阶段 6.6 调用）。"""
    return _eval_cond(cond, ctx)


# ============================================================
# 生成（纯函数：所有玩家状态由 engine 传参）
# ============================================================
def _roll_margin() -> float:
    spread = TUNE['commission_margin_spread']
    mid = TUNE['commission_margin']
    return random.uniform(mid - spread, mid + spread)


def _expected_growth(country) -> float:
    """单国预期自然增长（M/周期）——与 engine 阶段 1 的基础增长同源，
    但不含网络效应 / 阻止惩罚（未来状态不可预测，取保守基准）。"""
    cfg = country.config
    return (cfg.population_m * TUNE['growth_base'] * cfg.tech_adoption
            * AGE_STRUCTURE_BONUS[cfg.age_structure])


def _expected_steal(countries) -> float:
    """当前经济下的预期单周期偷算力（与 engine 阶段 2 同源，取基准比例）。"""
    total = 0.0
    for c in countries:
        if c.unlocked and c.downloads_m > 0:
            active_users = c.downloads_m * TUNE['active_user_ratio']
            total += (active_users * TUNE['compute_per_user']
                      * TUNE['stealth_ratio_base'] * TUNE['compute_scale'])
    return total


def _pen_candidates(countries) -> list:
    """C1 目标国过滤（设计稿 §1.2，防孤岛死单）：
    「已解锁且未饱和」或「锁定但 ≥1 个已解锁邻国」。"""
    cands = []
    for c in countries:
        if c.unlocked:
            if c.penetration_rate < TUNE['penetration_saturated']:
                cands.append(c)
        else:
            if any(o.unlocked for o in countries
                   if o.config.code in c.config.neighbors):
                cands.append(c)
    return cands


def _pick_skill(window: int, unlocked_skills, avoid_skill) -> Optional[str]:
    """C4 技能选择：避开上一条委托的技能；
    校验 K ≤ floor(窗口 / 冷却) 且冷却必须 < 窗口（防软锁）。"""
    cands = [s for s in sorted(unlocked_skills)
             if s != avoid_skill and window // SKILLS[s].cooldown >= 1]
    return random.choice(cands) if cands else None


def _stealth_cap(margin: float) -> float:
    """C5 怀疑度上限：难度随机量归一化后映射到 [cap-range, cap]。"""
    t5 = TEMPLATE_BY_ID['C5']
    spread = TUNE['commission_margin_spread']
    lo = TUNE['commission_margin'] - spread
    span = 2.0 * spread
    f = 0.0 if span <= 0 else min(max((margin - lo) / span, 0.0), 1.0)
    return t5['stealth_cap'] - t5['stealth_range'] * f


def _build_instance(t, countries, unlocked_skills, compute_earned_total,
                    avoid_skill) -> Optional[CommissionState]:
    """为单个模板构造实例；不可行（无合格目标 / 技能）返回 None。"""
    goal = t['goal']
    window = t['window']
    margin = _roll_margin()
    target_country = None
    skill_id = None

    if goal == 'pen':
        cands = _pen_candidates(countries)
        if not cands:
            return None
        picked = random.choice(cands)
        target_country = picked.config.code
        target = (_expected_growth(picked) * window * margin
                  / picked.config.population_m)
        cond = _cond_for(t, target)
    elif goal == 'downloads':
        unlocked = [c for c in countries if c.unlocked]
        if not unlocked:
            return None
        target = sum(_expected_growth(c) for c in unlocked) * window * margin
        cond = _cond_for(t, target)
    elif goal == 'compute':
        target = _expected_steal(countries) * window * margin
        cond = _cond_for(t, target)
    elif goal == 'skill':
        skill_id = _pick_skill(window, unlocked_skills, avoid_skill)
        if skill_id is None:
            return None
        # K = floor(窗口 / 冷却)，上限 3（设计稿「K=2-3 静态」），下限 1
        target = min(max(window // SKILLS[skill_id].cooldown, 1), 3)
        cond = _cond_for(t, target, skill_id=skill_id)
    elif goal == 'stealth':
        target = _stealth_cap(margin)
        cond = _cond_for(t, target)
    else:  # unlock
        target = 1.0
        cond = _cond_for(t, target)

    return CommissionState(
        uid=_new_uid(), template_id=t['id'], goal=goal,
        icon=t['icon'], name_zh=t['name_zh'], name_en=t['name_en'],
        window=window, reward_mult=t['reward_mult'], offered_tick=0,
        target_country=target_country, skill_id=skill_id,
        target_value=target, cond=cond,
        sus_relief=t.get('sus_relief', 0.0))


def generate_offer(countries, unlocked_skills, recent_templates,
                   compute_earned_total,
                   avoid_skill: Optional[str] = None) -> Optional[CommissionState]:
    """尝试生成一条委托；无可行模板返回 None。

    Args:
        countries: engine.player_countries（CountryState 列表，鸭子类型）。
        unlocked_skills: 玩家已解锁技能 id 集合。
        recent_templates: 最近 2 个生成位用掉的模板 id（防刷同款）。
        compute_earned_total: 玩家累计偷算力（C3 自标定基准）。
        avoid_skill: C4 要避开的上一条委托技能。
    """
    recent = set(recent_templates)
    avail = [t for t in COMMISSION_TEMPLATES if t['id'] not in recent]
    random.shuffle(avail)
    for t in avail:
        com = _build_instance(t, countries, unlocked_skills,
                              compute_earned_total, avoid_skill)
        if com is not None:
            return com
    return None


def compute_reward(tick_accepted: int, reward_mult: float) -> float:
    """完成奖励 = base × (1 + ramp × 接单周期) × 模板系数（设计稿 §1.1/§1.4）。"""
    return (TUNE['commission_reward_compute_base']
            * (1 + TUNE['commission_reward_ramp'] * tick_accepted)
            * reward_mult)


# ============================================================
# 自检
# ============================================================
if __name__ == '__main__':
    random.seed(7)
    print(f"[commissions] 模板 {len(COMMISSION_TEMPLATES)} 条")
    for t in COMMISSION_TEMPLATES:
        c = sample_cond(t)
        print(f"  {t['id']} {t['name_zh']:<6} goal={t['goal']:<9} "
              f"window={t['window']:>2} 奖励×{t['reward_mult']}  cond={c}")

    errs = []
    for t in COMMISSION_TEMPLATES:
        for k in set(__import__('conditions').collect_keys(sample_cond(t))):
            if k.split('.')[0] not in COND_CTX_KEYS:
                errs.append(f"{t['id']}: 未知 ctx 字段 {k}")
    print(f"  cond 字段交叉校验：{len(errs)} 个问题"
          + ('' if not errs else f" → {errs}"))

    # 生成冒烟：假国家状态（鸭子类型，不依赖 engine）
    class _Cfg:
        def __init__(s, code, pop, adoption, age, neighbors):
            s.code, s.population_m = code, pop
            s.tech_adoption, s.age_structure = adoption, age
            s.neighbors = neighbors

    class _C:
        def __init__(s, cfg, unlocked, dl):
            s.config, s.unlocked, s.downloads_m = cfg, unlocked, dl

        @property
        def penetration_rate(s):
            return s.downloads_m / s.config.population_m

    countries = [_C(_Cfg('CN', 1400, 0.7, 'young', ['XX']), True, 50.0),
                 _C(_Cfg('XX', 100, 0.5, 'mature', ['CN']), False, 0.0)]
    got = []
    for i in range(30):
        com = generate_offer(countries, {'push_song', 'stealth'},
                             [], 500.0, avoid_skill=None)
        if com is not None:
            got.append(com)
    print(f"  连续 30 次生成（无冷却限制）成功 {len(got)} 条："
          + ", ".join(f"{c.template_id}" for c in got[:8]) + " …")
    assert got, "生成不应全部失败"
    print("[commissions] 自检通过")
