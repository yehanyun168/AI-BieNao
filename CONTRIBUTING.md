# 参与开发指南（CONTRIBUTING）

> 核心原则：**小步改动 → 验证全绿 → 一个任务一个提交**。
> 本规范对所有人（包括项目主理与 AI 协作流程）同等生效。

## 1. 环境准备

- Python **3.12.x**（必须——Kivy 2.3.1 不兼容 3.13/3.14）+ Kivy 2.3.1
- 安装步骤见《docs/交付文档.md》第 2.2 节（Windows 需额外装 kivy_deps 三件套）
- 装完先建立基线：`cd demo && python test_build.py`，确认全部断言通过再动手

## 2. 标准开发循环（必守）

```
改动 → 验证三连（按改动类型选）→ 全绿 → git commit → push
```

**一个任务一个 commit**——出问题可精确回退到任意一步。

### 验证三连（在 demo/ 目录下运行，按改动类型选）

| 改动类型 | 必跑 | 验收标准 |
|---------|------|---------|
| 数值 / 结局 / 成就 / 事件（balance.py、endings.py、achievements.py、v2/events.json） | `python verify_tables.py` + `python balance_sim.py --seeds 30` | 35/35；7 结局全 ≥5%、平均局长 30–50 周期 |
| 任何代码改动 | `python test_build.py` | 全部断言通过 |
| 科技树 | `python verify_tech_tree.py` | 29/29 |
| UI 组件 / 布局 | `python test_ui_v4.py` + `python verify_v4_shots.py` | 全绿；对齐 `design/ui_design_v0.4.html` 令牌表 |

### 提交规范

- 分支：从 main 拉出 `feat/功能名` / `fix/问题描述` / `balance/调参说明`
- commit message：`类型: 一句话说清改了什么、为什么`（类型：feat / fix / balance / docs / chore）
- ❌ 禁止一个 commit 混多个不相关任务
- ❌ 禁止验证未全绿就 push
- push 前先 `git pull --rebase` 同步远程

### 提交守卫（pre-commit hook）

仓库已启用 `.git/hooks/pre-commit`，提交时**自动**跑两个快且无窗口的脚本：

| 脚本 | 检查内容 | 期望 | 耗时 |
|------|---------|------|------|
| `demo/verify_tables.py` | 数据表结构 + **[6] 分层依赖方向**（低层不得 import 高层） | 35/35 | ~1s |
| `demo/verify_tech_tree.py` | 科技树节点 / 连线 + 状态机 | 29/29 | ~3s |

合计**约 4 秒**。背景：2026-09-11 的 `c94e480`「清理未使用 import」引入了分层违规
（`ui_v4_screens.py`(L5) import 了 `ui_modal.py`(L7)），靠人工事后复跑才发现——
钩子就是把那次人工复跑固化下来。

- **什么时候跑**：仅当暂存区里有 `demo/*.py`、`tools/*.py`、`v2/*.json` 或 `*.spec`。
  只改 `.md` 文档 → 打印跳过原因并**直接放行**（不拦文档改动）。
- **失败会怎样**：任一脚本非 0 退出 → 拒绝提交，终端打印 `[FAIL]` 项与常见原因。
  修复后 `git add` 重新提交即可。
- **刻意不跑的**：`test_v4_app.py`（会真的弹 Kivy 窗口，打扰开发）、
  `balance_sim.py --seeds 30`（慢）——仍按第 2 节「验证三连」手动 / CI 跑。
- **环境要求**：Python **3.12.x + Kivy 2.3.1**。钩子会自动挑「能 `import kivy`」的
  解释器（PATH 里的 python 若是 3.13 会被跳过），也可用
  `AI_BIE_NAO_PYTHON=/path/to/python.exe` 指定。
  找不到可用解释器时**只警告、放行**——不因机器环境差异把人卡死，但请自行补跑。
- **新机器 / 新 clone**：`.git/hooks/` 不随 clone 分发，**首次 clone 后执行一条命令重建**：

  ```bash
  cp tools/git-hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
  ```

  （Windows 若无 `chmod`，可跳过——Git for Windows 的 bash 不强制要求可执行位。）
  仓库根的 `.pre-commit-config.yaml` 是同口径的 pre-commit 框架配置，
  目前**尚未接入**，仅作迁移蓝图；接入后上面这条手工命令即可退役。
- 钩子脚本必须是 LF 换行，CRLF 会让 Git for Windows 的 bash 报 `bad interpreter`。

#### `--no-verify` 使用守则

`git commit --no-verify` 会**整条跳过**守卫，风险等同于把分层违规直接放行。

- ❌ **默认禁止**。不要因为「急着提交」「CI 会跑」「改动很小」而使用。
- ✅ **只允许在明确知道自己在做什么的紧急情况下使用**，例如：
  生产环境热修、钩子自身因环境故障误拦且已人工确认改动无害。
- ✅ **守则（缺一不可）**：
  1. 用之前先想清楚：这次跳过的检查，这次改动有没有可能踩到？
  2. **事后必须补跑**：`cd demo && python verify_tables.py && python verify_tech_tree.py`
  3. 补跑不通过 → **必须立刻修正**（单独出一个 fix commit），不许带着违规继续开发。
  4. 在 PR / 交接说明里写明「用了 --no-verify + 原因 + 补跑结果」，让评审可追溯。

## 3. 架构铁律（违反会被 verify_tables 拦下，提交时自动拦）

1. 数值只进 `balance.py` 的 `TUNE` 表，`engine.py` 不出现裸魔数
2. `engine.py` 不得 import 任何 UI 模块（无头平衡模拟依赖此边界）
3. 单文件 ≤800 行；新功能域新建 `ui_xxx.py` Mixin 挂进 `main.py`
4. 可写全局只放 `ui_shared.py`，读写一律 `import ui_shared as ST; ST.X = …`

## 4. 改什么动哪个文件

见《docs/交付文档.md》第 8 节速查表（数值 / 结局 / 事件 / 科技 / 文案 / UI 一览）。改完数据表必跑 `verify_tables.py`。

## 5. 提交之后

- push 自己的 feature 分支 → GitHub 发 Pull Request → 描述改动内容与已跑的验证
- **数值类 PR 必须贴 `balance_sim.py --seeds 30` 的结局分布结果**
- 评审通过由维护者合并（main 建议开启分支保护）
