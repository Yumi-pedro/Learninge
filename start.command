#!/bin/bash
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo '未找到 Python 3。请先安装 Python 3，再重新打开此文件。'
  read -r -p '按回车关闭…'
  exit 1
fi
python3 server.py
read -r -p '服务已关闭，按回车退出…'
