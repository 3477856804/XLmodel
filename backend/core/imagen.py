#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · AI 生图联动
====================

迁移自小玥的「参考图入库 + Banana 生图管线」：
* 参考图库：`.star_core/refs/图N.png`（对话中说"新增参考图"即可入库，自动编号）
* 生图：优先走本地管线命令（如 ComfyUI/banana CLI），否则走 OpenAI 兼容 images API
* 出图后回调（数字人气泡 + 打开图片）
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from core.paths import STAR_DIR

BASE_DIR = STAR_DIR.parent
REF_DIR = STAR_DIR / 'refs'
OUT_DIR = STAR_DIR / 'images'


def _cfg():
    try:
        from core import config
        return config.load().get('imagen', {})
    except Exception:                                                 # noqa: BLE001
        return {}


def add_reference(pil_image) -> dict:
    """把参考图入库，返回 {index, path, name}。"""
    REF_DIR.mkdir(parents=True, exist_ok=True)
    exist = sorted(REF_DIR.glob('图*.png'))
    idx = len(exist) + 1
    p = REF_DIR / f'图{idx}.png'
    pil_image.convert('RGB').save(p)
    return {'index': idx, 'path': str(p), 'name': p.stem,
            'total': len(list(REF_DIR.glob('图*.png')))}


def add_reference_bytes(data: bytes) -> dict:
    import io
    from PIL import Image
    return add_reference(Image.open(io.BytesIO(data)))


def references() -> list:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    return [{'name': p.stem, 'path': str(p)} for p in sorted(REF_DIR.glob('图*.png'))]


def generate(prompt: str, refs: list | None = None, size: str = '1024x1024'):
    cfg = _cfg()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f'gen_{int(time.time())}.png'
    pipeline = cfg.get('pipeline')
    if pipeline:      # 本地管线（例如 banana / ComfyUI 脚本）
        cmd = pipeline.format(prompt=prompt, out=str(out), size=size)
        try:
            subprocess.run(cmd, shell=True, check=True, timeout=600)
            if out.exists():
                return str(out)
        except Exception as e:                                        # noqa: BLE001
            print(f'  [生图] 本地管线失败：{e}')
    key = cfg.get('api_key') or os.environ.get('XIAOLING_IMAGE_KEY', '')
    if not key:
        return None
    payload = {'model': cfg.get('model', 'dall-e-3'), 'prompt': prompt, 'n': 1, 'size': size,
               'response_format': 'b64_json'}
    req = urllib.request.Request((cfg.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
                                 + '/images/generations',
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': f'Bearer {key}'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode('utf-8', 'ignore'))
        b64 = data['data'][0].get('b64_json')
        if b64:
            out.write_bytes(base64.b64decode(b64))
            return str(out)
        url = data['data'][0].get('url')
        if url:
            with urllib.request.urlopen(url, timeout=300) as r2:
                out.write_bytes(r2.read())
            return str(out)
    except Exception as e:                                            # noqa: BLE001
        print(f'  [生图] 失败：{e}')
    return None


def open_image(path):
    try:
        import platform
        if platform.system() == 'Windows':
            os.startfile(path)                                        # noqa: S606
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])
        return True
    except Exception:                                                 # noqa: BLE001
        return False


if __name__ == '__main__':
    import sys
    p = generate(' '.join(sys.argv[1:]) or '一只坐在窗台上的白猫，水彩风格')
    print(p or '未配置生图 API')
