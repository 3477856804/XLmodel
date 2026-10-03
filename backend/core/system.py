"""系统信息 - 硬件检测 + 设备信息"""
import platform
import subprocess


# ===== 硬件检测 =====
def get_cpu_info() -> str:
    """获取 CPU 信息"""
    return platform.processor() or "Unknown CPU"


def get_memory_info() -> dict:
    """获取内存信息"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {"total": mem.total, "available": mem.available, "percent": mem.percent}
    except ImportError:
        return {"total": 0, "available": 0, "percent": 0}


def get_gpu_info() -> str:
    """获取 GPU 信息"""
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
        return "CPU only"
    except ImportError:
        return "Unknown"


# ===== 设备信息 =====
class DeviceInfo:
    """设备信息"""

    def __init__(self):
        self.os = platform.system()
        self.os_version = platform.version()
        self.machine = platform.machine()
        self.processor = get_cpu_info()
        self.memory = get_memory_info()
        self.gpu = get_gpu_info()

    def summary(self) -> str:
        """设备摘要"""
        return f"{self.os} {self.machine} | {self.processor} | {self.gpu}"

    def is_gpu_available(self) -> bool:
        """是否有 GPU"""
        return self.gpu != "CPU only" and self.gpu != "Unknown"


# ===== 系统检测 =====
def detect_best_device() -> str:
    """检测最佳运行设备"""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    except ImportError:
        return "cpu"


def get_system_info() -> dict:
    """获取系统信息"""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": get_cpu_info(),
        "memory": get_memory_info(),
        "gpu": get_gpu_info(),
        "best_device": detect_best_device(),
    }
