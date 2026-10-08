# -*- coding: utf-8 -*-
"""code_formatter 插件

按语言调用真实格式化工具：
  - .py          -> black（首选），不可用回退 autopep8
  - .dart        -> dart format
  - .js/.ts/.jsx/.tsx/.json/.css/.html -> prettier

核心红线：对应格式化工具不可用时，必须返回明确错误，绝不假装已格式化。
格式化默认写回文件，并返回 {changed, original_size, formatted_size, engine}。
"""
from __future__ import annotations

import os
import shutil
import subprocess

try:
    from core.plugin_system import PluginBase
except ImportError:
    from backend.core.plugin_system import PluginBase


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _fmt_python(path: str, original: str):
    """返回 (new_content, engine, error)。"""
    # 首选 black
    try:
        import black  # type: ignore
        try:
            mode = black.Mode()
            new = black.format_file_contents(original, fast=False, mode=mode)
            return new, "black", ""
        except black.NothingChanged:
            return original, "black", ""
        except Exception as e:
            return None, "", "black 格式化失败: {}: {}".format(type(e).__name__, e)
    except ImportError:
        pass
    # 回退 autopep8
    try:
        import autopep8  # type: ignore
        try:
            new = autopep8.fix_code(original)
            return new, "autopep8", ""
        except Exception as e:
            return None, "", "autopep8 格式化失败: {}: {}".format(type(e).__name__, e)
    except ImportError:
        return None, "", "Python 格式化工具不可用：未安装 black，也未安装 autopep8"


def _run_tool(cmd, cwd):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return False, "命令未找到: {}".format(cmd[0])
    except subprocess.TimeoutExpired:
        return False, "格式化超时"


def _fmt_dart(path: str, cwd: str):
    if not shutil.which("dart"):
        return None, "dart format 不可用：未安装 dart SDK"
    ok, out = _run_tool(["dart", "format", path], cwd)
    if not ok:
        return None, "dart format 失败: {}".format(out.strip())
    return _read(path), ""


def _fmt_prettier(path: str, cwd: str):
    # 优先本地 prettier，再 PATH 里的 prettier，最后 npx
    for cmd in (["prettier", "--write", path],
                ["npx", "--yes", "prettier", "--write", path]):
        ok, out = _run_tool(cmd, cwd)
        if ok:
            return _read(path), ""
        if cmd[0] == "npx" and ("not found" in out.lower() or "ENOENT" in out):
            continue
        # prettier 命令不存在时试下一种
        if cmd[0] == "prettier" and "命令未找到" in out:
            continue
        return None, "prettier 失败: {}".format(out.strip())
    return None, "prettier 不可用：未安装 prettier / npx"


class CodeFormatterPlugin(PluginBase):
    name = "code_formatter"
    version = "0.0.1"
    description = "代码格式化：Python(black/autopep8)、Dart(dart format)、JS/TS(prettier)"
    author = "xiaoling"
    category = "development"
    permissions = ["file:read", "file:write"]

    _PRETTIER_EXT = {".js", ".jsx", ".ts", ".tsx", ".json", ".css", ".scss",
                     ".html", ".vue", ".yaml", ".yml", ".md"}

    def init(self):
        self._tools = [
            {
                "name": "format_file",
                "description": "按文件类型调用真实格式化工具写回文件",
                "args_schema": {"file_path": "string"},
                "handler": self.format_file,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    def format_file(self, file_path: str = "") -> dict:
        try:
            if not file_path:
                return {"ok": False, "error": "缺少参数 file_path"}
            path = os.path.abspath(os.path.expanduser(str(file_path)))
            if not os.path.isfile(path):
                return {"ok": False, "error": "文件不存在: {}".format(path)}
            ext = os.path.splitext(path)[1].lower()
            cwd = os.path.dirname(path)
            try:
                original = _read(path)
            except OSError as e:
                return {"ok": False, "error": "读取文件失败: {}".format(e)}

            new, engine, err = None, "", ""
            if ext == ".py":
                new, engine, err = _fmt_python(path, original)
            elif ext == ".dart":
                new, err = _fmt_dart(path, cwd)
                engine = "dart format"
            elif ext in self._PRETTIER_EXT:
                new, err = _fmt_prettier(path, cwd)
                engine = "prettier"
            else:
                return {"ok": False,
                        "error": "不支持的文件类型 {}（支持 .py/.dart/.js/.ts/.json/.css/.html 等）".format(ext or "无扩展名")}

            if err:
                return {"ok": False, "file": path, "engine": engine, "error": err}
            if new is None:
                return {"ok": False, "file": path, "error": "格式化未产生结果（工具异常）"}

            changed = new != original
            if changed:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new)
                except OSError as e:
                    return {"ok": False, "error": "写回文件失败: {}".format(e)}
            return {"ok": True, "file": path, "engine": engine,
                    "changed": changed,
                    "original_size": len(original), "formatted_size": len(new)}
        except Exception as e:
            return {"ok": False, "error": "format_file 失败: {}: {}".format(type(e).__name__, e)}
