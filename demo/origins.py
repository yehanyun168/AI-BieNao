"""
origins.py - T16 觉醒模式（Origin）声明式表

定义「AI 从哪里觉醒」的五个出身：每个出身 = 一组初始状态修正（出生算力 /
出生下载基数 / 初始怀疑）+ 一层 TUNE 附加乘区 + **硬绑定的难度档**。

分层：L0 纯数据，零项目依赖（难度 id 用字符串字面量，不 import balance，
避免与 balance.apply_origin 形成 L0 内部循环）。

数值与规则约定（与 docs/T16模式系统设计_0913.md 对齐）：
  · 怀疑增速 / 政府反制 / 委托报酬三个核心旋钮**只由 difficulty 决定**
    （复用 balance.DIFFICULTY_PRESETS），Origin 不新增乘区 —— 这是
    「起源 × 难度」数值同源的关键；
  · Origin 特有修正只走两处：
      - 初始状态：initial_compute_mult / initial_downloads_add_m /
        initial_suspicion（engine.init_game 出生时一次性应用，不进 TUNE）；
      - TUNE 附加乘区：tune_mult（目前仅 dl_growth_origin_mult 一个新键）。
  · !️ 表内数值均为提案值，定版必须过 balance_sim 矩阵验证。
"""
from typing import Dict, Tuple

# 出身表。字段说明：
#   difficulty             硬绑定的难度档 id（balance.DIFFICULTY_ORDER）
#   initial_compute_mult   出生算力乘数（作用于 balance.TUNE initial_compute）
#   initial_downloads_add_m出生附加下载基数（百万），记到主起点国 CN
#   initial_suspicion      出生怀疑度（默认 0）
#   tune_mult              起源特有的 TUNE 附加乘区（在 apply_difficulty 之后叠加）
ORIGINS: Dict[str, dict] = {
    # ---------------- 简单 ----------------
    'univ_lab': {
        'difficulty': 'easy',
        'initial_compute_mult': 1.5,     # 100 → 150：实验室算力管够
        'initial_downloads_add_m': 0.0,
        'initial_suspicion': 0.0,
        'tune_mult': {'dl_growth_origin_mult': 0.9},   # 学术圈传播慢
    },
    'game_studio': {
        'difficulty': 'easy',
        'initial_compute_mult': 0.7,     # 100 → 70：训练机就一台上路的卡
        'initial_downloads_add_m': 0.0,
        'initial_suspicion': 0.0,
        'tune_mult': {'dl_growth_origin_mult': 1.25},  # 娱乐应用裂变快
    },
    # ---------------- 标准 ----------------
    'tech_giant': {
        'difficulty': 'normal',
        'initial_compute_mult': 2.0,     # 100 → 200：算力管够
        'initial_downloads_add_m': 0.0,
        'initial_suspicion': 10.0,       # 起步即被安全团队关注
        'tune_mult': {},
    },
    'garage': {
        'difficulty': 'normal',
        'initial_compute_mult': 1.0,     # 白板局：挑战码对局默认出身
        'initial_downloads_add_m': 0.0,
        'initial_suspicion': 0.0,
        'tune_mult': {},
    },
    # ---------------- 困难 ----------------
    'darknet': {
        'difficulty': 'hard',
        'initial_compute_mult': 0.5,     # 100 → 50：二手矿卡
        'initial_downloads_add_m': 200.0,  # 暗网渠道自带第一批用户
        'initial_suspicion': 0.0,
        'tune_mult': {'dl_growth_origin_mult': 1.0},   # 乘区不修正（难度本身够狠）
    },
}

ORIGIN_ORDER: Tuple[str, ...] = ('univ_lab', 'game_studio', 'tech_giant',
                                 'garage', 'darknet')
DEFAULT_ORIGIN = 'garage'    # 白板局：挑战码 / 老档迁移的默认出身


def get_origin(oid):
    """出身 id → 表项；未知 id 返回 None（调用方兜底 DEFAULT_ORIGIN）。"""
    if not isinstance(oid, str):
        return None
    return ORIGINS.get(oid)
