@echo off

rem ============================================================
rem  《AI 别闹》一键启动 —— 直接跑 demo/ 下的最新源码
rem  别名：与「启动游戏_源码最新版.bat」等价，方便习惯叫 run_demo 的用户
rem  注意：dist\ / share\ 里的旧 exe 是 2026-09-12 的快照，已过期，
rem        若想试玩最新功能（含「返回主菜单」按钮 / 新音效 / UI 改动），
rem        请双击本文件，不要双击旧 exe。
rem ============================================================

cd /d "%~dp0demo"

set PY=C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe
set KIVY_NO_FILELOG=1

if not exist "%PY%" (
    echo [错误] 找不到 Python 解释器：%PY%
    echo 请确认路径，或修改本文件里的 PY 变量。
    pause
    exit /b 1
)

"%PY%" main.py

echo.
echo ============================================================
echo   游戏已退出。
echo ============================================================
pause
