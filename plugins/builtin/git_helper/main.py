# -*- coding: utf-8 -*-
"""git_helper 插件

Git 操作助手，底层复用 backend/core/git_tool.py 的 GitTool（真实调用 git CLI）。
工具：
  - git_status()          查看工作区变更
  - git_commit(message)   暂存全部并提交
  - git_branch(name)      创建并切换到新分支
  - git_diff(file)        查看未暂存差异

git 命令不可用 / 不在仓库内时，返回明确错误，绝不伪造结果。
"""
from __future__ import annotations

try:
    from core.plugin_system import PluginBase
    from core.git_tool import GitTool
except ImportError:  # 兜底
    from backend.core.plugin_system import PluginBase
    from backend.core.git_tool import GitTool


class GitHelperPlugin(PluginBase):
    name = "git_helper"
    version = "0.0.1"
    description = "Git 操作助手：查看状态、提交、创建分支、查看 diff"
    author = "xiaoling"
    category = "development"
    permissions = ["file:read", "file:write"]

    def __init__(self, context=None, repo_path: str = "."):
        super().__init__(context)
        # 允许在测试里注入 repo_path；默认在当前目录操作 git
        self._repo_path = repo_path

    def init(self):
        self._tools = [
            {
                "name": "git_status",
                "description": "查看 Git 工作区变更状态",
                "args_schema": {"repo_path": "string?"},
                "handler": self.git_status,
            },
            {
                "name": "git_commit",
                "description": "暂存全部变更并提交，message 为提交信息",
                "args_schema": {"message": "string", "repo_path": "string?"},
                "handler": self.git_commit,
            },
            {
                "name": "git_branch",
                "description": "创建并切换到新分支 name",
                "args_schema": {"name": "string", "repo_path": "string?"},
                "handler": self.git_branch,
            },
            {
                "name": "git_diff",
                "description": "查看未暂存差异，可指定单个文件",
                "args_schema": {"file": "string?", "repo_path": "string?"},
                "handler": self.git_diff,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    def _tool(self, repo_path: str = "") -> GitTool:
        return GitTool(repo_path or self._repo_path or ".")

    def git_status(self, repo_path: str = "") -> dict:
        try:
            gt = self._tool(repo_path)
            r = gt.status()
            if not r.get("ok") and not r.get("files"):
                # status 的 ok 恒为 True；这里用 rev-parse 判定是否在仓库内
                root = gt.repo_root()
                if root == (repo_path or self._repo_path):
                    return {"ok": False, "error": "当前目录不是 Git 仓库，或 git 命令不可用"}
            return {"ok": True, "repo": gt.repo_root(),
                    "files": r.get("files", []), "raw": r.get("raw", "")}
        except Exception as e:
            return {"ok": False, "error": "git_status 失败: {}: {}".format(type(e).__name__, e)}

    def git_commit(self, message: str = "", repo_path: str = "") -> dict:
        try:
            if not message or not str(message).strip():
                return {"ok": False, "error": "缺少提交信息 message"}
            gt = self._tool(repo_path)
            r = gt.commit(str(message).strip())
            return {"ok": bool(r.get("ok")), "message": r.get("message", "")}
        except Exception as e:
            return {"ok": False, "error": "git_commit 失败: {}: {}".format(type(e).__name__, e)}

    def git_branch(self, name: str = "", repo_path: str = "") -> dict:
        """创建并切换到新分支（git checkout -b <name>）。"""
        try:
            if not name or not str(name).strip():
                return {"ok": False, "error": "缺少分支名 name"}
            gt = self._tool(repo_path)
            r = gt._run(["checkout", "-b", str(name).strip()])
            if not r.get("ok"):
                return {"ok": False,
                        "error": "创建分支失败: {}".format((r.get("stderr") or r.get("stdout")).strip())}
            return {"ok": True, "branch": str(name).strip(),
                    "message": (r.get("stdout") or r.get("stderr")).strip()}
        except Exception as e:
            return {"ok": False, "error": "git_branch 失败: {}: {}".format(type(e).__name__, e)}

    def git_diff(self, file: str = "", repo_path: str = "") -> dict:
        try:
            gt = self._tool(repo_path)
            out = gt.diff(str(file) if file else None)
            if out is None:
                out = ""
            return {"ok": True, "file": file or "", "diff": out,
                    "changed": bool(out.strip())}
        except Exception as e:
            return {"ok": False, "error": "git_diff 失败: {}: {}".format(type(e).__name__, e)}
