# 📍 AI 别闹 - 文件路径速查表

> 工作区根目录：`C:\Users\tianm\WorkBuddy\workbuddy\game_optimization\`

## 🎮 最新 Demo 在哪？

**根目录**：`demo/`

**入口文件**：
- Windows：`demo\run_demo.bat`（双击即玩）
- macOS/Linux：`demo/run_demo.sh`
- 手动启动：`demo/main.py`（用 `py -3.12 demo\main.py`）

**demo 里有什么**（v2 收口版）：

| 文件 | 作用 |
|------|------|
| `main.py` | Kivy UI 入口（RootView / MainMenu / GameUI 三层；快捷键 + 自适应缩放） |
| `engine.py` | 游戏主循环 + 阻止机制 + 偷算力 + 事件 + 结局 + 成就 |
| `tech_tree.py` | 6 槽位 × 3 分支 × 3 级 科技树 |
| `data.py` | 20 国配置 + polygon + 6 技能 + 通用事件 |
| `i18n.py` | 双语支持（中文 / English） |
| `country_events.py` | 20 国专属事件 |
| `v2_events.py` ⭐ | v2/events.json 适配器 —— 37 条选择型事件 |
| `endings.py` ⭐ | 7 种结局判定（双语） |
| `achievements.py` ⭐ | 20 个成就（13 条件型 + 7 事件型） |
| `save_manager.py` ⭐ | 存档 / 读档（JSON，存到 `demo/saves/`） |
| `balance_sim.py` ⭐ | 数值平衡模拟器（批量跑局统计结局分布） |
| `world_map.py` | 120×60 像素世界地图（Miller 投影）+ 点击检测 |
| `flag_draw.py` | 程序化绘制 20 面像素国旗（不依赖 emoji 字体） |
| `pixel_assets.py` ⭐ | 像素地图 / 国旗素材（world_map + flag_draw 的运行时依赖，勿删） |
| `pixel_ui.py` | 像素风组件库 |
| `ui_v4.py` ⭐ | v0.4 通用像素组件库 |
| `ui_v4_screens.py` ⭐ | v0.4 页面级组装（检视卡 / 投放 / 技能页 / 科技树 / 成就 / 帮助 / 设置 / 日志） |
| `test_build.py` | 烟雾测试 + **12 项回归断言** |
| `test_v4_app.py` ⭐ | v0.4 十四屏冒烟测试（**59 项断言**） |
| `test_ui_v4.py` | v0.4 组件库单元自测 |
| `test_country_events.py` | 国家事件专项测试 |
| `make_screenshots_v4.py` / `verify_v4_shots.py` | v0.4 真机 14 屏截图 + PIL 配色令牌核对 |
| `_v4shots/` | v0.4 真机 14 屏截图产物 |
| `screenshot_menu.png` / `screenshot_game.png` / `screenshot_achievements.png` | 真实截图（主菜单 / 主界面 / 成就弹窗） |
| `run_demo.bat` / `run_demo.sh` | 一键启动（Windows / macOS-Linux） |
| `diagnose.bat` | 故障排查工具 |
| `README.md` | demo 使用说明 |

## 📦 完整工作区结构

```
C:\Users\tianm\WorkBuddy\workbuddy\game_optimization\
│
├── README.md                       ⭐ 主入口（项目进度 + 结构）
│
├── demo/                           ⭐ 最新 Demo（v2 收口版）
│   ├── README.md
│   ├── main.py / engine.py / tech_tree.py / data.py
│   ├── i18n.py / country_events.py
│   ├── v2_events.py / endings.py / achievements.py / save_manager.py / balance_sim.py  ⭐
│   ├── world_map.py / pixel_ui.py / flag_draw.py
│   ├── test_build.py / test_country_events.py
│   ├── screenshot_menu.png / screenshot_game.png / screenshot_achievements.png
│   └── run_demo.bat / run_demo.sh / diagnose.bat
│
├── v2/                             📘 完整方案文档 + 数据
│   ├── project_plan_v3.html        ⭐ 当前口径计划书（20 国 / 6 槽位 / 实测平衡）
│   ├── team_division.html          两人分工方案
│   └── game_data_v2.json + countries.json + events.json + tech_tree.json + *.py
│
├── design/                         🎨 UI 设计稿（像素风）
│   ├── ui_design_v0.4.html         ⭐ 当前稿（14 屏可交互 + 10 张内嵌地图 SVG）
│   ├── ui_design_v0.3.html         上一版（三列常驻：20 面国旗 + 像素世界地图）
│   ├── ui_design_v0.2.html / v0.1.html  更早版本
│   ├── v4_src/                     v0.4 分片源（00_head / 10/20/30_screens / 90_tail）
│   └── pixel_map_assets.json       地图/国旗素材数据（由 gen_pixel_map.py 生成）
│
├── tools/                          🔧 工具（脚本 + data/）
│   ├── repack.py                   重新打包分享包
│   ├── build_exe.py                PyInstaller 打包脚本
│   ├── gen_pixel_map.py            ⭐ 像素世界地图 + 20 面国旗生成器
│   ├── build_design_doc.py         由 v0.2 生成 v0.3 设计稿
│   ├── build_design_doc_v4.py      ⭐ 由 v4_src 分片生成 v0.4 设计稿
│   ├── portable_build.md           便携版指南
│   └── data/                       Natural Earth 110m 海岸线/国界（公有领域）
│
├── share/                          📤 分享包归档
│   └── AI_Bienao_v2_20260910_1222.zip  ⭐ 留存最新一份（40 文件；早于 v0.4，待重打包）
│
├── AI别闹.spec                     ⭐ PyInstaller 配置
└── build_exe.bat                   ⭐ Windows 打包一键脚本
```

> 🧹 **2026-09-10 清理**：`dist/`（PyInstaller 产物）、`build/`（中间产物）、`archive/`（Day1 旧归档 + 过期预览图）、`share/` 里 7 个 Day2 旧包、`v2/project_plan_v2.html` 均已移入系统回收站。项目体积 **120M → 8.1M**。
> `dist/AI别闹/` 可随时用 `build_exe.bat` 或 `python tools/build_exe.py --onedir` 再生。

## 🚀 4 个高频操作路径

### 1. 玩 demo
```
C:\Users\tianm\WorkBuddy\workbuddy\game_optimization\demo\run_demo.bat
```

### 2. 故障排查
```
C:\Users\tianm\WorkBuddy\workbuddy\game_optimization\demo\diagnose.bat
```

### 3. 打包成 exe
```
C:\Users\tianm\WorkBuddy\workbuddy\game_optimization\build_exe.bat
```
打包产物：`dist\AI别闹\AI别闹.exe`（整个 `dist\AI别闹\` 文件夹约 75 MB，直接发同伴即可）
> ⚠️ `dist/` 已于 2026-09-10 清理，运行 `build_exe.bat` 会重新生成（约 1–2 分钟）。

### 4. 发给同伴的压缩包
```
源码工程包（最新）：share\AI_Bienao_v2_20260910_1222.zip
重新生成：py -3.12 tools\repack.py
```

## 📊 当前版本：v2 收口版

| Phase | 状态 |
|-------|------|
| Day 1 Demo | 🗄️ 已归档（被推翻） |
| Day 2 Demo | ✅（已被后续覆盖） |
| Day 3 Demo | ✅（修 3 个阻断 bug + 结局/成就/存档/37 事件库） |
| **v2 收口版** | ✅（20 国 / 6 技能 / 7 结局 / 20 成就 / F01 主菜单 / F11–F12） |
| **v0.4 UI 落地** | ✅ 像素风 14 屏 1:1 搬到真机（`design/ui_design_v0.4.html` → `demo/ui_v4*.py`） |
| **本次：项目清理** | ✅ 2026-09-10 瘦身 **120M → 8.1M**（构建产物 / 旧归档 / 旧包 → 回收站） |
| Day 5 剩余 | ⏸ 待办（20 国详细介绍 / 演示视频 / 重打包含 v0.4 的分享包） |

### 🎮 快捷键速查
`Space` 暂停 · `1–6` 技能 · `Tab` 切大洲 · `+/-` 缩放 · `F11` 全屏 · `F1` 帮助 · `Esc` 返回菜单 · `L` 中英切换 · `S` 存档 · `R` 读档 · `A` 成就

## 🔄 重新生成分享包

```bash
cd C:\Users\tianm\WorkBuddy\workbuddy\game_optimization
py -3.12 tools\repack.py
```

输出：`share\AI_Bienao_v2_<时间戳>.zip`

---

_Last updated: 2026-09-10（v0.4 像素风 UI 落地真机 + 项目文件夹清理：120M → 8.1M）_
