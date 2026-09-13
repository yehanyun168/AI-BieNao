# 04 · 开场动画播放状态持久化设计（`intro_seen`）

> 文档状态：**设计稿（未实现）** —— 本轮为只读调研，未改动任何 `.py`。
> 调研人：程基岩（工程负责人） · 任务 INTRO-V2-PERSIST-R01
> 所有行号基于本机 `game_optimization` 工作树当前代码（commit `94951f2` 之后、本任务之前的状态），
> 实现前请二次复核（尤其是 `main.py` —— 它离行数上限只剩 1 行，见 §7）。

---

## 0. 用户规则 → 判定式

用户原话：

> 「如果是在旧存档继续游戏并且已经播放过了的话，就不再出现动画。
> 如果是旧存档开启新游戏或者新存档开始新游戏那么就播放。」

翻译成判定式（实现必须逐条对齐）：

```
播放开场动画  ⟺  开始新游戏（存档新旧都算）
             OR  载入存档继续游戏 AND 该存档 intro_seen == False（含老存档无此字段）

跳过开场动画  ⟺  载入存档继续游戏 AND 该存档 intro_seen == True
```

⚠️ **判据是存档内的字段，不是「存档文件是否存在」**。后者是被明令禁止的旧逻辑（守卫见 §5）。

---

## 1. 存档结构

### 1.1 权威结构来自序列化器（不是 sample 文件）

`demo/saves/` 已被 `.gitignore:19` 忽略（`demo/saves/`），仓库里没有任何样例存档，
本机当前也没有现存存档 —— **唯一权威的存档结构定义在 `demo/save_manager.py:139-188` 的 `save()` 里**。

### 1.2 顶层字段清单（`save_manager.py:139-188`）

| 顶层键 | 行号 | 说明 |
|---|---|---|
| `version` | `save_manager.py:140` | `SAVE_VERSION`（当前 **3**，`:44`） |
| `saved_at` | `:141` | 时间戳字符串 |
| `player` | `:142-172` | 玩家状态（扁平字段 + 三个集合有序化） |
| `tech` | `:173-177` | `t0_unlocked` / `branch_levels` / `chosen_branch` |
| `countries` | `:178-187` | 每国 `code/unlocked/downloads_m/current_block_intensity/block_budget_remaining` |

`player` 层现有字段（节选，完整见 `:142-172`）：
`compute / compute_peak / suspicion / suspicion_peak / tick_count / events_history /
skill_cooldowns / selected_country / crisis_triggered / game_over / ending_id /
v2_cooldowns / v2_seen / achievements / **seen_tutorial** / unlocked_skills /
commissions* / last_commission_tick / compute_earned_total / skill_uses /
seed / difficulty / origin`

### 1.3 版本号与迁移机制

- `SAVE_VERSION = 3`（`save_manager.py:44`）
- 迁移骨架：`_migrate(data, from_version)`（`:331-359`）：`from_version == SAVE_VERSION` 原样返回；
  更小则沿 `_MIGRATIONS` 逐级升（缺环抛 `ValueError`）；更大（未来版本）→ 调用方按 `LOAD_BAD_VERSION` 拒。
- 已登记：`1 → _v1_to_v2`（`:296-307`，补 seed/difficulty，`_MIGRATIONS` 在 `:310`）；
  `2 → _v2_to_v3`（`:313-325`，补 `player.origin`，`_MIGRATIONS[2] = _v2_to_v3` 在 `:328`）
- 入口：`load_ex()`（`:362-426`）→ `:401-413` 版本分流 → `:417 _apply_save(data)`
- **`_apply_save` 的关键顺序：`:217 engine.init_game()` 先重建**全新** PlayerState，然后才逐字段覆盖**
  （`:220-293`）。所以任何"从存档恢复"的字段都必须写在 `:217` 之后。

### 1.4 「一次性看过」的现成范式：`seen_tutorial`

完全同构，直接照抄即可：

| 环节 | 位置 |
|---|---|
| 字段声明 | `engine.py:89-90`（`# —— 新手引导 ——` / `seen_tutorial: bool = False`） |
| 序列化 | `save_manager.py:157` `'seen_tutorial': bool(getattr(p, 'seen_tutorial', False))` |
| 反序列化 | `save_manager.py:235` `p.seen_tutorial = bool(ps.get('seen_tutorial', False))` |
| 判定（看过就跳过） | `tutorial.py:214-218` `maybe_start()`：`if engine.player is None or engine.player.seen_tutorial: return` |
| 置 True + 立即落盘 | `tutorial.py:473-482` `finish()`：`True` → `save_manager.save()`（`:477`）→ 失败 `save_manager.log_crash`（`:481`）留痕、**不阻断流程** |

### 1.5 `intro_seen` 放哪一层 → **建议放 `player` 层**

理由（四条，按重要性）：

1. **语义归属**：这是"这个存档的玩家有没有看过开场动画"，是 `PlayerState` 的状态，
   与 `seen_tutorial`（`engine.py:90`）完全同构；放顶层等于承认它是"存档文件级元数据"，
   但它并不描述存档文件，它描述的是这一局玩家。
2. **零新增通道**：`player` 层已有完整读写链路（`:157` / `:235`），加两行即可；
   放顶层要在 `_apply_save` 里额外 `data.get('intro_seen')` 开一路，与
   「顶层只有 `version / saved_at / player / tech / countries`」的既有约定冲突 ——
   该约定被 `test_edge_cases.py:489-490` 明确记录（PR-24 用例注释）。
3. **迁移路径一致**：`_v3_to_v4`（若走版本 +1）或 `.get(key, False)` 兜底，都作用在 `ps` 上，
   与 `_v2_to_v3` 补 `origin` 的写法一模一样。
4. **UI 读取最短**：`engine.player.intro_seen`，与 `main.py` 里其它 player 字段读法统一
   （如 `_log_run_info` 的 `getattr(p, 'origin', 'garage')`，`main.py:1384`）。

> `intro_seen` 的语义边界（建议写进字段注释）：
> **「这个存档所记录的这条游戏线，玩家已经看过开场动画了」**。
> `init_game()` 出来的**全新一局 = 没看过 = False（必须先播）**；读完老档后由 `_apply_save` 覆盖为存档里的值。

---

## 2. 「开始新游戏」调用链

### 2.1 主菜单 → 动画（**点「开始新游戏」立刻播，不等选出身**）

```
MainMenu._build()【主按钮区】                  main.py:722 起，按钮表 :750-764
  └─ 「▶ 开始新游戏」按钮 cb=self._fire_start              :755
MainMenu._fire_start()                                   :893-900
  └─ self._open_origin_flow(on_picked=λ oid: _open_new_game_modal(origin=oid, ...))
MainMenu._open_origin_flow(on_picked, slot_path=None)     :920-931
  ├─ :926 self._close_origin_flow()
  ├─ :927 player = intro.IntroPlayer(on_done=λ: self._show_origin_page(on_picked))   ★动画在此创建
  ├─ :928-930 size_hint=(1,1) / pos_hint={'x':0,'y':0} / self._origin_flow = player
  └─ :931 self.add_widget(player)                          ★全屏盖在 MainMenu 上
```

**结论：动画在点「开始新游戏」的那一刻就开始播，`IntroPlayer` 直接 `add_widget` 到 `MainMenu` 上
（`main.py:931`），播完 `on_done` 才 `_show_origin_page`。**

### 2.2 设置浮层「在某槽开新游戏」（同链路）

```
MainMenu._slot_actions()                   main.py:1127-1148
  └─ 空槽 → (t('slot_new_game'), λ: self._start_new_on_slot(p))            :1145-1147
MainMenu._start_new_on_slot(path)          :902-915
  └─ :908-915 self._open_origin_flow(slot_path=path, on_picked=λ: _open_new_game_modal(...))
       └─ 同上，动画在 :927 立刻播
```
另有键盘/槽位路径 `MainMenu._slot_pick` `:1177-1189`：空槽 → `_start_new_on_slot`（播）；
有档 → `_confirm_overwrite` `:1154-1175` → 确认后 `_start_new_on_slot`（播）。

### 2.3 动画之后：出身页 → 新档弹窗 → 真正开局

```
IntroPlayer 播完 / 跳过 → IntroPlayer._finish() → cb  (intro.py:198-205)
MainMenu._show_origin_page(on_picked)      main.py:933-948
  ├─ :935-937 remove_widget(self._origin_flow)   ← 摘掉动画层
  └─ :943-948 S.OriginPage(on_pick=_picked, on_cancel=_close_origin_flow)
       └─ _picked(oid)  :939-941  → _close_origin_flow()  → on_picked(oid)
MainMenu._open_new_game_modal(...)         :958-1058
  └─ 点「开始」_fire_start  :1041-1047 → pop.dismiss() → on_confirm(seed, diff_holder[0])
       └─ 回调到 _fire_start 的 λ        :896-900
RootView.start_new_game(seed, diff, origin)  :1303-1307
  ├─ :1306 engine.init_game(seed=..., difficulty=..., origin=...)   ★新 PlayerState 在此诞生
  └─ :1307 self._enter_game()
RootView._enter_game()                     :1356-1370
  ├─ :1357 clear_widgets()  :1358-1363 MainMenu._keyboard_closed()  :1294-1295 None
  ├─ :1364 self.game = GameUI(...)  :1365 add_widget
  └─ :1370 Clock.schedule_once(λ: tutorial.maybe_start(), 0.3)
```
带槽变体：`RootView.start_new_game_on_slot` `:1345-1354`
（`:1352 engine.init_game` → **`:1353 save_manager.save(path)`** → `:1354 _enter_game()`）。

### 2.4 对 `intro_seen` 的致命约束

`engine.py:203 player = PlayerState()` —— `init_game()` 每次都 **new 一个全新 PlayerState**，
`intro_seen` 会被重置为 False。

> ⚠️ **任何在动画期间（即 `init_game()` 之前）写入 `engine.player.intro_seen = True` 的尝试都会被抹掉。**
> 必须在 `init_game()` **之后**置位 —— 这是本设计最容易踩空的一处，见 §8 清单第 4 条。

---

## 3. 「继续游戏 / 载入存档」调用链（**当前完全不播动画**）

### 3.1 主菜单「继续」按钮

```
MainMenu._build()【主按钮区】                  main.py:722 起，按钮表 :750-764
  └─ 「■ 继续游戏（槽 xx）」 enabled=has_save, cb=self._fire_continue   :750, 756-757
MainMenu._fire_continue()                  :1060-1063
  └─ path = newest_save_path()  (:540-549) → self.on_continue(path)
RootView.start_load_game(path)             :1309-1326     ← on_continue 绑定于 show_menu :1296
  ├─ :1317 ok, reason = save_manager.load_ex(path)
  ├─ :1318-1320 if ok: self._enter_game(); return         ★ok 直接进局，全程无 IntroPlayer
  └─ :1321-1322 坏档/空槽：engine.init_game() → _enter_game()（同样不播）
```
键盘捷径同理：`MainMenu._on_key_down` `:1261-1263` `'c'` → `_fire_continue()`。

### 3.2 设置浮层 / 局内「读取」

```
MainMenu._slot_actions()[0]  :1139-1141  「读取」 → self._load_and_start(p)   :1150-1152
                                                    → self.on_continue(path) → 同上
SessionMixin._load_slot(slot)  ui_session.py:100-112  局内存/读
SessionMixin.do_load()         ui_session.py:128-138  读默认槽
```
均**不含 IntroPlayer**。

### 3.3 复核结论 ✅

> team-lead 的调研正确：**「继续游戏」链路当前一行动画都不播**。
> 全项目 `intro.IntroPlayer` 的唯一实例化点是 `main.py:927`，只能从
> `_fire_start`（`:895`）与 `_start_new_on_slot`（`:908`）两条"开新游戏"路径到达。

### 3.4 新增插入点 → 建议插在 **`RootView.start_load_game` `:1317` 与 `:1319` 之间**

```
RootView.start_load_game(path)             main.py:1309-1326
  :1317  ok, reason = save_manager.load_ex(path)
  :1318  if ok:
  ★NEW★  ├─ if not getattr(engine.player, 'intro_seen', False):
  ★NEW★  │      self._play_intro_then(lambda: self._enter_game(), mark_path=path)
  ★NEW★  │      return                       # 动画 on_done 里才 _enter_game()
         └─ :1319 self._enter_game(); return
```

为什么插这一层最干净（四个候选层对比）：

| 候选层 | 位置 | 评价 |
|---|---|---|
| **A. `RootView.start_load_game`** | `main.py:1317-1319` | ✅ **推荐**。此时 `load_ex` 已成功，`engine.player` 已是存档内容（含 `intro_seen`）；进局也只有 `_enter_game()` 一个出口（`1319`），单点控制不漏；改一处即覆盖主菜单「继续」+ 槽位「读取」两条入口。 |
| B. `MainMenu._fire_continue` | `main.py:1060-1063` | ❌ 此时存档**还没读**，拿不到 `intro_seen`；要 peek JSON 就要 File IO 二次解析，且绕开 `load_ex` 的迁移与容错，等于重造半个读档器。 |
| C. `_load_and_start` / `_slot_actions` | `main.py:1150` | ❌ 同上，而且只覆盖设置浮层这一条，主菜单按钮会漏。 |
| D. `_enter_game` 内部 | `main.py:1356` | ❌ 它被**新游戏**路径也调用（`:1307`、`:1354`），会把"读档"和"新开"两条语义混在一起，无法区分 —— 正是用户规则要求区分的那件事。 |

会话内 `_load_slot`（`ui_session.py:100-112`）/ `do_load`（`:128-138`）建议 **v2 第二期**再决定是否同样处理
（语义上也是"继续"，但它们在中途换档，且 `_load_slot` 之后有 UI 重建序列；本期保持一致地**不播**是最保守的选择）。

---

## 4. 存档写回时机

### 4.1 现有全部落盘点（全项目 `save_manager.save(` 调用一览）

| # | 时机 | 位置 | 类型 |
|---|---|---|---|
| 1 | 在某槽**开新游戏**：`init_game` 后立刻写槽 | `main.py:1353`（`start_new_game_on_slot`） | 写槽 |
| 2 | 局内「存到指定槽」 | `ui_session.py:95`（`_save_slot`） | 手动 |
| 3 | 局内「存档」（默认槽） | `ui_session.py:125`（`do_save`） | 手动 |
| 4 | **结局自动存档**（`report['ending']` 非空） | `ui_input.py:686-690`（在 `game_tick` 里） | 自动 |
| 5 | **新手引导完成自动存档** | `tutorial.py:477`（`finish()`） | 自动 |

明确不存在：**无周期结算存档、无 tick 自动存档、无退出时存档**
（`RootView.show_menu` `:1282-1301`、`App.on_stop` 附近的收尾代码均无 `save` 调用；
`ui_session.exit_to_menu` `:302-309` 也只停 tick + 回调）。
也没有"读档后立即回写"的逻辑。

### 4.2 建议：**动画「结束或被跳过」的那一刻立刻写回**

即 `IntroPlayer` 的 `on_done` 触发瞬间 —— 等价于照抄 `tutorial.finish()`（`tutorial.py:473-482`）的范式：

```python
# 伪码（实现见 §8）
engine.player.intro_seen = True
try:
    save_manager.save(path)          # path = 该存档的完整路径
except Exception as e:
    save_manager.log_crash(f'[intro] intro_seen 落盘失败：{e!r}')   # 留痕，绝不阻断进局
```

**理由：**

1. **不立刻写，用户的规则就落空一半。** 项目没有周期存档也没有退出存档 ——
   如果等到"第一次手动存 / 结局自动存"才落盘，那么
   「读旧档 → 看完 55 秒动画 → 玩了 20 分钟 → 强退 → 下次继续」会**再看一遍动画**，
   正是用户说"已经播放过了的话就不再出现"要禁止的情形。
2. **成本极低**：`save()` 是原子写（`.tmp` → `fsync` → `os.replace`，`save_manager.py:190-204`），
   一次 JSON 落盘；且此刻 `engine` 状态刚刚 `load_ex` 还原完毕（`save_manager.py:208-293`），
   序列化结果与磁盘上的原存档**逐字段等价，只多一个 `intro_seen: true`** —— 语义上就是"给这个存档打个勾"，没有副作用。
3. **失败安全**：沿用 `tutorial.py:478-481` 的 `try/except + log_crash`，写盘失败也照样进局；
   退化行为仅是"下次再看一遍动画"，**宁可重播，也不能因为一次写盘失败把玩家挡在门外**。
4. **跳过也算法看过**：用户点跳过同样表示"我知道这是开场动画了"，必须同样写 True。
   这是整个设计里唯一一处需要在 `IntroPlayer` 之外感知「动画已结束」的地方 ——
   但**不要让 intro.py 去碰 engine/save_manager**（L4 不得依赖 L3/L1 之外的东西，见 §7 层级守卫）。
   IntroPlayer 已经有 `on_done` 回调（`intro.py:198-205`，由 `_finish` 触发，**播完与跳过共用同一出口**），
   调用方（`RootView`）在回调里置位 + 落盘即可，**intro.py 一行都不用改**。 ✅

### 4.3 明确回答：玩家看了动画但没保存就退出，下次要不要重播？

> **不要重播。** 因为我们在动画结束时已经代为保存了一次。
> 只有当这次自动保存本身失败（磁盘满 / 只读 / 权限）时才会退化为重播 —— 可接受的最坏情况。

### 4.4 新游戏路径（对照）

- `start_new_game_on_slot`（`main.py:1345-1354`）：`init_game`（`:1352`）→ **置 True** → `save(path)`（`:1353`）。
  动画早在 `:927` 就播完了，此时补上 `intro_seen=True` 标记即可，随后那次写槽自带该字段，无需额外写盘。
- `start_new_game`（默认槽，`main.py:1303-1307`）：`init_game`（`:1306`）→ **置 True** → `_enter_game()`。
  此路径不落盘；标记随下一次手动存 / 结局自动存自然持久化。
  中间退出也没关系 —— 没有存档文件，"继续游戏"按钮本身就是 disabled（`main.py:750` `has_save`）。
- `restart_game`（`ui_session.py:311-326`）：`:312 engine.init_game()` 会重置 →
  建议也置 True（玩家本会话已经看过动画了，不能让一次重开把标记洗掉）。

---

## 5. 与旧守卫的冲突分析

### 5.1 旧守卫原文（`demo/test_build.py:739-745`）

```python
# 2026-09-13：每次新游戏都播开场动画——main.py 不得再有「仅首次播放」的
# 存档存在判定；intro.py 必须有触摸吞掉（防误触主菜单）与立即跳过。
assert "os.path.exists(target)" not in _main_src, \
    "main.py 仍保留仅首次播放的存档判定（应每次新游戏都播动画）"
for _needle in ('def on_touch_down', 'self._finish()'):
    assert _needle in open(os.path.join(_HERE, 'intro.py'),
                           encoding='utf-8').read(), f"intro.py 缺 { _needle }"
```

### 5.2 它当初拦的是什么

2026-09-13 之前，代码里的是

```python
if not os.path.exists(target):        # target = 目标存档路径
    play_intro()
```

即 **"存档文件不存在 → 这是新手 → 播动画；存档存在 → 老玩家 → 不播"**。
后果：**任何第二次开始新游戏的玩家都被静默跳过动画**（"我已经有 slot1.json 了，所以再也不给我看"）。
用户当时的要求是「**每次开始新游戏都播放**」—— 与用户今天的要求并不矛盾，只是**粒度太粗**。

### 5.3 新逻辑为什么**不冲突**

| | 旧逻辑（被禁） | 新逻辑（本次） |
|---|---|---|
| 判据来源 | **文件系统**：存档文件在不在 | **存档内容**：`player.intro_seen` 布尔 |
| 粒度 | 一个进程全局事实（这台机器有没有存档） | 每个存档各自的字段（slot1 看过 ≠ slot2 看过） |
| 新游戏体验 | ❌ 第二次开新游戏被吞掉动画 | ✅ 新旧存档开新游戏**一律播**（不受任何存档状态影响） |
| 读档体验 | ✅ 不播（但这是"因为文件在"，顺带的） | ✅ 看过才不播（首次读老档仍播一次，符合用户语义） |

关键点：**`intro_seen` 完全不参与"是否开始新游戏"的判定**，只在"载入存档继续"这条路径上起过滤作用。
旧守卫要防的是"用存档存在性去掐掉新游戏动画"，而新实现压根不在那条路径上出现 ——
`_fire_start`（`:895`）与 `_start_new_on_slot`（`:908`）到 `_open_origin_flow` 保持**无条件播**，不受任何存档字段影响。

> 甚至可以更严格：新游戏路径 `_open_origin_flow`（`main.py:920-931`）在实现后**不得出现任何 `intro_seen` 读取** ——
> 这本身就可以做成一条正契约断言（见 5.4 的第 3 条）。

### 5.4 建议的守卫改法

保留旧断言（它仍在正确地拦"文件存在性偷懒"），并**追加三条**新契约。
建议位置：`test_build.py` 第 739-745 行处（该文件当前 760 行，800 行上限有 **40 行余量**，放得下；
且"引入口判定"与 "intro.py 契约"的旧断言本来就在这里，改在一处便于追溯）：

```python
# ===== 开场动画播放判定契约（2026-09-13 旧约 + intro_v2 新约）=====
# 旧约（继续有效）：不得用「存档文件是否存在」决定播不播开场动画 ——
#   那会让第二次开新游戏被静默掐掉动画。
assert "os.path.exists(target)" not in _main_src, \
    "main.py 仍保留仅首次播放的存档判定（新游戏应每次都播动画）"
# 新约 1：真正的判据是存档内的 intro_seen 字段 —— 引擎要有字段、
#   save_manager 要能序列化 + 反序列化（含缺省值），缺一不可。
_sm_src = open(os.path.join(_HERE, 'save_manager.py'), encoding='utf-8').read()
assert "intro_seen" in open(os.path.join(_HERE, 'engine.py'),
                            encoding='utf-8').read(), \
    "engine.PlayerState 缺 intro_seen 字段（开场动画播放状态无处持久化）"
assert _sm_src.count("intro_seen") >= 2, \
    "save_manager 必须同时读写 intro_seen（序列化 + _apply_save 反序列化）"
# 新约 2：「开始新游戏」路径不得读 intro_seen —— 新旧存档开新游戏一律播。
_flow = _main_src.split('def _open_origin_flow')[1].split('def _show_origin_page')[0]
assert 'intro_seen' not in _flow, \
    "_open_origin_flow 不得判 intro_seen（开始新游戏无条件播动画）"
# 新约 3：「载入存档继续」路径必须读 intro_seen（否则读老档永远不播/永远播）。
_load = _main_src.split('def start_load_game')[1].split('def _show_load_fail_notice')[0]
assert 'intro_seen' in _load, \
    "start_load_game 未做 intro_seen 判定（读档继续时应按存档字段决定播不播）"
# 旧约（intro.py 侧，保持）：触摸吞掉（防穿透）+ 统一的 `_finish()` 收尾出口必须还在
for _needle in ('def on_touch_down', 'self._finish()'):
    assert _needle in open(os.path.join(_HERE, 'intro.py'),
                           encoding='utf-8').read(), f"intro.py 缺 { _needle }"
```

配套的行为守卫（**存读档往返 + 老档默认值**）建议加在 `demo/test_intro_skip.py`
（我上一轮为跳过契约建的独立文件，现 162 行，800 行上限余量充足，且它就是开场动画契约的归属文件）：

```python
# —— intro_seen 持久化契约（intro_v2）——
import json, os, tempfile, engine, save_manager

_tmpdir = tempfile.mkdtemp()
_path = os.path.join(_tmpdir, 'intro.json')

# 1) 写 True → 落盘 → 读回，必须保持 True
engine.init_game()
engine.player.intro_seen = True
save_manager.save(_path)
assert json.load(open(_path, encoding='utf-8'))['player']['intro_seen'] is True
assert save_manager.load(_path) and engine.player.intro_seen is True, \
    "intro_seen 必须跨存/读档保持（否则读档还会重播动画）"

# 2) 缺省必须是 False（老存档 / 无该字段 → 播一次）
_raw = json.load(open(_path, encoding='utf-8'))
_raw['player'].pop('intro_seen')
_raw['version'] = save_manager.SAVE_VERSION      # 同版本但缺键的老档形态
json.dump(_raw, open(_path, 'w', encoding='utf-8'), ensure_ascii=False)
assert save_manager.load(_path) and engine.player.intro_seen is False, \
    "缺 intro_seen 时必须默认 False（首次读老档要播动画）"

# 3) 若走了版本号 +1 方案，还要补一条：v{OLD} 老档经迁移链仍读得出 False
_raw['version'] = 3                              # OLD = SAVE_VERSION - 1
_raw['player'].pop('intro_seen', None)
json.dump(_raw, open(_path, 'w', encoding='utf-8'), ensure_ascii=False)
_ok, _reason = save_manager.load_ex(_path)
assert _ok and engine.player.intro_seen is False, \
    f"v3 老档迁移后 intro_seen 应为 False，实际 {_ok}/{_reason}"

import shutil
shutil.rmtree(_tmpdir, ignore_errors=True)
```

### 5.5 我上一轮写的 `demo/test_intro_skip.py` 是否需要同步调整？

**不需要。** 已逐条复核：它的 5 组断言全部落在"跳过机制本身的交互契约"上
（键位集合 / 无延迟常量 / 按钮构造即可见可点 / 点空白区跳过 / 按钮区不双触发 / 滚轮右键只吞不跳 / 双语键位提示），
**不含任何"每次都播 / 存档存在与否"的断言**，也不依赖 `_fire_start` 这类调用链。
`intro_v2` 落地后它照旧全绿；唯一建议是按 5.4 末尾**追加**一节持久化契约。

---

## 6. 老存档迁移默认值 → **复核结论：默认 `False`（播）** ✅ 同意 team-lead 的暂定

三条理由：

1. **符合用户原话的字面语义**：「已经播放过了的话，就不再出现」—— 老存档里**没有这条记录**，
   即"没有播放过的记录"，那就播一次。反过来说，默认 True 等于替老玩家做了一个他们没做过的决定。
2. **动画是新增内容（T16 才做出来）**：所有老存档都产生于"还没有开场动画"的版本，
   默认 True 会让 100% 的老玩家**永远看不到**这段刚做的内容 —— 这是最坏的结果。
3. **与项目既有缺省约定一致**：`seen_tutorial`（`save_manager.py:235`）、`unlocked_skills`
   （`:236-245` 缺键时从 STARTER_SKILLS 推导）、`origin`（`:273-276` 坏值兜底 garage）——
   项目的一贯约定是**缺键 = 最保守的"还没发生过"**，宁可补一次体验也不吞掉内容。

代价（可接受）：每位老玩家首次读旧档会多看一次 ~55 秒动画；
但**这次观看会被立刻落盘**（§4.2），第二次起不再播。

配套的两种实现写法（建议走 **A**）：

| 方案 | 做法 | 评价 |
|---|---|---|
| **A. 版本号 +1（3 → 4）** | `SAVE_VERSION = 4`；新增纯函数 `_v3_to_v4(d)`：`ps.setdefault('intro_seen', False)`、`d['version'] = SAVE_VERSION`；`_MIGRATIONS[3] = _v3_to_v4` | ✅ **推荐**。与项目约定（`save_manager.py:19-24`：改结构就 `SAVE_VERSION += 1` 并补一级纯函数迁移）完全一致；存档自描述"带不带该字段"，可审计。`_migrate`（`:331-359`）会自动沿链升级 v3 老档。 |
| B. 不升版本，靠 `.get` 兜底 | 只在 `:157` / `:235` 加读写 | ⚠️ 能跑，但违反项目既定约定，且未来无法从版本号判断"这个档有没有该字段"。 |

采用 **A** 时记得：`test_build.py:706` 里那条 `_raw['version'] = 2 → 期望迁移为 garage` 的用例
依然成立（2 < 4 仍属"更老版本"，沿 2→3→4 迁移），无需改动。

---

## 7. ⚠️ 隐性地雷：行数上限会在实现阶段直接拦 CI

`demo/verify_tables.py:576-619` 有一条 `demo/*.py 行数全部不超上限` 的守卫，
硬限 800 行，另有**冻结白名单**（`:577-604`）。当前实测：

| 文件 | 当前行数 | 冻结上限 | 余量 | 是否会被本任务突破 |
|---|---|---|---|---|
| **`engine.py`** | 1739 | **1739**（`:583-587`） | **0** | 🔴 **会**（加 1 行字段声明即 1740） |
| **`main.py`** | 1454 | **1455**（`:588-591`） | **1** | 🔴 **会**（继续游戏分支需 ~12-20 行） |
| `i18n.py` | 1342 | 1342（`:595-599`） | 0 | 本任务不涉及（别顺手加注释，我上一轮已踩过一次） |
| `save_manager.py` | 465 | 800（硬限） | 充足 | ✅ |
| `intro.py` | 503 | 800（硬限） | 充足 | ✅（本方案不改动 intro.py） |
| `test_build.py` | 760 | 800（硬限） | 40 | ✅（守卫追加 ~14 行放得下） |
| `test_intro_skip.py` | 162 | 800（硬限） | 充足 | ✅ |

> **实现阶段必须同步做"白名单再登记"**（项目既定做法：在 `LINE_LIMIT_WHITELIST` 注释里写明日期、
> 原值 → 新值、变更原因，如 `verify_tables.py:583-587` 里 `engine.py` 那条
> 「2026-09-13 再登记（原 1732）：… `PlayerState.origin` 字段 + `init_game(origin=)` 重写」就是同款先例）。
> 建议预告值：`engine.py: 1741`（+2：字段 + 注释）、`main.py: 1475`（+21）。

另有一条层级守卫 `verify_tables.py:385`：`'intro.py': 4`（L4）——
**本方案不往 `intro.py` 引入任何新 import**（判定与落盘全在调用方），层级不变。✅

---

## 8. 建议实现清单

改动落在 **4 个文件**（2 个生产文件 + 2 个测试文件），**`demo/intro.py` 一行不动**。

| # | 文件 | 位置（函数 + 行号） | 动作 | 说明 |
|---|---|---|---|---|
| 1 | `demo/engine.py` | `PlayerState` 数据类，`engine.py:89-90` 之后（`seen_tutorial` 下方） | **增 2 行** | `intro_seen: bool = False` + 注释「本存档是否已播过开场动画；缺键 / 全新一局 = False（必播）」。🔴 会突破 1739 冻结值 → 见 §7 再登记 |
| 2 | `demo/save_manager.py` | `save()` 序列化，`save_manager.py:157` 下方（`seen_tutorial` 同行之后） | **增 1 行** | `'intro_seen': bool(getattr(p, 'intro_seen', False))` —— 照抄 `:157` 的 `getattr + bool` 写法（防御旧对象无该属性） |
| 3 | `demo/save_manager.py` | `_apply_save()`，`save_manager.py:235` 下方 | **增 1 行** | `p.intro_seen = bool(ps.get('intro_seen', False))` —— 必须在 `:217 engine.init_game()` 之后（这里本来就在后面） |
| 4 | `demo/save_manager.py` | `SAVE_VERSION`（`:44`）+ 迁移链（`_v2_to_v3` 之后、`:328` 附近）+ 模块头注释 `:38-44` | **改 + 增 ~12 行** | 方案 A：`SAVE_VERSION = 4`；新增纯函数 `_v3_to_v4(d)`（`ps.setdefault('intro_seen', False)`）；`_MIGRATIONS[3] = _v3_to_v4`；并按项目惯例在 docstring 里写明「为什么是 False」 |
| 5 | `demo/main.py` | `RootView.start_load_game`，`main.py:1317` 与 `:1319` 之间 | **增 ~12 行** | ★核心：读档成功后 `if not getattr(engine.player, 'intro_seen', False):` → 播动画 → `on_done` 里再 `_enter_game()`；否则原样 `:1319 _enter_game()` |
| 6 | `demo/main.py` | 新增私有方法 `RootView._play_intro_then(self, done_cb, mark_path=None)`（建议放 `:1343` 之后、`start_new_game_on_slot` `:1345` 之前） | **增 ~18 行** | 挂载 IntroPlayer（照抄 `main.py:928-931` 的 `size_hint/pos_hint/_origin_flow/add_widget` 四件套），`on_done` 里：置 `intro_seen=True` →（有 `mark_path` 时）`try: save_manager.save(mark_path) except: save_manager.log_crash(...)` → `done_cb()`。失败安全照抄 `tutorial.py:476-481` |
| 7 | `demo/main.py` | `RootView.start_new_game`，`main.py:1306` 之后 | **增 1 行** | `engine.player.intro_seen = True` —— ⚠️ 必须在 `init_game()`（`:1306`）**之后**，否则被 `engine.py:203` 的新 PlayerState 抹掉 |
| 8 | `demo/main.py` | `RootView.start_new_game_on_slot`，`main.py:1352` 与 `:1353` 之间（夹在 init_game 与 save 中间） | **增 1 行** | `engine.player.intro_seen = True` —— 让 `:1353` 的写槽直接带上 True |
| 9 | `demo/ui_session.py` | `SessionMixin.restart_game`，`ui_session.py:312` 之后 | **增 1 行** | `engine.player.intro_seen = True`（局内重开不该把"看过"洗掉；否则下一次手动存档会把 False 写回去） |
| 10 | `demo/main.py` | `main.py:750` 附近 `_open_origin_flow` 的 docstring（`:921-925`） | **改注释** | 把「2026-09-13：每次开始新游戏都播开场动画」更新为 intro_v2 的完整判定式，避免注释与行为不符 |
| 11 | `demo/test_build.py` | `test_build.py:739-745`（替换旧守卫块） | **改 + 增 ~14 行** | §5.4 的断言代码（保留 `os.path.exists(target)` 旧断言 + 追加 3 条新契约） |
| 12 | `demo/test_intro_skip.py` | 文末（双语检查之后） | **增 ~28 行** | §5.4 末尾的持久化往返用例（True 往返 / 缺键默认 False / v3 迁移默认 False） |
| 13 | `demo/verify_tables.py` | `LINE_LIMIT_WHITELIST`，`:583-587`（engine）与 `:588-591`（main） | **改 2 行 + 补注释** | 白名单再登记，写明日期与变更原因（项目既定做法） |

### 实现顺序建议

1. `engine.py` 字段（#1）+ `save_manager.py` 读写与迁移（#2-#4）+两侧 §7 白名单登记 —— 最小可测单元，
   立刻跑 `#12` 的往返用例验证；
2. `main.py` 判定与辅助方法（#5-#8、`#10`）—— 换 `#11` 的新守卫；
3. 全量回归（见下）。
4. 最后再回头核对 `#13` 的最终行数与实际写入值一致。

### 验收命令（全部 exit=0）

```
cd C:/Users/tianm/WorkBuddy/workbuddy/game_optimization/demo
KIVY_NO_FILELOG=1 <py> verify_tables.py        # 🔴 最容易挂：engine.py / main.py 行数
KIVY_NO_FILELOG=1 <py> test_build.py           # 新守卫所在
KIVY_NO_FILELOG=1 <py> test_intro_skip.py      # 跳过契约 + intro_seen 往返
KIVY_NO_FILELOG=1 <py> test_ui_v4.py
KIVY_NO_FILELOG=1 <py> test_ui_v4_split.py
KIVY_NO_FILELOG=1 <py> test_sfx_assets.py
KIVY_NO_FILELOG=1 <py> test_cursor_fx.py
KIVY_NO_FILELOG=1 <py> verify_tech_tree.py
KIVY_NO_FILELOG=1 <py> test_edge_cases.py      # P0-2 读档容错 + 版本迁移
KIVY_NO_FILELOG=1 <py> balance_sim.py --seeds 30
```
`balance_sim --seeds 30` 必须**逐位不变**：11/7/6/3/2/1 局、平均 46.5 周期、36.26% 渗透、18.6/20 国
（`init_game` 里多一个字段不该影响任何随机数序列；若变了说明误改了 `engine.init_game` 的逻辑）。

---

## 9. 附：系统键盘单例对出身页 ESC 的影响（只读结论，本轮不修）

桌面端 Kivy（`keyboard_mode=system`，`allow_vkeyboard=False`）走 `Window.request_keyboard`
的**系统键盘分支**（`kivy/core/window/__init__.py:2449-2451`）：返回的是**同一个单例**
`_system_keyboard`，只改它的 `callback` / `target`；请求前会先 `release_keyboard(target)`，
其系统分支（`:2476-2481`）会**调用上一个持有者的 close 回调**。

推论链（已复核代码）：

1. `IntroPlayer.__init__` 请求键盘（`intro.py:114-117`）
   → `MainMenu._keyboard_closed()`（`main.py:1223-1226`）被调用
   → **`self._keyboard.unbind(on_key_down=self._on_key_down)`** —— MainMenu 从此收不到任何按键，
   一直到下一次 `RootView.show_menu()`（`main.py:1294-1299`）构造**新的** MainMenu 实例为止。
2. 因此 `MainMenu._on_key_down` 里那个 `if self._origin_flow is not None:` 分支
   （`main.py:1230-1236`）在 IntroPlayer 持键期间**是死代码** ——
   特别是 **`:1233-1235` 的「出身页按 ESC 取消流程」永远不会触发**，
   因为同一流程里 MainMenu 早在第 1 步就被解绑了。
   出身页的鼠标取消按钮仍然可用（`_show_origin_page` 传入的 `on_cancel`，`main.py:944`），
   所以表现为"ESC 退出出身页无效"，不是致命问题，但是个真实的体验缺口。
3. 动画收尾时 `IntroPlayer._finish` 调的 `_release_kb()`（`intro.py:155-167`，本轮我加的）
   会 `kb.release()` → 清掉 `_system_keyboard.callback`，
   之后由 `GameUI.__init__`（`main.py:450-451`）重新请求 —— 进局后键盘正常。

**对 intro_v2 的影响面：**
- 若在 `_enter_game()` **之前**播放（§3.4 推荐方案正是如此），GameUI 会在动画释放键盘之后才构造，秩序正确，无冲突。✅
- 若将来把动画挪到 GameUI 已创建之后播，IntroPlayer 会反过来抢走 GameUI 的键盘且**同样的 MainMenu 式解绑**会发生在 GameUI 上 —— 别这么做。
- **遗留的「出身页 ESC 失效」**不在本任务范围；建议另开一张小单：要么让 IntroPlayer 释放后主动把键盘还给 MainMenu
  （例如在 `_release_kb` 之后由调用方回调 `MainMenu._bind_keyboard()`），要么改用 `Window.bind(on_key_down=...)`
  这种不解绑的监听方式。我在这里只做影响面确认，不动代码。
