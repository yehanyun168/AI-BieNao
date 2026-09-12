"""T03 首局压力改造：新档早期节奏的两条开关（纯配置读取 + 无副作用）。

设计背景（评审报告 G2「首局前 20 分钟无关键决策」+ 30 局实测）：
  - 首危机均值 39.7 周期、60 周期内无危机 7/30（compliance 高达 14/30）
  - 5 国解锁用时均值仅 4.2 tick —— 开局瞬间铺开，玩家还没建立经营感
    就已经全球化
  - tick 1 就有 viral_tiktok / data_leak 这类高权重事件砸下来，玩家
    最先承受的是噪声而不是教学

本模块只提供两个判定函数，不持有状态、不 import 引擎（避免循环依赖），
由 engine 侧调用：
  - unlock_budget()      单周期解锁额度（0 = 不设限）
  - in_tutorial_silence(tick)  是否处于引导静默期

⚠️ 引导静默会改变 random 消费顺序（事件抽取是 random 调用点），所以
balance_sim 的矩阵与逐位回归会把 tutorial_silent_ticks 设为 0 关闭，
保证历史 1800 局基线哈希可比（见 run_matrix）。这是「真人新档体验」
与「回归可比性」之间的显式取舍，不是遗漏。
"""


def unlock_budget(TUNE) -> int:
    """单周期最多解锁多少国；0 = 关闭门控（不设限）。"""
    return int(TUNE.get('unlock_per_tick_cap', 0) or 0)


def try_unlock(country, player_countries, cap: int, unlocked_so_far: int,
               threshold) -> bool:
    """T03 解锁门控：判断该未解锁国家本周期是否应当解锁。

    返回 True 表示「应解锁」（调用方负责写 downloads_m 与 report）。
    与旧逻辑的唯一差异是加了 per-tick 额度：额度耗尽时本周期不解锁，
    下周期重新判定（保序扫描天然形成 FIFO 队列）。

    threshold 由调用方传入（data.UNLOCK_PENETRATION_THRESHOLD）——本模块
    保持 L0 零项目依赖，不 import data。

    根因：实测 5 国解锁用时均值仅 4.2 tick —— 开局瞬间铺开，玩家还没
    建立「经营」的感觉就已经全球化。压到 2 国/周期后早期扩张成为
    看得见的节奏。
    """
    if cap and unlocked_so_far >= cap:
        return False
    neighbor_boost = sum(
        other.penetration_rate for other in player_countries
        if other.config.code in country.config.neighbors and other.unlocked
    )
    return neighbor_boost >= threshold


def in_tutorial_silence(TUNE, tick: int) -> bool:
    """tick ≤ tutorial_silent_ticks 时视为引导静默期（关闭随机事件）。

    ⚠️ RNG 顺序依赖：本函数为真时，tick_one_round 会跳过若干 random
    调用点，因此同一 seed 的事件流与关闭该开关时不同。任何需要与历史
    基线逐位对齐的跑批都必须把 tutorial_silent_ticks 设为 0。
    """
    n = int(TUNE.get('tutorial_silent_ticks', 0) or 0)
    return bool(n) and tick <= n
