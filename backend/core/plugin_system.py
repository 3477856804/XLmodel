"""小凌 · 统一插件系统

合并自两处历史实现（此前并行存在、互不引用）：
- 原 config.py 中的 PluginManager：BUILTIN_PLUGINS 内置插件列表、钩子系统、权限管理
- 原 plugin_sdk.py 中的 PluginManager：动态导入、热重载(reload_plugin)、依赖检查(check_dependencies)

本模块为唯一的插件系统实现。config.py 通过再导出保持向后兼容：
    from core.config import PluginManager, PluginManifest, Plugin   # 仍然可用

注意：本模块刻意不在模块顶层 `from .config import ...`，插件目录路径在运行时
惰性解析，以避免与 config.py 的再导出形成循环导入。
"""
import importlib.util
import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

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


def _default_plugins_dir() -> Path:
    """运行时惰性解析默认插件目录（避免与 config.py 循环导入）。"""
    try:
        from .config import STAR_DIR
        return STAR_DIR / "plugins"
    except Exception:
        return Path("plugins")


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


class PluginBase:
    """插件基类，所有外部 Python 插件继承此类（SDK 风格）。"""

    name = "unknown"
    version = "0.0.1"
    description = ""
    author = ""
    category = "tool"
    permissions: List[str] = []  # ["file_read", "file_write", "network", "terminal"]

    def __init__(self, context=None):
        self.context = context
        self.enabled = False

    def init(self):
        """插件初始化，重写此方法"""
        pass

    def dispose(self):
        """插件销毁，重写此方法"""
        pass

    def register_tools(self) -> List[Dict]:
        """注册工具，返回 [{name, description, args_schema, handler}]"""
        return []

    def register_commands(self) -> Dict:
        """注册命令，返回 {command_name: handler}"""
        return {}

    def get_info(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "permissions": list(self.permissions),
        }


class PluginManager:
    """统一插件管理器：内置插件元数据 + 外部动态加载 + 热重载 + 钩子 + 权限。

    构造可无参调用（向后兼容）：PluginManager()
    """

    def __init__(self, plugins_dir=None, enable_builtin: bool = True):
        self.plugins_dir = Path(plugins_dir) if plugins_dir else _default_plugins_dir()
        self.plugins: Dict[str, Plugin] = {}
        self._hooks: Dict[str, list] = {}
        self._tool_index: Dict[str, Tuple[str, dict]] = {}  # tool_name -> (plugin_name, tool_dict)
        self._lock = threading.RLock()
        try:
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        if enable_builtin:
            self._load_builtin()
        self._load_external()

    # ---------------- 内置插件（元数据注册，不加载模块） ----------------
    def _load_builtin(self):
        with self._lock:
            for item in BUILTIN_PLUGINS:
                try:
                    manifest = PluginManifest.from_dict(item)
                    p = Plugin(manifest=manifest, path=Path("builtin"),
                               is_builtin=True,
                               enabled=bool(item.get("enabled", False)))
                    self.plugins[manifest.name] = p
                except Exception as e:
                    logger.warning("内置插件注册失败 %s: %s", item.get("name"), e)

    # ---------------- 外部插件扫描与动态加载 ----------------
    def _read_manifest_file(self, dir_path: Path):
        """兼容两种清单格式：SDK 的 plugin.json 与历史的 manifest.json。"""
        for fname in ("plugin.json", "manifest.json"):
            f = dir_path / fname
            if f.is_file():
                try:
                    return json.loads(f.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning("插件清单解析失败 %s: %s", f, e)
                    return None
        return None

    def check_dependencies(self, manifest: Dict) -> Tuple[bool, str]:
        """检查依赖是否满足，返回 (ok, error_msg)"""
        deps = manifest.get("dependencies") or []
        if not deps:
            return True, ""
        for dep in deps:
            if dep not in self.plugins:
                return False, "缺少依赖插件: {}".format(dep)
        return True, ""

    def load_plugin(self, plugin_path) -> bool:
        """从目录加载插件：读取清单 → 依赖检查 → 动态导入 entry → 实例化并 init。"""
        path = Path(plugin_path)
        try:
            if not path.is_dir():
                logger.warning("插件目录不存在: %s", path)
                return False
            data = self._read_manifest_file(path)
            if not isinstance(data, dict):
                logger.warning("插件缺少 plugin.json/manifest.json: %s", path)
                return False

            manifest = PluginManifest.from_dict(data)
            if not manifest.name:
                manifest.name = path.name

            ok, err = self.check_dependencies(data)
            if not ok:
                logger.warning("插件 %s 依赖不满足: %s", manifest.name, err)
                return False

            # SDK 的 entry 是入口文件名（main.py）；历史 manifest 的 entry 是钩子名。
            entry_file = "main.py"
            raw_entry = data.get("entry", "")
            if isinstance(raw_entry, str) and raw_entry.endswith(".py"):
                entry_file = raw_entry
            entry_path = path / entry_file
            if not entry_path.is_file():
                self.plugins[manifest.name] = Plugin(
                    manifest=manifest, path=path,
                    enabled=bool(data.get("enabled", False)),
                    error="缺少 {}".format(entry_file))
                return False

            spec = importlib.util.spec_from_file_location(
                "xl_plugin_{}".format(manifest.name), entry_path)
            if spec is None or spec.loader is None:
                self.plugins[manifest.name] = Plugin(
                    manifest=manifest, path=path,
                    enabled=bool(data.get("enabled", False)),
                    error="无法创建模块规范: {}".format(entry_file))
                return False
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                logger.warning("插件模块加载失败 %s: %s", manifest.name, e)
                self.plugins[manifest.name] = Plugin(
                    manifest=manifest, path=path,
                    enabled=False, error="{}: {}".format(type(e).__name__, e))
                return False

            # 优先查找 PluginBase 子类并实例化；否则按历史方式直接挂模块对象。
            module_obj = module
            instance = None
            try:
                for attr in vars(module).values():
                    if (isinstance(attr, type) and issubclass(attr, PluginBase)
                            and attr is not PluginBase):
                        instance = attr(context=self)
                        instance.init()
                        break
            except Exception as e:
                logger.warning("插件 %s 实例化/init 失败: %s", manifest.name, e)
                self.plugins[manifest.name] = Plugin(
                    manifest=manifest, path=path,
                    enabled=False, error="{}: {}".format(type(e).__name__, e))
                return False
            if instance is not None:
                module_obj = instance
                instance.enabled = bool(data.get("enabled", True))

            p = self.plugins.get(manifest.name) or Plugin(manifest=manifest, path=path)
            p.manifest = manifest
            p.path = path
            p.module = module_obj
            p.is_builtin = False
            p.enabled = bool(data.get("enabled", p.enabled))
            p.loaded_at = time.time()
            p.error = ""
            self.plugins[manifest.name] = p
            self._index_tools(manifest.name)
            self._register_hooks(p)
            logger.info("插件已加载: %s v%s", manifest.name, manifest.version)
            return True
        except Exception as e:
            logger.warning("加载插件异常 %s: %s", plugin_path, e)
            return False

    def _load_external(self):
        try:
            entries = sorted(
                p for p in self.plugins_dir.iterdir()
                if p.is_dir() and not p.name.startswith("."))
        except OSError:
            return
        for d in entries:
            try:
                self.load_plugin(d)
            except Exception as e:
                self.plugins[d.name] = Plugin(
                    manifest=PluginManifest(name=d.name, description="加载失败"),
                    path=d, error="{}: {}".format(type(e).__name__, e))

    def load_all(self):
        """加载 plugins_dir 下所有插件目录"""
        try:
            if not self.plugins_dir.is_dir():
                return
            for entry in sorted(p for p in self.plugins_dir.iterdir() if p.is_dir()):
                self.load_plugin(entry)
        except Exception as e:
            logger.warning("批量加载插件异常: %s", e)

    def _unload_locked(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        if plugin is None:
            return False
        try:
            if isinstance(plugin.module, PluginBase):
                plugin.module.dispose()
        except Exception as e:
            logger.warning("插件 %s dispose 失败: %s", name, e)
        try:
            plugin.enabled = False
        except Exception:
            pass
        self.plugins.pop(name, None)
        self._tool_index = {k: v for k, v in self._tool_index.items() if v[0] != name}
        logger.info("插件已卸载: %s", name)
        return True

    def unload_plugin(self, name: str) -> bool:
        """卸载插件：调用 dispose，从字典移除"""
        try:
            with self._lock:
                return self._unload_locked(name)
        except Exception as e:
            logger.warning("卸载插件异常 %s: %s", name, e)
            return False

    def reload_plugin(self, name: str) -> bool:
        """热重载：unload + 重新从磁盘加载"""
        try:
            with self._lock:
                p = self.plugins.get(name)
                if p is None:
                    logger.warning("无法重载未加载的插件: %s", name)
                    return False
                path = p.path
                self._unload_locked(name)
                return self.load_plugin(path)
        except Exception as e:
            logger.warning("重载插件异常 %s: %s", name, e)
            return False

    # ---------------- 安装 / 卸载 ----------------
    def install(self, src_dir) -> dict:
        src = Path(src_dir)
        if not src.exists() or not src.is_dir():
            return {"ok": False, "error": "目录不存在"}
        if not ((src / "plugin.json").exists() or (src / "manifest.json").exists()):
            return {"ok": False, "error": "缺少 plugin.json/manifest.json"}
        try:
            data = self._read_manifest_file(src) or {}
            name = data.get("name") or src.name
        except Exception as e:
            return {"ok": False, "error": "清单解析失败：{}".format(e)}
        dst = self.plugins_dir / name
        try:
            if dst.exists():
                import shutil
                shutil.rmtree(dst)
            import shutil
            shutil.copytree(src, dst)
        except OSError as e:
            return {"ok": False, "error": "复制失败：{}".format(e)}
        self.load_plugin(dst)
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
                return {"ok": False, "error": "删除失败：{}".format(e)}
            self._unload_locked(name)
        return {"ok": True, "name": name}

    # ---------------- 列表与查询 ----------------
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
        out: Dict[str, list] = {}
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

    # ---------------- 启用 / 禁用 ----------------
    def enable(self, name: str) -> bool:
        with self._lock:
            p = self.plugins.get(name)
            if not p:
                return False
            if not p.is_builtin and p.module is None:
                if not self.load_plugin(p.path):
                    return False
            p.enabled = True
            p.loaded_at = time.time()
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

    # ---------------- 钩子系统 ----------------
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

    # ---------------- 权限管理 ----------------
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

    # ---------------- 消息 / 响应 / 心跳分发 ----------------
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

    # ---------------- 插件工具（SDK 风格） ----------------
    def _index_tools(self, name: str):
        p = self.plugins.get(name)
        if p is None or not isinstance(p.module, PluginBase):
            return
        try:
            tools = p.module.register_tools() or []
        except Exception as e:
            logger.warning("插件 %s 注册工具失败: %s", name, e)
            return
        for tool in tools:
            try:
                tname = tool.get("name")
            except AttributeError:
                continue
            if not tname:
                continue
            self._tool_index[tname] = (name, tool)

    def get_plugin_tools(self) -> List[Dict]:
        """获取所有已启用插件的工具"""
        result: List[Dict] = []
        try:
            with self._lock:
                for tname, (pname, tool) in list(self._tool_index.items()):
                    p = self.plugins.get(pname)
                    if p is None or not p.enabled:
                        continue
                    item = dict(tool)
                    item.setdefault("tool_name", tname)
                    item.setdefault("plugin", pname)
                    result.append(item)
        except Exception as e:
            logger.warning("获取插件工具异常: %s", e)
        return result

    def call_plugin_tool(self, tool_name: str, args: Dict) -> str:
        """调用插件工具"""
        try:
            with self._lock:
                entry = self._tool_index.get(tool_name)
                if entry is None:
                    return "未找到插件工具: {}".format(tool_name)
                pname, tool = entry
                p = self.plugins.get(pname)
                if p is None or not p.enabled:
                    return "插件未启用: {}".format(pname)
                handler = tool.get("handler")
                if not callable(handler):
                    return "工具未提供 handler: {}".format(tool_name)
            result = handler(**(args or {}))
            return str(result)
        except Exception as e:
            logger.warning("调用插件工具异常 %s: %s", tool_name, e)
            return "工具调用失败: {}".format(e)

    # ---------------- 整体重载与统计 ----------------
    def reload(self) -> int:
        with self._lock:
            self.plugins = {}
            self._hooks.clear()
            self._tool_index = {}
        self._load_builtin()
        self._load_external()
        return len(self.plugins)

    def stats(self) -> dict:
        with self._lock:
            total = len(self.plugins)
            enabled = sum(1 for p in self.plugins.values() if p.enabled)
            builtin = sum(1 for p in self.plugins.values() if p.is_builtin)
            by_cat: Dict[str, int] = {}
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
