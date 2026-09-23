#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 语音输入（录音 + 识别）
================================

迁移自小玥的「按住 F2 语音输入（百度 STT）」。Python 侧统一：
  * `record(seconds)`  → 用 sounddevice 录音为 wav（无麦克风/无依赖则返回 None）
  * `transcribe(wav)`  → 百度短语音识别（需 Key）或 OpenAI 兼容 whisper 端点
  * `listen(seconds)`  → 录 + 识别一步到位
"""
from __future__ import annotations

import base64
import json
import struct
import time
import urllib.parse
import urllib.request
import wave
from pathlib import Path

from core.paths import STAR_DIR

BASE_DIR = STAR_DIR.parent
REC_DIR = STAR_DIR / 'recordings'


def _cfg():
    try:
        from core import config
        return config.load().get('asr', {})
    except Exception:                                                 # noqa: BLE001
        return {}


def record(seconds: float = 5.0, sample_rate: int = 16000):
    REC_DIR.mkdir(parents=True, exist_ok=True)
    path = REC_DIR / f'rec_{int(time.time())}.wav'
    try:
        import numpy as np
        import sounddevice as sd
    except Exception as e:                                            # noqa: BLE001
        print(f'  [语音输入] 缺少录音依赖：{e}（pip install sounddevice numpy）')
        return None
    try:
        frames = int(seconds * sample_rate)
        audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait()
        with wave.open(str(path), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(audio.tobytes())
        return path
    except Exception as e:                                            # noqa: BLE001
        print(f'  [语音输入] 录音失败：{e}')
        return None


def _baidu_token(api_key, secret):
    url = ('https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials'
           f'&client_id={api_key}&client_secret={secret}')
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())['access_token']


def transcribe(path, cfg=None):
    cfg = cfg or _cfg()
    p = Path(path)
    if not p.exists():
        return None
    if cfg.get('engine', 'baidu') == 'baidu' and cfg.get('baidu_key') and cfg.get('baidu_secret'):
        try:
            tok = _baidu_token(cfg['baidu_key'], cfg['baidu_secret'])
            audio = base64.b64encode(p.read_bytes()).decode()
            data = urllib.parse.urlencode({'format': 'wav', 'rate': cfg.get('sample_rate', 16000),
                                           'channel': 1, 'cuid': 'xiaoling',
                                           'token': tok, 'speech': audio,
                                           'len': p.stat().st_size}).encode()
            req = urllib.request.Request(
                'https://vop.baidu.com/server_api', data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read().decode('utf-8', 'ignore'))
            if res.get('err_no') in (0, None):
                return ''.join(res.get('result', []))
            print(f"  [语音输入] 百度识别失败：{res.get('err_msg')}")
        except Exception as e:                                        # noqa: BLE001
            print(f'  [语音输入] 百度识别异常：{e}')
    return None


def listen(seconds: float = 5.0):
    p = record(seconds, _cfg().get('sample_rate', 16000))
    if not p:
        return None
    return transcribe(p)


if __name__ == '__main__':
    import sys
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(listen(secs))
