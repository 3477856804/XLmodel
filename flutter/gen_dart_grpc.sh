#!/usr/bin/env bash
# 生成 Dart gRPC 代码（需要本机已装 Flutter SDK + protoc）
# 用法：在 flutter/ 目录下跑 ./gen_dart_grpc.sh
set -e
cd "$(dirname "$0")"

PROTOC="${PROTOC:-protoc}"
PROTOC_GEN_DART="${PROTOC_GEN_DART:-dart_proto_plugin}"

# 找上级目录的 proto
PROTO=../rpc/xiaoling.proto

echo ">> 生成 Dart pb / pbgrpc ..."
$PROTOC --dart_out=grpc:lib/grpc \
        -I "$(dirname $PROTO)" \
        "$PROTO"

echo ">> 完成：lib/grpc/xiaoling.pb.dart + xiaoling.pbgrpc.dart"
