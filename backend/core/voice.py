"""语音系统 - ASR语音识别 + TTS语音合成 + 音色绑定"""
import asyncio
import io
from pathlib import Path

# ===== 音色库 =====
VOICE_MAP = {
    "小凌": "zh-CN-XiaoxiaoNeural",
    "Vivi": "zh-CN-XiaohanNeural",
    "QuQu": "zh-CN-XiaoyiNeural",
}

VOICES = [
    {"id": "zh-CN-XiaoxiaoNeural", "name": "小凌", "lang": "zh-CN"},
    {"id": "zh-CN-XiaohanNeural", "name": "Vivi", "lang": "zh-CN"},
    {"id": "zh-CN-XiaoyiNeural", "name": "QuQu", "lang": "zh-CN"},
    {"id": "zh-CN-YunxiNeural", "name": "云希", "lang": "zh-CN"},
    {"id": "zh-CN-YunyangNeural", "name": "云扬", "lang": "zh-CN"},
]


def get_voice(character_name: str) -> str:
    return VOICE_MAP.get(character_name, "zh-CN-XiaoxiaoNeural")


# ===== TTS 语音合成 =====
class TTS:
    """edge-tts 语音合成引擎"""

    def __init__(self, engine="edge"):
        self.engine = engine

    def synthesize(self, text: str, voice: str = None) -> bytes:
        """合成语音，返回 MP3 bytes"""
        if not text or not text.strip():
            return b""
        voice = voice or "zh-CN-XiaoxiaoNeural"
        try:
            import edge_tts
            out = io.BytesIO()

            async def _gen():
                comm = edge_tts.Communicate(text, voice=voice)
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        out.write(chunk["data"])

            asyncio.run(_gen())
            return out.getvalue()
        except Exception as e:
            print(f"  [TTS] 合成失败: {e}")
            return b""

    def speak(self, text: str, voice: str = None):
        audio = self.synthesize(text, voice)
        if audio:
            path = "/tmp/xl_tts.mp3"
            with open(path, "wb") as f:
                f.write(audio)
            print(f"  [TTS] 已保存: {path} ({len(audio)} bytes)")


# ===== ASR 语音识别 =====
class ASR:
    """语音识别引擎（占位）"""

    def __init__(self, engine="whisper"):
        self.engine = engine

    def record(self, seconds: float = 5.0):
        return None

    def transcribe(self, path) -> str:
        return ""

    def listen(self, seconds: float = 5.0) -> str:
        path = self.record(seconds)
        if not path:
            return ""
        return self.transcribe(path)
