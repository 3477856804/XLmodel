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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
