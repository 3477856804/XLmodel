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