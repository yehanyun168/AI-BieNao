"""音效资源完整性专项（2026-09-13 从 test_build.py 第 23 项抽出）

为什么要单独测：``sfx.py`` 是「失败安全」设计 —— 文件缺失只打一行警告后静默
跳过，游戏照跑但不响。保证不崩，代价是缺失**无声无息**；真人测试包丢过音效
（repack 硬编码清单漏登记），靠这些断言才能发现。

抽出动机：test_build.py 已顶到 800 行门禁，且本项属于「音效资源」独立关注点，
与 test_build 的「构建可启动」职责可分。

运行：``python test_sfx_assets.py``
"""
import os
import re
import sys

# Kivy 日志清理在部分 Windows 机器会因文件保护抛 OSError（游戏侧已在
# main.py 兜底设 KIVY_NO_FILELOG=1，测试脚本同样需要）
os.environ.setdefault('KIVY_NO_FILELOG', '1')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import sfx as _sfx_mod          # noqa: E402
import bgm as _bgm_mod          # noqa: E402

# ---- 1) 文件齐全：NAMES 里每个音效都要能在 assets/sfx 找到 ----
sfx_dir = os.path.join(HERE, 'assets', 'sfx')
missing = [n for n in _sfx_mod.NAMES if not any(
    os.path.exists(os.path.join(sfx_dir, n + s)) for s in _sfx_mod.SUFFIXES)]
assert not missing, f"demo/assets/sfx 缺音效文件: {missing}（sfx.py 会静默静音）"

# ---- 2) 合成基线 12 个必须在（gen_sfx.py 可复现；删掉=破坏可复现基线）----
BASE12 = ('click', 'select', 'cast', 'success', 'fail', 'crisis',
          'end_win', 'end_lose', 'tech', 'pause', 'drop', 'unlock')
assert not [n for n in BASE12 if n not in _sfx_mod.NAMES], "sfx.NAMES 丢了合成基线音效"

# ---- 3) 语义分层 12 个必须在 NAMES 里 ----
SEMANTIC = ('hover', 'page', 'toggle', 'error', 'confirm', 'deploy', 'branch',
            'confirm_cast', 'counter_warn', 'counter_hit', 'achieve', 'commission')
_lost = [n for n in SEMANTIC if n not in _sfx_mod.NAMES]
assert not _lost, f"sfx.NAMES 缺语义分层音效: {_lost}"

# ---- 4) scroll 必须已移除（零调用点 + 亮度 11964Hz 拉高整库上限 + 语义错误）----
# 若日后真需要滚动音，应用 gen_sfx.py 合成 20-40ms 参数化短脉冲。
assert 'scroll' not in _sfx_mod.NAMES, "scroll 应已移除（无调用点且指标超标）"

# ---- 5) BGM 曲池每首必须存在（bgm.py 同样静默降级）----
bgm_dir = os.path.join(HERE, 'assets', 'bgm')
for st in _bgm_mod.STATES:
    for stem in _bgm_mod.pool_stems(st):
        assert _bgm_mod._resolve(bgm_dir, stem) is not None, \
            f"demo/assets/bgm 缺 BGM: {stem}"

# ---- 6) 授权声明必须随源码走（素材合规留痕）----
for d in (sfx_dir, bgm_dir):
    assert os.path.exists(os.path.join(d, 'CREDITS.md')), \
        f"{d}/CREDITS.md 缺失（素材授权声明必须入库）"

# ---- 7) 接线断言：语义音效必须真的被用上，否则等于没集成 ----
# ⚠️ main.py 必须在内 —— 它此前是唯一零音效接线的 UI 文件（5 主按钮 + 3 存档槽
# 点击全静默），而旧版这里漏扫 main.py，导致该缺陷长期不被测试发现。
# 2026-09-13：ui_v4_screens.py 已拆分为 6 个模块，音效调用点随之分散，
# 扫描清单必须覆盖全家族，否则「已接线」断言会假绿。
# 2026-09-14：intro.py 拆为三模块，intro_shots.py（渲染器）承载全部音效调用点，
# 同样必须入列；循环床接口 play_loop/stop_loop 也算接线（server_hum/machine_run）。
SRC_FILES = ('ui_pages.py', 'ui_session.py', 'ui_input.py', 'ui_drop.py',
             'main.py', 'intro.py', 'intro_shots.py', 'intro_common.py',
             'ui_popups.py',
             'ui_v4_common.py', 'ui_v4_panels.py', 'ui_v4_cards.py',
             'ui_v4_canvas.py', 'ui_v4_syspages.py', 'ui_v4_screens.py')
src_all = ''.join(open(os.path.join(HERE, f), encoding='utf-8').read()
                  for f in SRC_FILES)
for needle in ("sfx.play('error')", "sfx.play('page')", "sfx.play('toggle')",
               "sfx.play('deploy' if ok else 'error')", "sfx.play('branch')",
               "sfx.play('achieve')", "sfx.play('commission')",
               "sfx.play('counter_warn')", "sfx.play('counter_hit')",
               "sfx.play('confirm' if _tone == 'primary' else 'click')",
               "sfx.play('select')"):
    assert needle in src_all, f"语义音效未接线: {needle}"

# ---- 8) 死资产守卫：声明但零调用的音效 = 白占体积 + 误导维护 ----
# 判据：音效名出现在任一 sfx.play(...) 实参即算已接线（含三目形式）。
# 已知豁免须显式登记理由，不允许默默存在。
DEAD_OK = {
    'hover': "留待鼠标悬停反馈（光标方案 A 配套，尚未接线）",
    'confirm_cast': "留待「确认投放」二次确认流（当前 deploy 单音已够）",
}
played = {m for a in re.findall(r"sfx\.(?:play|play_loop|stop_loop)\(([^)]*)\)",
                                src_all, re.S)
          for m in re.findall(r"'([a-z_]+)'", a)}
# 动态派发：sfx.play(shot['sfx']) —— 开场动画 INTRO_SHOTS 表驱动（power_on 等）
has_dyn = bool(re.search(r"sfx\.play\((shot\['sfx'\]|sfx_name|_name|name)\)",
                         src_all))
for n in _sfx_mod.NAMES:
    assert n in played or has_dyn or n in DEAD_OK, \
        f"音效 {n} 已声明但零调用点 → 接线 / 删除 / 登记进 DEAD_OK"

n_bgm = sum(_bgm_mod.pool_count(s) for s in _bgm_mod.STATES)
print(f"[OK] 音效资源完整：{len(_sfx_mod.NAMES)} 个音效 "
      f"(合成基线 {len(BASE12)} + 语义分层 {len(_sfx_mod.NAMES) - len(BASE12)})"
      f" / BGM {len(_bgm_mod.STATES)} 曲池 ×{n_bgm} 首"
      f" / 双 CREDITS 入库 / 接线已生效 / 死资产守卫通过")
print("OK")
