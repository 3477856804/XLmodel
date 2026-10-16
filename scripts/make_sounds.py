#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""程序化生成工具音效（不依赖任何外部素材）

    python3 工具/make_sounds.py            # 生成到 sounds/tool/
    python3 工具/make_sounds.py --out sounds/tool
"""
import argparse
import math
import struct
import wave
from pathlib import Path

SOUNDS = {'notify': [880], 'success': [660, 990], 'error': [320, 240], 'click': [1200],
          'remind': [784, 1046], 'start': [523, 659], 'message': [740, 880], 'wake': [988, 1318]}


def tone(path: Path, freqs, dur=0.18, vol=0.35, sr=22050):
    frames = bytearray()
    n = int(sr * dur)
    for i in range(n):
        t = i / sr
        env = min(1.0, t / 0.01) * max(0.0, 1 - t / dur + 0.4)
        s = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
        frames += struct.pack('<h', int(max(-1.0, min(1.0, s * env * vol)) * 32767))
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))


def main(argv=None):
    ap = argparse.ArgumentParser(description='生成小凌工具音效')
    ap.add_argument('--out', default='sounds/tool')
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, freqs in SOUNDS.items():
        tone(out / f'{name}.wav', freqs)
    print(f'已生成 {len(SOUNDS)} 个音效 → {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
