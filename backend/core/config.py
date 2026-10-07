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

"""小凌 · 插件系统（内置 + 外部加载 + 权限 + 钩子）"""
import importlib.util
import json
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .config import STAR_DIR

PLUGINS_DIR = STAR_DIR / "plugins"

PERMISSIONS = {
    "chat:read": "读取聊天消息",
    "chat:write": "发送消息",
    "file:read": "读取文件",
    "file:write": "写入文件",
    "network": "网络访问",
    "system": "系统操作",
    "tts": "语音合成",
    "asr": "语音识别",
    "avatar": "3D 动作控制",
}

HOOKS = ("on_load", "on_unload", "on_message", "on_response",
         "on_tick", "on_idle", "before_chat", "after_chat",
         "on_startup", "on_shutdown")

BUILTIN_PLUGINS = [
    {"name": "deep_chat", "version": "1.0.0", "category": "core",
     "description": "深度对话模式，更深入的思考和回复",
     "entry": "on_message", "permissions": ["chat:read", "chat:write"],
     "author": "XiaoLing", "enabled": True},
    {"name": "agent_task", "version": "1.0.0", "category": "core",
     "description": "Agent 任务执行，帮你做事",
     "entry": "on_message", "permissions": ["chat:read", "chat:write",
                                            "file:read", "network"],
     "author": "XiaoLing", "enabled": True},
    {"name": "reminder", "version": "1.0.0", "category": "tool",
     "description": "定时提醒，记住你要做的事",
     "entry": "on_tick", "permissions": ["system"],
     "author": "XiaoLing", "enabled": True},
    {"name": "read_aloud", "version": "1.0.0", "category": "core",
     "description": "语音朗读，用小凌的声音读出来",
     "entry": "on_response", "permissions": ["chat:read", "tts"],
     "author": "XiaoLing", "enabled": True},
    {"name": "distill_train", "version": "1.0.0", "category": "ai",
     "description": "蒸馏训练，小凌自己成长",
     "entry": "on_idle", "permissions": ["file:read", "file:write", "system"],
     "author": "XiaoLing", "enabled": True},
    {"name": "emotion_system", "version": "1.0.0", "category": "core",
     "description": "表情系统，小凌有情绪变化",
     "entry": "on_message", "permissions": ["chat:read", "avatar"],
     "author": "XiaoLing", "enabled": True},
    {"name": "search_web", "version": "0.9.2", "category": "tool",
     "description": "DuckDuckGo 无追踪搜索",
     "entry": "on_message", "permissions": ["network"],
     "author": "XiaoLing", "enabled": False},
    {"name": "knowledge_graph", "version": "1.2.0", "category": "ai",
     "description": "三元组记忆，构建专属世界",
     "entry": "on_message", "permissions": ["chat:read", "file:write"],
     "author": "XiaoLing", "enabled": True},
    {"name": "voice_broadcast", "version": "1.1.0", "category": "core",
     "description": "edge-tts 自动朗读回复",
     "entry": "on_response", "permissions": ["tts"],
     "author": "XiaoLing", "enabled": True},
    {"name": "lora_train", "version": "1.3.0", "category": "ai",
     "description": "持续微调，让模型更像她",
     "entry": "on_idle", "permissions": ["file:read", "file:write", "system"],
     "author": "XiaoLing", "enabled": True},
    {"name": "goal_manager", "version": "0.7.4", "category": "tool",
     "description": "持久化目标与完成度追踪",
     "entry": "on_tick", "permissions": ["file:read", "file:write"],
     "author": "XiaoLing", "enabled": False},
    {"name": "auto_update", "version": "1.0.3", "category": "system",
     "description": "检查并提示新版本",
     "entry": "on_startup", "permissions": ["network"],
     "author": "XiaoLing", "enabled": True},
    {"name": "quick_command", "version": "0.6.0", "category": "fun",
     "description": "自定义一键触发动作",
     "entry": "on_message", "permissions": ["chat:read", "system"],
     "author": "XiaoLing", "enabled": False},
    {"name": "privacy_sandbox", "version": "1.0.0", "category": "system",
     "description": "数据完全本地，不出本机",
     "entry": "on_startup", "permissions": [],
     "author": "XiaoLing", "enabled": True},
    {"name": "emotion_analysis", "version": "0.5.2", "category": "ai",
     "description": "感知语气，调整回应节奏",
     "entry": "on_message", "permissions": ["chat:read"],
     "author": "XiaoLing", "enabled": False},
    {"name": "custom_plugin", "version": "1.0.0", "category": "system",
     "description": "Python 文件即插即用",
     "entry": "on_load", "permissions": [],
     "author": "XiaoLing", "enabled": True},
]


@dataclass
class PluginManifest:
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    category: str = "tool"
    entry: str = "on_message"
    permissions: list = field(default_factory=list)
    min_app_version: str = "0.0.1"
    homepage: str = ""

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "PluginManifest":
        return PluginManifest(
            name=d.get("name", ""),
            version=d.get("version", "1.0.0"),
            description=d.get("description", ""),
            author=d.get("author", ""),
            category=d.get("category", "tool"),
            entry=d.get("entry", "on_message"),
            permissions=list(d.get("permissions") or []),
            min_app_version=d.get("min_app_version", "0.0.1"),
            homepage=d.get("homepage", ""),
        )


@dataclass
class Plugin:
    manifest: PluginManifest
    path: Path = field(default_factory=lambda: Path("builtin"))
    enabled: bool = False
    module: object = None
    is_builtin: bool = False
    loaded_at: float = 0.0
    error: str = ""


class PluginManager:
    def __init__(self, plugins_dir: str | None = None, enable_builtin: bool = True):
        self.plugins_dir = Path(plugins_dir) if plugins_dir else PLUGINS_DIR
        self.plugins: dict[str, Plugin] = {}
        self._hooks: dict[str, list] = {}
        self._lock = threading.RLock()
        try:
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        if enable_builtin:
            self._load_builtin()
        self._load_external()

    def _load_builtin(self):
        with self._lock:
            for item in BUILTIN_PLUGINS:
                manifest = PluginManifest.from_dict(item)
                p = Plugin(manifest=manifest, path=Path("builtin"),
                           is_builtin=True, enabled=bool(item.get("enabled", False)))
                self.plugins[manifest.name] = p

    def _load_external(self):
        with self._lock:
            for d in self.plugins_dir.iterdir():
                if not d.is_dir() or d.name.startswith("."):
                    continue
                manifest_file = d / "manifest.json"
                if not manifest_file.exists():
                    continue
                try:
                    data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    manifest = PluginManifest.from_dict(data)
                    if not manifest.name:
                        manifest.name = d.name
                    self.plugins[manifest.name] = Plugin(
                        manifest=manifest, path=d,
                        enabled=bool(data.get("enabled", False)))
                except Exception as e:
                    self.plugins[d.name] = Plugin(
                        manifest=PluginManifest(name=d.name, description="加载失败"),
                        path=d, error=f"{type(e).__name__}: {e}")

    def install(self, src_dir: Path | str) -> dict:
        src = Path(src_dir)
        if not src.exists() or not src.is_dir():
            return {"ok": False, "error": "目录不存在"}
        manifest_file = src / "manifest.json"
        if not manifest_file.exists():
            return {"ok": False, "error": "缺少 manifest.json"}
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            name = data.get("name") or src.name
        except Exception as e:
            return {"ok": False, "error": f"manifest 解析失败：{e}"}
        dst = self.plugins_dir / name
        try:
            if dst.exists():
                import shutil
                shutil.rmtree(dst)
            import shutil
            shutil.copytree(src, dst)
        except OSError as e:
            return {"ok": False, "error": f"复制失败：{e}"}
        self._load_external()
        return {"ok": True, "name": name, "path": str(dst)}

    def uninstall(self, name: str) -> dict:
        with self._lock:
            p = self.plugins.get(name)
            if not p:
                return {"ok": False, "error": "插件不存在"}
            if p.is_builtin:
                return {"ok": False, "error": "内置插件不能卸载"}
            self.disable(name)
            import shutil
            try:
                shutil.rmtree(p.path)
            except OSError as e:
                return {"ok": False, "error": f"删除失败：{e}"}
            self.plugins.pop(name, None)
        return {"ok": True, "name": name}

    def list_plugins(self) -> list:
        with self._lock:
            return [
                {
                    "name": p.manifest.name,
                    "version": p.manifest.version,
                    "description": p.manifest.description,
                    "author": p.manifest.author,
                    "category": p.manifest.category,
                    "enabled": p.enabled,
                    "builtin": p.is_builtin,
                    "permissions": p.manifest.permissions,
                    "error": p.error,
                }
                for p in self.plugins.values()
            ]

    def list_enabled(self) -> list:
        with self._lock:
            return [p.manifest.name for p in self.plugins.values() if p.enabled]

    def list_by_category(self) -> dict:
        out: dict[str, list] = {}
        with self._lock:
            for p in self.plugins.values():
                c = p.manifest.category or "other"
                out.setdefault(c, []).append(p.manifest.name)
        return out

    def get(self, name: str) -> Plugin | None:
        with self._lock:
            return self.plugins.get(name)

    def is_enabled(self, name: str) -> bool:
        with self._lock:
            p = self.plugins.get(name)
            return bool(p and p.enabled)

    def enable(self, name: str) -> bool:
        with self._lock:
            p = self.plugins.get(name)
            if not p:
                return False
            if not p.is_builtin and p.module is None:
                if not self._load_module(p):
                    return False
            p.enabled = True
            p.loaded_at = time.time()
        self._register_hooks(p)
        self.emit("on_load", p)
        return True

    def disable(self, name: str) -> bool:
        with self._lock:
            p = self.plugins.get(name)
            if not p:
                return False
            p.enabled = False
        self.emit("on_unload", p)
        return True

    def toggle(self, name: str) -> bool:
        if self.is_enabled(name):
            self.disable(name)
            return False
        self.enable(name)
        return True

    def _load_module(self, p: Plugin) -> bool:
        main = p.path / "main.py"
        if not main.exists():
            p.error = "缺少 main.py"
            return False
        try:
            spec = importlib.util.spec_from_file_location(f"xl_plugin_{p.manifest.name}", main)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            p.module = module
            p.error = ""
            return True
        except Exception as e:
            p.error = f"{type(e).__name__}: {e}"
            return False

    def _register_hooks(self, p: Plugin):
        if p.module is None:
            return
        entry = p.manifest.entry
        fn = getattr(p.module, entry, None)
        if callable(fn):
            self.on(entry, fn)

    def on(self, hook: str, callback):
        with self._lock:
            self._hooks.setdefault(hook, []).append(callback)

    def off(self, hook: str, callback):
        with self._lock:
            if hook in self._hooks and callback in self._hooks[hook]:
                self._hooks[hook].remove(callback)

    def emit(self, hook: str, *args, **kwargs):
        with self._lock:
            callbacks = list(self._hooks.get(hook, []))
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception:
                pass

    def check_permission(self, name: str, permission: str) -> bool:
        with self._lock:
            p = self.plugins.get(name)
            if not p:
                return False
            return permission in p.manifest.permissions

    def grant(self, name: str, permission: str) -> bool:
        with self._lock:
            p = self.plugins.get(name)
            if not p or permission not in PERMISSIONS:
                return False
            if permission not in p.manifest.permissions:
                p.manifest.permissions.append(permission)
            return True

    def revoke(self, name: str, permission: str) -> bool:
        with self._lock:
            p = self.plugins.get(name)
            if not p:
                return False
            if permission in p.manifest.permissions:
                p.manifest.permissions.remove(permission)
            return True

    def process_message(self, message: str) -> str:
        result = message
        for p in list(self.plugins.values()):
            if not p.enabled or p.module is None:
                continue
            fn = getattr(p.module, "on_message", None)
            if callable(fn):
                try:
                    out = fn(result)
                    if isinstance(out, str) and out:
                        result = out
                except Exception:
                    pass
        return result

    def broadcast_response(self, text: str):
        for p in list(self.plugins.values()):
            if not p.enabled or p.module is None:
                continue
            fn = getattr(p.module, "on_response", None)
            if callable(fn):
                try:
                    fn(text)
                except Exception:
                    pass

    def tick(self):
        for p in list(self.plugins.values()):
            if not p.enabled or p.module is None:
                continue
            fn = getattr(p.module, "on_tick", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass

    def reload(self) -> int:
        with self._lock:
            self.plugins = {}
            self._hooks.clear()
        self._load_builtin()
        self._load_external()
        return len(self.plugins)

    def stats(self) -> dict:
        with self._lock:
            total = len(self.plugins)
            enabled = sum(1 for p in self.plugins.values() if p.enabled)
            builtin = sum(1 for p in self.plugins.values() if p.is_builtin)
            by_cat: dict[str, int] = {}
            for p in self.plugins.values():
                c = p.manifest.category or "other"
                by_cat[c] = by_cat.get(c, 0) + 1
            return {"total": total, "enabled": enabled, "builtin": builtin,
                    "external": total - builtin, "categories": by_cat,
                    "hooks": list(self._hooks.keys()), "dir": str(self.plugins_dir)}

    def permission_list(self) -> dict:
        return dict(PERMISSIONS)

    def hook_list(self) -> list:
        return list(HOOKS)
"""小凌 · 更新检查（GitHub Release API + 多镜像 + 缓存 + 跳过版本）"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

CACHE_PATH = DATA_DIR / "update_cache.json"
SKIP_PATH = DATA_DIR / "update_skip.json"

REPO = "3477856804/XLmodel-release"
CURRENT_VERSION = "0.0.1"
CACHE_TTL = 1800.0
TIMEOUT = 6.0
MIRRORS = (
    f"https://api.github.com/repos/{REPO}/releases/latest",
    f"https://ghfast.top/https://api.github.com/repos/{REPO}/releases/latest",
    f"https://ghproxy.net/https://api.github.com/repos/{REPO}/releases/latest",
)


class UpdateInfo:
    def __init__(self, has_update: bool = False, latest: str = "", current: str = "",
                 tag: str = "", name: str = "", body: str = "", html_url: str = "",
                 published_at: str = "", prerelease: bool = False, draft: bool = False,
                 size_mb: float = 0.0, assets: list | None = None,
                 source: str = "", message: str = ""):
        self.has_update = has_update
        self.latest = latest
        self.current = current
        self.tag = tag
        self.name = name
        self.body = body
        self.html_url = html_url
        self.published_at = published_at
        self.prerelease = prerelease
        self.draft = draft
        self.size_mb = size_mb
        self.assets = assets or []
        self.source = source
        self.message = message

    def to_dict(self) -> dict:
        return {
            "has_update": self.has_update, "latest": self.latest,
            "current": self.current, "tag": self.tag, "name": self.name,
            "body": self.body, "html_url": self.html_url,
            "published_at": self.published_at, "prerelease": self.prerelease,
            "draft": self.draft, "size_mb": round(self.size_mb, 2),
            "assets": self.assets, "source": self.source,
            "message": self.message,
        }

    def changelog_lines(self) -> list:
        if not self.body:
            return []
        out = []
        for line in self.body.split("\n"):
            s = line.strip()
            if not s:
                continue
            s = s.lstrip("-*+ ").lstrip("#").strip()
            if s:
                out.append(s)
        return out


class UpdateAsset:
    def __init__(self, name: str = "", url: str = "", size_mb: float = 0.0,
                 platform: str = "other", recommended: bool = False):
        self.name = name
        self.url = url
        self.size_mb = size_mb
        self.platform = platform
        self.recommended = recommended

    def to_dict(self) -> dict:
        return {"name": self.name, "url": self.url,
                "size_mb": round(self.size_mb, 2),
                "platform": self.platform, "recommended": self.recommended}


def platform_of(name: str) -> str:
    n = (name or "").lower()
    if n.endswith(".exe") or "setup" in n or "windows" in n:
        return "windows"
    if n.endswith(".dmg") or "macos" in n or "mac" in n:
        return "macos"
    if n.endswith(".appimage") or n.endswith(".deb") or "linux" in n:
        return "linux"
    if n.endswith(".apk") or "android" in n:
        return "android"
    if n.endswith(".ipa") or "ios" in n:
        return "ios"
    if n.endswith(".zip"):
        return "zip"
    if n.endswith(".tar.gz") or n.endswith(".tgz"):
        return "tarball"
    return "other"


def is_recommended(name: str) -> bool:
    n = (name or "").lower()
    return (n.endswith(".exe") or "setup" in n or "installer" in n
            or n.endswith(".dmg") or n.endswith(".appimage"))


def normalize_version(tag: str) -> str:
    v = (tag or "").strip()
    if v[:1].lower() == "v":
        v = v[1:]
    return v


def is_newer(latest: str, current: str) -> bool:
    try:
        a = [int(x) for x in latest.split(".")]
        b = [int(x) for x in current.split(".")]
        n = max(len(a), len(b))
        for i in range(n):
            x = a[i] if i < len(a) else 0
            y = b[i] if i < len(b) else 0
            if x > y:
                return True
            if x < y:
                return False
    except (ValueError, AttributeError):
        pass
    return False


def source_label(url: str) -> str:
    if "ghfast.top" in url:
        return "ghfast"
    if "ghproxy.net" in url:
        return "ghproxy"
    if "api.github.com" in url:
        return "github"
    return "mirror"


def format_size(mb: float) -> str:
    if mb <= 0:
        return "—"
    if mb < 1:
        return f"{int(mb * 1024)} KB"
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb / 1024:.2f} GB"


def format_date(iso: str) -> str:
    if not iso:
        return "—"
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return d.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


class UpdateChecker:
    def __init__(self, repo: str = REPO, current_version: str = CURRENT_VERSION,
                 allow_prerelease: bool = False):
        self.repo = repo
        self.current = current_version
        self.allow_prerelease = allow_prerelease
        self._lock = threading.RLock()
        self._cache: UpdateInfo | None = None
        self._cache_at: float = 0.0
        self._skipped: str = ""
        self._load_skip()

    def _load_skip(self):
        if not SKIP_PATH.exists():
            return
        try:
            data = json.loads(SKIP_PATH.read_text(encoding="utf-8"))
            self._skipped = data.get("skip", "")
        except Exception:
            pass

    def _save_skip(self):
        try:
            SKIP_PATH.parent.mkdir(parents=True, exist_ok=True)
            SKIP_PATH.write_text(json.dumps({"skip": self._skipped,
                                             "updated_at": time.time()},
                                            ensure_ascii=False),
                                 encoding="utf-8")
        except OSError:
            pass

    def skip_version(self, version: str):
        with self._lock:
            self._skipped = normalize_version(version)
            self._save_skip()

    def clear_skip(self):
        with self._lock:
            self._skipped = ""
            self._save_skip()

    @property
    def skipped(self) -> str:
        with self._lock:
            return self._skipped

    def invalidate(self):
        with self._lock:
            self._cache = None
            self._cache_at = 0.0

    def check(self) -> tuple:
        info = self.check_detailed()
        return (info.has_update, info.latest, info.message)

    def check_detailed(self, force: bool = False, use_cache: bool = True) -> UpdateInfo:
        with self._lock:
            if (not force and use_cache and self._cache is not None
                    and (time.time() - self._cache_at) < CACHE_TTL):
                return self._cache
        last_error = "unknown"
        for url in MIRRORS:
            info = self._try_mirror(url)
            if info is not None:
                with self._lock:
                    self._cache = info
                    self._cache_at = time.time()
                return info
            last_error = url
        return UpdateInfo(current=self.current,
                          message=f"检查失败：{last_error}")

    def _try_mirror(self, url: str) -> UpdateInfo | None:
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"XiaoLing-Updater/{self.current}",
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                if r.status != 200:
                    return None
                raw = json.loads(r.read().decode("utf-8"))
            if not isinstance(raw, dict):
                return None
            return self._parse(raw, url)
        except Exception:
            return None

    def _parse(self, raw: dict, source: str) -> UpdateInfo | None:
        tag = str(raw.get("tag_name") or "")
        latest = normalize_version(tag)
        if not latest:
            return None
        if raw.get("draft") is True:
            return None
        prerelease = bool(raw.get("prerelease"))
        if prerelease and not self.allow_prerelease:
            return None
        with self._lock:
            skipped = self._skipped
        has_update = is_newer(latest, self.current) and latest != skipped
        assets = []
        for a in (raw.get("assets") or []):
            if not isinstance(a, dict):
                continue
            name = str(a.get("name") or "")
            url = str(a.get("browser_download_url") or "")
            if not name or not url:
                continue
            size = float(a.get("size") or 0) / 1048576.0
            assets.append(UpdateAsset(name=name, url=url, size_mb=size,
                                       platform=platform_of(name),
                                       recommended=is_recommended(name)))
        assets.sort(key=lambda x: (not x.recommended, x.size_mb))
        total_size = sum(a.size_mb for a in assets)
        return UpdateInfo(
            has_update=has_update, latest=latest, current=self.current,
            tag=tag or f"v{latest}", name=str(raw.get("name") or ""),
            body=str(raw.get("body") or ""),
            html_url=str(raw.get("html_url") or ""),
            published_at=str(raw.get("published_at") or ""),
            prerelease=prerelease, draft=False, size_mb=total_size,
            assets=[a.to_dict() for a in assets],
            source=source_label(source),
            message=("发现新版本 v" + latest if has_update
                     else ("已跳过 v" + latest if latest == skipped else "已是最新版本")),
        )

    def pick_for_platform(self, info: UpdateInfo, platform: str) -> dict | None:
        for a in info.assets:
            if a.get("platform") == platform:
                return a
        return None

    def pick_recommended(self, info: UpdateInfo) -> dict | None:
        for a in info.assets:
            if a.get("recommended"):
                return a
        return info.assets[0] if info.assets else None

    def snapshot(self) -> dict:
        with self._lock:
            return {"current": self.current, "skipped": self._skipped,
                    "cached": self._cache.to_dict() if self._cache else None,
                    "cache_age": round(time.time() - self._cache_at, 1)
                    if self._cache_at else None}


def check_for_updates(current: str = CURRENT_VERSION) -> dict:
    checker = UpdateChecker(current_version=current)
    info = checker.check_detailed()
    return info.to_dict()


def changelog_lines(body: str) -> list:
    if not body:
        return []
    out = []
    for line in body.split("\n"):
        s = line.strip()
        if not s:
            continue
        s = s.lstrip("-*+ ").lstrip("#").strip()
        if s:
            out.append(s)
    return out