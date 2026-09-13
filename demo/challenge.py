"""
challenge.py - T13 挑战码（种子分享）编解码 + 本地战绩记录

职责单一：把 (seed, difficulty) 编成一段人类可粘贴的短文本码，并能反向解析；
再配套一份本地战绩账（challenge_log.json），让同一个码反复挑战时能对照成绩。

分层：L0 纯逻辑，零项目依赖（只用标准库）。战绩文件所在目录由调用方传入
（唯一真相源是 save_manager.SAVE_DIR），故本模块刻意不 import save_manager，
避免反向依赖，也便于单元测试用临时目录。

码格式（16 字符）：``AINB-XXXX-XXXX-X``
  · 前 7 位   seed（Base32，5 bit/位 → 支持 0 ~ 2^35-1，覆盖文字口令哈希的 32 bit）
  · 第 8 位   校验位（前 7 位 seed + 难度字符的字母表序号和 mod 32）
  · 第 9 位   难度（E / N / H）
  · 字母表剔除了 0/O/1/I 四个易混字符；解析时大小写、分隔符、前缀全部容错。

为什么不直接用「种子数字 + 难度」明文：明文无法察觉粘贴截断/漏字，
而校验位让一次误粘贴立刻显示为「码无效」，而不是静默开出一局错的种子。
"""
import json
import os
import tempfile

# ---- 字母表：32 字符，去掉 0/O/1/I（手抄与截图识别最容易混淆的四个）----
ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
assert len(ALPHABET) == 32, "挑战码字母表必须是 32 字符"

PREFIX = 'AINB'
SEED_DIGITS = 7                      # 7 × 5 bit = 35 bit 种子空间
SEED_MAX = 1 << (SEED_DIGITS * 5)    # 2^35

# 难度字符与 balance.DIFFICULTY_ORDER 的对应（此处硬编码以保持 L0 零依赖；
# 若难度档增删，test_build 的 check 21 会因往返失败而报警）
DIFF_CODE = {'easy': 'E', 'normal': 'N', 'hard': 'H'}
CODE_DIFF = {v: k for k, v in DIFF_CODE.items()}

LOG_NAME = 'challenge_log.json'
LOG_MAX = 80          # 最多保留 80 个码的战绩，防止账本无限膨胀
LOG_KEEP_RUNS = 5     # 每个码只留最近 5 局明细


# ============================================================
# 编解码
# ============================================================
def _checksum(body: str) -> str:
    """校验位 = 有效字符的字母表序号之和 mod 32。

    刻意取最简单的加权和无——目标是抓「漏抄/错位/贴了一半」这类
    粗错，不是防伪造（本地游戏的成绩账本没有防伪价值）。
    """
    return ALPHABET[sum(ALPHABET.index(c) for c in body) % 32]


def encode(seed, difficulty: str):
    """(seed, difficulty) → 挑战码；不可编码时返回 None。

    返回 None 的三种情况：seed 为空（真随机局无法复现）、seed 越界
    （≥ 2^35，玩家手填的巨型数字）、难度 id 不认识。
    """
    if seed is None:
        return None
    try:
        seed = int(seed)
        difficulty = str(difficulty)
    except (TypeError, ValueError):
        return None
    if not (0 <= seed < SEED_MAX):
        return None
    d = DIFF_CODE.get(difficulty)
    if d is None:
        return None
    body = []
    v = seed
    for _ in range(SEED_DIGITS):
        body.append(ALPHABET[v & 31])
        v >>= 5
    body.reverse()
    seed_part = ''.join(body)
    chk = _checksum(seed_part + d)
    raw = seed_part + chk
    return f"{PREFIX}-{raw[:4]}-{raw[4:]}-{d}"


def decode(text: str):
    """挑战码 → (seed, difficulty)；无效返回 None。

    容错范围：大小写无关、``-``/空格任意、可省略 ``AINB`` 前缀、
    允许从一整段文字里链出码（其余字符被忽略）。
    """
    if not text:
        return None
    s = str(text).strip().upper()
    # ⚠️ 必须「先剥前缀再过滤字母表」：前缀 AINB 含 I，而 I 不在字母表里，
    # 一旦先过滤就会把前缀打成 ANB，前缀信息丢失后无法再剥。
    # 反过来不可能误伤码体 —— 码体取自字母表，天然不含 I，拼不出 'AINB'。
    if PREFIX in s:
        s = s.replace(PREFIX, '')
    s = ''.join(c for c in s if c in ALPHABET)
    if len(s) != SEED_DIGITS + 2:          # 7 seed + 1 校验 + 1 难度
        return None
    seed_part, chk, d = s[:SEED_DIGITS], s[SEED_DIGITS], s[SEED_DIGITS + 1]
    if _checksum(seed_part + d) != chk:
        return None
    diff = CODE_DIFF.get(d)
    if diff is None:
        return None
    seed = 0
    for c in seed_part:
        seed = (seed << 5) | ALPHABET.index(c)
    return seed, diff


def looks_like_code(text: str) -> bool:
    """是否是「长得像挑战码」的输入（用于 UI 分流，不要求码本身合法）。

    比 decode 宽松：只要剥掉前缀与分隔符后剩 9 个字母表字符就算。
    这样玩家贴了个校验位写错的码时，UI 提示的是「码无效」而非
    「当作种子的文字」——错误信息才对得上玩家的意图。
    """
    if not text:
        return False
    s = str(text).strip().upper()
    if PREFIX in s:
        return True
    s = ''.join(c for c in s if c in ALPHABET)
    return len(s) == SEED_DIGITS + 2


def format_for_display(code: str) -> str:
    """统一显示形态（大写）；供 UI 直接渲染，避免各处自行 upper()。"""
    return (code or '').strip().upper()


# ============================================================
# 战绩账本
# ============================================================
def log_path(dir_path: str) -> str:
    return os.path.join(dir_path, LOG_NAME)


def load_log(dir_path: str) -> dict:
    """读账本；文件缺失或损坏一律回空账（战绩是锦上添花，绝不因此崩游戏）。"""
    try:
        with open(log_path(dir_path), 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_log(dir_path: str, data: dict) -> None:
    """原子写（.tmp → fsync → os.replace），与存档同一套路，避免半截文件。"""
    path = log_path(dir_path)
    try:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.',
                                   prefix='.chlog_', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        pass          # 落盘失败只丢本次战绩，不影响对局


def run_rank(summary: dict) -> tuple:
    """成绩排序键：先看结局档位（win > neutral > lose），再比全球渗透率。

    只比渗透率会把「顶满怀疑被关停」的高渗透误判成最佳——所以结局
    档位必须排在渗透率前面。第 3 位用周期数做稳定 tiebreak（越快越好）。
    """
    kind = (summary or {}).get('kind') or 'neutral'
    rank = {'win': 2, 'neutral': 1, 'lose': 0}.get(kind, 1)
    try:
        pen = float((summary or {}).get('pen') or 0.0)
    except (TypeError, ValueError):
        pen = 0.0
    try:
        ticks = int((summary or {}).get('ticks') or 0)
    except (TypeError, ValueError):
        ticks = 0
    return (rank, pen, -ticks)


def record(dir_path: str, code: str, seed, difficulty: str,
           summary: dict) -> dict:
    """登记一局成绩，返回该码更新后的条目（含 plays / best / last）。"""
    code = format_for_display(code)
    if not code:
        return {}
    data = load_log(dir_path)
    entry = data.get(code)
    if not isinstance(entry, dict):
        entry = {'plays': 0, 'seed': seed, 'difficulty': difficulty,
                 'best': None, 'last': None, 'runs': []}
    entry['plays'] = int(entry.get('plays') or 0) + 1
    entry['seed'] = seed
    entry['difficulty'] = difficulty
    entry['last'] = summary
    runs = entry.get('runs')
    if not isinstance(runs, list):
        runs = []
    runs.append(summary)
    entry['runs'] = runs[-LOG_KEEP_RUNS:]
    if entry.get('best') is None or \
            run_rank(summary) > run_rank(entry['best']):
        entry['best'] = summary
    data[code] = entry
    if len(data) > LOG_MAX:                 # 账本裁剪：丢最早写入的条目
        for stale in list(data.keys())[:-LOG_MAX]:
            data.pop(stale, None)
    _save_log(dir_path, data)
    return entry


def compare(entry_before: dict, summary: dict) -> dict:
    """本次成绩 vs 该码历史最佳，产出 UI 直接可用的对照数值。

    !️ 必须传入 **登记本局之前** 的条目（即 ``record()`` 的前一次返回），
    否则 best 已把本局算进去，对照会永远显示「打平」。

    返回 ``{'plays', 'is_first', 'is_best', 'best', 'd_pen', 'd_dl'}``；
    ``plays`` 是含本局的总局数，``d_*`` 为「本次 − 最佳」的有符号差值
    （正 = 本次更好）。
    """
    out = {'plays': 1, 'is_first': True, 'is_best': True,
           'best': None, 'd_pen': None, 'd_dl': None}
    if not isinstance(entry_before, dict):
        return out
    prev_plays = int(entry_before.get('plays') or 0)
    out['plays'] = prev_plays + 1
    out['is_first'] = prev_plays <= 0
    best = entry_before.get('best')
    out['best'] = best if isinstance(best, dict) else None
    out['is_best'] = out['is_first'] or not isinstance(best, dict) or \
        run_rank(summary) > run_rank(best)

    def _num(d, k):
        try:
            return float((d or {}).get(k))
        except (TypeError, ValueError):
            return None

    cur_pen, best_pen = _num(summary, 'pen'), _num(best, 'pen')
    if cur_pen is not None and best_pen is not None:
        out['d_pen'] = cur_pen - best_pen
    cur_dl, best_dl = _num(summary, 'dl_m'), _num(best, 'dl_m')
    if cur_dl is not None and best_dl is not None:
        out['d_dl'] = cur_dl - best_dl
    return out


def summarize(player, ending_id: str = None, kind: str = None) -> dict:
    """从 PlayerState 抽一局成绩摘要（UI 层调用后交给 record）。

    只取「可跨局比较」的字段，不含渠道/科技等本局内部状态。
    ``kind`` 是结局档位（win/neutral/lose），必须由 UI 层从 endings
    表取出后传入 —— 本模块是 L0，不能 import endings(L2)。
    """
    def _f(name, default=0.0):
        try:
            return float(getattr(player, name, default))
        except (TypeError, ValueError):
            return default

    return {
        'ending': getattr(player, 'ending', None) or ending_id,
        'kind': kind or 'neutral',
        'pen': _f('global_penetration'),
        'dl_m': _f('total_downloads_m'),
        'ticks': int(getattr(player, 'tick_count', 0) or 0),
        'crisis': bool(getattr(player, 'crisis_triggered', False)),
    }
