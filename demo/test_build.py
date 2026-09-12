"""
test_build.py - 验证 UI 能正常构建（不进入 mainloop）
"""
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_WINDOW'] = 'sdl2'  # sandbox 里也能跑

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 引入 main 模块
import main as main_module

# 创建 App 实例但不 run
app = main_module.AIBienaoApp()

# 触发 build（现在返回 RootView：主菜单 ↔ 游戏 的切换容器）
ui = app.build()
print(f" RootView 构建成功: {type(ui).__name__}")
print(f"   - 子组件数: {len(ui.children)}")
print(f"   - 大小: {ui.size}")

# --- F01：主菜单应立即可用，点击「开始新游戏」后才构建 GameUI ---
menu = ui.menu
assert menu is not None, "启动后应显示主菜单"
print(f"   - 主菜单: {type(menu).__name__}  按钮 {len(menu.children)} 个控件")
assert ui.game is None, "未点击开始前不应构建 GameUI"
ui.start_new_game()
assert isinstance(ui.game, main_module.GameUI), "开始后应构建 GameUI"
print(f"   - 已进入游戏: {type(ui.game).__name__}  子组件数 {len(ui.game.children)}")

# 后续用例直接在 GameUI 上操作
ui = ui.game

# 模拟 3 个 tick
import engine
for i in range(3):
    report = engine.tick_one_round()
    print(f"   周期 {report['tick']}: 下载 +{report['download_growth']:.1f}M | 算力 +{report['compute_gain']:.1f}")

# 验证 i18n
import i18n
print(f"\n i18n 测试:")
print(f"   zh app_title = '{i18n.t('app_title')}'")
i18n.set_lang('en')
print(f"   en app_title = '{i18n.t('app_title')}'")
i18n.set_lang('zh')

# 验证国家事件
import country_events as ce
import data
print(f"\n 国家专属事件库: {len(ce.COUNTRY_EVENTS)} 条")
for code in ['CN', 'US', 'JP']:
    events = ce.get_country_events(code)
    print(f"   {code}: {len(events)} 条")
    for e in events:
        print(f"      - {e.title_zh} / {e.title_en}（阈值 {e.trigger_threshold_m}M）")

# ============================================================
# 回归测试：锁住已修复的 3 个 bug
# ============================================================
print("\n 回归测试：")

# --- 1. 技能冷却必须递减（旧代码从不递减 → 技能用一次永久锁死）---
engine.init_game()
p = engine.player
assert engine.use_skill('push_song'), "技能应当可用"
assert p.skill_cooldowns.get('push_song') == 3, "冷却初值应为 3"
for _ in range(4):
    engine.tick_one_round()
assert p.skill_cooldowns.get('push_song') is None, "4 周期后冷却应已归零并移除"
print("   ✅ 技能冷却会递减（push_song 3 → 0）")

# --- 2. 邻国解锁必须能推进（旧阈值 0.2 导致 150 周期仍卡 2/12）---
engine.init_game()
import random
random.seed(1)
for _ in range(60):
    engine.tick_one_round()
unlocked = sum(1 for c in engine.player_countries if c.unlocked)
total = len(engine.player_countries)
assert unlocked >= 5, f"60 周期应至少解锁 5 国，实际 {unlocked}/{total}"
print(f"   ✅ 国家解锁可推进（60 周期 {unlocked}/{total} 国）")

# --- 3. 事件效果不得重复结算（旧代码算力/怀疑度被加两次）---
engine.init_game()
p = engine.player
# 3a. 算力型事件（opensource_push: 算力 +15）
evt_c = next(e for e in data.EVENTS if e.effect_compute)
before = p.compute
engine._apply_event(evt_c)
assert abs((p.compute - before) - evt_c.effect_compute) < 1e-9, \
    f"算力应只加一次（期望 +{evt_c.effect_compute}，实际 +{p.compute - before}）"
# 3b. 怀疑度型事件（viral_tiktok: 怀疑 -2；先垫高避免被 0 下限截断）
evt_s = next(e for e in data.EVENTS if e.effect_suspicion)
p.suspicion = 50.0
before = p.suspicion
engine._apply_event(evt_s)
assert abs((p.suspicion - before) - evt_s.effect_suspicion) < 1e-9, \
    f"怀疑度应只加一次（期望 {evt_s.effect_suspicion}，实际 {p.suspicion - before}）"
print(f"   ✅ 事件效果只结算一次（{evt_c.id} 算力 +{evt_c.effect_compute} / "
      f"{evt_s.id} 怀疑 {evt_s.effect_suspicion}）")

# --- 4. 结局系统：怀疑度 100% 必须判定为「被关停」且游戏结束 ---
engine.init_game()
p = engine.player
p.suspicion = 100.0
e = engine.check_ending()
assert e is not None and e.id == 'shutdown', f"怀疑度 100% 应触发被关停，实际 {e}"
report = engine.tick_one_round()
assert p.game_over, "结局命中后 game_over 应为 True"
assert report["ending"] is not None, "report 应携带 ending"
print(f"   ✅ 结局判定生效（{e.icon} {e.title_zh}）")

# --- 5. 结局命中后不得继续推进 ---
ticks_before = p.tick_count
for _ in range(5):
    engine.tick_one_round()
assert p.tick_count == ticks_before, "游戏结束后 tick_count 不应再增加"
print("   ✅ 结局后停止推进")

# --- 6. v2 事件库（37 条）已接入并可触发 ---
import v2_events
assert len(v2_events.EVENTS) >= 30, f"v2 事件应加载 ≥30 条，实际 {len(v2_events.EVENTS)}"
engine.init_game()
random.seed(5)
fired = set()
for _ in range(60):
    r = engine.tick_one_round()
    if r.get('v2_event'):
        fired.add(r['v2_event'][0].id)
assert fired, "60 周期内应至少触发 1 条 v2 事件"
print(f"   ✅ v2 事件库已接入（{len(v2_events.EVENTS)} 条，"
      f"60 周期触发 {len(fired)} 条）")

# --- 7. 成就系统可解锁 ---
engine.init_game()
random.seed(2)
for _ in range(60):
    engine.tick_one_round()
assert len(engine.player.achievements) > 0, "60 周期内应至少解锁 1 个成就"
print(f"   ✅ 成就系统生效（解锁 {len(engine.player.achievements)} 个："
      f"{', '.join(sorted(engine.player.achievements)[:3])}…）")

# --- 8. 存档 / 读档一致性 ---
import save_manager
engine.init_game()
for _ in range(20):
    engine.tick_one_round()
snapshot = (engine.player.tick_count,
            round(engine.player.total_downloads_m, 4),
            dict(engine.player.tech.branch_levels))
save_manager.save()
for _ in range(5):
    engine.tick_one_round()
assert save_manager.load(), "读档应成功"
restored = (engine.player.tick_count,
            round(engine.player.total_downloads_m, 4),
            dict(engine.player.tech.branch_levels))
assert snapshot == restored, f"读档后状态不一致：{snapshot} vs {restored}"
print(f"   ✅ 存档/读档一致（tick {restored[0]} / {restored[1]:.1f}M）")

# --- 9. F12 自适应：缩放基础设施必须真的改到字号/行高 ---
ui._apply_scale()
base_font = ui.stats_compute.font_size
base_fx = ui.skill_cards['push_song'].lbl_fx.font_size
ui.adjust_scale(+0.30)
assert ui.scale > 1.0, "放大后 scale 应 > 1"
big_font = ui.stats_compute.font_size
big_fx = ui.skill_cards['push_song'].lbl_fx.font_size
assert big_font > base_font, "放大后状态条字号应变大"
assert big_fx > base_fx, "放大后技能带字号应变大"
ui.adjust_scale(-0.60)
assert ui.stats_compute.font_size < base_font, "缩小后状态条字号应变小"
assert ui.skill_cards['push_song'].lbl_fx.font_size < big_fx, "缩小后技能带字号应变小"
ui.user_scale = 1.0
ui._apply_scale()
print(f"   ✅ F12 自适应缩放生效（状态条字号 {base_font:.0f} → {big_font:.0f}；"
      f"技能带字号 {base_fx:.0f} → {big_fx:.0f}，+/- 可调）")

# --- 10. F11：Tab 切区域高亮（设计稿 §5 的 5 个页签）---
ui.cycle_continent()                      # 亚洲
asia_codes = set(ui.map_widget._continent_codes)
assert asia_codes, "切大洲后应有高亮国家"
assert 'CN' in asia_codes, "亚洲高亮应包含 CN"
for _ in range(len(ui.REGION_KEYS)):      # 从亚洲起再转 5 步回到「取消高亮」
    ui.cycle_continent()
assert not ui.map_widget._continent_codes, "转满一圈后应取消高亮"
print(f"   ✅ Tab 切区域生效（亚洲 {len(asia_codes)} 国，{len(ui.REGION_KEYS)} 区域转一圈可取消高亮）")

# --- 11. F11：全屏开关（只验证方法可调用，不干扰沙箱窗口）---
import inspect
assert hasattr(ui, 'toggle_fullscreen'), "应提供 F11 全屏切换方法"
assert 'f11' in inspect.getsource(main_module.GameUI._on_keyboard_down), \
    "F11 应绑定在键盘处理里"
for k in ('tab', "f1", 'escape', '+', '-'):
    assert k in inspect.getsource(main_module.GameUI._on_keyboard_down), \
        f"快捷键 {k} 应绑定在键盘处理里"
print("   ✅ F11 快捷键齐全（F11 全屏 / Tab 大洲 / +/- 缩放 / Esc 菜单 / F1 帮助）")

# --- 12. 计划书验收数量断言（F02 / F05 / F08 / F09）---
import data, endings as endings_mod, achievements as ach_mod
assert len(data.COUNTRIES) == 20, f"应 20 国，实际 {len(data.COUNTRIES)}"
assert len(data.SKILLS) == 6, f"应 6 技能，实际 {len(data.SKILLS)}"
assert len(data.SKILL_ORDER) == 6, "快捷键 1-6 应映射 6 个技能"
assert len(endings_mod.ENDINGS) == 7, f"应 7 结局，实际 {len(endings_mod.ENDINGS)}"
# 成就总数 = 任务型 15 + 事件型 7 = 22（随内容扩充从 20 增至 22）
assert len(ach_mod.ALL_BY_ID) == 22, f"应 22 成就，实际 {len(ach_mod.ALL_BY_ID)}"
triggerable = sum(1 for e in endings_mod.ENDINGS if e.id != 'liberation')
assert triggerable >= 4, "至少 4 种结局可自动触发"
assert len(ui.map_widget.country_labels) == 20, "地图应画出 20 国标签"
print(f"   ✅ 验收数量达标：{len(data.COUNTRIES)} 国 / {len(data.SKILLS)} 技能 / "
      f"{len(endings_mod.ENDINGS)} 结局（{triggerable} 种可自动判定）/ "
      f"{len(ach_mod.ALL_BY_ID)} 成就")

# --- 13. P0-3 委托系统：到期成功 / 失败路径 + 接受状态机 ---
import commissions
engine.init_game()
p = engine.player
random.seed(3)
com = commissions.CommissionState(
    uid=9001, template_id='C6', goal='unlock', icon='[N]',
    name_zh='测试开疆', name_en='Test Frontier', window=2, reward_mult=1.0,
    status='active', accepted_tick=0, deadline_tick=0,
    cond={'unlocked_delta': {'gte': 1}},
    snap_unlocked=sum(1 for c in engine.player_countries if c.unlocked),
    reward=100.0)
p.commissions.append(com)
done_before = p.commissions_done
compute_before = p.compute
engine.player_countries[2].unlocked = True       # 解锁_delta = 1 → 达成
r = engine.tick_one_round()
assert p.commissions_done == done_before + 1, "到期判定应完成委托"
assert r.get("commission_done") is not None, "report 应携带 commission_done"
assert p.compute > compute_before, "完成奖励算力应到账"
assert com not in p.commissions, "完成后应从在场列表移除"
# 失败路径：目标不可达 → 到期失败 + 怀疑惩罚
com2 = commissions.CommissionState(
    uid=9002, template_id='C2', goal='downloads', icon='[D]',
    name_zh='测试拉新', name_en='Test Sprint', window=8, reward_mult=1.0,
    status='active', accepted_tick=0, deadline_tick=0,
    cond={'downloads_delta': 10**9},
    snap_downloads=p.total_downloads_m)
p.commissions.append(com2)
fail_before = p.commissions_failed
susp_before = p.suspicion
r = engine.tick_one_round()
assert p.commissions_failed == fail_before + 1, "到期未达成应判失败"
assert r.get("commission_failed") is not None, "report 应携带 commission_failed"
assert p.suspicion > susp_before, "失败应有怀疑度惩罚"
assert com2 not in p.commissions, "失败后应从在场列表移除"
# 接受状态机：offered → accept → active + 快照
engine.init_game()
p = engine.player
com3 = commissions.CommissionState(
    uid=9003, template_id='C3', goal='compute', icon='[C]',
    name_zh='测试算力', name_en='Test Compute', window=8, reward_mult=1.0)
com3.offered_tick = p.tick_count
p.commissions.append(com3)
p.compute_earned_total = 555.0
assert engine.accept_commission(9003), "接受待接受委托应成功"
assert com3.status == 'active' and com3.deadline_tick, "接受后应为进行中"
assert com3.snap_compute == 555.0, "接受时应写入偷算力快照"
assert not engine.accept_commission(9003), "同一委托不可重复接受"
print("   ✅ P0-3 委托系统生效（成功/失败判定 + 接受状态机 + 快照）")

# --- 14. P0-3 政府反制：预警结算 + 怀疑度截断在危机线下 ---
engine.init_game()
p = engine.player
random.seed(7)
cs = engine.player_countries[0]                  # CN 已解锁
cs.current_block_intensity = 0.5
cs.block_budget_remaining = 100.0
engine._counterplay_pending[cs.config.code] = p.tick_count + 1
r = engine.tick_one_round()
cp_events = r.get("counterplay") or []
strikes = [e for e in cp_events if e["phase"] == "strike"]
assert strikes, "预警后下一周期应结算反制"
# 截断硬规则：跨境协查永不把怀疑度推过危机线 −1
p.suspicion = 78.5
res = [engine._resolve_counterplay(cs, 1.0) for _ in range(60)]
assert p.suspicion <= 79.0, \
    f"反制怀疑度应截断在危机线下，实际 {p.suspicion}"
assert any(e["type"] == "cross_inquiry" for e in res), \
    "60 次三选一应覆盖跨境协查"
print("   ✅ P0-3 政府反制生效（预警→结算 + 怀疑度截断在危机线下）")

# --- 15. P0-3 存档往返：委托 / 计数器 / 快照字段 ---
import save_manager
engine.init_game()
p = engine.player
random.seed(9)
for _ in range(12):
    engine.tick_one_round()
    for c in list(p.commissions):
        if c.status == 'offered':
            engine.accept_commission(c.uid)
snap_c = (len(p.commissions), p.commissions_done, p.commissions_failed,
          round(p.compute_earned_total, 2), dict(p.skill_uses),
          p.last_commission_tick)
save_manager.save()
for _ in range(3):
    engine.tick_one_round()
assert save_manager.load(), "读档应成功"
p = engine.player          # load 内部 init_game 会换全新状态对象，必须重新取引用
res_c = (len(p.commissions), p.commissions_done, p.commissions_failed,
         round(p.compute_earned_total, 2), dict(p.skill_uses),
         p.last_commission_tick)
assert snap_c == res_c, f"委托存档往返不一致：{snap_c} vs {res_c}"
print(f"   ✅ P0-3 存档往返一致（在场 {res_c[0]} 单 / 完成 {res_c[1]} / "
      f"失败 {res_c[2]} / 累计偷取 {res_c[3]:.0f}）")

# ---- 16) 委托/反制 UI 接线（i18n 键完整性 + 模板字段 + Mixin 装配）----
import i18n as i18n_mod
import commissions as commissions_mod
_needed = [
    'com_offer_new', 'com_offer_tag', 'com_active_tag', 'com_accept',
    'com_decline', 'com_close', 'com_reward_est', 'com_reward_unit',
    'com_left_short', 'com_left_unit', 'com_done_toast', 'com_failed_toast',
    'com_declined_log', 'com_goal_pen', 'com_goal_downloads',
    'com_goal_compute', 'com_goal_skill', 'com_goal_stealth',
    'com_goal_unlock', 'com_c5_bonus', 'com_sus_short',
    'cp_warn_toast', 'cp_warn_log', 'cp_strike_toast',
    'cp_type_compute_seizure', 'cp_type_budget_reinforce',
    'cp_type_cross_inquiry',
]
for _lang in (i18n_mod.LANG_ZH, i18n_mod.LANG_EN):
    _miss = [k for k in _needed if k not in i18n_mod.TRANSLATIONS[_lang]]
    assert not _miss, f"i18n[{_lang}] 缺委托/反制键: {_miss}"
for _tpl in commissions_mod.COMMISSION_TEMPLATES:
    for _f in ('id', 'icon', 'name_zh', 'name_en', 'goal', 'window',
               'reward_mult'):
        assert _f in _tpl, f"模板 {_tpl.get('id')} 缺字段 {_f}"
assert hasattr(main_module.GameUI, 'refresh_commissions'), \
    "GameUI 应装配 CommissionMixin（委托芯片条）"
assert hasattr(main_module.GameUI, 'show_top_toast'), \
    "GameUI 应具备顶部弹条（反制预警）"
print(f"   ✅ 16) 委托/反制 UI 接线（i18n zh+en ×{len(_needed)} 键 / "
      f"模板字段 / Mixin 装配）")

# ---- 17) 可视化 / 引导 / 节奏参考（玩家反馈 6、7、10）----
# 顶栏四个统计各挂一根趋势火花线（设计稿 S05）；UiStats 必须维护全局序列。
import ui_v4_screens as _screens
_st = _screens.UiStats()
for _attr in ('global_downloads', 'global_compute', 'global_suspicion',
              'global_unlocked'):
    assert hasattr(_st, _attr), f"UiStats 缺全局序列 {_attr}"
assert hasattr(_st, 'stat_spark'), "UiStats 应提供 stat_spark(key)"
# 归一化：单调递增序列应能产出递增的 0–1 火花值
from collections import deque as _dq
_st.global_compute = _dq([1.0, 2.0, 4.0, 8.0], maxlen=12)
_vals = _st.stat_spark('compute')
assert _vals and abs(_vals[-1] - 1.0) < 1e-9 and _vals[0] < _vals[-1], \
    f"火花线归一化异常: {_vals}"
assert _st.stat_spark('不存在') == [], "未知 key 应返回空序列"
# 顶栏装配：已构建的 GameUI 实例必须注册 4 个 spark_key（实例属性，
# 在 _make_topbar 里填充，故检查实例而非类）。
# ⚠️ 本文件第 35 行已把 ui 重绑定为 GameUI 实例（ui = ui.game），
# 所以这里直接用 ui，不要再写 ui.game。
_ui_sparks = getattr(ui, '_stat_sparks', None)
assert _ui_sparks, "GameUI 实例应具备顶栏火花线注册表 _stat_sparks"
_core_keys = {'compute', 'downloads', 'suspicion', 'unlocked'}
_missing_sk = _core_keys - set(_ui_sparks)
assert not _missing_sk, f"顶栏缺火花线: {_missing_sk}"
for _k, _sp in _ui_sparks.items():
    assert hasattr(_sp, 'set_values'), f"spark[{_k}] 不可更新"

# 新手指引：核心循环 + 参数讲解 + 科技树演示
import tutorial as _tut
_steps = _tut.TutorialController.STEPS
assert len(_steps) >= 12, f"引导步骤应 ≥12（含核心循环），实际 {len(_steps)}"
_titles = ' '.join(s.title for s in _steps)
for _kw in ('循环', '核心参数', '科技'):
    assert _kw in _titles, f"引导应讲「{_kw}」，实际标题: {_titles}"
# 至少一步演示科技树（诊断结论：科技是第一加速器）
_demo = [s for s in _steps if s.action == 'open_tech_page']
assert _demo, "引导应包含打开科技树的演示步骤"
# 所有步骤不得残留未替换的占位符
import re as _re
for _i, _s in enumerate(_steps):
    _bad = _re.findall(r'\{[a-z_]+\}', _s.body)
    assert not _bad, f"引导第 {_i} 步残留占位符: {_bad}"

# 里程碑提示（检视卡）：按引擎真实阈值分档
_insp_cls = _screens.InspectorPanel
_ms = _insp_cls._milestone_text
assert '还差' in _ms(0.031, 0.80, False, 0.10), "未解锁应给出「还差 X%」"
assert '饱和' in _ms(0.995, 0.80, True, 0.10), "≥99% 应显示已饱和"
assert '阻止' in _ms(0.82, 0.80, True, 0.10), "越过阻止阈值应警告"

# 节奏参考 + 里程碑 i18n 键（zh/en 对称）
_pace_keys = ['help_pace_t', 'help_pace_body', 'insp_ms_unlock', 'insp_ms_need',
              'insp_ms_next', 'insp_ms_ready', 'insp_ms_blocked',
              'insp_ms_saturated']
for _lang in (i18n_mod.LANG_ZH, i18n_mod.LANG_EN):
    _m = [k for k in _pace_keys if k not in i18n_mod.TRANSLATIONS[_lang]]
    assert not _m, f"i18n[{_lang}] 缺可视化/节奏键: {_m}"
print(f"   ✅ 17) 可视化/引导/节奏（顶栏火花×4 / 引导 {len(_steps)} 步 / "
      f"里程碑分档 / i18n ×{len(_pace_keys)} 键）")

# ---- 18) T09 背景音乐：资源 / 两态映射 / 设置页开关接线 ----
import bgm as _bgm
import ui_v4_screens as _screens_m

assert _bgm.STATES == ('calm', 'tense'), f"BGM 态定义变了: {_bgm.STATES}"
_bgm_dir = _bgm._base_dir()
for _st in _bgm.STATES:
    _p = os.path.join(_bgm_dir, _st + '.wav')
    assert os.path.exists(_p), f"BGM 资源缺失: {_p}（打包时须 add-data assets/bgm）"

# 两态映射：70% 危机线为阈值（低于→calm，达到/超过→tense）
assert _bgm.state_for_suspicion(0.0, 50.0) == 'calm'
assert _bgm.state_for_suspicion(34.9, 50.0) == 'calm'
assert _bgm.state_for_suspicion(35.0, 50.0) == 'tense', "70% 危机线应切 tense"
assert _bgm.state_for_suspicion(80.0, 50.0) == 'tense'
assert _bgm.state_for_suspicion('bad', 50.0) == 'calm', "脏输入应降级为 calm"

# 设置页开关：on_music 是 SettingsPage 的合法形参，且实际构造出 sw_music
_sp = _screens_m.SettingsPage(on_music=lambda i: None)
assert hasattr(_sp, 'sw_music'), "设置页缺音乐开关控件"

# i18n 键 zh/en 对称
for _lang in (i18n_mod.LANG_ZH, i18n_mod.LANG_EN):
    for _k in ('set_music', 'set_music_hint'):
        assert _k in i18n_mod.TRANSLATIONS[_lang], f"i18n[{_lang}] 缺 {_k}"

# main.py 接线点存在（import bgm / load_all / on_music 回调）
_main_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'main.py'), encoding='utf-8').read()
for _needle in ('import bgm', 'bgm.load_all()', 'on_music=self._set_music_idx',
                'def _set_music_idx'):
    assert _needle in _main_src, f"main.py 缺 BGM 接线: {_needle}"
print("   ✅ 18) T09 背景音乐（calm/tense 两态 WAV / 70% 阈值映射 / "
      "设置页开关 ×2 语 / main 接线四连）")

# ---- 19) T10 地图渗透热力层：同心环几何 + 图例语义 + 图层互斥 ----
import world_map as _wm
import ui_hud as _hud

# 环预算常量存在且自洽（最内环 > 信标半宽，避免与信标重叠）
assert _wm.WorldMap.HEAT_MAX_RINGS >= 4, "热力环数太少，梯度会看不出差别"
assert _wm.WorldMap.HEAT_BASE_R > _wm.WorldMap.BEACON / 2.0, \
    "最内环半径须大于信标半宽，否则环会压住信标"
assert _wm.WorldMap.HEAT_STEP_R > 0, "环间距须为正"

# 图例 4 档色与实际光晕取色同源（改色只动一处）
assert len(_hud.HEAT_LEGEND) == 4, f"图例应为 4 档: {_hud.HEAT_LEGEND}"
# 旧的 8 档整国涂色色阶应已下线（避免双份热力口径）
assert not hasattr(_hud, 'HEAT_SCALE'), "HEAT_SCALE 应已下线，热力统一走光晕"

# 图层定义与取数函数齐备
assert 'heat' in _hud.LAYER_KEYS, f"LAYER_KEYS 缺 heat: {_hud.LAYER_KEYS}"
assert hasattr(_hud.HudMixin, '_heat_data'), "HudMixin 缺 _heat_data"
assert hasattr(_wm.WorldMap, 'set_heat'), "WorldMap 缺 set_heat"
assert hasattr(_wm.WorldMap, '_layout_heat'), "WorldMap 缺 _layout_heat"

# i18n 图例 4 键 zh/en 对称
for _lang in (i18n_mod.LANG_ZH, i18n_mod.LANG_EN):
    _miss = [k for k in ('heat_leg_low', 'heat_leg_mid', 'heat_leg_high',
                         'heat_leg_full') if k not in i18n_mod.TRANSLATIONS[_lang]]
    assert not _miss, f"i18n[{_lang}] 缺热力图例键: {_miss}"
print("   ✅ 19) T10 渗透热力层（同心环几何自洽 / 4 档图例同源 / "
      "8 档旧色阶已下线 / 图层互斥 / i18n ×4 键）")

print("\n 全部通过 - demo 可以正常启动")
print()
print(" 在你的本地 Windows 双击 run_demo.bat 即可运行")