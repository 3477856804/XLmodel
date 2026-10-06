"""小凌 · 视觉系统（截屏 + 摄像头 + 多模态理解 + 图像生成）"""
import base64
import io
import json
import subprocess
import threading
import time
from pathlib import Path

from .config import DATA_DIR

SCREENSHOT_DIR = DATA_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def screenshot(path: str | None = None, region: tuple | None = None) -> str:
    target = Path(path) if path else SCREENSHOT_DIR / f"shot_{int(time.time() * 1000)}.png"
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=region)
        img.save(str(target))
        return str(target)
    except ImportError:
        pass
    try:
        if __import__("sys").platform == "darwin":
            subprocess.run(["screencapture", "-x", str(target)],
                           capture_output=True, timeout=10)
            if target.exists():
                return str(target)
        elif __import__("sys").platform.startswith("linux"):
            for cmd in (["gnome-screenshot", "-f", str(target)],
                        ["scrot", str(target)],
                        ["import", "-window", "root", str(target)]):
                try:
                    r = subprocess.run(cmd, capture_output=True, timeout=10)
                    if r.returncode == 0 and target.exists():
                        return str(target)
                except (OSError, subprocess.SubprocessError):
                    continue
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def screenshot_base64(path: str = "") -> str:
    p = path or screenshot()
    if not p or not Path(p).exists():
        return ""
    try:
        data = Path(p).read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    except OSError:
        return ""


def screenshot_resize(path: str, max_side: int = 1280,
                      quality: int = 72) -> str:
    try:
        from PIL import Image
    except ImportError:
        return path
    try:
        img = Image.open(path)
        if max(img.size) > max_side:
            r = max_side / max(img.size)
            img = img.resize((int(img.size[0] * r), int(img.size[1] * r)),
                             Image.LANCZOS)
        out = Path(path).with_suffix(".jpg")
        img.convert("RGB").save(str(out), "JPEG", quality=quality, optimize=True)
        try:
            Path(path).unlink()
        except OSError:
            pass
        return str(out)
    except Exception:
        return path


class Camera:
    def __init__(self, device: int = 0, width: int = 640, height: int = 480):
        self.device = device
        self.width = width
        self.height = height
        self._cap = None
        self._lock = threading.RLock()

    def available(self) -> bool:
        try:
            import cv2  # noqa: F401
            return True
        except ImportError:
            return False

    def open(self) -> bool:
        with self._lock:
            if self._cap is not None:
                return True
            try:
                import cv2
                self._cap = cv2.VideoCapture(self.device)
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                return self._cap.isOpened()
            except ImportError:
                return False

    def capture(self, path: str | None = None) -> str:
        if not self.open():
            return ""
        try:
            import cv2
            with self._lock:
                ret, frame = self._cap.read()
            if not ret:
                return ""
            target = Path(path) if path else SCREENSHOT_DIR / f"cam_{int(time.time() * 1000)}.jpg"
            cv2.imwrite(str(target), frame)
            return str(target)
        except Exception:
            return ""

    def release(self):
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None

    def stats(self) -> dict:
        return {"device": self.device, "opened": self._cap is not None,
                "available": self.available()}


class ImageGenerator:
    def __init__(self, engine: str = "auto", api_key: str = "",
                 base_url: str = "", model: str = ""):
        self.engine = engine
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def generate(self, prompt: str, size: str = "1024x1024",
                 path: str | None = None) -> str:
        if not self.available():
            return ""
        try:
            import urllib.request
            payload = json.dumps({"model": self.model, "prompt": prompt,
                                  "size": size}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url.rstrip('/')}/images/generations",
                data=payload, headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                })
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
            url = ""
            if isinstance(data, dict):
                items = data.get("data") or []
                if items and isinstance(items[0], dict):
                    url = items[0].get("url") or ""
            if not url:
                return ""
            target = Path(path) if path else SCREENSHOT_DIR / f"gen_{int(time.time() * 1000)}.png"
            with urllib.request.urlopen(url, timeout=60) as r:
                target.write_bytes(r.read())
            return str(target)
        except Exception:
            return ""


class VisionClient:
    def __init__(self, api_key: str = "", base_url: str = "",
                 model: str = "qwen-vl-max", max_side: int = 1280,
                 quality: int = 72):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_side = max_side
        self.quality = quality

    def available(self) -> bool:
        return bool(self.api_key and self.base_url)

    def describe(self, image_path: str, prompt: str = "描述这张图片") -> str:
        if not self.available():
            return ""
        p = screenshot_resize(image_path, self.max_side, self.quality)
        b64 = screenshot_base64(p)
        if not b64:
            return ""
        try:
            import urllib.request
            payload = json.dumps({
                "model": self.model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": b64}},
                    ],
                }],
                "max_tokens": 1024,
            }, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url.rstrip('/')}/chat/completions",
                data=payload, headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                })
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, dict):
                choices = data.get("choices") or []
                if choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message") or {}
                    return str(msg.get("content") or "").strip()
        except Exception:
            pass
        return ""


class VisionHub:
    def __init__(self, api_key: str = "", base_url: str = "",
                 model: str = "qwen-vl-max", image_api_key: str = "",
                 image_base_url: str = "", image_model: str = ""):
        self.camera = Camera()
        self.client = VisionClient(api_key=api_key, base_url=base_url, model=model)
        self.generator = ImageGenerator(api_key=image_api_key,
                                         base_url=image_base_url,
                                         model=image_model)
        self.last_screenshot = ""
        self.last_description = ""
        self._lock = threading.RLock()

    def see_screen(self, prompt: str = "描述一下当前屏幕") -> str:
        p = screenshot()
        if not p:
            return "截屏失败"
        with self._lock:
            self.last_screenshot = p
        text = self.client.describe(p, prompt)
        if text:
            with self._lock:
                self.last_description = text
            return text
        return "屏幕上没看到什么特别的"

    def see_camera(self, prompt: str = "描述一下摄像头画面") -> str:
        p = self.camera.capture()
        if not p:
            return "摄像头不可用"
        return self.client.describe(p, prompt) or "摄像头画面上没什么特别的"

    def generate_image(self, prompt: str) -> str:
        return self.generator.generate(prompt)

    def stats(self) -> dict:
        return {"screenshot_dir": str(SCREENSHOT_DIR),
                "last_screenshot": self.last_screenshot,
                "last_description": self.last_description[:200],
                "camera": self.camera.stats(),
                "vision_available": self.client.available(),
                "image_available": self.generator.available()}

    def close(self):
        self.camera.release()


def look_at_screen(prompt: str = "") -> str:
    hub = VisionHub()
    try:
        return hub.see_screen(prompt or "描述一下当前屏幕")
    finally:
        hub.close()
"""小凌 · 语音系统（TTS 合成 + ASR 识别 + SSML + 音色库 + 缓存 + 情感映射）"""
import asyncio
import hashlib
import io
import json
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import dataclass, asdict
from pathlib import Path

VOICES = [
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "lang": "zh-CN", "gender": "female", "style": "温柔"},
    {"id": "zh-CN-XiaoyiNeural", "name": "晓伊", "lang": "zh-CN", "gender": "female", "style": "活泼"},
    {"id": "zh-CN-XiaohanNeural", "name": "晓涵", "lang": "zh-CN", "gender": "female", "style": "知性"},
    {"id": "zh-CN-XiaomoNeural", "name": "晓墨", "lang": "zh-CN", "gender": "female", "style": "文艺"},
    {"id": "zh-CN-XiaoxuanNeural", "name": "晓萱", "lang": "zh-CN", "gender": "female", "style": "温柔"},
    {"id": "zh-CN-XiaoruiNeural", "name": "晓睿", "lang": "zh-CN", "gender": "female", "style": "成熟"},
    {"id": "zh-CN-XiaoshuangNeural", "name": "晓双", "lang": "zh-CN", "gender": "female", "style": "童声"},
    {"id": "zh-CN-XiaoyanNeural", "name": "晓颜", "lang": "zh-CN", "gender": "female", "style": "亲切"},
    {"id": "zh-CN-XiaozhenNeural", "name": "晓甄", "lang": "zh-CN", "gender": "female", "style": "新闻"},
    {"id": "zh-CN-YunxiNeural", "name": "云希", "lang": "zh-CN", "gender": "male", "style": "阳光"},
    {"id": "zh-CN-YunyangNeural", "name": "云扬", "lang": "zh-CN", "gender": "male", "style": "专业"},
    {"id": "zh-CN-YunjianNeural", "name": "云健", "lang": "zh-CN", "gender": "male", "style": "浑厚"},
    {"id": "zh-CN-YunfengNeural", "name": "云枫", "lang": "zh-CN", "gender": "male", "style": "低沉"},
    {"id": "zh-CN-YunhaoNeural", "name": "云皓", "lang": "zh-CN", "gender": "male", "style": "磁性"},
    {"id": "zh-CN-YunxiaNeural", "name": "云夏", "lang": "zh-CN", "gender": "male", "style": "少年"},
    {"id": "zh-CN-YunzeNeural", "name": "云泽", "lang": "zh-CN", "gender": "male", "style": "成熟"},
    {"id": "zh-CN-liaoning-XiaobeiNeural", "name": "晓北", "lang": "zh-CN-liaoning", "gender": "female", "style": "东北"},
    {"id": "zh-CN-shaanxi-XiaoniNeural", "name": "晓妮", "lang": "zh-CN-shaanxi", "gender": "female", "style": "陕西"},
    {"id": "zh-HK-HiuGaaiNeural", "name": "曉佳", "lang": "zh-HK", "gender": "female", "style": "粤语"},
    {"id": "zh-HK-HiuMaanNeural", "name": "曉曼", "lang": "zh-HK", "gender": "female", "style": "粤语"},
    {"id": "zh-HK-WanLungNeural", "name": "雲龍", "lang": "zh-HK", "gender": "male", "style": "粤语"},
    {"id": "zh-TW-HsiaoChenNeural", "name": "曉臻", "lang": "zh-TW", "gender": "female", "style": "台湾"},
    {"id": "zh-TW-HsiaoYuNeural", "name": "曉雨", "lang": "zh-TW", "gender": "female", "style": "台湾"},
    {"id": "zh-TW-YunJheNeural", "name": "雲哲", "lang": "zh-TW", "gender": "male", "style": "台湾"},
    {"id": "en-US-AriaNeural", "name": "Aria", "lang": "en-US", "gender": "female", "style": "narration"},
    {"id": "en-US-JennyNeural", "name": "Jenny", "lang": "en-US", "gender": "female", "style": "assistant"},
    {"id": "en-US-GuyNeural", "name": "Guy", "lang": "en-US", "gender": "male", "style": "news"},
    {"id": "ja-JP-NanamiNeural", "name": "ナナミ", "lang": "ja-JP", "gender": "female", "style": "casual"},
    {"id": "ja-JP-KeitaNeural", "name": "ケイタ", "lang": "ja-JP", "gender": "male", "style": "casual"},
    {"id": "ko-KR-SunHiNeural", "name": "선히", "lang": "ko-KR", "gender": "female", "style": "casual"},
]

ROLE_VOICE = {
    "小凌": "zh-CN-XiaoxiaoNeural",
    "Vivi": "zh-CN-XiaoyiNeural",
    "QuQu": "zh-CN-liaoning-XiaobeiNeural",
    "Imeris": "zh-CN-XiaomoNeural",
    "Yuki": "zh-CN-XiaohanNeural",
}

EMOTION_PARAMS = {
    "开心": ("cheerful", "+12%", "+8Hz", "+5%"),
    "happy": ("cheerful", "+12%", "+8Hz", "+5%"),
    "难过": ("sad", "-12%", "-6Hz", "-8%"),
    "sad": ("sad", "-12%", "-6Hz", "-8%"),
    "生气": ("angry", "+8%", "+4Hz", "+10%"),
    "angry": ("angry", "+8%", "+4Hz", "+10%"),
    "害怕": ("fearful", "+15%", "+10Hz", "-5%"),
    "惊讶": ("excited", "+10%", "+12Hz", "+8%"),
    "兴奋": ("excited", "+15%", "+10Hz", "+8%"),
    "害羞": ("gentle", "-5%", "+4Hz", "-3%"),
    "平静": ("calm", "+0%", "+0Hz", "+0%"),
    "calm": ("calm", "+0%", "+0Hz", "+0%"),
}

LANG_HINTS = {
    "zh": re.compile(r"[\u4e00-\u9fff]"),
    "ja": re.compile(r"[\u3040-\u30ff]"),
    "ko": re.compile(r"[\uac00-\ud7af]"),
    "en": re.compile(r"[A-Za-z]"),
}


@dataclass
class TTSResult:
    ok: bool = False
    data: bytes = b""
    voice: str = ""
    cached: bool = False
    elapsed_ms: float = 0.0
    error: str = ""

    def __bool__(self):
        return self.ok and bool(self.data)

    def to_dict(self):
        return {"ok": self.ok, "voice": self.voice, "bytes": len(self.data),
                "cached": self.cached, "elapsed_ms": self.elapsed_ms, "error": self.error}


def _run_async(coro_func):
    box = {"value": b"", "error": None}

    def _worker():
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            box["value"] = loop.run_until_complete(coro_func())
        except Exception as e:
            box["error"] = e
        finally:
            try:
                loop.close()
            except Exception:
                pass

    th = threading.Thread(target=_worker, daemon=True)
    th.start()
    th.join()
    if box["error"]:
        raise box["error"]
    return box["value"]


def get_voice(character: str) -> str:
    return ROLE_VOICE.get(character, "zh-CN-XiaoxiaoNeural")


def detect_lang(text: str) -> str:
    if not text:
        return "zh"
    for lang in ("ja", "ko", "zh", "en"):
        if len(LANG_HINTS[lang].findall(text)) >= max(1, len(text) // 8):
            return lang
    return "zh"


def pick_voice(lang: str, gender: str = "female") -> str:
    for v in VOICES:
        if v["lang"].startswith(lang) and v["gender"] == gender:
            return v["id"]
    for v in VOICES:
        if v["lang"].startswith(lang):
            return v["id"]
    return "zh-CN-XiaoxiaoNeural"


def voice_meta(vid: str) -> dict:
    for v in VOICES:
        if v["id"] == vid:
            return dict(v)
    return {"id": vid, "name": vid.split("-")[-1].replace("Neural", ""),
            "lang": "unknown", "gender": "unknown", "style": ""}


def list_voices(lang: str = "") -> list:
    return list(VOICES) if not lang else [v for v in VOICES if v["lang"].startswith(lang)]


def list_characters() -> list:
    return [{"character": k, "voice": v, "meta": voice_meta(v)} for k, v in ROLE_VOICE.items()]


class AudioCache:
    def __init__(self, root: str = None, max_entries: int = 512, max_bytes: int = 512 * 1024 * 1024):
        self.root = Path(root) if root else Path(tempfile.gettempdir()) / "xl_tts_cache"
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries
        self.max_bytes = max_bytes

    def key(self, text: str, voice: str, rate: str = "", pitch: str = "", volume: str = "", style: str = "") -> str:
        raw = f"{voice}|{rate}|{pitch}|{volume}|{style}|{text.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def get(self, key: str):
        p = self.root / f"{key}.mp3"
        if not p.exists():
            return None
        try:
            return p.read_bytes()
        except OSError:
            return None

    def put(self, key: str, data: bytes) -> bool:
        try:
            (self.root / f"{key}.mp3").write_bytes(data)
            self._gc()
            return True
        except OSError:
            return False

    def _gc(self):
        try:
            files = sorted(self.root.glob("*.mp3"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            total = 0
            for i, f in enumerate(files):
                total += f.stat().st_size
                if i >= self.max_entries or total > self.max_bytes:
                    try:
                        f.unlink()
                    except OSError:
                        pass
        except OSError:
            pass

    def stats(self) -> dict:
        try:
            files = list(self.root.glob("*.mp3"))
            total = sum(f.stat().st_size for f in files)
            return {"entries": len(files), "bytes": total,
                    "mb": round(total / 1048576, 2), "dir": str(self.root)}
        except OSError:
            return {"entries": 0, "bytes": 0, "mb": 0.0, "dir": str(self.root)}

    def clear(self) -> int:
        n = 0
        try:
            for f in self.root.glob("*.mp3"):
                try:
                    f.unlink()
                    n += 1
                except OSError:
                    pass
        except OSError:
            pass
        return n


class SSMLBuilder:
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", lang: str = "zh-CN"):
        self.voice = voice
        self.lang = lang
        self.rate = "+0%"
        self.pitch = "+0Hz"
        self.volume = "+0%"
        self.style = ""
        self.degree = 1.0
        self.parts: list[str] = []

    def with_rate(self, v):
        self.rate = v
        return self

    def with_pitch(self, v):
        self.pitch = v
        return self

    def with_volume(self, v):
        self.volume = v
        return self

    def with_style(self, v, degree=1.0):
        self.style = v
        self.degree = degree
        return self

    def say(self, text: str):
        self.parts.append(self._esc(text))
        return self

    def pause(self, ms: int = 300):
        self.parts.append(f'<break time="{ms}ms"/>')
        return self

    def emphasize(self, text: str, level: str = "moderate"):
        self.parts.append(f'<emphasis level="{level}">{self._esc(text)}</emphasis>')
        return self

    def prosody(self, text: str, rate="", pitch="", volume=""):
        attrs = []
        if rate:
            attrs.append(f'rate="{rate}"')
        if pitch:
            attrs.append(f'pitch="{pitch}"')
        if volume:
            attrs.append(f'volume="{volume}"')
        self.parts.append(f'<prosody {" ".join(attrs)}>{self._esc(text)}</prosody>')
        return self

    def build(self) -> str:
        body = "".join(self.parts)
        inner = f'<prosody rate="{self.rate}" pitch="{self.pitch}" volume="{self.volume}">{body}</prosody>'
        if self.style:
            inner = f'<mstts:express-as style="{self.style}" styledegree="{self.degree}">{inner}</mstts:express-as>'
        return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
                f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{self.lang}">'
                f'<voice name="{self.voice}">{inner}</voice></speak>')

    @staticmethod
    def _esc(text: str) -> str:
        return (text.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


class TTS:
    def __init__(self, cache: AudioCache = None, cache_enabled: bool = True):
        self.cache = cache or AudioCache()
        self.cache_enabled = cache_enabled
        self.last_error = ""

    def synth(self, text: str, voice: str = None, rate: str = "+0%", pitch: str = "+0Hz",
              volume: str = "+0%", style: str = "", use_cache: bool = True) -> TTSResult:
        t0 = time.time()
        if not text or not text.strip():
            return TTSResult(error="empty text")
        voice = voice or "zh-CN-XiaoxiaoNeural"
        key = self.cache.key(text, voice, rate, pitch, volume, style)
        if use_cache and self.cache_enabled:
            cached = self.cache.get(key)
            if cached:
                return TTSResult(ok=True, data=cached, voice=voice, cached=True,
                                 elapsed_ms=round((time.time() - t0) * 1000, 1))
        try:
            import edge_tts
        except ImportError:
            self.last_error = "edge-tts not installed"
            return TTSResult(voice=voice, error=self.last_error)
        out = io.BytesIO()

        async def _gen():
            kwargs = {"rate": rate, "pitch": pitch, "volume": volume}
            if style:
                kwargs["style"] = style
            comm = edge_tts.Communicate(text, voice=voice, **kwargs)
            async for chunk in comm.stream():
                if chunk.get("type") == "audio":
                    out.write(chunk["data"])

        try:
            _run_async(_gen)
            data = out.getvalue()
            if use_cache and self.cache_enabled and data:
                self.cache.put(key, data)
            return TTSResult(ok=bool(data), data=data, voice=voice,
                             elapsed_ms=round((time.time() - t0) * 1000, 1))
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            return TTSResult(voice=voice, error=self.last_error,
                             elapsed_ms=round((time.time() - t0) * 1000, 1))

    def synth_ssml(self, ssml: str, voice: str = None, use_cache: bool = True) -> TTSResult:
        t0 = time.time()
        if not ssml or not ssml.strip():
            return TTSResult(error="empty ssml")
        voice = voice or "zh-CN-XiaoxiaoNeural"
        key = self.cache.key(ssml, voice, "ssml")
        if use_cache and self.cache_enabled:
            cached = self.cache.get(key)
            if cached:
                return TTSResult(ok=True, data=cached, voice=voice, cached=True,
                                 elapsed_ms=round((time.time() - t0) * 1000, 1))
        try:
            import edge_tts
        except ImportError:
            return TTSResult(voice=voice, error="edge-tts not installed")
        out = io.BytesIO()

        async def _gen():
            comm = edge_tts.Communicate(ssml, voice=voice)
            async for chunk in comm.stream():
                if chunk.get("type") == "audio":
                    out.write(chunk["data"])

        try:
            _run_async(_gen)
            data = out.getvalue()
            if use_cache and self.cache_enabled and data:
                self.cache.put(key, data)
            return TTSResult(ok=bool(data), data=data, voice=voice,
                             elapsed_ms=round((time.time() - t0) * 1000, 1))
        except Exception as e:
            return TTSResult(voice=voice, error=f"{type(e).__name__}: {e}",
                             elapsed_ms=round((time.time() - t0) * 1000, 1))

    def synth_emotion(self, text: str, character: str = "小凌", emotion: str = "平静",
                      use_cache: bool = True) -> TTSResult:
        voice = get_voice(character)
        style, rate, pitch, volume = EMOTION_PARAMS.get(emotion, EMOTION_PARAMS["平静"])
        return self.synth(text, voice, rate, pitch, volume, style, use_cache)

    def synth_to_file(self, text: str, path: str = None, voice: str = None,
                      rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> str:
        r = self.synth(text, voice, rate, pitch, volume)
        if not r.ok:
            return ""
        target = Path(path) if path else Path(tempfile.gettempdir()) / "xl_tts.mp3"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(r.data)
            return str(target)
        except OSError:
            return ""

    def synth_batch(self, items, voice: str = None, rate: str = "+0%",
                    pitch: str = "+0Hz", volume: str = "+0%", parallel: int = 4) -> list:
        items = list(items)
        if not items:
            return []
        if parallel <= 1:
            return [self.synth(t if isinstance(t, str) else t.get("text", ""),
                               voice, rate, pitch, volume) for t in items]
        results = [None] * len(items)
        lock = threading.Lock()

        def _worker(start, chunk):
            for i, it in enumerate(chunk):
                text = it if isinstance(it, str) else it.get("text", "")
                r = self.synth(text, voice, rate, pitch, volume)
                with lock:
                    results[start + i] = r

        threads = []
        step = max(1, len(items) // parallel + (1 if len(items) % parallel else 0))
        for i in range(0, len(items), step):
            t = threading.Thread(target=_worker, args=(i, items[i:i + step]))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        return [r for r in results if r is not None]

    def cache_stats(self) -> dict:
        return self.cache.stats()

    def cache_clear(self) -> int:
        return self.cache.clear()

    def set_cache(self, on: bool):
        self.cache_enabled = bool(on)


class ASR:
    def __init__(self, engine: str = "whisper", model_size: str = "base", language: str = "zh"):
        self.engine = engine
        self.model_size = model_size
        self.language = language
        self._model = None
        self._lock = threading.Lock()

    def available(self) -> bool:
        try:
            import whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def record(self, seconds: float = 5.0, sample_rate: int = 16000) -> str:
        try:
            import pyaudio
        except ImportError:
            return ""
        path = Path(tempfile.gettempdir()) / f"xl_rec_{int(time.time() * 1000)}.wav"
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate,
                            input=True, frames_per_buffer=1024)
            frames = [stream.read(1024, exception_on_overflow=False)
                      for _ in range(int(sample_rate / 1024 * seconds))]
            stream.stop_stream()
            stream.close()
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                w.setframerate(sample_rate)
                w.writeframes(b"".join(frames))
            return str(path)
        except Exception:
            return ""
        finally:
            try:
                p.terminate()
            except Exception:
                pass

    def _load(self) -> bool:
        if self._model is not None:
            return True
        with self._lock:
            if self._model is not None:
                return True
            try:
                import whisper
                self._model = whisper.load_model(self.model_size)
                return True
            except Exception:
                return False

    def transcribe(self, path: str) -> str:
        if not path or not Path(path).exists():
            return ""
        if not self._load():
            return ""
        try:
            result = self._model.transcribe(path, language=self.language, fp16=False)
            return (result.get("text") or "").strip()
        except Exception:
            return ""

    def listen(self, seconds: float = 5.0) -> str:
        path = self.record(seconds)
        if not path:
            return ""
        try:
            return self.transcribe(path)
        finally:
            try:
                Path(path).unlink()
            except OSError:
                pass

    def transcribe_pcm(self, pcm: bytes, sample_rate: int = 16000) -> str:
        if not pcm:
            return ""
        tmp = Path(tempfile.gettempdir()) / f"xl_pcm_{int(time.time() * 1000)}.wav"
        try:
            with wave.open(str(tmp), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                w.writeframes(pcm)
            return self.transcribe(str(tmp))
        except Exception:
            return ""
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass


class AudioConverter:
    @staticmethod
    def available() -> bool:
        return bool(shutil.which("ffmpeg"))

    @staticmethod
    def convert(src: str, dst: str, fmt: str = "wav", sample_rate: int = 16000,
                channels: int = 1) -> bool:
        if not AudioConverter.available():
            return False
        cmd = ["ffmpeg", "-y", "-i", src, "-ar", str(sample_rate),
               "-ac", str(channels), "-f", fmt, dst]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=120)
            return r.returncode == 0 and Path(dst).exists()
        except (subprocess.SubprocessError, OSError):
            return False

    @staticmethod
    def mp3_to_pcm(mp3_path: str, sample_rate: int = 16000) -> bytes:
        if not AudioConverter.available():
            return b""
        tmp = tempfile.mktemp(suffix=".wav")
        try:
            if not AudioConverter.convert(mp3_path, tmp, "wav", sample_rate, 1):
                return b""
            with wave.open(tmp, "rb") as w:
                return w.readframes(w.getnframes())
        except Exception:
            return b""
        finally:
            try:
                if Path(tmp).exists():
                    Path(tmp).unlink()
            except OSError:
                pass

    @staticmethod
    def duration(path: str) -> float:
        if not AudioConverter.available():
            return 0.0
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of",
                                "default=noprint_wrappers=1:nokey=1", path],
                               capture_output=True, timeout=10, text=True)
            return float(r.stdout.strip() or 0)
        except Exception:
            return 0.0


class VoiceEngine:
    def __init__(self, character: str = "小凌", emotion: str = "平静",
                 cache_dir: str = None, asr_model: str = "base"):
        self.character = character
        self.emotion = emotion
        self.tts = TTS(cache=AudioCache(cache_dir) if cache_dir else None)
        self.asr = ASR(model_size=asr_model)
        self.history: list[dict] = []
        self._lock = threading.Lock()

    def set_character(self, name: str):
        self.character = name

    def set_emotion(self, emotion: str):
        self.emotion = emotion

    def say(self, text: str, character: str = None, emotion: str = None) -> dict:
        ch = character or self.character
        em = emotion or self.emotion
        r = self.tts.synth_emotion(text, ch, em)
        self.history.append({"kind": "tts", "text": text, "voice": r.voice,
                             "cached": r.cached, "ok": r.ok, "at": time.time()})
        if len(self.history) > 500:
            self.history = self.history[-300:]
        return r.to_dict()

    def say_bytes(self, text: str) -> bytes:
        r = self.tts.synth_emotion(text, self.character, self.emotion)
        return r.data if r.ok else b""

    def say_file(self, text: str, path: str = None) -> str:
        r = self.tts.synth_emotion(text, self.character, self.emotion)
        if not r.ok:
            return ""
        target = Path(path) if path else Path(tempfile.gettempdir()) / "xl_tts.mp3"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(r.data)
            return str(target)
        except OSError:
            return ""

    def say_ssml(self, ssml: str) -> dict:
        r = self.tts.synth_ssml(ssml)
        self.history.append({"kind": "ssml", "voice": r.voice, "ok": r.ok, "at": time.time()})
        return r.to_dict()

    def listen(self, seconds: float = 5.0) -> str:
        text = self.asr.listen(seconds)
        self.history.append({"kind": "asr", "text": text, "at": time.time()})
        return text

    def transcribe_file(self, path: str) -> str:
        return self.asr.transcribe(path)

    def stats(self) -> dict:
        tts_n = sum(1 for h in self.history if h["kind"] == "tts")
        asr_n = sum(1 for h in self.history if h["kind"] == "asr")
        hit_n = sum(1 for h in self.history if h["kind"] == "tts" and h.get("cached"))
        return {"character": self.character, "emotion": self.emotion,
                "voice": get_voice(self.character),
                "tts_calls": tts_n, "asr_calls": asr_n, "cache_hits": hit_n,
                "cache": self.tts.cache_stats(),
                "asr_available": self.asr.available(),
                "ffmpeg": AudioConverter.available()}

    def clear_history(self):
        self.history.clear()

    def close(self):
        try:
            self.tts.cache.clear()
        except Exception:
            pass


def synthesize(text: str, voice: str = None, rate: str = "+0%",
               pitch: str = "+0Hz", volume: str = "+0%") -> bytes:
    r = TTS().synth(text, voice, rate, pitch, volume)
    return r.data if r.ok else b""


def synthesize_character(text: str, character: str = "小凌", emotion: str = "平静") -> bytes:
    r = TTS().synth_emotion(text, character, emotion)
    return r.data if r.ok else b""


def synthesize_ssml(ssml: str, voice: str = None) -> bytes:
    r = TTS().synth_ssml(ssml, voice)
    return r.data if r.ok else b""


def synthesize_file(text: str, path: str = None, voice: str = None) -> str:
    return TTS().synth_to_file(text, path, voice)


def transcribe(path: str, language: str = "zh") -> str:
    return ASR(language=language).transcribe(path)


def record(seconds: float = 5.0) -> str:
    return ASR().record(seconds)


def listen(seconds: float = 5.0, language: str = "zh") -> str:
    return ASR(language=language).listen(seconds)


def build_ssml(parts, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%",
               pitch: str = "+0Hz", volume: str = "+0%", style: str = "") -> str:
    b = SSMLBuilder(voice).with_rate(rate).with_pitch(pitch).with_volume(volume)
    if style:
        b.with_style(style)
    for p in parts:
        if isinstance(p, str):
            b.say(p)
        elif isinstance(p, dict):
            kind = p.get("kind")
            if kind == "pause":
                b.pause(p.get("ms", 300))
            elif kind == "em":
                b.emphasize(p.get("text", ""), p.get("level", "moderate"))
            elif kind == "prosody":
                b.prosody(p.get("text", ""), p.get("rate", ""),
                          p.get("pitch", ""), p.get("volume", ""))
    return b.build()


def selftest() -> dict:
    out = {"edge_tts": False, "ffmpeg": AudioConverter.available(),
           "pyaudio": False, "whisper": False, "voices": len(VOICES)}
    for mod, key in (("edge_tts", "edge_tts"), ("pyaudio", "pyaudio"), ("whisper", "whisper")):
        try:
            __import__(mod)
            out[key] = True
        except ImportError:
            pass
    return out