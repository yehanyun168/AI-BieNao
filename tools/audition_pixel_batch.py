# -*- coding: utf-8 -*-
"""pixel-ui-sfx 分组试听器 —— 一次只播一小批，播完等你看屏幕上的编号反馈

设计目标（针对"执行不了/记不住"两个问题）：
1. **不依赖命令行参数** —— 双击 bat 就能跑，环境变量已在 bat 里设好。
2. **不一次播 65 条** —— 按包内自然分组（UI 短音区 / 长音区）分批，
   每批 10 条，播完打印本批清单并**停下来等你按回车**，再继续下一批。
3. **屏幕上有编号对照** —— 你看到的是 `[12] Pixel_12  0.59s` 这样的行，
   反馈时直接说编号即可。

用法（项目根目录）：
    PY="C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe"
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_pixel_batch.py
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_pixel_batch.py 1 20
只读工具。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
LIB = os.path.join(ROOT, 'assets_library', 'audio', 'sfx',
                   'pixel-ui-sfx', '--Pixelated UI')
VOLUME = 0.55
BATCH = 10          # 每批条数


def _files():
    if not os.path.isdir(LIB):
        return []
    return sorted(os.path.join(LIB, f) for f in os.listdir(LIB)
                  if f.lower().endswith('.wav'))


def _dur(p):
    try:
        import wave
        w = wave.open(p, 'rb')
        d = w.getnframes() / w.getframerate()
        w.close()
        return d
    except Exception:
        return 0.0


def _play(name, path, idx, total, d):
    print('\n  ┌─ [%2d/%d]  %-11s  %5.2fs' % (idx, total, name, d))
    print('  └─ 正在播放 ...', end=' ', flush=True)


def main():
    files = _files()
    if not files:
        print('未找到素材目录：')
        print('  %s' % LIB)
        print('（assets_library 被 .gitignore 排除，只在本机存在）')
        return 1

    nums = [int(a) for a in sys.argv[1:] if a.lstrip('-').isdigit()]
    if len(nums) >= 2:
        lo, hi = nums[0], nums[1]
    elif len(nums) == 1:
        lo = hi = nums[0]
    else:
        lo, hi = 1, len(files)
    lo, hi = max(1, lo), min(len(files), hi)

    from kivy.core.audio import SoundLoader

    print('=' * 60)
    print('  pixel-ui-sfx 分组试听  (第 %d-%d 条 / 共 %d 条)' % (lo, hi, len(files)))
    print('  每批 %d 条，播完停下等你按回车继续' % BATCH)
    print('  想跳过整批：直接按回车；想中断：Ctrl+C' % ())
    print('=' * 60)

    idx = lo
    while idx <= hi:
        batch_end = min(idx + BATCH - 1, hi)
        print('\n' + '-' * 60)
        print(' ▸ 第 %d 批：第 %d - %d 条' % ((idx - lo) // BATCH + 1, idx, batch_end))
        print('-' * 60)
        for i in range(idx, batch_end + 1):
            path = files[i - 1]
            name = os.path.basename(path)[:-4]
            d = _dur(path)
            snd = SoundLoader.load(path)
            if snd is None:
                print('\n  ┌─ [%2d]  %-11s  加载失败' % (i, name))
                continue
            _play(name, path, i, len(files), d)
            try:
                snd.volume = VOLUME
                snd.play()
            except Exception as e:
                print('异常: %s' % e)
                continue
            time.sleep(d + 0.3)
            try:
                snd.stop()
            except Exception:
                pass
            print('ok')
        # 本批结束，列清单 + 停等
        print('\n' + '-' * 60)
        print(' 本批清单（请按编号反馈）：')
        for i in range(idx, batch_end + 1):
            print('   %2d  %-11s  %5.2fs' % (
                i, os.path.basename(files[i - 1])[:-4], _dur(files[i - 1])))
        print('-' * 60)
        if batch_end < hi:
            print(' ▸ 按回车听下一批，或 Ctrl+C 结束。')
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                print('\n已结束。')
                break
        idx = batch_end + 1

    print('\n' + '=' * 60)
    print(' 全部播放完毕。请告诉 AI：哪条编号适合什么场景。')
    print('=' * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
