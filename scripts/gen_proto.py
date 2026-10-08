#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从**唯一权威源** `shared/proto/xiaoling.proto` 生成前后端 gRPC 代码。

这个脚本存在的根本原因：项目里曾同时存在两份 proto ——
`shared/proto/xiaoling.proto`（标称权威）与 `backend/rpc/xiaoling.proto`，
二者各自演化导致漂移（shared 版少了 StartTraining 与 status_text 字段）。
两份定义手工维护必然再次分叉，因此统一由本脚本从shared 版生成。

用法：
    # Python 后端（生成到 backend/rpc/）
    .venv/Scripts/python.exe scripts/gen_proto.py

    # 同时生成 Dart（前端，需protoc-gen-dart 在 PATH）
    .venv/Scripts/python.exe scripts/gen_proto.py --dart

    # 只校验不写入（CI 用）
    .venv/Scripts/python.exe scripts/gen_proto.py --check

流程：
  1. 读取 shared/proto/xiaoling.proto（唯一真源）
  2. 同步一份到 backend/rpc/xiaoling.proto（供 protoc 就地生成，避免路径问题）
  3. 用 grpcio-tools 生成 Python 的 *_pb2 / *_pb2_grpc
  4. 可选：用 protoc 生成 Dart 的 *.pb.dart / *.pbgrpc.dart / *.pbenum.dart / *.pbjson.dart

注意：生成前会检测 protoc-gen-dart 是否可用，缺失则跳过 Dart 并明确提示，
不会静默失败。
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTHORITATIVE = ROOT / "shared" / "proto" / "xiaoling.proto"
BACKEND_PROTO_DIR = ROOT / "backend" / "rpc"
BACKEND_PROTO = BACKEND_PROTO_DIR / "xiaoling.proto"
FRONTEND_OUT = ROOT / "frontend" / "lib" / "rpc"

GREEN, YELLOW, RED, DIM, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def _log(msg: str, color: str = "") -> None:
    print(f"{color}{msg}{RESET}")


def sync_proto(check_only: bool) -> bool:
    """把权威 proto 同步到 backend/rpc/。返回是否一致。"""
    if not AUTHORITATIVE.exists():
        _log(f"[FAIL] 权威 proto 不存在：{AUTHORITATIVE}", RED)
        return False
    same = (BACKEND_PROTO.exists()
            and filecmp.cmp(AUTHORITATIVE, BACKEND_PROTO, shallow=False))
    if check_only:
        if same:
            _log(f"[OK  ] backend/rpc/xiaoling.proto 与权威源一致", GREEN)
        else:
            _log("[DIFF] backend/rpc/xiaoling.proto 与权威源不一致，"
                 "请运行 python scripts/gen_proto.py", YELLOW)
        return same
    if not same:
        BACKEND_PROTO_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(AUTHORITATIVE, BACKEND_PROTO)
        _log(f"[SYNC] 已同步权威 proto -> {BACKEND_PROTO.relative_to(ROOT)}", GREEN)
    else:
        _log(f"[OK  ] backend/rpc/xiaoling.proto 已最新", GREEN)
    return True


def gen_python(check_only: bool) -> bool:
    """用 grpcio-tools 生成 Python pb2。"""
    try:
        import grpc_tools.protoc  # noqa: F401
    except ImportError:
        _log("[SKIP] 未安装 grpcio-tools，跳过 Python 代码生成", YELLOW)
        return False
    args = [
        "grpc_tools.protoc",
        f"--proto_path={BACKEND_PROTO_DIR}",
        f"--python_out={BACKEND_PROTO_DIR}",
        f"--grpc_python_out={BACKEND_PROTO_DIR}",
        str(BACKEND_PROTO),
    ]
    if check_only:
        return True
    r = subprocess.run([sys.executable, "-m", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        _log(f"[FAIL] Python 代码生成失败：\n{r.stderr}", RED)
        return False
    _log("[OK  ] Python pb2 / pb2_grpc 已生成", GREEN)
    return True


def _has_protoc_gen_dart() -> bool:
    return shutil.which("protoc-gen-dart") is not None


def _find_protoc() -> list[str] | None:
    """定位 protoc。

    优先用系统 PATH 上的 protoc；没有则退回 grpcio-tools 自带的编译器
    （grpc_tools.protoc 内部内嵌了 protoc，且 pip 装 grpcio-tools 就会带上，
    无需用户额外安装 protoc.exe）。
    """
    exe = shutil.which("protoc")
    if exe:
        return [exe]
    try:
        import grpc_tools.protoc  # noqa: F401
        return [sys.executable, "-m", "grpc_tools.protoc"]
    except ImportError:
        return None


def gen_dart(check_only: bool) -> bool:
    """用 protoc 生成 Dart 代码（需 PATH 里有 protoc-gen-dart）。"""
    if not _has_protoc_gen_dart():
        _log("[SKIP] 未找到 protoc-gen-dart，跳过 Dart 生成。"
             "装法：dart pub global activate protoc_plugin", YELLOW)
        return False
    protoc = _find_protoc()
    if not protoc:
        _log("[SKIP] 未找到 protoc，跳过 Dart 生成。"
             "装法：pip install grpcio-tools 或 dart pub global activate protoc_plugin", YELLOW)
        return False
    if check_only:
        return True
    FRONTEND_OUT.mkdir(parents=True, exist_ok=True)
    cmd = protoc + [
        f"--proto_path={ROOT / 'shared' / 'proto'}",
        f"--dart_out=grpc:{FRONTEND_OUT}",
        str(AUTHORITATIVE),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        _log(f"[FAIL] Dart 代码生成失败：\n{r.stderr}", RED)
        return False
    _log("[OK  ] Dart pb / pbgrpc 已生成", GREEN)
    return True


def verify() -> None:
    """生成后自检：三方 RPC 数与关键字段是否齐平。"""
    import re

    def rpcs(text: str) -> set[str]:
        return set(re.findall(r"^\s*rpc\s+(\w+)", text, re.M))

    auth = AUTHORITATIVE.read_text(encoding="utf-8")
    pb2_grpc = (BACKEND_PROTO_DIR / "xiaoling_pb2_grpc.py").read_text(encoding="utf-8")
    generated = set(re.findall(r"'/xiaoling\.XiaoLing/(\w+)'", pb2_grpc))

    dart = FRONTEND_OUT / "xiaoling.pbgrpc.dart"
    dart_set = set()
    if dart.exists():
        dart_set = set(re.findall(r"'/xiaoling\.XiaoLing/(\w+)'",
                                  dart.read_text(encoding="utf-8")))

    _log("\n--- 生成结果自检 ---", DIM)
    _log(f"权威 proto     : {len(rpcs(auth))} 个 RPC")
    _log(f"Python pb2_grpc: {len(generated)} 个 RPC")
    _log(f"Dart pbgrpc    : {len(dart_set)} 个 RPC" if dart_set else "Dart pbgrpc    : (未生成)")

    ok = True
    if rpcs(auth) != generated:
        _log(f"[FAIL] 权威与 Python 生成不一致，差集："
             f"{rpcs(auth) ^ generated}", RED)
        ok = False
    else:
        _log("[OK  ] 权威 proto 与 Python 生成完全一致", GREEN)

    if dart_set:
        if rpcs(auth) != dart_set:
            _log(f"[WARN] 权威与 Dart 不一致，差集：{rpcs(auth) ^ dart_set}", YELLOW)
        else:
            _log("[OK  ] 权威 proto 与 Dart 完全一致", GREEN)


def main() -> int:
    ap = argparse.ArgumentParser(description="从 shared/proto 生成前后端 gRPC 代码")
    ap.add_argument("--dart", action="store_true",
                    help="同时生成 Dart 代码（需 protoc + protoc-gen-dart）")
    ap.add_argument("--check", action="store_true",
                    help="只校验 proto 是否同步，不写入任何文件")
    args = ap.parse_args()

    _log(f"权威源：{AUTHORITATIVE.relative_to(ROOT)}")
    if not sync_proto(args.check):
        return 1
    gen_python(args.check)
    if args.dart:
        gen_dart(args.check)
    if not args.check:
        verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())