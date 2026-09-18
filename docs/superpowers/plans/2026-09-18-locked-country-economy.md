# Locked-Country Economy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让未解锁国家在新档和迁移后的旧档中始终不产生、不贡献下载量，并使预览、委托及存档遵循相同口径。

**Architecture:** 实际结算和全局汇总在 `engine` 中修正；两个影子预览只对齐本次范围内的解锁/下载语义。`save_manager` 做 v4→v5 的一次性内存迁移，并对 v5 脏数据防御性归零；不重算历史结局。

**Tech Stack:** Python 3.12、现有 Kivy 项目、自带 `unittest`、JSON 存档、PowerShell。所有需导入 Kivy 的命令使用 `C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe`。

---

## 工作边界与文件地图

本计划在 `C:\Users\tianm\WorkBuddy\workbuddy\game_optimization\.workbuddy\locked-country-worktree`、分支 `codex/locked-country-economy` 内执行。已批准规格：`docs/superpowers/specs/2026-09-18-locked-country-economy-design.md`。不改主工作区、旧 A 工作树、真实存档、打包物；技能施放覆写和持续时间另立计划。

| 文件 | 职责 |
|---|---|
| `demo/engine.py` | 实际增长、全球下载汇总、两条影子预览口径 |
| `demo/save_manager.py` | v5 迁移、下载委托公平重启、v5 锁国脏值归零及诊断 |
| `demo/test_locked_country_economy.py`（新） | 本包独立无头回归：结算、预览、迁移、读档 |
| `demo/balance_sim.py` | 为矩阵增加显式输出目录，避免覆盖 1800 局历史基线 |
| `docs/superpowers/verification/2026-09-18-locked-country-economy.md`（新） | 记录新旧矩阵差异、回归命令和人工边界检查 |

每个任务的代码修改前先跑对应失败测试；通过后只暂存该任务列出的文件并单独提交。PowerShell 会话先设置：

```powershell
$env:KIVY_NO_ARGS='1'
$env:KIVY_NO_FILELOG='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
$py='C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe'
```

以下命令均从 `demo` 目录运行测试；从工作树根目录运行 `git` 和矩阵命令。遇到临时目录权限卡住，只对相同精确命令请求沙箱升级，不改用其他 Python。`git add`/`git commit` 若因工作树外的 Git 元数据被拒，按同样方式申请升级。

### Task 1: 实际结算与全局下载不变量

**Files:** Modify `demo/engine.py:104-110,317-360`; Create `demo/test_locked_country_economy.py`。

- [ ] **Step 1: 写失败测试。** 新文件先放以下内容：

```python
"""未解锁国家经济口径的无头回归。"""
import os
import unittest

os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KIVY_NO_FILELOG', '1')

import balance
import data
import engine


class LockedCountryTickTests(unittest.TestCase):
    def setUp(self):
        balance.apply_difficulty('normal')
        engine.init_game(seed=17)

    def tearDown(self):
        balance.apply_difficulty('normal')

    def test_locked_countries_stay_zero_for_three_ticks(self):
        from unittest.mock import patch
        with patch.dict(balance.TUNE, {'unlock_per_tick_cap': 0}):
            # 禁止邻国解锁，隔离「锁国不得自行增长」这条规则。
            with patch.object(data, 'UNLOCK_PENETRATION_THRESHOLD', 999.0):
                for _ in range(3):
                    engine.tick_one_round()
                    self.assertTrue(all(c.downloads_m == 0.0
                                        for c in engine.player_countries
                                        if not c.unlocked))

    def test_hidden_downloads_do_not_count_toward_global_total(self):
        locked = next(c for c in engine.player_countries if not c.unlocked)
        before = engine.player.total_downloads_m
        locked.downloads_m = 123.0
        self.assertEqual(engine.player.total_downloads_m, before)
        self.assertAlmostEqual(engine.player.global_penetration,
                               before / data.POTENTIAL_USERS_M)

    def test_unlock_gets_seed_only_and_never_reduces_total(self):
        locked = next(c for c in engine.player_countries if not c.unlocked)
        locked.downloads_m = data.UNLOCK_SEED_DOWNLOADS_M + 100.0
        before = engine.player.total_downloads_m
        from unittest.mock import patch
        with patch.object(engine.onboarding, 'try_unlock',
                          side_effect=lambda c, *_: c is locked):
            engine.tick_one_round()
        self.assertTrue(locked.unlocked)
        self.assertEqual(locked.downloads_m, data.UNLOCK_SEED_DOWNLOADS_M)
        self.assertGreaterEqual(engine.player.total_downloads_m, before)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: 确认红灯。** 在 `demo` 下运行 `& $py -m unittest test_locked_country_economy.LockedCountryTickTests -v`；预期至少锁国三周期或隐藏总量断言失败。
- [ ] **Step 3: 最小实现。** 将 `PlayerState.total_downloads_m` 返回式替换为：

```python
return sum(c.downloads_m for c in player_countries if c.unlocked)
```

在 `tick_one_round` 原有成功解锁分支的 `continue` 后、`cfg = country.config` 前插入：

```python
            # 解锁失败的国家本周期不能获得下载，下一周期再判定。
            continue
```

- [ ] **Step 4: 确认绿灯。** 同 Step 2 命令，预期 `Ran 3 tests`、`OK`。再运行 `& $py test_edge_cases.py`，预期全部通过；若旧测试硬编码错误口径，先判断期望是否应更新，不能删用例。
- [ ] **Step 5: 提交。** 根目录运行 `git add demo/engine.py demo/test_locked_country_economy.py`；`git commit -m "fix: stop locked-country download growth"`。

### Task 2: 两条影子预览与解锁额度对齐

**Files:** Modify `demo/engine.py:1267-1275,1331-1380,1463-1518,1554-1565`; Modify `demo/test_locked_country_economy.py`。

- [ ] **Step 1: 增加失败测试。** 在测试文件增加以下类；`push_song` 是开局自带技能，确保预览有可用路径。

```python
class LockedCountryPreviewTests(unittest.TestCase):
    def setUp(self):
        balance.apply_difficulty('normal')
        engine.init_game(seed=19)

    def tearDown(self):
        balance.apply_difficulty('normal')

    def test_dirty_locked_downloads_excluded_from_both_previews(self):
        locked = next(c for c in engine.player_countries if not c.unlocked)
        locked.downloads_m = 88.0
        actual = engine.player.total_downloads_m
        from unittest.mock import patch
        with patch.object(data, 'UNLOCK_PENETRATION_THRESHOLD', 999.0):
            plain = engine.preview_next_cycle()
            skill = engine.preview_skill('push_song')
        self.assertTrue(skill['ok'], skill['reason'])
        self.assertEqual(plain['downloads_before'], actual)
        self.assertEqual(skill['downloads_before'], actual)
        self.assertEqual(skill['growth_by_country'][locked.config.code], 0.0)

    def test_preview_unlock_cap_and_seed_match_real_tick(self):
        from unittest.mock import patch
        with patch.dict(balance.TUNE, {
                'unlock_per_tick_cap': 1,
                'event_prob_global': 0.0,
                'event_prob_country': 0.0,
                'event_prob_v2': 0.0,
                'counterplay_prob': 0.0}):
            with patch.object(data, 'UNLOCK_PENETRATION_THRESHOLD', -1.0):
                before = {c.config.code for c in engine.player_countries
                          if c.unlocked}
                plain = engine.preview_next_cycle()
                skill = engine.preview_skill('push_song')
                self.assertTrue(skill['ok'], skill['reason'])
                report = engine.tick_one_round()
                newly = [c for c in engine.player_countries
                         if c.unlocked and c.config.code not in before]
                self.assertEqual(len(newly), 1)
                self.assertEqual(len(report['unlocked']), 1)
                self.assertEqual(newly[0].downloads_m,
                                 data.UNLOCK_SEED_DOWNLOADS_M)
                self.assertAlmostEqual(plain['downloads_after'],
                                       engine.player.total_downloads_m, places=5)
                self.assertEqual(skill['growth_by_country'][newly[0].config.code],
                                 data.UNLOCK_SEED_DOWNLOADS_M)
                self.assertEqual(sum(
                    skill['growth_by_country'][c.config.code] > 0
                    for c in engine.player_countries
                    if c.config.code not in before), 1)
```

注意：`preview_skill` 带技能乘数，其总下载不应与无技能真实 tick 作全值比较；只比较它的解锁种子、额度、锁国增长与自身前后口径。测试里关闭事件/反制随机流；若固定种子仍触发危机，则增加低怀疑夹具后仅比较阶段 1 的解锁/增长，不删除覆盖范围。

- [ ] **Step 2: 确认红灯。** `& $py -m unittest test_locked_country_economy.LockedCountryPreviewTests -v`；预期隐藏下载、锁国增长或解锁额度相关断言失败。
- [ ] **Step 3: 两处入口和两处循环作相同的最小修正。** `preview_skill`、`preview_next_cycle` 的 `downloads_before` 改为只加 `c.unlocked` 的国家；各自 `total_dl` 改为：

```python
total_dl = sum(s['dl'] for s in shadow if s['unlocked'])
cap, unlocked_this_tick = onboarding.unlock_budget(TUNE), 0
```

在两条预览各自的 `if not s['unlocked']:` 块中，以以下完整块替换原来的解锁判定；后续已解锁增长公式保持原样：

```python
        if not s['unlocked']:
            boost = sum(_pen(by[n]) for n in cfg.neighbors
                        if n in by and by[n]['unlocked'])
            if ((not cap or unlocked_this_tick < cap)
                    and boost >= data.UNLOCK_PENETRATION_THRESHOLD):
                s['unlocked'] = True
                unlocked_this_tick += 1
                s['growth'] = data.UNLOCK_SEED_DOWNLOADS_M
                s['dl'] = data.UNLOCK_SEED_DOWNLOADS_M
                total_dl += s['dl']
            continue
```

`preview_skill` 阶段 5、`preview_next_cycle` 阶段 5 的危机衰减汇总也只取影子已解锁国家：

```python
dl_after = sum(s['dl'] for s in shadow if s['unlocked']) * data.CRISIS_DOWNLOAD_DECAY
```

此任务不宣称完整技能预测与真实结算逐位一致。影子对象保留锁国脏值但不汇总、不增长，实际旧档清理由 Task 3 负责。

- [ ] **Step 4: 确认绿灯。** `& $py -m unittest test_locked_country_economy -v`；预期本文件全过；`& $py test_edge_cases.py` 继续全过。
- [ ] **Step 5: 提交。** `git add demo/engine.py demo/test_locked_country_economy.py`；`git commit -m "fix: align locked-country previews with unlock cap"`。

### Task 3: 存档 v5 迁移、委托重启及脏档诊断

**Files:** Modify `demo/save_manager.py:50,312-400,400-475`; Modify `demo/test_locked_country_economy.py`。

- [ ] **Step 1: 添加失败测试。** 测试文件增加 `json`、`tempfile`、`pathlib.Path`、`unittest.mock.patch`、`save_manager` 导入，并增加以下类。用真实 v5 新档改造成 v4 夹具，避免手写不完整 schema。

```python
class LockedCountrySaveTests(unittest.TestCase):
    def setUp(self):
        balance.apply_difficulty('normal')
        engine.init_game(seed=23)

    def tearDown(self):
        balance.apply_difficulty('normal')

    def _fixture(self, path):
        import json
        import save_manager
        from unittest.mock import patch
        with patch.object(save_manager, 'SAVE_DIR', str(path.parent)):
            save_manager.save(str(path))
        d = json.loads(path.read_text(encoding='utf-8'))
        d['version'] = 4
        locked = next(c for c in d['countries'] if not c['unlocked'])
        locked['downloads_m'] = 55.0
        active = {'uid': 1001, 'template_id': 'C2', 'goal': 'downloads',
                  'icon': 'x', 'name_zh': '测试', 'name_en': 'test',
                  'window': 6, 'reward_mult': 1.0, 'status': 'active',
                  'accepted_tick': 1, 'deadline_tick': 2,
                  'target_value': 10.0, 'reward': 42.0,
                  'snap_downloads': 555.0}
        offered = {**active, 'uid': 1002, 'status': 'offered',
                   'deadline_tick': None}
        other = {**active, 'uid': 1003, 'goal': 'compute',
                 'deadline_tick': 20}
        d['player']['tick_count'] = 3
        d['player']['commissions'] = [active, offered, other]
        path.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        return d, locked['code']

    def test_v4_migrates_in_memory_without_rewriting_file(self):
        import tempfile
        from pathlib import Path
        import save_manager
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'legacy.json'
            source, code = self._fixture(path)
            original = path.read_bytes()
            ok, reason = save_manager.load_ex(str(path))
            self.assertEqual((ok, reason), (True, save_manager.LOAD_OK))
            self.assertEqual(path.read_bytes(), original)
            country = next(c for c in engine.player_countries
                           if c.config.code == code)
            self.assertEqual(country.downloads_m, 0.0)
            self.assertEqual(engine.player.tick_count, 3)
            active, offered, other = engine.player.commissions
            self.assertEqual(active.snap_downloads,
                             engine.player.total_downloads_m)
            self.assertEqual(active.accepted_tick, 3)
            self.assertEqual(active.deadline_tick, 9)
            self.assertEqual(active.reward, 42.0)
            self.assertEqual(offered.snap_downloads, 555.0)
            self.assertEqual(other.snap_downloads, 555.0)
            self.assertEqual(source['player']['commissions'][0]['deadline_tick'], 2)

    def test_chain_is_idempotent_and_preserves_ended_result(self):
        import copy
        import save_manager
        base = {'version': 4,
                'player': {'tick_count': 3, 'game_over': True,
                           'ending_id': 'historic', 'achievements': ['old'],
                           'commissions': []},
                'countries': [{'code': 'JP', 'unlocked': False,
                               'downloads_m': 55.0}]}
        first = save_manager._migrate(copy.deepcopy(base), 4)
        second = save_manager._migrate(copy.deepcopy(first), 4)
        self.assertEqual(first, second)
        self.assertEqual(first['version'], 5)
        self.assertEqual(first['countries'][0]['downloads_m'], 0.0)
        self.assertEqual(first['player']['ending_id'], 'historic')
        self.assertEqual(first['player']['achievements'], ['old'])
        for v in (1, 2, 3, 4):
            older = copy.deepcopy(base)
            older['version'] = v
            self.assertEqual(save_manager._migrate(older, v)['version'], 5)

    def test_v5_dirty_locked_value_is_logged_and_cleared(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import save_manager
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dirty.json'
            with patch.object(save_manager, 'SAVE_DIR', str(path.parent)):
                save_manager.save(str(path))
            d = json.loads(path.read_text(encoding='utf-8'))
            locked = next(c for c in d['countries'] if not c['unlocked'])
            locked['downloads_m'] = 99.0
            path.write_text(json.dumps(d), encoding='utf-8')
            original = path.read_bytes()
            with patch.object(save_manager, 'log_crash') as log:
                self.assertEqual(save_manager.load_ex(str(path))[0], True)
            log.assert_called_once()
            self.assertIn(locked['code'], log.call_args.args[0])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(next(c.downloads_m for c in engine.player_countries
                                  if c.config.code == locked['code']), 0.0)
```

测试里的过期 `active` 委托会被 `_apply_save` 既有过期过滤丢掉；迁移必须在该过滤之前将期限重置，这是特意设置的回归边界。

- [ ] **Step 2: 确认红灯。** `& $py -m unittest test_locked_country_economy.LockedCountrySaveTests -v`；预期 v4 未清理、委托丢失或版本断言失败。
- [ ] **Step 3: 实施迁移和加载防线。** `SAVE_VERSION = 5`；既有 `_v1_to_v2`、`_v2_to_v3`、`_v3_to_v4` 分别写目标字面版本 `2`、`3`、`4`。在 `_MIGRATIONS[3] = _v3_to_v4` 后加入：

```python
def _v4_to_v5(d: dict) -> dict:
    """锁国下载清零；活动下载委托按新口径公平重启。"""
    unlocked_total = sum(c['downloads_m'] for c in d.get('countries', [])
                         if c['unlocked'])
    for c in d.get('countries', []):
        if not c['unlocked']:
            c['downloads_m'] = 0.0
    ps = d.get('player', {})
    tick = ps.get('tick_count', 0)
    for com in ps.get('commissions', []):
        if com.get('status') == 'active' and com.get('goal') == 'downloads':
            com['snap_downloads'] = unlocked_total
            com['accepted_tick'] = tick
            com['deadline_tick'] = tick + com['window']
    d['version'] = 5
    return d


_MIGRATIONS[4] = _v4_to_v5
```

`load_ex` 的迁移 `try` 后再加一条 schema 异常分支，防止 v4 国家/委托结构损坏时 `TypeError`、`KeyError` 逃出：

```python
        except (TypeError, KeyError) as e:
            _log_load_fail(LOAD_BAD_SCHEMA, path, e)
            return False, LOAD_BAD_SCHEMA
```

此分支放在既有 `except (NotImplementedError, ValueError)` 之后。

在 `load_ex` 版本迁移之后、`_apply_save(data)` 之前，放入 `try` 范围内的防御归零；日志只用于**原生 v5 脏档**，避免正常 v4 迁移也报错：

```python
        dirty = []
        for cs in data.get('countries', []):
            if not cs['unlocked'] and cs['downloads_m'] != 0:
                dirty.append(cs['code'])
                cs['downloads_m'] = 0.0
        if dirty and v == SAVE_VERSION:
            log_crash('LOAD_NORMALIZED locked_downloads=' + ','.join(dirty))
        _apply_save(data)
```

保持既有 `except (KeyError, TypeError, ValueError, AttributeError)`，损坏 schema 仍返回 `LOAD_BAD_SCHEMA`。不要直接写回原存档；`save()` 已按当前版本自然输出 v5。已解锁国家的非数值下载字段走坏档路径；锁国字段无论原值为何均归零，不计入全球总量。

- [ ] **Step 4: 确认绿灯。** `& $py -m unittest test_locked_country_economy.LockedCountrySaveTests -v`，预期 `Ran 3 tests`、`OK`；`& $py test_edge_cases.py` 全通过。
- [ ] **Step 5: 提交。** `git add demo/save_manager.py demo/test_locked_country_economy.py`；`git commit -m "fix: migrate locked-country saves to v5"`。

### Task 4: 矩阵不覆盖历史基线，并完成回归/评审

**Files:** Modify `demo/balance_sim.py:552-565,697-714`; Create `docs/superpowers/verification/2026-09-18-locked-country-economy.md`。

- [ ] **Step 1: 添加失败测试。** 在 `demo/test_locked_country_economy.py` 增加：

```python
class MatrixOutputTests(unittest.TestCase):
    def test_matrix_explicit_output_directory(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import argparse
        import balance_sim
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_module = root / 'demo' / 'balance_sim.py'
            fake_module.parent.mkdir()
            requested = root / 'requested'
            args = argparse.Namespace(seeds=1, ticks=2,
                                      matrix_output_dir=str(requested))
            sample = dict.fromkeys(balance_sim.REGRESSION_FIELDS, 0) | {
                'ending_name': 'test', 'ticks': 2, 'penetration': 0.0,
                'suspicion': 0.0, 'unlocked': 2,
                'anomalies': {'bug_count': 0, 'review_count': 0, 'by_type': {}},
                'delta_hist': {}, 'doomed_pressure_tick': None,
                'doomed_crisis_tick': None, 'doomed_correct': False}
            with patch.object(balance_sim, '__file__', str(fake_module)):
                with patch.object(balance_sim, 'simulate', return_value=sample):
                    balance_sim.run_matrix(args)
            self.assertTrue((requested / 'playtest_baseline.json').exists())
            self.assertEqual(len(list((requested / 'playtest_reports').glob('*.md'))), 1)
```

此用例把模块路径也指向临时目录；加参数前会写入临时的默认目录，并因指定目录缺少 JSON 失败，不会碰真实的历史基线。

- [ ] **Step 2: 确认红灯。** `& $py -m unittest test_locked_country_economy.MatrixOutputTests -v`；预期目标目录缺少 JSON。
- [ ] **Step 3: 实现显式输出目录。** 在 `_run_matrix_inner` 中以以下表达式替换原固定 `data_dir` 的赋值：

```python
data_dir = (os.path.abspath(args.matrix_output_dir)
            if getattr(args, 'matrix_output_dir', None)
            else os.path.normpath(os.path.join(here, '..', 'tools', 'data')))
```

在 `main()` 的 `--matrix` 参数后增加：

```python
ap.add_argument('--matrix-output-dir', default=None,
                help='矩阵 JSON 和报告输出目录；不传沿用 tools/data')
```

- [ ] **Step 4: 确认绿灯及全套回归。** `& $py -m unittest test_locked_country_economy -v` 应全部通过。从工作树根目录运行：

```powershell
& $py demo/verify_tables.py
& $py demo/verify_tech_tree.py
& $py demo/test_edge_cases.py
& $py demo/test_build.py
git diff --check
```

预期前两项分别 `38/38`、`29/29`，后两项全部通过，`git diff --check` 无输出；任何失败先定位原因，不用改验收线掩盖。`test_build.py` 若沙箱临时文件阻塞，按本计划开头的精确命令升级权限重跑。

- [ ] **Step 5: 跑同规模平衡矩阵并记录差异。** 根目录运行：

```powershell
& $py demo/balance_sim.py --matrix --seeds 200 --ticks 200 --matrix-output-dir '..\locked-country-matrix-output'
```

预期 9 组合 × 200 局，输出 JSON 写到 `.workbuddy/locked-country-matrix-output/playtest_baseline.json`，**不能**覆盖已跟踪的 `tools/data/playtest_baseline.json`。基线与新矩阵各有 1800 局；比较每组 `summary.ending_dist`、`avg_ticks`、`avg_penetration`、`avg_unlocked`、`bug_count`、`review_count`，记录新值减旧值；另从模拟器 `--tutorial --seeds 30` 记录首危机和早期解锁节奏。差值可非零，但 bug 级异常须为 0；如结局严重偏斜，先报告并暂停下一项修复，不悄悄调数值。

```powershell
& $py -c "import json; from pathlib import Path; old=json.loads(Path('tools/data/playtest_baseline.json').read_text(encoding='utf-8')); new=json.loads(Path('../locked-country-matrix-output/playtest_baseline.json').read_text(encoding='utf-8')); keys=('avg_ticks','avg_penetration','avg_unlocked','bug_count','review_count'); [print(k, 'old_endings=', old['combos'][k]['summary']['ending_dist'], 'new_endings=', new['combos'][k]['summary']['ending_dist'], 'delta=', {f: round(new['combos'][k]['summary'][f]-old['combos'][k]['summary'][f], 4) for f in keys}) for k in old['combos']]"
& $py demo/balance_sim.py --tutorial --seeds 30
git status --short
```

预期逐组打印旧/新结局与 5 项差值，教程压力输出首危机/解锁统计；`git status` 不应显示历史基线被改动。

- [ ] **Step 6: 写验收记录。** 新文档使用以下固定结构，填入 Step 4/5 的**实测数值和命令退出码**，以及一个通过游戏读档 UI 检查的旧档顶栏/活动下载委托期限；未做的人工检查明确标记“未验证”，不可写“通过”。

```markdown
# 锁国经济口径验收（2026-09-18）

## 自动测试

| 命令 | 退出码 | 结果 |
|---|---:|---|

## 1800 局同种子矩阵对照

| 策略_难度 | 结局分布变化 | 平均局长 Δ | 平均渗透 Δ | 平均解锁国 Δ | bug/review 新值 |
|---|---|---:|---:|---:|---|

## 首局压力及人工边界

旧档 UI 顶栏；活动下载委托剩余期；首危机/早期解锁；未验证项及原因。

## 结论

是否存在 P0/P1 未解决问题；是否可继续下一项技能状态修复。旧档下载总量可能下降、活动下载委托重启计时；历史结局/成就不撤销。本轮不发布 exe。
```

- [ ] **Step 7: 评审和提交。** 检查 `git status --short` 不含真实存档/历史基线变更、`git diff --check` 通过；按 `superpowers:requesting-code-review` 做独立评审，修复 P0/P1 后重跑受影响测试。只暂存 `demo/balance_sim.py` 与验收文档：`git add demo/balance_sim.py docs/superpowers/verification/2026-09-18-locked-country-economy.md`；`git commit -m "test: record locked-country economy verification"`。

## 结束条件

所有任务复选框完成且证据齐备后，按 `superpowers:verification-before-completion` 复核最新测试输出；按 `superpowers:finishing-a-development-branch` 给出合并/保留选项。不要自动合并旧 A 分支或用户的主工作区修改。下一包技能状态修复需另开规格和计划。
