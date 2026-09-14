"""把纯 JSON 偏好应用到 UI、声音和节奏运行时。"""
import bgm
import i18n
import preferences
import sfx
import ui_shared as ST


def load_and_apply() -> dict:
    data = preferences.load()
    i18n.set_lang(data['language'])
    ST.CURRENT_SPEED_IDX = data['speed_idx']
    ST.REDUCE_MOTION = data['reduce_motion']
    ST.GRID_MODE = data['grid_mode']
    ST.A11Y_SHAPES = data['a11y_shapes']
    sfx.set_enabled(data['sound_on'])
    bgm.set_enabled(data['music_on'])
    return data


def set_language(lang):
    i18n.set_lang(lang); preferences.update(language=lang)


def set_sound(i):
    sfx.set_enabled(bool(int(i))); preferences.update(sound_on=sfx.SFX_ON)


def set_music(i):
    bgm.set_enabled(bool(int(i))); preferences.update(music_on=bgm.BGM_ON)


def set_motion(i):
    ST.REDUCE_MOTION = bool(int(i)); preferences.update(reduce_motion=ST.REDUCE_MOTION)


def set_a11y(i):
    ST.A11Y_SHAPES = bool(int(i)); preferences.update(a11y_shapes=ST.A11Y_SHAPES)


def set_speed(i):
    ST.CURRENT_SPEED_IDX = max(0, min(int(i), len(ST.SPEED_STEPS) - 1))
    preferences.update(speed_idx=ST.CURRENT_SPEED_IDX)


def set_grid(i, map_widget=None):
    ST.GRID_MODE = max(0, min(int(i), 2))
    if map_widget is not None:
        map_widget.set_grid_mode(ST.GRID_MODE)
    preferences.update(grid_mode=ST.GRID_MODE)
