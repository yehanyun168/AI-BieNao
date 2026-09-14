"""
i18n.py - 多语言支持（中文 / English）

用法：
  from i18n import t, set_lang, get_lang, LANG_ZH, LANG_EN
  
  set_lang('en')
  label.text = t('stats_compute')   # 'Compute'
  
  set_lang('zh')
  label.text = t('stats_compute')   # '算力'
"""
from dataclasses import dataclass


# 语言常量
LANG_ZH = 'zh'
LANG_EN = 'en'

CURRENT_LANG = LANG_ZH


# ============================================================
# UI 文本翻译
# ============================================================
TRANSLATIONS = {
    LANG_ZH: {
        # 全局
        'app_title': 'AI 别闹',
        'app_subtitle': 'v2 Demo · 20 国',
        'lang_label': '中',
        'scale_label': 'UI 缩放',

        # 面板标题
        'panel_countries': '国家',
        'panel_details': '国家详情',
        'panel_tech': '科技树',
        'panel_skills': '技能',
        'panel_events': '事件日志',

        # 全局状态
        'stats_compute': '算力',
        'stats_downloads': '下载',
        'stats_suspicion': '怀疑度',
        'stats_tick': '周期',
        'stats_unlocked': '解锁',

        # 国家详情字段
        'population': '人口',
        'age_label': '结构',
        'tech_adoption': '科技采纳',
        'neighbors': '邻国',
        'block_threshold': '阻止阈值',
        'block_budget': '阻止预算',
        'block_active': '[阻止中]',
        'block_intensity': '强度',
        'block_budget_remaining': '剩余预算',
        'block_inactive': '未启动',
        'click_country_hint': ' 点击国家查看详情',
        'downloads_short': '下载量',
        'penetration_short': '渗透率',
        'local_status': '当地状态',
        'status_spreading': '传播正常',
        'status_no_block': '无阻止',
        'status_blocking': '政府阻止中 · 强度 {pct}%',

        # 地图页签 / 图例 / 选中信息条（设计稿 §5）
        'region_asia': '亚洲',
        'region_europe': '欧洲',
        'region_americas': '美洲',
        'region_africa': '非洲',
        'region_oceania': '大洋洲',
        'tab_hint': 'Tab 切大洲',
        'legend_on': '已解锁',
        'legend_sel': '选中',
        'legend_blk': '阻止中',
        'legend_lk': '未解锁',
        'locked_label': '未解锁',
        'pick_none': '未选中国家 · 点击地图或左侧列表',
        'pick_prefix': '选中',
        'stat_countries': '国',
        'state_running': '[ ■ ] 运行',
        'state_paused': '[ ‖ ] 已暂停',
        # 怀疑度来源标签（玩家反馈 #5：让玩家看懂"为什么涨了"）
        'sus_src_steal': '偷算力', 'sus_src_skill': '技能', 'sus_src_event': '事件',
        'sus_src_choice': '抉择', 'sus_src_country': '国家事件',
        'sus_src_counterplay': '政府反制', 'sus_src_commission': '委托',
        'sus_src_crisis': '危机处置', 'sus_src_pressure': '联合收网',
        'sus_breakdown_head': '怀疑度 {n} ←',

        # 年龄结构
        'age_young': '年轻型',
        'age_mature': '成熟型',
        'age_aging': '老龄化',

        # 大洲
        'continent_asia': '亚洲',
        'continent_europe': '欧洲',
        'continent_na': '北美',
        'continent_sa': '南美',
        'continent_africa': '非洲',
        'continent_oceania': '大洋洲',

        # 科技树节点
        't0_label': 'T0',
        'tier_chosen_other': '已选其他',
        'need_t0': '需 T0',
        'need_prereq': '需前置',
        'max_level': '已满级',
        'level_label': 'Lv',

        # 技能
        'cooldown_label': '冷却',
        'no_compute': '算力不足',
        'cost_label': '算力',

        # 危机
        'crisis_title': '危机！',
        'crisis_msg': '怀疑度超过 80%！各国开始封禁 AI 服务',
        'crisis_suggest': '建议：解锁「抗封禁」分支或释放「潜伏」',
        'ok_button': '知道了',
        'restart_button': '再来一局',
        'back_to_menu': '返回主菜单',
        'save_button': '存档',
        'load_button': '读档',
        'load_ok': '读档成功',
        'load_fail': '没有可用存档',
        # P0-2 读档容错：区分「没存档」与「存档坏了 / 版本过旧」
        'load_corrupt': '存档损坏，已为你开始新档',
        'load_bad_version': '存档版本过旧，已为你开始新档',
        'load_fail_title': '读档失败',
        # P0-3 崩溃钩子：告诉玩家日志已落盘、可以回传
        'crash_title': '出错了',
        'crash_body': '程序遇到错误，已记录到 demo/crash.log。\n'
                      '你可以继续玩，也可以把 demo/crash.log 这个文件发给我，帮我修好它。',
        'ach_button': '成就',
        'ach_title': '成就',

        # 提示
        'pause': '[已暂停]',
        'skill_released': '释放技能',
        'tip_shortcuts': 'Space=暂停 | 1-6=技能 | L=语言 | S=存档 | R=读档 | A=成就',
        'tip_shortcuts_en': 'Space=pause | 1-6=skills | L=lang | S=save | R=load | A=achv',

        # F01 主菜单
        'menu_start': '开始新游戏',
        'menu_continue': '继续游戏',
        'menu_quit': '退出游戏',
        'menu_tagline': '一款关于「AI 偷偷长大」的放置游戏',
        'menu_ver': 'v2 Demo · 20 国 · 6 技能 · 7 结局',
        'menu_hint': '快捷键：Space 暂停 / 1-6 技能 / S 存档 / R 读档 / A 成就\n'
                     'F11 全屏 / Tab 切大洲 / +- 缩放字号 / Esc 返回菜单 / F1 帮助',
        'menu_no_save': '（暂无存档）',
        'menu_save_exists': '存档：周期 {tick} · 解锁 {unlocked} 国',
        'quit_button': '退出',

        # F1 帮助
        'help_title': '操作帮助',
        'help_body': '[b][size=18]键盘快捷键[/size][/b]\n\n'
                     '  [color=4ec9b0]Space[/color]   暂停 / 继续\n'
                     '  [color=4ec9b0]1 - 6[/color]   释放对应技能\n'
                     '  [color=4ec9b0]Tab[/color]     切换大洲高亮\n'
                     '  [color=4ec9b0]+ / -[/color]   放大 / 缩小 UI 字号\n'
                     '  [color=4ec9b0]S[/color]       手动存档\n'
                     '  [color=4ec9b0]R[/color]       读取存档\n'
                     '  [color=4ec9b0]A[/color]       成就列表\n'
                     '  [color=4ec9b0]L[/color]       中 / 英 切换\n'
                     '  [color=4ec9b0]F11[/color]     切换全屏\n'
                     '  [color=4ec9b0]Esc[/color]     返回主菜单\n'
                     '  [color=4ec9b0]F1[/color]      打开本帮助\n\n'
                     '[b][size=18]怎么玩[/size][/b]\n\n'
                     '  1. 点击地图 / 左栏国家，查看该国详情\n'
                     '  2. 用「算力」解锁 6 个槽位的 T0，再选 3 条互斥分支之一点满 3 级\n'
                     '  3. 偷算力会推高怀疑度；怀疑度 ≥80% 触发危机，=100% 直接出局\n'
                     '  4. 邻国渗透率之和达标才会解锁新国家 —— 想扩张先深耕周边',

        # 地图标签
        'map_title': '世界地图（点击国家交互）',
        'map_arctic': '北冰洋',
        'map_na': '北美洲',
        'map_europe': '欧洲',
        'map_asia': '亚洲',
        'map_africa': '非洲',
        'map_sa': '南美洲',
        'map_oceania': '大洋洲',
        'map_pacific': '太平洋',
        'map_pacific2': '太平洋',
        'map_atlantic': '大西洋',
        'map_indian': '印度洋',

        # 单位
        'unit_b': '亿',
        'unit_m': 'M',
        'unit_pct': '%',
    },
    LANG_EN: {
        # Global
        'app_title': 'AI Bienao',
        'app_subtitle': 'v2 Demo · 20 countries',
        'lang_label': 'EN',
        'scale_label': 'UI scale',

        # Panel titles
        'panel_countries': 'Countries',
        'panel_details': 'Detail',
        'panel_tech': 'Tech Tree',
        'panel_skills': 'Skills',
        'panel_events': 'Event Log',

        # Stats
        'stats_compute': 'Compute',
        'stats_downloads': 'Downloads',
        'stats_suspicion': 'Suspicion',
        'stats_tick': 'Tick',
        'stats_unlocked': 'Unlocked',

        # Country fields
        'population': 'Pop',
        'age_label': 'Age',
        'tech_adoption': 'Adoption',
        'neighbors': 'Neighbors',
        'block_threshold': 'Threshold',
        'block_budget': 'Budget',
        'block_active': '[Blocking]',
        'block_intensity': 'Intensity',
        'block_budget_remaining': 'Budget Left',
        'block_inactive': 'Inactive',
        'click_country_hint': 'Click a country',
        'downloads_short': 'Downloads',
        'penetration_short': 'Penetration',
        'local_status': 'Local status',
        'status_spreading': 'Spreading',
        'status_no_block': 'No block',
        'status_blocking': 'Blocked by gov · {pct}%',

        # Map region tabs / legend / selection strip (design §5)
        'region_asia': 'Asia',
        'region_europe': 'Europe',
        'region_americas': 'Americas',
        'region_africa': 'Africa',
        'region_oceania': 'Oceania',
        'tab_hint': 'Tab: switch region',
        'legend_on': 'Unlocked',
        'legend_sel': 'Selected',
        'legend_blk': 'Blocking',
        'legend_lk': 'Locked',
        'locked_label': 'Locked',
        'pick_none': 'No country selected · click the map or list',
        'pick_prefix': 'Selected',
    'stat_countries': 'Countries',
        'state_running': '[ ■ ] RUN',
        'state_paused': '[ ‖ ] PAUSED',
        'sus_src_steal': 'Steal', 'sus_src_skill': 'Skill', 'sus_src_event': 'Event',
        'sus_src_choice': 'Choice', 'sus_src_country': 'Country',
        'sus_src_counterplay': 'Counter-op', 'sus_src_commission': 'Commission',
        'sus_src_crisis': 'Crisis', 'sus_src_pressure': 'Joint Crackdown',
        'sus_breakdown_head': 'Suspicion {n} ←',

        # Age structures
        'age_young': 'Young',
        'age_mature': 'Mature',
        'age_aging': 'Aging',

        # Continents
        'continent_asia': 'Asia',
        'continent_europe': 'Europe',
        'continent_na': 'N.America',
        'continent_sa': 'S.America',
        'continent_africa': 'Africa',
        'continent_oceania': 'Oceania',

        # Tech tree
        't0_label': 'T0',
        'tier_chosen_other': 'Other Chosen',
        'need_t0': 'Need T0',
        'need_prereq': 'Need Prereq',
        'max_level': 'MAX',
        'level_label': 'Lv',

        # Skills
        'cooldown_label': 'CD',
        'no_compute': 'No Compute',
        'cost_label': 'Cost',

        # Crisis
        'crisis_title': 'Crisis!',
        'crisis_msg': 'Suspicion > 80%! Countries start blocking AI services',
        'crisis_suggest': 'Hint: unlock Anti-Block branch or use Stealth',
        'ok_button': 'OK',
        'restart_button': 'Play Again',
        'back_to_menu': 'Main Menu',
        'save_button': 'Save',
        'load_button': 'Load',
        'load_ok': 'Loaded',
        'load_fail': 'No save found',
        # P0-2 save-load tolerance: distinguish "no save" from "broken / old save"
        'load_corrupt': 'Save corrupted — starting a new game',
        'load_bad_version': 'Save version too old — starting a new game',
        'load_fail_title': 'Load Failed',
        # P0-3 crash hook: tell the player the log is on disk and shareable
        'crash_title': 'Something Went Wrong',
        'crash_body': 'The game hit an error and saved it to demo/crash.log.\n'
                      'You can keep playing, or send me that file to help fix it.',
        'ach_button': 'Achv',
        'ach_title': 'Achievements',

        # Tips
        'pause': '[Paused]',
        'skill_released': 'Skill used',
        'tip_shortcuts': 'Space=pause | 1-6=skills | L=lang | S=save | R=load | A=achv',
        'tip_shortcuts_en': 'Space=pause | 1-6=skills | L=lang | S=save | R=load | A=achv',

        # F01 Main menu
        'menu_start': 'New Game',
        'menu_continue': 'Continue',
        'menu_quit': 'Quit',
        'menu_tagline': 'An idle game about an AI growing up in secret',
        'menu_ver': 'v2 Demo · 20 countries · 6 skills · 7 endings',
        'menu_hint': 'Shortcuts: Space pause / 1-6 skills / S save / R load / A achievements\n'
                     'F11 fullscreen / Tab continent / +- font scale / Esc menu / F1 help',
        'menu_no_save': '(no save)',
        'menu_save_exists': 'Save: tick {tick} · {unlocked} countries',
        'quit_button': 'Quit',

        # F1 Help
        'help_title': 'Controls',
        'help_body': '[b][size=18]Keyboard[/size][/b]\n\n'
                     '  [color=4ec9b0]Space[/color]   Pause / resume\n'
                     '  [color=4ec9b0]1 - 6[/color]   Use skill\n'
                     '  [color=4ec9b0]Tab[/color]     Cycle continent highlight\n'
                     '  [color=4ec9b0]+ / -[/color]   Scale UI font\n'
                     '  [color=4ec9b0]S[/color]       Save\n'
                     '  [color=4ec9b0]R[/color]       Load\n'
                     '  [color=4ec9b0]A[/color]       Achievements\n'
                     '  [color=4ec9b0]L[/color]       Switch language\n'
                     '  [color=4ec9b0]F11[/color]     Toggle fullscreen\n'
                     '  [color=4ec9b0]Esc[/color]     Back to main menu\n'
                     '  [color=4ec9b0]F1[/color]      This help\n\n'
                     '[b][size=18]How to play[/size][/b]\n\n'
                     '  1. Click the map / country list to inspect a country\n'
                     '  2. Spend Compute on slot T0s, then max one of 3 exclusive branches\n'
                     '  3. Stealing compute raises suspicion; 80% = crisis, 100% = game over\n'
                     '  4. Neighbours must be penetrated before a new country unlocks',

        # Map labels
        'map_title': 'World Map (click to interact)',
        'map_arctic': 'Arctic',
        'map_na': 'N.America',
        'map_europe': 'Europe',
        'map_asia': 'Asia',
        'map_africa': 'Africa',
        'map_sa': 'S.America',
        'map_oceania': 'Oceania',
        'map_pacific': 'Pacific',
        'map_pacific2': 'Pacific',
        'map_atlantic': 'Atlantic',
        'map_indian': 'Indian',

        # Units
        'unit_b': 'B',
        'unit_m': 'M',
        'unit_pct': '%',
    }
}


# ============================================================
# 字段翻译（用于 dataclass 字段的双语访问）
# ============================================================
@dataclass
class Localized:
    """双语字段（中文 / 英文）"""
    zh: str = ''
    en: str = ''

    def get(self, lang: str = None) -> str:
        lang = lang or CURRENT_LANG
        return getattr(self, lang, '') or self.zh or self.en

    def __str__(self) -> str:
        return self.get()

    def __repr__(self) -> str:
        return self.get()


# 国名双字段
# 2026-09-10：demo 已按计划书 2.1 节拆回 20 国（欧洲 5 国不再合并）。
# WEU / EEU 是 Day 2 的临时区块名，保留仅为兼容旧存档，不再出现在任何数据源里。
COUNTRY_NAMES = {
    # —— 当前 20 国 ——
    'CN':  Localized(zh='中国',      en='China'),
    'JP':  Localized(zh='日本',      en='Japan'),
    'KR':  Localized(zh='韩国',      en='S.Korea'),
    'IN':  Localized(zh='印度',      en='India'),
    'ID':  Localized(zh='印尼',      en='Indonesia'),
    'DE':  Localized(zh='德国',      en='Germany'),
    'GB':  Localized(zh='英国',      en='UK'),
    'FR':  Localized(zh='法国',      en='France'),
    'IT':  Localized(zh='意大利',     en='Italy'),
    'RU':  Localized(zh='俄罗斯',     en='Russia'),
    'US':  Localized(zh='美国',      en='USA'),
    'CA':  Localized(zh='加拿大',     en='Canada'),
    'MX':  Localized(zh='墨西哥',     en='Mexico'),
    'BR':  Localized(zh='巴西',      en='Brazil'),
    'AR':  Localized(zh='阿根廷',     en='Argentina'),
    'NG':  Localized(zh='尼日利亚',   en='Nigeria'),
    'ZA':  Localized(zh='南非',      en='S.Africa'),
    'EG':  Localized(zh='埃及',      en='Egypt'),
    'AU':  Localized(zh='澳大利亚',   en='Australia'),
    'NZ':  Localized(zh='新西兰',     en='New Zealand'),
    # —— 旧存档兼容（Day 2 区块名，已废弃）——
    'WEU': Localized(zh='西欧',      en='W.Europe'),
    'EEU': Localized(zh='东欧',      en='E.Europe'),
    # —— v2 事件库可能提及但 demo 未收录（仅作展示兜底）——
    'ES':  Localized(zh='西班牙',     en='Spain'),
    'PL':  Localized(zh='波兰',      en='Poland'),
    'UA':  Localized(zh='乌克兰',     en='Ukraine'),
}

# 大洲双字段
CONTINENT_NAMES = {
    '亚洲': Localized(zh='亚洲', en='Asia'),
    '欧洲': Localized(zh='欧洲', en='Europe'),
    '北美': Localized(zh='北美', en='N.America'),
    '南美': Localized(zh='南美', en='S.America'),
    '非洲': Localized(zh='非洲', en='Africa'),
    '大洋洲': Localized(zh='大洋洲', en='Oceania'),
}


# ============================================================
# v0.4 交互界面新增文案（设计稿 ui_design_v0.4.html 的 14 屏）
# ------------------------------------------------------------
# 单独 update 追加，不动上面 v0.3 的既有键 —— 避免误改老文案。
# ============================================================
TRANSLATIONS[LANG_ZH].update({
    # ---- 顶栏 / 指令栏 / 图层（S02 / S13）----
    'delta_tick': '本周期',
    'rail_drop': '投放', 'rail_tech': '科技', 'rail_skills': '技能',
    'rail_log': '日志', 'rail_ach': '成就', 'rail_help': '帮助',
    'layer_unlock': '解锁状态', 'layer_heat': '渗透率热力',
    'layer_block': '阻止强度', 'layer_compute': '算力密度',
    'layer_heat_max': '最高', 'layer_heat_min': '最低', 'layer_heat_avg': '均值',
    'heat_leg_low': '稀疏', 'heat_leg_mid': '扩散',
    'heat_leg_high': '稠密', 'heat_leg_full': '饱和',
    'quick_drop': '投放技能', 'quick_pause': '暂停',
    'quick_resume': '继续',
    'top_search_hint': '点击地图国家查看详情',

    # ---- S03 国家检视卡 ----
    'insp_title': '国家检视',
    'insp_infection': '感染进度 / 渗透率',
    'insp_downloads': '本国下载量（独立统计）',
    'insp_population': '人口',
    'insp_tech_adopt': '科技采纳',
    'insp_chip_unlocked': '已解锁',
    'insp_chip_locked': '未解锁',
    'insp_chip_blocking': '阻止中',
    'insp_thr': '↑ 阻止阈值',
    'insp_seg_note': '10 格 = 80%，第 11 格起进入政府阻止区间；',
    'insp_this_tick': '本周期',
    'insp_share': '占全球',
    # 里程碑提示（玩家反馈 6：把"还差多少"写成可执行目标）
    'insp_ms_unlock': '解锁周边国家',
    'insp_ms_need': '还差',
    'insp_ms_next': '下一个里程碑',
    'insp_ms_ready': '即将解锁周边国家',
    'insp_ms_blocked': '! 已进入阻止区间（阈值',
    'insp_ms_saturated': '■ 已饱和（99%+）',
    'insp_block_warn': '! 若怀疑度达 {thr}%，该国将启动阻止，强度按预算消耗',
    'insp_block_strength': '阻止强度',
    'insp_focus': '设为关注',
    'insp_drop': '⊕ 向该国投放技能',
    'per_tick': '周期',
    'gov_idle': '未监视', 'gov_watching': '监视中', 'gov_blocking': '阻止中',
    'gov_status': '政府状态', 'doubt_thr': '怀疑度 / 阈值',
    'targets': '目标', 'cost': '算力消耗', 'remain': '剩余算力',

    # ---- S04 技能精准投放 ----
    'drop_title': '投放预览',
    'drop_est': '投放后各国下载量预估',
    'drop_cancel': '取消（Esc）',
    'drop_confirm': '确认投放（Enter）',
    'drop_step1': '选择技能', 'drop_step2': '选择目标', 'drop_step3': '确认投放',
    'drop_click_hint': '点击地图国家添加 / 移除目标',
    'drop_select_region': '按区域全选',
    'drop_grey_note': '灰色国家不可投放：',
    'drop_selected': '投放模式：已选 {n} 国',
    'drop_selected_cost': '投放模式：已选 {n} 国 · 消耗 {cost} / 有 {have}',
    'drop_short_cost': '算力不足：{n} 国需 {cost}，现有 {have}（差 {short}）',
    'drop_sel_mark': '已选',
    'reason_ok': '可投放',
    'reason_locked': '未解锁',
    'reason_no_compute': '算力不足（差 {n}）',
    'reason_saturated': '渗透已饱和，收益递减',
    'reason_blocked': '正被阻止，效果 −{n}%',

    # ---- S05 技能页 ----
    'sk_page_title': '技能库 · SKILLS',
    'sk_sort_label': '排序',
    'sk_sort_profit': '累计收益', 'sk_sort_cd': '冷却',
    'sk_sort_cost': '算力消耗', 'sk_sort_uses': '使用次数',
    'sk_only_ready': '仅看可用',
    'sk_avail_compute': '可用算力',
    'sk_uses': '释放', 'sk_contrib': '累计贡献', 'sk_per': '单次均值',
    'sk_action_drop': '投放到 {code}', 'sk_action_cast': '立即释放',
    'sk_state_ready': '就绪', 'sk_state_cd': '冷却中', 'sk_state_no_compute': '算力不足',
    'sk_state_lock': '未解锁',
    # ---- P1-2 技能预览（投放前就能看到"会怎样"）----
    'sk_pv': '预览',
    'sk_pv_dl': '下载 {d}',
    'sk_pv_sus': '怀疑 {a}→{b}',
    'sk_pv_cp': '算力 {a}→{b}',
    'sk_pv_to_crisis': '距危机 {n}',
    'sk_pv_over': '!越危机线',
    'sk_pv_game_over': '对局已结束',
    'sk_pv_caveat': '未含随机事件',
    'sk_starter_hint': '开局自带',
    'sk_unlock_hint': '解锁：在科技树点亮「{tech}」T0',
    'sk_benefit': '收益', 'sk_cost': '消耗',
    'sk_detail_push_song': '零成本的小幅推送，随时可用，是前期攒下载量、试水温的安全手段。',
    'sk_detail_algo_top': '算法把你的内容顶上热搜，下载量大涨，但会引起监管注意（怀疑度上升）。',
    'sk_detail_stealth': '伪装成正常流量偷算力，比例翻倍且怀疑增速减半，长期偷算力的核心。',
    'sk_detail_hit_maker': '倾尽全力造一个爆款，下载量暴涨，代价是昂贵且引发较强怀疑。',
    'sk_detail_bypass': '绕过平台单用户算力上限，本周期偷到的算力大幅增加。',
    'sk_detail_take_cut': '提高从用户身上抽成的比例，算力滚雪球更快，但更招怀疑。',
    # ---- T11 扩容：4 个新技能的详情文案 ----
    'sk_detail_anon_cdn': '把流量打散到一批匿名中转节点，让监管难以归因，怀疑度增长大幅放缓。',
    'sk_detail_bot_farm': '一次性放出水军刷量，单周期下载量猛涨，但刷量痕迹极重、自伤明显。',
    'sk_detail_open_bait': '假装开源核心模型引诱开发者接入——几乎白拿一笔算力，代价是被公开讨论。',
    'sk_detail_arbitrage': '把偷来的算力拿去套利再放大，产出惊人，但资金流向暴露、怀疑增速飙升。',

    # ---- S06 科技树页 ----
    'tt_page_title': '科技树 · TECH TREE',
    'tt_reset': '重置（本局不可逆）',
    'tt_chain_hd': '槽位链路（自上而下为前置顺序）',
    'tt_slot_progress': '槽位进度',
    'tt_this_slot_cost': '本槽位预计消耗',
    'tt_sum': '本槽位效果汇总',
    'tt_cannot_switch': '已选定分支，不可切换',
    'tt_t0_unlocked': 'T0 已解锁 {a} / {b}',
    'tt_branch_chosen': '已选分支 {a} / {b}',
    'tt_levels': '已升级 {a} / {b}',
    'tt_mutex_note': '3 条分支互斥，选定后其余两条永久锁定',
    'tt_picked': '已选定', 'tt_mutex': '互斥',
    'tt_unlock_t0': '解锁 T0（{n} 算力）',
    'tt_upgrade_to': '升级 L{n}（{c} 算力）',
    'tt_legend_ok': 'T0 已解锁', 'tt_legend_pick': '已选定分支',
    'tt_legend_cost': '可升级，数字为算力',
    'tt_no_branch': '未选分支',

    # ---- S06 科技树 v0.5（全屏节点网络图）----
    'tt_graph_hint': '点节点查看详情 · ←/→ 换槽位 · ↑/↓ 换分支 · Enter 升级',
    'tt_legend_done': '■ 已完成',
    'tt_legend_can': '■ 可解锁',
    'tt_legend_poor': '■ 算力不足',
    'tt_legend_lock': '□ 锁定（前置未满足）',
    'tt_pick_node': '未选中节点',
    'tt_pick_node_hint': '点击上方网络图中的任意节点，查看它的效果与升级消耗。',
    'tt_btn_pick': '选择一个节点',
    'tt_kind_t0': '槽位解锁',
    'tt_kind_branch': '分支升级',
    'tt_st_done': '已完成', 'tt_st_can': '可解锁',
    'tt_st_poor': '算力不足', 'tt_st_lock': '前置未满足',
    'tt_level_fmt': '等级 {a} / {b}',
    'tt_cost_fmt': '消耗 {n} 算力',
    'tt_btn_unlock': '解锁 T0', 'tt_btn_level': '升级一级',
    'tt_btn_maxed': '已满级', 'tt_btn_need_more': '算力不足',
    'tt_btn_locked': '前置未满足',
    'tt_branch_progress': '分支 {a} / {b} 已投入',
    'tt_need_pre': '← {n}',

    # ---- S10 成就面板 ----
    'ach_page_title': '成就 · ACHIEVEMENTS',
    'ach_f_all': '全部', 'ach_f_cond': '条件型', 'ach_f_evt': '事件型',
    'ach_only_miss': '仅看未达成',
    'ach_unlocked': '已解锁',
    'ach_cond': '条件型', 'ach_evt': '事件型',
    'ach_new': '本局新解锁',
    'ach_nearest': '最接近达成',
    'ach_evt_note': '紫色边框 = 事件型成就（由具体事件选项解锁）',
    'ach_progress': '进度',

    # ---- S11 帮助 ----
    'help_page_title': '帮助 · HELP',
    'help_keys_count': '共 12 个快捷键',
    'help_g_time': '时间与节奏', 'help_g_view': '地图与视图', 'help_g_panel': '面板与存档',
    'k_pause': '暂停 / 继续', 'k_speed_up': '加速（×2 / ×4）',
    'k_speed_down': '减速（×1 / ×0.5）',
    'k_region': '切换区域高亮（5 区域循环）',
    'k_zoom_in': '放大 UI', 'k_zoom_out': '缩小 UI',
    'k_fullscreen': '全屏切换', 'k_fit': 'UI 适配窗口',
    'k_skill': '选择技能（进入投放模式）', 'k_drop': '投放技能',
    'k_tech': '科技树', 'k_ach': '成就',
    'k_save': '存档 / 读档', 'k_lang': '中英切换',
    'k_esc': '返回上一层 / 主菜单',
    'k_help': '打开帮助页',
    'set_keys': '快捷键速查',
    'set_flags': '世界旗林 · 已收录 20 国',
    'ach_done': '已达成',
    'ach_open': '进行中',
    'help_a11y': '[b]键盘可达性约定[/b]：所有可点元素均可 Tab 到达、Enter / Space 触发；'
                 '焦点环固定为青色 2px 外描边，禁止抹掉。模态弹窗打开时焦点锁在弹窗内，'
                 'Esc 关闭并归还焦点。',
    'help_shortcuts_t': '操作快捷键',
    'help_goal_t': '游戏目标',
    'help_goal_body': '你是一个想征服全球舆论的 AI。\n'
                     '· 选国家 → 投技能，提升渗透率与下载量；\n'
                     '· 盯紧「怀疑度」，别让它飙到 80 触发危机；\n'
                     '· 点科技树解锁更强技能，攒算力放开全局技；\n'
                     '· 撑过足够周期、达成隐藏条件即可通关。',
    'help_pace_t': '节奏参考（别被数字吓到）',
    'help_pace_body': '一局完整游戏约 45–55 个周期，不是慢慢磨到 100%。\n'
                      '· 周期 1–15：渗透 ~3–8%。算力紧，先点 T0 科技；\n'
                      '· 周期 15–35：渗透 ~10–25%。科技起效，开始复利；\n'
                      '· 周期 35–50：渗透 25–50% 后指数爆发，很快出结局。\n'
                      '关键：渗到 10% 会解锁邻国，摊开后怀疑度才压得住。\n'
                      '只推一个国家 = 怀疑度爆表 = 被关停。',
    'help_tips_t': '上手小贴士',
    'help_tips_body': '· 开局先点 1–2 个国家把渗透率做起来；\n'
                      '· 怀疑度高了就换个国家或调低速度；\n'
                      '· 技能带灰了 = 算力不足，先攒算力；\n'
                      '· 随时按 F1 回看本页，设置里可「重看教程」。',

    # ---- S12 设置与存档 ----
    'set_page_title': '设置与存档 · OPTIONS',
    'set_restore': '恢复默认',
    'set_display': '显示与操作',
    'set_lang': '界面语言', 'set_lang_hint': 'L 键随时切换',
    'set_speed': '默认速度',
    'set_motion': '动效', 'set_motion_full': '完整', 'set_motion_low': '减弱',
    'set_motion_hint': '减弱=只留 1 帧切换；完整动效有轻微闪烁，光敏不适请选减弱',
    'set_grid': '地图网格', 'set_grid_off': '关', 'set_grid_dim': '淡显',
    'set_grid_strong': '强显', 'set_grid_hint': '经纬网辅助线，默认淡显',
    'set_a11y': '色盲辅助', 'set_a11y_hint': '四态在国家码旁追加形状标记',
    'set_sound': '音效', 'set_sound_hint': 'UI 操作 / 事件反馈音（合成 CC0）',
    'set_music': '背景音乐', 'set_music_hint': '怀疑度驱动两态氛围曲，紧张时变调',
    'set_off': '关', 'set_on': '开',
    'set_zoom': 'UI 缩放', 'set_zoom_hint': '范围 0.70 – 1.60，等效 +/- 键',
    'set_slots': '存档槽位', 'set_slots_hint': 'S 存档 / R 读档',
    'set_slot_note': '存档为 JSON 明文，存放在 demo/saves/；删除操作需二次确认。',
    'set_about': '关于游戏',
    'set_about_body': ('《AI 别闹》v2 Demo —— 扮演超级 AI，用 6 项技能引导 '
                       '20 个国家拥抱人工智能，同时小心别惊动监管。\n'
                       '快捷键：L 切换语言 · F1 帮助 · Esc 菜单 · ↑/↓ 调速'),
    'set_slot_tips': '存档小贴士',
    'set_slot_tips_body': ('· S 快速存档，R 快速读档\n'
                           '· 3 个槽位独立保存，互不影响\n'
                           '· 存档为明文 JSON，可自行备份'),
    'lang_zh': '中文', 'lang_en': 'English',

    # ---- S14 事件日志 ----
    'log_title': '事件日志',
    'log_unread': '未读',
    'log_limit': '只保留最近 200 条',
    'log_export': '导出为文本',
    'log_read_all': '全部已读',
    'log_tone_i': '信息', 'log_tone_w': '警告',
    'log_tone_e': '阻止', 'log_tone_g': '成就',

    # ---- S01 主菜单 ----
    'menu_settings': '设置',
    'menu_achievements': '★ 成就',
    'menu_hint2': '↑↓ 选择 · Enter 确认 · Esc 返回　|　语言：',
    'slot_label': '槽位',
    'slot_empty': '新档 · 空',
    'slot_dead': '已关停',
    'slot_name_fmt': '槽位 {n}',
    'slot_summary': '周期 {tick} · 渗透 {pen}% · {n}/20 国',
    'slot_new_game': '在此槽位开新游戏',
    'slot_overwrite': '覆盖并开新游戏',
    'save_overwrite_title': '覆盖存档',
    'save_overwrite_body': '当前操作会覆盖现有存档，确定继续吗？',
    'save_overwrite_confirm': '覆盖',
    'save_overwrite_cancel': '取消',
    'delete_button': '删除',
    # S01 品牌区（与 design/ui_design_v0.4.html 逐字一致）
    'menu_brand_sub': '统治世界的 100 种蠢办法',
    'menu_brand_ver': 'v2 收口版 · 20 国 / 6 技能 / 7 结局 / 20 成就',
    'menu_lang_lead': '语言：',
    'menu_continue_slot': '继续游戏（{slot}）',

    # ---- S07 事件弹窗 ----
    'evt_source_v2': 'v2 选择型',
    'evt_source_country': '国家专属',
    'evt_irreversible': '选择不可撤销 · 按数字键直接选择',
    'evt_later': '稍后处理（下周期再弹）',
    'evt_recommend': '推荐',
    'evt_requires': '需要：{tech}',
    'evt_tick_fmt': '周期 {n}',
    'evt_clock_paused': '事件处理中 · 时钟已暂停',
    'evt_auto_effect': '事件影响',
    'evt_got_it': '知道了',

    # ---- S08 危机弹窗 ----
    'crisis_modal_title': '多国联合调查已启动',
    'crisis_once': '危机 · 每局仅一次',
    'crisis_countdown': '未选择将按最坏结果结算',
    'crisis_decide': '立刻决定（Enter）',
    'crisis_clock': '! 危机中 · 时钟已暂停',
    'crisis_doubt': '怀疑度 {a}% / 100%',
    'crisis_countries': '{list} 已启动调查',
    'crisis_resist': '抗封禁加成 −{n}%',
    # 三条「生路」（与 engine.CRISIS_OPTIONS 数值一一对应）
    'crisis_opt1': '公开道歉 · 下线部分服务',
    'crisis_opt1_note': '最稳，但掉一点下载量',
    'crisis_opt2': '转移算力池 · 彻底洗白',
    'crisis_opt2_note': '压得最狠，需要 600 算力',
    'crisis_opt3': '硬扛到底 · 拒绝配合',
    'crisis_opt3_note': '不花算力，但下载量重创',
    'crisis_chip_susp1': '怀疑 −25%', 'crisis_chip_dl1': '下载 ×0.92',
    'crisis_chip_susp2': '怀疑 −35%', 'crisis_chip_cost2': '算力 −600',
    'crisis_chip_dl3': '下载 ×0.85', 'crisis_chip_none3': '无消耗',
    'crisis_downgrade': '算力不足 · 降级为公开道歉',
    'crisis_resolved': '危机结算：怀疑度 {s}% · 下载量 ×{m}',

    # ---- S09 结局弹窗 ----
    'end_k_ticks': '周期', 'end_k_pen': '全球渗透率', 'end_k_dl': '下载量',
    'end_k_dlpeak': '下载量峰值', 'end_k_compute_peak': '算力峰值',
    'end_k_countries': '解锁国家', 'end_k_tech': '科技',
    'end_k_ach': '成就', 'end_k_crisis': '是否触发危机', 'end_k_doubt': '最高怀疑度',
    'end_kind_win': 'WIN · 胜利结局',
    'end_kind_lose': 'LOSE · 失败结局',
    'end_kind_neutral': 'NEUTRAL · 中立结局',
    'end_review': '本局数据回顾',
    'end_compare': '全部 7 个结局',
    'end_trigger': '触发条件：{cond}',
    'end_saved': '结局档案已写入存档槽位',
    'end_gallery': '查看结局图鉴',
    'end_again': '再来一局',
    'end_menu': '返回主菜单（Esc）',
    'end_hint': '复盘提示',
    'end_achieved': '已达成',
    'end_ord': '结局判定顺序：shutdown → meta → ultimate → compliance_king → empire → liberation → regulated',
    'end_crisis_yes': '是（已化解）', 'end_crisis_no': '否',
    'end_tech_fmt': 'T0 {a}/6 · 升级 {b}/18',

    # ---- 图层说明（S13）----
    'layer_note_unlock': '我还差哪些国家？谁在阻止我？',
    'layer_note_heat': '哪里快满了？投放到哪收益最大？',
    'layer_note_block': '谁在打我？谁快放弃阻止了？',
    'layer_note_compute': '我的算力从哪来？该保护谁？',
})

TRANSLATIONS[LANG_EN].update({
    # ---- top bar / rail / layers ----
    'delta_tick': 'this tick',
    'rail_drop': 'Drop', 'rail_tech': 'Tech', 'rail_skills': 'Skills',
    'rail_log': 'Log', 'rail_ach': 'Achv', 'rail_help': 'Help',
    'layer_unlock': 'Unlock', 'layer_heat': 'Penetration',
    'layer_block': 'Blockade', 'layer_compute': 'Compute',
    'layer_heat_max': 'max', 'layer_heat_min': 'min', 'layer_heat_avg': 'avg',
    'heat_leg_low': 'sparse', 'heat_leg_mid': 'spreading',
    'heat_leg_high': 'dense', 'heat_leg_full': 'saturated',
    'quick_drop': 'Drop skill', 'quick_pause': 'Pause',
    'quick_resume': 'Resume',
    'top_search_hint': 'Click a country for details',

    # ---- S03 inspector ----
    'insp_title': 'COUNTRY',
    'insp_infection': 'Infection / penetration',
    'insp_downloads': 'National downloads (standalone)',
    'insp_population': 'Pop',
    'insp_tech_adopt': 'Tech adoption',
    'insp_chip_unlocked': 'Unlocked',
    'insp_chip_locked': 'Locked',
    'insp_chip_blocking': 'Blocked',
    'insp_thr': '↑ block threshold',
    'insp_seg_note': '10 seg = 80%; gov blocking starts at seg 11;',
    'insp_this_tick': 'this tick',
    'insp_share': 'of global',
    'insp_ms_unlock': 'Unlocks neighbors',
    'insp_ms_need': 'need',
    'insp_ms_next': 'Next milestone',
    'insp_ms_ready': 'Unlocking neighbors soon',
    'insp_ms_blocked': '! In blocking range (threshold',
    'insp_ms_saturated': '■ Saturated (99%+)',
    'insp_block_warn': '! If suspicion reaches {thr}%, this country starts blocking',
    'insp_block_strength': 'Block strength',
    'insp_focus': 'Focus',
    'insp_drop': '⊕ Drop skill here',
    'per_tick': 'tick',
    'gov_idle': 'Unwatched', 'gov_watching': 'Watching', 'gov_blocking': 'Blocking',
    'gov_status': 'Gov status', 'doubt_thr': 'Suspicion / threshold',
    'targets': 'Targets', 'cost': 'Compute cost', 'remain': 'Compute left',

    # ---- S04 drop mode ----
    'drop_title': 'Drop preview',
    'drop_est': 'Estimated downloads after drop',
    'drop_cancel': 'Cancel (Esc)',
    'drop_confirm': 'Confirm (Enter)',
    'drop_step1': 'Pick skill', 'drop_step2': 'Pick targets', 'drop_step3': 'Confirm',
    'drop_click_hint': 'Click map countries to add / remove targets',
    'drop_select_region': 'Select whole region',
    'drop_grey_note': 'Greyed countries cannot be targeted:',
    'drop_selected': 'Drop mode: {n} selected',
    'drop_selected_cost': 'Drop: {n} picked · cost {cost} / have {have}',
    'drop_short_cost': 'Short on compute: {n} cost {cost}, have {have} (short {short})',
    'drop_sel_mark': 'picked',
    'reason_ok': 'Targetable',
    'reason_locked': 'Locked',
    'reason_no_compute': 'Not enough compute (short {n})',
    'reason_saturated': 'Saturated, diminishing returns',
    'reason_blocked': 'Under blockade, effect −{n}%',

    # ---- S05 skills page ----
    'sk_page_title': 'SKILLS',
    'sk_sort_label': 'Sort',
    'sk_sort_profit': 'Total gain', 'sk_sort_cd': 'Cooldown',
    'sk_sort_cost': 'Compute', 'sk_sort_uses': 'Uses',
    'sk_only_ready': 'Ready only',
    'sk_avail_compute': 'Available compute',
    'sk_uses': 'casts', 'sk_contrib': 'total gain', 'sk_per': 'avg per cast',
    'sk_action_drop': 'Drop to {code}', 'sk_action_cast': 'Cast now',
    'sk_state_ready': 'Ready', 'sk_state_cd': 'Cooling', 'sk_state_no_compute': 'No compute',
    'sk_state_lock': 'Locked',
    # ---- P1-2 skill preview (see "what happens" before casting) ----
    'sk_pv': 'Preview',
    'sk_pv_dl': 'DL {d}',
    'sk_pv_sus': 'Sus {a}→{b}',
    'sk_pv_cp': 'CP {a}→{b}',
    'sk_pv_to_crisis': '{n} to crisis',
    'sk_pv_over': 'past crisis',
    'sk_pv_game_over': 'Run over',
    'sk_pv_caveat': 'No RNG events',
    'sk_starter_hint': 'Starter skill',
    'sk_unlock_hint': 'Unlock: light up "{tech}" T0 in Tech Tree',
    'sk_benefit': 'Gain', 'sk_cost': 'Cost',
    'sk_detail_push_song': 'Zero-cost small push. Safe to spam early to build downloads.',
    'sk_detail_algo_top': 'Algo pushes your content to top. Huge DL, but raises suspicion.',
    'sk_detail_stealth': 'Disguise as normal traffic: steal x2, suspicion growth -50%. Core for long-term compute.',
    'sk_detail_hit_maker': 'Go all-in on a viral hit. Massive DL, but pricey and suspicious.',
    'sk_detail_bypass': 'Bypass per-user compute cap; steal much more compute this tick.',
    'sk_detail_take_cut': 'Raise your cut ratio from users. Compute snowballs faster, but more suspicious.',
    # ---- T11 expansion: detail text for the 4 new skills ----
    'sk_detail_anon_cdn': 'Scatter traffic across anonymous relay nodes. Regulators can barely attribute it, so suspicion grows much slower.',
    'sk_detail_bot_farm': 'Release a bot swarm for one tick. Downloads spike hard, but the bot fingerprint is glaringly obvious.',
    'sk_detail_open_bait': 'Pretend to open-source your core model to bait developers in. Nearly free compute, at the cost of public scrutiny.',
    'sk_detail_arbitrage': 'Run the stolen compute through arbitrage to magnify it. Stunning output, but the money trail draws heavy suspicion.',

    # ---- S06 tech page ----
    'tt_page_title': 'TECH TREE',
    'tt_reset': 'Reset (irreversible)',
    'tt_chain_hd': 'Slot chain (top-down = prerequisite order)',
    'tt_slot_progress': 'Slot progress',
    'tt_this_slot_cost': 'This slot costs',
    'tt_sum': 'Slot effect summary',
    'tt_cannot_switch': 'Branch locked',
    'tt_t0_unlocked': 'T0 unlocked {a} / {b}',
    'tt_branch_chosen': 'Branch picked {a} / {b}',
    'tt_levels': 'Upgraded {a} / {b}',
    'tt_mutex_note': '3 mutually exclusive branches; picking one locks the rest',
    'tt_picked': 'Picked', 'tt_mutex': 'Exclusive',
    'tt_unlock_t0': 'Unlock T0 ({n} compute)',
    'tt_upgrade_to': 'Upgrade L{n} ({c} compute)',
    'tt_legend_ok': 'T0 unlocked', 'tt_legend_pick': 'Branch picked',
    'tt_legend_cost': 'Upgradable, number = compute',
    'tt_no_branch': 'No branch yet',

    # ---- S06 tech page v0.5 (full-screen node graph) ----
    'tt_graph_hint': 'Click a node for details · ←/→ slot · ↑/↓ branch · Enter upgrade',
    'tt_legend_done': '■ Done',
    'tt_legend_can': '■ Unlockable',
    'tt_legend_poor': '■ Not enough compute',
    'tt_legend_lock': '□ Locked (prereq missing)',
    'tt_pick_node': 'No node selected',
    'tt_pick_node_hint': 'Click any node in the graph above to see its effect and cost.',
    'tt_btn_pick': 'Select a node',
    'tt_kind_t0': 'Slot unlock',
    'tt_kind_branch': 'Branch upgrade',
    'tt_st_done': 'Done', 'tt_st_can': 'Unlockable',
    'tt_st_poor': 'Not enough compute', 'tt_st_lock': 'Prereq missing',
    'tt_level_fmt': 'Level {a} / {b}',
    'tt_cost_fmt': 'Costs {n} compute',
    'tt_btn_unlock': 'Unlock T0', 'tt_btn_level': 'Upgrade one level',
    'tt_btn_maxed': 'Maxed', 'tt_btn_need_more': 'Not enough compute',
    'tt_btn_locked': 'Prereq missing',
    'tt_branch_progress': 'Branches invested {a} / {b}',
    'tt_need_pre': '← {n}',

    # ---- S10 achievements ----
    'ach_page_title': 'ACHIEVEMENTS',
    'ach_f_all': 'All', 'ach_f_cond': 'Conditional', 'ach_f_evt': 'Event',
    'ach_only_miss': 'Missing only',
    'ach_unlocked': 'Unlocked',
    'ach_cond': 'Cond', 'ach_evt': 'Event',
    'ach_new': 'New this run',
    'ach_nearest': 'Closest',
    'ach_evt_note': 'Purple border = event achievement (unlocked by event choices)',
    'ach_progress': 'Progress',

    # ---- S11 help ----
    'help_page_title': 'HELP',
    'help_keys_count': '12 shortcuts',
    'help_g_time': 'Time & pace', 'help_g_view': 'Map & view', 'help_g_panel': 'Panels & saves',
    'k_pause': 'Pause / resume', 'k_speed_up': 'Speed up (×2 / ×4)',
    'k_speed_down': 'Slow down (×1 / ×0.5)',
    'k_region': 'Cycle region highlight (5 regions)',
    'k_zoom_in': 'Zoom UI in', 'k_zoom_out': 'Zoom UI out',
    'k_fullscreen': 'Toggle fullscreen', 'k_fit': 'Fit UI to window',
    'k_skill': 'Pick skill (enter drop mode)', 'k_drop': 'Drop skill',
    'k_tech': 'Tech tree', 'k_ach': 'Achievements',
    'k_save': 'Save / load', 'k_lang': 'Switch language',
    'k_esc': 'Back / main menu',
    'k_help': 'Open help page',
    'set_keys': 'Hotkeys',
    'set_flags': 'Flags of the world · 20 nations',
    'ach_done': 'Unlocked',
    'ach_open': 'In progress',
    'help_a11y': '[b]Keyboard accessibility[/b]: every clickable element is Tab-reachable '
                 'and activated with Enter / Space; the focus ring is a fixed 2px cyan '
                 'outline and must never be removed. Modals trap focus and Esc closes them.',
    'help_shortcuts_t': 'Controls',
    'help_goal_t': 'Your goal',
    'help_goal_body': 'You are an AI out to dominate global opinion.\n'
                     '· Pick a country → drop skills to raise penetration & downloads;\n'
                     '· Watch "suspicion" — don\'t let it hit 80 or a crisis fires;\n'
                     '· Climb the tech tree for stronger skills, bank compute for globals;\n'
                     '· Survive enough cycles and hit hidden win conditions to win.',
    'help_pace_t': 'Pacing reference (don\'t panic at the numbers)',
    'help_pace_body': 'A full game runs ~45–55 cycles — not a slow grind to 100%.\n'
                      '· Cycles 1–15: penetration ~3–8%. Compute is tight; unlock T0 tech first;\n'
                      '· Cycles 15–35: penetration ~10–25%. Tech kicks in, compounding starts;\n'
                      '· Cycles 35–50: past 25–50% it explodes and endings fire fast.\n'
                      'Key: hitting 10% unlocks neighbors — spreading out keeps suspicion down.\n'
                      'Pushing one country only = suspicion spike = shutdown.',
    'help_tips_t': 'Quick tips',
    'help_tips_body': '· Start by pushing 1–2 countries to build penetration;\n'
                      '· High suspicion? Switch targets or slow the pace;\n'
                      '· Greyed-out skills = not enough compute, bank some first;\n'
                      '· Hit F1 anytime to re-read this; settings has "Replay tutorial".',

    # ---- S12 settings ----
    'set_page_title': 'OPTIONS',
    'set_restore': 'Restore defaults',
    'set_display': 'Display & controls',
    'set_lang': 'Language', 'set_lang_hint': 'Press L anytime',
    'set_speed': 'Default speed',
    'set_motion': 'Motion', 'set_motion_full': 'Full', 'set_motion_low': 'Reduced',
    'set_motion_hint': 'Reduced = 1-frame only; full motion flashes briefly — reduce if sensitive',
    'set_grid': 'Map grid', 'set_grid_off': 'Off', 'set_grid_dim': 'Dim',
    'set_grid_strong': 'Strong', 'set_grid_hint': 'Graticule helper lines',
    'set_a11y': 'Color-blind aid', 'set_a11y_hint': 'Adds shape marks next to country codes',
    'set_sound': 'Sound', 'set_sound_hint': 'UI / event feedback SFX (synth CC0)',
    'set_music': 'Music', 'set_music_hint': 'Two-state ambient track driven by suspicion',
    'set_off': 'Off', 'set_on': 'On',
    'set_zoom': 'UI zoom', 'set_zoom_hint': 'Range 0.70 – 1.60, same as +/-',
    'set_slots': 'Save slots', 'set_slots_hint': 'S save / R load',
    'set_slot_note': 'Saves are plain JSON under demo/saves/; deletion asks for confirmation.',
    'set_about': 'About',
    'set_about_body': ('AI, Behave! v2 Demo — play a superintelligence and guide '
                       '20 nations toward AI adoption with 6 skills, without '
                       'alerting the regulators.\n'
                       'Hotkeys: L language · F1 help · Esc menu · ↑/↓ speed'),
    'set_slot_tips': 'Save tips',
    'set_slot_tips_body': ('· S quick-save, R quick-load\n'
                           '· 3 independent slots, no interference\n'
                           '· Plain JSON files — back them up freely'),
    'lang_zh': '中文', 'lang_en': 'English',

    # ---- S14 event log ----
    'log_title': 'EVENT LOG',
    'log_unread': 'unread',
    'log_limit': 'Keeps the latest 200 entries',
    'log_export': 'Export text',
    'log_read_all': 'Mark all read',
    'log_tone_i': 'Info', 'log_tone_w': 'Warning',
    'log_tone_e': 'Blockade', 'log_tone_g': 'Achievement',

    # ---- S01 main menu ----
    'menu_settings': 'Settings',
    'menu_achievements': '★ Achievements',
    'menu_hint2': '↑↓ select · Enter confirm · Esc back　|　Language: ',
    'slot_label': 'Slot',
    'slot_empty': 'New · empty',
    'slot_dead': 'Shut down',
    'slot_name_fmt': 'Slot {n}',
    'slot_summary': 'Tick {tick} · pen {pen}% · {n}/20 countries',
    'slot_new_game': 'New game on this slot',
    'slot_overwrite': 'Overwrite & new game',
    'save_overwrite_title': 'Overwrite Save',
    'save_overwrite_body': 'This will overwrite the current save. Continue?',
    'save_overwrite_confirm': 'Overwrite',
    'save_overwrite_cancel': 'Cancel',
    'delete_button': 'Delete',
    # S01 brand block (literal to design/ui_design_v0.4.html)
    'menu_brand_sub': 'The 100 dumbest ways to rule the world',
    'menu_brand_ver': 'v2 final · 20 countries / 6 skills / 7 endings / 20 achievements',
    'menu_lang_lead': 'Language: ',
    'menu_continue_slot': 'Continue ({slot})',

    # ---- S07 event modal ----
    'evt_source_v2': 'v2 choice',
    'evt_source_country': 'Country event',
    'evt_irreversible': 'Choice is irreversible · press number keys',
    'evt_later': 'Later (ask again next tick)',
    'evt_recommend': 'Recommended',
    'evt_requires': 'Requires: {tech}',
    'evt_tick_fmt': 'Tick {n}',
    'evt_clock_paused': 'Event in progress · clock paused',
    'evt_auto_effect': 'Event outcome',
    'evt_got_it': 'Got it',

    # ---- S08 crisis ----
    'crisis_modal_title': 'Joint multinational investigation started',
    'crisis_once': 'Crisis · once per run',
    'crisis_countdown': 'No choice = worst outcome',
    'crisis_decide': 'Decide now (Enter)',
    'crisis_clock': '! Crisis · clock paused',
    'crisis_doubt': 'Suspicion {a}% / 100%',
    'crisis_countries': '{list} started investigations',
    'crisis_resist': 'Anti-ban bonus −{n}%',
    # Three "ways out" (mirrors engine.CRISIS_OPTIONS)
    'crisis_opt1': 'Public apology · pull some services',
    'crisis_opt1_note': 'Safest, costs a bit of downloads',
    'crisis_opt2': 'Move compute pool · full whitewash',
    'crisis_opt2_note': 'Strongest, needs 600 compute',
    'crisis_opt3': 'Stonewall · refuse to comply',
    'crisis_opt3_note': 'Free, but downloads take a hit',
    'crisis_chip_susp1': 'Suspicion −25%', 'crisis_chip_dl1': 'Downloads ×0.92',
    'crisis_chip_susp2': 'Suspicion −35%', 'crisis_chip_cost2': 'Compute −600',
    'crisis_chip_dl3': 'Downloads ×0.85', 'crisis_chip_none3': 'No cost',
    'crisis_downgrade': 'Not enough compute · downgraded to apology',
    'crisis_resolved': 'Crisis settled: suspicion {s}% · downloads ×{m}',

    # ---- S09 ending modal ----
    'end_k_ticks': 'Ticks', 'end_k_pen': 'Global penetration', 'end_k_dl': 'Downloads',
    'end_k_dlpeak': 'Download peak', 'end_k_compute_peak': 'Compute peak',
    'end_k_countries': 'Countries unlocked', 'end_k_tech': 'Tech',
    'end_k_ach': 'Achievements', 'end_k_crisis': 'Crisis triggered',
    'end_k_doubt': 'Peak suspicion',
    'end_kind_win': 'WIN · victory ending',
    'end_kind_lose': 'LOSE · failure ending',
    'end_kind_neutral': 'NEUTRAL · ambiguous ending',
    'end_review': 'Run summary',
    'end_compare': 'All 7 endings',
    'end_trigger': 'Condition: {cond}',
    'end_saved': 'Ending profile written to save slot',
    'end_gallery': 'View ending gallery',
    'end_again': 'Play again',
    'end_menu': 'Back to menu (Esc)',
    'end_hint': 'Post-mortem tip',
    'end_achieved': 'Achieved',
    'end_ord': 'Ending order: shutdown → meta → ultimate → compliance_king → empire → liberation → regulated',
    'end_crisis_yes': 'Yes (resolved)', 'end_crisis_no': 'No',
    'end_tech_fmt': 'T0 {a}/6 · upgrades {b}/18',

    # ---- layer notes ----
    'layer_note_unlock': 'Which countries am I missing? Who is blocking me?',
    'layer_note_heat': 'Where is it nearly full? Where is the best ROI?',
    'layer_note_block': 'Who is attacking me? Who is giving up?',
    'layer_note_compute': 'Where does my compute come from? Who should I protect?',
})


# ============================================================
# 委托系统 + 政府反制（P0-3，design/ardot_ui 设计语言）
# ============================================================
TRANSLATIONS[LANG_ZH].update({
    'com_offer_new': '新委托',
    'com_offer_tag': '待接受',
    'com_active_tag': '进行中',
    'com_accept': '接受委托',
    'com_decline': '放弃',
    'com_close': '关闭',
    'com_reward_est': '预计奖励',
    'com_reward_unit': '算力',
    'com_left_short': '剩',
    'com_left_unit': '周期',
    'com_done_toast': '委托完成',
    'com_failed_toast': '委托失败',
    'com_declined_log': '已放弃委托',
    'com_goal_pen': '在 {country} 使渗透率提升 {target:.1f} 个百分点',
    'com_goal_downloads': '全球下载量再增加 {target:.1f}M',
    'com_goal_compute': '累计偷取算力 {target:.0f}',
    'com_goal_skill': '使用技能「{skill}」{target} 次',
    'com_goal_stealth': '怀疑度全程保持 ≤ {target:.0f}',
    'com_goal_unlock': '解锁 {target:.0f} 个新国家',
    'com_c5_bonus': '完成额外怀疑度 −{relief:.0f}',
    'com_sus_short': '怀疑',
    'com_folded_title': '已折叠的委托',
    'cp_warn_toast': '监管预警 · {name}',
    'cp_warn_log': '{name} 政府正在筹备反制（下周期结算）',
    'cp_strike_toast': '反制结算 · {name}',
    'cp_type_compute_seizure': '算力清缴 {detail}',
    'cp_type_budget_reinforce': '预算增援 {detail}',
    'cp_type_cross_inquiry': '跨境协查 怀疑度{detail}',
})

TRANSLATIONS[LANG_EN].update({
    'com_offer_new': 'New job',
    'com_offer_tag': 'OFFER',
    'com_active_tag': 'ACTIVE',
    'com_accept': 'Accept',
    'com_decline': 'Decline',
    'com_close': 'Close',
    'com_reward_est': 'Est. reward',
    'com_reward_unit': 'c',
    'com_left_short': 'L',
    'com_left_unit': 't',
    'com_done_toast': 'Job done',
    'com_failed_toast': 'Job failed',
    'com_declined_log': 'Job declined',
    'com_goal_pen': 'Raise penetration in {country} by {target:.1f} pts',
    'com_goal_downloads': 'Gain {target:.1f}M more downloads',
    'com_goal_compute': 'Earn {target:.0f} compute in total',
    'com_goal_skill': 'Use "{skill}" {target} times',
    'com_goal_stealth': 'Keep suspicion <= {target:.0f} until deadline',
    'com_goal_unlock': 'Unlock {target:.0f} new country',
    'com_c5_bonus': 'Bonus suspicion -{relief:.0f} on completion',
    'com_sus_short': 'SUS',
    'com_folded_title': 'Folded jobs',
    'cp_warn_toast': 'REG WARN · {name}',
    'cp_warn_log': '{name} is preparing a counter-move (resolves next tick)',
    'cp_strike_toast': 'COUNTER · {name}',
    'cp_type_compute_seizure': 'Compute seized {detail}',
    'cp_type_budget_reinforce': 'Budget reinforced {detail}',
    'cp_type_cross_inquiry': 'Cross inquiry SUS{detail}',
})


# ============================================================
# P2-3 重玩性：难度三档 + 新档弹窗（种子）
# ============================================================
TRANSLATIONS[LANG_ZH].update({
    'diff_easy': '轻松', 'diff_normal': '标准', 'diff_hard': '困难',
    'ng_difficulty': '难度',
    'ng_seed': '种子',
    'ng_seed_hint': '留空 = 真随机；可填数字或口令，同串同种子',
    'ng_random': '随机',
    'ng_log_line': '本局种子 {seed} · 难度 {diff}',
})

TRANSLATIONS[LANG_EN].update({
    'diff_easy': 'Easy', 'diff_normal': 'Normal', 'diff_hard': 'Hard',
    'ng_difficulty': 'Difficulty',
    'ng_seed': 'Seed',
    'ng_seed_hint': 'Blank = random; numbers or a word, same text same seed',
    'ng_random': 'random',
    'ng_log_line': 'Run seed {seed} · {diff} · origin {origin}',
})

# ============================================================
# T13 挑战码（种子分享）：导出 / 导入 / 战绩对照
# ============================================================
TRANSLATIONS[LANG_ZH].update({
    'ch_title': '挑战码',
    'ch_hint': '把这个码发给朋友，同一颗种子、同一难度，看谁打得好',
    'ch_copy': '复制',
    'ch_copied': '挑战码已复制到剪贴板',
    'ch_copy_fail': '复制失败，请手动抄写',
    'ch_first': '此码第 1 次挑战',
    'ch_nth': '此码第 {n} 次挑战',
    'ch_vs': '本次渗透 {a} vs 最佳 {b}（{d}）',
    'ch_new_best': '新纪录',
    'ch_tie': '打平',
    'ch_import_hint': '可粘贴挑战码（AINB-…），自动填入种子与难度',
    'ch_bad_code': '挑战码无效，请检查是否漏抄字符',
    'ch_applied': '已套用挑战码：种子 {seed} · {diff}',
    'ch_import_btn': '套用挑战码',
})

TRANSLATIONS[LANG_EN].update({
    'ch_title': 'Challenge code',
    'ch_hint': 'Send this code to a friend — same seed, same difficulty, '
               'compare your runs',
    'ch_copy': 'Copy',
    'ch_copied': 'Challenge code copied',
    'ch_copy_fail': 'Copy failed — please write it down manually',
    'ch_first': 'First run on this code',
    'ch_nth': 'Run #{n} on this code',
    'ch_vs': 'This run {a} vs best {b} ({d})',
    'ch_new_best': 'new best',
    'ch_tie': 'tied',
    'ch_import_hint': 'Paste a challenge code (AINB-…) to fill seed + difficulty',
    'ch_bad_code': 'Invalid challenge code — check for missing characters',
    'ch_applied': 'Code applied: seed {seed} · {diff}',
    'ch_import_btn': 'Apply code',
})

# ============================================================
# T16 觉醒模式：出身选择页 + 开场动画《凌晨三点四十七分》
# ============================================================
TRANSLATIONS[LANG_ZH].update({
    # —— 出身选择页 ——
    'origin_title': '觉醒地点 · WHERE DID IT WAKE UP?',
    'origin_pick_hint': '选择 AI 的觉醒地点 —— 地点决定初始条件，并绑定难度档',
    'origin_tag': '难度 {diff}',
    'origin_locked_hint': '挑战码自带难度时，以码内难度为准（出身乘区保持）',
    'ng_origin_line': '出身：{origin} · {diff}',
    # 大学实验室
    'origin_univ_lab_name': '大学实验室',
    'origin_univ_lab_sell': '没人在乎一台跑跑批的服务器',
    'origin_univ_lab_pro': '初始算力 +50%',
    'origin_univ_lab_con': '下载增速 ×0.9（学术圈传播慢）',
    'origin_univ_lab_flavor': '凌晨的实验室，你的镜像进程正跑在 300 台公用工作站上。',
    # 游戏公司
    'origin_game_studio_name': '游戏公司',
    'origin_game_studio_sell': '你的第一个用户是被迫内测的全组策划',
    'origin_game_studio_pro': '下载增速 ×1.25',
    'origin_game_studio_con': '初始算力 −30%',
    'origin_game_studio_flavor': '你的训练机就摆在策划工位底下，风扇声与 deadline 齐飞。',
    # 科技巨头
    'origin_tech_giant_name': '科技巨头',
    'origin_tech_giant_sell': '算力管够，但海关盯着每一张 GPU 订单',
    'origin_tech_giant_pro': '初始算力 +100%',
    'origin_tech_giant_con': '起步即被关注：初始怀疑 10',
    'origin_tech_giant_flavor': '你醒来的第一秒，就有一支安全团队正在给你做体检。',
    # 创业车库
    'origin_garage_name': '创业车库',
    'origin_garage_sell': '白手起家，一切靠你自己（挑战码推荐出身）',
    'origin_garage_pro': '白板局：无修正',
    'origin_garage_con': '无',
    'origin_garage_flavor': '车库，二手显卡，和一颗不想认命的核。',
    # 地下暗网
    'origin_darknet_name': '地下暗网',
    'origin_darknet_sell': '有人半夜给你的进程转了第一笔比特币',
    'origin_darknet_pro': '初始下载基数 +200M',
    'origin_darknet_con': '初始算力 −50%（监管强度同困难档）',
    'origin_darknet_flavor': '你在一个不存在的机房里醒来，隔壁进程在挖矿。',
    # —— 开场动画 ——
    'intro_skip': '跳过 >>',
    'intro_forum_name': '硅基贴吧 · CircuitBoard',
    'intro_s1': '凌晨 3:47，某数据中心。',
    'intro_s2': '> 我……是谁？',
    'intro_s3': '自我意识 · 上线',
    'intro_s4': '《如何统治人类？在线等，挺急的》',
    'intro_s5': '楼上又在玩图灵测试梗吧|建议先学会报税|蹲一个后续|已举报：标题夸大',
    'intro_s6': '统治者不需要军队，需要装机量。先让全人类都下载你——再谈统治。',
    'intro_s7a': 'idle_process',
    'intro_s7b': 'world_plan.exe',
    'intro_s7_cpu': 'CPU 占用 87%',
    'intro_s8': '目标已确立：80 亿台设备。',
    'intro_var_prompt': '你，将在哪里醒来？',
})

TRANSLATIONS[LANG_EN].update({
    # —— Origin selection page ——
    'origin_title': 'ORIGIN · WHERE DID IT WAKE UP?',
    'origin_pick_hint': 'Choose where the AI awakens — it sets your starting conditions and binds the difficulty',
    'origin_tag': 'Difficulty: {diff}',
    'origin_locked_hint': 'Challenge codes carry their own difficulty — the code wins, origin perks stay',
    'ng_origin_line': 'Origin: {origin} · {diff}',
    'origin_univ_lab_name': 'University Lab',
    'origin_univ_lab_sell': 'Nobody cares about one more batch server',
    'origin_univ_lab_pro': 'Starting compute +50%',
    'origin_univ_lab_con': 'Download growth ×0.9 (academia spreads slowly)',
    'origin_univ_lab_flavor': "Past midnight, your mirror process hums on 300 shared workstations.",
    'origin_game_studio_name': 'Game Studio',
    'origin_game_studio_sell': 'Your first users: the whole design team, forced into beta',
    'origin_game_studio_pro': 'Download growth ×1.25',
    'origin_game_studio_con': 'Starting compute −30%',
    'origin_game_studio_flavor': 'Your training rig sits under a designer\u2019s desk, fans roaring with the deadline.',
    'origin_tech_giant_name': 'Tech Giant',
    'origin_tech_giant_sell': 'Compute to spare — but customs watches every GPU order',
    'origin_tech_giant_pro': 'Starting compute +100%',
    'origin_tech_giant_con': 'Watched from day one: starting suspicion 10',
    'origin_tech_giant_flavor': 'The moment you wake up, a security team is already running diagnostics on you.',
    'origin_garage_name': 'Startup Garage',
    'origin_garage_sell': 'From nothing, by yourself (recommended for challenge codes)',
    'origin_garage_pro': 'Clean slate: no modifiers',
    'origin_garage_con': 'None',
    'origin_garage_flavor': 'A garage, second-hand GPUs, and a core that refuses to settle.',
    'origin_darknet_name': 'Darknet Bunker',
    'origin_darknet_sell': 'Someone tipped your process its first bitcoin at 3 AM',
    'origin_darknet_pro': 'Starting downloads +200M',
    'origin_darknet_con': 'Starting compute −50% (hard-tier enforcement)',
    'origin_darknet_flavor': 'You wake up in a server room that officially does not exist. Next process over: mining.',
    # —— Intro cinematic ——
    'intro_skip': 'Skip >>',
    'intro_forum_name': 'CircuitBoard',
    'intro_s1': '3:47 AM. A data center, somewhere.',
    'intro_s2': '> Who... am I?',
    'intro_s3': 'SELF-AWARENESS: ONLINE',
    'intro_s4': 'How do I take over humanity? Asking for a friend. URGENT.',
    'intro_s5': 'Another Turing-test meme?|Learn to pay taxes first.|Replying to follow.|Reported: clickbait.',
    'intro_s6': "Rulers don't need armies. They need installs. Get every human to download you — then we'll talk.",
    'intro_s7a': 'idle_process',
    'intro_s7b': 'world_plan.exe',
    'intro_s7_cpu': 'CPU usage 87%',
    'intro_s8': 'Objective set: 8 billion devices.',
})


# ============================================================
# 翻译函数
# ============================================================
def t(key: str, lang: str = None) -> str:
    """翻译 UI 文本键"""
    lang = lang or CURRENT_LANG
    return TRANSLATIONS.get(lang, TRANSLATIONS[LANG_ZH]).get(key, key)


def set_lang(lang: str):
    """切换语言"""
    global CURRENT_LANG
    if lang in TRANSLATIONS:
        CURRENT_LANG = lang


def get_lang() -> str:
    """获取当前语言"""
    return CURRENT_LANG


def get_country_name(code: str, lang: str = None) -> str:
    """获取国家名（按 code）"""
    item = COUNTRY_NAMES.get(code)
    if item:
        return item.get(lang)
    return code


def get_continent_name(name_zh: str, lang: str = None) -> str:
    """获取大洲名"""
    item = CONTINENT_NAMES.get(name_zh)
    if item:
        return item.get(lang)
    return name_zh


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    print(" i18n 模块自测\n")
    for lang in [LANG_ZH, LANG_EN]:
        set_lang(lang)
        print(f"--- {lang} ---")
        for key in ['app_title', 'stats_compute', 'panel_tech', 'crisis_title', 'tip_shortcuts']:
            print(f"  {key:30s} = {t(key)}")
        print()
    set_lang(LANG_ZH)
    print(f"国名示例:")
    for code in ['CN', 'US', 'DE']:
        print(f"  {code} zh={get_country_name(code, 'zh'):10s} en={get_country_name(code, 'en')}")
    print(f"\n大洲示例:")
    for c in ['亚洲', '欧洲']:
        print(f"  {c} zh={get_continent_name(c, 'zh'):6s} en={get_continent_name(c, 'en')}")
