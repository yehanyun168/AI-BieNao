"""
save_manager.py - 存档 / 读档

存档内容：玩家状态 + 各国状态 + 科技进度 + 成就 + v2 事件冷却
存储格式：JSON（明文，方便调试和手工改数值）

用法：
    save_manager.save('save.json')     # 存档
    save_manager.load('save.json')     # 读档（直接写回 engine 的全局状态）
    save_manager.list_saves()          # 列出存档目录里的所有存档
"""
import json
import os
from datetime import datetime
from typing import List

from data import STARTER_SKILLS, SKILL_UNLOCK
import commissions

SAVE_VERSION = 1
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saves')
DEFAULT_SLOT = 'slot1.json'


def _ensure_dir():
    os.makedirs(SAVE_DIR, exist_ok=True)


def save(path: str = None) -> str:
    """存档，返回实际写入的路径"""
    import engine

    _ensure_dir()
    path = path or os.path.join(SAVE_DIR, DEFAULT_SLOT)
    p = engine.player

    data = {
        'version': SAVE_VERSION,
        'saved_at': datetime.now().isoformat(timespec='seconds'),
        'player': {
            'compute': p.compute,
            'compute_peak': p.compute_peak,
            'suspicion': p.suspicion,
            'suspicion_peak': getattr(p, 'suspicion_peak', 0.0),
            'tick_count': p.tick_count,
            'events_history': p.events_history,
            'skill_cooldowns': dict(p.skill_cooldowns),
            'selected_country': p.selected_country,
            'crisis_triggered': p.crisis_triggered,
            'game_over': p.game_over,
            'ending_id': p.ending_id,
            'v2_cooldowns': dict(p.v2_cooldowns),
            'v2_seen': sorted(getattr(p, 'v2_seen', set())),
            'achievements': sorted(p.achievements),
            'seen_tutorial': bool(getattr(p, 'seen_tutorial', False)),
            'unlocked_skills': sorted(getattr(p, 'unlocked_skills', [])),
            # —— P0-3 委托 / 反制相关计数 ——
            'commissions': [commissions.to_dict(c) for c in
                            getattr(p, 'commissions', [])],
            'commissions_done': getattr(p, 'commissions_done', 0),
            'commissions_failed': getattr(p, 'commissions_failed', 0),
            'last_commission_tick': getattr(p, 'last_commission_tick', 0),
            'compute_earned_total': getattr(p, 'compute_earned_total', 0.0),
            'skill_uses': dict(getattr(p, 'skill_uses', {})),
        },
        'tech': {
            't0_unlocked': dict(p.tech.t0_unlocked),
            'branch_levels': dict(p.tech.branch_levels),
            'chosen_branch': dict(p.tech.chosen_branch),
        },
        'countries': [
            {
                'code': c.config.code,
                'unlocked': c.unlocked,
                'downloads_m': c.downloads_m,
                'current_block_intensity': c.current_block_intensity,
                'block_budget_remaining': c.block_budget_remaining,
            }
            for c in engine.player_countries
        ],
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load(path: str = None) -> bool:
    """读档，成功返回 True"""
    import engine

    path = path or os.path.join(SAVE_DIR, DEFAULT_SLOT)
    if not os.path.exists(path):
        return False

    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if data.get('version') != SAVE_VERSION:
        return False

    # 先把国家状态初始化好，再覆盖
    engine.init_game()
    p = engine.player

    ps = data['player']
    p.compute = ps['compute']
    p.compute_peak = ps.get('compute_peak', ps['compute'])
    p.suspicion = ps['suspicion']
    p.suspicion_peak = ps.get('suspicion_peak', ps['suspicion'])
    p.tick_count = ps['tick_count']
    p.events_history = ps.get('events_history', [])
    p.skill_cooldowns = ps.get('skill_cooldowns', {})
    p.selected_country = ps.get('selected_country')
    p.crisis_triggered = ps.get('crisis_triggered', False)
    p.game_over = ps.get('game_over', False)
    p.ending_id = ps.get('ending_id')
    p.v2_cooldowns = ps.get('v2_cooldowns', {})
    p.v2_seen = set(ps.get('v2_seen', []))
    p.achievements = set(ps.get('achievements', []))
    p.seen_tutorial = bool(ps.get('seen_tutorial', False))
    raw = ps.get('unlocked_skills')
    if raw:
        p.unlocked_skills = set(raw)
    else:
        # 旧档兼容：本次改动前写入的存档没有该键。从「开局自带 + 已解锁科技
        # T0」推导，避免读旧档后所有技能被锁死。
        p.unlocked_skills = set(STARTER_SKILLS)
        for sid, req in SKILL_UNLOCK.items():
            if p.tech.t0_unlocked.get(req['slot'], False):
                p.unlocked_skills.add(sid)

    ts = data.get('tech', {})
    p.tech.t0_unlocked = ts.get('t0_unlocked', p.tech.t0_unlocked)
    p.tech.branch_levels = ts.get('branch_levels', {})
    p.tech.chosen_branch = ts.get('chosen_branch', {})

    # —— P0-3 委托（老档无这些键 → default 补齐，读档不炸）——
    p.commissions = [commissions.from_dict(d)
                     for d in ps.get('commissions', [])]
    p.commissions_done = ps.get('commissions_done', 0)
    p.commissions_failed = ps.get('commissions_failed', 0)
    p.last_commission_tick = ps.get('last_commission_tick', 0)
    p.compute_earned_total = ps.get('compute_earned_total', 0.0)
    p.skill_uses = dict(ps.get('skill_uses', {}))
    # 存档一致性校验：deadline 已过的在场委托直接丢弃 —— 不加怀疑惩罚、
    # 不计 failed（存档锅不算玩家头，设计稿 §4.1/§4.6）
    p.commissions = [c for c in p.commissions
                     if c.deadline_tick is None
                     or c.deadline_tick > p.tick_count]

    by_code = {c.config.code: c for c in engine.player_countries}
    for cs in data.get('countries', []):
        c = by_code.get(cs['code'])
        if c is None:
            continue
        c.unlocked = cs['unlocked']
        c.downloads_m = cs['downloads_m']
        c.current_block_intensity = cs.get('current_block_intensity', 0.0)
        c.block_budget_remaining = cs.get('block_budget_remaining',
                                          c.config.block_budget)
    return True


def list_saves() -> List[str]:
    """列出存档目录里的所有 .json 存档（按修改时间倒序）"""
    _ensure_dir()
    files = [f for f in os.listdir(SAVE_DIR) if f.endswith('.json')]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(SAVE_DIR, f)),
               reverse=True)
    return files


def delete(path: str) -> bool:
    try:
        os.remove(path)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    import engine
    engine.init_game()
    for _ in range(15):
        engine.tick_one_round()
    path = save()
    print(f" 存档成功: {path}")
    before = (engine.player.tick_count, engine.player.total_downloads_m)
    engine.player.suspicion = 0
    for _ in range(5):
        engine.tick_one_round()
    print(f" 又跑了 5 周期: tick={engine.player.tick_count} "
          f"下载={engine.player.total_downloads_m:.1f}M")
    ok = load()
    after = (engine.player.tick_count, engine.player.total_downloads_m)
    print(f" 读档 {'成功' if ok else '失败'}: tick={after[0]} 下载={after[1]:.1f}M")
    print(f" 一致性: {'✅ 一致' if before == after else '❌ 不一致'}")
