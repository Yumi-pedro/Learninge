#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo 'BetterEnglish 本机检查（不修改系统，也不下载软件）'
echo '系统与芯片：'
uname -sm
if [ "$(uname -s)" = Darwin ]; then
  sw_vers -productVersion
  echo '内存字节数（17179869184 约为16GB）：'
  sysctl -n hw.memsize
fi
echo 'Python：'
if command -v python3 >/dev/null 2>&1; then python3 --version; else echo '未找到 Python 3'; fi
echo 'Ollama：'
if command -v ollama >/dev/null 2>&1; then
  ollama --version
  ollama list
else
  echo '命令行中未找到 Ollama；如果已安装，请打开 Ollama 应用后再试。'
fi
read -r -p '检查结束，按回车关闭…'
