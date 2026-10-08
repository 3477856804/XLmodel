# -*- coding: utf-8 -*-
"""rss_reader 插件

RSS / Atom 订阅阅读：真实联网拉取并解析，不硬编码任何文章。

工具：
  - add_feed(url)                校验并新增一个订阅源（同时拉取一次取标题）
  - list_feeds()                 列出已保存的订阅源
  - get_articles(feed_url, limit=10)
                                 实时拉取该源最新文章（含未读标记）
  - mark_read(article_id)       把某篇文章标记为已读

解析后端：
  1) 优先 feedparser（若已安装）；
  2) 未安装则回退到标准库 urllib + xml.etree.ElementTree，
     同时兼容 RSS 2.0（channel/item）与 Atom 1.0（feed/entry）。

任何网络 / 解析错误都以 {ok: False, error: ...} 返回，绝不伪造文章列表。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from urllib import request as _urlrequest
from xml.etree import ElementTree as _ET

try:
    from core.plugin_system import PluginBase
except ImportError:
    from backend.core.plugin_system import PluginBase

try:
    import feedparser  # type: ignore
    _HAVE_FEEDPARSER = True
except Exception:
    feedparser = None
    _HAVE_FEEDPARSER = False

_TIMEOUT = 10  # 秒
_UA = "Mozilla/5.0 (compatible; xiaoling-rss/0.0.1)"


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _article_id(feed_url: str, link: str, title: str) -> str:
    raw = "{}|{}|{}".format(feed_url, link or "", title or "")
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


class RssReaderPlugin(PluginBase):
    name = "rss_reader"
    version = "0.0.1"
    description = "RSS/Atom 订阅阅读：添加订阅源 / 实时拉取文章 / 标记已读"
    author = "xiaoling"
    category = "tool"
    permissions = ["network", "file:read", "file:write"]

    def __init__(self, context=None, store_path: str = ""):
        super().__init__(context)
        self._lock = threading.RLock()
        if not store_path:
            store_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "feeds.json")
        self._store_path = store_path

    # ---------------- 持久化 ----------------
    def _load(self) -> dict:
        try:
            if os.path.isfile(self._store_path):
                with open(self._store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("feeds"), list):
                    data.setdefault("read", [])
                    return data
        except Exception as e:
            return {"feeds": [], "read": [],
                    "_warn": "读取订阅数据失败: {}".format(e)}
        return {"feeds": [], "read": []}

    def _save(self, data: dict) -> None:
        tmp = self._store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._store_path)

    # ---------------- HTTP + 解析 ----------------
    def _fetch(self, url: str) -> bytes:
        req = _urlrequest.Request(url, headers={"User-Agent": _UA,
                                                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
        with _urlrequest.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read()

    def _parse(self, raw: bytes):
        """返回 (feed_title, [ {title, link, summary, published} ])。"""
        if _HAVE_FEEDPARSER:
            d = feedparser.parse(raw)
            feed_title = (d.feed.get("title") or "").strip()
            articles = []
            for e in (d.entries or []):
                articles.append({
                    "title": (e.get("title") or "").strip(),
                    "link": (e.get("link") or "").strip(),
                    "summary": _strip_html(e.get("summary") or
                                           e.get("description") or ""),
                    "published": (e.get("published") or
                                  e.get("updated") or "").strip(),
                })
            return feed_title, articles

        # 标准库兜底解析
        try:
            root = _ET.fromstring(raw)
        except Exception as e:
            raise ValueError("XML 解析失败: {}".format(e))

        # Atom: {http://www.w3.org/2005/Atom}feed
        tag = root.tag.lower()
        if tag.endswith("feed"):
            ns = {"a": "http://www.w3.org/2005/Atom"}
            feed_title = (root.findtext("a:title", default="", namespaces=ns)
                          or "").strip()
            articles = []
            for entry in root.findall("a:entry", ns):
                link = ""
                for l in entry.findall("a:link", ns):
                    if l.get("href"):
                        link = l.get("href") or ""
                        if l.get("rel", "alternate") == "alternate":
                            break
                articles.append({
                    "title": (entry.findtext("a:title", default="",
                                             namespaces=ns) or "").strip(),
                    "link": link.strip(),
                    "summary": _strip_html(entry.findtext(
                        "a:summary", default="", namespaces=ns) or
                        entry.findtext("a:content", default="",
                                       namespaces=ns) or ""),
                    "published": (entry.findtext("a:published", default="",
                                                  namespaces=ns) or
                                   entry.findtext("a:updated", default="",
                                                  namespaces=ns) or "").strip(),
                })
            return feed_title, articles

        # RSS 2.0: rss/channel/item
        channel = root.find("channel")
        if channel is None:
            raise ValueError("未识别的 RSS/Atom 结构（找不到 channel 或 feed）")
        feed_title = (channel.findtext("title", default="") or "").strip()
        articles = []
        for item in channel.findall("item"):
            articles.append({
                "title": (item.findtext("title", default="") or "").strip(),
                "link": (item.findtext("link", default="") or "").strip(),
                "summary": _strip_html(item.findtext("description", default="")
                                       or ""),
                "published": (item.findtext("pubDate", default="") or "").strip(),
            })
        return feed_title, articles

    # ---------------- 工具注册 ----------------
    def init(self):
        self._tools = [
            {
                "name": "add_feed",
                "description": "校验并新增一个 RSS/Atom 订阅源（实时拉取取标题）",
                "args_schema": {"url": "string"},
                "handler": self.add_feed,
            },
            {
                "name": "list_feeds",
                "description": "列出已保存的订阅源",
                "args_schema": {},
                "handler": self.list_feeds,
            },
            {
                "name": "get_articles",
                "description": "实时拉取指定订阅源最新文章（含未读标记）",
                "args_schema": {"feed_url": "string", "limit": "int?"},
                "handler": self.get_articles,
            },
            {
                "name": "mark_read",
                "description": "把 article_id 对应的文章标记为已读",
                "args_schema": {"article_id": "string"},
                "handler": self.mark_read,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    # ---------------- 工具实现 ----------------
    def add_feed(self, url: str = "") -> dict:
        try:
            url = str(url or "").strip()
            if not url.startswith(("http://", "https://")):
                return {"ok": False, "error": "url 必须以 http:// 或 https:// 开头"}
            try:
                raw = self._fetch(url)
                feed_title, articles = self._parse(raw)
            except Exception as e:
                return {"ok": False, "url": url,
                        "error": "订阅源拉取 / 解析失败: {}: {}".format(
                            type(e).__name__, e)}
            with self._lock:
                data = self._load()
                if any(f.get("url") == url for f in data["feeds"]):
                    return {"ok": False, "error": "该订阅源已存在: {}".format(url)}
                feed = {
                    "url": url,
                    "title": feed_title or url,
                    "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "cached_count": len(articles),
                }
                data["feeds"].append(feed)
                self._save(data)
            return {"ok": True, "feed": feed}
        except Exception as e:
            return {"ok": False,
                    "error": "add_feed 失败: {}: {}".format(type(e).__name__, e)}

    def list_feeds(self) -> dict:
        try:
            with self._lock:
                data = self._load()
                feeds = list(data["feeds"])
            return {"ok": True, "count": len(feeds), "feeds": feeds,
                    "parser": "feedparser" if _HAVE_FEEDPARSER else "stdlib"}
        except Exception as e:
            return {"ok": False,
                    "error": "list_feeds 失败: {}: {}".format(type(e).__name__, e)}

    def get_articles(self, feed_url: str = "", limit: int = 10) -> dict:
        try:
            feed_url = str(feed_url or "").strip()
            if not feed_url:
                return {"ok": False, "error": "缺少参数 feed_url"}
            try:
                lim = int(limit)
            except (TypeError, ValueError):
                lim = 10
            lim = max(1, min(lim, 50))
            try:
                raw = self._fetch(feed_url)
                feed_title, articles = self._parse(raw)
            except Exception as e:
                return {"ok": False, "feed_url": feed_url,
                        "error": "拉取文章失败: {}: {}".format(
                            type(e).__name__, e)}
            with self._lock:
                read_set = set(self._load().get("read", []))
            out = []
            for a in articles[:lim]:
                aid = _article_id(feed_url, a.get("link", ""),
                                  a.get("title", ""))
                out.append({
                    "id": aid,
                    "title": a.get("title", ""),
                    "link": a.get("link", ""),
                    "summary": (a.get("summary", "") or "")[:300],
                    "published": a.get("published", ""),
                    "read": aid in read_set,
                })
            return {"ok": True, "feed_url": feed_url, "feed_title": feed_title,
                    "count": len(out), "articles": out}
        except Exception as e:
            return {"ok": False,
                    "error": "get_articles 失败: {}: {}".format(
                        type(e).__name__, e)}

    def mark_read(self, article_id: str = "") -> dict:
        try:
            aid = str(article_id or "").strip()
            if not aid:
                return {"ok": False, "error": "缺少参数 article_id"}
            with self._lock:
                data = self._load()
                if aid not in data["read"]:
                    data["read"].append(aid)
                    self._save(data)
            return {"ok": True, "article_id": aid}
        except Exception as e:
            return {"ok": False,
                    "error": "mark_read 失败: {}: {}".format(type(e).__name__, e)}
