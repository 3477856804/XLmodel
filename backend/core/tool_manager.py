"""工具管理器 - 注册/执行/缓存工具"""
import time
from pathlib import Path


class ToolManager:
    """工具管理器"""

    CORE_TOOLS = {"get_time", "read_file", "write_file", "list_dir", "calculator", "remember", "recall"}
    WRITE_TOOLS = {"write_file", "str_replace", "run_cmd", "pip_install"}

    def __init__(self, base_dir=None, memory=None):
        self.base_dir = Path(base_dir) if base_dir else Path(".")
        self.memory = memory
        self.tools = {}
        self.before_hooks = []
        self.after_hooks = []
        self._tool_cache = {}
        self._tool_cache_ttl = 60.0
        self._register()

    def register(self, name, func, desc):
        self.tools[name] = {"func": func, "desc": desc}

    def add_before_hook(self, hook):
        self.before_hooks.append(hook)

    def add_after_hook(self, hook):
        self.after_hooks.append(hook)

    CACHEABLE_TOOLS = {"get_time", "calculator", "list_dir", "read_file"}

    def execute(self, name, args):
        if name not in self.tools:
            return f"未知工具：{name}"
        if name in self.CACHEABLE_TOOLS:
            key = (name, str(args))
            hit = self._tool_cache.get(key)
            if hit and (time.time() - hit[0]) < self._tool_cache_ttl:
                return hit[1]
        cur_args = dict(args) if isinstance(args, dict) else {}
        for hook in self.before_hooks:
            try:
                out = hook(name, cur_args)
            except Exception as e:
                return f"before hook异常：{e}"
            if out:
                if isinstance(out, dict) and out.get("block"):
                    return str(out.get("reason", "被拦截"))
                if isinstance(out, dict) and "args" in out:
                    cur_args = out["args"]
        try:
            result = str(self.tools[name]["func"](**cur_args))
        except Exception as e:
            result = f"工具出错：{e}"
        if name in self.CACHEABLE_TOOLS:
            self._tool_cache[(name, str(cur_args))] = (time.time(), result)
        for hook in self.after_hooks:
            try:
                out = hook(name, result)
            except Exception:
                out = None
            if out is not None:
                result = str(out)
        return result

    def _register(self):
        self.register("get_time", lambda **kw: time.strftime("%Y-%m-%d %H:%M:%S"), "获取当前时间")
        self.register("calculator", lambda expr="", **kw: eval(expr, {"__builtins__": {}}, {}), "计算器")

    def tool_list_text(self):
        return "可用工具：" + ", ".join(self.tools.keys())
