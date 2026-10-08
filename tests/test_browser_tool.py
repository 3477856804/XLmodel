#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""浏览器工具（backend/core/browser_tool.py）单元测试。

覆盖降级路径（无可用 Playwright 内核时）——这是该模块最重要的设计承诺：
真实浏览器不可用时诚实降级，绝不假装能渲染 JS。
  1. 降级标志位：_is_browser_ready / _ensure_browser
  2. 交互方法（click/fill/evaluate/screenshot）在降级时返回不可用
  3. render 的 requests fallback（仅桩掉 HTTP 网络边界，渲染分支为真实代码）
  4. 纯解析逻辑（title / links / text 提取）

网络边界用 FakeResponse 桩掉，其余均为被测真实代码，不需要真实网络与浏览器。
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

from backend.core.browser_tool import BrowserTool


class FakeResp:
    """模拟 requests.Response，仅提供 render 用到的字段。"""

    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


@pytest.fixture
def degraded_bt():
    """构造一个明确处于降级态的 BrowserTool（无真实浏览器）。"""
    bt = BrowserTool()
    bt._pw_failed = True      # 模拟「playwright 内核不可用」
    bt._browser = None
    bt._page = None
    return bt


# ---------------------------------------------------------------------------
# 1. 降级标志
# ---------------------------------------------------------------------------
def test_browser_degraded_not_ready(degraded_bt):
    assert degraded_bt._is_browser_ready() is False
    assert degraded_bt._ensure_browser() is False


# ---------------------------------------------------------------------------
# 2. 交互方法降级返回错误
# ---------------------------------------------------------------------------
def test_browser_screenshot_returns_empty_when_degraded(degraded_bt):
    assert degraded_bt.screenshot("http://x", "/tmp/x.png") == ""


def test_browser_interactive_methods_return_error(degraded_bt):
    for call in (lambda: degraded_bt.click("a"),
                 lambda: degraded_bt.fill("input", "hi"),
                 lambda: degraded_bt.evaluate("1+1")):
        r = call()
        assert r["ok"] is False
        assert "活动页面" in r["error"] or "浏览器" in r["error"]


# ---------------------------------------------------------------------------
# 3. render 的 requests fallback（仅桩掉 session.get 网络边界）
# ---------------------------------------------------------------------------
def test_browser_render_uses_requests_fallback(degraded_bt, monkeypatch):
    html = "<html><title>Test</title><body>hello</body></html>"
    monkeypatch.setattr(
        degraded_bt.session, "get",
        lambda url, timeout=None: FakeResp(html, 200))
    out = degraded_bt.render("http://example.com")
    assert out == html
    assert degraded_bt.current_url == "http://example.com"
    assert degraded_bt.last_status == 200
    # 降级模式下不是真实浏览器渲染
    assert degraded_bt._is_browser_ready() is False


def test_browser_navigate_degraded_reports_not_rendered(degraded_bt, monkeypatch):
    monkeypatch.setattr(
        degraded_bt.session, "get",
        lambda url, timeout=None: FakeResp("<html><title>P</title></html>"))
    r = degraded_bt.navigate("http://example.com")
    assert r["ok"] is True
    assert r["rendered"] is False, "requests 路径不应宣称真实浏览器渲染"
    assert r["title"] == "P"


# ---------------------------------------------------------------------------
# 4. 纯解析逻辑
# ---------------------------------------------------------------------------
def test_browser_extract_title(degraded_bt):
    assert degraded_bt._extract_title("<title>  My  Page </title>") == "My Page"
    assert degraded_bt._extract_title("<html>no title</html>") == ""


def test_browser_get_links(degraded_bt):
    degraded_bt.current_url = "http://example.com/base/"
    degraded_bt.current_html = (
        '<a href="/page1">Page One</a>'
        '<a href="https://elsewhere.com/x">X</a>'
        '<a href="#anchor">Anchor</a>')
    links = degraded_bt.get_links()
    texts = {l["text"] for l in links}
    assert "Page One" in texts
    assert any(l["href"].startswith("http://example.com/page1") for l in links)


def test_browser_get_text_strips_tags(degraded_bt):
    degraded_bt.current_html = (
        "<html><style>.a{}</style><script>var x=1;</script>"
        "<body>Hello <b>World</b></body></html>")
    text = degraded_bt.get_text()
    assert "Hello" in text and "World" in text
    assert "script" not in text.lower() and ".a" not in text


# ---------------------------------------------------------------------------
# 工具定义与未知工具
# ---------------------------------------------------------------------------
def test_browser_get_tools_count(degraded_bt):
    tools = degraded_bt.get_tools()
    names = {t["name"] for t in tools}
    assert "browser_navigate" in names and "browser_screenshot" in names
    assert len(tools) >= 6


def test_browser_execute_unknown_tool(degraded_bt):
    out = degraded_bt.execute_tool("no_such_tool", {})
    assert out.startswith("Unknown tool")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
