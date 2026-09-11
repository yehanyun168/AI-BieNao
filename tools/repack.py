"""
repack.py - 重新打包分享包（当前版本：20 国 / 6 技能 / 7 结局 / 22 成就）

用法：
  py -3.12 tools/repack.py

输出：
  share/AI_Bienao_v2_<时间戳>.zip
"""
import os
import sys
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

# 真实截图（主菜单 / 主界面 / 成就）
screenshot_files = [
    "demo/screenshot_menu.png",
    "demo/screenshot_game.png",
    "demo/screenshot_achievements.png",
]

# ---- demo/*.py 自动发现 ------------------------------------------------
# ⚠️ 历史教训：这份清单以前是**手写**的，新增模块（ui_fx / ui_input /
#    ui_drop / ui_hud / ui_modal / ui_popups / ui_pages / ui_shared /
#    ui_session / ui_commissions）时没人记得同步，导致分享包解压后
#    import 就崩 —— 而本地测试永远发现不了（本地有全部文件）。
#    现在改为扫描 demo/ 下所有 .py，仅排除明确不该入包的文件。
#    新增模块**不需要**改这里，只有"不想给别人看的"才加进 EXCLUDE。
DEMO_EXCLUDE = {
    "__init__.py",
    "conftest.py",            # 本机测试脚手架
}
DEMO_EXCLUDE_PREFIX = ("_t_", "_tmp_", "scratch_")   # 临时探针/试验脚本
DEMO_EXCLUDE_SUFFIX = ("_out.txt",)

# v2 事件数据（引擎运行时依赖：demo/v2_events.py 从磁盘读取）
# 2026-09-11：目录整理——原型期数据/规划稿（compute_system_demo、generate_v2_data、
# countries/tech_tree/game_data_v2.json、project_plan_v3、team_division）已清理，
# git 历史可追溯；仅保留运行时必需的 events.json
v2_files = [
    "v2/events.json",
]

# demo 非 .py 资产（源码目录之外仍需入包的资源）
demo_asset_files = [
    "demo/assets/sfx/click.wav",
    "demo/assets/sfx/select.wav",
    "demo/assets/sfx/cast.wav",
    "demo/assets/sfx/success.wav",
    "demo/assets/sfx/fail.wav",
    "demo/assets/sfx/crisis.wav",
    "demo/assets/sfx/end_win.wav",
    "demo/assets/sfx/end_lose.wav",
    "demo/diagnose.bat",
    "demo/run_demo.bat",
    "demo/run_demo.sh",
    "demo/README.md",
]


def _discover_demo_py(src_dir: str):
    """扫描 demo/*.py，返回相对路径清单（已按名排序，保证打包可复现）。"""
    demo_dir = os.path.join(src_dir, "demo")
    out = []
    for name in sorted(os.listdir(demo_dir)):
        if not name.endswith(".py"):
            continue
        if name in DEMO_EXCLUDE:
            continue
        if name.startswith(DEMO_EXCLUDE_PREFIX):
            continue
        if name.endswith(DEMO_EXCLUDE_SUFFIX):
            continue
        out.append("demo/" + name)
    return out

# 项目级文档 + 打包工具（文档已归类至 docs/，2026-09-11）
misc_files = [
    "README.md",
    "CONTRIBUTING.md",
    "docs/交付文档.md",
    "docs/DeepSeek_接手文档.md",
    "docs/游戏开发待办清单.md",
    "docs/WHERE_IS_EVERYTHING.md",
    "AI别闹.spec",
    "build_exe.bat",
    "tools/build_exe.py",
    "tools/gen_pixel_map.py",           # 地图重生成（Natural Earth 110m）
    "tools/gen_sfx.py",                 # 音效合成（CC0 WAV，无需联网）
    "tools/check_map_palette.py",       # 地图配色 vs 设计稿一致性校验
    "tools/repack.py",
    "tools/portable_build.md",
]

added = 0
missing = []

with zipfile.ZipFile(OUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    demo_py = _discover_demo_py(SRC_DIR)
    print(f"   自动发现 demo 源码: {len(demo_py)} 个 .py")
    for group in (v2_files, demo_py, demo_asset_files, screenshot_files,
                  misc_files):
        for rel_path in group:
            full_path = os.path.join(SRC_DIR, rel_path)
            if os.path.exists(full_path):
                z.write(full_path, f"{PKG}/{rel_path}")
                added += 1
            else:
                missing.append(rel_path)

# ---- 完整性自检：运行时必需的模块是否都在包里 -------------------------
# 光"文件存在"不够 —— 真正要保证的是「解压后能 import 起来」。
# 这里把入口链路的关键模块列出来，缺一个就明确报错，
# 避免"本地跑得好、别人解压就崩"的老问题复发。
REQUIRED_IN_PKG = [
    "demo/main.py",
    "demo/engine.py",
    "demo/ui_fx.py",
    "demo/ui_input.py",
    "demo/ui_drop.py",
    "demo/ui_hud.py",
    "demo/ui_shared.py",
    "demo/ui_v4.py",
    "demo/ui_v4_screens.py",
    "demo/ui_commissions.py",
    "demo/ui_pages.py",
    "demo/ui_modal.py",
    "demo/ui_popups.py",
    "demo/ui_session.py",
    "demo/world_map.py",
    "demo/pixel_assets.py",
    "demo/tutorial.py",
    "v2/events.json",
]

with zipfile.ZipFile(OUT_ZIP) as z:
    packaged = set(z.namelist())

absent = [p for p in REQUIRED_IN_PKG if f"{PKG}/{p}" not in packaged]
# 顺序无关的粗检：包内 demo/*.py 是否覆盖了源目录的全部 .py
src_py = set(_discover_demo_py(SRC_DIR))
pkg_py = {n.split("/", 2)[-1] for n in packaged
          if n.startswith(f"{PKG}/demo/") and n.endswith(".py")}
uncovered = sorted(src_py - {f"demo/{n}" for n in pkg_py})

size = os.path.getsize(OUT_ZIP)
print("\n✅ 打包完成")
print(f"   文件数: {added} 个")
print(f"   大小:   {size:,} 字节 ({size / 1024:.1f} KB)")
if missing:
    print(f"   ⚠️ 跳过 {len(missing)} 个不存在的文件: {', '.join(missing)}")

if absent:
    print(f"\n❌ 关键模块缺失 {len(absent)} 个 —— 分享包解压后可能无法运行：")
    for p in absent:
        print(f"     - {p}")
    sys.exit(1)
if uncovered:
    print(f"\n❌ demo/*.py 未被完整打包，缺失 {len(uncovered)} 个：")
    for p in uncovered:
        print(f"     - {p}")
    sys.exit(1)
print("   ✅ 完整性自检通过：关键模块齐全，demo/*.py 已全覆盖")
