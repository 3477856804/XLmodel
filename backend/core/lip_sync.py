# -*- coding: utf-8 -*-
"""小凌 · 口型同步（viseme 时间轴分析）

简化策略：基于音频短时 RMS 能量估计嘴部开合程度。
不做音素级识别（那需要 forced alignment / 声学模型），
而是按固定窗口切片，把能量归一化到 0.0~1.0 作为 mouth_open。

不可用（缺依赖 / 文件损坏）时返回明确错误，绝不伪造口型数据。
"""
from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path


class LipSync:
    """基于 RMS 能量的口型时间轴分析器。"""

    WINDOW_MS = 40.0
    HOP_MS = 20.0

    def __init__(self, window_ms: float = WINDOW_MS, hop_ms: float = HOP_MS):
        self.window_ms = float(window_ms)
        self.hop_ms = float(hop_ms)
        self.last_error = ""

    # ------------------------------------------------------------------ 工具
    def _to_wav(self, audio_path: str) -> tuple[str, bool]:
        """把任意音频转成 16k 单声道 WAV。返回 (路径, 是否临时文件)。"""
        p = Path(audio_path)
        if not p.is_file():
            self.last_error = f"音频文件不存在：{audio_path}"
            return "", False
        if p.suffix.lower() == ".wav":
            return str(p), False
        try:
            from .multimodal import AudioConverter
        except Exception:
            from multimodal import AudioConverter  # type: ignore
        if not AudioConverter.available():
            self.last_error = "ffmpeg 不可用，无法转码非 WAV 音频"
            return "", False
        tmp = Path(tempfile.gettempdir()) / f"xl_lipsync_{p.stem}.wav"
        if not AudioConverter.convert(str(p), str(tmp), "wav", 16000, 1):
            self.last_error = f"ffmpeg 转码失败：{audio_path}"
            return "", False
        return str(tmp), True

    @staticmethod
    def _read_wav_mono(path: str) -> tuple[list[float], int]:
        """读 WAV，返回 (-1.0~1.0) 归一化的单声道采样 + 采样率。"""
        with wave.open(path, "rb") as w:
            n_channels = w.getnchannels()
            sampwidth = w.getsampwidth()
            framerate = w.getframerate()
            n_frames = w.getnframes()
            raw = w.readframes(n_frames)
        if sampwidth == 2:
            fmt = "<" + "h" * (len(raw) // 2)
            samples = list(struct.unpack(fmt, raw))
        elif sampwidth == 1:
            samples = [(b - 128) * 256 for b in raw]
        elif sampwidth == 4:
            fmt = "<" + "i" * (len(raw) // 4)
            samples = list(struct.unpack(fmt, raw))
            samples = [s // 65536 for s in samples]
        else:
            raise ValueError(f"不支持的采样位宽：{sampwidth}")
        if n_channels > 1:
            mono = []
            for i in range(0, len(samples), n_channels):
                chunk = samples[i:i + n_channels]
                mono.append(sum(chunk) / len(chunk))
            samples = mono
        peak = max(1, max(abs(s) for s in samples)) if samples else 1
        return [s / peak for s in samples], framerate

    # ------------------------------------------------------------------ 主接口
    def analyze_viseme(self, audio_path: str) -> dict:
        """分析音频，返回口型时间轴。

        返回：
            {"ok": True, "duration": float, "visemes": [{"time": float, "level": float}, ...]}
            失败：
            {"ok": False, "error": "...", "visemes": []}
        """
        self.last_error = ""
        try:
            wav_path, is_tmp = self._to_wav(audio_path)
            if not wav_path:
                return {"ok": False, "error": self.last_error or "无法读取音频",
                        "visemes": []}
            try:
                samples, sr = self._read_wav_mono(wav_path)
            finally:
                if is_tmp:
                    try:
                        Path(wav_path).unlink()
                    except OSError:
                        pass
            if not samples or sr <= 0:
                return {"ok": False, "error": "音频内容为空或采样率异常",
                        "visemes": []}

            win = max(1, int(sr * self.window_ms / 1000.0))
            hop = max(1, int(sr * self.hop_ms / 1000.0))
            visemes = []
            energies = []
            for start in range(0, len(samples) - win + 1, hop):
                chunk = samples[start:start + win]
                rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
                energies.append(rms)
            if not energies:
                return {"ok": False, "error": "窗口数为零，无法分析",
                        "visemes": []}
            peak = max(energies) or 1.0
            floor = max(0.02, peak * 0.15)
            for i, e in enumerate(energies):
                level = (e - floor) / (peak - floor) if peak > floor else 0.0
                level = max(0.0, min(1.0, level))
                visemes.append({
                    "time": round(i * self.hop_ms / 1000.0, 3),
                    "level": round(level, 3),
                })
            duration = len(samples) / sr
            return {"ok": True, "duration": round(duration, 3),
                    "visemes": visemes}
        except Exception as e:
            self.last_error = f"analyze_viseme: {type(e).__name__}: {e}"
            return {"ok": False, "error": self.last_error, "visemes": []}

    def viseme_timeline_for_tts(self, text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> dict:
        """TTS 合成时同步生成 viseme 时间轴。

        先用 TTS 合成到临时文件，再 analyze_viseme 分析。
        不可用时返回明确错误，不伪造。
        """
        self.last_error = ""
        if not text or not text.strip():
            return {"ok": False, "error": "空文本", "visemes": []}
        try:
            from .multimodal import TTS
        except Exception:
            from multimodal import TTS  # type: ignore
        try:
            tts = TTS()
            r = tts.synth(text, voice=voice, use_cache=True)
            if not r.ok or not r.data:
                self.last_error = tts.last_error or "TTS 合成失败"
                return {"ok": False, "error": self.last_error, "visemes": []}
            tmp = Path(tempfile.gettempdir()) / f"xl_lipsync_tts_{abs(hash(text)) & 0xffffff}.mp3"
            tmp.write_bytes(r.data)
            try:
                return self.analyze_viseme(str(tmp))
            finally:
                try:
                    tmp.unlink()
                except OSError:
                    pass
        except Exception as e:
            self.last_error = f"viseme_timeline_for_tts: {type(e).__name__}: {e}"
            return {"ok": False, "error": self.last_error, "visemes": []}


def analyze_viseme(audio_path: str) -> dict:
    """模块级便捷函数。"""
    return LipSync().analyze_viseme(audio_path)
