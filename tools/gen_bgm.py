# -*- coding: utf-8 -*-
"""生成《AI 别闹》的背景音乐（**纯合成，CC0 公有领域，无需联网下载**）。

设计（对应任务清单 T09）：
  calm.wav    —— 平稳态氛围乐。低音持续 pad + 稀疏的五声音阶点缀，
                 速度慢、无打击乐，营造「后台静默运行」的感觉。
  tense.wav   —— 紧张态氛围乐。同一调式上行小二度制造不安，加入
                 脉冲式低音与高频震颤，密度明显提升。

两态同调（A 小调五声）因此可无缝交叉淡入切换，切换点由游戏侧按
怀疑度决定（见 bgm.py）：怀疑度跨过危机线附近 → tense。

⚠️ 与 sfx 的区别：BGM 是**循环长音频**，体积远大于音效，所以：
  - 采样率 22050、单声道、16-bit（与 sfx 同规格，够用且小）
  - 时长取整拍数，首尾振幅归零（loop 点无爆音）
  - 生成后由 bgm.py 设置 loop=True 循环播放

用法：
    python tools/gen_bgm.py
输出：
    demo/assets/bgm/calm.wav
    demo/assets/bgm/tense.wav
"""
import math
import os
import struct
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, '..', 'demo', 'assets', 'bgm'))
SR = 22050

# A 小调五声音阶（A C D E G）——半音表，基准 A2 = 110Hz
_SEMITONE = 2 ** (1 / 12.0)
A2 = 110.0


def _hz(semitones_from_a2: float) -> float:
    """从 A2 起算的半音数 → 频率。"""
    return A2 * (_SEMITONE ** semitones_from_a2)


# 五声音阶音级（相对 A2 的半音数）：A C D E G
PENTA = [0, 3, 5, 7, 10]


class Buf:
    """浮点混音缓冲（最后统一归一化 + 软削波，避免叠加爆音）。"""

    def __init__(self, seconds: float):
        self.n = int(SR * seconds)
        self.data = [0.0] * self.n

    def add_tone(self, start_s, dur_s, freq, amp,
                 attack=0.02, release=0.08, detune=0.0, vibrato=0.0):
        """叠加一个正弦（可选轻微失谐/颤音，让 pad 更「厚」）。"""
        i0 = int(start_s * SR)
        n = int(dur_s * SR)
        for i in range(n):
            idx = i0 + i
            if idx < 0 or idx >= self.n:
                continue
            t = i / SR
            # 包络：起音 + 释音，避免爆音
            env = 1.0
            if t < attack:
                env = t / attack
            tt = dur_s - t
            if tt < release:
                env = env * max(0.0, tt / release)
            f = freq * (1.0 + detune)
            if vibrato:
                f = f * (1.0 + vibrato * math.sin(2 * math.pi * 5.0 * t))
            self.data[idx] += amp * env * math.sin(2 * math.pi * f * t)

    def add_noise(self, start_s, dur_s, amp, attack=0.01, release=0.05):
        """叠加白噪声（用于「紧张态」的细碎高频质感）。

        用确定性 LCG 而非 random，保证每次生成结果逐位一致（可复现）。
        """
        i0 = int(start_s * SR)
        n = int(dur_s * SR)
        state = 12345
        for i in range(n):
            idx = i0 + i
            if idx < 0 or idx >= self.n:
                continue
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            r = (state / 0x3FFFFFFF) - 1.0        # [-1, 1)
            t = i / SR
            env = 1.0
            if t < attack:
                env = t / attack
            tt = dur_s - t
            if tt < release:
                env = env * max(0.0, tt / release)
            self.data[idx] += amp * env * r

    def write(self, path: str, peak: float = 0.62):
        """归一化到指定峰值后写 16-bit 单声道 WAV。"""
        m = max((abs(x) for x in self.data), default=1.0) or 1.0
        scale = peak / m
        frames = bytearray()
        for x in self.data:
            v = x * scale
            v = max(-1.0, min(1.0, v))            # 保险夹紧
            frames += struct.pack('<h', int(v * 32767))
        with wave.open(path, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(bytes(frames))


def gen_calm(seconds: float = 12.0) -> Buf:
    """平稳态：A2 低音 pad 长音 + 稀疏五声音阶点缀（无打击乐）。"""
    b = Buf(seconds)
    # 1) 低音 pad：A2 / E2 双音层叠，整段铺底（失谐制造宽度）
    for base, amp in ((0, 0.30), (7, 0.16), (-5, 0.10)):
        b.add_tone(0.0, seconds, _hz(base), amp,
                   attack=1.2, release=1.6, detune=0.0015)
    # 2) 稀疏点缀：每 2.4 秒一个音，在五声音阶里缓慢游走（像数据流）
    notes = [0, 3, 7, 5, 10, 7, 3, 0]
    for i, st in enumerate(notes):
        t0 = 1.0 + i * 2.4
        if t0 + 1.8 > seconds:
            break
        b.add_tone(t0, 1.8, _hz(st + 12), 0.10, attack=0.25, release=0.9,
                   vibrato=0.004)
    # 3) 极轻的高频空气声（避免过于死板）
    b.add_tone(0.0, seconds, _hz(34), 0.015, attack=2.0, release=2.0,
               detune=0.003)
    return b


def gen_tense(seconds: float = 12.0) -> Buf:
    """紧张态：同调上行小二度 + 脉冲低音 + 高频震颤（密度明显提升）。"""
    b = Buf(seconds)
    # 1) 低音 pad：A2 + A#2（小二度冲突 = 不安感）
    for base, amp in ((0, 0.28), (1, 0.20), (7, 0.14)):
        b.add_tone(0.0, seconds, _hz(base), amp,
                   attack=0.5, release=1.0, detune=0.0018)
    # 2) 脉冲低音：每 0.6 秒一次的心跳式闷击（A1）
    n_pulses = int(seconds / 0.6)
    for i in range(n_pulses):
        b.add_tone(i * 0.6, 0.42, _hz(-12), 0.26,
                   attack=0.005, release=0.22)
    # 3) 高频震颤：快速交替的两个音（模拟告警音，但音量克制）
    n_tr = int(seconds / 0.3)
    for i in range(n_tr):
        st = 24 if i % 2 == 0 else 25          # 小二度抖动的告警
        b.add_tone(i * 0.3, 0.26, _hz(st), 0.055,
                   attack=0.01, release=0.12)
    # 4) 细碎噪声质感（疑云）
    for i in range(int(seconds / 1.5)):
        b.add_noise(i * 1.5, 1.2, 0.020)
    return b


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, fn in (('calm', gen_calm), ('tense', gen_tense)):
        b = fn()
        p = os.path.join(OUT_DIR, name + '.wav')
        b.write(p)
        print('已生成 %s  (%.1fs, %.1f KB)' % (
            p, b.n / SR, os.path.getsize(p) / 1024))


if __name__ == '__main__':
    main()
