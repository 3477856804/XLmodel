"""活动日志：真实记录小凌系统事件（对话/训练/模型/插件/系统）。

持久化到 data/activity_log.json，按时间倒序供仪表盘活动流与设置页读取。
所有写入都在内部 try-except 兜住，绝不影响主流程。
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

VALID_TYPES = ("chat", "training", "model", "plugin", "system")
VALID_SEVERITY = ("info", "warn", "error")

MAX_RECORDS = 5000
DEFAULT_RETENTION_DAYS = 30


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ActivityLog:
    """线程安全的活动日志存储（JSON 文件持久化）。"""

    def __init__(self, path: Path | str | None = None):
        if path is None:
            try:
                from . import config as _cfg
                path = _cfg.data("activity_log.json")
            except Exception:  # noqa: BLE001
                path = Path("activity_log.json")
        self.path = Path(path)
        self._lock = threading.RLock()
        self._records: list[dict[str, Any]] = []
        self._next_id = 1
        self._retention_days = DEFAULT_RETENTION_DAYS
        self._load()
        # 去抖落盘：原实现每条记录都全量重写整个 JSON（最多 5000 条）。
        # 改为内存即时可读、磁盘写入限频合并（≈2s 窗口），由后台兜底 flush。
        try:
            from ._persist import DebouncedSaver
            self._saver = DebouncedSaver(self._flush, interval=2.0,
                                         key=f"activity_log:{id(self)}")
        except Exception:  # noqa: BLE001
            self._saver = None

    def flush(self) -> None:
        """强制把脏记录落盘（关闭/导出/测试时调用）。异常不外抛。"""
        try:
            if self._saver is not None:
                self._saver.flush()
        except Exception:  # noqa: BLE001
            pass

    def _load(self) -> None:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
                if isinstance(raw, dict):
                    self._records = list(raw.get("records") or [])
                    self._retention_days = int(raw.get("retention_days")
                                               or DEFAULT_RETENTION_DAYS)
                elif isinstance(raw, list):
                    self._records = list(raw)
            ids = [r.get("id", 0) for r in self._records if isinstance(r, dict)]
            self._next_id = (max(ids) + 1) if ids else 1
        except Exception:  # noqa: BLE001
            self._records = []
            self._next_id = 1

    def _flush(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "retention_days": self._retention_days,
                "records": self._records,
            }
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(self.path)
        except Exception:  # noqa: BLE001
            pass

    def set_retention_days(self, days: int) -> int:
        days = max(1, int(days))
        with self._lock:
            self._retention_days = days
            self._prune_locked()
            self._flush()
        return days

    def get_retention_days(self) -> int:
        with self._lock:
            return self._retention_days

    def log(self, type_: str, title: str, detail: str = "",
            severity: str = "info") -> dict[str, Any] | None:
        try:
            if type_ not in VALID_TYPES:
                type_ = "system"
            if severity not in VALID_SEVERITY:
                severity = "info"
            record = {
                "id": self._next_id,
                "timestamp": _now_iso(),
                "type": type_,
                "title": str(title)[:120],
                "detail": str(detail)[:500],
                "severity": severity,
            }
            with self._lock:
                self._next_id += 1
                self._records.append(record)
                self._prune_locked()
                # 去抖：不再每条都全量重写；由 _saver 限频合并落盘。
                if self._saver is not None:
                    self._saver.mark_dirty()
                else:
                    self._flush()
            return record
        except Exception:  # noqa: BLE001
            return None

    def _prune_locked(self) -> None:
        try:
            cutoff = datetime.now() - timedelta(days=self._retention_days)
            kept = []
            for r in self._records:
                try:
                    ts = datetime.fromisoformat(r.get("timestamp", ""))
                    if ts >= cutoff:
                        kept.append(r)
                except Exception:  # noqa: BLE001
                    kept.append(r)
            self._records = kept
            if len(self._records) > MAX_RECORDS:
                self._records = self._records[-MAX_RECORDS:]
        except Exception:  # noqa: BLE001
            pass

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        with self._lock:
            recs = sorted(self._records, key=lambda r: r.get("timestamp", ""),
                          reverse=True)
            return [dict(r) for r in recs[:limit]]

    def list_by_type(self, type_: str, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        with self._lock:
            recs = [r for r in self._records if r.get("type") == type_]
            recs = sorted(recs, key=lambda r: r.get("timestamp", ""),
                          reverse=True)
            return [dict(r) for r in recs[:limit]]

    def clear(self) -> int:
        with self._lock:
            n = len(self._records)
            self._records = []
            self._flush()
            return n

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._records)
            types = {t: 0 for t in VALID_TYPES}
            for r in self._records:
                t = r.get("type")
                if t in types:
                    types[t] += 1
            sorted_ts = sorted(r.get("timestamp", "") for r in self._records)
            return {
                "total": total,
                "by_type": types,
                "earliest": sorted_ts[0] if sorted_ts else "",
                "latest": sorted_ts[-1] if sorted_ts else "",
                "retention_days": self._retention_days,
            }


_singleton: ActivityLog | None = None
_singleton_lock = threading.Lock()


def get_activity_log() -> ActivityLog:
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = ActivityLog()
    return _singleton


def record(type_: str, title: str, detail: str = "",
           severity: str = "info") -> dict[str, Any] | None:
    """模块内埋点统一入口：任何异常都不外抛。"""
    try:
        return get_activity_log().log(type_, title, detail, severity)
    except Exception:  # noqa: BLE001
        return None
