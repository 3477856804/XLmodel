"""小凌 Android 沙箱入口。

由 Kotlin（Chaquopy）通过 Python.getInstance().getModule("sandbox_entry") 调用：

    setup(home_dir)     注入 App 私有目录（必须最先调用）
    start(port)         启动 gRPC 服务（grpcio 可用时），否则进入轻量模式
    stop()              停止服务
    status_json()       状态快照（JSON 字符串，供 Kotlin 读取）
    download_model_json(n, q)  后台触发模型下载（JSON 返回）
    model_snapshot_json()      模型预设/已装/进度快照（JSON）

所有重型依赖（grpc / protobuf / torch / transformers）均 try-except 降级，
任何缺失都不会让 Python 进程崩溃。
"""
from __future__ import annotations

import json as _json
import os
import threading
import time

# 后端模块在 setup() 注入 home 后再导入，确保路径解析基于 App 私有目录。
config = None
model_manager = None

_state = {
    "started": False,
    "grpc_available": False,
    "port": 50051,
    "server": None,
    "error": "",
}
_state_lock = threading.RLock()
_setup_done = False


def setup(home_dir: str) -> str:
    """注入 App 私有目录并惰性导入后端模块。返回 JSON 状态。"""
    global config, model_manager, _setup_done
    os.environ["XIAOLING_HOME"] = home_dir
    from backend import config as cfg
    from backend import model_manager as mm
    # env 设置后重算路径常量
    from pathlib import Path
    home = Path(home_dir)
    cfg.APP_DIR = home
    cfg.STAR_DIR = home / ".star_core"
    cfg.DATA_DIR = home / "data"
    cfg.MODELS_DIR = cfg.STAR_DIR / "models"
    cfg.CONFIG_PATH = cfg.STAR_DIR / "xiaoling_config.json"
    cfg.ensure_dirs()
    config = cfg
    model_manager = mm
    _setup_done = True
    return _json.dumps({"ok": True, "home": home_dir}, ensure_ascii=False)


def _require_setup() -> None:
    if not _setup_done:
        raise RuntimeError("sandbox not setup: call setup(home_dir) first")


def _build_servicer(pb, pb_grpc):
    """构造最小 XiaoLing servicer。仅在 grpc/protobuf 可用时调用。"""

    class _SandboxServicer(pb_grpc.XiaoLingServicer):
        def GetStatus(self, request, context):
            installed = model_manager.list_installed()
            model = installed[0]["name"] if installed else "none"
            return pb.StatusReply(
                ok=True,
                message="sandbox ready",
                stage="ready",
                model=model,
                backend="android-sandbox",
                progress=100.0,
                version="0.0.1",
            )

        def Chat(self, request, context):
            text = getattr(request, "text", "") or ""
            reply = "（沙箱轻量模式）已收到：" + text + "。本地未加载模型，可在设置中配置远程 API。"
            yield pb.ChatChunk(delta=reply, done=True)

        def ListInstalledModels(self, request, context):
            lst = pb.ModelList()
            for m in model_manager.list_installed():
                lst.models.add(name=m["name"], path=m.get("file", ""),
                               size_mb=m.get("size_mb", 0.0))
            return lst

        def ListRecommendedModels(self, request, context):
            lst = pb.RecommendedModelList()
            for item in model_manager.presets():
                try:
                    lst.models.add(name=item["name"], desc=item.get("desc", ""))
                except Exception:
                    pass
            return lst

        def DownloadModel(self, request, context):
            name = getattr(request, "model_name", "") or ""
            quant = getattr(request, "quant", "q4_k_m") or "q4_k_m"

            def _run():
                model_manager.download(name, quant)

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            for _ in range(60 * 60):
                if not t.is_alive():
                    break
                info = model_manager.get_progress(name)
                st = info.get("status", "")
                yield pb.DownloadProgress(
                    percent=info.get("percent", 0.0),
                    downloaded_mb=info.get("downloaded_mb", 0.0),
                    total_mb=info.get("total_mb", 0.0),
                    status=st if st in ("downloading", "done", "failed") else "downloading",
                )
                time.sleep(0.5)
            info = model_manager.get_progress(name)
            final_st = "done" if info.get("status") == "installed" else "failed"
            yield pb.DownloadProgress(
                percent=info.get("percent", 100.0),
                downloaded_mb=info.get("downloaded_mb", 0.0),
                total_mb=info.get("total_mb", 0.0),
                status=final_st,
            )

    return _SandboxServicer()


def start(port: int = 50051) -> dict:
    """启动沙箱。返回状态字典。"""
    _require_setup()
    global _state
    with _state_lock:
        if _state["started"]:
            return status()
        _state["port"] = int(port)

        grpc_ok = False
        err = ""
        try:
            import grpc  # noqa: F401
            import xiaoling_pb2 as pb
            import xiaoling_pb2_grpc as pb_grpc
            from concurrent import futures

            server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
            pb_grpc.add_XiaoLingServicer_to_server(_build_servicer(pb, pb_grpc), server)
            server.add_insecure_port(f"127.0.0.1:{port}")
            server.start()
            _state["server"] = server
            grpc_ok = True
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
            _state["server"] = None

        _state["grpc_available"] = grpc_ok
        _state["error"] = err
        _state["started"] = True
        return status()


def stop() -> dict:
    with _state_lock:
        srv = _state.get("server")
        if srv is not None:
            try:
                srv.stop(grace=0.5)
            except Exception:
                pass
        _state["server"] = None
        _state["started"] = False
        _state["grpc_available"] = False
        return status()


def download_model(name: str, quant: str = "q4_k_m") -> dict:
    """异步触发模型下载（非阻塞）。"""
    _require_setup()

    def _run():
        try:
            model_manager.download(name, quant)
        except Exception as e:  # noqa: BLE001
            model_manager._set_progress(name, status="error",
                                       error=f"{type(e).__name__}: {e}")
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"ok": True, "started": True, "name": name}


def status() -> dict:
    _require_setup()
    installed = model_manager.list_installed()
    with _state_lock:
        return {
            "started": bool(_state["started"]),
            "grpc_available": bool(_state["grpc_available"]),
            "port": _state["port"],
            "error": _state["error"],
            "version": "0.0.1",
            "python": __import__("sys").version.split()[0],
            "installed_models": installed,
            "models_dir": str(config.MODELS_DIR),
        }


def status_json() -> str:
    return _json.dumps(status(), ensure_ascii=False)


def model_snapshot_json() -> str:
    return _json.dumps(model_manager.status_snapshot(), ensure_ascii=False)


def download_model_json(name: str, quant: str = "q4_k_m") -> str:
    return _json.dumps(download_model(name, quant), ensure_ascii=False)


if __name__ == "__main__":
    import sys
    home = sys.argv[1] if len(sys.argv) > 1 else "/data/local/tmp/xl"
    print(setup(home))
    print(start(50051))
    while True:
        time.sleep(60)
