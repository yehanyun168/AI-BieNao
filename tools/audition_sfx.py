# -*- coding: utf-8 -*-
"""audition_sfx.py —— 音效试听 / 候选对比工具（人工验音用，不参与游戏运行）。

用途：把候选音效依次播一遍并打印清单，供人工判断「哪条听起来像什么语义」。
自动化测试无法替代耳朵 —— 本工具存在的意义就是把「选音」这一步交还给人类。

用法：
    PY="C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe"
    "$PY" tools/audition_sfx.py                 # 试听项目当前全部音效
    "$PY" tools/audition_sfx.py --lib sfx --filter click   # 素材库 interface 的 click 系
    "$PY" tools/audition_sfx.py --lib pixel     # 素材库 pixel-ui-sfx 全量（65 条，较长）
    "$PY" tools/audition_sfx.py --lib pixel --range 1-12   # 只试听序号 1..12
    "$PY" tools/audition_sfx.py --gap 1.2       # 调整条目间隔秒数

⚠️ 必须带 KIVY_NO_ARGS=1 运行，否则 Kivy 会抢走命令行参数解析：
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_sfx.py --lib sfx

注意：
- 需要能出声的音频后端；无后端时 SoundLoader.load 返回 None，本脚本会明确提示。
- 全程只读，不修改任何文件。
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))

# 素材库位置（被 .gitignore 排除，仅本机存在）
LIB = os.path.join(ROOT, 'assets_library', 'audio')

LIBS = {
    # 名称: (目录, 是否递归)
    'sfx':   (os.path.join(LIB, 'sfx', 'interface-sounds', 'Audio'), False),
    'ui':    (os.path.join(LIB, 'sfx', 'ui-audio', 'Audio'), False),
    'digi':  (os.path.join(LIB, 'sfx', 'digital-audio', 'Audio'), False),
    'scifi': (os.path.join(LIB, 'sfx', 'sci-fi-sounds', 'Audio'), False),
    'pixel': (os.path.join(LIB, 'sfx', 'pixel-ui-sfx', '--Pixelated UI'), False),
}

AUDIO_EXT = ('.wav', '.ogg', '.mp3')


def _collect(path, recursive=False):
    out = []
    if not os.path.isdir(path):
        return out
    if recursive:
        for dirpath, _dirs, files in os.walk(path):
            for f in files:
                if f.lower().endswith(AUDIO_EXT):
                    out.append(os.path.join(dirpath, f))
    else:
        for f in os.listdir(path):
            if f.lower().endswith(AUDIO_EXT):
                out.append(os.path.join(path, f))
    return sorted(out)


def _targets(args):
    """返回 [(显示名, 绝对路径), ...]"""
    if args.lib:
        # 试听素材库
        key = args.lib.lower()
        if key not in LIBS:
            print('未知库名 %r；可选：%s' % (args.lib, ', '.join(sorted(LIBS))))
            return []
        d, rec = LIBS[key]
        files = _collect(d, rec)
        # 可选的按名过滤（如 click / select）
        if args.filter:
            kw = args.filter.lower()
            files = [f for f in files if kw in os.path.basename(f).lower()]
    else:
        # 试听项目当前音效
        d = os.path.join(ROOT, 'demo', 'assets', 'sfx')
        files = _collect(d)
    # 可选的序号区间（1-based，含两端）
    if args.range:
        lo, hi = args.range
        files = files[max(0, lo - 1):hi]
    return [(os.path.basename(f), f) for f in files]


def main():
    ap = argparse.ArgumentParser(description='音效试听 / 候选对比')
    ap.add_argument('--lib', help='素材库名：%s（省略则试听项目当前音效）'
                                  % '/'.join(sorted(LIBS)))
    ap.add_argument('--filter', default=None,
                    help='按文件名关键词过滤（如 click / select）')
    ap.add_argument('--range', dest='rng', default=None,
                    help='只试听序号区间，如 --range 1-12（1-based，含两端）')
    ap.add_argument('--gap', type=float, default=0.9, help='条目间隔秒数（默认 0.9）')
    ap.add_argument('--vol', type=float, default=0.5, help='播放音量（默认 0.5）')
    args = ap.parse_args()

    # 解析序号区间 "1-12" / "5" / "5-"
    rng = None
    if args.rng:
        txt = str(args.rng).strip()
        try:
            if '-' in txt:
                a, b = txt.split('-', 1)
                lo = int(a) if a.strip() else 1
                hi = int(b) if b.strip() else 10 ** 9
            else:
                lo = hi = int(txt)
            rng = (max(1, lo), max(1, hi))
        except ValueError:
            print('--range 格式无效：%r（应为 1-12 或 5）' % args.rng)
            return 2
    args.range = rng

    items = _targets(args)
    if not items:
        print('没有可试听的音效。')
        return 1

    from kivy.core.audio import SoundLoader

    print('=' * 62)
    print('将试听 %d 条音效（间隔 %.2fs，音量 %.2f）' % (len(items), args.gap, args.vol))
    print('按 Ctrl+C 可随时中断')
    print('=' * 62)
    ok = miss = 0
    try:
        for i, (name, path) in enumerate(items, 1):
            snd = SoundLoader.load(path)
            if snd is None:
                miss += 1
                print('%3d/%3d  %-24s  [加载失败/无后端]' % (i, len(items), name))
                continue
            ok += 1
            try:
                snd.volume = max(0.0, min(1.0, args.vol))
                snd.play()
            except Exception as e:
                print('%3d/%3d  %-24s  [播放异常: %s]' % (i, len(items), name, e))
                continue
            ln = getattr(snd, 'length', 0) or 0
            print('%3d/%3d  %-24s  %.2fs' % (i, len(items), name, ln))
            # 播放时长与间隔取较大者，避免长音被截断
            time.sleep(max(args.gap, min(ln, 5.0) + 0.15))
            try:
                snd.stop()
            except Exception:
                pass
    except KeyboardInterrupt:
        print('\n已中断。')
    print('=' * 62)
    print('完成：成功 %d / 失败 %d / 共 %d' % (ok, miss, len(items)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
