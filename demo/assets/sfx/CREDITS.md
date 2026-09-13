# demo/assets/sfx/ —— 音效来源与授权

本目录音效分两个来源，**全部可商用**。同名多后缀时 `sfx.py` 优先 `.wav`。

---

## 一、本地合成音效（12 个 · 基线）

| 文件 | 语义 |
|---|---|
| `click.wav` / `select.wav` | 通用点击 / 选项确认 |
| `cast.wav` | 技能释放 |
| `success.wav` / `fail.wav` | 操作成功 / 失败 |
| `crisis.wav` | 危机弹窗 |
| `end_win.wav` / `end_lose.wav` | 结局出现 |
| `tech.wav` / `unlock.wav` | 科技树节点点选 / 科技解锁 |
| `pause.wav` | 暂停与继续 |
| `drop.wav` | 技能投放模式发射 |

- **生成方式**：`tools/gen_sfx.py`（纯正弦/方波/三角波 + AD 包络合成，22050Hz 单声道 16bit）
- **授权**：公有领域 / CC0 —— 自产合成音，无第三方权利
- **可复现**：`python tools/gen_sfx.py` 可完整重建全部 12 个文件

---

## 二、语义分层音效（2026-09-13 新增，共 9 个）

用于区分原本共用同一个 `click.wav` 的各类交互，让 UI 有反馈层次。
分两批加入，均取自 Kenney *Interface Sounds*（CC0）。

### 第 1 批（6 个）：基础交互分层

| 文件 | 语义 | 接入位置 | 源文件 |
|---|---|---|---|
| `hover.ogg` | 鼠标悬停 / 焦点移动 | 卡片、按钮 hover | `bong_001` |
| `page.ogg` | 页面返回 / 上一页 | 各页返回按钮、翻页 | `back_001` |
| `toggle.ogg` | 开关切换 | 设置页音效/音乐/画质开关 | `toggle_001` |
| `error.ogg` | 非法操作 / 条件不足 | 技能未解锁、算力不足、非法投放 | `error_001` |
| `confirm.ogg` | 重要确认 / 提交 | 新档确认、导入挑战码、结局确认 | `confirmation_001` |
| `scroll.ogg` | 滚动 / 列表浏览 | 日志抽屉、成就墙、图鉴滚动 | `scroll_001` |

### 第 2 批（3 个）：技能投放 / 科技分支缺口

| 文件 | 语义 | 接入位置 | 源文件 |
|---|---|---|---|
| `deploy.ogg` | **确认投放** | 投放模式「确认投放」按钮 | `drop_001` |
| `branch.ogg` | **科技分支升级** | 科技树分支升级按钮 | `switch_002` |
| `confirm_cast.ogg` | 投放结果确认（备用） | 暂未接线，留作结果反馈扩展 | `confirmation_002` |

**补齐的缺口（2026-09-13 核查）**：

1. **`deploy` 替换了原先共用的 `cast`**：确认投放与全局技能直接释放原本
   都播 `cast`，玩家从声音上分不出「我刚才是确认了投放还是直接放了个技能」。
   现确认投放用 `deploy`（0.11s / 2100Hz / 起音 0.0ms），直接释放保留 `cast`。
   失败时播 `error` —— **成功/失败只响一声**，不叠响。

2. **`branch` 补上原本完全静默的路径**：`on_upgrade_branch`（科技分支升级）
   此前**没有任何音效**，玩家升完听不到反馈。用 `switch_002`
   （0.61s / 2422Hz / 起音 0.2ms）与解锁 T0 的 `unlock` 区分 ——
   解锁是「开新枝」，升级是「加深已有枝」，听感应有别。

3. **`hover` 换掉了过短版本**：原 `hover.ogg` 源自 `click_002`，时长仅
   **0.01s**（项目内最短，连 `click.wav` 都有 0.05s），高频悬停时听不清。
   换成 `bong_001`（0.12s / 291Hz / 起音 0.2ms），时长与低频都更合适。

### 声学筛选依据

新音效按项目既有风格基线筛选（亮度 / 起音 / 时长），实测基线为
**亮度 197–11964Hz、起音 0.1–0.7ms**。第 2 批三个音效的实测：

| 文件 | 时长 | 亮度 | 起音 |
|---|---|---|---|
| `deploy.ogg` | 0.11s | 2100Hz | 0.0ms |
| `branch.ogg` | 0.61s | 2422Hz | 0.2ms |
| `hover.ogg` | 0.12s | 291Hz | 0.2ms |

### ⚠️ 已知仍不合适的音效（待处理）

`scroll.ogg`（源 `scroll_001`）实测 **1.00s / 亮度 11964Hz**，是 1 秒渐起的
高频氛围噪声，而非滚动提示音 —— 它拉高了整个音效库的亮度上限。
同批候选（`pluck_001/002` 约 8600–9300Hz、`tick_001/002` 约 10700–11200Hz、
`open_001`/`close_001` 约 12230Hz）亮度同样超标，**均未采用**。
若要修 `scroll`，需另找低频素材或改用自产合成音。

### 授权原文

> **Interface Sounds (1.0)**
> Created/distributed by Kenney (www.kenney.nl)
> License: (Creative Commons Zero, CC0)
> http://creativecommons.org/publicdomain/zero/1.0/
>
> This content is free to use in personal, educational and commercial projects.
> Support us by crediting Kenney or www.kenney.nl (this is not mandatory)

**结论**：CC0 授权，可商用、可修改、可再分发，**无署名义务**（署名自愿）。
本项目仍在此处保留出处记录，以便日后追溯。

---

## 三、已知未采用的素材（存档备查）

- `assets_library/audio/sfx/pixel-ui-sfx/`（Atelier Magicae，65 个 WAV，11MB）
  授权：**可商用 / 禁止再分发 / 必须署名 "Atelier Magicae"**。
  因体积（11MB vs 本目录合计 240KB）与"禁止再分发"条款，**未采用**；
  如需采用，必须在本文件与游戏内 credits 中同时署名，且需评估分享包体积增长。
- `assets_library/audio/sfx/ui-audio/`、`digital-audio/`
  同为 Kenney CC0，本次未采用但**可随时补入**（无需改代码，放进本目录并在
  `demo/sfx.py::NAMES` 登记即可）。
- ~~`assets_library/audio/sfx/sci-fi-sounds/` 本次未采用~~
  → **2026-09-14 已部分采用**，见下节。

---

## 四、开场动画音效（2026-09-14 新增，4 个）

《AI 别闹》开场动画 v2 重制（`docs/intro_v2/03_audio_design.md` v1.2）配套：
3 个 Kenney *Sci-Fi Sounds*（CC0）选材加工 + 1 个自产合成，
全部经 `tools/make_intro_sfx.py` 统一定标（44.1kHz mono OGG）。

| 文件 | 语义 | 源文件 | 加工 |
|---|---|---|---|
| `server_hum.ogg` | 机房低沉运行嗡鸣（循环床） | `spaceEngineLow_003.ogg` | 8ms 交叉淡化（loop 无缝）→ 高通 28Hz → 120Hz 低架 −2dB |
| `machine_run.ogg` | 电脑自动开机（风扇+磁盘） | `computerNoise_001.ogg` | 裁前 2.4s |
| `impact_low.ogg` | 「目标已确立」定格重音 | `impactMetal_001.ogg` | 全长 |
| `power_on.ogg` | 屏幕亮起的滋滋开机电流声 | **自产合成** | `tools/make_intro_sfx.py::make_power_on`（50Hz 市电 + 锯齿 FM + 白噪颗粒 + 15.7kHz 行频，0.85s） |

- **生成/加工方式**：`tools/make_intro_sfx.py`（可复现，固定随机种子）
- **响度**：`server_hum` / `machine_run` RMS −18 dBFS；`impact_low` / `power_on`
  为瞬态衰减型，按峰值 −3 dBFS 定标（RMS −18 物理不可达，见脚本 docstring）
- **授权**：Kenney Sci-Fi Sounds 为 CC0，可商用、可修改、可再分发，无署名义务；
  `power_on` 自产合成，无第三方权利

### 授权原文（Sci-Fi Sounds）

> **Sci-Fi Sounds**
> Created/distributed by Kenney (www.kenney.nl)
> License: (Creative Commons Zero, CC0)
> http://creativecommons.org/publicdomain/zero/1.0/
