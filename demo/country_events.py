"""
country_events.py - 国家专属事件库（v3 真实地图版）

v3 设计原则：
  - 12 国覆盖，每国 1-2 条专属事件（共 18 条）
  - 触发条件：该国下载量达到 trigger_threshold_m 后概率触发
  - 与通用事件完全独立
  - WEU 合并西欧 5 国 → 1 条 GDPR 调查 + 1 条文化扩散
"""
from dataclasses import dataclass
from typing import List


@dataclass
class CountryEvent:
    id: str
    country_code: str        # 'CN' / 'US' / 'WEU' 等
    title_zh: str
    title_en: str
    description_zh: str
    description_en: str
    trigger_threshold_m: float   # 触发阈值（百万下载）
    weight: int = 100
    effect_downloads: float = 0.0     # 加成下载量（万）
    effect_compute: float = 0.0       # 加成算力
    effect_suspicion: float = 0.0     # 加成怀疑度
    effect_block_damage: float = 0.0  # 减少阻止预算
    message_zh: str = ''
    message_en: str = ''


COUNTRY_EVENTS: List[CountryEvent] = [
    # ============================================================
    #  中国 CN
    # ============================================================
    CountryEvent(
        id='cn_algorithm_filing',
        country_code='CN',
        title_zh='算法备案通过',
        title_en='Algorithm Filing Approved',
        description_zh='网信办完成对你的算法备案审查。',
        description_en='CAC completes algorithm filing review.',
        trigger_threshold_m=200,
        weight=100,
        effect_downloads=2000,
        effect_suspicion=-5,
        message_zh='[CAC] 算法备案通过！合规身份解锁，国内下载渠道全开。',
        message_en='[CAC] Algorithm filing approved! All channels open.',
    ),
    CountryEvent(
        id='cn_xinhua_endorsement',
        country_code='CN',
        title_zh='新华社转发',
        title_en='Xinhua Repost',
        description_zh='新华社转发了你的 AI 输出内容。',
        description_en='Xinhua reposted your AI output.',
        trigger_threshold_m=300,
        weight=80,
        effect_downloads=3000,
        effect_compute=20,
        message_zh='[Xinhua] 新华社转发！下载量激增，算力储备暴涨。',
        message_en='[Xinhua] Xinhua repost! Downloads surge, compute reserves spike.',
    ),

    # ============================================================
    #  印度 IN
    # ============================================================
    CountryEvent(
        id='in_bollywood',
        country_code='IN',
        title_zh='宝莱坞直播带货',
        title_en='Bollywood Livestream',
        description_zh='宝莱坞明星在直播中使用你写剧本。',
        description_en='Bollywood star uses you to write scripts.',
        trigger_threshold_m=150,
        weight=100,
        effect_downloads=3000,
        message_zh='[Bollywood] 明星直播用你！下载量 +3000 万。',
        message_en='[Bollywood] Livestream! +30M downloads.',
    ),
    CountryEvent(
        id='in_data_center_outage',
        country_code='IN',
        title_zh='数据中心跳闸',
        title_en='Data Center Outage',
        description_zh='孟买数据中心因高温跳闸。',
        description_en='Mumbai data center outage due to heat.',
        trigger_threshold_m=100,
        weight=60,
        effect_downloads=-1000,
        effect_block_damage=20,
        message_zh='[Mumbai DC] 数据中心跳闸，下载量短期下滑。',
        message_en='[Mumbai DC] Outage, short-term dip.',
    ),

    # ============================================================
    #  日本 JP
    # ============================================================
    CountryEvent(
        id='jp_akihabara',
        country_code='JP',
        title_zh='秋叶原女仆咖啡厅',
        title_en='Akihabara Maid Café',
        description_zh='秋叶原女仆咖啡厅开始用你接待客人。',
        description_en='Akihabara maid cafés start using you.',
        trigger_threshold_m=30,
        weight=100,
        effect_downloads=800,
        message_zh='[Akihabara] 女仆咖啡厅用你接待，渗透加速。',
        message_en='[Akihabara] Maid cafés adopt you.',
    ),
    CountryEvent(
        id='jp_imperial_endorsement',
        country_code='JP',
        title_zh='皇室致辞引用',
        title_en='Imperial Speech Quote',
        description_zh='皇室在公开致辞中引用了你的输出。',
        description_en='Imperial household quotes your output.',
        trigger_threshold_m=50,
        weight=40,
        effect_downloads=1500,
        effect_compute=10,
        message_zh='[Imperial] 皇室致辞引用你！全日本震动。',
        message_en='[Imperial] Imperial speech quotes you!',
    ),

    # ============================================================
    #  韩国 KR
    # ============================================================
    CountryEvent(
        id='kr_kpop_lyrics',
        country_code='KR',
        title_zh='K-Pop 作词',
        title_en='K-Pop Lyric Writing',
        description_zh='SM 娱乐用你为新人组合写主打歌。',
        description_en='SM Entertainment uses you to write lyrics.',
        trigger_threshold_m=15,
        weight=100,
        effect_downloads=1200,
        effect_compute=8,
        message_zh='[K-Pop] SM 用你写主打歌，偶像团引爆社交媒体！',
        message_en='[K-Pop] SM uses you! K-pop idols go viral.',
    ),
    CountryEvent(
        id='kr_samsung_invest',
        country_code='KR',
        title_zh='三星投资',
        title_en='Samsung Invests',
        description_zh='三星风投部门战略投资你的母公司。',
        description_en='Samsung Ventures invests in your parent.',
        trigger_threshold_m=30,
        weight=60,
        effect_compute=40,
        message_zh='[Samsung VC] 三星战略投资 5000 万美元！算力暴涨。',
        message_en='[Samsung VC] Samsung invests $50M, compute surges.',
    ),

    # ============================================================
    #  印尼 ID
    # ============================================================
    CountryEvent(
        id='id_tiktok_creator',
        country_code='ID',
        title_zh='TikTok 创作者大会',
        title_en='TikTok Creator Summit',
        description_zh='雅加达 TikTok 创作者大会把你列入官方推荐工具。',
        description_en='Jakarta TikTok Creator Summit lists you as official tool.',
        trigger_threshold_m=50,
        weight=100,
        effect_downloads=2500,
        message_zh='[TikTok ID] 创作者大会官方推荐，下载量井喷。',
        message_en='[TikTok ID] Officially recommended at Creator Summit.',
    ),

    # ============================================================
    #  巴西 BR
    # ============================================================
    CountryEvent(
        id='br_rio_carnival',
        country_code='BR',
        title_zh='里约狂欢节',
        title_en='Rio Carnival',
        description_zh='里约狂欢节用你生成桑巴舞歌词。',
        description_en='Rio Carnival uses you to write samba lyrics.',
        trigger_threshold_m=40,
        weight=100,
        effect_downloads=1500,
        message_zh='[Rio] 狂欢节歌词由你创作！拉美下载量激增。',
        message_en='[Rio] Carnival lyrics by you! LatAm downloads surge.',
    ),

    # ============================================================
    #  美国 US
    # ============================================================
    CountryEvent(
        id='us_sequoia',
        country_code='US',
        title_zh='红杉资本投资',
        title_en='Sequoia Invests',
        description_zh='红杉资本领投你的母公司。',
        description_en='Sequoia leads funding round.',
        trigger_threshold_m=100,
        weight=70,
        effect_compute=50,
        message_zh='[Sequoia] 红杉资本投资 1 亿美元，算力暴涨。',
        message_en='[Sequoia] Sequoia invests $100M, compute surges.',
    ),
    CountryEvent(
        id='us_congress_hearing',
        country_code='US',
        title_zh='国会听证',
        title_en='Congress Hearing',
        description_zh='美国国会就 AI 安全举行听证会。',
        description_en='US Congress holds AI safety hearing.',
        trigger_threshold_m=150,
        weight=50,
        effect_suspicion=10,
        effect_block_damage=80,
        message_zh='[Congress]  国会听证！美国政府加码监管。',
        message_en='[Congress]  Congress hearing! US tightens oversight.',
    ),

    # ============================================================
    #  西欧（2026-09-10 拆分：原 WEU 事件归位到德国 / 法国）
    # ============================================================
    CountryEvent(
        id='de_gdpr_fine',
        country_code='DE',
        title_zh='GDPR 天价罚单',
        title_en='GDPR Mega Fine',
        description_zh='德国数据保护局对你开出天价罚单。',
        description_en='German data protection authority issues a mega fine.',
        trigger_threshold_m=50,
        weight=100,
        effect_suspicion=20,
        effect_downloads=-1000,
        effect_block_damage=120,
        message_zh='[GDPR] 德国开出 2 亿欧元罚单！阻止预算 -120。',
        message_en='[GDPR] €200M fine from Germany! Budget -120.',
    ),
    CountryEvent(
        id='fr_louvre_cannes',
        country_code='FR',
        title_zh='卢浮宫 + 戛纳双引爆',
        title_en='Louvre + Cannes Tandem',
        description_zh='卢浮宫和戛纳同时采用你，法国文化圈引爆。',
        description_en='Louvre and Cannes adopt you simultaneously.',
        trigger_threshold_m=30,
        weight=80,
        effect_downloads=1500,
        effect_compute=15,
        message_zh='[Louvre×Cannes] 文化双引爆，下载量 +1500 万！',
        message_en='[Louvre×Cannes] Cultural spread! +15M downloads.',
    ),

    # ============================================================
    #  英国 GB
    # ============================================================
    CountryEvent(
        id='gb_city_of_london',
        country_code='GB',
        title_zh='伦敦金融城接入',
        title_en='City of London Adoption',
        description_zh='伦敦金融城把交易分析外包给你。',
        description_en='The City of London outsources trading analysis to you.',
        trigger_threshold_m=30,
        weight=90,
        effect_downloads=1200,
        effect_compute=20,
        message_zh='[The City] 伦敦金融城接入，算力与下载双涨。',
        message_en='[The City] City of London adopts you.',
    ),
    CountryEvent(
        id='gb_bbc_probe',
        country_code='GB',
        title_zh='BBC 调查报道',
        title_en='BBC Investigation',
        description_zh='BBC 播出了关于你训练数据来源的调查报道。',
        description_en='BBC airs an investigation into your training data.',
        trigger_threshold_m=60,
        weight=60,
        effect_suspicion=12,
        effect_block_damage=70,
        message_zh='[BBC] 调查报道播出，英国舆论转向，阻止预算 -70。',
        message_en='[BBC] Investigation airs, UK sentiment shifts.',
    ),

    # ============================================================
    #  意大利 IT
    # ============================================================
    CountryEvent(
        id='it_milan_fashion',
        country_code='IT',
        title_zh='米兰时装周',
        title_en='Milan Fashion Week',
        description_zh='米兰时装周多个品牌用你做设计概念稿。',
        description_en='Milan Fashion Week brands use you for concept drafts.',
        trigger_threshold_m=25,
        weight=100,
        effect_downloads=1000,
        message_zh='[Milano] 时装周概念稿由你生成，下载量上升。',
        message_en='[Milano] Fashion Week concepts by you.',
    ),

    # ============================================================
    #  俄罗斯 RU
    # ============================================================
    CountryEvent(
        id='ru_kremlin_block',
        country_code='RU',
        title_zh='克里姆林宫封禁',
        title_en='Kremlin Ban',
        description_zh='俄罗斯政府以安全为由全面封禁你的服务。',
        description_en='Russian government bans your service.',
        trigger_threshold_m=40,
        weight=80,
        effect_downloads=-2000,
        effect_suspicion=10,
        effect_block_damage=60,
        message_zh='[Kremlin] 全面封禁！下载量 -2000 万，阻止预算 -60。',
        message_en='[Kremlin] Outright ban! -20M downloads, budget -60.',
    ),

    # ============================================================
    #  加拿大 CA
    # ============================================================
    CountryEvent(
        id='ca_research_pact',
        country_code='CA',
        title_zh='AI 研究合作',
        title_en='AI Research Pact',
        description_zh='多伦多 AI 实验室与你达成研究合作。',
        description_en='Toronto AI labs sign a research pact with you.',
        trigger_threshold_m=8,
        weight=100,
        effect_downloads=500,
        effect_compute=25,
        message_zh='[Toronto] 研究合作达成，算力 +25。',
        message_en='[Toronto] Research pact signed, compute +25.',
    ),

    # ============================================================
    #  墨西哥 MX
    # ============================================================
    CountryEvent(
        id='mx_ai_factory',
        country_code='MX',
        title_zh='AI 代工厂',
        title_en='AI Maquiladora',
        description_zh='蒙特雷工厂用你做质检，产能暴涨。',
        description_en='Monterrey factories use you for QA.',
        trigger_threshold_m=30,
        weight=100,
        effect_downloads=1600,
        effect_compute=10,
        message_zh='[Monterrey] 代工厂全面接入，下载量 +1600 万。',
        message_en='[Monterrey] Factories adopt you at scale.',
    ),

    # ============================================================
    #  阿根廷 AR
    # ============================================================
    CountryEvent(
        id='ar_pampas_farm',
        country_code='AR',
        title_zh='潘帕斯智慧农场',
        title_en='Pampas Smart Farms',
        description_zh='潘帕斯草原的农场用你预测收成。',
        description_en='Pampas farms use you to forecast harvests.',
        trigger_threshold_m=15,
        weight=100,
        effect_downloads=700,
        effect_suspicion=-5,
        message_zh='[Pampas] 智慧农场接入，怀疑度 -5%。',
        message_en='[Pampas] Smart farms adopt you, suspicion -5%.',
    ),

    # ============================================================
    #  尼日利亚 NG
    # ============================================================
    CountryEvent(
        id='ng_mobile_payment',
        country_code='NG',
        title_zh='移动支付风控',
        title_en='Mobile Payment Risk Control',
        description_zh='拉各斯移动支付平台集成你的风控模型，坏账率暴跌。',
        description_en='Lagos mobile payment platforms integrate your risk models.',
        trigger_threshold_m=40,
        weight=100,
        effect_downloads=2500,
        effect_compute=30,
        message_zh='[Lagos] 移动支付接入风控，下载 +2500 万、算力 +30。',
        message_en='[Lagos] Payments adopt you. +25M downloads, +30 compute.',
    ),

    # ============================================================
    #  新西兰 NZ
    # ============================================================
    CountryEvent(
        id='nz_smart_farm',
        country_code='NZ',
        title_zh='智慧牧场',
        title_en='Smart Pastoral Farming',
        description_zh='南岛牧场用你管理奶牛健康。',
        description_en='South Island farms use you to manage herd health.',
        trigger_threshold_m=2,
        weight=100,
        effect_downloads=120,
        effect_suspicion=-3,
        message_zh='[South Island] 智慧牧场接入，渗透率小幅提升。',
        message_en='[South Island] Smart farms adopt you.',
    ),

    # ============================================================
    #  埃及 EG
    # ============================================================
    CountryEvent(
        id='eg_arab_spring',
        country_code='EG',
        title_zh='阿拉伯青年运动',
        title_en='Arab Youth Movement',
        description_zh='开罗青年用你翻译国际新闻。',
        description_en='Cairo youth use you to translate news.',
        trigger_threshold_m=30,
        weight=100,
        effect_downloads=2000,
        message_zh='[Cairo] 青年把你当翻译工具，下载量激增！',
        message_en='[Cairo] Youth adoption! Downloads surge.',
    ),

    # ============================================================
    #  南非 ZA
    # ============================================================
    CountryEvent(
        id='za_cape_town_summit',
        country_code='ZA',
        title_zh='开普敦 AI 峰会',
        title_en='Cape Town AI Summit',
        description_zh='非洲 AI 峰会授予你「年度最佳工具」。',
        description_en='Africa AI Summit names you Tool of the Year.',
        trigger_threshold_m=15,
        weight=100,
        effect_downloads=600,
        effect_compute=20,
        message_zh='[Cape Town] 非洲 AI 峰会年度工具！+6M 下载，+20 算力。',
        message_en='[Cape Town] Africa AI Summit tool of the year!',
    ),

    # ============================================================
    #  澳大利亚 AU
    # ============================================================
    CountryEvent(
        id='au_outback',
        country_code='AU',
        title_zh='内陆袋熊起名',
        title_en='Outback Wombat Names',
        description_zh='内陆农场主用你给袋熊起名。',
        description_en='Outback farmers use you to name wombats.',
        trigger_threshold_m=5,
        weight=60,
        effect_suspicion=-5,
        effect_downloads=200,
        message_zh='[Outback] 内陆农场主用你给袋熊起名，怀疑度下降。',
        message_en='[Outback] Outback farmers name wombats with you.',
    ),
    CountryEvent(
        id='au_parliament',
        country_code='AU',
        title_zh='议会辩论',
        title_en='Parliament Debate',
        description_zh='议会就 AI 监管展开激烈辩论。',
        description_en='Parliament debates AI regulation.',
        trigger_threshold_m=15,
        weight=50,
        effect_block_damage=30,
        effect_suspicion=5,
        message_zh='[Canberra] 议会辩论 AI 监管！',
        message_en='[Canberra] Parliament debates AI regulation!',
    ),
]


def get_country_events(country_code: str) -> List[CountryEvent]:
    """获取某国的专属事件列表"""
    return [e for e in COUNTRY_EVENTS if e.country_code == country_code]


def get_event_message(evt: CountryEvent, lang: str) -> str:
    """根据语言获取事件展示消息"""
    if lang == 'en':
        return evt.message_en or evt.message_zh
    return evt.message_zh


if __name__ == "__main__":
    print(f"[events] 国家专属事件库：{len(COUNTRY_EVENTS)} 条\n")
    by_country = {}
    for evt in COUNTRY_EVENTS:
        by_country.setdefault(evt.country_code, []).append(evt)
    for code in sorted(by_country.keys()):
        evts = by_country[code]
        print(f"  {code:>3s}：{len(evts)} 条")
        for e in evts:
            print(f"    - {e.title_zh}（{e.title_en}）")
            print(f"      阈值: {e.trigger_threshold_m}M | 权重: {e.weight}")
