"""系统模块 - 硬件检测 + 设备信息 + 生命周期 + 自检"""
import platform
import subprocess
import time


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


# ===== 生命周期 =====
class Lifecycle:
    """生命周期管理"""

    def __init__(self):
        self.start_time = time.time()
        self.state = "init"
        self._handlers = {}

    def on(self, event: str, handler):
        """注册事件处理器"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def emit(self, event: str, *args):
        """触发事件"""
        if event in self._handlers:
            for handler in self._handlers[event]:
                try:
                    handler(*args)
                except Exception as e:
                    print(f"  [生命周期] {event} 处理器失败: {e}")

    def uptime(self) -> float:
        """运行时间（秒）"""
        return time.time() - self.start_time

    def set_state(self, state: str):
        """设置状态"""
        old = self.state
        self.state = state
        self.emit("state_changed", old, state)


# ===== 自检 =====
def selftest() -> dict:
    """全系统自检"""
    results = {}

    # 1. Python 版本
    results["python"] = f"{platform.python_version()}"

    # 2. 系统
    results["os"] = platform.system()

    # 3. GPU
    results["gpu"] = get_gpu_info()

    # 4. 内存
    mem = get_memory_info()
    results["memory"] = f"{mem['percent']}%"

    # 5. 关键模块
    modules = ["torch", "transformers", "peft"]
    for mod in modules:
        try:
            __import__(mod)
            results[mod] = "OK"
        except ImportError:
            results[mod] = "MISSING"

    return results


def print_selftest():
    """打印自检结果"""
    results = selftest()
    print("=== 自检结果 ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
