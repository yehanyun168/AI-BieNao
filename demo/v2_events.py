"""
v2_events.py - v2 事件库（37 条）适配器

把 v2/events.json 的「选择型事件」接进 demo 引擎。原 v2 事件模型与 demo
不同，本模块负责三件事：

  1. 国家映射：v2 是 20 国，demo 合并为 12 个区块
       DE/GB/FR/IT/ES → WEU（西欧）      RU/PL/UA → EEU（东欧）
       CA/MX → US（北美）   AR → BR（南美）   NG → ZA（撒哈拉以南）   NZ → AU（大洋洲）
  2. 科技门控映射：v2 是 5 分支 × 4 层，demo 是 6 槽位 × 3 分支
       dist→localization   rnd→capability   comp→resistance
       compute→compute     stealth→compute
       _t0 = 槽位 T0 已解锁；_t1/_t2/_t3 = 该槽位任一分支达到对应等级
  3. 效果解析：v2 用 "10%" / "+40%" / 15 混写，统一成 (kind, value)

事件是「选择型」的（有 options），需要玩家点选，所以引擎只负责挑选，
效果由 UI 调用 resolve_choice() 后结算。
"""
import json
import os
import random
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def _candidate_event_paths() -> List[str]:
    """列出 events.json 所有可能的落点（开发态 + PyInstaller 打包态）。

    PyInstaller 打包后 __file__ 位于 bundle 内部，`../v2/events.json` 不再成立，
    所以这里按优先级枚举候选路径，由 _resolve_events_path() 逐个探测。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    cands: List[str] = []

    env = os.environ.get('AI_BIENAO_EVENTS')          # 手动覆盖（调试用）
    if env:
        cands.append(env)

    roots: List[str] = []
    meipass = getattr(sys, '_MEIPASS', None)          # 打包态的资源根目录
    if meipass:
        roots.append(meipass)
    roots.append(here)                               # 与模块同目录（打包时被一起放进来）
    roots.append(os.path.join(here, '..'))           # demo/ 的上级 = 项目根
    roots.append(os.path.join(here, '..', '..'))

    for r in roots:
        cands.append(os.path.join(r, 'events.json'))
        cands.append(os.path.join(r, 'v2', 'events.json'))
    return cands


def _resolve_events_path() -> Optional[str]:
    """返回第一个真实存在的 events.json 路径；都找不到则返回 None。"""
    for p in _candidate_event_paths():
        if p and os.path.exists(p):
            return os.path.normpath(p)
    return None


# 兼容旧引用：启动时尽力解析一次（打包态 sys._MEIPASS 在导入前已就绪）
_EVENTS_PATH = _resolve_events_path() or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'v2', 'events.json')


# ============================================================
# 映射表
# ============================================================
# 2026-09-10：demo 已拆回 20 国，与 v2 事件库的 20 国**完全对齐** → 全部恒等映射。
# 仍保留几个兜底映射，防止 v2 事件库将来新增法国/波兰等未收录国家时炸掉。
COUNTRY_MAP = {
    'CN': 'CN', 'JP': 'JP', 'KR': 'KR', 'IN': 'IN', 'ID': 'ID',
    'US': 'US', 'CA': 'CA', 'MX': 'MX',
    'BR': 'BR', 'AR': 'AR',
    'DE': 'DE', 'GB': 'GB', 'FR': 'FR', 'IT': 'IT', 'RU': 'RU',
    'NG': 'NG', 'ZA': 'ZA', 'EG': 'EG',
    'AU': 'AU', 'NZ': 'NZ',
    # 兜底：v2 若有 demo 未收录的国家，就近归到同区域
    'ES': 'FR', 'PL': 'RU', 'UA': 'RU',
}

TECH_MAP = {
    'dist': 'localization',      # 传播系 → 本地化
    'rnd': 'capability',         # 研发系 → 功能深度
    'comp': 'resistance',        # 合规系 → 抗封禁
    'compute': 'compute',        # 算力系 → 算力效率
    'stealth': 'compute',        # 隐蔽系 → 算力效率（其中的隐蔽/静默分支）
}

CATEGORY_ICON = {
    'positive': '[+]',
    'negative': '[-]',
    'crisis': '[!]',
    'chaos': '[~]',
    'narrative': '[?]',
}


# ============================================================
# 数据结构
# ============================================================
@dataclass
class V2Effect:
    type: str
    value: float = 0.0
    value_kind: str = 'abs'     # 'abs' 绝对值 / 'pct' 百分比（0.1 = 10%）
    country: str = None         # add_downloads 用（'all' 或 code）
    duration: int = 0           # add_compute_income 用
    ach_id: str = None
    ending_id: str = None


@dataclass
class V2Option:
    text: str
    effects: List[V2Effect] = field(default_factory=list)


@dataclass
class V2Event:
    id: str
    title: str
    flavor: str
    category: str
    icon: str
    weight: int
    cooldown: int
    focus: Optional[str] = None          # 已映射的 demo 国家代码
    min_downloads_m: float = 0.0         # 触发所需该国下载量（百万）
    doubt_min: float = 0.0               # 触发所需怀疑度
    progress_min: float = 0.0            # 触发所需全球渗透率
    tech_gate: Optional[Tuple[str, int]] = None   # (slot_id, level)
    options: List[V2Option] = field(default_factory=list)


# ============================================================
# 加载
# ============================================================
def _parse_value(v) -> Tuple[str, float]:
    """把 v2 的混写数值统一成 ('pct', 0.1) 或 ('abs', 15.0)"""
    if v is None:
        return ('abs', 0.0)
    if isinstance(v, str):
        s = v.strip().replace('+', '')
        if s.endswith('%'):
            return ('pct', float(s[:-1]) / 100.0)
        try:
            return ('abs', float(s))
        except ValueError:
            return ('abs', 0.0)
    return ('abs', float(v))


def load_events(path: str = None) -> List[V2Event]:
    """加载并归一化 v2 事件库"""
    path = path or _resolve_events_path()
    if not path or not os.path.exists(path):
        print("[v2_events] 警告：未找到 events.json，v2 事件库为空！"
              "（开发态应在 v2/events.json；打包态请确认已随包分发）")
        return []

    with open(path, encoding='utf-8') as f:
        raw = json.load(f)

    events: List[V2Event] = []
    for e in raw:
        trig = e.get('trigger', {})

        # 国家映射（无法映射的国家 → 降级为全球事件）
        focus_raw = trig.get('country_focus')
        focus = COUNTRY_MAP.get(focus_raw) if focus_raw else None

        # 科技门控
        tech_gate = None
        gate_raw = trig.get('tech_unlocked_min')
        if gate_raw:
            branch, _, tier = gate_raw.partition('_t')
            slot = TECH_MAP.get(branch)
            if slot:
                try:
                    tech_gate = (slot, int(tier or 0))
                except ValueError:
                    tech_gate = (slot, 0)

        # 下载量阈值：v2 单位是「万」→ demo 用「百万」
        min_dl = float(trig.get('min_downloads', 0) or 0) / 100.0

        options = []
        for o in e.get('options', []):
            effs = []
            for f in o.get('effects', []):
                kind, val = _parse_value(f.get('value'))
                effs.append(V2Effect(
                    type=f['type'],
                    value=(val if kind == 'abs' else val),
                    value_kind=kind,
                    country=COUNTRY_MAP.get(f.get('country'), f.get('country')),
                    duration=int(f.get('duration', 0) or 0),
                    ach_id=f.get('ach_id'),
                    ending_id=f.get('ending_id'),
                ))
            options.append(V2Option(text=o.get('text', ''), effects=effs))

        events.append(V2Event(
            id=e['id'],
            title=e.get('title', e['id']),
            flavor=e.get('flavor', ''),
            category=e.get('category', 'positive'),
            icon=CATEGORY_ICON.get(e.get('category', 'positive'), '[*]'),
            weight=int(e.get('weight', 10) or 10),
            cooldown=int(e.get('cooldown', 30) or 30),
            focus=focus,
            min_downloads_m=min_dl,
            doubt_min=float(trig.get('doubt_min', 0) or 0),
            progress_min=float(trig.get('global_progress_min', 0) or 0),
            tech_gate=tech_gate,
            options=options,
        ))
    return events


# 模块级缓存（只解析一次）
EVENTS: List[V2Event] = load_events()


# ============================================================
# 触发判定
# ============================================================
def _tech_gate_ok(tech, gate: Tuple[str, int]) -> bool:
    slot_id, level = gate
    if not tech.t0_unlocked.get(slot_id, False):
        return False
    if level <= 0:
        return True
    # 该槽位任一分支达到 level 级即可
    from tech_tree import SLOT_MAP
    slot = SLOT_MAP.get(slot_id)
    if not slot:
        return True
    return any(tech.branch_levels.get(b.branch_id, 0) >= level
               for b in slot.branches)


def is_eligible(evt: V2Event, ctx: Dict) -> bool:
    """判断事件是否满足触发条件"""
    if evt.progress_min and ctx['penetration'] < evt.progress_min:
        return False
    if evt.doubt_min and ctx['suspicion'] < evt.doubt_min:
        return False
    if evt.tech_gate and not _tech_gate_ok(ctx['tech'], evt.tech_gate):
        return False
    if evt.focus:
        country = ctx['countries'].get(evt.focus)
        if country is None or not country.unlocked:
            return False
        if evt.min_downloads_m and country.downloads_m < evt.min_downloads_m:
            return False
    return True


def pick_event(ctx: Dict, cooldowns: Dict[str, int],
               rng: random.Random = None) -> Optional[V2Event]:
    """按权重挑一个可触发且不在冷却中的事件"""
    rng = rng or random
    pool = []
    seen_events = set(ctx.get('seen_events', ()))
    for evt in EVENTS:
        if evt.id in seen_events:
            continue
        if cooldowns.get(evt.id, 0) > 0:
            continue
        if not is_eligible(evt, ctx):
            continue
        pool.extend([evt] * max(1, evt.weight // 5 + 1))
    if not pool:
        return None
    return rng.choice(pool)


def tick_cooldowns(cooldowns: Dict[str, float], dt_seconds: float = 1.0) -> None:
    """每周期按秒递减事件冷却（dt_seconds 默认 1.0 保持模拟语义）"""
    for k in list(cooldowns):
        cooldowns[k] -= dt_seconds
        if cooldowns[k] <= 0:
            del cooldowns[k]


if __name__ == "__main__":
    print(f"[v2_events] 已加载 {len(EVENTS)} 条事件（源 {os.path.normpath(_EVENTS_PATH)}）")
    from collections import Counter
    print(" 分类:", dict(Counter(e.category for e in EVENTS)))
    print(" 归属:", dict(Counter(e.focus for e in EVENTS)))
    no_opt = [e.id for e in EVENTS if not e.options]
    print(f" 无选项事件: {no_opt or '无'}")
    print("\n 示例：")
    for e in EVENTS[:2]:
        print(f"  {e.icon} {e.title}  [focus={e.focus} gate={e.tech_gate}]")
        for o in e.options:
            print(f"     - {o.text}")
            for f in o.effects:
                print(f"         {f.type} {f.value_kind}:{f.value} "
                      f"country={f.country}")
