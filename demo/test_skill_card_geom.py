"""test_skill_card_geom.py - 技能页卡片几何回归守卫（方案 A「整页滚动」）

背景 bug（本轮修复）：
    技能页 3×4 网格在窄窗 / 矮窗下把卡片**压扁**，三处「半截字」：
      (a) 名字被右上状态芯片遮住 —— 行高被父容器均分挤压；
      (c) 说明第 3 行被裁 —— DESC 盒高 48 只够 2 行（msyh 行高 ≈24px）；
      (d) 底栏预览文案折成两行塞进 22px 盒 —— 上下一半被裁成「半截字」。

方案 A（已实施）：
    把 3×N 网格放进 ScrollView，网格 size_hint_y=None + minimum_height→height，
    行高恒等于 SkillPageCard.CARD_H（不再随窗口高度均分挤压），放不下就纵向滚动。
    同时 DESC 盒高 48 → 72（3 行容量）、去掉底栏全弹性 spacer、底栏改单行 shorten。

本测试在三档窗口宽 × 4 行下断言（离线可跑，不需要真机交互）：
    1. 每张卡高度 == CARD_H（不被挤压）；
    2. 说明 lbl_desc 的纹理高 ≤ 盒高（不裁字）；
    3. 底栏 lbl_ft 只有一行（纹理高 < 两行）；
    4. 卡片正文盒无溢出（BODY_OVERFLOW 为空）。

跑法：
    python test_skill_card_geom.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.config import Config
Config.set('graphics', 'resizable', '1')
Config.set('graphics', 'width', '1680')     # ! 宽度必须能被 4 整除
Config.set('graphics', 'height', '980')

from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.clock import Clock

for _fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(_fp):
        try:
            LabelBase.register(name='MicrosoftYaHei', fn_regular=_fp)
            LabelBase.register(name='Roboto', fn_regular=_fp)
        except Exception:
            pass

import i18n
import ui_v4 as U
import ui_v4_screens as S
from data import SKILLS, SKILL_ORDER
from ui_v4_cards import SkillPageCard

# 三档窗口（同一 1680×980 设计的三级缩放，等价逻辑宽 1680 / 2100 / 2520）
WINDOWS = ((1680, 980), (2100, 1225), (2520, 1470))

# 底栏最坏情况：真实预览文案（code 现算），≈ 250px，窄卡里必超一行
FOOT_WORST = "怀疑 0→0 · 算力 100→104 · 距危机 80"

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


def _real_desc(sid: str) -> str:
    """复刻 ui_pages._fill_skill_card 的说明文案：detail 行 + 收益/消耗行。

    两行都由代码现算（i18n + data.SKILLS），因此测试用的是**真实文案**，
    不是手写样例 —— 文案改长导致裁字时本测试会立刻报警。
    """
    sk = SKILLS[sid]
    benefit = []
    if sk.downloads_mult > 1.0:
        benefit.append(f"下载 ×{sk.downloads_mult:.2f}")
    if sk.compute_mult > 1.0:
        benefit.append(f"偷算力 ×{sk.compute_mult:.1f}")
    if sk.stealth_ratio_mult > 1.0 or sk.stealth_ratio_bonus > 0:
        if sk.stealth_ratio_mult > 1.0:
            benefit.append(f"偷算力比 ×{sk.stealth_ratio_mult:.1f}")
        if sk.stealth_ratio_bonus > 0:
            benefit.append(f"偷算力比 +{sk.stealth_ratio_bonus * 100:.0f}%")
    if sk.suspicion_mult < 1.0:
        benefit.append(f"怀疑增速 ×{sk.suspicion_mult:.1f}")
    cost = f"算力 {sk.cost:.0f}"
    if sk.suspicion_delta > 0:
        cost += f" · 怀疑 +{sk.suspicion_delta:.0f}%"
    detail = i18n.t(f'sk_detail_{sid}')
    bc = (f"[color={U.MK['cyan']}]{i18n.t('sk_benefit')}[/color] "
          f"{' · '.join(benefit) or '—'}    "
          f"[color={U.MK['red']}]{i18n.t('sk_cost')}[/color] {cost}")
    return f"{detail}\n{bc}"


def _build_page(W: float, H: float) -> S.SkillPage:
    """造一张满配技能页：10 张卡 + 真实说明/底栏文案，钉死尺寸。"""
    p = S.SkillPage()
    p.size_hint = (None, None)
    p.size = (W, H)
    p.pos = (0, 0)
    p.ensure_cards(SKILL_ORDER)
    for sid, card in p.cards.items():
        card.update(SKILLS[sid], '↑↑', f"技能·{sid}", '1',
                    [('算力 20', 'cost'), ('CD 4', 'plain')],
                    _real_desc(sid), 3, '12.0M', '4.00M', [0.2] * 12,
                    'ready', '就绪', '投放到 CN', True, FOOT_WORST)
    return p


def _ref_line_h() -> float:
    """参考单行行高（当前字号下），用于判定底栏是否折成两行。"""
    lbl = U.mk_label('Ag', font_size=U.FS_CAP)
    lbl.texture_update()
    return float(lbl.texture_size[1])


def _force_layout(w, depth: int = 0) -> None:
    if depth > 16:
        return
    if hasattr(w, 'do_layout'):
        try:
            w.do_layout()
        except Exception:
            pass
    for ch in list(getattr(w, 'children', ()) or ()):
        _force_layout(ch, depth + 1)


def _settle(page, times: int = 4) -> None:
    """反复「布局 + 跑一帧」，让 ScrollView/网格/文字纹理收敛。"""
    for _ in range(times):
        _force_layout(page)
        Clock.tick()


def _body_overflow(card) -> float:
    """卡片正文盒（BoxLayout）的溢出像素：>0 表示固定高子段塞不下。"""
    body = card._body
    kids = list(body.children)
    req = sum(getattr(c, 'height', 0) for c in kids)
    req += body.padding[1] + body.padding[3]
    req += body.spacing * max(len(kids) - 1, 0)
    return req - body.height


def _natural_h(label, lift_maxlines: bool = False) -> float:
    """量标签在当前宽度下「换行后真正需要」的高度。

    ⚠️ 不能直接读 label.texture_size[1]：盒高固定时 Kivy 把纹理按 text_size
       的高度补齐，读出来恒等于盒高（72），任何裁字都测不出来。必须临时把
       text_size 的高置 None（只按宽度换行、高度自由增长）再量。
    """
    saved_ts = label.text_size
    saved_ml = label.max_lines
    saved_sh = label.shorten
    try:
        if lift_maxlines:
            label.max_lines = 0
            label.shorten = False
        label.text_size = (saved_ts[0], None)
        label.texture_update()
        return float(label.texture_size[1])
    finally:
        label.max_lines = saved_ml
        label.shorten = saved_sh
        label.text_size = saved_ts
        label.texture_update()


def _case(W: float, H: float, line_h: float):
    def run():
        page = _build_page(W, H)
        _settle(page)
        grid = page._grid
        cards = list(page.cards.values())

        # 0) 网格行高固定：minimum_height == 4 行 CARD_H + 3 间距
        rows = -(-len(cards) // grid.cols)
        want_min = rows * SkillPageCard.CARD_H + (rows - 1) * grid.spacing[1]
        assert abs(grid.minimum_height - want_min) < 1.0, (
            f"grid.minimum_height={grid.minimum_height:.1f} ≠ {want_min:.1f}")

        body_over = []
        max_desc_need = max_foot_need = 0.0
        for sid in SKILL_ORDER:
            card = page.cards[sid]
            # 1) 卡高固定（不被父容器均分挤压 —— 方案 A 的核心保证）
            assert abs(card.height - SkillPageCard.CARD_H) < 0.5, (
                f"{sid}: 卡高 {card.height:.1f} ≠ CARD_H {SkillPageCard.CARD_H}")
            # 2) 说明不裁字：换行后真正需要的高度 ≤ 盒高
            desc_need = _natural_h(card.lbl_desc)
            max_desc_need = max(max_desc_need, desc_need)
            assert desc_need <= card.lbl_desc.height + 0.5, (
                f"{sid}: 说明需 {desc_need:.1f}px > 盒高 "
                f"{card.lbl_desc.height:.1f}px（裁字）")
            # 3) 底栏：硬性单行 + 省略号 + 单行放得进盒高 + 未被 spacer 挤半宽
            ft = card.lbl_ft
            assert ft.max_lines == 1, f"{sid}: 底栏 max_lines={ft.max_lines} ≠ 1"
            assert ft.shorten is True, f"{sid}: 底栏未开 shorten（应省略号截断）"
            assert line_h <= ft.height + 0.5, (
                f"{sid}: 单行 {line_h:.1f}px > 盒高 {ft.height:.1f}px（纵向裁字）")
            assert ft.width >= 0.55 * card.width, (
                f"{sid}: 底栏宽 {ft.width:.0f} < 0.55×卡宽 {card.width:.0f}"
                f"（疑似被弹性 spacer 挤半）")
            max_foot_need = max(max_foot_need, _natural_h(ft, lift_maxlines=True))
            # 4) 正文盒不溢出
            if _body_overflow(card) > 0.5:
                body_over.append((sid, round(_body_overflow(card), 1)))

        if body_over:
            raise AssertionError(f"BODY_OVERFLOW 非空：{body_over}")

        if os.environ.get('GEOM_DEBUG'):
            for sid in SKILL_ORDER:
                c = page.cards[sid]
                lab = c.lbl_desc
                full = _real_desc(sid)
                # 强制窄宽（250）再量一次：看它到底会不会换行
                _st = lab.text_size
                lab.text_size = (250, None)
                lab.texture_update()
                narrow = float(lab.texture_size[1])
                lab.text_size = _st
                lab.texture_update()
                print(f"           · {sid:12s} 宽={lab.width:.0f} 需={_natural_h(lab):5.1f}"
                      f" 窄250需={narrow:5.1f} len={len(full)}")
                print(f"               {full!r}")

        print(f"         卡宽≈{cards[0].width:.0f}  说明宽 {cards[0].lbl_desc.width:.0f}"
              f"  说明需 {max_desc_need:.0f}/{cards[0].lbl_desc.height:.0f}px"
              f"  底栏自然 {max_foot_need:.0f}px（盒 {cards[0].lbl_ft.height:.0f}）"
              f"  底栏宽 {cards[0].lbl_ft.width:.0f}/{0.55 * cards[0].width:.0f}"
              f"  BODY_OVERFLOW=[]")
    return run


def main() -> int:
    i18n.set_lang('zh')
    line_h = _ref_line_h()
    print(f"\n# 参考单行行高 = {line_h:.1f}px（FS_CAP）")
    print(f"# CARD_H={SkillPageCard.CARD_H}  DESC_H={SkillPageCard.DESC_H}  "
          f"HEAD_H={SkillPageCard.HEAD_H}  FOOT_H={SkillPageCard.FOOT_H}")
    print("\n=== 技能页卡片几何（方案 A 整页滚动）===")
    for (W, H) in WINDOWS:
        check(f"技能页几何 @ {W}×{H}", _case(W, H, line_h))

    # EN 也过一遍：英文说明更长，最容易顶到 DESC 上限
    i18n.set_lang('en')
    line_h = _ref_line_h()
    print("\n=== EN 文案回归（更长的英文说明）===")
    for (W, H) in WINDOWS:
        check(f"EN 技能页几何 @ {W}×{H}", _case(W, H, line_h))
    i18n.set_lang('zh')

    print()
    if FAILED:
        print(f"× {len(FAILED)} 项失败: {FAILED}")
        return 1
    print("■ 技能页卡片几何全部达标（三档宽度 × 4 行，zh + en）")
    return 0


if __name__ == '__main__':
    code = main()
    Window.close()
    sys.exit(code)
