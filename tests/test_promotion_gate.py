#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""晋升前验收门槛 + training:/growth: 接线 的行为测试。

这一块是「去伪存真」的最后一环：以前 config 里的 growth.require_eval /
pass_threshold 两个键从来没被任何代码读过（写了等于没写），晋升只看
adapter 体积够不够大。现在 merge_and_promote 在**基底退役之前**必须过
eval_probe 的生成式验收，且：

  - 开关关闭时如实标注「没测」，不假装通过；
  - 测不动（没 torch / 模型加载失败）时**拦住晋升**，不是放行；
  - 阈值真的来自 config，报告回显实际用的那一个；
  - 拦住时合并产物进隔离区，不静默 rm -rf，也不留在 STAR_DIR 里污染。

不需要 torch 权重：验收结果用 monkeypatch 喂给 gate，测的是**判定与
落地顺序**这类会用错的行为，不是模型质量本身。
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "backend", ROOT / "backend" / "rpc"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

tg = importlib.import_module("test_growth")


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """临时 HOME + 隔离的隔离区目录（quarantine 默认落在真实家目录）。"""
    gr = tg._make_home(tmp_path)
    monkeypatch.setenv("XIAOLING_PENDING_DIR", str(tmp_path / "pending"))
    return gr


def _set_growth_cfg(**kw):
    from core import config as C
    cfg = C.load(use_cache=False)
    g = cfg.setdefault("growth", {})
    g.update(kw)
    C.save(cfg)


def _fake_merged_dir(gr, name="_merge_tmp_test"):
    """造一个「看起来像合并产物」的中间目录（够 _validate_model_dir 通过）。"""
    d = gr.STAR_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps({"model_type": "mini"}),
                                   encoding="utf-8")
    (d / "model.safetensors").write_bytes(b"\0" * (2 * 1024 ** 2))
    return d


def _fake_merge(eng, monkeypatch):
    """把 _merge_adapter 换成「在调用方给的目录里造出权重」，路径语义与真的一致。

    不能自己挑目录名：merge_and_promote 用的是 STAR_DIR/_merge_tmp_<时间戳>，
    后面对这个目录的清理、隔离都依赖它确实是 out_dir。
    """
    def fake(out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "config.json").write_text(json.dumps({"model_type": "mini"}),
                                             encoding="utf-8")
        (out_dir / "model.safetensors").write_bytes(b"\0" * (2 * 1024 ** 2))
        return True, "2.0 MB 已合并"
    monkeypatch.setattr(eng, "_merge_adapter", fake)
    monkeypatch.setattr(eng, "_validate_model_dir", lambda d: True)
    return eng


def _stub_probes(monkeypatch, *, verdict="pass", ran=4, passed=4, ok=True,
                 reason=None, threshold=None, skipped=0):
    """替换 eval_probe.run_probes，返回它收到的参数供断言。"""
    from core import eval_probe as ep
    seen = {}

    def fake(model_dir, teacher_dir=None, max_new_tokens=32,
             timeout_sec=600, pass_rate=None):
        seen["model_dir"] = str(model_dir)
        seen["teacher_dir"] = str(teacher_dir) if teacher_dir else ""
        seen["pass_rate"] = pass_rate
        rep = {"ok": ok, "ran": ran, "passed": passed,
               "skipped": skipped, "pass_rate": (passed / ran) if ran else 0.0,
               "threshold": pass_rate if pass_rate is not None else threshold,
               "verdict": verdict,
               "probes": [{"id": f"p{i}", "kind": "identity", "ran": True,
                           "ok": i < passed, "output": "ok"}
                          for i in range(ran)],
               "reason": reason or ""}
        return rep
    monkeypatch.setattr(ep, "run_probes", fake)
    return seen


# --------------------------------------------------------------------------- #
#  门槛判定本身
# --------------------------------------------------------------------------- #

def test_gate_off_says_it_did_not_measure(home, monkeypatch):
    """关闭验收时必须明确「未测」——前端不能把它显示成通过。"""
    gr = home
    eng = gr.GrowthEngine()
    d = _fake_merged_dir(gr)
    g = eng._acceptance_gate(d)
    assert g["ok"] is True and g["skipped"] is True, g
    assert g["enforced"] is False
    assert "未做生成式验收" in g["message"], g["message"]


def test_gate_blocks_when_probes_cannot_run(home, monkeypatch):
    """开了验收但探针跑不动：拦住晋升。看不见的问题不能当没发生。"""
    gr = home
    _set_growth_cfg(require_eval=True)
    eng = gr.GrowthEngine()
    seen = _stub_probes(monkeypatch, ok=False, verdict="unknown", ran=0,
                        passed=0, reason="缺少推理依赖")
    d = _fake_merged_dir(gr, "_merge_tmp_broken")
    g = eng._acceptance_gate(d)
    assert g["ok"] is False, g
    assert "未能执行" in g["message"] and "没测出来" in g["message"], g["message"]
    assert seen["pass_rate"] == 0.9, "阈值应取 config 的 pass_threshold 默认值"


def test_gate_uses_config_threshold(home, monkeypatch):
    """阈值真的从 config 传到探针，不是写死在模块里。"""
    gr = home
    _set_growth_cfg(require_eval=True, pass_threshold=0.5)
    eng = gr.GrowthEngine()
    seen = _stub_probes(monkeypatch, verdict="pass")
    g = eng._acceptance_gate(_fake_merged_dir(gr, "_merge_tmp_thr"))
    assert g["ok"] is True and g["enforced"] is True, g
    assert seen["pass_rate"] == 0.5, seen
    assert g["threshold"] == 0.5, g


def test_gate_compares_against_current_base(home, monkeypatch):
    """对照方必须是当前基底，否则「有没有训坏」无从比较。"""
    gr = home
    _set_growth_cfg(require_eval=True)
    tg._fake_base(gr)
    eng = gr.GrowthEngine()
    seen = _stub_probes(monkeypatch)
    eng._acceptance_gate(_fake_merged_dir(gr, "_merge_tmp_cmp"))
    assert seen["teacher_dir"] == str(gr.BASE_MODEL_DIR), seen


# --------------------------------------------------------------------------- #
#  在晋升流程里的位置与后果
# --------------------------------------------------------------------------- #

def test_failed_gate_does_not_retire_base(home, monkeypatch):
    """验收没过：基底必须原封不动，代次不 +1，产物进隔离区。"""
    gr = home
    _set_growth_cfg(require_eval=True)
    tg._fake_base(gr)
    eng = _fake_merge(gr.GrowthEngine(), monkeypatch)
    _stub_probes(monkeypatch, ok=True, verdict="fail", passed=1, ran=4)
    r = eng.merge_and_promote()
    assert r["ok"] is False, r
    assert r.get("blocked_by") == "acceptance", r
    assert "验收未通过" in r["message"], r
    assert (gr.BASE_MODEL_DIR / "model.safetensors").is_file(), "被拦下时基底不能被搬走"
    assert int(eng.state().get("promotions", 0)) == 0, "拦下不应记为已晋升"
    leftovers = [p.name for p in gr.STAR_DIR.glob("_merge_tmp_*")]
    assert not leftovers, f"失败的中间产物不该留在 STAR_DIR：{leftovers}"
    pend = Path(os.environ["XIAOLING_PENDING_DIR"])
    assert pend.is_dir() and any(p.is_dir() for p in pend.rglob("*")), \
        "应移入隔离区而不是就地删除"
    events = [j.get("event") for j in eng.recent_journal(50)]
    assert "promote_blocked" in events, events
    assert "merge_quarantined" in events or "merge_removed" in events, events
    assert not (gr.TRASH_DIR.is_dir() and any(gr.TRASH_DIR.iterdir())), \
        "没理由产生退役目录"


def test_gate_off_promotes_but_reports_unmeasured(home, monkeypatch):
    """关闭验收时照常晋升，但结果里必须带上「没测」的事实给前端显示。"""
    gr = home
    _set_growth_cfg(require_eval=False)
    tg._fake_base(gr)
    eng = _fake_merge(gr.GrowthEngine(), monkeypatch)
    called = []
    from core import eval_probe as ep
    monkeypatch.setattr(ep, "run_probes",
                        lambda *a, **k: called.append(1) or {})
    r = eng.merge_and_promote()
    assert r["ok"] is True, r
    assert called == [], "require_eval 关闭时不该偷偷跑一遍验收"
    acc = r.get("acceptance") or {}
    assert acc.get("skipped") is True and acc.get("enforced") is False, r
    assert int(eng.state().get("promotions", 0)) == 1


def test_gate_blocks_partial_run(home, monkeypatch):
    """跑不完 = 不能晋升。verdict=pass 但 skipped>0 时，门槛必须拦。

    这是最容易被糊弄过去的一种半吊子：超时只剩 1 条探针跑完且通过，
    分数 1/1 看起来是满分，实际上另外 3 条根本没测。
    """
    gr = home
    _set_growth_cfg(require_eval=True)
    eng = gr.GrowthEngine()
    _stub_probes(monkeypatch, verdict="pass", ran=1, passed=1, skipped=3)
    g = eng._acceptance_gate(_fake_merged_dir(gr, "_merge_tmp_partial"))
    assert g["ok"] is False, g
    assert "不完整" in g["message"] and "只跑到 1 条" in g["message"], g["message"]
    assert g["skipped"] == 3, g


def test_passed_gate_reports_verdict(home, monkeypatch):
    """验收通过：晋升结果要带真实判定数字，供前端显示「测过了，4/4」。"""
    gr = home
    _set_growth_cfg(require_eval=True)
    tg._fake_base(gr)
    eng = _fake_merge(gr.GrowthEngine(), monkeypatch)
    _stub_probes(monkeypatch, verdict="pass", passed=4, ran=4)
    r = eng.merge_and_promote()
    assert r["ok"] is True, r
    acc = r["acceptance"]
    assert acc["enforced"] is True and acc["verdict"] == "pass", r
    assert acc["passed"] == 4 and acc["ran"] == 4, acc
    assert acc["threshold"] == 0.9, acc


def test_quarantine_failure_still_cleans_and_logs(home, monkeypatch):
    """隔离区本身写不进去时：删掉源目录，但必须写日志说清「删了」。"""
    gr = home
    eng = gr.GrowthEngine()
    d = _fake_merged_dir(gr, "_merge_tmp_dirty")
    from core import quarantine as q
    monkeypatch.setattr(q, "move_to_pending",
                        lambda *a, **k: {"ok": False, "error": "磁盘只读"})
    eng._quarantine_failed_merge(d)
    assert not d.exists(), "隔离失败时必须清掉本次中间产物"
    j = eng.recent_journal(30)
    assert any(x.get("event") == "merge_removed" for x in j), j


def test_pending_root_honors_env_at_call_time(tmp_path, monkeypatch):
    """隔离区位置必须**调用时**解析。

    回归点：PENDING_ROOT 曾是 import 期常量，测试/打包版在运行期设置
    XIAOLING_PENDING_DIR 完全不生效，隔离区静默写到真实 ~/待处理。
    """
    from core import quarantine as q
    # 真实家目录的隔离区必须一动不动（本用例只允许写 tmp_path）
    real_root = Path.home() / "待处理"
    before = sorted(p.name for p in real_root.iterdir()) if real_root.is_dir() else []
    target = tmp_path / "moved" / "pending"
    monkeypatch.setenv("XIAOLING_PENDING_DIR", str(target))
    assert q.pending_root() == target
    src = tmp_path / "victim"
    src.mkdir()
    (src / "a.txt").write_text("x", encoding="utf-8")
    r = q.move_to_pending(src, reason="回归测试", category="test")
    assert r["ok"] is True, r
    assert str(target) in r["dst"], r
    assert (target / Path(r["dst"]).name / "a.txt").is_file(), r
    assert not src.exists()
    # 清单与副本也必须跟着落到同一个隔离区，不能一个在临时目录一个在真实家目录
    assert (target / q.MANIFEST_NAME).is_file(), "清单没写进隔离区"
    after = sorted(p.name for p in real_root.iterdir()) if real_root.is_dir() else []
    assert after == before, f"自定义隔离区时不该碰真实家目录：{set(after) - set(before)}"


# --------------------------------------------------------------------------- #
#  RPC 接线（training: / growth: 指令族）
# --------------------------------------------------------------------------- #

def _cmd(server_mod, ns_cmd: str) -> dict:
    if ns_cmd.startswith("training:"):
        return json.loads(server_mod._handle_training_cmd(ns_cmd.split(":", 1)[1]))
    return json.loads(server_mod._handle_growth_cmd(ns_cmd.split(":", 1)[1]))


@pytest.fixture()
def server_mod(home):
    """导入真的 server 模块，但把「拿引擎」换成临时 HOME 里的真 GrowthEngine。

    只替换 _get_engine：_handle_growth_cmd / _handle_training_cmd 本体、
    后台任务表、配置读写全都走真实代码路径，这样测到的是接线本身。
    """
    srv = importlib.import_module("server")
    engine = SimpleNamespace(growth=home.GrowthEngine(), model_replace=None)
    srv._get_engine = lambda log=None: engine
    return srv


def test_mergestatus_reports_facts_and_acceptance(server_mod):
    d = _cmd(server_mod, "training:mergestatus")
    assert d["ok"] is True, d
    # 没训练过时 has_adapter=False，且要给出可执行的原因，不是空字符串
    assert "has_adapter" in d and "base_error" in d, d
    assert "acceptance" in d and "enforced" in d["acceptance"], d
    assert "current_base_dir" in d, d
    assert "found" in d["gguf"], d


def test_acceptance_roundtrip_writes_config(server_mod):
    before = _cmd(server_mod, "training:acceptance")
    assert before["ok"] is True and before["source"] == "config", before
    off = _cmd(server_mod, "training:acceptance off")
    assert off["enforced"] is False, off
    on = _cmd(server_mod, "training:acceptance on")
    assert on["enforced"] is True, on
    thr = _cmd(server_mod, "training:acceptance 0.6")
    assert thr["enforced"] is True and thr["threshold"] == 0.6, thr
    # 写入必须落盘可复读，不是只改内存
    again = _cmd(server_mod, "training:acceptance")
    assert again["threshold"] == 0.6, again
    bad = _cmd(server_mod, "training:acceptance 7")
    assert bad["ok"] is False and "0~1" in bad["error"], bad
    bad2 = _cmd(server_mod, "training:acceptance 随便")
    assert bad2["ok"] is False, bad2
    _cmd(server_mod, f"training:acceptance "
         f"{'on' if before['enforced'] else 'off'}")


def test_probe_and_gguf_fail_honestly_without_tools(server_mod, monkeypatch):
    monkeypatch.delenv("XIAOLING_LLAMA_CPP", raising=False)
    r = _cmd(server_mod, "training:gguf")
    assert r["ok"] is False and "llama.cpp" in r["reason"], r
    assert "XIAOLING_LLAMA_CPP" in r["reason"], r
    # 没有可验收的模型目录：直接报错，不启动一个「假装在跑」的后台任务
    p = _cmd(server_mod, "training:probe")
    assert p["ok"] is False and "找不到" in p["error"], p


def test_unknown_subcommand_lists_new_ops(server_mod):
    r = _cmd(server_mod, "training:nope")
    assert r["ok"] is False
    for op in ("mergestatus", "export", "gguf", "probe", "acceptance"):
        assert op in r["error"], r["error"]


def test_promotecheck_is_read_only(home, server_mod):
    """刷新成长页不该往 journal 里写流水：promotecheck 必须只读。"""
    gr = home
    tg._fake_base(gr)
    eng = gr.GrowthEngine()
    journal = gr.JOURNAL
    before = journal.read_text(encoding="utf-8") if journal.exists() else ""
    d = _cmd(server_mod, "growth:promotecheck")
    assert d["ok"] is True, d
    for k in ("size_gate_met", "acceptance", "will_run_acceptance",
              "progress_percent", "cap", "paused"):
        assert k in d, d
    after = journal.read_text(encoding="utf-8") if journal.exists() else ""
    assert after == before, "promotecheck 不应写 journal"


def test_export_returns_task_id_not_a_fake_result(server_mod):
    """长任务必须交后台任务表：同步回一个 ok=True 就是骗人。"""
    d = _cmd(server_mod, "training:export")
    assert d["ok"] is True and d["task_id"], d
    assert d["status"] == "running", d
    assert d["poll"].startswith("agent:task status "), d
