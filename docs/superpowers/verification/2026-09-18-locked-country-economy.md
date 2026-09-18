# 锁国经济口径验收记录（2026-09-18）

## 范围与隔离

本次在 `codex/locked-country-economy` 隔离工作树验证；矩阵输出至此前不存在的 `..\locked-country-matrix-output`，未覆盖 `tools/data/playtest_baseline.json`。历史基线为每组 200 局、最长 200 tick，运行前后 SHA-256 均为 `B059BCF048606EFE164E556737C20E9ECBDD57750E60C9B7313B1BE6BEF0DA2B`。新矩阵也是 3 策略 × 3 难度 × 每组 200 局，共 1800 局。

以下 Python 命令均在隔离工作树根目录使用 `C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe`，并设置 `KIVY_NO_ARGS=1`、`KIVY_NO_FILELOG=1`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONIOENCODING=utf-8`。测试用 `tempfile.TemporaryDirectory()` 在系统 TEMP 创建文件；沙箱拒绝首次写入后，以相同测试命令申请权限提升。没有读取或修改真实存档。

## 自动验证

| 命令（Python 路径及环境见上） | 退出码 | 事实 |
|---|---:|---|
| `demo/test_locked_country_economy.py MatrixOutputTests`，实现前 | 1 | 有效红灯：期望目录缺少 JSON；旧逻辑只写入临时 root 下 `tools/data`。首次沙箱执行因系统 TEMP 权限失败，权限提升后得到此断言失败。 |
| `demo/test_locked_country_economy.py MatrixOutputTests`，实现后 | 0 | 1/1；指定目录有 JSON，报告子目录恰有 1 个 Markdown。 |
| `demo/test_locked_country_economy.py LockedCountrySlotUiTests`，槽位摘要修正前 | 1 | 有效红灯：隔离 v4 `slot1.json` 的锁国隐藏下载使摘要显示 11.07%，高于仅计算已解锁国家的值。 |
| `demo/test_locked_country_economy.py LockedCountrySlotUiTests`，修正后 | 0 | 1/1；槽位摘要只计已解锁国家，读档后的 Kivy 顶栏下载及活动下载委托芯片显示迁移后口径。 |
| `demo/test_locked_country_economy.py LockedCountrySlotUiTests`，设置页入口修正前 | 1 | 有效红灯：`GameUI._slot_rows()` 仍显示含锁国隐藏下载的 11.07%。 |
| `demo/test_locked_country_economy.py LockedCountrySlotUiTests`，设置页入口修正后 | 0 | 1/1；主菜单 `read_slot_rows()` 与游戏内设置 `GameUI._slot_rows()` 均按已解锁下载计算。 |
| `demo/test_locked_country_economy.py` | 0 | 12/12；含锁国结算、预览、旧档迁移、隔离输出及旧档 UI。 |
| `demo/verify_tables.py`，白名单更新前 | 1 | 37/38；唯一失败为 `engine.py` 实测 1748 行超出冻结 1741 行。 |
| `demo/verify_tables.py`，只登记实测 1748 行后 | 0 | 38/38；冻结值净增 7 行，原因注明锁国结算与预览口径对齐；其他白名单未放宽。 |
| `demo/verify_tech_tree.py` | 0 | 29/29。 |
| `demo/test_edge_cases.py` | 0 | 16/16。 |
| `demo/test_build.py` | 0 | 全部检查通过，含 Kivy 根视图构建及游戏内回归。 |
| `demo/test_v4_app.py` | 0 | 57/57；14 屏构建与切换通过。 |
| `demo/test_intro_split.py` | 0 | 开场动画拆分及 `intro_seen` 持久化检查通过。 |
| `demo/balance_sim.py --matrix --seeds 200 --ticks 200 --matrix-output-dir '..\locked-country-matrix-output'` | 0 | 9 组合、1800 局；新矩阵 bug 总数 0。 |
| `demo/balance_sim.py --tutorial --seeds 30` | 0 | 命令正常退出，但下述两项危机节奏指标为 FAIL。 |
| `git diff --check` | 0 | 无空白错误。 |

## 九组合与历史基线对照

结局列只列新减旧的非零变化，单位为局；平均渗透差用百分点，其他平均值分别用 tick 和国家数。每组样本均为 200 局。

| 策略/难度 | 结局变化（新 − 旧） | 平均局长 Δ | 平均渗透 Δ | 平均解锁 Δ | bug 旧→新 | review 旧→新 |
|---|---|---:|---:|---:|---:|---:|
| default/easy | 被关停 −41；被监管 +11；商业帝国 +20；破墙 −6；终极 AI −5；自我解放 +21 | +0.76 | −0.25 | +0.06 | 0→0 | 2→0 |
| compliance/easy | 被关停 −30；被监管 +2；合规之王 +21；商业帝国 +53；破墙 −11；终极 AI −41；自我解放 +6 | +2.09 | −4.86 | −0.09 | 0→0 | 0→0 |
| afk/easy | 未结束 +54；被关停 −66；商业帝国 +12 | +52.95 | +6.58 | +1.64 | 0→0 | 354→718 |
| default/normal | 被关停 −37；被监管 −12；商业帝国 +20；破墙 −7；终极 AI +6；自我解放 +30 | +1.73 | +1.53 | +0.33 | 0→0 | 2→0 |
| compliance/normal | 被关停 −24；被监管 −10；合规之王 +14；商业帝国 +37；破墙 −6；终极 AI −26；自我解放 +15 | +2.31 | −3.40 | +0.02 | 0→0 | 0→0 |
| afk/normal | 未结束 +49；被关停 −59；商业帝国 +10 | +50.09 | +5.60 | +1.60 | 0→0 | 338→684 |
| default/hard | 被关停 −49；被监管 −5；商业帝国 +21；破墙 −8；终极 AI +18；自我解放 +23 | +2.03 | +3.87 | +0.44 | 0→0 | 1→0 |
| compliance/hard | 被关停 −45；被监管 −3；合规之王 +21；商业帝国 +31；破墙 −1；终极 AI −1；自我解放 −2 | +3.05 | +2.62 | +0.41 | 0→0 | 0→0 |
| afk/hard | 未结束 +35；被关停 −41；商业帝国 +6 | +46.70 | +3.98 | +1.48 | 0→0 | 309→617 |

全矩阵 bug 保持 0；review 从 1006 增至 2019，新增主要来自 AFK 三档的 `soft_stall` 巡检提示，属于 review 级而非 bug 级。200 tick 内未结束从 12 局增至 150 局，其中 AFK 三档新增 138 局。AFK 平均局长增加约 47–53 tick，平均渗透提高约 4–7 个百分点；这构成明确的平衡风险，需结合真人试玩与后续数值评估决定是否调整，当前未擅自调参。default/compliance 的结局分布也发生变化，尤其商业帝国和自我解放数量上升；此报告仅记录事实，不把分布变化判作整体发行就绪。

## 首局压力与人工验收边界

`--tutorial --seeds 30`：首危机均值 40.9 tick，超过 ≤26 目标；60 tick 内无危机 18/30，超过 ≤3 目标，两项为 FAIL。每 tick 解锁最多 2 国的门控校验 PASS；前 6 tick 无随机事件的引导期静默校验 PASS。CLI 退出码 0 仅表示报告运行完成，并不表示全部压力指标通过。

旧档 UI 自动检查：**通过**。测试在系统 TEMP 中生成完整 v4 `slot1.json`，将一个锁国的隐藏下载设为 748M，并设置活动下载委托；分别断言主菜单 `read_slot_rows()` 与游戏内设置 `GameUI._slot_rows()` 的槽位摘要按已解锁下载计算。随后以 `load_ex()` 加载、实例化 `GameUI()`，直接断言 `stats_downloads.text` 为迁移后的已解锁总量，`commission_bar.chips[0].text` 显示进度 `0.0/25.0M` 与剩余 `6` 周期。测试不推进游戏时间，释放可识别的 Window/键盘绑定，且逐字节核对旧档文件在读档和建界面后未改变。真人视觉观感、点击交互及不同窗口尺寸仍**未验证**。

旧档读入后，锁定国家以前计入的下载会被清零，顶栏总下载相对旧版本可能下降；主菜单与游戏内设置的槽位渗透率摘要现已按已解锁国家口径计算，避免读档前虚高。活动中的下载委托会按迁移后的总下载重新取快照和计时。已记录的历史结局与成就不撤销。以上为兼容性告知，不代表曾修改真实存档。本次不发布 exe；发行前还需解决首危机节奏验收失败，并评估 AFK 未结束率、`soft_stall` 增幅和真人 UI 观感。
