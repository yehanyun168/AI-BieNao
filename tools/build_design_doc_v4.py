# -*- coding: utf-8 -*-
"""
build_design_doc_v4.py —— 生成《AI 别闹》像素风交互界面设计稿 v0.4

与 build_design_doc.py（生成 v0.3）的区别：
  v0.3 是「把 v0.2 打补丁升级」，v0.4 是重做交互，所以改成
  **分片模板 + 资源注入** 的方式重建，不再依赖 v0.2 的 HTML。

输入：
  design/v4_src/00_head.html            样式与令牌 + 屏幕切换器
  design/v4_src/10_screens_main.html    S01 主菜单 / S02 主界面 / S03 国家检视 / S04 技能投放
  design/v4_src/20_screens_panels.html  S05 技能页 / S06 科技树页
  design/v4_src/30_screens_modals.html  S07–S14 事件 / 危机 / 结局 / 成就 / 帮助 / 设置 / 图层 / 日志
  design/v4_src/90_tail.html            规格附录 + 原型交互脚本
  design/pixel_map_assets.json          像素地图与国旗资源（由 tools/gen_pixel_map.py 生成）

输出：
  design/ui_design_v0.4.html            单文件、自包含、可离线打开

用法：
  python tools/build_design_doc_v4.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
DESIGN = os.path.join(ROOT, 'design')
SRC = os.path.join(DESIGN, 'v4_src')
DST = os.path.join(DESIGN, 'ui_design_v0.4.html')

PARTS = [
    '00_head.html',
    '10_screens_main.html',
    '20_screens_panels.html',
    '30_screens_modals.html',
    '90_tail.html',
]

# 地图四态：fill / edge（与 pixel_ui.COLORS、world_map.STATE_* 同源）
FO = {
    'on':  ('#1f6f63', '#3ec9ac'),
    'sel': ('#4ec9b0', '#eafffb'),
    'blk': ('#5c2323', '#ef4444'),
    'lk':  ('#232a30', '#4a5560'),
}
# 标签文字色（在深色标签底上必须够亮）
TEXT_COLOR = {
    'on': '#8ff0da', 'sel': '#eafffb', 'blk': '#ffb4b4', 'lk': '#b6c2cd',
}


def load_parts():
    chunks = []
    for name in PARTS:
        p = os.path.join(SRC, name)
        with open(p, encoding='utf-8') as f:
            chunks.append(f.read())
        print('   + %-28s %7d chars' % (name, os.path.getsize(p)))
    return '\n'.join(chunks)


def contour_path(points):
    """把轮廓点列（格中心坐标）转成闭合的 SVG path"""
    if not points:
        return ''
    d = ['M%.1f %.1f' % (points[0][0], points[0][1])]
    for x, y in points[1:]:
        d.append('L%.1f %.1f' % (x, y))
    d.append('Z')
    return ''.join(d)


def build_map(assets, idx):
    """生成一张可交互的像素世界地图 SVG（每个国家是一段独立可点的 <g>）"""
    countries = assets['countries']
    anchors = assets['anchors']
    labels = assets['labels']

    # --- 国家地块（先填充后国界：国界游程是填充的子集，反了会被盖住）---
    cells = []
    for c in countries:
        code, st, name = c['c'], c['st'], c['n']
        f, b = FO[st]
        ring = contour_path(assets['contours'].get(code) or [])
        cells.append(
            '      <g class="cnt" data-c="%s" data-n="%s" tabindex="0" role="button" '
            'aria-label="%s %s">' % (code, name, name, code))
        cells.append('        <path class="px" d="%s" fill="%s"/>'
                     % (assets['fills'][code], f))
        cells.append('        <path class="px" d="%s" fill="%s"/>'
                     % (assets['borders'][code], b))
        if ring:
            cells.append('        <path class="hitring" d="%s" fill="none" '
                         'stroke="#dcdcaa" stroke-width="0.55"/>' % ring)
        cells.append('      </g>')

    # --- 引导线 + 国家码标签 ---
    labs = []
    for c in countries:
        code, st = c['c'], c['st']
        ax, ay = anchors[code]
        lx, ly = labels[code]
        _, b = FO[st]
        t = TEXT_COLOR[st]
        w = 4.6 if code != 'CN' else 5.4
        h = 3.4
        if abs(lx - ax) > 2.6 or abs(ly - ay) > 2.6:
            labs.append('      <path d="M%.1f %.1f L%.1f %.1f" fill="none" stroke="%s" '
                        'stroke-width="0.22" opacity=".7"/>' % (ax, ay, lx, ly, b))
        labs.append('      <rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                    'fill="#0b1218" stroke="%s" stroke-width="0.3"/>'
                    % (lx - w / 2, ly - h / 2, w, h, b))
        labs.append('      <rect x="%.1f" y="%.1f" width="1.1" height="1.1" fill="%s"/>'
                    % (ax - 0.55, ay - 0.55, b))
        labs.append('      <text x="%.1f" y="%.1f" font-size="2.2" fill="%s" '
                    'text-anchor="middle" dominant-baseline="central" '
                    'letter-spacing="0.1">%s</text>' % (lx, ly + 0.1, t, code))

    return '''<svg class="world map-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet"
       role="img" aria-label="像素风世界地图：20 个可玩国家，按解锁状态着色，可点击查看详情">
  <defs>
    <pattern id="seaGrid{n}" width="4" height="4" patternUnits="userSpaceOnUse">
      <path d="M4 0H0V4" fill="none" stroke="#12293c" stroke-width="0.16"/>
    </pattern>
  </defs>
  <rect width="{W}" height="{H}" fill="#0a1828"/>
  <rect width="{W}" height="{H}" fill="url(#seaGrid{n})"/>
  <g class="px">
    <path d="{land}" fill="#16323c"/>
    <path d="{coast}" fill="#27505b"/>
  </g>
  <g class="px">
{cells}
  </g>
  <g>
{labs}
  </g>
</svg>'''.format(W=assets['grid']['w'], H=assets['grid']['h'], n=idx,
                 land=assets['land'], coast=assets['coast'],
                 cells='\n'.join(cells), labs='\n'.join(labs))


def main():
    print('📐 读取分片模板…')
    html = load_parts()

    print('🗺  读取像素地图资源…')
    with open(os.path.join(DESIGN, 'pixel_map_assets.json'), encoding='utf-8') as f:
        assets = json.load(f)
    print('   grid %dx%d · 20 国 · 轮廓 %d 段'
          % (assets['grid']['w'], assets['grid']['h'], len(assets['contours'])))

    # 1) 国旗雪碧图（必须落在 <body> 里，放 <head> 不渲染）
    assert html.count('<!--SPRITE-->') == 1, '应有且仅有 1 处雪碧图占位'
    html = html.replace('<!--SPRITE-->', assets['sprite'])

    # 2) 地图：每一处占位注入一份完整 SVG（pattern id 加序号避免重复）
    n_map = html.count('<!--MAP-->')
    assert n_map >= 1, '至少要有一处地图占位'
    counter = [0]

    def _sub(_m):
        counter[0] += 1
        return build_map(assets, counter[0])

    html = re.sub(r'<!--MAP-->', _sub, html)
    print('   ⤷ 注入地图 %d 处' % counter[0])

    # 3) 自检：关键标记必须存在
    checks = {
        '屏幕切换器': 'id="switcher"',
        'S02 主界面': 'id="s02"',
        'S03 国家检视': 'id="s03"',
        'S04 技能投放': 'id="s04"',
        'S05 技能页': 'id="s05"',
        'S06 科技树页': 'id="s06"',
        'S07 事件弹窗': 'id="s07"',
        'S09 结局弹窗': 'id="s09"',
        'S10 成就面板': 'id="s10"',
        'S13 图层': 'id="s13"',
        'S14 日志': 'id="s14"',
        '语义边框令牌': '--border-strong:#6e7681',
        '分段感染条': 'class="segbar"',
        '投放准星': 'class="reticle"',
        '国旗引用': '#flag-cn',
        '地图国家块': 'class="cnt"',
    }
    bad = [k for k, v in checks.items() if v not in html]
    assert not bad, '缺少关键标记：%s' % bad

    # 4) 无障碍红线：<style> 块里不得出现 outline:none（正文提到「禁止 outline:none」不算）
    css = '\n'.join(re.findall(r'<style>(.*?)</style>', html, re.S))
    offenders = re.findall(r'outline\s*:\s*none', css)
    assert not offenders, 'CSS 中出现 outline:none，违反焦点可见规范'
    # 反向确认：焦点环规范本身必须在样式里
    assert 'outline:2px solid var(--cyan)' in css, '缺少焦点环样式'

    with open(DST, 'w', encoding='utf-8') as f:
        f.write(html)

    print('\n✅ 写出 %s' % DST)
    print('   %d chars (%.1f KB)'
          % (len(html), os.path.getsize(DST) / 1024.0))
    print('   <section class="scr"> 共 %d 屏' % html.count('<section class="scr"'))
    print('   <svg class="world map-svg"> 共 %d 张地图'
          % html.count('<svg class="world map-svg"'))
    print('   自检 %d 项标记全部命中' % len(checks))


if __name__ == '__main__':
    main()
