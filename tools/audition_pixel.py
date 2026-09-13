# -*- coding: utf-8 -*-
"""试听 pixel-ui-sfx 全部 65 条（带编号对照表）

为什么单独写这个：pixel-ui-sfx 的 65 个文件全部是无语义编号命名
（Pixel_01 … Pixel_65），判断"哪条像什么场景"只能靠人耳。
所以这里给出 **编号 + 时长对照表**，你听完直接按编号反馈即可。

用法：
    PY="C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe"
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_pixel.py            # 全听（约 2 分钟）
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_pixel.py 1 20       # 只听 1-20 号
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_pixel.py 53 65      # 只听长音区
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_pixel.py --list     # 只打印对照表不出声

只读工具，不修改任何文件。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
LIB = os.path.join(ROOT, 'assets_library', 'audio', 'sfx',
                   'pixel-ui-sfx', '--Pixelated UI')

VOLUME = 0.45
GAP = 0.55          # 条目之间的静默间隔


def _files():
    if not os.path.isdir(LIB):
        return []
    return sorted(os.path.join(LIB, f) for f in os.listdir(LIB)
                  if f.lower().endswith('.wav'))


def _table(files):
    print('=' * 58)
    print('pixel-ui-sfx 对照表（Atelier Magicae · 65 条）')
    print('=' * 58)
    print('序号  文件         时长     大小')
    print('-' * 58)
    for i, f in enumerate(files, 1):
        try:
            import wave
            w = wave.open(f, 'rb')
            dur = w.getnframes() / w.getframerate()
            w.close()
        except Exception:
            dur = 0.0
        print('%3d   %-12s %5.2fs  %6.0f KB'
              % (i, os.path.basename(f)[:-4], dur, os.path.getsize(f) / 1024))
    print('=' * 58)


def main():
    files = _files()
    if not files:
        print('未找到素材目录：%s' % LIB)
        print('（assets_library 被 .gitignore 排除，仅本机存在）')
        return 1

    if '--list' in sys.argv:
        _table(files)
        return 0

    nums = [int(a) for a in sys.argv[1:] if a.lstrip('-').isdigit()]
    if len(nums) >= 2:
        lo, hi = nums[0], nums[1]
    elif len(nums) == 1:
        lo = hi = nums[0]
    else:
        lo, hi = 1, len(files)
    lo = max(1, lo)
    hi = min(len(files), hi)

    _table(files)

    from kivy.core.audio import SoundLoader

    print('\n开始试听 %d–%d 号（音量 %.2f，每条间隔 %.2fs）' % (lo, hi, VOLUME, GAP))
    print('按 Ctrl+C 可中断\n')
    try:
        for i in range(lo, hi + 1):
            path = files[i - 1]
            snd = SoundLoader.load(path)
            if snd is None:
                print('%3d  [加载失败]' % i)
                continue
            try:
                snd.volume = VOLUME
                snd.play()
            except Exception as e:
                print('%3d  [播放异常 %s]' % (i, e))
                continue
            ln = getattr(snd, 'length', 0) or 0
            print('%3d  %-12s %.2fs  ← 听' % (i, os.path.basename(path)[:-4], ln))
            time.sleep(ln + GAP)
            try:
                snd.stop()
            except Exception:
                pass
    except KeyboardInterrupt:
        print('\n已中断。')
    print('\n完成。请按编号反馈：哪几条适合 click / success / fail / 结局 / 氛围 loop 等。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
