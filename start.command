#!/bin/bash
# macOS / Linux 一键启动脚本
# 双击本文件（或在终端执行 ./start.command）即可启动 Jev Studio
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "  未检测到 Python 3。"
  echo "  macOS 通常自带；若没有，请安装：https://www.python.org/downloads/"
  echo ""
  read -n 1 -s -r -p "按任意键关闭窗口..."
  exit 1
fi

# 浏览器由 server.py 自动打开，这里无需重复处理
python3 server.py
