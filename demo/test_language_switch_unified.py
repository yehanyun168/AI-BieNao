"""所有语言入口应共享状态，并完整刷新当前页面。"""

import unittest
from types import SimpleNamespace

import engine
import i18n
import main
import ui_v4_screens as screens


class UnifiedLanguageSwitchTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang(i18n.LANG_ZH)

    def test_settings_switch_reflects_current_language(self):
        i18n.set_lang(i18n.LANG_EN)
        page = screens.SettingsPage()
        self.assertEqual(page.lbl_lang_val.current, 1)

    def test_game_settings_switch_rebuilds_open_page(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.open_page('settings')

        game._page.lbl_lang_val.set_current(1, notify=True)

        self.assertEqual(i18n.get_lang(), i18n.LANG_EN)
        self.assertIsInstance(game._page, screens.SettingsPage)
        self.assertEqual(game._page.lbl_lang_val.current, 1)
        self.assertEqual(game._page.lbl_title.text, i18n.t('set_page_title'))

    def test_game_top_switch_rebuilds_open_help_page(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.open_page('help')

        game.toggle_lang()

        self.assertIsInstance(game._page, screens.HelpPage)
        self.assertEqual(game._page.lbl_title.text, i18n.t('help_page_title'))

    def test_clicking_game_language_chip_uses_unified_switch(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        touch = SimpleNamespace(pos=game.lang_switch.center)

        handled = game.lang_switch.on_touch_down(touch)

        self.assertTrue(handled)
        self.assertEqual(i18n.get_lang(), i18n.LANG_EN)
        self.assertIn(i18n.t('stats_compute'), game.stats_compute.text)
        self.assertEqual(game.lbl_tick_cap.text, i18n.t('stats_tick'))

    def test_game_language_switch_translates_command_rail(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()

        game.toggle_lang()

        for key in ('drop', 'tech', 'skills', 'log', 'ach'):
            self.assertEqual(game.rail.buttons[key]._caption, i18n.t(f'rail_{key}'))

    def test_menu_settings_switch_keeps_translated_settings_open(self):
        i18n.set_lang(i18n.LANG_ZH)
        menu = main.MainMenu()
        menu._open_settings()

        menu._overlay.lbl_lang_val.set_current(1, notify=True)

        self.assertEqual(i18n.get_lang(), i18n.LANG_EN)
        self.assertIsInstance(menu._overlay, screens.SettingsPage)
        self.assertEqual(menu._overlay.lbl_lang_val.current, 1)
        self.assertEqual(menu._overlay.lbl_title.text, i18n.t('set_page_title'))

    # ------------------------------------------------------------------
    # 常驻浮层（检视卡 / 日志抽屉 / 投放预览）
    #
    # 这三块「首次打开才建、关闭才销毁」，挂在 map_stage 上、不在页面栈里。
    # 语言切换走 _rebuild_lang()（只重建带页码的页面），以前碰不到它们 →
    # 中英切换后左列仍是旧语种（实测 EN 下显示「政府状态」「邻国」）。
    # ------------------------------------------------------------------
    def test_inspector_static_labels_follow_language_switch(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.on_map_country_click('CN')
        insp = game._inspector
        self.assertIsNotNone(insp)
        zh = (insp.lbl_hd.text, insp.lbl_sec_infection.text,
              insp.lbl_sec_downloads.text, insp.btn_focus.text,
              insp.btn_drop.text)
        self.assertEqual(zh[0], i18n.t('insp_title'))

        game.toggle_lang()

        self.assertIs(game._inspector, insp, '浮层应跨语言重建存活（不重挂）')
        self.assertIn(insp, game.map_stage.children, '浮层应仍挂在 map_stage 上')
        en = (insp.lbl_hd.text, insp.lbl_sec_infection.text,
              insp.lbl_sec_downloads.text, insp.btn_focus.text,
              insp.btn_drop.text)
        self.assertEqual(en[0], i18n.t('insp_title'))
        self.assertEqual(en[1], i18n.t('insp_infection'))
        self.assertEqual(en[2], i18n.t('insp_downloads'))
        self.assertEqual(en[3], i18n.t('insp_focus'))
        self.assertEqual(en[4], i18n.t('insp_drop'))
        for a, b in zip(zh, en):
            self.assertNotEqual(a, b, '切换语言后文案必须真的变了')

    def test_inspector_kv_grid_left_column_follows_language_switch(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.on_map_country_click('CN')
        kv = game._inspector.kv
        keys = ['gov_status', 'doubt_thr', 'block_budget', 'neighbors']
        self.assertEqual(kv._labels['gov_status'].text, i18n.t('gov_status'))
        zh = {k: kv._labels[k].text for k in keys}

        game.toggle_lang()

        for k in keys:
            self.assertEqual(kv._labels[k].text, i18n.t(k))
            self.assertNotEqual(zh[k], kv._labels[k].text)

    def test_log_drawer_follows_language_switch(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.toggle_log()
        drawer = game._log_drawer
        self.assertIsNotNone(drawer)
        zh_note = drawer.lbl_note.text

        game.toggle_lang()

        self.assertIs(game._log_drawer, drawer)
        self.assertEqual(drawer.lbl_hd.text, i18n.t('log_title'))
        self.assertEqual(drawer.lbl_note.text, i18n.t('log_limit'))
        self.assertEqual(drawer.btn_export.text, i18n.t('log_export'))
        self.assertEqual(drawer.btn_read_all.text, i18n.t('log_read_all'))
        self.assertNotEqual(zh_note, drawer.lbl_note.text)

    def test_drop_preview_follows_language_switch(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.start_drop('push_song', ['CN'])
        game._show_drop_preview()
        pv = game._drop_preview
        zh_est = pv.lbl_est_hd.text

        game.toggle_lang()

        self.assertIs(game._drop_preview, pv)
        self.assertEqual(pv.lbl_est_hd.text, i18n.t('drop_est'))
        self.assertEqual(pv.btn_cancel.text, i18n.t('drop_cancel'))
        self.assertEqual(pv.btn_ok.text, i18n.t('drop_confirm'))
        for k in ('targets', 'cost', 'remain'):
            self.assertEqual(pv.kv._labels[k].text, i18n.t(k))
        self.assertNotEqual(zh_est, pv.lbl_est_hd.text)

    def test_panels_do_not_truncate_text_in_either_language(self):
        """中英两种语言下，自适应高度的标签都必须装得下自己的文本。

        这是「切换语言时文字不被截断」的直接守卫：拿 text_size=(w, None)
        量真实排版高度，再断言控件现有高度不小于它。高度被写死的老 bug
        就是在这里被抓住的（英文比中文长 30~70%，固定高必然裁字）。
        """
        import ui_v4_panels as panels
        for lang in (i18n.LANG_ZH, i18n.LANG_EN):
            i18n.set_lang(lang)
            engine.init_game()
            game = main.GameUI()
            game.on_map_country_click('CN')
            insp = game._inspector
            insp.update(*_inspector_args(game, 'CN'))
            for attr, width in panels.InspectorPanel.FIT_WIDTH.items():
                lbl = getattr(insp, attr, None)
                if lbl is None:
                    continue
                lbl.text_size = (width, None)
                lbl.texture_update()
                need = max(lbl.texture_size[1], 1)
                self.assertGreaterEqual(
                    lbl.height + 0.5, need,
                    f'[{lang}] {attr} 高 {lbl.height:.0f} < 需要 {need:.0f}（会裁字）')

    def test_inspector_switch_keeps_layout_height_sufficient(self):
        """切换语言后立刻量一次，防止 refresh_lang 后高度残留旧语种需求。"""
        import ui_v4_panels as panels
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.on_map_country_click('CN')
        game.toggle_lang()
        insp = game._inspector
        insp.update(*_inspector_args(game, 'CN'))
        for attr, width in panels.InspectorPanel.FIT_WIDTH.items():
            lbl = getattr(insp, attr, None)
            if lbl is None:
                continue
            lbl.text_size = (width, None)
            lbl.texture_update()
            self.assertGreaterEqual(
                lbl.height + 0.5, max(lbl.texture_size[1], 1),
                f'切换语言后 {attr} 装不下文本')


    def test_tech_selection_survives_language_switch(self):
        """科技页切语言要保住选中节点，且详情描述随之换语种。"""
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        game = main.GameUI()
        game.open_page('tech')
        game._page.selected_key = 'br:traffic_obfuscation'
        game._refresh_tech_page()
        self.assertNotIn('traffic_obfuscation', game._page.lbl_d_desc.text)
        zh_desc = game._page.lbl_d_desc.text

        game.toggle_lang()

        self.assertEqual(game._page.selected_key, 'br:traffic_obfuscation',
                         '切语言后选中节点被丢掉（详情面板退回未选中态）')
        self.assertIn('Obfuscation', game._page.lbl_d_title.text)
        self.assertNotEqual(zh_desc, game._page.lbl_d_desc.text)
        self.assertNotIn('suspicion_mult', game._page.lbl_d_desc.text,
                         '描述里泄漏了英文效果键名')


def _inspector_args(game, code):
    """按 PagesMixin._open_inspector 的口径组装 InspectorPanel.update 的实参。"""
    import engine as _e
    from balance import TUNE
    cs = game._country_state(code)
    return (cs, game.stats, _e.player.total_downloads_m,
            _e.player.suspicion, TUNE['unlock_penetration_threshold'])


if __name__ == '__main__':
    unittest.main()
