import requests
import re
import json
import logging
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# ==========================================================================
# Playwright 可选依赖（真实浏览器渲染 JS / SPA）
# --------------------------------------------------------------------------
# 设计原则：有真实浏览器就用真实浏览器，没有就明确降级到 requests，
# 绝不假装支持 JS 渲染。
#   1) 包未安装        -> 导入失败，_PLAYWRIGHT_IMPORTED = False
#   2) 包已装但内核没下 -> chromium.launch() 失败，_ensure_browser() 捕获并降级
# 两种情况都把 self._pw_failed 置位，之后所有交互方法诚实返回
#「真实浏览器不可用」，不会静默走 requests 冒充渲染结果。
# ==========================================================================
try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    _PLAYWRIGHT_IMPORTED = True
except Exception as _import_err:  # pragma: no cover - 取决于运行环境
    sync_playwright = None
    _PLAYWRIGHT_IMPORTED = False
    logger.info(
        "playwright 未安装，浏览器 JS 渲染能力降级为 requests 方案: %s",
        _import_err,
    )


class BrowserTool:
    """浏览器工具：网页获取、JS 渲染、截图、交互、文本/链接提取、搜索。

    引擎策略（自动探测、绝不硬依赖）：
      - 首选 Playwright 真实 Chromium（可渲染 React/Vue/Angular 动态页面、可点击/输入/截图）
      - Playwright 不可用（包未装 / 内核未下载 / 启动失败）时，自动降级到 requests + 正则
    """

    def __init__(self, timeout=30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (compatible; XiaoLing/0.0.1)"}
        )
        self.current_url = None
        self.current_html = None
        self.last_status = None

        # ---- Playwright 真实浏览器引擎（懒启动，可选）----
        self._pw = None       # playwright 上下文
        self._browser = None  # chromium 实例
        self._page = None     # 当前活动页面（render/navigate 后保留，供 click/fill/evaluate）
        self._pw_failed = not _PLAYWRIGHT_IMPORTED  # 一旦确认不可用就不再重试

    # ------------------------------------------------------------------
    # 引擎管理
    # ------------------------------------------------------------------
    def _is_browser_ready(self) -> bool:
        """真实浏览器是否已就绪可用。已确认失败则直接返回 False。"""
        if self._pw_failed:
            return False
        return self._browser is not None

    def _ensure_browser(self) -> bool:
        """懒启动 Playwright + Chromium。任何一步失败都明确降级，返回 False。"""
        if self._pw_failed:
            return False
        if self._browser is not None:
            return True
        if not _PLAYWRIGHT_IMPORTED:
            self._pw_failed = True
            return False
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            logger.info("Playwright 真实浏览器已启动（JS 渲染可用）")
            return True
        except Exception as e:
            # 常见：内核未下载（Executable doesn't exist）、缺系统库等
            logger.warning(
                "Playwright 浏览器启动失败，明确降级为 requests 方案: %s", e
            )
            self._pw_failed = True
            self._shutdown_browser()
            return False

    def _shutdown_browser(self) -> None:
        """安全关闭浏览器资源，吞掉所有异常。"""
        try:
            if self._page is not None:
                self._page.close()
        except Exception:
            pass
        self._page = None
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        self._browser = None
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._pw = None

    def close(self) -> None:
        """释放浏览器资源（可在程序退出时调用）。"""
        self._shutdown_browser()

    # ------------------------------------------------------------------
    # 核心：渲染 / 抓取
    # ------------------------------------------------------------------
    def render(self, url: str, wait_seconds: float = 3) -> str:
        """用真实浏览器打开页面、等待 JS 渲染后返回完整 HTML。

        Playwright 不可用时降级到 requests 抓取原始 HTML（不渲染 JS）。
        无论走哪条路径，都会更新 current_url / current_html。
        """
        if self._ensure_browser():
            try:
                self._close_page()
                self._page = self._browser.new_page()
                resp_obj = self._page.goto(
                    url, timeout=self.timeout * 1000, wait_until="load"
                )
                try:
                    # 给 SPA 框架留出渲染时间
                    self._page.wait_for_timeout(max(0, int(wait_seconds * 1000)))
                except Exception:
                    pass
                html = self._page.content()
                self.current_url = self._page.url
                self.current_html = html
                self.last_status = resp_obj.status if resp_obj else None
                return html
            except Exception as e:
                logger.warning("playwright render 失败 %s，降级 requests: %s", url, e)
                self._close_page()

        # ---- 降级：requests 抓原始 HTML（无 JS 渲染）----
        try:
            resp = self.session.get(url, timeout=self.timeout)
            self.current_url = url
            self.current_html = resp.text
            self.last_status = resp.status_code
            return resp.text
        except Exception as e:
            logger.warning("requests 降级抓取也失败 %s: %s", url, e)
            self.current_url = url
            self.current_html = None
            self.last_status = None
            return ""

    def _close_page(self) -> None:
        try:
            if self._page is not None:
                self._page.close()
        except Exception:
            pass
        self._page = None

    def navigate(self, url: str) -> dict:
        """访问网页，返回 {url, title, status, content_length, rendered}。

        签名向后兼容；内部优先用真实浏览器渲染，不可用时降级 requests。
        """
        try:
            html = self.render(url)
            if not html:
                return {"ok": False, "url": url, "error": "empty content"}
            title = self._extract_title(html)
            return {
                "ok": True,
                "url": self.current_url or url,
                "title": title,
                "status": self.last_status or 200,
                "content_length": len(html),
                "rendered": self._is_browser_ready(),  # True=真实浏览器渲染，False=requests 原始 HTML
            }
        except Exception as e:
            logger.warning("navigate failed for %s: %s", url, e)
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # 截图与页面交互（仅真实浏览器可用；降级模式下诚实返回不可用）
    # ------------------------------------------------------------------
    def screenshot(self, url: str, path: str) -> str:
        """用真实浏览器截图保存到 path，成功返回路径，失败返回 ""。

        requests 方案无法截图——此时明确返回 ""，不做任何伪装。
        """
        if not self._ensure_browser():
            logger.warning("真实浏览器不可用，无法截图（requests 方案不支持截图）")
            return ""
        try:
            page = self._browser.new_page()
            page.goto(url, timeout=self.timeout * 1000, wait_until="load")
            try:
                page.wait_for_timeout(1500)
            except Exception:
                pass
            page.screenshot(path=path, full_page=True)
            page.close()
            return path
        except Exception as e:
            logger.warning("screenshot 失败 %s: %s", url, e)
            try:
                page.close()
            except Exception:
                pass
            return ""

    def click(self, selector: str) -> dict:
        """点击当前页面元素（需先 render/navigate 打开页面）。"""
        if not self._page:
            return {"ok": False, "error": "无活动页面：请先用 render(url) 打开页面（需真实浏览器）"}
        try:
            self._page.click(selector)
            self.current_html = self._page.content()
            return {"ok": True, "selector": selector}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def fill(self, selector: str, text: str) -> dict:
        """在当前页面输入框填入文本。"""
        if not self._page:
            return {"ok": False, "error": "无活动页面：请先用 render(url) 打开页面（需真实浏览器）"}
        try:
            self._page.fill(selector, text)
            self.current_html = self._page.content()
            return {"ok": True, "selector": selector}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def evaluate(self, js: str):
        """在当前页面执行 JS 并返回结果。"""
        if not self._page:
            return {"ok": False, "error": "无活动页面：请先用 render(url) 打开页面（需真实浏览器）"}
        try:
            result = self._page.evaluate(js)
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # 提取（复用原正则逻辑，兼容现有调用）
    # ------------------------------------------------------------------
    def _extract_title(self, html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        if not m:
            return ""
        return re.sub(r"\s+", " ", m.group(1)).strip()

    def get_text(self, url: str = None) -> str:
        """提取纯文本（去 HTML 标签）。

        - 传入 url：优先用真实浏览器渲染后再提取；失败降级 requests 抓取后提取。
        - 不传 url：基于当前已打开页面（current_html）提取——保持旧签名兼容。
        """
        try:
            if url:
                self.render(url)
        except Exception as e:
            logger.warning("get_text render 失败 %s: %s", url, e)
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
            {"name": "browser_navigate", "description": "访问指定URL网页（优先真实浏览器渲染JS）", "args": {"url": "string"}},
            {"name": "browser_get_text", "description": "获取网页纯文本内容（可传url渲染后提取）", "args": {"url": "string"}},
            {"name": "browser_get_links", "description": "获取当前网页所有链接", "args": {}},
            {"name": "browser_search", "description": "搜索网页", "args": {"query": "string", "num": "int"}},
            {"name": "browser_render", "description": "用真实浏览器渲染页面返回完整HTML", "args": {"url": "string", "wait_seconds": "int"}},
            {"name": "browser_screenshot", "description": "对页面截图保存到指定路径（需真实浏览器）", "args": {"url": "string", "path": "string"}},
        ]

    def execute_tool(self, name: str, args: dict) -> str:
        """执行工具，返回结果字符串"""
        try:
            if name == "browser_navigate":
                return json.dumps(self.navigate(args.get("url", "")), ensure_ascii=False)
            elif name == "browser_get_text":
                return self.get_text(args.get("url") or None)
            elif name == "browser_get_links":
                return json.dumps(self.get_links(), ensure_ascii=False)
            elif name == "browser_search":
                return json.dumps(
                    self.search(args.get("query", ""), args.get("num", 10)),
                    ensure_ascii=False,
                )
            elif name == "browser_render":
                html = self.render(
                    args.get("url", ""), args.get("wait_seconds", 3)
                )
                return json.dumps(
                    {"ok": bool(html), "rendered": self._is_browser_ready(), "length": len(html)},
                    ensure_ascii=False,
                )
            elif name == "browser_screenshot":
                path = self.screenshot(args.get("url", ""), args.get("path", ""))
                return json.dumps({"ok": bool(path), "path": path}, ensure_ascii=False)
            return f"Unknown tool: {name}"
        except Exception as e:
            return f"Error: {e}"
