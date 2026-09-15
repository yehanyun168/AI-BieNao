"""冻结态（PyInstaller 单文件 exe）下，设置与存档必须写到持久目录，而非
被进程退出即删的 sys._MEIPASS 临时解压目录，也不能落到 exe 同级目录
（否则桌面 / 下载文件夹会凭空出现 settings.json / saves）。

回归锚点：v0.4.0 单文件打包后，preferences.SETTINGS_PATH 与
save_manager.SAVE_DIR / CRASH_LOG 都由 exe 目录推导，导致运行时数据污染
exe 所在目录。v0.4.1+ 改为统一写到 ``%APPDATA%/AI-BieNao``。
本测试模拟冻结态并覆盖 APPDATA 环境变量，断言路径落在该目录下，
并能正确往返读写；同时验证 migrate_legacy_data 能把旧版 exe 旁的数据
复制到 APPDATA。
"""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import preferences
import save_manager


class FrozenPersistPathTests(unittest.TestCase):
    def _simulate_frozen(self, d: Path, appdata: Path):
        """d 放虚拟 exe；appdata 作为 %APPDATA%。"""
        exe = d / 'AI-BieNao.exe'
        exe.write_bytes(b'MZ')
        self._old_frozen = getattr(sys, 'frozen', None)
        self._old_exe = sys.executable
        self._old_appdata = os.environ.get('APPDATA')
        sys.frozen = True
        sys.executable = str(exe)
        os.environ['APPDATA'] = str(appdata)
        return exe

    def _restore(self):
        if self._old_frozen is None:
            if hasattr(sys, 'frozen'):
                del sys.frozen
        else:
            sys.frozen = self._old_frozen
        sys.executable = self._old_exe
        if self._old_appdata is None:
            os.environ.pop('APPDATA', None)
        else:
            os.environ['APPDATA'] = self._old_appdata

    def test_preferences_path_in_appdata_when_frozen(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as appd:
            self._simulate_frozen(Path(d), Path(appd))
            try:
                importlib.reload(preferences)
                self.assertNotIn('_MEIPASS', preferences.SETTINGS_PATH)
                self.assertTrue(
                    preferences.SETTINGS_PATH.startswith(appd))
                self.assertIn('AI-BieNao', preferences.SETTINGS_PATH)
            finally:
                self._restore()
                importlib.reload(preferences)

    def test_save_manager_paths_in_appdata_when_frozen(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as appd:
            self._simulate_frozen(Path(d), Path(appd))
            try:
                importlib.reload(save_manager)
                self.assertNotIn('_MEIPASS', save_manager.SAVE_DIR)
                self.assertNotIn('_MEIPASS', save_manager.CRASH_LOG)
                self.assertTrue(save_manager.SAVE_DIR.startswith(appd))
                self.assertTrue(save_manager.CRASH_LOG.startswith(appd))
                self.assertIn('AI-BieNao', save_manager.SAVE_DIR)
            finally:
                self._restore()
                importlib.reload(save_manager)

    def test_settings_round_trip_under_frozen_path(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as appd:
            self._simulate_frozen(Path(d), Path(appd))
            try:
                importlib.reload(preferences)
                preferences.save({'language': 'en', 'ui_scale': 1.4})
                loaded = preferences.load()
                self.assertEqual(loaded['language'], 'en')
                self.assertEqual(loaded['ui_scale'], 1.4)
                self.assertTrue(
                    os.path.exists(os.path.join(appd, 'AI-BieNao', 'settings.json')))
            finally:
                self._restore()
                importlib.reload(preferences)

    def test_migrate_legacy_data_from_exe_dir_to_appdata(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as appd:
            exe_dir = Path(d)
            app_data_dir = Path(appd) / 'AI-BieNao'
            self._simulate_frozen(exe_dir, Path(appd))
            try:
                # 模拟旧版数据落在 exe 同级目录
                (exe_dir / 'settings.json').write_text(
                    json.dumps({'language': 'zh', 'ui_scale': 1.2},
                               ensure_ascii=False),
                    encoding='utf-8')
                (exe_dir / 'saves').mkdir()
                (exe_dir / 'saves' / 'slot1.json').write_text(
                    '{"version": 4}', encoding='utf-8')
                (exe_dir / 'crash.log').write_text('legacy log\n', encoding='utf-8')

                importlib.reload(save_manager)
                save_manager.migrate_legacy_data()

                self.assertTrue(
                    (app_data_dir / 'settings.json').exists())
                self.assertTrue(
                    (app_data_dir / 'saves' / 'slot1.json').exists())
                self.assertTrue(
                    (app_data_dir / 'crash.log').exists())
                # 迁移是复制，源文件应保留（外层决定清理）
                self.assertTrue((exe_dir / 'settings.json').exists())
            finally:
                self._restore()
                importlib.reload(save_manager)


if __name__ == '__main__':
    unittest.main()
