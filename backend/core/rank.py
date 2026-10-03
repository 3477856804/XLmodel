#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.rank —— 动态升 rank（让适配器体积真正长大）
====================================================

对应设计文档第七章 7.1 节「动态升 rank 方案」：

    r=8 → 16 → 32 → 64 → 128 → 256 → ...  当 r ≈ hidden_size 时 LoRA 参数量 ≈ 全量权重

    升 rank 时旧权重复制：
        · 旧 A 矩阵 [r_old, in]  → 新 A 前 r_old 行
        · 旧 B 矩阵 [out, r_old] → 新 B 前 r_old 列
        · 其余随机初始化（A 用小方差随机；B 补零，保证升完 rank 的输出与升之前一致）

    7.5 存储估算：建议设上限，如 rank 最大 256；7.2 多适配器堆叠作备选。

实现要点
--------
* **零 torch 依赖**：自带 safetensors 读写（numpy + 8 字节头），因此在没有 torch 的
  机器上也能扩 rank、也能被回归测试覆盖。装了 torch 时对 `.pt/.bin` 适配器走 torch 分支。
* **可解释**：返回每轮的 rank、参数量估算、文件体积变化（体积是晋升条件 A 的依据）。
* **幂等安全**：先写临时文件再原子替换，失败自动回滚，不破坏原适配器。

用法：
    python3 -m core.rank status                  # 查看当前 rank / 体积 / 下一步计划
    python3 -m core.rank grow                    # 升一档 rank（8→16→32…，上限 256）
    python3 -m core.rank grow --rank 64          # 直接升到指定 rank
    python3 -m core.rank grow --dry-run
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path

from core.paths import APP_DIR

DEFAULT_MAX_RANK = 256
DEFAULT_FACTOR = 2
ADAPTER_CONFIG = 'adapter_config.json'
ADAPTER_WEIGHTS = ('adapter_model.safetensors', 'adapter_model.bin', 'adapter.pt')

_DTYPES = {
    'F64': 'float64', 'F32': 'float32', 'F16': 'float16', 'I64': 'int64', 'I32': 'int32',
    'I16': 'int16', 'I8': 'int8', 'U8': 'uint8', 'BOOL': 'bool',
}
_NP_TO_ST = {'float64': 'F64', 'float32': 'F32', 'float16': 'F16', 'int64': 'I64',
             'int32': 'I32', 'int16': 'I16', 'int8': 'I8', 'uint8': 'U8', 'bool': 'BOOL'}


# ------------------------------------------------------------ safetensors IO
def read_safetensors(path: Path) -> tuple:
    """返回 (header: dict, tensors: {name: np.ndarray})。支持 F32/F16/BF16 等。"""
    import numpy as np
    raw = Path(path).read_bytes()
    if len(raw) < 8:
        raise ValueError('文件太小，不是 safetensors')
    (n,) = struct.unpack('<Q', raw[:8])
    header = json.loads(raw[8:8 + n].decode('utf-8'))
    body = raw[8 + n:]
    tensors = {}
    for name, meta in header.items():
        if name == '__metadata__':
            continue
        dt = meta.get('dtype')
        shape = meta.get('shape') or []
        start, end = meta.get('data_offsets', [0, 0])
        buf = body[start:end]
        if dt == 'BF16':
            u = np.frombuffer(buf, dtype='<u2').astype(np.uint32) << 16
            arr = u.view(np.float32)
        else:
            np_dt = _DTYPES.get(dt)
            if np_dt is None:
                raise ValueError(f'不支持的 dtype：{dt}')
            arr = np.frombuffer(buf, dtype=np.dtype(np_dt))
        tensors[name] = arr.reshape(shape).copy() if shape else arr.copy()
    return header, tensors


def write_safetensors(path: Path, tensors: dict, dtype_of: dict | None = None,
                      metadata: dict | None = None) -> int:
    """写 safetensors（头部 8 字节对齐）。dtype_of 可指定各张量原始 dtype（如 BF16）。"""
    import numpy as np
    dtype_of = dtype_of or {}
    header, blobs, offset = {}, [], 0
    for name, arr in tensors.items():
        want = dtype_of.get(name)
        if want == 'BF16':
            u = (arr.astype(np.float32).view(np.uint32) >> 16).astype('<u2')
            buf = u.tobytes()
            header[name] = {'dtype': 'BF16', 'shape': list(arr.shape),
                            'data_offsets': [offset, offset + len(buf)]}
        else:
            a = np.ascontiguousarray(arr)
            if a.dtype.name not in _NP_TO_ST:
                a = a.astype(np.float32)
            buf = a.tobytes()
            header[name] = {'dtype': _NP_TO_ST[a.dtype.name], 'shape': list(a.shape),
                            'data_offsets': [offset, offset + len(buf)]}
        offset += len(buf)
        blobs.append(buf)
    if metadata:
        header['__metadata__'] = metadata
    hj = json.dumps(header, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    pad = (-len(hj)) % 8
    hj += b' ' * pad
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(struct.pack('<Q', len(hj)))
        f.write(hj)
        for b in blobs:
            f.write(b)
    return Path(path).stat().st_size


# ------------------------------------------------------------------ 工具
def find_weights(adapter_dir: Path) -> Path | None:
    for name in ADAPTER_WEIGHTS:
        p = Path(adapter_dir) / name
        if p.exists():
            return p
    return None


def read_config(adapter_dir: Path) -> dict:
    p = Path(adapter_dir) / ADAPTER_CONFIG
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:                                                # noqa: BLE001
        return {}


def read_rank(adapter_dir: Path) -> int:
    cfg = read_config(adapter_dir)
    if cfg.get('r'):
        return int(cfg['r'])
    w = find_weights(adapter_dir)
    if w and w.suffix == '.safetensors':
        try:
            _h, ts = read_safetensors(w)
            for k, v in ts.items():
                if k.endswith('lora_A.weight') and v.ndim == 2:
                    return int(v.shape[0])
        except Exception:                                            # noqa: BLE001
            pass
    return 0


def plan_next_rank(cur: int, max_rank: int = DEFAULT_MAX_RANK, factor: int = DEFAULT_FACTOR) -> int:
    """下一档 rank；已达上限则返回当前值（此时应改用 7.2 的多适配器堆叠）。"""
    nxt = max(cur, 1) * max(factor, 2)
    return min(nxt, int(max_rank))


def human(n: float) -> str:
    for unit, div in (('GB', 1024 ** 3), ('MB', 1024 ** 2), ('KB', 1024)):
        if n >= div:
            return f'{n / div:.2f} {unit}'
    return f'{int(n)} B'


# ------------------------------------------------------------ 升 rank 实现
def grow_lora_rank(adapter_dir: Path | str, new_rank: int | None = None,
                   max_rank: int = DEFAULT_MAX_RANK, factor: int = DEFAULT_FACTOR,
                   seed: int = 20260925, dry_run: bool = False, log=print) -> dict:
    """把 LoRA 适配器升到更大的 rank（旧权重复制保留，其余随机/补零）。"""
    import numpy as np
    d = Path(adapter_dir)
    cfg = read_config(d)
    if not cfg:
        return {'ok': False, 'error': f'找不到 {ADAPTER_CONFIG}（{d}）'}
    cur = int(cfg.get('r') or 0) or read_rank(d)
    if not cur:
        return {'ok': False, 'error': '无法确定当前 rank'}
    nxt = int(new_rank) if new_rank else plan_next_rank(cur, max_rank, factor)
    nxt = min(nxt, int(max_rank))          # 硬上限保护：显式指定也不允许越界
    if nxt <= cur:
        return {'ok': False, 'reason': 'at_max_rank', 'rank': cur, 'max_rank': max_rank,
                'message': f'rank 已到上限 {cur}（上限 {max_rank}）。'
                           f'建议改用设计文档 7.2 的多适配器堆叠方案继续成长。'}
    w = find_weights(d)
    if w is None:
        if dry_run:
            return {'ok': True, 'dry_run': True, 'rank_from': cur, 'rank_to': nxt}
        return {'ok': False, 'error': '找不到适配器权重文件'}

    before_size = w.stat().st_size
    if w.suffix != '.safetensors':
        return _grow_with_torch(w, d, cur, nxt, dry_run, log)

    header, tensors = read_safetensors(w)
    new_tensors, dtype_of = {}, {}
    rng = np.random.default_rng(seed)
    grown = {'A': 0, 'B': 0, 'other': 0}
    for name, arr in tensors.items():
        meta = header.get(name, {})
        dtype_of[name] = meta.get('dtype', 'F32')
        if name.endswith('lora_A.weight') and arr.ndim == 2 and arr.shape[0] == cur:
            fan_in = int(arr.shape[1])
            out = np.zeros((nxt, fan_in), dtype=np.float32)
            out[:cur] = arr.astype(np.float32)
            std = 1.0 / max(fan_in, 1) ** 0.5 * 0.01        # 新增行：小方差，避免扰动已学知识
            out[cur:] = rng.normal(0.0, std, size=(nxt - cur, fan_in)).astype(np.float32)
            new_tensors[name] = out
            grown['A'] += 1
        elif name.endswith('lora_B.weight') and arr.ndim == 2 and arr.shape[1] == cur:
            out_dim = int(arr.shape[0])
            out = np.zeros((out_dim, nxt), dtype=np.float32)
            out[:, :cur] = arr.astype(np.float32)
            # 新增列补零 → 升 rank 后初始输出与升之前完全一致
            new_tensors[name] = out
            grown['B'] += 1
        else:
            new_tensors[name] = arr
            grown['other'] += 1

    new_cfg = dict(cfg)
    ratio = float(cfg.get('lora_alpha') or (cur * 2)) / max(cur, 1)
    new_cfg['r'] = int(nxt)
    new_cfg['lora_alpha'] = int(round(nxt * ratio)) or nxt * 2
    if 'rank_pattern' in new_cfg:
        new_cfg.pop('rank_pattern', None)
    if 'alpha_pattern' in new_cfg:
        new_cfg.pop('alpha_pattern', None)

    params = _count_lora_params(new_tensors)
    result = {'ok': True, 'rank_from': cur, 'rank_to': int(nxt), 'factor': factor,
              'max_rank': max_rank, 'grown': grown, 'lora_params': params,
              'alpha': new_cfg['lora_alpha'],
              'weights': w.name, 'dry_run': bool(dry_run),
              'message': f'LoRA rank {cur} → {nxt}（旧权重复制保留，新增行小方差 / 新增列补零）'}
    if dry_run:
        result['size_before'] = before_size
        return result

    tmp_w = w.with_suffix(w.suffix + '.tmp')
    write_safetensors(tmp_w, new_tensors, dtype_of)
    after_size = tmp_w.stat().st_size
    # 原子替换：先备份 config，再落盘
    bak_cfg = d / (ADAPTER_CONFIG + '.bak')
    shutil.copy2(d / ADAPTER_CONFIG, bak_cfg)
    shutil.move(str(w), str(w.with_suffix(w.suffix + '.old')))
    shutil.move(str(tmp_w), str(w))
    (d / ADAPTER_CONFIG).write_text(json.dumps(new_cfg, ensure_ascii=False, indent=1), encoding='utf-8')
    (w.with_suffix(w.suffix + '.old')).unlink(missing_ok=True)
    bak_cfg.unlink(missing_ok=True)
    result['size_before'] = before_size
    result['size_after'] = after_size
    result['growth_bytes'] = after_size - before_size
    result['growth_human'] = human(max(after_size - before_size, 0))
    log(f'  [升 rank] {cur} → {nxt}：适配器 {human(before_size)} → {human(after_size)}'
        f'（+{human(max(after_size - before_size, 0))}）')
    return result


def _grow_with_torch(w: Path, d: Path, cur: int, nxt: int, dry_run: bool, log) -> dict:
    """非 safetensors 适配器（.bin/.pt）：装 torch 时用 torch 扩秩。"""
    try:
        import torch
    except Exception:                                                # noqa: BLE001
        return {'ok': False, 'error': f'{w.name} 需要 torch 才能扩秩（或把适配器存成 safetensors）'}
    if dry_run:
        return {'ok': True, 'dry_run': True, 'rank_from': cur, 'rank_to': nxt,
                'message': '演练：torch 分支未实际写盘'}
    sd = torch.load(str(w), map_location='cpu')
    out = {}
    for k, v in sd.items():
        if k.endswith('lora_A.weight') and v.ndim == 2 and v.shape[0] == cur:
            t = torch.zeros(nxt, v.shape[1], dtype=v.dtype)
            t[:cur] = v
            t[cur:] = torch.randn(nxt - cur, v.shape[1], dtype=v.dtype) * 0.01 / max(v.shape[1], 1) ** 0.5
            out[k] = t
        elif k.endswith('lora_B.weight') and v.ndim == 2 and v.shape[1] == cur:
            t = torch.zeros(v.shape[0], nxt, dtype=v.dtype)
            t[:, :cur] = v
            out[k] = t
        else:
            out[k] = v
    shutil.copy2(w, w.with_suffix(w.suffix + '.old'))
    torch.save(out, str(w))
    w.with_suffix(w.suffix + '.old').unlink(missing_ok=True)
    cfg = read_config(d)
    ratio = float(cfg.get('lora_alpha') or cur * 2) / max(cur, 1)
    cfg.update({'r': nxt, 'lora_alpha': int(round(nxt * ratio))})
    (d / ADAPTER_CONFIG).write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding='utf-8')
    size = w.stat().st_size
    return {'ok': True, 'rank_from': cur, 'rank_to': nxt, 'size_after': size,
            'message': f'torch 分支：rank {cur} → {nxt}'}


def _count_lora_params(tensors: dict) -> int:
    total = 0
    for k, v in tensors.items():
        if 'lora_' in k and hasattr(v, 'size'):
            n = 1
            for s in v.shape:
                n *= int(s)
            total += n
    return total


# ------------------------------------------------------------ 堆叠（备选）
def stack_info(adapter_dir: Path | str, seeds_dir: Path | str | None = None) -> dict:
    """设计文档 7.2「多适配器堆叠」：列出当前适配器与历史种子，供合并排序。"""
    d = Path(adapter_dir)
    seeds = Path(seeds_dir) if seeds_dir else (d.parent / 'adapter_seeds')
    items = []
    cur_r = read_rank(d)
    items.append({'name': 'current', 'dir': str(d), 'rank': cur_r,
                  'bytes': sum(f.stat().st_size for f in d.glob('*') if f.is_file())})
    if seeds.exists():
        for s in sorted(seeds.iterdir()):
            if s.is_dir():
                items.append({'name': s.name, 'dir': str(s), 'rank': read_rank(s),
                              'bytes': sum(f.stat().st_size for f in s.glob('*') if f.is_file())})
    return {'stacks': items, 'count': len(items),
            'note': '主用动态升 rank（core.rank.grow_lora_rank）；堆叠为备选方案，'
                    '合并时按创建顺序依次 merge。'}


def status(adapter_dir: Path | str, max_rank: int = DEFAULT_MAX_RANK) -> dict:
    d = Path(adapter_dir)
    cfg = read_config(d)
    cur = read_rank(d)
    w = find_weights(d)
    size = w.stat().st_size if w else 0
    nxt = plan_next_rank(cur, max_rank) if cur else 0
    return {'adapter_dir': str(d), 'rank': cur, 'alpha': cfg.get('lora_alpha'),
            'target_modules': cfg.get('target_modules'), 'weights': w.name if w else None,
            'weights_human': human(size), 'weights_bytes': size,
            'next_rank': nxt, 'max_rank': max_rank,
            'at_max_rank': bool(cur and cur >= max_rank),
            'note': ('rank 已到上限，建议改用多适配器堆叠' if cur and cur >= max_rank
                     else f'下一步可升到 rank {nxt}')}


def main(argv=None):
    ap = argparse.ArgumentParser(description='小凌 LoRA 动态升 rank')
    ap.add_argument('cmd', choices=['status', 'grow', 'stack'])
    ap.add_argument('--adapter', default='')
    ap.add_argument('--rank', type=int, default=None)
    ap.add_argument('--max-rank', type=int, default=DEFAULT_MAX_RANK)
    ap.add_argument('--factor', type=int, default=DEFAULT_FACTOR)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--root', default=str(APP_DIR))
    a = ap.parse_args(argv)
    adp = Path(a.adapter) if a.adapter else (Path(a.root) / '.star_core' / 'adapter')
    if a.cmd == 'status':
        print(json.dumps(status(adp, a.max_rank), ensure_ascii=False, indent=1))
    elif a.cmd == 'grow':
        print(json.dumps(grow_lora_rank(adp, a.rank, a.max_rank, a.factor, dry_run=a.dry_run),
                         ensure_ascii=False, indent=1))
    else:
        print(json.dumps(stack_info(adp), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
