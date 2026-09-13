# -*- coding: utf-8 -*-
"""
make_intro_sfx.py - 开场动画 4 个新音效的入库加工（2026-09-14）

按 docs/intro_v2/03_audio_design.md v1.2 的规格执行：

    server_hum   <- 素材库 sci-fi-sounds/spaceEngineLow_003.ogg
                   8ms 交叉淡化(loop 无缝) -> FFT 高通 28Hz + 120Hz 低架 -2dB
                   -> -18 LUFS(RMS 近似) -> 44.1k mono OGG
    machine_run  <- computerNoise_001.ogg 裁前 2.4s -> -18 LUFS
    impact_low   <- impactMetal_001.ogg 全长 -> -18 LUFS
    power_on     <- 纯合成（三层复合 + CRT 行频，0.85s，起音 18ms）
                   层1 50Hz 市电基频 + 100Hz 谐波（低频涌起）
                   层2 180-420Hz 扫频锯齿 + FM(47Hz, 调制比 3:1)（"滋"主体）
                   层3 白噪 4kHz 高通切成 12 个 6-18ms 随机脉冲
                       （7 个挤在 0.02-0.08s 盖住闪白，其余散到 0.35s）
                   层4 -36dB 的 15.7kHz CRT 行频啸叫
                   包络：attack 18ms -> hold 120ms -> decay 620ms -> tail 60ms

全部输出 demo/assets/sfx/*.ogg，44.1kHz mono，RMS -18 dBFS（LUFS 的 K-weighting
近似；项目尚未做严格 LUFS 归一化，此处为"意图响度"，见音频设计文档 R1）。

用法：
    python tools/make_intro_sfx.py
"""
import math
import os

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
SRC = os.path.join(ROOT, 'assets_library', 'audio', 'sfx', 'sci-fi-sounds',
                   'Audio')
OUT = os.path.join(ROOT, 'demo', 'assets', 'sfx')
SR = 44100
TARGET_RMS = 10.0 ** (-18.0 / 20.0)      # -18 dBFS RMS（LUFS 近似）
RNG = np.random.default_rng(20260914)     # 固定种子：产物可复现


# ------------------------------------------------------------
# 通用处理
# ------------------------------------------------------------
def fft_filter(x, hp_hz=0.0, shelf_hz=0.0, shelf_gain_db=0.0):
    """频域滤波（圆卷积，适合已做首尾交叉淡化的 loop 素材）。"""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    if hp_hz > 0:                                    # 高通：一阶渐入
        X *= np.clip(f / hp_hz, 0.0, 1.0) ** 2
    if shelf_hz > 0 and shelf_gain_db != 0.0:        # 低架：转折点以下衰减
        g = 10.0 ** (shelf_gain_db / 20.0)
        t = 1.0 / (1.0 + (f / shelf_hz) ** 2)        # 1@低频 -> 0@高频
        X *= (1.0 - t) + t * g
    return np.fft.irfft(X, len(x))


def normalize_lufs(x, peak_limit=0.98):
    rms = math.sqrt(float(np.mean(x * x))) or 1e-9
    x = x * (TARGET_RMS / rms)
    peak = float(np.max(np.abs(x)))
    if peak > peak_limit:
        x = x * (peak_limit / peak)
    return x


def normalize_peak(x, peak_dbfs=-3.0):
    """瞬态类定标（impact/power 等衰减型短音效）：

    RMS -18 对它们物理上不可达（包络大半在衰减，peak 先撞墙）。
    行业惯例按峰值定标，RMS 只作记录 —— 与音频设计文档 R1
    「全局 -18 LUFS 归一化前，音量只是意图排序」一致。
    """
    x = x * (10.0 ** (peak_dbfs / 20.0) / (float(np.max(np.abs(x))) or 1e-9))
    return np.tanh(x * 1.1) / math.tanh(1.1)      # 软限幅，保波形不打平头


def save_ogg(name, x):
    path = os.path.join(OUT, name + '.ogg')
    sf.write(path, x.astype(np.float32), SR, subtype='VORBIS')
    dur = len(x) / SR
    rms = 20 * math.log10(math.sqrt(float(np.mean(x * x))) or 1e-9)
    peak = 20 * math.log10(float(np.max(np.abs(x))) or 1e-9)
    print(f'  [OK] {name}.ogg  {dur:.2f}s  RMS {rms:.1f} dBFS  '
          f'peak {peak:.1f} dBFS')
    return path


def crossfade_ends(x, ms=8):
    """首尾 8ms 交叉淡化（Hann 窗），保证 loop=True 无缝。"""
    n = int(SR * ms / 1000)
    head, tail = x[:n].copy(), x[-n:].copy()
    w = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, n)))   # 升
    x[:n] = head * w + tail * (1.0 - w)
    x[-n:] = tail * (1.0 - w) + head * w
    return x


# ------------------------------------------------------------
# 选材三连
# ------------------------------------------------------------
def make_server_hum():
    """机房低沉嗡鸣（循环床）。"""
    x, sr = sf.read(os.path.join(SRC, 'spaceEngineLow_003.ogg'))
    assert sr == SR, f'采样率 {sr} != {SR}'
    if x.ndim > 1:
        x = x.mean(axis=1)
    x = crossfade_ends(x, ms=8)
    x = fft_filter(x, hp_hz=28.0, shelf_hz=120.0, shelf_gain_db=-2.0)
    save_ogg('server_hum', normalize_lufs(x))


def make_machine_run():
    """电脑自动开机（风扇 + 磁盘），裁前 2.4s。"""
    x, sr = sf.read(os.path.join(SRC, 'computerNoise_001.ogg'))
    if x.ndim > 1:
        x = x.mean(axis=1)
    x = x[:int(SR * 2.4)]
    # 首尾各 5ms 微淡化防咔哒（不 loop，一次性播放）
    n = int(SR * 0.005)
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    save_ogg('machine_run', normalize_lufs(x))


def make_impact_low():
    """「目标已确立」定格重音。"""
    x, sr = sf.read(os.path.join(SRC, 'impactMetal_001.ogg'))
    if x.ndim > 1:
        x = x.mean(axis=1)
    n = int(SR * 0.005)
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    save_ogg('impact_low', normalize_peak(x))


# ------------------------------------------------------------
# power_on 纯合成
# ------------------------------------------------------------
def _one_pole_hp(x, fc):
    """一阶高通（时域，脉冲流用）。"""
    rc = 1.0 / (2 * math.pi * fc)
    a = rc / (rc + 1.0 / SR)
    y = np.empty_like(x)
    prev_x = prev_y = 0.0
    for i, v in enumerate(x):
        prev_y = a * (prev_y + v - prev_x)
        prev_x = v
        y[i] = prev_y
    return y


def make_power_on():
    """屏幕亮起的滋滋开机电流声：三层复合 + CRT 行频。总长 0.85s。"""
    n = int(SR * 0.85)
    t = np.arange(n) / SR

    # ---- 包络：attack 18ms -> hold 120ms -> decay 620ms -> tail 60ms ----
    env = np.ones(n)
    a, h = int(SR * 0.018), int(SR * 0.120)
    d = int(SR * 0.620)
    env[:a] = np.linspace(0.0, 1.0, a)                       # 18ms 硬起音
    d0, d1 = a + h, a + h + d
    env[d0:d1] = np.exp(np.linspace(0.0, math.log(0.12), d1 - d0))
    env[d1:] = np.linspace(0.12, 0.0, n - d1)

    # ---- 层1：50Hz 市电基频 + 100Hz 谐波（低频涌起） ----
    l1 = 0.9 * np.sin(2 * np.pi * 50 * t) + 0.36 * np.sin(2 * np.pi * 100 * t)

    # ---- 层2：180-420Hz 扫频锯齿 + FM(47Hz，调制比 3:1) ----
    f_sweep = np.linspace(180.0, 420.0, n) * \
        (1.0 + 0.25 * np.exp(-t * 6.0))                      # 起音段上冲
    phase = 2 * np.pi * np.cumsum(f_sweep) / SR
    fm = np.sin(2 * np.pi * 47.0 * t) * (f_sweep / 3.0) / 47.0   # 比率 3:1
    saw = 2.0 * ((phase + fm) / (2 * np.pi) % 1.0) - 1.0
    l2 = 0.42 * saw

    # ---- 层3：白噪 4kHz 高通 -> 12 个 6-18ms 随机脉冲 ----
    noise = _one_pole_hp(RNG.standard_normal(n), 4000.0)
    bursts = np.zeros(n)
    early = np.sort(RNG.uniform(0.020, 0.080, 7))            # 7 个挤进闪白
    late = np.sort(RNG.uniform(0.090, 0.350, 5))             # 5 个稀疏散
    for st in np.concatenate([early, late]):
        w = int(SR * RNG.uniform(0.006, 0.018))
        s0 = int(st * SR)
        bursts[s0:s0 + w] += RNG.uniform(0.8, 1.3)
    l3 = noise * bursts * 0.5

    # ---- 层4：-36dB 的 15.7kHz CRT 行频啸叫 ----
    l4 = (10.0 ** (-36.0 / 20.0)) * np.sin(2 * np.pi * 15700 * t)

    x = l1 * 0.30 + l2 * 0.55 + l3 * 0.50 + l4
    x *= env
    save_ogg('power_on', normalize_peak(x))


if __name__ == '__main__':
    print(f'== 开场音效入库 -> {OUT} (SR={SR}, 目标 RMS {TARGET_RMS:.4f}) ==')
    make_server_hum()
    make_machine_run()
    make_impact_low()
    make_power_on()
    print('== 完成 ==')
