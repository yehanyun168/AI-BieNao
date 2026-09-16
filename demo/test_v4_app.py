"""v0.4 真机冒烟测试 —— 离屏构建全部 14 屏，捕获异常。

用法：
    python test_v4_app.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.config import Config
# 窗口物理宽度必须能被 4 整除，否则 RGBA 行错位、颜色循环移位
Config.set('graphics', 'width', '1440')
Config.set('graphics', 'height', '880')
Config.set('graphics', 'resizable', '1')

from kivy.core.window import Window  # noqa: E402

import main as M  # noqa: E402

RESULTS = []


def check(name, fn):
    """跑一个检查项，记录成功/失败。"""
    try:
        fn()
        RESULTS.append((name, True, ''))
        print(f"  [OK]   {name}")
    except Exception as e:                      # noqa: BLE001
        RESULTS.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"  [FAIL] {name}")
        traceback.print_exc()


def need(cond, msg):
    """断言辅助（lambda 里用）。"""
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    print("=" * 66)
    print("v0.4 真机冒烟测试")
    print("=" * 66)

    # ---------- 1. 主菜单（S01） ----------
    print("\n[1] S01 主菜单")
    rv = M.RootView()
    check('RootView 构建', lambda: need(rv.menu is not None, 'menu is None'))
    check('剪影地图存在', lambda: need(rv.menu.sil_map is not None, 'no sil_map'))
    check('存档槽 3 行', lambda: need(len(M.read_slot_rows(1)) == 3, 'rows != 3'))
    check('菜单有子控件', lambda: need(len(rv.menu.children) > 0, 'empty menu'))
    check('成就快照口径', lambda: need(len(M.ach_snapshot('all')[0]) == 22,
                                       f"cells {len(M.ach_snapshot('all')[0])}"))
    check('打开菜单设置浮层', rv.menu._open_settings)
    check('打开菜单成就浮层', rv.menu._open_ach)
    check('打开菜单帮助浮层', rv.menu._open_help)
    check('关闭浮层', rv.menu._close_overlay)

    # ---------- 2. 进入游戏（S02） ----------
    print("\n[2] S02 主界面")
    check('启动新游戏', rv.start_new_game)
    check('GameUI 实例', lambda: need(rv.game is not None, 'no game'))
    g = rv.game
    check('地图存在', lambda: need(g.map_widget is not None, 'no map'))
    check('技能卡 10 张', lambda: need(len(g.skill_cards) == 10, f'{len(g.skill_cards)}'))
    check('区域页签 5 个', lambda: need(len(g.region_tabs) == 5, f'{len(g.region_tabs)}'))
    check('指令栏存在', lambda: need(g.rail is not None, 'no rail'))
    check('技能带存在', lambda: need(g._skill_row is not None, 'no skillbar'))

    # ---------- 3. S03 检视卡 ----------
    print("\n[3] S03 国家检视卡")
    check('打开检视卡', lambda: g.on_map_country_click('CN'))
    check('检视卡实例', lambda: need(g._inspector is not None, 'no inspector'))
    check('关闭检视卡', g._close_inspector)

    # ---------- 4. S04 技能精准投放 ----------
    print("\n[4] S04 技能精准投放")
    check('进入投放模式', lambda: g.start_drop('push_song', ['CN', 'JP']))
    check('投放模式已开', lambda: need(g.drop_mode, 'off'))
    check('目标 2 个', lambda: need(len(g.drop_targets) == 2, f'{len(g.drop_targets)}'))
    check('切换目标', lambda: g.toggle_target('KR'))
    check('取消投放', g._cancel_drop)

    # ---------- 5. 五个全屏页 ----------
    print("\n[5] 全屏页（S05/S06/S10/S11/S12）")
    for name in ('skills', 'tech', 'ach', 'help', 'settings'):
        check(f'打开页 {name}', lambda n=name: g.open_page(n))
        check(f'关闭页 {name}', g.close_page)

    # ---------- 6. S14 日志抽屉 ----------
    print("\n[6] S14 日志抽屉")
    check('打开日志', g.toggle_log)
    check('关闭日志', g._close_log)

    # ---------- 7. S13 图层切换 ----------
    print("\n[7] S13 地图图层")
    for key in ('unlock', 'heat', 'block', 'compute'):
        check(f'图层 {key}', lambda k=key: g.set_layer(k))
    check('回到解锁图层', lambda: g.set_layer('unlock'))

    # ---------- 8. 区域 / 缩放 / 网格 ----------
    print("\n[8] 区域 / 缩放 / 网格")
    for key in ('asia', 'europe', 'americas', 'africa', 'oceania'):
        check(f'区域 {key}', lambda k=key: g.select_region(k))
    check('网格 off', lambda: g.map_widget.set_grid_mode(0))
    check('网格 on', lambda: g.map_widget.set_grid_mode(1))

    # ---------- 9. 弹窗（S07/S08/S09） ----------
    print("\n[9] 弹窗 S07/S08/S09")
    check('危机弹窗', g.show_crisis_popup)
    check('结局弹窗', lambda: g.show_ending_popup('regulated'))
    check('成就页兼容接口', g.show_achievements)

    # ---------- 10. 键盘 / 语言 / 暂停 ----------
    print("\n[10] 键盘 / 语言 / 暂停")
    check('暂停切换', g.toggle_pause)
    check('暂停恢复', g.toggle_pause)
    check('语言切换', g.toggle_lang)
    check('语言切回', g.toggle_lang)
    check('返回主菜单', rv.show_menu)
    check('菜单重建（语言）', lambda: rv.menu.rebuild())

    # ---------- 汇总 ----------
    ok = sum(1 for _, s, _ in RESULTS if s)
    bad = [(n, e) for n, s, e in RESULTS if not s]
    print("\n" + "=" * 66)
    print(f"结果：{ok}/{len(RESULTS)} 通过")
    for n, e in bad:
        print(f"  x {n}  ->  {e}")
    print("=" * 66)
    if not bad:
        print("\n全部通过 —— 14 屏全部可构建、可切换")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
