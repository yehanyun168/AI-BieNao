# -*- coding: utf-8 -*-
"""sfx_profile.py —— 候选音效声学特征分析（在"人耳试听"前先客观筛选）

为什么需要：判断"某个音效是否合适"最终靠耳朵，但**大部分不适配是能客观测出来的**——
  · 时长：点击/悬停类高频交互只能用 0.02~0.20s，长了会糊成一团；
  · 音色亮度：频谱重心（spectral centroid）过高的会刺耳，过低会沉闷；
  · 频谱平坦度（flatness）：接近 1 = 噪声型（沙沙声），接近 0 = 纯音调型；
  · 起音时间（attack）：太长会有"延迟感"，交互反馈必须 <15ms；
  · 尾部拖尾：尾音长则连续点击会叠音。
先用这些客观指标把关，只把"参数合理"的候选交给人耳，避免人工试听 200+ 个。

依赖：soundfile + numpy（仅本工具需要，游戏本体不依赖）。
    "PY" -m pip install --user soundfile

用法：
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/sfx_profile.py
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/sfx_profile.py --purpose tap
    KIVY_NO_FILELOG=1 KIVY_NO_ARGS=1 "$PY" tools/sfx_profile.py --pack ui

只读工具，不修改任何文件。
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
LIB = os.path.join(ROOT, 'assets_library', 'audio', 'sfx')

PACKS = {
    'interface': os.path.join(LIB, 'interface-sounds', 'Audio'),
    'ui':        os.path.join(LIB, 'ui-audio', 'Audio'),
    'digital':   os.path.join(LIB, 'digital-audio', 'Audio'),
    'scifi':     os.path.join(LIB, 'sci-fi-sounds', 'Audio'),
    'stock':     os.path.join(ROOT, 'demo', 'assets', 'sfx'),
}

# 用途 → (时长下限, 时长上限, 频谱重心上限Hz, 起音上限ms)
PURPOSE_SPEC = {
    'tap':  (0.02, 0.20, 6000, 15),    # 点击/悬停/开关
    'page': (0.03, 0.45, 6000, 20),    # 翻页/返回/开合
    'act':  (0.05, 0.70, 8000, 30),    # 确认/接受/提交
    'soft': (0.10, 1.20, 6000, 40),    # 滚动/列表
    'long': (0.20, 3.00, 8000, 60),    # 成就/结局/解锁
}


def _analyze(path):
    """返回声学特征 dict；解码失败返回 None。"""
    try:
        import soundfile as sf
        import numpy as np
    except ImportError:
        return {'error': 'need soundfile+numpy'}
    try:
        data, sr = sf.read(path, dtype='float32')
    except Exception as e:
        return {'error': str(e)}
    if data.size == 0:
        return {'error': 'empty'}
    # 混合到单声道
    if data.ndim > 1:
        data = data.mean(axis=1)
    dur = len(data) / float(sr)
    a = np.abs(data)
    peak = float(a.max())
    if peak <= 1e-6:
        return {'dur': dur, 'peak': 0.0, 'centroid': 0.0, 'flatness': 0.0,
                'attack_ms': 0.0, 'tail': 0.0, 'ok': True}

    # ---- 起音时间：从 0 到峰值所需毫秒 ----
    imax = int(np.argmax(a))
    attack_ms = imax / float(sr) * 1000.0

    # ---- 频谱重心 + 频谱平坦度（用整段的中段窗口，避开首尾静音）----
    n = len(data)
    seg = data[n // 4: max(n // 4 + 1, 3 * n // 4)]
    if len(seg) < 64:
        seg = data
    win = np.hanning(len(seg))
    spec = np.abs(np.fft.rfft(seg * win)) + 1e-12
    freqs = np.fft.rfftfreq(len(seg), 1.0 / sr)
    centroid = float((spec * freqs).sum() / spec.sum())
    gmean = float(np.exp(np.log(spec).mean()))
    amean = float(spec.mean())
    flatness = gmean / amean if amean > 0 else 0.0

    # ---- 尾部拖尾：最后 15% 时间内高于峰值 35% 的样本占比 ----
    tail = 0.0
    if n > 20:
        seg_t = a[int(n * 0.85):]
        tail = float((seg_t > peak * 0.35).mean())

    return {'dur': dur, 'peak': peak, 'centroid': centroid,
            'flatness': flatness, 'attack_ms': attack_ms, 'tail': tail,
            'ok': True}


def _verdict(pr, purpose):
    """按用途判定是否推荐，返回 (推荐?, 问题列表)"""
    if purpose not in PURPOSE_SPEC or not pr.get('ok'):
        return True, []
    lo, hi, cmax, amax = PURPOSE_SPEC[purpose]
    probs = []
    if pr['dur'] < lo:
        probs.append('过短')
    if pr['dur'] > hi:
        probs.append('过长')
    if pr['centroid'] > cmax:
        probs.append('偏刺耳')
    if pr['attack_ms'] > amax:
        probs.append('起音迟')
    if pr['tail'] > 0.5:
        probs.append('拖尾长')
    return (not probs), probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', default=None, help='包：%s' % '/'.join(PACKS))
    ap.add_argument('--purpose', default=None, help='用途：%s' % '/'.join(PURPOSE_SPEC))
    ap.add_argument('--max-tail', type=float, default=None,
                    help='只看拖尾低于该值的（如 0.3）')
    args = ap.parse_args()

    packs = [args.pack] if args.pack else [p for p in PACKS if p != 'stock']
    rows = []
    for pk in packs:
        d = PACKS.get(pk)
        if not d or not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(('.ogg', '.wav', '.mp3')):
                continue
            p = os.path.join(d, f)
            pr = _analyze(p)
            if not pr.get('ok'):
                continue
            ok, probs = _verdict(pr, args.purpose)
            if args.max_tail is not None and pr['tail'] > args.max_tail:
                continue
            rows.append((pk, f, pr, ok, probs))

    if not rows:
        print('没有可分析的音频（assets_library 被 .gitignore 排除，仅本机存在）')
        print('若报缺依赖： "PY" -m pip install --user soundfile')
        return 1

    if args.purpose:
        lo, hi, cmax, amax = PURPOSE_SPEC[args.purpose]
        print('=' * 96)
        print('用途：%s   合理区间 时长 %.2f-%.2f秒 / 亮度<%dHz / 起音<%dms'
              % (args.purpose, lo, hi, cmax, amax))
        print('=' * 96)
        rows = [r for r in rows if r[3]]
        print('通过客观筛选：%d 个候选（这些才值得用人耳进一步判断）\n' % len(rows))
    else:
        print('=' * 96)
        print('全部候选声学特征')
        print('=' * 96)

    print('%-10s %-20s %6s %6s %9s %8s %7s %6s  %s'
          % ('包', '文件', '时长', '峰值', '亮度Hz', '平坦度', '起音ms', '拖尾', '问题'))
    print('-' * 96)
    for pk, f, pr, ok, probs in rows:
        print('%-10s %-20s %5.2fs %6.2f %9.0f %8.2f %7.1f %5.0f%%  %s'
              % (pk, f.rsplit('.', 1)[0], pr['dur'], pr['peak'],
                 pr['centroid'], pr['flatness'], pr['attack_ms'],
                 pr['tail'] * 100, '、'.join(probs)))
    print('-' * 96)
    print('指标说明：')
    print('  亮度Hz  频谱重心。高→尖亮刺耳，低→沉闷。UI 音效一般 500-4000Hz。')
    print('  平坦度  0=纯音调(叮/嘟)，1=噪声(沙沙)。辨识度靠音调，质感靠混合。')
    print('  起音ms  从开始到峰值的时间。>30ms 会有"延迟感"，交互反馈应尽量小。')
    print('  拖尾    结尾仍有声的比例。高→连续点击会叠音糊掉。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
