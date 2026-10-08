import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / 'backend'
for p in (ROOT, BACKEND):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core.knowledge_base import KnowledgeBase


def _make_kb(tmp_path):
    return KnowledgeBase(index_path=str(tmp_path / 'kb_index.json'))


def _long_doc():
    para = ('混合检索结合 TF-IDF 关键词匹配与语义向量相似度。'
            '中文分词使用 jieba 精确模式，停用词表过滤常见虚词。')
    return ('\n\n'.join([para] * 8))


def test_chunk_basic():
    pieces = KnowledgeBase.chunk_document(_long_doc(), chunk_size=200, overlap=40)
    assert len(pieces) >= 2
    assert all('chunk_index' in p and 'offset' in p and 'text' in p for p in pieces)
    offsets = [p['offset'] for p in pieces]
    assert offsets == sorted(offsets)
    assert offsets[0] == 0


def test_chunk_overlap_and_empty():
    text = '第一段内容。' * 100
    pieces = KnowledgeBase.chunk_document(text, chunk_size=120, overlap=20)
    assert len(pieces) >= 2
    for i in range(1, len(pieces)):
        assert pieces[i]['offset'] <= pieces[i - 1]['offset'] + 120
    assert KnowledgeBase.chunk_document('') == []
    assert KnowledgeBase.chunk_document('   \n  ') == []


def test_add_and_search_has_source(tmp_path):
    kb = _make_kb(tmp_path)
    kb.add_document('手册.md', _long_doc(), path='/docs/手册.md')
    results = kb.search('语义向量 相似度', top_k=3)
    assert results, '关键词检索应返回真实索引结果'
    top = results[0]
    assert top['source']['file'] == '手册.md'
    assert top['source']['path'] == '/docs/手册.md'
    assert isinstance(top['source']['chunk'], int)
    assert top['score'] > 0
    assert top['text']


def test_hybrid_search_degrades_without_semantic(tmp_path):
    kb = _make_kb(tmp_path)
    kb.add_document('a.md', _long_doc(), path='/a.md')
    kb.add_document('b.txt', '完全无关的另一篇文档，讲烹饪与种植。', path='/b.txt')
    results = kb.hybrid_search('语义向量 分词', top_k=2)
    assert results
    assert all('source' in r and 'chunk_id' in r for r in results)
    files = {r['source']['file'] for r in results}
    assert 'a.md' in files


def test_get_source_traceable(tmp_path):
    kb = _make_kb(tmp_path)
    kb.add_document('x.md', _long_doc(), path='/x.md')
    r = kb.search('混合检索', top_k=1)[0]
    src = kb.get_source(r['chunk_id'])
    assert src is not None
    assert src['file'] == 'x.md'
    assert src['text'] == r['text']
    assert isinstance(src['offset'], int)
    assert kb.get_source('not-exist') is None


def test_list_delete_documents(tmp_path):
    kb = _make_kb(tmp_path)
    kb.add_document('one.md', '检索关键词一：知识库分块策略。', path='/one.md')
    kb.add_document('two.md', '检索关键词二：引用溯源与偏移量记录。', path='/two.md')
    docs = kb.list_documents()
    assert {d['name'] for d in docs} == {'one.md', 'two.md'}
    assert all(d['chunks'] >= 1 for d in docs)

    assert kb.delete_document('one.md') is True
    assert kb.delete_document('one.md') is False
    names = {d['name'] for d in kb.list_documents()}
    assert names == {'two.md'}
    assert kb.total_docs == 1
    freqs = [c for c in kb.chunks.values() if c['doc_id'] == 'one.md']
    assert freqs == []


def test_reindex(tmp_path):
    kb = _make_kb(tmp_path)
    kb.add_document('r.md', '索引重建测试文档内容。', path='/r.md')
    info = kb.reindex()
    assert info['docs'] == 1
    assert info['chunks'] >= 1
    assert info['terms'] > 0
    assert kb.search('索引重建', top_k=1)


def test_persistence_roundtrip(tmp_path):
    kb = _make_kb(tmp_path)
    kb.add_document('p.md', '持久化往返测试：混合检索与引用溯源。', path='/p.md')
    assert os.path.exists(kb.index_path)

    kb2 = KnowledgeBase(index_path=str(tmp_path / 'kb_index.json'))
    results = kb2.search('持久化', top_k=1)
    assert results, '重载索引后应仍能检索到文档'
    assert results[0]['source']['file'] == 'p.md'
    assert kb2.get_source(results[0]['chunk_id'])['text']


def test_search_empty_index(tmp_path):
    kb = _make_kb(tmp_path)
    assert kb.search('任何词') == []
    assert kb.hybrid_search('任何词') == []
    assert kb.list_documents() == []
