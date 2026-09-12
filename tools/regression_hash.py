"""
regression_hash.py - 逐位回归哈希工具（M0 自动试玩配套，非运行时模块）

对 balance_sim 结果的原字段子集（与历史版本完全一致的 14 个字段）做
sha256，用于「改动前后逐位一致」验证：同一脚本分别加载新旧
balance_sim 模块各跑一遍，哈希相等即证明引擎路径零漂移。

用法（传绝对路径，避免相对路径 sys.path 歧义）：
  python tools/regression_hash.py <demo 下某 balance_sim 副本.py>

对照组生成：git show HEAD:demo/balance_sim.py > demo/_probe_sim_old.py
（_probe 前缀已被 .gitignore 与 verify_tables EXEMPT_PREFIXES 覆盖）
"""
import os
os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KIVY_NO_FILELOG', '1')

import hashlib
import importlib.util
import json
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.normpath(os.path.join(HERE, '..', 'demo'))
sys.path.insert(0, DEMO)

SEEDS = 90
MAX_TICKS = 200
# 逐位回归基线组合（与 M0 改动前抓取口径一致）
COMBOS = [('default', 'normal'), ('compliance', 'normal'), ('default', 'hard')]
FIELDS = ('seed', 'ending', 'ending_name', 'ticks', 'penetration',
          'downloads_m', 'suspicion', 'compute_peak', 'unlocked',
          'total_countries', 'crisis', 'commissions_done',
          'commissions_failed', 'counterplay')


def load_sim(path: str):
    spec = importlib.util.spec_from_file_location('balance_sim', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    sim_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        DEMO, 'balance_sim.py')
    sim = load_sim(os.path.abspath(sim_path))
    import balance
    for strategy, difficulty in COMBOS:
        if difficulty != 'normal':
            balance.apply_difficulty(difficulty)
        results = [sim.simulate(s, MAX_TICKS, strategy)
                   for s in range(1, SEEDS + 1)]
        payload = json.dumps([{k: r[k] for k in FIELDS} for r in results],
                             ensure_ascii=False, sort_keys=True)
        h = hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]
        print(f'{strategy}_{difficulty}: {h}', flush=True)


if __name__ == '__main__':
    main()
