# -*- coding: utf-8 -*-
"""web_summarizer 插件

网页摘要：抓取 URL → 提取正文纯文本 → 生成摘要。
底层复用 backend/core/browser_tool.py 的 BrowserTool
（优先真实浏览器渲染 JS，不可用时明确降级 requests）。

摘要策略：按句切分后取前 N 句，截断到 max_length。
抓不到正文时返回明确错误，绝不编造内容。
"""
from __future__ import annotations

import re

try:
    from core.plugin_system import PluginBase
    from core.browser_tool import BrowserTool
except ImportError:  # requests / playwright 未装等情况在实例化时再判
    from backend.core.plugin_system import PluginBase
    try:
        from backend.core.browser_tool import BrowserTool
    except Exception:  # pragma: no cover - 环境缺 requests 等依赖
        BrowserTool = None


_SENT_SPLIT = re.compile(r"(?<=[。！？!?．.])\s+")


def _make_summary(text: str, max_length: int) -> str:
    """把长正文压缩为前若干句的摘要。"""
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    sentences = [s for s in _SENT_SPLIT.split(text) if s.strip()]
    out = ""
    for s in sentences:
        if len(out) + len(s) > max_length:
            break
        out += s
    if not out:  # 单行超长无标点：硬截断
        out = text[:max_length]
    return out.rstrip() + "…" if len(text) > max_length else out


class WebSummarizerPlugin(PluginBase):
    name = "web_summarizer"
    version = "0.0.1"
    description = "网页摘要：抓取 URL、提取正文、生成摘要"
    author = "xiaoling"
    category = "tool"
    permissions = ["network"]

    def init(self):
        self._tools = [
            {
                "name": "summarize_url",
                "description": "抓取指定 URL 并生成摘要，max_length 限制摘要长度",
                "args_schema": {"url": "string", "max_length": "int?"},
                "handler": self.summarize_url,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    def summarize_url(self, url: str = "", max_length: int = 500) -> dict:
        try:
            if not url:
                return {"ok": False, "error": "缺少参数 url"}
            if not str(url).startswith(("http://", "https://")):
                return {"ok": False, "error": "url 必须以 http:// 或 https:// 开头"}
            if BrowserTool is None:
                return {"ok": False,
                        "error": "浏览器工具不可用（缺少 requests 等依赖），无法抓取网页"}
            try:
                limit = int(max_length)
            except (TypeError, ValueError):
                limit = 500
            limit = max(50, min(limit, 5000))

            tool = BrowserTool(timeout=20)
            try:
                text = tool.get_text(str(url).strip())
                title = ""
                try:
                    title = tool._extract_title(tool.current_html or "")
                except Exception:
                    title = ""
            finally:
                try:
                    tool.close()
                except Exception:
                    pass

            if not text:
                return {"ok": False, "url": url,
                        "error": "未提取到正文（页面可能为空、需 JS 渲染但浏览器不可用，或网络失败）"}
            summary = _make_summary(text, limit)
            return {
                "ok": True,
                "url": url,
                "title": title,
                "content_length": len(text),
                "summary": summary,
                "summary_length": len(summary),
            }
        except Exception as e:
            return {"ok": False, "error": "summarize_url 失败: {}: {}".format(type(e).__name__, e)}
