# -*- coding: utf-8 -*-
"""逐条试听 pixel-ui-sfx —— 专为"人耳判定 + 立即反馈"设计

与 audition_pixel.py 的区别：本脚本**每播一条就停下等待**，
可以按回车继续、输入编号记备注、输入 q 退出。
这样你不会听完 65 条却忘了前 10 条是什么感觉。

交互命令（每条播放后）：
    回车     → 听下一条
    r        → 重听这一条
    <任意文字> → 给这一条记备注（会打印在末尾汇总里）
    q        → 提前结束并打印汇总

用法（在项目根目录）：
    PY="C:/Users/tianm/AppData/Local/Programs/Python/Python312/python.exe"
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_pixel_step.py          # 1-30
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/audition_pixel_step.py 31 65    # 31-65

只读工具，不修改任何文件。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
LIB = os.path.join(ROOT, 'assets_library', 'audio', 'sfx',
                   'pixel-ui-sfx', '--Pixelated UI')
VOLUME = 0.55
NOTES_FILE = os.path.join(ROOT, 'tools', '_sfx_notes.txt')


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


def main():
    files = _files()
    if not files:
        print('未找到素材目录：%s' % LIB)
        print('（assets_library 被 .gitignore 排除，仅本机存在）')
        return 1

    nums = [int(a) for a in sys.argv[1:] if a.lstrip('-').isdigit()]
    if len(nums) >= 2:
        lo, hi = nums[0], nums[1]
    elif len(nums) == 1:
        lo = hi = nums[0]
    else:
        lo, hi = 1, min(30, len(files))
    lo = max(1, lo)
    hi = min(len(files), hi)

    from kivy.core.audio import SoundLoader

    print('=' * 66)
    print(' 逐条试听 pixel-ui-sfx  第 %d-%d 条（共 %d 条）' % (lo, hi, len(files)))
    print('=' * 66)
    print(' 命令：回车=下一条   r=重听   任意文字=记备注   q=结束')
    print('=' * 66)

    notes = {}
    i = lo
    while i <= hi:
        path = files[i - 1]
        snd = SoundLoader.load(path)
        name = os.path.basename(path)[:-4]
        d = _dur(path)
        if snd is None:
            print('\n[%3d] %s  加载失败，跳过' % (i, name))
            i += 1
            continue
        print('\n[%3d/%d]  %-12s  %5.2fs   %s   播放中...'
              % (i, hi, name, d, ('%.0f KB' % (os.path.getsize(path) / 1024))))
        try:
            snd.volume = VOLUME
            snd.play()
        except Exception as e:
            print('         播放异常: %s' % e)
            i += 1
            continue
        time.sleep(d + 0.25)
        try:
            snd.stop()
        except Exception:
            pass
        print('         → 听后请回复：回车 / r / 备注 / q', end=' ')
        try:
            ans = input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if ans.lower() == 'q':
            break
        if ans.lower() == 'r':
            continue                      # 重听同一条（不 i+=1）
        if ans:
            notes[i] = ans
            print('         已记：%s' % ans)
        i += 1

    print('\n' + '=' * 66)
    if notes:
        print(' 备注汇总')
        print('=' * 66)
        for k in sorted(notes):
            print('  [%3d] %-12s → %s'
                  % (k, os.path.basename(files[k - 1])[:-4], notes[k]))
        try:
            with open(NOTES_FILE, 'w', encoding='utf-8') as fh:
                for k in sorted(notes):
                    fh.write('%d\t%s\t%s\n'
                             % (k, os.path.basename(files[k - 1])[:-4], notes[k]))
            print('\n 备注已存：%s' % NOTES_FILE)
        except Exception as e:
            print('\n (备注写盘失败: %s)' % e)
    else:
        print(' 本次没有记录备注。')
    print('=' * 66)
    return 0


if __name__ == '__main__':
    sys.exit(main())
