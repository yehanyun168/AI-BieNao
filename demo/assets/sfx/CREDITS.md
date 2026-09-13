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

## 二、语义分层音效（6 个 · 2026-09-13 新增）

用于区分原本共用同一个 `click.wav` 的各类交互，让 UI 有反馈层次。

| 文件 | 语义 | 接入位置 | 素材来源 |
|---|---|---|---|
| `hover.ogg` | 鼠标悬停 / 焦点移动 | 卡片、按钮 hover | Kenney *Interface Sounds* `click_002` |
| `page.ogg` | 页面返回 / 上一页 | 各页返回按钮、翻页 | Kenney *Interface Sounds* `back_001` |
| `toggle.ogg` | 开关切换 | 设置页音效/音乐/画质开关 | Kenney *Interface Sounds* `toggle_001` |
| `error.ogg` | 非法操作 / 条件不足 | 技能未解锁、算力不足、非法投放 | Kenney *Interface Sounds* `error_001` |
| `confirm.ogg` | 重要确认 / 提交 | 新档确认、导入挑战码、结局确认 | Kenney *Interface Sounds* `confirmation_001` |
| `scroll.ogg` | 滚动 / 列表浏览 | 日志抽屉、成就墙、图鉴滚动 | Kenney *Interface Sounds* `scroll_001` |

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
- `assets_library/audio/sfx/ui-audio/`、`digital-audio/`、`sci-fi-sounds/`
  同为 Kenney CC0，本次未采用但**可随时补入**（无需改代码，放进本目录并在
  `demo/sfx.py::NAMES` 登记即可）。
