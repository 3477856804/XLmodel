"""安全中心：权限管理、目录保护、操作审计"""
import json
import os
import time
from typing import List, Dict, Set  # noqa: F401  (预留类型导入)


class SecurityCenter:
    def __init__(self, config_path="data/security_config.json"):
        self.config_path = config_path
        self.audit_log: list = []  # 操作审计日志
        self._load_config()

    def _load_config(self):
        default = {
            "tool_permissions": {
                "file_read": True,
                "file_write": True,
                "terminal": True,
                "network": True,
                "browser": True,
                "git": True,
                "mcp": True,
            },
            "protected_dirs": [
                "resources/models",
                "resources/sounds",
                "frontend/assets",
            ],
            "allowed_dirs": [],
            "require_approval": ["file_write", "terminal", "git"],
            "max_file_size_mb": 50,
            "audit_enabled": True,
        }
        if os.path.exists(self.config_path):
            with open(self.config_path) as f:
                self.config = {**default, **json.load(f)}
        else:
            self.config = default
            self._save_config()

    def _save_config(self):
        d = os.path.dirname(self.config_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def check_permission(self, tool: str) -> dict:
        """检查工具是否被允许，是否需要审批"""
        allowed = self.config["tool_permissions"].get(tool, True)
        need_approval = tool in self.config["require_approval"]
        return {"allowed": allowed, "need_approval": need_approval, "tool": tool}

    def set_permission(self, tool: str, allowed: bool):
        self.config["tool_permissions"][tool] = allowed
        self._save_config()

    def is_protected(self, path: str) -> bool:
        """检查路径是否在受保护目录下"""
        abs_path = os.path.abspath(path)
        for protected in self.config["protected_dirs"]:
            protected_abs = os.path.abspath(protected)
            if abs_path.startswith(protected_abs):
                return True
        return False

    def add_protected_dir(self, path: str):
        if path not in self.config["protected_dirs"]:
            self.config["protected_dirs"].append(path)
            self._save_config()

    def remove_protected_dir(self, path: str):
        if path in self.config["protected_dirs"]:
            self.config["protected_dirs"].remove(path)
            self._save_config()

    def audit(self, action: str, detail: str = "", risk: str = "low"):
        """记录操作审计日志"""
        if not self.config.get("audit_enabled", True):
            return
        entry = {"time": time.time(), "action": action,
                 "detail": detail, "risk": risk}
        self.audit_log.append(entry)
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]

    def get_audit_log(self, limit=50) -> list:
        return list(reversed(self.audit_log[-limit:]))

    def get_config(self) -> dict:
        return self.config
