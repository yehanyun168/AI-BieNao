"""test_ui_v4.py - v0.4 组件离屏实例化自测

目的：在不人工点界面的前提下，把 ui_v4 / ui_v4_screens 的每个组件都真造一遍，
并调用一次它们的 update()/refresh()，用来捕获 Kivy 特有的运行时错误
（MRO 冲突、只读属性赋值、size_hint 塌陷、canvas 指令错序等）。

跑法：
    python test_ui_v4.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.config import Config
Config.set('graphics', 'resizable', '1')
Config.set('graphics', 'width', '1440')     # ! 宽度必须能被 4 整除
Config.set('graphics', 'height', '880')

from kivy.core.text import LabelBase
from kivy.core.window import Window

for _fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(_fp):
        try:
            LabelBase.register(name='MicrosoftYaHei', fn_regular=_fp)
            LabelBase.register(name='Roboto', fn_regular=_fp)
        except Exception:
            pass

import engine
import i18n
import tech_tree
import ui_v4 as U
import ui_v4_screens as S

FAILED = []


def check(name, fn):
    try:
        fn()
        print(f"  [OK]   {name}")
    except Exception as e:
        import traceback
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        FAILED.append(name)


def main():
    i18n.set_lang('zh')
    engine.init_game()
    stats = S.UiStats()
    stats.sample(engine.player_countries, engine.player, 1.2)
    for _ in range(6):
        stats.sample(engine.player_countries, engine.player, 0.8)

    print("\n=== ui_v4 原子组件 ===")

    def t_panel():
        p = U.StrokePanel()
        p.size = (300, 200)
    check('StrokePanel', t_panel)
    check('PxChip', lambda: [U.PxChip('x', tone=t).refresh_scale(1.0)
                             for t in ('up', 'dn', 'cost', 'lock', 'sys', 'plain', 'on')])
    check('ChipRow', lambda: U.ChipRow([('a', 'up'), ('b', 'dn')]).set_chips([('c', 'sys')]))
    check('SegBar', lambda: U.SegBar(12, 5.5, threshold=0.85, highlight={6, 7}))
    check('Spark', lambda: U.Spark([0.2, 0.5, 0.9], highlight_last=True))
    check('BlockBar', lambda: U.BlockBar(0.62).set_ratio(0.3))
    check('Steps', lambda: U.Steps(['a', 'b', 'c'], current=1).set_current(2))
    check('Reticle', lambda: U.Reticle())
    check('TgtLabel', lambda: U.TgtLabel('CN +30%', tone='ok').set_state('JP', 'bad'))
    check('RailButton', lambda: U.RailButton('⊕', 'Drop', badge=2).set_active(True))
    check('RegionTab', lambda: U.RegionTab('亚洲').set_text_parts('亚洲', 5))
    check('SegSwitch', lambda: U.SegSwitch(['a', 'b', 'c'], 1).set_current(2))
    check('LegendChip', lambda: U.LegendChip('#1f6f63', '#3ec9ac', '已解锁 11').set_text('x'))
    check('KvGrid', lambda: U.KvGrid(['a', 'b']).set_value('a', '1'))
    check('SkillBarCard', lambda: U.SkillBarCard('algo_top', '2', '算法霸榜', 'DL+30%', 50)
          .set_state('cd', 5, 0.62, '5 周期'))
    check('OptButton', lambda: U.OptButton(1, 'title', 'note', [('x', 'up')], badge='推荐'))
    check('StatsGrid', lambda: U.StatsGrid([('k', 'v', 'cyan'), ('k2', 'v2')]))
    check('AchCell', lambda: U.AchCell('1', 'name', 'desc', got=True, event_type=True))
    check('LogRow', lambda: U.LogRow('[24] hi', 'w'))
    check('KeyBox', lambda: U.KeyBox('组', [('Space', '暂停')]).height)
    check('SaveSlotRow', lambda: U.SaveSlotRow('槽位 01', '新档 · 空',
                                               [('存档', 'primary', lambda: None)],
                                               active=True))
    check('PageScreen', lambda: U.PageScreen('T').add_head_widget(U.PxChip('x')))

    print("\n=== ui_v4_screens 屏幕级组件 ===")
    check('InspectorPanel', lambda: S.InspectorPanel().update(
        engine.player_countries[0], stats, 500.0, 41.0))
    check('DropPreview', lambda: S.DropPreview().update(
        'algo_top', '算法霸榜', ['CN', 'JP'], 50, 1284.0,
        [('下载量 +30% ×3', 'up')], [('CN', 79.3, 103.1)], '警告文案'))
    check('SkillPage', lambda: (lambda p: (p.ensure_cards(['push_song', 'algo_top']),
                                           p.set_compute(1284),
                                           p.set_sort_visual('profit')))(S.SkillPage()))
    check('SkillPageCard', lambda: S.SkillPageCard().update(
        None, '↑↑', '主动推送', '1', [('a', 'up')], 'desc', 28, '46.2M', '1.65M',
        [0.1] * 12, 'ready', '就绪', '投放到 CN', True, '当前选中国家：中国 CN'))
    def t_skill_preview_click():
        # 守卫1：绑定回调签名必须是 (inst, touch)——Kivy 传 (instance, touch)。
        # 曾误写成 (touch, ...) → card 变成 touch、touch 变成 card →
        # card.collide_point 不存在 → 点击技能卡即闪退。
        import inspect
        if 'lambda inst, touch, c=card, s=sid' not in inspect.getsource(S):
            raise AssertionError(
                "on_touch_down 回调签名必须是 (inst, touch)（Kivy 传 instance,touch）")
        # 守卫2：卡体点击确实切换右侧预览
        p = S.SkillPage()
        p.ensure_cards(['push_song', 'algo_top', 'stealth'])
        p.preview._sid = None

        class _Card:
            class btn:
                @staticmethod
                def collide_point(x, y):
                    return False

            @staticmethod
            def collide_point(x, y):
                return True

        class _Touch:
            pos = (10, 10)

        p._card_select(_Touch(), _Card(), 'algo_top')
        if p.preview._sid != 'algo_top':
            raise AssertionError(f"点击卡未切换预览：{p.preview._sid}")
    check('SkillPage 点击卡切换预览 + 回调签名守卫', t_skill_preview_click)
    check('TechPage', lambda: (lambda p: (p.ensure_slots(tech_tree.TECH_TREE,
                                                         lambda s: None),
                                          p.set_main_action('升级', lambda: None)))(S.TechPage()))
    check('BranchCard', lambda: S.BranchCard().update(
        '南亚语系', '已选定', 'up', 'SA', 'desc',
        [('L1', '40', 'done'), ('L2', '80', 'done'), ('L3', '150', 'can')],
        'foot', 'orange', picked=True, dim=False))
    check('SlotRow', lambda: S.SlotRow('L', '本地化', 'T0 ■', state='done'))
    check('LvRow', lambda: S.LvRow('L1', '40', 'can'))
    check('LinkBar', lambda: S.LinkBar(True))
    check('AchPage', lambda: (lambda p: p.rebuild(
        [('1', 'n', 'd', True, False)] * 20, 7, 20, 5, 13, 2, 7, 3,
        [('全球通吃', '12/20')]))(S.AchPage()))
    check('HelpPage', lambda: S.HelpPage())
    check('SettingsPage', lambda: (lambda p: p.rebuild_slots(
        [('槽位 01', 'x', True)]))(S.SettingsPage()))
    check('LogDrawer', lambda: (lambda d: (d.rebuild([{'tick': 24, 'text': 'hi', 'tone': 'w'}], 2)))(S.LogDrawer()))

    print("\n=== 语言切换回归（所有组件在 EN 下重建一遍）===")
    i18n.set_lang('en')
    check('EN InspectorPanel', lambda: S.InspectorPanel().update(
        engine.player_countries[0], stats, 500.0, 41.0))
    check('EN SkillPage', lambda: S.SkillPage())
    check('EN TechPage', lambda: (lambda p: p.ensure_slots(tech_tree.TECH_TREE,
                                                           lambda s: None))(S.TechPage()))
    check('EN AchPage', lambda: S.AchPage())
    check('EN HelpPage', lambda: S.HelpPage())
    check('EN SettingsPage', lambda: S.SettingsPage())
    check('EN LogDrawer', lambda: S.LogDrawer())
    i18n.set_lang('zh')

    print()
    if FAILED:
        print(f"× {len(FAILED)} 项失败: {FAILED}")
        return 1
    print("■ 全部组件实例化通过")
    return 0


if __name__ == '__main__':
    code = main()
    Window.close()
    sys.exit(code)
