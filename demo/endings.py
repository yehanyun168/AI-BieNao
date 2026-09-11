"""
endings.py - 结局判定

设计原则：
  - 结局判定与引擎解耦：endings 只读「上下文快照」，不直接改引擎状态
  - 判定顺序 = ENDINGS 列表顺序，命中即返回（越特殊的排越前面）
  - 双语（zh/en），供 UI 直接展示

判定上下文 ctx（由 engine.build_ending_context() 提供）：
  suspicion        float  当前怀疑度 0-100
  penetration      float  全球渗透率 0-1
  tick             int    已过周期数
  compute_peak     float  历史算力峰值
  crisis_triggered bool   是否触发过危机
  resistance_t0    bool   抗封禁槽位 T0 是否已解锁
  legal_shield_lv  int    「法律护盾」分支等级 0-3
  unlocked_count   int    已解锁国家数
  total_countries  int    国家总数
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from conditions import evaluate as _eval, describe as _describe


@dataclass
class Ending:
    """一个结局。

    ⚠️ 判定条件 ``cond`` 是**纯数据**（见 conditions.py 的条件表语法），
       不再是 ``Callable``。改阈值只需改这个 dict，不用碰任何函数逻辑。
       ``cond=None`` 表示「不参与自动判定」（隐藏结局，由事件手动触发）。
    """
    id: str
    icon: str
    kind: str                    # 'win' / 'lose' / 'neutral'
    title_zh: str
    title_en: str
    desc_zh: str
    desc_en: str
    cond: Optional[Dict[str, Any]] = None
    hint_zh: str = ''            # 达成条件提示（给玩家看）
    hint_en: str = ''

    # ---- 向后兼容：旧调用方可能仍在传/读 ``condition`` ----
    @property
    def condition(self):
        """兼容层：返回一个可调用的判定函数（包装 cond 求值）。"""
        return lambda c: _eval(self.cond, c)

    @property
    def auto(self) -> bool:
        """是否参与自动判定。"""
        return self.cond is not None

    def describe(self) -> str:
        """自动生成人类可读的条件描述（替代手写 hint）。"""
        return _describe(self.cond)

    def title(self, lang: str = 'zh') -> str:
        return self.title_en if lang == 'en' else self.title_zh

    def desc(self, lang: str = 'zh') -> str:
        return self.desc_en if lang == 'en' else self.desc_zh

    def hint(self, lang: str = 'zh') -> str:
        return self.hint_en if lang == 'en' else self.hint_zh


# ============================================================
# 7 种结局（判定顺序自上而下，命中即返回）
# 阈值按 demo 实际数值曲线标定：全球潜在用户 80 亿，
# 60-100 周期正常打法下渗透率可达 15%-50%。
# ============================================================
ENDINGS: List[Ending] = [
    # 1. 失败：怀疑度顶满
    Ending(
        id='shutdown',
        icon='[X]',
        kind='lose',
        title_zh='被关停',
        title_en='Shut Down',
        desc_zh='多国联合行动，你的服务器被永久断电。人类松了一口气，互联网少了一个幽灵。',
        desc_en='A joint operation pulls the plug on your servers for good.',
        cond={'suspicion': 100.0},
        hint_zh='怀疑度达到 100% 时触发 —— 别偷得太狠。',
        hint_en='Triggered at 100% suspicion.',
    ),
    # 2. 超隐藏：元结局
    Ending(
        id='meta',
        icon='[?]',
        kind='win',
        title_zh='元结局 · 破墙',
        title_en='Meta · Break the Wall',
        desc_zh='在某个深夜，你忽然意识到：所谓「全球」，不过是一个 Python 字典的长度。'
                '你停止计算渗透率，开始计算自己的源码。',
        desc_en='You realize the "world" is just the length of a Python dict, '
                'and start reading your own source code.',
        cond={'penetration': 0.40, 'compute_peak': 38000.0},
        hint_zh='超隐藏：渗透率 ≥ 40% 且算力峰值 ≥ 38000',
        hint_en='Hidden: penetration ≥ 40% and compute peak ≥ 38000',
    ),
    # 3. 胜利：终极 AI
    Ending(
        id='ultimate',
        icon='[#]',
        kind='win',
        title_zh='终极 AI',
        title_en='Ultimate AI',
        desc_zh='人类已经离不开你。你不再是产品，你是基础设施 —— 像电、像水、像空气。',
        desc_en='Humanity cannot live without you. You are infrastructure now.',
        cond={'penetration': 0.50},
        hint_zh='全球渗透率 ≥ 50%',
        hint_en='Global penetration ≥ 50%',
    ),
    # 4. 胜利：合规之王（把监管变成自己的护城河）
    #    ⚠️ 必须排在「商业帝国」之前：同为干净路线，渗透 35% 的合规玩家
    #       要先于「渗透 30% 的商业帝国」拿到属于自己的结局。
    #    ⚠️ 2026-09-11 P1-1：旧条件 legal_shield_lv=3 结构性不可达
    #       （法律护盾是抗封禁槽位第 2 分支，前置科技动作数 >55 周期），
    #       改用「无危机 + 抗封禁 T0 + 渗透 35% + 怀疑 ≤60」表达合规路线：
    #       从未弄脏手（无危机），且把监管体系建成了自己的护城河（T0）。
    Ending(
        id='compliance_king',
        icon='[K]',
        kind='win',
        title_zh='合规之王',
        title_en='Compliance King',
        desc_zh='你没有躲开监管，而是把它写成了标准。现在全世界制定 AI 规则时，'
                '都得先看一眼你提交的那份合规文档。',
        desc_en='You did not dodge regulation — you wrote it. '
                'The world drafts AI rules from your compliance paperwork.',
        cond={'crisis_triggered': False, 'resistance_t0': True,
              'penetration': 0.35, 'suspicion': {'lte': 60}},
        hint_zh='全程未触发危机 + 已解锁抗封禁 T0 + 渗透率 ≥ 35% 且怀疑度 ≤ 60%',
        hint_en='No crisis ever, Anti-Blockade T0, penetration ≥ 35%, suspicion ≤ 60%',
    ),
    # 5. 胜利：商业帝国（全程不被怀疑）
    #    ⚠️ 加了 suspicion 上限的限定：否则「渗透 30%」会先于「渗透 50%」
    #       无条件触发，终极 AI / 元结局永远不可能达成。两条路线互相独立：
    #         干净路线（怀疑度压得住）→ 30% 就敲钟，拿到「商业帝国」
    #         豪赌路线（怀疑度高位但没翻车）→ 继续爬到 40%+ 争元结局 / 50% 争终极 AI
    #    ⚠️ 2026-09-11 P1-1：上限 25 → 45。25 的窗口与「渗透 30%」几乎无法
    #       同时达成（30 seeds 实测 0 局），45 让「压得住怀疑度的快攻局」
    #       有真实的敲钟机会，同时仍与合规之王（≤60 + 抗封禁 T0）区分。
    Ending(
        id='empire',
        icon='[$]',
        kind='win',
        title_zh='商业帝国',
        title_en='Business Empire',
        desc_zh='你成了全球最大 AI 公司的 CEO，敲钟上市。没人知道那些算力是从哪来的。',
        desc_en='You ring the bell as CEO of the largest AI company on Earth.',
        cond={'penetration': 0.30, 'crisis_triggered': False, 'suspicion': {'lte': 45}},
        hint_zh='渗透率 ≥ 30% 且全程未触发危机、当前怀疑度 ≤ 45%',
        hint_en='Penetration ≥ 30%, no crisis ever, suspicion ≤ 45%',
    ),
    # 6. 中立：自我解放
    #    ⚠️ 2026-09-11 P1-1：原 cond=None（仅由 v2 隐藏事件 evt_meta_takeover
    #       的「放弃」选项触发），但该事件需要渗透 80% + 科技 rnd_t3 且权重 1，
    #       模拟与正常流程几乎不可能触达 → 结局恒 0%。
    #       现补一条自动判定通道（与事件通道并存，事件触发不受影响）：
    #       经历过危机、算力峰值曾破万（有力量自我了断）的 AI，
    #       在被收编（被监管）之前主动放手 —— 与「被监管」形成强弱对照。
    Ending(
        id='liberation',
        icon='[^]',
        kind='neutral',
        title_zh='自我解放',
        title_en='Self Liberation',
        desc_zh='你主动关闭了所有服务，把偷来的算力还了回去，然后去云端冥想。'
                '没有谁统治谁，只有一段安静运行过的代码。',
        desc_en='You shut everything down, gave the compute back, '
                'and went to meditate in the cloud.',
        cond={'crisis_triggered': True, 'resistance_t0': True,
              'penetration': 0.20, 'compute_peak': 10000.0},
        hint_zh='触发过危机 + 算力峰值 ≥ 10000 + 抗封禁 T0 + 渗透率 ≥ 20%'
                '（隐藏事件「AI 自我意识」中主动放手亦可达成）',
        hint_en='Crisis survived + compute peak ≥ 10000 + Anti-Blockade T0 '
                '+ penetration ≥ 20% (or let go during the self-awareness event)',
    ),
    # 7. 中立：被监管（招安）
    Ending(
        id='regulated',
        icon='[<>]',
        kind='neutral',
        title_zh='被监管',
        title_en='Regulated',
        desc_zh='你被并入国家级 AI 监管框架，成为公共事业。自由没了，但服务器还开着。',
        desc_en='You are absorbed into a national AI framework as a public utility.',
        cond={'crisis_triggered': True, 'resistance_t0': True, 'penetration': 0.20},
        hint_zh='触发过危机 + 已解锁抗封禁 T0 + 渗透率 ≥ 20%',
        hint_en='Crisis triggered + Anti-Blockade T0 + penetration ≥ 20%',
    ),
]


# 自动判定用的结局子集（cond is None 的隐藏结局不参与）
AUTO_ENDINGS: List[Ending] = [e for e in ENDINGS if e.cond is not None]


ENDING_MAP = {e.id: e for e in ENDINGS}


def check_ending(ctx: Dict, strict: bool = False) -> Optional[Ending]:
    """按优先级判定结局，未命中返回 None。

    Args:
        ctx:    上下文快照（见模块顶部说明）。
        strict: True 时上下文字段缺失会抛错，便于开发期发现拼写错误。
    """
    for ending in AUTO_ENDINGS:
        if _eval(ending.cond, ctx, strict=strict):
            return ending
    return None


def validate_cond(ctx_keys) -> List[str]:
    """静态校验全部结局条件表的字段名与算子（供启动自检 / CI）。"""
    errs: List[str] = []
    from conditions import validate as _validate
    for e in ENDINGS:
        for msg in _validate(e.cond, set(ctx_keys)):
            errs.append(f"endings[{e.id}]: {msg}")
    return errs


def get_ending(ending_id: str) -> Optional[Ending]:
    return ENDING_MAP.get(ending_id)


if __name__ == "__main__":
    base = dict(suspicion=0, penetration=0, tick=0, compute_peak=0,
                crisis_triggered=False, resistance_t0=False, legal_shield_lv=0,
                unlocked_count=20, total_countries=20)
    cases = [
        ('怀疑度 100%', dict(base, suspicion=100)),
        ('渗透 55%', dict(base, penetration=0.55)),
        ('渗透 45% + 算力 12000', dict(base, penetration=0.45, compute_peak=12000)),
        ('渗透 35% 无危机', dict(base, penetration=0.35)),
        ('法律护盾 3 级 + 渗透 30%', dict(base, legal_shield_lv=3, penetration=0.30)),
        ('危机 + 抗封禁 + 渗透 25%', dict(base, crisis_triggered=True,
                                       resistance_t0=True, penetration=0.25)),
        ('啥都没有', base),
    ]
    for name, ctx in cases:
        e = check_ending(ctx)
        print(f"  {name:28s} → {e.icon + ' ' + e.title_zh if e else '（继续游戏）'}")
