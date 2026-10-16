#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成长运维指令（暂停/恢复/状态/回滚/GC/清库）的 RPC 接线回归测试。

动手前用 grep 钉死的事实（不是猜的）：

  1. `GrowthEngine.pause/resume/rollback/gc` 与 `GrowthStore.purge` 五个方法
     在仓库里**只有测试调用**，`rpc/server.py` 的 growth: 指令族没有其中任何
     一条分支 —— 也就是说前端一个按钮都按不到，文档却把它们写成「已实现的能力」。
  2. `GrowthEngine.gc()` 无条件 `self.journal("gc", ...)`；`rollback()` 在
     ok 且非 dry_run 时写 journal。所以「只读预览」必须绕开引擎、直接调
     `ModelLifecycle.gc/rollback(dry_run=True)`，否则前端每刷新一次成长页
     就往流水里塞一行，报表随后把这行当真实事件统计。

本文件盯的就是这两件事，外加一条通用原则：**破坏性操作必须显式 confirm**。
  - 裸调用一律 readonly=True，且能用文件系统证据证明确实没动；
  - confirm 才走后台任务，返回值里必须带 poll（否则前端不知道该接着问）；
  - 预览报 ok 却没带 dry_run，视为假成功，不能当成「演练通过」。
"""
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "backend", ROOT / "backend" / "rpc"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

tg = importlib.import_module("test_growth")


@pytest.fixture()
def home(tmp_path, monkeypatch):
    gr = tg._make_home(tmp_path)
    monkeypatch.setenv("XIAOLING_PENDING_DIR", str(tmp_path / "pending"))
    return gr


class _Tasks:
    """替身任务表：记住 job 但不真起线程 —— 断言的是「接线正确 + 真的执行」。"""

    def __init__(self):
        self.started = []

    def start_task(self, name, job):
        self.started.append((name, job))
        return {"task_id": f"t{len(self.started)}", "state": "queued"}

    def run_last(self, *args, **kw):
        """在最近一个任务上真跑一遍 job（cancel_event 默认不取消）。"""
        name, job = self.started[-1]
        return job(types.SimpleNamespace(is_set=lambda: False),
                   lambda s: None, *args, **kw)


@pytest.fixture()
def srv(home, monkeypatch):
    import server as S
    monkeypatch.setattr(S, "_get_engine",
                        lambda: types.SimpleNamespace(
                            growth=home.GrowthEngine(), model_replace=None,
                            persona=None))
    tasks = _Tasks()
    monkeypatch.setattr(S, "_get_bg_tasks", lambda: tasks)
    S._tasks = tasks            # 测试里取回替身
    return S


def _cmd(srv, cmd):
    return json.loads(srv._handle_growth_cmd(cmd))


def _journal_lines(gr):
    j = Path(gr.JOURNAL)
    return j.read_text(encoding="utf-8").splitlines() if j.exists() else []


def _mk_model_dir(p: Path, tag: str):
    """造一个能被 registry 认出体积的假模型目录。"""
    p.mkdir(parents=True, exist_ok=True)
    (p / "config.json").write_text('{"n_layer": 2}', encoding="utf-8")
    (p / "model.safetensors").write_bytes(tag.encode("utf-8") * 2048)
    return p


# --------------------------------------------------------------------------- #
#  1. pause / resume：暂停真的拦训练，恢复真的放行
# --------------------------------------------------------------------------- #

def test_pause_blocks_training_for_real(srv, home):
    eng = srv._get_engine().growth
    eng.store.add("练一下", "好", source="chat")
    d = _cmd(srv, "pause 我在评测")
    assert d["ok"] is True and d["paused"] is True, d
    assert d["reason"] == "我在评测", d
    assert eng.is_paused() is True, "写了状态却没生效 = 假暂停"
    # 真正的拦阻证据：train_round 直接 skipped，不进训练
    r = eng.train_round()
    assert r.get("skipped") is True and r.get("paused") is True, r
    assert _cmd(srv, "promotecheck")["paused"] is True


def test_pause_writes_journal_and_reports_repeat(srv, home):
    before = _journal_lines(home)
    d1 = _cmd(srv, "pause")
    d2 = _cmd(srv, "pause")
    after = _journal_lines(home)
    assert d1["ok"] and d1["already_paused"] is False, d1
    assert d2["already_paused"] is True, "重复暂停要如实说早暂停了"
    assert len(after) - len(before) == 2, after[len(before):]
    assert '"event": "pause"' in after[-1], after[-1]


def test_resume_clears_pause_and_shows_gate(srv, home):
    eng = srv._get_engine().growth
    _cmd(srv, "pause")
    assert eng.is_paused() is True
    d = _cmd(srv, "resume")
    assert d["ok"] is True and d["paused"] is False, d
    assert eng.is_paused() is False
    # 恢复后必须回显「现在能不能练」，前端才敢说话
    assert "can_train_now" in d, d
    assert isinstance(d.get("train_blockers"), list), d
    again = _cmd(srv, "resume")            # 幂等：重复恢复不报错
    assert again["ok"] is True and again["paused"] is False, again


def test_status_is_read_only(srv, home):
    gr = home
    eng = srv._get_engine().growth
    eng.store.add("看一眼", "嗯", source="chat")
    before = _journal_lines(gr)
    a = _cmd(srv, "status")
    b = _cmd(srv, "status")
    assert a["ok"] is True and b["ok"] is True, a
    for k in ("paused", "base_bytes", "adapter_bytes", "progress_percent",
              "stage", "rank", "can_train_now", "train_blockers", "config",
              "pause_reason", "paused_at", "resumed_at"):
        assert k in a, (k, sorted(a))
    assert _journal_lines(gr) == before, "刷新成长页不该写流水（看过一眼≠事件）"
    assert a["config"]["min_samples"] == eng.cfg("min_samples"), a["config"]


def test_status_carries_pause_provenance(srv):
    """前端横幅要说「谁什么时候暂停的」，只回布尔等于没回。"""
    _cmd(srv, "pause 我在评测")
    st = _cmd(srv, "status")
    assert st["pause_reason"] == "我在评测", st
    assert st["paused_at"], st
    _cmd(srv, "resume")
    st2 = _cmd(srv, "status")
    assert st2["paused"] is False and st2["resumed_at"], st2


def test_pause_resume_status_roundtrip_visible_to_promotecheck(srv):
    _cmd(srv, "pause")
    assert _cmd(srv, "promotecheck")["paused"] is True
    _cmd(srv, "resume")
    assert _cmd(srv, "promotecheck")["paused"] is False


# --------------------------------------------------------------------------- #
#  2. rollback：裸调用只列回收区，confirm 才搬目录
# --------------------------------------------------------------------------- #

def test_rollback_list_empty_is_honest(srv, home):
    d = _cmd(srv, "rollback")
    assert d["ok"] is True and d["readonly"] is True, d
    assert d["can_rollback"] is False and d["trash"] == [], d
    assert "回收区为空" in d["note"], d
    assert "usage" in d, d


def test_rollback_bare_never_moves_dirs(srv, home):
    gr = home
    base = Path(gr.BASE_MODEL_DIR)
    _mk_model_dir(base, "gen1")
    trash = gr.TRASH_DIR / "gen0_stamp"
    _mk_model_dir(trash, "gen0")
    eng = srv._get_engine().growth
    eng.lifecycle.register(1, "第 1 代", base, status="active")
    eng.lifecycle.register(0, "第 0 代", trash, status="trash", stamp="stamp")
    before = sorted(x.name for x in gr.TRASH_DIR.iterdir())

    lst = _cmd(srv, "rollback")
    assert lst["can_rollback"] is True, lst
    assert lst["trash"][0]["gen"] == 0 and lst["trash"][0]["exists"] is True, lst
    assert lst["active_gen"] == 1, lst

    prev = _cmd(srv, "rollback 0")
    assert prev["ok"] is True and prev.get("dry_run") is True, prev
    assert prev["readonly"] is True and "confirm" in prev["next"], prev
    assert prev["from_gen"] == 1 and prev["target_gen"] == 0, prev
    # 演练的证据：目录一个没动，registry 一个没改
    assert sorted(x.name for x in gr.TRASH_DIR.iterdir()) == before
    assert (base / "model.safetensors").read_bytes().startswith(b"gen1")
    states = {int(g["gen"]): g["status"]
              for g in eng.lifecycle.registry()["generations"]}
    assert states == {1: "active", 0: "trash"}, states


def test_rollback_confirm_swaps_bases(srv, home):
    gr = home
    base = Path(gr.BASE_MODEL_DIR)
    _mk_model_dir(base, "gen1")
    trash = gr.TRASH_DIR / "gen0_conf"
    _mk_model_dir(trash, "gen0")
    eng = srv._get_engine().growth
    eng.lifecycle.register(1, "第 1 代", base, status="active")
    eng.lifecycle.register(0, "第 0 代", trash, status="trash", stamp="conf")

    d = _cmd(srv, "rollback 0 confirm")
    assert d.get("task_id") and d.get("poll", "").endswith(d["task_id"]), d
    assert srv._tasks.started[-1][0] == "growth:rollback 0 confirm"
    res = srv._tasks.run_last()
    assert res["ok"] is True, res
    assert (base / "model.safetensors").read_bytes().startswith(b"gen0"), "基底没换回来"
    states = {int(g["gen"]): g["status"]
              for g in eng.lifecycle.registry()["generations"]}
    assert states[0] == "active" and states[1] == "trash", states
    assert eng.state().get("promotions") == 0, eng.state()


def test_rollback_bad_gen_and_missing_dir(srv, home):
    d = _cmd(srv, "rollback abc")
    assert d["ok"] is False and "整数" in d["error"], d
    d2 = _cmd(srv, "rollback 7")
    assert d2["ok"] is False and d2.get("readonly") is True, d2
    assert "回收区" in d2.get("message", "") or "不存在" in d2.get("message", ""), d2
    assert "dry_run" not in d2, "预览失败不许报成演练通过"


# --------------------------------------------------------------------------- #
#  3. gc：裸调用演练（不删不写流水），run 才真删
# --------------------------------------------------------------------------- #

def _seed_trash(srv, home, gens=(0, 1, 2)):
    gr = home
    base = Path(gr.BASE_MODEL_DIR)
    _mk_model_dir(base, "gen9")
    eng = srv._get_engine().growth
    eng.lifecycle.register(9, "第 9 代", base, status="active")
    for n in gens:
        d = gr.TRASH_DIR / f"gen{n}_g"
        _mk_model_dir(d, f"g{n}")
        eng.lifecycle.register(n, f"第 {n} 代", d, status="trash", stamp="g")
    return eng


def test_gc_bare_is_dry_run_without_journal(srv, home):
    eng = _seed_trash(srv, home)
    before = _journal_lines(home)
    d = _cmd(srv, "gc")
    assert d["ok"] is True and d["readonly"] is True, d
    assert d["dry_run"] is True, d
    assert d["keep_generations"] == int(eng.cfg("keep_generations", 2)), d
    assert "stability" in d and "deletable" in d, sorted(d)
    # 目录一个没少
    assert all((home.TRASH_DIR / f"gen{n}_g").exists() for n in (0, 1, 2)), d
    assert _journal_lines(home) == before, "演练写流水 = 把看过一眼当事件"


def test_gc_respects_stability_unless_forced(srv, home):
    _seed_trash(srv, home)
    d = _cmd(srv, "gc")
    if not d["stability"]["stable"]:
        assert d["allowed"] is False, d
        assert "稳定期" in d["message"], d
        res = srv._tasks.started
        assert res == [], "演练不该起后台任务"


def test_gc_run_deletes_only_after_force(srv, home):
    eng = _seed_trash(srv, home)
    keep = int(eng.cfg("keep_generations", 2))
    _cmd(srv, "gc 3")            # 带保留数也仍是演练
    assert srv._tasks.started == [], "gc <n> 不许起后台任务"
    d = _cmd(srv, "gc run force")
    assert d.get("task_id") and "agent:task" in d["poll"], d
    assert srv._tasks.started[-1][0] == "growth:gc run"
    res = srv._tasks.run_last()
    assert res["ok"] is True and res.get("deleted"), res
    # ModelLifecycle.gc 的口径：keep=2 → 最新的 1 个回收代留底，其余真删
    survivors = sorted(x.name for x in home.TRASH_DIR.iterdir())
    assert "gen2_g" in survivors, survivors
    assert "gen0_g" not in survivors and "gen1_g" not in survivors, survivors
    st = {int(g["gen"]): g["status"]
          for g in eng.lifecycle.registry()["generations"]}
    assert st[0] == "deleted" and st[1] == "deleted", st
    assert st[2] == "trash" and st[9] == "active", st
    assert len(res["deleted"]) == max(3 - max(keep - 1, 0), 0), res["deleted"]


def test_gc_run_without_force_is_blocked_when_unstable(srv, home):
    eng = _seed_trash(srv, home)
    d = _cmd(srv, "gc run")
    res = srv._tasks.run_last()
    if not eng.lifecycle.stability()["stable"]:
        assert res["allowed"] is False and res["deleted"] == [], res
        assert all((home.TRASH_DIR / f"gen{n}_g").exists() for n in (0, 1, 2))


def test_gc_bad_keep(srv, home):
    d = _cmd(srv, "gc 很多")
    assert d["ok"] is False and "整数" in d["error"], d


# --------------------------------------------------------------------------- #
#  4. purge：预览数条数，confirm 才删数据
# --------------------------------------------------------------------------- #

def test_purge_preview_does_not_delete(srv, home):
    eng = srv._get_engine().growth
    eng.store.add("保留", "好", source="chat")
    eng.store.add("讨厌", "差", source="chat", feedback="dislike")
    eng.store.add_dpo("p", "c", "r")
    st = eng.store.stats()
    d = _cmd(srv, "purge all")
    assert d["ok"] is True and d["readonly"] is True, d
    assert d["scope"] == "all" and d["would_remove"] == st["total"], d
    assert "不可撤销" in d["warning"] and "confirm" in d["warning"], d
    assert eng.store.stats()["total"] == st["total"], "预览把数据删了"


def test_purge_scoped_counts(srv, home):
    eng = srv._get_engine().growth
    eng.store.add_dpo("p1", "c1", "r1")
    eng.store.add_dpo("p2", "c2", "r2")
    assert _cmd(srv, "purge dpo")["would_remove"] == 2
    eng.store.add("踩", "差", source="chat", feedback="dislike")
    assert _cmd(srv, "purge disliked")["would_remove"] == 1
    assert _cmd(srv, "purge trained")["would_remove"] == 0


def test_purge_confirm_actually_deletes(srv, home):
    eng = srv._get_engine().growth
    eng.store.add("保留", "好", source="chat")
    eng.store.add("讨厌", "差", source="chat", feedback="dislike")
    d = _cmd(srv, "purge disliked confirm")
    assert d.get("task_id") and d.get("poll_result"), d
    assert srv._tasks.started[-1][0] == "growth:purge disliked"
    res = srv._tasks.run_last()
    assert res["ok"] is True and res["removed"] == 1, res
    assert eng.store.stats()["total"] == 1, eng.store.stats()
    assert eng.store.stats()["feedback"]["dislike"] == 0


def test_purge_scope_all_wipes_dpo_too(srv, home):
    eng = srv._get_engine().growth
    eng.store.add("x", "y", source="chat")
    eng.store.add_dpo("p", "c", "r")
    _cmd(srv, "purge all confirm")
    res = srv._tasks.run_last()
    assert res["ok"] is True, res
    st = eng.store.stats()
    assert st["total"] == 0 and st["dpo_pairs"] == 0, st


def test_purge_unknown_scope_rejected(srv, home):
    d = _cmd(srv, "purge everything")
    assert d["ok"] is False, d
    for s in ("all", "trained", "disliked", "dpo"):
        assert s in d["error"], d
    _cmd(srv, "purge everything confirm")
    assert srv._tasks.started == [], "非法 scope 不许起后台任务"


# --------------------------------------------------------------------------- #
#  5. 指令族出口：用法提示要带上新命令
# --------------------------------------------------------------------------- #

def test_unknown_op_lists_new_commands(srv):
    d = _cmd(srv, "nonsense")
    assert d["ok"] is False, d
    for k in ("pause", "resume", "status", "rollback", "gc", "purge", "distill"):
        assert k in d["error"], (k, d["error"])


def test_empty_command_and_engine_missing(srv, home, monkeypatch):
    assert _cmd(srv, "")["ok"] is False
    import server as S
    monkeypatch.setattr(S, "_get_engine", lambda: None)
    d = _cmd(srv, "pause")
    assert d["ok"] is False and "引擎" in d["error"], d


@pytest.mark.parametrize("cmd", ["pause", "resume", "status", "rollback",
                                 "gc", "purge all"])
def test_no_api_key_leaks_in_lifecycle_replies(srv, cmd):
    d = _cmd(srv, cmd)
    txt = json.dumps(d, ensure_ascii=False)
    for secret in ("sk-", "api_key\": \"sk"):
        assert secret not in txt, (secret, txt[:400])


def test_shutil_left_clean(home):
    """本文件的目录搬运全在临时 HOME 里，不许污染仓库工作区。"""
    repo_star = ROOT / ".star_core"
    if repo_star.exists():
        trash = repo_star / "trash"
        assert not trash.exists() or \
            all("rollback_gen" not in p.name for p in trash.iterdir()), \
            list(trash.iterdir())
