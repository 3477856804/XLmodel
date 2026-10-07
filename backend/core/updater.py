"""小凌 · 更新检查（GitHub Release API + 多镜像 + 缓存 + 跳过版本）

从原 config.py 拆分而来。config.py 通过再导出保持向后兼容：
    from core.config import UpdateChecker, UpdateInfo, UpdateAsset   # 仍然可用

注意：本模块刻意不在模块顶层 `from .config import DATA_DIR`，数据目录在运行时
惰性解析，以避免与 config.py 的再导出形成循环导入。
"""
import json
import threading
import time
from datetime import datetime

REPO = "3477856804/XLmodel-release"
CURRENT_VERSION = "0.0.1"
CACHE_TTL = 1800.0
TIMEOUT = 6.0
MIRRORS = (
    f"https://api.github.com/repos/{REPO}/releases/latest",
    f"https://ghfast.top/https://api.github.com/repos/{REPO}/releases/latest",
    f"https://ghproxy.net/https://api.github.com/repos/{REPO}/releases/latest",
)


def _data_dir():
    """运行时惰性解析数据目录（避免与 config.py 循环导入）。"""
    try:
        from .config import DATA_DIR
        return DATA_DIR
    except Exception:
        import tempfile
        from pathlib import Path
        return Path(tempfile.gettempdir()) / "xiaoling_data"


def _skip_path():
    return _data_dir() / "update_skip.json"


def _cache_path():
    return _data_dir() / "update_cache.json"


class UpdateInfo:
    def __init__(self, has_update: bool = False, latest: str = "", current: str = "",
                 tag: str = "", name: str = "", body: str = "", html_url: str = "",
                 published_at: str = "", prerelease: bool = False, draft: bool = False,
                 size_mb: float = 0.0, assets: list | None = None,
                 source: str = "", message: str = ""):
        self.has_update = has_update
        self.latest = latest
        self.current = current
        self.tag = tag
        self.name = name
        self.body = body
        self.html_url = html_url
        self.published_at = published_at
        self.prerelease = prerelease
        self.draft = draft
        self.size_mb = size_mb
        self.assets = assets or []
        self.source = source
        self.message = message

    def to_dict(self) -> dict:
        return {
            "has_update": self.has_update, "latest": self.latest,
            "current": self.current, "tag": self.tag, "name": self.name,
            "body": self.body, "html_url": self.html_url,
            "published_at": self.published_at, "prerelease": self.prerelease,
            "draft": self.draft, "size_mb": round(self.size_mb, 2),
            "assets": self.assets, "source": self.source,
            "message": self.message,
        }

    def changelog_lines(self) -> list:
        if not self.body:
            return []
        out = []
        for line in self.body.split("\n"):
            s = line.strip()
            if not s:
                continue
            s = s.lstrip("-*+ ").lstrip("#").strip()
            if s:
                out.append(s)
        return out


class UpdateAsset:
    def __init__(self, name: str = "", url: str = "", size_mb: float = 0.0,
                 platform: str = "other", recommended: bool = False):
        self.name = name
        self.url = url
        self.size_mb = size_mb
        self.platform = platform
        self.recommended = recommended

    def to_dict(self) -> dict:
        return {"name": self.name, "url": self.url,
                "size_mb": round(self.size_mb, 2),
                "platform": self.platform, "recommended": self.recommended}


def platform_of(name: str) -> str:
    n = (name or "").lower()
    if n.endswith(".exe") or "setup" in n or "windows" in n:
        return "windows"
    if n.endswith(".dmg") or "macos" in n or "mac" in n:
        return "macos"
    if n.endswith(".appimage") or n.endswith(".deb") or "linux" in n:
        return "linux"
    if n.endswith(".apk") or "android" in n:
        return "android"
    if n.endswith(".ipa") or "ios" in n:
        return "ios"
    if n.endswith(".zip"):
        return "zip"
    if n.endswith(".tar.gz") or n.endswith(".tgz"):
        return "tarball"
    return "other"


def is_recommended(name: str) -> bool:
    n = (name or "").lower()
    return (n.endswith(".exe") or "setup" in n or "installer" in n
            or n.endswith(".dmg") or n.endswith(".appimage"))


def normalize_version(tag: str) -> str:
    v = (tag or "").strip()
    if v[:1].lower() == "v":
        v = v[1:]
    return v


def is_newer(latest: str, current: str) -> bool:
    try:
        a = [int(x) for x in latest.split(".")]
        b = [int(x) for x in current.split(".")]
        n = max(len(a), len(b))
        for i in range(n):
            x = a[i] if i < len(a) else 0
            y = b[i] if i < len(b) else 0
            if x > y:
                return True
            if x < y:
                return False
    except (ValueError, AttributeError):
        pass
    return False


def source_label(url: str) -> str:
    if "ghfast.top" in url:
        return "ghfast"
    if "ghproxy.net" in url:
        return "ghproxy"
    if "api.github.com" in url:
        return "github"
    return "mirror"


def format_size(mb: float) -> str:
    if mb <= 0:
        return "—"
    if mb < 1:
        return f"{int(mb * 1024)} KB"
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb / 1024:.2f} GB"


def format_date(iso: str) -> str:
    if not iso:
        return "—"
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return d.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


class UpdateChecker:
    def __init__(self, repo: str = REPO, current_version: str = CURRENT_VERSION,
                 allow_prerelease: bool = False):
        self.repo = repo
        self.current = current_version
        self.allow_prerelease = allow_prerelease
        self._lock = threading.RLock()
        self._cache: UpdateInfo | None = None
        self._cache_at: float = 0.0
        self._skipped: str = ""
        self._load_skip()

    def _load_skip(self):
        try:
            p = _skip_path()
            if not p.exists():
                return
            data = json.loads(p.read_text(encoding="utf-8"))
            self._skipped = data.get("skip", "")
        except Exception:
            pass

    def _save_skip(self):
        try:
            p = _skip_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"skip": self._skipped,
                                     "updated_at": time.time()},
                                    ensure_ascii=False),
                         encoding="utf-8")
        except OSError:
            pass

    def skip_version(self, version: str):
        with self._lock:
            self._skipped = normalize_version(version)
            self._save_skip()

    def clear_skip(self):
        with self._lock:
            self._skipped = ""
            self._save_skip()

    @property
    def skipped(self) -> str:
        with self._lock:
            return self._skipped

    def invalidate(self):
        with self._lock:
            self._cache = None
            self._cache_at = 0.0

    def check(self) -> tuple:
        info = self.check_detailed()
        return (info.has_update, info.latest, info.message)

    def check_detailed(self, force: bool = False, use_cache: bool = True) -> UpdateInfo:
        with self._lock:
            if (not force and use_cache and self._cache is not None
                    and (time.time() - self._cache_at) < CACHE_TTL):
                return self._cache
        last_error = "unknown"
        for url in MIRRORS:
            info = self._try_mirror(url)
            if info is not None:
                with self._lock:
                    self._cache = info
                    self._cache_at = time.time()
                return info
            last_error = url
        return UpdateInfo(current=self.current,
                          message=f"检查失败：{last_error}")

    def _try_mirror(self, url: str) -> UpdateInfo | None:
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"XiaoLing-Updater/{self.current}",
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                if r.status != 200:
                    return None
                raw = json.loads(r.read().decode("utf-8"))
            if not isinstance(raw, dict):
                return None
            return self._parse(raw, url)
        except Exception:
            return None

    def _parse(self, raw: dict, source: str) -> UpdateInfo | None:
        tag = str(raw.get("tag_name") or "")
        latest = normalize_version(tag)
        if not latest:
            return None
        if raw.get("draft") is True:
            return None
        prerelease = bool(raw.get("prerelease"))
        if prerelease and not self.allow_prerelease:
            return None
        with self._lock:
            skipped = self._skipped
        has_update = is_newer(latest, self.current) and latest != skipped
        assets = []
        for a in (raw.get("assets") or []):
            if not isinstance(a, dict):
                continue
            name = str(a.get("name") or "")
            url = str(a.get("browser_download_url") or "")
            if not name or not url:
                continue
            size = float(a.get("size") or 0) / 1048576.0
            assets.append(UpdateAsset(name=name, url=url, size_mb=size,
                                       platform=platform_of(name),
                                       recommended=is_recommended(name)))
        assets.sort(key=lambda x: (not x.recommended, x.size_mb))
        total_size = sum(a.size_mb for a in assets)
        return UpdateInfo(
            has_update=has_update, latest=latest, current=self.current,
            tag=tag or f"v{latest}", name=str(raw.get("name") or ""),
            body=str(raw.get("body") or ""),
            html_url=str(raw.get("html_url") or ""),
            published_at=str(raw.get("published_at") or ""),
            prerelease=prerelease, draft=False, size_mb=total_size,
            assets=[a.to_dict() for a in assets],
            source=source_label(source),
            message=("发现新版本 v" + latest if has_update
                     else ("已跳过 v" + latest if latest == skipped else "已是最新版本")),
        )

    def pick_for_platform(self, info: UpdateInfo, platform: str) -> dict | None:
        for a in info.assets:
            if a.get("platform") == platform:
                return a
        return None

    def pick_recommended(self, info: UpdateInfo) -> dict | None:
        for a in info.assets:
            if a.get("recommended"):
                return a
        return info.assets[0] if info.assets else None

    def snapshot(self) -> dict:
        with self._lock:
            return {"current": self.current, "skipped": self._skipped,
                    "cached": self._cache.to_dict() if self._cache else None,
                    "cache_age": round(time.time() - self._cache_at, 1)
                    if self._cache_at else None}


def check_for_updates(current: str = CURRENT_VERSION) -> dict:
    checker = UpdateChecker(current_version=current)
    info = checker.check_detailed()
    return info.to_dict()


def changelog_lines(body: str) -> list:
    if not body:
        return []
    out = []
    for line in body.split("\n"):
        s = line.strip()
        if not s:
            continue
        s = s.lstrip("-*+ ").lstrip("#").strip()
        if s:
            out.append(s)
    return out
