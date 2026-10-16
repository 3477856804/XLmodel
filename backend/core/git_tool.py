import shlex
import subprocess

# GitTool 的所有命令都通过 exec_gate 执行。exec_gate 内部是 shell=True 的
# 字符串命令（bash -c / cmd /c），所以**每个来自用户输入的 argv 都必须
# shlex.quote**：提交信息里的空格、中文、`;`、`|`、`$`、反引号、引号都会被
# shell 二次解析。此前这里用 `" ".join(args)` 直接拼，`git commit -m "x; 恶意命令"`
# 会被拆成两条命令 —— 这是真实的命令注入面，不是理论风险。
#
# permission 三档（默认 'default'，绝不自动升权）：
#   readonly : 只放行 status/diff/log/branches 这类只读命令
#   default  : 沙箱 workspace 内可读写
#   full     : 前端**显式选了用户自己的某个仓库路径**时用；这是用户主动动作，
#              且仍走 exec_gate（黑名单 / 联网判定 / 审批 / 审计都在），
#              只是不再叠加路径沙箱。不会因为传了 repo 参数就悄悄升权。


class GitTool:
    def __init__(self, repo_path=".", permission: str = "default"):
        self.repo_path = repo_path or "."
        if permission not in ("readonly", "default", "full"):
            permission = "default"
        self.permission = permission

    def _run(self, args):
        try:
            from .exec_gate import execute as exec_gate
            cmd = "git " + " ".join(shlex.quote(str(a)) for a in args)
            result = exec_gate(cmd, permission=self.permission, timeout=30,
                               cwd=self.repo_path)
            return {
                "ok": result.get("ok", False),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "code": result.get("code", -1),
                "isolation": result.get("isolation", "unknown"),
                "blocked_reason": result.get("blocked_reason", "") or "",
                "error": result.get("error", "") or "",
            }
        except ImportError:
            # exec_gate 不可用时降级：走 subprocess 的 argv 列表（不经过
            # shell），注入面为零；权限闸门缺失则如实标 isolation='none'。
            try:
                result = subprocess.run(
                    ["git"] + [str(a) for a in args],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return {"ok": result.returncode == 0,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "code": result.returncode,
                        "isolation": "none",
                        "blocked_reason": "",
                        "error": "" if result.returncode == 0
                        else (result.stderr or "git 执行失败")}
            except FileNotFoundError:
                return {"ok": False, "stdout": "", "stderr": "git command not found",
                        "code": -1, "isolation": "none", "blocked_reason": "",
                        "error": "找不到 git 可执行文件"}
            except subprocess.TimeoutExpired:
                return {"ok": False, "stdout": "", "stderr": "git command timed out",
                        "code": -1, "isolation": "none", "blocked_reason": "",
                        "error": "git 命令超时（>30s）"}

    def _fail_reason(self, result):
        return (result.get("blocked_reason") or result.get("error")
                or result.get("stderr") or "命令未成功")

    def status(self) -> dict:
        """git status --porcelain → 变更文件列表。失败如实 ok=false + 原因，
        不再伪装成「干净工作树」。"""
        result = self._run(["status", "--porcelain"])
        if not result["ok"]:
            return {"ok": False, "files": [], "raw": "",
                    "error": self._fail_reason(result), "cwd": self.repo_path}
        files = []
        for line in result["stdout"].split("\n"):
            if not line:
                continue
            status_code = line[:2]
            filename = line[3:] if len(line) > 3 else ""
            files.append({"path": filename, "status": status_code,
                          "type": self._status_type(status_code)})
        return {"ok": True, "files": files, "raw": result["stdout"],
                "error": "", "cwd": self.repo_path}

    def _status_type(self, code):
        if code.startswith("??"): return "untracked"
        if code.startswith("M"): return "modified"
        if code.startswith("A"): return "added"
        if code.startswith("D"): return "deleted"
        if code.startswith("R"): return "renamed"
        return "other"

    def diff(self, filepath=None) -> dict:
        """git diff（可选限定文件）。返回 dict 带 ok/diff/error，
        失败不再返回空字符串冒充「没有差异」。"""
        args = ["diff"]
        if filepath:
            args += ["--", filepath]
        result = self._run(args)
        if not result["ok"]:
            return {"ok": False, "diff": "", "error": self._fail_reason(result)}
        return {"ok": True, "diff": result["stdout"], "error": ""}

    def commit(self, message: str, files=None) -> dict:
        """提交变更。files 给了就只 stage 那些；没给才 `add -A`。"""
        add_args = ["add", "-A"] if not files else (["add", "--"] + list(files))
        add_res = self._run(add_args)
        if not add_res["ok"]:
            return {"ok": False,
                    "message": self._fail_reason(add_res),
                    "stage_ok": False}
        if not (message or "").strip():
            return {"ok": False, "message": "提交信息不能为空", "stage_ok": True}
        result = self._run(["commit", "-m", message])
        return {"ok": result["ok"],
                "message": (result["stdout"] or self._fail_reason(result))
                .strip(),
                "stage_ok": True}

    def branches(self) -> dict:
        result = self._run(["branch", "-a"])
        if not result["ok"]:
            return {"ok": False, "branches": [], "current": "",
                    "error": self._fail_reason(result)}
        branches = []
        current = ""
        for line in result["stdout"].split("\n"):
            if not line.strip():
                continue
            if line.startswith("*"):
                current = line[2:].strip()
                branches.append({"name": current, "current": True})
            else:
                name = line.strip()
                branches.append({"name": name, "current": False,
                                 "remote": name.startswith("remotes/")})
        return {"ok": True, "branches": branches, "current": current,
                "error": ""}

    def checkout(self, branch: str) -> dict:
        if not (branch or "").strip():
            return {"ok": False, "message": "缺少分支名"}
        result = self._run(["checkout", branch])
        return {"ok": result["ok"],
                "message": (result["stdout"] or self._fail_reason(result)).strip()}

    def log(self, count=20) -> dict:
        """提交历史。分隔符用 \x1f（ASCII 单元分隔符），提交信息里出现 | 也
        不会把字段切歪（旧实现用 | 分隔，一条含竖线的 commit message 会解析错位）。"""
        try:
            n = max(1, min(200, int(count)))
        except (TypeError, ValueError):
            n = 20
        fmt = "%H\x1f%h\x1f%an\x1f%ad\x1f%s"
        result = self._run(["log", f"-{n}", f"--pretty=format:{fmt}",
                            "--date=short"])
        if not result["ok"]:
            return {"ok": False, "commits": [],
                    "error": self._fail_reason(result)}
        commits = []
        for line in result["stdout"].split("\n"):
            if not line:
                continue
            parts = line.split("\x1f")
            if len(parts) == 5:
                commits.append({"hash": parts[0], "short": parts[1],
                                "author": parts[2], "date": parts[3],
                                "message": parts[4]})
        return {"ok": True, "commits": commits, "error": ""}

    def repo_root(self) -> str:
        result = self._run(["rev-parse", "--show-toplevel"])
        if result["ok"]:
            return result["stdout"].strip()
        return self.repo_path

    def get_tools(self):
        return [
            {"name": "git_status", "description": "查看Git变更状态", "args": {}},
            {"name": "git_diff", "description": "查看文件差异", "args": {"filepath": "string"}},
            {"name": "git_commit", "description": "提交变更", "args": {"message": "string", "files": "list"}},
            {"name": "git_log", "description": "查看提交历史", "args": {"count": "int"}},
        ]
