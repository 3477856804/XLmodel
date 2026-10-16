# -*- coding: utf-8 -*-
"""note_taker 插件

本地笔记管理，数据持久化到同目录下的 notes.json（不入库，已 gitignore）。

工具：
  - create_note(title, content="", tags="")   新建笔记；tags 用逗号分隔
  - list_notes(tag="")                        列出笔记，可按标签过滤
  - search_notes(keyword)                     在标题/正文/标签里全文检索
  - delete_note(id)                           按 id 删除笔记

核心原则：真实读写 JSON 文件；任何异常都以 {ok: False, error: ...} 返回，
绝不伪造结果。
"""
from __future__ import annotations

import json
import os
import threading
import time

try:
    from core.plugin_system import PluginBase
except ImportError:  # 直接脚本运行 / 非打包态兜底
    from backend.core.plugin_system import PluginBase


def _split_tags(raw) -> list:
    """把 'a, b, c' 这类输入拆成去空白、去重、小写后的标签列表。"""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        items = str(raw).replace("，", ",").split(",")
    seen, out = set(), []
    for t in items:
        t = str(t).strip().lower()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


class NoteTakerPlugin(PluginBase):
    name = "note_taker"
    version = "0.0.1"
    description = "笔记管理：创建 / 列出 / 搜索 / 删除，支持标签，数据持久化到本地 JSON"
    author = "xiaoling"
    category = "productivity"
    permissions = ["file:read", "file:write"]

    def __init__(self, context=None, store_path: str = ""):
        super().__init__(context)
        self._lock = threading.RLock()
        if not store_path:
            store_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "notes.json")
        self._store_path = store_path

    # ---------------- 持久化 ----------------
    def _load(self) -> dict:
        try:
            if os.path.isfile(self._store_path):
                with open(self._store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("notes"), list):
                    return data
        except Exception as e:
            return {"notes": [], "next_id": 1,
                    "_warn": "读取笔记数据失败: {}".format(e)}
        return {"notes": [], "next_id": 1}

    def _save(self, data: dict) -> None:
        tmp = self._store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._store_path)

    # ---------------- 工具注册 ----------------
    def init(self):
        self._tools = [
            {
                "name": "create_note",
                "description": "新建笔记，tags 为逗号分隔的标签字符串",
                "args_schema": {"title": "string", "content": "string?",
                                "tags": "string?"},
                "handler": self.create_note,
            },
            {
                "name": "list_notes",
                "description": "列出笔记，可选按标签过滤（tag 为空则全部返回）",
                "args_schema": {"tag": "string?"},
                "handler": self.list_notes,
            },
            {
                "name": "search_notes",
                "description": "在标题 / 正文 / 标签中搜索关键词（大小写不敏感）",
                "args_schema": {"keyword": "string"},
                "handler": self.search_notes,
            },
            {
                "name": "delete_note",
                "description": "按 id 删除笔记",
                "args_schema": {"id": "int"},
                "handler": self.delete_note,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    # ---------------- 工具实现 ----------------
    def create_note(self, title: str = "", content: str = "",
                     tags: str = "") -> dict:
        try:
            if not title or not str(title).strip():
                return {"ok": False, "error": "缺少参数 title"}
            with self._lock:
                data = self._load()
                notes = data["notes"]
                next_id = int(data.get("next_id", 1))
                note = {
                    "id": next_id,
                    "title": str(title).strip(),
                    "content": str(content or ""),
                    "tags": _split_tags(tags),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                notes.append(note)
                data["next_id"] = next_id + 1
                self._save(data)
            return {"ok": True, "note": note, "total": len(notes)}
        except Exception as e:
            return {"ok": False,
                    "error": "create_note 失败: {}: {}".format(type(e).__name__, e)}

    def list_notes(self, tag: str = "") -> dict:
        try:
            with self._lock:
                data = self._load()
                notes = list(data["notes"])
            t = str(tag or "").strip().lower()
            if t:
                picked = [n for n in notes if t in (n.get("tags") or [])]
            else:
                picked = notes
            # 最新在前
            picked = sorted(picked, key=lambda n: n.get("id", 0), reverse=True)
            return {"ok": True, "tag": t, "count": len(picked), "notes": picked}
        except Exception as e:
            return {"ok": False,
                    "error": "list_notes 失败: {}: {}".format(type(e).__name__, e)}

    def search_notes(self, keyword: str = "") -> dict:
        try:
            kw = str(keyword or "").strip().lower()
            if not kw:
                return {"ok": False, "error": "缺少参数 keyword"}
            with self._lock:
                data = self._load()
                notes = list(data["notes"])
            hits = []
            for n in notes:
                hay = " ".join([
                    str(n.get("title", "")),
                    str(n.get("content", "")),
                    " ".join(n.get("tags") or []),
                ]).lower()
                if kw in hay:
                    hits.append(n)
            hits = sorted(hits, key=lambda n: n.get("id", 0), reverse=True)
            return {"ok": True, "keyword": keyword, "count": len(hits),
                    "notes": hits}
        except Exception as e:
            return {"ok": False,
                    "error": "search_notes 失败: {}: {}".format(type(e).__name__, e)}

    def delete_note(self, id: int = 0) -> dict:
        try:
            try:
                nid = int(id)
            except (TypeError, ValueError):
                return {"ok": False, "error": "id 必须是整数"}
            with self._lock:
                data = self._load()
                before = len(data["notes"])
                data["notes"] = [n for n in data["notes"] if n.get("id") != nid]
                after = len(data["notes"])
                if after == before:
                    return {"ok": False,
                            "error": "未找到 id={} 的笔记".format(nid)}
                self._save(data)
                return {"ok": True, "deleted_id": nid, "remaining": after}
        except Exception as e:
            return {"ok": False,
                    "error": "delete_note 失败: {}: {}".format(type(e).__name__, e)}
