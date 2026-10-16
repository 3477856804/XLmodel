"""兼容层：插件系统已统一迁移到 plugin_system.py。

历史上本文件曾自带一套 PluginManager（动态导入 / 热重载 / 依赖检查），
与 config.py 中的另一套 PluginManager 并行存在、互不引用。
现已合并为唯一实现 backend/core/plugin_system.py。

本文件仅做再导出，保持任何旧导入路径可用：
    from core.plugin_sdk import PluginManager, PluginBase   # 仍然可用
"""
from .plugin_system import (  # noqa: F401
    PluginBase,
    PluginManager,
    PluginManifest,
    Plugin,
    BUILTIN_PLUGINS,
    PERMISSIONS,
    HOOKS,
)

__all__ = [
    "PluginBase",
    "PluginManager",
    "PluginManifest",
    "Plugin",
    "BUILTIN_PLUGINS",
    "PERMISSIONS",
    "HOOKS",
]
