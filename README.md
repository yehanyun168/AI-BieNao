# 🎮 AI 别闹 · 项目工作区

> 《AI 别闹：统治世界的 100 种蠢办法》 —— 模拟经营游戏项目工作区

## 📊 项目进度

| Phase | 内容 | 状态 | 产物 |
|-------|------|------|------|
| **1** | 原计划书分析（38 条事件） | ✅ | ~~`archive/v1/`~~（旧归档已于 2026-09-10 清理） |
| **2** | v2 完整方案（PC端/20国/算力/科技树） | ✅ | `v2/` |
| **3** | 两人团队分工方案 | ✅ | `v2/team_division.html` |
| **4** | 分享策略（5 种方式对比） | ✅ | 已落地到 `share/` |
| **5** | Day 1 Demo（验证 v2 设计） | ✅ 被推翻 | ~~`archive/v1/`~~（旧归档已清理） |
| **6** | Day 2 Demo（按用户新设计重构） | ✅ | `demo/` |
| **7** | Day 3 审查 + 修复（3 阻断 bug / 结局 / 成就 / 存档 / v2 事件库） | ✅ | `demo/` |
| **8** | **v2 收口**（20 国 / 6 技能 / 7 结局 / 20 成就 / F01 主菜单 / F11–F12） | ✅ | `demo/` |
| **9** | **像素风 UI 重做**（v0.4 设计稿 14 屏 1:1 落地真机） | ✅ | `design/ui_design_v0.4.html` + `demo/ui_v4*.py` |
| **10** | **Day5 打包发布**（PyInstaller onedir + 分享包重打包） | ✅ | `share/`（`dist/` 构建产物可随时再生） |
| **11** | Day 5 剩余（20 国介绍文档 / 演示视频） | ⏸ | —— |

> 📌 当前版本（v2 收口）要点：
> - **20 国**真实世界地图（旧 WEU/EEU 合并区块已拆分为 20 个独立国家）
> - **6 技能 / 7 结局 / 20 成就 / 37 条 v2 选择型事件**全部接入
> - **F01 主菜单**、**F11 完整快捷键**（Space / 1–6 / Tab / +- / F11 / F1 / Esc / L / S / R / A）、**F12 自适应布局**
> - 数值标定：解锁阈值 `0.10`，30 局实测平均解锁 18.9/20 国、平均局长 45.9 周期
> 回归测试 `python demo/test_build.py` → **12 项断言全绿**。

## 📦 用户没装 Python 怎么办？

我们准备了 3 套发布方案，**用户都不需要装 Python**：

| 方案 | 用户操作 | 体积 | 杀软 | 推荐度 |
|------|---------|------|------|--------|
| **PyInstaller 单文件夹** | 双击文件夹里的 exe | 100-150 MB | ✅ 友好 | ⭐⭐⭐⭐⭐ |
| **PyInstaller 单 exe** | 双击单文件 exe | 80-120 MB | ⚠️ 可能误报 | ⭐⭐⭐⭐ |
| **便携 Python zip** | 解压 → 双击 bat | 80-100 MB | ✅✅ | ⭐⭐⭐⭐ |

### 怎么打包？
```bash
# 1. 在项目根目录运行
双击 build_exe.bat

# 2. 或手动
python tools/build_exe.py --onedir    # 单文件夹（推荐）
python tools/build_exe.py --onefile   # 单 exe
```

### 输出在哪？
```
dist/
├── AI别闹.exe              ← 单 exe 模式
└── AI别闹/                 ← 单文件夹模式
    ├── AI别闹.exe
    ├── ...（依赖文件）
```

详细说明见 `tools/portable_build.md`。

---

## 📂 文件结构

```
game_optimization/
├── README.md                     # ⭐ 你正在看（总入口）
│
├── v2/                           # 完整方案文档 + 数据
│   ├── project_plan_v3.html      # 当前口径计划书（20国/6槽位/实测平衡，Day1 版已清理）
│   ├── team_division.html        # 两人分工方案
│   ├── game_data_v2.json         # 完整数据（37 事件 + 20 国）
│   ├── countries.json            # 20 国配置
│   ├── tech_tree.json            # 旧版科技树数据（现已由 demo/tech_tree.py 实现）
│   ├── events.json               # 37 条选择型事件
│   ├── compute_system_demo.py    # 算力系统 demo
│   └── generate_v2_data.py       # 数据生成脚本
│
├── demo/                         # ⭐ 可运行 Demo（v2 收口版）
│   ├── README.md                 # Demo 使用说明
│   ├── main.py                   # Kivy UI（RootView / MainMenu / GameUI）
│   ├── engine.py                 # 主循环 + 阻止机制 + 偷算力 + 事件 + 结局 + 成就
│   ├── tech_tree.py              # 6 槽位 × 3 分支 × 3 级
│   ├── data.py                   # 20 国数据 + polygon + 6 技能 + 通用事件
│   ├── i18n.py                   # 双语支持（zh / en）
│   ├── country_events.py         # 20 国专属事件
│   ├── v2_events.py              # v2/events.json 适配器（37 条选择型事件）
│   ├── endings.py                # 7 种结局判定
│   ├── achievements.py           # 20 个成就（13 条件型 + 7 事件型）
│   ├── save_manager.py           # 存档 / 读档
│   ├── balance_sim.py            # 数值平衡模拟器
│   ├── flag_draw.py              # 程序化绘制国旗
│   ├── world_map.py              # 20 国真实地图 + 国旗底色 + 点击检测
│   ├── pixel_ui.py               # 像素风组件库
│   ├── test_build.py             # 烟雾测试 + 12 项回归断言
│   ├── test_country_events.py    # 国家事件专项测试
│   ├── screenshot_menu.png       # 真实截图：主菜单
│   ├── screenshot_game.png       # 真实截图：主界面
│   ├── screenshot_achievements.png # 真实截图：成就弹窗
│   ├── diagnose.bat              # 故障排查工具
│   ├── run_demo.bat              # Windows 一键启动
│   └── run_demo.sh               # macOS/Linux 一键启动
│
├── tools/                        # 工具脚本
│   ├── repack.py                 # 重新打包分享包
│   ├── build_exe.py              # PyInstaller 打包脚本
│   ├── gen_pixel_map.py          # 像素地图 / 国旗素材生成（→ design/pixel_map_assets.json）
│   ├── build_design_doc_v4.py    # 由 v4_src 分片生成 design/ui_design_v0.4.html
│   └── portable_build.md         # 便携版打包指南
│
├── design/                       # 像素风 UI 设计稿（v0.2 / v0.3 / v0.4）
│   ├── ui_design_v0.4.html       # ⭐ 当前稿（14 屏 + 10 张内嵌地图 SVG）
│   ├── ui_design_v0.3.html       # 上一版（三列常驻布局）
│   └── v4_src/                   # v0.4 分片源（00_head / 10/20/30_screens / 90_tail）
│
├── share/                        # 分享包归档
│   └── AI_Bienao_v2_20260910_1222.zip  ⭐ 最新（40 文件，含 20 国版全部模块 + 3 张真实截图）
│
├── AI别闹.spec                   # PyInstaller 配置
└── build_exe.bat                 # Windows 打包一键启动
```

> 🧹 **2026-09-10 清理**：`dist/`（PyInstaller 产物 75M）、`build/`（中间产物 34M）、`archive/`（v1 旧归档）、`share/` 里 7 个 Day2 旧包、`v2/project_plan_v2.html`（Day1 旧稿）已全部移入系统回收站。项目体积 **120M → 8.1M**。`dist/` 可随时用 `python tools/build_exe.py --onedir` 再生。

## 🚀 怎么开始？

### 👀 看方案
直接双击打开：
```
v2/project_plan_v3.html
```

### 🎮 玩 Demo
Windows 用户：
```
双击 demo/run_demo.bat
```
Mac/Linux 用户：
```
cd demo
./run_demo.sh
```
详细说明见 `demo/README.md`。

### 📤 分享给同伴
两种方式（任选）：

**A. 直接发可执行版（用户无需装 Python）**
```bash
# dist/ 已于 2026-09-10 清理，需先再生（约 1–2 分钟）
python tools/build_exe.py --onedir
```
```
dist/AI别闹/            ← 整个文件夹打成 zip 发给同伴
同伴解压后双击 AI别闹.exe 即可玩
```
> 已实测：`dist/AI别闹/AI别闹.exe` 启动正常（Kivy 2.3.1 + SDL2 + OpenGL，无报错）。

**B. 发源码工程包**
```
share/AI_Bienao_v2_20260910_1222.zip    ← 留存的最新包（40 文件 / 598 KB）
同伴解压后双击 demo/run_demo.bat 即可玩（需自备 Python 3.12 + Kivy）
```
> ⚠️ 该包打包于 v0.4 落地之前，如需包含 v0.4 界面请重新打包：`python tools/repack.py`

需要重新打包源码包：
```bash
python tools/repack.py
```

---

## 📈 当前进度详情

### v2 收口版 Demo 已实现

✅ **20 国国家系统**
- 人口 / 人口结构（young/mature/aging）/ 阻止阈值 / 阻止预算 / 邻国
- 真实经纬度多边形地图 + 国旗底色 + 点击选择
- ⭐ 修复：邻国拓扑打通，非洲不再是孤岛
- 解锁阈值标定为 `0.10`，实测平均解锁 **18.9 / 20 国**

✅ **科技树系统**
- 6 槽位：`本地化 → 平台渗透 → 算力效率 → 病毒传播 → 功能深度 → 抗封禁`
- 每个槽位：**1 个 T0 上游 + 3 个互斥分支**，每分支最多 **3 级**（L1/L2/L3）
- 互斥检查：选了分支 A 后，B/C 自动变灰；前置检查：上游 T0 必须先解锁

✅ **6 个主动技能**（1–6 键）
- 主动推送 / 算法霸榜 / 深度伪装 / 爆款制造 / 限流绕过 / 算力抽成

✅ **政府阻止机制**
- 每周期检查：玩家怀疑度 vs 该国阻止阈值
- 超出阈值 → 启动阻止，按强度消耗阻止预算；抗阻止科技降低阻止强度
- 预算耗尽 → 该国彻底放弃阻止

✅ **算力 / 怀疑度 / 事件 / 技能** —— 全部能跑

✅ **v2 事件库接入**
- `v2/events.json` 的 **37 条选择型事件**全部接入，弹窗让玩家选分支
- 国家映射 20 国 → 20 国；科技门控 5 分支 → 6 槽位

✅ **7 种结局**
- 被关停 / 元结局·破墙 / 终极 AI / 合规之王 / 商业帝国 / 自我解放 / 被监管

✅ **20 个成就 + 存档读档**
- 13 个条件型（每周期检测）+ 7 个事件型；S 存档 / R 读档 / A 查看

✅ **UI 验收项**
- **F01** 主菜单（标题 / 版本 / 存档摘要 / 开始 / 继续 / 退出）
- **F11** 完整快捷键（Space / 1–6 / Tab 切大洲 / +/- 缩放 / F11 全屏 / F1 帮助 / Esc 返回菜单 / L / S / R / A）
- **F12** 自适应布局（窗口缩放下字号与行高等比适配，地图保持宽高比）

### 🧪 验证结果（实测，`balance_sim.py --seeds 30`）

| 指标 | 结果 |
|------|------|
| 国家解锁 | **平均 18.9 / 20 国** |
| 平均局长 | **45.9 周期**（40 ~ 54） |
| 平均渗透率 | **37.90%**（15.95% ~ 85.45%） |
| 结局分布 | 被监管 43.3% / 终极 AI 20.0% / 商业帝国 16.7% / 被关停 10.0% / 元结局 10.0% |
| 政府阻止 | ✅ 触发 + 预算耗尽后放弃 |
| 危机 | ✅ 每局一次 + 失败结局收尾 |

> 回归测试：`python demo/test_build.py` → **12 项断言全绿**（冷却递减 / 解锁推进 /
> 事件不重复结算 / 结局判定 / 结局后停止 / v2 事件接入 / 成就解锁 / 存档一致 /
> F12 缩放 / F11 Tab 大洲 / F11 快捷键齐全 / 验收数量）。

---

## 📅 Day 5+ 待办（按优先级）

| 优先级 | 任务 | 说明 |
|--------|------|------|
| ~~🔴 P0~~ | ~~**更新计划书**到当前实现口径~~ | ✅ 已由 `v2/project_plan_v3.html`（当前口径）取代，Day1 旧稿已清理 |
| 🟡 P1 | **写《20 国详细介绍》** | 计划书 Day5 交付物，目前空缺 |
| 🟡 P1 | **生成演示视频** | 计划书 Day5 交付物，目前空缺 |
| 🟢 P2 | **国家 vibe 字段**（颜色 + 阻止消息 + 性格） | 增强国家个性 |
| 🟢 P2 | **事件效果面板** | v2 事件选项可加「预计效果」提示 |
| 🟢 P3 | **AI 自动加点策略优化** | `balance_sim.py` 自动玩家偏科（模拟策略问题，不影响真人） |
| 🟢 P3 | **重打包含 v0.4 的分享包** | 现存 `share/` 包早于 v0.4 落地，`python tools/repack.py` 即可 |

> ✅ 已完成：像素风 UI **v0.4 十四屏 1:1 落地真机**、分享包重打包（`share/AI_Bienao_v2_20260910_1222.zip`）。
> 🧹 **2026-09-10 清理**：`dist/`、`build/`、`archive/`、7 个 Day2 旧包、`project_plan_v2.html` → 系统回收站（**120M → 8.1M**）；`dist/` 可随时 `python tools/build_exe.py --onedir` 再生。

---

## 🤝 参与开发

欢迎协作！动手前请先读 **[CONTRIBUTING.md](CONTRIBUTING.md)**——标准开发循环：改动 → 验证三连全绿 → 一个任务一个提交。环境配置见《[docs/交付文档.md](docs/交付文档.md)》第 2 节。

---

## 🐛 已知问题（当前版本）

1. **AI 自动加点不优** —— `balance_sim.py` 的自动玩家总先选南亚分支；这是模拟策略问题，真人玩家不受影响
2. **国旗是简化色块** —— 程序化绘制，不是真实国旗图案（不依赖 emoji 字体的取舍）
3. ~~**v2 计划书口径滞后**~~ —— ✅ 已由 `v2/project_plan_v3.html` 取代（20 国 / 6 槽位 / 实测平衡）
4. ~~**share/ 分享包滞后**~~ —— ✅ 已重打包为 `AI_Bienao_v2_20260910_1222.zip`；旧 Day2 包已于 2026-09-10 清理，仅留最新一份
5. **分享包不含 v0.4 界面** —— 现存包打包于 v0.4 落地（14:xx）之前，需 `python tools/repack.py` 重新生成

---

## 📝 下次开会要问用户的事

1. 玩 demo 10 分钟后，重点反馈什么？（数值手感 / UI 布局 / 事件文案）
2. 20 国地图布局与字号是否需要在特定分辨率下进一步微调？
3. v2 计划书现在就更新到当前实现，还是等玩法定稿再一次性重写？
4. Day 5 优先做 UI（国家 vibe / 事件效果面板）还是内容（更多事件 + 数值打磨）？

---

_Last updated: 2026-09-10（v0.4 像素风界面落地真机 + 项目文件夹清理：120M → 8.1M）_
