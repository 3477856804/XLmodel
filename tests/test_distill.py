#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""蒸馏链路回归测试（把「死链路」接成真链路之后的盯梢）。

动手前用探针钉死的事实（不是猜的）：

  1. 全仓库唯一的入库调用是 `engine._post_chat` 里的
     `store.add(text, reply, source="chat")` —— **teacher_output 永远不传**，
     实测入库记录 `deepseek_output=''`，`distill_samples()` 恒为 0 条。
  2. `deepseek_api_key` / `deepseek_base_url` / `teacher_model` 三个键只有
     写入方（config 默认值、setup.sh 让用户填、.env 迁移表），**零读取方**。
     用户填完 key，程序一次请求都不发。
  3. `DistillThrottle.check()/record()/cached()` **没有任何调用方**，但
     `samples_report()` 照样打印「蒸馏 API：开｜今日 0/200（缓存命中 0）｜
     本月 0.0000 元」—— 报表看着在运转，链路一根线都没通。

本文件测的是接通后的事实，每条都对应一个曾经的假：
  - 老师端配置必须真的被读，占位符「暂未填入」算没配；
  - 对话入库真的会登记蒸馏队列，且不在对话路径里联网；
  - 队列 → 真 HTTP 请求 → 写回 deepseek_output → **重算质量分**；
  - 失败/配额/缓存/失效记录各有如实的计数，绝不「问了 5 条成功 5 条」；
  - 训练组语料前会先蒸馏，且顺序可证（先问后写语料）；
  - 报表与 RPC 里不出现 API key 明文；没配置时不许说「开」。
"""
import importlib
import json
import os
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "backend", ROOT / "backend" / "rpc"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

tg = importlib.import_module("test_growth")
G = importlib.import_module("core.growth")


# --------------------------------------------------------------------------- #
#  桩老师：真 HTTP 服务，端口由系统分配，测试结束关掉了事
# --------------------------------------------------------------------------- #
class _Teacher:
    """OpenAI 兼容端点的行为桩。hits 记真实请求次数 —— 「发了几次」只能这么证。"""

    def __init__(self, mode="ok"):
        self.mode = mode
        self.hits = 0
        self.last_auth = None
        self.seen_prompts = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):            # 别把噪声刷进测试输出
                pass

            def do_POST(self):
                outer.hits += 1
                outer.last_auth = self.headers.get("Authorization") or ""
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(n).decode("utf-8"))
                except Exception:
                    body = {}
                outer.seen_prompts.append(
                    (body.get("messages") or [{}])[-1].get("content", ""))
                if outer.mode == "error":
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":{"message":"boom quota"}}')
                    return
                if outer.mode == "empty":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"choices":[{"message":{"content":""}}]}')
                    return
                reply = f"老师回答：关于「{outer.seen_prompts[-1]}」"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "choices": [{"message": {"role": "assistant",
                                             "content": reply}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 7},
                }, ensure_ascii=False).encode("utf-8"))

        self._h = H
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=5)


KEY = "sk-test-abcdef1234567890"


@pytest.fixture()
def home(tmp_path, monkeypatch):
    gr = tg._make_home(tmp_path)
    monkeypatch.setenv("XIAOLING_PENDING_DIR", str(tmp_path / "pending"))
    return gr


def _set_cfg(**kw):
    from core import config as C
    cfg = C.load(use_cache=False)
    g = cfg.setdefault("growth", {})
    g.update(kw.pop("growth", {}) or {})
    cfg.update(kw)
    C.save(cfg)
    return cfg


@pytest.fixture()
def teacher_stub(home):
    """配好老师端 + 起桩服务。yield (gr, stub)。"""
    t = _Teacher()
    _set_cfg(deepseek_api_key=KEY, deepseek_base_url=t.base_url,
             teacher_model="stub-teacher")
    try:
        yield home, t
    finally:
        t.stop()


def _eng(gr, **kw):
    _set_cfg(growth=kw)
    return gr.GrowthEngine()


def _store(gr):
    return gr.GrowthStore()


# --------------------------------------------------------------------------- #
#  1. 配置读取方终于存在了：此前三个键零读取方
# --------------------------------------------------------------------------- #

def test_teacher_config_treats_placeholder_key_as_unconfigured(home):
    """config 默认值就是「暂未填入」。把它当已配置 = 假装老师在场。"""
    cfg = G.teacher_config()
    assert cfg["configured"] is False, cfg
    assert cfg["has_key"] is False, cfg
    assert "API Key" in cfg["reason"], cfg
    # 绝不把 key 明文放进返回值
    assert KEY not in json.dumps(cfg, ensure_ascii=False)


def test_teacher_config_never_leaks_key(home, teacher_stub):
    cfg = G.teacher_config()
    assert cfg["configured"] is True, cfg
    assert cfg["key_tail"] == KEY[-4:], cfg
    assert KEY not in json.dumps(cfg, ensure_ascii=False)
    assert cfg["model"] == "stub-teacher" and cfg["base_url"]


def test_teacher_config_requires_all_three(home):
    _set_cfg(deepseek_api_key=KEY, deepseek_base_url="", teacher_model="")
    cfg = G.teacher_config()
    assert cfg["configured"] is False
    assert "deepseek_base_url" in cfg["reason"] and "teacher_model" in cfg["reason"]


def test_teacher_config_survives_broken_config(home, monkeypatch):
    from core import config as C
    monkeypatch.setattr(C, "load", lambda *a, **k: (_ for _ in ()).throw(
        OSError("读不到")))
    cfg = G.teacher_config()
    assert cfg["configured"] is False and "配置读不出来" in cfg["reason"], cfg


# --------------------------------------------------------------------------- #
#  2. 入队：登记在本地完成，对话路径不联网
# --------------------------------------------------------------------------- #

def test_register_for_distill_skips_when_unconfigured(home):
    eng = _eng(home)
    st = _store(home)
    row = st.add("今天天气怎么样", "晴", source="chat")
    assert eng.register_for_distill(row["id"], "今天天气怎么样") == ""
    assert st.distill_pending() == [], "没配老师端不该攒队列垃圾"


def test_register_for_distill_queues_when_configured(teacher_stub):
    gr, _t = teacher_stub
    eng = _eng(gr)
    st = _store(gr)
    row = st.add("帮我讲讲梯度下降", "嗯", source="chat")
    qid = eng.register_for_distill(row["id"], "帮我讲讲梯度下降")
    assert qid, qid
    pend = st.distill_pending()
    assert len(pend) == 1 and pend[0]["record_id"] == row["id"], pend
    # 重复登记不产生第二行（否则一次提问能攒出 N 条待问）
    assert eng.register_for_distill(row["id"], "帮我讲讲梯度下降") == qid
    assert len(st.distill_pending()) == 1


def test_register_for_distill_respects_switch(teacher_stub):
    gr, _t = teacher_stub
    eng = _eng(gr, distill_enabled=False)
    st = _store(gr)
    row = st.add("你好", "你好呀", source="chat")
    assert eng.register_for_distill(row["id"], "你好") == ""


def test_post_chat_registers_queue(home, teacher_stub):
    """生产入口的证明：_post_chat 之后队列里必须真有一行。

    此前这里只调 store.add(text, reply) —— teacher_output 永远不传，
    蒸馏样本恒为 0。
    """
    gr, _t = teacher_stub
    from core.engine import XiaoLing as XL
    eng = _eng(gr)
    fake = types.SimpleNamespace(
        interaction_count=0, last_active=0.0, conversation=[],
        memory_hub=None, persona=None, plugins=None, growth=eng,
        bus=types.SimpleNamespace(emit=lambda *a, **k: None))
    XL._post_chat(fake, "说点什么好呢", "我没想到")
    pend = eng.store.distill_pending()
    assert len(pend) == 1, pend
    assert pend[0]["prompt"] == "说点什么好呢"
    # 对话路径不能联网：桩服务一次都没被打
    assert _t.hits == 0, "蒸馏必须异步登记，不能卡在聊天里"


def test_post_chat_does_not_queue_duplicates(home, monkeypatch):
    """重复的对话（dup_of 非空）不该再占一条队列 —— 问老师要花真钱。"""
    gr = home
    t = _Teacher()
    monkeypatch.setattr(t, "mode", "ok")
    _set_cfg(deepseek_api_key=KEY, deepseek_base_url=t.base_url,
             teacher_model="stub-teacher")
    try:
        from core.engine import XiaoLing as XL
        eng = _eng(gr)
        fake = types.SimpleNamespace(
            interaction_count=0, last_active=0.0, conversation=[],
            memory_hub=None, persona=None, plugins=None, growth=eng,
            bus=types.SimpleNamespace(emit=lambda *a, **k: None))
        XL._post_chat(fake, "同样的问题", "答一次")
        XL._post_chat(fake, "同样的问题", "答两次")
        assert len(eng.store.distill_pending()) == 1, eng.store.distill_stats()
    finally:
        t.stop()


# --------------------------------------------------------------------------- #
#  3. 真请求：问了、写回、重算质量分
# --------------------------------------------------------------------------- #

def test_distill_round_hits_teacher_and_fills_record(teacher_stub):
    gr, t = teacher_stub
    eng = _eng(gr)
    st = eng.store
    before = st.add("什么是过拟合", "就是拟合过头了", source="chat")
    st.queue_distill(before["id"], "什么是过拟合")
    # 第二条走「用户纠正」路径，老师不该覆盖它
    r = distill = eng.distill_round(limit=5)
    assert r["ok"] and r["asked"] == 1 and r["answered"] == 1, r
    assert t.hits == 1, f"真的发了几次请求？{t.hits}"
    row = st.get(before["id"])
    assert "什么是过拟合" in row["deepseek_output"], row
    assert t.last_auth == "Bearer " + KEY, t.last_auth
    assert row["score_detail"]["teacher"] == 1.0, row["score_detail"]
    assert distill["tokens_in"] == 11 and distill["tokens_out"] == 7, distill
    # 质量分必须重算过：没老师时 teacher 权重只有 0.5
    assert row["quality_score"] > before["quality_score"], (
        before["quality_score"], row["quality_score"])


def test_distill_round_unconfigured_is_honest_not_silent(home):
    eng = _eng(home)
    r = eng.distill_round()
    assert r["ok"] is False and r["skipped"] is True, r
    assert r["reason"] == "not_configured", r
    assert "API Key" in r["message"], r


def test_distill_round_dry_run_never_touches_network(teacher_stub):
    gr, t = teacher_stub
    eng = gr.GrowthEngine(dry_run=True)
    r = eng.distill_round()
    assert r["ok"] is False and r.get("dry_run") is True, r
    assert t.hits == 0


def test_distill_round_switch_off_blocks_before_request(teacher_stub):
    gr, t = teacher_stub
    eng = _eng(gr, distill_enabled=False)
    st = eng.store
    row = st.add("问个问题", "答", source="chat")
    st.queue_distill(row["id"], "问个问题")
    r = eng.distill_round()
    assert r["ok"] is False and r["reason"] == "disabled", r
    assert t.hits == 0 and len(st.distill_pending()) == 1


def test_http_failure_counts_as_failure_not_answer(teacher_stub):
    gr, t = teacher_stub
    t.mode = "error"
    eng = _eng(gr)
    st = eng.store
    row = st.add("会失败的提问", "答", source="chat")
    st.queue_distill(row["id"], "会失败的提问")
    r = eng.distill_round(max_attempts=3)
    assert r["asked"] == 1 and r["answered"] == 0 and r["failed"] == 1, r
    assert r["errors"] and r["errors"][0]["reason"] == "http_error", r["errors"]
    assert st.get(row["id"])["deepseek_output"] == "", "失败不能写脏记录"
    # 第二次仍失败，第三次放弃 → 必须落到 failed，而不是一直 pending
    eng.distill_round(max_attempts=3)
    r3 = eng.distill_round(max_attempts=3)
    assert r3["gave_up"] == 1, r3
    assert st.distill_stats()["pending"] == 0, st.distill_stats()


def test_empty_completion_is_declared_not_saved_as_answer(teacher_stub):
    gr, t = teacher_stub
    t.mode = "empty"
    eng = _eng(gr)
    st = eng.store
    row = st.add("空响应", "答", source="chat")
    st.queue_distill(row["id"], "空响应")
    r = eng.distill_round()
    assert r["answered"] == 0 and r["failed"] == 1, r
    assert r["errors"][0]["reason"] == "empty_response", r["errors"]


def test_stale_queue_row_skipped_without_request(teacher_stub):
    gr, t = teacher_stub
    eng = _eng(gr)
    st = eng.store
    row = st.add("会被删掉的记录", "答", source="chat")
    st.queue_distill(row["id"], "会被删掉的记录")
    with st._lock:
        st.conn.execute("DELETE FROM records WHERE id=?", (row["id"],))
        st.conn.commit()
    r = eng.distill_round()
    assert r["asked"] == 0 and r["skipped_stale"] == 1, r
    assert t.hits == 0, "记录都没了还问老师 = 白花钱"
    assert st.distill_stats()["pending"] == 0, st.distill_stats()


def test_existing_teacher_output_not_queried_again(teacher_stub):
    gr, t = teacher_stub
    eng = _eng(gr)
    st = eng.store
    row = st.add("已有老师答案", "答", teacher_output="老师早先就答过了",
                 source="import")
    st.queue_distill(row["id"], "已有老师答案")
    r = eng.distill_round()
    assert r["answered"] == 1 and r["asked"] == 0, r
    assert t.hits == 0
    assert st.get(row["id"])["deepseek_output"] == "老师早先就答过了"


def test_set_teacher_output_refuses_empty_and_overwrite(teacher_stub):
    gr, _t = teacher_stub
    st = _store(gr)
    row = st.add("写入测试", "答", teacher_output="原文", source="chat")
    assert st.set_teacher_output(row["id"], "")["ok"] is False
    assert st.set_teacher_output("no-such-id", "x")["ok"] is False
    w = st.set_teacher_output(row["id"], "新的")
    assert w.get("ok") and w.get("unchanged"), w
    assert st.get(row["id"])["deepseek_output"] == "原文", "不许覆盖已有老师答案"


def test_set_teacher_output_adds_dpo_for_dislike(teacher_stub):
    """踩过的样本：有了老师答案才补得出 (chosen, rejected) 对。"""
    gr, _t = teacher_stub
    st = _store(gr)
    row = st.add("这句错了", "我瞎说的", feedback="dislike", source="chat")
    assert st.dpo_pairs() == []
    w = st.set_teacher_output(row["id"], "正确的老师答案")
    assert w["dpo_added"] is True, w
    pairs = st.dpo_pairs()
    assert len(pairs) == 1, pairs
    assert pairs[0]["chosen"] == "正确的老师答案"
    assert pairs[0]["rejected"] == "我瞎说的"
    # 重算不能把 DPO 加两遍
    st.set_teacher_output(row["id"], "另一份")
    assert len(st.dpo_pairs()) == 1


# --------------------------------------------------------------------------- #
#  4b. 时间预算：训练入口是同步的，老师端挂了不能让小凌不回话
# --------------------------------------------------------------------------- #

def test_time_budget_truncates_and_leaves_rest(teacher_stub):
    gr, t = teacher_stub
    # 让桩每次响应前睡 0.4s：预算 0.5s 就只做得完一两条
    orig = t._h.do_POST

    def do_POST_slow(self):
        time.sleep(0.4)
        orig(self)

    t._h.do_POST = do_POST_slow
    try:
        eng = _eng(gr, distill_time_budget_sec=0.5)
        st = eng.store
        for i in range(4):
            row = st.add(f"慢问题 {i}", "答", source="chat")
            st.queue_distill(row["id"], f"慢问题 {i}")
        r = eng.distill_round(limit=4, time_budget=0.5)
        assert r["ok"] and r["asked"] >= 1, r
        assert r["truncated"] >= 1, r
        assert "预算" in r["message"] and "留在队列" in r["message"], r["message"]
        # 剩下的必须还在队列里，而不是被标成失败或凭空消失
        assert r["remaining_pending"] == st.distill_stats()["pending"], r
        assert st.distill_stats()["pending"] >= 1, st.distill_stats()
        assert r["elapsed_sec"] < 4.0, r
    finally:
        t._h.do_POST = orig


def test_teacher_timeout_comes_from_config(home):
    """默认 12s；配成 1.5s 就该真的用 1.5s —— 不是写死在代码里。"""
    _set_cfg(growth={"distill_timeout_sec": 1.5})
    eng = _eng(home)
    assert eng.teacher.timeout == 1.5, eng.teacher.timeout
    _set_cfg(growth={"distill_timeout_sec": "abc"})
    eng2 = home.GrowthEngine()
    assert eng2.teacher.timeout == 12.0, eng2.teacher.timeout
    # 越界值钳回合理区间，不接受 0（等于永不超时）
    _set_cfg(growth={"distill_timeout_sec": 0})
    eng3 = home.GrowthEngine()
    assert eng3.teacher.timeout >= 1.0, eng3.teacher.timeout


def test_distill_result_reports_cost_honestly(teacher_stub):
    gr, _t = teacher_stub
    eng = _eng(gr, teacher_price_in=100.0, teacher_price_out=200.0)
    st = eng.store
    row = st.add("贵的问题", "答", source="chat")
    st.queue_distill(row["id"], "贵的问题")
    r = eng.distill_round()
    # 桩回 11 进 7 出 → 11*100/1e6 + 7*200/1e6
    assert abs(r["cost_yuan"] - (11 * 100 / 1e6 + 7 * 200 / 1e6)) < 1e-9, r
    assert r["queued"] == 1 and r["tokens_in"] == 11, r


def test_journal_records_distill_round(teacher_stub):
    gr, _t = teacher_stub
    eng = _eng(gr)
    st = eng.store
    row = st.add("记账", "答", source="chat")
    st.queue_distill(row["id"], "记账")
    eng.distill_round()
    j = [json.loads(l) for l in
         Path(gr.GROWTH_DIR, "journal.jsonl").read_text(
             encoding="utf-8").splitlines() if l.strip()]
    rec = [x for x in j if x.get("event") == "distill"]
    assert rec and rec[-1]["asked"] == 1 and rec[-1]["answered"] == 1, rec[-1:]
    # 只读的 status（RPC distill）不该往 journal 里写东西
    n = len(rec)
    eng.store.distill_stats()
    j2 = Path(gr.GROWTH_DIR, "journal.jsonl").read_text(encoding="utf-8")
    assert len([x for x in map(json.loads, j2.strip().splitlines())
               if x.get("event") == "distill"]) == n, "只读操作写了流水"


# --------------------------------------------------------------------------- #
#  4c. 节流器终于有调用方：配额与缓存是真的在算
# --------------------------------------------------------------------------- #

def test_throttle_quota_blocks_and_records(teacher_stub):
    gr, t = teacher_stub
    eng = _eng(gr, distill_daily_limit=1)
    st = eng.store
    for i in range(3):
        row = st.add(f"问题 {i}", "答", source="chat")
        st.queue_distill(row["id"], f"问题 {i}")
    r = eng.distill_round(limit=3)
    assert r["answered"] == 1, r
    assert r["quota"]["used_today"] == 1, r["quota"]
    assert t.hits == 1, f"配额 1 却发了 {t.hits} 次"
    # 第二天之前，剩下的只能留在队列里
    r2 = eng.distill_round(limit=3)
    assert r2["asked"] == 0 or r2["answered"] == 0 or r2["failed"] > 0, r2


def test_cache_second_same_prompt_no_http(teacher_stub):
    gr, t = teacher_stub
    eng = _eng(gr)
    st = eng.store
    a = st.add("同一个问题", "答A", source="chat")
    b = st.add("同一个问题问第二次", "答B", source="chat")
    st.queue_distill(a["id"], "同一个问题")
    st.queue_distill(b["id"], "同一个问题")
    r = eng.distill_round(limit=5)
    assert r["answered"] == 2, r
    assert t.hits == 1, f"缓存没生效：{t.hits} 次请求"
    assert r["from_cache"] == 1, r
    assert st.get(b["id"])["deepseek_output"] == st.get(a["id"])["deepseek_output"]


def test_usage_report_month_cost_not_zero_after_distill(teacher_stub):
    gr, _t = teacher_stub
    eng = _eng(gr)
    st = eng.store
    row = st.add("花钱的提问", "答", source="chat")
    st.queue_distill(row["id"], "花钱的提问")
    eng.distill_round()
    rep = eng.throttle.usage_report()
    assert rep["used_today"] == 1, rep
    assert rep["month"]["cost_yuan"] > 0, rep
    assert rep["cache_entries"] == 1, rep


# --------------------------------------------------------------------------- #
#  5. 蒸馏确实进了语料：顺序可证
# --------------------------------------------------------------------------- #

def test_train_round_distills_before_corpus(teacher_stub, monkeypatch):
    """「先问老师、后组语料」必须是可证的顺序，否则蒸馏永远进不了训练。"""
    gr, t = teacher_stub
    eng = _eng(gr, distill_enabled=True)
    row = eng.store.add("讲讲反向传播", "不太清楚", source="chat")
    eng.register_for_distill(row["id"], "讲讲反向传播")

    order = []
    real_round = eng.distill_round
    real_corpus = eng._round_corpus

    def _dr(*a, **k):
        order.append("distill")
        return real_round(*a, **k)

    def _rc(*a, **k):
        order.append("corpus")
        return real_corpus(*a, **k)

    monkeypatch.setattr(eng, "distill_round", _dr)
    monkeypatch.setattr(eng, "_round_corpus", _rc)
    fake_result = {"ok": True, "avg_loss": 0.5, "summary": "桩训练",
                   "steps": 1, "adapter_dir": str(eng.adapter_dir)}
    monkeypatch.setattr(eng.trainer, "train",
                        lambda **kw: dict(fake_result))
    res = eng.train_round()
    assert order[:2] == ["distill", "corpus"], order
    assert res["distill"]["answered"] == 1, res["distill"]
    # 语料里的答案应当是老师写的（corrected→teacher→base 的优先级）
    corpus = (Path(gr.GROWTH_DIR) / "round_corpus.jsonl")
    text = corpus.read_text(encoding="utf-8") if corpus.is_file() else ""
    assert "讲讲反向传播" in text, text
    assert t.hits == 1, t.hits


def test_sample_for_training_prefers_teacher_over_base(home):
    st = _store(home)
    st.add("只有一条线索", "基底瞎答", teacher_output="老师的好答案",
           source="chat")
    pack = st.sample_for_training(limit=10, min_quality=0.0,
                                  base_mix_ratio=0.0)
    answers = [s["answer"] for s in pack["samples"]]
    assert "老师的好答案" in answers, answers


# --------------------------------------------------------------------------- #
#  6. 报表与 RPC：没配置时不许说「开」
# --------------------------------------------------------------------------- #

def test_samples_report_says_unconfigured(home):
    eng = _eng(home)
    eng.store.add("你好", "你好呀", source="chat")
    txt = eng.samples_report()
    assert "未配置" in txt, txt
    assert "蒸馏 API：开" not in txt, "没配 key 却报「开」就是原来的假话"


def test_samples_report_shares_queue_when_configured(teacher_stub):
    gr, _t = teacher_stub
    eng = _eng(gr)
    row = eng.store.add("报队列", "答", source="chat")
    eng.register_for_distill(row["id"], "报队列")
    txt = eng.samples_report()
    assert "stub-teacher" in txt and "待问 1" in txt, txt
    assert KEY not in txt, "报表里绝不出现 key 明文"


def _growth_cmd(srv, cmd):
    return json.loads(srv._handle_growth_cmd(cmd))


@pytest.fixture()
def server_mod(home, monkeypatch):
    import server as srv
    gr = home
    monkeypatch.setattr(srv, "_get_engine",
                        lambda: types.SimpleNamespace(
                            growth=gr.GrowthEngine(), model_replace=None,
                            persona=None))
    return srv


def test_rpc_distill_read_only_is_honest(server_mod, home):
    d = _growth_cmd(server_mod, "distill")
    assert d["ok"] is True, d
    assert d["teacher"]["configured"] is False, d["teacher"]
    assert "note" in d and "next" in d, d
    assert KEY not in json.dumps(d, ensure_ascii=False)
    # 只读：不该写 journal、不该发请求
    assert "queue" in d, d


def test_rpc_distill_run_returns_task_not_fake_success(server_mod, home,
                                                       monkeypatch):
    """run 必须走真实 _bg_start（它会补 poll 字段）——只 patch 任务表，
    patch 掉 _bg_start 就等于把「前端能不能接着问」这件事跳过了。"""
    seen = {}

    class _Tasks:
        def start_task(self, name, job):
            seen["name"] = name
            seen["job"] = job
            return {"task_id": "t1", "state": "queued"}

    monkeypatch.setattr(server_mod, "_get_bg_tasks", lambda: _Tasks())
    d = _growth_cmd(server_mod, "distill run 3")
    assert seen["name"] == "growth:distill run", seen
    assert d["task_id"] == "t1" and d["poll"].endswith("t1"), d
    assert d["poll_result"].endswith("t1"), d
    # 任务函数本身可调用：签名是 (cancel_event, output)
    out = []
    res = seen["job"](types.SimpleNamespace(is_set=lambda: True),
                      lambda s: out.append(s))
    assert res == {"ok": False, "cancelled": True}, res
    assert out == [], "取消时不该已经开工"


def test_rpc_distill_switch_and_limit(server_mod, home):
    from core import config as C
    d = _growth_cmd(server_mod, "distill off")
    assert d["ok"] and d["written"] and d["enabled"] is False, d
    assert C.load()["growth"]["distill_enabled"] is False
    d2 = _growth_cmd(server_mod, "distill on")
    assert d2["enabled"] is True, d2
    d3 = _growth_cmd(server_mod, "distill limit 20")
    assert d3["ok"] and d3["limit"] == 20, d3
    bad = _growth_cmd(server_mod, "distill limit 0")
    assert bad["ok"] is False and "1~200" in bad["error"], bad
    bad2 = _growth_cmd(server_mod, "distill limit abc")
    assert bad2["ok"] is False, bad2


def test_rpc_distill_after_configured_shows_key_tail(teacher_stub):
    gr, _t = teacher_stub
    import server as srv
    srv._get_engine = lambda: types.SimpleNamespace(
        growth=gr.GrowthEngine(), model_replace=None, persona=None)
    d = _growth_cmd(srv, "distill")
    assert d["teacher"]["configured"] is True, d
    assert d["teacher"]["key_tail"] == KEY[-4:], d["teacher"]
    assert KEY not in json.dumps(d, ensure_ascii=False)


def test_unknown_growth_op_lists_distill(server_mod):
    d = _growth_cmd(server_mod, "nonsense")
    assert "distill" in d["error"], d


def test_growth_distill_bad_subcommand(server_mod):
    d = _growth_cmd(server_mod, "distill sideways")
    assert d["ok"] is False and "未知" in d["error"], d


# --------------------------------------------------------------------------- #
#  7. 客户端自身的降级判据（不发网络也能验）
# --------------------------------------------------------------------------- #

def test_parse_completion_shapes():
    assert G._parse_completion({"choices": [{"message": {"content": " 嗨 "}}]})[0] == "嗨"
    assert G._parse_completion({"choices": [{"text": "备用字段"}]})[0] == "备用字段"
    assert G._parse_completion([]) == ("", 0, 0)
    assert G._parse_completion({"choices": []})[0] == ""
    ti, to = G._parse_completion(
        {"choices": [{"message": {"content": "x"}}],
         "usage": {"prompt_tokens": 3, "completion_tokens": 4}})[1:]
    assert (ti, to) == (3, 4)


def test_teacher_ask_blocked_never_opens_socket(home):
    """未配置时 gate 就该拦住 —— 连 DNS 都不该查。"""
    tc = G.TeacherClient()
    r = tc.ask("随便问点什么", cfg={"configured": False, "reason": "没配",
                                   "model": "", "base_url": ""})
    assert r["ok"] is False and r["reason"] == "not_configured", r
    assert r["text"] == ""


def test_teacher_unreachable_reports_network_reason(home, monkeypatch):
    _set_cfg(deepseek_api_key=KEY,
             deepseek_base_url="http://127.0.0.1:1/v1",
             teacher_model="x")
    tc = G.TeacherClient(timeout=2.0)
    r = tc.ask("打不开的地址", cfg=G.teacher_config())
    assert r["ok"] is False and r["reason"] == "network", r


def test_mark_distill_rejects_unknown_status(home):
    st = _store(home)
    row = st.add("状态字", "答", source="chat")
    qid = st.queue_distill(row["id"], "状态字")
    assert qid
    assert st.mark_distill(qid, "answered") is True
    assert st.mark_distill(qid, "whatever") is False, "不接受的结论不能写进去"
