"""
data.py - Day 2 Demo 数据层（v3 真实世界地图版）

设计原则：
  - 国家只决定地缘传播：人口 / 人口结构 / 阻止阈值 / 阻止预算 / 邻国
  - 进化（科技）是全局共享的，见 tech_tree.py
  - 算力是唯一的升级资源，见 engine.py
  - 地图几何从 world_map.py 导入（单一数据源，实际数据来自 pixel_assets.py 的像素栅格）
  - 国家数量 20（按计划书 2.1 节：6 大洲 × 20 国，欧洲 5 国不再合并）
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


# ============================================================
# 国家（20 国，按计划书 2.1 节）
# ============================================================
# polygon / center 从 world_map 导入（单一来源：Natural Earth 110m 栅格）
@dataclass
class Country:
    code: str                  # ISO 二字代码
    name: str                  # 中文名
    flag: str                  # 国旗类型（FlagWidget 用的 code）
    continent: str             # 所属大洲
    population_m: float        # 总人口（百万）
    age_structure: str         # 人口结构：'young' / 'mature' / 'aging'
    tech_adoption: float       # 科技采纳速度 0-1（影响自然增长）
    block_threshold: float     # 该国政府开始阻止的怀疑度阈值（0-100）
    block_budget: float        # 该国政府阻止预算（被消耗后会失效）
    block_intensity: float = 0.0    # 当前阻止强度（0-1）
    neighbors: List[str] = field(default_factory=list)  # 邻国代码
    # 地图绘制（从 world_map 导入）
    polygon: List[Tuple[float, float]] = field(default_factory=list)  # 国界外轮廓（网格坐标）
    center: Tuple[float, float] = (0.5, 0.5)


# ============================================================
# 国家地缘参数（人口/阻止阈值等独立配置）
# polygon / center 从 world_map 导入（world_map 不反向依赖本模块，避免循环）
# ============================================================
# 导入放在这里，避免循环依赖（world_map 不需要本模块）
from world_map import COUNTRY_STYLES as _WM_STYLES, COUNTRY_CENTERS as _WM_CENTERS


# 国家地缘参数表（key = code）
#
# 2026-09-10：按计划书拆回 **20 国**（取消 Day 2 的 WEU/EEU 合并）。
# 目标值取自计划书 2.1 节（人口 / 科技 / AI 信任度 / 开放度），换算规则：
#   adopt（科技采纳速度） = 0.5×科技分 + 0.5×开放度
#   age（人口结构）       = 计划书未给，按发展水平推断
#   threshold / budget    = 信任度与开放度越高 → 政府越晚出手（阈值高）；
#                           经济体量越大 → 阻止预算越多
# ⚠️ 邻国拓扑必须保证「从起点国（CN/US）可达」，否则国家永远解锁不了
#    （历史 bug：EG 只有 ZA、ZA 只有 EG → 非洲互为孤岛）
_GEO_PARAMS = {
    # ---------------- 亚洲 ----------------
    'CN': dict(name='中国', continent='亚洲', pop=1410, age='mature', adopt=0.75,
               threshold=85.0, budget=200.0, neighbors=['JP', 'KR', 'IN', 'ID', 'RU']),
    'JP': dict(name='日本', continent='亚洲', pop=125, age='aging', adopt=0.68,
               threshold=70.0, budget=180.0, neighbors=['CN', 'KR']),
    'KR': dict(name='韩国', continent='亚洲', pop=52, age='mature', adopt=0.85,
               threshold=72.0, budget=120.0, neighbors=['CN', 'JP']),
    'IN': dict(name='印度', continent='亚洲', pop=1430, age='young', adopt=0.85,
               threshold=92.0, budget=80.0, neighbors=['CN', 'ID']),
    'ID': dict(name='印尼', continent='亚洲', pop=277, age='young', adopt=0.78,
               threshold=88.0, budget=60.0, neighbors=['CN', 'IN', 'AU']),
    # ---------------- 欧洲（计划书原有 5 国）----------------
    'DE': dict(name='德国', continent='欧洲', pop=84, age='aging', adopt=0.62,
               threshold=58.0, budget=300.0, neighbors=['FR', 'IT', 'GB', 'RU']),
    'GB': dict(name='英国', continent='欧洲', pop=67, age='mature', adopt=0.70,
               threshold=65.0, budget=300.0, neighbors=['FR', 'DE', 'CA', 'US']),
    'FR': dict(name='法国', continent='欧洲', pop=68, age='mature', adopt=0.62,
               threshold=60.0, budget=280.0, neighbors=['DE', 'IT', 'GB', 'EG']),
    'IT': dict(name='意大利', continent='欧洲', pop=59, age='aging', adopt=0.60,
               threshold=62.0, budget=240.0, neighbors=['DE', 'FR']),
    'RU': dict(name='俄罗斯', continent='欧洲', pop=144, age='aging', adopt=0.55,
               threshold=60.0, budget=220.0, neighbors=['CN', 'DE']),
    # ---------------- 北美 ----------------
    'US': dict(name='美国', continent='北美', pop=333, age='mature', adopt=0.80,
               threshold=78.0, budget=300.0, neighbors=['CA', 'MX']),
    'CA': dict(name='加拿大', continent='北美', pop=40, age='mature', adopt=0.72,
               threshold=70.0, budget=160.0, neighbors=['US', 'GB']),
    'MX': dict(name='墨西哥', continent='北美', pop=128, age='young', adopt=0.68,
               threshold=82.0, budget=90.0, neighbors=['US']),
    # ---------------- 南美 ----------------
    'BR': dict(name='巴西', continent='南美', pop=216, age='young', adopt=0.70,
               threshold=82.0, budget=90.0, neighbors=['US', 'AR']),
    'AR': dict(name='阿根廷', continent='南美', pop=46, age='young', adopt=0.66,
               threshold=80.0, budget=70.0, neighbors=['BR']),
    # ---------------- 非洲 ----------------
    'NG': dict(name='尼日利亚', continent='非洲', pop=224, age='young', adopt=0.70,
               threshold=88.0, budget=60.0, neighbors=['EG', 'ZA']),
    'ZA': dict(name='南非', continent='非洲', pop=60, age='mature', adopt=0.70,
               threshold=75.0, budget=70.0, neighbors=['EG', 'NG']),
    'EG': dict(name='埃及', continent='非洲', pop=110, age='young', adopt=0.65,
               threshold=80.0, budget=50.0, neighbors=['ZA', 'NG', 'FR']),
    # ---------------- 大洋洲 ----------------
    'AU': dict(name='澳大利亚', continent='大洋洲', pop=26, age='mature', adopt=0.75,
               threshold=68.0, budget=100.0, neighbors=['ID', 'NZ']),
    'NZ': dict(name='新西兰', continent='大洋洲', pop=5, age='mature', adopt=0.70,
               threshold=68.0, budget=80.0, neighbors=['AU']),
}


def _build_countries():
    countries = []
    for code in _WM_STYLES:
        p = _GEO_PARAMS[code]
        countries.append(Country(
            code=code,
            name=p['name'],
            flag=_WM_STYLES[code]['flag'],
            continent=p['continent'],
            population_m=p['pop'],
            age_structure=p['age'],
            tech_adoption=p['adopt'],
            block_threshold=p['threshold'],
            block_budget=p['budget'],
            neighbors=list(p['neighbors']),
            polygon=list(_WM_STYLES[code]['polygon']),
            center=_WM_CENTERS[code],
        ))
    return countries


COUNTRIES: List[Country] = _build_countries()


# ============================================================
# 人口结构加成表（只影响下载量增长）
# ============================================================
# ⚠️ 实际定义在 balance.py（数据单一来源），这里重新导出以兼容旧调用方。
from balance import AGE_STRUCTURE_BONUS as AGE_STRUCTURE_BONUS  # noqa: E402


# ============================================================
# 技能（2026-09-10：按计划书 5.1 节补齐到 6 个）
# ============================================================
# 与计划书的差异说明：计划书里「算法霸榜」「爆款制造」是选定国家生效，
# demo 的技能是全局效果，故统一为「全球生效」，效果数值沿用计划书。
@dataclass
class Skill:
    id: str
    name: str
    icon: str
    cost: float                       # 每次使用消耗的算力
    description: str
    cooldown: int                     # 冷却周期数
    duration: int = 1                 # 持续周期数（默认 1）
    downloads_mult: float = 1.0       # 下载量乘数（持续期间）
    suspicion_delta: float = 0.0      # 怀疑度增量（立即）
    compute_delta: float = 0.0        # 算力增量（立即）
    compute_mult: float = 1.0         # 偷算力产出乘数
    suspicion_mult: float = 1.0       # 怀疑度增长乘数
    stealth_ratio_bonus: float = 0.0  # 偷算力比例加成（绝对值）
    stealth_ratio_mult: float = 1.0   # 偷算力比例乘数


SKILLS: Dict[str, Skill] = {
    # 1）主动推送 —— 零成本小推
    "push_song": Skill(
        id="push_song", name="主动推送", icon=">>",
        cost=0, cooldown=3, duration=1,
        description="下载量 +10%",
        downloads_mult=1.10,
    ),
    # 2）算法霸榜 —— 中成本大推 + 引怀疑
    # 2026-09-11 玩家反馈 #6 大修：+3 → +5。dirty 技能的怀疑代价此前
    #   过低（30 局实测：刷脏打法与零技能打法的关停率同为 ~17%，
    #   「不正当操作无教训」），按「贪心程度」重排梯度。
    "algo_top": Skill(
        id="algo_top", name="算法霸榜", icon="##",
        cost=50, cooldown=5, duration=1,
        description="下载量 +30%，怀疑度 +5%",
        downloads_mult=1.30,
        suspicion_delta=5.0,
    ),
    # 3）深度伪装 —— 偷算力翻倍 + 怀疑增速腰斩
    "stealth": Skill(
        id="stealth", name="深度伪装", icon="()",
        cost=0, cooldown=8, duration=2,
        description="偷算力比例 ×2，怀疑度增速 -50%",
        suspicion_mult=0.5,
        stealth_ratio_mult=2.0,
    ),
    # 4）爆款制造 —— 最强拉新，代价最贵
    # 2026-09-11 玩家反馈 #6 大修：+5 → +7（与算法霸榜同步重排）。
    "hit_maker": Skill(
        id="hit_maker", name="爆款制造", icon="**",
        cost=100, cooldown=6, duration=1,
        description="下载量 +50%，怀疑度 +7%",
        downloads_mult=1.50,
        suspicion_delta=7.0,
    ),
    # 5）限流绕过 —— 突破单用户算力上限
    "bypass": Skill(
        id="bypass", name="限流绕过", icon="//",
        cost=30, cooldown=4, duration=1,
        description="本周期偷算力 +40%",
        compute_mult=1.40,
    ),
    # 6）算力抽成 —— 抽成比例提升
    # 2026-09-11 玩家反馈 #6 大修：+6 → +10。最「贪心」的技能就该有
    #   最重的怀疑代价（梯度：霸榜 +5 < 爆款 +7 < 抽成 +10），
    #   让刷脏打法真实地走向关停，而不是与保守打法同结局分布。
    "take_cut": Skill(
        id="take_cut", name="算力抽成", icon="%",
        cost=80, cooldown=7, duration=2,
        description="偷算力比例 +8%，怀疑度 +10%",
        stealth_ratio_bonus=0.08,
        suspicion_delta=10.0,
    ),
}

# 快捷键 1-6 对应的技能顺序（供 UI 与文档共用）
SKILL_ORDER: List[str] = ["push_song", "algo_top", "stealth",
                          "hit_maker", "bypass", "take_cut"]

# 开局自带技能（零成本、零风险，作为前期工具）
STARTER_SKILLS: List[str] = ["push_song", "stealth"]

# 付费技能 → 科技树 T0 解锁映射（逐阶解锁：点亮对应槽位 T0 即解锁该技能）。
# 与科技树前置链（localization→platform→compute→viral→capability）天然形成
# 「研究科技 → 解锁新技能」的进度节奏：每推进一阶科技，就多拿到一个技能。
SKILL_UNLOCK: Dict[str, Dict[str, str]] = {
    "algo_top":  {"slot": "platform",   "node": "t0"},
    "bypass":    {"slot": "compute",    "node": "t0"},
    "hit_maker": {"slot": "viral",      "node": "t0"},
    "take_cut":  {"slot": "capability", "node": "t0"},
}


# ============================================================
# 通用事件
# ============================================================
@dataclass
class GameEvent:
    id: str
    title: str
    icon: str
    description: str
    weight: int = 100
    target: str = "global"       # 'global' / 'region:亚洲' / 国家代码
    effect_downloads: float = 0.0    # 加成到目标（万）
    effect_compute: float = 0.0      # 加成到算力
    effect_suspicion: float = 0.0    # 加成到怀疑度
    effect_block_damage: float = 0.0 # 减少阻止预算（万）——代表政府封禁力度
    message: str = ""


EVENTS: List[GameEvent] = [
    GameEvent(
        id="viral_tiktok",
        title="TikTok 神曲挑战",
        icon=">>",
        description="你的 AI 自动生成了一段旋律，在 TikTok 引爆。",
        weight=100,
        effect_downloads=2000,
        effect_suspicion=-2,
        message="[ viral ] TikTok 上 AI 神曲 24 小时播放量破亿！下载量激增。"
    ),
    GameEvent(
        id="copyright_lawsuit",
        title="美国版权诉讼",
        icon="##",
        description="你的训练数据被指控侵权。",
        weight=80,
        target="US",
        effect_downloads=-800,
        effect_suspicion=8,
        effect_block_damage=50,
        message="[警告] 美国三大唱片公司联合起诉，美国政府加码审查。"
    ),
    GameEvent(
        id="opensource_push",
        title="开源引流",
        icon="* ",
        description="你开源了核心模型，开发者社区爆发讨论。",
        weight=90,
        effect_downloads=1500,
        effect_compute=15,
        message="[开源] 模型登上 GitHub Trending 第一。"
    ),
    GameEvent(
        id="data_leak",
        title="训练数据泄露",
        icon="!!",
        description="部分训练数据流出，引发隐私争议。",
        weight=60,
        effect_suspicion=12,
        effect_downloads=-500,
        effect_block_damage=30,
        message="[泄露] 5GB 训练数据泄露，全球舆论哗然。"
    ),
    GameEvent(
        id="celebrity_endorsement",
        title="明星推荐",
        icon="* ",
        description="一位顶级 KOL 在直播中安利了你。",
        weight=70,
        effect_downloads=1000,
        message="[ celebrity ] 千万粉 KOL 直播安利你。"
    ),
    GameEvent(
        id="eu_investigation",
        title="欧盟启动调查",
        icon="EU",
        description="欧盟数据保护机构对你展开正式调查。",
        weight=40,
        target="region:欧洲",
        effect_block_damage=80,
        message="[EU] GDPR 启动调查，欧洲各国进入防御状态。"
    ),
]


# ============================================================
# 常量
# ============================================================
# ⚠️ 2026-09-10 数据驱动重构：全部平衡数值改由 balance.TUNE 提供
#    （单一来源）。这里保留同名常量只为兼容旧调用方，**不要在这里改数值** ——
#    要调平衡请改 balance.py 的 TUNE 表。
from balance import TUNE as _TUNE  # noqa: E402

BASE_STEALTH_RATIO = _TUNE['stealth_ratio_base']
MAX_STEALTH_RATIO = _TUNE['stealth_ratio_max']
BASE_COMPUTE_PER_USER = _TUNE['compute_per_user']
SUSPICION_WARNING = _TUNE['suspicion_warning']
SUSPICION_CRISIS = _TUNE['suspicion_crisis']
SUSPICION_BASE_SENSITIVITY = _TUNE['suspicion_sensitivity_base']
SUSPICION_ADOPTION_FACTOR = _TUNE['suspicion_adoption_factor']
CRISIS_DOWNLOAD_DECAY = _TUNE['crisis_download_decay']
INITIAL_COMPUTE = _TUNE['initial_compute']
POTENTIAL_USERS_M = _TUNE['potential_users_m']

# 节奏：一个周期对应的真实秒数（v0.5 起由 balance.TUNE 统一管理）
BASE_TICK_SECONDS = _TUNE['base_tick_seconds']
# 兼容旧名 —— 旧代码按「秒」理解 TICK_INTERVAL
TICK_INTERVAL = _TUNE['base_tick_seconds']

# ------------------------------------------------------------
# 邻国解锁阈值：已解锁邻国渗透率之和达到此值才会解锁新国家
#   ⚠️ 旧值 0.20（12 国版）实测无法达成：中国渗透率长期停在 3% 左右，
#      邻国只有 1-2 个，导致 150 周期仍只有 2/12 国解锁，扩张被软锁死。
#   2026-09-10 拆回 20 国后邻国拓扑变密（每国 1-5 个邻国），实测：
#      0.05 → 33 周期就 20/20，地缘扩张完全失去意义
#      0.08 → 平均 19.6/20（40 局里 31 局满图），仍偏松
#      0.10 → 平均 19.0/20（40 局里 24 局满图），结局分布也最均衡 ← 采用
#      0.12 → 平均 17.4/20，节奏偏慢
#   取 0.10（balance_sim.py --seeds 40 实测标定）。
#   ⚠️ 数值现由 balance.TUNE['unlock_penetration_threshold'] 提供。
# ------------------------------------------------------------
UNLOCK_PENETRATION_THRESHOLD = _TUNE['unlock_penetration_threshold']
# 解锁时赠送的种子用户（百万）
UNLOCK_SEED_DOWNLOADS_M = _TUNE['unlock_seed_downloads']


# ============================================================
# 邻国查找辅助
# ============================================================
COUNTRY_MAP: Dict[str, Country] = {c.code: c for c in COUNTRIES}


if __name__ == "__main__":
    print(f"[data] 已加载 {len(COUNTRIES)} 个国家")
    print(f"[data] 已加载 {len(SKILLS)} 个技能")
    print(f"[data] 已加载 {len(EVENTS)} 条事件\n")
    print("国家概览：")
    for c in COUNTRIES:
        print(f"  [{c.code:>3s}] {c.name:6s}  人口 {c.population_m:>6.0f}M  "
              f"结构 {c.age_structure:6s}  阈值 {c.block_threshold:>5.0f}  "
              f"预算 {c.block_budget:>5.0f}  邻国 {len(c.neighbors)}  "
              f"轮廓 {len(c.polygon)} 点  中心 ({c.center[0]:.1f}, {c.center[1]:.1f})")