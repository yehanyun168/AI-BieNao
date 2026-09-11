# GDD-lite · 动态委托 + 政府反制（《AI 别闹》P0-3）

> 作者：文策渊（design-strategist）· 状态：待评审
> 数值均为「初始标定值」，最终由 TASK-B1 跑 `balance_sim --seeds 30` 定稿；本稿只给设计、挂接点与落点。
> 挂接点均已对照 engine.py / balance.py / conditions.py / tech_tree.py 现有代码核实（见 §6 汇总表）。

## 0. 问题与设计支柱

**现状**：一局均值 45.9 周期；中后期 20 国解锁完、科技买完 → 只剩等结局；自动策略滚向
「危机 → 抗封禁 T0 → 渗透 20% → 被监管」单一通路（43.3%）。

**支柱**：
1. **永远有一个 8 分钟内的目标** —— 委托是短期任务流，填充推图完成后的真空。
2. **世界会还手** —— 被阻止的国家不坐以待毙，惩罚「一条路走到黑」的偷取。
3. **不新增资源、不新增操作层级** —— 委托与反制只复用算力/怀疑度/阻止预算/现有技能与科技，杜绝认知过载。

红线自查：反制有预警、有上限（防随机暴击挫败）；委托奖励是小额零花非财源（防唯一最优解）。

## 1. 动态委托系统

### 1.1 节奏与槽位（全部进 TUNE）

| 参数 | 初始值 | 说明 |
|---|---|---|
| `commission_start_tick` | 8 | 首个委托出现周期（避开 P0-2 引导期 round 1–6） |
| `commission_interval` | 6 | 每隔多少周期尝试生成 1 条（槽位未满时） |
| `commission_max_active` | 2 | 同时在场委托上限（含待接受） |
| `commission_offer_ttl` | 3 | 待接受委托的存活周期数；超时视为玩家放弃，**无惩罚**（自主性支柱） |
| `commission_margin` | 1.5 | 目标值 = 预期自然增长 × 窗口 × margin（自标定，见 1.3） |
| `commission_margin_spread` | 0.4 | margin 实际取 uniform(margin−spread, margin+spread) → 同模板天然有难有易 |
| `commission_reward_compute_base` | 200 | 完成奖励算力基准 |
| `commission_reward_ramp` | 0.02 | 奖励 = base × (1 + 0.02 × 接单周期) |
| `commission_fail_suspicion` | 6.0 | 失败怀疑度惩罚（固定值） |

流程：到期生成 → toast + HUD chip 出现「接受 / 放弃」小卡（复用 `make_modal`）→ 接受后开始计时。
全局危机（suspicion ≥ 80）期间**暂停生成新委托**，在场委托照常走表（危机已是强压力源，见 §2.4）。

### 1.2 委托模板（6 条，`commissions.py` 数据表）

统一结构：`id / icon / 标题(zh+en) / goal 类型 / 时限窗口 / 奖励系数`。
时限窗口是**内容参数**放模板表（C1=12、C2=8、C3=8、C4=6、C5=8、C6=15 周期）；
可调平衡参数进 TUNE（上表），二者分工明确。
目标值全部**按接单时刻的实际经济自标定**（预期自然增长 × 窗口 × margin），
不写死绝对数——同一模板前期后期都成立，且天然免疫科技/难度改动造成的失衡。

| # | 模板 | 目标类型 | 具体示例（中期一局语境的演算样例） | 难度曲线 |
|---|---|---|---|---|
| C1 | 渗透攻坚 | 指定国渗透率提升 ≥ Δ | 「12 周期内让 RU 渗透率提升 2.1%」（Δ = RU 单周期增长 0.30M × 12 × margin 1.58 ÷ 144M） | 大国 Δ 大、小国 Δ 小；margin 随 spread 浮动 |
| C2 | 拉新冲刺 | 全球下载量净增 ≥ X | 「8 周期内全球新增 260M 下载」 | 随全局增长水涨船高 |
| C3 | 算力冲刺 | 窗口内累计偷取算力 ≥ C | 「8 周期内偷取算力 ≥ 1.9k」 | 与偷算力经济同源，永不通胀 |
| C4 | 技能特训 | 指定技能使用 ≥ K 次 | 「6 周期内使用 3 次『爆款制造』」 | K=2–3 静态；逼玩家练冷门技能 |
| C5 | 隐身行动 | 窗口内怀疑度始终 ≤ X | 「8 周期内怀疑度不高于 45%」 | 违约即刻失败；X 在 40–50 随 spread 浮动 |
| C6 | 开疆拓土 | 窗口内解锁 ≥ 1 新国家 | 「15 周期内解锁任意新国家」 | 后期邻国渗透普遍过阈值 → 变简单，作保底单 |

生成过滤规则（写进 `commissions.generate()`）：
- C1 目标国只在「已解锁且未饱和」或「锁定但 ≥1 个已解锁邻国」里选——防孤岛死单
  （呼应 data.py 注释里的 EG/ZA 邻国孤岛历史 bug）；
- C4 指定技能避开上一条委托的技能；生成时校验 `K ≤ floor(窗口 / 技能冷却)`，防软锁；
- 同一模板冷却 2 个生成位（代码内常量即可），防刷同款。

### 1.3 判定：全部用 conditions.py 的 cond 语法

引擎在阶段 6.6 为每条在场委托构造增量 ctx，用 `conditions.evaluate` 判定；
`verify_tables` 用 `collect_keys` 对字段名做交叉校验：

```python
# C1 渗透攻坚（生成时算好 Δ 写进实例）
{'target_pen_delta': 0.021}
# C2 拉新：ctx['downloads_delta'] = 当前全球总量 − 接单快照
{'downloads_delta': 260.0}
# C3 算力：ctx['compute_earned_delta'] = player.compute_earned_total − 快照
{'compute_earned_delta': 1900.0}
# C4 技能特训
{'skill_uses_delta.hit_maker': 3}
# C5 隐身行动（每周期检查，违约即失败）
{'suspicion': {'lte': 45}}
# C6 开疆拓土
{'unlocked_delta': {'gte': 1}}
```

需要引擎新增的快照源（各一行计数，挂接点真实存在）：
- `player.compute_earned_total`：阶段 2 末尾累加 `total_stolen`；
- `player.skill_uses: Dict[str, int]`：`use_skill()` 扣费成功处累加；
- C1/C2/C6 的基线在接单时存入 CommissionState（pen / downloads / unlocked_count）。

### 1.4 奖励 / 惩罚

- 完成：算力 `base × (1 + ramp × tick)`；C5 额外「怀疑度 −4」（风险回报对价）。
  进事件日志 + `_notify` toast（复用 ui_popups）。
- 失败（到期未达成 / C5 违约）：怀疑度 `+commission_fail_suspicion`；`commissions_failed += 1`。
- **设计约束**：奖励 ≈ 同期 1–2 个周期偷算力收入的小比例（约 5–10%），委托是「零花」不是「财源」。

### 1.5 与成就系统的联动

`build_achievement_context` 新增 `commissions_done / commissions_failed` 两个键，
新增 2 条条件型成就（20 → 22，**test_build.py 数量断言必须同步**）：

```python
Achievement('ACH_FIXER', '[W]', '金牌承包商', 'Fixer',
            '完成 10 个委托', 'Complete 10 commissions',
            cond={'commissions_done': 10}),
Achievement('ACH_CLEAN_SHEET', '[✓]', '零差评', 'Clean Sheet',
            '完成 5 个委托且零失败', 'Complete 5 commissions with none failed',
            cond={'all': [{'commissions_done': 5},
                          {'commissions_failed': {'eq': 0}}]}),
```

（远期联动：v2 事件型成就可改由「特殊委托」解锁——本期不做，只留接口。）

## 2. 政府反制机制（Counter-Op）

### 2.1 触发（引擎阶段 3.5，紧跟现有阻止结算）

每周期对每个**正在阻止**且**预算未耗尽**的国家掷一次：
- 门控：`current_block_intensity ≥ counterplay_intensity_gate`（0.4）；
- 概率 `counterplay_prob = 0.08`；每国冷却 `counterplay_cooldown_ticks = 12`；
- **1 周期预警**：命中先发日志/toast「DE 正在发起跨境协查…」，下一周期才结算——
  给玩家一周期反应窗（用 stealth / 压怀疑 / 换目标），反 RNG 挫败。

> 数值推论（设计有意为之）：intensity = min(0.8, excess×3.0)×(1−block_resist)，
> gate 0.4 ⇒ 怀疑度需 ≥ 阈值+13.3。低阈值国（DE58/FR60/RU60/IT62/GB65…）常态化反制，
> 高阈值国（IN92/CN85/ID88）只在怀疑度深红时出手 → 监管者有「性格分层」，也呼应 P1-3 vibe 差异化。

### 2.2 效果（三选一等权随机；数值全部进 TUNE）

| 类型 | 效果 | TUNE 键 / 初始值 | 打击什么 |
|---|---|---|---|
| 算力清缴 | 当前算力 −8% | `counterplay_compute_lose_pct` 0.08 | 「无视阻止继续全图偷」的经济滚雪球 |
| 预算增援 | 该国 block_budget_remaining +25%（按初始预算） | `counterplay_budget_reinforce` 0.25 | 延长阻止期，逼玩家绕路换目标 |
| 跨境协查 | 怀疑度 +3 | `counterplay_suspicion_gain` 3.0 | 全局压力，推高危机风险 |

三种幅度统一 × `(1 − effects['block_resist'])`——抗封禁分支
（traffic_obfuscation / community_armor，tech_tree 现有 id）自动成为反制答案，**不新增科技数据**。

### 2.3 玩家反制手段（全部复用现有系统，零新增操作）

1. 压怀疑度过该国阈值 → 强度按现有 `block_decay=0.7` 衰减 → 跌破 gate 反制停火（门控自带退出条件）；
2. S04 精准投放换目标：把偷取集中在非阻止国，单位怀疑增速更低；
3. 深度伪装（suspicion_mult 0.5）压全局斜率；
4. 抗封禁分支的 block_resist 直接削减反制幅度（见 2.2）；
5. 危机三选一仍是终极兜底（不重复造「平息」按钮）。

### 2.4 与危机弹窗的边界（明确共存规则，反制 ≠ 危机）

| | 危机（CRISIS_OPTIONS + resolve_crisis） | 反制（本设计） |
|---|---|---|
| 粒度 | 全局、一次性（压到 crisis_clear_ratio 才重置） | 国家级、周期性 |
| 交互 | 模态弹窗三选一 | 无弹窗：日志 + toast + 1 周期预警 |
| 量级 | 大额（±25–35 怀疑 / −600 算力 / ×0.85–0.92 下载） | 小额（≤8% 算力 / +3 怀疑 / +25% 预算） |
| 触发 | suspicion ≥ 80（engine 阶段 5，不改） | 阶段 3.5 概率 + 预警 |

三条硬规则保证不打架：
1. 反制怀疑度增量**截断在危机线下**：`delta = min(delta, SUSPICION_CRISIS − 1 − player.suspicion)`
   ——反制永远不会成为危机弹窗的直接触发者；
2. **全局危机期间反制挂起**（危机已在结算 CRISIS_DOWNLOAD_DECAY，双压过罚）；
3. 反制不写 crisis_triggered、不触碰 resolve_crisis 状态机，两套状态零共享。

## 3. 结局可达性调整方向（只给方向与理由，数值归 TASK-B1）

原则：cond 写法不动、只动阈值/组合结构，全部是 endings.py 数据改动。

| 结局 | 现状 | 调整方向 | 理由 |
|---|---|---|---|
| regulated（43.3%） | crisis + resistance_t0 + pen ≥ 0.20 | ① pen 抬到 0.25–0.30 方向；② 或加 `{'tick': {'gte': 40}}` 时间下限 | 0.20 是每个危机局最早够到的门槛，把 meta/ultimate/compliance 全吞了；抬门槛让「被监管」从默认结局变成「被拿捏后的现实选择」 |
| compliance_king | legal_shield_lv 3 + pen ≥ 0.25 | ① pen 降到 0.20 方向；② 或改 `any`：法律护盾 3 级 **或** `sum(keys=['branch_levels.legal_shield','branch_levels.community_armor','branch_levels.traffic_obfuscation'], gte=4)` | 单分支 L3 投入过重且与 empire 抢渗透节奏；放宽为「抗封禁路线身份」即触发，奖励玩法而非单点 |
| empire | pen ≥ 0.30 + 无危机 + susp ≤ 25 | 怀疑约束放宽：`suspicion_peak ≤ 35` 方向（或当前 ≤ 30） | 偷算力天然抬怀疑；双 25 门槛在均值 45.9 周期的局里几乎不可同时满足 |
| liberation | 仅 v2 隐藏事件 evt_meta_takeover | 数据侧：调高 weight / 降 cooldown（v2/events.json）；若 seeds 30 仍 <5%，加引擎保底「tick ≥ 60 未见过则强制入池」——唯一需 1 行引擎的项，需用户点头 | 纯概率不可达 ≠ 隐藏，是缺失 |
| meta | pen ≥ 0.40 + compute_peak ≥ 10000 | peak 阈值与成长曲线同调：若典型局峰值 4–6k，应落在可达 p85 区间（~7–8k），或同步抬高偷算力经济 | 10000 若超经济天花板则等价于关闭该结局（现 ACH_COMPUTE_BARON 才 3000） |
| shutdown / ultimate | 不动 | — | shutdown 是失败出口应保持；ultimate 是明牌长线目标 |

验收口径（与待办 P0-3 / P1-1 一致）：`balance_sim --seeds 30` 每结局 ≥5%，均值回合 30–50。

## 4. 边缘情况

1. **委托目标国永不开锁**（孤岛拓扑）→ 生成过滤（§1.2）；读档时校验 deadline > tick，否则转失败但**不计惩罚**（存档锅不算玩家头）。
2. **危机期内 C2/C3 目标不可达**（下载 ×0.97/周期衰减）→ 挂起新委托后在场单仍可能被拖死：到期按失败走，但危机期间失败的 `commission_fail_suspicion` **减半**（避免双重惩罚）。
3. **反制算力清缴时算力不足** → 百分比扣减天然 ≥0，仍 clamp max(0, …) 防负数路径。
4. **C5 与危机弹窗同周期** → 危机结算（阶段 5）先于委托检查（6.6）：本周期触发过 crisis 则 C5 违约检查跳过一次（弹窗打断不计违约）。
5. **C4 技能在冷却 / 算力不足** → 生成时已校验 K ≤ floor(窗口/冷却)；算力是玩家排程问题，不做软锁。
6. **老存档兼容** → 读档侧 default 补齐（commissions=[]，计数器 0），save_manager 加字段序列化。

## 5. 验收标准

- 引擎：`tick_one_round` 新 report 键（commission_offered / commission_done / commission_failed / counterplay）有值或 None；无 UI 依赖，无头可跑。
- 数据：`verify_tables` 通过——TUNE 新键同步进 `_REQUIRED`（否则 validate 报「未登记额外参数」）；委托 cond 字段做 collect_keys 交叉校验；engine 无新魔数。
- 平衡：--seeds 30 每结局 ≥5%；场均完成委托 6–10、反制 3–8 次；3 组种子方差 <15%。
- 成就：22 个全部可检（test_build.py 断言 20→22）。

## 6. 数值与实现落点汇总表

| # | 设计条目 | 文件 | 落点 | 预估 |
|---|---|---|---|---|
| 1 | 15 个 TUNE 键 + `_REQUIRED` + validate 规则（prob∈(0,1)、margin>1、max_active≥1） | balance.py | TUNE / _REQUIRED / validate() | 0.5h |
| 2 | 委托模板表 ×6 + CommissionState + 生成/判定纯函数 | commissions.py（新） | COMMISSION_TEMPLATES；依赖 commissions → conditions（数据层方向合规） | 3h |
| 3 | 引擎接线：阶段 3.5 反制 / 6.6 委托 / report 新键 / init 重置 / 危机挂起 | engine.py | tick_one_round 两处插入 + PlayerState 6 字段（commissions、commissions_done/failed、last_commission_tick、compute_earned_total、skill_uses） | 3h |
| 4 | 快照计数器挂接（阶段 2 累加 / use_skill 累加 / build_achievement_context 新键） | engine.py | 3 处单行 | 0.5h |
| 5 | 存档扩展 + 老档兼容 | save_manager.py | 序列化 active 委托列表 | 1.5h |
| 6 | 成就 ×2 + ctx 键 | achievements.py + engine | ACHIEVEMENTS 追加 | 0.5h |
| 7 | UI：委托 HUD chip（HudBox 一行，点击出 make_modal 详情/接受卡）+ offer/完成/失败/预警 toast + report 派发 | ui_hud.py / ui_popups.py / ui_input.py | 复用 _notify / make_modal | 5h |
| 8 | 中英文案 ~30 键 | i18n.py | ZH/EN 字典 | 1h |
| 9 | 自动策略接委托（全部接受）+ 回归跑 | balance_sim.py | auto_choice 风格 | 1h |
| 10 | verify_tables 扩展：委托 cond 字段校验 | verify_tables.py | collect_keys 交叉 | 0.5h |
| 11 | test_build 断言 20→22 + 委托/反制单测 | test_*.py | — | 1.5h |
| 12 | 数值标定迭代（TUNE + 结局阈值回归） | balance.py / endings.py | --seeds 30 × 若干轮 | 3h |
| | **合计** | | | **≈21h**（不含真人测试与 UI 打磨） |

依赖顺序建议：1 → 2 → 3/4 → 5 → 9（先无头跑通平衡）→ 7/8（UI）→ 10/11 → 12。
与 P0-2 的交界：`commission_start_tick=8` 避开引导期；引导事件优先级高于委托生成（阶段 6.6 在引导步进机活跃时跳过）。

## 7. 设计上最可能被用户挑战的 3 个点

1. **「委托奖励会不会变成第二个滚雪球？」** —— 奖励定为同期偷算力收入的 5–10% 小额零花，且 C3 目标与经济同源自标定、不存在正反馈通胀。若用户希望委托成为主要经济来源，需改静态奖励表——设计上不推荐（会破坏「免疫失衡」性质，且挤压偷算力主循环）。
2. **「反制是不是随机惩罚玩家？」** —— 三重保险：可见门控（强度 ≥40% 才出手，地图 [B] 标识可读）、1 周期预警、幅度 ×(1−block_resist)。若用户仍嫌打断节奏，备选方案：反制仅在怀疑度 50–80 区间生效（定位成「危机前奏」而非常态骚扰）。
3. **「被监管抬到 0.25–0.30 会不会违背『监管是常态』的叙事？」** —— 分布健康 vs 叙事压缩感的取舍。若用户想保叙事，替代方向：不动 pen，改为要求「危机 ≥ 2 次」（新增 crisis_count 计数器：1 行引擎 + ctx 键）——「屡教不改才被收编」，叙事更狠且不碰渗透语义。
