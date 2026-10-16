# -*- coding: utf-8 -*-
"""todo_manager 插件

本地待办事项管理，数据持久化到同目录下的 store.json（不入库，已 gitignore）。

工具：
  - add_task(title, priority="normal")   添加待办，返回新任务 id
  - list_tasks(filter="all")             列出任务：all / pending / done
  - complete_task(id)                    把任务标记为已完成
  - delete_task(id)                      删除任务

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


_PRIORITIES = ("high", "normal", "low")


class TodoManagerPlugin(PluginBase):
    name = "todo_manager"
    version = "0.0.1"
    description = "待办事项管理：添加 / 列出 / 完成 / 删除，数据持久化到本地 JSON"
    author = "xiaoling"
    category = "productivity"
    permissions = ["file:read", "file:write"]

    def __init__(self, context=None, store_path: str = ""):
        super().__init__(context)
        self._lock = threading.RLock()
        if not store_path:
            store_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "store.json")
        self._store_path = store_path

    # ---------------- 持久化 ----------------
    def _load(self) -> dict:
        try:
            if os.path.isfile(self._store_path):
                with open(self._store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                    return data
        except Exception as e:
            logger_warning = "读取待办数据失败: {}".format(e)
            return {"tasks": [], "_warn": logger_warning}
        return {"tasks": [], "next_id": 1}

    def _save(self, data: dict) -> None:
        tmp = self._store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._store_path)

    # ---------------- 工具注册 ----------------
    def init(self):
        self._tools = [
            {
                "name": "add_task",
                "description": "添加待办事项，priority 可为 high/normal/low",
                "args_schema": {"title": "string", "priority": "string?"},
                "handler": self.add_task,
            },
            {
                "name": "list_tasks",
                "description": "列出任务，filter 可选 all/pending/done",
                "args_schema": {"filter": "string?"},
                "handler": self.list_tasks,
            },
            {
                "name": "complete_task",
                "description": "把 id 对应的任务标记为已完成",
                "args_schema": {"id": "int"},
                "handler": self.complete_task,
            },
            {
                "name": "delete_task",
                "description": "删除 id 对应的任务",
                "args_schema": {"id": "int"},
                "handler": self.delete_task,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    # ---------------- 工具实现 ----------------
    def add_task(self, title: str = "", priority: str = "normal") -> dict:
        try:
            if not title or not str(title).strip():
                return {"ok": False, "error": "缺少参数 title"}
            pri = str(priority or "normal").strip().lower()
            if pri not in _PRIORITIES:
                return {"ok": False,
                        "error": "priority 必须是 {} 之一".format("/".join(_PRIORITIES))}
            with self._lock:
                data = self._load()
                tasks = data["tasks"]
                next_id = int(data.get("next_id", 1))
                task = {
                    "id": next_id,
                    "title": str(title).strip(),
                    "priority": pri,
                    "done": False,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                tasks.append(task)
                data["next_id"] = next_id + 1
                self._save(data)
            return {"ok": True, "task": task, "total": len(tasks)}
        except Exception as e:
            return {"ok": False,
                    "error": "add_task 失败: {}: {}".format(type(e).__name__, e)}

    def list_tasks(self, filter: str = "all") -> dict:
        try:
            f = str(filter or "all").strip().lower()
            if f not in ("all", "pending", "done"):
                return {"ok": False,
                        "error": "filter 必须是 all/pending/done 之一"}
            with self._lock:
                data = self._load()
                tasks = data["tasks"]
            if f == "pending":
                picked = [t for t in tasks if not t.get("done")]
            elif f == "done":
                picked = [t for t in tasks if t.get("done")]
            else:
                picked = tasks
            # 优先级排序：high > normal > low
            order = {"high": 0, "normal": 1, "low": 2}
            picked = sorted(picked,
                            key=lambda t: (order.get(t.get("priority", "normal"), 1),
                                           t.get("id", 0)))
            return {"ok": True, "filter": f, "count": len(picked), "tasks": picked}
        except Exception as e:
            return {"ok": False,
                    "error": "list_tasks 失败: {}: {}".format(type(e).__name__, e)}

    def complete_task(self, id: int = 0) -> dict:
        try:
            try:
                tid = int(id)
            except (TypeError, ValueError):
                return {"ok": False, "error": "id 必须是整数"}
            with self._lock:
                data = self._load()
                for t in data["tasks"]:
                    if t.get("id") == tid:
                        t["done"] = True
                        t["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        self._save(data)
                        return {"ok": True, "task": t}
                return {"ok": False, "error": "未找到 id={} 的任务".format(tid)}
        except Exception as e:
            return {"ok": False,
                    "error": "complete_task 失败: {}: {}".format(type(e).__name__, e)}

    def delete_task(self, id: int = 0) -> dict:
        try:
            try:
                tid = int(id)
            except (TypeError, ValueError):
                return {"ok": False, "error": "id 必须是整数"}
            with self._lock:
                data = self._load()
                before = len(data["tasks"])
                data["tasks"] = [t for t in data["tasks"] if t.get("id") != tid]
                after = len(data["tasks"])
                if after == before:
                    return {"ok": False, "error": "未找到 id={} 的任务".format(tid)}
                self._save(data)
                return {"ok": True, "deleted_id": tid, "remaining": after}
        except Exception as e:
            return {"ok": False,
                    "error": "delete_task 失败: {}: {}".format(type(e).__name__, e)}
