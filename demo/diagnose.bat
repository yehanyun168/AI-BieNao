@echo off
chcp 65001 >nul
title AI 别闹 demo 诊断工具

echo.
echo ============================================================
echo   AI 别闹 Demo 一键诊断工具
echo ============================================================
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"

echo [1/6] 检测 Python 版本...
where python >nul 2>&1
if errorlevel 1 (
    echo   ❌ 没找到 python 命令！
    echo   解决：安装 Python 3.11-3.12（不要 3.13，Kivy 兼容性差）
    echo         下载：https://www.python.org/downloads/
    goto :end
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   ✅ Python %PYVER%

echo.
echo [2/6] 检查 demo 文件完整性...
set MISSING=0
for %%f in (data.py engine.py main.py tech_tree.py i18n.py country_events.py) do (
    if not exist "%%f" (
        echo   ❌ 缺少 demo\%%f
        set MISSING=1
    )
)
if %MISSING%==0 echo   ✅ 8 个 demo 文件完整

echo.
echo [3/6] 检查 Kivy...
python -c "import kivy; print('  ✅ Kivy', kivy.__version__, '已安装')" 2>nul
if errorlevel 1 (
    echo   ⚠️  Kivy 未安装
    echo.
    echo   正在尝试安装（约 2-3 分钟）...
    python -m pip install --upgrade pip --quiet 2>nul
    python -m pip install kivy[base] --quiet
    if errorlevel 1 (
        echo   ❌ pip install kivy 失败！
        echo.
        echo   常见原因：
        echo   - 网络问题（试试国内镜像：pip install kivy -i https://pypi.tuna.tsinghua.edu.cn/simple/）
        echo   - Python 3.13 兼容性问题（装 Python 3.11 或 3.12）
        echo.
        goto :end
    )
    echo   ✅ Kivy 安装完成
)

echo.
echo [4/6] 检查 Kivy 依赖（SDL2/GLEW/ANGLE）...
python -c "import kivy_deps.sdl2; print('  ✅ SDL2 OK')" 2>nul || echo   ❌ SDL2 缺失
python -c "import kivy_deps.glew; print('  ✅ GLEW OK')" 2>nul || echo   ❌ GLEW 缺失
python -c "import kivy_deps.angle; print('  ✅ ANGLE OK')" 2>nul || echo   ❌ ANGLE 缺失

echo.
echo [5/6] 运行烟雾测试（验证代码逻辑）...
python test_build.py 2>nul
if errorlevel 1 (
    echo   ❌ 烟雾测试失败！上面有具体错误信息
    echo.
    echo   最常见原因：
    echo   - import 错误：某个文件缺失
    echo   - 语法错误：重新下载 demo 包
    goto :end
)
echo.

echo [6/6] 启动 demo...
echo.
echo   ============================================================
echo   ✅ 所有检查通过！即将启动 demo...
echo   看到一个 1480x820 的暗色窗口就是成功了
echo   按 Ctrl+C 退出
echo   ============================================================
echo.
timeout /t 3 /nobreak >nul
python main.py
goto :end

:end
echo.
echo ============================================================
echo   诊断结束
echo ============================================================
echo.
echo 如果还是不行，把上面所有输出截图发给开发者。
echo.
pause