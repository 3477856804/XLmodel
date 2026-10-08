import uuid, time, json, logging, threading
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Generator

@dataclass
class SubAgentTask:
    id: str
    description: str
    status: str = "pending"  # pending/running/completed/failed
    result: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0
    progress: float = 0
    events: List[Dict] = field(default_factory=list)

class SubAgent:
    """独立上下文的子 Agent"""
    def __init__(self, agent_id: str, engine=None):
        self.id = agent_id
        self.engine = engine
        self.context = []  # 独立上下文
        self.tasks = {}  # task_id -> SubAgentTask
        self._lock = threading.Lock()

    def delegate(self, description: str, tools: List[str] = None) -> str:
        """委派任务给子 Agent，返回 task_id"""
        task_id = str(uuid.uuid4())[:8]
        task = SubAgentTask(id=task_id, description=description)
        with self._lock:
            self.tasks[task_id] = task
        # 在后台线程执行任务
        threading.Thread(target=self._execute, args=(task, tools), daemon=True).start()
        return task_id

    def _execute(self, task: SubAgentTask, tools: List[str] = None):
        """执行子任务（真实调用 engine；引擎未加载时直接返回错误，不假装执行）。"""
        task.status = "running"
        task.events.append({"type": "start", "content": f"子 Agent 开始执行: {task.description}"})
        try:
            if self.engine and hasattr(self.engine, "chat"):
                # 真实调用 engine 执行任务
                result = self.engine.chat(task.description)
                task.result = result
                task.progress = 100
                task.status = "completed"
                task.completed_at = time.time()
                task.events.append({"type": "complete", "content": task.result})
            else:
                # 引擎未加载：返回错误状态，不 sleep 假装在执行
                task.status = "failed"
                task.error = "子Agent执行失败：引擎未加载"
                task.result = ""
                task.events.append({"type": "error", "content": task.error})
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.events.append({"type": "error", "content": str(e)})

    def get_task(self, task_id: str) -> Optional[SubAgentTask]:
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[Dict]:
        return [{"id": t.id, "description": t.description, "status": t.status,
                 "progress": t.progress, "result": t.result[:200] if t.result else "",
                 "created_at": t.created_at} for t in self.tasks.values()]


class SubAgentManager:
    """子 Agent 管理器"""
    def __init__(self, engine=None):
        self.engine = engine
        self.agents = {}  # agent_id -> SubAgent
        self._lock = threading.Lock()

    def create_agent(self, name: str = None) -> str:
        """创建子 Agent"""
        agent_id = name or f"sub_{uuid.uuid4().hex[:6]}"
        agent = SubAgent(agent_id, self.engine)
        with self._lock:
            self.agents[agent_id] = agent
        return agent_id

    def delegate(self, agent_id: str, description: str, tools: List[str] = None) -> str:
        """委派任务给指定子 Agent"""
        if agent_id not in self.agents:
            agent_id = self.create_agent(agent_id)
        return self.agents[agent_id].delegate(description, tools)

    def get_status(self, agent_id: str = None) -> Dict:
        """获取子 Agent 状态"""
        if agent_id:
            agent = self.agents.get(agent_id)
            if agent:
                return {"agent_id": agent_id, "tasks": agent.list_tasks()}
            return {"error": "agent not found"}
        return {"agents": [{"id": aid, "task_count": len(a.tasks)} for aid, a in self.agents.items()]}
