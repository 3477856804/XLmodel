"""小凌 Android 沙箱 · 精简配置中心。

与桌面版 backend/core/config.py 对齐字段，但只依赖标准库。
所有路径以 Android App 私有目录（由 Kotlin 经 XIAOLING_HOME 注入）为根。
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

_lock = threading.RLock()
_cache: dict | None = None
_cache_mtime: float = 0.0


def _home() -> Path:
    env = os.environ.get("XIAOLING_HOME")
    if env:
        p = Path(env).expanduser().resolve()
    else:
        p = Path(__file__).resolve().parent.parent
    p.mkdir(parents=True, exist_ok=True)
    return p


APP_DIR = _home()
STAR_DIR = APP_DIR / ".star_core"
DATA_DIR = APP_DIR / "data"
MODELS_DIR = STAR_DIR / "models"
CONFIG_PATH = STAR_DIR / "xiaoling_config.json"

DEFAULTS = {
    "version": "0.0.1",
    "name": "小凌",
    "user_name": "你",
    "persona": "活泼",
    "language": "zh",
    "model": {
        "base_model": "Qwen2.5-0.5B-Instruct",
        "hf_id": "Qwen/Qwen2.5-0.5B-Instruct",
        "quant": "q4_k_m",
        "auto_download": False,
    },
    "teacher_model": "deepseek-chat",
    "deepseek_api_key": "暂未填入",
    "deepseek_base_url": "https://api.deepseek.com/v1",
    "temperature": 0.85,
    "max_tokens": 8192,
    "offline_mode": "auto",
}


def ensure_dirs() -> dict:
    """创建沙箱运行所需的目录。"""
    created = []
    for d in (STAR_DIR, DATA_DIR, MODELS_DIR,
              STAR_DIR / "plugins", STAR_DIR / "memory",
              STAR_DIR / "rag", STAR_DIR / "tts"):
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d))
    return {"created": created}


def _deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path: Path | str | None = None, use_cache: bool = True) -> dict:
    global _cache, _cache_mtime
    p = Path(path) if path else CONFIG_PATH
    if use_cache and _cache is not None and p == CONFIG_PATH:
        try:
            if p.stat().st_mtime == _cache_mtime:
                return _deep_merge(DEFAULTS, _cache)
        except OSError:
            pass
    cfg = dict(DEFAULTS)
    raw = {}
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8")) or {}
            cfg = _deep_merge(DEFAULTS, raw)
        except Exception:
            cfg = dict(DEFAULTS)
    if p == CONFIG_PATH:
        _cache = raw
        try:
            _cache_mtime = p.stat().st_mtime if p.exists() else 0.0
        except OSError:
            _cache_mtime = 0.0
    return cfg


def save(cfg: dict, path: Path | str | None = None) -> Path:
    global _cache, _cache_mtime
    p = Path(path) if path else CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        p.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        if p == CONFIG_PATH:
            _cache = cfg
            try:
                _cache_mtime = p.stat().st_mtime
            except OSError:
                _cache_mtime = 0.0
    return p


def patch(changes: dict, path: Path | str | None = None) -> dict:
    cfg = _deep_merge(load(path, use_cache=False), changes or {})
    save(cfg, path)
    return cfg


def get(dotted: str, default=None):
    cur = load()
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur if cur is not None else default


def describe() -> dict:
    return {
        "python": sys.version.split()[0],
        "app_dir": str(APP_DIR),
        "star_dir": str(STAR_DIR),
        "models_dir": str(MODELS_DIR),
        "config_path": str(CONFIG_PATH),
        "platform": "android-sandbox",
    }
