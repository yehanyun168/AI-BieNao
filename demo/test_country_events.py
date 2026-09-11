"""验证国家专属事件能正常触发"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine
import country_events as ce
import i18n

engine.init_game()

# 强制让中国达到 200M+ 以便触发算法备案
engine.player_countries[0].downloads_m = 250.0  # 中国

print(f"中国下载量: {engine.player_countries[0].downloads_m}M\n")

print("触发 50 次循环，看国家事件能否出现:\n")
country_event_hits = []
for i in range(50):
    report = engine.tick_one_round()
    for evt, _ in report["events"]:
        if isinstance(evt, ce.CountryEvent):
            country_event_hits.append((i, evt.id, evt.country_code))

if country_event_hits:
    print(f" 共触发 {len(country_event_hits)} 次国家专属事件:")
    for tick, eid, cc in country_event_hits:
        evt_obj = next(e for e in ce.COUNTRY_EVENTS if e.id == eid)
        print(f"  周期 {tick:>2}: [{cc}] {evt_obj.title_zh} ({evt_obj.title_en})")
else:
    print(" 50 周期未触发国家事件（检查概率和阈值）")

# 测试 i18n 切换
print(f"\n 当前语言: {i18n.get_lang()}")
print(f"  算法备案消息 zh: {ce.get_event_message(ce.COUNTRY_EVENTS[0], 'zh')}")
print(f"  算法备案消息 en: {ce.get_event_message(ce.COUNTRY_EVENTS[0], 'en')}")
i18n.set_lang('en')
print(f"  切换到 en 后: {ce.get_event_message(ce.COUNTRY_EVENTS[0], 'en')}")