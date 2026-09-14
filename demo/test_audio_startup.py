# -*- coding: utf-8 -*-
"""守卫：音频「启动阶段静默」缺陷不回退。

背景（2026-09-14 修复）：
`sfx.load_all()` / `bgm.load_all()` 原本**只**写在 `GameUI.__init__` 里（进对局
才执行），而 `sfx.play()` / `sfx.play_loop()` / `bgm.update()` 都有
`if not ... or not _LOADED: return` 的前置拦截 —— 于是**启动阶段**（主菜单 +
开场动画）`_LOADED` 恒为 False，所有播放请求在加载之前就被 return 掉：
  · 主菜单按钮点击音 → 静默
  · 开场动画 server_hum / power_on / machine_run / impact_low → 静默
  · 主菜单 BGM（bgm.update('menu')）→ 静默
只有进对局（GameUI 构造）之后才出声。

三层防护：
1) App.build() 在 RootView/MainMenu 构建**之前**完成音频加载；
2) sfx.play / play_loop / bgm.update 首次调用时按需自举 load_all()，
   从此调用顺序不再影响发声；
3) 本文件做源码断言 + 运行时断言。

不依赖音频硬件：只断言 Sound 对象被真正 play（state == 'play'）。
"""
import ast
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('KIVY_NO_FILELOG', '1')

import sfx  # noqa: E402
import bgm  # noqa: E402


def _src(name):
    return io.open(os.path.join(HERE, name), encoding='utf-8').read()


def _func_src(path, func, cls=None):
    """取指定函数（可选限定类）的源码。"""
    src = _src(path)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if cls:
            if isinstance(node, ast.ClassDef) and node.name == cls:
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef) and sub.name == func:
                        return ast.get_source_segment(src, sub) or ''
        elif isinstance(node, ast.FunctionDef) and node.name == func:
            return ast.get_source_segment(src, sub if False else node) or ''
    return ''


def test_audio_loaded_before_menu_built():
    """App.build() 必须在构建 RootView（含 MainMenu）之前加载音频。"""
    seg = _func_src('main.py', 'build', cls='AIBienaoApp')
    assert seg, '找不到 AIBienaoApp.build'
    assert 'sfx.load_all()' in seg, 'AIBienaoApp.build 未加载音效'
    assert 'bgm.load_all()' in seg, 'AIBienaoApp.build 未加载 BGM'
    # 顺序：加载必须早于 RootView 构造
    assert (seg.index('sfx.load_all()') < seg.index('RootView(')
            ), '音频加载晚于 RootView 构造 —— 主菜单/开场仍会静默'


def test_play_not_blocked_by_loaded_flag():
    """play/play_loop/update 不得再用「未加载就直接 return」的写法。

    旧写法 `if not SFX_ON or not _LOADED: return` 会在加载之前把请求丢掉；
    新写法必须是 `if not _LOADED: load_all()`（按需自举）后再取 Sound。
    """
    whole = _src('sfx.py') + _src('bgm.py')
    for bad in ('if not SFX_ON or not _LOADED', 'if not BGM_ON or not _LOADED'):
        assert bad not in whole, (
            '仍存在「%s」—— 启动阶段会在加载前直接 return，导致静默' % bad)

    for path, func in (('sfx.py', 'play'), ('sfx.py', 'play_loop'),
                       ('bgm.py', 'update')):
        seg = _func_src(path, func)
        assert seg, '找不到 %s.%s' % (path, func)
        assert 'if not _LOADED:' in seg, (
            '%s.%s 缺少按需自举分支（首次调用时应 load_all()）' % (path, func))
        assert 'load_all()' in seg, (
            '%s.%s 未调用 load_all() 自举' % (path, func))


def test_sfx_self_bootstraps_at_startup():
    """运行时：模拟启动阶段（_LOADED=False），play / play_loop 必须能出声。"""
    sfx._LOADED = False                 # 刻意回到「尚未加载」的启动态
    sfx._SOUNDS.clear()
    sfx._LOOP_SOUNDS.clear()
    try:
        sfx.play('confirm')             # 主菜单主按钮音
        time.sleep(0.06)
        snd = sfx._SOUNDS.get('confirm')
        assert snd is not None, 'confirm 未加载（启动阶段静默）'
        assert getattr(snd, 'state', '') == 'play', 'confirm 未真正播放'

        sfx.play_loop('server_hum', 0.34)   # 开场环境床
        time.sleep(0.06)
        lp = sfx._LOOP_SOUNDS.get('server_hum')
        assert lp is not None, 'server_hum 循环未建立'
        assert getattr(lp, 'state', '') == 'play', 'server_hum 未播放'
    finally:
        sfx.stop_all_loops()


def test_intro_sfx_playable_at_startup():
    """开场 4 个专属音效在启动阶段（未预加载）也要能播。"""
    sfx._LOADED = False
    sfx._SOUNDS.clear()
    for n in ('power_on', 'machine_run', 'impact_low'):
        sfx.play(n)
        time.sleep(0.05)
        snd = sfx._SOUNDS.get(n)
        assert snd is not None, '%s 未加载' % n
        assert getattr(snd, 'state', '') == 'play', '%s 未播放' % n
        snd.stop()


if __name__ == '__main__':
    cases = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failed = 0
    for c in cases:
        try:
            c()
            print('  [OK]   %s' % c.__name__)
        except AssertionError as e:
            failed += 1
            print('  [FAIL] %s — %s' % (c.__name__, e))
    print('=' * 62)
    if failed:
        print('存在未通过项：%d/%d' % (failed, len(cases)))
        sys.exit(1)
    print('全部通过 —— %d/%d（音频启动阶段发声守卫）' % (len(cases), len(cases)))
