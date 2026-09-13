"""开场动画 v2 拆分守卫 + intro_seen 持久化契约（test_intro_split.py）

两块独立关注点合守一文件（test_build 已顶行数门禁）：

A) 拆分守卫 —— 2026-09-14 intro.py（1300 行）拆为 intro_common（公共底座）/
   intro_shots（IntroShotsMixin 渲染器）/ intro（IntroPlayer 核心 + 转发）。
   守五条契约：转发完整 / 无反向 import（防循环导入）/ 无复制粘贴事故
   （方法双定义）/ 行数门禁 / 镜头表 kind ↔ 渲染器一一对应。
   ⚠️ 检查 import 必须走 AST，纯文本匹配会被 docstring 里的「intro.py」误伤。

B) intro_seen 持久化契约（用户 2026-09-13 拍板规则）——
   跳过=载入存档继续且已播过；播放=开始新游戏（无论存档新旧）或载入从未
   播过的旧档（v3 老档缺字段默认播）。守卫：字段默认 / SAVE_VERSION 4 迁移 /
   存读往返 / main·ui_session 接线（源码扫描，test_build 同款手法）。

运行：``python test_intro_split.py``
（必须带 KIVY_NO_FILELOG=1，否则 Kivy import 阶段 purge_logs() 会抛 OSError）
"""
import ast
import json
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ.setdefault('KIVY_NO_FILELOG', '1')
os.environ.setdefault('KIVY_WINDOW', 'sdl2')

import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import i18n                # noqa: E402
import intro               # noqa: E402
import intro_common        # noqa: E402
import intro_shots         # noqa: E402

print(" 开场动画拆分守卫 + intro_seen 持久化契约")

# ============================================================
# A1) 转发完整：外部契约符号都从 intro 可达
# ============================================================
for _sym in ('IntroPlayer', 'INTRO_SHOTS', 'SKIP_KEY_NAMES', 'SKIP_KEY_CODES',
             'MIN_CPS', 'dim', 'alpha', 'mix'):
    assert hasattr(intro, _sym), f"intro 转发缺 {_sym}"
    assert getattr(intro, _sym) is getattr(intro_common, _sym, None) or \
        _sym not in ('INTRO_SHOTS', 'dim', 'alpha', 'mix', 'MIN_CPS'), \
        f"intro.{_sym} 与 intro_common.{_sym} 不是同一对象（应转发而非复制）"
print("   ■ A1) 转发完整：INTRO_SHOTS/dim/alpha/mix 等与 intro_common 同对象")

# ============================================================
# A2) 无反向 import（intro_shots/intro_common 不得 import intro）
# ============================================================
def _imported(path):
    out = set()
    for n in ast.walk(ast.parse(open(path, encoding='utf-8').read())):
        if isinstance(n, ast.Import):
            out |= {a.name.split('.')[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0:
            out.add(n.module.split('.')[0])
    return out


for _f in ('intro_common.py', 'intro_shots.py'):
    assert 'intro' not in _imported(os.path.join(HERE, _f)), \
        f"{_f} 反向 import intro（循环导入，启动即崩）"
print("   ■ A2) 无反向 import：intro_shots/intro_common 均不 import intro")

# ============================================================
# A3) 无复制粘贴事故：两模块方法名集合不相交；kind ↔ 渲染器一一对应
# ============================================================
def _methods(path, cls_name):
    t = ast.parse(open(path, encoding='utf-8').read())
    c = next(n for n in t.body if isinstance(n, ast.ClassDef)
             and n.name == cls_name)
    return {m.name for m in c.body if isinstance(m, ast.FunctionDef)}


_core = _methods(os.path.join(HERE, 'intro.py'), 'IntroPlayer')
_shot_m = _methods(os.path.join(HERE, 'intro_shots.py'), 'IntroShotsMixin')
_dup = _core & _shot_m
assert not _dup, f"方法双定义（复制粘贴事故）: {sorted(_dup)}"
_kinds = [s['kind'] for s in intro.INTRO_SHOTS]
assert all(('_shot_' + k) in _shot_m for k in _kinds), \
    "INTRO_SHOTS.kind 缺对应 _shot_* 渲染器"
assert all(hasattr(intro.IntroPlayer, '_shot_' + k) for k in _kinds), \
    "IntroPlayer（MRO 合并后）缺 _shot_* 渲染器"
assert not any(k == 'variation' for k in _kinds), "variation 镜应已删除"
assert 30.0 <= sum(s['dur'] for s in intro.INTRO_SHOTS) <= 45.0
print(f"   ■ A3) 方法集不相交 / {_kinds.count(_kinds[0]) and len(_kinds)} 镜 kind↔渲染器一一对应 / 30-45s")
print(f"         （{_kinds}）")

# ============================================================
# A4) 行数门禁 + 底座零家族内依赖
# ============================================================
for _f, _cap in (('intro.py', 800), ('intro_shots.py', 800),
                 ('intro_common.py', 800)):
    _n = sum(1 for _ in open(os.path.join(HERE, _f), encoding='utf-8'))
    assert _n <= _cap, f"{_f} {_n} 行超门禁 {_cap}"
_common_deps = _imported(os.path.join(HERE, 'intro_common.py'))
assert not (_common_deps & {'intro', 'intro_shots'}), \
    "intro_common 底座不得依赖 intro 家族内模块"
assert 'pixel_ui' in _common_deps or not _common_deps, "底座需从 pixel_ui 取色"
print("   ■ A4) 三模块 ≤800 行 / intro_common 零家族内依赖")

# ============================================================
# B1) intro_seen 默认值 + SAVE_VERSION 4 + v3→v4 迁移（老档默认补播）
# ============================================================
import engine as _engine    # noqa: E402
import save_manager as _sm  # noqa: E402

_p = _engine.init_game(seed=13, origin='univ_lab')
assert getattr(_p, 'intro_seen', None) is False, \
    "PlayerState.intro_seen 默认必须 False（新档必播由 main 判定，不靠默认 True）"
_tmp = os.path.join(HERE, '_tintro.json')
_engine.player.intro_seen = True
assert _sm.save(_tmp), "存档失败"
_raw = json.load(open(_tmp, encoding='utf-8'))
assert _raw['version'] == 4, f"SAVE_VERSION 应为 4，实际 {_raw['version']}"
assert _raw['player']['intro_seen'] is True, "序列化应含 intro_seen=True"
assert _sm.load(_tmp) and _engine.player.intro_seen is True, "往返丢失 intro_seen"
# v3 老档迁移：缺字段 → 默认 False（老玩家下次读档补播一次，用户规则）
_engine.player.intro_seen = True
_sm.save(_tmp)
_raw = json.load(open(_tmp, encoding='utf-8'))
_raw['version'] = 3
_raw['player'].pop('intro_seen', None)
json.dump(_raw, open(_tmp, 'w', encoding='utf-8'), ensure_ascii=False)
assert _sm.load(_tmp), "v3 档加载失败"
assert _engine.player.intro_seen is False, \
    "v3 老档迁移后 intro_seen 应为 False（从未播过 → 补播一次）"
os.remove(_tmp)
print("   ■ B1) intro_seen：默认 False / v4 序列化往返 / v3→v4 迁移默认补播")

# ============================================================
# B2) 接线扫描：main 读档补播 + 进局置位落盘；ui_session 重开置位
# ============================================================
_sm_src = open(os.path.join(HERE, 'save_manager.py'), encoding='utf-8').read()
for _n in ("SAVE_VERSION = 4", "'intro_seen'", "_v3_to_v4",
           "_MIGRATIONS[3]"):
    assert _n in _sm_src, f"save_manager.py 缺 {_n}"
_main_src = open(os.path.join(HERE, 'main.py'), encoding='utf-8').read()
for _n in ("def _play_intro_then", "def _finish_intro_and_enter",
           "intro_seen", "intro.IntroPlayer"):
    assert _n in _main_src, f"main.py 缺开场持久化接线: {_n}"
_us_src = open(os.path.join(HERE, 'ui_session.py'), encoding='utf-8').read()
assert 'intro_seen = True' in _us_src, \
    "ui_session.restart_game 应置 intro_seen=True（重开不重复播）"
print("   ■ B2) 接线：save_manager v4 迁移 / main 补播+置位 / ui_session 重开置位")

print("\n 全部通过 - 拆分契约与 intro_seen 持久化契约成立")
