# -*- coding: utf-8 -*-
"""小凌 · 后台任务管理（BackgroundTaskManager）
==================================================

把长任务（跑测试、构建、批量处理、长时间命令）放到后台线程执行，
RPC / UI 可随时查询状态、取结果、请求取消。

核心原则（真实执行，绝不伪造状态）：
  * start_task 真正起一个 daemon 线程跑 func；
  * status 只有 running / completed / failed / cancelled / interrupted；
  * Python 线程无法被强制杀死，cancel_task 是**协作式**取消：设置一个
    cancel Event，任务函数需自行检查；本模块如实把任务标记为 cancelled，
    绝不假装"已杀死"；
  * 任务元数据持久化到 JSON，进程重启后恢复：重启前仍在 running 的任务
    如实标记为 interrupted（线程已随进程消亡，无法真续跑）；
  * 所有方法 try-except，返回 dict，不向调用方抛异常。
"""
from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from pathlib import Path

try:  # 兼容包导入与直接运行
    from .config import DATA_DIR
except Exception:  # pragma: no cover
    DATA_DIR = Path("data")

_TERMINAL_STATUSES = ("completed", "failed", "cancelled", "interrupted")
MAX_OUTPUT_LINES = 2000


class BackgroundTaskManager:
    """后台任务生命周期管理 + JSON 持久化。"""

    def __init__(self, persist_path: str | Path | None = None,
                 max_tasks: int = 500):
        self.path = Path(persist_path) if persist_path else (
            DATA_DIR / "background_tasks.json")
        self.max_tasks = int(max_tasks or 500)
        self._tasks: dict[str, dict] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.RLock()
        self._load()

    # ------------------------------------------------------------------ start
    def start_task(self, name: str, func, *args, **kwargs) -> dict:
        """启动后台任务，返回 {ok, task_id, name, status}。

        func 形如 func(cancel_event: threading.Event, output, *args)，
        其中 output 是一个可调用对象 output(text: str)，用于追加进度输出。
        func 抛出异常记为 failed；正常返回值记入 result。
        """
        if not callable(func):
            return {"ok": False, "error": "func 必须是可调用对象"}
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        cancel_event = threading.Event()
        task = {
            "id": task_id,
            "name": (name or "unnamed")[:200],
            "status": "running",
            "result": None,
            "error": "",
            "output": [],
            "started_at": time.time(),
            "finished_at": 0.0,
            "cancelled": False,
        }
        with self._lock:
            self._tasks[task_id] = task
            self._cancel_events[task_id] = cancel_event

        def _append(line: str):
            try:
                text = str(line)
                with self._lock:
                    self._tasks[task_id]["output"].append(text)
                    if len(self._tasks[task_id]["output"]) > MAX_OUTPUT_LINES:
                        self._tasks[task_id]["output"] = \
                            self._tasks[task_id]["output"][-MAX_OUTPUT_LINES:]
            except Exception:  # noqa: BLE001
                pass

        def _runner():
            try:
                ret = func(cancel_event, _append, *args, **kwargs)
                with self._lock:
                    t = self._tasks.get(task_id)
                    if t is None:
                        return
                    if cancel_event.is_set():
                        t["status"] = "cancelled"
                    else:
                        t["status"] = "completed"
                        t["result"] = self._safe_result(ret)
                    t["finished_at"] = time.time()
            except Exception as e:  # noqa: BLE001
                with self._lock:
                    t = self._tasks.get(task_id)
                    if t is not None:
                        t["status"] = "failed"
                        t["error"] = f"{type(e).__name__}: {e}"
                        t["finished_at"] = time.time()
            finally:
                with self._lock:
                    self._threads.pop(task_id, None)
                self._save()

        th = threading.Thread(target=_runner, daemon=True,
                              name=f"xl-{task_id}")
        with self._lock:
            self._threads[task_id] = th
        th.start()
        self._save()
        return {"ok": True, "task_id": task_id, "name": task["name"],
                "status": "running"}

    @staticmethod
    def _safe_result(ret):
        """结果尽量 JSON 序列化；不可序列化则降级为字符串。"""
        if ret is None:
            return None
        try:
            json.dumps(ret)
            return ret
        except Exception:  # noqa: BLE001
            return str(ret)[:10000]

    # ------------------------------------------------------------------ query
    def get_task_status(self, task_id: str = "") -> dict:
        """获取任务状态快照。未知 id 返回错误字典。"""
        try:
            with self._lock:
                t = self._tasks.get(task_id)
                if t is None:
                    return {"ok": False, "error": f"未知任务：{task_id}"}
                out = dict(t)
                out.pop("output", None)
                out["ok"] = True
                out["alive"] = task_id in self._threads
                out["output_lines"] = len(t.get("output", []))
                return out
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def get_task_result(self, task_id: str = "", tail: int = 200) -> dict:
        """获取任务结果与尾部输出。未知 id 返回错误字典。"""
        try:
            with self._lock:
                t = self._tasks.get(task_id)
                if t is None:
                    return {"ok": False, "error": f"未知任务：{task_id}"}
                output = t.get("output", [])
                return {
                    "ok": True, "id": task_id, "name": t.get("name", ""),
                    "status": t.get("status", "unknown"),
                    "result": t.get("result"), "error": t.get("error", ""),
                    "output": output[-int(tail or 200):],
                    "started_at": t.get("started_at", 0.0),
                    "finished_at": t.get("finished_at", 0.0),
                }
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def cancel_task(self, task_id: str = "") -> dict:
        """协作式取消：设置取消 Event，任务函数应自行退出。

        如实说明：无法强制杀死线程；若任务不检查 cancel_event，它仍会跑到
        自然结束。本方法只把 running 任务标记为待取消。
        """
        try:
            with self._lock:
                t = self._tasks.get(task_id)
                if t is None:
                    return {"ok": False, "error": f"未知任务：{task_id}"}
                if t.get("status") in _TERMINAL_STATUSES:
                    return {"ok": True, "task_id": task_id,
                            "status": t.get("status"),
                            "message": "任务已结束，无需取消"}
                ev = self._cancel_events.get(task_id)
                if ev is not None:
                    ev.set()
                t["cancelled"] = True
            self._save()
            return {"ok": True, "task_id": task_id, "status": "cancelled",
                    "message": "已请求协作式取消（任务函数需响应 cancel_event）"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def list_tasks(self, limit: int = 100) -> dict:
        """列出所有任务（按启动时间倒序）。"""
        try:
            with self._lock:
                items = []
                for t in self._tasks.values():
                    s = dict(t)
                    s.pop("output", None)
                    s["alive"] = s.get("id") in self._threads
                    items.append(s)
            items.sort(key=lambda x: x.get("started_at", 0), reverse=True)
            return {"ok": True, "tasks": items[:int(limit or 100)],
                    "total": len(items)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def stats(self) -> dict:
        try:
            with self._lock:
                by_status: dict[str, int] = {}
                for t in self._tasks.values():
                    s = t.get("status", "unknown")
                    by_status[s] = by_status.get(s, 0) + 1
                return {"total": len(self._tasks), "by_status": by_status,
                        "path": str(self.path)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # ------------------------------------------------------------------ persist
    def _load(self):
        """从 JSON 恢复任务状态。重启前 running 的任务如实标记为 interrupted。"""
        try:
            if not self.path.exists():
                return
            data = json.loads(self.path.read_text(encoding="utf-8"))
            tasks = data.get("tasks") if isinstance(data, dict) else data
            if not isinstance(tasks, list):
                return
            with self._lock:
                for t in tasks:
                    if not isinstance(t, dict) or "id" not in t:
                        continue
                    if t.get("status") == "running":
                        t["status"] = "interrupted"
                        t["error"] = "进程重启，任务被中断（未真正续跑）"
                        t["finished_at"] = t.get("finished_at") or time.time()
                    t.setdefault("output", [])
                    self._tasks[t["id"]] = t
        except Exception:  # noqa: BLE001
            self._tasks = {}

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                # 裁剪任务数，丢弃最老的已结束任务
                if len(self._tasks) > self.max_tasks:
                    ordered = sorted(self._tasks.values(),
                                     key=lambda x: x.get("started_at", 0))
                    stale = [t["id"] for t in ordered
                             if t.get("status") in _TERMINAL_STATUSES]
                    for tid in stale[:len(self._tasks) - self.max_tasks]:
                        self._tasks.pop(tid, None)
                    payload = list(self._tasks.values())
                else:
                    payload = list(self._tasks.values())
            self.path.write_text(
                json.dumps({"tasks": payload}, ensure_ascii=False, indent=1),
                encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def _selftest():  # pragma: no cover
    import tempfile
    p = Path(tempfile.mkdtemp()) / "tasks.json"
    m = BackgroundTaskManager(persist_path=p)

    def job(cancel_event, output, n):
        for i in range(n):
            if cancel_event.is_set():
                return "aborted"
            output(f"step {i}")
            time.sleep(0.01)
        return f"done-{n}"

    r = m.start_task("test", job, 3)
    tid = r["task_id"]
    time.sleep(0.2)
    st = m.get_task_status(tid)
    res = m.get_task_result(tid)
    print("status:", st["status"], "| result:", res["result"],
          "| out_lines:", len(res["output"]))

    r2 = m.start_task("slow", job, 1000)
    time.sleep(0.02)
    print("cancel:", m.cancel_task(r2["task_id"])["message"])
    time.sleep(0.1)
    print("after cancel:", m.get_task_status(r2["task_id"])["status"])
    print("list:", m.list_tasks()["total"])

    m2 = BackgroundTaskManager(persist_path=p)
    print("reload running->interrupted check:",
          [t["status"] for t in m2.list_tasks()["tasks"]])


if __name__ == "__main__":  # pragma: no cover
    _selftest()
