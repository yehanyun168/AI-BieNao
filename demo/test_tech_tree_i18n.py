"""科技树节点中英文数据与已打开页面的语言刷新。"""

import unittest

import engine
import i18n
import main
from tech_tree import TECH_TREE


class TechTreeI18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang(i18n.LANG_ZH)

    def test_all_slots_and_branches_have_english_name_and_description(self):
        for slot in TECH_TREE:
            self.assertTrue(slot.name_en, slot.slot_id)
            self.assertTrue(slot.description_en, slot.slot_id)
            self.assertNotEqual(slot.name_for('zh'), slot.name_for('en'))
            for branch in slot.branches:
                self.assertTrue(branch.name_en, branch.branch_id)
                self.assertTrue(branch.description_en, branch.branch_id)
                self.assertEqual(branch.name_for('en'), branch.name_en)

    def test_open_tech_page_changes_node_names_and_detail_to_english(self):
        i18n.set_lang(i18n.LANG_ZH)
        engine.init_game()
        ui = main.GameUI()
        ui.open_page('tech')
        page = ui._page
        page.selected_key = 't0:localization'
        ui._refresh_tech_page()
        self.assertEqual(page.canvas_view.nodes['t0:localization'].name, '本地化')

        ui.toggle_lang()

        node = page.canvas_view.nodes['t0:localization']
        self.assertEqual(node.name, 'Localization')
        self.assertIn('Asian and European markets', node.desc)


if __name__ == '__main__':
    unittest.main()
