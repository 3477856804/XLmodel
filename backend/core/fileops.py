"""小凌 · 安全文件操作（FileManager）
==========================================

在项目根路径内提供受沙箱保护的文件读写与目录浏览：
  * list_dir(path)    -> 目录条目列表（目录在前、文件在后，名称排序）
  * read_file(path)   -> 文件内容 + 语言推断 + 行数 + 大小
  * write_file(path)  -> 写入 / 追加，自动创建父目录

所有路径经 _safe_path 解析后必须落在 root_path 之内（os.path.commonpath
校验），越界访问抛出 PermissionError，调用方可自行捕获。
"""
from __future__ import annotations

import os

# 扩展名 -> 语言（供编辑器高亮 / 统计使用）
_EXT_LANG = {
    ".py": "python",
    ".dart": "dart",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".md": "markdown",
    ".markdown": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".proto": "protobuf",
    ".css": "css",
    ".scss": "css",
    ".html": "html",
    ".htm": "html",
    ".xml": "xml",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".txt": "text",
}

_MAX_READ_BYTES = 1024 * 1024      # 1MB
_MAX_READ_LINES = 1000             # 超大文件最多读取行数


class FileManager:
    """受沙箱限制的文件操作管理器。"""

    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(os.path.expanduser(str(root_path)))

    # ------------------------------------------------------------ path safety
    def _safe_path(self, path: str) -> str:
        """解析相对 / 绝对路径，确保落在 root_path 内。越界抛 PermissionError。"""
        if not path:
            path = "."
        p = os.path.expanduser(str(path))
        if not os.path.isabs(p):
            p = os.path.join(self.root_path, p)
        p = os.path.abspath(p)
        try:
            common = os.path.commonpath([self.root_path, p])
        except ValueError:
            raise PermissionError(f"路径越界：{path}")
        if common != self.root_path:
            raise PermissionError(f"路径越界（不允许访问项目外）：{path}")
        return p

    # -------------------------------------------------------------- extension
    @staticmethod
    def _lang_of(path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        return _EXT_LANG.get(ext, "text")

    # ---------------------------------------------------------------- list_dir
    def list_dir(self, path: str = ".") -> dict:
        """列出目录内容。返回 {items, current_path, parent_path}。"""
        try:
            target = self._safe_path(path)
        except PermissionError as e:
            return {"items": [], "current_path": path,
                    "parent_path": "", "error": str(e)}
        if not os.path.isdir(target):
            return {"items": [], "current_path": target,
                    "parent_path": "", "error": "目录不存在"}
        items = []
        try:
            with os.scandir(target) as it:
                entries = list(it)
        except OSError as e:
            return {"items": [], "current_path": target,
                    "parent_path": "", "error": str(e)}

        for e in entries:
            try:
                is_dir = e.is_dir(follow_symlinks=False)
                stat = e.stat(follow_symlinks=False)
                ext = "" if is_dir else os.path.splitext(e.name)[1].lower()
                items.append({
                    "name": e.name,
                    "path": os.path.join(target, e.name),
                    "is_dir": is_dir,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "extension": ext,
                })
            except OSError:
                continue
        # 目录在前、文件在后，各自按名称排序
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        parent = os.path.dirname(target.rstrip(os.sep))
        try:
            parent = self._safe_path(parent) if parent else self.root_path
        except PermissionError:
            parent = self.root_path
        return {"items": items, "current_path": target,
                "parent_path": parent}

    # ---------------------------------------------------------------- read_file
    def read_file(self, path: str = "") -> dict:
        """读取文件内容。超大文件只读前 1000 行并标注 truncated。"""
        try:
            target = self._safe_path(path)
        except PermissionError as e:
            return {"path": path, "content": "", "language": "text",
                    "lines": 0, "size": 0, "error": str(e)}
        if not os.path.isfile(target):
            return {"path": target, "content": "", "language": "text",
                    "lines": 0, "size": 0, "error": "文件不存在"}
        try:
            size = os.path.getsize(target)
        except OSError:
            size = 0
        lang = self._lang_of(target)
        truncated = False
        try:
            if size > _MAX_READ_BYTES:
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= _MAX_READ_LINES:
                            truncated = True
                            break
                        lines.append(line)
                content = "".join(lines)
            else:
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
        except OSError as e:
            return {"path": target, "content": "", "language": lang,
                    "lines": 0, "size": size, "error": str(e)}
        n_lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        if truncated:
            content = content + f"\n...（文件超过 1MB，仅读取前 {_MAX_READ_LINES} 行）"
        return {"path": target, "content": content, "language": lang,
                "lines": n_lines, "size": size, "truncated": truncated}

    # ---------------------------------------------------------------- write_file
    def write_file(self, path: str, content: str = "", append: bool = False) -> bool:
        """写入（或追加）文件，自动创建父目录。成功返回 True。"""
        try:
            target = self._safe_path(path)
        except PermissionError:
            return False
        try:
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            mode = "a" if append else "w"
            with open(target, mode, encoding="utf-8") as f:
                f.write(content or "")
            return True
        except OSError as e:
            print(f"  [FileOps] write_file 失败：{type(e).__name__}: {e}")
            return False
