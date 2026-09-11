#!/bin/bash
# AI 别闹 · Day 1 Demo Linux/macOS 一键启动
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  AI 别闹 · Day 1 Demo"
echo "============================================================"
echo

# P0-7：禁掉 Kivy 文件日志，必须在任何 import kivy 之前导出。
# Kivy 在 import 阶段会跑 file_log_handler.purge_logs() 清理 ~/.kivy/logs/，
# 部分机器上该目录受保护 → safe-delete 抛 OSError，游戏还没开窗口就崩。
# 首次运行通常正常，日志累积后才触发 —— 典型「玩几天突然打不开」。
# 用 ${VAR:-1} 形式：尊重外部环境已设置的值（想开日志排查时可设 0）。
export KIVY_NO_FILELOG="${KIVY_NO_FILELOG:-1}"

# 检测 python3
if ! command -v python3 &> /dev/null; then
    echo "[错误] 没找到 python3，请先安装 Python 3.11+"
    exit 1
fi

echo "[1/2] 检查依赖..."
if ! python3 -c "import kivy" 2>/dev/null; then
    echo "      首次运行，正在安装 Kivy..."
    python3 -m pip install kivy
fi

echo "[2/2] 启动游戏..."
echo
python3 main.py