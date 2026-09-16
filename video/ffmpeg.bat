@echo off
rem ffmpeg 转发器 —— 本机 ffmpeg 由 winget 安装但符号链接创建失败，未进 PATH。
rem 本文件与 export_video.bat 同目录，因此在 video/ 下调用 "ffmpeg" 会优先命中这里。
rem 若日后 ffmpeg 正常进 PATH（或在别处安装），可直接删除本文件。

set "FF=C:\Users\tianm\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"

if exist "%FF%" (
    "%FF%" %*
    exit /b %ERRORLEVEL%
)

rem 兜底：尝试 PATH 里的 ffmpeg
where ffmpeg >nul 2>nul
if %ERRORLEVEL%==0 (
    ffmpeg %*
    exit /b %ERRORLEVEL%
)

echo [ffmpeg.bat] 未找到 ffmpeg。
echo 请安装：winget install Gyan.FFmpeg
echo 或把 ffmpeg.exe 路径写进本文件的 FF 变量。
exit /b 1
