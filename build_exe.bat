@echo off
chcp 65001 >nul
title AI 别闹 - Windows 打包工具

echo.
echo ============================================================
echo   AI 别闹 - Windows 打包工具
echo ============================================================
echo.

REM 切换到工作区根目录
cd /d "%~dp0.."

REM 智能选择 Python 3.12（不要用 3.14！）
set PYTHON_EXE=
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_EXE=py -3.12
        echo [Python] 使用 Python 3.12（推荐）
        py -3.12 --version
        goto :python_ready
    )
    py -3.13 --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_EXE=py -3.13
        echo [Python] 使用 Python 3.13（兼容性可能有问题）
        py -3.13 --version
        goto :python_ready
    )
)
where python >nul 2>&1
if errorlevel 1 (
    echo   ❌ 没找到 python，请安装 Python 3.12
    goto :end
)
set PYTHON_EXE=python
python --version

:python_ready
echo.

echo.
echo [2/5] 检查/安装 PyInstaller...
%PYTHON_EXE% -c "import PyInstaller; print('  ✅ PyInstaller', PyInstaller.__version__)" 2>nul
if errorlevel 1 (
    echo   正在安装 PyInstaller...
    %PYTHON_EXE% -m pip install pyinstaller --quiet
    if errorlevel 1 (
        echo   ❌ PyInstaller 安装失败
        goto :end
    )
)

echo.
echo [3/5] 选择打包模式...
echo   1. 单文件夹（启动快，杀软友好，推荐）
echo   2. 单 exe（分发便利，启动慢 5-10 秒）
echo.
set /p MODE=请输入 1 或 2：
if "%MODE%"=="1" (
    set PYI_MODE=onedir
) else if "%MODE%"=="2" (
    set PYI_MODE=onefile
) else (
    echo   ❌ 输入错误，默认使用单文件夹模式
    set PYI_MODE=onedir
)
echo   ✅ 模式：%PYI_MODE%

echo.
echo [4/5] 开始打包（首次打包约 5-10 分钟）...
%PYTHON_EXE% tools\build_exe.py --%PYI_MODE%

echo.
echo [5/5] 打包结果...
if exist dist\AI别闹.exe (
    echo   ✅ 单文件模式成功: dist\AI别闹.exe
    for %%A in ("dist\AI别闹.exe") do echo      体积: %%~zA 字节
) else if exist dist\AI别闹\AI别闹.exe (
    echo   ✅ 单文件夹模式成功: dist\AI别闹\
    for %%A in ("dist\AI别闹\AI别闹.exe") do echo      入口 exe: %%~zA 字节
    echo      整个文件夹: dist\AI别闹\（约 100-150 MB）
) else (
    echo   ❌ 打包失败，请看上面的错误
)

echo.
echo ============================================================
echo   下一步
echo ============================================================
echo.
echo 1. 测试：在 dist 目录里双击 AI别闹.exe 看能否正常启动
echo 2. 分发：把整个 dist/AI别闹/ 文件夹打成 zip 发给用户
echo 3. 备用：tools\portable_build.md 有便携版打包方法
echo.
goto :end

:end
echo.
pause