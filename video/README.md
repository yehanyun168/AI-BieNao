# 《AI 别闹》实机演示视频 · 视频工程

把 `docs/演示脚本_0916.md`（30 镜 / 178 秒）落成**可预览、可渲染、可替换素材**的完整视频工程。

- 规格：**1920×1080 / 16:9 / 30fps / 178.00 秒（5340 帧）**
- 当前画面：**全部为占位素材**（`assets/placeholders/*.svg`），结构是完整的，替换录屏即可出片
- 工程主文件：**`index.html`**（浏览器播放器，同时是渲染源）

---

## 1. 交付文件清单

| 文件 | 用途 | 你会不会改它 |
|---|---|---|
| **`index.html`** | **工程主文件 / 播放器**：16:9 画布，按时间轴播放 30 幕，含高亮框、箭头、标注、字幕轨与转场。渲染时由 Edge 无头逐帧截图 | 一般不改（改样式才动） |
| **`shots.json`** | **分镜数据源**：30 幕的画面、时长、运镜、转场、叠加元素坐标、字幕。所有改动的源头 | ✅ 最常改 |
| **`shots.js`** | `shots.json` 的 JS 包装，让 `file://` 双击也能加载（自动生成，**勿手改**） | ❌ |
| **`build_data.py`** | 构建 + 校验脚本：校验时间码连续性/总时长/坐标越界，生成 `shots.js`、`subtitles.srt`、占位图 | 改完 `shots.json` 后必跑 |
| **`storyboard.md`** | **分镜脚本（人读）**：逐幕画面内容、镜头动效、时长、转场、标注元素、字幕，含 3 处改动说明 | ✅ |
| **`narration.md`** | **旁白稿**：逐幕中文解说词 + 字幕对照 + 配音提示 | ✅ 配音前看 |
| **`narration.json`** | 旁白机读版，播放器可在字幕上方显示解说词（按 `N` 开关） | ❌ |
| **`subtitles.srt`** | 标准 SRT 字幕（29 条，S02 留白），可直接挂 ffmpeg 或导入剪辑软件 | ❌ 自动生成 |
| **`assets/placeholders/*.svg`** | 30 张 1920×1080 占位图，印有镜号 / 场景 / 运镜 / 替换文件名 | 录屏到位后弃用 |
| **`assets/PLACEHOLDER.md`** | **素材规范**：命名规范、录制参数、逐幕采集清单、替换步骤 | 录屏前看 |
| **`preview.bat`** | 一键预览（Edge `--app` 模式，1920×1080 无地址栏窗口） | ❌ |
| **`export_frames.py`** | 无头逐帧导出：调用 Edge 截出 5340 帧 PNG 到 `frames/`（**已实测**：试渲 6/6 成功） | ❌ |
| **`export_video.bat`** | 一键合成 mp4：帧序列 → H.264 1080p，自动烧录 `subtitles.srt`、自动混音 `audio/`（**已实测**：ffmpeg + 字幕烧录链路通过） | ❌ |
| **`ffmpeg.bat`** | ffmpeg 转发器：本机 ffmpeg 经 winget 安装但符号链接失败未进 PATH，此文件兜底（可直接删除不影响已配好 PATH 的机器） | ❌ |
| **`README.md`** | 本文件：交付清单 + 预览 / 导出操作 | — |

---

## 2. 本地预览（三种方式，任选）

### 方式 A · 一键（推荐）
双击 **`preview.bat`**
→ 以 Edge 应用窗口（1920×1080、无地址栏）打开 `index.html`，最接近成片观感。

### 方式 B · 直接打开
双击 **`index.html`**（Edge / Chrome 均可）
→ 数据从 `shots.js` 加载，`file://` 下也能跑，不需要起服务器。

### 方式 C · 从指定时间看
在浏览器地址栏加参数：

| 参数 | 作用 | 例 |
|---|---|---|
| `?t=88.0` | 跳到 88 秒并暂停 | `index.html?t=88.0` |
| `&still=1` | 隐藏所有 UI（进度条/水印），用于干净导出 | `index.html?t=88.0&still=1` |
| `&subs=0` | 不渲染字幕（导出无字幕版时有用） | `index.html?t=88.0&still=1&subs=0` |

### 播放快捷键

| 键 | 功能 |
|---|---|
| `空格` | 播放 / 暂停 |
| `←` `→` | 上一幕 / 下一幕 |
| `Home` | 回到 0 秒 |
| `[` `]` | 显示 / 隐藏 UI 与水印（导出前按 `]` 隐藏） |
| `N` | 切换显示旁白解说词（默认关闭，正式成片只出字幕） |
| `1` `2` | 0.5x / 1x 速度 |
| `F` | 全屏 |

---

## 3. 导出视频

### 步骤 1 · 逐帧导出（约 10–20 分钟，5340 帧）
```bat
python export_frames.py                 :: 全部 5340 帧
python export_frames.py --start 76 --end 96   :: 只导 76–96 秒（先试渲看效果）
python export_frames.py --step 10       :: 每 10 帧导 1 帧（快速抽查）
python export_frames.py --force         :: 覆盖已存在的帧
```
输出：`frames/f000001.png …`，另有 `frames/timecode.txt` 记录每帧时间码。
（脚本用本机 Edge 无头截图，8 线程并发；Edge 路径已写死在脚本里。）

### 步骤 2 · 合成 mp4
```bat
export_video.bat
```
- **ffmpeg 本机已就绪**（v9.0.1，winget 安装但因符号链接问题未进 PATH，同目录 `ffmpeg.bat` 已兜底转发，无需任何配置）
- 输出：`out/AI-BieNao_Demo_1080p.mp4`（H.264 / 1080p / 30fps / CRF 18）
- **字幕自动烧录**：检测到 `subtitles.srt` 就自动烧（微软雅黑）；不想烧就先把它改名
- **音频自动混音**：放 `audio/bgm.wav` 与 `audio/voice.wav` 后重跑即可（BGM 自动压到 25%）；没有音频文件则只出画面

### 备选方案 · OBS 直接录屏（不用 ffmpeg，最快）
本机已装 OBS：`C:\Program Files\obs-studio\bin\64bit\obs64.exe`
1. 双击 `preview.bat` 打开播放器 → 按 `]` 隐藏 UI → `F` 全屏
2. OBS 新建「显示器采集」→ 输出 1920×1080 / 60fps → 开始录制
3. 播放器按 `空格` 播放，178 秒后停止录制
- 优点：零依赖、带转场动效；缺点：依赖屏幕刷新率，偶有掉帧。**赶时间就用这个**。

---

## 4. 常见改动怎么走

| 想改什么 | 改哪里 | 然后 |
|---|---|---|
| 某一幕的字幕 | `shots.json` → `subtitle` | 跑 `build_data.py` |
| 高亮框位置 / 箭头指向 | `shots.json` → `overlays` 的 `x/y/w/h/from/to` | 跑 `build_data.py` |
| 某一幕时长 | `shots.json` → `dur` **并同步后续所有幕的 start/end** | 跑 `build_data.py`（会校验总时长，不等于 178 会报错） |
| 换实机录屏 | `shots.json` → `media.src` | 见 `assets/PLACEHOLDER.md` §5 |
| 旁白措辞 | `narration.md` 与 `narration.json` | 无需构建 |

> ⚠️ 改时长后 `build_data.py` 会校验「幕号连续 / 时间码无缝 / 总时长 = 178.00s」，不通过会报错并指出是哪一幕 —— 这是防错设计，别绕过。

---

## 5. 当前待办（出片前）

1. **录 30 段实机素材**（`assets/PLACEHOLDER.md` 有逐幕清单），或至少先录第三段核心循环。
2. **拍板 S11 技能数口径**：游戏内版本行文案 `i18n.py:153` / `:716` 仍是「6 技能」，实际技能是 10 个。建议录前改成「10 技能」，否则画面与解说打架（详见 `storyboard.md` 第 3 段）。
3. **配音**：按 `narration.md` 录 `audio/voice.wav`；BGM 放 `audio/bgm.wav`（母本 `docs/演示脚本_0916.md` §4 有 BGM 情绪段落表）。
