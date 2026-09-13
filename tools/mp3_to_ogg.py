# -*- coding: utf-8 -*-
"""mp3_to_ogg.py —— 把 MP3 素材转成无缝循环友好的 OGG（供 BGM 使用）。

为什么需要这个脚本：
  tallbeard 包里作者附带 OGG 版，直接取即可；但 **HydroGene 包只发 MP3**，
  而作者与 tallbeard 都指出 MP3 循环会有可闻缝隙（帧对齐 + 编解码器
  前后静音）。本项目 BGM 是 loop=True 长时间循环，缝隙每轮都会暴露，
  所以必须转码成 OGG/Vorbis。

为什么不只做纯解码转码还要裁静音：
  MP3 解码后首尾常带 padding 静音（编码器为了帧对齐填的），直接转会得到
  「每轮循环前静音 20~80ms」的效果，听感是节奏被卡一下。本脚本先扫描
  首尾低于阈值的静音段并裁掉，再用短交叉淡化把首尾接上，消除咔哒。

用法：
    python tools/mp3_to_ogg.py <src.mp3> <dst.ogg> [--fade-ms 8] [--thresh-db -50]

注意：这是**构建期工具**，不是游戏运行时依赖（游戏侧只读 OGG）。
"""
import argparse
import os
import sys

import numpy as np
import soundfile as sf


def _db(x):
    return 20.0 * np.log10(max(float(x), 1e-12))


def _trim_silence(data, thresh_db):
    """裁掉首尾低于阈值的静音段；返回裁剪后的数组。

    data: (n, ch) float 数组。
    """
    if data.size == 0:
        return data
    # 用逐样本峰值（各声道取最大）判断是否有声
    mono = np.max(np.abs(data), axis=1)
    thr = 10.0 ** (thresh_db / 20.0)
    voiced = np.where(mono > thr)[0]
    if voiced.size == 0:
        return data                      # 全静音，原样返回（不制造空数组）
    lo, hi = int(voiced[0]), int(voiced[-1]) + 1
    return data[lo:hi]


def _crossfade_loop(data, sr, fade_ms):
    """把尾部 fade 段与首部 fade 段交叉淡化，使首尾相接处连续。

    返回**已经接好**的数组（长度 = 原长 - fade 长度），循环时首尾样本值
    与斜率都接近，消掉不连续导致的咔哒。
    """
    n = int(sr * fade_ms / 1000.0)
    if n <= 0 or data.shape[0] <= 2 * n:
        return data
    head = data[:n].copy()
    tail = data[-n:].copy()
    body = data[n:-n].copy()
    # 等功率交叉淡化系数（sin/cos 保证能量不塌陷）
    t = np.linspace(0.0, np.pi / 2.0, n, dtype=np.float32)[:, None]
    fade = tail * np.cos(t) ** 2 + head * np.sin(t) ** 2
    return np.concatenate([fade, body], axis=0)


def write_ogg(path, data, sr, chunk_frames=200000):
    """分块写 OGG/Vorbis。

    ⚠️ 为什么必须分块（2026-09-13 实测踩坑）：
    `soundfile.write()` 一次性写大数组时，libsndfile 的 Vorbis 编码路径会在
    约 40 万~80 万帧之间触发 **C 层 stack overflow**（Windows 上直接
    进程死亡，退出码 127，Python 层捕获不到任何异常，`try/except` 完全失效）。
    30 秒的 44.1kHz 立体声就是 130 万帧，必然踩中。
    实测 40 万帧（9 秒）正常、80 万帧崩溃，故每块取 20 万帧留足余量。
    """
    data = np.ascontiguousarray(data, dtype='float32')
    n = data.shape[0]
    with sf.SoundFile(path, 'w', samplerate=sr, channels=data.shape[1],
                      format='OGG', subtype='VORBIS') as f:
        for i in range(0, n, chunk_frames):
            f.write(data[i:i + chunk_frames])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--fade-ms', type=float, default=10.0,
                    help='首尾交叉淡化时长（毫秒），0 = 不做（默认 10）')
    ap.add_argument('--thresh-db', type=float, default=-50.0,
                    help='静音判定阈值（dBFS，默认 -50）')
    ap.add_argument('--no-trim', action='store_true', help='跳过裁静音')
    args = ap.parse_args()

    data, sr = sf.read(args.src, always_2d=True, dtype='float32')
    n0 = data.shape[0]
    if not args.no_trim:
        data = _trim_silence(data, args.thresh_db)
    n1 = data.shape[0]
    if args.fade_ms > 0:
        data = _crossfade_loop(data, sr, args.fade_ms)
    n2 = data.shape[0]

    os.makedirs(os.path.dirname(os.path.abspath(args.dst)) or '.', exist_ok=True)
    write_ogg(args.dst, data, sr)

    peak = float(np.max(np.abs(data))) if data.size else 0.0
    print('[mp3_to_ogg] %s' % os.path.basename(args.src))
    print('  源: %d 样本 / %dHz / %dch (%.1fs)' % (n0, sr, data.shape[1], n0 / sr))
    print('  裁静音: %d -> %d 样本 (裁掉首尾 %d)' % (n0, n1, n0 - n1))
    print('  交叉淡化: %d -> %d 样本 (%.0fms)' % (n1, n2, args.fade_ms))
    print('  峰值 %.2f dBFS / 输出 %.1fs / %.0f KB'
          % (_db(peak), n2 / sr, os.path.getsize(args.dst) / 1024.0))


if __name__ == '__main__':
    sys.exit(main())
