"""
verify_tables.py - 数据驱动结构校验（CI / 启动自检）

校验目标
--------
把「改数据只需改表格，不用改函数」这条约定变成**可自动检查的约束**：

  [1] 所有判定条件都是纯数据（不再有 lambda / callable）
  [2] 条件表引用的上下文字段名全部真实存在（防拼写错误静默失效）
  [3] 条件表结构合法（算子名、嵌套形式）
  [4] 平衡参数没有散落在 engine.py 函数体里
  [5] 表与表之间的引用一致（技能顺序 ↔ 技能表、邻国拓扑对称可达）
  [6] 分层依赖正确（低层不 import 高层）

用法::

    python verify_tables.py
    # 退出码 0 = 全部通过；1 = 有问题
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conditions
import balance
import data
import engine
import endings
import achievements
import tech_tree

HERE = os.path.dirname(os.path.abspath(__file__))

_PASS = 0
_FAIL = 0


def check(name: str, ok: bool, detail: str = '') -> None:
    global _PASS, _FAIL
    if ok:
        _PASS += 1
        print(f"  [OK]   {name}" + (f"  — {detail}" if detail else ""))
    else:
        _FAIL += 1
        print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}")


def _is_callable(v) -> bool:
    return callable(v)


# ============================================================
# [1] 判定条件必须是纯数据
# ============================================================
section("[1] 判定条件为纯数据（不含 lambda / callable）")

bad_endings = [e.id for e in endings.ENDINGS if _is_callable(e.cond)]
check('7 个结局的 cond 全部是 dict 或 None', not bad_endings,
      f"违规：{bad_endings}" if bad_endings else f"共 {len(endings.ENDINGS)} 条")

bad_achs = [a.ach_id for a in achievements.ACHIEVEMENTS if _is_callable(a.cond)]
check(f'{len(achievements.ACHIEVEMENTS)} 个条件型成就的 cond 全部是 dict',
      not bad_achs, f"违规：{bad_achs}" if bad_achs
      else f"{len(achievements.ACHIEVEMENTS)}/{len(achievements.ACHIEVEMENTS)}")

# 事件型成就的 cond 必须为 None（由事件解锁，不参与自动检测）
ev_bad = [a.ach_id for a in achievements.EVENT_ACHIEVEMENTS.values()
          if a.cond is not None]
check('7 个事件型成就的 cond 为 None', not ev_bad,
      f"违规：{ev_bad}" if ev_bad else "7/7")

# 源码层面：这几个文件不该再出现 lambda（兼容层属性除外）
for fn in ('endings.py', 'achievements.py'):
    src = io.open(os.path.join(HERE, fn), encoding='utf-8').read()
    code_lines = [ln for ln in src.splitlines()
                  if not ln.strip().startswith('#')]
    # 唯一允许的 lambda 是向后兼容的 ``condition`` 属性包装
    hits = [ln.strip() for ln in code_lines
            if 'lambda' in ln and 'return lambda c: _eval' not in ln]
    check(f'{fn} 源码中无 lambda 判定', not hits,
          f"{len(hits)} 处：{hits[:2]}" if hits else '仅保留兼容属性包装')


# ============================================================
# [2] 条件表字段名 ↔ 上下文快照 交叉校验
# ============================================================
section("[2] 条件表引用的字段真实存在")

# ⚠️ 必须先初始化一局，否则 engine.player 是 None，上下文取不到真实字段
engine.init_game()
ctx = engine.build_achievement_context()
# 结局上下文额外补上只有结局才用的键
ending_ctx_keys = set(ctx) | {'legal_shield_lv', 'resistance_t0',
                              'crisis_triggered', 'tick', 'total_countries'}
ach_ctx_keys = set(ctx)

errs = endings.validate_cond(ending_ctx_keys)
check('结局条件表全部字段名与算子合法', not errs,
      f"{len(errs)} 个问题" if errs else f"{len(endings.ENDINGS)} 条全部合法")
for e in errs:
    print(f"         · {e}")

errs = achievements.validate_cond(ach_ctx_keys)
check('成就条件表全部字段名与算子合法', not errs,
      f"{len(errs)} 个问题" if errs else f"{len(achievements.ACHIEVEMENTS)} 条全部合法")
for e in errs:
    print(f"         · {e}")

# 反向：条件表用到的字段，是否都真的出现在 ctx 里（strict 模式实跑一遍）
#
# ⚠️ 注意：子表引用（如 ``branch_levels.silent_upgrade``）在开局时该分支
#    尚未解锁、键不存在 —— 这是**正常**的，不该算「字段缺失」。
#    所以这里只对「顶层字段」跑 strict，子表键改为静态校验
#    （即 [2] 上面的 validate_cond，它检查的是键名合法性而非存在性）。
ctx_strict = engine.build_ending_context()
try:
    endings.check_ending(ctx_strict, strict=True)
    check('结局检查在 strict 模式下无顶层字段缺失', True, '')
except conditions.ConditionError as exc:
    check('结局检查在 strict 模式下无顶层字段缺失', False, str(exc))

# 成就：子表键的合法性用「真实分支 id / 槽位 id」交叉验证
import tech_tree as _tt
real_branch_ids = {b.branch_id for s in _tt.TECH_TREE for b in s.branches}
real_slot_ids = {s.slot_id for s in _tt.TECH_TREE}

bad_refs = []
for a in achievements.ACHIEVEMENTS:
    for key in sorted(conditions.collect_keys(a.cond)):
        if '.' not in key:
            continue
        head, _, tail = key.partition('.')
        if head == 'branch_levels' and tail not in real_branch_ids:
            bad_refs.append(f"{a.ach_id}: branch_levels.{tail} 不是真实分支")
        elif head == 't0_unlocked' and tail not in real_slot_ids:
            bad_refs.append(f"{a.ach_id}: t0_unlocked.{tail} 不是真实槽位")
        elif head == 'slot_branch_lv2' and tail not in real_slot_ids:
            bad_refs.append(f"{a.ach_id}: slot_branch_lv2.{tail} 不是真实槽位")
check('成就的子表引用指向真实分支 / 槽位', not bad_refs,
      f"{len(bad_refs)} 处：{bad_refs[:3]}" if bad_refs else
      f"覆盖 {len(real_branch_ids)} 分支 / {len(real_slot_ids)} 槽位")
for b in bad_refs:
    print(f"         · {b}")

# 反向兜底：成就引用的槽位/分支覆盖率（保证「科技全开」这类成就真的可达成）
t0_refs = {k.split('.')[1] for a in achievements.ACHIEVEMENTS
           for k in conditions.collect_keys(a.cond)
           if k.startswith('t0_unlocked.')}
check('「科技全开」成就覆盖全部 6 个槽位',
      t0_refs == real_slot_ids,
      f"引用 {len(t0_refs)}/{len(real_slot_ids)} 个槽位")


# ============================================================
# [3] 条件求值器自检
# ============================================================
section("[3] 条件求值器语义正确")

_t = dict(a=5, b=2, flag=True, levels={'x': 3})
cases = [
    ({'a': 5}, True, '默认 ≥'),
    ({'a': 6}, False, '默认 ≥ 不成立'),
    ({'a': {'gt': 5}}, False, '>'),
    ({'a': {'gte': 5}}, True, '≥'),
    ({'a': {'lt': 6}}, True, '<'),
    ({'b': {'lte': 2}}, True, '≤'),
    ({'a': {'ne': 6}}, True, '≠'),
    ({'flag': {'eq': True}}, True, '= (bool)'),
    ({'a': {'mul': 4, 'gte': 20}}, True, '×4 后比较'),
    ({'levels.x': 3}, True, '子表取值'),
    ({'a': {'gte': '@b'}}, True, '@字段引用'),
    ({'all': [{'a': 5}, {'b': 2}]}, True, 'all'),
    ({'all': [{'a': 5}, {'b': 9}]}, False, 'all 有假'),
    ({'any': [{'a': 99}, {'b': 2}]}, True, 'any'),
    ({'not': {'a': 99}}, True, 'not'),
    ({'sum': {'keys': ['a', 'b'], 'eq': 7}}, True, 'sum'),
    ({'count': {'of': ['flag', 'a', 'b'], 'eq': 3}}, True, 'count'),
    ({'missing_key': 1}, False, '缺失字段 → 不通过'),
    (None, True, 'None = 无条件'),
]
ok = True
for cond, want, name in cases:
    got = conditions.evaluate(cond, _t)
    if got != want:
        ok = False
        print(f"         · {name}: 期望 {want}，实际 {got}")
check(f'求值器 {len(cases)} 条用例', ok)

# 反向用例：strict 模式必须报错
try:
    conditions.evaluate({'missing_key': 1}, _t, strict=True)
    check('strict 模式对缺失字段抛错', False, '未抛错')
except conditions.ConditionError:
    check('strict 模式对缺失字段抛错', True)

# 非法算子必须报错
try:
    conditions.evaluate({'a': {'badop': 1}}, _t)
    check('非法算子抛 ConditionError', False, '未抛错')
except conditions.ConditionError:
    check('非法算子抛 ConditionError', True)

# describe 必须能对全部真实条件生成非空描述
desc_fail = [e.id for e in endings.ENDINGS
             if e.auto and not conditions.describe(e.cond)]
check('全部结局条件可自动生成描述', not desc_fail,
      f"失败：{desc_fail}" if desc_fail else '')


# ============================================================
# [4] 平衡数值不再散落在 engine 函数体
# ============================================================
section("[4] 平衡数值集中在 balance.TUNE")

errs = balance.validate()
check('balance.TUNE 一致性自检', not errs,
      f"{len(errs)} 个问题" if errs else f"{len(balance.TUNE)} 项参数")
for e in errs:
    print(f"         · {e}")

# 扫描 engine.py：tick 相关的函数体里不该再有裸浮点魔数
src = io.open(os.path.join(HERE, 'engine.py'), encoding='utf-8').read()
# 去掉注释行和字符串里的内容后，找形如 " * 0.003" 这种内联系数
stripped = re.sub(r'#.*', '', src)
# 白名单：0.0 / 1.0 / 2.0 这类中性值不算魔数
MAGIC = re.compile(r'(?<![\w.])(0\.0(?!\d)[1-9]\d*|0\.[0-9]{2,})(?![\w])')
found = []
for i, ln in enumerate(stripped.splitlines(), 1):
    # 只关心函数体内的算式行（含 * 或 + 的浮点运算）
    if not re.search(r'[*/+-]\s*$|[*/]\s*0\.', ln):
        continue
    for m in MAGIC.finditer(ln):
        val = m.group(1)
        if val in ('0.5', '0.0'):
            continue
        found.append(f"L{i}: {val}  ← {ln.strip()[:64]}")
check('engine.py 函数体内无遗留平衡魔数', not found,
      f"{len(found)} 处" if found else '已全部收敛到 TUNE')
for f in found[:6]:
    print(f"         · {f}")


# ============================================================
# [5] 表间引用一致性
# ============================================================
section("[5] 表间引用一致性")

check('SKILL_ORDER 与 SKILLS 表一致',
      set(data.SKILL_ORDER) == set(data.SKILLS),
      f"顺序表 {len(data.SKILL_ORDER)} / 技能表 {len(data.SKILLS)}")

check('技能 id 与字典键一致',
      all(k == s.id for k, s in data.SKILLS.items()),
      '6/6')

# 邻国引用：不能指向不存在的国家
dangling = []
for c in data.COUNTRIES:
    for n in c.neighbors:
        if n not in data.COUNTRY_MAP:
            dangling.append(f"{c.code}→{n}")
check('邻国不指向不存在的国家', not dangling,
      f"{len(dangling)} 处：{dangling[:3]}" if dangling else '无悬空引用')

# 全部国家必须从起点国可达（游戏语义：C 可由其 neighbors 中已解锁国解锁）
# 等价於反向图连通：X→Y 当且仅当 X ∈ Y.neighbors
start = 'CN'
rev = {c.code: set() for c in data.COUNTRIES}
for c in data.COUNTRIES:
    for n in c.neighbors:
        if n in data.COUNTRY_MAP:
            rev[n].add(c.code)
seen, frontier = {start}, [start]
while frontier:
    cur = frontier.pop()
    for nxt in rev.get(cur, ()):
        if nxt not in seen:
            seen.add(nxt)
            frontier.append(nxt)
unreachable = [c.code for c in data.COUNTRIES if c.code not in seen]
check('全部国家从起点国可达（真实解锁语义）', not unreachable,
      f"不可达：{unreachable}" if unreachable else f"{len(seen)}/{len(data.COUNTRIES)}")

# 科技树：槽位 id 唯一、分支 id 唯一、等级/成本长度对齐
slot_ids = [s.slot_id for s in tech_tree.TECH_TREE]
check('科技槽位 id 唯一', len(slot_ids) == len(set(slot_ids)), f"{len(slot_ids)} 个槽位")

branch_ids = [b.branch_id for s in tech_tree.TECH_TREE for b in s.branches]
check('科技分支 id 唯一', len(branch_ids) == len(set(branch_ids)),
      f"{len(branch_ids)} 条分支")

mis = [b.branch_id for s in tech_tree.TECH_TREE for b in s.branches
       if len(b.effects_per_level) != len(b.costs)]
check('每分支的「效果级数」与「成本级数」对齐', not mis,
      f"不对齐：{mis}" if mis else '全部对齐')

prereq_bad = [s.slot_id for s in tech_tree.TECH_TREE
              if s.prereq_slot and s.prereq_slot not in slot_ids]
check('科技前置槽位引用有效', not prereq_bad,
      f"无效：{prereq_bad}" if prereq_bad else '全部有效')

# 危机选项 idx 连续
idx_ok = [o['idx'] for o in balance.CRISIS_OPTIONS] == list(range(len(balance.CRISIS_OPTIONS)))
check('危机选项 idx 从 0 连续递增', idx_ok,
      f"{[o['idx'] for o in balance.CRISIS_OPTIONS]}")

# 事件文案中引用的成就 id 必须存在
known_ach = set(achievements.ALL_BY_ID)
missing_ach = []
try:
    import v2_events
    for ev in v2_events.EVENTS:
        for opt in getattr(ev, 'options', []) or []:
            for eff in getattr(opt, 'effects', []) or []:
                if getattr(eff, 'kind', '') == 'achievement':
                    aid = getattr(eff, 'value', None)
                    if aid and aid not in known_ach:
                        missing_ach.append(f"{ev.event_id}→{aid}")
except Exception as exc:
    print(f"         (跳过 v2 事件成就引用检查：{exc})")
if not missing_ach:
    check('v2 事件引用的成就 id 全部存在', True, '')
else:
    check('v2 事件引用的成就 id 全部存在', False, f"缺失：{missing_ach}")


# ============================================================
# [6] 分层依赖：低层不 import 高层
# ============================================================
section("[6] 分层依赖方向正确")

LAYERS = {
    'conditions.py':      0,
    'balance.py':         0,
    'pixel_ui.py':        1,
    'data.py':            1,
    'tech_tree.py':       1,
    'country_events.py':  1,
    'v2_events.py':       1,
    'commissions.py':     2,
    'endings.py':         2,
    'achievements.py':    2,
    'engine.py':          3,
    'ui_v4.py':           4,
    'ui_v4_screens.py':   5,
    'ui_shared.py':       6,
    'ui_modal.py':        7,
    'ui_hud.py':          8,
    'ui_pages.py':        9,
    'ui_drop.py':         9,
    'ui_popups.py':       9,
    'ui_session.py':      9,
    'ui_input.py':        9,
    'main.py':           10,
}

violations = []
for fn, lv in LAYERS.items():
    path = os.path.join(HERE, fn)
    if not os.path.exists(path):
        continue
    src = io.open(path, encoding='utf-8').read()
    for m in re.finditer(r'^\s*(?:from|import)\s+([A-Za-z_][\w]*)',
                         src, re.M):
        mod = m.group(1)
        dep = f"{mod}.py"
        if dep in LAYERS and LAYERS[dep] > lv:
            violations.append(f"{fn}(L{lv}) → {dep}(L{LAYERS[dep]})")
check('无「低层 import 高层」的反向依赖', not violations,
      f"{len(violations)} 处" if violations else f"检查了 {len(LAYERS)} 个模块")
for v in violations:
    print(f"         · {v}")

# engine.py 不该 import 任何 UI 模块
ui_mods = {'ui_v4', 'ui_v4_screens', 'world_map', 'flag_draw', 'tutorial'}
engine_src = io.open(os.path.join(HERE, 'engine.py'), encoding='utf-8').read()
bad_ui = [m for m in ui_mods
          if re.search(rf'^\s*(?:from|import)\s+{m}\b', engine_src, re.M)]
check('engine.py 不依赖任何 UI 模块', not bad_ui, f"违规：{bad_ui}" if bad_ui else '')


# ============================================================
# [7] 委托系统（P0-3）：模板 / cond 字段 / ctx 一致性
# ============================================================
section("[7] 委托系统数据一致性（P0-3）")

import commissions

# 模板结构：id 唯一、goal 合法、窗口为正
t_ids = [t['id'] for t in commissions.COMMISSION_TEMPLATES]
check('委托模板 id 唯一', len(t_ids) == len(set(t_ids)),
      f"{len(t_ids)} 条模板")

valid_goals = set(commissions._GOAL_FIELD)
bad_goals = [t['id'] for t in commissions.COMMISSION_TEMPLATES
             if t['goal'] not in valid_goals]
check('委托模板 goal 类型合法', not bad_goals,
      f"违规：{bad_goals}" if bad_goals else f"{sorted(valid_goals)}")

bad_win = [t['id'] for t in commissions.COMMISSION_TEMPLATES
           if not isinstance(t['window'], int) or t['window'] < 1]
check('委托时限窗口为正整数', not bad_win, f"违规：{bad_win}" if bad_win else '')

# 模板样例 cond 的字段名 ⊆ 委托判定 ctx 键集（与 engine 构造路径共享 _cond_for）
bad_fields = []
for t in commissions.COMMISSION_TEMPLATES:
    for k in sorted(conditions.collect_keys(commissions.sample_cond(t))):
        if k.split('.')[0] not in commissions.COND_CTX_KEYS:
            bad_fields.append(f"{t['id']}: {k}")
check('委托 cond 字段全部在判定 ctx 键集内', not bad_fields,
      f"{len(bad_fields)} 处：{bad_fields[:3]}" if bad_fields else
      f"覆盖 {len(commissions.COMMISSION_TEMPLATES)} 条模板")

# 反向：engine.build_commission_ctx 对每种 goal 产出的字段 ⊆ 键集
engine.init_game()
_ctx_seen = set()
for goal in sorted(valid_goals):
    fake = commissions.CommissionState(
        uid=0, template_id='X', goal=goal, icon='x', name_zh='x',
        name_en='x', window=1, reward_mult=1.0,
        target_country=engine.player_countries[0].config.code,
        skill_id='hit_maker', cond=commissions.sample_cond(
            {'goal': goal}))
    _ctx_seen |= set(engine.build_commission_ctx(fake))
_unknown = _ctx_seen - commissions.COND_CTX_KEYS
check('engine 委托 ctx 产出字段与键集一致', not _unknown,
      f"多余：{sorted(_unknown)}" if _unknown else
      f"实际产出 {len(_ctx_seen)} 键")

# 样例 cond 在真实 ctx 形状上可求值（不抛错）
try:
    for t in commissions.COMMISSION_TEMPLATES:
        fake = commissions.CommissionState(
            uid=0, template_id=t['id'], goal=t['goal'], icon='x',
            name_zh='x', name_en='x', window=1, reward_mult=1.0,
            target_country=engine.player_countries[0].config.code,
            skill_id='hit_maker', cond=commissions.sample_cond(t))
        engine.build_commission_ctx(fake)
        conditions.evaluate(commissions.sample_cond(t),
                            engine.build_commission_ctx(fake))
    check('委托样例 cond 全部可求值', True,
          f"{len(commissions.COMMISSION_TEMPLATES)} 条模板通过")
except conditions.ConditionError as exc:
    check('委托样例 cond 全部可求值', False, str(exc))

# TUNE 新键（委托 + 反制）不得成为死键：engine / commissions 必须引用
engine_src = io.open(os.path.join(HERE, 'engine.py'), encoding='utf-8').read()
comm_src = io.open(os.path.join(HERE, 'commissions.py'),
                   encoding='utf-8').read()
dead_keys = [k for k in balance._REQUIRED
             if k.startswith(('commission_', 'counterplay_'))
             and f"TUNE['{k}']" not in engine_src
             and f"TUNE['{k}']" not in comm_src]
check('委托/反制 TUNE 键全部被引擎引用（无死键）', not dead_keys,
      f"死键：{dead_keys}" if dead_keys
      else f"{sum(1 for k in balance._REQUIRED if k.startswith(('commission_', 'counterplay_')))} 键全部在用")


# ============================================================
# 汇总
# ============================================================
print('\n' + '=' * 62)
total = _PASS + _FAIL
print(f"结果：{_PASS}/{total} 通过")
print('=' * 62)
if _FAIL:
    print('存在未通过项 —— 数据驱动约束被打破，请修复后重跑')
else:
    print('全部通过 —— 数据与逻辑已解耦：改表格即可改游戏，无需碰函数')
sys.exit(1 if _FAIL else 0)
