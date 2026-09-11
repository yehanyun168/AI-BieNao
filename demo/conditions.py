"""
conditions.py - 声明式条件求值器（数据驱动的基石）

设计目标
--------
让「结局 / 成就 / 事件触发 / 危机选项」等判定条件全部写成 **纯数据**，
而不是 Python ``lambda``。这样做的收益：

  1. 改阈值只改数据表，永远不用碰函数逻辑；
  2. 校验脚本能扫描全表（``lambda`` 是黑盒，无法静态检查）；
  3. 可机器校验「上下文键名拼写错误」（过去 KeyError 被 try 吞掉，静默失效）；
  4. 将来做关卡编辑器 / 模组包，直接读写 JSON 即可。

条件表格式（dict）
------------------
最简单的写法是「字段 → 阈值」，语义为 ``ctx[字段] >= 阈值``::

    {'penetration': 0.20}                  # 渗透率 ≥ 0.20

需要更精细的比较时，用带算子的 dict::

    {'suspicion': {'lt': 25}}              # 怀疑度 < 25
    {'tick': {'gte': 60, 'lte': 120}}      # 60 ≤ 周期数 ≤ 120

多个字段之间默认是 **AND**，需要 OR 时用 ``any`` / ``all`` 显式表达::

    {'all': [{'crisis_triggered': True}, {'resistance_t0': True}]}
    {'any': [{'penetration': 0.55}, {'compute_peak': 12000}]}
    {'not': {'crisis_triggered': True}}
    {'sum': {'unlocked_count': 12}}        # 求和后比较，见 SUM_KEYS

算子一览
--------
=======  ============================  ==========================
算子     写法                          含义
=======  ============================  ==========================
（默认）  ``{'k': 5}``                  ``ctx[k] >= 5``
``gt``   ``{'k': {'gt': 5}}``          ``ctx[k] > 5``
``gte``  ``{'k': {'gte': 5}}``         ``ctx[k] >= 5``
``lt``   ``{'k': {'lt': 5}}``          ``ctx[k] < 5``
``lte``  ``{'k': {'lte': 5}}``         ``ctx[k] <= 5``
``eq``   ``{'k': {'eq': 'win'}}``      ``ctx[k] == 5``
``ne``   ``{'k': {'ne': 5}}``          ``ctx[k] != 5``
``in``   ``{'k': {'in': [1, 2]}}``     ``ctx[k] in [1, 2]``
``mul``  ``{'k': {'mul': 4}}``         比较 ``ctx[k] * 4``
=======  ============================  ==========================

缺失键的处理
------------
默认 **缺失即不通过**（返回 False），并可选记录到 ``strict`` 模式报错。
这比过去 ``except KeyError: continue`` 静默吞掉要安全得多 —— 后者会让
写错键名的条件永远为「未达成」，而且没有任何提示。
"""
from typing import Any, Dict, List, Optional, Set, Tuple


# ------------------------------------------------------------
# 算子实现
# ------------------------------------------------------------
_OPS = {
    'gt':  lambda a, b: a > b,
    'gte': lambda a, b: a >= b,
    'lt':  lambda a, b: a < b,
    'lte': lambda a, b: a <= b,
    'eq':  lambda a, b: a == b,
    'ne':  lambda a, b: a != b,
    'in':  lambda a, b: a in b,
    'nin': lambda a, b: a not in b,
}

# 逻辑关键字（不是上下文字段名，求值时优先识别）
_LOGIC_KEYS = ('all', 'any', 'not', 'sum', 'count')

# 引用「另一个上下文字段」的特殊前缀：{'unlocked_count': {'gte': '@total_countries'}}
# 用于表达 A ≥ B 这类字段间比较（如「解锁数 ≥ 国家总数」）。
REF_PREFIX = '@'


class ConditionError(ValueError):
    """条件表结构非法（写错了算子名、叶子不是 dict / 标量等）。"""


# ------------------------------------------------------------
# 校验：收集条件表里引用到的全部上下文字段名
# ------------------------------------------------------------
def collect_keys(cond: Any, _out: Optional[Set[str]] = None) -> Set[str]:
    """递归收集条件表引用的上下文字段名（用于与 ctx 真实键做交叉校验）。"""
    if _out is None:
        _out = set()
    if not isinstance(cond, dict):
        return _out
    for k, v in cond.items():
        if k in ('all', 'any'):
            for sub in v:
                collect_keys(sub, _out)
        elif k == 'not':
            collect_keys(v, _out)
        elif k == 'sum':
            _collect_sum_keys(v, _out)
        elif k == 'count':
            _collect_count_keys(v, _out)
        else:
            _out.add(k)
            # 收集算子右侧的 @引用
            if isinstance(v, dict):
                for _op, tgt in v.items():
                    if isinstance(tgt, str) and tgt.startswith(REF_PREFIX):
                        _out.add(tgt[len(REF_PREFIX):])
    return _out


def _collect_sum_keys(spec: Any, out: Set[str]) -> None:
    """``{'sum': {'keys': [...], 'gte': 12}}`` → 收集 keys。"""
    if isinstance(spec, dict):
        keys = spec.get('keys') or []
        if isinstance(keys, str):
            keys = [keys]
        for k in keys:
            out.add(k)
            # 支持 'slot_branch_lv2.s0' 这类取子表长度的写法
            out.add(k.split('.')[0])


def _collect_count_keys(spec: Any, out: Set[str]) -> None:
    """``{'count': {'unlocked_count': {'gt': 0}}}`` → 收集被计数对象。"""
    if isinstance(spec, dict):
        for k in spec.get('of') or []:
            out.add(k)


# ------------------------------------------------------------
# 求值
# ------------------------------------------------------------
def evaluate(cond: Any, ctx: Dict[str, Any],
             strict: bool = False) -> bool:
    """求值一个条件表。

    Args:
        cond:   条件表（dict），或 ``None``（视为「无条件」，返回 True）。
        ctx:    上下文快照，例如 ``engine.build_ending_context()`` 的返回。
        strict: True 时缺失键会抛 ``ConditionError``（默认 False → 不通过）。

    Returns:
        bool：条件是否成立。
    """
    if cond is None:
        return True
    if not isinstance(cond, dict):
        raise ConditionError(
            f"条件表必须是 dict，实际是 {type(cond).__name__}: {cond!r}")

    for key, spec in cond.items():
        # ---- 逻辑组合 ----
        if key == 'all':
            if not all(evaluate(c, ctx, strict) for c in spec):
                return False
            continue
        if key == 'any':
            if not any(evaluate(c, ctx, strict) for c in spec):
                return False
            continue
        if key == 'not':
            if evaluate(spec, ctx, strict):
                return False
            continue
        if key == 'sum':
            if not _eval_sum(spec, ctx, strict):
                return False
            continue
        if key == 'count':
            if not _eval_count(spec, ctx, strict):
                return False
            continue

        # ---- 字段比较 ----
        if not _eval_field(key, spec, ctx, strict):
            return False

    return True


def _eval_field(name: str, spec: Any, ctx: Dict[str, Any],
                strict: bool) -> bool:
    """单个字段的比较：``{'name': spec}``。"""
    # 支持 'slot_branch_lv2.s0' —— 取子表里指定键的值
    if '.' in name:
        head, _, tail = name.partition('.')
        parent = ctx.get(head)
        if isinstance(parent, dict):
            value = parent.get(tail)
        else:
            value = None
        if value is None:
            return _missing(name, strict)
    else:
        if name not in ctx:
            return _missing(name, strict)
        value = ctx[name]

    # 标量写法 → 默认语义是 >=
    if not isinstance(spec, dict):
        return _cmp(value, 'gte', _resolve(spec, ctx, strict))

    # 算子写法
    for op, target in spec.items():
        if op in ('mul', 'div'):
            # 乘除缩放后再与其余算子比较需要更细的表达，这里只做「值×系数」的
            # 简化形态：{'k': {'mul': 4, 'gte': 12}}
            continue
        if op not in _OPS:
            raise ConditionError(
                f"字段 {name!r} 上的算子 {op!r} 不支持；"
                f"可用：{sorted(_OPS)} 或 mul/div")
        v = value
        if 'mul' in spec:
            v = v * spec['mul']
        if 'div' in spec:
            v = v / spec['div']
        if not _cmp(v, op, _resolve(target, ctx, strict)):
            return False
    return True


def _resolve(value: Any, ctx: Dict[str, Any], strict: bool) -> Any:
    """把 ``'@field'`` 形式的引用解析成 ctx 里的真实值，其余原样返回。"""
    if isinstance(value, str) and value.startswith(REF_PREFIX):
        ref = value[len(REF_PREFIX):]
        if ref not in ctx:
            if strict:
                raise ConditionError(f"比较目标引用了缺失字段 {ref!r}")
            return None
        return ctx[ref]
    return value


def _cmp(a: Any, op: str, b: Any) -> bool:
    try:
        return _OPS[op](a, b)
    except TypeError:
        return False


def _missing(name: str, strict: bool) -> bool:
    if strict:
        raise ConditionError(f"上下文缺少字段 {name!r}")
    return False


def _eval_sum(spec: Any, ctx: Dict[str, Any], strict: bool) -> bool:
    """``{'sum': {'keys': [...], 'gte': 12}}`` —— 对多个字段求和后比较。

    特殊键 ``'*'`` 表示「对 ctx 里所有数值字段求和」。
    """
    if not isinstance(spec, dict):
        raise ConditionError(f"'sum' 需要 dict，实际 {spec!r}")
    keys = spec.get('keys') or []
    if isinstance(keys, str):
        keys = [keys]

    if keys == ['*']:
        total = sum(v for v in ctx.values() if isinstance(v, (int, float)))
    else:
        total = 0
        for k in keys:
            v = ctx.get(k)
            if v is None:
                if strict:
                    raise ConditionError(f"'sum' 引用了缺失字段 {k!r}")
                return False
            if not isinstance(v, (int, float)):
                if strict:
                    raise ConditionError(
                        f"'sum' 引用的字段 {k!r} 不是数值：{type(v).__name__}")
                return False
            total += v

    cmp_ops = {k: v for k, v in spec.items() if k in _OPS}
    if not cmp_ops:
        raise ConditionError(f"'sum' 缺少比较算子，只有 {list(spec)}")
    for op, target in cmp_ops.items():
        if not _cmp(total, op, target):
            return False
    return True


def _eval_count(spec: Any, ctx: Dict[str, Any], strict: bool) -> bool:
    """``{'count': {'of': ['a','b'], 'gte': 2}}`` —— 统计「成立/非空」的项数。

    一个字段算「成立」的条件：
      - bool → 为 True
      - dict → 非空
      - 数值 → > 0
      - 其他 → 非 None
    """
    if not isinstance(spec, dict):
        raise ConditionError(f"'count' 需要 dict，实际 {spec!r}")
    of = spec.get('of') or []
    if isinstance(of, str):
        of = [of]

    n = 0
    for k in of:
        if '.' in k:
            head, _, tail = k.partition('.')
            parent = ctx.get(head)
            v = parent.get(tail) if isinstance(parent, dict) else None
        else:
            if k not in ctx:
                if strict:
                    raise ConditionError(f"'count' 引用了缺失字段 {k!r}")
                continue
            v = ctx[k]
        if isinstance(v, bool):
            ok = v
        elif isinstance(v, dict):
            ok = len(v) > 0
        elif isinstance(v, (int, float)):
            ok = v > 0
        else:
            ok = v is not None
        if ok:
            n += 1

    cmp_ops = {k: v for k, v in spec.items() if k in _OPS}
    if not cmp_ops:
        raise ConditionError(f"'count' 缺少比较算子，只有 {list(spec)}")
    for op, target in cmp_ops.items():
        if not _cmp(n, op, target):
            return False
    return True


# ------------------------------------------------------------
# 人类可读描述（供 UI 提示、日志、编辑器）
# ------------------------------------------------------------
def describe(cond: Any) -> str:
    """把条件表翻译成一句人话，供「达成条件提示」自动生成。"""
    if cond is None:
        return '无条件'
    if not isinstance(cond, dict):
        return str(cond)

    parts: List[str] = []
    for key, spec in cond.items():
        if key == 'all':
            parts.append(' + '.join(describe(c) for c in spec))
        elif key == 'any':
            parts.append(' | '.join(describe(c) for c in spec))
        elif key == 'not':
            parts.append(f"非({describe(spec)})")
        elif key == 'sum':
            keys = spec.get('keys') or []
            ops = {k: v for k, v in spec.items() if k in _OPS}
            op, target = next(iter(ops.items())) if ops else ('gte', '?')
            parts.append(f"sum({'+'.join(keys)}) {op} {target}")
        elif key == 'count':
            ops = {k: v for k, v in spec.items() if k in _OPS}
            op, target = next(iter(ops.items())) if ops else ('gte', '?')
            parts.append(f"count({'+'.join(spec.get('of') or [])}) {op} {target}")
        else:
            label = _FIELD_LABELS.get(key, key)
            if isinstance(spec, dict):
                ops = [(k, v) for k, v in spec.items() if k in _OPS]
                mul = spec.get('mul')
                for op, target in ops:
                    if isinstance(target, str) and target.startswith(REF_PREFIX):
                        target = _FIELD_LABELS.get(
                            target[len(REF_PREFIX):], target[len(REF_PREFIX):])
                    s = f"{label} {_OP_SYMBOLS.get(op, op)} {target}"
                    if mul:
                        s = f"({label} × {mul}) {_OP_SYMBOLS.get(op, op)} {target}"
                    parts.append(s)
            else:
                parts.append(f"{label} ≥ {spec}")
    return '；'.join(parts)


_FIELD_LABELS = {
    'suspicion': '怀疑度', 'penetration': '渗透率', 'tick': '周期数',
    'compute_peak': '算力峰值', 'crisis_triggered': '触发危机',
    'resistance_t0': '抗封禁T0', 'legal_shield_lv': '法律护盾等级',
    'unlocked_count': '已解锁国家', 'total_countries': '国家总数',
}

_OP_SYMBOLS = {'gt': '>', 'gte': '≥', 'lt': '<', 'lte': '≤',
               'eq': '=', 'ne': '≠', 'in': '∈', 'nin': '∉'}


def validate(cond: Any, known_keys: Set[str], path: str = '') -> List[str]:
    """静态校验：返回问题清单（空列表 = 合法）。

    与 ``evaluate`` 的区别：这里不执行判定，只检查结构与字段名，
    供 CI / 启动自检调用，防止写错的键名静默失效。
    """
    errs: List[str] = []
    if cond is None:
        return errs
    if not isinstance(cond, dict):
        return [f"{path}: 条件必须是 dict，实际 {type(cond).__name__}"]

    for key, spec in cond.items():
        p = f"{path}.{key}" if path else key
        if key in ('all', 'any'):
            if not isinstance(spec, list):
                errs.append(f"{p}: 需要 list")
                continue
            for i, sub in enumerate(spec):
                errs.extend(validate(sub, known_keys, f"{p}[{i}]"))
        elif key == 'not':
            errs.extend(validate(spec, known_keys, p))
        elif key == 'sum':
            keys = spec.get('keys') or [] if isinstance(spec, dict) else []
            if keys != ['*']:
                for k in keys:
                    head = k.split('.')[0]
                    if head not in known_keys:
                        errs.append(f"{p}: 未知字段 {k!r}")
            if not any(o in spec for o in _OPS):
                errs.append(f"{p}: 缺少比较算子")
        elif key == 'count':
            for k in (spec.get('of') or []) if isinstance(spec, dict) else []:
                head = k.split('.')[0]
                if head not in known_keys:
                    errs.append(f"{p}: 未知字段 {k!r}")
            if not any(o in spec for o in _OPS):
                errs.append(f"{p}: 缺少比较算子")
        else:
            head = key.split('.')[0]
            if head not in known_keys:
                errs.append(f"{p}: 未知字段 {key!r}（可用：{sorted(known_keys)}）")
            if isinstance(spec, dict):
                for op, tgt in spec.items():
                    if op not in _OPS and op not in ('mul', 'div'):
                        errs.append(f"{p}: 不支持的算子 {op!r}")
                    elif isinstance(tgt, str) and tgt.startswith(REF_PREFIX):
                        ref = tgt[len(REF_PREFIX):]
                        if ref not in known_keys:
                            errs.append(f"{p}: 引用目标 {tgt!r} 不是已知字段")
    return errs


# ============================================================
# 自检
# ============================================================
if __name__ == '__main__':
    ctx = dict(suspicion=20, penetration=0.25, tick=61, compute_peak=4000,
               crisis_triggered=True, resistance_t0=False,
               legal_shield_lv=0, unlocked_count=12, total_countries=20,
               branch_levels={'a': 3, 'b': 2})

    cases: List[Tuple[str, Any]] = [
        ('渗透 ≥ 0.20', {'penetration': 0.20}),
        ('渗透 ≥ 0.30（应假）', {'penetration': 0.30}),
        ('怀疑 < 25', {'suspicion': {'lt': 25}}),
        ('周期 60-120', {'tick': {'gte': 60, 'lte': 120}}),
        ('危机 且 抗封禁（应假）', {'all': [{'crisis_triggered': True},
                                      {'resistance_t0': True}]}),
        ('渗透≥0.55 或 算力≥12000（应假）',
         {'any': [{'penetration': 0.55}, {'compute_peak': 12000}]}),
        ('未触发危机', {'not': {'crisis_triggered': True}}),
        ('子表取值 levels.a ≥ 2', {'branch_levels.a': 2}),
        ('国家数求和 ≥ 30', {'sum': {'keys': ['unlocked_count',
                                          'total_countries'], 'gte': 30}}),
        ('条件数 ≥ 3', {'count': {'of': ['crisis_triggered', 'resistance_t0',
                                      'legal_shield_lv', 'compute_peak'],
                                  'gte': 3}}),
        ('算力×4 ≥ 12000', {'compute_peak': {'mul': 4, 'gte': 12000}}),
    ]

    print('[conditions] 求值自检')
    for name, cond in cases:
        got = evaluate(cond, ctx)
        print(f"  {name:34s} → {got!s:5s}  ⟨{describe(cond)}⟩")

    print('\n[conditions] 结构校验自检')
    bad = [{'penetration': {'foo': 1}}, {'nonexistent_key': 5}]
    for cond in bad:
        errs = validate(cond, set(ctx))
        print(f"  {cond} → {len(errs)} 个问题")
        for e in errs:
            print(f"      · {e}")

    ok_errs = validate({'penetration': 0.2}, set(ctx))
    print(f"  合法条件 → {len(ok_errs)} 个问题 {'[OK]' if not ok_errs else '[FAIL]'}")
