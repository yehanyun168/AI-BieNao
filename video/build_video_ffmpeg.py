# -*- coding: utf-8 -*-
"""用真机截图（video/assets/footage/Sxx.png）合成 1080p 演示 mp4，并混入游戏原声。

每镜只用一张实机截图，按 shots.json 的 dur 停留对应秒数，cover-fit 到 1920x1080；
烧录 subtitles.srt 中文字幕。产出 out/AI-BieNao_Demo_1080p.mp4。

音频分**两层**，各自独立成轨、最后终混（可单独取用）：
  1. BGM 床 —— 按「幕」切池（开场/菜单 menu，对局 calm，潜行/危机 tense，结尾主题重现
     menu），**幕内不重启**、幕边界交叉淡入淡出，全片一条连续音乐床。
     → out/audio/bgm_bed_<总长>s.m4a
  2. 音效轨 —— 按全局时间轴把每镜音效叠到绝对时刻（不是逐镜各起一条再拼）。
     → out/audio/sfx_only_<总长>s.m4a
  两条都可单独导出给剪辑软件重配。音效映射依据 docs/演示脚本_0916.md 每镜 audio 设计，
  落到 demo/assets/sfx 真实音效。

用法（在 video/ 目录下）：
    python build_video_ffmpeg.py
    python build_video_ffmpeg.py --no-subs      # 不烧字幕
    python build_video_ffmpeg.py --no-bgm       # 只留音效（等同「录制期关 BGM」）
    python build_video_ffmpeg.py --no-sfx       # 只留 BGM 床
    python build_video_ffmpeg.py --no-audio     # 纯画面无声
    python build_video_ffmpeg.py --audio-only   # 只出音频三轨，不动画面
"""
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)  # game_optimization

FF_EXE = r"C:\Users\tianm\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
if not os.path.exists(FF_EXE):
    FF_EXE = "ffmpeg"

BGM_DIR = os.path.join(ROOT, "demo", "assets", "bgm")
SFX_DIR = os.path.join(ROOT, "demo", "assets", "sfx")
AUDIO_OUT = os.path.join(BASE, "out", "audio")

# 每镜 BGM 池（故事板情绪：开场/菜单 menu，对局 calm，潜行/危机 tense，结尾主题重现 menu）
BGM_SEQ = {}
BGM_SEQ.update({("S%02d" % i): "menu" for i in range(1, 14)})    # S01-S13 开场 + 菜单 + 出身
BGM_SEQ.update({("S%02d" % i): "calm" for i in range(14, 22)})   # S14-S21 对局主界面/技能/科技
BGM_SEQ.update({("S%02d" % i): "tense" for i in range(22, 26)})  # S22-S25 告警/伪装/冲线
BGM_SEQ.update({("S%02d" % i): "menu" for i in range(26, 31)})   # S26-S30 结局 + 主题重现

# 音乐床选曲：每池挑一首**长曲**当床，幕内不重启（曲长 > 幕长 时无需循环）。
# menu.ogg 101.8s / calm_alt3.ogg 110.8s / tense_alt.ogg 102.4s，均长于对应幕。
BED_TRACK = {"menu": "menu.ogg", "calm": "calm_alt3.ogg", "tense": "tense_alt.ogg"}
# 幕边界交叉淡入淡出时长（秒）。两端各用同一时长做 true crossfade，
# 交叉吃掉的时间由前一幕末尾补等长素材补回，故全片总长仍严格等于故事板总长。
XFADE = 1.5
# 末幕「主题重现」从 menu 曲的哪里起播。0.0 = 原样重现开场主题（预告片惯用做法）。
BGM_REPRISE_START = 0.0

# 每镜音效：(文件, 镜内偏移秒)。依据故事板 audio.sfx 语义映射到游戏真实音效。
SFX_CUES = {
    "S01": [("server_hum.wav", 0.0)],
    "S02": [("power_on.wav", 0.0)],
    "S03": [("click.wav", 0.5), ("click.wav", 1.3)],
    "S04": [("click.wav", 0.3), ("click.wav", 1.2)],
    "S05": [("click.wav", 0.5), ("click.wav", 1.3)],
    "S06": [("unlock.wav", 0.2)],
    "S07": [("click.wav", 0.6), ("click.wav", 1.3), ("click.wav", 2.0)],
    "S09": [("counter_warn.wav", 0.3), ("confirm.wav", 1.6)],
    "S11": [("hover.wav", 0.6)],
    "S12": [("select.wav", 0.4), ("select.wav", 1.6), ("select.wav", 2.8)],
    "S13": [("confirm.wav", 0.4)],
    "S15": [("impact_low.wav", 0.3), ("counter_warn.wav", 1.2)],
    "S16": [("click.wav", 0.6), ("click.wav", 1.5)],
    "S17": [("toggle.wav", 0.3), ("machine_run.wav", 0.7)],
    "S18": [("confirm_cast.wav", 0.3), ("success.wav", 1.2)],
    "S19": [("confirm_cast.wav", 0.3), ("counter_warn.wav", 1.2)],
    "S20": [("page.wav", 0.3)],
    "S21": [("unlock.wav", 0.4)],
    "S22": [("counter_warn.wav", 0.3), ("counter_warn.wav", 1.5), ("confirm_cast.wav", 2.7)],
    "S23": [("success.wav", 0.4)],
    "S24": [("unlock.wav", 0.6), ("unlock.wav", 1.9), ("unlock.wav", 3.2)],
    "S25": [("crisis.wav", 0.3), ("impact_low.wav", 2.2)],
    "S26": [("end_win.wav", 0.3)],
    "S27": [("achieve.ogg", 0.6), ("achieve.ogg", 2.2)],
    "S28": [("click.wav", 1.2)],
    "S29": [("page.wav", 0.4)],
}
BGM_VOL = 0.35
SFX_VOL = 0.85


def log(*a):
    print(*a, flush=True)


def run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        log("  [FFMPEG ERROR]")
        log(r.stderr[-1500:])
        return False
    return True


def bgm_acts(shots):
    """把故事板切成「BGM 幕」：同一个情绪池的连续镜头算一幕。

    幕内音乐不重启（这是「不混乱」的关键），只在幕边界换池并交叉淡化。
    返回 [(pool, 起始秒, 时长), ...]。
    """
    acts = []
    t = 0.0
    for s in shots:
        pool = BGM_SEQ.get(s["id"], "calm")
        dur = float(s["dur"])
        if acts and acts[-1][0] == pool:
            acts[-1][2] += dur
        else:
            acts.append([pool, t, dur])
        t += dur
    return [(p, st, d) for p, st, d in acts]


def _bed_track(pool):
    """该池的音乐床选曲（长曲优先），找不到就退回池名同名曲，再退回 calm。"""
    for name in (BED_TRACK.get(pool), pool + ".ogg", "calm.ogg"):
        if name and os.path.exists(os.path.join(BGM_DIR, name)):
            return os.path.join(BGM_DIR, name)
    return None


def build_bgm_bed(seg_dir, shots):
    """全片一条**连续** BGM 床：按幕切池、幕内不重启、幕边界交叉淡入淡出。

    与旧版「逐镜从 0 起播」的区别：旧版每 4~10 秒就把曲子拽回开头、还频繁换曲，
    听感上等于不停重启；这里每幕只在**开头起播一次**，幕内一路播下去。
    """
    acts = bgm_acts(shots)
    total = sum(float(s["dur"]) for s in shots)
    if not acts:
        return None
    os.makedirs(AUDIO_OUT, exist_ok=True)

    cmd = [FF_EXE, "-y"]
    for pool, _st, _d in acts:
        cmd += ["-stream_loop", "-1", "-i", _bed_track(pool)]

    filters, labels = [], []
    for k, (pool, _st, dur) in enumerate(acts):
        # 除末幕外，每幕多留 XFADE 秒素材，补回交叉淡化吃掉的时间 → 全片总长不变
        need = dur + (XFADE if k < len(acts) - 1 else 0.0)
        # 末幕（主题重现）从指定位置起播
        ss = (BGM_REPRISE_START
              if (k == len(acts) - 1 and pool == "menu" and acts[0][0] == "menu")
              else 0.0)
        filters.append("[%d:a]aresample=44100,aformat=channel_layouts=stereo,"
                       "atrim=start=%.3f:end=%.3f,asetpts=N/SR/TB,volume=%s[g%d]"
                       % (k, ss, ss + need, BGM_VOL, k))
        labels.append("[g%d]" % k)

    prev = labels[0]
    for k in range(1, len(labels)):
        out = "[x%d]" % k
        filters.append("%s%sacrossfade=d=%.2f:c1=tri:c2=tri%s"
                       % (prev, labels[k], XFADE, out))
        prev = out
    filters.append("%saformat=sample_rates=44100:channel_layouts=stereo[bed]" % prev)

    bed = os.path.join(AUDIO_OUT, "bgm_bed_%ds.m4a" % int(round(total)))
    cmd += ["-filter_complex", ";".join(filters), "-map", "[bed]",
            "-t", "%.3f" % total, "-c:a", "aac", "-b:a", "192k", bed]
    if not run(cmd):
        log("  [WARN] BGM 床生成失败")
        return None
    log("  BGM 床：%d 幕（%s）→ %s"
        % (len(acts), " + ".join("%s %.0fs" % (p, d) for p, _s, d in acts),
           os.path.basename(bed)))
    return bed


def build_sfx_track(shots):
    """全片一条音效轨：按**全局时间轴**把每镜音效叠到绝对时刻。

    走绝对时间轴而不是「逐镜各起一条再拼接」，是为了让相邻镜之间的音效可以自然
    交叠、也方便单独导出给剪辑软件重配。
    """
    cues = []
    t = 0.0
    for s in shots:
        sid, dur = s["id"], float(s["dur"])
        for fn, off in SFX_CUES.get(sid, []):
            p = os.path.join(SFX_DIR, fn)
            if os.path.exists(p):
                cues.append((p, int(round((t + float(off)) * 1000))))
        t += dur
    total = t
    if not cues:
        log("  [WARN] 没有任何音效可用")
        return None
    os.makedirs(AUDIO_OUT, exist_ok=True)

    cmd = [FF_EXE, "-y"]
    for p, _ms in cues:
        cmd += ["-i", p]
    filters, labels = [], []
    for k, (_p, ms) in enumerate(cues):
        filters.append("[%d:a]aresample=44100,aformat=channel_layouts=stereo,"
                       "adelay=%d:all=1,volume=%s[c%d]" % (k, ms, SFX_VOL, k))
        labels.append("[c%d]" % k)
    filters.append("%samix=inputs=%d:normalize=0:duration=longest,"
                   "apad,atrim=0:%.3f[sfx]"
                   % ("".join(labels), len(labels), total))

    sfx = os.path.join(AUDIO_OUT, "sfx_only_%ds.m4a" % int(round(total)))
    cmd += ["-filter_complex", ";".join(filters), "-map", "[sfx]",
            "-t", "%.3f" % total, "-c:a", "aac", "-b:a", "192k", sfx]
    if not run(cmd):
        log("  [WARN] 音效轨生成失败")
        return None
    log("  音效轨：%d 处（全局时间轴）→ %s" % (len(cues), os.path.basename(sfx)))
    return sfx


def build_audio(seg_dir, shots, want_bgm=True, want_sfx=True):
    """生成成片音轨。BGM 床与音效轨各自独立导出，再终混成 soundtrack.m4a。"""
    total = sum(float(s["dur"]) for s in shots)
    os.makedirs(AUDIO_OUT, exist_ok=True)

    bed = build_bgm_bed(seg_dir, shots) if want_bgm else None
    sfx = build_sfx_track(shots) if want_sfx else None
    if not bed and not sfx:
        log("  [WARN] 音轨为空")
        return None
    if bed and not sfx:
        return bed
    if sfx and not bed:
        return sfx

    soundtrack = os.path.join(seg_dir, "soundtrack.m4a")
    cmd = [FF_EXE, "-y", "-i", bed, "-i", sfx,
           "-filter_complex",
           "[0:a][1:a]amix=inputs=2:normalize=0:duration=first[aout]",
           "-map", "[aout]", "-t", "%.3f" % total,
           "-c:a", "aac", "-b:a", "192k", soundtrack]
    if not run(cmd):
        log("  [WARN] 终混失败")
        return None
    log("  终混：BGM 床 + 音效轨 → soundtrack.m4a（%.1fs）" % total)
    return soundtrack


def main():
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-bgm", action="store_true",
                    help="不铺 BGM 床，只留音效（等同「录制期关 BGM」）")
    ap.add_argument("--no-sfx", action="store_true", help="不叠音效，只留 BGM 床")
    ap.add_argument("--audio-only", action="store_true",
                    help="只生成音频三轨（BGM 床/音效/终混），不重新编码画面")
    args = ap.parse_args()

    with open(os.path.join(BASE, "shots.json"), encoding="utf-8") as f:
        data = json.load(f)
    shots = data["shots"]

    sub_style = "FontName=Microsoft YaHei,FontSize=30,Outline=2,Shadow=1,Bold=1"
    subtitles_srt = os.path.join(BASE, "subtitles.srt")
    burn_subs = (not args.no_subs) and os.path.exists(subtitles_srt)

    seg_dir = os.path.join(BASE, "_segtmp")
    os.makedirs(seg_dir, exist_ok=True)

    want_bgm = not (args.no_audio or args.no_bgm)
    want_sfx = not (args.no_audio or args.no_sfx)

    if args.audio_only:
        soundtrack = build_audio(seg_dir, shots, want_bgm, want_sfx)
        if not soundtrack:
            log("[FAIL] 音频生成失败")
            return 1
        log("=" * 60)
        log("音频完成（未重新编码画面）：%s" % os.path.join(AUDIO_OUT, ""))
        return 0

    total = 0.0
    seg_list = []
    for i, s in enumerate(shots, 1):
        src = (s.get("media") or {}).get("src", "")
        img = os.path.join(BASE, src)
        if not os.path.exists(img):
            log("[WARN] 缺少素材，跳过 %s: %s" % (s["id"], src))
            continue
        dur = float(s["dur"])
        total += dur
        seg = os.path.join(seg_dir, "seg_%03d.mp4" % i)
        vf = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
        cmd = [FF_EXE, "-y", "-loop", "1", "-i", img,
               "-t", "%.3f" % dur, "-r", "30", "-vf", vf,
               "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-crf", "18", "-preset", "veryfast", "-an", seg]
        if not run(cmd):
            log("[FAIL] 分镜 %s 编码失败" % s["id"])
            return 1
        seg_list.append(seg)
        log("  [%02d/%02d] %s  %.1fs  %s" % (i, len(shots), s["id"], dur, os.path.basename(src)))

    if not seg_list:
        log("[ERROR] 没有任何分镜素材")
        return 1

    list_path = os.path.join(seg_dir, "list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for seg in seg_list:
            f.write("file '%s'\n" % seg.replace("\\", "/"))

    os.makedirs(os.path.join(BASE, "out"), exist_ok=True)
    merged = os.path.join(seg_dir, "merged.mp4")
    if not run([FF_EXE, "-y", "-f", "concat", "-safe", "0",
                "-i", list_path, "-c", "copy", merged]):
        log("[FAIL] 拼接失败")
        return 1

    soundtrack = None
    if not args.no_audio:
        soundtrack = build_audio(seg_dir, shots, want_bgm, want_sfx)

    vf = ("subtitles=subtitles.srt:force_style='%s'" % sub_style) if burn_subs else None
    out = os.path.join(BASE, "out", "AI-BieNao_Demo_1080p.mp4")
    cmd = [FF_EXE, "-y", "-i", merged]
    has_audio = bool(soundtrack and os.path.exists(soundtrack))
    if has_audio:
        cmd += ["-i", soundtrack]
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-map", "0:v:0"]
    if has_audio:
        cmd += ["-map", "1:a:0", "-c:a", "copy"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p"]
    if not has_audio:
        cmd += ["-an"]
    cmd += [out]
    log("  封装成片 -> %s  (字幕:%s 音轨:%s)" % (
        out, "已烧录" if burn_subs else "无", "有" if has_audio else "无"))
    if not run(cmd, cwd=BASE):
        log("[FAIL] 最终封装失败")
        return 1

    if has_audio:
        layers = []
        if want_bgm:
            layers.append("BGM 床")
        if want_sfx:
            layers.append("音效轨")
        audio_desc = "+".join(layers)
    else:
        audio_desc = "未混入"
    sz = os.path.getsize(out)
    log("=" * 60)
    log("完成：%s" % out)
    log("  时长约 %.1fs（目标 178.0s）| 大小 %.1f MB" % (total, sz / 1024 / 1024))
    log("  字幕：%s | 音轨：%s" % ("已烧录" if burn_subs else "未烧录", audio_desc))
    if has_audio:
        log("  分层音轨（可单独取用）：%s" % AUDIO_OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
