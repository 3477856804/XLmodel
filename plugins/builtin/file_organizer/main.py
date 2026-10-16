# -*- coding: utf-8 -*-
"""file_organizer 插件

文件整理助手（真实文件系统操作，不写假数据）：
  - organize_dir(path)        按扩展名把文件归类到子目录（移动，不删除）
  - find_large_files(path, min_size)  查找超过阈值的大文件
  - find_duplicates(path)     按大小+内容 MD5 查找重复文件
  - clean_temp(path)          列出临时文件；confirm=True 时才真正删除（默认 dry-run）

安全约定：
  * 遍历限制深度，避免误扫整个磁盘；
  * clean_temp 默认只报告不删除，删除只针对明确的临时扩展名；
  * 任何异常都被捕获并以 {ok: False, error: ...} 返回。
"""
from __future__ import annotations

import hashlib
import os

try:
    from core.plugin_system import PluginBase
except ImportError:
    from backend.core.plugin_system import PluginBase


# 扩展名 -> 分类目录
_CATEGORY = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"},
    "documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".ppt", ".pptx"},
    "spreadsheets": {".xls", ".xlsx", ".csv", ".ods"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "code": {".py", ".js", ".ts", ".html", ".css", ".json", ".java", ".c", ".cpp", ".go", ".rs"},
    "media": {".mp3", ".wav", ".flac", ".mp4", ".avi", ".mkv", ".mov"},
}

# 视为"临时文件"的扩展名 / 后缀
_TEMP_SUFFIX = {".tmp", ".temp", ".bak", ".old", "~", ".swp", ".swo"}


def _category_of(ext: str) -> str:
    ext = ext.lower()
    for cat, exts in _CATEGORY.items():
        if ext in exts:
            return cat
    return "others"


def _iter_files(path: str, max_depth: int = 6):
    """递归遍历文件，(root, dirs, files) 形式，限制深度。"""
    base = os.path.abspath(path)
    for dirpath, dirnames, filenames in os.walk(base):
        rel = os.path.relpath(dirpath, base)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= max_depth:
            dirnames[:] = []
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def _md5_of(file_path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


class FileOrganizerPlugin(PluginBase):
    name = "file_organizer"
    version = "0.0.1"
    description = "文件整理：按类型分类、查找大文件、查找重复文件、清理临时文件"
    author = "xiaoling"
    category = "tool"
    permissions = ["file:read", "file:write"]

    def init(self):
        self._tools = [
            {
                "name": "organize_dir",
                "description": "按文件类型把 path 下的文件移动到分类子目录",
                "args_schema": {"path": "string"},
                "handler": self.organize_dir,
            },
            {
                "name": "find_large_files",
                "description": "查找 path 下大于 min_size_bytes 的文件",
                "args_schema": {"path": "string", "min_size": "int"},
                "handler": self.find_large_files,
            },
            {
                "name": "find_duplicates",
                "description": "按大小+MD5 查找 path 下的重复文件",
                "args_schema": {"path": "string"},
                "handler": self.find_duplicates,
            },
            {
                "name": "clean_temp",
                "description": "列出临时文件（默认 dry-run）；confirm=True 时才删除",
                "args_schema": {"path": "string", "confirm": "bool?"},
                "handler": self.clean_temp,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    @staticmethod
    def _check_dir(path: str):
        if not path:
            return None, {"ok": False, "error": "缺少参数 path"}
        ap = os.path.abspath(os.path.expanduser(str(path)))
        if not os.path.isdir(ap):
            return None, {"ok": False, "error": "目录不存在: {}".format(ap)}
        return ap, None

    def organize_dir(self, path: str = "") -> dict:
        try:
            ap, err = self._check_dir(path)
            if err:
                return err
            moved = []
            skipped = []
            for fp in list(_iter_files(ap)):
                # 不处理已经在分类目录里的文件
                parts = set(fp[len(ap):].split(os.sep))
                if parts & set(_CATEGORY.keys()) | {"others"}:
                    continue
                ext = os.path.splitext(fp)[1]
                cat = _category_of(ext)
                target_dir = os.path.join(ap, cat)
                os.makedirs(target_dir, exist_ok=True)
                target = os.path.join(target_dir, os.path.basename(fp))
                if os.path.exists(target):
                    skipped.append(fp)
                    continue
                os.rename(fp, target)
                moved.append({"from": fp, "to": target, "category": cat})
            return {"ok": True, "dir": ap, "moved_count": len(moved),
                    "skipped_count": len(skipped), "moved": moved}
        except Exception as e:
            return {"ok": False, "error": "organize_dir 失败: {}: {}".format(type(e).__name__, e)}

    def find_large_files(self, path: str = "", min_size: int = 0) -> dict:
        try:
            ap, err = self._check_dir(path)
            if err:
                return err
            try:
                min_bytes = int(min_size)
            except (TypeError, ValueError):
                return {"ok": False, "error": "min_size 必须是整数字节数"}
            if min_bytes <= 0:
                min_bytes = 10 * 1024 * 1024  # 默认 10MB
            result = []
            for fp in _iter_files(ap):
                try:
                    size = os.path.getsize(fp)
                except OSError:
                    continue
                if size >= min_bytes:
                    result.append({"path": fp, "size": size,
                                  "size_mb": round(size / 1024 / 1024, 2)})
            result.sort(key=lambda x: x["size"], reverse=True)
            return {"ok": True, "min_size_bytes": min_bytes,
                    "count": len(result), "files": result}
        except Exception as e:
            return {"ok": False, "error": "find_large_files 失败: {}: {}".format(type(e).__name__, e)}

    def find_duplicates(self, path: str = "") -> dict:
        try:
            ap, err = self._check_dir(path)
            if err:
                return err
            # 第一遍按大小分组（只有大小相同才可能重复）
            by_size = {}
            for fp in _iter_files(ap):
                try:
                    size = os.path.getsize(fp)
                except OSError:
                    continue
                by_size.setdefault(size, []).append(fp)
            dup_groups = []
            for size, files in by_size.items():
                if size == 0 or len(files) < 2:
                    continue
                by_hash = {}
                for fp in files:
                    try:
                        digest = _md5_of(fp)
                    except OSError:
                        continue
                    by_hash.setdefault(digest, []).append(fp)
                for digest, group in by_hash.items():
                    if len(group) >= 2:
                        dup_groups.append({"size": size, "md5": digest,
                                           "files": group})
            wasted = sum(g["size"] * (len(g["files"]) - 1) for g in dup_groups)
            return {"ok": True, "groups": len(dup_groups),
                    "wasted_bytes": wasted, "duplicates": dup_groups}
        except Exception as e:
            return {"ok": False, "error": "find_duplicates 失败: {}: {}".format(type(e).__name__, e)}

    def clean_temp(self, path: str = "", confirm: bool = False) -> dict:
        try:
            ap, err = self._check_dir(path)
            if err:
                return err
            targets = []
            for fp in _iter_files(ap):
                base = os.path.basename(fp)
                ext = os.path.splitext(fp)[1]
                if ext.lower() in _TEMP_SUFFIX or base.endswith("~") or base.endswith(".swp"):
                    try:
                        size = os.path.getsize(fp)
                    except OSError:
                        size = 0
                    targets.append({"path": fp, "size": size})
            if not confirm:
                return {"ok": True, "dry_run": True, "count": len(targets),
                        "total_bytes": sum(t["size"] for t in targets),
                        "files": targets,
                        "note": "dry-run：未删除任何文件。传 confirm=True 才会删除"}
            removed, failed = [], []
            for t in targets:
                try:
                    os.remove(t["path"])
                    removed.append(t["path"])
                except OSError as e:
                    failed.append({"path": t["path"], "error": str(e)})
            return {"ok": True, "dry_run": False, "removed": len(removed),
                    "failed": failed, "freed_bytes": sum(t["size"] for t in targets)}
        except Exception as e:
            return {"ok": False, "error": "clean_temp 失败: {}: {}".format(type(e).__name__, e)}
