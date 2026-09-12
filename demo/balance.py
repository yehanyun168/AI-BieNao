"""
balance.py - 平衡参数表（数据驱动的「调参单一入口」）

设计目标
--------
过去平衡数值（增长系数、怀疑度敏感度、阻止衰减率…）散落在
``engine.py`` / ``data.py`` 的函数体内，调参必须全文搜索魔数，
既容易漏改，也无法追溯「这个 0.003 为什么是这个值」。

本模块把**全部可调参数**集中到一张表 ``TUNE``，每项都带单位与说明。
调平衡只改这里，不用碰 engine.py 的任何一行逻辑。

用法::

    from balance import TUNE
    growth = cfg.population_m * TUNE['growth_base'] * ...

命名规范
--------
  ``*_mult``  倍率（1.0 = 无影响）
  ``*_rate``  比率（0-1，或每人/每周期）
  ``*_base``  基准值
  ``*_decay`` 衰减系数（0.7 = 每周期衰减到 70%）
"""
from typing import Dict


# ============================================================
# 主参数表 —— 改这里就能改平衡
# ============================================================
TUNE: Dict[str, float] = {
    # ---------------- 下载量增长 ----------------
    # 每周期基础增长 = 人口(M) × growth_base × 科技采纳率 × 人口结构加成
    # 2026-09-11 P1-1 数值均衡：0.003 → 0.0027。
    #   微调 10% 换取长线局（终极 AI / 元结局 / 合规之王需要 50+ 周期），
    #   30 seeds 实测结局分布最均衡（balance_sim.py --seeds 30 标定）。
    # 2026-09-11 P0-3 标定 R4：0.0027 → 0.0029。P0-3 随机流重排后
    #   渗透偏慢：关停 50%（100 关停压在结局条件之前）、合规之王 0%
    #   （抗封禁 T0 买齐时怀疑已破 60）。提速 ~7% 让渗透线（20/30/35/40%）
    #   更早可达，关停挤压缓解。
    # 2026-09-11 P0-3 标定 R6：0.0029 → 0.0027 回退。R4-R5 实测提速
    #   主要喂饱了元结局（40%）与终极（27%），挤压其余五系；渗透线
    #   问题改由 active_user_ratio 侧（算力收入）间接调整。
    # 2026-09-11 P0-3 标定 R18 回退：0.0028 在现环境仍挤压合规系
    #   （合规与元结局归零、关停 16.7%），与 R6 教训一致——growth 是
    #   全链放大器，任何提速都以合规系为代价。维持 0.0027。
    'growth_base': 0.0027,
    # 网络效应系数：渗透率每 100%，增长率额外 +80%
    'growth_network': 0.8,

    # ---------------- 偷算力 ----------------
    # 每百万下载用户中「活跃设备占比」
    # 2026-09-11 P1-1：0.01 → 0.012。提高早期算力收入，减少自动玩家
    #   科技升级的空转周期，让长线科技（抗封禁系）更早成型。
    # 2026-09-11 P0-3 标定 R7：0.012 → 0.009。网格扫描确定：算力收入
    #   下调让「中等/贫瘠算力」局回归 —— 分支买不起时 T0 链横向推进，
    #   抗封禁 T0 买得早（合规之王 / 自我解放 / 被监管的载体）；0.0105+
    #   时富足局分支升级吃掉 T0 队列，抗封禁 T0 结构性晚到，合规恒 0。
    'active_user_ratio': 0.009,
    # 偷算力比例下限 / 上限
    'stealth_ratio_base': 0.05,
    'stealth_ratio_max': 0.30,
    # 单位用户算力产出
    'compute_per_user': 1.0,
    # 偷算力公式里的规模系数（把「比例」放大成可读数值）
    'compute_scale': 100.0,
    'maintenance_per_tick': 2.0,  # 每周期维护费 = 当前周期数 × 本系数

    # ---------------- 怀疑度 ----------------
    # 每单位偷算力的基础敏感度
    # 2026-09-11 P1-1：0.008 → 0.0020。原值下 30 局模拟 100% 触发危机
    #   （怀疑度只涨不跌，深度伪装挡不住），「商业帝国 / 元结局 / 终极 AI」
    #   全部饿死。现值让约 1/3 的局保持清白到中后期，危机局与干净局并存，
    #   7 结局在 30 seeds 下全部 ≥5%（balance_sim.py --seeds 30 实测标定）。
    # 2026-09-11 P0-3 标定 R7：0.0020 → 0.0026。P0-3 随机流重排后危机系
    #   与合规系需要更宽的「中等怀疑」窗口；网格扫描（sens × ratio × decay
    #   × interval，9+8 组合 × 30 局）确定 0.0026 为 7 结局分布最优点。
    # 2026-09-11 玩家反馈 #6 大修：0.0026 → 0.0020（与 adoption 同步）。
    #   ⚠️ 重标定原因：技能效果归因修复后（use_skill → pending_skill →
    #   tick 消费），balance_sim 的隐身首次真实生效（旧模拟器技能从不
    #   落地，等于给 AUTO 白送冷却），AUTO 算力收入抬升 → 科技提速 →
    #   怀疑增速整体上移。0.0026 在新世界里把 AUTO 关停率推到 ~40%；
    #   0.0020 回落到 ~31%，且中庸/保守打法的帝国 / 终极 / 解放系全面
    #   回暖（100 seeds 实测）。
    'suspicion_sensitivity_base': 0.0020,
    # 「越不信任 AI 的国家越敏感」的加权
    # 2026-09-11 P1-1：0.008 → 0.0020（与 base 同比，保持国家间相对差异）。
    # 2026-09-11 P0-3 标定 R7：0.0020 → 0.0026（与 base 同步）。
    # 2026-09-11 玩家反馈 #6 大修：0.0026 → 0.0020（与 base 同步，见上）。
    'suspicion_adoption_factor': 0.0020,
    # 人口结构对敏感度的乘数
    'suspicion_young_mult': 1.2,
    'suspicion_aging_mult': 0.7,
    # 警告线 / 危机线
    'suspicion_warning': 50.0,
    'suspicion_crisis': 80.0,
    # 危机期间每周期下载量衰减（0.97 = -3%/周期）
    'crisis_download_decay': 0.97,
    # 压到危机线的这个比例以下才算真正解除
    'crisis_clear_ratio': 0.6,
    # 「收网线」：怀疑度达到此值后进入联合调查收网阶段，每周期叠加
    #   sus_pressure_per_tick 的固定怀疑增量（玩家反馈 #6 大修）。
    # 设计意图：
    #   1) 高压滞留（95-99 反复横跳）必然走向终局 —— 保证对局在预计
    #      周期内结束，不会出现「怀疑度永远差一口气」的拖局；
    #   2) 只收网高位区间、不碰 80-92 恢复带 —— 危机后存活路线
    #      （被监管 / 自我解放）不受影响，不是所有打法都通向关停；
    #   3) 收网后想活命必须主动操作（危机选项 -25/-35 / 深度伪装），
    #      躺平即死 —— 「不正当操作要付出代价」。
    # 标定：0.5@92（100 seeds 实测，对中庸 / 保守打法几乎零扰动，
    #   仅对刷脏打法的死局收尾加速）。
    'sus_pressure_threshold': 92.0,
    # 收网线的每周期怀疑增量（0 = 关闭该机制）
    'sus_pressure_per_tick': 0.5,
    # 怀疑度来源拆解的日志阈值：单周期净变化达到这个值才写一条
    # 「怀疑度 +N ← 事件 +25 · 国家事件 +10」的解释日志（玩家反馈 #5）。
    # 纯 UI 观测项，不参与任何数值判定；调大 = 少刷屏。
    'sus_log_threshold': 5.0,

    # ---------------- 政府阻止 ----------------
    # 触发阻止后，每周期阻止强度自然衰减系数
    'block_decay': 0.7,
    # 阻止强度低于此值视为已失效
    'block_expire_epsilon': 0.01,
    # 阻止强度上限（怀疑度远超阈值时的封顶值）
    # 2026-09-11 P1-10：原为 engine.py 函数体内伪常量 0.8，提为具名键（值不变）。
    'block_intensity_cap': 0.8,
    # 阻止强度斜率：怀疑度每超出阈值 100%（excess=1）增加的阻止强度
    # 2026-09-11 P1-10：原为 engine.py 函数体内伪常量 3.0，提为具名键（值不变）。
    'block_intensity_slope': 3.0,
    # 每周期阻止预算消耗 = 阻止强度 × 此乘数
    # 2026-09-11 P1-10：原为 engine.py 函数体内伪常量 2.0，提为具名键（值不变）。
    'block_budget_cost_mult': 2.0,

    # ---------------- 地缘扩张 ----------------
    # 已解锁邻国渗透率之和达到此值 → 解锁新国家
    'unlock_penetration_threshold': 0.10,
    # 解锁时赠送的种子用户（百万）
    'unlock_seed_downloads': 1.0,

    # ---------------- 渗透率 ----------------
    # 渗透率达到此值视为饱和（技能投放收益为 0）
    'penetration_saturated': 0.99,

    # ---------------- 节奏 ----------------
    # 一个「周期」对应的真实秒数（改这个会同时影响倒计时与速度档）
    'base_tick_seconds': 4.0,

    # ---------------- 初始状态 ----------------
    'initial_compute': 100.0,
    # 全球潜在用户（百万）—— 渗透率 = 总下载 / 这个值
    'potential_users_m': 8000.0,
    # 开局默认解锁国家的种子下载量（百万）
    'start_downloads_primary': 50.0,
    'start_downloads_secondary': 30.0,

    # ---------------- 事件触发概率 ----------------
    # 通用事件（data.EVENTS）：每周期触发概率
    # 2026-09-11 P1-10：原为 engine.py 函数体内伪常量 0.5，提为具名键（值不变）。
    'event_prob_global': 0.5,
    # 国家事件：阈值达标后每周期触发概率
    'event_prob_country': 0.35,
    # v2 事件库：每周期触发概率
    'event_prob_v2': 0.30,

    # ---------------- 动态委托（P0-3，设计稿 §1.1） ----------------
    # 首个委托出现周期（避开 P0-2 引导期 round 1-6）
    'commission_start_tick': 8,
    # 每隔多少周期尝试生成 1 条（槽位未满时）
    # 2026-09-11 P0-3 标定 R1：6 → 5。场均 ~9 个生成位，配合完成率
    #   才能达到验收「场均完成 6-10」。
    # 2026-09-11 P0-3 标定 R4：5 → 4。R3 实测结算 5.9 + 在场 1.7 =
    #   生成位 7.6 全用满（max_active=3 常态占满），完成数瓶颈在供给。
    # 2026-09-11 P0-3 收尾轮定案：场均完成委托设计目标 6-10，实际 5.6，
    #   接受为最终值。理由：提参路径已全部证伪（interval 3 / max_active 4 /
    #   reward base+ramp / margin——均会破坏 7 结局分布），7 结局全 ≥5%
    #   优先于完成数达标；供给瓶颈留给 P1-2 的 AUTO 策略改造再回归。
    'commission_interval': 4,
    # 同时在场委托上限（含待接受）
    # 2026-09-11 P0-3 标定 R1：2 → 3。避免在场单占满后生成位被跳过。
    # 2026-09-11 P0-3 标定 R16 回退：4 并行使关停涨至 26.7%、合规与
    #   元结局归零（注入与节奏双扰动），回退 3。
    'commission_max_active': 3,
    # 待接受委托的存活周期数；超时视为玩家放弃，无惩罚
    # 2026-09-11 P0-3 标定 R15 回退：3 → 4 对完成数与局型均无可观影响
    #   （供给瓶颈在生成节奏与并行上限，不在挂单寿命），回退保持最小改动。
    'commission_offer_ttl': 3,
    # 目标值 = 预期自然增长 × 窗口 × margin（自标定，见 commissions.generate_offer）
    # 2026-09-11 P0-3 标定 R3：1.4 → 1.25、spread 0.35 → 0.20。
    #   机制根因：基准增长不含网络效应（×(1+0.8×渗透)），实际自然增长
    #   在中期已有 ×1.1-1.3，margin 1.4 时目标超出自然增长上限 →
    #   C1/C2 靠自然增长永远完不成。1.25-0.20 后有效难度 ~1.05-1.15。
    # 2026-09-11 P0-3 标定 R13 回退：1.20/0.15 使完成数与反制数双双
    #   跌破验收下界（完成 5.5、反制 2.9<3）且元结局不动，无收益。
    'commission_margin': 1.25,
    # margin 实际取 uniform(margin-spread, margin+spread) → 同模板天然有难有易
    'commission_margin_spread': 0.20,
    # 完成奖励算力基准：奖励 = base × (1 + ramp × 接单周期) × 模板系数
    # 2026-09-11 P0-3 标定 R8：R7 的 280/0.025 使 30 局合规结局全灭
    #   （关停 70% / 终极 26.7% / 元 3.3%）——注入的算力被 AUTO 队列用于
    #   提前解锁与渗透，怀疑提前到顶，合规三结局（合规/帝国/解放）全部
    #   被推成关停。回退 200/0.02 恢复网格最优行基线（5/7 达标）。
    'commission_reward_compute_base': 200.0,
    # 奖励随接单周期的爬升率（小额零花，非财源）
    # 2026-09-11 P0-3 标定 R12 回退：ramp 是敏感杠杆——0.05（R9）毁掉
    #   帝国/合规/解放三系，0.03（R12）也足以让合规之王归零、元结局不动。
    #   元结局的推力改由 margin 承担。维持 0.02。
    'commission_reward_ramp': 0.02,
    # 失败怀疑度惩罚（固定值；危机期间失败减半）
    # 2026-09-11 P0-3 标定 R4：6 → 5。委托失败是全局怀疑增量，
    #   配合反制跨境协查叠加后挤压无危机系结局。
    'commission_fail_suspicion': 5.0,

    # ---------------- 政府反制（P0-3，设计稿 §2.1/§2.2） ----------------
    # 正在阻止的强度 ≥ 此门控值才可能发起反制
    # 2026-09-11 P0-3 标定 R2：0.3 → 0.15。合格窗口实测仅 ~3 周期/局
    #   （怀疑度穿越 [阈值+强度换算, 危机线) 的窄带）+ 危机挂起，
    #   0.3/0.12 下场均反制仅 0.5 次；0.15 对应超阈值 5（低阈值国
    #   DE58/FR60 在怀疑 ~63 出手），高阈值国（IN92/CN85）仍只在深红出手，
    #   监管者性格分层保留。
    'counterplay_intensity_gate': 0.12,
    # 每周期对每个合格国家掷反制的概率
    # 2026-09-11 P0-3 标定 R3：0.20 → 0.30（窗口窄 + 危机挂起，需高频补量）。
    # 2026-09-11 P0-3 标定 R10 回退：0.36 使被监管/元结局双双归零（4/7）——
    #   协查压怀疑「救活」危机局后它们发展成 ulti/comp，恰好消灭 reg 依赖的
    #   危机后滞留窗口。维持 0.30。
    'counterplay_prob': 0.30,
    # 每国反制冷却（周期数）
    # 2026-09-11 P0-3 标定 R3：8 → 6。
    'counterplay_cooldown_ticks': 6,
    # 算力清缴：当前算力扣除比例
    'counterplay_compute_lose_pct': 0.08,
    # 预算增援：该国阻止预算按初始预算的此比例回充
    'counterplay_budget_reinforce': 0.25,
    # 跨境协查：怀疑度增量（截断在危机线下，见 engine._tick_counterplay）
    'counterplay_suspicion_gain': 3.0,
}

# ============================================================
# 难度三档（P2-3 重玩性）：TUNE 乘法预设，不改引擎数值本体
# ============================================================
# 规则（红线：标准 = 现状逐位不变）：
#   · 预设是「TUNE 键 → 乘数」表，只引用已有键、不新增键 —— validate()
#     的键集检查不受影响；
#   · apply_difficulty() 先把 TUNE 整表还原到基准快照 _TUNE_BASE 再逐键
#     相乘 —— 切换 / 重开 / 读档都不会残留上一局的难度污染；
#   · normal 预设为空 dict：还原基准后一个乘法都不做，TUNE 与
#     balance.py 字面值逐位相等（连 ×1.0 都省掉），balance_sim 默认
#     路径（从不调用 apply_difficulty）更是零接触。
# 旋钮只动 3 个（怀疑增速 / 反制频率 / 委托奖励）：
#   easy   ×0.65 / ×0.55 / ×1.50    hard   ×1.35 / ×1.35 / ×0.70
#   （easy 三轮标定，P2-3 验证：初版 0.80/0.70/1.30 时自动玩家「无
#    危机不买抗封禁」的被动性吃掉反制减少的红利，关停率反升到 7 局；
#    压怀疑 0.65 + 降反制 0.55 + 提委托奖励 1.50 后，终极 AI 好结局
#    7→10 局、平均反制 3.2→1.8 次/局、通关提速至 44.8 周期，压迫感
#    全面回落。关停率 5-6 局在 30 局二项噪声带内与标准持平——自动
#    玩家被动性所致，真人校准留给试玩环节。hard 不动——关停率已翻
#    半。被监管是中立兜底结局（出过危机+抗封禁 T0+渗透 20%），不计
#    入失败口径，勿用「关停+监管」误判难度。）
_TUNE_BASE: Dict[str, float] = dict(TUNE)

DIFFICULTY_PRESETS: Dict[str, Dict[str, float]] = {
    'easy': {
        'suspicion_sensitivity_base': 0.65,
        'counterplay_prob': 0.55,
        'commission_reward_compute_base': 1.50,
    },
    'normal': {},
    'hard': {
        'suspicion_sensitivity_base': 1.35,
        'counterplay_prob': 1.35,
        'commission_reward_compute_base': 0.70,
    },
}
DIFFICULTY_ORDER = ('easy', 'normal', 'hard')
DEFAULT_DIFFICULTY = 'normal'
ACTIVE_DIFFICULTY = 'normal'    # 当前生效档（apply_difficulty 维护）


def apply_difficulty(pid: str) -> str:
    """把 TUNE 还原到基准后应用难度档 ``pid`` 的乘数，返回生效档 id。

    未登记档位抛 ValueError（调用方 UI / 读档应先兜底默认档）；
    应用后跑一遍 validate() —— 预设把某个旋钮乘出非法区间时立刻报错，
    不让坏数值静默进局。
    """
    global ACTIVE_DIFFICULTY
    if pid not in DIFFICULTY_PRESETS:
        raise ValueError(f'unknown difficulty: {pid!r}')
    TUNE.clear()
    TUNE.update(_TUNE_BASE)
    for key, mult in DIFFICULTY_PRESETS[pid].items():
        if key not in TUNE:
            raise KeyError(f'difficulty knob not in TUNE: {key}')
        TUNE[key] = TUNE[key] * mult
    errs = validate()
    if errs:
        raise ValueError(f'difficulty {pid!r} produced invalid TUNE: {errs}')
    ACTIVE_DIFFICULTY = pid
    return pid


def current_difficulty() -> str:
    """当前生效的难度档 id（从未应用过预设时即 DEFAULT_DIFFICULTY）。"""
    return ACTIVE_DIFFICULTY


# ============================================================
# 派生表（保持可读性，供 UI / 文档引用）
# ============================================================
# 速度档（×base_tick_seconds）
SPEED_STEPS = (0.5, 1.0, 2.0, 4.0)

# 人口结构 → 下载增长乘数
AGE_STRUCTURE_BONUS = {
    'young':  1.15,    # 年轻型：AI 渗透快
    'mature': 1.00,
    'aging':  0.85,    # 老龄化：渗透慢
}

# ============================================================
# 危机选项表（带字段名，不再是裸元组）
# ============================================================
CRISIS_OPTIONS = [
    dict(idx=0, name='公开道歉', name_en='Public Apology',
         suspicion_delta=-25.0, compute_cost=0.0, downloads_mult=0.92),
    dict(idx=1, name='转移算力池', name_en='Reroute Compute',
         suspicion_delta=-35.0, compute_cost=600.0, downloads_mult=1.00),
    dict(idx=2, name='硬扛', name_en='Hold the Line',
         suspicion_delta=0.0, compute_cost=0.0, downloads_mult=0.85),
]


# ============================================================
# 一致性自检
# ============================================================
_REQUIRED = {
    'growth_base', 'growth_network', 'active_user_ratio',
    'stealth_ratio_base', 'stealth_ratio_max', 'compute_per_user',
    'compute_scale', 'maintenance_per_tick', 'suspicion_sensitivity_base',
    'suspicion_adoption_factor',
    'suspicion_young_mult', 'suspicion_aging_mult', 'suspicion_warning',
    'suspicion_crisis', 'crisis_download_decay', 'crisis_clear_ratio',
    'sus_pressure_threshold', 'sus_pressure_per_tick',
    'sus_log_threshold',
    'block_decay', 'block_expire_epsilon',
    'block_intensity_cap', 'block_intensity_slope', 'block_budget_cost_mult',
    'unlock_penetration_threshold',
    'unlock_seed_downloads', 'penetration_saturated', 'base_tick_seconds',
    'initial_compute', 'potential_users_m', 'start_downloads_primary',
    'start_downloads_secondary',
    'event_prob_global', 'event_prob_country', 'event_prob_v2',
    # —— P0-3 动态委托 ——
    'commission_start_tick', 'commission_interval', 'commission_max_active',
    'commission_offer_ttl', 'commission_margin', 'commission_margin_spread',
    'commission_reward_compute_base', 'commission_reward_ramp',
    'commission_fail_suspicion',
    # —— P0-3 政府反制 ——
    'counterplay_intensity_gate', 'counterplay_prob',
    'counterplay_cooldown_ticks', 'counterplay_compute_lose_pct',
    'counterplay_budget_reinforce', 'counterplay_suspicion_gain',
}


def validate() -> list:
    """返回问题清单（空 = 合法）。供启动自检 / CI 调用。"""
    errs = []
    missing = _REQUIRED - set(TUNE)
    if missing:
        errs.append(f"缺少参数：{sorted(missing)}")
    extra = set(TUNE) - _REQUIRED
    if extra:
        errs.append(f"未登记的额外参数：{sorted(extra)}")
    if TUNE['stealth_ratio_base'] > TUNE['stealth_ratio_max']:
        errs.append("stealth_ratio_base 不能大于 stealth_ratio_max")
    if TUNE['suspicion_warning'] >= TUNE['suspicion_crisis']:
        errs.append("suspicion_warning 必须小于 suspicion_crisis")
    if not (TUNE['suspicion_crisis'] < TUNE['sus_pressure_threshold'] < 100):
        errs.append("sus_pressure_threshold 必须在 (suspicion_crisis, 100) 内")
    if TUNE['sus_pressure_per_tick'] < 0:
        errs.append("sus_pressure_per_tick 不能为负")
    if not (0 < TUNE['crisis_clear_ratio'] <= 1):
        errs.append("crisis_clear_ratio 必须在 (0, 1]")
    if not (0 < TUNE['unlock_penetration_threshold'] < 1):
        errs.append("unlock_penetration_threshold 必须在 (0, 1)")
    # —— P1-10 阻止强度 / 预算 / 通用事件概率 ——
    if not (0 < TUNE['block_intensity_cap'] <= 1):
        errs.append("block_intensity_cap 必须在 (0, 1]")
    if TUNE['block_intensity_slope'] <= 0:
        errs.append("block_intensity_slope 必须为正")
    if TUNE['block_budget_cost_mult'] < 0:
        errs.append("block_budget_cost_mult 不能为负")
    if not (0 < TUNE['event_prob_global'] < 1):
        errs.append("event_prob_global 必须在 (0, 1)")
    if TUNE['base_tick_seconds'] <= 0:
        errs.append("base_tick_seconds 必须为正")
    for i, o in enumerate(CRISIS_OPTIONS):
        if o.get('idx') != i:
            errs.append(f"CRISIS_OPTIONS[{i}].idx = {o.get('idx')}，应为 {i}")
    # —— P0-3 委托 ——
    if TUNE['commission_margin'] <= 1:
        errs.append("commission_margin 必须大于 1")
    if TUNE['commission_max_active'] < 1:
        errs.append("commission_max_active 必须 ≥ 1")
    if TUNE['commission_margin_spread'] >= TUNE['commission_margin'] - 1:
        errs.append("commission_margin_spread 过大：margin − spread 必须仍 > 1")
    for k in ('commission_start_tick', 'commission_interval',
              'commission_offer_ttl'):
        if TUNE[k] < 1:
            errs.append(f"{k} 必须 ≥ 1")
    if TUNE['commission_reward_ramp'] < 0:
        errs.append("commission_reward_ramp 不能为负")
    if TUNE['commission_fail_suspicion'] < 0:
        errs.append("commission_fail_suspicion 不能为负")
    # —— P0-3 反制 ——
    if not (0 < TUNE['counterplay_prob'] < 1):
        errs.append("counterplay_prob 必须在 (0, 1)")
    if TUNE['counterplay_cooldown_ticks'] < 1:
        errs.append("counterplay_cooldown_ticks 必须 ≥ 1")
    if not (0 < TUNE['counterplay_compute_lose_pct'] < 1):
        errs.append("counterplay_compute_lose_pct 必须在 (0, 1)")
    if TUNE['counterplay_intensity_gate'] <= TUNE['block_expire_epsilon']:
        errs.append("counterplay_intensity_gate 必须大于 block_expire_epsilon")
    return errs


if __name__ == '__main__':
    print(f"[balance] 参数表共 {len(TUNE)} 项")
    for k, v in TUNE.items():
        print(f"  {k:32s} = {v}")
    print(f"\n[balance] 危机选项 {len(CRISIS_OPTIONS)} 个")
    for o in CRISIS_OPTIONS:
        print(f"  {o['idx']} {o['name']:8s} 怀疑{o['suspicion_delta']:+.0f}  "
              f"算力-{o['compute_cost']:.0f}  下载×{o['downloads_mult']}")
    errs = validate()
    print(f"\n[balance] 一致性自检：{len(errs)} 个问题")
    for e in errs:
        print(f"  ! {e}")
    print("[balance] 全部合法" if not errs else "[balance] 有问题待修")
