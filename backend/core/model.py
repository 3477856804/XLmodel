"""小凌 · 模型中心（硬件探测 + 设备策略 + 模型商店 + 本地推理）"""
import json
import math
import os
import platform
import shutil
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from fnmatch import fnmatch
from pathlib import Path

from .config import APP_DIR, STAR_DIR, DATA_DIR

MODELS_DIR = STAR_DIR / "models"

MODEL_PRESETS = {
    "Qwen2.5-0.5B-Instruct": {
        "repo": "Qwen/Qwen2.5-0.5B-Instruct",
        "size_mb": 988, "score": 25.0, "params": "0.5B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "tiny",
        "desc": "最小模型，CPU 秒跑，适合低配",
    },
    "Qwen2.5-1.5B-Instruct": {
        "repo": "Qwen/Qwen2.5-1.5B-Instruct",
        "size_mb": 3100, "score": 40.0, "params": "1.5B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "balanced",
        "desc": "性价比最高，中文流畅",
    },
    "Qwen2.5-3B-Instruct": {
        "repo": "Qwen/Qwen2.5-3B-Instruct",
        "size_mb": 6100, "score": 52.0, "params": "3B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "balanced",
        "desc": "能力强，需 4GB 内存",
    },
    "Qwen2.5-7B-Instruct": {
        "repo": "Qwen/Qwen2.5-7B-Instruct",
        "size_mb": 4460, "score": 70.0, "params": "7B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "quality",
        "desc": "能力大幅提升，需 8GB 内存",
    },
    "Llama-3.2-1B-Instruct": {
        "repo": "meta-llama/Llama-3.2-1B-Instruct",
        "size_mb": 1300, "score": 39.0, "params": "1B", "quant": "Q4_K_M",
        "context": "128K", "langs": "英/多语", "tier": "tiny",
        "desc": "英文强，中文一般",
    },
    "Llama-3.2-3B-Instruct": {
        "repo": "meta-llama/Llama-3.2-3B-Instruct",
        "size_mb": 2020, "score": 54.0, "params": "3B", "quant": "Q4_K_M",
        "context": "128K", "langs": "英/多语", "tier": "balanced",
        "desc": "英文能力突出",
    },
    "Phi-3.5-mini-instruct": {
        "repo": "microsoft/Phi-3.5-mini-instruct",
        "size_mb": 2300, "score": 49.0, "params": "3.8B", "quant": "Q4_K_M",
        "context": "128K", "langs": "英/多语", "tier": "balanced",
        "desc": "微软小钢炮，推理快",
    },
    "Gemma-2-2B-Instruct": {
        "repo": "google/gemma-2-2b-it",
        "size_mb": 1610, "score": 48.0, "params": "2B", "quant": "Q4_K_M",
        "context": "8K", "langs": "英/多语", "tier": "balanced",
        "desc": "Google 出品，均衡",
    },
    "Gemma-2-9B-Instruct": {
        "repo": "google/gemma-2-9b-it",
        "size_mb": 5380, "score": 73.0, "params": "9B", "quant": "Q4_K_M",
        "context": "8K", "langs": "英/多语", "tier": "cuda",
        "desc": "质量高，建议 GPU",
    },
    "DeepSeek-R1-Distill-1.5B": {
        "repo": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "size_mb": 1120, "score": 45.0, "params": "1.5B", "quant": "Q4_K_M",
        "context": "64K", "langs": "中/英", "tier": "balanced",
        "desc": "推理能力强的蒸馏版",
    },
    "Qwen2.5-14B-Instruct": {
        "repo": "Qwen/Qwen2.5-14B-Instruct",
        "size_mb": 8820, "score": 85.0, "params": "14B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "cuda",
        "desc": "接近 GPT-3.5，需 GPU",
    },
}

WEIGHT_EXTS = (".safetensors", ".bin", ".gguf", ".pt", ".pth")
CONFIG_FILES = ("config.json", "tokenizer.json", "tokenizer_config.json",
                "vocab.json", "merges.txt", "special_tokens_map.json")

PLATFORM_NAMES = {"win": "Windows", "mac": "macOS", "linux": "Linux"}


def human_bytes(n: float) -> str:
    for unit, div in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if n >= div:
            return f"{n / div:.2f} {unit}"
    return f"{int(n)} B"


def platform_key() -> str:
    if sys.platform == "win32":
        return "win"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def platform_name() -> str:
    return PLATFORM_NAMES.get(platform_key(), "Unknown")


def is_win() -> bool:
    return platform_key() == "win"


def is_mac() -> bool:
    return platform_key() == "mac"


def is_linux() -> bool:
    return platform_key() == "linux"


@dataclass
class HardwareInfo:
    platform: str = ""
    platform_version: str = ""
    machine: str = ""
    cpu: str = ""
    cpu_cores: int = 0
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    ram_percent: float = 0.0
    gpu_name: str = ""
    gpu_memory_gb: float = 0.0
    has_cuda: bool = False
    has_metal: bool = False
    has_rocm: bool = False
    disk_free_gb: float = 0.0
    disk_total_gb: float = 0.0
    battery_percent: float = -1.0
    battery_plugged: bool = False
    cpu_temp: float = -1.0

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        parts = [self.platform, self.machine]
        if self.cpu_cores:
            parts.append(f"{self.cpu_cores} 核")
        if self.ram_total_gb:
            parts.append(f"RAM {self.ram_total_gb:.1f}GB")
        if self.gpu_name:
            parts.append(self.gpu_name)
        return " · ".join(p for p in parts if p)

    def tier(self) -> str:
        ram = self.ram_total_gb
        vram = self.gpu_memory_gb
        if vram >= 12 or ram >= 32:
            return "flagship"
        if vram >= 8 or ram >= 24:
            return "high"
        if vram >= 6 or ram >= 16:
            return "standard"
        if ram >= 8:
            return "entry"
        return "minimal"

    def recommended_ram_gb(self) -> float:
        return max(0.0, self.ram_available_gb - 1.0)

    def max_model_params(self) -> int:
        vram = self.gpu_memory_gb
        ram = self.ram_available_gb
        if self.has_cuda and vram >= 12:
            return 14
        if self.has_cuda and vram >= 8:
            return 9
        if self.has_cuda and vram >= 6:
            return 7
        if self.has_metal and ram >= 16:
            return 7
        if ram >= 12:
            return 3
        if ram >= 6:
            return 1
        return 0

    def recommended_size_label(self) -> str:
        p = self.max_model_params()
        if p <= 0:
            return "建议先升级内存"
        if p <= 1:
            return "推荐 0.5B ~ 1.5B"
        if p <= 3:
            return "推荐 1.5B ~ 3B"
        if p <= 7:
            return "推荐 3B ~ 7B"
        if p <= 9:
            return "推荐 7B ~ 9B"
        return "推荐 7B ~ 14B"

    def accel_label(self) -> str:
        if self.has_cuda:
            return "CUDA"
        if self.has_metal:
            return "METAL"
        if self.has_rocm:
            return "ROCm"
        return "CPU"

    def accel_full(self) -> str:
        if self.has_cuda:
            return "CUDA 加速可用"
        if self.has_metal:
            return "Metal 加速可用"
        if self.has_rocm:
            return "ROCm 加速可用"
        return "仅 CPU 推理"


def get_cpu_name() -> str:
    try:
        name = platform.processor() or platform.machine()
        if is_linux() and Path("/proc/cpuinfo").exists():
            for line in Path("/proc/cpuinfo").read_text(errors="ignore").splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
        if is_win():
            try:
                out = subprocess.run(
                    ["wmic", "cpu", "get", "name"],
                    capture_output=True, timeout=5, text=True)
                lines = [l.strip() for l in out.stdout.splitlines() if l.strip()]
                if len(lines) >= 2:
                    return lines[1]
            except (OSError, subprocess.SubprocessError):
                pass
        return name or "Unknown CPU"
    except Exception:
        return "Unknown CPU"


def get_memory_info() -> dict:
    try:
        import psutil
        m = psutil.virtual_memory()
        return {"total": m.total, "available": m.available, "percent": m.percent}
    except ImportError:
        pass
    try:
        if is_linux() and Path("/proc/meminfo").exists():
            data = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                k, _, v = line.partition(":")
                v = v.strip().split()
                if v:
                    data[k.strip()] = int(v[0]) * 1024
            total = data.get("MemTotal", 0)
            avail = data.get("MemAvailable", 0)
            pct = (1 - avail / total) * 100 if total else 0
            return {"total": total, "available": avail, "percent": round(pct, 1)}
    except Exception:
        pass
    return {"total": 0, "available": 0, "percent": 0}


def _query_nvidia_smi() -> dict:
    """用 nvidia-smi 查询 NVIDIA 独显（Windows / Linux 通用）。

    独立于 torch：装了 CPU 版 torch 时torch.cuda 不可用，但 nvidia-smi 依然
    能报出真实硬件。前置条件是 PATH 里有 nvidia-smi（NVIDIA 驱动会自带）。
    """
    out = {"name": "", "memory_gb": 0.0, "driver": ""}
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, timeout=5, text=True)
    except (OSError, subprocess.SubprocessError):
        return out
    if r.returncode != 0 or not r.stdout.strip():
        return out
    line = r.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    if len(parts) >= 1:
        out["name"] = parts[0]
    if len(parts) >= 2:
        try:
            # nvidia-smi 的 memory.total 单位是 MiB
            out["memory_gb"] = round(int(float(parts[1])) / 1024, 2)
        except ValueError:
            pass
    if len(parts) >= 3:
        out["driver"] = parts[2]
    return out


def _gpu_name_from_os() -> str:
    """从操作系统侧兜底取显卡名（没有 nvidia-smi 时用）。

    Windows 新版已移除 wmic，改用 PowerShell CIM；
    旧版 Windows 保留 wmic 兜底。
    """
    if is_win():
        # 首选 PowerShell CIM（Win 10 21H1+ / Win 11 均可用）
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController | "
                 "Where-Object { $_.AdapterRAM } | "
                 "Select-Object -First 1 -ExpandProperty Name)"],
                capture_output=True, timeout=8, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().splitlines()[0].strip()
        except (OSError, subprocess.SubprocessError):
            pass
        # 老Windows 兜底：wmic
        try:
            r = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, timeout=5, text=True)
            if r.returncode == 0:
                lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
                if len(lines) >= 2:
                    return lines[1]
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def get_gpu_info() -> dict:
    """探测 GPU 信息。

    区分两个概念，不要混为一谈：
      - name / memory_gb：**硬件事实**。有没有独显、叫什么、显存多大。
      - cuda：**torch 能否用 CUDA**。装了 CPU 版 torch 时硬件明明在，
        但 torch.cuda.is_available() 为 False，此时必须让上层知道
        「硬件有，但需要装 CUDA 版 torch」而不是谎报「没有GPU」。

    这个区分很重要：老实现只在 torch.cuda 可用时才填 name/memory，
    于是 CPU 版 torch + 独显机器会报出一片空白，看起来像没显卡。
    """
    out = {"name": "", "memory_gb": 0.0, "cuda": False,
           "metal": False, "rocm": False}

    # ---- 1. torch 侧：能否真正用上加速 ----
    torch_usable = False
    try:
        import torch
        if torch.cuda.is_available():
            torch_usable = True
            out["cuda"] = True
            try:
                out["name"] = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                out["memory_gb"] = round(props.total_memory / 1024 ** 3, 2)
            except Exception:
                pass
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            out["metal"] = True
            out["name"] = out["name"] or f"Apple {platform.machine()}"
    except ImportError:
        pass

    # ---- 2. 硬件侧：无论 torch 能不能用，都如实报告显卡 ----
    if not out["name"] or not out["memory_gb"]:
        smi = _query_nvidia_smi()
        if smi["name"]:
            out["name"] = smi["name"] or out["name"]
            out["memory_gb"] = smi["memory_gb"] or out["memory_gb"]
            # 有 N 卡硬件但 torch 用不上时，cuda 保持 False（那是 torch 的能力，
            # 不是硬件的属性）；硬件存在性由 name/memory_gb 体现。
    if not out["name"]:
        out["name"] = _gpu_name_from_os()

    if not torch_usable:
        # torch 是 CPU 版或未装：显式标注，避免上层误判成「没有显卡」
        out["torch_usable"] = False
    else:
        out["torch_usable"] = True
    return out


def get_disk_info(path: Path | None = None) -> dict:
    try:
        target = str(path or APP_DIR)
        usage = shutil.disk_usage(target)
        return {"total_gb": round(usage.total / 1024 ** 3, 2),
                "free_gb": round(usage.free / 1024 ** 3, 2),
                "used_gb": round(usage.used / 1024 ** 3, 2),
                "percent": round(usage.used / max(usage.total, 1) * 100, 1)}
    except (OSError, AttributeError):
        return {"total_gb": 0.0, "free_gb": 0.0, "used_gb": 0.0, "percent": 0.0}


def get_battery() -> dict:
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return {"percent": -1.0, "plugged": True}
        return {"percent": round(b.percent, 1), "plugged": bool(b.power_plugged)}
    except (ImportError, AttributeError):
        return {"percent": -1.0, "plugged": True}


def get_cpu_temp() -> float:
    try:
        import psutil
        temps = psutil.sensors_temperatures() or {}
        for name in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
            if name in temps and temps[name]:
                return round(temps[name][0].current, 1)
        for entries in temps.values():
            if entries:
                return round(entries[0].current, 1)
    except (ImportError, AttributeError):
        pass
    return -1.0


def get_load_avg() -> float:
    try:
        return round(os.getloadavg()[0], 2)
    except (OSError, AttributeError):
        return 0.0


def detect_hardware() -> HardwareInfo:
    mem = get_memory_info()
    gpu = get_gpu_info()
    disk = get_disk_info()
    bat = get_battery()
    return HardwareInfo(
        platform=platform_name(),
        platform_version=platform.version(),
        machine=platform.machine(),
        cpu=get_cpu_name(),
        cpu_cores=os.cpu_count() or 0,
        ram_total_gb=round(mem["total"] / 1024 ** 3, 2),
        ram_available_gb=round(mem["available"] / 1024 ** 3, 2),
        ram_percent=float(mem["percent"]),
        gpu_name=gpu["name"],
        gpu_memory_gb=gpu["memory_gb"],
        has_cuda=gpu["cuda"],
        has_metal=gpu["metal"],
        has_rocm=gpu["rocm"],
        disk_free_gb=disk["free_gb"],
        disk_total_gb=disk["total_gb"],
        battery_percent=bat["percent"],
        battery_plugged=bat["plugged"],
        cpu_temp=get_cpu_temp(),
    )


def best_device() -> str:
    """选择推理/训练设备。

    可用环境变量 `XIAOLING_FORCE_DEVICE` 强制指定（cpu / cuda / mps），
    便于做性能对比基线或临时绕开有问题的 GPU。
    """
    forced = (os.environ.get("XIAOLING_FORCE_DEVICE") or "").strip().lower()
    if forced in ("cpu", "cuda", "mps"):
        return forced
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def device_kwargs(device: str | None = None) -> dict:
    dev = device or best_device()
    if dev in ("cuda", "mps"):
        return {"device_map": "auto", "torch_dtype": "auto"}
    return {"device_map": "cpu", "low_cpu_mem_usage": True}


def inference_device() -> str:
    """选择**日常对话推理**用的设备。

    与训练刻意分开，理由有三：

    1. **收益不对称**：0.5B 模型在 CPU 上生成一句话只需约 8 秒，本来就不慢；
       搬上 GPU 省不了多少，但要多付一次权重搬运 + bf16转换的开销
       （实测 Chat 从 7.7s 涨到 19.5s，主要就来自首次加载与设备迁移）。
    2. **抢显存**：训练要用 GPU 余量，推理常驻会白占1GB 显存，
       反而可能让 OOM 阈值提前触发。
    3. **稳定性**：CPU 推理没有 CUDA 上下文切换与驱动占用的不确定性。

    训练仍走 `best_device()`（GPU），推理默认 CPU。
    需要强制时用环境变量：
      XIAOLING_INFER_DEVICE=cuda / cpu / mps
      XIAOLING_FORCE_DEVICE=cuda   （同时覆盖训练与推理，优先级更高）
    """
    forced = (os.environ.get("XIAOLING_FORCE_DEVICE")
              or os.environ.get("XIAOLING_INFER_DEVICE") or "").strip().lower()
    if forced in ("cpu", "cuda", "mps"):
        return forced
    return os.environ.get("XIAOLING_INFER_DEVICE_DEFAULT", "").strip().lower() \
        or "cpu"


def inference_device_kwargs() -> dict:
    """推理专用的加载参数（比device_kwargs 更保守）。"""
    dev = inference_device()
    if dev in ("cuda", "mps"):
        return {"device_map": "auto", "torch_dtype": "auto"}
    return {"device_map": "cpu", "low_cpu_mem_usage": True}


def compute_plan() -> dict:
    dev = best_device()
    hw = detect_hardware()
    notes = {
        "cuda": "GPU 可用，训练与推理均走 GPU",
        "mps": "Apple 芯片可用，走 MPS",
        "cpu": "仅 CPU：推理可用，训练较慢",
    }
    return {"tier": dev, "note": notes.get(dev, "未知设备"),
            "can_train": True, "hardware_tier": hw.tier(),
            "accel": hw.accel_label(), "vram_gb": hw.gpu_memory_gb,
            "ram_gb": hw.ram_total_gb, "cores": hw.cpu_cores}


def train_plan(tier: str) -> list:
    if tier == "cuda":
        cfg = {"batch_size": 4, "grad_accum": 1, "quant": "fp16"}
    elif tier == "mps":
        cfg = {"batch_size": 2, "grad_accum": 2, "quant": "none"}
    else:
        cfg = {"batch_size": 1, "grad_accum": 8, "quant": "none"}
    return [cfg]


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    zh = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other = len(text) - zh
    return zh + (other + 3) // 4


def estimate_context_tokens(messages: list) -> int:
    n = 0
    for m in messages:
        n += estimate_tokens(m.get("content", "")) + 4
    return n


def parse_params_billions(params: str) -> float:
    if not params:
        return 0.0
    s = params.upper().replace("B", "").replace("M", "e-3").strip()
    try:
        if "e-" in s:
            return float(s) / 1000
        return float(s)
    except ValueError:
        return 0.0


def parse_context_k(context: str) -> int:
    if not context:
        return 8
    s = context.upper().replace("K", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return 8


def estimate_vram_for(model: dict) -> float:
    params = parse_params_billions(model.get("params", ""))
    quant = (model.get("quant") or "Q4").upper()
    bits = 4.0
    if "Q8" in quant or "INT8" in quant:
        bits = 8.0
    elif "Q5" in quant:
        bits = 5.0
    elif "Q6" in quant:
        bits = 6.0
    elif "FP16" in quant or "F16" in quant:
        bits = 16.0
    elif "FP32" in quant or "F32" in quant:
        bits = 32.0
    base = params * bits / 8
    overhead = base * 0.15
    ctx_k = parse_context_k(model.get("context", "8K"))
    kv_cache = params * 0.02 * (ctx_k / 8)
    return round(base + overhead + kv_cache, 2)


def estimate_ram_for(model: dict, has_gpu: bool = False) -> float:
    vram = estimate_vram_for(model)
    if has_gpu:
        return round(vram * 0.5 + 1.0, 2)
    return round(vram * 1.3 + 1.0, 2)


def list_recommended() -> list:
    items = []
    for name, info in MODEL_PRESETS.items():
        ratio = info["score"] / max(info["size_mb"] / 1024, 0.1)
        items.append({"name": name, **info, "ratio": round(ratio, 2)})
    items.sort(key=lambda x: x["ratio"], reverse=True)
    return items


def get_recommended(config: dict | None = None) -> dict | None:
    recs = list_recommended()
    if not config:
        return recs[0] if recs else None
    max_size = config.get("max_size_mb", 10000)
    lang = config.get("lang", "zh")
    candidates = [r for r in recs if r["size_mb"] <= max_size] or recs
    if lang == "zh":
        zh = [c for c in candidates if "中" in c["langs"]]
        if zh:
            return zh[0]
    return candidates[0]


def fit_models_for_hardware(hw: HardwareInfo | None = None) -> list:
    hw = hw or detect_hardware()
    max_params = hw.max_model_params()
    out = []
    for name, info in MODEL_PRESETS.items():
        params = parse_params_billions(info.get("params", ""))
        vram_need = estimate_vram_for(info)
        ram_need = estimate_ram_for(info, hw.has_cuda or hw.has_metal)
        can_run = params <= max_params and ram_need <= hw.ram_available_gb
        out.append({"name": name, **info,
                    "vram_need_gb": vram_need, "ram_need_gb": ram_need,
                    "can_run": can_run, "recommended": False})
    runnable = [m for m in out if m["can_run"]]
    if runnable:
        runnable.sort(key=lambda x: x["score"], reverse=True)
        runnable[0]["recommended"] = True
    return out


def scan_model_dir(path: Path) -> dict:
    if not path.exists() or not path.is_dir():
        return {"ok": False, "error": "目录不存在"}
    weights = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in WEIGHT_EXTS]
    if not weights:
        return {"ok": False, "error": "没有权重文件"}
    total = 0
    complete = True
    for w in weights:
        size = w.stat().st_size
        total += size
        if w.suffix.lower() == ".safetensors" and size < 1024:
            complete = False
        try:
            if w.suffix.lower() == ".safetensors":
                with open(w, "rb") as f:
                    head = struct.unpack("<Q", f.read(8))[0]
                    if head <= 0 or head > 100 * 1024 * 1024:
                        complete = False
                    else:
                        f.seek(8)
                        hdr = json.loads(f.read(head))
                        if not isinstance(hdr, dict):
                            complete = False
                        else:
                            expected = max(
                                (v["data_offsets"][1] for k, v in hdr.items()
                                 if k != "__metadata__" and isinstance(v, dict)
                                 and "data_offsets" in v), default=0)
                            if expected and size != 8 + head + expected:
                                complete = False
        except Exception:
            complete = False
    has_config = (path / "config.json").exists()
    return {"ok": complete and has_config, "complete": complete,
            "has_config": has_config, "weights": len(weights),
            "bytes": total, "size": human_bytes(total),
            "path": str(path)}


class ModelStore:
    def __init__(self, store_dir: str | None = None):
        self.store_dir = Path(store_dir) if store_dir else MODELS_DIR
        self._lock = threading.RLock()
        try:
            self.store_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def list_available(self) -> list:
        return list_recommended()

    def list_installed(self) -> list:
        out = []
        with self._lock:
            for d in self.store_dir.iterdir():
                if not d.is_dir() or d.name.startswith("."):
                    continue
                info = scan_model_dir(d)
                if info.get("weights", 0) > 0:
                    out.append({"name": d.name, **info})
        return out

    def list_installed_names(self) -> list:
        return [m["name"] for m in self.list_installed()]

    def list_models(self) -> list:
        return self.list_installed_names()

    def is_installed(self, name: str) -> bool:
        return name in self.list_installed_names()

    def find_installed(self, name: str | None = None) -> Path | None:
        with self._lock:
            dirs = [d for d in self.store_dir.iterdir()
                    if d.is_dir() and not d.name.startswith(".")]
        if name:
            for d in dirs:
                if d.name == name and scan_model_dir(d).get("ok"):
                    return d
        for d in dirs:
            if scan_model_dir(d).get("ok"):
                return d
        return None

    def download(self, model_name: str, progress_cb=None) -> dict:
        preset = MODEL_PRESETS.get(model_name)
        if not preset:
            return {"ok": False, "error": f"未知模型：{model_name}"}
        dest = self.store_dir / model_name
        try:
            from huggingface_hub import hf_hub_download
            from huggingface_hub import HfApi
        except ImportError:
            return {"ok": False, "error": "huggingface_hub 未安装"}

        repo = preset["repo"]
        allow = ["*.json", "*.safetensors", "*.txt", "tokenizer*", "*.model"]
        # 先枚举仓库文件清单与字节大小，作为总进度分母
        files = []
        total_bytes = 0
        try:
            api = HfApi()
            info = api.repo_info(repo, files_metadata=True)
            for s in getattr(info, "siblings", []) or []:
                rf = getattr(s, "rfilename", "") or ""
                if not rf:
                    continue
                if any(fnmatch(rf, pat) for pat in allow):
                    sz = int(getattr(s, "size", 0) or 0)
                    files.append((rf, sz))
                    total_bytes += sz
        except Exception:
            files = []
            total_bytes = 0
        if not files:
            # 枚举失败时退化为 snapshot_download（无逐文件进度）
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(repo_id=repo, local_dir=str(dest),
                                  allow_patterns=allow)
            except Exception as e:
                return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        else:
            downloaded = 0
            for rf, sz in files:
                try:
                    hf_hub_download(repo_id=repo, filename=rf, local_dir=str(dest))
                except Exception as e:
                    return {"ok": False, "error": f"下载 {rf} 失败：{e}"}
                downloaded += sz
                if progress_cb:
                    try:
                        progress_cb(downloaded, total_bytes)
                    except Exception:
                        pass
        info = scan_model_dir(dest)
        return {"ok": bool(info.get("ok")), "path": str(dest),
                "size": info.get("size", "0 B")}

    def delete(self, name: str) -> bool:
        target = self.store_dir / name
        if not target.exists() or not target.is_dir():
            return False
        try:
            shutil.rmtree(target)
            return True
        except OSError:
            return False

    def disk_usage(self) -> dict:
        total = 0
        with self._lock:
            for d in self.store_dir.iterdir():
                if d.is_dir():
                    for p in d.rglob("*"):
                        if p.is_file():
                            try:
                                total += p.stat().st_size
                            except OSError:
                                pass
        return {"bytes": total, "size": human_bytes(total),
                "count": len(self.list_installed_names()),
                "dir": str(self.store_dir)}

    def stats(self) -> dict:
        return {"available": len(MODEL_PRESETS),
                "installed": len(self.list_installed_names()),
                "disk": self.disk_usage()}

    # ---- 增量：缓存管理 / 模型验证 / 增强列表 ----
    def clear_cache(self) -> bool:
        """删除 HuggingFace 下载缓存目录（~/.cache/huggingface）。"""
        cache_dir = Path.home() / ".cache" / "huggingface"
        if not cache_dir.exists():
            return True
        try:
            shutil.rmtree(cache_dir)
            return True
        except OSError:
            return False

    def get_cache_size(self) -> float:
        """返回 HuggingFace 缓存大小（MB）。"""
        cache_dir = Path.home() / ".cache" / "huggingface"
        if not cache_dir.exists():
            return 0.0
        total = 0
        for p in cache_dir.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return round(total / 1024 / 1024, 1)

    @staticmethod
    def validate_model(model_path: str | Path) -> tuple:
        """检查模型目录完整性，返回 (是否通过, 说明)。"""
        p = Path(model_path)
        if not p.exists() or not p.is_dir():
            return False, "模型目录不存在"
        if not (p / "config.json").exists():
            return False, "缺少 config.json"
        has_weights = any(p.glob(f"*{ext}") for ext in WEIGHT_EXTS)
        if not has_weights:
            return False, "缺少权重文件"
        total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        if total < 100 * 1024 * 1024:
            return False, f"模型过小（{human_bytes(total)}），可能不完整"
        return True, f"校验通过，大小 {human_bytes(total)}"

    def list_models_ex(self, sort_by_size: bool = False,
                       installed_only: bool | None = None) -> list:
        """增强模型列表：支持按大小排序、过滤已下载/未下载。"""
        if installed_only is False:
            installed = set(self.list_installed_names())
            return [n for n in MODEL_PRESETS if n not in installed]
        installed = self.list_installed()
        if installed_only is True:
            return [m["name"] for m in installed]
        if sort_by_size:
            installed.sort(key=lambda x: x.get("bytes", 0), reverse=True)
            return installed
        return self.list_installed_names()

    # ---- 增量：缓存统计 / SHA256 校验 / 完整安装列表 ----
    def cache_stats_detailed(self) -> dict:
        """返回 HuggingFace 缓存详细统计：总大小、文件数、缓存目录路径。"""
        try:
            cache_dir = Path.home() / ".cache" / "huggingface"
            if not cache_dir.exists():
                return {"exists": False, "bytes": 0, "files": 0,
                        "dir": str(cache_dir)}
            total = 0
            files = 0
            for p in cache_dir.rglob("*"):
                if p.is_file():
                    try:
                        total += p.stat().st_size
                        files += 1
                    except OSError:
                        pass
            return {"exists": True, "bytes": total,
                    "size_h": human_bytes(total),
                    "files": files, "dir": str(cache_dir)}
        except Exception as e:
            return {"exists": False, "error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def compute_file_sha256(file_path: str | Path,
                            chunk_size: int = 1 << 20) -> str:
        """计算单个文件的 SHA256（流式读取，避免大文件占内存）。"""
        try:
            import hashlib
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def verify_weights_integrity(self, model_path: str | Path) -> dict:
        """对模型目录下所有权重文件做 SHA256 完整性摘要。

        返回 {ok, weights: [{name, sha256, size}], total_bytes}。
        这里只计算并记录哈希供比对，不做逐字节官方比对（无官方清单）。
        """
        try:
            p = Path(model_path)
            if not p.exists() or not p.is_dir():
                return {"ok": False, "error": "目录不存在"}
            weights = [f for f in p.rglob("*")
                       if f.is_file() and f.suffix.lower() in WEIGHT_EXTS]
            if not weights:
                return {"ok": False, "error": "无权重文件"}
            items = []
            total = 0
            for w in weights:
                try:
                    size = w.stat().st_size
                    total += size
                    sha = self.compute_file_sha256(w)
                    items.append({"name": w.name, "sha256": sha,
                                  "size": size, "size_h": human_bytes(size)})
                except OSError:
                    continue
            return {"ok": True, "weights": items, "total_bytes": total,
                    "total_h": human_bytes(total), "path": str(p)}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def list_installed_full(self) -> list:
        """扩展已安装模型列表：含大小、量化格式、修改时间、权重数。"""
        try:
            out = []
            with self._lock:
                dirs = [d for d in self.store_dir.iterdir()
                        if d.is_dir() and not d.name.startswith(".")]
            for d in dirs:
                try:
                    info = scan_model_dir(d)
                    if info.get("weights", 0) <= 0:
                        continue
                    preset = MODEL_PRESETS.get(d.name, {})
                    quant = preset.get("quant", "")
                    if not quant:
                        w = next((f for f in d.rglob("*")
                                   if f.suffix.lower() in WEIGHT_EXTS), None)
                        quant = ("gguf" if w and w.suffix.lower() == ".gguf"
                                 else "unknown")
                    mtime = 0.0
                    try:
                        mtime = max((f.stat().st_mtime for f in d.rglob("*")
                                     if f.is_file()), default=0.0)
                    except OSError:
                        pass
                    out.append({
                        "name": d.name,
                        "size": info.get("size", "0 B"),
                        "bytes": info.get("bytes", 0),
                        "quant": quant,
                        "modified_at": mtime,
                        "modified_h": (time.strftime("%Y-%m-%d %H:%M",
                                      time.localtime(mtime)) if mtime else ""),
                        "weights": info.get("weights", 0),
                        "complete": info.get("complete", False),
                    })
                except Exception:
                    continue
            out.sort(key=lambda x: x.get("bytes", 0), reverse=True)
            return out
        except Exception:
            return []


class LocalModel:
    def __init__(self, model_dir: str | Path, adapter_dir: str | Path | None = None,
                 context_limit: int = 8192, temperature: float = 0.85,
                 max_new_tokens: int = 512, system_prompt: str = ""):
        self.model_dir = Path(model_dir)
        self.adapter_dir = Path(adapter_dir) if adapter_dir else None
        self.context_limit = context_limit
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self.system_prompt = system_prompt
        self.model = None
        self.tokenizer = None
        # 对话推理默认走 CPU（见 inference_device 的说明：收益不对称且会抢显存），
        # 训练仍走 best_device() 的 GPU。
        self.device = inference_device()
        self._lock = threading.RLock()
        self._loaded_at = 0.0

    def load(self) -> bool:
        if not self.model_dir.exists():
            return False
        with self._lock:
            if self.model is not None:
                return True
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError:
                return False
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    str(self.model_dir), trust_remote_code=True)
                kwargs = inference_device_kwargs()
                self.model = AutoModelForCausalLM.from_pretrained(
                    str(self.model_dir), trust_remote_code=True, **kwargs)
                if self.adapter_dir and self.adapter_dir.exists():
                    try:
                        from peft import PeftModel
                        self.model = PeftModel.from_pretrained(self.model, str(self.adapter_dir))
                    except Exception:
                        pass
                try:
                    self.model.eval()
                except AttributeError:
                    pass
                self._loaded_at = time.time()
                return True
            except Exception:
                self.model = None
                self.tokenizer = None
                return False

    def unload(self):
        with self._lock:
            self.model = None
            self.tokenizer = None
            try:
                import torch
                if self.device == "cuda":
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def is_loaded(self) -> bool:
        return self.model is not None

    def build_messages(self, text: str, history: list | None = None) -> list:
        msgs = []
        sys_p = self.system_prompt or "你是小凌，一个住在用户电脑里的AI女孩。简短、友好地回答。"
        msgs.append({"role": "system", "content": sys_p})
        for h in (history or []):
            role = h.get("role")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": text})
        return msgs

    def trim_history(self, messages: list) -> list:
        if not messages:
            return messages
        head = [messages[0]] if messages[0].get("role") == "system" else []
        body = messages[len(head):]
        while head and estimate_context_tokens(head + body) > self.context_limit - self.max_new_tokens:
            if len(body) <= 2:
                break
            body = body[2:]
        return head + body

    def generate(self, text: str, history: list | None = None,
                 max_new_tokens: int = 0, temperature: float = -1.0) -> str:
        if not self.load():
            return ""
        messages = self.build_messages(text, history)
        messages = self.trim_history(messages)
        try:
            prompt = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            inputs = self.tokenizer(prompt, return_tensors="pt")
            input_len = inputs["input_ids"].shape[1]
            if self.device != "cpu":
                try:
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                except Exception:
                    pass
            kwargs = {
                "max_new_tokens": max_new_tokens or self.max_new_tokens,
                "do_sample": True,
                "temperature": temperature if temperature >= 0 else self.temperature,
                "top_p": 0.9,
                "repetition_penalty": 1.05,
                "pad_token_id": getattr(self.tokenizer, "pad_token_id", None),
            }
            with self._lock:
                out = self.model.generate(**inputs, **kwargs)
            new_ids = out[0][input_len:]
            return self.tokenizer.decode(new_ids, skip_special_tokens=True).strip()
        except Exception as e:
            return f"推理出错：{type(e).__name__}: {e}"

    def stream_generate(self, text: str, history: list | None = None,
                        on_chunk=None, max_new_tokens: int = 0):
        result = self.generate(text, history, max_new_tokens)
        if on_chunk:
            for i in range(0, len(result), 3):
                on_chunk(result[i:i + 3])
        return result

    def chat(self, text: str) -> str | None:
        return self.generate(text)

    def info(self) -> dict:
        info = scan_model_dir(self.model_dir)
        return {"loaded": self.is_loaded(), "device": self.device,
                "dir": str(self.model_dir), "size": info.get("size", "0 B"),
                "weights": info.get("weights", 0),
                "adapter": str(self.adapter_dir) if self.adapter_dir else "",
                "loaded_at": self._loaded_at}

    def stats(self) -> dict:
        return {"loaded": self.is_loaded(), "device": self.device,
                "context_limit": self.context_limit,
                "model_dir": str(self.model_dir)}


class ModelReplacement:
    def __init__(self, store_dir: str | None = None,
                 adapter_dir: str | None = None,
                 selected_name: str | None = None,
                 context_limit: int = 8192,
                 system_prompt: str = ""):
        self.store = ModelStore(store_dir)
        self.adapter_dir = Path(adapter_dir) if adapter_dir else (STAR_DIR / "adapter")
        self.selected_name = selected_name
        self.context_limit = context_limit
        self.system_prompt = system_prompt
        self._local: LocalModel | None = None
        self._lock = threading.RLock()

    def select(self, name: str) -> dict:
        with self._lock:
            path = self.store.find_installed(name)
            if path is None:
                return {"ok": False, "error": f"模型未安装：{name}"}
            self.selected_name = name
            if self._local is not None:
                self._local.unload()
            self._local = None
            return {"ok": True, "name": name, "path": str(path)}

    def current_name(self) -> str:
        return self.selected_name or ""

    def get_model(self) -> LocalModel | None:
        with self._lock:
            if self._local is not None:
                return self._local
            path = self.store.find_installed(self.selected_name)
            if path is None:
                return None
            self._local = LocalModel(
                path, adapter_dir=self.adapter_dir,
                context_limit=self.context_limit,
                system_prompt=self.system_prompt)
            if not self.selected_name:
                self.selected_name = path.name
            return self._local

    def ensure_loaded(self) -> bool:
        m = self.get_model()
        if m is None:
            return False
        return m.load()

    def unload(self):
        with self._lock:
            if self._local is not None:
                self._local.unload()

    def chat(self, text: str, history: list | None = None) -> str | None:
        m = self.get_model()
        if m is None:
            return None
        if not m.load():
            return None
        return m.generate(text, history)

    def is_ready(self) -> bool:
        m = self._local
        return bool(m and m.is_loaded())

    def status_text(self) -> str:
        if self._local and self._local.is_loaded():
            return f"已加载：{self.selected_name or self._local.model_dir.name}"
        installed = self.store.list_installed_names()
        if not installed:
            return "等待下载模型"
        if self.selected_name and self.selected_name in installed:
            return f"已选：{self.selected_name}（未加载）"
        return f"有 {len(installed)} 个模型可用（未选）"

    def list_available(self) -> list:
        return self.store.list_available()

    def list_installed(self) -> list:
        return self.store.list_installed()

    def recommended_for_self(self) -> list:
        return fit_models_for_hardware()

    def download(self, name: str, progress_cb=None) -> dict:
        return self.store.download(name, progress_cb)

    def delete(self, name: str) -> bool:
        if self.selected_name == name:
            self.unload()
            self.selected_name = None
        return self.store.delete(name)

    def stats(self) -> dict:
        return {"selected": self.selected_name or "",
                "ready": self.is_ready(),
                "installed": self.store.list_installed_names(),
                "adapter_dir": str(self.adapter_dir),
                "context_limit": self.context_limit,
                "store": self.store.stats()}

    # ---- 增量：模型回退链 ----
    def init_fallback_chain(self) -> "FallbackChain":
        """惰性创建/获取回退链（不修改 __init__）。"""
        try:
            if not hasattr(self, "_fallback") or self._fallback is None:
                self._fallback = FallbackChain(self)
            return self._fallback
        except Exception:
            return FallbackChain(self)

    def chat_with_fallback(self, text: str,
                           history: list | None = None) -> dict:
        """带回退的对话：主模型失败自动切换备用链中的下一个可用模型。"""
        try:
            chain = self.init_fallback_chain()
            return chain.chat(text, history)
        except Exception as e:
            return {"ok": False, "text": "", "used_model": "",
                    "tried": [], "error": f"{type(e).__name__}: {e}"}


class FallbackChain:
    """模型回退链：主模型失败时按顺序自动尝试备用模型。

    维护一个有序的备用模型名列表；每次对话先试当前选中模型，失败则按链依次切换。
    记录每个模型的失败次数，便于上层观察哪个模型不稳定。
    """

    def __init__(self, replacement: "ModelReplacement"):
        self._rep = replacement
        self._chain: list[str] = []
        self._lock = threading.RLock()
        self._failures: dict[str, int] = {}

    def set_chain(self, names: list):
        """整体替换备用链（传入模型名列表）。"""
        try:
            with self._lock:
                self._chain = [n for n in (names or []) if isinstance(n, str)]
        except Exception:
            pass

    def add_backup(self, name: str):
        """追加一个备用模型名。"""
        try:
            with self._lock:
                if name and name not in self._chain:
                    self._chain.append(name)
        except Exception:
            pass

    def chat(self, text: str, history: list | None = None) -> dict:
        """按链尝试对话，返回 {ok, text, used_model, tried}。"""
        tried = []
        # 先试当前选中模型
        try:
            main = self._rep.current_name()
            if main:
                tried.append(main)
                reply = self._rep.chat(text, history)
                if reply and not str(reply).startswith("推理出错"):
                    return {"ok": True, "text": reply,
                            "used_model": main, "tried": tried}
                self._failures[main] = self._failures.get(main, 0) + 1
        except Exception as e:
            tried.append(f"main_error:{type(e).__name__}")
        # 再按备用链依次尝试
        with self._lock:
            chain = list(self._chain)
        for name in chain:
            try:
                if not self._rep.store.is_installed(name):
                    continue
                self._rep.select(name)
                tried.append(name)
                reply = self._rep.chat(text, history)
                if reply and not str(reply).startswith("推理出错"):
                    return {"ok": True, "text": reply,
                            "used_model": name, "tried": tried}
                self._failures[name] = self._failures.get(name, 0) + 1
            except Exception:
                continue
        return {"ok": False, "text": "", "used_model": "",
                "tried": tried, "failures": dict(self._failures)}

    def status(self) -> dict:
        """返回回退链状态：链内容、失败计数、当前模型。"""
        try:
            with self._lock:
                return {"chain": list(self._chain),
                        "failures": dict(self._failures),
                        "current": self._rep.current_name()}
        except Exception:
            return {}


class Lifecycle:
    def __init__(self):
        self.start_time = time.time()
        self.state = "init"
        self._handlers: dict[str, list] = {}
        self._lock = threading.RLock()

    def on(self, event: str, handler):
        with self._lock:
            self._handlers.setdefault(event, []).append(handler)

    def off(self, event: str, handler):
        with self._lock:
            if event in self._handlers and handler in self._handlers[event]:
                self._handlers[event].remove(handler)

    def emit(self, event: str, *args):
        with self._lock:
            handlers = list(self._handlers.get(event, []))
        for h in handlers:
            try:
                h(*args)
            except Exception:
                pass

    def uptime(self) -> float:
        return time.time() - self.start_time

    def set_state(self, state: str):
        with self._lock:
            old = self.state
            self.state = state
        self.emit("state_changed", old, state)

    def snapshot(self) -> dict:
        return {"state": self.state, "uptime_s": round(self.uptime(), 1)}


def system_report() -> dict:
    hw = detect_hardware()
    plan = compute_plan()
    store = ModelStore()
    return {
        "hardware": hw.to_dict(),
        "hardware_summary": hw.summary(),
        "tier": hw.tier(),
        "accel": hw.accel_label(),
        "recommended_size": hw.recommended_size_label(),
        "compute": plan,
        "train_plan": train_plan(plan["tier"])[0],
        "store": store.stats(),
        "paths": {"app_dir": str(APP_DIR), "star_dir": str(STAR_DIR),
                  "data_dir": str(DATA_DIR), "models_dir": str(MODELS_DIR)},
    }


def selftest() -> dict:
    out = {}
    try:
        import torch
        out["torch"] = torch.__version__
    except ImportError:
        out["torch"] = "MISSING"
    try:
        import transformers
        out["transformers"] = transformers.__version__
    except ImportError:
        out["transformers"] = "MISSING"
    try:
        import peft
        out["peft"] = peft.__version__
    except ImportError:
        out["peft"] = "MISSING"
    try:
        import huggingface_hub
        out["huggingface_hub"] = huggingface_hub.__version__
    except ImportError:
        out["huggingface_hub"] = "MISSING"
    try:
        import psutil
        out["psutil"] = psutil.__version__
    except ImportError:
        out["psutil"] = "MISSING"
    out["device"] = best_device()
    out["hardware_tier"] = detect_hardware().tier()
    out["models_installed"] = len(ModelStore().list_installed_names())
    return out