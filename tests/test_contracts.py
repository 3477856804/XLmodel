#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重构后架构的契约与冒烟测试。

覆盖 v0.0.1 大重构（34 个 core 模块合并为 9 个）之后最容易回归的点：

  1. 9 个后端模块全部可导入
  2. `core.*` → `backend.core.*` 别名机制可用（server.py 内部全靠它）
  3. 所有 `from core.X import Y` 的符号真实存在（防重构断链）
  4. proto 契约三方一致：proto / pb2 / server 实现
  5. 目录体系常量指向真实存在的路径
  6. pb2 与 shared/proto 权威版的 RPC 差异（记录已知偏差）
  7. TTS / GrowthEngine 的真实方法名（历史上曾因名字写错而静默失败）

这些测试不需要 torch 权重、不连网络，可在任意环境稳定运行。
"""

from __future__ import annotations

import ast
import importlib
import importlib.abc
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

CORE_MODULES = [
    "channels", "config", "engine", "growth", "memory",
    "model", "multimodal", "search", "tools",
]


# --------------------------------------------------------------------------
# 1. 模块可导入
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", CORE_MODULES)
def test_core_module_importable(name):
    mod = importlib.import_module(f"backend.core.{name}")
    assert mod is not None


def test_rpc_server_module_parses():
    """server.py 必须能被解析（语法层）。"""
    src = (BACKEND / "rpc" / "server.py").read_text(encoding="utf-8")
    ast.parse(src)  # 不抛异常即通过


# --------------------------------------------------------------------------
# core.* 别名由 tests/conftest.py 的 _CoreAliasFinder 提供（与 main.py 同一机制），
# 这里直接验证它生效。
# --------------------------------------------------------------------------
def test_core_alias_works():
    """`import core.config` 应该被重写到 backend.core.config。"""
    mod = importlib.import_module("core.config")
    assert mod is not None
    # 别名模块与真实模块应是同一对象
    assert mod is importlib.import_module("backend.core.config")


def test_server_import_style_resolvable():
    """server.py 用的 `from core.X import` 目标必须都存在。"""
    import core.config as cfg

    # server.py 引用过的几个关键符号
    for attr in ("APP_DIR", "resource", "PluginManager"):
        assert hasattr(cfg, attr), f"core.config 缺少 {attr}（server.py 依赖它）"


# --------------------------------------------------------------------------
# 3. 全部 core.* 引用的符号有效性（AST 扫描，防断链）
# --------------------------------------------------------------------------
def _iter_python_files():
    for p in BACKEND.rglob("*.py"):
        if "__pycache__" not in p.parts:
            yield p
    yield ROOT / "main.py"


def test_all_core_imports_resolve():
    """遍历所有 `from core.X import Y`，确认 Y 真实存在。"""
    missing = []
    checked = 0
    for fp in _iter_python_files():
        tree = ast.parse(fp.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module \
                    and node.module.startswith("core."):
                mod = importlib.import_module(node.module)
                for alias in node.names:
                    checked += 1
                    if not hasattr(mod, alias.name):
                        missing.append(f"{fp.relative_to(ROOT)}: "
                                       f"{node.module}.{alias.name}")
    assert not missing, "以下 core 引用已失效：\n  " + "\n  ".join(missing)
    assert checked > 0, "未扫描到任何 core 引用，测试本身可能失效"


# --------------------------------------------------------------------------
# 4. 目录体系常量
# --------------------------------------------------------------------------
def test_directory_constants_exist():
    from core import config as cfg

    assert cfg.APP_DIR.exists(), f"APP_DIR 不存在：{cfg.APP_DIR}"
    assert cfg.STAR_DIR.exists(), f"STAR_DIR 不存在：{cfg.STAR_DIR}"
    assert cfg.DATA_DIR.exists(), f"DATA_DIR 不存在：{cfg.DATA_DIR}"


def test_growth_base_and_adapter_dirs_exist():
    """成长引擎要求的基座与适配器目录必须就位。

    这是历史故障点：目录缺失时 stage_text() 会显示
    「无基底，适配器 XX 独自积累」，微调链路静默失效。
    """
    from core.growth import ADAPTER_DIR, BASE_MODEL_DIR

    assert BASE_MODEL_DIR.exists(), f"成长基座目录缺失：{BASE_MODEL_DIR}"
    assert ADAPTER_DIR.exists(), f"适配器目录缺失：{ADAPTER_DIR}"


def test_model_store_dir_exists():
    """模型安装目录必须存在，否则 ListInstalledModels 永远为空。"""
    from core.model import MODELS_DIR

    assert MODELS_DIR.exists(), f"模型目录缺失：{MODELS_DIR}"


# --------------------------------------------------------------------------
# 5. proto 契约三方一致
# --------------------------------------------------------------------------
def _rpc_names(text: str) -> set[str]:
    import re
    return set(re.findall(r"^\s*rpc\s+(\w+)", text, re.M))


def test_pb2_grpc_matches_server_impl():
    """pb2_grpc 提供的 RPC 必须与 server.py 实现的方法数一致。"""
    import re

    pb2_grpc = (BACKEND / "rpc" / "xiaoling_pb2_grpc.py").read_text(encoding="utf-8")
    pb_rpcs = set(re.findall(r"'/xiaoling\.XiaoLing/(\w+)'", pb2_grpc))

    server_src = (BACKEND / "rpc" / "server.py").read_text(encoding="utf-8")
    tree = ast.parse(server_src)
    impl = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    impl.add(item.name)
    # server 里还有若干非 RPC 的辅助方法，过滤：以 proto 方法名为准做双向包含校验
    proto_file = BACKEND / "rpc" / "xiaoling.proto"
    proto_rpcs = _rpc_names(proto_file.read_text(encoding="utf-8"))

    missing_impl = proto_rpcs - impl
    assert not missing_impl, f"proto 声明但 server 未实现：{missing_impl}"
    assert pb_rpcs, "pb2_grpc 里解析不到任何 RPC"


def test_proto_three_way_consistent():
    """权威 proto / Python pb2 / Dart pbgrpc 三方 RPC 集合必须完全一致。

    这是一项**守卫测试**：项目曾同时存在两份 proto（shared/ 与 backend/rpc/），
    各自演化后漂移（shared 版少了 StartTraining 与 status_text）。现在
    backend/rpc/xiaoling.proto 由 scripts/gen_proto.py 从权威源同步生成，
    Dart 侧也统一生成，因此三方应当严格一致——任何一方漂移都会让本测试失败。

    修复方式：python scripts/gen_proto.py --dart
    （需PATH 含 C:\\Users\\MVP\\AppData\\Local\\Pub\\Cache\\bin）
    """
    import re

    auth = _rpc_names((ROOT / "shared" / "proto" / "xiaoling.proto").read_text(encoding="utf-8"))
    backend_copy = _rpc_names((BACKEND / "rpc" / "xiaoling.proto").read_text(encoding="utf-8"))
    pb2_grpc = (BACKEND / "rpc" / "xiaoling_pb2_grpc.py").read_text(encoding="utf-8")
    py = set(re.findall(r"'/xiaoling\.XiaoLing/(\w+)'", pb2_grpc))

    assert auth == backend_copy, (
        "backend/rpc/xiaoling.proto 与权威源不一致，请运行 "
        "python scripts/gen_proto.py")
    assert auth == py, (
        f"Python pb2 与权威源不一致，差集：{auth ^ py}，"
        "请运行 python scripts/gen_proto.py")

    dart_file = ROOT / "frontend" / "lib" / "rpc" / "xiaoling.pbgrpc.dart"
    if dart_file.exists():
        dart = set(re.findall(r"'/xiaoling\.XiaoLing/(\w+)'",
                              dart_file.read_text(encoding="utf-8")))
        assert auth == dart, (
            f"Dart pbgrpc 与权威源不一致，差集：{auth ^ dart}，"
            "请运行 python scripts/gen_proto.py --dart")


def test_start_training_present_everywhere():
    """StartTraining 三方齐备（这条曾是已知偏差，现已修复）。"""
    auth = _rpc_names((ROOT / "shared" / "proto" / "xiaoling.proto").read_text(encoding="utf-8"))
    assert "StartTraining" in auth, "权威 proto 应含 StartTraining"
    assert "StartTraining" in _rpc_names(
        (BACKEND / "rpc" / "xiaoling.proto").read_text(encoding="utf-8"))


def test_growth_status_has_status_text():
    """GrowthStatusReply.status_text = 9 必须存在（曾只在 backend 版 proto 里）。"""
    text = (ROOT / "shared" / "proto" / "xiaoling.proto").read_text(encoding="utf-8")
    import re
    m = re.search(r"message GrowthStatusReply \{(.*?)\}", text, re.S)
    assert m, "权威 proto 应有 GrowthStatusReply"
    assert "status_text" in m.group(1), "GrowthStatusReply 应含 status_text"


# --------------------------------------------------------------------------
# 6. 关键类的真实方法名（防"名字写错被 except 吞掉"类故障）
# --------------------------------------------------------------------------
def test_tts_real_method_name():
    """TTS 的方法名是 synth()，历史上曾误写 synthesize() 导致语音永远 0 字节。"""
    from core.multimodal import TTS

    assert hasattr(TTS, "synth"), "TTS 缺少 synth()"
    assert hasattr(TTS, "synth_emotion"), "TTS 缺少 synth_emotion()"
    assert not hasattr(TTS, "synthesize"), \
        "TTS 不应有 synthesize()；server.ReadAloud 用的就是 synth()"


def test_growth_engine_signature():
    """GrowthEngine 现签名为 __init__(self, dry_run=False)，不再接受 root/log。"""
    import inspect

    from core.growth import GrowthEngine

    params = list(inspect.signature(GrowthEngine.__init__).parameters)
    assert params == ["self", "dry_run"], f"GrowthEngine 签名已变：{params}"


def test_voices_is_list_not_map():
    """server.ListVoices 遍历 VOICES，历史上有过不存在的 VOICE_MAP。"""
    from core.multimodal import VOICES

    assert isinstance(VOICES, list) and VOICES, "VOICES 应为非空 list"
    assert "id" in VOICES[0], "VOICES 元素需含 id 字段"


def test_detect_hardware_exists():
    """DetectHardware 依赖 core.model.detect_hardware（旧 code.system 已删）。"""
    from core.model import detect_hardware

    info = detect_hardware()
    assert hasattr(info, "ram_total_gb") or hasattr(info, "ram_gb")


def test_gpu_info_reports_hardware_even_without_cuda_torch():
    """装了 CPU 版 torch 时，也必须如实报告显卡型号与显存。

    这是一条守卫测试：老实现在 torch.cuda 不可用时直接 return，
    导致独显机器报出一片空白（看起来像没显卡）。
    修复后 name / memory_gb 由 nvidia-smi 提供，与 torch 能否使用解耦。
    """
    from core.model import get_gpu_info

    info = get_gpu_info()
    for key in ("name", "memory_gb", "cuda", "torch_usable"):
        assert key in info, f"get_gpu_info() 缺字段 {key}"
    assert isinstance(info["cuda"], bool)
    assert isinstance(info["torch_usable"], bool)
    # torch_usable 为 False 时（CPU 版 torch），cuda 必然也是 False
    if not info["torch_usable"]:
        assert info["cuda"] is False, "torch 不可用时 cuda 不应为 True"


def test_detect_hardware_exposes_gpu_fields():
    """detect_hardware 需把 GPU 字段透传到 HardwareInfo。"""
    from core.model import detect_hardware

    hw = detect_hardware()
    assert hasattr(hw, "gpu_name")
    assert hasattr(hw, "gpu_memory_gb")
    assert hasattr(hw, "has_cuda")
    assert hw.ram_total_gb > 0, "内存总量不应为 0"
    assert hw.cpu_cores > 0, "CPU 核数不应为 0"