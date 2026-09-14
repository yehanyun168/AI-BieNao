"""技能文案 i18n 守卫（sk_full_* / sk_detail_*）

背景：真人试玩反馈「技能介绍不全面」。设计口在
``docs/技能文案与悬停浮窗规格_0914.md`` 交付了 10 技能的完整介绍（交付物 A/B），
工程口接进 ``demo/i18n.py``。本文件单开（不改 test_build.py）钉死四条契约：

  1) ``sk_full_<sid>`` 与 ``sk_detail_<sid>`` 对全部 10 技能，在 zh / en **两段都存在**；
  2) zh / en 两段 **键集完全一致**（无单向缺项）；
  3) ``sk_full_*`` 文本里出现与 ``data.py`` ``SKILLS`` **一致的数值**（存在性即可，
     不做格式强校验）——数值行的单一来源仍是 ``data.py``（卡片现算），
     这里只保证展示文案不与之漂移；
  4) 无缺字形符号（MicrosoftYaHei 缺字形会渲染成豆腐块），且未引入新符号。

附带：``sk_detail_*`` 必须是**单行**且长度受控（文档 B3：zh ≤18 字 / en ≤60 字符），
否则在 FS_CAP 下会与代码现算的数值行挤成 3 行被裁掉。

运行：``python test_i18n_skills.py``（带 KIVY_NO_FILELOG=1 更稳）
"""
import os
os.environ.setdefault('KIVY_NO_FILELOG', '1')

import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import i18n     # noqa: E402
import data     # noqa: E402

SKILL_IDS = ["push_song", "algo_top", "stealth", "hit_maker", "bypass",
             "take_cut", "anon_cdn", "bot_farm", "open_bait", "arbitrage"]
LANGS = (i18n.LANG_ZH, i18n.LANG_EN)

# ---- 缺字形黑名单（单一来源 ui_v4.py 的 _GLYPH_NOTDEF；此处镜像一份避免
#      import ui_v4 触发 Kivy 窗口初始化）----
GLYPH_NOTDEF = {'▶', '⏸', '▦', '⌗', '✖', '✕', '✓', '✗', '⊞', '⊟', '☰', '⌂', '⌘'}
# 新词条允许的非 ASCII 符号（与设计文档 §0.3 一致；其余非 ASCII 仅限汉字/全角标点）
SAFE_SYMBOLS = set('×÷≥≤+−·—…→←↑↓')

print(" 技能文案 i18n 守卫（sk_full_* / sk_detail_*）")


def _symbols_of(text):
    """取文本里出现的一切符号类字符（排除 ASCII / 汉字 / 全角标点）。"""
    out = set()
    for c in text:
        o = ord(c)
        if c.isascii():
            continue
        if 0x4e00 <= o <= 0x9fff:          # CJK 统一表意
            continue
        if 0x3000 <= o <= 0x303f:          # CJK 标点（：；、…等）
            continue
        if 0xff00 <= o <= 0xffef:          # 全角形式（（）：；等）
            continue
        out.add(c)
    return out


# ---- 1) 全部 10 技能 × 2 键 × 2 语存在 ----
_missing = []
for _lang in LANGS:
    _tbl = i18n.TRANSLATIONS[_lang]
    for _sid in SKILL_IDS:
        for _kind in ('sk_full_', 'sk_detail_'):
            _k = f'{_kind}{_sid}'
            if _k not in _tbl:
                _missing.append(f'{_lang}:{_k}')
assert not _missing, f"缺技能文案键: {_missing}"
print(f"   ■ 1) 存在性：sk_full_/sk_detail_ × {len(SKILL_IDS)} 技能 × 2 语 "
      f"= {len(SKILL_IDS) * 2 * 2} 键 全在")

# ---- 2) zh / en 键集完全一致（无单向缺项）----
_zh = set(i18n.TRANSLATIONS[i18n.LANG_ZH])
_en = set(i18n.TRANSLATIONS[i18n.LANG_EN])
assert _zh == _en, (f"zh/en 键集不一致 —— "
                    f"仅 zh: {sorted(_zh - _en)}；仅 en: {sorted(_en - _zh)}")
_sk_keys = {f'{k}_{s}' for k in ('sk_full', 'sk_detail') for s in SKILL_IDS}
assert _sk_keys <= _zh, f"技能键未齐: {sorted(_sk_keys - _zh)}"
print(f"   ■ 2) 对称性：zh/en 键集完全一致（各 {len(_zh)} 键，技能键 "
      f"{len(_sk_keys)} 个双方齐备）")


# ---- 3) sk_full_* 数值与 data.py 一致（存在性）----
def _mult_forms(v):
    return {f'{v:.2f}', f'{v:.1f}', f'{v:g}'}


def _num_forms(v):
    v = float(v)
    return {f'{int(v)}'} if v.is_integer() else {f'{v:g}'}


_checks = []            # (sid, prefix, forms)
for _sid, _sk in data.SKILLS.items():
    if _sid not in SKILL_IDS:
        continue
    for _attr in ('downloads_mult', 'compute_mult',
                  'suspicion_mult', 'stealth_ratio_mult'):
        _v = float(getattr(_sk, _attr))
        if abs(_v - 1.0) > 1e-9:
            _checks.append((_sid, '×', _mult_forms(_v)))
    for _attr in ('suspicion_delta', 'compute_delta'):
        _v = float(getattr(_sk, _attr))
        if _v > 0:
            _checks.append((_sid, '+', _num_forms(_v)))
    _b = float(getattr(_sk, 'stealth_ratio_bonus'))
    if _b > 0:                                   # 绝对值加成，UI 口径为 %
        _checks.append((_sid, '+', {f'{_b * 100:g}'}))

_bad = []
for _lang in LANGS:
    for _sid, _pre, _forms in _checks:
        _txt = i18n.TRANSLATIONS[_lang][f'sk_full_{_sid}']
        if not any(f'{_pre}{_f}' in _txt for _f in _forms):
            _bad.append(f'{_lang}:{_sid} 缺 {_pre}{sorted(_forms)}')
assert not _bad, f"sk_full_* 数值与 data.py 不一致: {_bad}"
print(f"   ■ 3) 数值一致性：{len(_checks)} 项 ×{len(LANGS)} 语 均可在 sk_full_* 中查到"
      f"（tok 例：push_song 倍率 ×1.10、arbitrage ×1.60）")

# ---- 4a) sk_detail_* 单行 + 长度受控（防裁切）----
_len_bad = []
for _lang in LANGS:
    _cap = 18 if _lang == i18n.LANG_ZH else 60
    for _sid in SKILL_IDS:
        _txt = i18n.TRANSLATIONS[_lang][f'sk_detail_{_sid}']
        if '\n' in _txt:
            _len_bad.append(f'{_lang}:{_sid} 含换行（应单行）')
        elif len(_txt) > _cap:
            _len_bad.append(f'{_lang}:{_sid} 长度 {len(_txt)} > {_cap}')
assert not _len_bad, f"sk_detail_* 应为单行且不超长: {_len_bad}"
print("   ■ 4) sk_detail_* 全为单行且未超长（zh ≤18 字 / en ≤60 字符）")

# ---- 4b) 缺字形 + 新符号 ----
_glyph_bad = []
for _lang in LANGS:
    for _kind in ('sk_full_', 'sk_detail_'):
        for _sid in SKILL_IDS:
            _txt = i18n.TRANSLATIONS[_lang][f'{_kind}{_sid}']
            _hit = _symbols_of(_txt)
            _nd = _hit & GLYPH_NOTDEF
            if _nd:
                _glyph_bad.append(f'{_lang}:{_kind}{_sid} 缺字形 {sorted(_nd)}')
            _new = _hit - SAFE_SYMBOLS
            if _new:
                _glyph_bad.append(f'{_lang}:{_kind}{_sid} 引入新符号 {sorted(_new)}')
assert not _glyph_bad, f"技能文案符号问题: {_glyph_bad}"
print("   ■ 5) 符号：无缺字形符号，且未引入既有符号集之外的新符号")

print("\n 全部通过 - 技能完整介绍 i18n 契约成立"
      "（存在 / 对称 / 数值一致 / 单行受控 / 无缺字形）")
