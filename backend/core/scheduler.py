"""小凌 · 定时系统（CronScheduler）"""
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

JOBS_PATH = DATA_DIR / "cron_jobs.json"

INTERVAL_UNITS = (
    ("秒", 1.0), ("s", 1.0), ("sec", 1.0),
    ("分钟", 60.0), ("min", 60.0), ("m", 60.0),
    ("小时", 3600.0), ("hour", 3600.0), ("h", 3600.0),
    ("天", 86400.0), ("day", 86400.0), ("d", 86400.0),
)

DAILY_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


class CronScheduler:
    def __init__(self, app=None, jobs_path: str | None = None, tick: float = 15.0,
                 on_fire=None):
        self.app = app
        self.path = Path(jobs_path) if jobs_path else JOBS_PATH
        self.tick = float(tick)
        self.on_fire = on_fire
        self.jobs: list[dict] = []
        self._lock = threading.RLock()
        self._stop = False
        self._thread: threading.Thread | None = None
        self._load()
        self._start()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                with self._lock:
                    self.jobs = [j for j in data if isinstance(j, dict)]
        except Exception:
            pass

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = list(self.jobs)
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        except OSError:
            pass

    def _parse(self, spec: str) -> tuple:
        s = (spec or "").strip().lower()
        if s.startswith("every "):
            rest = s[6:].strip()
            for unit, mult in INTERVAL_UNITS:
                if unit in rest:
                    try:
                        n = float(rest.replace(unit, "").strip() or 1)
                        return "interval", max(n * mult, 1.0)
                    except ValueError:
                        break
        if s == "hourly":
            return "interval", 3600.0
        if s == "daily":
            return "daily", "09:00"
        if s.startswith("daily "):
            v = s[6:].strip()
            if DAILY_RE.match(v):
                return "daily", v
        if s.startswith("weekly "):
            return "weekly", s[7:].strip()
        return "interval", 300.0

    def add(self, desc: str, spec: str, action: str = "", payload: dict = None) -> dict:
        kind, value = self._parse(spec)
        job = {
            "id": f"job_{int(time.time() * 1000)}_{len(self.jobs)}",
            "desc": (desc or "")[:200],
            "spec": spec,
            "kind": kind,
            "value": value,
            "action": action,
            "payload": payload or {},
            "last_run": 0.0,
            "runs": 0,
            "created_at": time.time(),
            "enabled": True,
        }
        with self._lock:
            self.jobs.append(job)
        self.save()
        return job

    def remove(self, job_id: str) -> bool:
        with self._lock:
            before = len(self.jobs)
            self.jobs = [j for j in self.jobs if j.get("id") != job_id]
            changed = len(self.jobs) < before
        if changed:
            self.save()
        return changed

    def pause(self, job_id: str) -> bool:
        with self._lock:
            for j in self.jobs:
                if j.get("id") == job_id:
                    j["enabled"] = False
                    self.save()
                    return True
        return False

    def resume(self, job_id: str) -> bool:
        with self._lock:
            for j in self.jobs:
                if j.get("id") == job_id:
                    j["enabled"] = True
                    self.save()
                    return True
        return False

    def list_jobs(self) -> list:
        with self._lock:
            return [dict(j) for j in self.jobs]

    def list_text(self) -> str:
        with self._lock:
            jobs = list(self.jobs)
        if not jobs:
            return "当前无定时任务"
        lines = []
        for i, j in enumerate(jobs, 1):
            state = "▶" if j.get("enabled", True) else "⏸"
            lines.append(f"{state} {i}. {j['desc']}（{j['spec']}，已执行 {j['runs']} 次）")
        return "\n".join(lines)

    def _start(self):
        def _loop():
            while not self._stop:
                time.sleep(self.tick)
                try:
                    self._tick_once()
                except Exception:
                    pass
        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def _tick_once(self):
        now = time.time()
        fires = []
        with self._lock:
            for j in self.jobs:
                if not j.get("enabled", True):
                    continue
                kind = j.get("kind")
                value = j.get("value")
                last = float(j.get("last_run", 0))
                due = False
                if kind == "interval":
                    due = (now - last) >= float(value)
                elif kind == "daily":
                    cur = time.strftime("%H:%M")
                    due = (cur == value and now - last > 60)
                if due:
                    j["last_run"] = now
                    j["runs"] = int(j.get("runs", 0)) + 1
                    fires.append(dict(j))
        for job in fires:
            self._fire(job)
        if fires:
            self.save()

    def _fire(self, job: dict):
        if self.on_fire:
            try:
                self.on_fire(job)
            except Exception:
                pass
        if self.app and hasattr(self.app, "chat") and job.get("action"):
            try:
                self.app.chat(job["action"])
            except Exception:
                pass

    def stop(self):
        self._stop = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def clear(self):
        with self._lock:
            self.jobs.clear()
        self.save()

    def stats(self) -> dict:
        with self._lock:
            total = len(self.jobs)
            enabled = sum(1 for j in self.jobs if j.get("enabled", True))
            total_runs = sum(int(j.get("runs", 0)) for j in self.jobs)
            return {"total": total, "enabled": enabled, "runs": total_runs,
                    "path": str(self.path)}