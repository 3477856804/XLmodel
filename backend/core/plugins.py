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