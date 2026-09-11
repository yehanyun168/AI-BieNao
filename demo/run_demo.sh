#!/bin/bash
# AI 别闹 · Day 1 Demo Linux/macOS 一键启动
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  AI 别闹 · Day 1 Demo"
echo "============================================================"
echo

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