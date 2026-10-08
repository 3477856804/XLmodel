# -*- coding: utf-8 -*-
"""Agent 工具链扩展测试：多文件编辑 / 终端闭环 / 后台任务。

原则：所有用例真实执行（写临时文件、跑 echo、起后台线程），
绝不依赖网络或模型；沙箱根指向 tmp_path，不污染真实数据目录。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ---------------------------------------------------------------------------
# 1. MultiFileEditor
# ---------------------------------------------------------------------------
def test_multifile_editor_apply_and_rollback(tmp_path):
    from backend.core.tools import MultiFileEditor
    fp = tmp_path / "a.py"
    fp.write_text("def foo():\n    return 1\n", encoding="utf-8")
    ed = MultiFileEditor(base_dir=str(tmp_path))

    plan = ed.plan_edits([], [{
        "file_path": "a.py", "old_string": "return 1", "new_string": "return 2",
    }])
    assert plan["ok"] is True
    assert plan["plan"][0]["status"] == "ready"
    assert "return 2" in plan["plan"][0]["diff"]

    res = ed.apply_edit("a.py", "return 1", "return 2")
    assert res["ok"] is True
    assert fp.read_text(encoding="utf-8") == "def foo():\n    return 2\n"

    diff = ed.get_diff("a.py")
    assert diff["lines_added"] >= 1 and diff["lines_removed"] >= 1

    rb = ed.rollback()
    assert rb["ok"] is True
    assert fp.read_text(encoding="utf-8") == "def foo():\n    return 1\n"


def test_multifile_editor_rejects_missing_and_nonunique(tmp_path):
    from backend.core.tools import MultiFileEditor
    fp = tmp_path / "b.txt"
    fp.write_text("x x x\n", encoding="utf-8")
    ed = MultiFileEditor(base_dir=str(tmp_path))
    assert ed.apply_edit("b.txt", "nope", "y")["ok"] is False
    assert "未找到" in ed.apply_edit("b.txt", "nope", "y")["error"]
    assert "不唯一" in ed.apply_edit("b.txt", "x", "y")["error"]
    assert ed.apply_edit("missing.txt", "a", "b")["ok"] is False


def test_multifile_editor_batch_is_transactional(tmp_path):
    from backend.core.tools import MultiFileEditor
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_text("aaa\n", encoding="utf-8")
    f2.write_text("bbb\n", encoding="utf-8")
    ed = MultiFileEditor(base_dir=str(tmp_path))
    bad = ed.apply_edits_batch([
        {"file_path": "f1.txt", "old_string": "aaa", "new_string": "AAA"},
        {"file_path": "f2.txt", "old_string": "nope", "new_string": "BBB"},
    ])
    assert bad["ok"] is False
    # 校验失败 -> 全部不执行
    assert f1.read_text() == "aaa\n"
    ok = ed.apply_edits_batch([
        {"file_path": "f1.txt", "old_string": "aaa", "new_string": "AAA"},
        {"file_path": "f2.txt", "old_string": "bbb", "new_string": "BBB"},
    ])
    assert ok["ok"] is True and ok["count"] == 2
    assert f1.read_text() == "AAA\n"


# ---------------------------------------------------------------------------
# 2. 终端闭环（复用沙箱）
# ---------------------------------------------------------------------------
def test_terminal_closed_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOLING_SANDBOX_ROOT", str(tmp_path))
    from backend.core import terminal as t
    out = t.run_command_with_output("echo hello_close", timeout=15)
    assert out["ok"] is True
    assert "hello_close" in out["combined"]

    missing = t.run_command_with_output("definitely_not_a_cmd_zzz", timeout=15)
    assert missing["ok"] is False

    lines = [c for c in t.run_command_stream("for i in 1 2; do echo line$i; done",
                                             timeout=15)]
    text = "".join(c.get("text", "") for c in lines if c.get("type") == "line")
    assert "line1" in text and "line2" in text
    end = [c for c in lines if c.get("type") == "end"][0]
    assert end["code"] == 0

    assert t.check_command_exists("echo")["exists"] is True
    assert t.check_command_exists("no_such_cmd_zzz")["exists"] is False


# ---------------------------------------------------------------------------
# 3. 后台任务
# ---------------------------------------------------------------------------
def test_background_task_lifecycle(tmp_path):
    from backend.core.background_tasks import BackgroundTaskManager
    m = BackgroundTaskManager(persist_path=str(tmp_path / "tasks.json"))

    def job(cancel_event, output, n):
        for i in range(n):
            if cancel_event.is_set():
                return "aborted"
            output(f"step{i}")
            time.sleep(0.01)
        return f"done{n}"

    r = m.start_task("fast", job, 3)
    assert r["ok"] is True
    tid = r["task_id"]
    time.sleep(0.2)
    st = m.get_task_status(tid)
    assert st["status"] == "completed"
    res = m.get_task_result(tid)
    assert res["result"] == "done3"
    assert len(res["output"]) == 3

    slow = m.start_task("slow", job, 1000)
    sid = slow["task_id"]
    time.sleep(0.02)
    c = m.cancel_task(sid)
    assert c["ok"] is True
    time.sleep(0.1)
    assert m.get_task_status(sid)["status"] in ("cancelled", "completed")

    lst = m.list_tasks()
    assert lst["total"] >= 2


def test_background_task_reload_marks_interrupted(tmp_path):
    from backend.core.background_tasks import BackgroundTaskManager
    p = tmp_path / "tasks.json"
    m = BackgroundTaskManager(persist_path=str(p))
    m.start_task("noop", lambda ev, out: "x")
    time.sleep(0.1)
    m2 = BackgroundTaskManager(persist_path=str(p))
    statuses = {t["status"] for t in m2.list_tasks()["tasks"]}
    assert "interrupted" not in statuses  # 已完成的不被标记
    assert "completed" in statuses
