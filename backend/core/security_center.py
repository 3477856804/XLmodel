"""安全中心：权限管理、目录保护、操作审计。

本模块此前有三个"看起来能用、实际是空的"问题（前端「设置 → 安全中心」的
开关与审计列表因此是装饰性的）：

1. **配置落在相对路径 `data/security_config.json`**
   —— 后端从 exe 目录或 Flutter 根目录启动时，`data/` 会落到程序目录甚至
   当前工作目录，与「沙箱统一收敛到用户数据目录」的约定冲突，升级即丢。
   现改为 `config.data('security_config.json')`，与其它运行时数据同源。

2. **审计日志只存在内存里**
   —— `audit_log` 是个 list，进程一退出全没了。前端「审计日志」页刷新后
   永远为空（重启更不必说）。现改为追加写 `<data>/security_audit.jsonl`，
   启动时回读末尾若干条。

3. **`check_permission()` 全仓零调用方**
   —— 权限开关能改、能存盘，但没有任何执行路径读它，也就是开关不起作用。
   现在 `core/exec_gate.py`（模型产出命令的唯一闸门）会在执行前咨询
   `get_security_center().check_permission(...)`，开关真正生效。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Set  # noqa: F401  (预留类型导入)

logger = logging.getLogger('xiaoling.security')

# 审计日志在内存里保留的最大条数（落盘不受此限制）
_MAX_MEMORY_AUDIT = 1000


def _default_config_path() -> str:
    """配置文件的默认落点：用户沙箱的 data/ 目录。

    取不到沙箱路径时（例如单独 import 本模块做单元测试）退回相对路径，
    保持向后兼容，不让安全中心成为启动的硬依赖。
    """
    try:
        from . import config as _cfg
    except Exception:                                            # noqa: BLE001
        try:
            import config as _cfg                                 # type: ignore
        except Exception:                                        # noqa: BLE001
            return os.path.join('data', 'security_config.json')
    try:
        return str(_cfg.data('security_config.json'))
    except Exception:                                            # noqa: BLE001
        return os.path.join('data', 'security_config.json')


def _audit_path() -> str:
    try:
        from . import config as _cfg
    except Exception:                                            # noqa: BLE001
        try:
            import config as _cfg                                 # type: ignore
        except Exception:                                        # noqa: BLE001
            return os.path.join('data', 'security_audit.jsonl')
    try:
        return str(_cfg.data('security_audit.jsonl'))
    except Exception:                                            # noqa: BLE001
        return os.path.join('data', 'security_audit.jsonl')


class SecurityCenter:
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or _default_config_path()
        self.audit_log: list = []       # 最近的操作审计（内存镜像，落盘见 _append_audit）
        self._audit_lock = threading.Lock()
        self._load_config()
        self._load_audit()

    # ---------------------------------------------------------------- 配置
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
            try:
                with open(self.config_path, encoding='utf-8') as f:
                    self.config = {**default, **json.load(f)}
                return
            except Exception as e:                               # noqa: BLE001
                # 配置损坏时不要静默吞掉，也不能让安全中心直接不可用：
                # 退回默认值并在日志里说清楚（此前是直接抛异常，整个
                # security: 指令族全废）。
                logger.warning('安全中心配置损坏，已退回默认值：%s', e)
        self.config = default
        self._save_config()

    def _save_config(self):
        d = os.path.dirname(self.config_path)
        if d:
            os.makedirs(d, exist_ok=True)
        try:
            with open(self.config_path, "w", encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:                                   # noqa: BLE001
            logger.warning('安全中心配置写入失败：%s', e)

    def get_config(self) -> dict:
        return self.config

    # ---------------------------------------------------------------- 权限
    def check_permission(self, tool: str) -> dict:
        """检查工具是否被允许，是否需要审批。"""
        allowed = self.config["tool_permissions"].get(tool, True)
        need_approval = tool in self.config["require_approval"]
        return {"allowed": allowed, "need_approval": need_approval, "tool": tool}

    def set_permission(self, tool: str, allowed: bool):
        self.config["tool_permissions"][tool] = allowed
        self._save_config()

    def set_require_approval(self, tool: str, required: bool):
        req = list(self.config.get("require_approval", []))
        if required and tool not in req:
            req.append(tool)
        elif not required and tool in req:
            req.remove(tool)
        self.config["require_approval"] = req
        self._save_config()

    # ---------------------------------------------------------------- 目录保护
    def _resolved_protected(self, protected: str) -> str:
        """把受保护目录解析成绝对路径。

        默认配置里是 `resources/models` 这种**相对**路径，直接 abspath 会按
        当前工作目录解析 —— 程序从别的目录启动时保护范围就错了。这里优先按
        程序的资源目录解析。
        """
        if os.path.isabs(protected):
            return os.path.abspath(protected)
        try:
            from . import config as _cfg
        except Exception:                                        # noqa: BLE001
            try:
                import config as _cfg                             # type: ignore
            except Exception:                                    # noqa: BLE001
                return os.path.abspath(protected)
        try:
            return str((_cfg.RESOURCE_DIR / protected).resolve())
        except Exception:                                        # noqa: BLE001
            return os.path.abspath(protected)

    def is_protected(self, path: str) -> bool:
        """检查路径是否在受保护目录下。"""
        abs_path = os.path.abspath(path)
        for protected in self.config.get("protected_dirs", []):
            protected_abs = self._resolved_protected(protected)
            if abs_path == protected_abs or abs_path.startswith(
                    protected_abs + os.sep):
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

    # ---------------------------------------------------------------- 审计
    def _load_audit(self):
        """从 JSONL 回读最近的审计记录（最多 _MAX_MEMORY_AUDIT 条）。"""
        p = _audit_path()
        if not os.path.exists(p):
            return
        try:
            items = []
            with open(p, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        items.append(json.loads(line))
                    except Exception:                            # noqa: BLE001
                        continue
            self.audit_log = items[-_MAX_MEMORY_AUDIT:]
        except Exception as e:                                   # noqa: BLE001
            logger.warning('安全审计日志读取失败：%s', e)

    def audit(self, action: str, detail: str = "", risk: str = "low"):
        """记录操作审计日志（内存 + 追加落盘）。"""
        if not self.config.get("audit_enabled", True):
            return
        entry = {"time": time.time(), "action": action,
                 "detail": detail, "risk": risk}
        with self._audit_lock:
            self.audit_log.append(entry)
            if len(self.audit_log) > _MAX_MEMORY_AUDIT:
                self.audit_log = self.audit_log[-_MAX_MEMORY_AUDIT:]
            try:
                p = _audit_path()
                d = os.path.dirname(p)
                if d:
                    os.makedirs(d, exist_ok=True)
                with open(p, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            except Exception as e:                               # noqa: BLE001
                # 落盘失败不能影响主流程，但必须留痕
                logger.warning('安全审计落盘失败：%s', e)

    def get_audit_log(self, limit=50) -> list:
        return list(reversed(self.audit_log[-limit:]))

    def clear_audit_log(self) -> int:
        """清空审计（内存 + 文件）。返回清掉的条数。"""
        with self._audit_lock:
            n = len(self.audit_log)
            self.audit_log = []
        try:
            p = _audit_path()
            if os.path.exists(p):
                # 红线：不删除文件，改为截断为空文件
                open(p, 'w', encoding='utf-8').close()
        except Exception as e:                                   # noqa: BLE001
            logger.warning('安全审计清空失败：%s', e)
        return n


# ---------------------------------------------------------------- 单例
_center: SecurityCenter | None = None
_center_lock = threading.Lock()


def get_security_center() -> SecurityCenter:
    """进程内单例。执行链（exec_gate）与 RPC 共用同一个实例，
    否则「改开关」与「读开关」会落在两个互不可见的对象上。"""
    global _center
    if _center is not None:
        return _center
    with _center_lock:
        if _center is None:
            _center = SecurityCenter()
    return _center
