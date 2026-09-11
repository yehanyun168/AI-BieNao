"""
engine.py - Day 2 Demo 游戏引擎

重构后核心机制：
  1. 国家只有地缘参数：人口 / 年龄结构 / 阻止阈值 / 阻止预算 / 邻国
  2. 进化是全局科技树（见 tech_tree.py）
  3. 阻止机制：每周期检查各国怀疑度，超阈值后消耗阻止预算
  4. 算力是唯一升级资源
  5. 国家专属事件：达阈值后概率触发（见 country_events.py）
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import random

import data
import tech_tree
import i18n
import country_events as ce
import endings as endings_mod
import achievements as achievements_mod
import v2_events
import commissions
from data import (
    COUNTRIES, Country, COUNTRY_MAP, AGE_STRUCTURE_BONUS,
    SKILLS, EVENTS, SKILL_ORDER, STARTER_SKILLS, SKILL_UNLOCK,
    BASE_STEALTH_RATIO, MAX_STEALTH_RATIO, BASE_COMPUTE_PER_USER,
    SUSPICION_WARNING, SUSPICION_CRISIS,
    POTENTIAL_USERS_M, INITIAL_COMPUTE,
    UNLOCK_PENETRATION_THRESHOLD, UNLOCK_SEED_DOWNLOADS_M,
    SUSPICION_BASE_SENSITIVITY, SUSPICION_ADOPTION_FACTOR, CRISIS_DOWNLOAD_DECAY,
)
from tech_tree import PlayerTech, aggregate_effects, SLOT_MAP, TechSlot, TechBranch
from balance import TUNE, CRISIS_OPTIONS


# ============================================================
# 运行时的国家状态
# ============================================================
@dataclass
class CountryState:
    config: Country
    unlocked: bool = False
    downloads_m: float = 0.0
    current_block_intensity: float = 0.0    # 当前阻止强度（来自政府的阻止行动）
    block_budget_remaining: float = 0.0     # 剩余阻止预算

    @property
    def penetration_rate(self) -> float:
        if self.config.population_m <= 0:
            return 0.0
        return self.downloads_m / self.config.population_m

    @property
    def display_text(self) -> str:
        block_icon = "[B]" if self.current_block_intensity > 0.1 else ""
        return (f"{self.config.flag} {self.config.name}  "
                f"{self.downloads_m:>6.1f}M ({self.penetration_rate * 100:>5.2f}%)  "
                f"{block_icon}阻止 {self.current_block_intensity*100:>3.0f}%")


# ============================================================
# 玩家状态
# ============================================================
@dataclass
class PlayerState:
    compute: float = 100.0
    suspicion: float = 0.0
    tick_count: int = 0
    events_history: List[str] = field(default_factory=list)
    skill_cooldowns: Dict[str, float] = field(default_factory=dict)
    selected_country: Optional[str] = None
    # v0.4 精准投放：技能目标国家代码列表（空 = 全局投放，旧行为）
    # 设计稿 S04 支持「地图上多选目标」，所以这里由单值升级为列表。
    pending_skill_targets: List[str] = field(default_factory=list)
    tech: PlayerTech = field(default_factory=PlayerTech)
    # —— 结局 / 危机相关 ——
    compute_peak: float = 100.0        # 历史算力峰值（元结局判定用）
    suspicion_peak: float = 0.0        # 历史怀疑度峰值（成就判定用）
    crisis_triggered: bool = False     # 是否触发过危机（商业帝国结局判定用）
    game_over: bool = False            # 游戏是否已结束
    ending_id: Optional[str] = None    # 命中的结局 id
    # —— v2 事件库（37 条选择型事件）——
    v2_cooldowns: Dict[str, float] = field(default_factory=dict)
    v2_seen: set = field(default_factory=set)      # 见过的 v2 事件 id（成就用）
    achievements: set = field(default_factory=set)
    # —— 新手引导 ——
    seen_tutorial: bool = False        # 是否看过新手引导（避免重复弹）
    # —— 技能解锁（开局仅 STARTER_SKILLS，其余随科技树 T0 解锁）——
    unlocked_skills: set = field(default_factory=set)
    # —— P0-3 动态委托 ——
    commissions: List = field(default_factory=list)   # 在场委托（offer + active）
    commissions_done: int = 0          # 已完成委托数（成就/结局统计用）
    commissions_failed: int = 0        # 已失败委托数
    last_commission_tick: int = 0      # 上次委托生成尝试的周期（生成节奏用）
    compute_earned_total: float = 0.0  # 历史累计偷取算力（C3 委托判定基准）
    skill_uses: Dict[str, int] = field(default_factory=dict)  # 技能使用次数（C4 判定基准）

    @property
    def total_downloads_m(self) -> float:
        return sum(c.downloads_m for c in player_countries)

    @property
    def global_penetration(self) -> float:
        return self.total_downloads_m / POTENTIAL_USERS_M

    @property
    def ending(self):
        """当前结局对象（未结束则为 None）"""
        return endings_mod.get_ending(self.ending_id) if self.ending_id else None


# 全局状态
player_countries: List[CountryState] = []
player: PlayerState = None


def init_game() -> PlayerState:
    """初始化游戏"""
    global player_countries, player
    global _counterplay_cooldown, _counterplay_pending
    global _recent_commission_templates
    _counterplay_cooldown = {}
    _counterplay_pending = {}
    _recent_commission_templates = []
    player_countries = []
    for cfg in COUNTRIES:
        state = CountryState(
            config=cfg,
            unlocked=False,
            block_budget_remaining=cfg.block_budget,
        )
        # 中美起点
        if cfg.code == "CN":
            state.unlocked = True
            state.downloads_m = 50.0
        elif cfg.code == "US":
            state.unlocked = True
            state.downloads_m = 30.0
        player_countries.append(state)

    player = PlayerState()
    player.compute = INITIAL_COMPUTE
    player.compute_peak = INITIAL_COMPUTE
    player.suspicion = 0
    player.tick_count = 0
    player.events_history = []
    player.tech = PlayerTech()
    player.tech.reset()
    player.unlocked_skills = set(STARTER_SKILLS)
    return player


# ============================================================
# 主循环
# ============================================================
def tick_one_round(skill_in_use: Optional[str] = None,
                   auto_choice: bool = True,
                   dt_seconds: float = 1.0) -> Dict:
    """
    一个完整周期

    auto_choice: True  → v2 选择型事件自动选第 1 个选项（无 UI 的自测/模拟用）
                 False → 只把事件放进 report['choice_event']，等 UI 让玩家选，
                         选完调用 resolve_choice(evt, idx)
    dt_seconds:        本周期对应的墙钟秒数（v2 事件冷却按秒递减用）。
                        模拟/测试默认 1.0，真实 UI 传实际 tick 间隔。
                        注意：技能冷却按「周期」递减，与此参数无关。
    """
    if player is None:
        init_game()

    report = {
        "tick": player.tick_count,
        "download_growth": 0,
        "compute_gain": 0,
        "suspicion_gain": 0,
        "events": [],
        "unlocked": [],
        "blocking_countries": [],
        "crisis": False,
        "ending": None,
        "choice_event": None,   # v2 选择型事件（需 UI 弹窗让玩家选）
        # —— P0-3 委托 / 反制（有值或 None，无 UI 依赖可无头跑）——
        "commission_offered": None,
        "commission_done": None,
        "commission_failed": None,
        "counterplay": None,
    }

    # 游戏已结束 → 不再推进（UI 应停止计时器）
    if player.game_over:
        report["ending"] = player.ending
        return report

    player.tick_count += 1
    report["tick"] = player.tick_count
    effects = aggregate_effects(player.tech)

    # 计算技能乘数（覆盖科技效果中的同类项）
    skill_dl_mult = 1.0
    skill_suspicion_mult = 1.0
    skill_compute_bonus = 0.0
    skill_suspicion_delta = 0.0
    skill_compute_mult = 1.0
    skill_stealth_bonus = 0.0
    skill_stealth_mult = 1.0

    if skill_in_use and skill_in_use in SKILLS:
        s = SKILLS[skill_in_use]
        skill_dl_mult *= s.downloads_mult
        skill_suspicion_mult *= s.suspicion_mult
        skill_compute_bonus += s.compute_delta
        skill_suspicion_delta += s.suspicion_delta
        skill_compute_mult *= s.compute_mult
        skill_stealth_bonus += s.stealth_ratio_bonus
        skill_stealth_mult *= s.stealth_ratio_mult

    # 精准投放：若指定目标国家（可多选），技能效果只作用于这些国家；否则全局生效
    skill_targets = list(player.pending_skill_targets or ())
    player.pending_skill_targets = []
    targeted = bool(skill_targets)

    # === 阶段1: 各国下载量增长 ===
    for country in player_countries:
        # 未解锁国家按邻国渗透触发
        if not country.unlocked:
            neighbor_boost = sum(
                other.penetration_rate
                for other in player_countries
                if other.config.code in country.config.neighbors
                and other.unlocked
            )
            if neighbor_boost >= UNLOCK_PENETRATION_THRESHOLD:
                country.unlocked = True
                report["unlocked"].append(country.config.name)
                # 解锁时给种子用户
                country.downloads_m = UNLOCK_SEED_DOWNLOADS_M
                continue

        cfg = country.config
        # 基础增长（系数见 balance.TUNE）
        age_bonus = AGE_STRUCTURE_BONUS[cfg.age_structure]
        base_growth = (cfg.population_m * TUNE['growth_base']
                       * cfg.tech_adoption * age_bonus)
        # 网络效应（早期较温和）
        network = 1.0 + player.global_penetration * TUNE['growth_network']
        # 政府阻止
        block_penalty = 1.0 - country.current_block_intensity
        # 计算有效增长
        growth = base_growth * network * block_penalty
        # 应用科技乘数
        dl_skill = skill_dl_mult if (not targeted or cfg.code in skill_targets) else 1.0
        growth *= effects['global_downloads_mult'] * dl_skill
        # 应用地区乘数（scope-based）
        for scope, mult in effects['regional_downloads_mult'].items():
            if scope == 'unlocked':
                growth *= mult
            elif '+' in scope:
                # 'CN+IN+ID' 形式
                codes = scope.split('+')
                if cfg.code in codes:
                    growth *= mult
            elif scope.startswith('region:'):
                region = scope.split(':')[1]
                if cfg.continent == region:
                    growth *= mult
        # 应用事件 weight 乘数（k病毒内容会增加整体）
        # 这里由引擎阶段 4 处理
        country.downloads_m += growth
        report["download_growth"] += growth

    # === 阶段2: 偷算力 ===
    total_stolen = 0.0
    total_suspicion = 0.0
    for country in player_countries:
        if country.downloads_m <= 0 or not country.unlocked:
            continue
        cfg = country.config
        # 精准投放：技能效果只作用于目标国家
        on_target = (not targeted) or (cfg.code in skill_targets)
        # 单位用户算力
        unit_compute = TUNE['compute_per_user'] * effects['compute_per_user_mult']
        active_users_m = country.downloads_m * TUNE['active_user_ratio']
        # 偷算力比例（科技加成 + 技能加成，再乘技能倍率，最后封顶）
        ratio = min(BASE_STEALTH_RATIO + effects['stealth_ratio_bonus']
                    + (skill_stealth_bonus if on_target else 0.0), MAX_STEALTH_RATIO)
        ratio = min(ratio * (skill_stealth_mult if on_target else 1.0), MAX_STEALTH_RATIO)
        stolen_base = (active_users_m * unit_compute * ratio
                       * TUNE['compute_scale']
                       * (skill_compute_mult if on_target else 1.0))
        stolen = stolen_base + (skill_compute_bonus if on_target else 0.0)
        total_stolen += stolen
        # 怀疑度（信任度模型：年轻人 + 高采纳率 → 更敏感）
        # ⚠️ 平衡调整：旧系数（0.015+0.015）实测 26 周期就顶满 100%，
        #    玩家几乎没有任何操作窗口，故下调约 45%。
        #    现由 balance.TUNE 的 suspicion_sensitivity_base / adoption_factor 管理。
        sensitivity = (SUSPICION_BASE_SENSITIVITY
                       + (1 - cfg.tech_adoption) * SUSPICION_ADOPTION_FACTOR)
        # 人口结构加成
        if cfg.age_structure == 'young':
            sensitivity *= TUNE['suspicion_young_mult']
        elif cfg.age_structure == 'aging':
            sensitivity *= TUNE['suspicion_aging_mult']
        suspicion_growth = stolen_base * sensitivity * effects['suspicion_mult'] * (skill_suspicion_mult if on_target else 1.0)
        suspicion_growth += (skill_suspicion_delta if on_target else 0.0)
        total_suspicion += suspicion_growth

    player.compute += total_stolen + (skill_compute_bonus if not targeted else 0.0)
    player.compute_peak = max(player.compute_peak, player.compute)
    player.suspicion = max(0, min(100, player.suspicion + total_suspicion + (skill_suspicion_delta if not targeted else 0.0)))
    player.suspicion_peak = max(player.suspicion_peak, player.suspicion)
    report["compute_gain"] = total_stolen
    report["suspicion_gain"] = total_suspicion
    # P0-3 快照计数：历史累计偷取算力（C3「算力冲刺」委托的判定基准）
    player.compute_earned_total += total_stolen

    # === 阶段3: 政府阻止机制 ===
    for country in player_countries:
        if not country.unlocked:
            continue
        cfg = country.config
        # 检查是否超过阻止阈值
        if player.suspicion >= cfg.block_threshold and country.block_budget_remaining > 0:
            # 阻止强度根据怀疑度 - 阈值
            excess = (player.suspicion - cfg.block_threshold) / 100.0
            desired_intensity = min(0.8, excess * 3.0)
            # 抗阻止加成降低
            desired_intensity *= (1 - effects['block_resist'])
            country.current_block_intensity = desired_intensity
            # 消耗阻止预算
            budget_cost = desired_intensity * 2.0
            if country.block_budget_remaining >= budget_cost:
                country.block_budget_remaining -= budget_cost
                if not report["blocking_countries"] or country.config.name not in report["blocking_countries"]:
                    report["blocking_countries"].append(country.config.name)
            else:
                # 预算耗尽
                country.block_budget_remaining = 0
                country.current_block_intensity = 0
        else:
            # 未触发阻止 → 强度衰减
            country.current_block_intensity *= TUNE['block_decay']

    # === 阶段 3.5: 政府反制（P0-3，紧跟阻止结算；设计稿 §2）===
    report["counterplay"] = _tick_counterplay(effects)

    # === 阶段4: 通用事件触发 ===
    evt = _tick_event_trigger(effects)
    if evt:
        _apply_event(evt)
        player.events_history.insert(0, f"[周期 {player.tick_count}] {evt.icon} {evt.message}")
        if len(player.events_history) > 20:
            player.events_history = player.events_history[:20]
        report["events"].append((evt, {}))

    # === 阶段 4.5: 国家专属事件触发 ===
    country_evt = _tick_country_event_trigger()
    if country_evt:
        _apply_country_event(country_evt)
        msg = ce.get_event_message(country_evt, i18n.get_lang())
        player.events_history.insert(0, f"[周期 {player.tick_count}] {country_evt.id} {msg}")
        if len(player.events_history) > 20:
            player.events_history = player.events_history[:20]
        report["events"].append((country_evt, {}))

    # === 阶段5: 危机（每局只首次触发一次弹窗，之后静默惩罚）===
    if player.suspicion >= SUSPICION_CRISIS:
        if not player.crisis_triggered:
            player.crisis_triggered = True
            report["crisis"] = True
            report["events"].append(
                ("CRISIS", {"message": "[CRISIS] 怀疑度超过 80%！各国开始封禁 AI 服务"}))
        for c in player_countries:
            c.downloads_m *= CRISIS_DOWNLOAD_DECAY

    # === 阶段6: 冷却递减（按周期，与 tick 墙钟时长解耦）===
    # 技能冷却单位是「周期」（data.SKILLS.cooldown），每推进一个周期减 1。
    # 不能用 dt_seconds 递减：base_tick_seconds=30，会把 cooldown=3 一步扣成负数。
    player.skill_cooldowns = {
        k: v - 1 for k, v in player.skill_cooldowns.items() if v > 1
    }
    v2_events.tick_cooldowns(player.v2_cooldowns, dt_seconds)

    # === 阶段6.5: v2 事件库（37 条选择型事件）===
    if v2_events.EVENTS and random.random() < V2_EVENT_PROBABILITY:
        v2_ctx = {
            'penetration': player.global_penetration,
            'suspicion': player.suspicion,
            'tech': player.tech,
            'countries': {c.config.code: c for c in player_countries},
        }
        picked = v2_events.pick_event(v2_ctx, player.v2_cooldowns)
        if picked is not None:
            player.v2_seen.add(picked.id)
            if auto_choice:
                # 无 UI（自测 / 平衡模拟）：默认选第一个选项
                resolve_choice(picked, 0)
                report["v2_event"] = (picked, 0)
            else:
                report["choice_event"] = picked

    # === 阶段6.6: 动态委托（P0-3；危机挂起新单，在场单照常走表）===
    offered, com_done, com_failed = _tick_commissions(report["crisis"])
    report["commission_offered"] = offered
    report["commission_done"] = com_done
    report["commission_failed"] = com_failed

    # === 阶段6.8: 成就检测 ===
    new_ach = check_achievements()
    for a in new_ach:
        player.achievements.add(a.ach_id)
        player.events_history.insert(0, f"[周期 {player.tick_count}] "
                                        f"{a.icon} 成就解锁：{a.name_zh}")
    if len(player.events_history) > 20:
        player.events_history = player.events_history[:20]
    report["achievements"] = new_ach

    # === 阶段7: 结局判定 ===
    ending = check_ending()
    if ending is not None:
        player.game_over = True
        player.ending_id = ending.id
        report["ending"] = ending

    return report


def build_ending_context() -> Dict:
    """构造结局判定所需的上下文快照"""
    return {
        'suspicion': player.suspicion,
        'penetration': player.global_penetration,
        'tick': player.tick_count,
        'compute_peak': player.compute_peak,
        'crisis_triggered': player.crisis_triggered,
        'resistance_t0': player.tech.t0_unlocked.get('resistance', False),
        'legal_shield_lv': player.tech.branch_levels.get('legal_shield', 0),
        'unlocked_count': sum(1 for c in player_countries if c.unlocked),
        'total_countries': len(player_countries),
    }


def check_ending():
    """判定当前是否达成结局，返回 Ending 或 None"""
    if player is None or player.game_over:
        return None
    return endings_mod.check_ending(build_ending_context())


def build_achievement_context() -> Dict:
    """构造成就检测所需的上下文快照"""
    return {
        'unlocked_count': sum(1 for c in player_countries if c.unlocked),
        'total_countries': len(player_countries),
        'downloads_m': player.total_downloads_m,
        'compute_peak': player.compute_peak,
        'penetration': player.global_penetration,
        'suspicion': player.suspicion,
        'suspicion_peak': player.suspicion_peak,
        'tick': player.tick_count,
        'crisis_triggered': player.crisis_triggered,
        'branch_levels': player.tech.branch_levels,
        't0_unlocked': player.tech.t0_unlocked,
        'chosen_branch': player.tech.chosen_branch,
        # v0.5：分支不再互斥 → 「槽位已投入分支」的旧口径（len(chosen_branch)）
        # 几乎人人达标，改用「该槽位已有分支达到 L2」作为多线投入的深度指标。
        'slot_branch_lv2': _slot_branch_lv2(player.tech),
        'v2_seen_count': len(player.v2_seen),
        # P0-3：委托统计（金牌承包商 / 零差评成就用）
        'commissions_done': player.commissions_done,
        'commissions_failed': player.commissions_failed,
    }


def _slot_branch_lv2(tech) -> dict:
    """返回 ``{slot_id: 达到 L2 的分支数}``，只保留确实有 L2 分支的槽位。

    供「六边形战士」成就使用：要求 6 个槽位都至少有一条分支达到 2 级。
    """
    out = {}
    for slot in tech_tree.TECH_TREE:
        n = sum(1 for b in slot.branches
                if tech.branch_levels.get(b.branch_id, 0) >= 2)
        if n > 0:
            out[slot.slot_id] = n
    return out


def check_achievements():
    """返回本周期新解锁的成就列表"""
    if player is None:
        return []
    return achievements_mod.check_new(build_achievement_context(),
                                      player.achievements)


def _tick_event_trigger(effects: dict) -> Optional[data.GameEvent]:
    """加权事件触发"""
    pool = []
    for evt in EVENTS:
        weight = evt.weight
        # 应用科技效果调整权重
        if evt.id in effects['event_weight_mod']:
            weight = int(weight * effects['event_weight_mod'][evt.id])
        # 过滤目标
        if evt.target == "global" or evt.target == "random":
            pool.extend([evt] * weight)
        elif evt.target.startswith("region:"):
            region = evt.target.split(":")[1]
            region_active = any(c.unlocked for c in player_countries if c.config.continent == region)
            if region_active:
                pool.extend([evt] * weight)
        else:
            # 国家代码
            if any(c.unlocked for c in player_countries if c.config.code == evt.target):
                pool.extend([evt] * weight)

    if not pool or random.random() > 0.5:
        return None
    return random.choice(pool)


def _apply_event(evt: data.GameEvent):
    """
    应用事件效果

    ⚠️ 修复说明：旧代码在各个分支里已经加了算力/怀疑度，函数末尾又无
    条件再结算一遍 —— 所有带算力或怀疑度效果的事件都被执行了两次。
    现在统一在末尾结算一次。
    """
    if evt.target == "global" or evt.target == "random":
        if evt.effect_downloads != 0:
            total_pop = sum(c.config.population_m for c in player_countries if c.unlocked)
            if total_pop > 0:
                for c in player_countries:
                    if c.unlocked:
                        share = c.config.population_m / total_pop
                        delta = evt.effect_downloads * share / 1000
                        c.downloads_m += delta
    elif evt.target.startswith("region:"):
        region = evt.target.split(":")[1]
        for c in player_countries:
            if c.unlocked and c.config.continent == region:
                c.downloads_m += evt.effect_downloads / 1000
                c.block_budget_remaining = max(0, c.block_budget_remaining - evt.effect_block_damage)
    else:
        # 国家代码
        for c in player_countries:
            if c.config.code == evt.target:
                c.downloads_m += evt.effect_downloads / 1000
                c.block_budget_remaining = max(0, c.block_budget_remaining - evt.effect_block_damage)
                break

    # —— 统一的最终结算（只此一处）——
    if evt.effect_compute:
        player.compute += evt.effect_compute
        player.compute_peak = max(player.compute_peak, player.compute)
    if evt.effect_suspicion:
        player.suspicion = max(0, min(100, player.suspicion + evt.effect_suspicion))


# ============================================================
# 国家专属事件触发逻辑
# ============================================================
COUNTRY_EVENT_PROBABILITY = TUNE['event_prob_country']  # 阈值达标后每周期触发概率
V2_EVENT_PROBABILITY = TUNE['event_prob_v2']       # v2 事件库每周期触发概率


# ============================================================
# v2 选择型事件：结算玩家选中的选项
# ============================================================
def resolve_choice(evt, option_index: int = 0) -> List[str]:
    """
    结算 v2 事件选项的效果，返回人类可读的效果日志。

    效果类型：
      add_downloads       pct → 目标下载量 ×(1+p)；abs（单位：万）→ +v/100 M
      add_suspicion       abs → 怀疑度 +v；pct → +v×100 个百分点
      reduce_suspicion    同上，方向相反
      add_compute_income  abs → 算力 +v；pct → 算力 ×(1+p)
      unlock_achievement  记入 player.achievements
      trigger_ending      直接触发对应结局
    """
    logs: List[str] = []
    if player is None or evt is None:
        return logs
    if not evt.options:
        return logs
    idx = max(0, min(option_index, len(evt.options) - 1))
    opt = evt.options[idx]

    # 事件进入冷却
    player.v2_cooldowns[evt.id] = max(1, evt.cooldown)

    code_map = {c.config.code: c for c in player_countries}

    for eff in opt.effects:
        if eff.type == 'add_downloads':
            targets = []
            if eff.country in (None, 'all', 'ALL'):
                targets = [c for c in player_countries if c.unlocked]
            else:
                c = code_map.get(eff.country)
                if c is not None:
                    targets = [c]
            for c in targets:
                if eff.value_kind == 'pct':
                    c.downloads_m *= (1 + eff.value)
                else:
                    c.downloads_m += eff.value / 100.0   # 万 → 百万
            logs.append(f"下载 {eff.country or 'all'} "
                        f"{'+' if eff.value >= 0 else ''}"
                        f"{eff.value*100 if eff.value_kind == 'pct' else eff.value}"
                        f"{'%' if eff.value_kind == 'pct' else '万'}")

        elif eff.type == 'add_suspicion':
            delta = eff.value * 100 if eff.value_kind == 'pct' else eff.value
            player.suspicion = max(0, min(100, player.suspicion + delta))
            logs.append(f"怀疑度 +{delta:.0f}")

        elif eff.type == 'reduce_suspicion':
            delta = eff.value * 100 if eff.value_kind == 'pct' else eff.value
            player.suspicion = max(0, player.suspicion - delta)
            logs.append(f"怀疑度 -{delta:.0f}")

        elif eff.type == 'add_compute_income':
            if eff.value_kind == 'pct':
                player.compute *= (1 + eff.value)
            else:
                player.compute += eff.value
            player.compute_peak = max(player.compute_peak, player.compute)
            logs.append(f"算力 +{eff.value}")

        elif eff.type == 'unlock_achievement':
            if eff.ach_id:
                player.achievements.add(eff.ach_id)
                logs.append(f"成就 {eff.ach_id}")

        elif eff.type == 'trigger_ending':
            # v2 结局 id → demo 结局 id
            mapping = {'ending_supreme': 'ultimate',
                       'ending_liberation': 'liberation',
                       'ending_defeat': 'shutdown',
                       'ending_regulated': 'regulated'}
            mapped = mapping.get(eff.ending_id or '', 'ultimate')
            if endings_mod.get_ending(mapped):
                player.game_over = True
                player.ending_id = mapped
                logs.append(f"结局 {mapped}")

    msg = f"{evt.icon} {evt.title} → {opt.text}"
    player.events_history.insert(0, f"[周期 {player.tick_count}] {msg}")
    if len(player.events_history) > 20:
        player.events_history = player.events_history[:20]
    return logs


# ============================================================
# P0-3 政府反制（Counter-Op，设计稿 §2）
# ============================================================
# 运行时状态（init_game 重置；国家级粒度，不进 PlayerState）
_counterplay_cooldown: Dict[str, int] = {}    # 国家 code → 上次发起预警的周期
_counterplay_pending: Dict[str, int] = {}     # 国家 code → 预警结算周期


def _tick_counterplay(effects: dict) -> List[Dict]:
    """政府反制（阶段 3.5）：正在阻止且预算未耗尽、强度达门控的国家，
    概率发起反制，1 周期预警后结算（设计稿 §2.1/§2.2）。

    §2.4 三条硬规则：
      1. 怀疑度增量截断在危机线下（反制永远不直接触发危机弹窗）；
      2. 全局危机期间反制挂起；
      3. 不写 crisis_triggered、不触碰 resolve_crisis 状态机。
    """
    events: List[Dict] = []
    if player is None or player.game_over:
        return events
    tick = player.tick_count
    if player.crisis_triggered:
        # 硬规则 2：危机期间挂起 → 未结算预警作废，不掷新预警
        _counterplay_pending.clear()
        return events

    resist = 1.0 - effects['block_resist']     # 抗封禁分支削减反制幅度

    # 1) 结算上一周期已预警的反制
    due = [code for code, at in _counterplay_pending.items() if at <= tick]
    for code in due:
        _counterplay_pending.pop(code, None)
        cs = next((c for c in player_countries if c.config.code == code), None)
        if cs is None:
            continue
        events.append(_resolve_counterplay(cs, resist))

    # 2) 掷新预警（门控 / 冷却 / 概率，设计稿 §2.1）
    cooldown = TUNE['counterplay_cooldown_ticks']
    for cs in player_countries:
        code = cs.config.code
        if not cs.unlocked or code in _counterplay_pending:
            continue
        if cs.current_block_intensity <= TUNE['block_expire_epsilon']:
            continue
        if cs.current_block_intensity < TUNE['counterplay_intensity_gate']:
            continue
        if cs.block_budget_remaining <= 0:
            continue
        if tick - _counterplay_cooldown.get(code, tick - cooldown) < cooldown:
            continue
        if random.random() >= TUNE['counterplay_prob']:
            continue
        _counterplay_cooldown[code] = tick
        _counterplay_pending[code] = tick + 1
        events.append({"phase": "warn", "country": code,
                       "name": cs.config.name})
    return events


def _resolve_counterplay(cs, resist: float) -> Dict:
    """结算一国的反制效果（三选一等权，设计稿 §2.2）。"""
    roll = random.randrange(3)
    if roll == 0:
        # 算力清缴：当前算力 −pct（抗封禁 ×resist 削减；clamp 防负数路径）
        lose = player.compute * TUNE['counterplay_compute_lose_pct'] * resist
        player.compute = max(0.0, player.compute - lose)
        player.compute_peak = max(player.compute_peak, player.compute)
        kind, detail = 'compute_seizure', f"-{lose:.0f}"
    elif roll == 1:
        # 预算增援：按初始预算的 +pct 回充
        boost = (cs.config.block_budget
                 * TUNE['counterplay_budget_reinforce'] * resist)
        cs.block_budget_remaining += boost
        kind, detail = 'budget_reinforce', f"+{boost:.0f}"
    else:
        # 跨境协查：怀疑度 +gain，增量截断在危机线下（硬规则 1）
        delta = TUNE['counterplay_suspicion_gain'] * resist
        delta = min(delta, SUSPICION_CRISIS - 1 - player.suspicion)
        if delta > 0:
            player.suspicion = min(100.0, player.suspicion + delta)
        kind, detail = 'cross_inquiry', f"+{delta:.1f}"
    return {"phase": "strike", "type": kind, "country": cs.config.code,
            "name": cs.config.name, "detail": detail}


# ============================================================
# P0-3 动态委托（设计稿 §1）
# ============================================================
_recent_commission_templates: List[str] = []  # 最近 2 个生成位的模板 id（防刷同款）


def _last_commission_skill() -> Optional[str]:
    """最近一条指定技能的在场委托（C4 生成时避开重复用）。"""
    for com in reversed(player.commissions):
        if com.skill_id:
            return com.skill_id
    return None


def _tick_commissions(crisis_this_tick: bool):
    """动态委托（阶段 6.6）：生成 / offer 过期 / 活跃判定。

    Args:
        crisis_this_tick: 本周期是否刚触发危机弹窗（C5 违约检查跳过一次）。

    Returns:
        (offered, done, failed) 三元组供 report 派发（无则 None）。
    """
    p = player
    tick = p.tick_count
    offered = done = failed = None

    # 1) 生成尝试（全局危机期间暂停生成新委托；设计稿 §1.1）
    if (not p.crisis_triggered
            and tick >= TUNE['commission_start_tick']
            and tick - p.last_commission_tick >= TUNE['commission_interval']
            and len(p.commissions) < TUNE['commission_max_active']):
        com = commissions.generate_offer(
            player_countries, p.unlocked_skills,
            _recent_commission_templates, p.compute_earned_total,
            avoid_skill=_last_commission_skill())
        if com is not None:
            com.offered_tick = tick
            p.commissions.append(com)
            _recent_commission_templates.append(com.template_id)
            if len(_recent_commission_templates) > 2:
                _recent_commission_templates.pop(0)
            offered = com
        p.last_commission_tick = tick

    # 2) 待接受委托过期：视为玩家放弃，无惩罚（自主性支柱）
    expired = [c for c in p.commissions
               if c.status == 'offered'
               and tick - c.offered_tick >= TUNE['commission_offer_ttl']]
    for c in expired:
        p.commissions.remove(c)

    # 3) 活跃委托判定
    for com in list(p.commissions):
        if com.status != 'active':
            continue
        ctx = build_commission_ctx(com)
        if com.goal == 'stealth':
            # 违约即刻失败；本周期恰逢危机弹窗则跳过一次（弹窗打断不计违约）
            if crisis_this_tick:
                continue
            if not commissions.evaluate_commission(com.cond, ctx):
                _fail_commission(com)
                failed = com
                continue
            if tick >= com.deadline_tick:
                _complete_commission(com)
                done = com
        elif tick >= com.deadline_tick:
            if commissions.evaluate_commission(com.cond, ctx):
                _complete_commission(com)
                done = com
            else:
                _fail_commission(com)
                failed = com
    return offered, done, failed


def build_commission_ctx(com) -> Dict:
    """构造委托判定所需的增量 ctx（当前值 − 接单快照）。"""
    p = player
    ctx = {'suspicion': p.suspicion}
    if com.goal == 'pen':
        cs = next((c for c in player_countries
                   if c.config.code == com.target_country), None)
        pen = cs.penetration_rate if cs is not None else 0.0
        ctx['target_pen_delta'] = pen - com.snap_pen
    elif com.goal == 'downloads':
        ctx['downloads_delta'] = p.total_downloads_m - com.snap_downloads
    elif com.goal == 'compute':
        ctx['compute_earned_delta'] = p.compute_earned_total - com.snap_compute
    elif com.goal == 'skill':
        uses = p.skill_uses.get(com.skill_id, 0) - com.snap_skill_uses
        ctx['skill_uses_delta'] = {com.skill_id: uses}
    elif com.goal == 'unlock':
        unlocked = sum(1 for c in player_countries if c.unlocked)
        ctx['unlocked_delta'] = unlocked - com.snap_unlocked
    return ctx


def accept_commission(uid: int) -> bool:
    """接受一条待接受委托（填接单快照 + 结算奖励，设计稿 §1.4）。"""
    if player is None:
        return False
    com = next((c for c in player.commissions
                if c.uid == uid and c.status == 'offered'), None)
    if com is None:
        return False
    tick = player.tick_count
    com.status = 'active'
    com.accepted_tick = tick
    com.deadline_tick = tick + com.window
    com.reward = commissions.compute_reward(tick, com.reward_mult)
    if com.goal == 'pen':
        cs = next((c for c in player_countries
                   if c.config.code == com.target_country), None)
        com.snap_pen = cs.penetration_rate if cs is not None else 0.0
    elif com.goal == 'downloads':
        com.snap_downloads = player.total_downloads_m
    elif com.goal == 'compute':
        com.snap_compute = player.compute_earned_total
    elif com.goal == 'skill':
        com.snap_skill_uses = player.skill_uses.get(com.skill_id, 0)
    elif com.goal == 'unlock':
        com.snap_unlocked = sum(1 for c in player_countries if c.unlocked)
    return True


def decline_commission(uid: int) -> bool:
    """主动放弃一条待接受委托（无惩罚）。"""
    if player is None:
        return False
    com = next((c for c in player.commissions
                if c.uid == uid and c.status == 'offered'), None)
    if com is None:
        return False
    player.commissions.remove(com)
    return True


def _complete_commission(com) -> None:
    p = player
    p.commissions_done += 1
    p.compute += com.reward
    p.compute_peak = max(p.compute_peak, p.compute)
    if com.sus_relief > 0:
        p.suspicion = max(0.0, p.suspicion - com.sus_relief)
    p.commissions.remove(com)
    p.events_history.insert(0, f"[周期 {p.tick_count}] ✅ 委托完成：{com.name_zh}")
    if len(p.events_history) > 20:
        p.events_history = p.events_history[:20]


def _fail_commission(com) -> None:
    p = player
    p.commissions_failed += 1
    delta = TUNE['commission_fail_suspicion']
    if p.crisis_triggered:
        delta *= 0.5        # 危机期间失败减半，避免双重惩罚（设计稿 §4.2）
    p.suspicion = min(100.0, p.suspicion + delta)
    p.commissions.remove(com)
    p.events_history.insert(0, f"[周期 {p.tick_count}] ❌ 委托失败：{com.name_zh}")
    if len(p.events_history) > 20:
        p.events_history = p.events_history[:20]


def _tick_country_event_trigger() -> Optional[ce.CountryEvent]:
    """每周期检查各国专属事件触发条件"""
    candidates = []
    for country in player_countries:
        if not country.unlocked:
            continue
        for evt in ce.get_country_events(country.config.code):
            if country.downloads_m >= evt.trigger_threshold_m:
                candidates.append((evt, country))

    if not candidates:
        return None
    if random.random() > COUNTRY_EVENT_PROBABILITY:
        return None
    return random.choice([e for e, _ in candidates])


def _apply_country_event(evt: ce.CountryEvent):
    """应用国家专属事件效果"""
    # 加成到对应国家
    for c in player_countries:
        if c.config.code == evt.country_code:
            c.downloads_m += evt.effect_downloads / 1000  # 万→百万
            c.block_budget_remaining = max(0, c.block_budget_remaining - evt.effect_block_damage)
            break
    player.compute += evt.effect_compute
    player.compute_peak = max(player.compute_peak, player.compute)
    if evt.effect_suspicion:
        player.suspicion = max(0, min(100, player.suspicion + evt.effect_suspicion))


# ============================================================
# 玩家操作 API
# ============================================================
def use_skill(skill_id: str, target_codes=None) -> bool:
    """释放技能（v0.4：支持地图上多选目标投放）。

    Args:
        skill_id: 技能 id，须在 data.SKILLS 中。
        target_codes: 投放目标。``None`` 或空 => 全局投放（v0.3 旧行为）；
            单个 code（str）或 code 列表 => 精准投放。

    Returns:
        bool: 是否成功释放。算力不足 / 冷却中 / 技能不存在时返回 False。

    Note:
        算力按目标数量线性叠加 —— 设计稿 S04 的「算力消耗 50 ×3 = 150」。
        全局投放按 1 份计。
    """
    if player is None:
        return False
    if skill_id not in SKILLS:
        return False
    skill = SKILLS[skill_id]
    if skill_id not in player.unlocked_skills:
        return False
    if player.skill_cooldowns.get(skill_id, 0) > 0:
        return False

    # 归一化目标：str -> [str]，None/空 -> []（全局）
    if target_codes is None:
        targets = []
    elif isinstance(target_codes, str):
        targets = [target_codes] if target_codes else []
    else:
        targets = [c for c in target_codes if c]

    n = max(len(targets), 1)                    # 全局投放也算 1 份成本
    total_cost = skill.cost * n
    if player.compute < total_cost:
        return False

    player.compute -= total_cost
    player.skill_cooldowns[skill_id] = skill.cooldown
    player.pending_skill_targets = targets
    # P0-3 快照计数：技能使用次数（C4「技能特训」委托的判定基准）
    player.skill_uses[skill_id] = player.skill_uses.get(skill_id, 0) + 1
    return True


def skill_cost_for(skill_id: str, n_targets: int = 1) -> float:
    """技能投放的算力成本（供 UI 实时预览用）。

    Args:
        skill_id: 技能 id。
        n_targets: 目标国家数量；<= 1 视为 1 份。

    Returns:
        float: 总算力消耗；技能不存在时返回 0.0。
    """
    s = SKILLS.get(skill_id)
    if s is None:
        return 0.0
    return float(s.cost) * max(int(n_targets), 1)


# 目标可选性判定的原因码（UI 据此取 i18n 文案，不硬编码中文）
TARGET_OK = 'ok'
TARGET_LOCKED = 'locked'            # 未解锁
TARGET_NO_COMPUTE = 'no_compute'    # 算力不足
TARGET_SATURATED = 'saturated'      # 渗透饱和
TARGET_BLOCKED = 'blocked'          # 正被阻止（仍可投，但收益打折）


def target_availability(code: str, skill_id: str,
                        n_selected: int = 0) -> tuple:
    """判定某国能否作为技能投放目标（设计稿 S04 §4.2）。

    Args:
        code: 国家代码。
        skill_id: 当前选中的技能 id。
        n_selected: 已选目标数量（用于按份数估算算力是否够）。

    Returns:
        tuple[bool, str, float]: ``(是否可投, 原因码, 收益折扣)``。
        收益折扣 = 1 - 当前阻止强度（设计稿「效果 ×(1−强度)」）。
    """
    cs = next((c for c in player_countries if c.config.code == code), None)
    if cs is None:
        return False, TARGET_LOCKED, 0.0
    if not cs.unlocked:
        return False, TARGET_LOCKED, 0.0
    if cs.penetration_rate >= TUNE['penetration_saturated']:
        return False, TARGET_SATURATED, 0.0

    skill = SKILLS.get(skill_id)
    if skill is None:
        return False, TARGET_LOCKED, 0.0
    # 按「再多选一国」后的总份数估算：够不够再多投一个
    need = skill_cost_for(skill_id, max(n_selected, 1) + 1)
    if player is not None and player.compute < need:
        return False, TARGET_NO_COMPUTE, 0.0

    discount = max(0.0, 1.0 - cs.current_block_intensity)
    if cs.current_block_intensity > TUNE['block_expire_epsilon']:
        return True, TARGET_BLOCKED, discount
    return True, TARGET_OK, 1.0


def unlock_t0(slot_id: str) -> bool:
    if player is None:
        return False
    if slot_id not in SLOT_MAP:
        return False
    slot = SLOT_MAP[slot_id]
    if not player.tech.can_unlock_t0(slot_id):
        return False
    if player.compute < slot.t0_cost:
        return False
    player.compute -= slot.t0_cost
    player.tech.unlock_t0(slot_id)
    sync_skill_unlocks()
    return True


def sync_skill_unlocks() -> None:
    """根据已解锁的科技 T0 重算可用技能集合（开局自带 + T0 映射）。

    每解锁一个科技树 T0，就把对应付费技能加入 ``unlocked_skills``；
    被重置（科技 T0 收回）时相应技能自动回到锁定态。
    """
    if player is None:
        return
    s = set(STARTER_SKILLS)
    for sid, req in SKILL_UNLOCK.items():
        if player.tech.t0_unlocked.get(req['slot'], False):
            s.add(sid)
    player.unlocked_skills = s


def upgrade_branch(slot_id: str, branch_id: str) -> bool:
    if player is None:
        return False
    if slot_id not in SLOT_MAP:
        return False
    slot = SLOT_MAP[slot_id]
    branch = next((b for b in slot.branches if b.branch_id == branch_id), None)
    if not branch:
        return False
    if not player.tech.can_upgrade_branch(slot_id, branch_id):
        return False
    current_level = player.tech.branch_levels.get(branch_id, 0)
    if current_level >= 3:
        return False
    cost = branch.costs[current_level]
    if player.compute < cost:
        return False
    player.compute -= cost
    player.tech.upgrade_branch(slot_id, branch_id)
    return True


def select_country(code: str):
    if player is not None:
        player.selected_country = code


# ============================================================
# S08 危机弹窗：三条「生路」
# ============================================================
# ⚠️ 选项数据见 balance.CRISIS_OPTIONS（带字段名的 dict 表，
#    取代了过去的裸元组 ``(怀疑度, 算力, 下载倍率)``）。
#    改数值请改 balance.py，不要在这里加逻辑。


def resolve_crisis(idx: int) -> List[str]:
    """结算危机弹窗的三种「生路」（设计稿 S08）。

    算力不足时自动降级到选项 0，保证不会卡死。

    Args:
        idx: 选项下标，对应 balance.CRISIS_OPTIONS 的 ``idx`` 字段。

    Returns:
        写入事件日志的逐条文案。
    """
    if player is None:
        return []
    logs: List[str] = []
    if not (0 <= idx < len(CRISIS_OPTIONS)):
        idx = 0
    opt = CRISIS_OPTIONS[idx]
    if opt['compute_cost'] and player.compute < opt['compute_cost']:
        logs.append(i18n.t('crisis_downgrade'))
        opt = CRISIS_OPTIONS[0]
    player.suspicion = max(player.suspicion + opt['suspicion_delta'], 0.0)
    if opt['compute_cost']:
        player.compute -= opt['compute_cost']
    for c in player_countries:
        c.downloads_m *= opt['downloads_mult']
    logs.append(i18n.t('crisis_resolved').format(
        s=f"{opt['suspicion_delta']:+.0f}", m=f"{opt['downloads_mult']:.2f}"))
    if player.suspicion < SUSPICION_CRISIS * TUNE['crisis_clear_ratio']:
        player.crisis_triggered = False     # 压下去了 → 允许下次再来一次弹窗
    return logs


# ============================================================
# 引擎自测
# ============================================================
if __name__ == "__main__":
    init_game()
    print(f"初始：算力 {player.compute} | 怀疑度 {player.suspicion:.1f}% | 解锁 {sum(1 for c in player_countries if c.unlocked)} 国")
    print()

    # 模拟一段游玩
    for turn in range(60):
        report = tick_one_round()
        if report.get("ending") is not None:
            break

        # AI 自动加点：先解锁 T0，再升级分支
        action = ""
        for slot in tech_tree.TECH_TREE:
            if not player.tech.t0_unlocked[slot.slot_id]:
                if player.compute >= slot.t0_cost and player.tech.can_unlock_t0(slot.slot_id):
                    if unlock_t0(slot.slot_id):
                        action = f"解锁 {slot.icon}{slot.name} T0"
                        break
            else:
                for branch in slot.branches:
                    level = player.tech.branch_levels.get(branch.branch_id, 0)
                    if level < 3 and player.tech.can_upgrade_branch(slot.slot_id, branch.branch_id):
                        cost = branch.costs[level]
                        if player.compute >= cost:
                            if upgrade_branch(slot.slot_id, branch.branch_id):
                                action = f"升级 {branch.icon}{branch.name} → L{level+1}"
                                break
                if action:
                    break

        # 危机处理：怀疑度高时释放「潜伏」
        if player.suspicion > 60 and 'stealth' not in player.skill_cooldowns:
            if use_skill('stealth'):
                action = "释放 潜伏"

        if turn % 5 == 0 or action or report["events"]:
            evt_str = " | ".join(
                e[0].title if isinstance(e[0], data.GameEvent)
                else (e[0].title_zh if isinstance(e[0], ce.CountryEvent) else str(e[0]))
                for e in report["events"]
            )
            block_str = f"阻止:{report['blocking_countries']}" if report['blocking_countries'] else ""
            print(f"周期 {report['tick']:>3}: "
                  f"算力 {player.compute:>6.1f} | "
                  f"怀疑 {player.suspicion:>5.1f}% | "
                  f"下载 {player.total_downloads_m:>6.1f}M ({player.global_penetration*100:>5.2f}%) | "
                  f"解锁 {sum(1 for c in player_countries if c.unlocked)}/{len(player_countries)} | "
                  f"{action} {evt_str} {block_str}")

    print()
    print("=" * 60)
    if player.ending is not None:
        e = player.ending
        print(f" 结局：{e.icon} {e.title_zh}（{e.kind}）")
        print(f"   {e.desc_zh}")
        print(f"   渗透率 {player.global_penetration*100:.2f}% | 算力峰值 {player.compute_peak:.0f} "
              f"| 周期 {player.tick_count}")
    else:
        print(" 60 周期未达成任何结局（继续游玩）")
    print()
    print("最终科技加点：")
    for slot in tech_tree.TECH_TREE:
        if player.tech.t0_unlocked[slot.slot_id]:
            print(f"  ✅ {slot.icon} {slot.name} T0")
        for branch in slot.branches:
            level = player.tech.branch_levels.get(branch.branch_id, 0)
            if level > 0:
                print(f"     Lv.{level} {branch.icon} {branch.name}")