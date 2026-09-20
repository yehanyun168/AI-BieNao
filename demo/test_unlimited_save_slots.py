"""无限存档槽和非覆盖自动保存。"""

import os
import tempfile
import unittest

import engine
import main
import save_manager
from i18n import t


class UnlimitedSaveSlotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_save_dir = save_manager.SAVE_DIR
        save_manager.SAVE_DIR = self.tmp.name
        engine.init_game(seed=1)

    def tearDown(self):
        save_manager.SAVE_DIR = self.old_save_dir
        self.tmp.cleanup()

    def test_next_slot_uses_highest_existing_number(self):
        for name in ('slot1.json', 'slot3.json', 'notes.json'):
            open(os.path.join(self.tmp.name, name), 'w').close()

        self.assertEqual(save_manager.next_slot_name(), 'slot4.json')
        self.assertEqual(save_manager.slot_names(),
                         ['slot1.json', 'slot3.json'])

    def test_auto_save_always_overwrites_dedicated_file(self):
        first = save_manager.save_auto()
        engine.player.tick_count = 7
        second = save_manager.save_auto()

        self.assertEqual(first, second)
        self.assertEqual(os.path.basename(first), 'autosave.json')
        self.assertEqual(save_manager.slot_names(), [])
        self.assertTrue(os.path.exists(first))

    def test_auto_save_is_first_row(self):
        save_manager.save_auto()
        save_manager.save(os.path.join(self.tmp.name, 'slot1.json'))

        rows = main.read_slot_rows()

        self.assertEqual(rows[0][0], t('slot_autosave'))
        self.assertEqual(rows[1][0], t('slot_name_fmt').format(n='01'))

    def test_periodic_auto_save_only_runs_every_twelve_rounds(self):
        view = main.GameUI()
        calls = []
        original = save_manager.save_auto
        save_manager.save_auto = lambda: calls.append(engine.player.tick_count)
        try:
            engine.player.tick_count = 11
            view._autosave_if_due()
            engine.player.tick_count = 12
            view._autosave_if_due()
        finally:
            save_manager.save_auto = original

        self.assertEqual(calls, [12])


if __name__ == '__main__':
    unittest.main()
