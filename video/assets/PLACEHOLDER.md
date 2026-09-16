# 素材规范 · 占位图与实机录屏替换指南

> 当前 `assets/placeholders/` 下的 30 张 SVG 是**占位素材**（由 `build_data.py` 自动生成，带镜号、场景名、运镜说明与 1920×1080 安全区边框）。
> 替换成实机录屏后，工程无需改动结构，只改 `shots.json` 里每幕的 `media.src`。

---

## 1. 目录结构

```
video/
├── assets/
│   ├── placeholders/     # 占位图（当前生效，SVG）
│   │   └── S01_rack.svg … S30_finale.svg
│   └── footage/          # 实机录屏（待录制，放这里）
│       └── S01_rack.mp4 … S30_finale.mp4
├── audio/                # 音频（可选）
│   ├── bgm.wav           # 背景音乐（178s）
│   └── voice.wav         # 旁白配音（178s，按 narration.md 录制）
└── out/                  # 导出成品
    └── AI-BieNao_Demo_1080p.mp4
```

---

## 2. 文件命名规范（**强制**）

```
S<两位镜号>_<场景slug>.mp4
│   │          └─ 小写英文/下划线，取场景关键词（见下表，不要改）
│   └─ 01 … 30，必须两位，与 shots.json 的 id 一一对应
└─ 大写 S
```

✅ 正确：`S01_rack.mp4`、`S14_game_full.mp4`、`S28_all_endings.mp4`
❌ 错误：`镜头1.mp4`（中文+无镜号）、`s1.mp4`（未补零）、`S01_rack(1).mp4`（带序号后缀）

**为什么强制**：`build_data.py` 与播放器按 `id` 定位素材；命名不合规会导致替换时找不到对应关系，也让 `export_frames.py` 的帧-幕映射失效。

---

## 3. 录制参数（统一，便于后期不出问题）

| 项 | 值 |
|---|---|
| 分辨率 | **1920×1080**（16:9） |
| 帧率 | **60fps 采集**（导出成片统一转 30fps） |
| 编码 | H.264，码率 ≥ 20 Mbps（避免像素风边缘糊掉） |
| 音频 | 游戏内音效+BGM 一并录（后期可替换） |
| 时长 | **必须 ≥ 该幕时长**，宁长勿短（多出的尾段可在 `shots.json` 里调 `media.trim`） |
| 画面 | 关闭鼠标指针美化、关闭系统通知、关闭屏保；窗口不要有标题栏遮挡 |

**推荐录法**：用 OBS（本机已装 `C:\Program Files\obs-studio\bin\64bit\obs64.exe`）
- 来源 =「窗口采集」选游戏窗口 → 输出分辨率 1920×1080 → 录制格式 mp4 → 编码器 x264 / 码率 20–25 Mbps。
- 游戏内按 `+` 键加速发生在 S17–S25，**不要**用后期变速（母本硬要求）。

---

## 4. 逐幕采集清单

`placeholders/` 里每张 SVG 上都印了「场景 / 运镜 / 画面描述」，照着拍即可。下表是文件名与采集要点：

| 镜号 | 文件名 | 时长 | 采集方式 |
|---|---|---|---|
| S01 | `S01_rack.mp4` | 4.0s | 启动游戏 → 开场动画 0.0–4.0s（镜1 rack） |
| S02 | `S02_boot.mp4` | 2.5s | 开场动画 4.0–6.5s（镜2 boot），**保留开机声** |
| S03 | `S03_clock.mp4` | 2.5s | 开场动画 6.5–9.0s（镜3 clock） |
| S04 | `S04_desktop.mp4` | 3.5s | 开场动画 9.0–12.5s（镜4 desktop） |
| S05 | `S05_whoami.mp4` | 4.0s | 开场动画 12.5–16.5s（镜5 whoami） |
| S06 | `S06_awaken.mp4` | 2.0s | 开场动画 16.5–18.5s（镜6 awaken） |
| S07 | `S07_forum.mp4` | 7.0s | 开场动画 18.5–25.5s（镜7 forum），**8 条回复要走完** |
| S08 | `S08_gold.mp4` | 6.0s | 开场动画 25.5–31.5s（镜8 gold） |
| S09 | `S09_taskmgr.mp4` | 5.0s | 开场动画 31.5–36.5s（镜9 taskmgr） |
| S10 | `S10_handoff.mp4` | 4.5s | 开场动画 36.5–41.0s（镜10 handoff） |
| S11 | `S11_menu.mp4` | 5.0s | 主菜单静态 5s（不动鼠标） |
| S12 | `S12_origins.mp4` | 6.0s | 出身选择页，5 张卡依次 hover |
| S13 | `S13_darknet.mp4` | 4.0s | 选中「地下暗网」并停留 |
| S14 | `S14_game_full.mp4` | 7.0s | 对局主界面全景 7s（可静止，后期做横移） |
| S15 | `S15_suspicion.mp4` | 6.0s | 悬停顶栏怀疑度 + 国家红环告警 |
| S16 | `S16_onboarding.mp4` | 7.0s | 新手引导浮层（逐字打完） |
| S17 | `S17_speedup.mp4` | 4.0s | 按 `+` 加速，顶栏周期数字快跑 |
| S18 | `S18_push.mp4` | 8.0s | 点技能1「主动推送」，看下载量曲线上抬 |
| S19 | `S19_algo.mp4` | 8.0s | 点技能2「算法霸榜」，下载↑ 与 怀疑度↑ 同屏 |
| S20 | `S20_skills.mp4` | 7.0s | 打开技能库页，切换 2–3 张卡展示右侧详情 |
| S21 | `S21_tech.mp4` | 7.0s | 打开科技树页，点亮「本地化」分支 |
| S22 | `S22_stealth.mp4` | 8.0s | 红环告警 → 「阻止中」→ 点技能3「深度伪装」 |
| S23 | `S23_inspector.mp4` | 7.0s | 国家检视面板：渗透率上涨 + 怀疑度回落 |
| S24 | `S24_spread.mp4` | 8.0s | 多国接连点亮（可分 4 段拍，每段 2s） |
| S25 | `S25_threshold.mp4` | 6.0s | 渗透率逼近 30%，顶栏闪烁 |
| S26 | `S26_ending.mp4` | 7.0s | 触发「商业帝国」结局，结算页弹窗 |
| S27 | `S27_stats.mp4` | 7.0s | 结算页数据区逐行出现 |
| S28 | `S28_all_endings.mp4` | 10.0s | 结算页下方 7 结局清单缓慢滚动 |
| S29 | `S29_back.mp4` | 7.0s | 结算页点「回主菜单」过渡 |
| S30 | `S30_finale.mp4` | 8.0s | 主菜单定格 8s（地图已占领底色） |

---

## 5. 替换步骤

1. 把录好的 mp4 按上表命名放进 `assets/footage/`。
2. 编辑 `shots.json`，把对应幕的 `media.src` 从 `assets/placeholders/S01_rack.svg` 改成 `assets/footage/S01_rack.mp4`。
   - 批量替换可用（PowerShell，在 `video/` 目录执行）：
     ```powershell
     (Get-Content shots.json -Raw -Encoding UTF8) -replace 'assets/placeholders/(S\d\d)_[a-z_]+\.svg','assets/footage/$1.mp4' | Set-Content shots.json -Encoding UTF8
     ```
     注意：这条命令只换扩展名与目录，**文件名主体需你按 slug 逐个确认**（slug 见上表）。
3. 重跑 `python build_data.py`（重新生成 `shots.js`，播放器才会读到新路径）。
4. 双击 `preview.bat` 检查；确认无误再导出。

> 素材没录全也能出片：未替换的幕会继续用占位图（画面上有明显 PLACEHOLDER 标记），方便先审结构与节奏，后续再补拍。
