"""跨对局的玩家设置：独立于游戏存档，修改后立即写盘。"""
import json
import os

from paths import _user_data_dir


SETTINGS_PATH = os.path.join(_user_data_dir(), 'settings.json')
DEFAULTS = {
    'language': 'zh',
    'speed_idx': 1,
    'reduce_motion': False,
    'grid_mode': 1,
    'a11y_shapes': True,
    'sound_on': True,
    'music_on': True,
}
_current = dict(DEFAULTS)


def _clean(raw: dict) -> dict:
    data = dict(DEFAULTS)
    if not isinstance(raw, dict):
        return data
    data['language'] = raw.get('language') if raw.get('language') in ('zh', 'en') else 'zh'
    data['speed_idx'] = max(0, min(int(raw.get('speed_idx', 1)), 3))
    data['grid_mode'] = max(0, min(int(raw.get('grid_mode', 1)), 2))
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
