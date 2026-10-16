#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子 Agent（backend/core/sub_agent.py）单元测试。

覆盖：
  1. 无引擎时 run() 返回结构化错误
  2. 权限拦截：readonly 拒绝 write / execute 类工具
  3. 工具白名单过滤
  4. 多步工具调用循环与结构化返回格式
  5. 工具调用标记解析、工具分类

引擎只伪造 chat() 的返回文本（外部边界），权限检查 / 循环 / 解析都是被测真代码。
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

from backend.core.sub_agent import SubAgent, _classify_tool


class FakeToolkit:
    def __init__(self):
        self.calls = []

    def execute_tool(self, name, args):
        self.calls.append((name, args))
        return f"result:{name}"


class ScriptEngine:
    """按脚本依次返回 chat 回复（模拟 LLM 逐步产出）。"""

    def __init__(self, replies):
        self.replies = list(replies)
        self.i = 0

    def chat(self, prompt):
        out = self.replies[min(self.i, len(self.replies) - 1)]
        self.i += 1
        return out


# ---------------------------------------------------------------------------
# 1. 无引擎
# ---------------------------------------------------------------------------
def test_subagent_no_engine_returns_error():
    sa = SubAgent("t_noengine", engine=None)
    r = sa.run("随便做件事")
    assert r["status"] == "error"
    assert "引擎" in r["error"]
    assert r["result"] == "" and r["tool_calls"] == []


# ---------------------------------------------------------------------------
# 2. 权限拦截
# ---------------------------------------------------------------------------
def test_subagent_readonly_blocks_write_tool():
    sa = SubAgent("t_ro", engine=ScriptEngine(["x"]),
                  permission_level="readonly", toolkit=FakeToolkit())
    out = sa._execute_tool("write_file", {"path": "a.py"})
    assert "权限不足" in out
    assert "default" in out


def test_subagent_readonly_blocks_execute_tool():
    sa = SubAgent("t_ro2", engine=ScriptEngine(["x"]),
                  permission_level="readonly", toolkit=FakeToolkit())
    out = sa._execute_tool("run_command", {"cmd": "ls"})
    assert "full" in out


def test_subagent_readonly_allows_read_tool():
    tk = FakeToolkit()
    sa = SubAgent("t_ro3", engine=ScriptEngine(["x"]),
                  permission_level="readonly", toolkit=tk)
    out = sa._execute_tool("read_file", {"path": "a.py"})
    assert out == "result:read_file", "read_file 在 readonly 下应放行"


# ---------------------------------------------------------------------------
# 3. 工具白名单
# ---------------------------------------------------------------------------
def test_subagent_whitelist_filters_tool():
    sa = SubAgent("t_wl", engine=ScriptEngine(["x"]),
                  tool_names=["read_file"], permission_level="full",
                  toolkit=FakeToolkit())
    assert "白名单" in sa._check_permission("write_file")
    assert sa._check_permission("read_file") is None


# ---------------------------------------------------------------------------
# 4. 结构化返回 + 多步循环
# ---------------------------------------------------------------------------
def test_subagent_plain_reply_returns_structured():
    sa = SubAgent("t_plain", engine=ScriptEngine(["这是最终回复"]),
                  permission_level="full", toolkit=FakeToolkit())
    r = sa.run("给我个回复")
    assert r["status"] == "completed"
    assert r["result"] == "这是最终回复"
    for key in ("status", "result", "tool_calls", "context_summary"):
        assert key in r
    assert r["tool_calls"] == []


def test_subagent_tool_call_loop_records_calls():
    tk = FakeToolkit()
    sa = SubAgent("t_loop", engine=ScriptEngine([
        "先读文件 [[tool:read_file|path=a.py]]",
        "读完了，给你结论",
    ]), permission_level="full", toolkit=tk)
    r = sa.run("读 a.py")
    assert r["status"] == "completed"
    names = [tc["name"] for tc in r["tool_calls"]]
    assert "read_file" in names
    assert any("read_file" in c[0] for c in tk.calls)


# ---------------------------------------------------------------------------
# 5. 分类与解析（纯函数）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tool,cat", [
    ("read_file", "readonly"), ("list_dir", "readonly"),
    ("write_file", "write"), ("remember", "write"),
    ("run_command", "execute"), ("web_search", "execute"),
    ("mcp__whatever", "execute"), ("unknown_tool", "unknown"),
])
def test_subagent_classify_tool(tool, cat):
    assert _classify_tool(tool) == cat


def test_subagent_extract_tool_calls():
    clean, calls = SubAgent._extract_tool_calls(
        '先查一下 [[tool:search_code|query=foo|max=5]] 再决定')
    assert calls == [{"name": "search_code",
                      "args": {"query": "foo", "max": "5"}}]
    assert "[[tool:" not in clean


def test_subagent_status_summary():
    sa = SubAgent("t_st", engine=ScriptEngine(["x"]), permission_level="default")
    st = sa.status()
    assert st["id"] == "t_st"
    assert st["permission_level"] == "default"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
