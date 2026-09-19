"""主菜单继续游戏应先弹出存档槽位选择。"""

import json
import os
import tempfile
import unittest

import main
import save_manager


class ContinueSlotModalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_save_dir = save_manager.SAVE_DIR
        save_manager.SAVE_DIR = self.tmp.name

    def tearDown(self):
        save_manager.SAVE_DIR = self.old_save_dir
        self.tmp.cleanup()

    def _write_slot(self, number: int) -> str:
        path = os.path.join(self.tmp.name, f'slot{number}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'player': {'tick_count': number, 'game_over': False},
                'countries': [],
            }, f)
        return path

    def test_continue_opens_slot_picker_without_loading_immediately(self):
        expected = self._write_slot(2)
        loaded = []
        menu = main.MainMenu(on_continue=loaded.append)

        menu._fire_continue()

        self.assertEqual(loaded, [])
        self.assertIsNotNone(menu._continue_modal)
        rows = menu._continue_rows
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(row._btns) for row in rows], [0, 1, 0])

        rows[1]._btns[0].trigger_action(duration=0)
        self.assertEqual(loaded, [expected])

    def test_main_menu_no_longer_embeds_slot_rows(self):
        self._write_slot(1)
        menu = main.MainMenu()

        self.assertFalse(any(isinstance(w, main.SaveSlotRow) for w in menu.walk()))


if __name__ == '__main__':
    unittest.main()
