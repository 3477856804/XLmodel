"""插件管理器 - 万物皆插件

支持：
- 内置插件（6个）
- 外部插件（从 plugins/ 目录加载）
- 启用/禁用开关
- 钩子系统（on_message/on_response/on_tick/on_idle）
- 权限检查
"""
import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .system import get_user_data_dir


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    author: str = ""
    permissions: list[str] = field(default_factory=list)
    entry: str = "main"
    min_app_version: str = "0.0.1"


@dataclass
class Plugin:
    manifest: PluginManifest
    path: Path
    enabled: bool = False
    module: object = None
    is_builtin: bool = False


# 权限定义
PERMISSIONS = {
    "chat:read": "读取聊天消息",
    "chat:write": "发送消息",
    "file:read": "读取文件",
    "file:write": "写入文件",
    "network": "网络访问",
    "system": "系统操作",
}


class PluginManager:
    """插件管理器"""

    BUILTIN_PLUGINS = [
        {
            "name": "deep_chat",
            "version": "0.1.0",
            "description": "深度对话模式 - 更深入的思考和回复",
            "entry": "on_message",
            "permissions": ["chat:read", "chat:write"],
        },
        {
            "name": "agent_task",
            "version": "0.1.0",
            "description": "Agent 任务执行 - 帮你做事",
            "entry": "on_message",
            "permissions": ["chat:read", "chat:write", "file:read", "network"],
        },
        {
            "name": "reminder",
            "version": "0.1.0",
            "description": "定时提醒 - 记住你要做的事",
            "entry": "on_tick",
            "permissions": ["system"],
        },
        {
            "name": "read_aloud",
            "version": "0.1.0",
            "description": "语音朗读 - 用小凌的声音读出来",
            "entry": "on_response",
            "permissions": ["chat:read"],
        },
        {
            "name": "distill_train",
            "version": "0.1.0",
            "description": "蒸馏训练 - 小凌自己成长",
            "entry": "on_idle",
            "permissions": ["file:read", "file:write", "system"],
        },
        {
            "name": "emotion_system",
            "version": "0.1.0",
            "description": "表情系统 - 小凌有情绪变化",
            "entry": "on_message",
            "permissions": ["chat:read"],
        },
    ]

    def __init__(self, plugins_dir: str = None):
        self.plugins_dir = Path(plugins_dir) if plugins_dir else get_user_data_dir() / "plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.plugins: dict[str, Plugin] = {}
        self._hooks: dict[str, list[Callable]] = {}
        self._load_builtin()
        self._load_external()

    def _load_builtin(self):
        """加载内置插件"""
        for p in self.BUILTIN_PLUGINS:
            manifest = PluginManifest(**p)
            self.plugins[p["name"]] = Plugin(
                manifest=manifest,
                path=Path("builtin"),
                is_builtin=True,
            )

    def _load_external(self):
        """从 plugins/ 目录加载外部插件"""
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            manifest_file = plugin_dir / "manifest.json"
            if not manifest_file.exists():
                continue
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                manifest = PluginManifest(**manifest_data)
                self.plugins[manifest.name] = Plugin(
                    manifest=manifest,
                    path=plugin_dir,
                )
            except Exception as e:
                print(f"  [Plugin] 加载插件 {plugin_dir.name} 失败: {e}")

    def list_plugins(self) -> list[dict]:
        """列出所有插件"""
        return [
            {
                "name": p.manifest.name,
                "version": p.manifest.version,
                "description": p.manifest.description,
                "author": p.manifest.author,
                "enabled": p.enabled,
                "builtin": p.is_builtin,
                "permissions": p.manifest.permissions,
            }
            for p in self.plugins.values()
        ]

    def enable(self, name: str) -> bool:
        """启用插件"""
        if name not in self.plugins:
            return False
        plugin = self.plugins[name]
        # 外部插件需要加载模块
        if not plugin.is_builtin and plugin.module is None:
            if not self._load_plugin_module(plugin):
                return False
        plugin.enabled = True
        self._register_plugin_hooks(plugin)
        return True

    def disable(self, name: str) -> bool:
        """禁用插件"""
        if name not in self.plugins:
            return False
        self.plugins[name].enabled = False
        return True

    def _load_plugin_module(self, plugin: Plugin) -> bool:
        """加载外部插件的 Python 模块"""
        main_file = plugin.path / "main.py"
        if not main_file.exists():
            return False
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin.manifest.name}",
                main_file,
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            plugin.module = module
            return True
        except Exception as e:
            print(f"  [Plugin] 加载模块失败: {e}")
            return False

    def _register_plugin_hooks(self, plugin: Plugin):
        """注册插件的钩子函数"""
        if plugin.module is None:
            return
        hook_name = plugin.manifest.entry
        handler = getattr(plugin.module, hook_name, None)
        if callable(handler):
            self.on(hook_name, handler)

    def is_enabled(self, name: str) -> bool:
        p = self.plugins.get(name)
        return p.enabled if p else False

    def on(self, hook: str, callback: Callable):
        """注册钩子"""
        if hook not in self._hooks:
            self._hooks[hook] = []
        self._hooks[hook].append(callback)

    def emit(self, hook: str, *args, **kwargs):
        """触发钩子"""
        if hook not in self._hooks:
            return
        for cb in self._hooks[hook]:
            try:
                cb(*args, **kwargs)
            except Exception as e:
                print(f"  [Plugin] {hook} 钩子执行失败: {e}")

    def check_permission(self, plugin_name: str, permission: str) -> bool:
        """检查插件是否有权限"""
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            return False
        return permission in plugin.manifest.permissions

    def process_message(self, message: str) -> str:
        """消息处理流水线：经过所有启用的插件"""
        result = message
        self.emit("on_message", result)
        return result

    def get_enabled_names(self) -> list[str]:
        return [name for name, p in self.plugins.items() if p.enabled]

    def get_permission_list(self) -> dict:
        """返回所有可用权限"""
        return PERMISSIONS
