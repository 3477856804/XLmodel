# -*- coding: utf-8 -*-
"""系统自检（system）—— `python main.py --selftest` 的支撑模块。

本模块原先缺失，导致 --selftest 直接抛 ImportError。此处按 main.py 的
调用契约重建：`selftest()` 返回一个可直接 print 的结果（字符串）。

自检覆盖：
    1. 核心模块能否导入
    2. 关键第三方依赖是否就位
    3. 运行时目录（数据/模型/插件）是否可写
    4. gRPC 契约是否可加载
    5. 模型商店与插件系统是否可用
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


CORE_MODULES = [
    "config", "engine", "model", "growth", "memory", "context",
    "agent", "channels", "fileops", "git_tool", "knowledge_base",
    "mcp_client", "multimodal", "persona_presets", "plugin_sdk",
    "plugin_system", "search", "security_center", "sub_agent",
    "terminal", "tools", "updater", "workflow_engine",
    "fusion", "quarantine", "system",
]

THIRD_PARTY = [
    ("grpc", False), ("torch", False), ("transformers", False),
    ("peft", False), ("requests", False), ("psutil", False),
    ("PIL", False), ("numpy", False), ("huggingface_hub", False),
    ("modelscope", False), ("edge_tts", False), ("aiohttp", False),
]


def _line(ok: bool, label: str, detail: str = "") -> str:
    mark = "[OK]  " if ok else "[MISS]"
    return f"  {mark} {label}{('  → ' + detail) if detail else ''}"


def _check_modules() -> list:
    out = []
    for name in CORE_MODULES:
        try:
            importlib.import_module("core." + name)
            out.append(_line(True, f"core.{name}"))
        except Exception as e:  # noqa: BLE001
            out.append(_line(False, f"core.{name}", f"{type(e).__name__}: {e}"))
    return out


def _check_deps() -> list:
    out = []
    for name, required in THIRD_PARTY:
        try:
            m = importlib.import_module(name)
            ver = getattr(m, "__version__", "")
            out.append(_line(True, f"{name} {ver}".strip()
                             + (" (必需)" if required else "")))
        except Exception:
            out.append(_line(False, f"{name}" + (" (必需)" if required else ""),
                             "未安装"))
    return out


def _check_dirs() -> list:
    out = []
    try:
        from core.config import describe
        d = describe() or {}
        data_dir = d.get("data_dir", "")
        out.append(_line(bool(data_dir), "数据目录", data_dir))
    except Exception as e:  # noqa: BLE001
        out.append(_line(False, "数据目录", str(e)))
    try:
        from core.model import MODELS_DIR
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        writable = os.access(str(MODELS_DIR), os.W_OK)
        out.append(_line(writable, "模型目录", str(MODELS_DIR)))
    except Exception as e:  # noqa: BLE001
        out.append(_line(False, "模型目录", str(e)))
    try:
        from core.config import PluginManager
        pd = PluginManager().plugins_dir
        out.append(_line(Path(pd).is_dir(), "插件目录", str(pd)))
    except Exception as e:  # noqa: BLE001
        out.append(_line(False, "插件目录", str(e)))
    return out


def _check_rpc() -> list:
    out = []
    rpc_dir = Path(__file__).resolve().parent.parent / "rpc"
    if str(rpc_dir) not in sys.path:
        sys.path.insert(0, str(rpc_dir))
    try:
        import xiaoling_pb2 as pb  # noqa: F401
        out.append(_line(True, "gRPC 消息定义 xiaoling_pb2"))
    except Exception as e:  # noqa: BLE001
        out.append(_line(False, "gRPC 消息定义", str(e)))
    try:
        import xiaoling_pb2_grpc as pbg
        n = len([m for m in dir(pbg.XiaoLingStub) if not m.startswith("_")])
        out.append(_line(True, "gRPC 服务桩 xiaoling_pb2_grpc", f"{n} 个方法"))
    except Exception as e:  # noqa: BLE001
        out.append(_line(False, "gRPC 服务桩", str(e)))
    return out


def _check_features() -> list:
    out = []
    try:
        from core.model import ModelStore
        st = ModelStore()
        info = st.list_all()
        out.append(_line(True, "模型商店",
                         f"已装 {len(info.get('installed', []))} / "
                         f"本地 {len(info.get('local', []))} / "
                         f"接口 {len(info.get('api', []))}"))
    except Exception as e:  # noqa: BLE001
        out.append(_line(False, "模型商店", str(e)))
    try:
        from core.config import PluginManager
        pl = PluginManager().list_plugins()
        on = sum(1 for p in pl if p.get("enabled"))
        out.append(_line(True, "插件系统",
                         f"{len(pl)} 个插件，{on} 个已启用（默认全关）"))
    except Exception as e:  # noqa: BLE001
        out.append(_line(False, "插件系统", str(e)))
    try:
        from core import fusion
        r = fusion.try_command(None, "help")
        out.append(_line(r is not None, "指令解析 fusion"))
    except Exception as e:  # noqa: BLE001
        out.append(_line(False, "指令解析 fusion", str(e)))
    try:
        from core.quarantine import PENDING_ROOT
        out.append(_line(True, "安全隔离区", str(PENDING_ROOT)))
    except Exception as e:  # noqa: BLE001
        out.append(_line(False, "安全隔离区", str(e)))
    return out


def selftest() -> str:
    """执行完整自检，返回可打印的报告字符串。"""
    lines = ["", "=" * 56, "  小凌 · 系统自检", "=" * 56]

    lines.append("")
    lines.append("[1] 核心模块")
    lines.extend(_check_modules())

    lines.append("")
    lines.append("[2] 第三方依赖")
    lines.extend(_check_deps())

    lines.append("")
    lines.append("[3] 运行时目录")
    lines.extend(_check_dirs())

    lines.append("")
    lines.append("[4] gRPC 契约")
    lines.extend(_check_rpc())

    lines.append("")
    lines.append("[5] 功能可用性")
    lines.extend(_check_features())

    bad = sum(1 for l in lines if l.strip().startswith("[MISS]"))
    lines.append("")
    lines.append("=" * 56)
    if bad == 0:
        lines.append("  自检通过：未发现缺失项")
    else:
        lines.append(f"  自检完成：{bad} 项缺失/未安装（不阻塞运行，仅提示）")
    lines.append("=" * 56)
    lines.append("")
    return "\n".join(lines)


def summary() -> dict:
    """结构化自检摘要（供程序内部调用）。"""
    report = selftest()
    miss = [l.strip()[6:].strip() for l in report.splitlines()
            if l.strip().startswith("[MISS]")]
    return {"ok": not miss, "missing": miss, "report": report}


if __name__ == "__main__":
    print(selftest())
