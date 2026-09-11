"""
repack.py - 重新打包分享包（当前版本：20 国 / 6 技能 / 7 结局 / 22 成就）

用法：
  py -3.12 tools/repack.py

输出：
  share/AI_Bienao_v2_<时间戳>.zip
"""
import os
import subprocess
import sys
import zipfile
from datetime import datetime

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARE_DIR = os.path.join(SRC_DIR, "share")

# 单次取时间戳：文件名与 VERSION.txt 的 built_at 必须同源，否则对不上账
NOW = datetime.now()
BUILT_AT = NOW.isoformat(timespec="seconds")

OUT_ZIP = os.path.join(
    SHARE_DIR, f"AI_Bienao_v2_{NOW.strftime('%Y%m%d_%H%M')}.zip")


# ---- 源码指纹（P0-1）--------------------------------------------------
# ⚠️ 历史教训：分享包曾与源码脱节 —— 包建于某次提交之前，之后又有
#    「大修 + 数值重平衡」「分层修复」两个提交没进包。发给真人测试
#    等于测旧版，回收的反馈全部作废。现在每个包强制写入 VERSION.txt，
#    任何一次解压都能立刻回答：这包是哪个 commit、干不干净、多少文件。
def _git(*args):
    """安全调用 git：任何失败都降级为 'unknown'，绝不让打包崩溃。

    git 可能没装、可能不在 PATH、仓库可能是纯压缩包解开的（没 .git），
    这些都不能成为「打不出包」的理由 —— 指纹降级，包照打，但要标出来。
    """
    try:
        r = subprocess.run(["git", *args], cwd=SRC_DIR,
                           capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return "unknown"
        return (r.stdout or "").strip() or "unknown"
    except Exception:
        return "unknown"


_commit = _git("rev-parse", "HEAD")
_commit_subject = _git("log", "-1", "--format=%s")
_status_out = _git("status", "--porcelain")
if _status_out == "":
    _dirty = "no"
elif _status_out == "unknown":
    _dirty = "unknown"
else:
    _dirty = "yes"

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
    "docs/真人测试指南.md",
    "docs/游戏项目改进优化计划书.md",
    "AI别闹.spec",
    "build_exe.bat",
    "tools/build_exe.py",
    "tools/gen_pixel_map.py",           # 地图重生成（Natural Earth 110m）
    "tools/gen_sfx.py",                 # 音效合成（CC0 WAV，无需联网）
    "tools/check_map_palette.py",       # 地图配色 vs 设计稿一致性校验
    "tools/repack.py",
    "tools/portable_build.md",
    # 提交守卫（P0-4）：.git/hooks 不随 clone 分发，故把钩子源码与
    # pre-commit 框架配置一并入包，新机器一条命令即可重建守卫。
    "tools/git-hooks/pre-commit",
    ".pre-commit-config.yaml",
]

added = 0
missing = []

with zipfile.ZipFile(OUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    demo_py = _discover_demo_py(SRC_DIR)
    print(f"   自动发现 demo 源码: {len(demo_py)} 个 .py")
    demo_py_added = 0
    for group in (v2_files, demo_py, demo_asset_files, screenshot_files,
                  misc_files):
        for rel_path in group:
            full_path = os.path.join(SRC_DIR, rel_path)
            if os.path.exists(full_path):
                z.write(full_path, f"{PKG}/{rel_path}")
                added += 1
                if group is demo_py:
                    demo_py_added += 1
            else:
                missing.append(rel_path)

    # VERSION.txt 必须最后写入 —— file_count 依赖「已写入的文件数」
    # （zipfile 以 'w' 模式打开时可以直接 writestr，无需重开文件）
    file_count = added + 1          # +1 = VERSION.txt 自己
    VERSION_TXT = (
        f"AI别闹 分享包版本指纹 / Package Fingerprint\n"
        f"========================================\n"
        f"commit: {_commit}\n"
        f"commit_subject: {_commit_subject}\n"
        f"built_at: {BUILT_AT}\n"
        f"dirty: {_dirty}\n"
        f"file_count: {file_count}\n"
        f"demo_py_count: {demo_py_added}\n"
        f"\n"
        f"说明 / Notes\n"
        f"-----------\n"
        f"- dirty=yes 表示打包时工作区有未提交改动，此包**无法**精确追溯到\n"
        f"  某一个 commit（commit 字段只代表当时的 HEAD），请勿用于真人测试。\n"
        f"- file_count 含 VERSION.txt 自身，可用 unzip -l 复核。\n"
        f"- 核对方式：在此文件所在目录执行 `git rev-parse HEAD`，\n"
        f"  与 commit 字段比对一致即为源码与包内容同步。\n"
    )
    z.writestr(f"{PKG}/VERSION.txt", VERSION_TXT)

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
print(f"   文件数: {file_count} 个")
print(f"   大小:   {size:,} 字节 ({size / 1024:.1f} KB)")
if missing:
    print(f"   ⚠️ 跳过 {len(missing)} 个不存在的文件: {', '.join(missing)}")

print(f"\n🔖 源码指纹（已写入 {PKG}/VERSION.txt）")
print(f"   commit:         {_commit}")
print(f"   commit_subject: {_commit_subject}")
print(f"   built_at:       {BUILT_AT}")
print(f"   dirty:          {_dirty}")
print(f"   file_count:     {file_count}")
print(f"   demo_py_count:  {demo_py_added}")

if _dirty == "yes":
    print("\n" + "!" * 66)
    print("❗❗ 警告：工作区是脏的（有未提交改动）❗❗")
    print("   此包无法精确追溯到某一个 commit —— VERSION.txt 里的 commit")
    print("   只代表打包那一刻的 HEAD，包内内容还含未提交的改动。")
    print("   → 请勿用于真人测试 / 外发；先 git commit 再重新打包。")
    print("!" * 66)
elif _dirty == "unknown":
    print("\n⚠️ 警告：无法读取 git 状态（git 不可用或不在仓库中）")
    print("   此包**没有**源码指纹，事后无法追溯。请确认 git 可用后重新打包。")

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

# ---- 特征串自检（P0-1）：「新改动是否真的进了包」变成可验证 ----------
# 上面只证明「文件在」；这个检查证明「改动在」。
# 这 4 条是本次脱节事故里**漏进包**的具体改动，做成断言防止复发。
# 以后每次重大修复合入，都建议往这里补一条对应的特征串。
FEATURE_MARKERS = [
    ("demo/balance.py", "sus_pressure_threshold",       "压力阈值平衡参数"),
    ("demo/data.py",    "suspicion_delta=10.0",         "take_cut 怀疑度 10.0"),
    ("demo/engine.py",  "player.pending_skill = skill_id", "pending_skill 归因修复"),
    ("demo/ui_v4.py",   "def hline",                    "hline 分层修复"),
]

with zipfile.ZipFile(OUT_ZIP) as z:
    missing_markers = []
    for rel_path, marker, desc in FEATURE_MARKERS:
        arcname = f"{PKG}/{rel_path}"
        try:
            content = z.read(arcname).decode("utf-8", errors="replace")
        except KeyError:
            missing_markers.append((rel_path, marker, desc, "文件不在包内"))
            continue
        if marker not in content:
            missing_markers.append((rel_path, marker, desc, "内容中未找到"))

print("\n🔍 特征串自检（新改动是否入包）")
for rel_path, marker, desc in FEATURE_MARKERS:
    hit = not any(m[0] == rel_path and m[1] == marker
                  for m in missing_markers)
    print(f"   {'✅' if hit else '❌'} {rel_path:<18} {marker:<32} ({desc})")

if missing_markers:
    print(f"\n❌ 包内缺少 {len(missing_markers)} 项预期改动 —— "
          f"包内容与源码脱节，禁止外发：")
    for rel_path, marker, desc, why in missing_markers:
        print(f"     - {rel_path} 缺 `{marker}`（{desc}）：{why}")
    sys.exit(1)
print("   ✅ 特征串自检通过：4 项改动全部在包内")
