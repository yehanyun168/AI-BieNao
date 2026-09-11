# 参与开发指南（CONTRIBUTING）

> 核心原则：**小步改动 → 验证全绿 → 一个任务一个提交**。
> 本规范对所有人（包括项目主理与 AI 协作流程）同等生效。

## 1. 环境准备

- Python **3.12.x**（必须——Kivy 2.3.1 不兼容 3.13/3.14）+ Kivy 2.3.1
- 安装步骤见《交付文档.md》第 2.2 节（Windows 需额外装 kivy_deps 三件套）
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

## 3. 架构铁律（违反会被 verify_tables 拦下）

1. 数值只进 `balance.py` 的 `TUNE` 表，`engine.py` 不出现裸魔数
2. `engine.py` 不得 import 任何 UI 模块（无头平衡模拟依赖此边界）
3. 单文件 ≤800 行；新功能域新建 `ui_xxx.py` Mixin 挂进 `main.py`
4. 可写全局只放 `ui_shared.py`，读写一律 `import ui_shared as ST; ST.X = …`

## 4. 改什么动哪个文件

见《交付文档.md》第 8 节速查表（数值 / 结局 / 事件 / 科技 / 文案 / UI 一览）。改完数据表必跑 `verify_tables.py`。

## 5. 提交之后

- push 自己的 feature 分支 → GitHub 发 Pull Request → 描述改动内容与已跑的验证
- **数值类 PR 必须贴 `balance_sim.py --seeds 30` 的结局分布结果**
- 评审通过由维护者合并（main 建议开启分支保护）
