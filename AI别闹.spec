# -*- mode: python ; coding: utf-8 -*-
"""
AI别闹.spec - PyInstaller 配置文件

直接运行打包：
  pyinstaller AI别闹.spec

或者用 build_exe.py 包装：
  python tools/build_exe.py
"""
from kivy_deps import sdl2, glew, angle
import sys

block_cipher = None


# Kivy 资源 + demo 数据
a = Analysis(
    ['demo/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('demo/data.py', '.'),
        ('demo/engine.py', '.'),
        ('demo/tech_tree.py', '.'),
        ('demo/i18n.py', '.'),
        ('demo/country_events.py', '.'),
        ('demo/test_build.py', '.'),
        ('demo/README.md', '.'),
        # ⚠️ v2_events.py 运行时从磁盘读取，必须随包分发
        ('v2/events.json', '.'),
    ],
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