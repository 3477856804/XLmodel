"""离线守卫 - 网络检测 + 离线模式"""
import socket
import time


class OfflineGuard:
    """网络检测 + 离线模式管理。断网时本地模型完整可用。"""

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
        if on:
            return "在线"
        return "离线模式——本地模型完整可用"
