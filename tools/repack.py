"""
repack.py - 重新打包分享包（当前版本：20 国 / 6 技能 / 7 结局 / 20 成就）

用法：
  py -3.12 tools/repack.py

输出：
  share/AI_Bienao_v2_<时间戳>.zip
"""
import os
import zipfile
from datetime import datetime

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARE_DIR = os.path.join(SRC_DIR, "share")
OUT_ZIP = os.path.join(
    SHARE_DIR, f"AI_Bienao_v2_{datetime.now().strftime('%Y%m%d_%H%M')}.zip")

os.makedirs(SHARE_DIR, exist_ok=True)
if os.path.exists(OUT_ZIP):
    os.remove(OUT_ZIP)

print("📦 重新打包分享包...")
print(f"   源目录: {SRC_DIR}")
print(f"   输出:   {OUT_ZIP}")

# 顶层分组目录（解压后同伴看到的结构）
PKG = "AI别闹_项目方案_v2"

# v2 方案文档与数据
# 2026-09-10：project_plan_v2.html（Day1 口径）已清理，改用当前口径的 v3 计划书
v2_files = [
    "v2/project_plan_v3.html",
    "v2/team_division.html",
    "v2/game_data_v2.json",
    "v2/countries.json",
    "v2/tech_tree.json",
    "v2/events.json",
    "v2/compute_system_demo.py",
    "v2/generate_v2_data.py",
]

# demo 全部源码（20 国 / 6 技能 / 7 结局 / 20 成就）
demo_files = [
    "demo/data.py",                     # 20 国 + polygon + 6 技能 + 通用事件
    "demo/tech_tree.py",                # 6 槽位 × 3 分支 × 3 级
    "demo/engine.py",                   # 主循环 + 阻止 + 偷算力 + 事件 + 结局 + 成就
    "demo/i18n.py",                     # 中英双语
    "demo/country_events.py",           # 20 国专属事件（27 条）
    "demo/v2_events.py",                # v2/events.json 适配器（37 条选择型事件）
    "demo/endings.py",                  # 7 种结局判定
    "demo/achievements.py",             # 20 个成就（13 条件 + 7 事件）
    "demo/save_manager.py",             # 存档 / 读档
    "demo/balance_sim.py",              # 数值平衡模拟器
    "demo/flag_draw.py",                # 程序化像素国旗绘制（20 面）
    "demo/world_map.py",                # 360x180 像素世界地图（Miller 投影，3x 重生成）
    "demo/pixel_ui.py",                 # 像素风组件库
    "demo/pixel_assets.py",             # ⭐ 像素地图/国旗资源（world_map+flag_draw 的依赖，勿删）
    "demo/ui_v4.py",                    # ⭐ v0.4 组件库（main.py 依赖，勿删）
    "demo/ui_v4_screens.py",            # ⭐ v0.4 页面级组装（检视卡/投放/技能页/科技树…，勿删）
    "demo/tutorial.py",                 # ⭐ 新手引导步骤机（main.py 依赖，勿删）
    "demo/sfx.py",                      # 音效管理器（失败安全，CC0 合成 WAV）
    "demo/assets/sfx/click.wav",
    "demo/assets/sfx/select.wav",
    "demo/assets/sfx/cast.wav",
    "demo/assets/sfx/success.wav",
    "demo/assets/sfx/fail.wav",
    "demo/assets/sfx/crisis.wav",
    "demo/assets/sfx/end_win.wav",
    "demo/assets/sfx/end_lose.wav",
    "demo/main.py",                     # 入口（RootView / MainMenu / GameUI）
    "demo/make_screenshots.py",         # 真机截图生成（README 用的 3 张图）
    "demo/make_screenshots_v4.py",      # v0.4 真机 14 屏截图
    "demo/verify_v4_shots.py",          # v0.4 截图配色令牌核对（PIL 程序化）
    "demo/test_build.py",               # 12 项回归断言
    "demo/test_ui_v4.py",               # v0.4 组件库单元自测
    "demo/test_v4_app.py",              # v0.4 十四屏冒烟测试
    "demo/test_country_events.py",
    "demo/legacy/render_map_preview.py",       # 早期离线预览（已废弃，仅追溯）
    "demo/legacy/render_pixel_ui_preview.py",  # 早期离线手稿（已废弃，仅追溯）
    "demo/legacy/README.md",
    "demo/diagnose.bat",                # 故障排查
    "demo/run_demo.bat",
    "demo/run_demo.sh",
    "demo/README.md",
]

# 真实截图（主菜单 / 主界面 / 成就）
screenshot_files = [
    "demo/screenshot_menu.png",
    "demo/screenshot_game.png",
    "demo/screenshot_achievements.png",
]

# 项目级文档 + 打包工具
misc_files = [
    "README.md",
    "WHERE_IS_EVERYTHING.md",
    "AI别闹.spec",
    "build_exe.bat",
    "tools/build_exe.py",
    "tools/gen_pixel_map.py",           # 地图重生成（Natural Earth 110m）
    "tools/gen_sfx.py",                 # 音效合成（CC0 WAV，无需联网）
    "tools/repack.py",
    "tools/portable_build.md",
]

added = 0
missing = []

with zipfile.ZipFile(OUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for group in (v2_files, demo_files, screenshot_files, misc_files):
        for rel_path in group:
            full_path = os.path.join(SRC_DIR, rel_path)
            if os.path.exists(full_path):
                z.write(full_path, f"{PKG}/{rel_path}")
                added += 1
            else:
                missing.append(rel_path)

size = os.path.getsize(OUT_ZIP)
print("\n✅ 打包完成")
print(f"   文件数: {added} 个")
print(f"   大小:   {size:,} 字节 ({size / 1024:.1f} KB)")
if missing:
    print(f"   ⚠️ 跳过 {len(missing)} 个不存在的文件: {', '.join(missing)}")
