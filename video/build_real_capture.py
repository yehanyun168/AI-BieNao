# -*- coding: utf-8 -*-
"""把 record_demo.py 录下的整屏原始录像，裁成游戏窗口、缩放 1080p，并混入 BGM/音效与字幕。

产出 out/AI-BieNao_Demo_RealCapture_1080p.mp4（真·动态实机录屏）。

音轨与静帧版共用同一套两层管线（见 build_video_ffmpeg.build_audio）：
BGM 床按幕连续铺（幕内不重启）、音效按全局时间轴叠；两条轨也各自导出到 out/audio/。

用法（在 video/ 目录下）：
    python build_real_capture.py
    python build_real_capture.py --no-bgm       # 只留音效（等同「录制期关 BGM」）
    python build_real_capture.py --no-sfx       # 只留 BGM 床
"""
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import build_video_ffmpeg as B  # noqa: E402  复用 ffmpeg 路径与音频生成

OUT = os.path.join(BASE, "out")
RAW = os.path.join(OUT, "_raw_capture.mp4")
RECT = os.path.join(OUT, "_raw_rect.json")
SUB_STYLE = "FontName=Microsoft YaHei,FontSize=30,Outline=2,Shadow=1,Bold=1"


def main():
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--no-bgm", action="store_true", help="不铺 BGM 床，只留音效")
    ap.add_argument("--no-sfx", action="store_true", help="不叠音效，只留 BGM 床")
    args = ap.parse_args()

    if not os.path.exists(RAW):
        print("[ERROR] 没找到原始录像：%s" % RAW)
        return 1

    with open(os.path.join(BASE, "shots.json"), encoding="utf-8") as f:
        shots = json.load(f)["shots"]
    total = sum(float(s["dur"]) for s in shots)

    seg_dir = os.path.join(BASE, "_segtmp")
    os.makedirs(seg_dir, exist_ok=True)

    # 音轨：BGM 床（按幕连续）+ 音效轨（全局时间轴），再终混
    soundtrack = B.build_audio(seg_dir, shots,
                               want_bgm=not args.no_bgm,
                               want_sfx=not args.no_sfx)

    rect = None
    if os.path.exists(RECT):
        with open(RECT, encoding="utf-8") as f:
            rect = json.load(f)
        print("[crop] 窗口矩形 =", rect)
    else:
        print("[crop] 无窗口矩形，按整屏缩放")

    vf = []
    if rect:
        x, y, w, h = int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"])
        vf.append("crop=%d:%d:%d:%d" % (w, h, x, y))
    vf.append("scale=1920:1080:force_original_aspect_ratio=increase")
    vf.append("crop=1920:1080")
    vf.append("setsar=1")
    if os.path.exists(os.path.join(BASE, "subtitles.srt")):
        vf.append("subtitles=subtitles.srt:force_style='%s'" % SUB_STYLE)
    vf_s = ",".join(vf)

    out = os.path.join(OUT, "AI-BieNao_Demo_RealCapture_1080p.mp4")
    cmd = [B.FF_EXE, "-y", "-i", RAW]
    has_audio = bool(soundtrack and os.path.exists(soundtrack))
    if has_audio:
        cmd += ["-i", soundtrack]
    cmd += ["-vf", vf_s, "-map", "0:v:0"]
    if has_audio:
        cmd += ["-map", "1:a:0", "-c:a", "copy"]
    cmd += ["-t", "%.3f" % total, "-c:v", "libx264", "-crf", "18",
            "-preset", "veryfast", "-pix_fmt", "yuv420p", out]
    print("  合成真录屏 -> %s" % out)
    r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True)
    if r.returncode != 0:
        print("[FFMPEG ERROR]")
        print(r.stderr[-1800:])
        return 1
    print("=" * 60)
    print("完成：%s" % out)
    print("  时长 %.1fs | 大小 %.1f MB | 音轨:%s"
          % (total, os.path.getsize(out) / 1024 / 1024, "有" if has_audio else "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
