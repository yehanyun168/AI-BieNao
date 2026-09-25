# 技能队列效果与 combo 探针验证报告

日期：2026-09-25（Asia/Shanghai）

提交范围：`8a1d9e8..HEAD`（Task6 提交）

解释器：`C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe`（Python 3.12.10）

工作目录：`demo`；环境固定为 `KIVY_NO_ARGS=1`、`KIVY_NO_FILELOG=1`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONIOENCODING=utf-8`。

## 实现与红绿证据

- `auto_play(strategy='combo')` 仅在两技能均解锁、不在 queue/active/cooldown、联合成本可负担且两次 `skill_cast_reason` 均为 `ok` 后，按 `push_song`、`algo_top` FIFO 预约。意外失败不手工退款，也不预先声称形成 pair。
- `simulate` 每 tick 只读取真实 `report['skills_activated']`；同一报告同时含两个 ID 才把 `combo_pair_activations` 加一。字段只加入巡检结果，不加入 `REGRESSION_FIELDS`。
- `MATRIX_STRATEGIES` 保持严格的 `('default', 'compliance', 'afk')`，历史矩阵仍为 3×3；standalone CLI 才新增 `combo`。
- RED：`python -m unittest test_skill_queue_effects.ComboSimulationTests -v`，exit 1；FIFO 测试得到空队列，结算计数测试得到 `KeyError: 'combo_pair_activations'`。
- GREEN：同命令，exit 0，`Ran 2 tests ... OK`。结算计数用 `strategy='default'` 驱动真实引擎跨 tick 结算，排除按策略标签计数的假阳性。

## Fresh 回归命令

| 命令 | exit | 结果 |
|---|---:|---|
| `python -m unittest test_skill_queue_effects -v` | 0 | 44/44；首次受限运行因临时目录权限产生 14 errors，按同一命令提权重跑通过 |
| `python verify_tables.py` | 0 | 38/38；初次 37/38 仅行数守卫失败，按技能队列实际触及文件实测再登记：`engine.py 1779`、`i18n.py 1432`、`ui_hud.py 977`、`balance_sim.py 816`、`test_skill_queue_effects.py 1190`，未放宽其他文件 |
| `python verify_tech_tree.py` | 0 | 29/29 |
| `python test_edge_cases.py` | 0 | 16/16；首次受限运行为临时存档权限失败，提权原命令通过 |
| `python test_build.py` | 0 | 全部通过；受限运行在 challenge 临时账本阶段高 CPU，定位后提权原命令通过；未运行打包 |
| `python test_intro_split.py` | 0 | 全部通过 |
| `python test_v4_app.py` | 0 | 57/57 |
| `python balance_sim.py --strategy combo --seeds 30 --ticks 200` | 0 | 159 次真实 pair 结算 |
| `python balance_sim.py --matrix --seeds 200 --ticks 200 --matrix-output-dir C:\Users\tianm\WorkBuddy\workbuddy\game_optimization\.workbuddy\skill-queue-matrix-output` | 0 | 9 组合 × 200 局；独立 sibling 输出 |

combo 30 局结局：被关停 9、终极 AI 6、被监管 5、自我解放 5、商业帝国 3、元结局·破墙 2；平均局长 44.5 tick。该结果只证明探针发生真实结算，不把分布判为“平衡”。

## 旧/新 9 组合差异

旧基线：`locked-country-matrix-output/playtest_baseline.json`（2026-09-18）

新结果：`skill-queue-matrix-output/playtest_baseline.json`（2026-09-25）

两者均为 200 seeds、200 ticks、3 策略 × 3 难度。下表结局列顺序为：关停 / 监管 / 合规王 / 商业 / 破墙 / 终极 AI / 自我解放，括号为新减旧。

| 组合 | 平均局长 旧→新 | 七结局 delta | 未结束 旧→新 | bug / review 旧→新 |
|---|---:|---|---:|---:|
| default_easy | 45.555→45.705 | -3 / -9 / 0 / +12 / +13 / -9 / -4 | 0→0 | 0/0→0/0 |
| compliance_easy | 47.035→47.195 | +1 / -5 / +1 / 0 / +5 / -1 / -1 | 0→0 | 0/0→0/0 |
| afk_easy | 169.800→169.800 | 0 / 0 / 0 / 0 / 0 / 0 / 0 | 61→61 | 0/718→0/718 |
| default_normal | 46.585→46.760 | +1 / -12 / +1 / +11 / +9 / -8 / -2 | 0→0 | 0/0→0/0 |
| compliance_normal | 48.330→48.400 | -3 / -3 / +4 / -1 / +4 / -3 / +2 | 0→0 | 0/0→0/0 |
| afk_normal | 165.860→165.860 | 0 / 0 / 0 / 0 / 0 / 0 / 0 | 52→52 | 0/684→0/684 |
| default_hard | 47.240→47.485 | +2 / -17 / +1 / +7 / +3 / 0 / +4 | 0→0 | 0/0→0/0 |
| compliance_hard | 49.335→49.360 | +2 / -11 / +1 / +1 / +7 / -8 / +8 | 0→0 | 0/0→0/0 |
| afk_hard | 158.870→158.870 | 0 / 0 / 0 / 0 / 0 / 0 / 0 | 37→37 | 0/617→0/617 |

非 AFK 六组合局长仅增加 0.025～0.245 tick，但结局结构有明显漂移，尤其监管减少、商业/破墙增加；这是技能从“静默丢失”变为真实结算后的平衡复核信号，不应被回归通过掩盖。AFK 三组合逐位不变，证明 3×3 历史矩阵维度与零操作路径未被 combo CLI 探针污染。

### 既有风险

- 基线 JSON/报告没有 first-crisis tick 字段，只有最终 `crisis` 布尔值，因此不能伪造首危机时点比较。危机局数旧→新为：default easy 77→68、normal 102→87、hard 119→107；compliance easy 45→43、normal 74→72、hard 89→87；AFK 154/165/178 均不变。首危机节奏仍需专门埋点后另验。
- AFK 未结束风险保持：easy 61/200（30.5%）、normal 52/200（26.0%）、hard 37/200（18.5%）。AFK review 718/684/617 全为预期 `soft_stall`，但“预期”不等于可忽略；它仍揭示 200 tick 内没有收束的躺平局。
- 所有 9 组合 bug 均为 0；非 AFK review 均为 0。此次没有通过放宽阈值或修改玩法数值来消除异常。

## Review 修复与边界

- 完整预检覆盖解锁、queue、active、cooldown、联合成本和两次 reason，避免可预见的部分 combo。
- pair 只按真实结算报告统计；测试用非 combo 标签证明计数不依赖策略名。
- `REGRESSION_FIELDS` 未改变；`MATRIX_STRATEGIES` 未改变；未修改玩法数值、矩阵维度或历史 baseline。
- 行数守卫只按本技能队列功能实际触及文件的当前实测值再登记，并逐项留下原因。
- 历史 `tools/data/playtest_baseline.json` 开始前 SHA-256：`B059BCF048606EFE164E556737C20E9ECBDD57750E60C9B7313B1BE6BEF0DA2B`。结束复核必须相同。
- 视觉验证仅覆盖布局/几何与 UI 构建契约；SDL 自动化窗口可能黑屏，因此没有声称像素级视觉通过。
- 未运行打包、未生成或修改 exe。`test_build` 在隔离 worktree 生成的临时 `demo/saves` 与失败测试临时目录已删除，不保留真实 save 变更。

结论：规则包与回归套件通过，只说明实现满足当前契约；**规则包通过 ≠ 平衡完成 / 可发行**。结局漂移、首危机缺少时点埋点、AFK 未收束比例仍需后续平衡评审。
