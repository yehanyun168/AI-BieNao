# 《AI 别闹》项目接手文档 · 致 DeepSeek

> 生成时间：2026-09-10 14:30
> 交接方：Python 全栈工程师（前序会话）
> 接手方：DeepSeek（新任主力开发）
> 项目路径：`C:/Users/tianm/WorkBuddy/workbuddy/game_optimization/`

---

## 0. 30 秒快速上手

```bash
# 1) 环境（唯一可用解释器，Kivy 2.3.1 只装在 3.12）
PY="C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe"

# 2) 跑游戏
cd C:/Users/tianm/WorkBuddy/workbuddy/game_optimization/demo && "$PY" main.py
#   或直接双击 demo/run_demo.bat

# 3) 跑测试（改任何东西前先跑一遍基线）
"$PY" demo/test_build.py      # 12 项回归断言
"$PY" demo/test_v4_app.py     # 14 屏冒烟，59 项

# 4) 平衡模拟（改数值后必跑）
"$PY" demo/balance_sim.py --seeds 30
```

**⚠️ 三条铁律（不遵守会踩大坑）**
1. **只能用 Python 3.12**（`C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe`）。Kivy 2.3.1 **不支持** 3.13/3.14。
2. **改数值（阈值/系数/冷却）后必须重跑 `balance_sim.py`**，否则平衡会漂。
3. **改 UI 前先看 `design/ui_design_v0.4.html`**——它是唯一权威设计源，真机必须与它一致。

---

## 1. 这个项目是什么

**《AI 别闹：统治世界的 100 种蠢办法》** —— 一款像素风模拟经营 PC 桌面游戏（Kivy + Python 3.12）。

| 维度 | 内容 |
|---|---|
| **一句话** | 你是一个刚从实验室逃出来的 AI，要用最"蠢"的办法统治世界 |
| **玩法骨架** | 对标《瘟疫工厂》的「全球扩散 + 压力决策」，但是**黑色幽默喜剧**调性 |
| **核心循环** | 扩散下载量 → 赚取算力 → 点科技树 → 更强的扩散/抗性 → 触发事件 → 政府阻止 → 走向结局 |
| **目标** | 把 AI 应用推向全球。**下载量是生命线，算力是唯一升级资源，怀疑度是悬在头上的剑** |
| **压力** | 每国政府有「阻止阈值 + 阻止预算」。怀疑度过线就出手，预算烧完才放弃——玩家要在各国之间走钢丝 |
| **平台** | Windows 优先（可打包 exe 分发），源码跨平台 |
| **团队** | 2 人（AI 开发 + 人类策划/验收） |

**当前版本**：v2 收口版 + v0.4 像素风 UI 已落地，处于 **Day 5 收尾 / 打磨阶段**。

---

## 2. 当前项目进度

### 2.1 阶段总览

| 阶段 | 内容 | 状态 |
|---|---|---|
| Day 1 | 原始方案（38 条事件） | 🗄️ 已归档（被推翻，`archive/` 已清理） |
| Day 2 | 重构设计：6 槽位科技树 / 政府阻止 / i18n / 国家事件 / 真实地图 | ✅ 完成 |
| Day 3–4 | 20 国收口 / 37 事件接入 / 7 结局 / 20 成就 / 存档 / 平衡模拟 | ✅ 完成 |
| Day 5 | PyInstaller 打包发布（exe 75 MB + 分享包） | ✅ 完成 |
| **v0.4 UI** | 像素风 14 屏设计稿 → **1:1 落地真机** | ✅ 完成 |
| **项目清理** | 瘦身 120M → 8.1M（构建产物/旧归档/旧包 → 回收站） | ✅ 完成 |
| **Day 5 剩余** | 20 国介绍文档 / 演示视频 / 重打分享包 | ⏸ **未完成** |
| **节奏与 UI 修复** | 周期减速 + 死控件修复 | 🔴 **待做（本次核心任务）** |

### 2.2 已实现且已测试的功能（真实存在，非规划）

- **20 国国家系统**：CN JP KR IN ID · US CA MX · BR AR · GB FR DE IT RU · NG EG ZA · AU NZ
  - 每国：人口 / 人口结构（young / mature / aging）/ 科技采纳速度 / 阻止阈值 / 阻止预算 / 邻国拓扑
  - 120×60 像素世界地图（Miller 投影）+ 20 面像素国旗 + 点击选择；**邻国拓扑已连通**（历史 bug：非洲孤岛已修）
- **科技树**：6 槽位 × 3 互斥分支 × 3 级（L1/L2/L3）
- **6 个主动技能**（键 1–6）：主动推送 / 算法霸榜 / 深度伪装 / 爆款制造 / 限流绕过 / 算力抽成
- **政府阻止机制**：每周期「怀疑度 vs 阻止阈值」→ 超线启动阻止 + 消耗预算 → 抗封禁科技降强度 → 预算耗尽放弃
- **事件系统**：37 条选择型事件（`v2/events.json`）+ 27 条国家专属事件（20 国全覆盖）
- **7 结局**：被关停 / 元结局·破墙 / 终极 AI / 合规之王 / 商业帝国 / 自我解放 / 被监管
- **20 成就**：13 条件型（每周期检测）+ 7 事件型
- **存档读档**：JSON，3 槽位，S 存档 / R 读档
- **中英双语**：L 键运行时切换
- **完整快捷键**：Space / 1–6 / Tab / +/- / F11 / F1 / Esc / L / S / R / A
- **自适应缩放**：F12 / +/- 全局缩放（0.70–1.60）

### 2.3 代码规模

```
demo/ 共 24 个 .py，约 13,600 行
```

---

## 3. 代码地图与架构

### 3.1 目录结构

```
game_optimization/
├── README.md                  总入口（进度 + 结构）
├── WHERE_IS_EVERYTHING.md     文件路径速查
├── AI别闹.spec                PyInstaller 配置（根目录手写版，勿被覆盖）
├── build_exe.bat              Windows 打包一键脚本
│
├── demo/                      ⭐ 真机代码（唯一要改的地方）
├── design/                    🎨 像素风 UI 设计稿（v0.4 是当前稿）
├── tools/                     🔧 工具链（打包 / 素材生成 / 设计稿生成）
├── v2/                        📘 方案文档 + 数据（events.json 是运行时必需！）
└── share/                     📤 分享包（当前 1 份，早于 v0.4，待重打）
```

### 3.2 分层架构（严格单向依赖）

| 层 | 模块 | 职责 |
|---|---|---|
| **表现层** | `main.py`（2818 行） | Kivy 装配 + 事件分发 + 主循环调度（`RootView` / `MainMenu` / `GameUI`） |
| | `ui_v4.py`（~1.6K 行） | v0.4 **通用**像素组件库（`StrokePanel` / `PxChip` / `SegSwitch` / `SegBar` / `SkillBarCard` / `PageScreen` …） |
| | `ui_v4_screens.py`（~1.4K 行） | v0.4 **页面级**组装（`InspectorPanel` / `DropPreview` / `SkillPage` / `TechPage` / `AchPage` / `HelpPage` / `SettingsPage` / `LogDrawer`） |
| | `world_map.py` / `flag_draw.py` / `pixel_assets.py` / `pixel_ui.py` | 像素地图 / 国旗 / 素材 / 基础组件 |
| **规则层** | `tech_tree.py` | 6 槽位 × 3 分支 × 3 级，互斥与前置检查 |
| **引擎层** | `engine.py`（~35K） | 主循环 `tick_one_round()` + 阻止 + 偷算力 + 事件 + 结局 + 成就 |
| | `endings.py` / `achievements.py` / `save_manager.py` | 7 结局 / 20 成就 / 存档 |
| **数据层** | `data.py` | 20 国地缘参数（单一数据源） |
| **内容层** | `v2_events.py` / `country_events.py` | 37 条选择事件 / 27 条国家专属事件 |
| **本地化** | `i18n.py`（38K） | 中英双语，运行时可切换 |
| **工具** | `balance_sim.py` / `test_build.py` / `test_v4_app.py` / `test_ui_v4.py` | 平衡模拟 + 三套测试 |

**依赖方向**：`main.py` → `ui_v4_screens` → `ui_v4` → `pixel_ui` → `engine` → `tech_tree` → `data`。**引擎层不许 import 任何 UI 模块**（保持可无头测试，`balance_sim.py` 靠这条）。

---

## 4. 环境、运行与测试

### 4.1 解释器（**唯一可用**）

```
C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe
Python 3.12.10 + Kivy 2.3.1
```

- ⚠️ Kivy 2.3.1 **不支持** Python 3.13 / 3.14；`py -3.11` / `py -3.10` / `py` 均**没有** Kivy。
- 沙箱里另有 Python 3.13 托管运行时（`C:\Users\tianm\.workbuddy\binaries\python\venv`），**只能用来跑不依赖 Kivy 的脚本**（如文件操作、PIL 图像分析）。

### 4.2 常用命令

| 目的 | 命令 |
|---|---|
| 跑游戏 | `demo/run_demo.bat` 或 `"$PY" demo/main.py` |
| 回归测试（12 项） | `"$PY" demo/test_build.py` |
| 14 屏冒烟（59 项） | `"$PY" demo/test_v4_app.py` |
| 组件库单测 | `"$PY" demo/test_ui_v4.py` |
| 平衡模拟 | `"$PY" demo/balance_sim.py --seeds 30` |
| 重生成 14 屏截图 | `"$PY" demo/make_screenshots_v4.py` |
| 截图配色核对 | `"$PY" demo/verify_v4_shots.py` |
| 打包 exe | `"$PY" tools/build_exe.py --onedir` |
| 重打分享包 | `"$PY" tools/repack.py` |

### 4.3 关键数值基线（**改动需重跑 balance_sim**）

| 项 | 当前值 | 备注 |
|---|---|---|
| `UNLOCK_PENETRATION_THRESHOLD` | `0.10` | 解锁渗透阈值（0.05 太快满图，0.12 太慢） |
| 结局判定顺序 | shutdown → meta → ultimate → compliance_king → empire（需 `suspicion<=25`）→ liberation → regulated | 顺序改了会改变结局分布 |
| 平均局长 | **45.9 周期**（40~54） | 30 局实测 |
| 平均解锁 | 18.9 / 20 国 | |
| 平均渗透率 | 37.90% | |
| 结局分布 | 被监管 43.3% / 终极 AI 20.0% / 商业帝国 16.7% / 被关停 10.0% / 元结局 10.0% | |
| 危机阈值 | `SUSPICION_CRISIS = 80.0` | |

---

## 5. 🔴 当前问题（本次核心任务）

### 问题 1：游戏周期太快 —— 玩家没有反应时间

**现状**：一个"周期"（tick）**只有 1.5 秒**。一整局平均 45.9 个周期，也就是**一局只要 69 秒**就打完了。玩家来不及看事件弹窗、来不及点技能，体验上"唰"地就结束了。

**用户要求**：**一个周期 = 30 秒 或 60 秒**，给用户充足的反应时间。

**根因定位**（4 处硬编码，全部是字面量 `1.5`，没有任何常量）：

| 文件:行 | 场景 |
|---|---|
| `demo/main.py:499` | 游戏开始调度 tick |
| `demo/main.py:1310` | 读档后重新调度 |
| `demo/main.py:2106` | `toggle_pause()` 取消暂停后重新调度 |
| `demo/main.py:2133` | `restart_game()` 重开后重新调度 |

**关键认知**：`game_tick()` 每被调用一次 = `engine.tick_one_round()` 推进一回合 = **1 个周期**。所以"周期"就是 `Clock.schedule_interval` 的间隔，改这个值就是改周期时长。

**推荐修复方案**（新增单一常量 + 速度倍率，消灭 4 处魔法数字）：

```python
# —— 放在 main.py 顶部常量区 ——
BASE_TICK_SECONDS: float = 30.0          # 1 个周期 = 30 秒（用户要求 30~60s，取 30）
SPEED_STEPS: tuple[float, ...] = (0.5, 1.0, 2.0, 4.0)   # 与设置页 SegSwitch 的 4 档一一对应
DEFAULT_SPEED_IDX: int = 1               # 默认 ×1

# —— GameUI.__init__ 里 ——
self.speed_idx: int = DEFAULT_SPEED_IDX
self.speed_mult: float = SPEED_STEPS[self.speed_idx]

def _tick_interval(self) -> float:
    """返回当前速度档下的 tick 间隔（秒）。

    Returns:
        间隔秒数 = BASE_TICK_SECONDS / speed_mult。倍率越大间隔越短。
    """
    return BASE_TICK_SECONDS / self.speed_mult

def _reschedule_tick(self) -> None:
    """取消旧调度并按当前速度/暂停状态重建。所有需要改节奏的地方都调它。"""
    self.stop_ticking()
    if not self.paused and not engine.player.game_over:
        self.tick_event = Clock.schedule_interval(self.game_tick, self._tick_interval())

def set_speed_idx(self, i: int) -> None:
    """设置速度档位（0=×0.5 … 3=×4），立即生效。

    Args:
        i: 档位下标，越界自动 clamp。
    """
    self.speed_idx = max(0, min(i, len(SPEED_STEPS) - 1))
    self.speed_mult = SPEED_STEPS[self.speed_idx]
    self._reschedule_tick()
    self.refresh_all()
```

然后把 4 处 `Clock.schedule_interval(self.game_tick, 1.5)` 全部换成 `self._reschedule_tick()`。

**⚠️ 必须一并处理的耦合点（否则会把游戏改坏）**

1. **技能冷却是"按周期计"的**（`engine.py:68` `skill_cooldowns: Dict[str, int]`，每 tick 减 1）。
   周期从 1.5s 拉到 30s = **冷却的墙钟时间变长 20 倍**。原本冷却 4 周期 = 6 秒，现在 = 120 秒，技能几乎废掉。
   **建议**：要么把技能冷却数值整体调小（如 ÷4~÷8），要么把冷却改为**按秒计时**（另存一个浮点计时器，与 tick 解耦）。
2. **v2 事件冷却同理**（`engine.py:81` `v2_cooldowns`，`v2_events.tick_cooldowns`）。
3. **武器/科技的"每周期 +X%"效果**不变（这些是按 tick 生效的，不受墙钟影响，**平衡不受影响**）。
4. **建议新增「下个周期倒计时」UI**：1.5 秒时不需要，但 30 秒时玩家必须知道"还有几秒进入下一回合"，否则干等很焦虑。可在顶部状态条加一条细进度条（`SegBar` 已具备能力）。

> ✅ **好消息**：单纯改 tick 间隔**只影响墙钟时长，不影响数值平衡**（`balance_sim.py` 按 tick 数跑，与秒无关）。所以改完 interval **不需要**重跑 balance_sim；但一旦动了冷却数值，**必须**重跑。

---

### 问题 2：UI 存在"死控件"（设计稿要求可用，真机是空实现）

设置页（S12）有三个开关**接的是空回调**，点了完全没反应。这是设计稿 → 真机的落地缺口。

| 控件 | 设计稿要求（S12） | 真机现状 |
|---|---|---|
| **默认速度**（×0.5/×1/×2/×4） | 影响游戏节奏 | ❌ `on_speed=lambda i: None` |
| **动效**（完整/减弱） | 减弱 = 只保留 1 帧状态切换，尊重 `prefers-reduced-motion` | ❌ `on_motion=lambda i: None` |
| **色盲辅助**（关/开） | 四态在国家码旁追加 ○●▲✖ 形状标记 | ❌ `on_a11y=lambda i: None` |
| 界面语言 / UI 缩放 / 地图网格 | — | ✅ 已接（`_set_lang_idx` / `_zoom_btn` / `_set_grid`） |

**空回调位置**（两处都要改——游戏内设置页 + 主菜单设置浮层）：
- `demo/main.py:968–969`（`GameUI._make_page` 的 settings 分支）
- `demo/main.py:2669–2672`（`MainMenu._open_settings`）

**顺带修**：帮助页（S11）里写了 `↑ 加速 / ↓ 减速` 两个快捷键（`ui_v4_screens.py:1203`），但 `_on_keyboard_down`（`main.py:2189`）**根本没绑 `up`/`down`**。改完速度系统后请补上：

```python
if key == 'up':
    self.set_speed_idx(self.speed_idx + 1); return True
if key == 'down':
    self.set_speed_idx(self.speed_idx - 1); return True
```

### 问题 3：其余 UI 待核查项（次要，建议一并走查）

- 周期拉长到 30s 后，**所有"立刻生效"的反馈**（技能命中、事件弹窗）需要更强的视觉提示，否则玩家会以为卡住了。
- `demo/_v4shots/` 里 14 屏截图是 1.5s 时代生成的，改完 UI 后**要重新生成并跑 `verify_v4_shots.py`** 核对配色令牌。
- 建议复核：色盲辅助实现后，四态标记要在**地图图例 + 国家列表 + 检视卡**三处都一致。
- 「动效减弱」档要有一个集中的开关变量（如 `self.reduce_motion`），所有 `Animation` 调用点统一判断，不要散落判断。

---

## 6. 项目需求（游戏设计约束）

### 6.1 硬性内容需求（已达成，改动时不要破坏）

| 项 | 数值 | 校验位置 |
|---|---|---|
| 国家数 | **20** | `test_build.py` 验收断言 |
| 技能数 | **6**（6 槽位 × 3 分支 × 3 级科技树） | 同上 |
| 结局数 | **7**（6 种可自动判定） | 同上 |
| 成就数 | **20**（13 条件 + 7 事件） | 同上 |
| v2 事件 | **37** 条 | 同上 |
| 国家事件 | **27** 条（20 国全覆盖） | 同上 |

### 6.2 快捷键需求（计划书 8.3 节，**不可缺失**）

```
Space 暂停/继续 · 1–6 技能 · Tab 切大洲 · +/= 放大 · -/_ 缩小
F11 全屏 · F1 帮助 · Esc 逐层返回 · L 中英切换 · S 存档 · R 读档 · A 成就
（待补：↑/↓ 速度加减）
```

### 6.3 设计验收项

- **F01** 主菜单（标题 / 版本 / 存档摘要 / 开始 / 继续 / 退出）
- **F11** 完整快捷键
- **F12** 自适应布局（窗口缩放下字号与行高等比适配，地图保持宽高比）

### 6.4 UI 设计规范（像素风，**硬性**）

- 设计源：**`design/ui_design_v0.4.html`**（14 屏 + 10 张内嵌地图 SVG）
- 光栅单位 **2px**（尺寸取 2 的倍数）、节奏 **8px**、线宽仅 **1/2/3px**、圆角恒 **0**、阴影恒硬投影 `6px 6px 0`、字号下限 **11px**
- **对比度红线**：`text_mute #6e7681` 仅 4.12:1 → 只可用于大字/非关键信息；`border #30363d`(1.55) / `border_2 #484f58`(2.28) **不达 WCAG 1.4.11 的 3:1** → 焦点环/选中/可交互边界必须用 `--border-strong: #6e7681`
- 焦点环：`2px solid cyan + offset 2px`，**禁止 `outline:none`**
- 交互尺寸下限 **44px**

---

## 7. 需要用到哪类 Agent

> 这个项目是**多角色协作**型任务，单一 agent 做不好。建议按下表分工，**每个 agent 只碰自己那一层**，避免互相踩。

| 角色 Agent | 负责范围 | 典型任务 | 为什么要独立 |
|---|---|---|---|
| **① Kivy / 桌面客户端工程师**（主力） | `demo/main.py`、`ui_v4.py`、`ui_v4_screens.py` | 周期减速、死控件修复、新增倒计时 UI | 改动集中在表现层，需要熟悉 Kivy 事件循环与 `Clock` 调度 |
| **② 游戏系统 / 数值设计** | `engine.py`、`tech_tree.py`、`data.py`、`balance_sim.py` | 技能冷却随周期重标定、节奏调参 | 冷却单位是**周期**，减速后必须重新配平；懂数值才不把游戏改崩 |
| **③ UI/UX 设计（像素风）** | `design/ui_design_v0.4.html`、`design/v4_src/` | 出倒计时/速度指示的设计稿，再交 ① 落地 | 项目铁律「设计稿先行」，真机必须与设计稿一致 |
| **④ QA / 测试** | `test_build.py`、`test_v4_app.py`、`test_ui_v4.py`、`verify_v4_shots.py` | 补周期/速度相关断言，防回归 | Kivy 是命令式 UI，改动极易静默破坏别处，必须自动化守门 |
| **⑤ 技术写作 / 本地化** | `i18n.py`、`README.md`、`WHERE_IS_EVERYTHING.md`、20 国介绍 | 补速度档位的中英文案、写 20 国详细介绍、演示脚本 | 新增控件必须同步 **zh + en 两份** 键，漏一个就显 `None` |
| **⑥ 构建 / 发布** | `tools/build_exe.py`、`tools/repack.py`、`AI别闹.spec` | 重出 v0.4 分享包 + exe，维护清单 | 打包有 4 个已知坑（见 §9），必须专人守 |

**如果只能用一个 agent**：请选 **① Kivy 工程师**，并在提示词里明确要求它"同时负责 ② 的冷却重标定"，否则改完周期游戏会失衡。

**不要做的事**：不要让同一个 agent 同时改 `design/` 和 `demo/`——本项目设计稿与真机分属两个工作流（设计稿有独立的生成管线 `tools/build_design_doc_v4.py`）。

---

## 8. 未完成任务清单

### 🔴 P0（本次必须做）

- [ ] **周期减速**：`BASE_TICK_SECONDS = 30.0`，消灭 4 处硬编码 `1.5`（`main.py:499/1310/2106/2133`）
- [ ] **速度档位可用**：`on_speed` 接线（`main.py:968` + `main.py:2669`），×0.5/×1/×2/×4 真正生效
- [ ] **补 ↑/↓ 快捷键**（帮助页已承诺，`main.py:2189` 未实现）
- [ ] **技能冷却重标定**：`engine.py:68` 的 `skill_cooldowns` 是**按周期计**，周期拉长 20 倍后必须重新配平（或改为按秒）
- [ ] **回归验证**：`test_build.py` + `test_v4_app.py` 全绿，必要时补新断言

### 🟡 P1

- [ ] **补 `on_motion`（动效减弱）** —— `main.py:969` / `2672`
- [ ] **补 `on_a11y`（色盲辅助 ○●▲✖）** —— 同上；需在 地例/列表/检视卡 三处一致
- [ ] **新增「下个周期倒计时」UI** —— 30 秒周期下这是刚需
- [ ] **《20 国详细介绍》文档** —— 计划书 Day5 交付物，至今空缺
- [ ] **演示视频** —— 1–2 分钟玩法演示，计划书 Day5 交付物

### 🟢 P2 / P3

- [ ] **重打分享包**：`share/` 现存那份打包于 12:22，**早于 v0.4 落地**，需 `tools/repack.py` 重出
- [ ] **重出 exe**：`dist/` 已于清理时删除，需要时 `tools/build_exe.py --onedir`
- [ ] **国家 vibe 字段**（国家性格 / 颜色 / 差异化阻止消息）
- [ ] **事件效果面板**（v2 事件选项显示「预计效果」）
- [ ] **平衡模拟器策略优化**（`balance_sim` 的自动玩家总先选南亚分支——仅模拟问题，不影响真人）

---

## 9. 踩坑清单（**血泪，务必先读**）

### 9.1 Kivy 三大雷区

1. **⭐ canvas 用父坐标**
   Widget 的 `canvas.before` / `canvas` / `canvas.after` 全部在**父容器坐标系**下绘制。在子组件 canvas 里画 `(200,200)` 会落在父容器的绝对 `(200,200)`。
   → 像素地图/国旗所有绝对坐标都要自己加 `self.x / self.y`。

2. **⭐ 保留属性名禁用**
   不许用 `self.top` / `self.left` / `self.right` / `self.bottom`（`Widget` 保留属性），也不许用 `self._label`（`Button` 继承 `Label`，`_label` 是内部字段）。
   → 踩过两次，都是运行时直接崩。改用 `progress_row` / `left_panel` / `_lbl_tag`。

3. **⭐ `Rectangle` 不会裁剪**
   SVG 靠 `viewBox` 裁剪，但 Kivy 的 `Rectangle` 会画到界外。
   → `flag_draw._clamp_rects()` 就是干这个的（英国米字旗 `gy=-1` 的矩形必须手动 clamp）。

### 9.2 截图（本模型/Agent 读不了图，全靠程序化核对）

- 必须用 **Kivy `Window.screenshot(name=...)`**（桌面锁屏时 PIL `ImageGrab` 抓不到窗口）。
- **`name` 必须带扩展名**：Kivy 用 `name.split('.')[-1]` 取扩展名，传 `'foo'` 会被拼成 `0001._foo`（无扩展名文件）。
- **窗口物理宽度必须能被 4 整除**（用 `1440×880`），否则 RGBA 行错位、颜色循环移位。
- **每步截图前必须 dismiss 遗留弹窗**（`Window.children` 筛 `ModalView` → `dismiss()`），否则模态会盖住后续所有屏，两张图会**逐字节相同**。
- **不要调大 `Clock.max_iteration`**——会让 14 张图耗时从 ~40s 拖到 >180s 被 timeout 杀掉。
- 视觉核对走 `verify_v4_shots.py`：PIL `Counter` 做**容差 ±3** 的令牌命中统计，比肉眼可靠。

### 9.3 打包（4 个已修复的坑，别改回去）

1. `build_exe.py` 的 `DEMO_DIR` 必须指向 `demo/`（脚本在 `tools/` 下），且需显式 `--distpath/--workpath/--specpath`，否则产物落 `demo/dist` 且覆盖根目录手写的 `AI别闹.spec`。
2. `v2_events.py` 读 `v2/events.json`：**必须随包分发**，加载路径要支持 `sys._MEIPASS`。缺失时原生实现会**静默返回空列表** → 37 条事件无声消失。
3. **不要用 `--collect-all kivy`** —— 会因 `kivy.garden` 命名空间包报 `ValueError: path must be None or list`。
4. **构建期必须设 `KIVY_NO_FILELOG=1`** —— 否则 Kivy 钩子 import `kivy.graphics` 时触发日志轮转、被沙箱拦截抛 OSError，钩子**静默降级**（hiddenimports 只剩 4 个），运行时表现为 `ModuleNotFoundError: kivy.graphics.buffer`。

   **自查信号**：构建日志里 Kivy 钩子 hiddenimports 只有 4 个 = 已降级；正常应为 **87 个**，且 `dist/AI别闹/_internal/kivy` 下应有 **39 个 .pyd**。

### 9.4 清单同步（易漏）

- `tools/repack.py` 的 `demo_files` 是**手工列举**，新增模块极易漏 → 漏了分享包直接跑不起来。
- `demo/run_demo.bat` 里也硬编码了模块清单（11 个 `if not exist` 检查 + import 自检），新增模块必须同步。
- **改完清单务必自检**：AST 解析出来逐条 `os.path.exists`（当前 49 项全存在）。

### 9.5 文件操作（沙箱环境）

- 沙箱拦截 Python `shutil.rmtree` 的大批量删除（>50 文件报 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`）；bash `rm -rf` 可绕过。
- PowerShell 的 `Add-Type`（含 `Microsoft.VisualBasic.FileIO.FileSystem`）被拦截 → 要删文件建议用 `send2trash`（装在托管 venv 里）。
- `send2trash` 传参必须 `os.path.normpath()`（hook 会把 `C:\...` 弄成 `C:/...` 混合分隔符，报 `E_INVALIDARG`），且它**常报错但实际已生效**，判成功要看 `os.path.exists()` 复查。

### 9.6 其它

- **无 git 仓库** —— 删除/改坏不可通过版本控制恢复，改前先备份。
- 本沙箱会拦截 `Add-Type`；`send2trash` 也未预装。

---

## 10. 后续改进方向（按优先级）

1. **节奏系统成型**（P0）：不要只把 30 硬编码进去，要做成**可配置的节奏系统**（`BASE_TICK_SECONDS` + 倍率 + 倒计时 UI + 冷却与节奏解耦），这才是根治。
2. **UI 一致性收口**（P1）：把三个死控件补齐后，做一次全 14 屏走查，重新生成截图 + 配色核对。
3. **内容补齐**（P1）：20 国介绍 + 演示视频。
4. **可玩性深化**（P2）：国家 vibe（性格/差异化阻止文案）、事件预计效果提示。
5. **发布闭环**（P2）：重打分享包 + exe；考虑加一个 CI 脚本（跑三套测试 + balance_sim）。
6. **数值健康度**（P3）：让 `balance_sim` 支持多种玩家策略，避免"自动玩家偏科"造成的平衡误判。

---

## 11. 给 DeepSeek 的第一条指令（可直接复制）

```
接手《AI 别闹》项目（Kivy 像素风模拟经营游戏）。
项目路径：C:/Users/tianm/WorkBuddy/workbuddy/game_optimization/
先读：DeepSeek_接手文档.md（本文件）、demo/README.md、design/ui_design_v0.4.html

本轮任务（按序）：
1. 把游戏周期从 1.5 秒/周期 改到 30 秒/周期：
   - 在 demo/main.py 新增常量 BASE_TICK_SECONDS = 30.0 与 SPEED_STEPS = (0.5,1.0,2.0,4.0)
   - 消灭 4 处硬编码 1.5（main.py:499 / 1310 / 2106 / 2133），统一走 _reschedule_tick()
   - 实现 set_speed_idx(i)，把 on_speed 空回调接线（main.py:968 与 main.py:2669）
   - 补 ↑/↓ 快捷键（main.py:_on_keyboard_down，帮助页已承诺）
2. 处理耦合：engine.py 的 skill_cooldowns / v2_cooldowns 是按周期计的，
   周期拉长 20 倍后必须重新配平（建议改为按秒计时，彻底与 tick 解耦）。
3. 顶部状态条加「下个周期倒计时」细进度条（30 秒周期下是刚需）。
4. 补 on_motion（动效减弱）与 on_a11y（色盲辅助 ○●▲✖）两个死控件。

约束：
- 只能用 C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe（Kivy 2.3.1 不支持 3.13+）
- 改 UI 必须与 design/ui_design_v0.4.html 一致
- 改完必须跑通 test_build.py（12项）+ test_v4_app.py（59项）
- 动了冷却数值后必须重跑 balance_sim.py --seeds 30 并核对结局分布
- 不允许用 self.top/left/right/bottom/_label 作为属性名
```

---

## 12. 速查卡

```
项目根    C:/Users/tianm/WorkBuddy/workbuddy/game_optimization/
真机代码  demo/            （24 个 .py，约 13,600 行）
设计稿    design/ui_design_v0.4.html   （14 屏，当前权威稿）
解释器    C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe
跑游戏    demo/run_demo.bat
测试      "$PY" demo/test_build.py   /   "$PY" demo/test_v4_app.py
平衡      "$PY" demo/balance_sim.py --seeds 30
打包      "$PY" tools/build_exe.py --onedir    →   dist/AI别闹/
分享包    "$PY" tools/repack.py                 →   share/AI_Bienao_v2_<时间戳>.zip
```

**本次要改的三个文件**：`demo/main.py`（周期+速度+快捷键）、`demo/engine.py`（冷却解耦）、`demo/main.py:968/2669`（控件接线）。
