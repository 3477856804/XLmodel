"""小凌 · 多子 Agent 并行系统"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

DECOMPOSE_HINTS = ("所有", "全部", "批量", "多个", "每个", "分别", "列表", "分类", "逐条")
ANGLES = ("从整体梳理", "从细节执行", "从风险排查", "从优化提升", "从成果验证",
          "从时间维度", "从空间维度")


class MultiAgentSystem:
    def __init__(self, app=None, max_agents: int = 100, max_workers: int = 16):
        self.app = app
        self.max_agents = max_agents
        self.max_workers = max_workers
        self.agents: dict[str, dict] = {}
        self._lock = threading.RLock()

    def spawn(self, task: str, count: int = 3, max_workers: int | None = None) -> str:
        count = max(1, min(int(count), self.max_agents))
        workers = max_workers or min(count, self.max_workers)
        subtasks = self._decompose(task, count)
        with self._lock:
            self.agents.clear()
            for i in range(count):
                aid = f"agent_{i + 1}"
                self.agents[aid] = {"status": "排队中",
                                    "task": subtasks[i % len(subtasks)][:60],
                                    "result": "", "started_at": 0.0,
                                    "finished_at": 0.0}
        results = {}

        def _run(aid: str, sub: str):
            with self._lock:
                if aid in self.agents:
                    self.agents[aid]["status"] = "执行中"
                    self.agents[aid]["started_at"] = __import__("time").time()
            try:
                if self.app and hasattr(self.app, "chat"):
                    out = self.app.chat(sub)
                    reply = out[0] if isinstance(out, (tuple, list)) else out
                else:
                    reply = f"任务完成：{sub[:50]}"
                with self._lock:
                    if aid in self.agents:
                        self.agents[aid]["status"] = "完成"
                        self.agents[aid]["result"] = str(reply)[:500]
                        self.agents[aid]["finished_at"] = __import__("time").time()
                return str(reply)
            except Exception as e:
                with self._lock:
                    if aid in self.agents:
                        self.agents[aid]["status"] = "失败"
                        self.agents[aid]["result"] = str(e)[:300]
                return f"子任务失败：{e}"

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for i in range(count):
                aid = f"agent_{i + 1}"
                sub = subtasks[i % len(subtasks)]
                futures[pool.submit(_run, aid, sub)] = aid
            for fut in as_completed(futures):
                aid = futures[fut]
                try:
                    results[aid] = fut.result()
                except Exception as e:
                    results[aid] = f"异常：{e}"

        lines = []
        for i in range(1, count + 1):
            aid = f"agent_{i}"
            lines.append(f"[{aid}] {str(results.get(aid, '无结果'))[:80]}")
        return "\n".join(lines)

    def _decompose(self, task: str, count: int) -> list:
        if not any(k in task for k in DECOMPOSE_HINTS):
            return [task]
        return [f"{task}（{ANGLES[i % len(ANGLES)]}）" for i in range(min(count, 5))]

    def status(self) -> str:
        with self._lock:
            if not self.agents:
                return "当前无子 agent 在运行"
            done = sum(1 for a in self.agents.values() if a["status"] == "完成")
            running = sum(1 for a in self.agents.values() if a["status"] == "执行中")
            failed = sum(1 for a in self.agents.values() if a["status"] == "失败")
            return (f"共 {len(self.agents)} 个子 agent："
                    f"完成 {done}｜执行中 {running}｜失败 {failed}")

    def report(self) -> list:
        with self._lock:
            return [{"id": k, **v} for k, v in self.agents.items()]

    def clear(self):
        with self._lock:
            self.agents.clear()

    def stats(self) -> dict:
        with self._lock:
            by_status: dict[str, int] = {}
            for a in self.agents.values():
                s = a.get("status", "unknown")
                by_status[s] = by_status.get(s, 0) + 1
            return {"total": len(self.agents), "by_status": by_status,
                    "max_agents": self.max_agents}