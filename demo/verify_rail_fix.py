"""verify_rail_fix.py —— 验证「实机看不到科技树」修复。

根因：RailBar.__init__ 曾设 self.opacity = 0，Kivy 的 opacity 会连子按钮一起
乘成透明，导致整条右侧 rail（含 tech 按钮）永久不可见。本脚本离屏构建游戏，
断言：
  * rail.opacity == 1.0（不再被隐藏）
  * 6 个 rail 按钮 opacity 均 == 1.0
  * tech 按钮的文字标签含 i18n 文案（科技 / Tech）

用法：
    python verify_rail_fix.py
"""
import os
import sys

# 不强制 SDL_VIDEODRIVER：沙箱默认后端可用，强制 dummy 会因无 OpenGL 而失败
os.environ.setdefault('KIVY_NO_FILELOG', '1')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from kivy.config import Config  # noqa: E402

# 沙箱虚拟显示尺寸有限，用较小窗口避免 SDL 创建失败（断言不依赖窗口尺寸）
Config.set('graphics', 'width', '480')
Config.set('graphics', 'height', '300')
Config.set('graphics', 'resizable', '1')

from kivy.core.window import Window  # noqa: E402

# 先显式触发窗口创建（与最小冒烟测试一致），避免 import main 时
# 在模块级 _update_window_title() 里首次访问 Window 因状态未就绪而失败。
_ = Window.size

import main as M  # noqa: E402


def main() -> int:
    rv = M.RootView()
    rv.start_new_game()
    g = rv.game
    rail = g.rail
    if rail is None:
        print("RAIL_FIX_FAIL: g.rail is None")
        return 1

    if rail.opacity != 1.0:
        print(f"RAIL_FIX_FAIL: rail.opacity={rail.opacity} (期望 1.0)")
        return 1

    for key, b in rail.buttons.items():
        if b.opacity != 1.0:
            print(f"RAIL_FIX_FAIL: rail 按钮 {key} opacity={b.opacity}")
            return 1

    tech = rail.buttons.get('tech')
    if tech is None:
        print("RAIL_FIX_FAIL: rail 无 tech 按钮")
        return 1

    caption_ok = ('科技' in tech.text) or ('Tech' in tech.text)
    if not caption_ok:
        print(f"RAIL_FIX_FAIL: tech 按钮文案未含标签 -> {tech.text!r}")
        return 1

    print("RAIL_FIX_OK:")
    print(f"  rail.opacity   = {rail.opacity}")
    print(f"  rail 按钮数    = {len(rail.buttons)} "
          f"(keys={list(rail.buttons.keys())})")
    print(f"  tech 按钮文案  = {tech.text!r}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
