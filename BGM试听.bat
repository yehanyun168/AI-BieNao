@echo off
chcp 65001 >nul

cd /d "%~dp0"

set PY=C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe
set KIVY_NO_FILELOG=1
set KIVY_NO_ARGS=1

echo.
echo ============================================================
echo   BGM 候选试听 - tallbeard-chiptune（每首 20 秒）
echo ============================================================
echo.
echo   Python: %PY%
echo   目录  : %CD%
echo.

"%PY%" tools\audition_bgm.py --secs 20

echo.
echo ============================================================
echo   试听结束。请告诉 AI：哪首当 calm、哪首当 tense。
echo ============================================================
echo.
pause
