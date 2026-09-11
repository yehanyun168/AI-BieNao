"""test_edge_cases.py - 边界用例（P0-2 存档读取全链路容错）

运行（必须从 demo/ 目录）：
    KIVY_NO_FILELOG=1 python test_edge_cases.py

覆盖：
  1. 乱码 JSON        → 不崩，返回 LOAD_CORRUPT
  2. {'version': 1}   → 缺 player 键，不崩，返回 LOAD_BAD_SCHEMA
  3. {'version': 999} → 版本不符，返回 LOAD_BAD_VERSION（不是裸 False）
  4. 正常存档          → 回归保护：仍能正常读出

后续 P1-7 的边界用例也往这里加，保持一个入口。
"""
import json
import os
import sys
import tempfile

import engine
import save_manager

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

    print("=" * 62)
    total = len(PASS) + len(FAIL)
    print(f"结果：{len(PASS)}/{total} 通过")
    if FAIL:
        print("失败用例：" + "、".join(FAIL))
        print("=" * 62)
        return 1
    print("全部通过 —— 任何坏档都不崩、都有明确原因、都落日志")
    print("=" * 62)
    return 0


if __name__ == '__main__':
    sys.exit(main())
