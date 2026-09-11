# -*- coding: utf-8 -*-
"""
生成《AI 别闹》的 UI 音效（**纯合成，公有领域 / CC0，无需联网下载**）。

所有音效用正弦/方波 + 包络合成成 16-bit 单声道 WAV，
不依赖任何外部素材库，规避版权与下载风险。

用法：
    python tools/gen_sfx.py
输出：
    demo/assets/sfx/*.wav   （click / select / cast / success / fail /
                              crisis / end_win / end_lose）
"""
import math
import os
import struct
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, '..', 'demo', 'assets', 'sfx'))
SR = 22050  # 采样率（音效够用，文件小）


def _tone(freq, dur, amp=0.5, wave_type='sine', attack=0.004, release=0.02):
    """单音：返回 16-bit PCM 字节串（带简单 AD 包络，避免爆音）。"""
    n = int(SR * dur)
    out = bytearray()
    for i in range(n):
        t = i / SR
        env = 1.0
        if t < attack:
            env = t / attack
        if t > dur - release:
            env = max(0.0, (dur - t) / release)
        ph = 2 * math.pi * freq * t
        if wave_type == 'square':
            s = 1.0 if math.sin(ph) >= 0 else -1.0
        elif wave_type == 'tri':
            s = 2 * abs(2 * (t * freq - math.floor(t * freq + 0.5))) - 1
        else:
            s = math.sin(ph)
        v = int(max(-1.0, min(1.0, s * amp * env)) * 32767)
        out += struct.pack('<h', v)
    return bytes(out)


def _sweep(f0, f1, dur, amp=0.5, wave_type='sine'):
    """频率扫描音（下滑/上滑），用于失败 / 危机等情绪音。"""
    n = int(SR * dur)
    out = bytearray()
    for i in range(n):
        t = i / SR
        env = max(0.0, min(1.0, 1 - t / dur))  # 线性淡出
        freq = f0 + (f1 - f0) * (t / dur)
        s = math.sin(2 * math.pi * freq * t)
        v = int(max(-1.0, min(1.0, s * amp * env)) * 32767)
        out += struct.pack('<h', v)
    return bytes(out)


def _seq(notes):
    """拼接多段字节串。notes: [(bytes), ...]"""
    return b''.join(notes)


def _write(name, pcm):
    path = os.path.join(OUT_DIR, name + '.wav')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    print('  %-10s %6d B' % (name + '.wav', len(pcm)))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print('写出音效到', OUT_DIR)
    _write('click', _tone(880, 0.05, amp=0.32, wave_type='square'))
    _write('select', _tone(660, 0.07, amp=0.38, wave_type='sine'))
    _write('cast', _seq([
        _tone(520, 0.10, amp=0.40, wave_type='square'),
        _tone(780, 0.10, amp=0.36, wave_type='square'),
    ]))
    _write('success', _seq([
        _tone(523, 0.10, amp=0.42),
        _tone(784, 0.14, amp=0.42),
    ]))
    _write('fail', _sweep(320, 150, 0.28, amp=0.45, wave_type='square'))
    _write('crisis', _seq([
        _tone(150, 0.34, amp=0.50, wave_type='sine'),
        _tone(150, 0.34, amp=0.0),  # 占位保持节奏
    ]) if False else _sweep(180, 120, 0.40, amp=0.48, wave_type='sine'))
    _write('end_win', _seq([
        _tone(523, 0.12, amp=0.44),
        _tone(659, 0.12, amp=0.44),
        _tone(784, 0.12, amp=0.44),
        _tone(1047, 0.20, amp=0.46),
    ]))
    _write('end_lose', _seq([
        _tone(440, 0.18, amp=0.44),
        _tone(330, 0.18, amp=0.44),
        _tone(247, 0.18, amp=0.44),
        _tone(196, 0.30, amp=0.46),
    ]))
    print('完成')


if __name__ == '__main__':
    main()
