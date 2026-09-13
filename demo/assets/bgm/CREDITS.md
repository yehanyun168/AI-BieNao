# demo/assets/bgm/ —— 背景音乐来源与授权

本目录 BGM 全部来自 **Abstraction / Tallbeard Studios · Free Music Loop Bundle**，
授权为 **CC0 公有领域**（可商用、可修改、可再分发，**署名非强制**）。

---

## 一、曲目登记（2026-09-13 · 真人试听裁决定版）

| 文件 | 原始曲名 | 用途 | 时长 | 来源包 |
|---|---|---|---|---|
| `calm.ogg` | Penguin Town | **主选** · 正常经营态 | 35.3s | Tallbeard |
| `calm_alt.ogg` | Rabbit Town | 备选 · 正常经营态 | 45.5s | Tallbeard |
| `calm_alt2.ogg` | I am not clumsy | 备选二 · 正常经营态 | 39.3s | HydroGene |
| `tense.ogg` | Rumble at the Gates | **主选** · 被封锁/被抵制态 | 90.9s | Tallbeard |
| `tense_alt.ogg` | Save the City | 备选 · 被封锁/被抵制态 | 102.4s | Tallbeard |

各态候选数不要求一致（calm 3 首 / tense 2 首）：`bgm.get_sound()` 在变体
越界时自动回落该态主选，不会静音。设置页曲目切换范围为 **0 ~ 2**。

> 听感裁决（用户原话转录）：`penguin town` 与 `rabbit town` 适合正常情况，
> **前者更顽皮**；被封锁被抵制时用 `rumble at the gates` 与 `save the city`，
> **前者更富希望，后者压迫感更强**。
> 后续追加采纳 `i am not clumsy`（HydroGene）作为 calm 第三候选。
> 据此：calm 主选 Penguin Town、tense 主选 Rumble at the Gates；
> 其余保留在目录内，经 `bgm.set_track_variant(n)` 可热切换。

### 音量归一化

5 首曲目峰值已统一到 **−0.1 ~ −0.5 dBFS**（原始素材极差 2.9 dB）。
统一是为避免切歌/切态时响度突变 —— `bgm.VOLUME` 是全局统一增益，
若素材本身响度差异大，玩家会感到「切到紧张态突然变小声」。
其中 `calm_alt2.ogg` 由 MP3 转码得来，原始峰值 −2.9 dBFS，已增益补偿。

### 选择 OGG 而非 MP3 的原因

作者在包内 README 明确说明：

> MP3 files will often NOT loop seamlessly... It is recommended to use these
> songs as OGG files.

本项目 BGM 是 `loop=True` 循环播放，MP3 的循环缝隙会每轮暴露一次，
故一律取 OGG 版。HydroGene 包**只发布 MP3**，因此其曲目经
`tools/mp3_to_ogg.py` 转码（含首尾静音裁剪 + 10ms 等功率交叉淡化，
消除循环接缝的咔哒声）后入库。原始 MP3 保留在
`assets_library/audio/bgm/hydrogene-8bit/`（该目录不入库）。

---

## 二、已退役素材（存档备查）

- `calm.wav` / `tense.wav`（各 529KB，12 秒合成片段，22050Hz 单声道）
  —— 由 `tools/gen_bgm.py` 合成，**已于 2026-09-13 移除**。
  退役原因：时长仅 12 秒，循环痕迹明显（每 12 秒听感重置一次），
  真人试听反馈不佳。生成脚本 `tools/gen_bgm.py` **保留**，作为无外部素材时
  的兜底方案；如需回退，重新执行即可再生成同款 WAV（`bgm.py` 的
  `SUFFIXES` 中 `.wav` 仍是合法候选后缀）。

---

## 三、授权原文

### 3.1 Abstraction / Tallbeard Studios（calm / calm_alt / tense / tense_alt）

> ===============================
> Abstraction - Music Loop Bundle
> ===============================
>
> This asset bundle is licensed as Public Domain (CC-0 - https://creativecommons.org/publicdomain/zero/1.0/)
>
> To the extent possible under law, Abstraction Music (https://abstractionmusic.com/)
> and Tallbeard Studios (https://www.abstractionmusic.com/tallbeard.htm) has waived
> all copyright and related or neighboring rights to the music contained in this
> asset pack. This work is published from the United States.
>
> All assets are available to use in any commercial or non-commercial project,
> and may be modified in any way the user chooses.
>
> Although permitted within the license terms, Abstraction and Tallbeard Studios
> do not endorse the use of these assets in any projects relating to NFTs,
> AI/Machine Learning, or direct resale of unmodified assets.

**结论**：CC0，无署名义务。本项目仍在此登记出处，一是便于日后追溯，
二是作者在 README 中表达了「用了请告诉我」的善意请求；
若正式发布，建议在游戏内 credits 署名：

```
Music: "Penguin Town" / "Rabbit Town" / "Rumble at the Gates" / "Save the City"
by Abstraction (tallbeard.itch.io/music-loop-bundle) — CC0
```

⚠️ 注意授权中「不背书用于 NFT / AI 机器学习」一句属**作者意愿表达**，
CC0 本身无此限制；本项目为普通像素策略游戏，无冲突。

### 3.2 HydroGene（calm_alt2 = "I am not clumsy"）

授权登记见 `assets_library/_licenses/README.md`：

> | HydroGene 18 首 8-bit | https://hydrogene.itch.io/high-quality-8-bit-musics | CC0 |

**结论**：CC0，无署名义务。该素材包**未随包附带授权文本**，
授权信息来自 itch.io 商店页（下载时确认）。若正式发布，建议一并署名：

```
Music: "I am not clumsy" by HydroGene (hydrogene.itch.io/high-quality-8-bit-musics) — CC0
```

⚠️ **补强建议**：目前该曲唯一授权凭据是 `_licenses/README.md` 里的一行表格
记录（人工誊写），无原始页面存档。若日后要公开发布，建议打开 itch 页面
截图或另存页面存档到 `demo/assets/bgm/` 同级，作为授权留痕的第二凭证。
