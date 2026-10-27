#!/bin/bash
# 备用启动脚本：当控制台「启动命令」强制要求填命令时，填 /code/start.sh
# 作用与 bootstrap 完全一致（设置 PYTHONPATH 指向 third_party 依赖目录后启动 uvicorn）
set -e

export PORT=9000
export FC_SERVER_PORT=9000
export KEEP_ALIVE=900
export PYTHONUNBUFFERED=1

# 代码解压目录（阿里云 FC 固定为 /code，腾讯云 SCF 为 /var/user，兼容处理）
CODE_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${CODE_DIR}:${CODE_DIR}/third_party:${PYTHONPATH}"

# /tmp 是 Serverless 环境唯一可靠可写目录
export LOTTERY_CACHE_DIR=/tmp/lottery_cache
export LOTTERY_TTL=${LOTTERY_TTL:-21600}
export LOTTERY_WORKERS=${LOTTERY_WORKERS:-10}

cd "${CODE_DIR}"

exec python3 -m uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --timeout-keep-alive "${KEEP_ALIVE}" \
  --log-level info
