"""
make_screenshots.py - 生成 README / 分享包里用的 3 张「真实截图」

    py -3.12 demo/make_screenshots.py

产出（覆盖 demo/ 下同名文件）：
    screenshot_menu.png          主菜单（F01）
    screenshot_game.png          游戏主界面（像素世界地图 + 20 面像素国旗 + 区域页签）
    screenshot_achievements.png  成就列表弹窗

!️ 两个已知坑（务必保留）：
  1. 窗口物理宽度必须能被 4 整除（这里 1440），否则 Window.screenshot 抓出来的
     RGBA 行会整体错位、颜色被循环移位（海面 #0d1117 会变成 (17,23,13) 等）。
  2. Kivy 的 Window.screenshot(name=...) 会自动追加 0001 序号，所以先抓到临时名
     再 os.replace 成目标文件名。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from kivy.config import Config
Config.set('graphics', 'width', '1440')      # !️ 必须被 4 整除
Config.set('graphics', 'height', '880')

import engine
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window

import main as M


def _rename_later(name_base, target, delay=0.4):
    """Kivy 会把 `name` 拼成 `<base>0001.png`；这里抓完改回目标文件名

    !️ name 必须带扩展名：Kivy 用 `name.split('.')[-1]` 取扩展名，
       若传 '_shot_menu'（无点）会被拼成 `0001._shot_menu`（无扩展名文件）。
    """
    def _do(*_):
        for i in range(1, 100000):
            cand = '%s%04d.png' % (name_base, i)
            if os.path.exists(cand):
                if os.path.exists(target):
                    os.remove(target)
                os.replace(cand, target)
                print('   [img] %s' % os.path.basename(target))
                return
        print('   !️ 未找到截图文件：%s*' % name_base)
    Clock.schedule_once(_do, delay)


def snap(name_base, target):
    """请求抓一帧（Kivy 会存成 <name_base>0001.png，稍后改名为 target）"""
    Window.screenshot(name=name_base + '.png')
    _rename_later(name_base, target)


class ShotApp(App):
    def build(self):
        os.chdir(_HERE)                       # 截图路径相对 demo/
        self.root_view = M.RootView()
        Clock.schedule_once(self._menu, 1.2)
        return self.root_view

    # ---- 1) 主菜单 ----
    def _menu(self, *_):
        snap('_shot_menu', 'screenshot_menu.png')
        Clock.schedule_once(self._game, 1.6)

    # ---- 2) 游戏主界面 ----
    def _game(self, *_):
        self.root_view.start_new_game()
        Clock.schedule_once(self._play, 1.0)

    def _play(self, *_):
        ui = self.root_view.game
        # 新手引导会在开局自动弹出，会挡住地图 —— 截图前直接结束它，
        # 否则「游戏主界面」这张图永远只能拍到引导弹窗。
        try:
            tut = getattr(ui, 'tutorial', None)
            if tut is not None:
                # skip() 走的是「玩家点跳过」的同一条路径（会 _teardown 掉遮罩）
                tut.skip()
        except Exception as e:
            print('   !️ 关闭引导失败（不影响截图）：%s' % e)
        # 先跑一段，让地图有「已解锁 / 未解锁 / 阻止中」三种状态同框
        import random
        random.seed(7)
        for _ in range(24):
            engine.tick_one_round()
        ui.toggle_pause()                       # 暂停，免得更新的数值把画面搅乱
        engine.select_country('CN')             # 选中中国（大陆 + 周边高亮）
        ui.select_region('asia')                # 亚洲页签高亮（amber）
        for c in engine.player_countries:       # 造一个「阻止中」的国家
            if c.config.code == 'GB':
                c.unlocked = True
                c.current_block_intensity = 0.62
        ui.refresh_all()
        Clock.schedule_once(self._shot_game, 1.6)

    def _shot_game(self, *_):
        snap('_shot_game', 'screenshot_game.png')
        Clock.schedule_once(self._achv, 1.0)

    # ---- 3) 成就弹窗 ----
    def _achv(self, *_):
        self.root_view.game.show_achievements()
        Clock.schedule_once(self._shot_achv, 1.4)

    def _shot_achv(self, *_):
        snap('_shot_achv', 'screenshot_achievements.png')
        Clock.schedule_once(lambda *_: self.stop(), 1.4)


if __name__ == '__main__':
    print('[img]  生成真实截图 → demo/')
    ShotApp().run()
    print('■ 完成')
