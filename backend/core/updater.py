"""自动更新检查 - 检查新版本并下载更新"""
import json
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from .platform import Platform

UPDATE_CHECK_URL = "https://xiaoling-4o6.pages.dev/update/check.json"


@dataclass
class UpdateInfo:
    latest_version: str
    current_version: str
    has_update: bool
    changelog: list[str]
    download_url: str
    sha256: str
    size_mb: float


class UpdateChecker:
    """自动更新检查器"""

    def __init__(self, current_version: str = "0.0.3"):
        self.current_version = current_version
        self.update_info: Optional[UpdateInfo] = None

    def check_for_updates(self) -> Optional[UpdateInfo]:
        """检查是否有新版本"""
        try:
            response = requests.get(UPDATE_CHECK_URL, timeout=10)
            if response.status_code != 200:
                return None

            data = response.json()
            latest = data.get("latest", "0.0.0")

            # 简单版本比较
            if self._compare_version(latest, self.current_version) <= 0:
                return None

            # 获取当前平台的下载地址
            platform_key = self._get_platform_key()
            platform_info = data.get(platform_key, {})

            self.update_info = UpdateInfo(
                latest_version=latest,
                current_version=self.current_version,
                has_update=True,
                changelog=data.get("changelog", []),
                download_url=platform_info.get("url", ""),
                sha256=platform_info.get("sha256", ""),
                size_mb=platform_info.get("size_mb", 0),
            )
            return self.update_info

        except Exception:
            return None

    def _get_platform_key(self) -> str:
        p = Platform.current()
        if p == Platform.WIN:
            return "windows"
        elif p == Platform.MAC:
            return "macos"
        else:
            return "linux"

    def _compare_version(self, v1: str, v2: str) -> int:
        """比较版本号，返回 1 表示 v1 > v2"""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            for i in range(max(len(parts1), len(parts2))):
                p1 = parts1[i] if i < len(parts1) else 0
                p2 = parts2[i] if i < len(parts2) else 0
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            return 0
        except Exception:
            return 0

    def download_update(self, save_path: Path, progress_callback=None) -> bool:
        """下载更新包"""
        if not self.update_info or not self.update_info.download_url:
            return False

        try:
            response = requests.get(
                self.update_info.download_url,
                stream=True,
                timeout=30,
            )
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total > 0:
                            progress_callback(downloaded / total * 100)
            return True
        except Exception:
            return False
