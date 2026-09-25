#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.device —— 算力探测与设备选择（GPU 优先，CPU 兜底）

启动/训练/推理前统一调用，把"能上 GPU 的全上 GPU，装不下的溢出到 CPU"：

    from core.device import best_torch_device, device_kwargs, describe

    dev = best_torch_device()                  # 'cuda' / 'mps' / 'cpu'
    kw = device_kwargs(dev, dtype='auto')      # 传给 from_pretrained 的参数
    model = AutoModelForCausalLM.from_pretrained(path, **kw)

* cuda：torch.cuda.is_available()；device_map="auto"（accelerate）自动把权重
  先铺满显存、装不下的层自动 offload 到 CPU —— 正是"GPU 优先 + 余量落 CPU"。
* mps：Apple Silicon。
* cpu：保持 fp32 + low_cpu_mem_usage（低配机器不 OOM）。
不依赖 torch 也能安全导入（返回 cpu / 空描述）。
"""
from __future__ import annotations

import os


def best_torch_device() -> str:
    """按 CUDA > MPS > CPU 顺序选择可用的最优设备。"""
    forced = os.environ.get('XIAOLING_DEVICE', '').strip().lower()
    if forced in ('cuda', 'mps', 'cpu'):
        return forced
    try:
        import torch
        if torch.cuda.is_available():
            return 'cuda'
        if getattr(torch.backends, 'mps', None) is not None \
                and getattr(torch.backends.mps, 'is_available', lambda: False)():
            return 'mps'
    except Exception:                                              # noqa: BLE001
        pass
    return 'cpu'


def gpu_info() -> dict:
    """GPU 概况（名称 / 显存 / 数量），无 GPU 返回 {'available': False}。"""
    dev = best_torch_device()
    if dev != 'cuda':
        return {'available': dev == 'mps', 'device': dev, 'name': '',
                'vram_gb': 0.0, 'count': 0}
    try:
        import torch
        props = torch.cuda.get_device_properties(0)
        return {'available': True, 'device': 'cuda', 'name': props.name,
                'vram_gb': round(props.total_memory / 1024 ** 3, 1),
                'count': torch.cuda.device_count()}
    except Exception:                                              # noqa: BLE001
        return {'available': False, 'device': 'cpu', 'name': '', 'vram_gb': 0.0, 'count': 0}


def describe() -> str:
    """给日志/设置页用的一句话算力描述。"""
    d = best_torch_device()
    info = gpu_info()
    if d == 'cuda':
        return f"GPU 加速已启用：{info['name']}（{info['vram_gb']}GB 显存 × {info['count']}），装不下的层自动回落 CPU"
    if d == 'mps':
        return 'GPU 加速已启用：Apple Silicon (MPS)'
    return '未检测到可用 GPU → 使用 CPU 模式（渲染与推理已按 CPU 优化）'


def device_kwargs(device: str | None = None, dtype='auto') -> dict:
    """生成 from_pretrained 关键字参数：GPU 优先铺显存、溢出自动 offload 到 CPU。"""
    dev = device or best_torch_device()
    kw = {'trust_remote_code': True, 'low_cpu_mem_usage': True}
    if dev == 'cuda':
        import torch
        # bf16 优先（新卡），不支持再 fp16；device_map=auto = GPU 装满 → 余量落 CPU
        dt = torch.bfloat16 if dtype == 'auto' and torch.cuda.is_bf16_supported() \
            else (torch.float16 if dtype == 'auto' else dtype)
        kw.update({'dtype': dt, 'device_map': 'auto', 'max_memory': None})
    elif dev == 'mps':
        import torch
        kw.update({'dtype': torch.float16 if dtype == 'auto' else dtype})
    else:
        import torch
        kw.update({'dtype': torch.float32 if dtype == 'auto' else dtype})
    return kw


# --------------------------------------------------------------- 显存分级策略
# 对应设计文档 6.4「自动策略（启动时探测显存）」与 6.5「桌宠场景推荐配置」
VRAM_TIERS = (
    # (上限 GB, 档位, 推理策略, 是否允许训练, 说明)
    (4.0, 'cpu_only', '纯 CPU 推理（fp32，low_cpu_mem_usage）', False,
     '显存 < 4GB：纯 CPU 推理，训练延后（可用 XIAOLING_ALLOW_TRAIN=1 强制）'),
    (8.0, 'partial_gpu', '4bit 量化 + 部分层上 GPU（n_gpu_layers / device_map=auto）', True,
     '显存 4~8GB：4bit + 部分层 GPU，LoRA + gradient_checkpointing 可训'),
    (float('inf'), 'full_gpu', '全量上 GPU（bf16/fp16）+ LoRA 训练', True,
     '显存 > 8GB：全 GPU + LoRA 训练'),
)


def vram_gb() -> float:
    """当前可用显存（GB）。无 GPU / 无 torch 时返回 0.0。"""
    info = gpu_info()
    return float(info.get('vram_gb') or 0.0)


def plan(vram: float | None = None, allow_train: bool | None = None) -> dict:
    """按显存给出推理/训练档位（设计文档 6.4）。

    返回 {'tier', 'strategy', 'can_train', 'device', 'vram_gb', 'limits', 'note'}
    """
    dev = best_torch_device()
    gb = vram_gb() if vram is None else float(vram)
    tier, strategy, can_train, note = VRAM_TIERS[-1][1:]
    for limit, t, s, c, n in VRAM_TIERS:
        if gb < limit:
            tier, strategy, can_train, note = t, s, c, n
            break
    if dev == 'mps':
        tier, strategy, can_train = 'mps', 'Apple Silicon MPS（fp16），训练可用但建议小 batch', True
        note = 'Apple Silicon：MPS 推理，LoRA 可训（batch_size 建议 1）'
    if dev == 'cpu':
        tier, strategy, can_train = 'cpu_only', '纯 CPU 推理（fp32）', False
        note = '未检测到 GPU：推理走 CPU；训练建议延后或走云，或用 XIAOLING_ALLOW_TRAIN=1 强制'
    env_force = os.environ.get('XIAOLING_ALLOW_TRAIN', '').strip() in ('1', 'true', 'yes')
    if allow_train is False:
        can_train = False
    elif allow_train is True or env_force:
        can_train = True
    return {'tier': tier, 'strategy': strategy, 'can_train': bool(can_train), 'device': dev,
            'vram_gb': round(gb, 1), 'limits': train_plan(tier)[0] if can_train else None,
            'note': note}


def train_plan(tier: str | None = None) -> tuple:
    """训练参数档位（设计文档 6.5）：batch / accumulation / 量化 / offload。

    返回 ({'batch_size','grad_accum','quant','offload_optimizer','gradient_checkpointing'}, 说明)
    """
    if tier is None:
        tier = plan()['tier']
    if tier == 'full_gpu':
        cfg = {'batch_size': 4, 'grad_accum': 2, 'quant': 'none', 'offload_optimizer': False,
               'gradient_checkpointing': True}
        note = '全 GPU：batch 4 × accum 2，LoRA + 梯度检查点'
    elif tier == 'partial_gpu':
        cfg = {'batch_size': 1, 'grad_accum': 8, 'quant': '4bit', 'offload_optimizer': True,
               'gradient_checkpointing': True}
        note = '4bit + 部分层 GPU：batch 1 × accum 8，优化器状态卸到 CPU 内存'
    elif tier == 'mps':
        cfg = {'batch_size': 1, 'grad_accum': 8, 'quant': 'fp16', 'offload_optimizer': False,
               'gradient_checkpointing': True}
        note = 'MPS：batch 1 × accum 8'
    else:
        cfg = {'batch_size': 1, 'grad_accum': 16, 'quant': 'fp32', 'offload_optimizer': True,
               'gradient_checkpointing': True}
        note = '纯 CPU：batch 1 × accum 16，训练耗时显著，建议延后到空闲时段'
    return cfg, note


def describe_plan() -> str:
    """一句话策略描述（启动日志/仪表盘用）。"""
    p = plan()
    cfg, note = train_plan(p['tier']) if p['can_train'] else (None, '当前档位不触发训练')
    line = f"{describe()}\n  策略档位：{p['tier']}（显存 {p['vram_gb']}GB）→ {note}"
    if cfg:
        line += f"\n  训练参数：batch={cfg['batch_size']} accum={cfg['grad_accum']} " \
                f"quant={cfg['quant']} offload={cfg['offload_optimizer']}"
    return line


# --------------------------------------------------------------------------- #
#  torch 尚未安装时的 GPU 探测（鸡生蛋问题）
#
#  上面所有函数（best_torch_device / gpu_info / vram_gb / plan）都先 import torch，
#  所以「torch 还没装、但需要决定装 cu128 还是 cpu」这个场景它们全部返回 cpu。
#  这一节用 nvidia-smi 做**完全不依赖 torch** 的探测，供环境配置向导选安装源。
# --------------------------------------------------------------------------- #
TORCH_INDEX_CU128 = 'https://download.pytorch.org/whl/cu128'
TORCH_INDEX_CU124 = 'https://download.pytorch.org/whl/cu124'
TORCH_INDEX_CU118 = 'https://download.pytorch.org/whl/cu118'
TORCH_INDEX_CPU = 'https://download.pytorch.org/whl/cpu'


def find_nvidia_smi() -> str | None:
    """定位 nvidia-smi。WSL2 里它常在 /usr/lib/wsl/lib 而不在 PATH 上。"""
    import shutil
    exe = shutil.which('nvidia-smi')
    if exe:
        return exe
    for p in ('/usr/lib/wsl/lib/nvidia-smi', '/usr/bin/nvidia-smi',
              '/usr/local/bin/nvidia-smi'):
        if os.path.exists(p):
            return p
    return None


def nvidia_smi_info() -> dict:
    """**不依赖 torch** 的 NVIDIA 探测。

    返回 {'found', 'name', 'driver', 'compute_cap', 'sm', 'wsl'}
    * sm 由 compute_cap 换算（"12.0" → 120），与 setup_kali.sh 的 50 系判定一致。
    * 在 WSL2 下额外标记 wsl=True，供向导提示"需在 Windows 侧升级驱动"。
    """
    out = {'found': False, 'name': '', 'driver': '', 'compute_cap': '', 'sm': 0, 'wsl': False}
    try:
        out['wsl'] = ('microsoft' in (os.uname().release or '').lower()) \
            if hasattr(os, 'uname') else False
    except Exception:                                                 # noqa: BLE001
        out['wsl'] = False
    exe = find_nvidia_smi()
    if not exe:
        return out
    try:
        import subprocess
        r = subprocess.run([exe, '--query-gpu=name,driver_version,compute_cap',
                            '--format=csv,noheader'],
                           capture_output=True, text=True, timeout=10)
        lines = [ln for ln in (r.stdout or '').strip().splitlines() if ln.strip()]
        if not lines:
            return out
        parts = [p.strip() for p in lines[0].split(',')]
        out['found'] = True
        out['name'] = parts[0] if len(parts) > 0 else ''
        out['driver'] = parts[1] if len(parts) > 1 else ''
        cap = parts[2] if len(parts) > 2 else ''
        out['compute_cap'] = cap
        if cap:
            try:
                out['sm'] = int(round(float(cap) * 10))
            except Exception:                                         # noqa: BLE001
                out['sm'] = 0
    except Exception:                                                 # noqa: BLE001
        pass
    return out


def torch_install_plan() -> dict:
    """该机器上 torch 应该从哪个源装（**不依赖 torch**）。

    返回 {'index_url', 'variant', 'reason', 'gpu'}
    规则与 setup_kali.sh 的方案表一致：
      * macOS            → 默认 PyPI（轮子自带 MPS）
      * sm >= 120（50 系）→ cu128
      * sm >= 80（30/40 系）→ cu124
      * 其它 NVIDIA      → cu118
      * 无 NVIDIA        → cpu
    """
    import platform
    gpu = nvidia_smi_info()
    if platform.system() == 'Darwin':
        return {'index_url': '', 'variant': 'default',
                'reason': 'macOS：PyPI 默认轮子已自带 MPS 支持', 'gpu': gpu}
    if gpu.get('found'):
        sm = int(gpu.get('sm') or 0)
        name = gpu.get('name') or 'NVIDIA GPU'
        if sm >= 120:
            return {'index_url': TORCH_INDEX_CU128, 'variant': 'cu128',
                    'reason': f'{name}（sm_{sm}，50 系）→ cu128', 'gpu': gpu}
        if sm >= 80:
            return {'index_url': TORCH_INDEX_CU124, 'variant': 'cu124',
                    'reason': f'{name}（sm_{sm}，30/40 系）→ cu124', 'gpu': gpu}
        return {'index_url': TORCH_INDEX_CU118, 'variant': 'cu118',
                'reason': f'{name}（sm_{sm}）→ cu118', 'gpu': gpu}
    return {'index_url': TORCH_INDEX_CPU, 'variant': 'cpu',
            'reason': '未检测到 NVIDIA GPU → CPU 版', 'gpu': gpu}
