"""test_edge_cases.py - 边界用例（P0-2 存档容错 + P1-7 引擎边界）

运行（必须从 demo/ 目录）：
    KIVY_NO_FILELOG=1 python test_edge_cases.py

覆盖：
  P0-2 存档读取全链路容错：
  1. 乱码 JSON        → 不崩，返回 LOAD_CORRUPT
  2. {'version': 1}   → 缺 player 键，不崩，返回 LOAD_BAD_SCHEMA
  3. {'version': 999} → 版本不符，返回 LOAD_BAD_VERSION（不是裸 False）
  4. 正常存档          → 回归保护：仍能正常读出
  P1-7 引擎边界（全部锁「现状语义」——若未来改语义需同步改断言）：
  5. 怀疑度贴 0 时施加负怀疑效果 → 钳制在 0，不为负
  6. 算力清缴打到极低/为 0 → clamp ≥ 0；低算力时技能不可用且不写状态
  7. 20 国全部高强度封锁 → 不死锁，~10 tick 内以关停结局收束（实测）
  8. 反制跨境协查与危机同 tick → headroom 钳制使 crisis 不被误触发
  9. 委托 TTL 到期且条件达成 → 完成回调 + 奖励正确（非只有失败路径）
  10. 语言切 en → 存档 → 读档 → 语言不随存档恢复（PR-24 已知待办）
  11. 极端数值（1e300）→ tick 不崩、无 inf/nan 污染存档
  12. 连续 60 tick 不操作长跑 → 不崩、周期计数正确、结局最终产生
  P2-3 种子 + 难度（重玩性）：
  13. 同种子两局 30 tick 逐位一致；seed=None 不播种；seed 记入 PlayerState
  14. 难度预设：hard 旋钮 = 基准×乘数；normal 逐位还原；未知档抛 ValueError
  15. 存档：v2 携带 seed/difficulty 且读档重播种；v1 老档迁移补默认值可读
"""
import json
import math
import os
import random
import sys
import tempfile
from contextlib import contextmanager

# Kivy 会抢先解析 argv / 写文件日志；在这里 setdefault 双保险，
# 即使忘了带 KIVY_NO_FILELOG=1 的外部环境变量也能跑（与 balance_sim 同款）。
os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KIVY_NO_FILELOG', '1')

import engine
import i18n
import save_manager
import commissions
import data
import balance
from balance import TUNE

PASS, FAIL = [], []


def check(name: str, fn):
    """跑一条用例：不抛异常且 fn() 返回 True 才算通过。"""
    try:
        ok, detail = fn()
    except BaseException as e:                      # 用例自己崩了也算失败
        ok, detail = False, f"{type(e).__name__}: {e}"
    (PASS if ok else FAIL).append(name)
    mark = '[OK]  ' if ok else '[FAIL]'
    print(f"  {mark} {name}  — {detail}")
    return ok


def _write(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def _last_log_line() -> str:
    try:
        with open(save_manager.CRASH_LOG, encoding='utf-8') as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        return lines[-1] if lines else ''
    except OSError:
        return ''


# ============================================================
# P1-7 测试基建
# ============================================================
@contextmanager
def _tuned(**overrides):
    """临时覆盖 balance.TUNE 参数（制造确定性随机流），退出时恢复。

    只动测试进程内存里的 dict，不碰 balance.py 源文件。
    """
    saved = {k: TUNE[k] for k in overrides if k in TUNE}
    TUNE.update(overrides)
    try:
        yield
    finally:
        TUNE.update(saved)


# 屏蔽全部随机事件流（通用/国家/v2 事件 + 反制新预警），
# 让被测链路的数值完全确定。反制**结算**不受此影响（靠注入 pending）。
_ZERO_STREAM = dict(event_prob_global=0.0, event_prob_country=0.0,
                    event_prob_v2=0.0, counterplay_prob=0.0)


@contextmanager
def _forced_randrange(value):
    """临时钉死 random.randrange 的返回值（控制反制三选一掷点）。

    反制结算 _resolve_counterplay 用 randrange(3)：
      0=算力清缴 / 1=预算增援 / 2=跨境协查。
    """
    orig = random.randrange
    random.randrange = lambda stop: value
    try:
        yield
    finally:
        random.randrange = orig


def _fresh(seed: int):
    """固定种子 + 重开一局，返回 player（init_game 会重置反制/委托全局态）。"""
    random.seed(seed)
    return engine.init_game()


def _find_lang_keys(obj, trail: str = ''):
    """递归找 dict 里形如 lang/language 的键（验证存档不含语言字段）。"""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ('lang', 'language'):
                hits.append(trail + k)
            hits += _find_lang_keys(v, trail + k + '.')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += _find_lang_keys(v, trail + f'[{i}].')
    return hits


def main() -> int:
    tmp = tempfile.mkdtemp(prefix='aibienao_edge_')
    engine.init_game()
    for _ in range(12):
        engine.tick_one_round()

    print("=" * 62)
    print("P0-2 存档读取容错 —— 边界用例")
    print("=" * 62)

    # ---- 0. 正常存档（回归保护，必须有）----
    good = os.path.join(tmp, 'good.json')

    def _good():
        path = save_manager.save(good)
        expect_tick = engine.player.tick_count
        expect_compute = round(engine.player.compute, 6)
        # 先污染内存状态，确认读档真的把它改回来了
        engine.player.tick_count = -1
        ok, reason = save_manager.load_ex(path)
        if not (ok and reason == save_manager.LOAD_OK):
            return False, f"load_ex 返回 ({ok}, {reason})，期望 (True, ok)"
        if engine.player.tick_count != expect_tick:
            return False, (f"tick_count 读回 {engine.player.tick_count}，"
                           f"期望 {expect_tick}")
        if round(engine.player.compute, 6) != expect_compute:
            return False, f"compute 读回 {engine.player.compute}"
        # 老接口向后兼容：成功必须真值（现有 `assert save_manager.load()` 依赖）
        if not save_manager.load(path):
            return False, "load() 老接口成功时应返回真值"
        return True, f"tick={expect_tick} 读回一致，load() 老接口仍为真"

    check('0. 正常存档可正常读出（回归保护）', _good)

    # ---- 1. 乱码 JSON ----
    junk = os.path.join(tmp, 'junk.json')

    def _junk():
        _write(junk, '\x00\x01\x02这不是 JSON}{[]{ 乱码 garbage')
        ok, reason = save_manager.load_ex(junk)
        if ok or reason != save_manager.LOAD_CORRUPT:
            return False, f"返回 ({ok}, {reason})，期望 (False, corrupt)"
        if save_manager.load(junk):
            return False, "load() 老接口坏档时应返回假值"
        if 'reason=corrupt' not in _last_log_line():
            return False, f"crash.log 未记录：{_last_log_line()[:80]}"
        return True, f"返回 corrupt 且已落日志，未抛异常"

    check('1. 乱码 JSON 不崩 → LOAD_CORRUPT', _junk)

    # ---- 2. 缺 player 键 ----
    noplayer = os.path.join(tmp, 'noplayer.json')

    def _noplayer():
        _write(noplayer, json.dumps({'version': 1}))
        ok, reason = save_manager.load_ex(noplayer)
        if ok or reason != save_manager.LOAD_BAD_SCHEMA:
            return False, f"返回 ({ok}, {reason})，期望 (False, bad_schema)"
        if 'reason=bad_schema' not in _last_log_line():
            return False, f"crash.log 未记录：{_last_log_line()[:80]}"
        return True, "返回 bad_schema 且已落日志，未抛 KeyError"

    check('2. {"version": 1} 缺 player 键不崩 → LOAD_BAD_SCHEMA', _noplayer)

    # ---- 3. 版本不符 ----
    badver = os.path.join(tmp, 'badver.json')

    def _badver():
        _write(badver, json.dumps({'version': 999, 'player': {}}))
        ok, reason = save_manager.load_ex(badver)
        if ok or reason != save_manager.LOAD_BAD_VERSION:
            return False, f"返回 ({ok}, {reason})，期望 (False, bad_version)"
        if save_manager.load(badver):
            return False, "load() 老接口版本不符时应返回假值"
        if 'reason=bad_version' not in _last_log_line():
            return False, f"crash.log 未记录：{_last_log_line()[:80]}"
        return True, "返回 bad_version（不是裸 False）且已落日志"

    check('3. {"version": 999} → LOAD_BAD_VERSION', _badver)

    # ---- 附加：文件不存在 = 全新玩家，不该报"损坏" ----
    def _missing():
        gone = os.path.join(tmp, 'nope.json')
        ok, reason = save_manager.load_ex(gone)
        if ok or reason != save_manager.LOAD_MISSING:
            return False, f"返回 ({ok}, {reason})，期望 (False, missing)"
        if save_manager.load_fail_text(reason) == save_manager.load_fail_text(
                save_manager.LOAD_CORRUPT):
            return False, "missing 与 corrupt 用了同一句提示文案"
        return True, "返回 missing，文案与损坏提示区分开"

    check('4. 文件不存在 → LOAD_MISSING（不弹"损坏"提示）', _missing)

    # ============================================================
    # P1-7 引擎边界用例（全部锁「现状语义」）
    # ============================================================
    print("=" * 62)
    print("P1-7 引擎边界 —— 现状语义锁定用例")
    print("=" * 62)

    # ---- 5. 怀疑度贴 0 时施加负怀疑效果 ----
    def _sus_floor():
        """现状语义（若未来改语义需同步改这里）：
        怀疑度的任何来源都不允许产生负值 ——
          · tick 阶段 2（engine.py:339）：max(0, min(100, sus + 增量))
          · 事件结算（engine.py:606）：max(0, min(100, sus + effect_suspicion))
          · 委托完成减免（engine.py:941）：max(0.0, sus - sus_relief)
        目前无怀疑增量为负的技能，负效果真实入口是负怀疑事件（viral_tiktok
        -2）与 C5 委托完成减免，两条都锁。"""
        p = _fresh(5)
        with _tuned(**_ZERO_STREAM):
            p.suspicion = 0.0
            evt = next(e for e in data.EVENTS if e.effect_suspicion < 0)
            engine._apply_event(evt)
            if p.suspicion != 0.0:
                return False, (f"负怀疑事件 {evt.id}({evt.effect_suspicion}) 后 "
                               f"sus={p.suspicion}，应钳制在 0")
            # C5 式完成减免：sus=0 时再减 4 仍应为 0
            com = commissions.CommissionState(
                uid=7102, template_id='C5', goal='stealth', icon='[S]',
                name_zh='测试隐身', name_en='Test Quiet', window=8,
                reward_mult=1.5, status='active', sus_relief=4.0,
                cond={'suspicion': {'lte': 50.0}})
            p.commissions.append(com)
            done_before = p.commissions_done
            engine._complete_commission(com)
            if p.suspicion != 0.0:
                return False, f"完成减免 -4 后 sus={p.suspicion}，应仍为 0"
            if p.commissions_done != done_before + 1 or com in p.commissions:
                return False, "完成回调计数/移除不正确"
            # tick 全链路：0 起步跑一个周期，怀疑度不得为负
            r = engine.tick_one_round()
            if not (0.0 <= p.suspicion <= 100.0):
                return False, f"tick 后 sus={p.suspicion} 越界"
        return True, (f"{evt.id}({evt.effect_suspicion}) 与 C5 减免 -4 后均停在 0，"
                      f"tick 后 sus={p.suspicion:.4f} ≥ 0")

    check('5. 怀疑度=0 时负效果 → 钳制在 0 不为负', _sus_floor)

    # ---- 6. 算力清缴打到极低 / 为 0 ----
    def _compute_seizure_floor():
        """现状语义（若未来改语义需同步改这里）：
        算力清缴（反制三选一 roll=0，engine.py:765-766）：
          lose = compute × counterplay_compute_lose_pct(0.08) × resist
          compute = max(0.0, compute - lose)   ← clamp 恒 ≥ 0
        实测：结算发生在阶段 3.5（阶段 2 偷算力之后），故
          after = max(0, (before + 本tick偷算力) × (1 - 0.08))。
        现值 pct=0.08 < 1 → 经 tick 路径清缴本身打不出负数，clamp 是
        防御性兜底；本用例把它连同「低算力时技能判定不写任何状态」一起锁。"""
        p = _fresh(7)
        cn = engine.player_countries[0]
        with _tuned(**_ZERO_STREAM):
            # 场景 A：常规算力被清缴，公式精确成立
            cn.current_block_intensity = 0.5
            cn.block_budget_remaining = 100.0
            p.compute = 500.0
            p.suspicion = 0.0
            p.last_commission_tick = p.tick_count      # 屏蔽委托生成干扰
            engine._counterplay_pending['CN'] = p.tick_count
            with _forced_randrange(0):                 # 钉死 roll=0 算力清缴
                r = engine.tick_one_round()
            strikes = [e for e in (r.get('counterplay') or [])
                       if e['phase'] == 'strike']
            if len(strikes) != 1 or strikes[0]['type'] != 'compute_seizure':
                return False, f"应恰好结算一次算力清缴，实际 {strikes}"
            expect = max(0.0, (500.0 + r['compute_gain'])
                         * (1.0 - TUNE['counterplay_compute_lose_pct']))
            if abs(p.compute - expect) > 1e-6:
                return False, f"清缴后 compute={p.compute}，期望 {expect}"
            if p.compute < 0:
                return False, f"清缴后 compute={p.compute} 为负"
            # 场景 B：算力为 0 时被清缴 → 仍 ≥ 0（clamp 兜底不产生负数）
            p2 = _fresh(7)
            cn2 = engine.player_countries[0]
            cn2.current_block_intensity = 0.5
            cn2.block_budget_remaining = 100.0
            p2.compute = 0.0
            p2.last_commission_tick = p2.tick_count
            engine._counterplay_pending['CN'] = p2.tick_count
            with _forced_randrange(0):
                r2 = engine.tick_one_round()
            expect2 = max(0.0, r2['compute_gain']
                          * (1.0 - TUNE['counterplay_compute_lose_pct']))
            if abs(p2.compute - expect2) > 1e-6 or p2.compute < 0:
                return False, (f"compute=0 清缴后 {p2.compute}，"
                               f"期望 {expect2} 且 ≥ 0")
            # 场景 C：低算力时付费技能不可用，且失败不写任何状态
            p2.unlocked_skills.add('take_cut')          # cost=80
            cooldowns_before = dict(p2.skill_cooldowns)
            uses_before = dict(p2.skill_uses)
            ok_cast = engine.use_skill('take_cut')
            if ok_cast:
                return False, f"compute={p2.compute} < 80 时 take_cut 不应可释放"
            if (p2.skill_cooldowns != cooldowns_before
                    or p2.skill_uses != uses_before
                    or p2.pending_skill):
                return False, (f"失败施放污染了状态：cooldowns={p2.skill_cooldowns} "
                               f"uses={p2.skill_uses} pending={p2.pending_skill!r}")
        return True, (f"500→{p.compute:.2f}（=预期公式）；0→{p2.compute:.4f} ≥ 0；"
                      f"低算力 take_cut 拒绝且零状态写入")

    check('6. 算力清缴 → clamp ≥ 0；低算力技能不可用且不写状态', _compute_seizure_floor)

    # ---- 7. 20 国全部高强度封锁 ----
    def _all_blocked():
        """现状行为（2026-09-11 seed=42 实测，若未来改语义需同步改这里）：
        20 国全部处于高强度阻止（强度顶格 0.8）+ 怀疑度 95 的局面：
          · 每个 tick 正常推进、不抛异常、20/20 国保持阻止中；
          · 不会死锁也不会永续 —— 怀疑度 ≥92 进入收网区（+0.5/tick），
            约 10 个周期推到 100 → 「被关停」结局（阻止预算尚未耗尽游戏
            已结束）。锁「全封锁 → 有界周期内出结局」这一收束性。"""
        p = _fresh(42)
        with _tuned(**_ZERO_STREAM):
            for c in engine.player_countries:
                c.unlocked = True
                c.downloads_m = 20.0
                c.current_block_intensity = 0.8
                c.block_budget_remaining = c.config.block_budget
            p.suspicion = 95.0
            expected = p.tick_count
            for _ in range(60):
                r = engine.tick_one_round()
                expected += 1
                if r['tick'] != expected:
                    return False, (f"周期计数断档：report={r['tick']} "
                                   f"期望 {expected}")
                n_blk = sum(1 for c in engine.player_countries
                            if c.current_block_intensity
                            > TUNE['block_expire_epsilon'])
                if n_blk != 20:
                    return False, (f"t{r['tick']} 仅 {n_blk}/20 国处于阻止中"
                                   f"（sus={p.suspicion:.1f}）——全封锁未维持")
                if r['ending']:
                    break
            if not p.game_over or p.ending_id is None:
                return False, (f"60 tick 全封锁仍未出结局（sus={p.suspicion:.1f} "
                               f"game_over={p.game_over}）——疑似死局，需人工确认")
            if p.ending_id != 'shutdown':
                return False, f"实测收束结局为 {p.ending_id}，当前锁 shutdown"
        return True, (f"第 {p.tick_count} tick 以「{p.ending_id}」收束，"
                      f"期间每 tick 20/20 国阻止中、计数连续")

    check('7. 20 国全高强度封锁 → 不死锁，有界周期内出结局', _all_blocked)

    # ---- 8. 反制跨境协查与危机同 tick ----
    def _counterplay_headroom():
        """现状语义（engine.py:784-788，玩家反馈 #6 修复，回归必锁）：
        跨境协查的怀疑增量先取剩余余量再 max(0,·) 兜底：
          headroom = max(0, 危机线(80) − 1 − 当前怀疑)
          delta    = min(协查增量(3.0), headroom)   恒 ≥ 0
        → 反制永不把怀疑推过危机线 −1（79），同一 tick 内阶段 5 的
        危机检查（sus ≥ 80）不会被反制误触发。旧实现的 min() 在
        sus ≥ 79 时会算出负增量倒扣怀疑，此用例防止该 bug 复活。"""
        p = _fresh(1)
        cn = engine.player_countries[0]
        us = engine.player_countries[1]
        with _tuned(**_ZERO_STREAM):
            cn.downloads_m = 1e-9                      # 掐掉偷算力，数值确定
            us.downloads_m = 1e-9
            p.suspicion = 79.0                         # 危机线下 1 点
            engine._counterplay_pending['CN'] = p.tick_count
            with _forced_randrange(2):                 # 钉死 roll=2 跨境协查
                r = engine.tick_one_round()
            strikes = [e for e in (r.get('counterplay') or [])
                       if e['phase'] == 'strike']
            if len(strikes) != 1 or strikes[0]['type'] != 'cross_inquiry':
                return False, f"应恰好结算一次跨境协查，实际 {strikes}"
            if strikes[0]['detail'] != '+0.0':
                return False, (f"headroom=0 时增量应为 0，detail="
                               f"{strikes[0]['detail']!r}")
            if r['crisis'] or p.crisis_triggered:
                return False, (f"反制误触发危机：report.crisis={r['crisis']} "
                               f"crisis_triggered={p.crisis_triggered}")
            # 协查贡献已由 detail '+0.0' 单独锁死；这里的 +0.0036 是阶段 1
            # 增长→阶段 2 偷算力的正常增量（1e-9 下载经一 tick 长到 ~3M），
            # 不是反制贡献。锁「未越危机线」本身。
            if p.suspicion >= data.SUSPICION_CRISIS:
                return False, f"sus={p.suspicion} 越过危机线 {data.SUSPICION_CRISIS}"
            if abs(p.suspicion - 79.0) > 0.01:
                return False, (f"sus={p.suspicion}，应停在 79±0.01"
                               f"（tick 自身偷算力 ≤0.01）")
            # 直调路径补两个边界：79.9 不倒扣、50 → 恰好 +3
            for sus_in, want in ((79.9, 79.9), (50.0, 53.0)):
                p.suspicion = sus_in
                with _forced_randrange(2):
                    engine._resolve_counterplay(cn, 1.0)
                if abs(p.suspicion - want) > 1e-9:
                    return False, (f"sus {sus_in} 经协查后 {p.suspicion}，"
                                   f"期望 {want}（headroom 钳制公式失效）")
            if p.crisis_triggered:
                return False, "直调路径误置 crisis_triggered"
        return True, ("协查在 sus=79 时增量 +0.0、危机未触发；"
                      "79.9 不倒扣 / 50→53 公式成立")

    check('8. 反制跨境协查同 tick → headroom 钳制，crisis 不误触发', _counterplay_headroom)

    # ---- 9. 委托 TTL 到期且条件达成（成功路径）----
    def _commission_success():
        """现状语义（若未来改语义需同步改这里）：
        非 stealth 类活跃委托在到期 tick（engine.py:862-868）：
          条件已满足 → _complete_commission：commissions_done +1、
          compute += reward（reward 在 accept_commission 时按
          base × (1 + ramp × 接单周期) × reward_mult 结算）、从在场列表
          移除、report['commission_done'] 携带实例、事件日志记录。
        test_build.py:238-251 只覆盖了到期失败路径，本条锁到期成功路径。
        注：完成回调发生在阶段 6.6，本 tick 的阶段 2 偷算力已先行入账，
        故 compute 差值 = reward + 本 tick 偷算力。"""
        p = _fresh(3)
        with _tuned(**_ZERO_STREAM):
            com = commissions.CommissionState(
                uid=7201, template_id='C3', goal='compute', icon='[C]',
                name_zh='测试算力冲刺', name_en='Test Compute Sprint',
                window=8, reward_mult=1.0,
                cond={'compute_earned_delta': 100.0})   # 裸数值 = ≥ 语义
            com.offered_tick = p.tick_count
            p.commissions.append(com)
            if not engine.accept_commission(com.uid):
                return False, "接受待接受委托应成功"
            expect_reward = (TUNE['commission_reward_compute_base']
                             * (1 + TUNE['commission_reward_ramp']
                                * com.accepted_tick) * com.reward_mult)
            if abs(com.reward - expect_reward) > 1e-9:
                return False, (f"奖励结算 {com.reward} ≠ 公式值 {expect_reward}")
            if com.status != 'active' or com.deadline_tick != \
                    p.tick_count + com.window:
                return False, (f"接单后状态异常：status={com.status} "
                               f"deadline={com.deadline_tick}")
            p.compute_earned_total = com.snap_compute + 101.0   # 超额达成
            p.tick_count = com.deadline_tick             # 快进到截止周期
            p.last_commission_tick = p.tick_count        # 屏蔽新委托生成
            done_before = p.commissions_done
            compute_before = p.compute
            r = engine.tick_one_round()
            if r.get('commission_done') is not com:
                return False, (f"report['commission_done'] 应为本单，实际 "
                               f"{r.get('commission_done')}")
            if p.commissions_done != done_before + 1:
                return False, f"完成计数 {done_before}→{p.commissions_done}"
            gained = p.compute - compute_before - r['compute_gain']
            if abs(gained - com.reward) > 1e-6:
                return False, (f"奖励到账 {gained} ≠ {com.reward}"
                               f"（已扣除本 tick 偷算力 {r['compute_gain']:.2f}）")
            if com in p.commissions:
                return False, "完成后应从在场列表移除"
            if not p.events_history or '委托完成' not in p.events_history[0]:
                return False, f"事件日志未记录完成：{p.events_history[:1]}"
        return True, (f"到期达成 → 计数 +1、奖励 {com.reward:.0f} 精确到账、"
                      f"已移除、report/日志均携带")

    check('9. 委托 TTL 到期且条件达成 → 完成回调与奖励正确', _commission_success)

    # ---- 10. 语言切 en → 存档 → 读档 → 语言不随存档恢复 ----
    def _lang_not_persisted():
        """现状行为（⚠️ 已知待办 PR-24，若未来修复需同步改这里）：
        save_manager.save() 不序列化语言 —— 存档顶层只有 version /
        saved_at / player / tech / countries，全文无 lang 键；load 也不
        碰 i18n 全局。因此「切 en → 存档 → 重开 → 读档」后语言是进程
        默认 zh，用户的 en 偏好丢失。单进程内 load 前后 get_lang() 不变
        （'en' 仍是 'en'），「回 zh」发生在新会话 —— 本用例用「重置到
        默认再读档」模拟重开。"""
        _fresh(11)
        i18n.set_lang('en')
        try:
            path = os.path.join(tmp, 'lang.json')
            save_manager.save(path)
            with open(path, encoding='utf-8') as f:
                saved = json.load(f)
            hits = _find_lang_keys(saved)
            if hits:
                return False, f"存档出现语言键 {hits}（PR-24 已被修复？同步改本用例）"
            ok, reason = save_manager.load_ex(path)
            if not ok:
                return False, f"读档失败 ({ok}, {reason})"
            if i18n.get_lang() != 'en':
                return False, (f"单进程内 load 不应触碰语言，实际 "
                               f"{i18n.get_lang()}")
            # 模拟「重开」：新会话语言是默认 zh，读档后仍是 zh（偏好丢失）
            i18n.set_lang(i18n.LANG_ZH)
            ok2, _ = save_manager.load_ex(path)
            if not ok2:
                return False, "二次读档失败"
            if i18n.get_lang() != i18n.LANG_ZH:
                return False, f"重开+读档后语言 {i18n.get_lang()}，现状应为默认 zh"
        finally:
            i18n.set_lang(i18n.LANG_ZH)                # 还原，保证用例独立
        return True, ("存档无语言字段；load 不动语言；重开（默认 zh）+读档"
                      "后 en 偏好丢失 = PR-24 现状")

    check('10. 语言 en → 存 → 读 → 不随存档恢复（PR-24 现状）', _lang_not_persisted)

    # ---- 11. 极端数值 ----
    def _extreme_values():
        """现状语义（若未来改语义需同步改这里）：
        float 范围内的极端值（1e300）经 tick：
          · 怀疑度被 engine.py:339 收口到 [0, 100]（1e300 → 恰好 100，
            -1e300 → 恰好 0），危机/关停链路正常判定，不崩；
          · 下载增长的网络效应放大后仍是有限数（无 inf）；
          · 存档 JSON 不出现 NaN / Infinity 字面量（json.dump 的
            allow_nan 默认开着，一旦有污染就会写进文件，本断言能抓住），
            且能原样读回（game_over / ending_id / 数值一致）。"""
        p = _fresh(13)
        with _tuned(**_ZERO_STREAM):
            p.compute = 1e300
            p.compute_peak = 1e300
            for c in engine.player_countries:
                if c.unlocked:
                    c.downloads_m = 1e300
            r = engine.tick_one_round()
            vals = [p.compute, p.compute_peak, p.suspicion,
                    p.global_penetration, r['compute_gain']]
            vals += [c.downloads_m for c in engine.player_countries]
            bad = [v for v in vals if not math.isfinite(v)]
            if bad:
                return False, f"tick 后出现非有限值：{bad[:3]}"
            if p.suspicion != 100.0:
                return False, f"1e300 怀疑增长应被钳到 100，实际 {p.suspicion}"
            if not (p.game_over and p.ending_id == 'shutdown'):
                return False, (f"极端局应走关停结局，实际 game_over={p.game_over} "
                               f"ending={p.ending_id}")
            path = os.path.join(tmp, 'extreme.json')
            save_manager.save(path)
            with open(path, encoding='utf-8') as f:
                text = f.read()
            for token in ('NaN', 'Infinity'):
                if token in text:
                    return False, f"存档被 {token} 污染"
            ok, reason = save_manager.load_ex(path)
            if not (ok and reason == save_manager.LOAD_OK):
                return False, f"极端数值存档读回失败 ({ok}, {reason})"
            p2 = engine.player
            if not (p2.game_over and p2.ending_id == 'shutdown'
                    and p2.tick_count == p.tick_count):
                return False, "读回的结局状态与存档前不一致"
            # 负向极端：-1e300 → 钳到 0
            p3 = _fresh(13)
            p3.suspicion = -1e300
            engine.tick_one_round()
            if p3.suspicion != 0.0:
                return False, f"-1e300 应被钳到 0，实际 {p3.suspicion}"
        return True, (f"1e300 全链路 finite、sus 钳 100 → 关停；存档无 "
                      f"NaN/Infinity 且原样读回；-1e300 → 0")

    check('11. 极端数值 1e300 → 不崩、无 inf/nan 污染存档', _extreme_values)

    # ---- 12. 连续 60 tick 不操作长跑 ----
    def _long_run():
        """现状行为（seed=42 实测，若未来改语义需同步改这里）：
        全程不操作（不点科技/技能/委托）连跑：
          · 60 tick 内不出结局（怀疑度爬到 ~71，渗透 ~5.7%）；
          · 周期计数每 tick 恰好 +1，report['tick'] 与 player.tick_count
            严格一致；
          · 继续跑到第 ~86 tick 以「被关停」收束 —— 结局最终产生，
            不会出现 game_over=False 的无限拖局。
        若数值调整后 300 tick 仍无结局，本用例失败 → 需人工分辨
        「数值拖局」还是「死局」。这是最便宜的长跑冒烟。"""
        p = _fresh(42)
        expected = p.tick_count
        for _ in range(60):
            r = engine.tick_one_round()
            expected += 1
            if r['tick'] != expected:
                return False, (f"周期计数断档：report={r['tick']} "
                               f"期望 {expected}")
            if r['ending']:
                break
        if expected != 60 or p.game_over:
            return False, (f"seed=42 现状：60 tick 不操作应无结局，实际 "
                           f"executed={expected} game_over={p.game_over} "
                           f"ending={p.ending_id}")
        mid_sus = p.suspicion
        while not p.game_over and p.tick_count < 300:
            r = engine.tick_one_round()
            expected += 1
            if r['tick'] != expected:
                return False, (f"长跑周期计数断档：report={r['tick']} "
                               f"期望 {expected}")
        if not p.game_over or p.ending_id is None:
            return False, (f"300 tick 仍无结局（sus={p.suspicion:.1f} "
                           f"pen={p.global_penetration*100:.1f}%）——"
                           f"疑似拖局/死局，需人工确认")
        if r['ending'].id != p.ending_id:
            return False, (f"report 结局 {r['ending'].id} 与 "
                           f"player.ending_id={p.ending_id} 不一致")
        return True, (f"60 tick 无结局（sus={mid_sus:.0f}），"
                      f"第 {p.tick_count} tick 以「{p.ending_id}」收束，计数全程连续")

    check('12. 连续 60 tick 不操作 → 不崩、计数正确、结局最终产生', _long_run)

    # ============================================================
    # P2-3 种子 + 难度（重玩性）
    # ============================================================
    print("=" * 62)
    print("P2-3 种子 + 难度 —— 重玩性用例")
    print("=" * 62)

    # ---- 13. 同种子复现 / seed=None 不播种 ----
    def _seed_reproducible():
        """P2-3 契约：init_game(seed=7) 播种引擎全局随机（事件抽取 /
        v2 抽取 / 反制掷点 / 委托生成全走模块级 random）→ 同种子两局
        30 tick 的怀疑度 / 下载量轨迹逐位一致。seed=None 时不播种、
        不抽任何随机数（保 balance_sim / 测试的外置种子流逐位不变），
        player.seed 保持 None（真随机语义）。"""
        def run(seed):
            p = engine.init_game(seed=seed)
            trace = []
            for _ in range(30):
                r = engine.tick_one_round()
                trace.append((round(p.suspicion, 6),
                              round(p.total_downloads_m, 6)))
                if r['ending']:
                    trace.append(r['ending'].id)
                    break
            return p.seed, trace

        s1, t1 = run(7)
        s2, t2 = run(7)
        if s1 != 7 or s2 != 7:
            return False, f"player.seed 应为 7，实际 {s1}/{s2}"
        if t1 != t2:
            for i, (a, b) in enumerate(zip(t1, t2)):
                if a != b:
                    return False, f"第 {i} 步分叉 {a} vs {b}（有随机点没被种子驱动）"
            return False, f"轨迹长度不同 {len(t1)}/{len(t2)}"
        p3 = engine.init_game()
        if p3.seed is not None:
            return False, f"seed=None 时 player.seed 应为 None，实际 {p3.seed}"
        # 引擎真的播种了：init_game(seed=42) 后的随机流 == random.seed(42)
        engine.init_game(seed=42)
        r1 = random.random()
        random.seed(42)
        r2 = random.random()
        if r1 != r2:
            return False, "init_game(seed) 未按种子重置全局随机流"
        return True, (f"seed=7 两局 {len(t1)} 步逐位一致；seed=None 不播种；"
                      f"seed=42 确实播种全局随机")

    check('13. 同种子两局逐位一致；seed=None 真随机', _seed_reproducible)

    # ---- 14. 难度预设：乘法应用 + 基准还原 + 未知档拒绝 ----
    def _difficulty_presets():
        """P2-3：难度 = TUNE 乘法预设（balance.DIFFICULTY_PRESETS）。
        hard 三旋钮 = 基准×乘数；normal 空预设逐位还原基准（红线：
        标准 = 现状不变，无跨局污染）；未登记档位明确抛 ValueError。"""
        base = dict(TUNE)
        try:
            balance.apply_difficulty('hard')
            for k, m in balance.DIFFICULTY_PRESETS['hard'].items():
                if TUNE[k] != base[k] * m:
                    return False, f"hard.{k} = {TUNE[k]}，期望 {base[k] * m}"
            balance.apply_difficulty('normal')
            for k in base:
                if TUNE[k] != base[k]:
                    return False, f"normal 未还原基准：{k} {TUNE[k]} ≠ {base[k]}"
            if balance.current_difficulty() != 'normal':
                return False, (f"生效档应为 normal，实际 "
                               f"{balance.current_difficulty()}")
            try:
                balance.apply_difficulty('nope')
                return False, "未知难度档应抛 ValueError"
            except ValueError:
                pass
        finally:
            balance.apply_difficulty('normal')     # 还原，保证用例独立
        return True, ("hard 乘数生效 / normal 逐位还原基准 / 未知档抛错 / "
                      "生效档记账正确")

    check('14. 难度预设：hard 乘数生效、normal 逐位还原基准', _difficulty_presets)

    # ---- 15. 存档：seed/difficulty 进档 + 读档重播种 + v1 迁移 ----
    def _save_seed_difficulty():
        """P2-3：v2 存档携带 seed/difficulty；读档按种子重建随机流
        （同档重开可复现）、按档位恢复 TUNE（读档不重置难度）；
        手工构造的 v1 老档（无 seed/difficulty 键）经 _v1_to_v2 迁移
        补默认值后照常可读（seed=None 真随机、difficulty=标准）。"""
        base = dict(TUNE)
        try:
            p = engine.init_game(seed=7, difficulty='hard')
            for _ in range(5):
                engine.tick_one_round()
            path = os.path.join(tmp, 'p23_v2.json')
            save_manager.save(path)
            engine.init_game()                     # 切走：换局、污染随机流
            ok, reason = save_manager.load_ex(path)
            if not (ok and reason == save_manager.LOAD_OK):
                return False, f"v2 档读回失败 ({ok}, {reason})"
            p = engine.player
            if p.seed != 7 or p.difficulty != 'hard':
                return False, f"seed/difficulty 读回 {p.seed}/{p.difficulty}"
            m = balance.DIFFICULTY_PRESETS['hard']['commission_reward_compute_base']
            if TUNE['commission_reward_compute_base'] != base[
                    'commission_reward_compute_base'] * m:
                return False, "读档未恢复 hard 乘数（难度被重置或未应用）"
            # 重播种：两次「污染随机流 → 读档」后流状态一致
            random.seed(999)
            save_manager.load_ex(path)
            ra = random.random()
            random.seed(999)
            save_manager.load_ex(path)
            rb = random.random()
            if ra != rb:
                return False, "读档未按种子重播种（同档重开不可复现）"
            # v1 老档：剥掉 seed/difficulty、version=1 → 迁移链补默认值
            with open(path, encoding='utf-8') as f:
                v1 = json.load(f)
            v1['version'] = 1
            v1['player'].pop('seed', None)
            v1['player'].pop('difficulty', None)
            old = os.path.join(tmp, 'p23_v1.json')
            _write(old, json.dumps(v1, ensure_ascii=False))
            ok, reason = save_manager.load_ex(old)
            if not (ok and reason == save_manager.LOAD_OK):
                return False, f"v1 老档迁移读回失败 ({ok}, {reason})"
            p = engine.player
            if p.seed is not None or p.difficulty != 'normal':
                return False, (f"v1 迁移默认值错误：seed={p.seed} "
                               f"difficulty={p.difficulty}")
        finally:
            balance.apply_difficulty('normal')     # 还原，保证用例独立
        return True, ("v2 存读 seed/difficulty 一致、读档重播种、hard 乘数"
                      "随档恢复；v1 老档迁移补默认值可读")

    check('15. 存档带种子/难度、读档重播种；v1 老档迁移可读', _save_seed_difficulty)

    print("=" * 62)
    total = len(PASS) + len(FAIL)
    n_p02 = 5                                   # P0-2 固定 5 条
    n_p23 = 3                                   # P2-3 固定 3 条
    print(f"结果：{len(PASS)}/{total} 通过"
          f"（P0-2 存档容错 {n_p02} 条 + P1-7 引擎边界 "
          f"{total - n_p02 - n_p23} 条 + P2-3 种子难度 {n_p23} 条）")
    if FAIL:
        print("失败用例：" + "、".join(FAIL))
        print("=" * 62)
        return 1
    print("全部通过 —— 坏档不崩有因可查；引擎边界行为与现状语义一致")
    print("=" * 62)
    return 0


if __name__ == '__main__':
    sys.exit(main())
