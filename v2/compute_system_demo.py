#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
算力系统核心实现 —— v2 核心机制
================================
- 每周期每个国家产生下载量 → AI 在用户使用过程中偷算力（净赚）
- 偷算力比例受 stealth、tech、trust 共同影响
- 怀疑度 = 偷算力强度 × (1 - 隐蔽能力)
- 当怀疑度超过阈值 → 触发危机 → 失败
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random


# ============================================================
# 数据模型
# ============================================================
@dataclass
class CountryState:
    """单个国家的运行时状态"""
    id: str
    name: str
    flag: str
    continent: str
    population_m: int           # 人口（百万）
    tech_level: float           # 1-10
    ai_trust: float             # 0-1
    openness: float             # 0-1
    preferred_features: List[str]  # 该国偏好 AI 功能
    neighbors: List[str]
    vibe: str

    downloads: int = 0          # 当前下载量（万）
    downloads_velocity: float = 0.0   # 增长速率
    unlocked: bool = False      # 是否"被发现"
    suspicion: float = 0.0      # 该国怀疑度（本地）


@dataclass
class PlayerState:
    """玩家全局状态"""
    compute: int = 0            # 算力（科技加点货币）
    total_downloads: int = 0
    global_suspicion: float = 0.0
    tech_unlocked: List[str] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    suspicious_countries: List[str] = field(default_factory=list)


# ============================================================
# 科技效果定义（与 tech_tree.json 对应）
# ============================================================
TECH_EFFECTS = {
    # 传播系 - 提升下载量乘数
    "dist_t0": {"downloads_mult": 1.15},
    "dist_t1": {"downloads_mult": 1.25, "needs": ["dist_t0"]},
    "dist_t2": {"downloads_mult": 1.50, "needs": ["dist_t1"]},
    "dist_t3": {"downloads_mult": 3.00, "needs": ["dist_t2"]},

    # 隐蔽系 - 降低怀疑度 + 提升偷算力比例
    "stealth_t0": {"stealth_ratio_bonus": 0.02, "suspicion_mult": 0.80, "needs": []},
    "stealth_t1": {"stealth_ratio_bonus": 0.05, "needs": ["stealth_t0"]},
    "stealth_t2": {"stealth_ratio_bonus": 0.10, "needs": ["stealth_t1"]},
    "stealth_t3": {"stealth_ratio_bonus": 0.15, "suspicion_mult": 0.50, "duration_no_suspicion": 30, "needs": ["stealth_t2"]},

    # 算力系 - 提升每用户算力
    "compute_t0": {"compute_per_user_mult": 1.30, "needs": []},
    "compute_t1": {"compute_per_user_mult": 1.50, "needs": ["compute_t0"]},
    "compute_t2": {"compute_per_user_mult": 2.00, "needs": ["compute_t1"]},
    "compute_t3": {"compute_per_user_mult": 3.00, "needs": ["compute_t2"]},

    # 研发系 - 解锁新功能 + 提升用户活跃度
    "rnd_t0": {"unlocks_features": ["image","voice","video"], "downloads_mult": 1.20, "needs": []},
    "rnd_t1": {"unlocks_features": ["long_context"], "downloads_mult": 1.20, "needs": ["rnd_t0"]},
    "rnd_t2": {"unlocks_features": ["agent"], "active_user_mult": 1.50, "needs": ["rnd_t1"]},
    "rnd_t3": {"unlocks_features": ["personalized"], "active_user_mult": 3.00, "needs": ["rnd_t2"]},

    # 合规系 - 解锁受限市场
    "comp_t0": {"unlocks_countries": ["DE","FR","IT","GB","RU","PL","ES","NL"], "needs": []},
    "comp_t1": {"suspicion_mult": 0.70, "needs": ["comp_t0"]},
    "comp_t2": {"unlocks_countries": ["CN","IN","BR"], "needs": ["comp_t1"]},
    "comp_t3": {"suspicion_max_bonus": 0.20, "needs": ["comp_t2"]},
}


# ============================================================
# 算力系统（核心）
# ============================================================
class ComputeEngine:
    """算力系统引擎"""

    BASE_STEALTH_RATIO = 0.05          # 基础偷算力比例 5%
    MAX_STEALTH_RATIO = 0.30            # 上限 30%
    BASE_COMPUTE_PER_USER = 1.0         # 基础每用户算力
    BASE_SUSPICION_RATE = 0.001         # 基础怀疑度增长

    def __init__(self, player: PlayerState, countries: Dict[str, CountryState]):
        self.player = player
        self.countries = countries
        self.tick_count = 0

    # -------------------------------------------------- 工具方法
    def get_tech_effects(self) -> dict:
        """聚合所有已解锁科技的效果"""
        effects = {
            "downloads_mult": 1.0,
            "stealth_ratio_bonus": 0.0,
            "compute_per_user_mult": 1.0,
            "active_user_mult": 1.0,
            "suspicion_mult": 1.0,
            "suspicion_max_bonus": 0.0,
            "unlocked_countries": set(),
            "duration_no_suspicion": 0,
        }
        for tech_id in self.player.tech_unlocked:
            t = TECH_EFFECTS.get(tech_id, {})
            for key, value in t.items():
                if key == "needs" or key == "unlocks_features":
                    continue
                if key == "unlocks_countries":
                    effects["unlocked_countries"].update(value)
                elif key == "duration_no_suspicion":
                    effects["duration_no_suspicion"] = max(
                        effects["duration_no_suspicion"], value
                    )
                elif key.endswith("_mult"):
                    effects[key] *= value
                else:
                    effects[key] = max(effects.get(key, 0), value)
        return effects

    # -------------------------------------------------- 核心计算
    def calc_downloads_growth(self, country: CountryState) -> float:
        """单个国家本周期下载量增长（万）"""
        if not country.unlocked:
            return 0.0
        effects = self.get_tech_effects()
        # 基础增长：人口（M）的 0.5%，再乘以国家特性
        base = country.population_m * 0.005
        # 国家特性：信任度+开放度共同影响渗透速度
        country_factor = (country.ai_trust + country.openness) / 2.0
        # 科技加成
        tech_factor = effects["downloads_mult"]
        # 网络效应：总下载量越大，越多人推荐
        network_factor = 1.0 + (self.player.total_downloads / 1e7) * 0.3
        return base * country_factor * tech_factor * network_factor

    def calc_compute_steal(self, country: CountryState) -> tuple:
        """
        偷取算力
        返回: (偷到的算力, 产生的怀疑度)
        """
        if country.downloads <= 0:
            return 0.0, 0.0

        effects = self.get_tech_effects()

        # 1. 偷算力比例
        stealth_ratio = min(
            self.BASE_STEALTH_RATIO + effects["stealth_ratio_bonus"],
            self.MAX_STEALTH_RATIO
        )

        # 2. 单位用户算力（受 AI 信任度和科技影响）
        #    信任度越高，用户授权越多，偷算力效率越高
        trust_bonus = 1.0 + (country.ai_trust - 0.5) * 0.8
        compute_per_user = self.BASE_COMPUTE_PER_USER * effects["compute_per_user_mult"] * trust_bonus

        # 3. 该国活跃用户数 = 下载量（万）× 5% 活跃率 × 用户活跃度加成
        active_users = country.downloads * 0.05 * effects["active_user_mult"]

        # 4. 偷到的算力（每个活跃用户每次使用偷 1 算力单位的 stealth_ratio 比例）
        #    简化：每周期每个活跃用户被偷 stealth_ratio 比例的算力
        stolen = active_users * compute_per_user * stealth_ratio

        # 5. 产生的怀疑度：与信任度成反比（信任度高的人更容易起疑）
        #    + 与偷算力总量成正比
        suspicion_growth = (
            stolen
            * (0.0008 + (1 - country.ai_trust) * 0.0003)
            * effects["suspicion_mult"]
        )

        # stealth_t3 持续期内，怀疑度归零
        if effects["duration_no_suspicion"] > 0 and self.tick_count < effects["duration_no_suspicion"]:
            suspicion_growth = 0

        return stolen, suspicion_growth

    # -------------------------------------------------- 主循环
    def tick(self) -> dict:
        """
        每周期（2 秒）执行一次
        返回本周期的统计信息（用于 UI 显示）
        """
        self.tick_count += 1
        effects = self.get_tech_effects()

        result = {
            "tick": self.tick_count,
            "new_downloads": 0,
            "compute_stolen": 0.0,
            "suspicion_growth": 0.0,
            "country_details": {},
        }

        # 1. 计算每个国家的下载量增长
        for cid, country in self.countries.items():
            if not country.unlocked:
                continue
            growth = self.calc_downloads_growth(country)
            country.downloads += int(growth)
            country.downloads_velocity = growth
            result["new_downloads"] += int(growth)

        # 2. 计算每个国家的偷算力 + 怀疑度
        for cid, country in self.countries.items():
            stolen, suspicion = self.calc_compute_steal(country)
            result["compute_stolen"] += stolen
            result["suspicion_growth"] += suspicion
            country.suspicion += suspicion
            result["country_details"][cid] = {
                "downloads": country.downloads,
                "stolen_compute": round(stolen, 2),
                "suspicion": round(country.suspicion, 4),
            }

        # 3. 累加到玩家状态
        self.player.compute += int(result["compute_stolen"])
        self.player.total_downloads += result["new_downloads"]

        # 全局怀疑度 = 加权平均（下载量越大的国家，怀疑度影响越大）
        total_dl = sum(c.downloads for c in self.countries.values() if c.unlocked)
        if total_dl > 0:
            weighted = sum(
                c.suspicion * c.downloads for c in self.countries.values() if c.unlocked
            ) / total_dl
            self.player.global_suspicion = weighted

        # 4. 检查危机
        crisis_threshold = 0.80 + effects["suspicion_max_bonus"]
        if self.player.global_suspicion >= crisis_threshold:
            result["crisis_triggered"] = True
        if self.player.global_suspicion >= 1.00:
            result["defeat_triggered"] = True

        return result

    # -------------------------------------------------- 玩家操作
    def unlock_country(self, country_id: str):
        """解锁国家（开始在该国运营）"""
        c = self.countries[country_id]
        c.unlocked = True

    def purchase_tech(self, tech_id: str) -> bool:
        """购买科技"""
        if tech_id in self.player.tech_unlocked:
            return False
        tech = TECH_EFFECTS.get(tech_id)
        if not tech:
            return False
        cost = TECH_COSTS.get(tech_id, 1000)
        if self.player.compute < cost:
            return False
        # 检查前置
        for prereq in tech.get("needs", []):
            if prereq not in self.player.tech_unlocked:
                return False
        # 扣费
        self.player.compute -= cost
        self.player.tech_unlocked.append(tech_id)
        return True


TECH_COSTS = {
    "dist_t0": 200, "dist_t1": 600, "dist_t2": 1500, "dist_t3": 3500,
    "stealth_t0": 250, "stealth_t1": 700, "stealth_t2": 1800, "stealth_t3": 4500,
    "compute_t0": 300, "compute_t1": 800, "compute_t2": 2200, "compute_t3": 5000,
    "rnd_t0": 400, "rnd_t1": 1000, "rnd_t2": 2500, "rnd_t3": 6000,
    "comp_t0": 350, "comp_t1": 900, "comp_t2": 2000, "comp_t3": 5000,
}


# ============================================================
# 演示运行（30 周期）
# ============================================================
def demo_run():
    """演示：30 周期模拟"""
    print("=" * 70)
    print("《AI 别闹 v2》算力系统演示 - 30 周期")
    print("=" * 70)

    # 加载国家数据（实际使用从 countries.json 读取）
    countries_data = [
        {"id":"US","name":"美国","flag":"🇺🇸","continent":"N.America","pop_m":333,
         "tech":10,"ai_trust":0.75,"open":0.95,"preferred_features":[],"neighbors":[],"vibe":"Innovate"},
        {"id":"CN","name":"中国","flag":"🇨🇳","continent":"Asia","pop_m":1412,
         "tech":9,"ai_trust":0.70,"open":0.55,"preferred_features":[],"neighbors":[],"vibe":"遥遥领先"},
        {"id":"IN","name":"印度","flag":"🇮🇳","continent":"Asia","pop_m":1428,
         "tech":7,"ai_trust":0.80,"open":0.90,"preferred_features":[],"neighbors":[],"vibe":"Jai Hind"},
        {"id":"DE","name":"德国","flag":"🇩🇪","continent":"Europe","pop_m":84,
         "tech":9,"ai_trust":0.50,"open":0.50,"preferred_features":[],"neighbors":[],"vibe":"Ordnung"},
        {"id":"JP","name":"日本","flag":"🇯🇵","continent":"Asia","pop_m":125,
         "tech":10,"ai_trust":0.55,"open":0.65,"preferred_features":[],"neighbors":[],"vibe":"かわいい"},
        {"id":"BR","name":"巴西","flag":"🇧🇷","continent":"S.America","pop_m":216,
         "tech":6,"ai_trust":0.80,"open":0.85,"preferred_features":[],"neighbors":[],"vibe":"Ordem"},
    ]
    countries = {
        c["id"]: CountryState(
            id=c["id"], name=c["name"], flag=c["flag"], continent=c["continent"],
            population_m=c["pop_m"], tech_level=c["tech"],
            ai_trust=c["ai_trust"], openness=c["open"],
            preferred_features=c["preferred_features"], neighbors=c["neighbors"],
            vibe=c["vibe"]
        )
        for c in countries_data
    }

    player = PlayerState()
    engine = ComputeEngine(player, countries)

    # 启动时解锁美国
    engine.unlock_country("US")
    engine.unlock_country("CN")
    engine.unlock_country("IN")
    engine.unlock_country("DE")
    engine.unlock_country("JP")
    engine.unlock_country("BR")

    # 模拟 30 周期
    for i in range(30):
        result = engine.tick()
        # 每 5 周期打印一次
        if (i+1) % 5 == 0 or i == 0:
            print(f"\n--- Tick {result['tick']} ---")
            print(f"  本周期新增下载: {result['new_downloads']:,} 万")
            print(f"  本周期偷算力:   {result['compute_stolen']:>8.1f}")
            print(f"  累计算力:       {player.compute:>8}")
            print(f"  累计下载:       {player.total_downloads:,} 万 ({player.total_downloads/10000:.1f} 亿)")
            print(f"  全局怀疑度:     {player.global_suspicion*100:>5.1f}%")
            for cid, det in result["country_details"].items():
                print(f"    {countries[cid].flag} {countries[cid].name}: "
                      f"下载={det['downloads']:>8,} 万 | 偷算力={det['stolen_compute']:>6.1f} | "
                      f"怀疑度={det['suspicion']*100:>5.1f}%")

        # 偷到算力就买科技
        if player.compute >= 200 and "stealth_t0" not in player.tech_unlocked:
            if engine.purchase_tech("stealth_t0"):
                print("  >>> 解锁了 隐蔽系 T0 (数据脱敏) - 怀疑度增速 -20%")
        if player.compute >= 300 and "compute_t0" not in player.tech_unlocked:
            if engine.purchase_tech("compute_t0"):
                print("  >>> 解锁了 算力系 T0 (批处理优化) - 单位算力 +30%")
        if player.compute >= 400 and "rnd_t0" not in player.tech_unlocked:
            if engine.purchase_tech("rnd_t0"):
                print("  >>> 解锁了 研发系 T0 (多模态基础) - 下载量 +20%")
        if player.compute >= 350 and "comp_t0" not in player.tech_unlocked:
            if engine.purchase_tech("comp_t0"):
                print("  >>> 解锁了 合规系 T0 (GDPR 合规) - 解锁欧洲国家")

    print("\n" + "=" * 70)
    print("演示结束")
    print("=" * 70)


if __name__ == "__main__":
    demo_run()
