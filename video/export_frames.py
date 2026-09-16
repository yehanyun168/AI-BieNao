# -*- coding: utf-8 -*-
"""无头逐帧导出：用本机 Edge 把 index.html 的每个时间点截成 1920x1080 PNG。

用法（在本 video/ 目录下）：
    python export_frames.py                    # 全部帧（178s x 30fps = 5340 帧）
    python export_frames.py --start 76 --end 96    # 只导 76-96 秒（先试渲）
    python export_frames.py --step 10          # 每 10 帧导 1 帧（快速抽查）
    python export_frames.py --fps 24           # 改帧率
    python export_frames.py --force            # 覆盖已存在的帧
    python export_frames.py --no-subs          # 不烧字幕（字幕交给 ffmpeg 挂 srt）
    python export_frames.py --jobs 12          # 并发数（默认 8）

输出：
    frames/f000001.png ...（连续编号，ffmpeg 直接吃）
    frames/timecode.txt（每帧时间码，便于核对）

依赖：仅 Python 标准库 + 本机 Edge（路径见下）。
"""
import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(BASE, "index.html")
FRAMES = os.path.join(BASE, "frames")

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",  # chrome 也可
]


def find_browser():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    print("[ERROR] 找不到 Edge/Chrome，请把浏览器路径加进脚本顶部 EDGE_CANDIDATES")
    sys.exit(1)


def png_size(path):
    import struct
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def shoot(browser, url, out, tries=2, slot=0):
    """截一帧，失败重试。返回 True/False。

    注意：Edge/Chrome 无头模式下多个实例共用默认 user-data-dir 会互锁，
    因此每个并发槽位分配独立 profile 目录（否则高并发时会随机失败）。
    """
    import threading
    tag = "%s_%d" % (threading.get_ident(), slot)
    profile = os.path.join(os.environ.get("TEMP", "/tmp"), "edge_profile_" + tag)
    for k in range(tries):
        r = subprocess.run(
            [browser,
             "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
             "--disable-extensions", "--mute-audio", "--no-default-browser-check",
             "--user-data-dir=" + profile,
             "--window-size=1920,1080",
             "--virtual-time-budget=6000",
             "--screenshot=" + out, url],
            capture_output=True, timeout=90)
        if os.path.exists(out) and os.path.getsize(out) > 5000:
            sz = png_size(out)
            if sz == (1920, 1080):
                return True
        time.sleep(0.5)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=float, default=0.0, help="起始秒")
    ap.add_argument("--end", type=float, default=None, help="结束秒（默认到片尾）")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--step", type=int, default=1, help="每 N 帧导 1 帧")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-subs", action="store_true", help="不渲染字幕")
    ap.add_argument("--out", default=FRAMES)
    args = ap.parse_args()

    import json
    with open(os.path.join(BASE, "shots.json"), encoding="utf-8") as f:
        meta = json.load(f)["meta"]
    total = float(meta["total"])
    end = args.end if args.end is not None else total
    start, end = max(0.0, args.start), min(end, total)

    browser = find_browser()
    os.makedirs(args.out, exist_ok=True)
    url_base = "file:///" + INDEX.replace("\\", "/")

    n0 = int(round(start * args.fps)) + 1          # 帧号从 1 开始
    n1 = int(round(end * args.fps))
    todo = []
    for n in range(n0, n1 + 1):
        if args.step > 1 and (n - n0) % args.step != 0:
            continue
        todo.append(n)
    print("=" * 62)
    print("导出范围 %.2fs - %.2fs @ %.0f fps | 共 %d 帧 | 并发 %d"
          % (start, end, args.fps, len(todo), args.jobs))
    print("输出 -> %s" % args.out)
    print("=" * 62)

    sub_q = "&subs=0" if args.no_subs else ""

    def job(n):
        t = (n - 1) / args.fps
        out = os.path.join(args.out, "f%06d.png" % n)
        if not args.force and os.path.exists(out) and os.path.getsize(out) > 5000:
            return (n, t, "skip")
        url = "%s?t=%.4f&still=1%s" % (url_base, t, sub_q)
        ok = shoot(browser, url, out, slot=n % args.jobs)
        return (n, t, "ok" if ok else "FAIL")

    done = fail = 0
    t0 = time.time()
    fails = []
    with open(os.path.join(args.out, "timecode.txt"), "w", encoding="utf-8") as tc:
        tc.write("# frame\ttime_s\n")
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = {ex.submit(job, n): n for n in todo}
            for fu in as_completed(futs):
                n, t, st = fu.result()
                tc.write("f%06d\t%.4f\n" % (n, t))
                if st == "FAIL":
                    fail += 1
                    fails.append(n)
                    print("  [FAIL] f%06d  t=%.2fs" % (n, t))
                else:
                    done += 1
                    if done % 100 == 0 or done == len(todo):
                        rate = done / max(1e-9, time.time() - t0)
                        eta = (len(todo) - done - fail) / max(1e-9, rate)
                        print("  %d/%d 帧 | %.1f 帧/秒 | 剩余约 %.0f 分钟"
                              % (done, len(todo), rate, eta / 60))
    print("=" * 62)
    print("完成：%d 成功 / %d 失败 / 总 %d" % (done, fail, len(todo)))
    if fails:
        print("失败帧（可用 --force 重跑）：", ", ".join("f%06d" % x for x in fails[:20]))
    print("下一步：export_video.bat 合成 mp4")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
