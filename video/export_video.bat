@echo off
chcp 65001 >nul
rem ============================================================
rem  一键合成 mp4：frames\f%06d.png  ->  out\AI-BieNao_Demo_1080p.mp4
rem  可选：同目录放 subtitles.srt（自动烧录字幕）
rem        audio\bgm.wav + audio\voice.wav（自动混音，BGM 压低到 25%）
rem  ffmpeg 查找顺序：同目录 ffmpeg.bat 转发器 -> PATH
rem ============================================================

cd /d "%~dp0"

set "FFMPEG=ffmpeg"
if exist "%~dp0ffmpeg.bat" set "FFMPEG=%~dp0ffmpeg.bat"

%FFMPEG% -version >nul 2>nul
if errorlevel 1 (
    echo [export_video.bat] 未找到 ffmpeg。
    echo   安装：winget install Gyan.FFmpeg
    echo   或下载 https://www.gyan.dev/ffmpeg/builds/ 后把 ffmpeg.exe 完整路径
    echo   写进同目录 ffmpeg.bat 的 FF 变量。
    exit /b 1
)

if not exist "frames\f000001.png" (
    echo [export_video.bat] 没有找到 frames\f000001.png
    echo   先运行：python export_frames.py
    exit /b 1
)

if not exist "out" mkdir "out"
set "OUT=out\AI-BieNao_Demo_1080p.mp4"

echo [export_video.bat] 开始合成 1920x1080 / 30fps / H.264 ...

rem ---- 分支 1：字幕 + 双音轨 ----
if exist "subtitles.srt" if exist "audio\bgm.wav" if exist "audio\voice.wav" (
    echo   挂字幕 + 混音 BGM/旁白
    %FFMPEG% -y -framerate 30 -i "frames\f%%06d.png" -i "audio\bgm.wav" -i "audio\voice.wav" -filter_complex "[1:a]volume=0.25[b];[b][2:a]amix=inputs=2:duration=first[a]" -map 0:v -map "[a]" -c:a aac -b:a 192k -vf "subtitles=subtitles.srt" -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium -movflags +faststart "%OUT%"
    goto :done
)

rem ---- 分支 2：字幕 + 仅旁白 ----
if exist "subtitles.srt" if exist "audio\voice.wav" (
    echo   挂字幕 + 旁白
    %FFMPEG% -y -framerate 30 -i "frames\f%%06d.png" -i "audio\voice.wav" -map 0:v -map 1:a -c:a aac -b:a 192k -vf "subtitles=subtitles.srt" -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium -movflags +faststart "%OUT%"
    goto :done
)

rem ---- 分支 3：字幕 + 仅 BGM ----
if exist "subtitles.srt" if exist "audio\bgm.wav" (
    echo   挂字幕 + BGM
    %FFMPEG% -y -framerate 30 -i "frames\f%%06d.png" -i "audio\bgm.wav" -map 0:v -map 1:a -c:a aac -b:a 192k -vf "subtitles=subtitles.srt" -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium -movflags +faststart "%OUT%"
    goto :done
)

rem ---- 分支 4：仅字幕 ----
if exist "subtitles.srt" (
    echo   挂字幕（无音轨）
    %FFMPEG% -y -framerate 30 -i "frames\f%%06d.png" -vf "subtitles=subtitles.srt" -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium -movflags +faststart "%OUT%"
    goto :done
)

rem ---- 分支 5：裸视频 ----
echo   无字幕无音轨（裸视频）
%FFMPEG% -y -framerate 30 -i "frames\f%%06d.png" -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium -movflags +faststart "%OUT%"

:done
if errorlevel 1 (
    echo [export_video.bat] 合成失败，请把上面的报错反馈给工程维护者。
    exit /b 1
)
echo.
echo [export_video.bat] 完成： %OUT%
for %%F in ("%OUT%") do echo   大小: %%~zF 字节
echo 请用播放器确认：时长约 178 秒、1080p、字幕在位。
