"""多子 Agent 并行系统 - 派发 N 个 agent 协同完成任务"""
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class MultiAgentSystem:
    """多子 Agent 并行系统"""

    def __init__(self, app=None):
        self.app = app
        self.agents = {}
        self.lock = threading.Lock()
        self.max_agents = 100

    def spawn(self, task, count=3, max_workers=None):
        """派発 count 个子 agent 并行执行"""
        count = max(1, min(count, self.max_agents))
        workers = max_workers or min(count, 16)
        print(f"\n  [智能体] 派发 {count} 个子 agent 并行工作")

        subtasks = self._decompose(task, count)
        if len(subtasks) == 1:
            subtasks = [f"{task}（角度{i+1}）" for i in range(count)]

        with self.lock:
            for i in range(count):
                aid = f"agent_{i+1}"
                self.agents[aid] = {"status": "排队中", "task": subtasks[i % len(subtasks)][:60], "result": ""}

        results = {}

        def _run(aid, sub):
            with self.lock:
                self.agents[aid]["status"] = "执行中"
            try:
                if self.app and hasattr(self.app, 'chat'):
                    reply, _ = self.app.chat(sub)
                else:
                    reply = f"任务完成: {sub[:50]}"
                with self.lock:
                    self.agents[aid]["status"] = "完成"
                    self.agents[aid]["result"] = reply[:300]
                return reply
            except Exception as e:
                with self.lock:
                    self.agents[aid]["status"] = "失败"
                    self.agents[aid]["result"] = str(e)[:200]
                return f"子任务失败: {e}"

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for i in range(count):
                aid = f"agent_{i+1}"
                sub = subtasks[i % len(subtasks)]
                futures[pool.submit(_run, aid, sub)] = aid
            for fut in as_completed(futures):
                aid = futures[fut]
                try:
                    results[aid] = fut.result()
                except Exception as e:
                    results[aid] = f"异常: {e}"

        summary_lines = []
        for i in range(1, count + 1):
            aid = f"agent_{i}"
            r = results.get(aid, "无结果")
            summary_lines.append(f"  [{aid}] {r[:80]}")

        return "\n".join(summary_lines)

    def _decompose(self, task, count):
        decompose_hint = ["所有", "全部", "批量", "多个", "每个", "分别", "列表"]
        if not any(k in task for k in decompose_hint):
            return [task]
        angles = ["从整体梳理", "从细节执行", "从风险排查", "从优化提升", "从成果验证"]
        return [f"{task}（{angles[i % len(angles)]}）" for i in range(min(count, 5))]

    def status(self):
        with self.lock:
            if not self.agents:
                return "当前无子 agent 在运行"
            lines = [f"共 {len(self.agents)} 个子 agent："]
            done = sum(1 for a in self.agents.values() if a["status"] == "完成")
            lines.append(f"完成：{done}/{len(self.agents)}")
            return "\n".join(lines)
