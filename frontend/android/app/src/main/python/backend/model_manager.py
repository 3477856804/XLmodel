"""小凌 Android 沙箱 · 模型下载管理器。

仅依赖标准库（urllib / json / threading / pathlib）。
下载进度写入模块级字典 `PROGRESS`，由 Kotlin 侧轮询读取，避免跨进程回调。
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

from . import config

_lock = threading.RLock()

# 下载进度表：name -> {percent, downloaded_mb, total_mb, status, speed_mb, error}
PROGRESS: dict[str, dict] = {}

# 沙箱内推荐的轻量模型预设（与桌面版 backend/core/model.py 对齐的子集）
PRESETS: dict[str, dict] = {
    "Qwen2.5-0.5B-Instruct": {
        "repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "file": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "size_mb": 352.0,
        "params": "0.5B",
        "tier": "tiny",
        "desc": "最小模型，CPU 可跑",
    },
    "Qwen2.5-1.5B-Instruct": {
        "repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "file": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size_mb": 988.0,
        "params": "1.5B",
        "tier": "balanced",
        "desc": "中文流畅，性价比高",
    },
    "Llama-3.2-1B-Instruct": {
        "repo": "bartowski/Llama-3.2-1B-Instruct-GGUF",
        "file": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "size_mb": 811.0,
        "params": "1B",
        "tier": "tiny",
        "desc": "英文强，中文一般",
    },
    "DeepSeek-R1-Distill-1.5B": {
        "repo": "unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF",
        "file": "DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
        "size_mb": 1120.0,
        "params": "1.5B",
        "tier": "balanced",
        "desc": "推理能力强的蒸馏版",
    },
}

# 下载镜像（HuggingFace 直连 + 国内反代）
_MIRRORS = (
    "https://huggingface.co",
    "https://hf-mirror.com",
)


def presets() -> list[dict]:
    out = []
    for name, p in PRESETS.items():
        item = {"name": name}
        item.update(p)
        out.append(item)
    return out


def models_dir() -> Path:
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return config.MODELS_DIR


def list_installed() -> list[dict]:
    """扫描已下载的模型文件。"""
    out = []
    d = models_dir()
    for f in sorted(d.glob("*.gguf")):
        try:
            mb = f.stat().st_size / 1048576.0
        except OSError:
            mb = 0.0
        out.append({"name": f.stem, "file": f.name, "size_mb": round(mb, 1)})
    return out


def _set_progress(name: str, **kw) -> None:
    with _lock:
        cur = PROGRESS.setdefault(name, {})
        cur.update(kw)
        cur["updated_at"] = time.time()


def get_progress(name: str | None = None) -> dict:
    with _lock:
        if name:
            return dict(PROGRESS.get(name, {}))
        return {k: dict(v) for k, v in PROGRESS.items()}


def _build_url(repo: str, file: str) -> list[str]:
    return [f"{m}/{repo}/resolve/main/{file}" for m in _MIRRORS]


def is_downloading(name: str) -> bool:
    with _lock:
        st = PROGRESS.get(name, {}).get("status")
        return st in ("downloading", "starting")


def download(name: str, quant: str = "q4_k_m") -> dict:
    """下载模型到私有目录。同步阻塞，应在后台线程调用。"""
    preset = PRESETS.get(name)
    if preset is None:
        _set_progress(name, status="error", error="未知模型: " + name)
        return {"ok": False, "error": "未知模型: " + name}

    if is_downloading(name):
        return {"ok": False, "error": "正在下载中"}

    dest = models_dir() / preset["file"]
    if dest.exists() and dest.stat().st_size > 0:
        _set_progress(name, status="installed", percent=100.0,
                      downloaded_mb=round(dest.stat().st_size / 1048576.0, 1))
        return {"ok": True, "already": True, "path": str(dest)}

    _set_progress(name, status="starting", percent=0.0,
                  downloaded_mb=0.0, total_mb=preset["size_mb"])

    urls = _build_url(preset["repo"], preset["file"])
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err = "unknown"

    for url in urls:
        try:
            _set_progress(name, status="downloading", source=url)
            req = urllib.request.Request(url, headers={
                "User-Agent": "XiaoLing-Sandbox/0.0.1",
                "Accept": "application/octet-stream",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                total_mb = total / 1048576.0 if total else preset["size_mb"]
                downloaded = 0
                last_tick = time.time()
                last_bytes = 0
                with open(tmp, "wb") as fp:
                    while True:
                        chunk = resp.read(1024 * 256)
                        if not chunk:
                            break
                        fp.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if now - last_tick >= 0.5:
                            dt = now - last_tick
                            speed = (downloaded - last_bytes) / 1048576.0 / dt
                            mb = downloaded / 1048576.0
                            pct = (downloaded / total * 100.0) if total else 0.0
                            _set_progress(name, status="downloading",
                                          percent=round(pct, 1),
                                          downloaded_mb=round(mb, 1),
                                          total_mb=round(total_mb, 1),
                                          speed_mb=round(speed, 2))
                            last_tick = now
                            last_bytes = downloaded
            tmp.replace(dest)
            _set_progress(name, status="installed", percent=100.0,
                          downloaded_mb=round(dest.stat().st_size / 1048576.0, 1))
            return {"ok": True, "path": str(dest)}
        except Exception as e:  # noqa: BLE001 - 任意网络错误都切下一个镜像
            last_err = f"{type(e).__name__}: {e}"
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            continue

    _set_progress(name, status="error", error=last_err)
    return {"ok": False, "error": last_err}


def status_snapshot() -> dict:
    return {
        "presets": presets(),
        "installed": list_installed(),
        "progress": get_progress(),
    }
