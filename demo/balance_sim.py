"""
balance_sim.py - 数值平衡模拟器（调参工具，不参与游戏运行）

用途：用「自动玩家」批量跑 N 局，统计结局分布 / 解锁节奏 / 渗透率曲线，
      用于验证数值调整是否合理，避免手动试玩半天才发现爆炸。

用法：
    python balance_sim.py                # 默认跑 20 个种子，每局最多 200 周期
    python balance_sim.py --seeds 50     # 跑 50 局
    python balance_sim.py --ticks 300    # 每局最多 300 周期

自动玩家策略（模拟一个「中等水平玩家」）：
  1. 优先解锁 T0，再沿第一个可选分支升级
  2. 怀疑度 > 60 且「潜伏」可用时释放

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

import engine
import tech_tree


def auto_play(tick_report_hook=None):
    """自动玩家的每周期决策"""
    p = engine.player

    # 0. 委托：全部接受（P0-3；自动玩家策略是「来者不拒」）
    for com in list(p.commissions):
        if com.status == 'offered':
            engine.accept_commission(com.uid)

    # 1. 科技加点：先 T0，后分支
    #    危机应答（P0-3）：政府反制引发危机后，中等玩家的本能是先补
    #    「抗封禁」T0（成本 50，前置 capability）——被反制了才点防御，
    #    下一 tick 回到常规队列。无危机时维持深度优先不变。
    if p.crisis_triggered and not p.tech.t0_unlocked.get('resistance'):
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
    if p.suspicion > 60:
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
                if (p.suspicion > 40 and sk is not None
                        and sk.suspicion_delta > 0):
                    continue
                if engine.use_skill(com.skill_id):
                    break


def simulate(seed: int, max_ticks: int = 200) -> dict:
    """跑一局，返回统计结果"""
    random.seed(seed)
    engine.init_game()
    p = engine.player

    unlock_timeline = []
    cp_strikes = 0
    for _ in range(max_ticks):
        report = engine.tick_one_round()
        auto_play()
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
    args = ap.parse_args()

    results = [simulate(s, args.ticks) for s in range(1, args.seeds + 1)]

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

    print(f" === {len(results)} 局模拟汇总 ===")
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
