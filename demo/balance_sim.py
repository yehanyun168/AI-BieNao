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

自动玩家人格（P1-4 新增 --strategy）：
  default    上述「中等水平玩家」，行为与历史版本逐位一致
  compliance 合规专精：开局沿前置链尽早买「抗封禁 T0」（不等危机）、
             全程不练脏技能（按 data.SKILLS.suspicion_delta > 0 判定）、
             怀疑度进入危机警戒区（距危机线 15 点）后暂停技能投放、
             深度伪装提前一档释放。其余决策（委托、常规科技）复用默认逻辑。

⚠️ 这不是 AI 最优策略 —— 它故意保持平庸，用来暴露数值问题：
   如果自动玩家 80% 都在第 30 周期前「被关停」，说明怀疑度还是太紧。
"""
import os
# Kivy 会抢先解析 argv，必须在导入任何 kivy 相关模块前关掉
os.environ.setdefault('KIVY_NO_ARGS', '1')

import argparse
import random
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0])

import data  # P1-10：SUSPICION_CRISIS 走 data 的 PEP 562 动态代理
import balance  # P2-3：难度预设（TUNE 乘法，apply_difficulty 在 main 应用一次）
import engine
import tech_tree


def auto_play(tick_report_hook=None, strategy: str = 'default'):
    """自动玩家的每周期决策

    strategy:
        'default'    —— 「中等水平玩家」，行为与历史版本逐位一致。
        'compliance' —— 合规专精人格（P1-4）：主动买抗封禁 T0、全程不练
                        脏技能、接近危机线时保守。其余决策复用默认逻辑。
    """
    p = engine.player

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


def simulate(seed: int, max_ticks: int = 200, strategy: str = 'default') -> dict:
    """跑一局，返回统计结果

    strategy 透传给 auto_play（'default' / 'compliance'，P1-4）。
    """
    random.seed(seed)
    engine.init_game()
    p = engine.player

    unlock_timeline = []
    cp_strikes = 0
    for _ in range(max_ticks):
        report = engine.tick_one_round()
        auto_play(strategy=strategy)
        cp_strikes += sum(1 for e in (report.get('counterplay') or [])
                          if e['phase'] == 'strike')

        for name in report["unlocked"]:
            unlock_timeline.append((p.tick_count, name))

        if report["ending"]:
            return {
                'seed': seed,
                'ending': report["ending"].id,
                'ending_name': report["ending"].title_zh,
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
            }

    # 跑满未出结局
    return {
        'seed': seed,
        'ending': 'none',
        'ending_name': '（未结束）',
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
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20, help='模拟局数（默认 20）')
    ap.add_argument('--ticks', type=int, default=200, help='每局最多周期数（默认 200）')
    ap.add_argument('--verbose', action='store_true', help='打印每局明细')
    ap.add_argument('--strategy', choices=['default', 'compliance'],
                    default='default',
                    help='自动玩家人格：default=中等水平（原版）；'
                         'compliance=合规专精（P1-4）')
    ap.add_argument('--difficulty', choices=['easy', 'normal', 'hard'],
                    default='normal',
                    help='难度预设（P2-3）：easy/normal/hard，默认 normal。'
                         'normal 不做任何 TUNE 改动，默认输出与历史版本逐字符一致')
    args = ap.parse_args()

    # P2-3：难度预设只在此应用一次（TUNE 是全局的，simulate 里的
    # init_game() 无 difficulty 参数 = 不动 TUNE；normal 完全跳过 apply，
    # 默认路径零接触，基线逐位不变）。
    if args.difficulty != 'normal':
        balance.apply_difficulty(args.difficulty)

    results = [simulate(s, args.ticks, args.strategy)
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

    # 策略/难度标注只在非默认时打印，default 输出与历史版本逐字符一致
    _tags = []
    if args.strategy != 'default':
        _tags.append(f"策略：{args.strategy}")
    if args.difficulty != 'normal':
        _tags.append(f"难度：{args.difficulty}")
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
