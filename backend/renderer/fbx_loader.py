#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.fbx_loader —— FBX 模型加载桥接（v0.0.1 新增）

背景：小凌的渲染管线是自写软件光栅 + VRM/glTF 解析（见 renderer/gltf.py），
原生只吃 ``.vrm / .glb / .gltf``。用户希望支持 ``.fbx``（例如 ty.fbx）。

现实约束：FBX 是 Autodesk 私有二进制格式，在纯 Python 里从零解析代价极高。
务实方案：
    1. 优先调用系统 ``assimp export xxx.fbx tmp.glb`` 转成 glb；
    2. 其次尝试 Python 侧 ``pyassimp``（同样依赖系统 libassimp）；
    3. 都没有就抛 ``FBXUnavailable``，上层回退到 .vrm，**绝不崩溃**。

转换产物缓存在 ``.star_core/fbx_cache/<fbx名>.glb``，避免每次启动都转。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FBXUnavailable(RuntimeError):
    """当前环境没有可用的 FBX→glb 转换工具（assimp）。"""


def _cache_dir() -> Path:
    d = Path.home() / '.star_core' / 'fbx_cache'
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:                                               # noqa: BLE001
        pass
    return d


def _find_assimp() -> str | None:
    """找系统里的 assimp 可执行文件。"""
    for name in ('assimp', 'assimp.exe'):
        p = shutil.which(name)
        if p:
            return p
    return None


def convert_fbx_to_glb(fbx_path: str | Path, log=print) -> Path:
    """把 .fbx 转成 .glb，返回 glb 路径。

    找不到 assimp 时抛 FBXUnavailable。
    """
    fbx = Path(fbx_path)
    if not fbx.exists():
        raise FileNotFoundError(f'FBX 不存在：{fbx}')

    out = _cache_dir() / (fbx.stem + '.glb')
    # 已缓存且比 fbx 新，直接用
    if out.exists() and out.stat().st_mtime >= fbx.stat().st_mtime:
        log(f'  [FBX] 使用缓存：{out.name}')
        return out

    assimp = _find_assimp()
    if not assimp:
        raise FBXUnavailable(
            '未找到 assimp 命令。请安装：\n'
            '  · Debian/Ubuntu: sudo apt install assimp\n'
            '  · macOS: brew install assimp\n'
            '  · Windows: 下载 https://github.com/assimp/assimp/releases 并加入 PATH\n'
            '安装后重启小凌即可加载 FBX 模型。')

    log(f'  [FBX] 用 assimp 转换 {fbx.name} → {out.name} ...')
    cmd = [assimp, 'export', str(fbx), str(out), '-f', 'glb2']
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(
            f'assimp 转换失败（exit={proc.returncode}）：'
            f'{(proc.stderr or proc.stdout).strip()[:400]}')
    log(f'  [FBX] 转换完成：{out}')
    return out


def load_any_model(path: str | Path, log=print):
    """按后缀加载模型：.vrm/.glb/.gltf 直接走 VRMModel，.fbx 先转 glb。

    返回 renderer.model.VRMModel 实例。
    """
    from renderer.model import VRMModel  # 延迟 import，避免循环依赖

    p = Path(path)
    suf = p.suffix.lower()
    if suf == '.fbx':
        glb = convert_fbx_to_glb(p, log=log)
        return VRMModel(glb)
    return VRMModel(p)


def list_model_files(model_dir: str | Path) -> list[Path]:
    """列出目录里所有可加载的模型文件（.vrm + .glb + .fbx）。"""
    d = Path(model_dir)
    out: list[Path] = []
    for ext in ('*.vrm', '*.VRM', '*.glb', '*.gltf', '*.fbx', '*.FBX'):
        out.extend(d.glob(ext))
    # 去重并排序
    seen = set()
    uniq = []
    for p in sorted(out):
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


__all__ = ['FBXUnavailable', 'convert_fbx_to_glb', 'load_any_model', 'list_model_files']
