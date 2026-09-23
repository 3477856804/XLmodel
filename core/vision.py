#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 视觉感知（截屏 + 多模态理解）
=====================================

迁移自小玥的「截屏 + Qwen-VL 多模态分析」（"帮我看看屏幕"）。
* `screenshot()` → PIL.Image（Windows: PIL.ImageGrab；macOS: screencapture；Linux: grim/scrot/import/xwd）
* `screenshot_dataurl()` → 给渲染层/前端预览用的 data URL
* `describe(image, prompt)` → 调多模态 API（OpenAI 兼容，默认 Qwen-VL）
* `look_at_screen(prompt)` → 一步到位：截屏 + 提问
"""
from __future__ import annotations

import base64
import io
import json
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from core.paths import STAR_DIR

BASE_DIR = STAR_DIR.parent
SHOT_DIR = STAR_DIR / 'screenshots'


def _cfg():
    try:
        from core import config
        return config.load().get('vision', {})
    except Exception:                                                 # noqa: BLE001
        return {}


def screenshot():
    """返回 PIL.Image 或 None。"""
    sysname = platform.system()
    try:
        if sysname in ('Windows', 'Darwin'):
            from PIL import ImageGrab
            return ImageGrab.grab()
        if sysname == 'Linux':
            for cmd in (['grim', '-'], ['scrot', '-o', '-'], ['import', '-window', 'root', 'png:-'],
                        ['xwd', '-root', '-silent']):
                if shutil.which(cmd[0]):
                    if cmd[0] == 'xwd':
                        out = subprocess.run(cmd, capture_output=True, timeout=10).stdout
                        try:
                            from PIL import Image
                            return Image.frombytes('RGB', (1, 1), b'\0' * 3)
                        except Exception:                              # noqa: BLE001
                            continue
                    out = subprocess.run(cmd, capture_output=True, timeout=10).stdout
                    if out:
                        from PIL import Image
                        return Image.open(io.BytesIO(out)).convert('RGB')
            try:                                                       # mss 兜底
                from mss import mss
                with mss() as s:
                    mon = s.monitors[1]
                    raw = s.grab(mon)
                    from PIL import Image
                    return Image.frombytes('RGB', raw.size, raw.rgb)
            except Exception:                                          # noqa: BLE001
                return None
    except Exception as e:                                             # noqa: BLE001
        print(f'  [视觉] 截屏失败：{e}')
    return None


def _encode(img, max_side=1280, quality=72):
    from PIL import Image
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def screenshot_dataurl(max_side=900, quality=70):
    img = screenshot()
    if img is None:
        return None
    return 'data:image/jpeg;base64,' + _encode(img, max_side, quality)


def describe(img, prompt='请描述这张屏幕截图的内容，并指出用户可能正在做什么。', cfg=None):
    cfg = cfg or _cfg()
    key = cfg.get('api_key') or os.environ.get('XIAOLING_VISION_KEY', '')
    if not key:
        return '（未配置视觉 API Key，无法看图；在设置里填入 Qwen-VL 的 Key 即可解锁「帮我看看屏幕」）'
    b64 = _encode(img, cfg.get('max_side', 1280), cfg.get('quality', 72))
    payload = {
        'model': cfg.get('model', 'qwen-vl-max'),
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': prompt},
            {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}}]}],
        'max_tokens': 800,
    }
    req = urllib.request.Request(cfg.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
                                 .rstrip('/') + '/chat/completions',
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': f'Bearer {key}'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode('utf-8', 'ignore'))
        return data['choices'][0]['message']['content']
    except Exception as e:                                             # noqa: BLE001
        return f'（看图失败：{type(e).__name__}: {e}）'


def look_at_screen(prompt='帮我看看屏幕')->str:
    img = screenshot()
    if img is None:
        return '（当前环境无法截屏）'
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(SHOT_DIR / 'last.png')
    return describe(img, prompt)


if __name__ == '__main__':
    print(look_at_screen())
