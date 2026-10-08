#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AgentEngine 单元测试。

覆盖 backend/core/agent.py 的核心路径（不依赖 torch / 模型 / 网络）：
  1. 无 LLM 时的规则匹配规划（_plan）
  2. LLM 规划 JSON 解析（正常 / 异常 / 围栏 JSON，_extract_json_array / _plan_with_llm）
  3. 执行循环（单步 / 多步 / 工具失败继续，run -> _execute_plan）
  4. 工具目录获取（_tool_catalog 三级降级）

引擎与工具包全部用轻量 fake 替身注入——只替换「外部依赖边界」（LLM 回复、
工具执行副作用），规划与执行循环本身是被测的真实代码。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.core.agent import AgentEngine


# ---------------------------------------------------------------------------
# 替身：只伪造「外部边界」——LLM 回复内容 / 工具执行的真实副作用
# ---------------------------------------------------------------------------
class FakeToolkit:
    """记录调用，并按名字返回预设结果（或抛异常）。"""

    def __init__(self, results=None):
        self.results = dict(results or {})
        self.calls = []

    def execute_tool(self, name, args):
        self.calls.append((name, args))
        v = self.results.get(name)
        if isinstance(v, Exception):
            raise v
        return v if v is not None else f"ok:{name}"


class FakeEngine:
    """有 tools（工具包）但 chat 可配：用来驱动 LLM 规划分支。"""

    def __init__(self, toolkit=None, chat_output="", chat_raises=False):
        self.tools = toolkit
        self._chat_output = chat_output
        self._chat_raises = chat_raises
        self.chat_calls = []

    def chat(self, prompt):
        self.chat_calls.append(prompt)
        if self._chat_raises:
            raise RuntimeError("chat boom")
        return self._chat_output


# ---------------------------------------------------------------------------
# 1. 规则匹配规划（无 LLM fallback）
# ---------------------------------------------------------------------------
def test_agent_plan_rule_run_command():
    """含「运行/执行」关键词 -> run_command 步骤。"""
    eng = AgentEngine(engine=None)
    steps = eng._plan("帮我运行 ls -la")
    assert any(s["tool"] == "run_command" for s in steps)
    step = next(s for s in steps if s["tool"] == "run_command")
    assert "ls" in step["args"].get("cmd", "")


def test_agent_plan_rule_web_search():
    """含「搜索」关键词 -> web_search 步骤。"""
    eng = AgentEngine(engine=None)
    steps = eng._plan("搜索一下今天的天气")
    assert any(s["tool"] == "web_search" for s in steps)


def test_agent_plan_rule_list_dir():
    """含「列目录」关键词 -> list_dir 步骤。"""
    eng = AgentEngine(engine=None)
    steps = eng._plan("帮我列目录看看")
    assert any(s["tool"] == "list_dir" for s in steps)


def test_agent_plan_falls_back_to_context():
    """无任何关键词命中 -> 兜底收集项目上下文。"""
    eng = AgentEngine(engine=None)
    steps = eng._plan("一个完全不相关的任务xyz")
    assert steps, "兜底也应至少产出一步"
    assert steps[-1]["tool"] == "get_project_context"


# ---------------------------------------------------------------------------
# 2. LLM JSON 解析（正常 / 异常 / 围栏）
# ---------------------------------------------------------------------------
def test_agent_extract_json_plain():
    raw = '[{"thought":"想","tool":"read_file","args":{"path":"a.py"}}]'
    arr = AgentEngine()._extract_json_array(raw)
    assert isinstance(arr, list) and len(arr) == 1
    assert arr[0]["tool"] == "read_file"


def test_agent_extract_json_fenced():
    """```json 代码块包裹的 JSON 数组应被正确提取。"""
    raw = '```json\n[{"thought":"x","tool":"list_dir","args":{}}]\n```'
    arr = AgentEngine()._extract_json_array(raw)
    assert arr and arr[0]["tool"] == "list_dir"


def test_agent_extract_json_with_surrounding_text():
    """前后多余文字不影响截取首个 [ 到末尾 ]。"""
    raw = '好的，计划如下：[{"tool":"web_search","args":{}}] 以上。'
    arr = AgentEngine()._extract_json_array(raw)
    assert arr and arr[0]["tool"] == "web_search"


@pytest.mark.parametrize("bad", ["", "   ", "没有JSON", "{}", "[1,2,3"])
def test_agent_extract_json_invalid(bad):
    """非法输入（空/纯文字/对象/非dict数组）一律返回 None。"""
    assert AgentEngine()._extract_json_array(bad) is None


# ---------------------------------------------------------------------------
# 2b. _plan_with_llm 整体规划
# ---------------------------------------------------------------------------
def test_agent_plan_with_llm_valid():
    """LLM 返回合法 JSON 且工具在白名单 -> 产出步骤。"""
    raw = '[{"thought":"a","tool":"read_file","args":{"path":"x"}},{"thought":"b","tool":"list_dir","args":{}}]'
    eng = AgentEngine(engine=FakeEngine(chat_output=raw))
    steps = eng._plan_with_llm("读一下文件")
    assert steps and len(steps) == 2
    assert [s["tool"] for s in steps] == ["read_file", "list_dir"]


def test_agent_plan_with_llm_invalid_json():
    """LLM 返回无效 JSON -> 返回 None，交由调用方降级规则。"""
    eng = AgentEngine(engine=FakeEngine(chat_output="我觉得应该先随便看看"))
    assert eng._plan_with_llm("做件事") is None


def test_agent_plan_with_llm_unknown_tool():
    """计划里出现不存在的工具 -> 整体降级（返回 None）。"""
    raw = '[{"thought":"a","tool":"nonexistent_tool_xyz","args":{}}]'
    eng = AgentEngine(engine=FakeEngine(chat_output=raw))
    assert eng._plan_with_llm("做件事") is None


def test_agent_plan_with_llm_no_engine():
    """无引擎 -> 直接 None。"""
    assert AgentEngine(engine=None)._plan_with_llm("做件事") is None


# ---------------------------------------------------------------------------
# 3. 执行循环（单步 / 多步 / 失败继续 / 无工具包）
# ---------------------------------------------------------------------------
def test_agent_run_single_step():
    """规则规划单步任务：产出 plan/thought/tool_call/tool_result/done 事件流。"""
    tk = FakeToolkit()
    eng = AgentEngine(engine=FakeEngine(toolkit=tk))  # 无 chat -> 走规则
    events = list(eng.run("列目录看看", max_steps=5))
    types = [e["type"] for e in events]
    assert types[0] == "plan"
    assert types[-1] == "done" and events[-1]["done"] is True
    assert "tool_result" in types
    assert tk.calls, "工具应被真实调用"


def test_agent_run_multi_step():
    """一个任务命中多条规则 -> 多步顺序执行。"""
    tk = FakeToolkit()
    eng = AgentEngine(engine=FakeEngine(toolkit=tk))
    list(eng.run("帮我搜索资料并列目录", max_steps=10))
    tools_called = [name for name, _ in tk.calls]
    assert "web_search" in tools_called
    assert "list_dir" in tools_called


def test_agent_run_tool_failure_continues():
    """单步工具抛异常：只记录错误，不中止整个任务，最终仍 done。"""
    tk = FakeToolkit(results={"list_dir": RuntimeError("boom")})
    eng = AgentEngine(engine=FakeEngine(toolkit=tk))
    events = list(eng.run("帮我列目录看看", max_steps=5))
    assert events[-1]["type"] == "done", "工具失败不应中断任务"
    result_events = [e for e in events if e["type"] == "tool_result"]
    assert result_events, "应有工具结果事件（即便失败）"


def test_agent_run_no_toolkit_reports_error():
    """engine=None -> 无工具包 -> 产出 error 事件而非抛异常。"""
    eng = AgentEngine(engine=None)
    events = list(eng.run("做点事"))
    assert any(e["type"] == "error" for e in events)


# ---------------------------------------------------------------------------
# 4. 工具目录获取
# ---------------------------------------------------------------------------
def test_agent_tool_catalog_builtin_fallback():
    """无 engine / 无工具包时，_tool_catalog 退回内置 7 个工具。"""
    catalog = AgentEngine(engine=None)._tool_catalog()
    names = {c["name"] for c in catalog}
    for n in ("read_file", "write_file", "list_dir", "search_code",
              "run_command", "web_search", "get_project_context"):
        assert n in names


def test_agent_tool_catalog_uses_toolkit():
    """engine.tools 带 agent_tools() 时优先采用它。"""
    class TKCatalog(FakeToolkit):
        def agent_tools(self):
            return [{"name": "custom_tool", "description": "自定义"}]

    tk = TKCatalog()
    eng = AgentEngine(engine=FakeEngine(toolkit=tk))
    catalog = eng._tool_catalog()
    names = {c["name"] for c in catalog}
    assert "custom_tool" in names


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
