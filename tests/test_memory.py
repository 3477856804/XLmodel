#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记忆系统（backend/core/memory.py）单元测试。

覆盖：
  1. 长期记忆 add / search / by_tag / recent / stats
  2. RAG add_document / search_keyword / search_semantic / format_for_prompt
  3. 语义向量降级模式（无 torch -> hash-ngram，诚实标注）
  4. 持久化（落盘后重新加载仍在）

全部使用 tmp_path 作为存储路径，不污染真实 DATA_DIR；不需要 torch / 模型权重 / 网络。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.core.memory import (
    LongTermMemory, RAG, KnowledgeGraph, get_embedding_backend, embed_text,
)


# ---------------------------------------------------------------------------
# 1. 长期记忆
# ---------------------------------------------------------------------------
def test_ltm_add_and_count(tmp_path):
    m = LongTermMemory(path=str(tmp_path / "mem.json"))
    m.add("user", "我喜欢猫", importance=0.8, tags=["宠物"])
    m.add("user", "我在做 Python 项目", importance=0.5, tags=["编程"])
    assert m.stats()["total"] == 2


def test_ltm_search_finds_relevant(tmp_path):
    m = LongTermMemory(path=str(tmp_path / "mem.json"))
    m.add("user", "今天去吃了苹果和香蕉")
    m.add("user", "量子力学的薛定谔方程很有意思")
    hits = m.search("苹果", top_k=3)
    assert hits, "应至少命中一条"
    assert "苹果" in hits[0].content


def test_ltm_by_tag(tmp_path):
    m = LongTermMemory(path=str(tmp_path / "mem.json"))
    m.add("user", "t1", tags=["工作"])
    m.add("user", "t2", tags=["生活"])
    m.add("user", "t3", tags=["工作"])
    assert len(m.by_tag("工作")) == 2


def test_ltm_recent(tmp_path):
    m = LongTermMemory(path=str(tmp_path / "mem.json"))
    for i in range(5):
        m.add("user", f"条目{i}")
    recent = m.recent(2)
    assert len(recent) == 2
    assert "条目4" in recent[-1].content


def test_ltm_persistence(tmp_path):
    p = str(tmp_path / "mem.json")
    m = LongTermMemory(path=p)
    m.add("user", "需要记住的私密事项", tags=["重要"])
    m.flush()
    # 重新加载：数据应从磁盘读回
    m2 = LongTermMemory(path=p)
    assert m2.stats()["total"] == 1
    assert any("私密事项" in i.content for i in m2.recent(10))


# ---------------------------------------------------------------------------
# 2. RAG
# ---------------------------------------------------------------------------
def test_rag_add_and_keyword_search(tmp_path):
    rag = RAG(path=str(tmp_path / "rag.jsonl"))
    rag.add_document("小凌的沙箱位于用户数据目录", metadata={"src": "doc1"})
    rag.add_document("今天天气晴朗适合出门散步", metadata={"src": "doc2"})
    hits = rag.search_keyword("沙箱", top_k=3)
    assert hits, "应检索到包含沙箱的文档"
    assert "沙箱" in hits[0]["content"]


def test_rag_semantic_search_returns_results(tmp_path):
    rag = RAG(path=str(tmp_path / "rag.jsonl"))
    rag.add_document("Python 是一门编程语言")
    rag.add_document("今天午饭吃了牛肉面")
    hits = rag.search_semantic("Python", top_k=2)
    # 降级后端下仍是关键词级匹配，至少不报错且结构正确
    assert isinstance(hits, list)


def test_rag_format_for_prompt(tmp_path):
    rag = RAG(path=str(tmp_path / "rag.jsonl"))
    rag.add_document("函数式编程用纯函数组合逻辑")
    text = rag.format_for_prompt("函数式", top_k=1)
    assert "相关知识" in text


def test_rag_persistence(tmp_path):
    p = str(tmp_path / "rag.jsonl")
    rag = RAG(path=p)
    rag.add_document("会被持久化的知识条目")
    rag2 = RAG(path=p)
    assert rag2.stats()["documents"] >= 1


# ---------------------------------------------------------------------------
# 3. 语义向量降级
# ---------------------------------------------------------------------------
def test_embedding_backend_is_hash_fallback():
    """无 torch / sentence-transformers 时，后端必须诚实降级为 hash-ngram。"""
    backend = get_embedding_backend()
    assert backend == "hash-ngram", f"本环境应走降级后端，实际 {backend}"


def test_embed_text_degraded_dim_and_tag():
    vec, tag = embed_text("测试文本")
    assert tag == "hash-ngram"
    assert len(vec) == 512
    # 归一化向量不应全 0
    assert any(abs(v) > 1e-9 for v in vec)


def test_rag_stats_reports_backend(tmp_path):
    rag = RAG(path=str(tmp_path / "rag.jsonl"))
    s = rag.stats()
    assert s["embedding_backend"] == "hash-ngram"


# ---------------------------------------------------------------------------
# 4. 知识图谱增强方法
# ---------------------------------------------------------------------------
def _make_graph(tmp_path):
    g = KnowledgeGraph(path=str(tmp_path / "kg.json"))
    g.learn("小明是学生")
    g.learn("小明喜欢篮球")
    g.learn("篮球属于运动")
    g.learn("小红喜欢音乐")
    return g


def test_kg_get_entity(tmp_path):
    g = _make_graph(tmp_path)
    info = g.get_entity("小明")
    assert info["found"] is True
    assert info["count"] >= 2
    verbs = {r["verb"] for r in info["relations"]}
    assert "是" in verbs or "喜欢" in verbs


def test_kg_get_entity_missing(tmp_path):
    g = _make_graph(tmp_path)
    info = g.get_entity("不存在的实体")
    assert info["found"] is False


def test_kg_get_related_entities(tmp_path):
    g = _make_graph(tmp_path)
    rels = g.get_related_entities("小明", depth=2)
    names = {r["name"] for r in rels}
    assert "篮球" in names
    assert all("hops" in r for r in rels)


def test_kg_get_graph_stats(tmp_path):
    g = _make_graph(tmp_path)
    s = g.get_graph_stats()
    assert s["entities"] >= 2
    assert s["relations"] >= 3
    assert s["most_active"], "应有最活跃实体列表"
    assert s["most_active"][0]["count"] >= 1


def test_kg_export_json_and_graphml(tmp_path):
    g = _make_graph(tmp_path)
    js = g.export_graph("json")
    assert "entities" in js
    xml = g.export_graph("graphml")
    assert "<graphml" in xml
    assert "<node" in xml


def test_kg_search_entities(tmp_path):
    g = _make_graph(tmp_path)
    hits = g.search_entities("小")
    names = {h["name"] for h in hits}
    assert "小明" in names
    assert all("count" in h for h in hits)


# ---------------------------------------------------------------------------
# 5. 长期记忆增强方法
# ---------------------------------------------------------------------------
def test_ltm_get_memory_stats(tmp_path):
    m = LongTermMemory(path=str(tmp_path / "mem.json"))
    m.add("user", "带标签内容", tags=["工作", "编程"])
    m.add("user", "另一条", tags=["工作"])
    s = m.get_memory_stats()
    assert s["total"] == 2
    assert s["tag_distribution"].get("工作") == 2
    assert len(s["recent"]) == 2


def test_ltm_search_by_date(tmp_path):
    import time as _t
    m = LongTermMemory(path=str(tmp_path / "mem.json"))
    m.add("user", "今天的内容")
    today = _t.strftime("%Y-%m-%d")
    items = m.search_by_date(today, today)
    assert any("今天的内容" in i["content"] for i in items)


def test_ltm_forget_old_keeps_important(tmp_path):
    import time as _t
    m = LongTermMemory(path=str(tmp_path / "mem.json"))
    m.add("user", "重要记忆", importance=0.95)
    m.add("user", "普通记忆", importance=0.3)
    removed = m.forget_old(days=0, keep_importance=0.8)
    assert removed >= 1
    contents = [i.content for i in m.recent(10)]
    assert "重要记忆" in contents


# ---------------------------------------------------------------------------
# 6. 人格系统：情绪/话术必须是可复现的真值，不是随机数
# ---------------------------------------------------------------------------
def _persona_mod():
    from backend.core import memory as M
    return M


def test_emotion_no_longer_fabricated_by_random(tmp_path):
    """没有情绪线索时不再掷骰子换情绪，而是确定性地衰减 / 归平静。

    旧实现在 pos==neg==0 时调用 _random_shift()，按一张手写概率表随机挑
    一种情绪 —— 前端展示的情绪与能量因此每次刷新都可能不同，且没有任何
    输入能解释它。这条用例锁死「同样的输入序列 → 同样的输出」。
    """
    M = _persona_mod()

    def seq():
        e = M.EmotionEngine()
        out = []
        for text, q in [("今天天气不错", 0.5), ("嗯", 0.5), ("你好", 0.5),
                        ("继续", 0.5), ("我有点累了想睡觉", 0.5), ("好的", 0.5)]:
            e.update(text, quality=q)
            out.append((e.get_emotion().value, round(e.get_intensity(), 6),
                        e.shift_reason()))
        return out

    a, b = seq(), seq()
    assert a == b, f"情绪路径不可复现：{a} != {b}"
    # 有明确线索时按线索走，并记录来源
    assert a[4][0] == "tired" and a[4][2] == "keyword:tired", a[4]
    # 无线索的那几步必须被标注成 no_signal / stale_decay，而不是伪装成情绪波动
    for i in (0, 1, 2, 3, 5):
        assert a[i][2].startswith(("no_signal", "stale_decay")), (i, a[i])


def test_emotion_uses_quality_signal_when_no_keywords(tmp_path):
    """文本里没有情绪词、但质量分是真实信号，不能因为「没关键词」就丢掉。"""
    M = _persona_mod()
    e = M.EmotionEngine()
    e.update("嗯", quality=0.95)
    assert e.get_emotion() == M.Emotion.HAPPY
    assert e.shift_reason() == "signal:quality", e.shift_reason()
    e2 = M.EmotionEngine()
    e2.update("哦", quality=0.05)
    assert e2.get_emotion() == M.Emotion.SAD


def test_emotion_snapshot_exposes_reason(tmp_path):
    """snapshot 必须带 reason，否则前端只能自己猜情绪是怎么来的（旧 bug）。"""
    M = _persona_mod()
    e = M.EmotionEngine()
    e.update("谢谢你，好棒", quality=0.5)
    snap = e.snapshot()
    assert snap["reason"] == "keyword:positive", snap
    assert snap["label"] == "开心"
    assert snap["history"][-1]["reason"] == "keyword:positive"


def test_proactive_talk_is_deterministic(tmp_path):
    """主动话术：同一状态序列必须得到同一串句子（旧的 random.choice 不可复现）。"""
    M = _persona_mod()
    a = M.ProactiveEngine()
    b = M.ProactiveEngine()
    sa = [a.talk(M.Emotion.NEUTRAL, M.RelationshipLevel.FRIEND) for _ in range(4)]
    sb = [b.talk(M.Emotion.NEUTRAL, M.RelationshipLevel.FRIEND) for _ in range(4)]
    assert sa == sb, (sa, sb)
    # 轮转而不是随机：同池内不会连续重复
    assert len(set(sa)) >= 3, sa
    assert a.last_talk_reason()


def test_proactive_due_reminder_beats_smalltalk(tmp_path):
    """到点的提醒是真实待办，必须压过寒暄，而且 talk() 不能偷偷吃掉它。"""
    import time as _t
    M = _persona_mod()
    p = M.ProactiveEngine()
    p.reminders.append({"text": "该喝水了", "time": _t.time() - 1,
                        "done": False, "created_at": _t.time()})
    got = p.talk(M.Emotion.HAPPY, M.RelationshipLevel.BONDED)
    assert got == "该喝水了", got
    assert p.last_talk_reason().startswith("reminder:due"), p.last_talk_reason()
    # 标记完成仍然只由 check_reminders 负责
    assert len(p.pending_reminders()) == 1
    assert p.check_reminders() == ["该喝水了"]


def test_proactive_respects_relationship_level(tmp_path):
    """时段内且关系不够近时，用时段问候，不用「有点想你了」这种越界话术。"""
    import time as _t
    M = _persona_mod()
    h = _t.localtime().tm_hour
    in_bucket = (5 <= h < 11) or (11 <= h < 14) or (17 <= h < 22) or h >= 23 or h < 5
    p = M.ProactiveEngine()
    p.talk(M.Emotion.SAD, M.RelationshipLevel.STRANGER)
    reason = p.last_talk_reason()
    if in_bucket:
        assert reason.startswith("time:"), (h, reason)
    else:
        assert reason.startswith("emotion:sad"), (h, reason)


def test_persona_snapshot_exposes_level_config(tmp_path):
    """关系档位定义必须从后端出，前端才不用在 Dart 里写死五档文案。"""
    M = _persona_mod()
    per = M.PersonaEngine(state_path=str(tmp_path / "persona.json"))
    snap = per.snapshot()
    levels = snap["levels"]
    assert [lv["label"] for lv in levels] == ["陌生人", "认识", "朋友", "亲密", "羁绊"]
    assert [lv["threshold"] for lv in levels] == [0, 10, 30, 60, 100]
    assert snap["relationship"]["level"] == "stranger"
    assert snap["next_threshold"] == 10
    assert "reason" in snap["emotion"]


def test_persona_persists_across_reload(tmp_path):
    """真值要能落盘重载，否则每次重启关系都归零、前端进度条是装饰。"""
    M = _persona_mod()
    path = str(tmp_path / "persona.json")
    p1 = M.PersonaEngine(state_path=path)
    for _ in range(6):
        p1.update_from_chat("谢谢你，真棒", quality=0.9)
    p1.flush()                      # engine 在每轮对话后就是这么做的
    score = p1.relationship.score
    label = p1.relationship.get_level_label()
    assert score > 0 and label != "陌生人", (score, label)
    p2 = M.PersonaEngine(state_path=path)
    assert p2.relationship.score == score
    assert p2.relationship.get_level_label() == label


def test_reminder_changes_persist_without_chat(tmp_path):
    """加提醒 / 提醒到点，必须自己触发落盘。

    以前只有 update_from_chat() 会置 _dirty，所以「设个 30 分钟后的提醒」
    之后如果用户不再说话，重启时提醒就没了；反过来已完成的提醒会复活。
    """
    import time as _t
    M = _persona_mod()
    path = str(tmp_path / "persona.json")
    p1 = M.PersonaEngine(state_path=path)
    p1.proactive.add_reminder("喝水", minutes=30)
    p1.proactive.reminders.append({"text": "到点的", "time": _t.time() - 5,
                                   "done": False, "created_at": _t.time()})
    assert p1.proactive.check_reminders() == ["到点的"]
    # 没有任何一次 flush() 调用 —— 全靠 on_change 自己把状态落盘
    p2 = M.PersonaEngine(state_path=path)
    texts = [(r["text"], r["done"]) for r in p2.proactive.reminders]
    assert ("喝水", False) in texts, texts
    assert ("到点的", True) in texts, texts


def test_reminder_completed_via_rpc_path_actually_persists(tmp_path):
    """CompleteReminder 走的必须是会落盘的路径。

    以前 RPC 层直接 pro.reminders[i]['done'] = True，再 persona.flush()；
    但 flush 的实现是 `if self._dirty: self._save()`，而改 done 不会置
    _dirty，于是接口返回「提醒已完成」、磁盘却没动，重启后提醒复活。
    """
    import json
    import time as _t
    M = _persona_mod()
    path = str(tmp_path / "persona.json")
    p1 = M.PersonaEngine(state_path=path)
    due = _t.time() + 60
    p1.proactive.reminders.append({"text": "开会", "time": due,
                                   "done": False, "created_at": _t.time()})
    # 走 RPC 的读法：pending 里有，且未落盘
    assert [r["text"] for r in p1.proactive.pending_reminders()] == ["开会"]
    assert p1.proactive.mark_done(due) == 1
    with open(path, encoding="utf-8") as f:
        on_disk = json.load(f)
    saved = on_disk["reminders"][0]
    assert saved["text"] == "开会" and saved["done"] is True, on_disk
    p2 = M.PersonaEngine(state_path=path)
    assert p2.proactive.pending_reminders() == [], p2.proactive.reminders
    # 重复完成不得谎报成功
    assert p1.proactive.mark_done(due) == 0
    # 时间戳容差：默认 1e-6 只认精确值，前端传回浮点截断值时要能命中
    due2 = _t.time() + 120
    p1.proactive.reminders.append({"text": "取件", "time": due2,
                                   "done": False, "created_at": _t.time()})
    assert p1.proactive.mark_done(due2 + 0.01) == 0
    assert p1.proactive.mark_done(due2 + 0.0005, tol=1e-3) == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
