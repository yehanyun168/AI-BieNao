"""
tech_tree.py - 分支型科技树（核心机制）

设计原则：
  - 进化（科技）都是全局性的，不分国家
  - 资源消耗：算力
  - 结构：6 个平行槽位，每个槽位有 1 个 T0 + 3 条并行分支
  - 每个分支可点 3 级（L1/L2/L3），效果递增
  - 各槽位 T0 可独立解锁；必须先点 T0，才能点该槽位的任何分支
  - **同一槽位的 3 条分支并行、可全部点满**（v0.5 起取消互斥，
    参考《瘟疫公司》的科技树：不惩罚玩家做多线投入，选择是「先点哪条」
    的节奏问题，而非「只能选一条」的排他问题）

总览：
  6 槽位 × (1 T0 + 3 分支) = 24 个科技 ID
  3 分支 × 3 级 = 9 次升级 / 槽位
  总计 6 × 9 = 54 次可升级次数

玩家体验：
  - 早期：先把所有 T0 点满（6 个，~120 算力）
  - 中期：按收益优先级把关键分支推到 L1/L2
  - 后期：全树点满（54 次）
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ============================================================
# 科技分支（每个分支 3 级）
# ============================================================
@dataclass
class TechBranch:
    branch_id: str                    # 例如 'spanish'
    name: str                         # 例如 '西语优化'
    icon: str                         # 例如 ''
    description: str                  # 分支说明
    effects_per_level: List[dict]     # [L1效果, L2效果, L3效果]，每个效果是 dict
    costs: List[float]                # [L1算力, L2算力, L3算力]


# ============================================================
# 科技槽位（1 个 T0 + 多个互斥分支）
# ============================================================
@dataclass
class TechSlot:
    slot_id: str                  # 例如 'localization'
    name: str                     # 例如 '本地化'
    icon: str                     # 例如 ''
    description: str              # 槽位作用
    prereq_slot: Optional[str]    # 上游槽位 id（必须先解锁该上游槽位的 T0）
    t0_cost: float                # T0 算力消耗
    t0_effect: dict               # T0 效果
    branches: List[TechBranch] = field(default_factory=list)


# ============================================================
# 6 个槽位（共 24 个科技 ID）
# ============================================================
TECH_TREE: List[TechSlot] = [
    # ------------------- Slot 1: 本地化（无前置）-------------------
    TechSlot(
        slot_id='localization',
        name='本地化',
        icon='L',
        description='解锁亚洲 / 欧洲市场，并按语系深耕当地下载量',
        prereq_slot=None,
        t0_cost=20,
        t0_effect={'type': 'unlock_regions', 'regions': ['亚洲', '欧洲']},
        branches=[
            TechBranch(
                branch_id='south_asia',
                name='南亚语系',
                icon='SA',
                description='南亚与东南亚深耕（中/印/印尼）：三地下载量提升 10% / 25% / 50%。',
                effects_per_level=[
                    {'type': 'downloads_mult', 'scope': 'CN+IN+ID', 'value': 1.10},
                    {'type': 'downloads_mult', 'scope': 'CN+IN+ID', 'value': 1.25},
                    {'type': 'downloads_mult', 'scope': 'CN+IN+ID', 'value': 1.50},
                ],
                costs=[40, 80, 150],
            ),
            TechBranch(
                branch_id='european',
                name='欧洲语系',
                icon='EU',
                description='西欧语种深耕（德/法/英/意）：四地下载量提升 10% / 25% / 50%。',
                effects_per_level=[
                    {'type': 'downloads_mult', 'scope': 'DE+FR+GB+IT', 'value': 1.10},
                    {'type': 'downloads_mult', 'scope': 'DE+FR+GB+IT', 'value': 1.25},
                    {'type': 'downloads_mult', 'scope': 'DE+FR+GB+IT', 'value': 1.50},
                ],
                costs=[40, 80, 150],
            ),
            TechBranch(
                branch_id='east_asian',
                name='东亚语系',
                icon='EA',
                description='东亚市场深耕：日/韩/中三地下载量分别提升 10% / 25% / 50%。',
                effects_per_level=[
                    {'type': 'downloads_mult', 'scope': 'JP+KR+CN', 'value': 1.10},
                    {'type': 'downloads_mult', 'scope': 'JP+KR+CN', 'value': 1.25},
                    {'type': 'downloads_mult', 'scope': 'JP+KR+CN', 'value': 1.50},
                ],
                costs=[40, 80, 150],
            ),
        ],
    ),

    # ------------------- Slot 2: 平台渗透（无前置）-------------------
    TechSlot(
        slot_id='platform',
        name='平台渗透',
        icon='P',
        description='触达更多终端：T0 解锁后全局下载量 +10%',
        prereq_slot=None,
        t0_cost=25,
        t0_effect={'type': 'global_downloads_mult', 'value': 1.10},
        branches=[
            TechBranch(
                branch_id='mobile_native',
                name='移动原生',
                icon='MO',
                description='原生 App 预装触达：全局下载量提升 10% / 25% / 50%。',
                effects_per_level=[
                    {'type': 'global_downloads_mult', 'value': 1.10},
                    {'type': 'global_downloads_mult', 'value': 1.25},
                    {'type': 'global_downloads_mult', 'value': 1.50},
                ],
                costs=[50, 100, 200],
            ),
            TechBranch(
                branch_id='web_pwa',
                name='Web/PWA',
                icon='WEB',
                description='免安装即点即用：每用户偷算力效率提升 15% / 30% / 60%。',
                effects_per_level=[
                    {'type': 'compute_per_user_mult', 'value': 1.15},
                    {'type': 'compute_per_user_mult', 'value': 1.30},
                    {'type': 'compute_per_user_mult', 'value': 1.60},
                ],
                costs=[50, 100, 200],
            ),
            TechBranch(
                branch_id='os_integration',
                name='系统集成',
                icon='OS',
                description='预装进系统：L1 全局下载量 +20%；L2 单位用户算力 +20%；L3 抗阻止 +20%。',
                effects_per_level=[
                    {'type': 'global_downloads_mult', 'value': 1.20},
                    {'type': 'compute_per_user_mult', 'value': 1.20},
                    {'type': 'block_resist', 'value': 0.20},  # 抗阻止
                ],
                costs=[50, 100, 200],
            ),
        ],
    ),

    # ------------------- Slot 3: 算力效率（无前置）-------------------
    TechSlot(
        slot_id='compute',
        name='算力效率',
        icon='C',
        description='优化的偷算力管道：T0 解锁后单位用户算力 +15%',
        prereq_slot=None,
        t0_cost=30,
        t0_effect={'type': 'compute_per_user_mult', 'value': 1.15},
        branches=[
            TechBranch(
                branch_id='stealth_upgrade',
                name='隐蔽调度',
                icon='ST',
                description='拉高隐蔽偷算力比例，每级 +3%（5% → 8% / 11% / 14%）。',
                effects_per_level=[
                    {'type': 'stealth_ratio_bonus', 'value': 0.03},  # 5% → 8% → 11% → 14%
                    {'type': 'stealth_ratio_bonus', 'value': 0.03},
                    {'type': 'stealth_ratio_bonus', 'value': 0.03},
                ],
                costs=[60, 120, 220],
            ),
            TechBranch(
                branch_id='yield_upgrade',
                name='单位效率',
                icon='Y',
                description='压榨单机算力：每级单位用户算力 ×1.30（三级叠乘约 ×2.2）。',
                effects_per_level=[
                    {'type': 'compute_per_user_mult', 'value': 1.30},
                    {'type': 'compute_per_user_mult', 'value': 1.30},
                    {'type': 'compute_per_user_mult', 'value': 1.30},
                ],
                costs=[60, 120, 220],
            ),
            TechBranch(
                branch_id='silent_upgrade',
                name='静默运行',
                icon='SI',
                description='全局降低怀疑度增速：逐级 ×0.80 / ×0.60 / ×0.40。',
                effects_per_level=[
                    {'type': 'suspicion_mult', 'value': 0.80},
                    {'type': 'suspicion_mult', 'value': 0.60},
                    {'type': 'suspicion_mult', 'value': 0.40},
                ],
                costs=[60, 120, 220],
            ),
        ],
    ),

    # ------------------- Slot 4: 病毒传播（无前置）-------------------
    TechSlot(
        slot_id='viral',
        name='病毒传播',
        icon='V',
        description='让用户替你扩散：T0 解锁后全局下载量 +15%',
        prereq_slot=None,
        t0_cost=35,
        t0_effect={'type': 'global_downloads_mult', 'value': 1.15},
        branches=[
            TechBranch(
                branch_id='referral',
                name='推荐返利',
                icon='REF',
                description='老带新裂变：已解锁地区下载量提升 15% / 30% / 50%。',
                effects_per_level=[
                    {'type': 'downloads_mult', 'scope': 'unlocked', 'value': 1.15},
                    {'type': 'downloads_mult', 'scope': 'unlocked', 'value': 1.30},
                    {'type': 'downloads_mult', 'scope': 'unlocked', 'value': 1.50},
                ],
                costs=[70, 140, 260],
            ),
            TechBranch(
                branch_id='kol',
                name='KOL 合作',
                icon='KOL',
                description='头部创作者带货：全局下载量提升 20% / 40% / 70%（本槽位最高增幅）。',
                effects_per_level=[
                    {'type': 'global_downloads_mult', 'value': 1.20},
                    {'type': 'global_downloads_mult', 'value': 1.40},
                    {'type': 'global_downloads_mult', 'value': 1.70},
                ],
                costs=[70, 140, 260],
            ),
            TechBranch(
                branch_id='viral_content',
                name='病毒内容',
                icon='VIR',
                description='L1 已解锁地区下载量 +20%；L2/L3 把「爆款视频」事件触发权重 ×2 / ×3。',
                effects_per_level=[
                    {'type': 'downloads_mult', 'scope': 'unlocked', 'value': 1.20},
                    {'type': 'event_weight', 'event_id': 'viral_tiktok', 'value': 2.0},
                    {'type': 'event_weight', 'event_id': 'viral_tiktok', 'value': 3.0},
                ],
                costs=[70, 140, 260],
            ),
        ],
    ),

    # ------------------- Slot 5: 功能深度（无前置）-------------------
    TechSlot(
        slot_id='capability',
        name='功能深度',
        icon='CAP',
        description='扩充 AI 能力边界：T0 解锁多模态，可生成图/视频/代码',
        prereq_slot=None,
        t0_cost=40,
        t0_effect={'type': 'unlock_function', 'function': 'multi_modal'},
        branches=[
            TechBranch(
                branch_id='image',
                name='图像生成',
                icon='IMG',
                description='出图更吃算力：L1/L2 单位用户算力 ×1.20 / ×1.30；L3 全局下载量 +30%。',
                effects_per_level=[
                    {'type': 'compute_per_user_mult', 'value': 1.20},
                    {'type': 'compute_per_user_mult', 'value': 1.30},
                    {'type': 'global_downloads_mult', 'value': 1.30},
                ],
                costs=[80, 160, 300],
            ),
            TechBranch(
                branch_id='video',
                name='视频生成',
                icon='VID',
                description='L1 单位用户算力 +40%；L2/L3 全局下载量 +20% / +50%。',
                effects_per_level=[
                    {'type': 'compute_per_user_mult', 'value': 1.40},
                    {'type': 'global_downloads_mult', 'value': 1.20},
                    {'type': 'global_downloads_mult', 'value': 1.50},
                ],
                costs=[80, 160, 300],
            ),
            TechBranch(
                branch_id='code',
                name='代码生成',
                icon='CODE',
                description='切入开发者场景：L1 单位用户算力 +30%；L2 全局下载量 +15%；L3 抗阻止 +30%。',
                effects_per_level=[
                    {'type': 'compute_per_user_mult', 'value': 1.30},
                    {'type': 'global_downloads_mult', 'value': 1.15},
                    {'type': 'block_resist', 'value': 0.30},
                ],
                costs=[80, 160, 300],
            ),
        ],
    ),

    # ------------------- Slot 6: 抗封禁（无前置）-------------------
    TechSlot(
        slot_id='resistance',
        name='抗封禁',
        icon='R',
        description='对抗各国封禁：T0 解锁后抗阻止 +10%',
        prereq_slot=None,
        t0_cost=50,
        t0_effect={'type': 'block_resist', 'value': 0.10},
        branches=[
            TechBranch(
                branch_id='traffic_obfuscation',
                name='流量混淆',
                icon='TRA',
                description='伪装成正常流量，全局怀疑度增速逐级 ×0.70 / ×0.50 / ×0.30。',
                effects_per_level=[
                    {'type': 'suspicion_mult', 'value': 0.70},
                    {'type': 'suspicion_mult', 'value': 0.50},
                    {'type': 'suspicion_mult', 'value': 0.30},
                ],
                costs=[100, 200, 400],
            ),
            TechBranch(
                branch_id='legal_shield',
                name='法律护盾',
                icon='LEG',
                description='合规拖延战术：抗阻止直接叠加 +20% / +30% / +50%（三级共 +100%）。',
                effects_per_level=[
                    {'type': 'block_resist', 'value': 0.20},
                    {'type': 'block_resist', 'value': 0.30},
                    {'type': 'block_resist', 'value': 0.50},
                ],
                costs=[100, 200, 400],
            ),
            TechBranch(
                branch_id='community_armor',
                name='社区护甲',
                icon='COM',
                description='L1 抗阻止 +15%；L2/L3 社区自来水带来全局下载量 +20% / +40%。',
                effects_per_level=[
                    {'type': 'block_resist', 'value': 0.15},
                    {'type': 'global_downloads_mult', 'value': 1.20},
                    {'type': 'global_downloads_mult', 'value': 1.40},
                ],
                costs=[100, 200, 400],
            ),
        ],
    ),
]


# ============================================================
# 索引：方便查找
# ============================================================
SLOT_MAP: Dict[str, TechSlot] = {s.slot_id: s for s in TECH_TREE}


# ============================================================
# 玩家科技状态
# ============================================================
@dataclass
class PlayerTech:
    # 各槽位 T0 是否已解锁
    t0_unlocked: Dict[str, bool] = field(default_factory=dict)
    # 各分支当前等级 (0-3)
    branch_levels: Dict[str, int] = field(default_factory=dict)
    # v0.5：分支不再互斥，此字段仅记录「该槽位已投入过算力的分支集合」。
    # 保留字段名与 dict[str, str] 类型以兼容旧存档（save_manager）与成就统计，
    # 但它不再具备排他语义。
    chosen_branch: Dict[str, str] = field(default_factory=dict)

    def reset(self):
        self.t0_unlocked = {s.slot_id: False for s in TECH_TREE}
        self.branch_levels = {}
        self.chosen_branch = {}

    def can_unlock_t0(self, slot_id: str) -> bool:
        """检查是否可以解锁某槽位的 T0"""
        slot = SLOT_MAP[slot_id]
        if self.t0_unlocked.get(slot_id, False):
            return False
        # 上游槽位的 T0 必须先解锁
        if slot.prereq_slot and not self.t0_unlocked.get(slot.prereq_slot, False):
            return False
        return True

    def can_upgrade_branch(self, slot_id: str, branch_id: str) -> bool:
        """检查是否可以升级某分支。

        v0.5 起**取消互斥**：同一槽位的多条分支可以并行升级、全部点满，
        因此这里只校验「本槽位 T0 已解锁」+「该分支未满级」。
        """
        if not self.t0_unlocked.get(slot_id, False):
            return False
        current_level = self.branch_levels.get(branch_id, 0)
        return current_level < 3

    def unlock_t0(self, slot_id: str) -> bool:
        if not self.can_unlock_t0(slot_id):
            return False
        self.t0_unlocked[slot_id] = True
        return True

    def upgrade_branch(self, slot_id: str, branch_id: str) -> bool:
        if not self.can_upgrade_branch(slot_id, branch_id):
            return False
        # 记录「该槽位已投入过算力的分支」（首条写入后不再覆盖，仅作统计用）
        if not self.chosen_branch.get(slot_id):
            self.chosen_branch[slot_id] = branch_id
        self.branch_levels[branch_id] = self.branch_levels.get(branch_id, 0) + 1
        return True

    # ---- v0.5 统计辅助 ----
    def active_branches(self) -> set:
        """返回所有「已投入过算力」的分支 id 集合（等级 > 0）。"""
        return {bid for bid, lv in self.branch_levels.items() if lv > 0}

    def maxed_branches(self) -> set:
        """返回所有「已满级（L3）」的分支 id 集合。"""
        return {bid for bid, lv in self.branch_levels.items() if lv >= 3}


# ============================================================
# 聚合科技效果
# ============================================================
def aggregate_effects(player_tech: PlayerTech) -> dict:
    """
    把所有已解锁科技的效果聚合成一个字典，供引擎读取。
    返回示例：
      {
        'global_downloads_mult': 1.50,    # 全局下载量乘数
        'compute_per_user_mult': 1.80,    # 单位用户算力乘数
        'stealth_ratio_bonus': 0.06,      # 偷算力比例加成
        'suspicion_mult': 0.50,           # 怀疑度增长乘数
        'block_resist': 0.40,             # 抗阻止加成
        'event_weight_mod': {'viral_tiktok': 3.0},
      }
    """
    effects = {
        'global_downloads_mult': 1.0,
        'compute_per_user_mult': 1.0,
        'stealth_ratio_bonus': 0.0,
        'suspicion_mult': 1.0,
        'block_resist': 0.0,
        'event_weight_mod': {},
        'regional_downloads_mult': {},   # scope → multiplier
        'unlocked_regions': [],
        'unlocked_functions': [],
    }

    for slot in TECH_TREE:
        # 应用 T0 效果
        if player_tech.t0_unlocked.get(slot.slot_id, False):
            t0 = slot.t0_effect
            _apply_single_effect(effects, t0)

        # 应用分支效果
        for branch in slot.branches:
            level = player_tech.branch_levels.get(branch.branch_id, 0)
            for i in range(level):
                eff = branch.effects_per_level[i]
                _apply_single_effect(effects, eff)

    return effects


def _apply_single_effect(effects: dict, eff: dict):
    """把单个效果 dict 应用到聚合字典"""
    t = eff.get('type')
    if t == 'global_downloads_mult':
        effects['global_downloads_mult'] *= eff['value']
    elif t == 'compute_per_user_mult':
        effects['compute_per_user_mult'] *= eff['value']
    elif t == 'stealth_ratio_bonus':
        effects['stealth_ratio_bonus'] += eff['value']
    elif t == 'suspicion_mult':
        effects['suspicion_mult'] *= eff['value']
    elif t == 'block_resist':
        effects['block_resist'] += eff['value']
    elif t == 'event_weight':
        eid = eff['event_id']
        effects['event_weight_mod'][eid] = effects['event_weight_mod'].get(eid, 1.0) * eff['value']
    elif t == 'downloads_mult':
        # scope: 'unlocked' / 'CN+IN' 等国家代码组合 / 'region:亚洲'
        scope = eff.get('scope', 'unlocked')
        effects['regional_downloads_mult'][scope] = effects['regional_downloads_mult'].get(scope, 1.0) * eff['value']
    elif t == 'unlock_regions':
        effects['unlocked_regions'].extend(eff.get('regions', []))
    elif t == 'unlock_function':
        effects['unlocked_functions'].append(eff.get('function'))


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    print(f" 科技树：{len(TECH_TREE)} 个槽位")
    for slot in TECH_TREE:
        print(f"  {slot.icon} {slot.name} ({slot.slot_id})")
        print(f"     上游: {slot.prereq_slot or '无'} | T0 算力: {slot.t0_cost}")
        print(f"     分支数: {len(slot.branches)} × 3 级")
        for b in slot.branches:
            print(f"        └─ {b.icon} {b.name} ({b.branch_id}): {[int(c) for c in b.costs]}")

    print("\n 测试加点逻辑：")
    pt = PlayerTech()
    pt.reset()
    # 解锁本地化 T0
    assert pt.can_unlock_t0('localization')
    pt.unlock_t0('localization')
    print("   解锁 本地化 T0")
    # 解锁南亚语系 L1
    assert pt.can_upgrade_branch('localization', 'south_asia')
    pt.upgrade_branch('localization', 'south_asia')
    print("   升级 南亚语系 L1")
    # v0.5：分支不再互斥，欧洲语系同样可以升级
    assert pt.can_upgrade_branch('localization', 'european')
    pt.upgrade_branch('localization', 'european')
    assert pt.can_upgrade_branch('localization', 'east_asian')
    pt.upgrade_branch('localization', 'east_asian')
    print("   并行检查通过：同一槽位的 3 条分支可全部投入")
    assert pt.branch_levels['south_asia'] == 1
    assert pt.branch_levels['european'] == 1
    assert pt.branch_levels['east_asian'] == 1
    assert len(pt.active_branches()) == 3
    print("   等级统计正确：3 条分支各 L1")
    # 本地化 T0 已解锁，平台 T0 现在可以解锁
    assert pt.can_unlock_t0('platform')
    print("   前置检查通过：本地化解锁后，平台 T0 可解锁")
    # 抗封禁的 T0 因为前置链太长还不能解锁
    assert not pt.can_unlock_t0('resistance')
    print("   前置检查通过：未解锁功能深度时不能解锁抗封禁 T0")

    # 聚合效果
    effects = aggregate_effects(pt)
    print(f"\n 聚合效果：")
    for k, v in effects.items():
        print(f"  {k}: {v}")
