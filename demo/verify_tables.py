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
  [6] 分层依赖正确（低层不 import 高层；运行时模块全量登记，
      未定级也未豁免的新模块直接报错 —— P1-8）

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
      f"{len(data.SKILLS)}/{len(data.SKILLS)}")

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

# —— 分层表（P1-8 扩容：22 → 31，运行时模块全量登记）——
# 层级含义：
#   0   纯逻辑零依赖（条件求值器 / 平衡参数表 / 文案表）
#   1   基础层（静态数据表、基础渲染组件、资源与音频服务）
#   2   领域规则表（玩法子系统纯数据 + 求值包装）
#   3   引擎核心（tick 循环 / 状态机；不得触碰任何 UI 渲染组件）
#   4   引擎之上的服务与 v4 组件库
#   5-9 UI 组件 / Mixin 分层（被依赖多者靠上）
#   10  组装层（把 Mixin 与控制器拼成 App）
# 定级依据：对 demo/*.py 全量 import 扫描，「被依赖越多越底层」。
LAYERS = {
    # L0 纯逻辑：零项目依赖
    'conditions.py':      0,
    'balance.py':         0,
    'onboarding.py':      0,   # T03：首局节奏开关（纯 TUNE 读取，零项目依赖）
    'i18n.py':            0,   # P1-8：文案表，零项目依赖；engine(L3) 引用属合法
                               #       逻辑依赖（此前不在白名单导致违规漏报，现按定级放行）
    'challenge.py':       0,   # T13：挑战码编解码 + 战绩账本（只依赖标准库）。
                               #       刻意不 import save_manager —— 账本目录由调用方
                               #       传入，保持 L0 零项目依赖，也不与 L4 成环
    'origins.py':         0,   # T16：觉醒出身声明式表（只依赖 typing）。
                               #       难度 id 用字符串字面量不 import balance，
                               #       避免 L0 内部循环；balance.apply_origin 反向引用它属
                               #       运行时函数内延迟 import，不构成模块级依赖
    # L1 基础层
    'pixel_assets.py':    1,   # P1-8：自动生成素材（零 import），仅提供游程数据
    'pixel_ui.py':        1,
    'sfx.py':             1,   # P1-8：音频服务（仅 kivy、失败安全），被
                               #       ui_drop/ui_pages/ui_popups/ui_session/main 使用
    'bgm.py':             1,   # T09：背景音乐服务（两态循环 + 交叉淡出），
                               #       与 sfx 同级；被 ui_input/ui_session/main 使用
    'world_map.py':       1,   # P1-8：地图渲染 + 地理常量，仅依赖 pixel_assets/pixel_ui；
                               #       data(L1) 同级复用其 COUNTRY_STYLES/COUNTRY_CENTERS
    'data.py':            1,
    'tech_tree.py':       1,
    'country_events.py':  1,
    'v2_events.py':       1,
    # L2 领域规则表
    'flag_draw.py':       2,   # P1-8：国旗渲染组件（依赖 pixel_assets/pixel_ui），供 ui_v4_screens 使用
    'commissions.py':     2,
    'endings.py':         2,
    'achievements.py':    2,
    # L3 引擎核心
    'engine.py':          3,
    # L4 引擎之上的服务 / v4 组件库
    # 2026-09-14：开场动画 v2 重制（10 镜 41.0s），intro.py（原 503 行 → 1300 行）
    # 按职责拆为三模块，全部同层 L4（依赖完全相同：kivy/i18n/sfx/ui_v4/pixel_ui），
    # 互相只有 intro → 其余 2 个的转发引用，同层允许。
    'intro_common.py':    4,   # 公共底座：派生色 dim/alpha/mix + INTRO_SHOTS + 常量
                               #       （零 intro 家族内依赖）
    'intro_shots.py':     4,   # IntroShotsMixin：10 镜渲染器（禁 import intro）
    'intro.py':           4,   # IntroPlayer 核心（生命周期/跳过/氛围/摄像机）+ 转发；
                               #       不 import 引擎，可独立实例化；播放与否由 main
                               #       按 player.intro_seen 判定（存档 v4 新字段）
    'save_manager.py':    4,   # P1-8：序列化整局需读 commissions(L2)/engine(L3) 状态
                               #       （函数内延迟 import 解循环），不是基础层，置其上
    'ui_v4.py':           4,
    # L5-9 UI 组件 / Mixin
    # 2026-09-13：ui_v4_screens.py（2327 行，长期占白名单）按职责拆为 6 个模块，
    # 全部同层 L5（依赖完全相同：ui_v4/pixel_ui/i18n/sfx/origins/flag_draw），
    # 互相之间只有 screens → 其余 5 个的转发引用，同层允许。
    'ui_v4_common.py':    5,   # 公共底座：UiStats + small_btn（零 ui_v4_* 依赖）
    'ui_v4_panels.py':    5,   # 浮层/抽屉：InspectorPanel / DropPreview / LogDrawer
    'ui_v4_cards.py':     5,   # 页面内重复单元：SkillPageCard / SlotRow / LinkBar / LvRow / BranchCard
    'ui_v4_canvas.py':    5,   # S06 科技树自绘节点网络图：TechNode / TechCanvas
    'ui_v4_syspages.py':  5,   # 非对局全屏页：HelpPage / SettingsPage / OriginPage
    'ui_v4_screens.py':   5,   # 对局全屏页 SkillPage / TechPage / AchPage + 家族转发入口
    'ui_shared.py':       6,
    'ui_fx.py':           7,   # P1-8：动效层（依赖 ui_shared/pixel_ui），被 ui_drop/ui_input 延迟调用
    'cursor_fx.py':       7,   # 2026-09-13：光标语义层（只依赖 kivy Window，零项目依赖，
                               #       与 ui_fx/ui_modal 同级；由 main 在 GameUI/MainMenu 装配）
    'ui_modal.py':        7,
    'ui_hud.py':          8,
    'ui_pages.py':        9,
    'ui_drop.py':         9,
    'ui_popups.py':       9,
    'ui_session.py':      9,
    'ui_input.py':        9,
    'ui_commissions.py':  9,   # P1-8：委托面板 Mixin（依赖 ui_hud/ui_modal），与 ui_input 同级互引合法
    # L10 组装层
    'main.py':           10,
    'tutorial.py':       10,  # P1-8：引导控制器（依赖 ui_modal/save_manager/engine）；
                              #       TYPE_CHECKING 引用 main.GameUI 属静态类型标注而非
                              #       运行时依赖，故与 main 同为组装层
}

# —— 显式豁免清单（不进 LAYERS 也不算未纳管；逐项注明理由，不做无声放行）——
EXEMPT_MODULES = {
    'perf.py':         'P1-3 性能探针，刻意保持零项目依赖（见其 docstring），由 main/工具按需 import',
    'balance_sim.py':  '平衡模拟 CLI 工具（argparse 驱动），非运行时模块',
    'thresholds.py':   '自动试玩阈值表（balance_sim 工具配套，非运行时模块）',
    'perf_stress.py':  '压测工具脚本，非运行时模块',
}
# 前缀豁免：测试脚本 / 校验脚本 / 截图工具 / 下划线开头的临时探针（如 _probe_clock.py）
# —— 测试与工具类文件本就不该进 LAYERS，它们属于开发期基础设施。
EXEMPT_PREFIXES = ('test_', 'verify_', 'make_screenshots', '_')

# 死键：LAYERS 里登记但文件已不存在（改名/删除后忘了同步登记表）
dead_layers = [fn for fn in LAYERS
               if not os.path.exists(os.path.join(HERE, fn))]
check('LAYERS 登记的模块全部存在（无死键）', not dead_layers,
      f"缺失：{dead_layers}" if dead_layers else f"{len(LAYERS)} 个登记项")

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

# engine.py 专项规则（P1-8，替代旧的 5 模块硬编码白名单）：
# 纯逻辑核心只允许依赖「逻辑层」= L≤3 且不在 UI 渲染禁止集。
# i18n 已定级 L0 属逻辑层 —— engine 用它无需开洞；world_map/flag_draw
# 层级虽低（L1/L2）但属 UI 渲染组件，显式列入禁止集。
ENGINE_UI_FORBIDDEN = {
    'pixel_ui',    # UI 渲染基础组件（层级低但属 UI，引擎不得引用）
    'world_map',   # 地图渲染组件
    'flag_draw',   # 国旗渲染组件
}
_engine_allowed = ({fn[:-3] for fn, lv in LAYERS.items() if lv <= 3}
                   - ENGINE_UI_FORBIDDEN)
engine_src = io.open(os.path.join(HERE, 'engine.py'), encoding='utf-8').read()
bad_engine = sorted({m.group(1) for m in
                     re.finditer(r'^\s*(?:from|import)\s+([A-Za-z_][\w]*)',
                                 engine_src, re.M)
                     if f"{m.group(1)}.py" in LAYERS
                     and m.group(1) not in _engine_allowed})
check('engine.py 仅依赖逻辑层（L≤3 且非 UI 渲染组件）', not bad_engine,
      f"违规：{bad_engine}" if bad_engine else 'i18n 为 L0 文案表，合法依赖')

# P1-8 新增：未纳管模块断言 —— demo/*.py 凡不在 LAYERS 又不在豁免清单的，
# 一律报错。目的：新增模块必须显式定级或显式豁免，不允许再"裸奔"
# （游离于分层检查之外，反向依赖无人报警）。
untracked = [f for f in sorted(os.listdir(HERE))
             if f.endswith('.py') and f not in LAYERS
             and f not in EXEMPT_MODULES
             and not f.startswith(EXEMPT_PREFIXES)]
check('demo/*.py 全部已定级或显式豁免（无未纳管模块）', not untracked,
      f"未纳管：{untracked}" if untracked else
      f"{len(LAYERS)} 定级 + {len(EXEMPT_MODULES)} 工具豁免 + 前缀规则{EXEMPT_PREFIXES}")


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
# [8] 单文件 800 行守卫（P2-1：只做守卫，不做拆分）
# ============================================================
section("[8] 单文件行数 ≤ 800（P2-1 守卫）")

# 规则（与 CONTRIBUTING.md「单文件 ≤800 行」配套的自动守卫）：
#   - 任何 demo/*.py 默认硬限 800 行 —— 新增代码文件必须 ≤800 行；
#   - 存量超限文件进入下面的白名单，行数**冻结在登记值**：只许变小、
#     不许变大，多 1 行（哪怕一个空行）都报错；
#   - 白名单登记的是本守卫落地当日的实测行数，注明超限原因；
#     拆分是独立排期的重构工作（8 人时级），本轮明确不做。
#   - 再登记约定（P2-3 起）：经主理人授权的功能轮次触碰白名单文件时，
#     随该次改动再登记新实测行数并注明日期与事由 —— 不是放开冻结，
#     而是把"每次放行"显式留痕。
FILE_LINE_LIMIT = 800
LINE_LIMIT_WHITELIST = {          # 文件: 冻结行数（登记日 2025-09-11 实测）
    'pixel_assets.py':   2353,    # 2026-09-12 再登记（原 2352）：台湾归属修正，gen_pixel_map.py 并入 6 格致游程换行 +1；自动生成的游程素材数据，重构 = 换生成器
    # 'ui_v4_screens.py' 已于 2026-09-13 拆分为 6 个模块（common/panels/cards/
    #   canvas/syspages/screens，各自 267~532 行），不再超限 → 移出白名单。
    #   若后续任一拆分模块涨过 800 行，需按「再登记约定」显式留痕后重新登记。
'ui_v4.py':          1995,    # 2026-09-14 再登记（原 1980）：PxChip Clock 死循环修复
                                  #    —— texture_size 正反馈链改为 Clock.create_trigger
                                  #    debounce，每帧最多合并一次 _resize；进局后
                                  #    主循环从「每帧 941 条 CRITICAL」降回 0 条
    'engine.py':         1741,    # 2026-09-14 再登记（原 1739）：开场动画 v2 持久化
                                  #    PlayerState.intro_seen 字段（+2 行）
    'main.py':           1503,    # 2026-09-14 再登记（原 1502）：对局内 Esc 兜底改为
                                  #    「暂停 + 打开设置页」（GameUI._pause_menu 标记 +1 行）
                                  #    开场动画 v2 持久化接线（start_load_game 补播判定 +
                                  #    _play_intro_then/_finish_intro_and_enter + _enter_game 置位）
                                  # 'main.py' 旧值 1455（T16 出身流程重排）／1377（T13 挑战码导入）
    'i18n.py':           1387,    # 2026-09-14 再登记（原 1381）：右侧预览面板兜底文案
                                  #    sk_preview_empty / sk_preview_missing ×2 语
                                  #    （原 1381：技能完整介绍 sk_full_* + sk_detail_*
                                  #     精简为单行）
    'ui_hud.py':          916,    # 2026-09-14 再登记（原 908）：顶栏火花线按指标语义着色
                                  #    （_SPARK_HEX 字典 + _stat 传 fill_hex，算力=黄/下载=粉/
                                  #     怀疑度=红/解锁国=青，修复「四根全青无法区分涨落」）
}

line_violations = []
for _f in sorted(os.listdir(HERE)):
    if not _f.endswith('.py'):
        continue
    with io.open(os.path.join(HERE, _f), encoding='utf-8',
                 errors='replace') as _fh:
        _n = sum(1 for _ in _fh)
    _cap = LINE_LIMIT_WHITELIST.get(_f, FILE_LINE_LIMIT)
    if _n > _cap:
        line_violations.append(f"{_f}: {_n} 行 > 上限 {_cap}"
                               + ("（白名单冻结值被突破！）" if _f in LINE_LIMIT_WHITELIST else ""))
check('demo/*.py 行数全部不超上限（存量白名单冻结在登记值）', not line_violations,
      f"{len(line_violations)} 处：{line_violations[:3]}" if line_violations else
      f"{len(LINE_LIMIT_WHITELIST)} 个存量白名单冻结 + 其余硬限 {FILE_LINE_LIMIT} 行")
for v in line_violations:
    print(f"         · {v}")


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
