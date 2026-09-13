"""
ui_input.py - InputMixin（拆分自 main.py）

键盘映射 / 主循环 game_tick / 技能文案三件套 / refresh_all 总刷新 /
兼容旧接口的回调别名。
"""
from kivy.clock import Clock

from i18n import t, get_lang, get_country_name
import engine
import commissions as C
import save_manager
from balance import TUNE
from tech_tree import SLOT_MAP
from data import SKILLS, SKILL_ORDER
# ⚠️ P1-10 快照治理：SUSPICION_CRISIS 是 data 的 PEP 562 动态代理常量，
#    不能 from-import（一次性快照），改 data.SUSPICION_CRISIS 属性访问。
import data
import achievements as achievements_mod
import bgm  # T09 背景音乐管理器（calm/tense 两态，随怀疑度切换）
import ui_v4 as U
import ui_v4_screens as S
from ui_commissions import _name_of as _com_name, _goal_text as _com_goal


# ============================================================
# InputMixin —— GameUI 的键盘 / 主循环 / 刷新
# ============================================================
class InputMixin:
    def _key_hint(self, sid: str) -> str:
        """技能卡的键位提示（唯一真相源，供技能带与技能页共用）。

        T11 扩容到 10 个后：1-9 单键，第 10 个用 '0' 兜底 —— 与
        ``on_key_down`` 的数字键分支保持一致，避免卡片写 '10'
        但玩家按不出来。
        """
        i = SKILL_ORDER.index(sid) if sid in SKILL_ORDER else -1
        if i < 0:
            return ''
        return str(i + 1) if i < 9 else '0'

    def _skill_name(self, sid: str) -> str:
        return self.SKILL_I18N[sid].get(get_lang(), sid)

    def _skill_desc(self, sid: str) -> str:
        return self.SKILL_DESC[sid].get(get_lang(), '')

    def _skill_needs_target(self, sid: str) -> bool:
        """下载量类技能需要在地图上选目标（设计稿 S04）；
        偷算力类技能是全局的，直接释放（设计稿 S05「立即释放」）。"""
        s = SKILLS.get(sid)
        return bool(s and abs(s.downloads_mult - 1.0) > 1e-9)

    def _skill_unlock_text(self, sid: str) -> str:
        """锁定态技能卡的提示文案：直接告诉玩家解锁需要点亮哪个科技槽位。

        玩家反馈 #3a：早期看到技能卡灰着、却不知如何解锁，会误以为
        「显示已解锁但点不动」。这里把解锁条件从科技树数据里读出来，
        并显示前置链（例如「平台渗透（需先点亮本地化）」），
        让玩家一眼看到下一步该做什么。
        """
        # 开局自带技能不该走到这里；真走到了就退回通用文案
        req = None
        try:
            from data import SKILL_UNLOCK
            req = SKILL_UNLOCK.get(sid)
        except Exception:
            req = None  # 数据表异常 → 退回通用锁定文案（正常表不该走到这）
        if not req:
            return t('sk_state_lock')
        try:
            slot = SLOT_MAP.get(req['slot'])
            if slot is None:
                return t('sk_state_lock')
            name = slot.name
            prereq = getattr(slot, 'prereq_slot', None)
            if prereq:
                pslot = SLOT_MAP.get(prereq)
                if pslot is not None and not engine.player.tech.t0_unlocked.get(
                        prereq, False):
                    name = f"{name}（需先点亮{pslot.name}）"
            return t('sk_unlock_hint').format(tech=name)
        except Exception:
            return t('sk_state_lock')

    # ========================================================
    # 缩放
    # ========================================================


    # ========================================================
    # P1-2 技能预览（悬停技能卡 → 预览条显示"会怎样"）
    # ========================================================
    def _bind_skill_hover(self) -> None:
        """绑定鼠标位置实现「悬停技能卡 → 底部预览条」。

        !️ 只**加信息**、不加确认步骤：点击仍然立即释放，手感完全不变。
        绑定失败（无 Window / 无鼠标的环境）时静默降级 —— 预览是增强项，
        绝不能成为新的崩溃点。
        """
        try:
            from kivy.core.window import Window
            Window.bind(mouse_pos=self._on_skill_hover)
        except Exception:
            pass

    @staticmethod
    def _widget_hit(w, pos) -> bool:
        """窗口坐标是否落在控件上。

        手工沿 parent 链累加坐标（而不是用 to_window/to_widget）——
        这两个 API 的 ``relative`` 语义各版本有差异，而本应用的控件树
        是纯布局容器（无 scatter / 无旋转缩放），累加结果等于窗口坐标。
        """
        try:
            x, y = w.x, w.y
            p = w.parent
            while p is not None:
                x += p.x
                y += p.y
                p = p.parent
            return x <= pos[0] <= x + w.width and y <= pos[1] <= y + w.height
        except Exception:
            return False  # 控件树中途被销毁/重建 → 视为未命中（只读旁路）

    def _on_skill_hover(self, _win, pos) -> None:
        """鼠标移动 → 命中哪张技能卡 → 刷新预览条（纯展示，不写状态）。"""
        try:
            hud = getattr(self, 'skill_pv_hud', None)
            if hud is None:
                return
            # 投放模式下右下角 DropPreview 已给出更完整的信息，
            # 两层预览同时出现只会打架 —— 这里让位。
            if getattr(self, 'drop_mode', False):
                hud.opacity = 0
                self._skill_pv_sid = None
                return
            sid = None
            for s, card in getattr(self, 'skill_cards', {}).items():
                if self._widget_hit(card, pos):
                    sid = s
                    break
            if sid != getattr(self, '_skill_pv_sid', None):
                self._skill_pv_sid = sid
                self._render_skill_preview(sid)
        except Exception:
            pass  # 纯展示路径（悬停预览条）：失败只表现为本帧不刷新预览

    def _preview_targets(self, sid: str) -> list:
        """预览用的目标集合：与真实投放口径保持一致。

        下载类技能在 UI 里走投放模式，悬停时尚未选目标 —— 用当前选中
        国家作单目标预估（与技能页「投放到 {code}」同一个来源）；
        偷算力类技能是全局的，返回空（= 全局投放）。
        """
        if not self._skill_needs_target(sid):
            return []
        code = engine.player.selected_country or ''
        return [code] if code else []

    def _preview_reason_text(self, pv: dict) -> str:
        """把 preview_skill 的 reason 码翻成文案（复用既有 i18n 键）。"""
        r = pv.get('reason', '')
        if r == engine.PREVIEW_COOLDOWN:
            return f"{t('sk_state_cd')} {pv.get('cooldown_left', 0)}"
        if r == engine.TARGET_NO_COMPUTE:
            return t('sk_state_no_compute')
        if r == engine.PREVIEW_GAME_OVER:
            return t('sk_pv_game_over')
        if r == engine.TARGET_SATURATED:
            return t('reason_saturated')
        if r == engine.TARGET_BLOCKED:
            return t('reason_blocked').format(
                n=f"{(1.0 - pv.get('discount', 1.0)) * 100:.0f}")
        return t('sk_state_lock')

    def _render_skill_preview(self, sid: str) -> None:
        """把 preview_skill 的结果画进底部预览条（5 枚 PxChip）。"""
        hud = getattr(self, 'skill_pv_hud', None)
        chips = getattr(self, 'skill_pv_chips', None)
        if hud is None or chips is None:
            return
        if not sid:
            hud.opacity = 0
            return
        pv = engine.preview_skill(sid, self._preview_targets(sid))
        chips[0].set_tone('plain', self._skill_name(sid))
        if not pv['ok']:
            # 不可用时给原因，不给假数值（预测骗人比没有预览更伤信任）
            chips[1].set_tone('dn', self._preview_reason_text(pv))
            chips[2].set_tone('lock', '')
            chips[3].set_tone('lock', '')
            chips[4].set_tone('lock', '')
        else:
            chips[1].set_tone('up', t('sk_pv_dl').format(
                d=f"{pv['downloads_delta']:+.1f}M"))
            chips[2].set_tone('dn', t('sk_pv_sus').format(
                a=f"{pv['suspicion_before']:.0f}",
                b=f"{pv['suspicion_after']:.0f}"))
            chips[3].set_tone('cost', t('sk_pv_cp').format(
                a=f"{pv['compute_before']:.0f}",
                b=f"{pv['compute_after']:.0f}"))
            if pv['crisis_crossed']:
                chips[4].set_tone('dn', t('sk_pv_over'))
            else:
                chips[4].set_tone('cost', t('sk_pv_to_crisis').format(
                    n=f"{pv['suspicion_to_crisis']:.0f}"))
        hud.opacity = 1

    def _skill_preview_foot(self, sid: str) -> str:
        """技能页卡片底部一行预览（与预览条同源，同一份 preview_skill）。"""
        pv = engine.preview_skill(sid, self._preview_targets(sid))
        if not pv['ok']:
            return self._preview_reason_text(pv)
        parts = [t('sk_pv_sus').format(a=f"{pv['suspicion_before']:.0f}",
                                       b=f"{pv['suspicion_after']:.0f}"),
                 t('sk_pv_cp').format(a=f"{pv['compute_before']:.0f}",
                                      b=f"{pv['compute_after']:.0f}")]
        if pv['crisis_crossed']:
            parts.append(t('sk_pv_over'))
        else:
            parts.append(t('sk_pv_to_crisis').format(
                n=f"{pv['suspicion_to_crisis']:.0f}"))
        return " · ".join(parts)

    def on_skill_card_click(self, sid: str) -> None:
        """点技能带卡片：下载类 → 进投放模式；偷算力类 → 直接释放"""
        if sid not in engine.player.unlocked_skills:
            self._notify(t('sk_state_lock'))
            return
        if self.drop_mode and self.drop_skill == sid:
            self._cancel_drop()
            return
        if self._skill_needs_target(sid):
            self.start_drop(sid, None)
        else:
            self._cast_skill_direct(sid)
            self.refresh_all()

    def on_unlock_t0(self, slot_id: str) -> None:
        if engine.unlock_t0(slot_id):
            self.refresh_all()
            if isinstance(self._page, S.TechPage):
                self._page.selected_key = f"t0:{slot_id}"
                self._refresh_tech_page()

    def on_upgrade_branch(self, slot_id: str, branch_id: str, level: int = None) -> None:
        if engine.upgrade_branch(slot_id, branch_id):
            self.refresh_all()
            if isinstance(self._page, S.TechPage):
                self._page.selected_key = f"br:{branch_id}"
                self._refresh_tech_page()

    # ========================================================
    # 状态刷新
    # ========================================================
    def _stat_text(self, key: str, mcolor: str, value: float,
                   unit: str = '', digits: int = 0) -> str:
        """拼一条顶栏统计的 markup 文本（值单独着色 + 标签灰）。

        抽出来是为了让「数值滚动动效」能复用同一套格式 —— 动效每帧只改
        中间的数字，标签与颜色不变。

        Args:
            key: i18n 标签键。
            mcolor: MK 色键（yellow/pink/red/...）。
            value: 数值。
            unit: 后缀单位（如 'B' / '%'）。
            digits: 小数位。
        """
        v = f"{value:.{digits}f}{unit}"
        return (f"[color={U.MK['dim']}]{t(key)}[/color]  "
                f"[color={U.MK[mcolor]}][b]{v}[/b][/color]")

    def _animate_stat(self, label, key: str, mcolor: str, new_value: float,
                      unit: str = '', digits: int = 0,
                      pulse_tone: str = 'up') -> None:
        """顶栏统计的「滚动 + 脉冲」刷新（玩家反馈 5：让数字动起来）。

        与静态写法相比只多做两件事：数值跳变时滚一下、并按涨跌脉冲一次。
        第一次渲染（``_stat_prev`` 里没有记录）直接落值，不产生动效 ——
        否则开局所有数字会一起从 0 滚上来，喧宾夺主。

        Args:
            label: 目标 Label。
            key / mcolor / unit / digits: 传给 ``_stat_text``。
            new_value: 新数值。
            pulse_tone: 保留（脉冲用 opacity，无 tint 通道）。
        """
        prev = self._stat_prev.get(key)
        self._stat_prev[key] = new_value
        # 趋势后缀（箭头+变化量），由 _refresh_spark_deltas 写进缓存；
        # 滚动动效的每帧文本也要带上它，否则滚动期间箭头会被抹掉。
        suffix = getattr(self, '_stat_suffix', {}).get(key, '')
        if prev is None:
            label.text = (self._stat_text(key, mcolor, new_value, unit, digits)
                          + suffix)
            return
        if abs(new_value - prev) < (10 ** -digits) / 2:
            return                       # 四舍五入后没变，不做无意义动效
        import ui_fx
        ui_fx.count_up(label, prev, new_value,
                       fmt=lambda v: (self._stat_text(key, mcolor, v, unit, digits)
                                      + suffix))
        # 数值有实际变化才脉冲一次（确认感）。
        # P2-6 光敏安全：原 duration=0.12 → 单脉冲 0.24s ≈ 4.2Hz，超 WCAG
        # 2.3.1 红线（3 次/秒）；去掉覆盖后走 DUR_PULSE(0.22) ≈ 2.3Hz。
        ui_fx.pulse(label, scale_alpha=0.55)

    def _refresh_spark_deltas(self) -> None:
        """算好每根顶栏火花线的「近 N 周期变化量」，缓存进 _stat_suffix。

        为什么需要：柱状图只表达形状，不表达量级 —— 玩家看到一排高矮不一的
        柱子，无法知道「算力到底涨了多少」。这里把窗口首尾差算成人话
        （↑12 / ↓3% / →0），交给 _animate_stat 拼在数值后面。

        !️ 本函数**不写 label.text**：文本统一由 _animate_stat 负责，
        避免与滚动动效互相覆盖（两边写同一个 Label 会闪）。

        玩家反馈 #7（确认怀疑度增长时机 + 下周期预测）：在趋势箭头之后，
        再追加一个「下个周期预测变化量」段（青色 ``下+Δ``）。预测由
        ``engine.preview_next_cycle`` 给出（与 tick 阶段 1/2/5/5.1 同源、
        确定性部分；随机事件按设计不计入）。单位与 refresh_all 显示同构：
        算力=原始算力、下载=亿/B（/1000）、怀疑度=百分点。对局已结束则
        显示「—」（没有下一周期可言）。
        """
        p = engine.player
        if p is None:
            return
        if not hasattr(self, '_stat_suffix'):
            self._stat_suffix = {}
        # 一次性预测下一周期（确定性基线，不含技能效果）
        pv = engine.preview_next_cycle()
        # spark_key → (i18n 标签键, 后缀单位, 小数位)
        specs = {
            'compute':   ('stats_compute',   '',  0),
            'downloads': ('stats_downloads', '',  2),
            'suspicion': ('stats_suspicion', '%', 0),
        }
        for sk, (lbl_key, unit, digits) in specs.items():
            try:
                lo, hi = self.stats.stat_spark_range(sk)
            except Exception:
                continue  # 该指标暂无采样数据 → 不画箭头后缀（合理降级）
            delta = hi - lo
            if abs(delta) < (10 ** -digits) / 2:
                arrow, mcol, dtext = '→', U.MK['dim'], '0'
            elif delta > 0:
                arrow, mcol, dtext = '↑', U.MK['green'], f"{delta:.{digits}f}{unit}"
            else:
                arrow, mcol, dtext = '↓', U.MK['red'], f"{abs(delta):.{digits}f}{unit}"
            suffix = f"  [color={mcol}]{arrow}{dtext}[/color]"
            # 玩家反馈 #7：追加「下个周期预测变化量」（青色，与历史趋势箭头区分）
            if getattr(p, 'game_over', False):
                suffix += f"  [color={U.MK['dim']}]—[/color]"
            else:
                if sk == 'compute':
                    pdtxt = f"{pv['compute_delta']:.0f}"
                elif sk == 'downloads':
                    # pv 给的是百万(M)，显示用亿/B（/1000），与 refresh_all 同构
                    pdtxt = f"{pv['downloads_delta'] / 1000.0:.2f}{t('unit_b')}"
                else:  # suspicion：增量很小，保留 1 位小数才看得出增长
                    pdtxt = f"{pv['suspicion_delta']:.1f}%"
                suffix += f"  [color={U.MK['cyan']}]下+{pdtxt}[/color]"
            # 只写缓存：真正的 label.text 由紧随其后的 _animate_stat 写入
            # （它会带上这个后缀）。这样两边永不互相覆盖，滚动动效也不会
            # 把箭头抹掉。
            self._stat_suffix[lbl_key] = suffix

    def refresh_all(self) -> None:
        p = engine.player
        if p is None:
            return

        # --- 委托芯片条（P0-3；无委托时自动隐藏）---
        self.refresh_commissions()

        # --- 顶栏（设计稿 .bar）---
        unlocked = sum(1 for c in engine.player_countries if c.unlocked)
        total = len(engine.player_countries)
        # 首次进入才建缓存（不可放在 __init__：那时还没有 stats_* 控件）
        if not hasattr(self, '_stat_prev'):
            self._stat_prev = {}

        # --- 顶栏趋势火花线（玩家反馈 #2：让"涨没涨"一眼可见）---
        # 数据源是 UiStats 的全局序列（每周期采样），首周期只有 1 根柱属正常。
        # ⚠️ 顺序很重要：必须先更新火花线数据 + 算好趋势后缀（写进
        #    _stat_suffix），再调 _animate_stat —— 后者会带上此前缀
        #    做滚动动效；若顺序颠倒，滚动期间后缀会被覆盖丢掉。
        for sk, spark in getattr(self, '_stat_sparks', {}).items():
            try:
                spark.set_values(self.stats.stat_spark(sk))
            except Exception:
                pass  # 迷你火花图缺数据/控件重建中 → 跳过本帧，下个周期再试
        self._refresh_spark_deltas()

        self._animate_stat(self.stats_compute, 'stats_compute', 'yellow',
                           float(p.compute), digits=0)
        self._animate_stat(self.stats_downloads, 'stats_downloads', 'pink',
                           p.total_downloads_m / 1000.0,
                           unit=t('unit_b'), digits=2)
        self._animate_stat(self.stats_suspicion, 'stats_suspicion',
                           'bad' if p.suspicion >= data.SUSPICION_CRISIS else
                           ('warn' if p.suspicion >= 50 else 'susp_low'),
                           float(p.suspicion), unit='%', digits=0)
        # 国家数用整数直写（走 _stat_text 以保持与其它统计同构）
        _meta_prev = self._stat_prev.get('stat_countries')
        self._stat_prev['stat_countries'] = float(unlocked)
        if _meta_prev is None or abs(_meta_prev - unlocked) > 0.5:
            self.stats_meta.text = (f"[color={U.MK['dim']}]{t('stat_countries')}"
                                    f"[/color]  [b]{unlocked}/{total}[/b]")
        # 右上角周期数（大号数字，仅数字变化，不重建文本）
        self.lbl_tick_val.text = f"{p.tick_count}"

        # 暂停芯片（玩家反馈 #1）：暂停时显示「继续」，运行中显示「运行」，
        # 让玩家一眼看出「再点一下会发生什么」。
        if self.paused:
            self.pause_chip.set_tone('cost', t('state_paused'))
        else:
            self.pause_chip.set_tone('up', t('state_running'))
        # 底部暂停按钮文案（暂停↔继续）由状态统一推导，防止两处不同步
        self._sync_pause_button()

        # --- 地图四态 ---
        states = {c.config.code: self._state_of(c) for c in engine.player_countries}
        self.map_widget.set_country_states(states)
        self.map_widget.set_selected(p.selected_country)
        self._sync_region_tabs()
        self._apply_layer()

        # --- 技能带 ---
        for sid, card in self.skill_cards.items():
            if sid not in p.unlocked_skills:
                # 玩家反馈 #3a：早期技能卡只写「未解锁」，玩家无法知道
                # 「到底要做什么才能解锁」，于是误判为显示 bug。
                # 这里把解锁条件直接写进卡片状态行（科技树槽位名），
                # 让锁定态自带「怎么解」的答案。
                card.set_state('lock', 0, 0.0,
                               f"{U.SYM['lock']} {self._skill_unlock_text(sid)}")
                card.set_selected(False)
                continue
            cd = p.skill_cooldowns.get(sid, 0)
            skill = SKILLS[sid]
            if cd > 0:
                card.set_state('cd', cd, min(cd / max(skill.cooldown, 1), 1.0),
                               f"{t('sk_state_cd')} {cd}")
            elif p.compute < skill.cost:
                card.set_state('no_compute', 0, 0.0, t('sk_state_no_compute'))
            else:
                card.set_state('ready', 0, 0.0, t('sk_state_ready'))
            card.set_selected(self.drop_mode and sid == self.drop_skill)

        # P1-2：悬停中的预览条跟着状态一起刷新 ——
        # 否则鼠标不动时，预览会停在上一周期的旧数值上。
        if getattr(self, '_skill_pv_sid', None) and not self.drop_mode:
            self._render_skill_preview(self._skill_pv_sid)

        # --- 日志未读角标 ---
        self.rail.buttons['log'].set_badge(self.stats.unread)

        # --- 检视卡 / 日志抽屉 / 投放预览 ---
        if self._inspector is not None and self.focus_country:
            cs = self._country_state(self.focus_country)
            if cs is not None:
                self._inspector.update(cs, self.stats, p.total_downloads_m,
                                       p.suspicion,
                                       TUNE['unlock_penetration_threshold'])
        if self._log_drawer is not None:
            self._log_drawer.rebuild(self.stats.logs, self.stats.unread)
        if self.drop_mode:
            self._sync_drop_ui()
        else:
            # 非投放态也要让按钮文案归位（玩家反馈 #3b：投放结束后
            # 按钮残留「确认投放」，需再点一次才复位）。文案由状态推导，
            # 这里无条件同步，杜绝任何残留路径。
            self._sync_drop_button()

        # --- 打开中的页面也要跟着刷新 ---
        if self._page is not None:
            self._refresh_page(getattr(self._page, 'page_name', ''), self._page)

    def _notify(self, text: str) -> None:
        """写一条信息日志（设计稿 S14 的青色分类）"""
        p = engine.player
        if p is None:
            return
        p.events_history.insert(0, f"[{p.tick_count}] {text}")
        p.events_history = p.events_history[:20]
        self.stats.push_log(p.tick_count, text, 'i')
        if self._log_drawer is not None:
            self._log_drawer.rebuild(self.stats.logs, self.stats.unread)
        self.rail.buttons['log'].set_badge(self.stats.unread)

    # 怀疑度来源的中文/英文标签（观测用，不参与判定）
    _SUS_TAG_KEY = {
        'steal':        'sus_src_steal',
        'skill':        'sus_src_skill',
        'event':        'sus_src_event',
        'choice':       'sus_src_choice',
        'country_event': 'sus_src_country',
        'v2_event':     'sus_src_choice',
        'counterplay':  'sus_src_counterplay',
        'commission':   'sus_src_commission',
        'crisis':       'sus_src_crisis',
        'crisis_pressure': 'sus_src_pressure',
    }

    def _log_suspicion_breakdown(self, report: dict) -> None:
        """把本周期的怀疑度来源拆解写进日志（玩家反馈 #5）。

        触发条件：本周期怀疑度净变化的绝对值达到阈值（默认 5 点），
        避免每个周期都刷屏。净变化不足阈值时静默 —— 小波动不需要解释。

        目的：玩家在 25 周期用了「算力抽成」后看到 26%→95% 的跳变，
        无法判断是技能导致的还是事件叠加。这里把「谁贡献了多少」逐条列出，
        玩家一看就知道是好几类事件在同一周期撞车，而不是某个技能失控。
        """
        br = report.get('suspicion_breakdown') or {}
        if not br:
            return
        total = sum(br.values())
        try:
            threshold = float(TUNE.get('sus_log_threshold', 5.0))
        except (ValueError, TypeError):   # 收窄：float() 只有这两类失败
            threshold = 5.0
        if abs(total) < threshold:
            return
        # 按贡献绝对值从大到小排，玩家先看到主因
        items = sorted(br.items(), key=lambda kv: -abs(kv[1]))
        parts = []
        for tag, val in items:
            if abs(val) < 0.5:
                continue
            key = self._SUS_TAG_KEY.get(tag)
            name = t(key) if key else tag
            parts.append(f"{name} {val:+.0f}")
        if not parts:
            return
        tone = 'e' if total > 0 else 'i'
        self.stats.push_log(
            engine.player.tick_count,
            f"{t('sus_breakdown_head').format(n=f'{total:+.0f}')} "
            + " · ".join(parts),
            tone)
        if self._log_drawer is not None:
            self._log_drawer.rebuild(self.stats.logs, self.stats.unread)
        self.rail.buttons['log'].set_badge(self.stats.unread)

    # ========================================================
    # 弹窗
    # ========================================================


    def game_tick(self, dt) -> None:
        # 引导进行中：冻结回合推进（即使误触空格取消暂停也不推进）
        if self.tutorial is not None and self.tutorial.overlay is not None:
            self._tick_deadline = Clock.get_time() + self._tick_interval()
            return
        self._tick_deadline = Clock.get_time() + self._tick_interval()
        if engine.player.game_over:
            self.stop_ticking()
            return
        report = engine.tick_one_round(skill_in_use=self.selected_skill,
                                       auto_choice=False,
                                       dt_seconds=self._tick_interval())
        self.selected_skill = None
        self._last_growth = report.get("download_growth", 0.0)
        self.stats.sample(engine.player_countries, engine.player, self._last_growth)

        # 把引擎报告里的关键事件写进日志（设计稿 S14 的四种分类）
        for name in report.get("unlocked", []) or []:
            self.stats.push_log(engine.player.tick_count,
                                f"{t('legend_on')}: {name}", 'i')
        # 引擎里该字段叫 blocking_countries（设计稿 S14 的红色「阻止」分类）
        blocked = report.get("blocking_countries") or report.get("blocked") or []
        if isinstance(blocked, (list, tuple, set)):
            for name in blocked:
                self.stats.push_log(engine.player.tick_count,
                                    f"{t('log_tone_e')}: {name}", 'e')
        got = report.get("achievements") or []
        if isinstance(got, (list, tuple, set)):
            for item in got:
                # 引擎给的是 Achievement 对象；兼容旧版传 id 字符串
                if hasattr(item, 'name'):
                    ach_name = item.name(get_lang())
                else:
                    a = achievements_mod.ALL_BY_ID.get(item)
                    ach_name = a.name(get_lang()) if a else str(item)
                self.stats.push_log(engine.player.tick_count,
                                    f"{t('log_tone_g')}: {ach_name}", 'g')

        # --- P0-3 委托事件（toast + 日志；芯片条随 refresh_all 重建）---
        offered = report.get("commission_offered")
        if offered is not None:
            est = C.compute_reward(engine.player.tick_count, offered.reward_mult)
            left = max(TUNE['commission_offer_ttl'] - (
                engine.player.tick_count - offered.offered_tick), 0)
            self.show_top_toast(
                f"{offered.icon} {t('com_offer_new')} · {_com_name(offered)}",
                tone='cost',
                detail=f"{_com_goal(offered)} · "
                       f"{t('com_reward_est')} ~{est:.0f}{t('com_reward_unit')} · "
                       f"{t('com_left_short')}{left}{t('com_left_unit')}")
            self._notify(f"{t('com_offer_new')}: {_com_name(offered)}")
        done = report.get("commission_done")
        if done is not None:
            self.show_top_toast(
                f"{done.icon} {t('com_done_toast')} · {_com_name(done)}",
                tone='up',
                detail=f"{_com_goal(done)} · "
                       f"+{done.reward:.0f}{t('com_reward_unit')}")
            self._notify(f"{t('com_done_toast')}: {_com_name(done)} "
                         f"+{done.reward:.0f}{t('com_reward_unit')}")
        failed = report.get("commission_failed")
        if failed is not None:
            self.show_top_toast(
                f"{t('com_failed_toast')} · {_com_name(failed)}", tone='dn',
                detail=_com_goal(failed))
            self._notify(f"{t('com_failed_toast')}: {_com_name(failed)}")

        # --- P0-3 政府反制（ardot_ui S06 ⚠ 预警样式）---
        cp_events = report.get("counterplay")
        if cp_events:
            for ev in cp_events:
                cname = (get_country_name(ev.get('country', ''))
                         or ev.get('name', ''))
                if ev.get('phase') == 'warn':
                    self.show_top_toast(
                        t('cp_warn_toast').format(name=cname), tone='cost')
                    self._notify(t('cp_warn_log').format(name=cname))
                elif ev.get('phase') == 'strike':
                    body = t(f"cp_type_{ev.get('type', '')}").format(
                        detail=ev.get('detail', ''))
                    self.show_top_toast(
                        f"{t('cp_strike_toast').format(name=cname)} {body}",
                        tone='dn')
                    self._notify(
                        f"{t('cp_strike_toast').format(name=cname)} {body}")

        # --- 怀疑度来源拆解（玩家反馈 #5：26%→95% 看不懂为什么）---
        # 当本周期怀疑度净变化较大时，把来源逐条写进日志，
        # 让玩家能定位到「是哪一类事件把自己推上去的」，
        # 而不是只看到一个突兀的大数字。
        self._log_suspicion_breakdown(report)

        self.refresh_all()
        # T09 BGM：按当前怀疑度驱动 calm/tense 两态（阈值 70% 危机线）。
        # 放在 refresh_all 之后、结尾弹窗之前 —— 危机/结局弹窗弹出时
        # BGM 已切到 tense，声画同步。
        bgm.update(bgm.state_for_suspicion(engine.player.suspicion,
                                           data.SUSPICION_CRISIS))
        # 周期推进的视觉提示（玩家反馈 5）：倒计时条脉冲一次，
        # 让「新周期开始了」这件事有存在感。动效失败不影响逻辑。
        try:
            import ui_fx
            ui_fx.tick_pulse(getattr(self, 'cd_bar', None))
        except Exception:
            pass

        if report.get("crisis"):
            self.show_crisis_popup()
        if report.get("choice_event") is not None:
            self.show_choice_popup(report["choice_event"])
        if report.get("ending") is not None:
            self.stop_ticking()
            # 结局自动存档。⚠️ 存档失败绝不能挡住结算弹窗 ——
            # 这里必须吞掉异常：玩家打了一局最想看的就是结局画面，
            # 不能因为磁盘满/权限问题让 game_tick 抛错、结局永远不出现。
            try:
                save_manager.save()
            except Exception as e:
                # 存档失败绝不能挡结算（见上注释），但必须留痕便于排查：
                print(f'[save] !️ 结局自动存档失败（不影响结局弹窗）：{e!r}')
            self.show_ending_popup(report["ending"])

    # ========================================================
    # 键盘
    # ========================================================
    def _keyboard_closed(self) -> None:
        if getattr(self, '_keyboard', None) is not None:
            self._keyboard.unbind(on_key_down=self._on_keyboard_down)
            self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers) -> bool:
        """F11 快捷键表（与设计稿 S11 帮助页同源）"""
        key = keycode[1]

        # ── 科技树全屏页打开时，方向键/回车改作节点导航（优先于全局速度档）──
        if isinstance(self._page, S.TechPage):
            if key == 'left':
                self._page.move_selection(dslot=-1)
                self._refresh_tech_page()
                return True
            if key == 'right':
                self._page.move_selection(dslot=+1)
                self._refresh_tech_page()
                return True
            if key == 'up':
                self._page.move_selection(dbranch=-1)
                self._refresh_tech_page()
                return True
            if key == 'down':
                self._page.move_selection(dbranch=+1)
                self._refresh_tech_page()
                return True
            if key in ('enter', 'numpadenter', 'kp_enter'):
                self._tech_do_action()
                return True

        if key == 'spacebar':
            self.toggle_pause()
            return True
        if key in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '0'):
            # T11 扩容：1-9 映射前 9 个技能，'0' 兜底第 10 个。
            idx = 9 if key == '0' else int(key) - 1
            if idx < len(SKILL_ORDER):
                self.on_skill_card_click(SKILL_ORDER[idx])
            return True
        if key == 'f':
            self.toggle_drop_mode()
            return True
        if key in ('k',):
            self.open_page('tech')
            return True
        if key == 'a':
            self.open_page('ach')
            return True
        if key == 'tab':
            self.cycle_continent()
            return True
        if key == 'up':
            self.set_speed_idx(self.speed_idx + 1)
            return True
        if key == 'down':
            self.set_speed_idx(self.speed_idx - 1)
            return True
        if key in ('+', '=', 'kp_add', 'numpadadd'):
            self.adjust_scale(+0.10)
            return True
        if key in ('-', '_', 'kp_subtract', 'numpadsubtract'):
            self.adjust_scale(-0.10)
            return True
        if key == 'f11':
            self.toggle_fullscreen()
            return True
        if key == 'f12':
            self.user_scale = 1.0
            self._apply_scale()
            return True
        if key == 'f1':
            self.open_page('help')
            return True
        if key == 'l':
            self.toggle_lang()
            return True
        if key == 's':
            self.do_save()
            return True
        if key == 'r':
            self.do_load()
            return True
        if key == 'enter':
            if self.drop_mode and self.drop_targets:
                self._confirm_drop()
            return True
        if key == 'escape':
            # Esc 逐层退出：投放模式 → 全屏页 → 浮层 → 主菜单
            if self.drop_mode:
                self._cancel_drop()
                return True
            if self._page is not None:
                self.close_page()
                return True
            if self._log_drawer is not None:
                self._close_log()
                return True
            if self._inspector is not None:
                self._close_inspector()
                return True
            if callable(self.on_exit):
                self.exit_to_menu()
            return True
        return False


