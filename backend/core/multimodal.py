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

# 二进制可用性缓存（避免重复检测）
_binary_cache = {}

def _can_run(binary: str) -> bool:
    """检测二进制是否可用（带缓存）。
    
    用于在调用 subprocess 前检查工具是否存在，避免在 iOS 等平台上直接崩溃。
    """
    if binary in _binary_cache:
        return _binary_cache[binary]
    
    import shutil
    available = shutil.which(binary) is not None
    _binary_cache[binary] = available
    return available

def _get_platform() -> str:
    """获取当前平台标识。"""
    import sys
    plat = sys.platform
    if plat in ('iphone', 'ipados'):
        return 'ios'
    elif plat == 'darwin':
        return 'macos'
    elif plat.startswith('linux'):
        return 'linux'
    elif plat == 'win32':
        return 'windows'
    elif plat == 'android':
        return 'android'
    return plat


def screenshot(path: str | None = None, region: tuple | None = None) -> str:
    """截屏功能，支持多平台降级。
    
    优先级：
    1. PIL ImageGrab（跨平台）
    2. 平台原生工具（screencapture/scrot/import）
    3. 返回空字符串（不抛异常）
    """
    target = Path(path) if path else SCREENSHOT_DIR / f"shot_{int(time.time() * 1000)}.png"
    
    # 尝试 PIL ImageGrab（最通用）
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=region)
        img.save(str(target))
        return str(target)
    except ImportError:
        pass
    except Exception:
        pass  # PIL 失败，继续尝试其他方法
    
    # 平台检测与降级
    platform = _get_platform()
    
    if platform == 'ios':
        # iOS 不支持 subprocess，直接返回空
        return ""
    
    try:
        if platform == 'macos':
            if _can_run('screencapture'):
                subprocess.run(["screencapture", "-x", str(target)],
                             capture_output=True, timeout=10)
                if target.exists():
                    return str(target)
        elif platform == 'linux':
            # 尝试多个 Linux 截屏工具
            for cmd in (["gnome-screenshot", "-f", str(target)],
                       ["scrot", str(target)],
                       ["import", "-window", "root", str(target)]):
                binary = cmd[0]
                if _can_run(binary):
                    try:
                        r = subprocess.run(cmd, capture_output=True, timeout=10)
                        if r.returncode == 0 and target.exists():
                            return str(target)
                    except (OSError, subprocess.SubprocessError):
                        continue
        elif platform == 'windows':
            # Windows 可以用 PIL 的 ImageGrab，如果前面失败了就不再有其他方案
            pass
    except (OSError, subprocess.SubprocessError):
        pass
    
    # 所有方法都失败，返回空字符串（不抛异常）
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
        if not self.client.available():
            return "视觉模块未配置（缺少API key），无法识别屏幕内容"
        with self._lock:
            self.last_screenshot = p
        text = self.client.describe(p, prompt)
        if text:
            with self._lock:
                self.last_description = text
            return text
        return "视觉模块调用失败，未返回识别结果"

    def see_camera(self, prompt: str = "描述一下摄像头画面") -> str:
        p = self.camera.capture()
        if not p:
            return "摄像头不可用"
        if not self.client.available():
            return "视觉模块未配置（缺少API key），无法识别摄像头画面"
        return self.client.describe(p, prompt) or "视觉模块调用失败，未返回识别结果"

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


# ---- 文件类型检测 / 图片处理 / OCR 提取 ----
_EXT_MAP = {
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".bmp": "image", ".webp": "image",
    ".wav": "audio", ".mp3": "audio", ".ogg": "audio", ".flac": "audio",
    ".m4a": "audio",
    ".mp4": "video", ".mov": "video", ".mkv": "video", ".avi": "video",
    ".txt": "text", ".md": "text", ".json": "text", ".csv": "text",
    ".pdf": "pdf",
}

_MAGIC = [
    (b"\xff\xd8\xff", "image"), (b"\x89PNG", "image"), (b"GIF8", "image"),
    (b"ID3", "audio"), (b"RIFF", "audio"),
    (b"%PDF", "pdf"),
]


def detect_file_type(filepath: str) -> str:
    """根据扩展名 + magic bytes 检测文件类型，返回 image/audio/video/text/pdf/unknown。"""
    p = Path(filepath)
    ftype = _EXT_MAP.get(p.suffix.lower(), "unknown")
    try:
        with open(p, "rb") as f:
            head = f.read(16)
        for magic, t in _MAGIC:
            if head.startswith(magic):
                return t
    except OSError:
        pass
    return ftype


def resize_image(filepath: str, max_size: int = 1024) -> str:
    """用 PIL 把图片最长边缩到 max_size，保存到临时文件返回新路径。PIL 不可用返回原路径。"""
    try:
        from PIL import Image
    except ImportError:
        return filepath
    try:
        img = Image.open(filepath)
        if max(img.size) > max_size:
            r = max_size / max(img.size)
            img = img.resize((int(img.size[0] * r), int(img.size[1] * r)),
                             Image.LANCZOS)
        import tempfile
        out = Path(tempfile.gettempdir()) / f"xl_resized_{int(time.time()*1000)}.jpg"
        img.convert("RGB").save(str(out), "JPEG", quality=85)
        return str(out)
    except Exception:
        return filepath


def extract_text_from_image(filepath: str) -> str:
    """从图片提取文字：pytesseract 可用则 OCR，否则返回空字符串。"""
    try:
        import pytesseract
        from PIL import Image
        return str(pytesseract.image_to_string(Image.open(filepath))).strip()
    except Exception:
        return ""
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


# --------------------------------------------------------------------------
# 音色真实可用性探测（结果做磁盘缓存，避免每次启动都联网拖慢）
# --------------------------------------------------------------------------
# 背景：VOICES 里的 edge-tts 音色并非每个都真实可用（部分已被下架 / 区域
# 限制）。曾经一律默认可用，导致前端把不可用音色也当成可切换。这里做一次
# 轻量真实探测，把「真正失败」的标成不可用，但**默认保持可用**——
# 网络抖动 / 超时等不确定错误一律保守地当作可用，绝不让正常音色被误杀。
_VOICE_AVAIL: dict[str, bool] = {}
_VOICE_AVAIL_LOCK = threading.Lock()
_VOICE_AVAIL_PROBING = False
_VOICE_AVAIL_CACHE_LOADED = False


def _voice_avail_cache_path() -> Path:
    try:
        from core.config import DATA_DIR
        base = Path(DATA_DIR)
    except Exception:
        base = Path("data")
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return base / "voice_availability.json"


def load_voice_availability_cache() -> dict:
    """启动时加载上次探测结果（磁盘缓存），保证离线/冷启动也能立即返回。"""
    global _VOICE_AVAIL, _VOICE_AVAIL_CACHE_LOADED
    if _VOICE_AVAIL_CACHE_LOADED:
        return _VOICE_AVAIL
    p = _voice_avail_cache_path()
    try:
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8")) or {}
            if isinstance(d, dict):
                with _VOICE_AVAIL_LOCK:
                    for k, v in d.items():
                        if isinstance(k, str):
                            _VOICE_AVAIL[k] = bool(v)
    except Exception:
        pass
    _VOICE_AVAIL_CACHE_LOADED = True
    return _VOICE_AVAIL


def save_voice_availability_cache() -> None:
    p = _voice_avail_cache_path()
    try:
        with _VOICE_AVAIL_LOCK:
            data = dict(_VOICE_AVAIL)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def probe_voice_availability(voice_id: str) -> bool:
    """真实验证一个 edge-tts 音色是否可合成。

    返回 True 表示可用；只有**明确**判定不可用时才返回 False。
    网络抖动 / 超时等非确定错误一律保守返回 True，避免误杀正常音色。
    """
    try:
        import edge_tts  # noqa: PLC0415
    except Exception:
        return False  # edge-tts 都没装，必定不可用
    # NoAudioReceived 是否存在因版本而异：单独导入，失败就当作“不存在”，
    # 绝不让它的导入失败连累整个探针（否则会把所有音色误标成不可用）。
    try:
        from edge_tts.exceptions import NoAudioReceived  # noqa: PLC0415
    except Exception:
        NoAudioReceived = None
    try:
        import asyncio  # noqa: PLC0415

        async def _probe():
            comm = edge_tts.Communicate("你好。", voice_id)
            async for chunk in comm.stream():
                if (isinstance(chunk, dict) and chunk.get("type") == "audio"
                        and chunk.get("data")):
                    return True
            return False

        return bool(asyncio.run(asyncio.wait_for(_probe(), timeout=10)))
    except Exception as e:  # noqa: BLE001
        if NoAudioReceived is not None and isinstance(e, NoAudioReceived):
            # 音色本身无效（被下架 / 区域限制）→ 确认不可用
            return False
        # 网络 / 超时 / 其他不确定错误 → 保守保持可用
        return True


def _probe_all_voices() -> None:
    global _VOICE_AVAIL_PROBING
    with _VOICE_AVAIL_LOCK:
        if _VOICE_AVAIL_PROBING:
            return
        _VOICE_AVAIL_PROBING = True
    try:
        try:
            import edge_tts  # noqa: PLC0415
        except Exception:
            return
        for v in VOICES:
            vid = str(v.get("id", ""))
            if not vid:
                continue
            try:
                ok = probe_voice_availability(vid)
            except Exception:
                ok = True
            with _VOICE_AVAIL_LOCK:
                _VOICE_AVAIL[vid] = ok
            save_voice_availability_cache()
    finally:
        with _VOICE_AVAIL_LOCK:
            _VOICE_AVAIL_PROBING = False


def ensure_voice_availability_probed() -> None:
    """首次使用时在后台线程探测所有音色（不阻塞调用方），结果写盘缓存。"""
    if not VOICES:
        return
    load_voice_availability_cache()
    try:
        import edge_tts  # noqa: PLC0415
    except Exception:
        return
    t = threading.Thread(target=_probe_all_voices, daemon=True)
    t.start()


def get_voice_availability(voice_id: str, edge_ok: bool) -> bool:
    """对外查询某个音色的真实可用性。

    - edge-tts 没装 → 不可用；
    - 已探测过 → 用真实结果；
    - 还没探测（首屏冷启动）→ 默认可用，避免把正常音色误标灰。
    """
    if not edge_ok:
        return False
    vid = str(voice_id)
    with _VOICE_AVAIL_LOCK:
        if vid in _VOICE_AVAIL:
            return _VOICE_AVAIL[vid]
    return True


# 注：磁盘缓存的加载与后台探测都在首次使用时（ensure_voice_availability_probed）
# 触发，不放在模块导入阶段，避免导入期产生跨模块/磁盘副作用。

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
        self.default_voice = "zh-CN-XiaoxiaoNeural"

    def list_voices(self, lang: str = "") -> list:
        try:
            return list_voices(lang)
        except Exception as e:
            self.last_error = f"list_voices: {type(e).__name__}: {e}"
            return []

    def set_default_voice(self, voice_id: str) -> bool:
        try:
            v = (voice_id or "").strip()
            if not v:
                self.last_error = "set_default_voice: empty voice id"
                return False
            if not any(x["id"] == v for x in VOICES):
                self.last_error = f"set_default_voice: unknown voice {v}"
                return False
            self.default_voice = v
            return True
        except Exception as e:
            self.last_error = f"set_default_voice: {type(e).__name__}: {e}"
            return False

    def get_default_voice(self) -> str:
        return self.default_voice

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
        self.last_error = ""

    def _api_enabled(self) -> bool:
        """外部 API 是否可用于语音识别（设置 → API 配置 已启用且有端点）。"""
        try:
            try:
                from . import api_config as _api
            except Exception:                                    # noqa: BLE001
                from api_config import _api                      # type: ignore
            c = _api.cfg()
            return bool(c.get("enabled")) and bool(c.get("has_base"))
        except Exception:                                        # noqa: BLE001
            return False

    def available(self) -> bool:
        try:
            import whisper  # noqa: F401
            self.last_error = ""
            return True
        except ImportError:
            # whisper 没装不代表语音就不能用：只要配了外部 API，走 API 识别。
            if self._api_enabled():
                self.last_error = ""
                return True
            self.last_error = ("语音识别未配置：本机未装 whisper，且未启用外部 API。"
                               "可在「设置 → API 配置」填端点后直接用云端识别。")
            return False

    def status(self) -> dict:
        return {
            "engine": self.engine,
            "model_size": self.model_size,
            "language": self.language,
            "available": self.available(),
            "loaded": self._model is not None,
            "last_error": self.last_error,
        }

    def record(self, seconds: float = 5.0, sample_rate: int = 16000) -> str:
        try:
            import pyaudio
        except ImportError:
            self.last_error = "录音不可用（pyaudio 未安装）"
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
            self.last_error = ""
            return str(path)
        except Exception as e:
            self.last_error = f"录音失败：{type(e).__name__}: {e}"
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
                self.last_error = ""
                return True
            except Exception as e:
                self.last_error = f"whisper 模型加载失败：{type(e).__name__}: {e}"
                return False

    def transcribe(self, path: str) -> str:
        if not path or not Path(path).exists():
            self.last_error = f"音频文件不存在：{path}"
            return ""
        # 本地 whisper 优先；没装/加载失败时，若配了外部 API 就走云端识别，
        # 而不是直接放弃 —— 这样「语音不能用」只在两条路都不通时才成立。
        if self._load():
            try:
                result = self._model.transcribe(path, language=self.language,
                                                fp16=False)
                text = (result.get("text") or "").strip()
                self.last_error = "" if text else "未识别到语音内容"
                return text
            except Exception as e:
                self.last_error = f"语音识别失败：{type(e).__name__}: {e}"
                return ""
        if self._api_enabled():
            try:
                try:
                    from . import api_config as _api
                except Exception:                                # noqa: BLE001
                    from api_config import _api                  # type: ignore
                data = Path(path).read_bytes()
                r = _api.transcribe(data, filename=Path(path).name,
                                    language=self.language)
                if r.get("ok"):
                    self.last_error = ""
                    return str(r.get("text", "")).strip()
                self.last_error = f"云端语音识别失败：{r.get('error')}"
                return ""
            except Exception as e:
                self.last_error = f"云端语音识别异常：{type(e).__name__}: {e}"
                return ""
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

    def transcribe_bytes(self, data: bytes, suffix: str = ".wav") -> str:
        if not data:
            self.last_error = "音频数据为空"
            return ""
        tmp = Path(tempfile.gettempdir()) / f"xl_in_{int(time.time() * 1000)}{suffix}"
        try:
            tmp.write_bytes(data)
            return self.transcribe(str(tmp))
        except Exception as e:
            self.last_error = f"音频写入失败：{type(e).__name__}: {e}"
            return ""
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

    def transcribe_pcm(self, pcm: bytes, sample_rate: int = 16000) -> str:
        if not pcm:
            self.last_error = "PCM 数据为空"
            return ""
        tmp = Path(tempfile.gettempdir()) / f"xl_pcm_{int(time.time() * 1000)}.wav"
        try:
            with wave.open(str(tmp), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                w.writeframes(pcm)
            return self.transcribe(str(tmp))
        except Exception as e:
            self.last_error = f"PCM 转写失败：{type(e).__name__}: {e}"
            return ""
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass


class AudioConverter:
    """音频格式转换器，依赖 ffmpeg/ffprobe。
    
    在 iOS/Android 等移动端平台，ffmpeg 通常不可用，方法会返回空结果/False，
    不会抛异常。
    """
    @staticmethod
    def available() -> bool:
        """检查 ffmpeg 是否可用（带缓存）。"""
        return _can_run("ffmpeg")
    
    @staticmethod
    def probe_available() -> bool:
        """检查 ffprobe 是否可用（带缓存）。"""
        return _can_run("ffprobe")

    @staticmethod
    def convert(src: str, dst: str, fmt: str = "wav", sample_rate: int = 16000,
                channels: int = 1) -> bool:
        """转换音频格式。ffmpeg 不可用时返回 False。"""
        if not AudioConverter.available():
            return False
        # 移动端平台直接返回 False（ffmpeg 通常不在 PATH 中）
        if _get_platform() in ('ios', 'android'):
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
        """将 MP3 转换为 PCM 数据。ffmpeg 不可用时返回空 bytes。"""
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
        """获取音频时长（秒）。ffprobe 不可用时返回 0.0。"""
        if not AudioConverter.probe_available():
            return 0.0
        # 移动端平台直接返回 0.0（ffprobe 通常不在 PATH 中）
        if _get_platform() in ('ios', 'android'):
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

    def list_voices(self, lang: str = "") -> list:
        try:
            return list_voices(lang)
        except Exception as e:
            self.tts.last_error = f"list_voices: {type(e).__name__}: {e}"
            return []

    def set_voice(self, voice_name: str) -> bool:
        try:
            v = (voice_name or "").strip()
            if not v:
                self.tts.last_error = "set_voice: empty voice id"
                return False
            if not any(x["id"] == v for x in VOICES):
                self.tts.last_error = f"set_voice: unknown voice {v}"
                return False
            self.tts.set_default_voice(v)
            return True
        except Exception as e:
            self.tts.last_error = f"set_voice: {type(e).__name__}: {e}"
            return False

    def current_voice(self) -> str:
        try:
            return self.tts.get_default_voice()
        except Exception:
            return "zh-CN-XiaoxiaoNeural"

    def voice_status(self) -> dict:
        return {"tts": self.tts.last_error or "ok",
                "asr": self.asr.status(),
                "voices": len(VOICES)}

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