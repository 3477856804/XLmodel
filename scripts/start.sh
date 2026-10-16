#!/usr/bin/env bash
# 小凌启动脚本 - 启动 Python 后端 + Flutter 前端
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== 启动小凌 ==="

# 启动 Python 后端
echo "[1/2] 启动 AI 后端..."
cd "$PROJECT_ROOT"
python -m backend.rpc.server &
BACKEND_PID=$!

# 启动 Flutter 前端
echo "[2/2] 启动 UI..."
cd "$PROJECT_ROOT/frontend"
flutter run -d linux &
FRONTEND_PID=$!

# 等待任一进程退出，关闭另一个
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
