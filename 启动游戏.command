#!/bin/zsh
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo '请先按照 README.md 安装 Python 与 Node.js 依赖。'
  read -k 1 '?按任意键关闭…'
  exit 1
fi
.venv/bin/python start.py
