"""跨对局的玩家设置：独立于游戏存档，修改后立即写盘。"""
import json
import os
import sys


def _user_data_dir():
    """持久化数据根目录（兼顾源码运行与 PyInstaller 单文件打包）。

    - 源码运行：本模块所在目录（demo/），与现有开发 / git 约定一致。
    - 打包为单文件 exe 后，所有脚本模块会被 PyInstaller 解压到临时目录
      ``sys._MEIPASS``，该目录在进程退出时被删除。若把 settings.json
      写在这里，设置会在重启后丢失。因此冻结态下改写到 exe 同级目录
      （持久、可写）；若该目录不可写（如安装到 Program Files）则回退到
      用户数据目录 ``%APPDATA%/AI-BieNao``。
    """
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.executable))
        probe = os.path.join(base, '.write_test')
        try:
            with open(probe, 'w') as _f:
                _f.write('')
            os.unlink(probe)
            return base
        except OSError:
            app = os.environ.get('APPDATA') or os.path.expanduser('~')
            return os.path.join(app, 'AI-BieNao')
    return os.path.dirname(os.path.abspath(__file__))


SETTINGS_PATH = os.path.join(_user_data_dir(), 'settings.json')
DEFAULTS = {
    'language': 'zh',
    'speed_idx': 1,
    'reduce_motion': False,
    'grid_mode': 1,
    'a11y_shapes': True,
    'sound_on': True,
    'music_on': True,
    'ui_scale': 1.0,
}
_current = dict(DEFAULTS)


def _clean(raw: dict) -> dict:
    data = dict(DEFAULTS)
    if not isinstance(raw, dict):
        return data
    data['language'] = raw.get('language') if raw.get('language') in ('zh', 'en') else 'zh'
    data['speed_idx'] = max(0, min(int(raw.get('speed_idx', 1)), 3))
    data['grid_mode'] = max(0, min(int(raw.get('grid_mode', 1)), 2))
    data['ui_scale'] = max(0.7, min(float(raw.get('ui_scale', 1.0)), 1.6))
    for key in ('reduce_motion', 'a11y_shapes', 'sound_on', 'music_on'):
        data[key] = bool(raw.get(key, DEFAULTS[key]))
    return data


def load() -> dict:
    global _current
    try:
        with open(SETTINGS_PATH, encoding='utf-8') as f:
            _current = _clean(json.load(f))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        _current = dict(DEFAULTS)
    return dict(_current)


def save(values: dict) -> str:
    global _current
    _current = _clean(values)
    folder = os.path.dirname(SETTINGS_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = SETTINGS_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(_current, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, SETTINGS_PATH)
    return SETTINGS_PATH


def update(**changes) -> str:
    values = dict(_current)
    values.update(changes)
    return save(values)


def get(key: str = None):
    return _current.get(key) if key is not None else dict(_current)
