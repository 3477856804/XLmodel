#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 情感语音合成（多引擎）
================================

迁移自小玥的「Minimax / Edge-TTS 双引擎情感语音」，在 Python 侧统一：

    engine = auto  →  minimax（有 Key）＞ edge-tts（有网/有包）＞ pyttsx3（离线）
    engine = pyttsx3 / edge / minimax 可强制指定

情绪 → 语速/音色映射：开心(快、亮) / 难过(慢、低) / 生气(快、硬) / 平静(中)。
产出：`.star_core/tts/out_<ts>.mp3|wav`，供数字人渲染层 `audio` 事件直接播放。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from core.paths import STAR_DIR

BASE_DIR = STAR_DIR.parent
OUT_DIR = STAR_DIR / 'tts'

EMOTION_PROFILE = {
    'happy': {'rate': 1.12, 'pitch': 1.06, 'edge_rate': '+12%', 'edge_pitch': '+6Hz'},
    'joy': {'rate': 1.12, 'pitch': 1.06, 'edge_rate': '+12%', 'edge_pitch': '+6Hz'},
    'sad': {'rate': 0.88, 'pitch': 0.94, 'edge_rate': '-14%', 'edge_pitch': '-6Hz'},
    'angry': {'rate': 1.15, 'pitch': 1.02, 'edge_rate': '+16%', 'edge_pitch': '+2Hz'},
    'surprised': {'rate': 1.2, 'pitch': 1.12, 'edge_rate': '+20%', 'edge_pitch': '+10Hz'},
    'neutral': {'rate': 1.0, 'pitch': 1.0, 'edge_rate': '+0%', 'edge_pitch': '+0Hz'},
}


def _cfg():
    try:
        from core import config
        return config.load()
    except Exception:                                                 # noqa: BLE001
        return {}


def _profile(emotion):
    return EMOTION_PROFILE.get((emotion or 'neutral').lower(), EMOTION_PROFILE['neutral'])


def synthesize(text: str, emotion: str = None, engine: str = None, out: Path | None = None):
    """把所有引擎统一成"返回音频文件路径或 None"。"""
    cfg = _cfg()
    tcfg = cfg.get('tts', {})
    engine = engine or tcfg.get('engine', 'auto')
    text = (text or '').strip()
    if not text:
        return None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prof = _profile(emotion)
    order = ([engine] if engine != 'auto' else
             (['minimax'] if tcfg.get('minimax_key') else []) +
             (['edge'] if _edge_available() else []) +
             ['pyttsx3'])
    for eng in order:
        try:
            if eng == 'minimax':
                p = _minimax(text, prof, tcfg, out)
            elif eng == 'edge':
                p = _edge(text, prof, tcfg, out)
            else:
                p = _pyttsx3(text, prof)
            if p:
                return str(p)
        except Exception as e:                                        # noqa: BLE001
            print(f'  [语音] {eng} 失败：{type(e).__name__}: {e}')
    return None


def _edge_available():
    if shutil.which('edge-tts'):
        return True
    try:
        import edge_tts                                          # noqa: F401
        return True
    except Exception:                                             # noqa: BLE001
        return False


def _edge(text, prof, tcfg, out=None):
    # 角色绑定音色优先（换角色即换声音）；未绑定时回退配置里的 edge_voice
    try:
        from core import voices
        voice = voices.get_current_voice()
    except Exception:                                            # noqa: BLE001
        voice = tcfg.get('edge_voice', 'zh-CN-XiaoxiaoNeural')
    path = Path(out) if out else OUT_DIR / f'out_{int(time.time() * 1000)}.mp3'
    if shutil.which('edge-tts'):
        cmd = ['edge-tts', '--voice', voice, '--text', text, '--write-media', str(path),
               '--rate', prof['edge_rate'], '--pitch', prof['edge_pitch']]
        subprocess.run(cmd, check=True, timeout=90, capture_output=True)
        return path if path.exists() else None
    import asyncio
    import edge_tts
    async def go():
        c = edge_tts.Communicate(text, voice, rate=prof['edge_rate'], pitch=prof['edge_pitch'])
        await c.save(str(path))
    asyncio.run(go())
    return path if path.exists() else None


def _minimax(text, prof, tcfg, out=None):
    key = tcfg.get('minimax_key', '')
    if not key:
        return None
    path = Path(out) if out else OUT_DIR / f'out_{int(time.time() * 1000)}.mp3'
    payload = {
        'model': 'speech-01-turbo',
        'text': text[:800],
        'voice_setting': {'voice_id': tcfg.get('minimax_voice', 'female-shaonv'),
                          'speed': prof['rate'], 'pitch': int((prof['pitch'] - 1) * 12)},
        'audio_setting': {'format': 'mp3'},
    }
    req = urllib.request.Request('https://api.minimax.chat/v1/t2a_v2',
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': f'Bearer {key}'})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode('utf-8', 'ignore'))
    hex_audio = (data.get('data') or {}).get('audio')
    if not hex_audio:
        return None
    path.write_bytes(bytes.fromhex(hex_audio))
    return path


def _pyttsx3(text, prof):
    import pyttsx3
    eng = pyttsx3.init()
    try:
        eng.setProperty('rate', int(175 * prof['rate']))
        eng.setProperty('volume', 1.0)
        path = OUT_DIR / f'out_{int(time.time() * 1000)}.wav'
        eng.save_to_file(text, str(path))
        eng.runAndWait()
        return path if path.exists() else None
    finally:
        try:
            eng.stop()
        except Exception:                                             # noqa: BLE001
            pass


def speak_blocking(text, emotion=None):
    """直接出声（无文件落盘时用系统 TTS）。"""
    path = synthesize(text, emotion)
    if not path:
        return False
    if path.endswith('.wav') or path.endswith('.mp3'):
        for player in (['ffplay', '-nodisp', '-autoexit'], ['mpv', '--no-video'], ['aplay'],
                       ['afplay'], ['start']):
            if shutil.which(player[0]):
                try:
                    subprocess.Popen(player + [path], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return True
                except Exception:                                     # noqa: BLE001
                    continue
    return False


if __name__ == '__main__':
    import sys
    print(synthesize(' '.join(sys.argv[1:]) or '你好呀，我是小凌'))
