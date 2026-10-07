"""小凌 · 项目上下文收集（ProjectContext）
==========================================

扫描项目根目录，统计代码文件数量 / 总行数 / 语言分布，并读取 README：
  * 跳过 .git / build / __pycache__ / .dart_tool / node_modules / .idea /
    venv / .venv / resources/models / resources/sounds 等目录
  * 统计每个代码文件的行数与语言
  * files 最多返回 200 个（按行数降序）
  * 读取 README.md 前 2000 字符
"""
from __future__ import annotations

import os

# 复用 fileops 的扩展名 -> 语言映射
try:
    from .fileops import _EXT_LANG
except Exception:  # pragma: no cover
    _EXT_LANG = {".py": "python", ".js": "javascript", ".ts": "typescript"}

# 需要整体跳过的目录名
_SKIP_DIRS = {
    ".git", "build", "__pycache__", ".dart_tool", "node_modules",
    ".idea", "venv", ".venv", "dist", ".next", ".gradle",
}
# 需要跳过的资源子目录（按路径片段匹配）
_SKIP_PATH_PARTS = {"resources"}
_SKIP_PATH_NAMES = {"models", "sounds"}

_CODE_EXTS = set(_EXT_LANG.keys()) | {
    ".kt", ".swift", ".rb", ".php", ".lua", ".rs", ".go", ".c",
    ".h", ".cpp", ".hpp", ".java", ".scala", ".r", ".m", ".mm",
}

_MAX_FILES = 200
_MAX_README_CHARS = 2000
_MAX_SCAN_BYTES = 512 * 1024  # 统计行数时跳过超过 512KB 的文件


def _lang_of(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _EXT_LANG.get(ext, "")


class ProjectContext:
    """收集项目结构与代码统计信息。"""

    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(os.path.expanduser(str(root_path)))

    def _should_skip_dir(self, dirpath: str, dirname: str) -> bool:
        if dirname in _SKIP_DIRS:
            return True
        # resources/models, resources/sounds
        parts = dirpath.replace("\\", "/").split("/")
        if "resources" in parts and dirname in _SKIP_PATH_NAMES:
            return True
        return False

    def collect(self) -> dict:
        """扫描项目并返回上下文摘要。任何异常都不抛出，返回空摘要。"""
        result = {
            "root_path": self.root_path,
            "project_name": os.path.basename(self.root_path.rstrip(os.sep)) or self.root_path,
            "files": [],
            "total_files": 0,
            "total_lines": 0,
            "languages": [],
            "readme": "",
        }
        if not os.path.isdir(self.root_path):
            return result
        file_entries = []
        lang_set = set()
        total_lines = 0
        total_files = 0
        try:
            for dirpath, dirnames, filenames in os.walk(self.root_path):
                # 原地过滤待遍历子目录
                dirnames[:] = [d for d in dirnames
                               if not self._should_skip_dir(dirpath, d)]
                for fn in filenames:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext not in _CODE_EXTS:
                        continue
                    full = os.path.join(dirpath, fn)
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        continue
                    if size > _MAX_SCAN_BYTES:
                        continue
                    rel = os.path.relpath(full, self.root_path)
                    lang = _lang_of(full) or "text"
                    try:
                        with open(full, "r", encoding="utf-8", errors="ignore") as f:
                            lines = sum(1 for _ in f)
                    except OSError:
                        lines = 0
                    total_files += 1
                    total_lines += lines
                    lang_set.add(lang)
                    file_entries.append({"path": rel, "language": lang,
                                         "lines": lines})
        except Exception as e:  # noqa: BLE001
            print(f"  [Context] collect 扫描异常：{type(e).__name__}: {e}")

        # 按行数降序，最多 200 个
        file_entries.sort(key=lambda x: x["lines"], reverse=True)
        result["files"] = file_entries[:_MAX_FILES]
        result["total_files"] = total_files
        result["total_lines"] = total_lines
        result["languages"] = sorted(lang_set)

        # 读取 README
        for name in ("README.md", "README.MD", "readme.md", "README"):
            rp = os.path.join(self.root_path, name)
            if os.path.isfile(rp):
                try:
                    with open(rp, "r", encoding="utf-8", errors="ignore") as f:
                        result["readme"] = f.read(_MAX_README_CHARS)
                except OSError:
                    result["readme"] = ""
                break
        return result
