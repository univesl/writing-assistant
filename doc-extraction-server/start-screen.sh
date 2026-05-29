#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

SCREEN_NAME="doc-extractor"
SCRIPT_DIR="$(pwd)"

# 检查 screen 是否安装
if ! command -v screen &> /dev/null; then
    echo "[ERROR] screen 未安装，请先安装: apt install screen 或 yum install screen"
    exit 1
fi

# 杀掉已有的同名 screen 会话
screen -S "$SCREEN_NAME" -X quit 2>/dev/null || true

# 在 screen 中启动服务
screen -dmS "$SCREEN_NAME" bash -c "
    cd '$SCRIPT_DIR'
    bash start.sh
"

echo "[INFO] 服务已在 screen 会话 '$SCREEN_NAME' 中启动"
echo "[INFO] 查看日志: screen -r $SCREEN_NAME"
echo "[INFO] 分离会话: Ctrl+A D"