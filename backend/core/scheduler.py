"""定时任务调度器 - 简化 cron"""
import json
import threading
import time

from .paths import DATA_DIR

CRON_JOBS = DATA_DIR / "cron_jobs.json"


class CronScheduler:
    """定时任务调度器"""

    def __init__(self, app=None):
        self.app = app
        self.jobs = []
        self.load()
        self._start()

    def load(self):
        try:
            if CRON_JOBS.exists():
                self.jobs = json.loads(CRON_JOBS.read_text(encoding="utf-8"))
        except Exception:
            pass

    def save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CRON_JOBS.write_text(json.dumps(self.jobs, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass

    def add(self, desc, spec):
        job = {
            "desc": desc, "spec": spec, "last_run": 0, "runs": 0,
            "type": self._parse_spec(spec),
        }
        self.jobs.append(job)
        self.save()
        return f"已添加定时任务：{desc}（{spec}）"

    def _parse_spec(self, spec):
        spec = spec.strip().lower()
        if spec.startswith("every "):
            rest = spec[6:]
            if "秒" in rest or "s" in rest:
                return ("interval", float(rest.replace("秒", "").replace("s", "").strip()))
            if "分钟" in rest or "m" in rest:
                return ("interval", float(rest.replace("分钟", "").replace("m", "").strip()) * 60)
        if spec.startswith("daily "):
            return ("daily", spec[6:].strip())
        if spec == "hourly":
            return ("interval", 3600)
        return ("interval", 300)

    def _start(self):
        def _loop():
            while True:
                time.sleep(15)
                try:
                    now = time.time()
                    for job in self.jobs:
                        kind, value = job["type"]
                        due = False
                        if kind == "interval":
                            due = (now - job["last_run"]) >= value
                        elif kind == "daily":
                            cur = time.strftime("%H:%M")
                            due = (cur == value and now - job["last_run"] > 60)
                        if due:
                            job["last_run"] = now
                            job["runs"] += 1
                            print(f"  [定时] 执行：{job['desc']}")
                            self.save()
                except Exception:
                    pass
        threading.Thread(target=_loop, daemon=True).start()

    def list_jobs(self):
        if not self.jobs:
            return "当前无定时任务"
        lines = []
        for i, j in enumerate(self.jobs, 1):
            lines.append(f"  {i}. {j['desc']}（{j['spec']}，已执行{j['runs']}次）")
        return "\n".join(lines)
