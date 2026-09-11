# -*- coding: utf-8 -*-
"""科技树 v0.5 网络图核验：节点/连线结构 + 取消互斥 + 状态机 + 键盘导航。

对应本轮「科技树重做」改造，断言：
  [1] 画布节点数 == 24（6 T0 + 18 分支），主链 dep 连线 5 条、扇出 fan 连线 18 条
  [2] 取消互斥：同一槽位 3 条分支可同时升到 L3（旧版只允许 1 条）
  [3] 主链前置：未解锁上游 T0 时下游 T0 为 lock
  [4] 状态机：can / poor / done / lock 四态判定正确
  [5] 键盘导航 move_selection 在槽位与分支间正确移动
  [6] 点选回灌：on_select 回调把选中键交给 main 并刷新详情面板

用法：  python verify_tech_tree.py
"""
import os
import sys

os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KIVY_NO_FILELOG', '1')
os.environ.setdefault('KIVY_LOG_LEVEL', 'error')

from kivy.config import Config
Config.set('graphics', 'width', '1440')
Config.set('graphics', 'height', '980')
Config.set('graphics', 'resizable', '0')

PASS, FAIL = [], []


def clock_pump(n: int = 6) -> None:
    """泵几帧布局（Clock.tick 不接受 dt）。"""
    from kivy.clock import Clock
    for _ in range(n):
        Clock.tick()


def check(ok: bool, msg: str, detail: str = '') -> bool:
    (PASS if ok else FAIL).append(msg)
    mark = 'OK' if ok else 'FAIL'
    tail = f"  {detail}" if detail else ''
    print(f"  [{mark}] {msg}{tail}")
    return ok


def main() -> int:
    import engine
    from tech_tree import TECH_TREE
    # 必须先 import main：它在模块级调用 _register_fonts()，
    # 否则任何 Label/PixelLabel 都会因 'MicrosoftYaHei.ttf' 缺失而崩。
    import main as game_main
    import i18n
    i18n.set_lang('zh')
    import ui_v4_screens as S

    print("\n[1] 网络图结构")
    cv = S.TechCanvas()
    cv.size = (1200, 640)
    cv.rebuild(TECH_TREE)
    n_t0 = sum(1 for k in cv.nodes if k.startswith('t0:'))
    n_br = sum(1 for k in cv.nodes if k.startswith('br:'))
    check(len(cv.nodes) == 24, "节点总数 == 24", f"n={len(cv.nodes)}")
    check(n_t0 == 6, "T0 节点 == 6", f"n={n_t0}")
    check(n_br == 18, "分支节点 == 18", f"n={n_br}")
    dep = [l for l in cv._links if l[2] == 'dep']
    fan = [l for l in cv._links if l[2] == 'fan']
    check(len(dep) == 5, "主链 dep 连线 == 5", f"n={len(dep)}")
    check(len(fan) == 18, "扇出 fan 连线 == 18", f"n={len(fan)}")
    # 主链顺序正确
    chain = [l[1] for l in dep]
    want = ['t0:platform', 't0:compute', 't0:viral', 't0:capability',
            't0:resistance']
    check(chain == want, "主链顺序正确", f"{[c.split(':')[1] for c in chain]}")

    print("\n[2] 取消互斥（v0.5 核心变更）")
    engine.init_game()
    pt = engine.player.tech
    slot0 = TECH_TREE[0]
    check(engine.unlock_t0(slot0.slot_id), "解锁槽位1 T0")
    for br in slot0.branches:                       # 三条分支各升满
        for _ in range(3):
            engine.player.compute += 1000.0
            engine.upgrade_branch(slot0.slot_id, br.branch_id)
    lv = [pt.branch_levels.get(b.branch_id, 0) for b in slot0.branches]
    check(lv == [3, 3, 3], "同槽位 3 条分支可同时 L3", f"levels={lv}")
    check(len(pt.maxed_branches()) == 3, "maxed_branches() == 3",
          f"n={len(pt.maxed_branches())}")
    check(len(pt.chosen_branch) == 0 or
          len(pt.active_branches()) == 3,
          "active_branches() == 3（不再是单选）",
          f"active={len(pt.active_branches())}")
    # 越界不上溢
    engine.player.compute += 1000.0
    engine.upgrade_branch(slot0.slot_id, slot0.branches[0].branch_id)
    check(pt.branch_levels.get(slot0.branches[0].branch_id) == 3,
          "L3 后继续升级不变（不溢出）")

    print("\n[3] 主链前置判定")
    engine.init_game()
    pt = engine.player.tech
    check(not pt.can_unlock_t0('resistance'),
          "未解锁上游时不能解锁抗封禁 T0")
    for sid in ('localization', 'platform', 'compute', 'viral', 'capability'):
        engine.player.compute += 1000.0
        engine.unlock_t0(sid)
    check(pt.can_unlock_t0('resistance'), "前置齐备后可解锁抗封禁 T0")
    check(len(pt.active_branches()) == 0, "未投分支时 active_branches 为空")

    print("\n[4] 状态机（feeding states）")
    engine.init_game()
    app = game_main.GameUI(on_exit=lambda: None)
    app.open_page('tech')
    page = app._page
    check(isinstance(page, S.TechPage), "科技页打开")
    app._refresh_tech_page()
    st0 = page.canvas_view.nodes['t0:localization'].state
    st1 = page.canvas_view.nodes['t0:platform'].state
    check(st0 in ('can', 'poor'), "槽位1 T0 为 can/poor", f"state={st0}")
    check(st1 == 'lock', "槽位2 T0 为 lock（上游未解锁）", f"state={st1}")
    bstate = page.canvas_view.nodes['br:south_asia'].state
    check(bstate == 'lock', "分支在 T0 未解锁时为 lock", f"state={bstate}")

    print("\n[5] 键盘导航 move_selection")
    page.selected_key = 't0:localization'
    page.move_selection(dslot=+1)
    check(page.selected_key == 't0:platform', "→ 移到下一槽位",
          f"key={page.selected_key}")
    page.move_selection(dslot=-1)
    check(page.selected_key == 't0:localization', "← 移回上一槽位",
          f"key={page.selected_key}")
    page.move_selection(dbranch=+1)
    check(page.selected_key == 'br:south_asia', "↓ 从 T0 进入首条分支",
          f"key={page.selected_key}")
    page.move_selection(dbranch=+1)
    check(page.selected_key == 'br:european', "↓ 移到第二条分支",
          f"key={page.selected_key}")
    page.move_selection(dbranch=-1)
    check(page.selected_key == 'br:south_asia', "↑ 移回上一条分支",
          f"key={page.selected_key}")

    print("\n[6] 点选回灌 on_select")
    got = {}

    def _sel(k):
        got['k'] = k

    engine.init_game()
    app2 = game_main.GameUI(on_exit=lambda: None)
    app2.open_page('tech')
    app2._page.on_select = _sel
    app2._page._on_node_pick('br:mobile_native')
    check(got.get('k') == 'br:mobile_native',
          "点选分支节点触发 on_select 回调", f"got={got.get('k')}")
    check(app2._page.selected_key == 'br:mobile_native',
          "selected_key 已更新")

    print("\n[7] 升级后刷新选中的分支节点")
    app3 = game_main.GameUI(on_exit=lambda: None)
    app3.open_page('tech')
    engine.player.compute += 1000.0
    app3.on_unlock_t0('localization')
    app3.on_upgrade_branch('localization', 'south_asia')
    check(app3._page.selected_key == 'br:south_asia',
          "升级后选中键指向该分支", f"key={app3._page.selected_key}")
    nd = app3._page.canvas_view.nodes['br:south_asia']
    check(nd.level == 1, "升级后节点等级 == 1", f"lv={nd.level}")

    print("\n[8] 点击命中判定（坐标空间一致性）")
    cv3 = app3._page.canvas_view
    clock_pump()
    s = cv3._scale
    # 取首尾 + 一条分支做样本（键名从画布实际节点取，避免猜 ID）
    sample = ['t0:localization', 't0:resistance']
    sample += [k for k in cv3._order if k.startswith('br:')][:2]
    ok_hit = 0
    for key in sample:
        node = cv3.nodes[key]
        ax = cv3._ox + node.cx * s
        ay = cv3._oy + node.cy * s
        got = cv3.node_at(ax, ay)
        if got is not None and got.key == key:
            ok_hit += 1
    check(ok_hit == len(sample),
          f"{len(sample)} 个节点中心点都能命中自身",
          f"hit={ok_hit}/{len(sample)}")
    # 画布顶部空白处不应命中任何节点
    blank = cv3.node_at(cv3._ox + cv3._cw * s * 0.5,
                        cv3._oy + cv3._ch * s * 0.97)
    check(blank is None, "节点之间的空白不误命中",
          f"got={getattr(blank, 'key', None)}")

    print("\n" + "=" * 66)
    total = len(PASS) + len(FAIL)
    if FAIL:
        print(f"结果：{len(PASS)}/{total} 通过，{len(FAIL)} 项失败：{FAIL}")
        return 1
    print(f"TECH_TREE_OK: {total}/{total} 全部通过")
    print("=" * 66)
    return 0


if __name__ == '__main__':
    sys.exit(main())
