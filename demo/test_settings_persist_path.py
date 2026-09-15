"""冻结态（PyInstaller 单文件 exe）下，设置与存档必须写到持久目录，而非
被进程退出即删的 sys._MEIPASS 临时解压目录。否则设置 / 存档会在重启后丢失。

回归锚点：v0.4.0 单文件打包后，preferences.SETTINGS_PATH 与
save_manager.SAVE_DIR / CRASH_LOG 都由 os.path.dirname(__file__) 推导，在
冻结态下落到 _MEIPASS，导致「原先可保存的设置现在丢失」。本测试模拟冻结态，
断言路径落在 exe 同级目录（或 %APPDATA%/AI-BieNao），并能正确往返读写。
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import preferences
import save_manager


class FrozenPersistPathTests(unittest.TestCase):
    def _simulate_frozen(self, d: Path):
        exe = d / 'AI-BieNao.exe'
        exe.write_bytes(b'MZ')
        self._old_frozen = getattr(sys, 'frozen', None)
        self._old_exe = sys.executable
        sys.frozen = True
        sys.executable = str(exe)
        return exe

    def _restore(self):
        if self._old_frozen is None:
            del sys.frozen
        else:
            sys.frozen = self._old_frozen
        sys.executable = self._old_exe

    def test_preferences_path_outside_meipass_when_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            exe = self._simulate_frozen(Path(d))
            try:
                importlib.reload(preferences)
                self.assertNotIn('_MEIPASS', preferences.SETTINGS_PATH)
                self.assertTrue(
                    preferences.SETTINGS_PATH.startswith(os.path.dirname(str(exe))))
            finally:
                self._restore()
                importlib.reload(preferences)

    def test_save_manager_paths_outside_meipass_when_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            exe = self._simulate_frozen(Path(d))
            try:
                importlib.reload(save_manager)
                self.assertNotIn('_MEIPASS', save_manager.SAVE_DIR)
                self.assertNotIn('_MEIPASS', save_manager.CRASH_LOG)
                self.assertTrue(
                    save_manager.SAVE_DIR.startswith(os.path.dirname(str(exe))))
            finally:
                self._restore()
                importlib.reload(save_manager)

    def test_settings_round_trip_under_frozen_path(self):
        with tempfile.TemporaryDirectory() as d:
            exe = self._simulate_frozen(Path(d))
            try:
                importlib.reload(preferences)
                old = preferences.SETTINGS_PATH
                preferences.SETTINGS_PATH = os.path.join(
                    os.path.dirname(str(exe)), 'settings.json')
                try:
                    preferences.save({'language': 'en', 'ui_scale': 1.4})
                    loaded = preferences.load()
                    self.assertEqual(loaded['language'], 'en')
                    self.assertEqual(loaded['ui_scale'], 1.4)
                finally:
                    preferences.SETTINGS_PATH = old
            finally:
                self._restore()
                importlib.reload(preferences)


if __name__ == '__main__':
    unittest.main()
