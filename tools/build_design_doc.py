# -*- coding: utf-8 -*-
"""
把 design/ui_design_v0.2.html 升级为 v0.3：
  1) 修正全部 20 面国旗（改为 <symbol> 雪碧图，修正中国/日/韩/英/澳/新/巴西/南非）
  2) 主游戏界面的地图：20 个绝对定位色块 -> 像素世界地图（真实海岸线栅格化）

前置：先跑 tools/gen_pixel_map.py 生成 design/pixel_map_assets.json
用法：python tools/build_design_doc.py
"""
import json, os, re, math

HERE = os.path.dirname(os.path.abspath(__file__))
DESIGN = os.path.abspath(os.path.join(HERE, '..', 'design'))
SRC = os.path.join(DESIGN, 'ui_design_v0.2.html')
DST = os.path.join(DESIGN, 'ui_design_v0.3.html')

assets = json.load(open(os.path.join(DESIGN, 'pixel_map_assets.json'), encoding='utf-8'))
html = open(SRC, encoding='utf-8').read()

def sub1(old, new, why):
    global html
    assert html.count(old) == 1, '命中 %d 次：%s' % (html.count(old), why)
    html = html.replace(old, new)

# ---------- 1. 旗帜雪碧图注入 <body> ----------
sub1('<body>\n', '<body>\n' + assets['sprite'] + '\n', '注入旗雪碧图')

# ---------- 2. CSS：旗帜 ----------
sub1("""  .flag{width:26px;height:17px;display:flex;border:1px solid var(--border-2);overflow:hidden;}
  .flag>div{flex:1;} .flag.v{flex-direction:column;}""",
     """  .flag{width:30px;height:20px;display:block;flex:0 0 auto;border:1px solid var(--border-2);
        background:#0d1117;overflow:hidden;}
  .flag--lg{width:48px;height:32px;border-width:2px;}""", 'CSS .flag')

sub1('.crow{display:grid;grid-template-columns:26px 1fr auto;gap:6px;align-items:center;',
     '.crow{display:grid;grid-template-columns:32px 1fr auto;gap:6px;align-items:center;', 'CSS .crow')

# ---------- 3. CSS：地图面板 ----------
sub1("""  .map{grid-area:map;position:relative;background:var(--sea);overflow:hidden;}
  .map .grid-bg{position:absolute;inset:0;
    background-image:linear-gradient(rgba(78,201,176,.05) 1px,transparent 1px),
                     linear-gradient(90deg,rgba(78,201,176,.05) 1px,transparent 1px);
    background-size:32px 32px;}
  .mlabel{position:absolute;font-size:11px;color:var(--text-mute);letter-spacing:.06em;pointer-events:none;}
  .pin{position:absolute;font-size:11px;padding:2px 5px;border:var(--bw) solid var(--border-2);
       background:rgba(13,17,23,.85);color:var(--text-dim);transform:translate(-50%,-50%);white-space:nowrap;}
  .pin.on{border-color:var(--cyan);color:var(--cyan);background:#0e2b28;}
  .pin.sel{border-color:var(--cyan);color:var(--bg);background:var(--cyan);}
  .pin.blk{border-color:var(--red);color:var(--red);background:#2a1616;}
  .map-title{position:absolute;top:6px;left:8px;font-size:var(--fs-sm);color:var(--cyan);}
  .map-legend{position:absolute;bottom:6px;left:8px;display:flex;gap:10px;font-size:11px;color:var(--text-mute);}
  .map-legend i{display:inline-block;width:9px;height:9px;border:2px solid var(--border-2);margin-right:4px;vertical-align:-1px;}""",
     """  /* 地图面板：区域页签 / 像素世界地图 / 图例 */
  .map{grid-area:map;position:relative;background:var(--sea);overflow:hidden;
       display:flex;flex-direction:column;}
  .map-head{flex:0 0 auto;display:flex;align-items:center;gap:4px;padding:4px 6px;
            border-bottom:1px solid var(--border);}
  .region{flex:0 0 auto;border:var(--bw) solid var(--border-2);background:var(--panel-2);
          color:var(--text-dim);padding:2px 7px;font-size:var(--fs-cap);cursor:pointer;}
  .region.on{border-color:var(--cyan);color:var(--cyan);background:#0e2b28;}
  .region .n{color:var(--text-mute);}
  .region.on .n{color:var(--cyan);}
  .map-canvas{flex:1 1 auto;min-height:0;display:flex;align-items:center;justify-content:center;
              padding:0 4px;}
  .map-canvas svg{width:100%;height:auto;max-height:100%;display:block;overflow:visible;}
  .map-svg .px{shape-rendering:crispEdges;}                 /* 陆地块：禁止抗锯齿，保留像素边 */
  .map-svg text{font-family:'Consolas','Courier New',monospace;text-rendering:geometricPrecision;}
  .map-foot{flex:0 0 auto;display:flex;align-items:center;gap:12px;padding:4px 8px;
            border-top:1px solid var(--border);font-size:var(--fs-cap);color:var(--text-mute);}
  .map-foot .spacer{flex:1;}
  .map-foot .pick{color:var(--text-dim);}
  .map-foot .pick b{color:var(--cyan);}
  .legend i{display:inline-block;width:9px;height:9px;border:2px solid var(--border-2);
            margin-right:4px;vertical-align:-1px;}
  .lg-on{border-color:#3ec9ac;background:#1f6f63;} .lg-sel{border-color:#eafffb;background:#4ec9b0;}
  .lg-blk{border-color:#ef4444;background:#5c2323;} .lg-lk{border-color:#4a5560;background:#232a30;}""",
     'CSS .map')

# ---------- 4. 主游戏界面的地图块 ----------
# 标签锚点：用真实经纬度的国界质心，个别（US 含阿拉斯加）手工校正到本土
ANCH = {
    'CN': (94.1, 25.0), 'JP': (105.8, 24.3), 'KR': (102.0, 25.0), 'IN': (86.1, 30.0),
    'ID': (98.4, 38.5), 'US': (27.3, 24.7), 'CA': (27.0, 12.8), 'MX': (25.0, 29.4),
    'BR': (41.9, 41.7), 'AR': (37.7, 50.8), 'GB': (58.4, 17.8), 'FR': (60.0, 21.0),
    'DE': (62.9, 18.9), 'IT': (63.4, 22.4), 'RU': (91.9, 13.3), 'NG': (62.1, 34.8),
    'EG': (69.4, 28.8), 'ZA': (68.1, 47.9), 'AU': (104.4, 46.8), 'NZ': (117.1, 52.6),
}
# 标签落点（避开重叠与大洲轮廓）
LBL = {
    'CN': (86.5, 28.0), 'JP': (111.5, 19.5), 'KR': (107.5, 27.5), 'IN': (77.5, 29.5),
    'ID': (106.0, 43.0), 'US': (16.5, 21.5), 'CA': (16.5, 9.0), 'MX': (12.5, 32.5),
    'BR': (41.5, 42.5), 'AR': (26.0, 53.5), 'GB': (47.5, 13.0), 'FR': (47.5, 22.0),
    'DE': (70.5, 14.5), 'IT': (70.5, 23.5), 'RU': (85.0, 12.5), 'NG': (51.5, 35.5),
    'EG': (63.0, 24.0), 'ZA': (73.0, 50.5), 'AU': (104.0, 47.5), 'NZ': (107.5, 55.0),
}
FO = {'on': ('#1f6f63', '#3ec9ac', '#8ff0da'),
      'sel': ('#4ec9b0', '#eafffb', '#eafffb'),
      'blk': ('#5c2323', '#ef4444', '#ffb4b4'),
      'lk': ('#232a30', '#4a5560', '#b6c2cd')}

paths = []
for c in assets['countries']:
    code, st = c['c'], c['st']
    f, b, t = FO[st]
    # ⚠️ 顺序必须「先填充后国界」：国界游程是填充的**子集**（内圈 1 格），
    #    反过来的话国界会被填充整块盖住，20 国只剩纯色块，图例里的描边色也对不上。
    paths.append('      <path class="px" d="%s" fill="%s"/>' % (assets['fills'][code], f))
    paths.append('      <path class="px" d="%s" fill="%s"/>' % (assets['borders'][code], b))

labels = []
for c in assets['countries']:
    code, st = c['c'], c['st']
    ax, ay = ANCH[code]
    lx, ly = LBL[code]
    f, b, t = FO[st]
    w = 4.6 if code != 'CN' else 5.4
    h = 3.4
    x0, y0 = lx - w / 2, ly - h / 2
    if abs(lx - ax) > 2.6 or abs(ly - ay) > 2.6:
        labels.append('      <path d="M%.1f %.1f L%.1f %.1f" fill="none" stroke="%s" '
                      'stroke-width="0.22" opacity=".7"/>' % (ax, ay, lx, ly, b))
    labels.append('      <rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#0b1218" '
                  'stroke="%s" stroke-width="0.3"/>' % (x0, y0, w, h, b))
    labels.append('      <rect x="%.1f" y="%.1f" width="1.1" height="1.1" fill="%s"/>'
                  % (ax - 0.55, ay - 0.55, b))
    labels.append('      <text x="%.1f" y="%.1f" font-size="2.2" fill="%s" text-anchor="middle" '
                  'dominant-baseline="central" letter-spacing="0.1">%s</text>'
                  % (lx, ly + 0.1, t, code))

MAP = '''  <!-- 中央：像素世界地图（120 x 60 网格 / Miller 投影 / 真实海岸线与国界） -->
  <div class="map">
    <div class="map-head">
      <span class="region on">亚洲 <span class="n">5</span></span>
      <span class="region">欧洲 <span class="n">5</span></span>
      <span class="region">美洲 <span class="n">5</span></span>
      <span class="region">非洲 <span class="n">3</span></span>
      <span class="region">大洋洲 <span class="n">2</span></span>
      <span class="spacer" style="flex:1"></span>
      <span class="muted">Tab 切大洲</span>
    </div>
    <div class="map-canvas">
      <svg class="map-svg" viewBox="0 0 120 60" preserveAspectRatio="xMidYMid meet"
           role="img" aria-label="像素风世界地图，20 个可玩国家按解锁状态着色">
        <defs>
          <pattern id="seaGrid" width="4" height="4" patternUnits="userSpaceOnUse">
            <path d="M4 0H0V4" fill="none" stroke="#12293c" stroke-width="0.16"/>
          </pattern>
        </defs>
        <rect width="120" height="60" fill="#0a1828"/>
        <rect width="120" height="60" fill="url(#seaGrid)"/>
        <g class="px">
          <path d="%(land)s" fill="#16323c"/>
          <path d="%(coast)s" fill="#27505b"/>
        </g>
        <g class="px">
%(paths)s
        </g>
        <g>
%(labels)s
        </g>
      </svg>
    </div>
    <div class="map-foot">
      <span class="legend"><i class="lg-on"></i>已解锁 11</span>
      <span class="legend"><i class="lg-sel"></i>选中 1</span>
      <span class="legend"><i class="lg-blk"></i>阻止中 1</span>
      <span class="legend"><i class="lg-lk"></i>未解锁 7</span>
      <span class="spacer"></span>
      <span class="pick">选中 <b>CN 中国</b> · 79.3M · 5.62%% · 阻止阈值 85%%</span>
    </div>
  </div>

''' % {'land': assets['land'], 'coast': assets['coast'],
       'paths': '\n'.join(paths), 'labels': '\n'.join(labels)}

start = html.index('  <!-- 中央：世界地图 -->')
end = html.index('  <!-- 右侧：科技树 -->')
html = html[:start] + MAP + html[end:]

# ---------- 5. 旗帜：div 色块 -> <use> 雪碧图 ----------
ZH2CODE = {'中国': 'cn', '日本': 'jp', '韩国': 'kr', '印度': 'in', '印尼': 'id', '美国': 'us',
           '加拿大': 'ca', '墨西哥': 'mx', '巴西': 'br', '阿根廷': 'ar', '英国': 'gb',
           '法国': 'fr', '德国': 'de', '意大利': 'it', '俄罗斯': 'ru', '尼日利亚': 'ng',
           '埃及': 'eg', '南非': 'za', '澳大利亚': 'au', '新西兰': 'nz'}
FLAG_RE = re.compile(r'<div class="flag[^"]*"[^>]*>(?:<div[^>]*></div>)+</div>')
hits = [0]

def _flag_sub(m):
    ctx = html[m.start():m.start() + 400]
    zh = next((k for k in ZH2CODE if k in ctx), None)
    assert zh, '认不出国旗：' + ctx[:90].replace('\n', ' ')
    cls = 'flag--lg' if 'width:48px' in m.group(0) else ''
    hits[0] += 1
    return ('<svg class="flag %s" viewBox="0 0 30 20" aria-hidden="true">'
            '<use href="#flag-%s"/></svg>' % (cls, ZH2CODE[zh]))

html = FLAG_RE.sub(_flag_sub, html)
print('替换国旗数量：', hits[0])

# ---------- 6. 文案与版本号 ----------
sub1('<h1>AI 别闹 · 像素风 UI 设计稿 v0.2</h1>',
     '<h1>AI 别闹 · 像素风 UI 设计稿 v0.3</h1>', '标题版本号')
sub1('''  v0.2 相对 v0.1 的关键变化：对齐 <b>20 国 / 6 技能 / 7 结局 / 20 成就</b>的当前实现，新增<b>主菜单</b>与 4 个弹窗规格，
  补齐<b>设计令牌</b>、<b>组件状态</b>、<b>对比度审计</b>与<b>键盘焦点</b>规范。''',
     '''  v0.3 相对 v0.2 的关键变化：<b>修正全部 20 面国旗</b>（原先用三色块近似，中国国旗画成了红-黄-红），
  并把主游戏界面的地图从「色块 pin」换成 <b>由真实海岸线栅格化出的像素世界地图</b>（120×60 网格 / Miller 投影 / 国界按解锁状态着色）。''',
     '概述文案')
sub1('<div class="note fix">\n  <b>本版修掉了两个真实的可用性缺陷</b>',
     '''<div class="note aa">
  <b>v0.3 修订记录</b>
  <br>① <b>国旗全量重画</b>：20 面改为 <code>&lt;symbol&gt;</code> 雪碧图（<code>viewBox 0 0 30 20</code>，逐 rect 绘制），
      中国为红底 + 左上大五角星 + 四颗小星；<s>v0.2 的错误版本是红-黄-红三横条</s>。
      顺带修正日本（正圆红日）、韩国（太极）、英国/澳洲/新西兰（米字旗）、巴西（黄菱形）、南非（绿 Y + 黑三角黄边）。
  <br>② <b>主游戏地图重做</b>：原先是 20 个绝对定位的色块标签，现在是一张真正的像素世界地图 ——
      陆地块由 Natural Earth 110m 海岸线栅格化而成，20 国按真实国界填充并按状态着色，配引导线标签。
</div>

<div class="note fix">
  <b>本版修掉了两个真实的可用性缺陷</b>''', '修订记录')
html = html.replace('14/20 国', '12/20 国').replace('COUNTRIES (14/20)', 'COUNTRIES (12/20)')
html = html.replace('已解锁 14/20 国', '已解锁 12/20 国')

sub1('<li><b>地图为中心</b> —— 世界地图占主区 50%+ 宽度，20 国以像素方块 + 国家码呈现，一眼看到全局</li>',
     '<li><b>地图为中心</b> —— 世界地图占主区约 58% 宽度；陆地为真实海岸线栅格化出的像素块，'
     '20 国按真实国界着色 + 国家码引导标签，一眼看到全局</li>', '设计原则')
sub1('20 国 pin + 20 成就全部渲染', '20 国像素地块 + 20 成就全部渲染', '验收清单')

sub1('<p class="frame-cap">1280×720 基准：顶部 48px / 底部 88px；三列 230 / auto / 292。地图占约 59% 宽度，是视觉重心。</p>',
     '''<p class="frame-cap">1280×720 基准：顶部 48px / 底部 88px；三列 230 / auto / 292。地图占约 58% 宽度，是视觉重心。</p>
<div class="note">
  <b>像素世界地图技术参数</b>（可直接交给开发实现）
  <ul style="margin:6px 0 0">
    <li><b>网格</b> 120 × 60，每格 3° 经度；<b>投影</b> Miller <code>y = 1.25·ln(tan(π/4 + 0.4φ))</code>，
        纬度范围 84°N – 57°S（裁掉南极与极区空白），内接比例约 <b>2:1</b></li>
    <li><b>数据源</b> Natural Earth 110m <code>ne_110m_land</code> / <code>ne_110m_admin_0_countries</code>（公有领域）；
        栅格化后按 50% 覆盖阈值二值化，跨日期变更线的多边形拆成两段分别投影</li>
    <li><b>绘制顺序</b> 海面 → 经纬网 → 陆地底 <code>#16323c</code> → 海岸线高亮 <code>#27505b</code>
        → 20 国国界（各自高亮色）→ 20 国填充 → 引导线 + 国家码标签</li>
    <li><b>路径形式</b> 横向游程合并 <code>M{x} {y}h{n}v1h-{n}z</code>；全图约 <b>19 KB</b> 路径数据，
        <b>零位图、零外部请求</b>，直接内联进 SVG</li>
    <li><b>缩放</b> <code>preserveAspectRatio="xMidYMid meet"</code> 内接等比，禁止拉伸；
        路径组加 <code>shape-rendering:crispEdges</code> 保住像素硬边，标签文字单独走几何精度渲染</li>
    <li><b>命中区</b> 每个国家是一段独立 <code>&lt;path&gt;</code>，可直接绑定点击与 hover；
        原始面积 &lt; 8 格的国家（韩国、新西兰等）已膨胀一圈，保证小屏下仍可点</li>
    <li><b>标签</b> 锚点取国界质心（美国含阿拉斯加，已手工校正到本土），标签框偏移放置并画引导线；
        选中态标签用近白色描边 <code>#eafffb</code> + 近白色文字，确保在深色底上可读</li>
  </ul>
</div>''', '地图技术参数')

sub1('<li>地图必须用<b>内接矩形</b>等比缩放，禁止拉伸 —— 否则国家形状会失真</li>',
     '<li>地图必须用<b>内接矩形</b>等比缩放（<code>preserveAspectRatio="xMidYMid meet"</code>），禁止拉伸 —— '
     '否则国家形状会失真；像素路径必须保持 <code>crispEdges</code>，一旦被抗锯齿就会失去像素感</li>',
     '响应式规范')

open(DST, 'w', encoding='utf-8').write(html)
print('v0.3 写出：', DST, len(html), 'chars')
