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

规划策略（核心原则：有 LLM 就用 LLM 自主规划，没有就降级规则匹配，
绝不假装能自主规划）：
  1. 优先 _plan_with_llm(task)：调用 engine.chat()，让 LLM 把任务拆解为
     JSON 步骤数组（thought / tool / args），支持多步推理与复杂任务。
  2. LLM 不可用、返回无效 JSON、或计划里出现不存在的工具时，整体降级到
     _plan(task) —— 即原来的规则-based 关键词匹配，作为 fallback 永久保留。
执行：
  *_execute_plan(steps, task, tk, max_steps, state) 按顺序执行每个步骤，
  上一步的工具结果会累积为上下文传给下一步思考；单步工具失败只记录不中止；
  计划步数上限 MAX_PLAN_STEPS，防止无限循环。
工具统一通过 engine.tools.execute_tool(name, args) 调用。
"""
from __future__ import annotations

import json


class AgentEngine:
    """自主任务执行框架：解析任务 -> 计划 -> 循环调用工具 -> 总结。"""

    #: LLM 单次规划最多拆出多少步（防无限循环 / 防超长计划）
    MAX_PLAN_STEPS = 10

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

    # ------------------------------------------------------------- toolkit access
    def _toolkit(self):
        """获取 engine 上的工具包（tools 或 toolkit 别名）。"""
        if self.engine is None:
            return None
        tk = getattr(self.engine, "tools", None)
        if tk is None:
            tk = getattr(self.engine, "toolkit", None)
        return tk

    def _tool_catalog(self) -> list:
        """收集 Agent 可调用工具的 {name, description} 列表。

        优先用 ToolKit.agent_tools()（带参数 schema，与 execute_tool 分发一致）；
        取不到时退回 ToolManager.list_tools()；再不行就用内置 self.tools 兜底。
        任何一步异常都降级，绝不因为取工具列表而炸掉规划。
        """
        catalog = []
        try:
            tk = self._toolkit()
            # 1) ToolKit.agent_tools() -> [{name, description, args}]
            if tk is not None and hasattr(tk, "agent_tools"):
                for t in tk.agent_tools():
                    name = t.get("name") if isinstance(t, dict) else None
                    desc = t.get("description") if isinstance(t, dict) else ""
                    if name:
                        catalog.append({"name": str(name),
                                        "description": str(desc or "")})
        except Exception:  # noqa: BLE001
            catalog = []
        if catalog:
            return catalog
        try:
            # 2) ToolManager.list_tools() -> [{name, desc, dangerous}]
            tk = self._toolkit()
            tm = getattr(tk, "tools", None) if tk is not None else None
            if tm is not None and hasattr(tm, "list_tools"):
                for t in tm.list_tools():
                    name = t.get("name") if isinstance(t, dict) else None
                    desc = t.get("desc") if isinstance(t, dict) else ""
                    if name:
                        catalog.append({"name": str(name),
                                        "description": str(desc or "")})
        except Exception:  # noqa: BLE001
            catalog = []
        if catalog:
            return catalog
        # 3) 内置兜底
        return [{"name": n, "description": ""} for n in self.tools]

    def _allowed_tool_names(self) -> set:
        """LLM 计划里允许出现的工具名集合（与执行端 execute_tool 对齐）。"""
        names = set(self.tools)
        try:
            for t in self._tool_catalog():
                names.add(t["name"])
        except Exception:  # noqa: BLE001
            pass
        return names

    # ------------------------------------------------------------- llm planning
    def _extract_json_array(self, text: str):
        """从 LLM 输出里容错地提取 JSON 数组。失败返回 None。

        容忍：```json 代码块包裹、前后多余文字、尾随逗号之外的小毛病。
        """
        if not text:
            return None
        s = str(text).strip()
        try:
            # 去掉 markdown 代码块围栏
            if s.startswith("```"):
                s = s.split("```", 2)
                s = s[1] if len(s) >= 2 else s[0]
                s = s.strip()
                if s.lower().startswith("json"):
                    s = s[4:].strip()
            # 截取第一个 [ 到最后一个 ]
            lo, hi = s.find("["), s.rfind("]")
            if lo == -1 or hi == -1 or hi <= lo:
                return None
            arr = json.loads(s[lo:hi + 1])
            return arr if isinstance(arr, list) else None
        except Exception:  # noqa: BLE001
            return None

    def _plan_with_llm(self, task: str):
        """让 LLM 自主把任务拆解为步骤 [{thought, tool, args}]。

        返回步骤列表；任何一步不合规（无 LLM / 无效 JSON / 未知工具）都返回
        None，由调用方降级到规则匹配。
        """
        if not self._has_llm() or not (task or "").strip():
            return None
        try:
            catalog = self._tool_catalog()
            tool_lines = "\n".join(
                f"- {t['name']}: {t['description']}".rstrip(": ")
                for t in catalog) or "- " + " / ".join(self.tools)
            prompt = (
                "你是一个任务规划Agent。请将以下任务拆解为步骤，"
                "每步包含thought（思考）、tool（工具名）、args（参数）。\n"
                f"可用工具：\n{tool_lines}\n"
                "只返回JSON数组，不要输出任何其他内容。格式示例：\n"
                '[{"thought":"先了解项目结构","tool":"get_project_context","args":{}},'
                '{"thought":"搜索关键词","tool":"search_code","args":{"query":"xxx"}}]\n'
                f"任务：{task}"
            )
            raw = self._llm_think(prompt)
            arr = self._extract_json_array(raw)
            if not arr:
                return None
            allowed = self._allowed_tool_names()
            steps = []
            for item in arr:
                if not isinstance(item, dict):
                    return None  # 结构不合规 -> 整体降级
                tool = item.get("tool")
                if not isinstance(tool, str) or not tool:
                    return None
                if tool not in allowed:
                    return None  # 调用了不存在的工具 -> 整体降级
                args = item.get("args")
                if not isinstance(args, dict):
                    args = {}
                steps.append({
                    "thought": str(item.get("thought", "") or ""),
                    "tool": tool,
                    "args": args,
                })
                if len(steps) >= self.MAX_PLAN_STEPS:
                    break
            return steps or None
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------- planning (rules fallback)
    def _plan(self, task: str) -> list:
        """根据任务生成步骤列表，每步 = {thought, tool, args}。规则-based。

        永久保留作为 LLM 不可用 / 规划失败时的 fallback，不删除、不改语义。
        """
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

    # ------------------------------------------------------------- execution loop
    def _execute_plan(self, steps: list, task: str, tk, max_steps: int,
                      state: dict):
        """按顺序执行计划里的每个步骤，逐步 yield 事件 dict。

        - 上一步的工具结果会累积进 state["contexts"]，作为下一步思考的上下文；
        - 单步工具执行失败只记录错误并继续（工具级错误不中止整个任务）；
        - state["step"] 记录已执行步数，供 run() 收尾使用。
        """
        total_steps = len(steps)
        contexts: list = state.get("contexts", [])
        for i, s in enumerate(steps, 1):
            if state.get("step", 0) >= max_steps or i > max_steps:
                yield {"type": "message",
                       "content": f"已达到最大步数 {max_steps}，停止执行",
                       "step": state.get("step", 0), "total_steps": total_steps,
                       "done": False, "error": "",
                       "tool_name": "", "tool_args": {}, "tool_result": ""}
                break
            state["step"] = i
            thought = s.get("thought", "") or ""
            # 把前面步骤的结果作为上下文传给下一步思考（LLM 可用时）
            if self._has_llm() and contexts:
                try:
                    ctx = "\n".join(
                        f"[第{j}步结果] {r}" for j, r in enumerate(contexts[-3:],
                                                                 start=max(1, i - len(contexts[-3:]))))
                    extra = self._llm_think(
                        f"任务：{task}\n已完成步骤结果：\n{ctx}\n"
                        f"当前第 {i}/{total_steps} 步，"
                        f"即将调用 {s['tool']}。用一句话说明你的思考。")
                    if extra:
                        thought = thought + " | " + extra
                except Exception:  # noqa: BLE001
                    pass
            # thought 事件
            yield {
                "type": "thought", "content": thought,
                "step": i, "total_steps": total_steps,
                "done": False, "error": "",
                "tool_name": s["tool"], "tool_args": s["args"],
                "tool_result": "",
            }
            # tool_call 事件
            yield {
                "type": "tool_call", "content": "",
                "step": i, "total_steps": total_steps,
                "done": False, "error": "",
                "tool_name": s["tool"], "tool_args": s["args"],
                "tool_result": "",
            }
            # 执行工具：失败只记录、继续下一步，不让整个任务崩掉
            try:
                result = tk.execute_tool(s["tool"], s["args"])
            except Exception as e:  # noqa: BLE001
                result = f"工具调用异常：{type(e).__name__}: {e}"
            try:
                contexts.append(str(result)[:500])
            except Exception:  # noqa: BLE001
                pass
            state["contexts"] = contexts
            # tool_result 事件
            yield {
                "type": "tool_result", "content": "",
                "step": i, "total_steps": total_steps,
                "done": False, "error": "",
                "tool_name": s["tool"], "tool_args": s["args"],
                "tool_result": str(result)[:2000],
            }

    # ------------------------------------------------------------------ run
    def run(self, task: str, context: str = "", autonomous: bool = True,
            max_steps: int = 20):
        """生成器：逐步执行任务，产出事件 dict。签名保持向后兼容。"""
        step = 0
        total_steps = 0
        try:
            # ---- 规划：优先 LLM 自主规划，失败降级规则匹配 ----
            steps = None
            plan_mode = "rules"
            try:
                steps = self._plan_with_llm(task)
                if steps:
                    plan_mode = "llm"
            except Exception:  # noqa: BLE001
                steps = None
            if not steps:
                try:
                    steps = self._plan(task)
                    plan_mode = "rules"
                except Exception as e:  # noqa: BLE001
                    steps = [{"thought": "规划失败，直接尝试",
                              "tool": "get_project_context", "args": {}}]
                    plan_mode = "rules"
            total_steps = max(1, len(steps))
            plan_desc = " -> ".join(s["tool"] for s in steps)
            yield {
                "type": "plan",
                "content": f"共规划 {total_steps} 个步骤（{plan_mode}）：{plan_desc}",
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

            # ---- 执行循环：按计划逐步跑，结果上下文在步骤间传递 ----
            state = {"step": 0, "contexts": []}
            try:
                for ev in self._execute_plan(steps, task, tk, max_steps, state):
                    yield ev
            except Exception as e:  # noqa: BLE001
                yield {"type": "error",
                       "content": f"执行循环异常：{type(e).__name__}: {e}",
                       "step": state.get("step", step),
                       "total_steps": total_steps,
                       "done": False,
                       "error": f"{type(e).__name__}: {e}",
                       "tool_name": "", "tool_args": {}, "tool_result": ""}
            step = state.get("step", step)

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
