# -*- coding: utf-8 -*-
"""用真机截图（video/assets/footage/Sxx.png）合成 1080p 演示 mp4，并混入游戏原声。

每镜只用一张实机截图，按 shots.json 的 dur 停留对应秒数，cover-fit 到 1920x1080；
音频逐镜生成（BGM 按情绪池循环到镜长 + 该镜音效按偏移叠加），再与画面一起
烧录 subtitles.srt 中文字幕。产出 out/AI-BieNao_Demo_1080p.mp4。

音效映射依据 docs/演示脚本_0916.md 的每镜 audio 设计，落到 demo/assets/sfx 真实音效。

用法（在 video/ 目录下）：
    python build_video_ffmpeg.py
    python build_video_ffmpeg.py --no-subs      # 不烧字幕
    python build_video_ffmpeg.py --no-audio     # 纯画面无声
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

# 每镜 BGM 池（故事板情绪：开场/菜单 menu，对局 calm，潜行/危机 tense，结尾主题重现 menu）
BGM_SEQ = {}
BGM_SEQ.update({("S%02d" % i): "menu" for i in range(1, 14)})    # S01-S13 开场 + 菜单 + 出身
BGM_SEQ.update({("S%02d" % i): "calm" for i in range(14, 22)})   # S14-S21 对局主界面/技能/科技
BGM_SEQ.update({("S%02d" % i): "tense" for i in range(22, 26)})  # S22-S25 告警/伪装/冲线
BGM_SEQ.update({("S%02d" % i): "menu" for i in range(26, 31)})   # S26-S30 结局 + 主题重现

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


def build_audio(seg_dir, shots):
    """逐镜生成音频段（BGM 循环 + 音效按偏移叠加），再拼接成整条音轨。"""
    parts = []
    ok_all = True
    for i, s in enumerate(shots, 1):
        sid, dur = s["id"], float(s["dur"])
        pool = BGM_SEQ.get(sid, "calm")
        bgm = os.path.join(BGM_DIR, pool + ".ogg")
        if not os.path.exists(bgm):
            bgm = os.path.join(BGM_DIR, "calm.ogg")
        cmd = [FF_EXE, "-y", "-stream_loop", "-1", "-i", bgm]
        filters = ["[0:a]aresample=44100,aformat=channel_layouts=stereo,"
                   "volume=%s,atrim=0:%.3f[bgm0]" % (BGM_VOL, dur)]
        labels = ["[bgm0]"]
        inp = 1
        for j, (fn, off) in enumerate(SFX_CUES.get(sid, [])):
            p = os.path.join(SFX_DIR, fn)
            if not os.path.exists(p):
                continue
            cmd += ["-i", p]
            ms = int(round(off * 1000))
            lab = "[c%d]" % j
            filters.append(
                "[%d:a]adelay=%d,aresample=44100,aformat=channel_layouts=stereo,"
                "volume=%s%s" % (inp, ms, SFX_VOL, lab))
            labels.append(lab)
            inp += 1
        if len(labels) == 1:
            filters.append("[bgm0]apad,atrim=0:%.3f[aout]" % dur)
        else:
            filters.append("%samix=inputs=%d:normalize=0,apad,atrim=0:%.3f[aout]"
                           % ("".join(labels), len(labels), dur))
        seg = os.path.join(seg_dir, "aud_%03d.m4a" % i)
        cmd += ["-filter_complex", ";".join(filters), "-map", "[aout]",
                "-t", "%.3f" % dur, "-c:a", "aac", "-b:a", "192k", seg]
        if not run(cmd):
            ok_all = False
            break
        parts.append(seg)
    if not ok_all or not parts:
        log("  [WARN] 分段音轨生成失败")
        return None
    # 拼接音频段
    alist = os.path.join(seg_dir, "aud_list.txt")
    with open(alist, "w", encoding="utf-8") as f:
        for p in parts:
            f.write("file '%s'\n" % p.replace("\\", "/"))
    soundtrack = os.path.join(seg_dir, "soundtrack.m4a")
    if not run([FF_EXE, "-y", "-f", "concat", "-safe", "0", "-i", alist,
                "-c", "copy", soundtrack]):
        log("  [WARN] 音轨拼接失败")
        return None
    n_cues = sum(len(v) for k, v in SFX_CUES.items() if any(s["id"] == k for s in shots))
    log("  混音完成：%d 段音轨（BGM 床 %.1fs + %d 处音效）"
        % (len(parts), sum(float(s["dur"]) for s in shots), n_cues))
    return soundtrack


def main():
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(BASE, "shots.json"), encoding="utf-8") as f:
        data = json.load(f)
    shots = data["shots"]

    sub_style = "FontName=Microsoft YaHei,FontSize=30,Outline=2,Shadow=1,Bold=1"
    subtitles_srt = os.path.join(BASE, "subtitles.srt")
    burn_subs = (not args.no_subs) and os.path.exists(subtitles_srt)

    seg_dir = os.path.join(BASE, "_segtmp")
    os.makedirs(seg_dir, exist_ok=True)

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
    if not args.no_audio and os.path.isdir(BGM_DIR):
        soundtrack = build_audio(seg_dir, shots)

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

    sz = os.path.getsize(out)
    log("=" * 60)
    log("完成：%s" % out)
    log("  时长约 %.1fs（目标 178.0s）| 大小 %.1f MB" % (total, sz / 1024 / 1024))
    log("  字幕：%s | 音轨：%s" % ("已烧录" if burn_subs else "未烧录",
                                    "BGM+音效" if has_audio else "未混入"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
