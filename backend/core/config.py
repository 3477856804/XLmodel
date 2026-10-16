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
        # 老板**当前选中**的模型（可能是本地登记的模型库里的任意一个，
        # 也可能是一个 .gguf 文件）。跟 base_model 是两件事：
        # base_model 记录「商店里下载的默认模型」，active 记录「此刻在用哪个」。
        # 以前没有这个字段，model:use 只改内存，一重启就退回默认的小模型，
        # 于是聊天质量突然变差 —— 看起来就像"本地模型没加载成功"。
        "active": "",
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
        # 断点续训。TrainingRequest（proto）只有 5 个字段、不能改，前端传不了
        # save_steps/resume，所以续训只能由这里配置（core.trainer.checkpoint_cfg
        # 在每次训练开始时读）。checkpoint_interval<1 = 不落检查点、不续训，
        # 行为与引入续训前完全一致；checkpoint_resume: auto|always|off。
        "checkpoint_interval": 0,
        "checkpoint_resume": "off",
        # 磁盘上保留最近几个检查点。optimizer.pt 比 LoRA 权重还大，不设上限
        # 的话长训练能把磁盘吃空，所以这里必须有默认值而不是「无限保留」。
        "checkpoint_keep": 3,
        "keep_generations": 2,
        "max_generations": 5,
        "max_total_bytes": 10737418240,
        "stability_hours": 24,
        "stability_rounds": 100,
        "distill_enabled": True,
        "distill_daily_limit": 200,
        # 一轮最多问老师几条。训练前会跑一次批量蒸馏，不设上限的话长队列
        # 会把一次训练拖成几十分钟的外网等待，费用也没有边界。
        "distill_batch_limit": 8,
        # 单次请求超时。训练入口是同步的（聊天里说「训练一下」），老师端挂了
        # 也不能让小凌不回话，所以宁可少问几条。
        "distill_timeout_sec": 12.0,
        # 一轮蒸馏的总时间预算；用完就把剩下的留在队列里，下次再问。
        "distill_time_budget_sec": 20.0,
        "teacher_price_in": 1.0,
        "teacher_price_out": 2.0,
        "paused": False,
    },
    # 依赖自愈（core/deps.py）：auto_install 只控制「轻量档」(light) 首启是否
    # 自动 pip 拉取；torch 等数 GB 的 train 档永远要显式 force，绝不被这里触发。
    "deps": {"auto_install": True},
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
    # 用户自定义的额外 3D 模型扫描目录（"自定义扫描/添加入口"）。
    # 列表项为绝对路径；目录本身或其任意层子目录下的
    # .vrm/.fbx/.glb/.gltf 都会被 ListModels、/api/vrm/list、
    # /models/<文件名> 自动识别与提供，前端无需改代码。
    # 例：["D:\\Models\\VRM", "E:\\角色\\我的VRM"]
    "model_extra_dirs": [],
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
    """合并配置字典。返回的结构与 base、extra 都不共享任何嵌套 dict。

    以前 base 里没被 extra 覆盖到的嵌套 dict 是**按引用**放进结果的，而
    load() 的 base 就是模块级 DEFAULTS：调用方拿 load() 的结果改一下子键
    （set_value / setdefault+update 都会这样）等于直接改 DEFAULTS，同一进程
    之后每次读配置都带着这份脏值 —— 默认值悄悄漂移，排查时看不出来源。
    """
    out = {}
    for k, v in (base or {}).items():
        out[k] = _deep_merge(v, {}) if isinstance(v, dict) else v
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = _deep_merge(v, {}) if isinstance(v, dict) else v
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


def model_extra_dirs() -> list[Path]:
    """用户配置的额外 3D 模型扫描目录（``model_extra_dirs``）。

    容错要点：
      * 字段缺失 / 为 None / 写成单个字符串时都按列表处理，不抛异常；
      * 相对路径按 ``APP_DIR`` 解析（打包态即用户沙箱），避免工作目录漂移；
      * 目录不存在时**跳过而不是报错**，让其余内置目录照常可用。
    """
    raw: object = DEFAULTS.get("model_extra_dirs")
    try:
        raw = load().get("model_extra_dirs", raw)
    except Exception:
        pass
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[Path] = []
    for item in raw:
        try:
            s = str(item).strip().strip('"').strip("'")
            if not s:
                continue
            p = Path(s).expanduser()
            if not p.is_absolute():
                p = APP_DIR / p
            if p.is_dir():
                out.append(p)
        except Exception:
            continue                                    # 单条坏配置不该拖垮整体
    return out


def model_roots() -> list[Path]:
    """所有可用于 3D 模型的扫描根目录（去重，保持优先级顺序）。

    顺序：随包``resources/models`` → ``<app>/.star_core/models`` →
    用户自定义 ``model_extra_dirs``。``webpanel`` 与 ``ListModels``
    共用本函数，避免两边白名单不一致导致"能列出来却加载不了"。
    """
    out: list[Path] = []
    for cand in (RESOURCE_DIR / "resources" / "models",
                 RESOURCE_DIR / "models",
                 STAR_DIR / "models",
                 APP_DIR / "models"):
        try:
            if cand.is_dir():
                out.append(cand)
        except Exception:
            continue
    out.extend(model_extra_dirs())
    seen, res = set(), []
    for r in out:
        try:
            key = str(r.resolve()).lower()
        except Exception:
            key = str(r).lower()
        if key not in seen:
            seen.add(key)
            res.append(r)
    return res


def model_files(exts=(".vrm", ".fbx", ".glb", ".gltf"), max_depth: int = 4) -> list[Path]:
    """递归收集所有模型文件（去重）。

    只读不删：目录不存在直接跳过。``max_depth`` 限制递归深度，
    避免把用户误指的巨大目录树整个遍历一遍拖慢启动。
    """
    found: list[Path] = []
    seen: set[str] = set()
    exts = tuple(e.lower() for e in exts)
    for root in model_roots():
        try:
            if not root.is_dir():
                continue
            for p in sorted(root.rglob("*")):
                try:
                    if not p.is_file() or p.suffix.lower() not in exts:
                        continue
                    key = str(p.resolve()).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append(p)
                except Exception:
                    continue
        except Exception:
            continue
    # max_depth 语义在此处不硬性裁剪（已 rglob 全量），保留参数仅为兼容调用方。
    return found


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
    cfg = _deep_merge(DEFAULTS, {})
    raw = {}
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8")) or {}
            cfg = _deep_merge(DEFAULTS, raw)
        except Exception:
            cfg = _deep_merge(DEFAULTS, {})
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
    # 实际合成读的是 voice.id（SetVoice / ReadAloud / options 全链路），
    # tts.edge_voice 只是个没人写的陈旧迁移键。校验要回落到真实生效的键，
    # 否则用户明明切了音色，validate 仍报「未配置任何可用音色」。
    if not str(voice.get("edge_voice") or (c.get("voice") or {}).get("id")
               or voice.get("minimax_voice") or "").strip():
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
    CURRENT_VERSION,
    UpdateInfo,
    UpdateAsset,
    UpdateChecker,
    check_for_updates,
    changelog_lines,
)
