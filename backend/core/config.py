"""小凌 · 统一配置中心（路径解析 + 配置读写 + 老版本迁移）"""
import json
import os
import sys
import threading
from pathlib import Path

_DEV_ROOT = Path(__file__).resolve().parent.parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _bundle_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", _DEV_ROOT))


def app_dir() -> Path:
    env = os.environ.get("XIAOLING_HOME")
    if env:
        p = Path(env).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _DEV_ROOT


def resource_dir() -> Path:
    return _bundle_dir() if is_frozen() else _DEV_ROOT


RESOURCE_DIR = resource_dir()
APP_DIR = app_dir()
STAR_DIR = APP_DIR / ".star_core"
DATA_DIR = APP_DIR / "data"
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
        "ms_id": "Qwen/Qwen2.5-0.5B-Instruct",
        "quant": "q4_k_m",
        "auto_download": False,
    },
    "growth": {
        "auto_train": True,
        "auto_check_after_train": True,
        "retire_mode": "trash",
        "keep_backup": False,
        "simulate_without_torch": False,
        "train_epochs": 2,
        "train_batch": 2,
        "train_lr": 0.0001,
        "min_samples": 500,
        "manual_min_samples": 20,
        "min_interval_hours": 24,
        "require_device_idle": True,
        "require_power_ok": True,
        "allow_train_on_cpu": False,
        "base_mix_ratio": 0.15,
        "init_rank": 8,
        "max_rank": 256,
        "min_quality": 0.5,
        "require_eval": False,
        "pass_threshold": 0.90,
        "keep_generations": 2,
        "max_generations": 5,
        "max_total_bytes": 10737418240,
        "stability_hours": 24,
        "stability_rounds": 100,
        "distill_enabled": True,
        "distill_daily_limit": 200,
        "teacher_price_in": 1.0,
        "teacher_price_out": 2.0,
        "paused": False,
    },
    "deepseek_api_key": "暂未填入",
    "deepseek_base_url": "https://api.deepseek.com/v1",
    "teacher_model": "deepseek-chat",
    "temperature": 0.85,
    "max_tokens": 8192,
    "max_context_turns": 200,
    "short_term_turns": 80,
    "summary_every_turns": 30,
    "enable_voice": True,
    "voice_rate": 175,
    "auto_save_memory": True,
    "proactive": True,
    "avatar": {
        "enabled": True,
        "model": "小凌.vrm",
        "scale": 1.0,
        "focus": "bust",
        "transparent": True,
        "always_on_top": True,
        "read_aloud": True,
        "idle_action": "待机站立.vrma",
        "dance_on_happy": True,
        "webm_fallback": True,
    },
    "rag": {"enabled": True, "top_k": 4, "dim": 512},
    "search": {"enabled": True, "engine": "duckduckgo", "max_results": 5},
    "vision": {
        "enabled": True,
        "api_key": "",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-vl-max",
        "max_side": 1280,
        "quality": 72,
    },
    "tts": {
        "engine": "auto",
        "minimax_key": "",
        "minimax_voice": "female-shaonv",
        "edge_voice": "zh-CN-XiaoxiaoNeural",
        "emotion_map": True,
    },
    "asr": {
        "enabled": False,
        "engine": "baidu",
        "baidu_key": "",
        "baidu_secret": "",
        "seconds": 5,
        "sample_rate": 16000,
    },
    "perception": {"enabled": True, "interval": 60, "tell_user": False},
    "imagen": {"enabled": False, "api_key": "", "base_url": "", "model": "", "pipeline": ""},
    "reminder": {"enabled": True, "notify_tts": True},
    "weather": {"engine": "free", "city": ""},
    "platforms": {
        "wechat": {"enabled": False, "token": "", "webhook": ""},
        "feishu": {"enabled": False, "app_id": "", "app_secret": "", "webhook": ""},
        "qq": {"enabled": False, "onebot_ws": "ws://127.0.0.1:6700", "group": ""},
        "wecom": {"enabled": False, "corp_id": "", "agent_id": "", "secret": "", "webhook": ""},
        "dingtalk": {"enabled": False, "webhook": "", "secret": ""},
        "telegram": {"enabled": False, "bot_token": "", "allowed_users": ""},
        "discord": {"enabled": False, "bot_token": "", "channel_id": ""},
    },
    # ===== 多平台通道扁平配置（供 backend/core/channels.py 使用）=====
    "webhook_enabled": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_enabled": False,
    "discord_webhook_url": "",
    "discord_enabled": False,
    "feishu_webhook_url": "",
    "feishu_enabled": False,
    "whatsapp_api_url": "",
    "whatsapp_token": "",
    "whatsapp_phone_number_id": "",
    "whatsapp_enabled": False,
    "slack_webhook_url": "",
    "slack_bot_token": "",
    "slack_channel": "#general",
    "slack_enabled": False,
    "signal_api_url": "",
    "signal_phone_number": "",
    "signal_enabled": False,
    "offline_mode": "auto",
    "wizard": {"never_show": False, "skip_until_change": "", "mirror": "tuna"},
    "render": {"backend": "auto"},
    "startup": {"mode": "ask"},
}

_LEGACY_ENV_MAP = {
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "DEEPSEEK_BASE_URL": "deepseek_base_url",
    "API_BASE_URL": "deepseek_base_url",
    "TEACHER_MODEL": "teacher_model",
}

_lock = threading.RLock()
_cache: dict | None = None
_cache_mtime: float = 0.0


def _deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def resource(*parts, must_exist: bool = False) -> Path:
    rel = Path(*parts)
    for base in (APP_DIR, RESOURCE_DIR):
        for cand in (base / rel, base / "resources" / rel):
            if cand.exists():
                return cand
    if must_exist:
        raise FileNotFoundError(f"资源不存在：{rel}")
    return APP_DIR / rel


def star(*parts, mkdir: bool = False) -> Path:
    p = STAR_DIR.joinpath(*parts)
    if mkdir:
        p.mkdir(parents=True, exist_ok=True)
    return p


def data(*parts, mkdir: bool = False) -> Path:
    p = DATA_DIR.joinpath(*parts)
    if mkdir:
        p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_dirs() -> dict:
    out = {"created": [], "seeded": []}
    for d in ("XLmodel", "adapter", "growth", "rag", "tts", "recordings",
              "screenshots", "images", "refs", "adapter_seeds", "plugins", "models"):
        p = STAR_DIR / d
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            out["created"].append(str(p))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    src = RESOURCE_DIR / "data"
    if src.exists() and src.resolve() != DATA_DIR.resolve():
        for f in src.glob("*"):
            if f.is_file() and not (DATA_DIR / f.name).exists():
                try:
                    (DATA_DIR / f.name).write_bytes(f.read_bytes())
                    out["seeded"].append(f.name)
                except OSError:
                    pass
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
    legacy = STAR_DIR / "model_choice.txt"
    if legacy.exists():
        try:
            name = legacy.read_text(encoding="utf-8").strip()
            if name:
                cfg["model"]["base_model"] = name
        except OSError:
            pass
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


def set_value(dotted: str, value, path: Path | str | None = None) -> dict:
    parts = dotted.split(".")
    cfg = load(path, use_cache=False)
    cur = cfg
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value
    save(cfg, path)
    return cfg


def _parse_env_file(path: Path) -> dict:
    out = {}
    try:
        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1]
            if k:
                out[k] = v
    except OSError:
        pass
    return out


def migrate_legacy_env(env_path: Path | str | None = None, log=None) -> dict:
    say = log or (lambda *a, **k: None)
    env_file = Path(env_path) if env_path else (APP_DIR / ".env")
    res = {"found": False, "migrated": [], "skipped": [], "env_path": str(env_file)}
    if not env_file.exists():
        return res
    parsed = _parse_env_file(env_file)
    picked = {dst: parsed[src] for src, dst in _LEGACY_ENV_MAP.items() if parsed.get(src)}
    if not picked:
        return res
    res["found"] = True
    cur = load(use_cache=False)
    changes = {}
    for k, v in picked.items():
        now = cur.get(k)
        default = DEFAULTS.get(k)
        unset = (now in (None, "", "暂未填入")) or (default is not None and now == default)
        if unset:
            changes[k] = v
        else:
            res["skipped"].append(k)
    if changes:
        patch(changes)
        res["migrated"] = sorted(changes)
        say(f"  [配置] 已迁移 {len(changes)} 项：{'、'.join(sorted(changes))}")
    return res


def describe() -> dict:
    return {
        "frozen": is_frozen(),
        "resource_dir": str(RESOURCE_DIR),
        "app_dir": str(APP_DIR),
        "star_dir": str(STAR_DIR),
        "data_dir": str(DATA_DIR),
        "config_path": str(CONFIG_PATH),
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "xiaoling_home": os.environ.get("XIAOLING_HOME", ""),
    }


def reset_cache():
    global _cache, _cache_mtime
    _cache = None
_cache_mtime = 0.0


def validate(cfg: dict | None = None) -> list:
    """校验必填配置项是否有效，返回 [(field, error_message), ...]。"""
    c = cfg if isinstance(cfg, dict) else load()
    errors = []
    model = c.get("model") or {}
    if not str(model.get("base_model") or "").strip():
        errors.append(("model.base_model", "模型名称为空"))
    voice = c.get("tts") or {}
    if not str(voice.get("edge_voice") or voice.get("minimax_voice") or "").strip():
        errors.append(("tts.voice", "未配置任何可用音色"))
    if not str(c.get("user_name") or "").strip():
        errors.append(("user_name", "用户名为空"))
    return errors


def migrate(cfg: dict | None = None) -> dict:
    """处理旧版本配置：缺失字段补默认值、字段重命名，返回新配置。"""
    c = dict(DEFAULTS)
    if isinstance(cfg, dict):
        c = _deep_merge(c, cfg)
    # 旧配置没有 telegram 扁平字段时补默认值
    c.setdefault("telegram_enabled", False)
    c.setdefault("telegram_bot_token", "")
    c.setdefault("telegram_chat_id", "")
    # 旧配置可能用旧字段名 voice.id，统一到 tts.edge_voice
    if not (c.get("tts") or {}).get("edge_voice"):
        old_voice = (c.get("voice") or {}).get("id")
        if old_voice:
            c.setdefault("tts", {})["edge_voice"] = old_voice
    c["version"] = "0.0.1"
    return c


def snapshot(cfg: dict | None = None) -> dict:
    """返回当前配置的深拷贝字典，用于备份。"""
    import copy
    return copy.deepcopy(cfg if isinstance(cfg, dict) else load())


def restore(snap: dict) -> dict:
    """从快照字典恢复配置并落盘。"""
    if not isinstance(snap, dict):
        raise ValueError("快照必须是字典")
    return save(snap)


# ============================================================================
# 以下为向后兼容再导出（历史上插件系统、更新检查曾挤在本文件中，现已拆分）：
#   - 插件系统 → backend/core/plugin_system.py（唯一 PluginManager 实现）
#   - 更新检查 → backend/core/updater.py
# 其他模块中 `from core.config import PluginManager / UpdateChecker ...`
# 的导入语句无需任何修改。
# ============================================================================
from .plugin_system import (  # noqa: E402,F401
    PluginBase,
    Plugin,
    PluginManifest,
    PluginManager,
    BUILTIN_PLUGINS,
    PERMISSIONS,
    HOOKS,
)
from .updater import (  # noqa: E402,F401
    UpdateInfo,
    UpdateAsset,
    UpdateChecker,
    check_for_updates,
    changelog_lines,
)
