import json
import os
import importlib.util
import threading
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class PluginBase:
    """插件基类，所有插件继承此类"""

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

    def register_commands(self) -> Dict[str, callable]:
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
    """插件管理器：加载、卸载、热重载、依赖管理"""

    def __init__(self, plugins_dir: str = "data/plugins"):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, PluginBase] = {}   # name -> PluginBase
        self.manifests: Dict[str, Dict] = {}        # name -> manifest dict
        self.plugin_paths: Dict[str, str] = {}      # name -> directory path
        self._tool_index: Dict[str, Tuple[str, Dict]] = {}  # tool_name -> (plugin_name, tool_dict)
        self._lock = threading.RLock()
        os.makedirs(plugins_dir, exist_ok=True)

    def check_dependencies(self, manifest: Dict) -> Tuple[bool, str]:
        """检查依赖是否满足，返回 (ok, error_msg)"""
        deps = manifest.get("dependencies") or []
        if not deps:
            return True, ""
        for dep in deps:
            if dep not in self.plugins:
                return False, "缺少依赖插件: {}".format(dep)
        return True, ""

    def load_plugin(self, plugin_path: str) -> bool:
        """从目录加载插件：读取plugin.json，动态导入entry，实例化并init"""
        try:
            with self._lock:
                manifest_path = os.path.join(plugin_path, "plugin.json")
                if not os.path.isfile(manifest_path):
                    logger.warning("插件缺少 plugin.json: %s", plugin_path)
                    return False

                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                except Exception as e:
                    logger.warning("插件 manifest 解析失败 %s: %s", plugin_path, e)
                    return False

                name = manifest.get("name")
                if not name or not isinstance(name, str):
                    logger.warning("插件 manifest 缺少 name: %s", plugin_path)
                    return False

                ok, err = self.check_dependencies(manifest)
                if not ok:
                    logger.warning("插件 %s 依赖不满足: %s", name, err)
                    return False

                entry = manifest.get("entry", "main.py")
                entry_path = os.path.join(plugin_path, entry)
                if not os.path.isfile(entry_path):
                    logger.warning("插件入口文件不存在: %s", entry_path)
                    return False

                module_name = "xl_plugin_{}".format(name)
                spec = importlib.util.spec_from_file_location(module_name, entry_path)
                if spec is None or spec.loader is None:
                    logger.warning("无法创建模块规范: %s", entry_path)
                    return False
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    logger.warning("插件模块加载失败 %s: %s", name, e)
                    return False

                plugin_cls = None
                for attr in vars(module).values():
                    if isinstance(attr, type) and issubclass(attr, PluginBase) and attr is not PluginBase:
                        plugin_cls = attr
                        break
                if plugin_cls is None:
                    logger.warning("插件 %s 未找到 PluginBase 子类", name)
                    return False

                if name in self.plugins:
                    self._unload_locked(name)

                try:
                    instance = plugin_cls(context=self)
                except Exception as e:
                    logger.warning("插件 %s 实例化失败: %s", name, e)
                    return False

                try:
                    instance.init()
                except Exception as e:
                    logger.warning("插件 %s init 失败: %s", name, e)
                    return False

                instance.enabled = True
                self.plugins[name] = instance
                self.manifests[name] = manifest
                self.plugin_paths[name] = plugin_path
                self._index_tools(name)
                logger.info("插件已加载: %s v%s", name, instance.version)
                return True
        except Exception as e:
            logger.warning("加载插件异常 %s: %s", plugin_path, e)
            return False

    def _unload_locked(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        if plugin is None:
            return False
        try:
            plugin.dispose()
        except Exception as e:
            logger.warning("插件 %s dispose 失败: %s", name, e)
        try:
            plugin.enabled = False
        except Exception:
            pass
        self.plugins.pop(name, None)
        self.manifests.pop(name, None)
        self.plugin_paths.pop(name, None)
        self._tool_index = {k: v for k, v in self._tool_index.items() if v[0] != name}
        logger.info("插件已卸载: %s", name)
        return True

    def unload_plugin(self, name: str) -> bool:
        """卸载插件：调用dispose，从字典移除"""
        try:
            with self._lock:
                return self._unload_locked(name)
        except Exception as e:
            logger.warning("卸载插件异常 %s: %s", name, e)
            return False

    def reload_plugin(self, name: str) -> bool:
        """热重载：unload + load"""
        try:
            with self._lock:
                path = self.plugin_paths.get(name)
                if path is None:
                    logger.warning("无法重载未加载的插件: %s", name)
                    return False
                self._unload_locked(name)
                return self.load_plugin(path)
        except Exception as e:
            logger.warning("重载插件异常 %s: %s", name, e)
            return False

    def load_all(self):
        """加载 plugins_dir 下所有插件目录"""
        try:
            if not os.path.isdir(self.plugins_dir):
                return
            with self._lock:
                entries = sorted(os.listdir(self.plugins_dir))
            for entry in entries:
                sub = os.path.join(self.plugins_dir, entry)
                if os.path.isdir(sub):
                    self.load_plugin(sub)
        except Exception as e:
            logger.warning("批量加载插件异常: %s", e)

    def _index_tools(self, name: str):
        plugin = self.plugins.get(name)
        if plugin is None:
            return
        try:
            tools = plugin.register_tools() or []
        except Exception as e:
            logger.warning("插件 %s 注册工具失败: %s", name, e)
            return
        for tool in tools:
            tname = tool.get("name")
            if not tname:
                continue
            self._tool_index[tname] = (name, tool)

    def get_plugin_tools(self) -> List[Dict]:
        """获取所有已启用插件的工具"""
        result: List[Dict] = []
        try:
            with self._lock:
                for tname, (pname, tool) in list(self._tool_index.items()):
                    plugin = self.plugins.get(pname)
                    if plugin is None or not plugin.enabled:
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
                plugin = self.plugins.get(pname)
                if plugin is None or not plugin.enabled:
                    return "插件未启用: {}".format(pname)
                handler = tool.get("handler")
                if not callable(handler):
                    return "工具未提供 handler: {}".format(tool_name)
            result = handler(**(args or {}))
            return str(result)
        except Exception as e:
            logger.warning("调用插件工具异常 %s: %s", tool_name, e)
            return "工具调用失败: {}".format(e)

    def list_plugins(self) -> List[Dict]:
        """列出所有插件信息（含已加载/未加载状态）"""
        result: List[Dict] = []
        try:
            with self._lock:
                loaded = {}
                for name, plugin in self.plugins.items():
                    info = plugin.get_info()
                    info["loaded"] = True
                    info["enabled"] = plugin.enabled
                    loaded[name] = info
                    result.append(info)

                if os.path.isdir(self.plugins_dir):
                    for entry in sorted(os.listdir(self.plugins_dir)):
                        sub = os.path.join(self.plugins_dir, entry)
                        mp = os.path.join(sub, "plugin.json")
                        if not os.path.isdir(sub) or not os.path.isfile(mp):
                            continue
                        name = entry
                        if name in loaded:
                            continue
                        try:
                            with open(mp, "r", encoding="utf-8") as f:
                                manifest = json.load(f)
                        except Exception:
                            continue
                        result.append({
                            "name": manifest.get("name", entry),
                            "version": manifest.get("version", "0.0.1"),
                            "description": manifest.get("description", ""),
                            "author": manifest.get("author", ""),
                            "category": manifest.get("category", "tool"),
                            "permissions": manifest.get("permissions", []),
                            "loaded": False,
                            "enabled": False,
                        })
        except Exception as e:
            logger.warning("列出插件异常: %s", e)
        return result
