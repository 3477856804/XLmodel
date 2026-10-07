"""小凌 · Agent 自主任务执行框架（AgentEngine）
==========================================

AgentEngine.run(task, context, autonomous, max_steps) 是一个生成器，
逐步产出事件流：
  * type="plan"       : 第一步，给出计划步数 total_steps
  * type="thought"    : 当前思考
  * type="tool_call"   : 即将调用的工具名与参数
  * type="tool_result" : 工具返回结果
  * type="message"    : 中间文本消息
  * type="error"       : 异常
  * type="done"        : 任务结束（done=True）

若 engine 具备真实 LLM（engine.chat），则优先用它生成计划与思考；
否则退化为规则-based 规划（按关键词匹配工具）。
工具统一通过 engine.tools.execute_tool(name, args) 调用。
"""
from __future__ import annotations


class AgentEngine:
    """自主任务执行框架：解析任务 -> 计划 -> 循环调用工具 -> 总结。"""

    def __init__(self, engine=None):
        self.engine = engine
        # Agent 可用工具名（与 ToolKit.agent_tools 对应）
        self.tools = [
            "read_file", "write_file", "list_dir", "search_code",
            "run_command", "web_search", "get_project_context",
        ]

    # ------------------------------------------------------------- llm helper
    def _has_llm(self) -> bool:
        return self.engine is not None and hasattr(self.engine, "chat") \
            and callable(getattr(self.engine, "chat", None))

    def _llm_think(self, prompt: str) -> str:
        """调用 engine.chat 生成一段思考文本；失败返回空串。"""
        if not self._has_llm():
            return ""
        try:
            out = self.engine.chat(prompt)
            if isinstance(out, (tuple, list)):
                out = out[0] if out else ""
            return str(out).strip()
        except Exception:  # noqa: BLE001
            return ""

    # ------------------------------------------------------------- planning
    def _plan(self, task: str) -> list:
        """根据任务生成步骤列表，每步 = {thought, tool, args}。规则-based。"""
        t = task or ""
        steps = []

        # 1) 先获取项目上下文（若任务与项目/代码相关）
        if any(k in t for k in ("项目", "代码", "文件", "目录", "结构", "工程")):
            steps.append({
                "thought": "先了解一下项目整体结构与上下文",
                "tool": "get_project_context", "args": {},
            })

        # 2) 关键词 -> 工具映射
        if any(k in t for k in ("搜索", "查找资料", "联网", "新闻", "web")):
            # 提取查询词（去掉动词）
            query = t
            for v in ("帮我", "搜索", "查一下", "查找", "联网", "搜索一下"):
                query = query.replace(v, "")
            steps.append({
                "thought": "需要联网检索相关信息",
                "tool": "web_search", "args": {"query": query.strip() or t},
            })

        if any(k in t for k in ("代码", "函数", "类", "定义", "search_code", "找代码")):
            query = t
            for v in ("帮我", "找", "查找", "代码", "函数", "类", "定义"):
                query = query.replace(v, "")
            steps.append({
                "thought": "在代码库中搜索相关符号 / 引用",
                "tool": "search_code", "args": {"query": query.strip() or t,
                                                "max_results": 30},
            })

        if any(k in t for k in ("列目录", "看目录", "列出", "ls ", "dir")):
            steps.append({
                "thought": "列出目录内容看看",
                "tool": "list_dir", "args": {"path": "."},
            })

        if any(k in t for k in ("读取文件", "读文件", "打开文件", "read file")):
            steps.append({
                "thought": "读取目标文件内容",
                "tool": "read_file", "args": {"path": "."},
            })

        if any(k in t for k in ("运行", "执行", "跑一下", "run ", "execute")):
            # 尝试提取命令：去掉动词后的内容作为 cmd
            cmd = t
            for v in ("帮我", "运行", "执行", "跑一下", "运行一下"):
                cmd = cmd.replace(v, "")
            steps.append({
                "thought": "执行 shell 命令",
                "tool": "run_command", "args": {"cmd": cmd.strip() or "echo done"},
            })

        # 兜底：若没有任何规则命中，尝试用 LLM 规划；否则做一次上下文收集
        if not steps:
            llm_plan = self._llm_think(
                f"请为任务「{t}」决定第一步该调用哪个工具"
                f"（read_file/write_file/list_dir/search_code/run_command/"
                f"web_search/get_project_context）。只回答工具名。")
            if llm_plan and any(tool in llm_plan for tool in self.tools):
                for tool in self.tools:
                    if tool in llm_plan:
                        steps.append({"thought": "根据判断选择合适的工具",
                                      "tool": tool, "args": {}})
                        break
            else:
                steps.append({
                    "thought": "没有明确的工具线索，先收集项目上下文",
                    "tool": "get_project_context", "args": {},
                })
        return steps

    # ------------------------------------------------------------- toolkit access
    def _toolkit(self):
        """获取 engine 上的工具包（tools 或 toolkit 别名）。"""
        if self.engine is None:
            return None
        tk = getattr(self.engine, "tools", None)
        if tk is None:
            tk = getattr(self.engine, "toolkit", None)
        return tk

    # ------------------------------------------------------------------ run
    def run(self, task: str, context: str = "", autonomous: bool = True,
            max_steps: int = 20):
        """生成器：逐步执行任务，产出事件 dict。"""
        step = 0
        total_steps = 0
        try:
            # 第一步：规划
            try:
                steps = self._plan(task)
            except Exception as e:  # noqa: BLE001
                steps = [{"thought": "规划失败，直接尝试",
                          "tool": "get_project_context", "args": {}}]
            total_steps = max(1, len(steps))
            yield {
                "type": "plan",
                "content": f"共规划 {total_steps} 个步骤：" +
                           " -> ".join(s["tool"] for s in steps),
                "step": 0, "total_steps": total_steps,
                "done": False, "error": "",
                "tool_name": "", "tool_args": {}, "tool_result": "",
            }

            tk = self._toolkit()
            if tk is None or not hasattr(tk, "execute_tool"):
                yield {"type": "error", "content": "工具包未就绪（缺少 execute_tool）",
                       "step": step, "total_steps": total_steps,
                       "done": False, "error": "no toolkit",
                       "tool_name": "", "tool_args": {}, "tool_result": ""}
                return

            for i, s in enumerate(steps, 1):
                if step >= max_steps:
                    yield {"type": "message",
                           "content": f"已达到最大步数 {max_steps}，停止执行",
                           "step": step, "total_steps": total_steps,
                           "done": False, "error": "",
                           "tool_name": "", "tool_args": {}, "tool_result": ""}
                    break
                step = i
                thought = s.get("thought", "")
                if self._has_llm():
                    extra = self._llm_think(
                        f"任务：{task}\n当前第 {i}/{total_steps} 步，"
                        f"即将调用 {s['tool']}。用一句话说明你的思考。")
                    if extra:
                        thought = thought + " | " + extra
                # thought 事件
                yield {
                    "type": "thought", "content": thought,
                    "step": step, "total_steps": total_steps,
                    "done": False, "error": "",
                    "tool_name": s["tool"], "tool_args": s["args"],
                    "tool_result": "",
                }
                # tool_call 事件
                yield {
                    "type": "tool_call", "content": "",
                    "step": step, "total_steps": total_steps,
                    "done": False, "error": "",
                    "tool_name": s["tool"], "tool_args": s["args"],
                    "tool_result": "",
                }
                # 执行工具
                try:
                    result = tk.execute_tool(s["tool"], s["args"])
                except Exception as e:  # noqa: BLE001
                    result = f"工具调用异常：{type(e).__name__}: {e}"
                # tool_result 事件
                yield {
                    "type": "tool_result", "content": "",
                    "step": step, "total_steps": total_steps,
                    "done": False, "error": "",
                    "tool_name": s["tool"], "tool_args": s["args"],
                    "tool_result": str(result)[:2000],
                }

            # 结束
            summary = f"任务「{task[:40]}」执行完成，共 {step} 步。"
            if self._has_llm():
                s2 = self._llm_think(f"请总结任务「{task[:60]}」的执行结果。")
                if s2:
                    summary = s2
            yield {
                "type": "done", "content": summary,
                "step": step, "total_steps": total_steps,
                "done": True, "error": "",
                "tool_name": "", "tool_args": {}, "tool_result": "",
            }
        except Exception as e:  # noqa: BLE001
            yield {
                "type": "error", "content": f"Agent 执行异常：{type(e).__name__}: {e}",
                "step": step, "total_steps": total_steps,
                "done": False, "error": f"{type(e).__name__}: {e}",
                "tool_name": "", "tool_args": {}, "tool_result": "",
            }
