"""开场动画「播完 / 跳过后停止 BGM」守卫（intro.py + main.py）

用户规则（2026-09-14）：开场动画播放结束、或被跳过时，开场期间放着的
音乐必须立刻停。

为什么单开一个文件：这条规则横跨两个模块，且极易被悄悄改回去 ——
  · intro.py `_finish()` 原本只 `sfx.stop_all_loops()`（停音效循环床），
    从没碰过 BGM；而开场动画是**盖在主菜单之上的浮层**，底下一直放着
    主菜单曲池，不停的话菜单音乐会一路漏进出身页甚至对局。
  · 停了之后必须有人接回来：取消出身页回主菜单要 `bgm.update('menu')`，
    进局由 `_enter_game` 的 `bgm.update('calm')` 接。漏接会静音。

运行：``python test_intro_bgm_stop.py``
（必须带 KIVY_NO_FILELOG=1，否则 Kivy import 阶段 purge_logs() 会抛 OSError）
"""
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ.setdefault('KIVY_NO_FILELOG', '1')
os.environ.setdefault('KIVY_WINDOW', 'sdl2')

import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bgm                # noqa: E402
import i18n               # noqa: E402
import intro              # noqa: E402

INTRO_SRC = open(os.path.join(HERE, 'intro.py'), encoding='utf-8').read()
MAIN_SRC = open(os.path.join(HERE, 'main.py'), encoding='utf-8').read()

print(" 开场动画 BGM 收尾守卫")
_checks = 0


def _ok(msg):
    global _checks
    _checks += 1
    print("   [OK] " + msg)


# ------------------------------------------------------------
# 1) 静态契约：intro._finish 必须停 BGM（与 stop_all_loops 并列）
# ------------------------------------------------------------
assert 'import bgm' in INTRO_SRC, \
    "intro.py 未 import bgm —— 开场收尾无法停 BGM"

_finish = INTRO_SRC.split('def _finish(self, *_a):', 1)[1].split('\n    def ', 1)[0]
assert 'bgm.stop()' in _finish, \
    "IntroPlayer._finish() 没有 bgm.stop() —— 播完/跳过後 BGM 会继续放"
assert 'sfx.stop_all_loops()' in _finish, \
    "IntroPlayer._finish() 应保留 sfx.stop_all_loops()（音效循环床兜底）"
_ok("intro._finish 同时停音效循环床与 BGM（源码断言）")

# ------------------------------------------------------------
# 2) 运行时：播完 / 跳过两条路径都要真的停掉
# ------------------------------------------------------------
bgm.load_all()
if not bgm.BGM_ON:          # 音乐开关被关时不做发声断言，只验证状态复位
    bgm.BGM_ON = True

for _label, _how in (('跳过（_skip）', '_skip'), ('播完（_finish）', '_finish')):
    bgm.update('menu')                    # 模拟：开场期间主菜单曲池在放
    assert bgm._current == 'menu', \
        "前置条件失败：bgm.update('menu') 未切到 menu 池（当前 %r）" % bgm._current

    _fired = []
    player = intro.IntroPlayer(on_done=lambda: _fired.append('done'))
    getattr(player, _how)()

    assert _fired == ['done'], \
        "%s 未触发 on_done（实际 %r）" % (_label, _fired)
    assert bgm._current is None, \
        "%s 後 bgm._current 应为 None（实际 %r）—— BGM 没停" % (_label, bgm._current)
    assert bgm._playing is None, \
        "%s 後 bgm._playing 应为 None（实际 %r）—— BGM 没停" % (_label, bgm._playing)
    for _stem, _snd in bgm._SOUNDS.items():
        if _snd is None:
            continue
        try:
            _st = _snd.state
        except Exception:
            continue
        assert _st != 'play', \
            "%s 後 %s 仍在播放（state=%r）" % (_label, _stem, _st)
    _ok("%s → on_done 触发且 BGM 全停（_current/_playing 复位，无曲目在播）"
        % _label)

# _finish 幂等：重复调用不得抛异常
bgm.update('menu')
_p2 = intro.IntroPlayer(on_done=lambda: None)
_p2._finish()
_p2._finish()
assert bgm._current is None, "重复 _finish 後 BGM 状态异常"
_ok("_finish 幂等（重复收尾不抛异常、状态保持已停）")

# ------------------------------------------------------------
# 3) 静态契约：取消出身页回主菜单必须把菜单曲池接回来
# ------------------------------------------------------------
assert '_close_origin_flow_to_menu' in MAIN_SRC, \
    "main.py 缺 _close_origin_flow_to_menu —— 取消出身页回菜单会静音"
assert 'on_cancel=self._close_origin_flow_to_menu' in MAIN_SRC, \
    "出身页「取消」按钮未走恢复版收尾，回菜单会没音乐"
_m = MAIN_SRC.split('def _close_origin_flow_to_menu', 1)[1].split(
    '\n    def ', 1)[0]
assert "bgm.update('menu')" in _m, \
    "_close_origin_flow_to_menu 未调用 bgm.update('menu')"
# ESC 取消是第二条路径，行为必须与取消按钮一致
_esc = MAIN_SRC.split("isinstance(self._origin_flow, S.OriginPage):", 1)[1]
assert '_close_origin_flow_to_menu()' in _esc.split('return True', 1)[0], \
    "出身页按 ESC 取消仍走旧收尾（两条取消路径行为不一致）→ 回菜单静音"
_ok("取消出身页（按钮 / ESC 两条路径）均恢复主菜单曲池")

print(" 开场动画 BGM 收尾守卫：%d 项全部通过" % _checks)
