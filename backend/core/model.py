"""小凌 · 模型中心（硬件探测 + 设备策略 + 模型商店 + 本地推理）"""
import json
import math
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from fnmatch import fnmatch
from pathlib import Path

from .config import APP_DIR, STAR_DIR, DATA_DIR

MODELS_DIR = STAR_DIR / "models"

MODEL_PRESETS = {
    "Qwen2.5-0.5B-Instruct": {
        "repo": "Qwen/Qwen2.5-0.5B-Instruct",
        "size_mb": 469, "score": 25.0, "params": "0.5B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "tiny",
        "desc": "最小模型，CPU 秒跑，适合低配",
    },
    "Qwen2.5-1.5B-Instruct": {
        "repo": "Qwen/Qwen2.5-1.5B-Instruct",
        "size_mb": 1066, "score": 40.0, "params": "1.5B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "balanced",
        "desc": "性价比最高，中文流畅",
    },
    "Qwen2.5-3B-Instruct": {
        "repo": "Qwen/Qwen2.5-3B-Instruct",
        "size_mb": 2007, "score": 52.0, "params": "3B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "balanced",
        "desc": "能力强，需 4GB 内存",
    },
    "Qwen2.5-7B-Instruct": {
        "repo": "Qwen/Qwen2.5-7B-Instruct",
        "size_mb": 4466, "score": 70.0, "params": "7B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "quality",
        "desc": "能力大幅提升，需 8GB 内存",
    },
    "Llama-3.2-1B-Instruct": {
        "repo": "meta-llama/Llama-3.2-1B-Instruct",
        "size_mb": 770, "score": 39.0, "params": "1B", "quant": "Q4_K_M",
        "context": "128K", "langs": "英/多语", "tier": "tiny",
        "desc": "英文强，中文一般",
    },
    "Llama-3.2-3B-Instruct": {
        "repo": "meta-llama/Llama-3.2-3B-Instruct",
        "size_mb": 1926, "score": 54.0, "params": "3B", "quant": "Q4_K_M",
        "context": "128K", "langs": "英/多语", "tier": "balanced",
        "desc": "英文能力突出",
    },
    "Phi-3.5-mini-instruct": {
        "repo": "microsoft/Phi-3.5-mini-instruct",
        "size_mb": 2282, "score": 49.0, "params": "3.8B", "quant": "Q4_K_M",
        "context": "128K", "langs": "英/多语", "tier": "balanced",
        "desc": "微软小钢炮，推理快",
    },
    "Gemma-2-2B-Instruct": {
        "repo": "google/gemma-2-2b-it",
        "size_mb": 9979, "score": 48.0, "params": "2B", "quant": "Q4_K_M",
        "context": "8K", "langs": "英/多语", "tier": "balanced",
        "desc": "Google 出品，均衡",
    },
    "Gemma-2-9B-Instruct": {
        "repo": "google/gemma-2-9b-it",
        "size_mb": 6526, "score": 73.0, "params": "9B", "quant": "Q4_K_M",
        "context": "8K", "langs": "英/多语", "tier": "cuda",
        "desc": "质量高，建议 GPU",
    },
    "DeepSeek-R1-Distill-1.5B": {
        "repo": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "size_mb": 1066, "score": 45.0, "params": "1.5B", "quant": "Q4_K_M",
        "context": "64K", "langs": "中/英", "tier": "balanced",
        "desc": "推理能力强的蒸馏版",
    },
    "Qwen2.5-14B-Instruct": {
        "repo": "Qwen/Qwen2.5-14B-Instruct",
        "size_mb": 8572, "score": 85.0, "params": "14B", "quant": "Q4_K_M",
        "context": "32K", "langs": "中/英", "tier": "cuda",
        "desc": "接近 GPT-3.5，需 GPU",
    },
}

WEIGHT_EXTS = (".safetensors", ".bin", ".gguf", ".pt", ".pth")

# 下载任务进度表：{模型名: {"percent","status","channel","error",...}}
# 模型商店的 UI 是"发起下载后另起轮询"看进度的，两次是不同的 RPC 请求，
# 光靠 progress_cb 回调传不到 UI —— 必须有这份进程内的共享表。
# status 取值：starting / downloading / done / error
TASKS: dict = {}

# 取消下载事件表：{模型名: threading.Event}
# 取消 ≠ 删除：.part 临时文件保留，下次点下载会从断点继续（Range 续传）。
# purge（连同 .part 一起清掉）由 RPC 层调用 quarantine 处理，本层只负责停。
_CANCEL_EVENTS: dict = {}


def request_cancel_download(model_name: str) -> bool:
    """请求取消某模型的下载任务。返回 False 表示当前没有进行中的任务。"""
    ev = _CANCEL_EVENTS.get(model_name)
    if ev is None or ev.is_set():
        return False
    ev.set()
    task = dict(TASKS.get(model_name) or {})
    task.update({"status": "cancelling",
                 "error": "用户取消（进度已保留，可继续下载）"})
    TASKS[model_name] = task
    return True


def is_download_cancelled(model_name: str) -> bool:
    ev = _CANCEL_EVENTS.get(model_name)
    return bool(ev is not None and ev.is_set())
CONFIG_FILES = ("config.json", "tokenizer.json", "tokenizer_config.json",
                "vocab.json", "merges.txt", "special_tokens_map.json")

PLATFORM_NAMES = {"win": "Windows", "mac": "macOS", "linux": "Linux"}

# 识别「我是什么模型」这类身份断言。用于把历史对话里的过期说法剔除，
# 避免模型一直复读自己以前说过的旧模型名（换模型后尤其明显）。
_IDENTITY_CLAIM = re.compile(
    r"(我是|我是一款|我是一种|我是一个|我叫|我基于|我是由|"
    r"i\s+am|i'?m)\s*[^。！？\n]{0,40}?"
    r"(qwen|llama|gpt|deepseek|gemma|granite|mistral|mixtral|phi|glm|chatglm|"
    r"\byi\b|baichuan|internlm|minicpm|falcon|stablelm|bloom|vicuna|wizard|"
    r"nous|hermes|nemotron|olmo|bonsai|devstral|qwq|command\s*r|dbrx|jamba|"
    r"seed|hunyuan|ernie|step|moonshot|kimi|doubao|spark)",
    re.IGNORECASE)


def looks_like_identity_claim(content: str) -> bool:
    """这句历史回复是不是在宣称"我是什么模型"？

    只做很窄的匹配：必须同时出现「我是…」这类自称 + 一个模型家族名。
    宁可漏判也不要误伤普通对话。
    """
    if not content:
        return False
    try:
        return bool(_IDENTITY_CLAIM.search(content))
    except Exception:
        return False


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
    except (ImportError, AttributeError, OSError):
        # 容器/部分 Linux 无 /sys/class/power_supply，psutil 会抛 FileNotFoundError
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
    except (ImportError, AttributeError, OSError):
        # 容器无 /sys/class/hwmon 时 psutil 会抛 OSError，不能让自检崩
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


def _scan_weight_file(p: Path) -> dict:
    """扫描**单个权重文件**（如 xxx.gguf）。

    GGUF 是自包含格式（权重 + 词表 + 超参都在一个文件里），
    不需要 config.json；因此不能用目录那套 `has_config` 判定标准，
    否则磁盘上所有 gguf 都会被误判为"不完整"。
    """
    suffix = p.suffix.lower()
    if suffix not in WEIGHT_EXTS:
        return {"ok": False, "error": f"不是受支持的权重文件：{suffix}",
                "weights": 0}
    size = p.stat().st_size
    base = {"weights": 1, "bytes": size, "size": human_bytes(size),
            "path": str(p), "kind": "file", "format": suffix.lstrip(".")}
    if suffix == ".gguf":
        return {**base, "ok": True, "complete": True, "has_config": False,
                "note": "GGUF 自包含格式（需 llama_cpp 运行时）"}
    # 非 gguf 的单文件缺少 tokenizer/config，视为不可用
    return {**base, "ok": False, "complete": False, "has_config": False,
            "error": "单文件权重缺少 config.json / tokenizer，建议放进模型目录"}


# ===================== 扫描缓存（性能关键） =====================
# 为什么需要：list_installed / is_installed / find_installed / stats 每次调用都会
# 对 models/ 下每个条目做 rglob + stat。老板的模型目录动辄几个 GB、几十个条目，
# 而 GetStatus、聊天路由、fallback 链、模型商店页面都会高频触发这些调用 ——
# 于是"打开聊天页"这种纯查询动作，也要付出扫整盘的代价，表现就是前端转圈很久。
#
# 这里用 (路径, mtime) 做 key 做进程内缓存：
#   * 目录/文件的 mtime 变化 → 缓存自动失效，模型下载完成能被立刻看见；
#   * mtime 不变 → 直接复用上次的扫描结果，避免重复 rglob。
# TTL 只是兜底，防止极端情况下 mtime 精度导致读到过期结果。
_SCAN_CACHE: dict = {}
_SCAN_TTL = 20.0


def _scan_key(p: Path) -> tuple:
    """缓存 key：路径 + mtime + 大小。任一变化即视为内容已变。"""
    try:
        st = p.stat()
        return (str(p), st.st_mtime, st.st_size)
    except OSError:
        return (str(p), 0.0, -1)


def _scan_cached(fn, path, ttl: float = _SCAN_TTL):
    """带缓存地执行扫描函数。path 变化或超时则重新扫描。"""
    try:
        key = _scan_key(path)
    except Exception:
        return fn(path)
    now = time.time()
    hit = _SCAN_CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    try:
        val = fn(path)
    except Exception:
        _SCAN_CACHE.pop(key, None)
        raise
    # 顺手清掉同一路径的过期条目，避免缓存无限增长
    for k in [k for k in _SCAN_CACHE if k[0] == str(path) and k != key]:
        _SCAN_CACHE.pop(k, None)
    _SCAN_CACHE[key] = (now, val)
    return val


def invalidate_scan_cache() -> None:
    """手动清空扫描缓存（模型下载完成、注册表变更后调用）。"""
    _SCAN_CACHE.clear()


def scan_model_dir(path: Path) -> dict:
    """扫描模型路径（**带缓存**）。兼容单文件权重与目录两种形态。"""
    return _scan_cached(_scan_model_dir_uncached, Path(path))


def _scan_model_dir_uncached(path: Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": "路径不存在"}
    if p.is_file():
        return _scan_weight_file(p)
    if not p.is_dir():
        return {"ok": False, "error": "既不是文件也不是目录"}
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
    formats = {w.suffix.lower().lstrip(".") for w in weights}
    if formats == {"gguf"}:
        fmt = "gguf"
    elif len(formats) == 1:
        fmt = next(iter(formats))
    else:
        fmt = "mixed"
    # 只装 gguf 的目录同样自包含，不该因为缺 config.json 被当成"不可用"
    ok = complete and (has_config or fmt == "gguf")
    return {"ok": ok, "complete": complete,
            "has_config": has_config, "weights": len(weights),
            "bytes": total, "size": human_bytes(total),
            "format": fmt, "path": str(path)}


def iter_model_entries(store_dir: Path):
    """枚举模型仓库条目：**目录** 与 **单文件权重**（如 xxx.gguf）一视同仁。

    旧实现只认目录，导致直接丢在 models/ 根目录的 .gguf 永远扫不出来。
    """
    try:
        for p in sorted(Path(store_dir).iterdir(), key=lambda x: x.name.lower()):
            if p.name.startswith("."):
                continue
            if p.is_dir():
                yield p
            elif p.is_file() and p.suffix.lower() in WEIGHT_EXTS:
                yield p
    except OSError:
        return


def entry_name(p: Path) -> str:
    """条目的对外名字：目录用目录名，文件去扩展名（去掉 .gguf 后缀更好看）。"""
    return p.stem if p.is_file() else p.name


def match_model_entry(p: Path, name: str) -> bool:
    """宽松匹配：既认完整名（含 .gguf），也认去掉扩展名后的名字。"""
    if not name:
        return False
    n = entry_name(p)
    return n == name or p.name == name or n.lower() == str(name).lower()


# ===================== GGUF 直连下载（免第三方 SDK） =====================
# 为什么必须自己写下载器，而不继续用 huggingface_hub / modelscope SDK：
#   1. 打包版 **排除了 modelscope**（它 __init__ 时会 JIT 编译 CUDA 扩展，
#      会让 PyInstaller 构建期子进程直接崩），而 huggingface_hub 也常不在
#      打包环境里 → 两条通道在 exe 里必然都返回"XX 未安装"，下载永远失败。
#   2. 更要命的是**格式不对**：SDK 拉下来的是 config.json + *.safetensors，
#      而打包版同时排除了 torch/transformers，这类权重**根本加载不了**。
#      程序真正跑推理的是 llama.cpp 的 GGUF。
# 所以正确做法是：只用标准库 urllib 直连 ModelScope 的 HTTP 接口，
# 拉 GGUF 单文件 —— 既免依赖，下载完还能直接被 llama.cpp 加载。
#
# 下面的仓库映射是 2026-10 实测探测出来的（对每个预设名逐个试候选仓库，
# 直到拿到 .gguf 文件列表）。11 个预设全部有 GGUF 源。
GGUF_REPO_MAP = {
    "Qwen2.5-0.5B-Instruct": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
    "Qwen2.5-1.5B-Instruct": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
    "Qwen2.5-3B-Instruct": "Qwen/Qwen2.5-3B-Instruct-GGUF",
    "Qwen2.5-7B-Instruct": "Qwen/Qwen2.5-7B-Instruct-GGUF",
    "Qwen2.5-14B-Instruct": "Qwen/Qwen2.5-14B-Instruct-GGUF",
    "Llama-3.2-1B-Instruct": "unsloth/Llama-3.2-1B-Instruct-GGUF",
    "Llama-3.2-3B-Instruct": "unsloth/Llama-3.2-3B-Instruct-GGUF",
    "Phi-3.5-mini-instruct": "LLM-Research/Phi-3.5-mini-instruct-GGUF",
    "Gemma-2-2B-Instruct": "google/gemma-2-2b-it-GGUF",
    "Gemma-2-9B-Instruct": "LLM-Research/gemma-2-9b-it-GGUF",
    "DeepSeek-R1-Distill-1.5B": "unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF",
}

# ModelScope 的 HTTP 接口（无需 SDK）
MODELSCOPE_API = "https://modelscope.cn/api/v1/models"
MODELSCOPE_RESOLVE = "https://modelscope.cn/models/{repo}/resolve/master/{path}"


def _http_json(url: str, timeout: float = 15.0):
    """GET 一个 JSON。只用标准库，不引入 requests 依赖。"""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as f:
        return json.loads(f.read().decode("utf-8", "replace"))


def _gguf_candidates(model_name: str) -> list:
    """候选 GGUF 仓库：先查映射表，再按常见组织名推导兜底。"""
    out = []
    mapped = GGUF_REPO_MAP.get(model_name)
    if mapped:
        out.append(mapped)
    preset = MODEL_PRESETS.get(model_name) or {}
    repo = preset.get("repo", "")
    if repo:
        base = repo.split("/")[-1]
        for org in (repo.split("/")[0], "qwen", "LLM-Research",
                    "AI-ModelScope", "unsloth", "google"):
            c = f"{org}/{base}-GGUF"
            if c not in out:
                out.append(c)
    return out


# 分片 GGUF 的命名：`xxx-q4_k_m-00001-of-00002.gguf`
_SHARD_RE = re.compile(r"-\d{5}-of-\d{5}(?=\.gguf$)", re.I)


def _pick_gguf_files(files: list, want_quant: str = "Q4_K_M") -> list:
    """挑出要下载的 gguf 文件（**可能是多个分片**）。

    大模型的 GGUF 常常被切成 `xxx-00001-of-00002.gguf` 这样的分片。
    只下载其中一个 = 模型残缺、加载必失败。所以这里按"去掉分片编号后的
    基名"分组，选中一个档位后**整组一起下**。

    档位优先级：想要档位 → 常见档位顺序 → 兜底第一组。
    """
    ggufs = [f for f in files if str(f).lower().endswith(".gguf")]
    if not ggufs:
        return []

    groups: dict = {}
    for f in ggufs:
        groups.setdefault(_SHARD_RE.sub("", str(f)), []).append(str(f))
    for k in groups:
        groups[k].sort()

    def _norm(s: str) -> str:
        return str(s).lower().replace("-", "_")

    w = _norm(want_quant or "Q4_K_M")
    for base in groups:
        if w in _norm(base):
            return groups[base]
    # 常见档位偏好：Q4_K_M 兼顾体积与质量；fp16/bf16 体积巨大放最后
    for pref in ("q4_k_m", "q5_k_m", "q4_0", "q8_0", "q6_k", "q3_k_m",
                 "q5_0", "iq4_nl", "q2_k", "q4_k_s", "f16", "bf16"):
        for base in groups:
            if pref in _norm(base):
                return groups[base]
    # 都没有明确档位标记（如 gemma 的 2b_it_v2.gguf）→ 取第一组
    return groups[sorted(groups)[0]]


def _pick_gguf_file(files: list, want_quant: str = "Q4_K_M"):
    """兼容旧调用：返回单个文件名（分片时返回第一片）。"""
    r = _pick_gguf_files(files, want_quant)
    return r[0] if r else None


def _download_gguf_repo(repo, files, dest, progress_cb=None,
                        quant="Q4_K_M", timeout=30.0,
                        cancel_check=None) -> dict:
    """已知 repo + 文件列表时执行 GGUF 下载（断点续传 + 自动重试）。

    由 _download_gguf_http 和 download_remote 共用，避免两份下载代码。
    """
    shards = _pick_gguf_files(files, quant)
    if not shards:
        return {"ok": False, "error": f"{repo} 下没有 .gguf 文件"}

    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"ok": False, "error": f"无法创建目录 {dest}：{e}"}

    # --- 先探所有分片的总大小，让进度条按"整个模型"走，而不是每片归零一次 ---
    sizes = {}
    for f in shards:
        try:
            req = urllib.request.Request(
                MODELSCOPE_RESOLVE.format(repo=repo, path=f), method="HEAD",
                headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                sizes[f] = int(r.headers.get("Content-Length") or 0)
        except Exception:                                   # noqa: BLE001
            sizes[f] = 0
    grand = sum(sizes.values())

    done_before = 0
    got_total = 0
    for fname in shards:
        url = MODELSCOPE_RESOLVE.format(repo=repo, path=fname)
        final_path = dest / fname
        part_path = dest / (fname + ".part")
        total = sizes.get(fname, 0)
        base_done = done_before

        # --- 断点续传 + 自动重试 ---
        last_err = ""
        for attempt in range(1, 9):
            have = part_path.stat().st_size if part_path.is_file() else 0
            if total and have >= total:
                break

            headers = {"User-Agent": "Mozilla/5.0"}
            mode = "wb" if not have else "ab"
            if have:
                headers["Range"] = f"bytes={have}-"
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    if have and r.status != 206:
                        # ModelScope 实测续传返回 200 + Content-Range（不是 206），
                        # 起始偏移与本地 have 一致时视为续传成功；否则回退重下。
                        cr = (r.headers.get("Content-Range") or "").strip()
                        resume_ok = False
                        if cr:
                            # 形如 "bytes 1234-5678/9012"
                            m = re.match(r"bytes\s+(\d+)-", cr)
                            if m and int(m.group(1)) == have:
                                resume_ok = True
                        if not resume_ok:
                            have, mode = 0, "wb"
                    if not total:
                        total = int(r.headers.get("Content-Length") or 0)
                        sizes[fname] = total
                    got = have
                    with open(part_path, mode) as out:
                        while True:
                            if cancel_check is not None and cancel_check():
                                return {"ok": False, "cancelled": True,
                                        "error": "已取消下载（进度保留，"
                                                 f"分片 {fname} 可继续续传）"}
                            chunk = r.read(1024 * 512)
                            if not chunk:
                                break
                            out.write(chunk)
                            got += len(chunk)
                            if progress_cb:
                                try:
                                    progress_cb(base_done + got,
                                                grand or total)
                                except Exception:           # noqa: BLE001
                                    pass
            except Exception as e:                          # noqa: BLE001
                last_err = f"{type(e).__name__}: {e}"

            got = part_path.stat().st_size if part_path.is_file() else 0
            if not total or got >= total:
                break
            last_err = last_err or f"连接在第 {attempt} 次尝试时提前断开"
            # 退避一下再续传，别把对方惹毛
            time.sleep(min(2 * attempt, 8))

        got = part_path.stat().st_size if part_path.is_file() else 0
        if total and got < total:
            return {"ok": False,
                    "error": f"分片 {fname} 重试 8 次仍未下完：{got}/{total}"
                             f" 字节（.part 已保留，可再次重试续传）"
                             f"｜最后错误：{last_err}"}
        if got <= 0:
            return {"ok": False, "error": f"分片 {fname} 没有下到数据｜{last_err}"}
        try:
            part_path.replace(final_path)
        except OSError as e:
            return {"ok": False, "error": f"写入完成但改名失败：{e}"}
        done_before += got
        got_total += got

    return {"ok": True, "path": str(dest), "bytes": got_total,
            "repo": repo, "files": shards, "shards": len(shards)}


def _download_gguf_http(model_name: str, dest: Path, progress_cb=None,
                        quant: str = "Q4_K_M", timeout: float = 30.0,
                        cancel_check=None) -> dict:
    """纯标准库下载 GGUF：列目录 → 选档位 → 断点续传下载。

    支持断点续传（Range 头）：大模型几个 GB，网络一抖从头再来会很崩溃。
    下载到 `.part` 临时文件，完成后才重命名，避免半截文件被当成已安装。
    cancel_check：返回 True 时立即中止（.part 保留，下次续传）。
    """
    repo = None
    files = []
    last_err = ""
    for cand in _gguf_candidates(model_name):
        try:
            d = _http_json(
                f"{MODELSCOPE_API}/{cand}/repo/files"
                f"?Revision=master&Recursive=True", timeout=timeout)
            fs = d.get("Data", {}).get("Files", []) or []
            names = [x.get("Path", "") for x in fs]
            if any(str(n).lower().endswith(".gguf") for n in names):
                repo, files = cand, names
                break
        except Exception as e:                              # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            continue
    if not repo:
        return {"ok": False, "error": f"未找到 GGUF 源（{last_err}）"}

    return _download_gguf_repo(repo, files, dest, progress_cb,
                               quant=quant, timeout=timeout,
                               cancel_check=cancel_check)


# ===================== 镜像源与下载策略 =====================
# 国内直连 huggingface.co 通常超时，因此默认走镜像；可用环境变量覆盖。
HF_ENDPOINTS = [
    os.environ.get("HF_ENDPOINT", "").strip(),
    "https://hf-mirror.com",
    "https://huggingface.co",
]
HF_ENDPOINTS = [e for e in HF_ENDPOINTS if e]

# 魔搭（ModelScope）仓库映射：国内可达时的首选通道
MODELSCOPE_MAP = {
    "Qwen/Qwen2.5-0.5B-Instruct": "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-1.5B-Instruct": "Qwen/Qwen2.5-1.5B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct": "Qwen/Qwen2.5-3B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct": "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-14B-Instruct": "Qwen/Qwen2.5-14B-Instruct",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
}


def _registry_path(name: str) -> Path:
    """注册表落盘位置（DATA_DIR 下，避免与模型权重混在一起）。"""
    try:
        base = DATA_DIR
    except Exception:
        base = Path("data")
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return base / name


def _load_json(path: Path, default):
    try:
        if path.is_file():
            d = json.loads(path.read_text(encoding="utf-8"))
            return d if isinstance(d, (dict, list)) else default
    except Exception:
        pass
    return default


def _save_json(path: Path, data) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return True
    except Exception:
        return False


class LocalModelRegistry:
    """本地已有模型的注册表。

    用途：老板磁盘上可能已经有下载好的模型（LM Studio / Ollama / 其他项目的
    权重目录），不必重新下载，直接把目录登记进来即可被小凌加载。
    登记只是"记账"（写 JSON），**不复制、不移动、不删除**任何文件。
    """

    FILE = "local_models.json"

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else _registry_path(self.FILE)
        self._lock = threading.RLock()

    def _all(self) -> dict:
        return _load_json(self.path, {}) or {}

    def add(self, name: str, directory: str, note: str = "") -> dict:
        """登记一个本地模型。directory 可以是**目录**，也可以是
        **单个权重文件**（如 xxx.gguf）——GGUF 自包含，不需要目录。
        """
        d = Path(directory)
        if not d.exists():
            return {"ok": False, "error": f"路径不存在：{directory}"}
        if not (d.is_dir() or (d.is_file() and d.suffix.lower() in WEIGHT_EXTS)):
            return {"ok": False,
                    "error": "既不是目录，也不是受支持的权重文件"
                             "（.safetensors/.bin/.gguf/.pt/.pth）"}
        info = scan_model_dir(d)
        if info.get("weights", 0) <= 0:
            return {"ok": False,
                    "error": "该路径下没有权重文件（.safetensors/.bin/.gguf/.pt/.pth）"}
        if not name.strip():
            name = entry_name(d)
        with self._lock:
            data = self._all()
            data[name] = {
                "name": name,
                "path": str(d.resolve()),
                "note": note,
                "source": "local",
                "kind": "file" if d.is_file() else "dir",
                "format": info.get("format", ""),
                "backend": ("gguf" if str(info.get("format", "")).lower() == "gguf"
                            else "transformers"),
                "weights": info.get("weights", 0),
                "size": info.get("size", "0 B"),
                "bytes": info.get("bytes", 0),
                "complete": bool(info.get("complete")),
                "has_config": bool(info.get("has_config")),
                "added_at": time.time(),
            }
            _save_json(self.path, data)
        return {"ok": True, "model": data[name]}

    def remove(self, name: str) -> dict:
        with self._lock:
            data = self._all()
            if name not in data:
                return {"ok": False, "error": f"未登记的本地模型：{name}"}
            data.pop(name, None)
            _save_json(self.path, data)
        return {"ok": True, "name": name}

    def list(self) -> list:
        with self._lock:
            data = self._all()
        out = []
        dirty = False
        for name, m in data.items():
            d = Path(m.get("path", ""))
            m = dict(m)
            if not d.exists():
                m["missing"] = True
            else:
                m["missing"] = False
                # 标记「模型库目录」，避免用户把它当单个模型去加载
                m["group"] = detect_model_group(d)
                # 实时校正 format / backend。
                # 早期版本登记时判错过：只含 gguf 的目录被判成 transformers，
                # 结果明明是 GGUF 却走 transformers 加载，必然失败。
                # 这里按磁盘现状重算，老登记项会自动纠正，无需用户重新登记。
                if not m.get("group"):
                    fmt, backend = m.get("format", ""), m.get("backend", "")
                    if is_gguf_path(d):
                        fmt, backend = "gguf", "gguf"
                    elif d.is_dir():
                        g = self._gguf_shallow(d)
                        if g is not None:
                            fmt, backend = "gguf", "gguf"
                        elif (d / "config.json").exists():
                            backend = "transformers"
                    if fmt != m.get("format", "") or backend != m.get("backend", ""):
                        m["format"], m["backend"] = fmt, backend
                        data[name]["format"] = fmt
                        data[name]["backend"] = backend
                        dirty = True
            out.append(m)
        if dirty:
            with self._lock:
                _save_json(self.path, data)
        return out

    @staticmethod
    def _gguf_shallow(d: Path):
        """只在目录**顶层**找 gguf。

        find_gguf_in 是 rglob 深扫，D:\\models 这类几百 GB 的库扫一次很慢；
        而绝大多数 GGUF 模型目录的权重就放在顶层，浅扫足够且几乎零成本。
        """
        try:
            best, best_size = None, -1
            for f in d.glob("*"):
                if f.is_file() and f.suffix.lower() == GGUF_SUFFIX:
                    try:
                        s = f.stat().st_size
                    except Exception:
                        s = 0
                    if s > best_size:
                        best, best_size = f, s
            return best
        except Exception:
            return None

    def get(self, name: str) -> dict | None:
        return self._all().get(name)

    def find_dir(self, name: str) -> Path | None:
        """按名字找登记项路径（目录或单个权重文件均可）。"""
        return self.find_path(name)

    def find_path(self, name: str) -> Path | None:
        m = self.get(name)
        if not m:
            return None
        p = Path(m.get("path", ""))
        return p if p.exists() else None


class ApiEndpointRegistry:
    """本地 / 远端 OpenAI 兼容 API 端点注册表。

    支持 LM Studio、Ollama、vLLM、One-API 等 OpenAI 兼容服务。
    登记后即可在模型商店里当作一个"模型"直接切换使用，无需下载权重。
    """

    FILE = "api_endpoints.json"

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else _registry_path(self.FILE)
        self._lock = threading.RLock()

    def _all(self) -> dict:
        return _load_json(self.path, {}) or {}

    def add(self, name: str, base_url: str, model: str = "",
            api_key: str = "", kind: str = "openai", note: str = "") -> dict:
        if not name.strip():
            return {"ok": False, "error": "名称不能为空"}
        base_url = (base_url or "").strip().rstrip("/")
        if not base_url:
            return {"ok": False, "error": "接口地址不能为空"}
        if not base_url.startswith(("http://", "https://")):
            base_url = "http://" + base_url
        with self._lock:
            data = self._all()
            data[name] = {
                "name": name,
                "base_url": base_url,
                "model": model or name,
                "api_key": api_key,
                "kind": kind or "openai",
                "note": note,
                "source": "api",
                "added_at": time.time(),
            }
            _save_json(self.path, data)
        return {"ok": True, "endpoint": _mask_key(data[name])}

    def remove(self, name: str) -> dict:
        with self._lock:
            data = self._all()
            if name not in data:
                return {"ok": False, "error": f"未登记的 API 端点：{name}"}
            data.pop(name, None)
            _save_json(self.path, data)
        return {"ok": True, "name": name}

    def list(self) -> list:
        with self._lock:
            data = self._all()
        return [_mask_key(v) for v in data.values()]

    def get(self, name: str) -> dict | None:
        v = self._all().get(name)
        return v if v else None

    def probe(self, name: str, timeout: float = 5.0) -> dict:
        """探测端点是否可达（只做 HEAD/GET，不写任何数据）。"""
        e = self.get(name)
        if not e:
            return {"ok": False, "error": f"未登记的 API 端点：{name}"}
        return probe_api_endpoint(e, timeout=timeout)


def _mask_key(e: dict) -> dict:
    """对外输出时遮蔽 api_key，避免泄露到前端日志。"""
    out = dict(e)
    k = out.get("api_key") or ""
    if k:
        out["api_key"] = ("*" * (len(k) - 4)) + k[-4:] if len(k) > 4 else "****"
        out["has_api_key"] = True
    else:
        out["has_api_key"] = False
    return out


def probe_api_endpoint(endpoint: dict, timeout: float = 5.0) -> dict:
    """探测 OpenAI 兼容端点：/v1/models 优先，失败退回根路径。"""
    import urllib.error
    import urllib.request

    base = (endpoint.get("base_url") or "").rstrip("/")
    headers = {"Accept": "application/json"}
    key = endpoint.get("api_key") or ""
    if key:
        headers["Authorization"] = "Bearer " + key

    last_err = ""
    for url in (base + "/v1/models", base + "/models", base):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(2048).decode("utf-8", errors="replace")
                models = []
                try:
                    j = json.loads(body)
                    if isinstance(j, dict) and isinstance(j.get("data"), list):
                        models = [str(x.get("id") or x.get("name") or "")
                                  for x in j["data"]][:50]
                except Exception:
                    pass
                return {"ok": True, "url": url, "status": resp.status,
                        "models": models}
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            continue
    return {"ok": False, "error": last_err or "不可达"}


def scan_directory_for_models(directory: str, max_depth: int = 3) -> dict:
    """扫描目录，找出其中"看起来像模型"的子目录。

    只读扫描，绝不改动任何文件。返回候选清单供用户在 UI 上勾选。
    """
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        return {"ok": False, "error": f"目录不存在：{directory}", "candidates": []}

    def _mk(path: Path, info: dict) -> dict:
        fmt = str(info.get("format", "") or "")
        if not fmt:
            # 目录里只有 gguf 时，scan_model_dir 现在会带上 format；
            # 兜底再探测一次，避免候选被标成 transformers 而误导用户
            if path.is_file():
                fmt = path.suffix.lower().lstrip(".")
            elif find_gguf_in(path) is not None:
                fmt = "gguf"
        return {
            "name": entry_name(path), "path": str(path.resolve()),
            "kind": "file" if path.is_file() else "dir",
            "format": fmt,
            "backend": "gguf" if fmt.lower() == "gguf" else "transformers",
            "weights": info.get("weights", 0),
            "size": info.get("size", "0 B"),
            "bytes": info.get("bytes", 0),
            "complete": bool(info.get("complete")),
            "has_config": bool(info.get("has_config")),
        }

    candidates = []
    # 自身即模型的情形：仅当 root **直接**持有权重文件或 config.json 时才算
    # （例如用户直接选了一个模型目录，或选了单个 .gguf 文件）。
    #
    # 重要：绝不能用 scan_model_dir(root) 的 rglob 结果判断 root 自身是不是模型。
    # scan_model_dir 会递归统计 root 下全部子目录的权重，若把「模型仓库容器目录」
    # （如 .star_core/models）传进来，它会被误当成一个是所有子模型权重之和
    # （约 6.15GB）的「模型」列出来。所以这里只看 root 的**一级子项**。
    self_is_model = False
    if root.is_file():
        self_is_model = (root.suffix.lower() in WEIGHT_EXTS
                         and bool(scan_model_dir(root).get("weights", 0) > 0))
    else:
        direct_weights = [c for c in root.iterdir()
                          if c.is_file() and c.suffix.lower() in WEIGHT_EXTS]
        has_direct_config = (root / "config.json").exists()
        if direct_weights or has_direct_config:
            self_is_model = bool(scan_model_dir(root).get("weights", 0) > 0)
    if self_is_model:
        candidates.append(_mk(root, scan_model_dir(root)))

    try:
        for d in sorted(root.iterdir(), key=lambda x: x.name.lower()):
            if d.name.startswith("."):
                continue
            # 散落的单文件权重（例如 LM Studio 风格的 xxx.gguf）
            if d.is_file() and d.suffix.lower() in WEIGHT_EXTS:
                info = scan_model_dir(d)
                if info.get("weights", 0) > 0:
                    candidates.append(_mk(d, info))
                continue
            if not d.is_dir():
                continue
            info = scan_model_dir(d)
            if info.get("weights", 0) > 0:
                candidates.append(_mk(d, info))
                continue
            # 下钻一层（常见布局：models/Qwen/Qwen2.5-0.5B-Instruct）
            if max_depth > 1:
                try:
                    for sub in sorted(d.iterdir(), key=lambda x: x.name.lower()):
                        if sub.name.startswith("."):
                            continue
                        if (sub.is_file()
                                and sub.suffix.lower() in WEIGHT_EXTS):
                            sinfo = scan_model_dir(sub)
                            if sinfo.get("weights", 0) > 0:
                                candidates.append(_mk(sub, sinfo))
                            continue
                        if not sub.is_dir():
                            continue
                        sinfo = scan_model_dir(sub)
                        if sinfo.get("weights", 0) > 0:
                            candidates.append(_mk(sub, sinfo))
                except OSError:
                    continue
    except OSError as e:
        return {"ok": False, "error": f"扫描失败：{e}", "candidates": candidates}

    return {"ok": True, "root": str(root.resolve()),
            "count": len(candidates), "candidates": candidates}


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
            for d in iter_model_entries(self.store_dir):
                info = scan_model_dir(d)
                if info.get("weights", 0) > 0:
                    out.append({"name": entry_name(d), **info})
        return out

    def list_installed_names(self) -> list:
        return [m["name"] for m in self.list_installed()]

    def list_models(self) -> list:
        return self.list_installed_names()

    def is_installed(self, name: str) -> bool:
        return name in self.list_installed_names()

    def find_installed(self, name: str | None = None) -> Path | None:
        with self._lock:
            entries = list(iter_model_entries(self.store_dir))
        if name:
            for d in entries:
                if match_model_entry(d, name) and scan_model_dir(d).get("ok"):
                    return d
        for d in entries:
            if scan_model_dir(d).get("ok"):
                return d
        return None

    def find_exact(self, name: str) -> Path | None:
        """**严格**按名字找模型，找不到就返回 None（不回退到任意模型）。

        find_installed 在名字匹配不上时会返回第一个可用模型（用于"默认模型"
        场景），但切换模型时这会把错误的模型当成用户指定的，必须避免。
        """
        with self._lock:
            entries = list(iter_model_entries(self.store_dir))
        for d in entries:
            if match_model_entry(d, name) and scan_model_dir(d).get("ok"):
                return d
        m = LocalModelRegistry().get(name)
        if m:
            p = Path(m.get("path", ""))
            if p.exists():
                return p
        return None

    # ---------------- 下载：多通道自动回退 ----------------

    def download(self, model_name: str, progress_cb=None,
                 channel: str = "auto") -> dict:
        """下载模型。国内网络优先走 ModelScope / HF 镜像，失败自动回退。

        channel: auto（默认，按序尝试）| modelscope | hf-mirror | huggingface
        返回: {"ok": bool, "channel": str, "path": str, "size": str, "error": str}

        进度除了回调给调用方，还会写进全局 TASKS —— 模型商店是在另一个
        RPC 里轮询进度的（不是调用 download 的那个请求），没有这份共享表，
        UI 就只能干等，看不出到底在下还是卡住了。
        """
        TASKS[model_name] = {
            'percent': 0.0, 'status': 'starting', 'channel': channel,
            'started': time.time(),
        }

        def _wrap(done, total):
            pct = 0.0
            try:
                if total:
                    pct = min(99.0, round(done * 100.0 / total, 1))
            except Exception:
                pct = 0.0
            TASKS[model_name].update({'percent': pct, 'status': 'downloading'})
            try:
                if progress_cb:
                    progress_cb(done, total)
            except Exception:
                pass

        preset = MODEL_PRESETS.get(model_name)
        if not preset:
            TASKS[model_name] = {'percent': 0.0, 'status': 'error',
                                 'error': f'未知模型：{model_name}'}
            return {"ok": False, "error": f"未知模型：{model_name}"}

        dest = self.store_dir / model_name
        # 注册取消事件：CancelDownload RPC 通过 request_cancel_download() 置位，
        # 下载循环每个分片检查，.part 保留 → 断点续传
        _CANCEL_EVENTS[model_name] = threading.Event()
        cancel_check = lambda: is_download_cancelled(model_name)  # noqa: E731
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            TASKS[model_name] = {'percent': 0.0, 'status': 'error',
                                 'error': f'无法创建目录 {dest}：{e}'}
            _CANCEL_EVENTS.pop(model_name, None)
            return {"ok": False, "error": f"无法创建目录 {dest}：{e}"}

        repo = preset["repo"]
        order = self._channel_order(channel, repo)

        errors = []
        quant = str(preset.get("quant") or "Q4_K_M")
        for ch in order:
            TASKS[model_name].update({'channel': ch, 'status': 'downloading'})
            try:
                if ch == "gguf-http":
                    res = _download_gguf_http(model_name, dest, _wrap,
                                              quant=quant,
                                              cancel_check=cancel_check)
                elif ch == "modelscope":
                    res = self._download_modelscope(model_name, repo, dest,
                                                    _wrap)
                else:
                    res = self._download_hf(repo, dest, _wrap, endpoint=ch)
            except Exception as e:  # noqa: BLE001
                res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            if res.get("cancelled"):
                # 用户主动取消：不进重试链，保留 .part，任务表标记 cancelled
                TASKS[model_name] = {
                    'percent': float((TASKS.get(model_name) or {})
                                     .get('percent', 0.0)),
                    'status': 'cancelled',
                    'error': '用户取消（进度保留，可继续下载）',
                }
                _CANCEL_EVENTS.pop(model_name, None)
                return res
            if res.get("ok"):
                _CANCEL_EVENTS.pop(model_name, None)
                info = scan_model_dir(dest)
                if info.get("ok"):
                    TASKS[model_name] = {
                        'percent': 100.0, 'status': 'done', 'channel': ch,
                        'path': str(dest), 'size': info.get('size', '0 B'),
                    }
                    # 磁盘变了 → 让活动模型缓存与扫描缓存立刻失效，
                    # 否则新下载的模型要等 TTL 到期才会被识别成"当前模型"。
                    invalidate_scan_cache()
                    _ACT_CACHE.clear()
                    try:
                        from .activity_log import record as _log_act
                        _log_act("model", f"模型下载完成：{model_name}",
                                 f"通道={ch}，大小={info.get('size', '0 B')}")
                    except Exception:
                        pass
                    return {"ok": True, "channel": ch, "path": str(dest),
                            "size": info.get("size", "0 B")}
                res = {"ok": False,
                       "error": "文件不完整（缺少 config.json 或权重损坏）"}
            errors.append(f"[{ch}] {res.get('error', '未知错误')}")

        err = "；".join(errors) or "全部通道均失败"
        TASKS[model_name] = {'percent': 0.0, 'status': 'error', 'error': err,
                             'tried': order}
        _CANCEL_EVENTS.pop(model_name, None)
        try:
            from .activity_log import record as _log_act
            _log_act("model", f"模型下载失败：{model_name}", err[:200],
                     severity="error")
        except Exception:
            pass
        return {"ok": False, "channel": ",".join(order),
                "error": err,
                "tried": order}

    def _channel_order(self, channel: str, repo: str) -> list:
        """决定尝试顺序。

        **gguf-http 必须排第一**：它是唯一在打包版里真正能跑通的通道
        （纯标准库 urllib，不依赖被排除的 modelscope / 未安装的
        huggingface_hub），而且下载下来的 GGUF 才是 llama.cpp 能加载的格式。
        其余通道保留，只在开发环境（装了 SDK 时）才有机会成功。
        """
        if channel and channel != "auto":
            return [channel]
        order = ["gguf-http"]
        if repo in MODELSCOPE_MAP:
            order.append("modelscope")
        order.extend([e for e in HF_ENDPOINTS])
        # 去重保序
        seen, out = set(), []
        for c in order:
            if c and c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _download_hf(self, repo: str, dest: Path, progress_cb,
                     endpoint: str = "") -> dict:
        """走 HuggingFace（可指定镜像 endpoint）下载。"""
        os.environ["HF_ENDPOINT"] = endpoint or HF_ENDPOINTS[0]
        try:
            from huggingface_hub import HfApi, hf_hub_download, snapshot_download
        except ImportError:
            return {"ok": False, "error": "huggingface_hub 未安装"}

        kw = {"endpoint": os.environ["HF_ENDPOINT"]} if endpoint else {}
        allow = ["*.json", "*.safetensors", "*.txt", "tokenizer*", "*.model"]

        files, total_bytes = [], 0
        try:
            try:
                api = HfApi(**kw)
            except TypeError:
                api = HfApi()          # 老版本不支持 endpoint 参数
            info = api.repo_info(repo, files_metadata=True)
            for s in getattr(info, "siblings", []) or []:
                rf = getattr(s, "rfilename", "") or ""
                if rf and any(fnmatch(rf, pat) for pat in allow):
                    sz = int(getattr(s, "size", 0) or 0)
                    files.append((rf, sz))
                    total_bytes += sz
        except Exception:
            files, total_bytes = [], 0

        if not files:
            # 枚举失败 → 退化整仓快照（无逐文件进度）
            try:
                snapshot_download(repo_id=repo, local_dir=str(dest),
                                  allow_patterns=allow, **kw)
            except TypeError:
                snapshot_download(repo_id=repo, local_dir=str(dest),
                                  allow_patterns=allow)
            return {"ok": True}

        downloaded = 0
        for rf, sz in files:
            try:
                hf_hub_download(repo_id=repo, filename=rf, local_dir=str(dest),
                                **kw)
            except TypeError:
                hf_hub_download(repo_id=repo, filename=rf, local_dir=str(dest))
            downloaded += sz
            if progress_cb:
                try:
                    progress_cb(downloaded, total_bytes)
                except Exception:
                    pass
        return {"ok": True}

    def _download_modelscope(self, model_name: str, repo: str, dest: Path,
                             progress_cb) -> dict:
        """走魔搭 ModelScope 下载（国内直连，速度最快）。"""
        try:
            from modelscope import snapshot_download as ms_snapshot
        except ImportError:
            return {"ok": False, "error": "modelscope 未安装"}
        ms_repo = MODELSCOPE_MAP.get(repo)
        if not ms_repo:
            return {"ok": False, "error": f"该模型无 ModelScope 映射：{repo}"}
        try:
            ms_snapshot(ms_repo, local_dir=str(dest))
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def delete(self, name: str) -> bool:
        """下线模型（**不删除**）：移入 D:\\待处理 隔离区等待人工复核。

        返回 True 表示已成功隔离或本来就不存在；False 表示隔离失败。
        """
        target = self.store_dir / name
        if not target.exists():
            # 可能是去掉扩展名后的 gguf 名字
            cand = next((p for p in iter_model_entries(self.store_dir)
                         if match_model_entry(p, name)), None)
            if cand is None:
                return False
            target = cand
        try:
            from .quarantine import move_to_pending
        except Exception:
            return False
        r = move_to_pending(target, reason="用户从模型商店移除",
                            category="model")
        if r.get("ok"):
            # 同步摘掉本地注册表中的记录（若有）
            try:
                LocalModelRegistry().remove(name)
            except Exception:
                pass
            return True
        return False

    def unregister(self, name: str) -> dict:
        """仅从注册表摘除本地登记项，**不碰磁盘上的权重目录**。"""
        r = LocalModelRegistry().remove(name)
        if r.get("ok"):
            return r
        e = ApiEndpointRegistry().remove(name)
        if e.get("ok"):
            return e
        return {"ok": False, "error": f"未找到登记项：{name}"}

    def resolve_path(self, name: str) -> Path | None:
        """按名字解析可用模型路径：商店条目（目录/单文件）→ 本地注册表。"""
        p = self.store_dir / name
        if p.exists() and scan_model_dir(p).get("ok"):
            return p
        cand = next((e for e in iter_model_entries(self.store_dir)
                     if match_model_entry(e, name)), None)
        if cand is not None and scan_model_dir(cand).get("ok"):
            return cand
        return LocalModelRegistry().find_path(name)

    def list_all(self) -> dict:
        """汇总：商店已下载 + 本地登记 + API 端点。"""
        return {
            "installed": self.list_installed(),
            "local": LocalModelRegistry().list(),
            "api": ApiEndpointRegistry().list(),
            "presets": list(MODEL_PRESETS.keys()),
        }

    def disk_usage(self) -> dict:
        total = 0
        with self._lock:
            for d in iter_model_entries(self.store_dir):
                if d.is_file():
                    try:
                        total += d.stat().st_size
                    except OSError:
                        pass
                    continue
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
        """清理 HuggingFace 下载缓存（~/.cache/huggingface）。

        **红线**：本项目绝不以任何方式删除文件。这里改为把缓存移入
        D:\\待处理 隔离区并登记清单，由人工复核后再决定是否真正删除。
        """
        cache_dir = Path.home() / ".cache" / "huggingface"
        if not cache_dir.exists():
            return True
        try:
            from .quarantine import move_to_pending
        except Exception:
            return False
        r = move_to_pending(cache_dir, reason="用户清理下载缓存",
                            category="cache")
        return bool(r.get("ok"))

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
                entries = list(iter_model_entries(self.store_dir))
            for d in entries:
                try:
                    info = scan_model_dir(d)
                    if info.get("weights", 0) <= 0:
                        continue
                    preset = MODEL_PRESETS.get(entry_name(d), {})
                    quant = preset.get("quant", "") or info.get("format", "")
                    if not quant:
                        w = next((f for f in d.rglob("*")
                                   if f.suffix.lower() in WEIGHT_EXTS), None)
                        quant = ("gguf" if w and w.suffix.lower() == ".gguf"
                                 else "unknown")
                    if d.is_file():
                        mtime = d.stat().st_mtime
                    else:
                        mtime = 0.0
                        try:
                            mtime = max((f.stat().st_mtime for f in d.rglob("*")
                                         if f.is_file()), default=0.0)
                        except OSError:
                            pass
                    out.append({
                        "name": entry_name(d),
                        "path": str(d),
                        "kind": "file" if d.is_file() else "dir",
                        "backend": ("gguf" if str(quant).lower() == "gguf"
                                    else "transformers"),
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


# ===================== 当前活动模型（唯一真源） =====================
# 需求：「聊天时实时识别并连通当前已下载/安装的模型」。
#
# 之前这块逻辑散落在三个地方，各算各的：
#   1. ModelReplacement.selected_name —— 用户指定的**名字**，可能指向已删除的模型；
#   2. GetStatus 里的 live_model —— 只读内存对象，引擎没起时为空；
#   3. cfg['model']['base_model'] —— 配置里的**静态默认值**，永远不变。
# 于是同一时刻三处可能给出三个不同的名字，前端聊天头显示的模型并不可信，
# 模型自己回答「我是谁」时更是完全靠猜。
#
# 现在统一到 active_model()：**以磁盘事实为准**，按「已加载 → 严格匹配选中名 →
# 磁盘上任意可用模型 → 空」的优先级解析，任何一处调用都得到同一个答案。
# 找不到就明确返回 available=False，并给出去模型商店下载的引导文案。

# 「没装模型」时的统一引导文案。放在这里而不是各处分写，
# 保证前端聊天页、状态栏、模型身份问答说的是同一句话。
NO_MODEL_GUIDANCE = (
    "我还没有可用的本地模型，所以现在没法真正对话。\n"
    "请打开【模型商店】下载一个模型（推荐 Qwen2.5-1.5B-Instruct 或 "
    "Qwen2.5-3B-Instruct），下载完成后我就能立刻用起来。"
)
NO_MODEL_ACTION = "open:model_store|我还没有安装任何模型，已为你打开【模型商店】，" \
                  "下载一个就能开始聊天啦（例如 Qwen2.5-1.5B-Instruct）。"

_ACT_CACHE: dict = {}
_ACT_TTL = 3.0


def params_from_name(name: str) -> float:
    """从模型名里解析参数量（B 数）。预设表没收录时用它兜底。

    老板常下载**预设表之外**的模型（比如 Qwen3.5-9B-DeepSeek-V4-Flash）。
    这些模型在 MODEL_PRESETS 里查不到 score/params，若不解析名字就会被当成
    「无评分的无名模型」排到最后 —— 明明是 5GB 的大模型，却输给 800MB 的小模型。
    """
    if not name:
        return 0.0
    # 匹配 9B / 1.5B / 0.5B / 27B / 8x7B 等写法；避开日期与版本号（v4、Qwen2.5）
    m = re.search(r"(?<![.\w])(\d+(?:\.\d+)?)\s*B(?![a-z0-9])", name, re.I)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return 0.0
    return 0.0


_FITS_CACHE: dict = {}


def _max_params_cached(ttl: float = 60.0) -> float:
    """缓存「本机能跑多大的模型」。

    detect_hardware() 会拉起 nvidia-smi / wmic / psutil 子进程，实测单次 ~70ms。
    active_model 会被聊天页、状态栏、模型商店高频调用，不能每次都付这个代价。
    硬件配置在运行期不会变，缓存 60 秒足够安全。
    """
    now = time.time()
    hit = _FITS_CACHE.get("max_params")
    if hit and now - hit[0] < ttl:
        return hit[1]
    try:
        val = float(detect_hardware().max_model_params())
    except Exception:
        val = 0.0
    _FITS_CACHE["max_params"] = (now, val)
    return val


def _best_installed_path() -> Path | None:
    """磁盘上「最值得用」的那个已安装模型。

    没有指定模型时的兜底选择。旧实现（find_installed(None)）直接返回**第一个**
    能用的条目 —— 那取决于目录名的字母序，老板 5GB 的 Qwen3.5-9B 和 800MB 的
    Llama-1B 放在一起时，可能挑中后者，对话质量凭空掉一档。

    这里改为按「硬件装得下 → 模型评分高 → 体积小」的顺序排序，
    让默认模型尽可能好，且在低配机器上仍能退到能跑的小模型。
    """
    try:
        entries = [d for d in iter_model_entries(MODELS_DIR)]
    except Exception:
        return None
    usable = []
    for d in entries:
        try:
            info = scan_model_dir(d)
            if info.get("ok"):
                usable.append((d, info))
        except Exception:
            continue
    if not usable:
        return None

    hw = None
    try:
        max_params = _max_params_cached()
    except Exception:
        max_params = 0

    def _rank(item):
        d, info = item
        name = entry_name(d)
        preset = MODEL_PRESETS.get(name) or {}
        # 预设表之外的模型：从名字解析参数量，避免大模型被当成无名小模型
        params = parse_params_billions(str(preset.get("params") or "")) \
            or params_from_name(name)
        score = float(preset.get("score") or 0.0)
        # 没有预设评分时，用参数量折算一个近似评分，保证不同家族的模型可比
        if not score and params:
            score = round(params * 8.0, 1)
        fits = 1 if (max_params and params and params <= max_params) else 0
        # fits 优先，其次评分，最后体积小者胜（平局时更稳）
        return (-fits, -score, int(info.get("bytes", 0) or 0))

    try:
        usable.sort(key=_rank)
    except Exception:
        pass
    return usable[0][0]


def _store_signature() -> tuple:
    """模型库的廉价指纹：目录 mtime + 一级条目名列表。

    只看一级条目，不做 rglob —— 几百 GB 的模型库也能在微秒级算出指纹，
    足以察觉「新增/删除/替换了一个模型」，又不会像全盘扫描那样拖慢聊天。
    """
    try:
        d = MODELS_DIR
        names = []
        for p in d.iterdir():
            if p.name.startswith("."):
                continue
            names.append(p.name)
        return (d.stat().st_mtime, tuple(sorted(names)))
    except OSError:
        return (0.0, ())


def _describe(path: Path, info: dict, loaded: bool) -> dict:
    """把一个模型路径整理成对外的「模型事实」描述。"""
    name = entry_name(path)
    fmt = str(info.get("format") or "")
    if not fmt:
        fmt = path.suffix.lower().lstrip(".") if path.is_file() else ""
    preset = MODEL_PRESETS.get(name) or {}
    # 参数量：预设优先，没有就从模型名解析（Qwen3.5-9B-… 这类自定义权重）
    params = str(preset.get("params") or "")
    if not params:
        p = params_from_name(name)
        params = f"{p:g}B" if p else ""
    # 量化档位：预设优先，否则从文件名里抠（…-Q4_K_M.gguf）
    quant = str(preset.get("quant") or "")
    if not quant:
        m = re.search(r"[-_]([iq]\d[qk0-9a-z_]*|f16|bf16|fp16|fp32)\.gguf$",
                      path.name, re.I)
        quant = m.group(1).upper() if m else (fmt.upper() if fmt else "")
    return {
        "available": True,
        "name": name,
        "path": str(path),
        "kind": "file" if path.is_file() else "dir",
        "backend": "gguf" if fmt.lower() == "gguf" else "transformers",
        "format": fmt,
        "quant": quant,
        "params": params,
        "size": info.get("size", "0 B"),
        "bytes": int(info.get("bytes", 0) or 0),
        "weights": int(info.get("weights", 0) or 0),
        "loaded": bool(loaded),
        "context": preset.get("context", ""),
        "langs": preset.get("langs", ""),
    }


def active_model(replacement: "ModelReplacement | None" = None,
                 refresh: bool = False) -> dict:
    """解析**当前正在使用的模型** —— 全系统唯一的真源。

    解析优先级（从强到弱，全部以磁盘事实为准）：
      1. 引擎里**已加载**的 LocalModel（最可信：它就是正在出字的进程）；
      2. 用户**选中**的模型（model.active / selected_name），严格匹配；
      3. 模型库里**任意可用**的模型（选中项失效时的兜底，会回写纠正 selected_name）；
      4. 本地注册表登记的模型；
      5. 都没有 → available=False + 下载引导。

    返回值字段见 `_describe`，外加 available / reason / guidance / source。
    `reason` 说明「为什么是它」，前端可直接展示，便于老板判断状态是否正确。
    """
    now = time.time()
    sig = _store_signature()
    if not refresh:
        hit = _ACT_CACHE.get("act")
        if hit and now - hit[0] < _ACT_TTL and hit[2] == sig:
            return hit[1]

    result = {"available": False, "name": "", "path": "", "loaded": False,
              "reason": "", "guidance": "", "source": "",
              "backend": "", "format": "", "params": "", "quant": "",
              "size": "", "bytes": 0, "weights": 0, "kind": "",
              "context": "", "langs": "", "selected": ""}

    # ---- 1. 已加载的对象（正在出字的那个，最真实） ----
    local = None
    selected = ""
    if replacement is not None:
        try:
            selected = replacement.current_name() or ""
        except Exception:
            selected = ""
        try:
            local = replacement._local            # noqa: SLF001 —— 有意读内部
        except Exception:
            local = None

    if local is not None:
        try:
            if local.is_loaded():
                src = local._gguf_path or local.model_dir    # noqa: SLF001
                if src and Path(src).exists():
                    result = _describe(Path(src),
                                       scan_model_dir(Path(src)), True)
                    result["source"] = "loaded"
                    result["reason"] = "当前正在对话的已加载模型"
                    result["selected"] = selected
                    _ACT_CACHE["act"] = (now, result, sig)
                    return result
        except Exception:
            pass

    # ---- 2/3. 严格按选中名找，找不到再退到磁盘上任意可用模型 ----
    store = ModelStore()
    path = None
    reason = ""
    if selected:
        try:
            path = store.resolve_path(selected)
        except Exception:
            path = None
        if path is not None:
            reason = f"你选中的模型「{selected}」"
    if path is None:
        try:
            path = _best_installed_path()
        except Exception:
            path = None
        if path is not None:
            reason = "模型库中已安装的模型"
    if path is not None:
        try:
            result = _describe(path, scan_model_dir(path), False)
            result["source"] = "store"
            result["reason"] = reason
            result["selected"] = selected
            # 选中项失效时顺手纠正，避免下次又解析回错的
            real_name = entry_name(path)
            if selected != real_name and replacement is not None:
                try:
                    replacement.selected_name = real_name
                except Exception:
                    pass
            _ACT_CACHE["act"] = (now, result, sig)
            return result
        except Exception:
            pass

    # ---- 4. 本地登记的模型（不在商店目录里的 LM Studio/Ollama 权重） ----
    try:
        locals_ = LocalModelRegistry().list()
    except Exception:
        locals_ = []
    usable = [m for m in locals_
              if not m.get("missing") and not m.get("group")
              and Path(m.get("path", "")).exists()]
    if usable:
        m = usable[0]
        p = Path(m["path"])
        try:
            result = _describe(p, scan_model_dir(p), False)
            result["source"] = "local"
            result["reason"] = "本地登记的模型"
            result["selected"] = selected
            _ACT_CACHE["act"] = (now, result, sig)
            return result
        except Exception:
            pass

    # ---- 5. 一个都没有 ----
    result["available"] = False
    result["reason"] = "模型库为空，尚未下载或登记任何模型"
    result["guidance"] = NO_MODEL_GUIDANCE
    _ACT_CACHE["act"] = (now, result, sig)
    return result


def active_model_name(replacement: "ModelReplacement | None" = None) -> str:
    """只要一个名字的快捷方式；没有模型时返回空串。"""
    try:
        info = active_model(replacement)
        return str(info.get("name") or "") if info.get("available") else ""
    except Exception:
        return ""


def active_model_answer(replacement: "ModelReplacement | None" = None) -> str:
    """回答「你用的什么模型」的标准话术 —— 全部基于磁盘事实，不让模型自己编。"""
    try:
        info = active_model(replacement)
    except Exception:
        info = {"available": False}
    if not info.get("available"):
        return NO_MODEL_ACTION
    name = info.get("name") or "未知模型"
    parts = [f"我现在用的是本地模型「{name}」。"]
    meta = []
    if info.get("params"):
        meta.append(f"{info['params']} 参数")
    if info.get("quant"):
        meta.append(f"{info['quant']} 量化")
    if info.get("size"):
        meta.append(f"体积 {info['size']}")
    if meta:
        parts.append("（" + "，".join(meta) + "）")
    if info.get("loaded"):
        parts.append("它已经加载好了，正在实时对话。")
    else:
        parts.append("它已经就位，我会在你第一条消息时自动加载。")
    parts.append("全程在你自己的电脑上运行，不联网。")
    return "".join(parts)


# ===================== GGUF 推理后端（llama.cpp） =====================
# transformers 的 AutoModelForCausalLM.from_pretrained **读不了 GGUF**：
# GGUF 是 llama.cpp 生态的自包含量化格式（权重+词表+超参打包进单个文件），
# 与 safetensors/HF 目录结构完全不是一回事。因此磁盘上的 .gguf 必须由
# llama_cpp 运行时加载。这里把它封装成与 transformers 接近的调用接口，
# 让上层 LocalModel 无需关心底层差异。

GGUF_SUFFIX = ".gguf"


def is_gguf_path(p: str | Path) -> bool:
    """判断路径是否为 GGUF 权重（文件或目录下的 .gguf）。"""
    try:
        p = Path(p)
    except Exception:
        return False
    if p.is_file():
        return p.suffix.lower() == GGUF_SUFFIX
    return False


def find_gguf_in(dir_path: str | Path) -> Path | None:
    """在目录里找 gguf 权重（取体积最大的一个）。"""
    try:
        d = Path(dir_path)
        if not d.is_dir():
            return None
        cands = [f for f in d.rglob("*")
                 if f.is_file() and f.suffix.lower() == GGUF_SUFFIX]
        if not cands:
            return None
        cands.sort(key=lambda f: f.stat().st_size, reverse=True)
        return cands[0]
    except Exception:
        return None


# 「模型库目录」判定缓存：D:\models 这类目录动辄几百 GB，不能每次列表都深扫
_GROUP_CACHE: dict = {}
_GROUP_TTL = 180.0


def _dir_has_weights(path: Path, depth: int = 2) -> bool:
    """浅层探测目录内是否含权重文件（最多下钻 depth 层）。"""
    try:
        for p in path.iterdir():
            if p.is_file() and p.suffix.lower() in WEIGHT_EXTS:
                return True
            if depth > 0 and p.is_dir() and _dir_has_weights(p, depth - 1):
                return True
    except OSError:
        pass
    return False


def detect_model_group(path: str | Path) -> bool:
    """判断一个路径是不是「模型库目录」（里面装着多个独立模型）。

    典型例子：D:\\models、D:\\models\\bartowski —— LM Studio / Ollama 习惯按
    「组织名 / 模型名 / 量化文件」三层存放。把它们当单个模型加载必然失败，
    正确做法是用 model:scan 挑出里面的具体模型再登记。
    """
    path = Path(path)
    key = str(path).lower()
    now = time.time()
    hit = _GROUP_CACHE.get(key)
    if hit and now - hit[0] < _GROUP_TTL:
        return bool(hit[1])
    res = False
    try:
        if path.is_file():
            res = False          # 单文件权重永远不是"库"
        elif not path.is_dir():
            res = False
        elif (path / "config.json").exists():
            res = False          # 自带 config.json = 单个 HF 模型
        else:
            n = 0
            for child in path.iterdir():
                if not child.is_dir() or child.name.startswith("."):
                    continue
                if _dir_has_weights(child):
                    n += 1
                    if n >= 2:
                        res = True
                        break
    except OSError:
        res = False
    _GROUP_CACHE[key] = (now, res)
    return res


def gguf_runtime_available() -> dict:
    """探测 llama_cpp 运行时是否可用（不含实际加载模型）。"""
    try:
        import llama_cpp  # noqa: F401
        return {"ok": True, "version": getattr(llama_cpp, "__version__", "")}
    except ImportError as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "fix": "pip install llama-cpp-python"}


class GGUFBackend:
    """GGUF 单文件模型的推理后端。

    用法与 transformers 路径对齐：
        backend.load() -> bool
        backend.chat(messages, max_tokens, temperature, top_p) -> str
        backend.stream_chat(messages, max_tokens, temperature, on_chunk) -> str
    """

    # 预填空的空思维块。Qwen3 / DeepSeek-R1 蒸馏类模型默认会先输出一大段
    # 思维链再回答；把 <think> 块预填成空可让模型跳过思考直接作答，
    # 实测同一问题从 13.1s / 满屏废话 → 3.3s / 干净回答。
    THINK_PREFILL = "<think>\n\n<<arg_key:6124c78e>>\n\n"

    def __init__(self, gguf_path: str | Path, n_ctx: int = 8192,
                 n_gpu_layers: int = -1, n_threads: int = 0,
                 verbose: bool = False, no_think: bool | None = None):
        self.path = Path(gguf_path)
        self.n_ctx = int(n_ctx) if n_ctx and n_ctx > 0 else 8192
        if n_gpu_layers is None:
            # 允许用环境变量指定卸载层数（0 = 纯 CPU；-1 = 全部上显卡）
            n_gpu_layers = int(os.environ.get("XIAOLING_GGUF_GPU_LAYERS", "-1"))
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.verbose = verbose
        if no_think is None:
            no_think = os.environ.get("XIAOLING_GGUF_NOTHINK", "1") != "0"
        self.no_think = no_think
        self.llm = None
        self.chat_format = None     # None = 交给 llama.cpp 自动识别
        self.loaded_layers = 0      # 实际卸载到 GPU 的层数（0 = 纯 CPU）
        self.is_chatml = False      # 模板是否为 ChatML（决定是否可预填空思维块）
        self._lock = threading.RLock()

    # ---------- 加载 ----------
    def _new_llm(self, **extra):
        from llama_cpp import Llama
        kwargs = dict(model_path=str(self.path), n_ctx=self.n_ctx,
                      n_gpu_layers=self.n_gpu_layers,
                      verbose=self.verbose)
        if self.n_threads and self.n_threads > 0:
            kwargs["n_threads"] = self.n_threads
        if self.chat_format:
            kwargs["chat_format"] = self.chat_format
        kwargs.update(extra)
        return Llama(**kwargs)

    def load(self) -> bool:
        with self._lock:
            if self.llm is not None:
                return True
            if not self.path.is_file():
                return False
            try:
                self.llm = self._new_llm()
            except Exception:
                # 最常见失败：预编译 wheel 不带 CUDA，n_gpu_layers=-1 直接炸。
                # 回退为纯 CPU 再试；再失败则确认不可用。
                try:
                    self.n_gpu_layers = 0
                    self.llm = self._new_llm()
                except Exception:
                    self.llm = None
                    return False
            try:
                self.loaded_layers = int(getattr(self.llm, "n_gpu_layers", 0) or 0)
            except Exception:
                self.loaded_layers = 0
            self._detect_chatml()
            return True

    def _detect_chatml(self):
        """判断模型是否使用 ChatML 模板（<|im_start|> 系）。

        只有确认是 ChatML，才能安全地手动拼 prompt 预填空思维块。
        """
        try:
            tpl = (getattr(self.llm, "metadata", None) or {}).get(
                "tokenizer.chat_template", "") or ""
        except Exception:
            tpl = ""
        if "<|im_start|>" in tpl:
            self.is_chatml = True
            return
        name = self.path.name.lower()
        self.is_chatml = ("qwen" in name or "deepseek" in name
                          or "chatml" in name)

    def _build_chatml(self, messages: list, prefill: str = "") -> str:
        """手工拼 ChatML prompt（含可选思维块预填空）。"""
        parts = []
        for m in messages or []:
            role = str(m.get("role", "user"))
            content = str(m.get("content", "") or "")
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
        parts.append("<|im_start|>assistant\n")
        if prefill:
            parts.append(prefill)
        return "".join(parts)

    @staticmethod
    def _strip_think(text: str) -> str:
        """兜底剥离残留的思维块（模型偶尔不按套路出牌）。"""
        out = text or ""
        for tag in ("<think>", "<thought>", "<|think|>"):
            if tag in out:
                for end in ("<<arg_key:6124c78e>>", "</thought>", "<|think_end|>",
                            "<|im_start|>"):
                    if end in out:
                        i = out.find(end)
                        out = out[i + len(end):]
                        break
                else:
                    out = out.split(tag, 1)[0]
        return out.strip()

    def _ensure_chat_template(self):
        """没有 chat template 时按模型名猜一个，Qwen 系用 chatml。"""
        if self.chat_format:
            return
        name = self.path.name.lower()
        if "qwen" in name or "deepseek" in name:
            self.chat_format = "chatml"
        else:
            self.chat_format = "chatml"   # 绝大多数中文聊天模型都是 chatml

    def _reload_with_format(self):
        self._ensure_chat_template()
        with self._lock:
            try:
                old = self.llm
                self.llm = self._new_llm()
                if old is not None:
                    try:
                        del old
                    except Exception:
                        pass
                return True
            except Exception:
                return False

    def is_loaded(self) -> bool:
        return self.llm is not None

    def unload(self):
        with self._lock:
            try:
                if self.llm is not None:
                    try:
                        self.llm.close()
                    except Exception:
                        pass
            finally:
                self.llm = None

    # ---------- 推理 ----------
    def _kwargs(self, max_tokens: int, temperature: float, top_p: float,
                stop=None):
        return dict(max_tokens=int(max_tokens) if max_tokens else 512,
                    temperature=float(temperature) if temperature >= 0 else 0.85,
                    top_p=float(top_p or 0.9),
                    repeat_penalty=1.05,
                    stop=stop or ["<|im_end|>", "</s>"])

    def chat(self, messages: list, max_tokens: int = 512,
             temperature: float = 0.85, top_p: float = 0.9) -> str:
        if not self.load():
            return ""
        # 关闭思维链：手工拼 ChatML 并预填空思维块（快且回答干净）
        if self.no_think and self.is_chatml:
            try:
                out = self.llm.create_completion(
                    prompt=self._build_chatml(messages, self.THINK_PREFILL),
                    max_tokens=int(max_tokens) if max_tokens else 512,
                    temperature=float(temperature) if temperature >= 0 else 0.85,
                    top_p=float(top_p or 0.9), repeat_penalty=1.05,
                    stop=["<|im_end|>", "<|endoftext|>", "</s>"])
                return self._strip_think(
                    (out.get("choices") or [{}])[0].get("text", ""))
            except Exception:
                pass  # 失败则回退标准 chat 接口
        kw = self._kwargs(max_tokens, temperature, top_p)
        try:
            out = self.llm.create_chat_completion(messages=messages, **kw)
            return self._pick(out)
        except Exception as e:
            # chat template 缺失时 llama.cpp 会抛错 → 指定 chatml 后重建
            msg = str(e).lower()
            if "chat template" in msg or "chat_format" in msg or "chat handler" in msg:
                if self._reload_with_format():
                    try:
                        out = self.llm.create_chat_completion(
                            messages=messages, **kw)
                        return self._pick(out)
                    except Exception as e2:
                        return f"推理出错：{type(e2).__name__}: {e2}"
            return f"推理出错：{type(e).__name__}: {e}"

    def stream_chat(self, messages: list, max_tokens: int = 512,
                    temperature: float = 0.85, top_p: float = 0.9,
                    on_chunk=None) -> str:
        """真·逐 token 流式（llama.cpp 原生支持 stream=True）。"""
        if not self.load():
            return ""
        buf = []

        def _emit(txt):
            if not txt:
                return
            buf.append(txt)
            if on_chunk:
                try:
                    on_chunk(txt)
                except Exception:
                    pass

        # 关闭思维链：手工拼 ChatML 并预填空思维块
        if self.no_think and self.is_chatml:
            try:
                gen = self.llm.create_completion(
                    prompt=self._build_chatml(messages, self.THINK_PREFILL),
                    max_tokens=int(max_tokens) if max_tokens else 512,
                    temperature=float(temperature) if temperature >= 0 else 0.85,
                    top_p=float(top_p or 0.9), repeat_penalty=1.05,
                    stop=["<|im_end|>", "<|endoftext|>", "</s>"],
                    stream=True)
                for piece in gen:
                    _emit((piece.get("choices") or [{}])[0].get("text", ""))
                return self._strip_think("".join(buf))
            except Exception:
                buf = []

        kw = self._kwargs(max_tokens, temperature, top_p)
        kw["stream"] = True
        try:
            gen = self.llm.create_chat_completion(messages=messages, **kw)
        except Exception as e:
            msg = str(e).lower()
            if "chat template" in msg or "chat_format" in msg or "chat handler" in msg:
                if self._reload_with_format():
                    try:
                        gen = self.llm.create_chat_completion(
                            messages=messages, **kw)
                    except Exception as e2:
                        return f"推理出错：{type(e2).__name__}: {e2}"
                else:
                    return f"推理出错：{type(e).__name__}: {e}"
            else:
                return f"推理出错：{type(e).__name__}: {e}"
        try:
            for piece in gen:
                try:
                    delta = (piece.get("choices") or [{}])[0].get("delta") or {}
                    txt = delta.get("content") or ""
                except Exception:
                    txt = ""
                if txt:
                    buf.append(txt)
                    if on_chunk:
                        try:
                            on_chunk(txt)
                        except Exception:
                            pass
        except Exception as e:
            if not buf:
                return f"推理出错：{type(e).__name__}: {e}"
        return "".join(buf).strip()

    @staticmethod
    def _pick(out) -> str:
        try:
            return ((out.get("choices") or [{}])[0]
                    .get("message", {}).get("content", "") or "").strip()
        except Exception:
            return ""


class LocalModel:
    def __init__(self, model_dir: str | Path, adapter_dir: str | Path | None = None,
                 context_limit: int = 8192, temperature: float = 0.85,
                 max_new_tokens: int = 512, system_prompt: str = "",
                 system_prompt_provider=None):
        self.model_dir = Path(model_dir)
        self.adapter_dir = Path(adapter_dir) if adapter_dir else None
        self.context_limit = context_limit
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self.system_prompt = system_prompt
        # 由 ModelReplacement 注入：每轮现取 system prompt，人格改动即时生效。
        self.system_prompt_provider = system_prompt_provider
        self.model = None
        self.tokenizer = None
        # 推理后端：transformers（HF/safetensors 目录）或 gguf（llama.cpp）
        self.backend = "transformers"
        self._gguf = None
        self._gguf_path = None
        if is_gguf_path(self.model_dir):
            self.backend = "gguf"
            self._gguf_path = self.model_dir
        elif not (self.model_dir / "config.json").exists():
            # 目录里没有 config.json 但有 gguf → 同样走 llama.cpp
            g = find_gguf_in(self.model_dir)
            if g is not None:
                self.backend = "gguf"
                self._gguf_path = g
        # 对话推理默认走 CPU（见 inference_device 的说明：收益不对称且会抢显存），
        # 训练仍走 best_device() 的 GPU。
        self.device = inference_device()
        self._lock = threading.RLock()
        self._loaded_at = 0.0
        self._last_stream_result = ""

    def load(self) -> bool:
        if not self.model_dir.exists():
            return False
        # ---- GGUF 分支：llama.cpp 运行时 ----
        if self.backend == "gguf" and self._gguf_path:
            with self._lock:
                if self._gguf is not None and self._gguf.is_loaded():
                    return True
                rt = gguf_runtime_available()
                if not rt.get("ok"):
                    raise RuntimeError(
                        "检测到 GGUF 模型，但 llama.cpp 运行时不可用："
                        f"{rt.get('error', '')}。请先执行 {rt.get('fix', '')}")
                if self._gguf is None:
                    self._gguf = GGUFBackend(self._gguf_path,
                                             n_ctx=self.context_limit)
                ok = self._gguf.load()
                if ok:
                    self._loaded_at = time.time()
                return ok
        # 模拟训练产出的模型不可用于推理：加载前检查 config.json，命中即拒绝
        try:
            cfg_path = self.model_dir / "config.json"
            if cfg_path.exists():
                _cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                if (str(_cfg.get("model_type", "")) == "xiaoling-simulated"
                        or _cfg.get("simulated") is True):
                    raise ValueError(
                        "这是模拟训练产出的模型，无法用于推理。请执行真实训练。")
        except ValueError:
            raise
        except Exception:
            # config 读取/解析失败时不阻断，交给后续正常加载流程自行处理
            pass
        with self._lock:
            if self.model is not None:
                return True
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError:
                # transformers 不可用时，目录里若有 gguf 仍可救活
                g = find_gguf_in(self.model_dir)
                if g is not None:
                    self.backend = "gguf"
                    self._gguf_path = g
                    self._gguf = GGUFBackend(g, n_ctx=self.context_limit)
                    if self._gguf.load():
                        self._loaded_at = time.time()
                        return True
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
            if self._gguf is not None:
                try:
                    self._gguf.unload()
                except Exception:
                    pass
            try:
                import torch
                if self.device == "cuda":
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def is_loaded(self) -> bool:
        if self.backend == "gguf":
            return self._gguf is not None and self._gguf.is_loaded()
        return self.model is not None

    def identity_hint(self) -> str:
        """告诉模型它真正的底座是什么。

        没有这段时，模型被问「你是什么模型」只能瞎猜 —— 更糟的是它会从
        历史对话里看到自己以前说过的旧名字（换模型后依然照抄），
        于是老板换成了 gpt-oss-20b，小凌还在自称 Qwen3.5。
        """
        try:
            src = self._gguf_path or self.model_dir
            name = entry_name(src)
        except Exception:
            name = ""
        if not name:
            return ""
        rt = "GGUF / llama.cpp" if self.backend == "gguf" else "transformers"
        return (
            f"\n\n【运行环境·事实】你此刻由本地模型「{name}」驱动，"
            f"推理运行时是 {rt}。"
            "若被问到用的是什么模型、底座、参数规模或量化方式，"
            "**只能依据上面这个真实名称回答**；"
            "绝对不要编造，也不要沿用历史对话里出现过的其它模型名"
            "（那些是旧记录，已经过时）。"
        )

    def build_messages(self, text: str, history: list | None = None) -> list:
        msgs = []
        # system_prompt_provider 优先：人格/情绪/关系是会随对话变化的，
        # 每轮现取才能让人格选择真正生效。此前这里只读创建时定死的
        # self.system_prompt（= DEFAULT_SYSTEM_PROMPT），engine.system_prompt()
        # 里组装的 persona hint + suffix 全链路没人调用 —— 表现为「换了人格
        # 但回复一个字节都没变」。没提供 provider 时才退回静态串。
        provider = getattr(self, "system_prompt_provider", None)
        sys_p = ""
        if callable(provider):
            try:
                sys_p = str(provider() or "")
            except Exception:
                sys_p = ""
        if not sys_p:
            sys_p = self.system_prompt or "你是小凌，一个住在用户电脑里的AI女孩。简短、友好地回答。"
        hint = self.identity_hint()
        if hint:
            sys_p = sys_p + hint
        msgs.append({"role": "system", "content": sys_p})
        for h in (history or []):
            role = h.get("role")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                # 关键：把历史里「过期的身份断言」剔掉。
                #
                # 光在 system 里告诉模型真名是不够的 —— 大模型有很强的
                # 「复读自己上一条回答」倾向。之前小凌说过一次"我基于 Qwen3.5"，
                # 这句话就被写进了对话历史，之后**每换一个模型它都照着念**，
                # 老板换成 gpt-oss-20b、granite，小凌还是自称 Qwen。
                # 所以这里直接把这类断言从上下文里去掉，断了复读的源头。
                if role == "assistant" and looks_like_identity_claim(content):
                    continue
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
        # ---- GGUF：走 llama.cpp 的 chat 接口 ----
        if self.backend == "gguf" and self._gguf is not None:
            return self._gguf.chat(
                messages,
                max_tokens=max_new_tokens or self.max_new_tokens,
                temperature=temperature if temperature >= 0 else self.temperature,
                top_p=0.9)
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
        """流式生成文本。

        注意：默认实现为「伪流式」——先整句生成完成，再按 3 字符分片回调
        on_chunk，并非真正的逐 token 流式输出。若 transformers 可用且模型
        已加载，会优先尝试用 TextIteratorStreamer 实现真流式；否则回退到
        伪流式。返回值末尾的元数据会标注实际使用的模式。
        """
        # 1) GGUF：llama.cpp 原生真流式
        if self.backend == "gguf" and self._gguf is not None:
            if not self.load():
                return ""
            messages = self.build_messages(text, history)
            messages = self.trim_history(messages)
            result = self._gguf.stream_chat(
                messages,
                max_tokens=max_new_tokens or self.max_new_tokens,
                temperature=self.temperature,
                top_p=0.9, on_chunk=on_chunk)
            self._last_stream_result = result
            return result

        # 3) 优先尝试真流式（TextIteratorStreamer，后台线程 generate）
        if self.is_loaded() and self._try_real_stream(text, history,
                                                      on_chunk, max_new_tokens):
            return self._last_stream_result

        # 4) 伪流式：整句生成后分片输出
        result = self.generate(text, history, max_new_tokens)
        if on_chunk:
            try:
                for i in range(0, len(result), 3):
                    on_chunk(result[i:i + 3])
            except Exception:
                pass
        self._last_stream_result = result
        return result

    def _try_real_stream(self, text: str, history: list | None,
                         on_chunk, max_new_tokens: int) -> bool:
        """尝试用 transformers.TextIteratorStreamer 做真流式；不可用返回 False。"""
        try:
            from transformers import TextIteratorStreamer
            import threading as _t

            messages = self.build_messages(text, history)
            messages = self.trim_history(messages)
            prompt = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            inputs = self.tokenizer(prompt, return_tensors="pt")
            input_len = inputs["input_ids"].shape[1]
            if self.device != "cpu":
                try:
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                except Exception:
                    pass
            streamer = TextIteratorStreamer(
                self.tokenizer, skip_prompt=True, skip_special_tokens=True)
            kwargs = dict(
                inputs,
                max_new_tokens=max_new_tokens or self.max_new_tokens,
                do_sample=True, temperature=self.temperature, top_p=0.9,
                repetition_penalty=1.05, streamer=streamer,
                pad_token_id=getattr(self.tokenizer, "pad_token_id", None),
            )
            holder = {}

            def _run():
                try:
                    with self._lock:
                        holder["out"] = self.model.generate(**kwargs)
                except Exception as e:
                    holder["error"] = e

            th = _t.Thread(target=_run, daemon=True)
            th.start()
            collected = []
            for chunk in streamer:
                if chunk:
                    collected.append(chunk)
                    if on_chunk:
                        try:
                            on_chunk(chunk)
                        except Exception:
                            pass
            th.join(timeout=30)
            if "error" in holder:
                return False
            self._last_stream_result = "".join(collected)
            return True
        except Exception:
            return False

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
                 system_prompt: str = "",
                 system_prompt_provider=None):
        self.store = ModelStore(store_dir)
        self.adapter_dir = Path(adapter_dir) if adapter_dir else (STAR_DIR / "adapter")
        self.selected_name = selected_name
        self.context_limit = context_limit
        self.system_prompt = system_prompt
        # 可选回调：返回本轮真正要用的 system prompt（人格会随对话变化）。
        self.system_prompt_provider = system_prompt_provider
        self._local: LocalModel | None = None
        self._lock = threading.RLock()

    def select(self, name: str) -> dict:
        with self._lock:
            # 必须用严格匹配：find_installed 找不到时会回退到任意可用模型，
            # 用在"切换模型"上会把错的模型当成用户指定的。
            path = self.store.find_exact(name)
            if path is None:
                return {"ok": False, "error": f"模型未安装：{name}"}
            if detect_model_group(path):
                return {"ok": False,
                        "error": f"「{name}」是模型库目录（里面装着多个模型），"
                                 f"不能直接加载。请执行 model:scan {path} "
                                 f"挑出具体模型后再登记。"}
            self.selected_name = name
            if self._local is not None:
                self._local.unload()
            self._local = None
            # 落盘记住选择。之前只改内存，重启就退回默认的小模型，
            # 用户会以为"本地模型根本没加载成功"。
            self._persist_active(name)
            return {"ok": True, "name": name, "path": str(path)}

    @staticmethod
    def _persist_active(name: str) -> None:
        try:
            from core import config as _cfg
            cfg = _cfg.load()
            cur = dict(cfg.get("model") or {})
            if cur.get("active") == name:
                return
            cur["active"] = name
            _cfg.patch({"model": cur})
        except Exception:
            # 记不住不是致命错误，不能因此让切换失败
            pass

    def current_name(self) -> str:
        return self.selected_name or ""

    def get_model(self) -> LocalModel | None:
        with self._lock:
            if self._local is not None:
                return self._local
            # 先用**严格**解析：如果老板指定了某个模型，就必须加载那一个。
            # 老代码直接调 find_installed，而它在名字对不上时会返回"任意一个
            # 可用模型"—— 于是选中的模型一旦被删/改路径，就会不声不响地
            # 加载另一个模型，用户完全摸不着头脑。
            path = (self.store.resolve_path(self.selected_name)
                    if self.selected_name else None)
            if path is None:
                # 指定的模型已经不存在了 → 退回商店默认模型（有兜底，但不静默换错）
                path = _best_installed_path()
                if path is not None:
                    self.selected_name = entry_name(path)
            if path is None:
                return None
            self._local = LocalModel(
                path, adapter_dir=self.adapter_dir,
                context_limit=self.context_limit,
                system_prompt=self.system_prompt,
                system_prompt_provider=self.system_prompt_provider)
            if not self.selected_name:
                self.selected_name = entry_name(path)
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

    def chat_stream(self, text: str, history: list | None = None,
                    on_chunk=None) -> str | None:
        """流式对话：底层（llama.cpp / transformers）原生支持逐 token 输出。

        与 chat() 的区别只是把 on_chunk 一路传下去，因此首个 token 一生成
        就能推到前端 —— 这是首字延迟下降的根本原因。

        **失败即降级**：任何一步出错都退回 chat() 的整句生成，
        保证流式是"加速手段"而不是"可用性前提"。
        """
        m = self.get_model()
        if m is None:
            return None
        try:
            if m.load():
                return m.stream_generate(text, history, on_chunk=on_chunk)
        except Exception:
            pass
        return self.chat(text, history)

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

    def download(self, name: str, progress_cb=None, channel: str = "auto") -> dict:
        return self.store.download(name, progress_cb, channel=channel)

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

# ===================== 远端搜索与下载（ModelScope 开放接口） =====================

_MODELSCOPE_SEARCH = "https://modelscope.cn/openapi/v1/models"
_MODELSCOPE_DETAIL = "https://modelscope.cn/openapi/v1/models/{namespace}/{name}"


def _validate_repo(repo: str) -> bool:
    """校验仓库名是否安全（用于拼进 URL，必须防注入/穿越）。

    合法形如 `namespace/name`：含且仅含一个 `/`，不含 `..`、反斜杠、
    URL 编码符号（`%`）、空白。
    """
    if not repo or not isinstance(repo, str):
        return False
    if repo.count("/") != 1:
        return False
    if ".." in repo or "\\" in repo or "%" in repo:
        return False
    if any(c.isspace() for c in repo):
        return False
    ns, name = repo.split("/", 1)
    if not ns or not name:
        return False
    return True


def search_remote(query: str, page: int = 1, page_size: int = 20,
                  timeout: float = 12.0) -> dict:
    """在 ModelScope 上搜索模型。

    失败时返回 ok=False + error，绝不返回空列表冒充成功。
    query 为空直接拒绝，不会返回全量列表。
    """
    if not query or not str(query).strip():
        return {"ok": False, "query": str(query or ""),
                "page": page, "page_size": page_size,
                "total": 0, "source": "modelscope",
                "models": [], "error": "搜索关键词不能为空"}

    url = (f"{_MODELSCOPE_SEARCH}?search={urllib.request.quote(query)}"
           f"&page_size={page_size}&page_number={page}")
    try:
        data = _http_json(url, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "query": str(query),
                "page": page, "page_size": page_size,
                "total": 0, "source": "modelscope",
                "models": [], "error": f"{type(e).__name__}: {e}"}

    if not isinstance(data, dict) or not data.get("success"):
        err = "接口返回 success=false" if isinstance(data, dict) else "响应格式异常"
        return {"ok": False, "query": str(query),
                "page": page, "page_size": page_size,
                "total": 0, "source": "modelscope",
                "models": [], "error": err}

    payload = data.get("data") or {}
    raw_models = payload.get("models") or []
    total = int(payload.get("total_count") or 0)

    out = []
    for m in raw_models:
        if not isinstance(m, dict):
            continue
        mid = m.get("id")
        if not mid:
            continue  # 脏数据过滤
        # id 形如 "namespace/name"，直接用；display_name 缺失时回退到 id 后半段
        desc = str(m.get("description") or "")
        if len(desc) > 200:
            desc = desc[:200] + "…"
        updated = str(m.get("last_modified") or "")
        if "T" in updated:
            updated = updated.split("T", 1)[0]
        elif " " in updated:
            updated = updated.split(" ", 1)[0]
        try:
            size_mb = int(float(m.get("file_size") or 0) / 1e6)
        except (TypeError, ValueError):
            size_mb = 0
        # 接口给的 params 是**参数量整数**（494032768），直接显示既看不懂
        # 也没法跟内置列表对齐，统一换算成 "0.5B" 这种写法。
        params = str(m.get("params") or "")
        if params.isdigit():
            params = f"{int(params) / 1e9:.1f}B".replace(".0B", "B")
        out.append({
            "repo": str(mid),
            "name": str(mid).split("/")[-1] if "/" in str(mid) else str(mid),
            "display_name": str(m.get("display_name") or ""),
            "description": desc,
            "downloads": int(m.get("downloads") or 0),
            "likes": int(m.get("likes") or 0),
            "license": str(m.get("license") or ""),
            "tasks": list(m.get("tasks") or []),
            "size_mb": size_mb,
            "params": params,
            "tags": list(m.get("tags") or []),
            "private": bool(m.get("private")),
            "gated": bool(m.get("gated")),
            "updated": updated,
        })

    return {"ok": True, "query": str(query),
            "page": int(payload.get("page_number") or page),
            "page_size": page_size,
            "total": total, "source": "modelscope",
            "models": out, "error": None}


def remote_model_files(repo: str, timeout: float = 15.0) -> dict:
    """列出 ModelScope 仓库的文件，并筛出 .gguf 路径。

    失败时返回 ok=False + error，files/gguf 为空列表。
    """
    if not _validate_repo(repo):
        return {"ok": False, "repo": repo, "files": [], "gguf": [],
                "error": "仓库名不合法"}
    url = (f"{MODELSCOPE_API}/{repo}/repo/files"
           f"?Revision=master&Recursive=True")
    try:
        data = _http_json(url, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "repo": repo, "files": [], "gguf": [],
                "error": f"{type(e).__name__}: {e}"}
    if not isinstance(data, dict):
        return {"ok": False, "repo": repo, "files": [], "gguf": [],
                "error": "响应格式异常"}
    code = data.get("Code")
    if code not in (200, "200"):
        return {"ok": False, "repo": repo, "files": [], "gguf": [],
                "error": f"接口返回 Code={code}"}

    raw_files = (data.get("Data") or {}).get("Files") or []
    files = []
    gguf = []
    for f in raw_files:
        if not isinstance(f, dict):
            continue
        path = str(f.get("Path") or "")
        if not path:
            continue
        try:
            size_mb = round(int(f.get("Size") or 0) / 1e6, 2)
        except (TypeError, ValueError):
            size_mb = 0
        is_lfs = bool(f.get("IsLFS"))
        files.append({"path": path, "size_mb": size_mb, "is_lfs": is_lfs})
        if path.lower().endswith(".gguf"):
            gguf.append(path)
    return {"ok": True, "repo": repo, "files": files, "gguf": gguf,
            "error": None}


def download_remote(remote_repo: str, dest_dir: Path | None = None,
                    quant: str = "Q4_K_M", progress_cb=None,
                    cancel_check=None, timeout: float = 30.0) -> dict:
    """从 ModelScope 远端仓库下载 GGUF 模型。

    复用 _download_gguf_repo 的实现（与 _download_gguf_http 共用同一套
    断点续传 + 自动重试逻辑），不复制粘贴下载代码。
    失败时返回 ok=False + error，不返回空结果冒充成功。
    """
    if not _validate_repo(remote_repo):
        return {"ok": False, "error": "仓库名不合法"}

    # 列文件
    listing = remote_model_files(remote_repo, timeout=timeout)
    if not listing.get("ok"):
        return listing
    paths = listing.get("gguf") or [f["path"] for f in listing.get("files", [])
                                    if f.get("path", "").lower().endswith(".gguf")]
    if not paths:
        return {"ok": False, "error": f"{remote_repo} 下没有 .gguf 文件"}

    dest = Path(dest_dir) if dest_dir else MODELS_DIR / remote_repo.split("/")[-1]
    return _download_gguf_repo(remote_repo, paths, dest, progress_cb,
                               quant=quant, timeout=timeout,
                               cancel_check=cancel_check)


def recommend_for_hardware(hw=None) -> dict:
    """根据硬件探测结果推荐适合的模型。

    如实反映探测结果：若 ram_total_gb<=0 或探测抛异常，available=False，
    且不会把任何模型标成 recommended=True。
    失败时返回 ok=False + error（当前实现总是 ok=True，但保留降级语义）。
    """
    detected = {
        "ram_total_gb": 0.0, "ram_available_gb": 0.0, "vram_gb": 0.0,
        "gpu_name": "", "disk_free_gb": 0.0, "cpu_cores": 0,
        "has_cuda": False, "has_metal": False, "platform": "",
    }
    available = True
    why = ""
    probe_error = ""
    try:
        if hw is None:
            hw = detect_hardware()
        detected = {
            "ram_total_gb": float(hw.ram_total_gb),
            "ram_available_gb": float(hw.ram_available_gb),
            "vram_gb": float(hw.gpu_memory_gb),
            "gpu_name": str(hw.gpu_name or ""),
            "disk_free_gb": float(hw.disk_free_gb),
            "cpu_cores": int(hw.cpu_cores or 0),
            "has_cuda": bool(hw.has_cuda),
            "has_metal": bool(hw.has_metal),
            "platform": str(hw.platform or ""),
        }
    except Exception as e:  # noqa: BLE001
        available = False
        probe_error = f"{type(e).__name__}: {e}"

    if hw is None:
        available = False
        probe_error = probe_error or "未能构造 HardwareInfo"
    elif detected["ram_total_gb"] <= 0:
        available = False
        probe_error = probe_error or "未能识别 RAM 容量"

    models = []
    tier = "unknown"
    try:
        tier = hw.tier() if hw is not None else "unknown"
    except Exception:
        tier = "unknown"

    if available:
        try:
            models = fit_models_for_hardware(hw)
        except Exception as e:  # noqa: BLE001
            available = False
            probe_error = f"推荐失败：{type(e).__name__}: {e}"
            models = []
        ram = detected["ram_total_gb"]
        vram = detected["vram_gb"]
        why = f"RAM {ram:.1f}GB"
        if vram > 0:
            why += f"，VRAM {vram:.1f}GB"
        why += f"，设备档位 {tier}"
    else:
        # 探测不可用时，保守给出最低档推荐，但**不**标 recommended=True
        try:
            models = fit_models_for_hardware(hw) if hw is not None else []
        except Exception:
            models = []
        for m in models:
            m["recommended"] = False
        reason = probe_error or "硬件探测不可用"
        why = f"未能识别硬件（{reason}），以下推荐按最低档保守给出"

    return {"ok": True, "tier": tier, "available": available,
            "why": why, "models": models, "detected": detected}
