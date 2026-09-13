@echo off
chcp 65001 >nul

cd /d "%~dp0"

set PY=C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe
set KIVY_NO_FILELOG=1
set KIVY_NO_ARGS=1

echo.
echo ============================================================
echo   音效试听器 - pixel-ui-sfx
echo ============================================================
echo.
echo   Python: %PY%
echo   目录  : %CD%
echo.

"%PY%" tools\audition_pixel_batch.py

echo.
echo ============================================================
echo   试听结束。请把「编号 -^> 适合什么场景」告诉 AI。
echo ============================================================
echo.
pause
