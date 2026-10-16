# -*- coding: utf-8 -*-
"""code_snippets 插件

常用代码片段管理，数据持久化到同目录 store.json（不入库，已 gitignore）。

工具：
  - save_snippet(name, language, code)   保存 / 覆盖一个命名片段
  - search_snippets(keyword)             在名称/语言/代码里做子串搜索
  - get_snippet(name)                     按名取出完整代码
  - list_snippets(language="")            列出全部；传 language 可按语言过滤

核心原则：真实读写 JSON；名称冲突时明确告知；异常一律 {ok:False,error:...}。
"""
from __future__ import annotations

import json
import os
import threading
import time

try:
    from core.plugin_system import PluginBase
except ImportError:
    from backend.core.plugin_system import PluginBase


class CodeSnippetsPlugin(PluginBase):
    name = "code_snippets"
    version = "0.0.1"
    description = "代码片段管理：保存 / 搜索 / 取出 / 列出常用代码片段，本地 JSON 持久化"
    author = "xiaoling"
    category = "development"
    permissions = ["file:read", "file:write"]

    def __init__(self, context=None, store_path: str = ""):
        super().__init__(context)
        self._lock = threading.RLock()
        if not store_path:
            store_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "store.json")
        self._store_path = store_path

    def _load(self) -> dict:
        try:
            if os.path.isfile(self._store_path):
                with open(self._store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("snippets"), dict):
                    return data
        except Exception:
            pass
        return {"snippets": {}}

    def _save(self, data: dict) -> None:
        tmp = self._store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._store_path)

    def init(self):
        self._tools = [
            {
                "name": "save_snippet",
                "description": "保存名为 name、语言为 language 的代码片段 code（同名会覆盖）",
                "args_schema": {"name": "string", "language": "string", "code": "string"},
                "handler": self.save_snippet,
            },
            {
                "name": "search_snippets",
                "description": "在片段名称/语言/代码中搜索关键词 keyword",
                "args_schema": {"keyword": "string"},
                "handler": self.search_snippets,
            },
            {
                "name": "get_snippet",
                "description": "按名称 name 取出完整代码片段",
                "args_schema": {"name": "string"},
                "handler": self.get_snippet,
            },
            {
                "name": "list_snippets",
                "description": "列出片段；传 language 可按语言过滤",
                "args_schema": {"language": "string?"},
                "handler": self.list_snippets,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    def save_snippet(self, name: str = "", language: str = "", code: str = "") -> dict:
        try:
            if not name or not str(name).strip():
                return {"ok": False, "error": "缺少参数 name"}
            if code is None or str(code) == "":
                return {"ok": False, "error": "缺少参数 code（代码内容不能为空）"}
            name = str(name).strip()
            language = str(language or "plain").strip() or "plain"
            with self._lock:
                data = self._load()
                existed = name in data["snippets"]
                data["snippets"][name] = {
                    "name": name,
                    "language": language,
                    "code": str(code),
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                self._save(data)
            return {"ok": True, "name": name, "overwritten": existed,
                    "language": language,
                    "total": len(data["snippets"])}
        except Exception as e:
            return {"ok": False,
                    "error": "save_snippet 失败: {}: {}".format(type(e).__name__, e)}

    def search_snippets(self, keyword: str = "") -> dict:
        try:
            if not keyword or not str(keyword).strip():
                return {"ok": False, "error": "缺少参数 keyword"}
            kw = str(keyword).strip().lower()
            with self._lock:
                data = self._load()
            hits = []
            for snip in data["snippets"].values():
                hay = "{} {} {}".format(
                    snip.get("name", ""), snip.get("language", ""),
                    snip.get("code", "")).lower()
                if kw in hay:
                    hits.append({
                        "name": snip.get("name"),
                        "language": snip.get("language"),
                        "preview": (snip.get("code", "") or "")[:120],
                    })
            hits.sort(key=lambda x: x["name"])
            return {"ok": True, "keyword": keyword, "count": len(hits), "results": hits}
        except Exception as e:
            return {"ok": False,
                    "error": "search_snippets 失败: {}: {}".format(type(e).__name__, e)}

    def get_snippet(self, name: str = "") -> dict:
        try:
            if not name or not str(name).strip():
                return {"ok": False, "error": "缺少参数 name"}
            name = str(name).strip()
            with self._lock:
                data = self._load()
            snip = data["snippets"].get(name)
            if not snip:
                return {"ok": False, "error": "未找到名为 {!r} 的片段".format(name)}
            return {"ok": True, "name": snip.get("name"),
                    "language": snip.get("language"),
                    "code": snip.get("code", ""),
                    "updated_at": snip.get("updated_at", "")}
        except Exception as e:
            return {"ok": False,
                    "error": "get_snippet 失败: {}: {}".format(type(e).__name__, e)}

    def list_snippets(self, language: str = "") -> dict:
        try:
            with self._lock:
                data = self._load()
            items = list(data["snippets"].values())
            if language and str(language).strip():
                lang = str(language).strip().lower()
                items = [s for s in items
                         if str(s.get("language", "")).lower() == lang]
            items.sort(key=lambda s: s.get("name", ""))
            summary = [{"name": s.get("name"), "language": s.get("language")}
                       for s in items]
            return {"ok": True, "count": len(summary), "language": language or "all",
                    "snippets": summary}
        except Exception as e:
            return {"ok": False,
                    "error": "list_snippets 失败: {}: {}".format(type(e).__name__, e)}
