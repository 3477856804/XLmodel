#!/usr/bin/env bash
# 小凌 v0.0.3 新架构一键启动：
#   Python gRPC 后端 (localhost:50051)  +  Flutter UI
set -e
cd "$(dirname "$0")"

echo "🌸 启动小凌（Flutter + Python + gRPC）"
echo ""

# 1) 起 Python 后端
python3 -m rpc.server --port 50051 &
SERVER_PID=$!
echo "  [1/2] Python gRPC 后端 PID=$SERVER_PID"

# 等后端起来
sleep 2

# 2) 起 Flutter 前端
cd flutter
if [ ! -f lib/grpc/xiaoling.pbgrpc.dart ]; then
    echo "  [!] 未发现 Dart gRPC 代码，先生成…"
    ./gen_dart_grpc.sh
fi
echo "  [2/2] 启动 Flutter 前端…"
flutter run

# 退出时一起杀后端
kill $SERVER_PID 2>/dev/null || true
