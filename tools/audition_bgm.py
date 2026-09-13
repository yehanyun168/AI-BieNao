# -*- coding: utf-8 -*-
"""试听 BGM 候选（tallbeard-chiptune / hydrogene-8bit）

用法：
    PY="C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe"
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_bgm.py --list
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_bgm.py            # 依次试听精选候选
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_bgm.py --secs 20  # 每条只听 20 秒
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_bgm.py --all      # 试听全部曲目

只读工具，不修改任何文件。
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
BGM_LIB = os.path.join(ROOT, 'assets_library', 'audio', 'bgm')

# 精选候选（按游戏两态情绪需求挑的，非全部）
PICKS = {
    'tallbeard-chiptune': [
        ('Three Red Hearts Sanctuary', 'calm 候选 —— 庇护所，平稳'),
        ('Three Red Hearts Pixel War 1', 'tense 候选 —— 像素战争，紧张'),
        ('Three Red Hearts Pixel War 2', 'tense 候选 —— 像素战争变奏'),
        ('Three Red Hearts Rumble at the Gates', 'tense 候选 —— 城门前骚动，压迫感'),
        ('Three Red Hearts Candy', 'calm 候选 —— 明快'),
        ('Three Red Hearts Penguin Town', 'calm 候选 —— 轻快城镇'),
        ('Three Red Hearts Puzzle Pieces', 'calm 候选 —— 解谜感'),
        ('Three Red Hearts Modern Bits', 'calm 候选 —— 偏现代电子'),
        ('Three Red Hearts Deep Blue', 'calm 候选 —— 深海氛围'),
        ('Three Red Hearts Save the City', 'tense 候选 —— 拯救城市，推进感'),
    ],
    'hydrogene-8bit': [
        ('01. Slay The Evil', 'tense 候选 —— 讨伐邪恶'),
        ('02. Perilous Dungeon', 'tense 候选 —— 危险地牢'),
        ('03. Boss Battle', 'tense 候选 —— Boss 战'),
        ('04. Mechanical Complex', 'calm 候选 —— 机械设施'),
        ('05. Last Mission', 'tense 候选 —— 最终任务'),
        ('06. Unknown Planet', 'calm 候选 —— 未知星球'),
    ],
}
VOLUME = 0.45


def _find(pack, stem):
    d = os.path.join(BGM_LIB, pack)
    if not os.path.isdir(d):
        return None
    for ext in ('.ogg', '.mp3', '.wav'):
        p = os.path.join(d, stem + ext)
        if os.path.exists(p):
            return p
    return None


def _list_all(pack):
    d = os.path.join(BGM_LIB, pack)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.lower().endswith(('.ogg', '.mp3', '.wav')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true', help='只打印清单不出声')
    ap.add_argument('--all', action='store_true', help='试听该包全部曲目')
    ap.add_argument('--pack', default='tallbeard-chiptune',
                    help='包名：tallbeard-chiptune / hydrogene-8bit')
    ap.add_argument('--secs', type=float, default=0,
                    help='每条试听秒数（0=全曲，默认 0）；建议 15~25 试听')
    args = ap.parse_args()

    items = []      # (显示名, 路径, 备注)
    for pack, lst in PICKS.items():
        if pack != args.pack:
            continue
        if args.all:
            for p in _list_all(pack):
                items.append((os.path.basename(p), p, ''))
        else:
            for stem, note in lst:
                p = _find(pack, stem)
                if p:
                    items.append((stem, p, note))

    if not items:
        print('未找到曲目（assets_library 被 .gitignore 排除，仅本机存在）')
        print('可试听的包：%s' % ', '.join(PICKS))
        return 1

    if args.list:
        print('=' * 72)
        print('BGM 候选清单 —— %s' % args.pack)
        print('=' * 72)
        for i, (name, p, note) in enumerate(items, 1):
            print('%2d  %-42s %8.0f KB  %s'
                  % (i, name, os.path.getsize(p) / 1024, note))
        return 0

    from kivy.core.audio import SoundLoader

    print('=' * 72)
    print('试听 %d 条（音量 %.2f，%s）' % (
        len(items), VOLUME,
        ('每条 %.0fs' % args.secs) if args.secs else '全曲'))
    print('=' * 72)
    try:
        for i, (name, p, note) in enumerate(items, 1):
            snd = SoundLoader.load(p)
            if snd is None:
                print('%2d  [加载失败] %s' % (i, name))
                continue
            ln = getattr(snd, 'length', 0) or 0
            play_for = min(ln, args.secs) if args.secs else ln
            print('%2d  %-42s %6.1fs  %s' % (i, name, ln, note))
            try:
                snd.volume = VOLUME
                snd.play()
            except Exception as e:
                print('     [播放异常 %s]' % e)
                continue
            time.sleep(play_for + 0.2)
            try:
                snd.stop()
            except Exception:
                pass
    except KeyboardInterrupt:
        print('\n已中断。')
    print('=' * 72)
    print('完成。请反馈：哪首当 calm、哪首当 tense。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
