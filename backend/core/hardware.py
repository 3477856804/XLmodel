"""硬件检测模块 - 检测用户硬件，用于智能模型推荐"""
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HardwareInfo:
    vram_gb: float = 0.0          # 显卡显存 GB
    ram_gb: float = 0.0           # 系统内存 GB
    cpu_cores: int = 0            # CPU 核心数
    disk_free_gb: float = 0.0     # 磁盘剩余空间 GB
    gpu_name: str = "Unknown"     # 显卡型号
    platform: str = "unknown"     # 平台 win/mac/linux
    has_cuda: bool = False        # 是否有 CUDA
    has_metal: bool = False        # 是否有 Metal (Apple Silicon)


def detect_hardware() -> HardwareInfo:
    """检测用户硬件信息"""
    info = HardwareInfo()

    # 平台
    from .platform import Platform
    info.platform = Platform.current()

    # CPU 核心数
    import os
    info.cpu_cores = os.cpu_count() or 4

    # 系统内存
    info.ram_gb = _detect_ram()

    # 磁盘空间
    info.disk_free_gb = _detect_disk()

    # GPU 显存
    info.vram_gb, info.gpu_name, info.has_cuda = _detect_gpu()

    # Apple Silicon
    if Platform.is_mac() and "Apple" in info.gpu_name:
        info.has_metal = True
        # Apple Unified Memory，用系统内存估算
        if info.vram_gb == 0:
            info.vram_gb = info.ram_gb * 0.5

    return info


def _detect_ram() -> float:
    """检测系统内存"""
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        return 8.0  # 默认估算


def _detect_disk() -> float:
    """检测当前目录所在磁盘剩余空间"""
    import shutil
    total, used, free = shutil.disk_usage(".")
    return free / (1024 ** 3)


def _detect_gpu() -> tuple[float, str, bool]:
    """检测 GPU 信息：(显存GB, 显卡名, 是否有CUDA)"""
    vram = 0.0
    gpu_name = "Unknown"
    has_cuda = False

    # NVIDIA CUDA
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                line = result.stdout.strip().split("\n")[0]
                parts = [p.strip() for p in line.split(",")]
                gpu_name = parts[0]
                vram = float(parts[1]) / 1024  # MiB -> GB
                has_cuda = True
        except Exception:
            pass

    # AMD ROCm
    if shutil.which("rocm-smi"):
        try:
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram", "--json"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                gpu_name = "AMD GPU (ROCm)"
                # 解析 JSON 获取显存
                import json
                data = json.loads(result.stdout)
                for k, v in data.items():
                    if "vram" in v:
                        vram = float(v["vram"]) / (1024 ** 3)
                        break
        except Exception:
            pass

    # Apple Silicon (macOS)
    from .platform import Platform
    if Platform.is_mac():
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                displays = data.get("SPDisplaysDataType", [])
                if displays:
                    gpu_name = displays[0].get("sppci_model", "Apple Silicon")
        except Exception:
            pass

    return vram, gpu_name, has_cuda


# 模型硬件需求表（类似 CanIRun.ai）
MODEL_REQUIREMENTS = [
    {
        "name": "Qwen3-0.6B",
        "params": "0.6B",
        "quant": "Q4_K_M",
        "vram_gb": 1.5,
        "ram_gb": 3.0,
        "quality": 60,
        "context": "32K",
        "size_mb": 450,
    },
    {
        "name": "Qwen3-1.7B",
        "params": "1.7B",
        "quant": "Q4_K_M",
        "vram_gb": 2.5,
        "ram_gb": 5.0,
        "quality": 72,
        "context": "32K",
        "size_mb": 1100,
    },
    {
        "name": "Qwen3-4B",
        "params": "4B",
        "quant": "Q4_K_M",
        "vram_gb": 3.5,
        "ram_gb": 7.0,
        "quality": 85,
        "context": "32K",
        "size_mb": 2500,
    },
    {
        "name": "Qwen3-8B",
        "params": "8B",
        "quant": "Q4_K_M",
        "vram_gb": 5.5,
        "ram_gb": 12.0,
        "quality": 92,
        "context": "32K",
        "size_mb": 4900,
    },
    {
        "name": "DeepSeek-R1-7B",
        "params": "7B",
        "quant": "Q4_K_M",
        "vram_gb": 5.0,
        "ram_gb": 10.0,
        "quality": 90,
        "context": "128K",
        "size_mb": 4300,
    },
]


def recommend_models(hw: HardwareInfo) -> list[dict]:
    """根据硬件推荐能跑的模型，按质量评分从高到低排序"""
    result = []
    for model in MODEL_REQUIREMENTS:
        # 过滤：硬件 >= 需求
        if hw.vram_gb >= model["vram_gb"] and hw.ram_gb >= model["ram_gb"]:
            item = model.copy()
            item["can_run"] = True
            result.append(item)
        else:
            item = model.copy()
            item["can_run"] = False
            result.append(item)

    # 排序：能跑的在前，按质量分降序
    result.sort(key=lambda x: (x["can_run"], x["quality"]), reverse=True)
    return result
