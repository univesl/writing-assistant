#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 未安装"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "[INFO] 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境并安装依赖
source venv/bin/activate
echo "[INFO] 安装依赖..."
pip install -q -r requirements.txt

# 创建上传目录
mkdir -p uploads

# 从 .env 读取端口
PORT=${PORT:-7500}
if [ -f .env ]; then
    source <(grep -E '^PORT=' .env | sed 's/ //g')
fi

echo "[INFO] 启动服务，端口: $PORT"
python -m uvicorn app.extractor_main:app --host 0.0.0.0 --port "$PORT"