# -*- mode: python ; coding: utf-8 -*-
"""
AI别闹.spec - PyInstaller 配置文件

直接运行打包：
  pyinstaller AI别闹.spec

或者用 build_exe.py 包装：
  python tools/build_exe.py
"""
from kivy_deps import sdl2, glew, angle
import glob
import os
import sys

block_cipher = None


# ---------------------------------------------------------------------------
# 随包资源 datas（P0-6 整改）
#
# 三条规则，避免「新增资源忘了同步 spec」的静默失效重演：
#   1. 资源按【整个目录】携带：demo/assets/sfx -> assets/sfx。
#      ⚠️ 目标路径 assets/sfx 必须与 demo/sfx.py::_base_dir() 打包态的
#         os.path.join(sys._MEIPASS, 'assets', 'sfx') 严格一致，
#         两者对不上 = 加了也白加（缺音效还不报错）。
#   2. demo 下的 .py 用 glob 自动生成（仅标准库），新增模块自动随包；
#      纯开发/测试工具按前缀排除，不进发行包。
#   3. _EXPLICIT_DATAS 是历史显式条目，原样保留，glob 结果自动去重。
# ---------------------------------------------------------------------------
_EXPLICIT_DATAS = [
    ('demo/data.py', '.'),
    ('demo/engine.py', '.'),
    ('demo/tech_tree.py', '.'),
    ('demo/i18n.py', '.'),
    ('demo/country_events.py', '.'),
    ('demo/test_build.py', '.'),
    ('demo/README.md', '.'),
    # ⚠️ v2_events.py 运行时从磁盘读取，必须随包分发
    ('v2/events.json', '.'),
]

# 纯开发/测试工具不随包分发（按前缀过滤，比逐个列举更不容易漏）
_DEV_PREFIXES = ('test_', 'verify_', 'make_screenshots')

_SFX_SRC = 'demo/assets/sfx'
_SFX_DST = 'assets/sfx'   # 对齐 demo/sfx.py::_base_dir()

# 构建期自检：缺 wav 直接中止打包，而不是静默产出一个「哑掉」的 exe
_SFX_FILES = sorted(glob.glob(_SFX_SRC + '/*.wav'))
if not _SFX_FILES:
    raise SystemExit(
        '[spec] 打包中止：%s 下没有找到任何 .wav（当前工作目录=%s）'
        % (_SFX_SRC, os.getcwd())
    )


def _norm(p):
    """路径分隔符统一为 /（Windows 下 glob/os.path 会返回 \\）。"""
    return p.replace('\\', '/')


_auto_py = [
    (_norm(p), '.')
    for p in sorted(glob.glob('demo/*.py'))
    if not os.path.basename(p).startswith(_DEV_PREFIXES)
]

_seen_src = {_norm(src) for src, _dst in _EXPLICIT_DATAS}
datas = (
    _EXPLICIT_DATAS
    + [e for e in _auto_py if e[0] not in _seen_src]
    + [(_SFX_SRC, _SFX_DST)]   # 音效：整目录携带，8 个 wav 自动跟随
)

print('[spec] 随包音效：%d 个 wav -> %s（%s）'
      % (len(_SFX_FILES), _SFX_DST, ', '.join(os.path.basename(f) for f in _SFX_FILES)))
print('[spec] datas 条目合计：%d（显式 %d + 自动 %d + 音效目录 1）'
      % (len(datas), len(_EXPLICIT_DATAS), len(datas) - len(_EXPLICIT_DATAS) - 1))

# Kivy 资源 + demo 数据
a = Analysis(
    ['demo/main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'kivy',
        'kivy.core',
        'kivy.core.window',
        'kivy.core.text',
        'kivy.core.image',
        'kivy.uix.boxlayout',
        'kivy.uix.gridlayout',
        'kivy.uix.button',
        'kivy.uix.label',
        'kivy.uix.scrollview',
        'kivy.uix.popup',
        'kivy.uix.floatlayout',
        'kivy.clock',
        'kivy.graphics',
        'kivy.core.window.window_sdl2',
        'kivy.core.text.text_sdl2',
        'kivy.core.image.img_sdl2',
        # demo 模块
        'data',
        'engine',
        'tech_tree',
        'i18n',
        'country_events',
        'v2_events',
        'endings',
        'achievements',
        'save_manager',
        'flag_draw',
        'world_map',
        'pixel_ui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy', 'pandas', 'matplotlib', 'scipy', 'PIL',
        'PyQt5', 'PyQt6', 'wx', 'gtk',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI别闹',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口（游戏窗口模式）
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='ai_bienao.ico',  # 如果有图标就启用
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AI别闹',
)