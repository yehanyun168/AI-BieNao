"""科技树「分支效果」文案必须走 i18n，而不是把 effect dict 的键名当文案。

背景（本次修复的根因）：
    旧 ``PagesMixin._branch_effect`` 直接遍历 ``effects_per_level[idx]`` 的
    ``.items()`` 并把**键名**拼进文案，于是中文环境下分支描述长这样：
        「本地化节点\\ntype；value ×1.10」
    —— 中文界面里出现英文代码串。效果字典的 ``type`` 值（block_resist /
    downloads_mult / …）现在统一映射到 ``tt_fx_*`` 键再查表。

本测试是三类不变量的守卫：
  1. 覆盖性：TECH_TREE 里**实际出现**的每种效果类型都必须已登记映射；
  2. 无泄漏：中文环境下任何分支描述都不得出现效果类型原文；
  3. 完整性：``tt_fx_*`` 家族中英键必须成对，且翻译值不等于键名本身。
"""

import unittest

import i18n
from tech_tree import TECH_TREE
from ui_pages import PagesMixin

# 效果 type 的实际形态（下划线英文串）。用于「不许泄漏」的检测。
_USED_TYPES = sorted({
    eff.get('type')
    for slot in TECH_TREE
    for br in slot.branches
    for eff in br.effects_per_level
    if isinstance(eff, dict) and eff.get('type')
})


class TechEffectI18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang(i18n.LANG_ZH)

    # ---------------- 1. 覆盖性 ----------------
    def test_every_used_effect_type_is_mapped(self):
        missing = [t for t in _USED_TYPES
                   if t not in PagesMixin._FX_TYPE_KEYS]
        self.assertEqual(missing, [],
                         f'未登记 i18n 映射的效果类型：{missing}（回退会丢成「效果」）')

    def test_every_mapped_key_exists_in_both_languages(self):
        for ftype, key in PagesMixin._FX_TYPE_KEYS.items():
            for lang in (i18n.LANG_ZH, i18n.LANG_EN):
                i18n.set_lang(lang)
                val = i18n.t(key)
                self.assertNotEqual(val, key,
                                    f'{key} 在 {lang} 下缺翻译（t() 回落成键名）')
                self.assertTrue(val.strip(), f'{key} 在 {lang} 下为空')

    def test_tt_fx_family_has_no_duplicate_or_language_gap(self):
        """tt_fx_* 家族在中英词典里键集必须一致（防止只补一边）。"""
        zh_keys = {k for k in i18n.TRANSLATIONS['zh'] if k.startswith('tt_fx_')}
        en_keys = {k for k in i18n.TRANSLATIONS['en'] if k.startswith('tt_fx_')}
        self.assertEqual(sorted(zh_keys), sorted(en_keys),
                         'tt_fx_* 中英键集不一致')
        self.assertTrue(zh_keys, 'tt_fx_* 家族为空')

    # ---------------- 2. 无泄漏 ----------------
    def test_chinese_branch_effect_never_leaks_raw_type(self):
        i18n.set_lang(i18n.LANG_ZH)
        leaks = []
        for slot in TECH_TREE:
            for br in slot.branches:
                for idx in range(len(br.effects_per_level)):
                    txt = PagesMixin._branch_effect(br, idx)
                    for ftype in _USED_TYPES:
                        if ftype in txt:
                            leaks.append(f'{br.branch_id}[{idx}] → {txt}')
        self.assertEqual(leaks, [], f'中文环境下泄漏英文效果类型：{leaks[:5]}')

    def test_branch_effect_translates_between_languages(self):
        """同一效果在中英下必须给出不同文案（证明确实查了表）。"""
        br = next(b for s in TECH_TREE for b in s.branches
                  if isinstance(b.effects_per_level[0], dict))
        i18n.set_lang(i18n.LANG_ZH)
        zh = PagesMixin._branch_effect(br, 0)
        i18n.set_lang(i18n.LANG_EN)
        en = PagesMixin._branch_effect(br, 0)
        self.assertNotEqual(zh, en, f'{br.branch_id} 效果文案未随语言变化')
        self.assertNotIn('_', zh, f'中文文案里不该有下划线代码串：{zh}')

    def test_effect_text_formats_number_by_type(self):
        """加法类（block_resist / stealth_ratio_bonus）用 +n%，乘数类用 ×n.nn。"""
        i18n.set_lang(i18n.LANG_ZH)
        add = PagesMixin._effect_text({'type': 'block_resist', 'value': 0.25})
        mul = PagesMixin._effect_text({'type': 'downloads_mult', 'value': 1.1})
        self.assertIn('+25%', add)
        self.assertIn('×1.10', mul)
        unknown = PagesMixin._effect_text({'type': 'not_a_type', 'value': 2})
        self.assertNotIn('not_a_type', unknown)

    def test_effect_text_appends_scope_only_when_not_unlocked(self):
        i18n.set_lang(i18n.LANG_ZH)
        with_scope = PagesMixin._effect_text(
            {'type': 'downloads_mult', 'value': 1.1, 'scope': 'CN+IN+ID'})
        no_scope = PagesMixin._effect_text(
            {'type': 'downloads_mult', 'value': 1.1, 'scope': 'unlocked'})
        self.assertIn('CN+IN+ID', with_scope)
        self.assertNotIn('unlocked', no_scope)

    def test_branch_effect_out_of_range_returns_placeholder(self):
        br = TECH_TREE[0].branches[0]
        self.assertEqual(PagesMixin._branch_effect(br, 99), '--')

    # ---------------- 3. 换行 & 页面级 ----------------
    def test_branch_desc_contains_real_newline(self):
        """回归守卫：``\\n``（双反斜杠）曾把描述与「n/3 · 效果」粘成一行。"""
        import engine
        import main
        engine.init_game()
        game = main.GameUI()
        slot = TECH_TREE[0]
        br = slot.branches[0]
        desc = game._branch_desc(slot.slot_id, br.branch_id)
        self.assertIn('\n', desc)
        self.assertNotIn('\\n', desc)
        self.assertNotIn('_mult', desc)


if __name__ == '__main__':
    unittest.main()
