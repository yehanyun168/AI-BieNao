# -*- coding: utf-8 -*-
"""T02 · 怀疑尖峰根因探针（只读观测工具，不改任何游戏数值）

用法：
    python tools/sus_spike_probe.py --seeds 200 --threshold 45

作用：
    逐局重跑模拟器，捕捉「单周期怀疑净增 ≥ threshold」的尖峰 tick，
    并打印该 tick 的 suspicion_breakdown（引擎 _sus 记账的来源拆解），
    用于回答「这一周期怀疑度为什么涨了这么多」。

设计约束（与 balance_sim 巡检一致）：
    - 只读：不修改 TUNE / 不调用引擎写接口
    - 可复现：外置 random.seed + init_game，随机流与 balance_sim 一致
    - 退出前必须把难度复位回 normal（否则污染后续任何跑批）
"""
import argparse
import collections
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.normpath(os.path.join(HERE, '..', 'demo'))
sys.path.insert(0, DEMO)

import balance  # noqa: E402
import engine  # noqa: E402
import balance_sim  # noqa: E402


def _event_label(e) -> str:
    """事件对象可能是 dict / tuple / 具名元组，统一取一个可读标签。"""
    if isinstance(e, dict):
        return str(e.get('title') or e.get('name') or e.get('id') or e)
    if isinstance(e, (tuple, list)):
        return str(e[0])
    return str(getattr(e, 'title', None) or getattr(e, 'name', None) or e)


def probe(strategy: str, difficulty: str, seeds: int, ticks: int,
          threshold: float):
    """跑一批种子，返回尖峰样本列表 + 全局来源贡献聚合。"""
    balance.apply_difficulty(difficulty)
    spikes = []
    src_agg = collections.Counter()   # 尖峰 tick 上各来源的贡献合计
    src_hits = collections.Counter()  # 各来源出现在尖峰 tick 上的次数
    try:
        for seed in range(1, seeds + 1):
            random.seed(seed)
            engine.init_game()
            p = engine.player
            prev_sus = float(p.suspicion)
            for _ in range(ticks):
                report = engine.tick_one_round()
                balance_sim.auto_play(strategy=strategy)
                sus = float(engine.player.suspicion)
                delta = sus - prev_sus
                prev_sus = sus
                if delta >= threshold:
                    bd = report.get('suspicion_breakdown') or {}
                    for k, v in bd.items():
                        src_agg[k] += v
                        if v:
                            src_hits[k] += 1
                    spikes.append({
                        'seed': seed,
                        'tick': engine.player.tick_count,
                        'delta': round(delta, 2),
                        'before': round(sus - delta, 2),
                        'after': round(sus, 2),
                        'breakdown': {k: round(v, 2) for k, v in
                                      sorted(bd.items(),
                                             key=lambda kv: -abs(kv[1]))},
                        'events': [_event_label(e)
                                   for e in (report.get('events') or [])],
                        'counterplay': len(report.get('counterplay') or []),
                    })
                if report.get('ending'):
                    break
    finally:
        balance.apply_difficulty('normal')  # 复位，防止污染后续跑批
    return spikes, src_agg, src_hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strategy', default='default',
                    choices=['default', 'compliance', 'afk'])
    ap.add_argument('--difficulty', default='easy',
                    choices=['easy', 'normal', 'hard'])
    ap.add_argument('--seeds', type=int, default=200)
    ap.add_argument('--ticks', type=int, default=200)
    ap.add_argument('--threshold', type=float, default=45.0)
    ap.add_argument('--show', type=int, default=12, help='打印前 N 条尖峰明细')
    args = ap.parse_args()

    spikes, src_agg, src_hits = probe(args.strategy, args.difficulty,
                                      args.seeds, args.ticks, args.threshold)

    print(f'=== 尖峰探针：strategy={args.strategy} '
          f'difficulty={args.difficulty} seeds={args.seeds} '
          f'阈值 Δ≥{args.threshold} ===')
    print(f'命中尖峰 {len(spikes)} 次')

    # 「无预警致死」判定：尖峰前怀疑度 < 30（玩家视角处于安全区）却被一击拉满
    nowarn = [s for s in spikes if s['before'] < 30]
    dead = [s for s in spikes if s['after'] >= 100]
    print(f'  其中 无预警（尖峰前 suspicion<30）: {len(nowarn)} 次 '
          f'({len(nowarn) / max(len(spikes), 1) * 100:.0f}%)')
    print(f'  其中 一击致死（尖峰后 suspicion=100）: {len(dead)} 次 '
          f'({len(dead) / max(len(spikes), 1) * 100:.0f}%)')
    tot_src = sum(abs(v) for v in src_agg.values())
    if tot_src:
        top_k, top_v = src_agg.most_common(1)[0]
        print(f'  主因来源: {top_k}（占尖峰贡献 '
              f'{abs(top_v) / tot_src * 100:.1f}%）')
    print()
    print('--- 尖峰 tick 上各来源贡献聚合（合计值 / 出现次数）---')
    for k, v in src_agg.most_common():
        print(f'  {k:<22} 合计 {v:>10.1f}   出现 {src_hits[k]:>4} 次'
              f'   均值 {v / max(src_hits[k], 1):>6.2f}')
    print()
    print(f'--- 前 {args.show} 条尖峰明细 ---')
    for s in spikes[:args.show]:
        bd = ' '.join(f'{k}={v:+.1f}' for k, v in s['breakdown'].items())
        print(f"  seed {s['seed']:>4} tick {s['tick']:>4}  "
              f"Δ={s['delta']:>6.1f}  ({s['before']:.0f}→{s['after']:.0f})  "
              f"反制{s['counterplay']}  [{bd}]")
        if s['events']:
            print(f"        事件: {s['events']}")
    print()
    print('--- 尖峰 tick 分布 ---')
    tc = collections.Counter(s['tick'] for s in spikes)
    for t in sorted(tc):
        print(f'  tick {t:>4}: {tc[t]} 次')


if __name__ == '__main__':
    main()
