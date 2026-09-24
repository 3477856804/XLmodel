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
