@echo off
chcp 65001 >nul
rem 一键预览：用 Edge 应用模式打开播放器（1920x1080、无地址栏，最接近成片观感）
rem 若 Edge 不在默认路径，回退用系统默认浏览器打开。

set "EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
set "URL=file:///%~dp0index.html"

if exist "%EDGE%" (
    start "" "%EDGE%" --app="%URL%" --window-size=1920,1080 --new-window
) else (
    echo [preview.bat] 未找到 Edge，使用默认浏览器打开...
    start "" "%URL%"
)

rem 若画面提示「未加载到分镜数据」，先运行：
rem   python build_data.py
rem 以生成 shots.js / narration.js
