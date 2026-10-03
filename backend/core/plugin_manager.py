"""插件管理器 - 万物皆插件"""
import importlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .platform import get_user_data_dir


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    author: str = ""
    permissions: list[str] = field(default_factory=list)
    entry: str = "main"  # 入口函数名


@dataclass
class Plugin:
    manifest: PluginManifest
    path: Path
    enabled: bool = False
    module: object = None


class PluginManager:
    """插件管理器"""

    BUILTIN_PLUGINS = [
        {
            "name": "deep_chat",
            "version": "0.1.0",
            "description": "深度对话模式 - 更深入的思考和回复",
            "entry": "on_message",
        },
        {
            "name": "agent_task",
            "version": "0.1.0",
            "description": "Agent 任务执行 - 帮你做事",
            "entry": "on_message",
        },
        {
            "name": "reminder",
            "version": "0.1.0",
            "description": "定时提醒 - 记住你要做的事",
            "entry": "on_tick",
        },
        {
            "name": "read_aloud",
            "version": "0.1.0",
            "description": "语音朗读 - 用小凌的声音读出来",
            "entry": "on_response",
        },
        {
            "name": "distill_train",
            "version": "0.1.0",
            "description": "蒸馏训练 - 小凌自己成长",
            "entry": "on_idle",
        },
        {
            "name": "emotion_system",
            "version": "0.1.0",
            "description": "表情系统 - 小凌有情绪变化",
            "entry": "on_message",
        },
    ]

    def __init__(self):
        self.plugins_dir = get_user_data_dir() / "plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.plugins: dict[str, Plugin] = {}
        self._hooks: dict[str, list[Callable]] = {}
        self._load_builtin()

    def _load_builtin(self):
        """加载内置插件列表"""
        for p in self.BUILTIN_PLUGINS:
            manifest = PluginManifest(**p)
            self.plugins[p["name"]] = Plugin(
                manifest=manifest,
                path=Path("builtin"),
            )

    def list_plugins(self) -> list[dict]:
        """列出所有插件"""
        return [
            {
                "name": p.manifest.name,
                "version": p.manifest.version,
                "description": p.manifest.description,
                "enabled": p.enabled,
            }
            for p in self.plugins.values()
        ]

    def enable(self, name: str) -> bool:
        """启用插件"""
        if name not in self.plugins:
            return False
        self.plugins[name].enabled = True
        return True

    def disable(self, name: str) -> bool:
        """禁用插件"""
        if name not in self.plugins:
            return False
        self.plugins[name].enabled = False
        return True

    def is_enabled(self, name: str) -> bool:
        return self.plugins.get(name, Plugin(manifest=None, path=None)).enabled

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

    def process_message(self, message: str) -> str:
        """消息处理流水线：经过所有启用的插件"""
        result = message
        for name, plugin in self.plugins.items():
            if not plugin.enabled:
                continue
            # 这里实际调用插件的处理函数
            # 目前是占位，后续实现插件加载
        return result

    def get_enabled_names(self) -> list[str]:
        return [name for name, p in self.plugins.items() if p.enabled]
