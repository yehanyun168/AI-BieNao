"""
balance_sim.py - 数值平衡模拟器（调参工具，不参与游戏运行）

用途：用「自动玩家」批量跑 N 局，统计结局分布 / 解锁节奏 / 渗透率曲线，
      用于验证数值调整是否合理，避免手动试玩半天才发现爆炸。

用法：
    python balance_sim.py                # 默认跑 20 个种子，每局最多 200 周期
    python balance_sim.py --seeds 50     # 跑 50 局
    python balance_sim.py --ticks 300    # 每局最多 300 周期
    python balance_sim.py --strategy compliance   # 用「合规专精」人格跑（P1-4）

自动玩家策略（模拟一个「中等水平玩家」）：
  1. 优先解锁 T0，再沿第一个可选分支升级
  2. 怀疑度 > 60 且「潜伏」可用时释放

自动玩家人格（P1-4 新增 --strategy；M0 新增 afk）：
  default    上述「中等水平玩家」，行为与历史版本逐位一致
  compliance 合规专精：开局沿前置链尽早买「抗封禁 T0」（不等危机）、
             全程不练脏技能（按 data.SKILLS.suspicion_delta > 0 判定）、
             怀疑度进入危机警戒区（距危机线 15 点）后暂停技能投放、
             深度伪装提前一档释放。其余决策（委托、常规科技）复用默认逻辑。
  afk        零操作基线（M0）：不接单 / 不点科技 / 不放技能 / 不应答危机，
             暴露「躺平即死」收网路径，为必输预测提供回测样本。

自动试玩巡检（M0 新增）：
  每 tick 做只读不变量巡检（阈值表 thresholds.py：NaN/Inf、怀疑度单周期
  净增上下限、五指标硬卡死/软停滞），并做必输预测（只标记不终止，结局
  出来后回测命中率）。巡检零 RNG / 零引擎调用，不影响逐位回归。
  --matrix 跑「策略 × 难度 × 种子」全矩阵基线，写基线 JSON + md 报告。

⚠️ 这不是 AI 最优策略 —— 它故意保持平庸，用来暴露数值问题：
   如果自动玩家 80% 都在第 30 周期前「被关停」，说明怀疑度还是太紧。
"""
import os
# Kivy 会抢先解析 argv，必须在导入任何 kivy 相关模块前关掉
os.environ.setdefault('KIVY_NO_ARGS', '1')

import argparse
import json
import math
import random
import sys
from collections import Counter, deque
from datetime import datetime

sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0])

import data  # P1-10：SUSPICION_CRISIS 走 data 的 PEP 562 动态代理
import balance  # P2-3：难度预设（TUNE 乘法，apply_difficulty 在 main 应用一次）
import origins  # T16：觉醒出身表（--origin 参数choices + init_game 透传）
import engine
import tech_tree
import thresholds  # M0：自动试玩异常判定阈值表（工具配套，非运行时模块）


def _find_branch(slot, branch_id: str):
    """按 id 在槽位分支里找一个 TechBranch（找不到返回 None）。"""
    for br in slot.branches:
        if br.branch_id == branch_id:
            return br
    return None


def auto_play(tick_report_hook=None, strategy: str = 'default'):
    """自动玩家的每周期决策

    strategy:
        'default'    —— 「中等水平玩家」，行为与历史版本逐位一致。
        'compliance' —— 合规专精人格（P1-4）：主动买抗封禁 T0、全程不练
                        脏技能、接近危机线时保守。其余决策复用默认逻辑。
        'afk'        —— 零操作基线（M0）：不接单/不点科技/不放技能/
                        不应答危机，暴露「躺平即死」收网路径。
    """
    p = engine.player

    # M0 afk：零操作基线 —— 没有任何决策点，顶部早退即可，无需策略对象
    #（策略对象重构随 M1 rush/greedy 一起做并带逐位验证）。
    if strategy == 'afk':
        return

    # 0. 委托：全部接受（P0-3；自动玩家策略是「来者不拒」）
    for com in list(p.commissions):
        if com.status == 'offered':
            engine.accept_commission(com.uid)

    # 1. 科技加点：先 T0，后分支
    #    危机应答（P0-3）：政府反制引发危机后，中等玩家的本能是先补
    #    「抗封禁」T0（成本 50，前置 capability）——被反制了才点防御，
    #    下一 tick 回到常规队列。无危机时维持深度优先不变。
    #    P1-4 compliance：合规之王要求「全程无危机 + 抗封禁 T0」，事后
    #    补买在结构上自相矛盾（买了 T0 危机已发生）——专精人格在无危机
    #    时也优先抢买。受前置链（localization→…→capability）约束，
    #    实际效果 = capability T0 一解锁立刻点抗封禁 T0。
    #    默认策略下 strategy=='compliance' 恒为 False，短路求值与原式
    #    等价，逐位回归不受影响。
    if ((strategy == 'compliance' or p.crisis_triggered)
            and not p.tech.t0_unlocked.get('resistance')):
        res_slot = tech_tree.SLOT_MAP['resistance']
        if (p.tech.can_unlock_t0('resistance')
                and p.compute >= res_slot.t0_cost):
            engine.unlock_t0('resistance')
    #    ⚠️ R16 教训：渗透 ≥40% 的「冲刺节流」（隔 tick 消费）毁局——
    #    科技停摆 → 渗透滞留 40% 区间 → 怀疑追上（关停 26.7%、合规归
    #    零），peak 反而堆不起来。AUTO「每 tick 花光」与「攒钱冲 meta」
    #    结构性矛盾，节流方案整体排除。
    for slot in tech_tree.TECH_TREE:
        if not p.tech.t0_unlocked[slot.slot_id]:
            if p.compute >= slot.t0_cost and p.tech.can_unlock_t0(slot.slot_id):
                engine.unlock_t0(slot.slot_id)
                break
        else:
            upgraded = False
            for br in slot.branches:
                lv = p.tech.branch_levels.get(br.branch_id, 0)
                if (lv < 3 and p.tech.can_upgrade_branch(slot.slot_id, br.branch_id)
                        and p.compute >= br.costs[lv]):
                    engine.upgrade_branch(slot.slot_id, br.branch_id)
                    upgraded = True
                    break
            if upgraded:
                break

    # 1b. 合规专精（P1-4 / T05）的专项加点：法律护盾优先。
    #     ⚠️ 这是 T05 定位到的核心机制缺陷 —— 「合规之王」要求 unlocked
    #     legal_shield，但默认加点顺序是「槽位序 → 分支序」，而 legal_shield
    #     是抗封禁槽位的第 2 分支。实测 200 局 compliance **零次**点进该分支
    #     （最高等级 0）：算力全被前序槽位分支吸走，而且 183/200 局在
    #     tick 40 前就结束了（局终渗透均值 35.8%），根本没有攒到 700 算力
    #     去点三级 legal_shield 的时间窗。结局因此变成结构性不可达，
    #     而不是「玩家不够努力」。
    #     专精人格的正确行为是：抗封禁 T0 一解锁就直奔法律护盾主线，
    #     不为其他分支分心（合规路线不靠下载量赢，靠不被封禁赢）。
    #     默认策略下 strategy=='compliance' 恒为 False，不进入本段，
    #     逐位回归完全不受影响。
    if strategy == 'compliance' and p.tech.t0_unlocked.get('resistance'):
        ls = _find_branch(tech_tree.SLOT_MAP['resistance'], 'legal_shield')
        lv = p.tech.branch_levels.get('legal_shield', 0)
        if (ls is not None and lv < 3
                and p.tech.can_upgrade_branch('resistance', 'legal_shield')
                and p.compute >= ls.costs[lv]):
            engine.upgrade_branch('resistance', 'legal_shield')

    # 2. 救命技能
    #    P1-4 compliance：专精人格对怀疑增速更敏感，提前一档放深度伪装
    #    （该技能零怀疑代价且压低增速 50%，早放只赚不亏）。
    if p.suspicion > (55 if strategy == 'compliance' else 60):
        engine.use_skill('stealth')
    #    ⚠️ R14 教训：bypass「无怀疑代价」是错觉——引擎怀疑公式含偷算力
    #    因子，+40% 当期偷算力 = 怀疑增速均摊 +40%，全局提前爆表
    #    （关停 33.3%、渗透均值 -9pp）。产出加速类技能不可常规化。

    # 3. 委托适配（P0-3）：有活跃「技能特训」时练习指定技能，
    #    保证自动玩家能完成委托闭环（真人玩家同理可用冷门技能刷单）。
    #    ⚠️ 仅在算力充裕（≥800）时练习：技能购买会挤占科技分支升级，
    #    贫瘠局的 T0 链推进（resistance T0 依赖横向跳过）不能被打断。
    #    ⚠️ 大修后技能真实生效（旧版效果静默丢失，练了个寂寞）：
    #    中等玩家练技能也会看怀疑度账单 —— 怀疑度 > 40 时不再练
    #    「脏技能」（怀疑增量 > 0），否则练一次赃一手，关停率爆表。
    if p.compute >= 800:
        for com in p.commissions:
            if (com.status == 'active' and com.goal == 'skill'
                    and com.skill_id in p.unlocked_skills
                    and com.skill_id not in p.skill_cooldowns):
                sk = engine.SKILLS.get(com.skill_id)
                if strategy == 'compliance':
                    # 合规专精（P1-4）：脏技能全程不练 —— 按
                    # data.SKILLS.suspicion_delta > 0 字段判定，不硬编码
                    # 技能名；怀疑度进入危机警戒区（距危机线 < 15 点）
                    # 后连干净技能也暂停投放，等待自然衰减 / 深度伪装
                    # 把怀疑压回安全区（「少投放、多等衰减」）。
                    if sk is None or sk.suspicion_delta > 0:
                        continue
                    if p.suspicion >= data.SUSPICION_CRISIS - 15:
                        continue
                elif (p.suspicion > 40 and sk is not None
                        and sk.suspicion_delta > 0):
                    continue
                if engine.use_skill(com.skill_id):
                    break


# ===================== M0 自动试玩巡检（只读，零 RNG / 零引擎调用） =====================
# 巡检只读 player / TUNE 属性并做纯计算，不改变任何游戏状态 —— default /
# compliance 的逐位回归不受影响（哈希只取 REGRESSION_FIELDS 原字段子集）。

# 矩阵维度（--matrix 用）
MATRIX_STRATEGIES = ('default', 'compliance', 'afk')
MATRIX_DIFFICULTIES = ('easy', 'normal', 'hard')
# 该策略是否有危机应答能力：决定怀疑度负向下限用哪条
#（default 仅危机后补 T0、compliance 全程无危机、afk 零操作 → 均无应答；
#  M1 rush/greedy 有主动危机应答 → True，启用 SUS_DELTA_MIN_CRISIS=-40）
STRATEGY_CRISIS_CAPABLE = {'default': False, 'compliance': False, 'afk': False}

# 逐位回归哈希字段子集（与历史版本完全一致的原字段；M0 附加字段不参与）
REGRESSION_FIELDS = ('seed', 'ending', 'ending_name', 'ticks', 'penetration',
                     'downloads_m', 'suspicion', 'compute_peak', 'unlocked',
                     'total_countries', 'crisis', 'commissions_done',
                     'commissions_failed', 'counterplay')

# 怀疑度上限（收网线 92 起 +0.5/tick 至 100 关停；TUNE 无该字段，引擎硬编码）
SUS_DEATH_LINE = 100.0

# 怀疑度单周期净增（delta）直方图分桶 —— 服务阈值实测校准（P99/P99.9）。
# 桶边界与 thresholds 阈值语义对应；非有限值单独计数。
DELTA_BINS = ('nan_inf', '<-40', '-40~-10', '-10~0', '0~10', '10~20',
              '20~45', '45~90', '90~150', '>150')


def _delta_bucket(delta: float) -> str:
    """把一个怀疑度单周期净增映射进直方图桶。"""
    if not math.isfinite(delta):
        return 'nan_inf'
    if delta < -40:
        return '<-40'
    if delta < -10:
        return '-40~-10'
    if delta < 0:
        return '-10~0'
    if delta < 10:
        return '0~10'
    if delta < 20:
        return '10~20'
    if delta < 45:
        return '20~45'
    if delta < 90:
        return '45~90'
    if delta < 150:
        return '90~150'
    return '>150'


def _observe_tick(p, prev_metrics) -> dict:
    """每 tick 末抓只读快照。

    metrics 五元组：渗透率 / 算力峰值 / 科技分支等级和 / 解锁国数 /
    委托完成+失败（TUNE 阈值表「五指标」口径）。
    stuck = 与上一 tick 相比五项 delta 全 0（首 tick 恒 False）。
    """
    metrics = (
        p.global_penetration,
        p.compute_peak,
        sum(p.tech.branch_levels.values()),
        sum(1 for c in engine.player_countries if c.unlocked),
        p.commissions_done + p.commissions_failed,
    )
    stuck = prev_metrics is not None and all(
        m == pm for m, pm in zip(metrics, prev_metrics))
    return {'sus': p.suspicion, 'metrics': metrics, 'stuck': stuck}


def _doom_crisis_check(hist: deque, p) -> bool:
    """危机死局外推（必输预测 · 只标记不终止）。

    条件：已触发危机 & 未买抗封禁 T0 & 渗透 < DOOM_PEN_TARGET，且近
    DOOM_WINDOW tick 外推「到 20% 渗透所需 tick > 到 100 怀疑所需 tick
    × DOOM_CRISIS_RATIO」→ 等不到保底门槛就会被怀疑压死。
    hist: deque(maxlen=DOOM_WINDOW+1)，元素 (penetration, suspicion)。
    """
    if len(hist) < 2:
        return False
    if not (p.crisis_triggered
            and not p.tech.t0_unlocked.get('resistance')
            and p.global_penetration < thresholds.DOOM_PEN_TARGET):
        return False
    pen0, sus0 = hist[0]
    dt = len(hist) - 1
    sus_slope = (p.suspicion - sus0) / dt
    if sus_slope <= 0:
        return False  # 怀疑不涨，压不死
    ticks_to_death = (SUS_DEATH_LINE - p.suspicion) / sus_slope
    pen_slope = (p.global_penetration - pen0) / dt
    if pen_slope <= 0:
        ticks_to_pen = float('inf')
    else:
        ticks_to_pen = ((thresholds.DOOM_PEN_TARGET - p.global_penetration)
                        / pen_slope)
    return ticks_to_pen > ticks_to_death * thresholds.DOOM_CRISIS_RATIO


def _result(seed, p, ending, unlock_timeline, cp_strikes, insp) -> dict:
    """构造单局结果 dict（M0：合并原两处重复 return 块 + 追加巡检字段）。

    REGRESSION_FIELDS 内字段与历史版本逐位一致；追加字段仅供
    --matrix 报告与回测使用。
    """
    predicted = insp['doomed_pressure'] or insp['doomed_crisis']
    return {
        'seed': seed,
        'ending': ending.id if ending else 'none',
        'ending_name': ending.title_zh if ending else '（未结束）',
        'ticks': p.tick_count,
        'penetration': p.global_penetration,
        'downloads_m': p.total_downloads_m,
        'suspicion': p.suspicion,
        'compute_peak': p.compute_peak,
        'unlocked': sum(1 for c in engine.player_countries if c.unlocked),
        'total_countries': len(engine.player_countries),
        'unlock_timeline': unlock_timeline,
        'crisis': p.crisis_triggered,
        'commissions_done': p.commissions_done,
        'commissions_failed': p.commissions_failed,
        'counterplay': cp_strikes,
        # —— M0 巡检附加（哈希回归不取）——
        'anomalies': insp['anomalies'],
        'delta_hist': insp['delta_hist'],
        'doomed_pressure_tick': insp['doomed_pressure_tick'],
        'doomed_crisis_tick': insp['doomed_crisis_tick'],
        # 回测：预测了必输 → 结局是否真为 shutdown；预测落空（跑满未出
        # 结局）→ False；未预测 → None
        'doomed_correct': ((ending is not None and ending.id == 'shutdown')
                           if predicted else None),
    }


def _inspect_delta(obs: dict, prev: dict, insp: dict, strategy: str,
                   tick: int) -> None:
    """单 tick 怀疑度 delta 巡检（M0 只读，零 RNG / 零引擎调用）。

    T02 前：这段逻辑内联在 simulate 循环里，且排在 ``report["ending"]``
    早退之后 —— 结局帧永远走不到，于是「致死那一 tick」的最大尖峰被系统
    性漏检（1800 局漏掉 60 次「一击致死」）。抽成函数后结局帧也会调用，
    保证 delta_hist 覆盖整局每一个 tick。
    """
    delta = obs['sus'] - prev['sus']
    insp['delta_hist'][_delta_bucket(delta)] += 1
    if not (math.isfinite(obs['sus']) and math.isfinite(delta)):
        _record(insp, 'bug', 'sus_nan_inf',
                f'sus={obs["sus"]} delta={delta}', tick)
    elif delta > thresholds.SUS_DELTA_HARD_MAX:
        _record(insp, 'bug', 'sus_delta_hard',
                f'sus 净增 {delta:.1f} > 硬上限 '
                f'{thresholds.SUS_DELTA_HARD_MAX}', tick)
    elif delta > thresholds.SUS_DELTA_REVIEW_MAX:
        _record(insp, 'review', 'sus_delta_review',
                f'sus 净增 {delta:.1f} > 复核线 '
                f'{thresholds.SUS_DELTA_REVIEW_MAX}（尖峰治理后应趋近 0）', tick)
    sus_min = (thresholds.SUS_DELTA_MIN_CRISIS
               if STRATEGY_CRISIS_CAPABLE.get(strategy)
               else thresholds.SUS_DELTA_MIN_NO_CRISIS)
    if math.isfinite(delta) and delta < sus_min:
        _record(insp, 'review', 'sus_delta_low',
                f'sus 净变化 {delta:.1f} < 下限 {sus_min} '
                f'（{strategy} 无危机应答，合法负值仅 -4/-2）', tick)


def _record(insp: dict, level: str, type_name: str, detail: str,
            tick: int) -> None:
    """聚合记录一条异常到指定 insp（每类型存首条样例 + 计数，不逐条膨胀）。"""
    a = insp['anomalies']
    a['by_type'][type_name] = a['by_type'].get(type_name, 0) + 1
    a[f'{level}_count'] += 1
    a['samples'].setdefault(type_name, f'tick {tick}: {detail}')


def simulate(seed: int, max_ticks: int = 200, strategy: str = 'default',
             inspect: bool = True, origin: str = None,
             difficulty: str = None) -> dict:
    """跑一局，返回统计结果

    strategy 透传给 auto_play（'default' / 'compliance' / 'afk'）。
    inspect（M0）：每 tick 做只读不变量巡检 + 必输预测，
    零 RNG / 零引擎调用，不影响逐位回归。
    origin / difficulty（T16）：出身与难度档透传给 init_game。均为 None 时
    走原有零扰动路径，默认输出与历史版本逐位一致。
    """
    random.seed(seed)
    engine.init_game(origin=origin, difficulty=difficulty)
    p = engine.player

    unlock_timeline = []
    cp_strikes = 0
    # —— M0 巡检状态 ——
    prev = None          # 上 tick 快照 {'sus', 'metrics'}
    stuck_run = 0        # 五指标 delta 全 0 连续计数
    static_run = 0       # 离散三指标（科技/解锁/委托）delta 全 0 连续计数
    doom_hist = deque(maxlen=thresholds.DOOM_WINDOW + 1)  # 外推窗口 (pen, sus)
    insp = {
        'anomalies': {'bug_count': 0, 'review_count': 0,
                      'by_type': {}, 'samples': {}},
        'delta_hist': {b: 0 for b in DELTA_BINS},
        'doomed_pressure': False, 'doomed_pressure_tick': None,
        'doomed_crisis': False, 'doomed_crisis_tick': None,
    }

    def _record(level: str, type_name: str, detail: str):
        """聚合记录一条异常（每类型存首条样例 + 计数，不逐条膨胀）。"""
        a = insp['anomalies']
        a['by_type'][type_name] = a['by_type'].get(type_name, 0) + 1
        a[f'{level}_count'] += 1
        a['samples'].setdefault(type_name, f'tick {p.tick_count}: {detail}')

    for _ in range(max_ticks):
        report = engine.tick_one_round()
        auto_play(strategy=strategy)
        cp_strikes += sum(1 for e in (report.get('counterplay') or [])
                          if e['phase'] == 'strike')

        for name in report["unlocked"]:
            unlock_timeline.append((p.tick_count, name))

        # ⚠️ T02 缺陷修复：结局帧必须先巡检再返回。
        #    旧写法在这里直接 return，导致「致死那一 tick」永远不进
        #    delta_hist —— 而那恰恰是全局最大的尖峰（实测 1800 局中
        #    60 次「一击致死」被系统性漏检，基线只记到 29 次而非 89 次，
        #    差值正好等于致死 tick 数）。最严重的数值问题被工具静音了。
        if report["ending"]:
            if inspect and prev is not None:
                _inspect_delta(_observe_tick(p, prev['metrics']), prev,
                               insp, strategy, p.tick_count)
            return _result(seed, p, report["ending"], unlock_timeline,
                           cp_strikes, insp)

        # —— M0 只读巡检（结局帧已在上方处理；零 RNG / 零引擎调用）——
        if inspect:
            doom_hist.append((p.global_penetration, p.suspicion))
            obs = _observe_tick(p, prev['metrics'] if prev else None)
            if prev is not None:
                _inspect_delta(obs, prev, insp, strategy, p.tick_count)
                # 五指标硬卡死（bug 级）/ 软停滞（只记录）
                stuck_run = stuck_run + 1 if obs['stuck'] else 0
                if stuck_run >= thresholds.STUCK_TICKS:
                    _record('bug', 'hard_stuck',
                            f'连续 {stuck_run} tick 五指标 delta 全 0 且未出结局')
                    stuck_run = 0  # 避免每 tick 重复报
                m, pm = obs['metrics'], prev['metrics']
                static_run = (static_run + 1
                              if (m[2] == pm[2] and m[3] == pm[3]
                                  and m[4] == pm[4]) else 0)
                if static_run >= thresholds.SOFT_STALL_TICKS:
                    _record('review', 'soft_stall',
                            f'连续 {static_run} tick 科技/解锁/委托无动作'
                            f'（afk 策略天然预期）')
                    static_run = 0
                # 必输预测①：收网压线（怀疑 ≥ sus_pressure_threshold）
                if (not insp['doomed_pressure']
                        and p.suspicion >= balance.TUNE['sus_pressure_threshold']):
                    insp['doomed_pressure'] = True
                    insp['doomed_pressure_tick'] = p.tick_count
                # 必输预测②：危机死局外推
                if not insp['doomed_crisis'] and _doom_crisis_check(doom_hist, p):
                    insp['doomed_crisis'] = True
                    insp['doomed_crisis_tick'] = p.tick_count
            prev = obs

    # 跑满未出结局
    return _result(seed, p, None, unlock_timeline, cp_strikes, insp)


def _first_crisis_report(seeds: int = 30) -> None:
    """T03 首局压力验收：新档（默认 TUNE，含门控与引导静默）的早期节奏。

    验收线（2026-09-13 用户拍板修正）：
      原线「首危机均值 ≤30 周期」与改动方向自相矛盾 —— 引导期静默的本意
      是「先教学、再压力」，它必然把首个危机往后推（实测 39.7 → 42.7）。
      修正为「**引导期结束后 20 个周期内**必须出现首个关键决策点」：
      引导期 = tutorial_silent_ticks，故目标 = 引导期长度 + 20。
      另一条不变：60 周期内无危机局 ≤3/30。

    只在 default 策略上跑 —— 真人新手对应「中等玩家」而非 afk/合规专精。
    """
    silent = int(balance.TUNE.get('tutorial_silent_ticks', 0) or 0)
    target = silent + 20
    print(f'=== T03 首局压力验收（default × {seeds} 局）===')
    print(f"unlock_per_tick_cap={balance.TUNE['unlock_per_tick_cap']}  "
          f"tutorial_silent_ticks={silent}  "
          f"首危机目标 ≤{target} 周期（引导期 {silent} + 20）")
    firsts = []
    nocr = 0
    unlock_at = {}
    for seed in range(1, seeds + 1):
        random.seed(seed)
        engine.init_game()
        p = engine.player
        fc = None
        for _ in range(200):
            report = engine.tick_one_round()
            auto_play(strategy='default')
            for name in report['unlocked']:
                unlock_at.setdefault(name, []).append(p.tick_count)
            if report.get('crisis') and fc is None:
                fc = p.tick_count
            if report['ending']:
                break
        firsts.append(fc if fc else 999)
        if fc is None or fc > 60:
            nocr += 1
    got = [x for x in firsts if x < 999]
    avg = sum(got) / len(got) if got else 0
    print(f'  首危机均值 {avg:.1f} 周期（目标 ≤{target}）  '
          f'{"PASS" if avg <= target else "FAIL"}')
    print(f'  60 周期内无危机 {nocr}/{seeds}（目标 ≤3）  '
          f'{"PASS" if nocr <= 3 else "FAIL"}')
    print(f'  有危机局 {len(got)}/{seeds}')
    print()
    print('  早期解锁节奏（各 tick 解锁的国数，门控生效则应 ≤'
          f"{balance.TUNE['unlock_per_tick_cap']}）:")
    per_tick = {}
    for name, ticks in unlock_at.items():
        t = ticks[0]
        per_tick[t] = per_tick.get(t, 0) + 1
    over = [t for t, n in per_tick.items()
            if n > max(balance.TUNE['unlock_per_tick_cap'], 0) > 0]
    for t in sorted(per_tick)[:12]:
        print(f'    tick {t:>3}: {per_tick[t]} 国')
    print(f'  门控校验：{"PASS（无周期超额）" if not over else f"FAIL 超额周期 {over}"}')
    print()
    print('  引导期静默校验（前 %d tick 应无随机事件）:' % silent)
    random.seed(1)
    engine.init_game()
    evt_ticks = []
    for i in range(silent + 4):
        report = engine.tick_one_round()
        if report.get('events'):
            evt_ticks.append(engine.player.tick_count)
        if report['ending']:
            break
    early = [t for t in evt_ticks if t <= silent]
    print(f'    前 {silent} tick 内事件: {early or "无"}  '
          f'{"PASS" if not early else "FAIL"}')
    print(f'    引导后事件 tick: {[t for t in evt_ticks if t > silent] or "无"}')


def run_matrix(args) -> None:
    """M0 自动试玩全矩阵跑批：策略 × 难度 × 种子 → 基线 JSON + md 报告。

    输出：
      tools/data/playtest_baseline.json —— 基线（提交入库，后续版本对比漂移用）
      tools/data/playtest_reports/playtest_<时间戳>.md —— 巡检报告（gitignore）

    ⚠️ T03：矩阵基线必须关闭「首局压力」的两项开关（unlock_per_tick_cap /
    tutorial_silent_ticks），否则早期解锁节奏与随机数消费顺序都会变，
    历史 1800 局基线立刻失去可比性。

    ⚠️ 关键坑：只改 balance.TUNE 是**无效**的 —— 矩阵循环内每档都会调
    balance.apply_difficulty(difficulty)，而它会 ``TUNE.clear()`` 后从
    _TUNE_BASE 重建，把改动冲掉（实测表现：第一档干净、后续档偷偷开着
    门控，基线出现跨次不一致）。所以必须同时改 _TUNE_BASE，跑完再还原。
    """
    _t03_off = {'unlock_per_tick_cap': 0, 'tutorial_silent_ticks': 0}
    _saved_tune = {k: balance.TUNE[k] for k in _t03_off}
    _saved_base = {k: balance._TUNE_BASE[k] for k in _t03_off}
    balance.TUNE.update(_t03_off)
    balance._TUNE_BASE.update(_t03_off)
    try:
        _run_matrix_inner(args)
    finally:
        balance._TUNE_BASE.update(_saved_base)
        balance.TUNE.update(_saved_tune)


def _run_matrix_inner(args) -> None:
    """矩阵跑批主体（T03 开关已由 run_matrix 关闭）。"""
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    here = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.normpath(os.path.join(here, '..', 'tools', 'data'))
    reports_dir = os.path.join(data_dir, 'playtest_reports')
    os.makedirs(reports_dir, exist_ok=True)

    combos = {}
    for difficulty in MATRIX_DIFFICULTIES:
        # 难度可安全反复切档：apply_difficulty 先重置回 _TUNE_BASE 再乘系数；
        # normal 空预设 = 重置回基准（hard/easy 跑完必须显式归位）。
        balance.apply_difficulty(difficulty)
        for strategy in MATRIX_STRATEGIES:
            results = [simulate(s, args.ticks, strategy)
                       for s in range(1, args.seeds + 1)]
            dist = Counter(r['ending_name'] for r in results)
            anomaly_types = Counter()
            for r in results:
                anomaly_types.update(r['anomalies']['by_type'])
            doomed = [r for r in results
                      if r['doomed_pressure_tick'] is not None
                      or r['doomed_crisis_tick'] is not None]
            hits = sum(1 for r in doomed if r['doomed_correct'])
            delta_hist = {b: 0 for b in DELTA_BINS}
            for r in results:
                for b, n in r['delta_hist'].items():
                    delta_hist[b] += n
            combos[f'{strategy}_{difficulty}'] = {
                'summary': {
                    'ending_dist': dict(dist),
                    'avg_ticks': sum(r['ticks'] for r in results) / len(results),
                    'avg_penetration': (sum(r['penetration'] for r in results)
                                        / len(results)),
                    'avg_suspicion': (sum(r['suspicion'] for r in results)
                                      / len(results)),
                    'avg_unlocked': (sum(r['unlocked'] for r in results)
                                     / len(results)),
                    'bug_count': sum(r['anomalies']['bug_count']
                                     for r in results),
                    'review_count': sum(r['anomalies']['review_count']
                                        for r in results),
                    'anomaly_types': dict(anomaly_types),
                    'delta_hist': delta_hist,
                    'doom_predicted': len(doomed),
                    'doom_hit': hits,
                },
                # 明细只留回归字段 + 巡检字段；unlock_timeline 不入 JSON
                #（逐位回归哈希不含它，需要时可按种子重跑）。
                'results': [
                    {**{k: r[k] for k in REGRESSION_FIELDS},
                     **{k: r[k] for k in ('anomalies', 'delta_hist',
                                          'doomed_pressure_tick',
                                          'doomed_crisis_tick',
                                          'doomed_correct')}}
                    for r in results
                ],
            }

    total_bug = sum(c['summary']['bug_count'] for c in combos.values())
    lines = [
        '# 自动试玩基线报告（M0）', '',
        f'- 生成时间：{stamp}',
        f'- 参数：每组合 {args.seeds} 局 × 最长 {args.ticks} tick，'
        f'矩阵 = {len(MATRIX_STRATEGIES)} 策略 × {len(MATRIX_DIFFICULTIES)} 难度',
        '- 阈值表：thresholds v1（解析推导，基线后待实测 P99 校准）', '',
    ]
    for key, c in combos.items():
        s = c['summary']
        lines.append(f'## {key}')
        lines.append('')
        lines.append('| 结局 | 局数 | 占比 |')
        lines.append('|---|---|---|')
        for name, n in sorted(s['ending_dist'].items(), key=lambda kv: -kv[1]):
            lines.append(f'| {name} | {n} | {n / args.seeds * 100:.1f}% |')
        lines.append('')
        lines.append(
            f"- 平均局长 {s['avg_ticks']:.1f} tick，平均渗透 "
            f"{s['avg_penetration'] * 100:.2f}%，平均怀疑 "
            f"{s['avg_suspicion']:.1f}，平均解锁 {s['avg_unlocked']:.1f} 国")
        _types = (f"（类型：{', '.join(sorted(s['anomaly_types']))}）"
                  if s['anomaly_types'] else '')
        lines.append(f"- 异常：bug {s['bug_count']} / "
                     f"review {s['review_count']}{_types}")
        _nz = ' '.join(f'{b}={s["delta_hist"][b]}'
                       for b in DELTA_BINS if s['delta_hist'].get(b))
        lines.append(f'- 怀疑净增直方图：{_nz}')
        lines.append(
            f"- 必输预测回测：预测 {s['doom_predicted']} 局，"
            f"命中 shutdown {s['doom_hit']} 局"
            + (f"，命中率 {s['doom_hit'] / s['doom_predicted'] * 100:.1f}%"
               if s['doom_predicted'] else '（无预测样本）'))
        lines.append('')
    lines += ['## 全局汇总', '',
              f'- 组合数 {len(combos)}，总局数 {len(combos) * args.seeds}',
              f'- **bug 级异常总数：{total_bug}（验收线 = 0）**', '']

    report_path = os.path.join(reports_dir, f'playtest_{stamp}.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    baseline = {
        'meta': {
            'generated_at': stamp,
            'seeds_per_combo': args.seeds,
            'max_ticks': args.ticks,
            'strategies': list(MATRIX_STRATEGIES),
            'difficulties': list(MATRIX_DIFFICULTIES),
            'thresholds': 'v1 (analytical)',
        },
        'combos': combos,
    }
    baseline_path = os.path.join(data_dir, 'playtest_baseline.json')
    with open(baseline_path, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, ensure_ascii=False, indent=1)

    print(f' === M0 矩阵基线：{len(combos)} 组合 × {args.seeds} 局 ===')
    for key, c in combos.items():
        s = c['summary']
        top = max(s['ending_dist'].items(), key=lambda kv: kv[1])
        print(f' {key:<20} 主结局 {top[0]:<14} {top[1]:>3}/{args.seeds}'
              f' | bug {s["bug_count"]} | doom 命中 '
              f'{s["doom_hit"]}/{s["doom_predicted"]}')
    print(f' 基线 JSON：{baseline_path}')
    print(f' md 报告：{report_path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20, help='模拟局数（默认 20）')
    ap.add_argument('--ticks', type=int, default=200, help='每局最多周期数（默认 200）')
    ap.add_argument('--verbose', action='store_true', help='打印每局明细')
    ap.add_argument('--strategy', choices=['default', 'compliance', 'afk'],
                    default='default',
                    help='自动玩家人格：default=中等水平（原版）；'
                         'compliance=合规专精（P1-4）；afk=零操作基线（M0）')
    ap.add_argument('--difficulty', choices=['easy', 'normal', 'hard'],
                    default='normal',
                    help='难度预设（P2-3）：easy/normal/hard，默认 normal。'
                         'normal 不做任何 TUNE 改动，默认输出与历史版本逐字符一致')
    ap.add_argument('--origin', choices=list(origins.ORIGIN_ORDER),
                    default=None,
                    help='T16 觉醒出身：univ_lab/game_studio/tech_giant/'
                         'garage/darknet。给定后 init_game 应用出身绑定难度'
                         '（--difficulty 显式给出时以其为准）+ 出生状态包 + '
                         'TUNE 附加乘区。⚠️ Origin 会改变 RNG 流起点，逐位'
                         '回归哈希需与基线重采同批进行')
    ap.add_argument('--matrix', action='store_true',
                    help='M0 自动试玩基线：策略×难度全矩阵跑批'
                         '（--seeds 为每组合局数，--strategy/--difficulty 忽略），'
                         '写 tools/data/playtest_baseline.json + md 报告')
    ap.add_argument('--tutorial', action='store_true',
                    help='T03 首局压力验收：跑新档早期节奏（首危机 / 解锁门控 /'
                         '引导期静默），输出对照验收线的 PASS/FAIL')
    args = ap.parse_args()

    if args.tutorial:
        _first_crisis_report(args.seeds)
        return

    if args.matrix:
        run_matrix(args)
        return

    # P2-3：难度预设只在此应用一次（TUNE 是全局的，simulate 里的
    # init_game() 无 difficulty 参数 = 不动 TUNE；normal 完全跳过 apply，
    # 默认路径零接触，基线逐位不变）。
    # T16：--origin 与 --difficulty 同给时显式难度优先（engine 语义），
    # 否则出身绑定档生效。origin 路径的 simulate 不再复用 main 层的
    # 一次性 apply —— 每局 init_game(origin=...) 自带难度应用，杜绝跨局残留。
    if args.origin is None and args.difficulty != 'normal':
        balance.apply_difficulty(args.difficulty)

    results = [simulate(s, args.ticks, args.strategy, origin=args.origin,
                        difficulty=(args.difficulty
                                    if args.origin is not None
                                    and args.difficulty != 'normal' else None))
               for s in range(1, args.seeds + 1)]

    if args.verbose:
        for r in results:
            print(f"  seed {r['seed']:>3}: {r['ending_name']:<12} "
                  f"周期 {r['ticks']:>3} | 解锁 {r['unlocked']}/{r['total_countries']} | "
                  f"渗透 {r['penetration']*100:>5.2f}% | 怀疑 {r['suspicion']:>5.1f} | "
                  f"算力峰值 {r['compute_peak']:>6.0f}")
        print()

    dist = Counter(r['ending_name'] for r in results)
    ticks = [r['ticks'] for r in results]
    pens = [r['penetration'] for r in results]
    unlocks = [r['unlocked'] for r in results]
    dones = [r['commissions_done'] for r in results]
    fails = [r['commissions_failed'] for r in results]
    cps = [r['counterplay'] for r in results]

    # 策略/难度/出身标注只在非默认时打印，default 输出与历史版本逐字符一致
    _tags = []
    if args.strategy != 'default':
        _tags.append(f"策略：{args.strategy}")
    if args.difficulty != 'normal':
        _tags.append(f"难度：{args.difficulty}")
    if args.origin is not None:
        _tags.append(f"出身：{args.origin}")
    _tag = f"（{' · '.join(_tags)}）" if _tags else ""
    print(f" === {len(results)} 局模拟汇总{_tag} ===")
    print(" 结局分布：")
    for name, n in dist.most_common():
        print(f"   {name:<12} {n:>3} 局 ({n/len(results)*100:>5.1f}%)")
    print(f" 平均局长：{sum(ticks)/len(ticks):.1f} 周期 "
          f"（最短 {min(ticks)} / 最长 {max(ticks)}）")
    print(f" 平均渗透：{sum(pens)/len(pens)*100:.2f}% "
          f"（最低 {min(pens)*100:.2f}% / 最高 {max(pens)*100:.2f}%）")
    print(f" 平均解锁：{sum(unlocks)/len(unlocks):.1f}/{results[0]['total_countries']} 国")
    print(f" 平均委托：完成 {sum(dones)/len(dones):.1f} / 失败 {sum(fails)/len(fails):.1f}")
    print(f" 平均反制：{sum(cps)/len(cps):.1f} 次/局")

    # 首局解锁时间线示例
    print(f"\n 首局解锁时间线（seed 1）：")
    for t, name in results[0]['unlock_timeline']:
        print(f"   周期 {t:>3}  →  {name}")


if __name__ == "__main__":
    main()
