"""
build_exe.py - PyInstaller 打包脚本

用法：
  1. 装 PyInstaller: pip install pyinstaller
  2. 跑: python build_exe.py
  3. 输出: dist/AI别闹.exe (单文件) 或 dist/AI别闹/ (单文件夹)

可选参数：
  --onedir    单文件夹（启动更快，杀软友好，推荐）
  --onefile   单 exe（分发更便利，启动慢 5-10 秒）
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path


DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
ROOT_DIR = DEMO_DIR.parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"


def clean():
    """清理之前的打包产物。

    删除失败时（例如被安全删除类工具拦截）降级为改名，而不是中断整个构建流程。
    """
    for d in [DIST_DIR, BUILD_DIR]:
        if not d.exists():
            continue
        try:
            shutil.rmtree(d)
            print(f"  清理 {d}")
        except Exception as e:
            backup = d.with_name(d.name + ".old")
            try:
                if backup.exists():
                    shutil.rmtree(backup, ignore_errors=True)
                d.rename(backup)
                print(f"  ⚠️ 无法删除 {d}（{e}），已改名为 {backup.name}")
            except Exception as e2:
                print(f"  ⚠️ 清理 {d} 失败，继续构建：{e2}")


def build(mode='onedir'):
    """打包"""
    print(f"🚀 开始打包（模式: {mode}）...")

    # PyInstaller 命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        f'--name=AI别闹',
        '--noconfirm',
        '--clean',
        # 添加 demo 目录的所有数据文件
        '--add-data', f'{DEMO_DIR}/data.py;.',
        '--add-data', f'{DEMO_DIR}/engine.py;.',
        '--add-data', f'{DEMO_DIR}/tech_tree.py;.',
        '--add-data', f'{DEMO_DIR}/i18n.py;.',
        '--add-data', f'{DEMO_DIR}/country_events.py;.',
        '--add-data', f'{DEMO_DIR}/test_build.py;.',
        # ⚠️ 运行时由 v2_events.py 从磁盘读取，必须随包分发（缺失会静默丢掉 37 条事件）
        '--add-data', f'{ROOT_DIR}/v2/events.json;.',
        # ⚠️ 音效资源：整目录随包（P0-6）。目标路径 assets/sfx 必须对齐
        #    demo/sfx.py::_base_dir() 的 os.path.join(sys._MEIPASS, 'assets', 'sfx')，
        #    对不上会导致 exe 形态 8 个音效全哑且不报错。
        '--add-data', f'{DEMO_DIR}/assets/sfx;assets/sfx',
        # ⚠️ BGM 资源：同样整目录随包（T09）。目标路径 assets/bgm 必须对齐
        #    demo/bgm.py::_base_dir() 的 os.path.join(sys._MEIPASS, 'assets', 'bgm')，
        #    对不上会导致 exe 形态 BGM 全哑且不报错（与 sfx 同一坑）。
        '--add-data', f'{DEMO_DIR}/assets/bgm;assets/bgm',
        # 注意：不要用 --collect-all kivy —— 它会让 collect_submodules 扫描
        # kivy.garden 这个命名空间包并抛 ValueError。PyInstaller 自带 hook-kivy.py
        # 已会委托 Kivy 官方钩子收集资源/依赖，无需手动 collect。
        # 图标（如果有）
        # '--icon=ai_bienao.ico',
        # 隐藏控制台（发布版用）
        # '--noconsole',
        # 模式
        f'--{mode}',
        # 产物路径：显式指定，避免落到 cwd(demo/) 下；
        # specpath 也指向 build/，避免覆盖根目录手写的 AI别闹.spec
        '--distpath', str(DIST_DIR),
        '--workpath', str(BUILD_DIR),
        '--specpath', str(BUILD_DIR),
        # 入口
        f'{DEMO_DIR}/main.py',
    ]

    print(f"  命令: {' '.join(cmd[:5])}...")
    # 构建期禁用 Kivy 文件日志：否则 PyInstaller 子进程 import kivy.graphics 时
    # 会触发日志轮转，一旦删除失败（或被安全删除工具拦截）就抛 OSError，
    # 导致 Kivy 官方钩子静默降级（hiddenimports 4 个、kivy/data 字体不打包）。
    env = dict(os.environ)
    env['KIVY_NO_FILELOG'] = '1'
    result = subprocess.run(cmd, cwd=str(DEMO_DIR), env=env)

    if result.returncode != 0:
        print("❌ 打包失败！")
        return False

    if mode == 'onefile':
        exe_path = DIST_DIR / "AI别闹.exe"
    else:
        exe_path = DIST_DIR / "AI别闹" / "AI别闹.exe"

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print(f"✅ 打包成功: {exe_path}")
        print(f"   体积: {size_mb:.1f} MB")
        return True
    else:
        print(f"❌ 找不到输出: {exe_path}")
        return False


def create_portable_zip():
    """方案 C：便携 Python zip（不需要 PyInstaller）"""
    print(f"\n📦 方案 C：便携 Python zip")
    print(f"   把 Python 解释器 + Kivy + demo 打包成自解压 zip")
    print(f"   用户解压后双击 run.bat 即可玩")
    print(f"   见 portable_build.md 详细步骤")


if __name__ == "__main__":
    mode = 'onedir'
    if '--onefile' in sys.argv:
        mode = 'onefile'
    elif '--onedir' in sys.argv:
        mode = 'onedir'

    print("=" * 60)
    print("  AI 别闹 打包工具")
    print("=" * 60)
    print(f"\n当前模式: {mode}")
    print(f"demo 目录: {DEMO_DIR}")
    print()

    clean()
    success = build(mode)

    if success:
        print("\n" + "=" * 60)
        print("✅ 打包完成！")
        print("=" * 60)
        if mode == 'onefile':
            print(f"\n📁 单 exe: {DIST_DIR}/AI别闹.exe")
            print(f"   分发给用户：把这个 exe 发出去就行")
        else:
            print(f"\n📁 单文件夹: {DIST_DIR}/AI别闹/")
            print(f"   整个文件夹打成 zip 发给用户")
            print(f"   用户解压后双击 AI别闹/AI别闹.exe")
        print()
        print("🛟 备用方案：便携 Python zip")
        print("   见 tools/portable_build.md")
    else:
        print("\n" + "=" * 60)
        print("❌ 打包失败，请看上面的错误信息")
        print("=" * 60)