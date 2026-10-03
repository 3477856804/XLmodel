#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.paths —— 统一路径解析（开发环境 / PyInstaller 打包后都正确）

打包后的关键区别：

    · **只读资源**（models / animations / assets / skills / data / tools / docs / renderer）
      跟着程序走：onedir 模式在可执行文件目录，onefile 模式在临时解包目录 `sys._MEIPASS`。
    · **可写数据**（.star_core：基底模型、LoRA 适配器、成长日志、记忆、配置、语音缓存）
      必须在可执行文件所在目录（用户可写），**绝不能放在 onefile 的临时目录**（退出即丢）。

对外 API：
    RESOURCE_DIR       只读资源根
    APP_DIR            可写数据根（= 可执行文件目录 / 项目根）
    STAR_DIR           APP_DIR/.star_core
    resource(*parts)   定位只读资源（自动兼容 onefile）
    star(*parts)       定位可写数据路径（自动建父目录）
    is_frozen()        是否运行在打包产物里
    describe()         打印路径诊断（自检/排障用）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_DEV_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/core/paths.py → 项目根


def is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def _bundle_dir() -> Path:
    """onefile 的临时解包目录 / onedir 的可执行文件目录。"""
    return Path(getattr(sys, '_MEIPASS', _DEV_ROOT))


def app_dir() -> Path:
    """可写数据根目录。可用环境变量 XIAOLING_HOME 覆盖（多用户/便携部署）。"""
    env = os.environ.get('XIAOLING_HOME')
    if env:
        p = Path(env).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _DEV_ROOT


def resource_dir() -> Path:
    """只读资源根目录。"""
    return _bundle_dir() if is_frozen() else _DEV_ROOT


RESOURCE_DIR = resource_dir()
APP_DIR = app_dir()
STAR_DIR = APP_DIR / '.star_core'
DATA_DIR = APP_DIR / 'data'


def resource(*parts, must_exist=False) -> Path:
    """定位只读资源：优先可执行文件目录（用户可放自己的模型覆盖），其次打包内资源。

    注意：必须逐个候选做**存在性判断**——否则打包后会把"可执行文件目录"的空路径
    当成命中，导致找不到 _internal/ 里的模型与动作。
    """
    rel = Path(*parts)
    # 资源统一放在 resources/ 下；开发态 APP_DIR=RESOURCE_DIR=项目根，
    # 因此既兼容旧的顶层平铺，也兼容 resources/ 子目录布局。
    for base in (APP_DIR, RESOURCE_DIR):
        for cand in (base / rel, base / 'resources' / rel):
            if cand.exists():
                return cand
    if must_exist:
        raise FileNotFoundError(f'资源不存在：{rel}（已查 {APP_DIR}、{RESOURCE_DIR}）')
    return APP_DIR / rel          # 都不存在 → 返回可写位置（调用方可能要新建）


def star(*parts, mkdir=False) -> Path:
    p = STAR_DIR.joinpath(*parts)
    if mkdir:
        p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_seed_dirs() -> dict:
    """打包后首次运行时准备可写目录，并把只读资源里的种子数据拷过来。

    · APP_DIR/.star_core/{XLmodel,adapter,growth,rag,tts,recordings,screenshots,images}
    · APP_DIR/data/  ← 若为空，从资源里复制 corpus.txt 等种子文件
    """
    out = {'created': [], 'seeded': []}
    for d in ('XLmodel', 'adapter', 'growth', 'rag', 'tts', 'recordings', 'screenshots',
              'images', 'refs', 'adapter_seeds'):
        p = STAR_DIR / d
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            out['created'].append(str(p))
    data_dir = APP_DIR / '数据'
    data_dir.mkdir(parents=True, exist_ok=True)
    src_data = RESOURCE_DIR / '数据'
    if src_data.exists() and src_data.resolve() != data_dir.resolve():
        for f in src_data.glob('*'):
            dst = data_dir / f.name
            if f.is_file() and not dst.exists():
                try:
                    dst.write_bytes(f.read_bytes())
                    out['seeded'].append(dst.name)
                except OSError:
                    pass
    return out


def describe() -> dict:
    return {'frozen': is_frozen(), 'resource_dir': str(RESOURCE_DIR), 'app_dir': str(APP_DIR),
            'star_dir': str(STAR_DIR), 'python': sys.version.split()[0],
            'executable': sys.executable,
            'xiaoling_home': os.environ.get('XIAOLING_HOME', '')}


if __name__ == '__main__':
    import json
    print(json.dumps(describe(), ensure_ascii=False, indent=1))
