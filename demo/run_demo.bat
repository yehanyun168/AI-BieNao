@echo off
REM AI Bienao Day 2 Demo - Smart Launcher
REM Pure ASCII to avoid GBK/UTF-8 encoding issues
chcp 65001 >nul 2>&1
title AI Bienao Day 2 Demo

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

%PYTHON_EXE% -c "import data, engine, tech_tree, i18n, country_events, flag_draw, world_map, pixel_ui, pixel_assets, ui_v4, ui_v4_screens, tutorial" >nul 2>&1
if errorlevel 1 goto :files_import_failed

echo   [OK] All 11 demo modules import successfully
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
echo   world_map.py, pixel_ui.py, pixel_assets.py, ui_v4.py, ui_v4_screens.py, tutorial.py
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