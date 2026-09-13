"""开场动画「跳过」契约守卫（intro.py）

为什么要单开一个文件：test_build.py 已顶到 800 行门禁，且「跳过契约」是
独立关注点。玩家反馈「想要跳过按键」后定死四条规则，任何一条被改回去
（任意键跳过 / 1s 延迟 / 按钮淡入 / 点击无效）都要在这里被拦下：

  1) 键盘只认 ESC / 空格 / 回车 —— 任意键跳过的旧行为会「手碰键盘就掐动画」；
  2) 无解锁延迟 —— 动画一开始（第一帧）键盘就能跳过；
  3) 点击屏幕任意处也能跳过，且跳过按钮自身不双触发、不失效；
  4) 跳过按钮一开场就可见（opacity=1 / disabled=False / 文案带键位提示）。

运行：``python test_intro_skip.py``
（必须带 KIVY_NO_FILELOG=1，否则 Kivy import 阶段 purge_logs() 会抛 OSError）
"""
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ.setdefault('KIVY_NO_FILELOG', '1')
os.environ.setdefault('KIVY_WINDOW', 'sdl2')

import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import i18n                # noqa: E402
import intro               # noqa: E402
from kivy.uix.widget import Widget   # noqa: E402

SRC = open(os.path.join(HERE, 'intro.py'), encoding='utf-8').read()

print(" 开场动画跳过契约守卫")

# ------------------------------------------------------------
# 1) 键位：只认 ESC / 空格 / 回车（静态契约）
# ------------------------------------------------------------
for _n in ('escape', 'spacebar', 'enter'):
    assert "'%s'" % _n in SRC, f"intro.py 跳过键位缺 {_n}"
assert 'SKIP_KEY_NAMES' in SRC and 'SKIP_KEY_CODES' in SRC, \
    "intro.py 应显式声明跳过键位表（键名 + 扫描码）"
# 「任意键跳过」的旧判定：把按钮 disabled 当开关 —— 必须彻底消失
assert 'if not self.skip_btn.disabled' not in SRC, \
    "intro.py 仍是「任意键跳过」（旧 disabled 开关判定），应只认 ESC/空格/回车"
# 1s 解锁延迟的常量与解锁方法都不该存在
assert 'SKIP_UNLOCK_AT' not in SRC, \
    "intro.py 仍有 SKIP_UNLOCK_AT（1s 后才可跳过），与「立刻可跳过」冲突"
assert 'def _unlock_skip' not in SRC, "解锁跳过的方法应已删除"
assert not hasattr(intro, 'SKIP_UNLOCK_AT'), "intro 模块仍暴露 SKIP_UNLOCK_AT"
# test_build 的源码扫描契约仍要成立（方法名不能改）
for _n in ('def on_touch_down', 'self._finish()'):
    assert _n in SRC, f"intro.py 缺 {_n}（test_build.py 的源码断言依赖它）"
# 触摸必须先进子控件，否则跳过按钮永远收不到点击（旧实现的死按钮坑）
assert 'super().on_touch_down(touch)' in SRC, \
    "on_touch_down 必须先把触摸派发给子控件，否则跳过按钮失效"
print("   ■ 1) 键位契约：只认 ESC/空格/回车，无「任意键」判定、无延迟常量")

# ------------------------------------------------------------
# 2) + 4) 构造即得：按钮立刻可见可点，无淡入 / 无 1s 延迟
# ------------------------------------------------------------
player = intro.IntroPlayer(on_done=lambda: None)
assert player.skip_btn.disabled is False, \
    "跳过按钮必须一开场就可点（不得 disabled 等解锁）"
assert player.skip_btn.opacity == 1, \
    "跳过按钮必须一开场就可见（不得 opacity=0 淡入）"
assert player._done is False, "刚构造的播放器不应是已收尾状态"
assert 'ESC' in player.skip_btn.text, \
    f"跳过按钮文案应带键位提示，实际: {player.skip_btn.text!r}"
print(f"   ■ 2) 构造即得：disabled={player.skip_btn.disabled} "
      f"opacity={player.skip_btn.opacity} 文案={player.skip_btn.text!r}")

# ------------------------------------------------------------
# 1) 键位判定：三键命中，其余键不命中（含回退扫描码 / 畸形入参）
# ------------------------------------------------------------
for _kc in ((27, 'escape'), (32, 'spacebar'), (13, 'enter')):
    assert player._is_skip_key(_kc), f"{_kc} 应能跳过"
for _kc in ((97, 'a'), (113, 'q'), (276, 'right'), (303, 'rctrl'),
            (1073741903, 'f1'), (8, 'backspace')):
    assert not player._is_skip_key(_kc), f"{_kc} 不应跳过（只认三键）"
# 后端只给扫描码 / 键名为空时仍要认
assert player._is_skip_key((27, None)), "扫描码回退失败：ESC 应能跳过"
assert player._is_skip_key((32, '')), "扫描码回退失败：空格 应能跳过"
assert not player._is_skip_key((97, None)), "字母键扫描码不应跳过"
# 畸形入参不抛、判为「不跳过」
for _bad in (None, (), (None, None), 'escape', 27):
    assert not player._is_skip_key(_bad), f"畸形入参 {_bad!r} 不应判为跳过键"

# 键盘回调：ESC/空格/回车 触发跳过，其余键不触发
_calls = []
player._finish = lambda *_a: _calls.append('finish')
for _kc in ((27, 'escape'), (32, 'spacebar'), (13, 'enter')):
    _calls.clear()
    assert player._on_key_down(None, _kc, '', []) is True, f"{_kc} 应返回已消费"
    assert _calls == ['finish'], f"{_kc} 应触发跳过"
for _kc in ((97, 'a'), (276, 'right')):
    _calls.clear()
    assert player._on_key_down(None, _kc, '', []) is False, f"{_kc} 应返回未消费"
    assert _calls == [], f"{_kc} 不应触发跳过"
print("   ■ 3) 键位判定：ESC/空格/回车 跳过，其余键不响应，畸形入参不抛")


# ------------------------------------------------------------
# 3) 点击任意处跳过（且子控件已消费时不双触发）
# ------------------------------------------------------------
class _Touch(object):
    """最小触摸替身：只带 on_touch_down 会读到的字段。"""

    def __init__(self, x=5, y=5, button='left', scrolling=False):
        self.x, self.y = x, y
        self.pos = (x, y)
        self.button = button
        self.is_mouse_scrolling = scrolling
        self.ud = {}

    def grab(self, *_a):
        pass

    def ungrab(self, *_a):
        pass


# 3a) 空白区域：无子控件消费 → 跳过 + 仍然吞掉（防穿透）
player.clear_widgets()
_calls.clear()
assert player.on_touch_down(_Touch()) is True, \
    "on_touch_down 必须返回 True 吞掉触摸（防穿透主菜单误触）"
assert _calls == ['finish'], "点击任意处应跳过"

# 3b) 子控件已消费（跳过按钮路径）→ 不得二次触发
class _Sink(Widget):
    def on_touch_down(self, touch):
        return True


_player2 = intro.IntroPlayer(on_done=lambda: None)
_calls2 = []
_player2._finish = lambda *_a: _calls2.append('finish')
_player2.clear_widgets()
_player2.add_widget(_Sink())
assert _player2.on_touch_down(_Touch()) is True, "子控件消费后仍要吞掉触摸"
assert _calls2 == [], \
    "子控件已消费（点中跳过按钮）时不得二次触发跳过（会重复音效/回调）"

# 3c) 滚轮 / 右键只吞不跳，防误触
_calls.clear()
assert player.on_touch_down(_Touch(scrolling=True)) is True
assert _calls == [], "滚轮不应跳过"
assert player.on_touch_down(_Touch(button='right')) is True
assert _calls == [], "右键不应跳过"
print("   ■ 4) 点击：空白区跳过 / 按钮区不双触发 / 滚轮·右键只吞不跳")

# ------------------------------------------------------------
# 双语：intro_skip 两个语言都要带键位提示，且不能出现缺字形符号
# ------------------------------------------------------------
for _lang in (i18n.LANG_ZH, i18n.LANG_EN):
    i18n.set_lang(_lang)
    _txt = i18n.t('intro_skip')
    assert 'ESC' in _txt, f"i18n[{_lang}].intro_skip 应带键位提示: {_txt!r}"
    for _bad in ('⏭', '⏩'):
        assert _bad not in _txt, \
            f"i18n[{_lang}].intro_skip 含缺字形符号 {_bad}（MicrosoftYaHei 无此字形）"
i18n.set_lang(i18n.LANG_ZH)
print("   ■ 5) 双语：intro_skip 中英文案均带 (ESC) 提示、无缺字形符号")

print("\n 全部通过 - 开场动画跳过契约成立（三键 / 无延迟 / 点击即跳 / 立即可见）")
