"""小凌 · 子 Agent（独立工具集 + 权限模型 + 多步执行循环）"""
import uuid, time, json, logging, threading, re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

logger = logging.getLogger("xiaoling.sub_agent")

# ---------------------------------------------------------------------------
# 工具权限分类
# ---------------------------------------------------------------------------
# 只读类：搜索 / 查看 / 计算 —— readonly 级别可用
READONLY_TOOLS = frozenset({
    "get_time", "calculator", "read_file", "list_dir", "recall",
    "search_code", "get_project_context",
})
# 写入类：修改文件 / 写入记忆 —— readonly 禁止，default 可用
WRITE_TOOLS = frozenset({
    "write_file", "remember",
})
# 执行 / 网络类：跑命令 / 联网搜索 / 装包 —— readonly 与 default 都禁止，full 才可用
EXECUTE_TOOLS = frozenset({
    "run_command", "run_cmd", "pip_install", "web_search",
})

PERMISSION_LEVELS = ("readonly", "default", "full")

_TOOL_CALL_RE = re.compile(r"\[\[tool:(\w+)([^\]]*)\]\]")


def _classify_tool(tool_name: str) -> str:
    """返回工具类别：readonly / write / execute / unknown。"""
    try:
        if tool_name in READONLY_TOOLS:
            return "readonly"
        if tool_name in WRITE_TOOLS:
            return "write"
        if tool_name in EXECUTE_TOOLS:
            return "execute"
        # MCP 工具或未登记工具默认归入 execute（最保守）
        if tool_name.startswith("mcp__"):
            return "execute"
        return "unknown"
    except Exception:
        return "unknown"


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
    tool_calls: List[Dict] = field(default_factory=list)
    history: List[Dict] = field(default_factory=list)


class SubAgent:
    """拥有独立工具集和权限模型的子 Agent。

    参数
    ----
    agent_id : str
        子 Agent 唯一标识。
    engine : object, optional
        对话引擎（需有 ``chat`` 方法）。为 None 时所有执行返回错误状态。
    tool_names : list[str], optional
        工具白名单。``None`` 表示全部工具（受权限级别约束）；
        ``[]`` 表示无工具（只能对话）。
    permission_level : str
        权限级别：``"readonly"``（只读）、``"default"``（可读写文件）、
        ``"full"``（可执行命令 / 联网）。
    toolkit : object, optional
        主 ToolKit 实例，用于实际执行工具调用。若不传则尝试从 engine.toolkit 获取。
    max_steps : int
        多步执行最大步数，默认 5。
    """

    def __init__(self, agent_id: str, engine=None,
                 tool_names: Optional[List[str]] = None,
                 permission_level: str = "default",
                 toolkit=None,
                 max_steps: int = 5):
        self.id = agent_id
        self.engine = engine
        # tool_names=None → 全部工具；tool_names=[] → 无工具
        self.tool_names: Optional[List[str]] = (
            list(tool_names) if tool_names is not None else None
        )
        self.permission_level = (
            permission_level if permission_level in PERMISSION_LEVELS else "default"
        )
        self._toolkit = toolkit
        self.max_steps = max(1, int(max_steps or 5))
        self.context: List[Dict] = []       # 独立上下文（不与主 Agent 共享）
        self.tasks: Dict[str, SubAgentTask] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # toolkit 获取（优先构造参数，其次 engine.toolkit）
    # ------------------------------------------------------------------
    @property
    def toolkit(self):
        try:
            if self._toolkit is not None:
                return self._toolkit
            if self.engine is not None and hasattr(self.engine, "toolkit"):
                return self.engine.toolkit
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # 权限检查
    # ------------------------------------------------------------------
    def _check_permission(self, tool_name: str) -> Optional[str]:
        """返回 None 表示允许执行；否则返回错误消息字符串。"""
        try:
            # 1) 白名单检查
            if self.tool_names is not None and tool_name not in self.tool_names:
                return f"权限不足：工具「{tool_name}」不在子 Agent 工具白名单中"

            # 2) 权限级别检查
            category = _classify_tool(tool_name)
            if self.permission_level == "readonly":
                if category in ("write", "execute"):
                    need = "default" if category == "write" else "full"
                    return f"权限不足：该工具需要 {need} 权限（当前为 readonly）"
            elif self.permission_level == "default":
                if category == "execute":
                    return f"权限不足：该工具需要 full 权限（当前为 default）"
            # full → 全部放行
            return None
        except Exception as e:
            return f"权限检查异常：{type(e).__name__}: {e}"

    # ------------------------------------------------------------------
    # 工具执行（经权限拦截）
    # ------------------------------------------------------------------
    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        try:
            error = self._check_permission(name)
            if error:
                return error
            tk = self.toolkit
            if tk is None:
                return "工具不可用：ToolKit 未加载"
            # 优先用 execute_tool（Agent 工具集），回退到 execute（基础工具）
            if hasattr(tk, "execute_tool"):
                return str(tk.execute_tool(name, args))
            if hasattr(tk, "execute"):
                return str(tk.execute(name, args))
            return "工具不可用：ToolKit 无 execute 方法"
        except Exception as e:
            return f"工具执行异常：{type(e).__name__}: {e}"

    # ------------------------------------------------------------------
    # 工具调用解析（与 engine.extract_tool_calls 同格式）
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_tool_calls(text: str) -> tuple:
        try:
            calls = []
            for m in _TOOL_CALL_RE.finditer(text or ""):
                args = {}
                rest = m.group(2).strip()
                if rest:
                    for part in rest.split("|"):
                        if "=" in part:
                            k, v = part.split("=", 1)
                            args[k.strip()] = v.strip()
                calls.append({"name": m.group(1), "args": args})
            clean = _TOOL_CALL_RE.sub("", text or "").strip()
            return clean, calls
        except Exception:
            return (text or ""), []

    # ------------------------------------------------------------------
    # 上下文 → prompt 构建
    # ------------------------------------------------------------------
    def _build_prompt(self) -> str:
        try:
            parts = []
            # 系统提示：告知子 Agent 可用工具与权限
            available = self._available_tool_text()
            parts.append(
                f"[子Agent #{self.id}]\n"
                f"权限级别：{self.permission_level}\n"
                f"可用工具：{available}\n"
                f"如需调用工具，请使用 [[tool:工具名|参数=值]] 格式。"
            )
            # 上下文轮次
            for turn in self.context[-20:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role == "user":
                    parts.append(f"用户: {content}")
                elif role == "assistant":
                    parts.append(f"助手: {content}")
                elif role == "tool_result":
                    parts.append(f"工具结果: {content}")
            return "\n".join(parts)
        except Exception:
            # 构建失败时退化为直接返回最后一条用户消息
            try:
                for t in reversed(self.context):
                    if t.get("role") == "user":
                        return t.get("content", "")
            except Exception:
                pass
            return ""

    def _available_tool_text(self) -> str:
        try:
            if self.tool_names is not None and len(self.tool_names) == 0:
                return "（无工具，只能对话）"
            if self.tool_names is not None:
                return ", ".join(self.tool_names)
            # 全部工具但受权限约束 → 列出当前级别允许的工具
            allowed = []
            for t in sorted(READONLY_TOOLS | WRITE_TOOLS | EXECUTE_TOOLS):
                if self._check_permission(t) is None:
                    allowed.append(t)
            return ", ".join(allowed) if allowed else "（无可用工具）"
        except Exception:
            return "未知"

    def _context_summary(self) -> str:
        try:
            lines = []
            for t in self.context[-10:]:
                role = t.get("role", "?")
                content = (t.get("content", "") or "")[:60]
                lines.append(f"{role}: {content}")
            return "\n".join(lines)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # 多步执行循环
    # ------------------------------------------------------------------
    def run(self, task: str) -> Dict[str, Any]:
        """执行任务，支持多步 LLM 规划 → 工具调用 → 结果反馈循环。

        返回 ``{status, result, tool_calls, context_summary}``。
        """
        if not self.engine or not hasattr(self.engine, "chat"):
            return {
                "status": "error",
                "error": "子Agent执行失败：引擎未加载",
                "result": "",
                "tool_calls": [],
                "context_summary": "",
            }

        self.context = [{"role": "user", "content": task}]
        all_tool_calls: List[Dict] = []
        final_reply = ""

        try:
            for step in range(self.max_steps):
                prompt = self._build_prompt()
                # 调用引擎
                raw = self.engine.chat(prompt)
                reply_text = ""
                try:
                    if isinstance(raw, (tuple, list)):
                        reply_text = str(raw[0]) if raw else ""
                    elif hasattr(raw, "text"):
                        reply_text = str(raw.text)
                    else:
                        reply_text = str(raw)
                except Exception:
                    reply_text = ""

                # 提取工具调用
                clean_reply, tool_calls = self._extract_tool_calls(reply_text)
                self.context.append({"role": "assistant", "content": clean_reply})

                if not tool_calls:
                    final_reply = clean_reply
                    break

                # 执行工具调用（每个都经权限检查）
                tool_results = []
                for tc in tool_calls:
                    all_tool_calls.append(tc)
                    name = tc.get("name", "")
                    args = tc.get("args", {}) or {}
                    out = self._execute_tool(name, args)
                    tool_results.append(f"[{name}] {out}")

                self.context.append({
                    "role": "tool_result",
                    "content": "\n".join(tool_results),
                })
            else:
                # 达到 max_steps
                final_reply = clean_reply + "\n（达到最大步数限制）"

            return {
                "status": "completed",
                "result": final_reply,
                "tool_calls": all_tool_calls,
                "context_summary": self._context_summary(),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "result": "",
                "tool_calls": all_tool_calls,
                "context_summary": self._context_summary(),
            }

    # ------------------------------------------------------------------
    # 向后兼容：delegate / _execute（后台线程方式）
    # ------------------------------------------------------------------
    def delegate(self, description: str, tools: Optional[List[str]] = None) -> str:
        """委派任务给子 Agent，返回 task_id（后台异步执行）。"""
        task_id = str(uuid.uuid4())[:8]
        task = SubAgentTask(id=task_id, description=description)
        with self._lock:
            self.tasks[task_id] = task
        threading.Thread(target=self._execute, args=(task, tools), daemon=True).start()
        return task_id

    def _execute(self, task: SubAgentTask, tools: Optional[List[str]] = None):
        """执行子任务：优先走多步 run()，引擎未加载时返回错误状态。"""
        task.status = "running"
        task.events.append({
            "type": "start",
            "content": f"子 Agent 开始执行: {task.description}"
        })
        try:
            if not (self.engine and hasattr(self.engine, "chat")):
                task.status = "failed"
                task.error = "子Agent执行失败：引擎未加载"
                task.events.append({"type": "error", "content": task.error})
                return

            # 临时覆盖 tools 参数（如果 delegate 传入了）
            saved_whitelist = self.tool_names
            if tools is not None:
                self.tool_names = list(tools)

            try:
                result = self.run(task.description)
            finally:
                if tools is not None:
                    self.tool_names = saved_whitelist

            task.tool_calls = result.get("tool_calls", [])
            task.history = list(self.context)

            if result.get("status") == "completed":
                task.result = result.get("result", "")
                task.progress = 100
                task.status = "completed"
                task.events.append({"type": "complete", "content": task.result[:500]})
            else:
                task.status = "failed"
                task.error = result.get("error", "未知错误")
                task.result = result.get("result", "")
                task.events.append({"type": "error", "content": task.error})
        except Exception as e:
            task.status = "failed"
            task.error = f"{type(e).__name__}: {e}"
            task.events.append({"type": "error", "content": task.error})
        finally:
            task.completed_at = time.time()

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------
    def get_task(self, task_id: str) -> Optional[SubAgentTask]:
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[Dict]:
        return [
            {
                "id": t.id,
                "description": t.description,
                "status": t.status,
                "progress": t.progress,
                "result": t.result[:200] if t.result else "",
                "created_at": t.created_at,
                "tool_calls": len(t.tool_calls),
            }
            for t in self.tasks.values()
        ]

    def status(self) -> Dict:
        """返回子 Agent 自身状态摘要。"""
        try:
            return {
                "id": self.id,
                "permission_level": self.permission_level,
                "tool_names": self.tool_names,
                "max_steps": self.max_steps,
                "context_len": len(self.context),
                "task_count": len(self.tasks),
                "toolkit_available": self.toolkit is not None,
            }
        except Exception:
            return {"id": self.id}


class SubAgentManager:
    """子 Agent 管理器：创建、委派、查询。"""

    def __init__(self, engine=None, toolkit=None):
        self.engine = engine
        self._toolkit = toolkit
        self.agents: Dict[str, SubAgent] = {}
        self._lock = threading.Lock()

    def create_agent(self, name: str = None,
                     tool_names: Optional[List[str]] = None,
                     permission_level: str = "default",
                     max_steps: int = 5) -> str:
        """创建子 Agent，返回 agent_id。"""
        agent_id = name or f"sub_{uuid.uuid4().hex[:6]}"
        try:
            agent = SubAgent(
                agent_id,
                engine=self.engine,
                tool_names=tool_names,
                permission_level=permission_level,
                toolkit=self._toolkit,
                max_steps=max_steps,
            )
        except Exception:
            # 兜底：用最简构造
            agent = SubAgent(agent_id, self.engine)
        with self._lock:
            self.agents[agent_id] = agent
        return agent_id

    def delegate(self, agent_id: str, description: str,
                 tools: Optional[List[str]] = None) -> str:
        """委派任务给指定子 Agent；不存在则自动创建。"""
        if agent_id not in self.agents:
            agent_id = self.create_agent(agent_id)
        return self.agents[agent_id].delegate(description, tools)

    def get_status(self, agent_id: str = None) -> Dict:
        """获取子 Agent 状态。"""
        if agent_id:
            agent = self.agents.get(agent_id)
            if agent:
                return {"agent_id": agent_id,
                        "tasks": agent.list_tasks(),
                        "config": agent.status()}
            return {"error": "agent not found"}
        return {
            "agents": [
                {"id": aid, "task_count": len(a.tasks),
                 "permission": a.permission_level}
                for aid, a in self.agents.items()
            ]
        }
