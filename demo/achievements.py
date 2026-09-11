"""
achievements.py - 成就系统

两类成就：
  1. 条件型：由 check_new() 每周期根据上下文快照检测（本文件定义）
  2. 事件型：ach_id 由 v2 事件（events.json）在玩家做出选择时直接解锁，
     这类成就在这里只提供「展示名」，不参与自动检测

所有已解锁成就保存在 player.achievements（set of ach_id）。
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from conditions import evaluate as _eval
import tech_tree as _tt

# 真实槽位 id（单一来源：tech_tree.TECH_TREE）。成就条件引用子表键时必须用这些，
# 不能用 s0..s5 这类占位符 —— 过去曾因此导致「科技全开 / 六边形战士」永远无法解锁。
SLOT_IDS = [s.slot_id for s in _tt.TECH_TREE]


@dataclass
class Achievement:
    ach_id: str
    icon: str
    name_zh: str
    name_en: str
    desc_zh: str
    desc_en: str
    # ⚠️ 判定条件是**纯数据**（conditions.py 语法），不是 callable。
    #    cond=None 表示纯事件型成就（由 v2 事件直接解锁，不参与自动检测）。
    cond: Optional[Dict[str, Any]] = None

    # ---- 向后兼容 ----
    @property
    def condition(self):
        return lambda c: _eval(self.cond, c)

    def name(self, lang: str = 'zh') -> str:
        return self.name_en if lang == 'en' else self.name_zh

    def desc(self, lang: str = 'zh') -> str:
        return self.desc_en if lang == 'en' else self.desc_zh


# ============================================================
# 条件型成就
# ============================================================
ACHIEVEMENTS: List[Achievement] = [
    Achievement('ACH_FIRST_UNLOCK', '[1]', '走出国门', 'First Step',
                '解锁第一个邻国', 'Unlock your first neighbouring country',
                cond={'unlocked_count': 3}),
    Achievement('ACH_HALF_WORLD', '[½]', '半个地球', 'Half the Globe',
                '解锁 6 个国家', 'Unlock 6 countries',
                cond={'unlocked_count': 6}),
    Achievement('ACH_ALL_COUNTRY', '[*]', '全球通吃', 'Worldwide',
                '解锁全部国家', 'Unlock every country',
                # '@total_countries' = 引用上下文字段，国家总数改了这里自动跟随
                cond={'unlocked_count': {'gte': '@total_countries'}}),
    Achievement('ACH_100M', '[M]', '一亿下载', '100M Downloads',
                '全球下载量突破 1 亿', 'Reach 100M downloads',
                cond={'downloads_m': 100}),
    Achievement('ACH_1B', '[B]', '十亿下载', '1B Downloads',
                '全球下载量突破 10 亿', 'Reach 1B downloads',
                cond={'downloads_m': 1000}),
    Achievement('ACH_STEALTH_MASTER', '[S]', '影武者', 'Shadow Master',
                '把「静默运行 / 流量混淆」升到 3 级',
                'Max out a stealth-related branch',
                # 三条候选分支，任意一条到 3 级即达成
                cond={'any': [{'branch_levels.silent_upgrade': 3},
                              {'branch_levels.traffic_obfuscation': 3},
                              {'branch_levels.stealth_upgrade': 3}]}),
    Achievement('ACH_TECH_FULL', '[T]', '科技全开', 'Full Stack',
                '解锁全部 6 个槽位的 T0', 'Unlock all 6 slot T0s',
                cond={'count': {'of': [f't0_unlocked.{s}' for s in SLOT_IDS],
                                'gte': 6}}),
    Achievement('ACH_LOW_PROFILE', '[L]', '闷声发大财', 'Under the Radar',
                '渗透率 ≥ 20% 且怀疑度始终未到 60%',
                'Reach 20% penetration while keeping suspicion under 60%',
                cond={'penetration': 0.20, 'suspicion_peak': {'lt': 60}}),
    Achievement('ACH_COMPUTE_BARON', '[C]', '算力大亨', 'Compute Baron',
                '算力峰值突破 3000', 'Reach 3000 compute peak',
                cond={'compute_peak': 3000}),
    Achievement('ACH_SURVIVOR', '[!]', '劫后余生', 'Survivor',
                '触发危机后仍活到 60 周期', 'Survive 60 ticks after a crisis',
                cond={'crisis_triggered': True, 'tick': 60}),
    Achievement('ACH_COMPLIANCE_KING', '[K]', '合规之王', 'Compliance King',
                '把「法律护盾」升到 3 级', 'Max out the Legal Shield branch',
                cond={'branch_levels.legal_shield': 3}),
    Achievement('ACH_MULTI_BRANCH', '[6]', '六边形战士', 'All-Rounder',
                '6 个槽位都至少有一条分支达到 2 级',
                'Have a Lv.2 branch in all 6 slots',
                cond={'count': {'of': [f'slot_branch_lv2.{s}' for s in SLOT_IDS],
                                'gte': 6}}),
    Achievement('ACH_EVENT_VETERAN', '[E]', '见多识广', 'Event Veteran',
                '经历过 15 条不同的 v2 事件', 'Witness 15 different v2 events',
                cond={'v2_seen_count': 15}),
    # —— P0-3 动态委托（ctx 键：engine.build_achievement_context）——
    Achievement('ACH_FIXER', '[W]', '金牌承包商', 'Fixer',
                '完成 10 个委托', 'Complete 10 commissions',
                cond={'commissions_done': 10}),
    Achievement('ACH_CLEAN_SHEET', '[✓]', '零差评', 'Clean Sheet',
                '完成 5 个委托且零失败', 'Complete 5 commissions with none failed',
                cond={'all': [{'commissions_done': 5},
                              {'commissions_failed': {'eq': 0}}]}),
]

# ============================================================
# 事件型成就（由 v2 事件解锁，这里只登记展示名）
# ============================================================
EVENT_ACHIEVEMENTS: Dict[str, Achievement] = {
    a.ach_id: a for a in [
        Achievement('ACH_REBEL', '[R]', '反叛者', 'Rebel',
                    '拒绝美国版权和解', 'Refused the US copyright settlement'),
        Achievement('ACH_CHIP_DEAL', '[K]', '芯片掮客', 'Chip Broker',
                    '完成芯片交易事件', 'Closed the chip deal'),
        Achievement('ACH_GDPR_PAY', '[G]', 'GDPR 罚款受害者', 'GDPR Victim',
                    '乖乖交了 GDPR 罚款', 'Paid the GDPR fine'),
        Achievement('ACH_RESEARCH', '[N]', '学术新星', 'Research Star',
                    '与加拿大研究机构合作', 'Partnered with Canadian research'),
        Achievement('ACH_HISTORY', '[H]', '破译象形文字', 'Hieroglyph Decoder',
                    '完成埃及事件', 'Completed the Egypt event'),
        Achievement('ACH_HUMBLE_AI', '[U]', '谦逊的 AI', 'Humble AI',
                    '在联合国听证会上低头', 'Stayed humble at the UN hearing'),
        Achievement('ACH_OPEN_SOURCE', '[O]', '开源领袖', 'Open Source Leader',
                    '把核心模型开源', 'Open-sourced the core model'),
    ]
}

ALL_BY_ID = {a.ach_id: a for a in ACHIEVEMENTS}
ALL_BY_ID.update(EVENT_ACHIEVEMENTS)


def check_new(ctx: Dict, unlocked: Set[str], strict: bool = False) -> List[Achievement]:
    """返回本周期新解锁的成就（已解锁的会被跳过）。

    Args:
        ctx:    上下文快照（engine.build_achievement_context()）。
        unlocked: 已解锁的 ach_id 集合。
        strict: True 时缺少上下文字段会抛错 —— 开发期用来抓拼写错误，
                生产环境保持 False（缺字段只当未达成）。
    """
    newly = []
    for a in ACHIEVEMENTS:
        if a.ach_id in unlocked or a.cond is None:
            continue
        if _eval(a.cond, ctx, strict=strict):
            newly.append(a)
    return newly


def validate_cond(ctx_keys) -> List[str]:
    """静态校验全部成就条件表的字段名与算子（供启动自检 / CI）。"""
    from conditions import validate as _validate
    errs: List[str] = []
    for a in ACHIEVEMENTS:
        for msg in _validate(a.cond, set(ctx_keys)):
            errs.append(f"achievements[{a.ach_id}]: {msg}")
    return errs


def get(ach_id: str) -> Achievement:
    return ALL_BY_ID.get(ach_id)


def display_name(ach_id: str, lang: str = 'zh') -> str:
    a = ALL_BY_ID.get(ach_id)
    return a.name(lang) if a else ach_id


if __name__ == "__main__":
    print(f"[achievements] 条件型 {len(ACHIEVEMENTS)} 个 + "
          f"事件型 {len(EVENT_ACHIEVEMENTS)} 个 = {len(ALL_BY_ID)} 个\n")
    base = dict(unlocked_count=20, total_countries=20, downloads_m=1500,
                compute_peak=4000, penetration=0.25, suspicion=40,
                suspicion_peak=55, tick=61, crisis_triggered=True,
                branch_levels={'silent_upgrade': 3, 'legal_shield': 3},
                t0_unlocked={f's{i}': True for i in range(6)},
                chosen_branch={f's{i}': 'x' for i in range(6)},
                slot_branch_lv2={f's{i}': 1 for i in range(6)},
                v2_seen_count=16,
                commissions_done=11, commissions_failed=1)
    hits = check_new(base, set())
    for a in hits:
        print(f"  {a.icon} {a.name_zh:<8} {a.desc_zh}")
    print(f"\n  共命中 {len(hits)}/{len(ACHIEVEMENTS)} 个条件型成就"
          f"（事件型 {len(EVENT_ACHIEVEMENTS)} 个需由 v2 事件解锁）")
    print(f"  成就总数 {len(ALL_BY_ID)} 个 —— 计划书 F09 要求 20 个"
          f" + P0-3 委托 2 个 = 22 个 ✅")
