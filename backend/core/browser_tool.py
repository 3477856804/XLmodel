import requests
import re
import json
import logging
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


class BrowserTool:
    """浏览器工具：网页获取、文本提取、链接提取、搜索"""

    def __init__(self, timeout=30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (compatible; XiaoLing/0.0.1)"}
        )
        self.current_url = None
        self.current_html = None

    def navigate(self, url: str) -> dict:
        """访问网页，返回 {url, title, status, content_length}"""
        try:
            resp = self.session.get(url, timeout=self.timeout)
            self.current_url = url
            self.current_html = resp.text
            title = self._extract_title(resp.text)
            return {
                "ok": True,
                "url": url,
                "title": title,
                "status": resp.status_code,
                "content_length": len(resp.text),
            }
        except Exception as e:
            logger.warning("navigate failed for %s: %s", url, e)
            return {"ok": False, "error": str(e)}

    def _extract_title(self, html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        if not m:
            return ""
        return re.sub(r"\s+", " ", m.group(1)).strip()

    def get_text(self) -> str:
        """提取当前网页纯文本（去除HTML标签）"""
        if not self.current_html:
            return ""
        text = re.sub(r"<script[^>]*>.*?</script>", "", self.current_html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]

    def get_links(self) -> list:
        """提取当前网页所有链接 [{text, href}]"""
        if not self.current_html:
            return []
        links = re.findall(
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            self.current_html,
            re.DOTALL | re.IGNORECASE,
        )
        result = []
        for href, text in links[:50]:
            clean_text = re.sub(r"<[^>]+>", "", text).strip()
            if clean_text and href.startswith(("http", "/", "#")):
                result.append(
                    {
                        "text": clean_text[:100],
                        "href": urljoin(self.current_url or "", href),
                    }
                )
        return result

    def search(self, query: str, num=10) -> list:
        """搜索网页（用 DuckDuckGo HTML 版）"""
        try:
            resp = self.session.get(
                f"https://html.duckduckgo.com/html/?q={query}",
                timeout=self.timeout,
            )
            results = re.findall(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                resp.text,
                re.DOTALL,
            )
            return [
                {"title": re.sub(r"<[^>]+>", "", t).strip(), "url": u}
                for u, t in results[:num]
            ]
        except Exception as e:
            logger.warning("search failed for %s: %s", query, e)
            return []

    def get_tools(self) -> list:
        """返回工具定义列表"""
        return [
            {"name": "browser_navigate", "description": "访问指定URL网页", "args": {"url": "string"}},
            {"name": "browser_get_text", "description": "获取当前网页纯文本内容", "args": {}},
            {"name": "browser_get_links", "description": "获取当前网页所有链接", "args": {}},
            {"name": "browser_search", "description": "搜索网页", "args": {"query": "string", "num": "int"}},
        ]

    def execute_tool(self, name: str, args: dict) -> str:
        """执行工具，返回结果字符串"""
        try:
            if name == "browser_navigate":
                return json.dumps(self.navigate(args.get("url", "")), ensure_ascii=False)
            elif name == "browser_get_text":
                return self.get_text()
            elif name == "browser_get_links":
                return json.dumps(self.get_links(), ensure_ascii=False)
            elif name == "browser_search":
                return json.dumps(
                    self.search(args.get("query", ""), args.get("num", 10)),
                    ensure_ascii=False,
                )
            return f"Unknown tool: {name}"
        except Exception as e:
            return f"Error: {e}"
