"""守卫系统 - 离线守卫 + 运行时守卫（循环检测）"""
import socket
import json
import time


# ===== 离线守卫 =====
class OfflineGuard:
    """网络检测 + 离线模式管理"""

    def __init__(self):
        self.online = None
        self.last_check = 0
        self.check_interval = 30

    def is_online(self, force=False):
        """检测网络是否可用"""
        now = time.time()
        if not force and self.online is not None and (now - self.last_check) < self.check_interval:
            return self.online
        self.last_check = now
        try:
            socket.setdefaulttimeout(2)
            socket.getaddrinfo("gitee.com", 443, socket.AF_INET, socket.SOCK_STREAM)
            self.online = True
        except Exception:
            self.online = False
        return self.online

    def status_text(self):
        on = self.is_online()
        return "在线" if on else "离线模式——本地模型完整可用"


# ===== 运行时守卫 =====
class Guard:
    """运行时守卫 - 循环检测"""

    SOFT_THRESHOLD = 3
    HARD_THRESHOLD = 5

    def __init__(self):
        self.tool_history = []
        self._consecutive = []

    def _normalize(self, obj):
        if isinstance(obj, dict):
            return {k: self._normalize(obj[k]) for k in sorted(obj.keys())}
        if isinstance(obj, (list, tuple)):
            return [self._normalize(x) for x in obj]
        return obj

    def _signature(self, name, args):
        try:
            return name + "|" + json.dumps(self._normalize(args), sort_keys=True, ensure_ascii=False)
        except Exception:
            return name + "|" + str(args)

    def record_tool(self, name, args):
        self.tool_history.append({"name": name, "args": str(args)[:100], "time": time.time()})
        if len(self.tool_history) > 100:
            self.tool_history = self.tool_history[-100:]
        self._consecutive.append(self._signature(name, args))
        if len(self._consecutive) > 20:
            self._consecutive = self._consecutive[-20:]

    def check(self, name, args):
        """两级循环检测"""
        sig = self._signature(name, args)
        run = 0
        for s in reversed(self._consecutive):
            if s == sig:
                run += 1
            else:
                break
        if run >= self.HARD_THRESHOLD:
            return ("hard", f"硬停止：{name} 连续调用 {run} 次")
        if run >= self.SOFT_THRESHOLD:
            return ("soft", f"软警告：{name} 连续调用 {run} 次")
        return (None, None)
