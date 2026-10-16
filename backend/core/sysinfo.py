# -*- coding: utf-8 -*-
"""跨平台实时系统资源采样。

为什么需要这个模块
==================
工作台（dashboard_page.dart）要显示 CPU / 内存 / 磁盘的实时占用，但**后端此前
没有任何"运行时资源采样"能力**（只有 DetectHardware 那种静态硬件清单：显存多大、
内存多大，不含"现在用了多少"）。

于是前端只能自己想办法，而且写法是**按平台去 shell 外部命令**：
    POSIX  → 读 /proc/stat、/proc/meminfo，再 Process.run('df', ...)
    Windows→ Process.run('wmic', ['OS', 'get', ...])
这带来三个实际问题：

    1. **Windows 上 CPU 与磁盘恒为 0%**
       —— `wmic` 从 Windows 10 21H1 起被弃用、24H2 起默认不再随系统安装，
          很多机器上直接"命令不存在"，拿不到值就只能显示 0，看起来像真的 0%。
    2. 每次刷新都 fork 进程，Windows 上尤其慢，还会闪一下控制台窗口。
    3. 采样口径散在 UI 层，前后端两套标准，数值对不上没法排查。

现在改为：**后端统一采样，前端只负责显示**。拿不到真实值就明确回报
``available: false``，让 UI 显示「—」，而不是拿 0 冒充 0%。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

__all__ = [
    'sample_stats',
    'cpu_count',
    'memory_usage',
    'disk_usage',
]

# 上次 CPU 采样快照（GetSystemTimes / /proc/stat 都需要两次采样求差）
_prev_cpu: dict = {}


def cpu_count() -> int:
    """返回可用 CPU 核心数（拿不到则返回 0，由调用方如实展示）。"""
    try:
        n = os.cpu_count()
        return int(n) if n else 0
    except Exception:                                             # noqa: BLE001
        return 0


# --------------------------------------------------------------------------- #
#  Windows
# --------------------------------------------------------------------------- #
def _cpu_percent_windows() -> float | None:
    """Windows CPU 占用：kernel32.GetSystemTimes 两次采样求差。

    不用 wmic：它在 Windows 10 21H1 起弃用、24H2 起默认不随系统安装，
    在缺它的机器上会静默失败，导致 UI 显示假的 0%。
    """
    try:
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD),
                        ("dwHighDateTime", wintypes.DWORD)]

        def _ft_to_int(ft: FILETIME) -> int:
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

        k = ctypes.windll.kernel32
        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
        if not k.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel),
                ctypes.byref(user)):
            return None
        idle_t = _ft_to_int(idle)
        # kernel 时间包含 idle 时间；总忙碌 = kernel + user - idle
        total = _ft_to_int(kernel) + _ft_to_int(user)
        return idle_t, total
    except Exception:                                             # noqa: BLE001
        return None


def _memory_windows() -> float | None:
    """Windows 内存占用百分比（不含缓存口径，与任务管理器基本一致）。"""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return float(st.dwMemoryLoad)
        return None
    except Exception:                                             # noqa: BLE001
        return None


def _disk_windows() -> float | None:
    """Windows 系统盘占用百分比。"""
    try:
        import ctypes

        free = ctypes.c_ulonglong()
        total = ctypes.c_ulonglong()
        total_free = ctypes.c_ulonglong()
        # 用系统盘（%SystemDrive%，通常是 C:\）
        root = os.environ.get('SystemDrive', 'C:') + os.sep
        ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(root), ctypes.byref(free),
            ctypes.byref(total), ctypes.byref(total_free))
        if ok and total.value > 0:
            used = total.value - free.value
            return round(used / total.value * 100.0, 2)
        return None
    except Exception:                                             # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
#  POSIX（Linux / Android / macOS）
# ---------------------------------------------------------------------------
def _cpu_percent_posix() -> float | None:
    """Linux/Android CPU 占用：/proc/stat 两次求差。"""
    try:
        def _read():
            with open('/proc/stat', encoding='utf-8') as f:
                parts = f.readline().split()
            return [int(x) for x in parts[1:]]

        a = _read()
        time.sleep(0.12)
        b = _read()
        idle_a, idle_b = a[3] + (a[4] if len(a) > 4 else 0), b[3] + (b[4] if len(b) > 4 else 0)
        total_a, total_b = sum(a), sum(b)
        dt = total_b - total_a
        di = idle_b - idle_a
        if dt <= 0:
            return None
        return round((1 - di / dt) * 100.0, 2)
    except Exception:                                             # noqa: BLE001
        return None


def _memory_posix() -> float | None:
    """Linux/Android 内存占用：/proc/meminfo。"""
    try:
        total = avail = 0.0
        with open('/proc/meminfo', encoding='utf-8') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    total = float(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    avail = float(line.split()[1])
        if total > 0:
            return round((total - avail) / total * 100.0, 2)
        return None
    except Exception:                                             # noqa: BLE001
        return None


def _disk_posix() -> float | None:
    """磁盘占用：os.statvfs('/')。"""
    try:
        st = os.statvfs('/')
        total = st.f_blocks * st.f_frsize
        if total <= 0:
            return None
        avail = st.f_bavail * st.f_frsize
        used = total - avail
        return round(used / total * 100.0, 2)
    except Exception:                                             # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
#  统一入口
# --------------------------------------------------------------------------- #
def _try_psutil() -> dict | None:
    """psutil 可用时优先用它：口径统一、跨平台可靠。"""
    try:
        import psutil
    except Exception:                                             # noqa: BLE001
        return None
    try:
        cpu = psutil.cpu_percent(interval=0.12)
        vm = psutil.virtual_memory()
        du = psutil.disk_usage(os.path.abspath(os.sep))
        return {
            "cpu_percent": float(cpu),
            "mem_percent": float(vm.percent),
            "disk_percent": float(du.percent),
            "available": True,
            "source": "psutil",
        }
    except Exception:                                             # noqa: BLE001
        return None


def sample_stats() -> dict:
    """采样一次系统资源占用。

    返回字段说明：
        available : bool   —— 是否**真的**采样到了资源数据。False 时 UI 应显示「—」，
                              不要把下面的 0 当成"占用 0%"。
        source    : str    —— 采样来源（psutil / native / unavailable）
        cpu_percent / mem_percent / disk_percent : float
        cpu_cores : int
        platform  : str
        ts        : float  —— 采样时刻（秒级 Unix 时间戳）
    """
    out = {
        "ok": True,
        "available": False,
        "source": "unavailable",
        "cpu_percent": 0.0,
        "mem_percent": 0.0,
        "disk_percent": 0.0,
        "cpu_cores": cpu_count(),
        "platform": _platform_name(),
        "ts": time.time(),
    }

    # 1) psutil（最可靠）
    got = _try_psutil()
    if got:
        out.update(got)
        return out

    # 2) 原生兜底（不装 psutil 也要能出真实值）
    try:
        if os.name == 'nt':
            cpu = _cpu_percent_windows()
            if isinstance(cpu, tuple):
                cpu = None
            mem = _memory_windows()
            disk = _disk_windows()
        elif os.path.exists('/proc/stat'):
            cpu = _cpu_percent_posix()
            mem = _memory_posix()
            disk = _disk_posix()
        else:
            cpu = mem = disk = None

        # macOS 无 /proc：用 sysctl 拿内存（CPU 用 load average 近似也无意义，
        # 故 macOS 且无 psutil 时如实回报不可用，不编造）。
        if sys_darwin() and mem is None:
            mem = _memory_macos()

        if any(v is not None for v in (cpu, mem, disk)):
            out.update({
                "available": True,
                "source": "native",
                "cpu_percent": float(cpu or 0.0),
                "mem_percent": float(mem or 0.0),
                "disk_percent": float(disk or 0.0),
            })
    except Exception:                                             # noqa: BLE001
        pass
    return out


def sys_darwin() -> bool:
    try:
        import platform as _p
        return _p.system().lower() == 'darwin'
    except Exception:                                             # noqa: BLE001
        return False


def _memory_macos() -> float | None:
    """macOS 无 /proc/meminfo：退到 sysctl 口径（hw.memsize + vm 统计）。

    只保证"能用且量级正确"；拿不到就返回 None，绝不猜测。
    """
    try:
        import subprocess as _sp
        total = None
        r = _sp.run(['sysctl', '-n', 'hw.memsize'], capture_output=True,
                    text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip().isdigit():
            total = float(r.stdout.strip())
        if not total:
            return None
        # vm_stat 里 page size 与 free/speculative 页数可算出空闲量
        ps = _sp.run(['vm_stat'], capture_output=True, text=True, timeout=5)
        if ps.returncode != 0:
            return None
        page_size = 4096.0
        free_pages = 0.0
        for line in ps.stdout.splitlines():
            low = line.lower()
            if 'page size of' in low:
                try:
                    page_size = float(line.split('page size of')[1].split('bytes')[0].strip())
                except Exception:                                 # noqa: BLE001
                    pass
            elif low.startswith(('pages free', 'pages speculative')):
                try:
                    free_pages += float(line.split(':')[1].strip().rstrip('.'))
                except Exception:                                 # noqa: BLE001
                    pass
        avail = free_pages * page_size
        if avail <= 0:
            return None
        return round((total - avail) / total * 100.0, 2)
    except Exception:                                             # noqa: BLE001
        return None


def _platform_name() -> str:
    try:
        import platform as _p
        return f'{_p.system()} {_p.release()}'
    except Exception:                                             # noqa: BLE001
        return ''
