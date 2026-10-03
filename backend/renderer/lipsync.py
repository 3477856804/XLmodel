#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.lipsync —— 中文/英文文本 → VRM 口型（aa/ih/ou/ee/oh）时间轴

纯离线规则映射：不需要音频分析、不依赖任何 TTS 引擎即可驱动口型（有音频时可叠加
RMS 幅度）。与旧版渲染层的 lipsync.js 行为一致，只是改成 Python 实现。
"""
from __future__ import annotations

import random
import time

VOWEL_MAP = {'a': 'aa', 'o': 'oh', 'e': 'ee', 'i': 'ih', 'u': 'ou', 'v': 'ou'}
VISEMES = ['aa', 'ih', 'ou', 'ee', 'oh']
PAUSE_CHARS = '，。！？、,.!?;:…—- \n\t'


def _han_viseme(ch: str) -> str:
    code = ord(ch)
    return VISEMES[(code * 7 + 13) % len(VISEMES)]


def text_to_visemes(text: str, speed: float = 0.16):
    track = []
    t = 0.0
    for ch in str(text or ''):
        if ch in PAUSE_CHARS:
            t += 0.10
            continue
        if '\u4e00' <= ch <= '\u9fff':
            v = _han_viseme(ch)
        elif ch.isalpha():
            v = VOWEL_MAP.get(ch.lower(), 'aa')
        else:
            continue
        dur = speed * (0.75 + random.random() * 0.5)
        track.append({'t': t, 'dur': dur, 'viseme': v, 'weight': 0.55 + random.random() * 0.4})
        t += dur
    return track, t


class LipSync:
    """把时间轴喂给表情权重（配合 renderer.renderer 的 morph 合并）。"""

    def __init__(self):
        self.track = []
        self.duration = 0.0
        self.time = 0.0
        self.playing = False
        self.amplitude = 1.0
        self.current = {v: 0.0 for v in VISEMES}

    def play(self, text: str, speed: float = 0.16) -> float:
        self.track, self.duration = text_to_visemes(text, speed)
        self.time = 0.0
        self.playing = bool(self.track)
        return self.duration

    def stop(self):
        self.playing = False
        self.track = []
        for v in VISEMES:
            self.current[v] = 0.0

    def set_amplitude(self, a: float):
        self.amplitude = max(0.0, min(2.0, float(a)))

    def update(self, dt: float):
        if not self.playing:
            return
        self.time += dt
        active = None
        for k in self.track:
            if k['t'] <= self.time < k['t'] + k['dur']:
                active = k
                break
        smooth = min(1.0, dt * 22)
        for v in VISEMES:
            target = (min(1.0, active['weight'] * self.amplitude)
                      if active and active['viseme'] == v else 0.0)
            self.current[v] += (target - self.current[v]) * smooth
        if self.time > self.duration + 0.15:
            self.stop()

    def weights(self) -> dict:
        """返回 {表情名: 权重}，可直接并入 morph 权重。"""
        table = {'aa': 'A', 'ih': 'I', 'ou': 'U', 'ee': 'E', 'oh': 'O'}
        return {table[v]: w for v, w in self.current.items() if w > 0.01}


def now() -> float:
    return time.time()
