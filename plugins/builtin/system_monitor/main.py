# -*- coding: utf-8 -*-
"""system_monitor 插件

系统状态实时监控，基于 psutil 真实读取本机指标。
psutil 未安装时所有工具返回明确错误，绝不伪造数字。

工具：
  - get_cpu()              CPU 使用率 / 核心数 / 负载
  - get_memory()           物理内存 + 交换内存使用情况
  - get_disk()             各挂载点磁盘用量
  - get_processes(limit=5) 占用 CPU 最高的前 N 个进程
  - get_network()          网卡收发字节数 + 累计速率
"""
from __future__ import annotations

import threading
import time

try:
    from core.plugin_system import PluginBase
except ImportError:
    from backend.core.plugin_system import PluginBase

try:
    import psutil  # type: ignore
    _HAVE_PSUTIL = True
except Exception:
    psutil = None
    _HAVE_PSUTIL = False


class SystemMonitorPlugin(PluginBase):
    name = "system_monitor"
    version = "0.0.1"
    description = "系统监控：CPU / 内存 / 磁盘 / 进程 / 网络实时状态"
    author = "xiaoling"
    category = "tool"
    permissions = ["system"]

    def __init__(self, context=None):
        super().__init__(context)
        self._lock = threading.RLock()
        self._net_last = None  # (ts, bytes_sent, bytes_recv)

    # ---------------- 工具注册 ----------------
    def init(self):
        self._tools = [
            {
                "name": "get_cpu",
                "description": "读取 CPU 使用率 / 核心数 / 1 分钟负载",
                "args_schema": {},
                "handler": self.get_cpu,
            },
            {
                "name": "get_memory",
                "description": "读取物理内存与交换内存使用情况",
                "args_schema": {},
                "handler": self.get_memory,
            },
            {
                "name": "get_disk",
                "description": "读取各挂载点磁盘用量",
                "args_schema": {},
                "handler": self.get_disk,
            },
            {
                "name": "get_processes",
                "description": "按 CPU 占用排序返回前 N 个进程",
                "args_schema": {"limit": "int?"},
                "handler": self.get_processes,
            },
            {
                "name": "get_network",
                "description": "读取网卡累计收发字节与相邻两次调用间的速率",
                "args_schema": {},
                "handler": self.get_network,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    # ---------------- 工具实现 ----------------
    def get_cpu(self) -> dict:
        try:
            if not _HAVE_PSUTIL:
                return {"ok": False,
                        "error": "psutil 未安装，无法读取 CPU 状态"}
            percent = psutil.cpu_percent(interval=0.5)
            info = {
                "percent": percent,
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
            }
            try:
                load = psutil.getloadavg()
                info["load_avg"] = {"1m": load[0], "5m": load[1],
                                    "15m": load[2]}
            except (AttributeError, OSError):
                info["load_avg"] = None
            return {"ok": True, "cpu": info}
        except Exception as e:
            return {"ok": False,
                    "error": "get_cpu 失败: {}: {}".format(type(e).__name__, e)}

    def get_memory(self) -> dict:
        try:
            if not _HAVE_PSUTIL:
                return {"ok": False,
                        "error": "psutil 未安装，无法读取内存状态"}
            vm = psutil.virtual_memory()
            sm = psutil.swap_memory()
            return {"ok": True, "memory": {
                "total": vm.total, "available": vm.available,
                "used": vm.used, "percent": vm.percent,
                "swap_total": sm.total, "swap_used": sm.used,
                "swap_percent": sm.percent,
            }}
        except Exception as e:
            return {"ok": False,
                    "error": "get_memory 失败: {}: {}".format(
                        type(e).__name__, e)}

    def get_disk(self) -> dict:
        try:
            if not _HAVE_PSUTIL:
                return {"ok": False,
                        "error": "psutil 未安装，无法读取磁盘状态"}
            parts = []
            for p in psutil.disk_partitions(all=False):
                try:
                    u = psutil.disk_usage(p.mountpoint)
                except (PermissionError, OSError):
                    continue
                parts.append({
                    "device": p.device, "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total": u.total, "used": u.used, "free": u.free,
                    "percent": u.percent,
                })
            return {"ok": True, "disks": parts, "count": len(parts)}
        except Exception as e:
            return {"ok": False,
                    "error": "get_disk 失败: {}: {}".format(type(e).__name__, e)}

    def get_processes(self, limit: int = 5) -> dict:
        try:
            if not _HAVE_PSUTIL:
                return {"ok": False,
                        "error": "psutil 未安装，无法读取进程列表"}
            try:
                lim = max(1, min(int(limit), 20))
            except (TypeError, ValueError):
                lim = 5
            # 先预热一次，让 cpu_percent 有基准
            for p in psutil.process_iter(["pid", "name", "cpu_percent",
                                          "memory_percent"]):
                try:
                    p.cpu_percent(interval=None)
                except Exception:
                    pass
            time.sleep(0.3)
            rows = []
            for p in psutil.process_iter(["pid", "name", "username"]):
                try:
                    rows.append({
                        "pid": p.info.get("pid"),
                        "name": p.info.get("name") or "",
                        "username": p.info.get("username") or "",
                        "cpu_percent": p.cpu_percent(interval=None),
                        "memory_percent": round(p.memory_percent(), 2),
                    })
                except Exception:
                    continue
            rows.sort(key=lambda r: r.get("cpu_percent") or 0, reverse=True)
            return {"ok": True, "count": lim, "processes": rows[:lim]}
        except Exception as e:
            return {"ok": False,
                    "error": "get_processes 失败: {}: {}".format(
                        type(e).__name__, e)}

    def get_network(self) -> dict:
        try:
            if not _HAVE_PSUTIL:
                return {"ok": False,
                        "error": "psutil 未安装，无法读取网络状态"}
            io = psutil.net_io_counters()
            now = time.time()
            rate_up = rate_down = None
            with self._lock:
                if self._net_last is not None:
                    t0, s0, r0 = self._net_last
                    dt = now - t0
                    if dt > 0:
                        rate_up = round((io.bytes_sent - s0) / dt, 2)
                        rate_down = round((io.bytes_recv - r0) / dt, 2)
                self._net_last = (now, io.bytes_sent, io.bytes_recv)
            return {"ok": True, "network": {
                "bytes_sent": io.bytes_sent,
                "bytes_recv": io.bytes_recv,
                "packets_sent": io.packets_sent,
                "packets_recv": io.packets_recv,
                "upload_bytes_per_sec": rate_up,
                "download_bytes_per_sec": rate_down,
            }}
        except Exception as e:
            return {"ok": False,
                    "error": "get_network 失败: {}: {}".format(
                        type(e).__name__, e)}
