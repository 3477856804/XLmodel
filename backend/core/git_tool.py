import subprocess, json, os


class GitTool:
    def __init__(self, repo_path="."):
        self.repo_path = repo_path

    def _run(self, args):
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}
        except FileNotFoundError:
            return {"ok": False, "stdout": "", "stderr": "git command not found"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": "git command timed out"}

    def status(self) -> dict:
        """获取 git status --porcelain，解析为变更文件列表"""
        result = self._run(["status", "--porcelain"])
        files = []
        if result["ok"]:
            for line in result["stdout"].strip().split("\n"):
                if line:
                    status_code = line[:2]
                    filename = line[3:]
                    files.append({"path": filename, "status": status_code, "type": self._status_type(status_code)})
        return {"ok": True, "files": files, "raw": result["stdout"]}

    def _status_type(self, code):
        if code.startswith("??"): return "untracked"
        if code.startswith("M"): return "modified"
        if code.startswith("A"): return "added"
        if code.startswith("D"): return "deleted"
        if code.startswith("R"): return "renamed"
        return "other"

    def diff(self, filepath=None) -> str:
        """获取 git diff，可选指定文件"""
        args = ["diff"]
        if filepath:
            args.append(filepath)
        result = self._run(args)
        return result["stdout"] if result["ok"] else result["stderr"]

    def commit(self, message: str, files=None) -> dict:
        """提交变更，files 为 None 则提交全部"""
        if files:
            self._run(["add"] + list(files))
        else:
            self._run(["add", "-A"])
        result = self._run(["commit", "-m", message])
        return {"ok": result["ok"], "message": result["stdout"] or result["stderr"]}

    def branches(self) -> dict:
        """列出所有分支"""
        result = self._run(["branch", "-a"])
        branches = []
        current = ""
        if result["ok"]:
            for line in result["stdout"].strip().split("\n"):
                if not line.strip():
                    continue
                if line.startswith("*"):
                    current = line[2:].strip()
                    branches.append({"name": current, "current": True})
                else:
                    branches.append({"name": line.strip(), "current": False})
        return {"ok": True, "branches": branches, "current": current}

    def checkout(self, branch: str) -> dict:
        result = self._run(["checkout", branch])
        return {"ok": result["ok"], "message": result["stdout"] or result["stderr"]}

    def log(self, count=20) -> list:
        """获取提交历史"""
        result = self._run(["log", f"-{count}", "--pretty=format:%H|%h|%an|%ad|%s", "--date=short"])
        commits = []
        if result["ok"]:
            for line in result["stdout"].strip().split("\n"):
                if "|" in line:
                    parts = line.split("|", 4)
                    if len(parts) == 5:
                        commits.append({
                            "hash": parts[0],
                            "short": parts[1],
                            "author": parts[2],
                            "date": parts[3],
                            "message": parts[4],
                        })
        return commits

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
