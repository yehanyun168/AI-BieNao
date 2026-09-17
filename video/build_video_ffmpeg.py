# -*- coding: utf-8 -*-
"""用真机截图（video/assets/footage/Sxx.png）直接合成 1080p 演示 mp4。

比 export_frames.py 的逐帧无头浏览器渲染快得多：每镜只用一张实机截图，
按 shots.json 的 dur 停留对应秒数，cover-fit 到 1920x1080，最后统一烧录
subtitles.srt 中文字幕。产出 out/AI-BieNao_Demo_1080p.mp4。

用法（在 video/ 目录下）：
    python build_video_ffmpeg.py
    python build_video_ffmpeg.py --no-subs      # 不烧字幕
"""
import json
import os
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))

FF_EXE = r"C:\Users\tianm\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
if not os.path.exists(FF_EXE):
    # 兜底走 PATH / 同目录 ffmpeg.bat
    FF_EXE = "ffmpeg"


def log(*a):
    print(*a, flush=True)


def run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        log("  [FFMPEG ERROR]")
        log(r.stderr[-1500:])
        return False
    return True


def main():
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--no-subs", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(BASE, "shots.json"), encoding="utf-8") as f:
        data = json.load(f)
    shots = data["shots"]

    # 字幕样式：确保中文可用（Windows 默认带微软雅黑）
    sub_style = "FontName=Microsoft YaHei,FontSize=30,Outline=2,Shadow=1,Bold=1"
    subtitles_srt = os.path.join(BASE, "subtitles.srt")
    burn_subs = (not args.no_subs) and os.path.exists(subtitles_srt)

    seg_dir = os.path.join(BASE, "_segtmp")
    os.makedirs(seg_dir, exist_ok=True)

    seg_list = []
    total = 0.0
    for i, s in enumerate(shots, 1):
        src = (s.get("media") or {}).get("src", "")
        img = os.path.join(BASE, src)
        if not os.path.exists(img):
            log("[WARN] 缺少素材，跳过 %s: %s" % (s["id"], src))
            continue
        dur = float(s["dur"])
        total += dur
        seg = os.path.join(seg_dir, "seg_%03d.mp4" % i)
        # loop 单图 -> 停留 dur 秒，cover-fit 到 1920x1080
        vf = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
        cmd = [
            FF_EXE, "-y", "-loop", "1", "-i", img,
            "-t", "%.3f" % dur, "-r", "30", "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "18", "-preset", "veryfast", "-an", seg,
        ]
        if not run(cmd):
            log("[FAIL] 分镜 %s 编码失败" % s["id"])
            return 1
        seg_list.append(seg)
        log("  [%02d/%02d] %s  %.1fs  %s" % (i, len(shots), s["id"], dur, os.path.basename(src)))

    if not seg_list:
        log("[ERROR] 没有任何分镜素材")
        return 1

    # 拼接清单
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

    out = os.path.join(BASE, "out", "AI-BieNao_Demo_1080p.mp4")
    if burn_subs:
        # 用相对路径避免 Windows 盘符冒号被 ffmpeg filter 解析成选项分隔符
        vf = "subtitles=subtitles.srt:force_style='%s'" % sub_style
        log("  烧录字幕 + 最终编码 -> %s" % out)
        if not run([FF_EXE, "-y", "-i", merged, "-vf", vf,
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-an", out], cwd=BASE):
            log("[FAIL] 烧字幕失败")
            return 1
    else:
        log("  直出（无字幕） -> %s" % out)
        if not run([FF_EXE, "-y", "-i", merged, "-c", "copy", out]):
            log("[FAIL] 直出失败")
            return 1

    sz = os.path.getsize(out)
    log("=" * 60)
    log("完成：%s" % out)
    log("  时长约 %.1fs（目标 178.0s）| 大小 %.1f MB" % (total, sz / 1024 / 1024))
    log("  字幕：%s" % ("已烧录" if burn_subs else "未烧录"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
