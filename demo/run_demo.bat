@echo off
REM AI Bienao Day 2 Demo - Smart Launcher
REM Pure ASCII to avoid GBK/UTF-8 encoding issues
chcp 65001 >nul 2>&1
title AI Bienao Day 2 Demo

REM ============================================================
REM CRITICAL (P0-7): disable Kivy file logging. DO NOT REMOVE.
REM ============================================================
REM Kivy runs file_log_handler.purge_logs() at IMPORT time, deleting old
REM files under ~/.kivy/logs/. On some Windows machines that folder is
REM protected, so Kivy's safe-delete throws:
REM     OSError: [safe-delete] operation failed
REM and the game dies BEFORE any window ever opens.
REM
REM Why this is a TIME BOMB, not an ordinary bug:
REM   * The FIRST launch is usually fine - there are no old logs to purge yet.
REM   * It only fires AFTER several sessions, once history logs pile up.
REM   * Symptom: "played fine for days, then suddenly won't start" - and the
REM     player has no way to diagnose it.
REM   * That lands exactly inside the M1 playtest window (3+ friends).
REM
REM Set here, BEFORE Step 1, on purpose: the very first probe below already
REM runs "import kivy", which triggers purge_logs() all by itself - setting
REM this any later is too late. main.py additionally calls
REM os.environ.setdefault() as a fallback for IDE / direct double-click
REM launches that never go through this script.
set KIVY_NO_FILELOG=1

echo.
echo ============================================================
echo   AI Bienao - Day 2 Demo
echo ============================================================
echo.

REM ============================================================
REM Step 1: Find a Python that has Kivy installed
REM ============================================================
echo [Step 1/4] Looking for Python with Kivy...
echo.

set PYTHON_EXE=

REM Test each candidate one by one (avoids batch delayed expansion issues)

py -3.12 -c "import kivy" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_EXE=py -3.12
    set PYTHON_LABEL=Python 3.12
    goto :found_python
)

py -3.11 -c "import kivy" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_EXE=py -3.11
    set PYTHON_LABEL=Python 3.11
    goto :found_python
)

py -3.10 -c "import kivy" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_EXE=py -3.10
    set PYTHON_LABEL=Python 3.10
    goto :found_python
)

py -c "import kivy" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_EXE=py
    set PYTHON_LABEL=Python (default py launcher)
    goto :found_python
)

python -c "import kivy" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_EXE=python
    set PYTHON_LABEL=Python (PATH)
    goto :found_python
)

python3 -c "import kivy" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_EXE=python3
    set PYTHON_LABEL=Python 3
    goto :found_python
)

REM ============================================================
REM No Python with Kivy found - give clear instructions
REM ============================================================
echo.
echo ============================================================
echo   [ERROR] No Python with Kivy found!
echo ============================================================
echo.
echo You said you have Python 3.12 and 3.14.
echo Kivy 2.3.1 does NOT support Python 3.13 or 3.14.
echo Kivy probably did not install on any of your Pythons.
echo.
echo Pick ONE solution:
echo.
echo   A) Install Kivy on your Python 3.12:
echo      py -3.12 -m pip install kivy[base]
echo.
echo   B) Install Python 3.11 (most stable for Kivy):
echo      https://www.python.org/downloads/release/python3119/
echo      Then: py -3.11 -m pip install kivy[base]
echo.
echo After installing, run this script again.
echo ============================================================
echo.
pause
exit /b 1

:found_python
echo   [OK] Found: %PYTHON_EXE% (%PYTHON_LABEL%)
echo.

REM ============================================================
REM Step 2: Check Kivy dependencies
REM ============================================================
echo [Step 2/4] Checking Kivy dependencies (SDL2/GLEW/ANGLE)...

%PYTHON_EXE% -c "from kivy_deps import sdl2" >nul 2>&1
if errorlevel 1 (
    echo   [WARN] kivy_deps.sdl2 missing - installing...
    %PYTHON_EXE% -m pip install kivy_deps.sdl2 --quiet
)

%PYTHON_EXE% -c "from kivy_deps import glew" >nul 2>&1
if errorlevel 1 (
    echo   [WARN] kivy_deps.glew missing - installing...
    %PYTHON_EXE% -m pip install kivy_deps.glew --quiet
)

%PYTHON_EXE% -c "from kivy_deps import angle" >nul 2>&1
if errorlevel 1 (
    echo   [WARN] kivy_deps.angle missing - installing...
    %PYTHON_EXE% -m pip install kivy_deps.angle --quiet
)

echo   [OK] Dependencies ready
echo.

REM ============================================================
REM Step 3: Verify demo files
REM ============================================================
echo [Step 3/4] Verifying demo files...

if not exist "data.py" goto :files_missing
if not exist "engine.py" goto :files_missing
if not exist "main.py" goto :files_missing
if not exist "tech_tree.py" goto :files_missing
if not exist "i18n.py" goto :files_missing
if not exist "country_events.py" goto :files_missing
if not exist "flag_draw.py" goto :files_missing
if not exist "world_map.py" goto :files_missing
if not exist "pixel_ui.py" goto :files_missing
if not exist "pixel_assets.py" goto :files_missing
if not exist "ui_v4.py" goto :files_missing
if not exist "ui_v4_screens.py" goto :files_missing
if not exist "tutorial.py" goto :files_missing

REM --- modules added after the original v0.4 checklist (P0-7) ---
if not exist "ui_commissions.py" goto :files_missing
if not exist "ui_fx.py" goto :files_missing
if not exist "ui_input.py" goto :files_missing
if not exist "ui_drop.py" goto :files_missing
if not exist "ui_hud.py" goto :files_missing
if not exist "ui_shared.py" goto :files_missing
if not exist "ui_modal.py" goto :files_missing
if not exist "ui_pages.py" goto :files_missing
if not exist "ui_popups.py" goto :files_missing
if not exist "ui_session.py" goto :files_missing
if not exist "save_manager.py" goto :files_missing
if not exist "balance.py" goto :files_missing
if not exist "conditions.py" goto :files_missing
if not exist "commissions.py" goto :files_missing
if not exist "endings.py" goto :files_missing
if not exist "achievements.py" goto :files_missing
if not exist "sfx.py" goto :files_missing
if not exist "v2_events.py" goto :files_missing

REM v2/events.json is a RUNTIME data dependency (the v2 event library).
REM Missing it does NOT crash the game - v2_events.py only warns and runs with
REM an EMPTY event pool - so this is a warning, not a hard stop: refusing to
REM launch is worse than a degraded session, and the path differs when packaged.
if not exist "..\v2\events.json" (
    echo   [WARN] ..\v2\events.json NOT found - v2 event library will be EMPTY
    echo         The game still starts, but v2 choice events will not appear.
)

%PYTHON_EXE% -c "import data, engine, tech_tree, i18n, country_events, flag_draw, world_map, pixel_ui, pixel_assets, ui_v4, ui_v4_screens, tutorial, ui_commissions, ui_fx, ui_input, ui_drop, ui_hud, ui_shared, ui_modal, ui_pages, ui_popups, ui_session, save_manager, balance, conditions, commissions, endings, achievements, sfx, v2_events" >nul 2>&1
if errorlevel 1 goto :files_import_failed

echo   [OK] All 30 demo modules import successfully
echo.

REM ============================================================
REM Step 4: Launch the game
REM ============================================================
echo [Step 4/4] Launching game...
echo.
echo   Game window will open. Press Ctrl+C to quit.
echo   If it crashes, check last_run.log below.
echo.

%PYTHON_EXE% main.py > last_run.log 2>&1
set GAME_EXITCODE=%errorlevel%

echo.
echo ============================================================
echo   Game exited (code %GAME_EXITCODE%)
echo ============================================================
echo.
echo ===== Last 30 lines of demo\last_run.log =====
powershell -NoProfile -Command "Get-Content -Path 'last_run.log' -Tail 30"
echo ===== End of log =====
echo.
echo If you see a Python error above, copy it and send to the developer.
echo.
pause
exit /b %GAME_EXITCODE%

:files_missing
echo.
echo ============================================================
echo   [ERROR] Demo files missing!
echo ============================================================
echo.
echo Expected files in this folder:
echo   data.py, engine.py, main.py, tech_tree.py, i18n.py, country_events.py, flag_draw.py,
echo   world_map.py, pixel_ui.py, pixel_assets.py, ui_v4.py, ui_v4_screens.py, tutorial.py,
echo   ui_commissions.py, ui_fx.py, ui_input.py, ui_drop.py, ui_hud.py, ui_shared.py,
echo   ui_modal.py, ui_pages.py, ui_popups.py, ui_session.py, save_manager.py,
echo   balance.py, conditions.py, commissions.py, endings.py, achievements.py,
echo   sfx.py, v2_events.py
echo.
echo Current folder: %CD%
echo.
echo You probably ran this script from the wrong folder.
echo Right-click run_demo.bat -^> "Run in folder" -^> open from demo folder
echo ============================================================
echo.
pause
exit /b 1

:files_import_failed
echo.
echo ============================================================
echo   [ERROR] Demo modules exist but cannot import!
echo ============================================================
echo.
echo This usually means Kivy or its deps are broken.
echo.
echo Try this:
echo   %PYTHON_EXE% -m pip install --upgrade kivy[base]
echo   %PYTHON_EXE% -m pip install --force-reinstall kivy_deps.sdl2 kivy_deps.glew kivy_deps.angle
echo.
echo Then run this script again.
echo ============================================================
echo.
pause
exit /b 1