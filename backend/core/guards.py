"""小凌 · 守卫（离线检测 + 循环检测）"""
import json
import socket
import threading
import time


class OfflineGuard:
    def __init__(self, host: str = "gitee.com", port: int = 443,
                 interval: float = 30.0, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.interval = interval
        self.timeout = timeout
        self.online: bool | None = None
        self.last_check = 0.0
        self._lock = threading.RLock()

    def is_online(self, force: bool = False) -> bool:
        now = time.time()
        with self._lock:
            if not force and self.online is not None and (now - self.last_check) < self.interval:
                return self.online
            self.last_check = now
        ok = False
        try:
            prev = socket.getdefaulttimeout()
            socket.setdefaulttimeout(self.timeout)
            try:
                socket.getaddrinfo(self.host, self.port,
                                   socket.AF_INET, socket.SOCK_STREAM)
                ok = True
            finally:
                socket.setdefaulttimeout(prev)
        except (socket.gaierror, socket.timeout, OSError):
            ok = False
        with self._lock:
            self.online = ok
        return ok

    def status_text(self) -> str:
        return "在线" if self.is_online() else "离线模式——本地模型完整可用"

    def reset(self):
        with self._lock:
            self.online = None
            self.last_check = 0.0

    def snapshot(self) -> dict:
        return {"online": self.online, "last_check": self.last_check,
                "host": self.host}


class Guard:
    SOFT_THRESHOLD = 3
    HARD_THRESHOLD = 5
    MAX_HISTORY = 100
    WINDOW = 20

    def __init__(self):
        self.tool_history: list[dict] = []
        self._consecutive: list[str] = []
        self._lock = threading.RLock()

    @staticmethod
    def _normalize(obj):
        if isinstance(obj, dict):
            return {k: Guard._normalize(obj[k]) for k in sorted(obj.keys())}
        if isinstance(obj, (list, tuple)):
            return [Guard._normalize(x) for x in obj]
        return obj

    def _signature(self, name: str, args) -> str:
        try:
            return f"{name}|{json.dumps(self._normalize(args), sort_keys=True, ensure_ascii=False)}"
        except Exception:
            return f"{name}|{args}"

    def record_tool(self, name: str, args):
        sig = self._signature(name, args)
        with self._lock:
            self.tool_history.append({"name": name, "args": str(args)[:100],
                                      "time": time.time()})
            if len(self.tool_history) > self.MAX_HISTORY:
                self.tool_history = self.tool_history[-self.MAX_HISTORY:]
            self._consecutive.append(sig)
            if len(self._consecutive) > self.WINDOW:
                self._consecutive = self._consecutive[-self.WINDOW:]

    def check(self, name: str, args) -> tuple:
        sig = self._signature(name, args)
        with self._lock:
            run = 0
            for s in reversed(self._consecutive):
                if s == sig:
                    run += 1
                else:
                    break
        if run >= self.HARD_THRESHOLD:
            return "hard", f"硬停止：{name} 连续调用 {run} 次"
        if run >= self.SOFT_THRESHOLD:
            return "soft", f"软警告：{name} 连续调用 {run} 次"
        return None, None

    def reset(self):
        with self._lock:
            self.tool_history.clear()
            self._consecutive.clear()

    def stats(self) -> dict:
        with self._lock:
            return {"history": len(self.tool_history),
                    "window": len(self._consecutive)}