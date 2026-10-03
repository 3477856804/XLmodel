"""模型商店 - 模型下载、管理、断点续传"""
import os
import hashlib
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable

from .platform import get_user_data_dir


# 下载源
DOWNLOAD_SOURCES = {
    "modelscope": {
        "name": "ModelScope (魔搭)",
        "base_url": "https://modelscope.cn/api/v1/models",
        "speed": "fast",
    },
    "hf_mirror": {
        "name": "HF Mirror",
        "base_url": "https://hf-mirror.com",
        "speed": "medium",
    },
}

# 默认主源
PRIMARY_SOURCE = "modelscope"


@dataclass
class DownloadTask:
    model_name: str
    url: str
    save_path: Path
    total_size: int = 0
    downloaded: int = 0
    progress: float = 0.0
    status: str = "pending"  # pending / downloading / paused / done / failed
    error: str = ""


class ModelStore:
    """模型商店管理"""

    def __init__(self):
        self.models_dir = get_user_data_dir() / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.downloads: dict[str, DownloadTask] = {}

    def list_installed(self) -> list[dict]:
        """列出已安装的模型"""
        result = []
        if not self.models_dir.exists():
            return result
        for item in self.models_dir.iterdir():
            if item.is_dir():
                size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                result.append({
                    "name": item.name,
                    "path": str(item),
                    "size_mb": size / (1024 * 1024),
                })
        return result

    def get_download_url(self, model_name: str, quant: str = "Q4_K_M") -> str:
        """获取模型下载 URL"""
        # ModelScope 格式
        return f"{DOWNLOAD_SOURCES[PRIMARY_SOURCE]['base_url']}/{model_name}/resolve/master/{quant}.gguf"

    def download_model(
        self,
        model_name: str,
        quant: str = "Q4_K_M",
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Path:
        """下载模型，支持断点续传"""
        url = self.get_download_url(model_name, quant)
        save_path = self.models_dir / f"{model_name}-{quant}.gguf"

        task = DownloadTask(
            model_name=model_name,
            url=url,
            save_path=save_path,
            status="downloading",
        )
        self.downloads[model_name] = task

        # 获取已下载大小（断点续传）
        resume_pos = save_path.stat().st_size if save_path.exists() else 0

        headers = {}
        if resume_pos > 0:
            headers["Range"] = f"bytes={resume_pos}-"

        try:
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            total = int(response.headers.get("content-length", 0)) + resume_pos
            task.total_size = total

            mode = "ab" if resume_pos > 0 else "wb"
            with open(save_path, mode) as f:
                downloaded = resume_pos
                for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        task.downloaded = downloaded
                        task.progress = (downloaded / total * 100) if total > 0 else 0
                        if progress_callback:
                            progress_callback(task.progress)

            task.status = "done"
            return save_path

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            raise

    def verify_sha256(self, file_path: Path, expected_hash: str) -> bool:
        """校验文件 SHA256"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest().lower() == expected_hash.lower()

    def delete_model(self, model_name: str) -> bool:
        """删除已安装的模型"""
        model_path = self.models_dir / model_name
        if model_path.exists():
            import shutil
            shutil.rmtree(model_path)
            return True
        return False

    def get_download_status(self, model_name: str) -> Optional[DownloadTask]:
        """获取下载进度"""
        return self.downloads.get(model_name)
