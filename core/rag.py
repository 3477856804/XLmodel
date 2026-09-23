#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 本地长期记忆检索（RAG）
================================

沿用并补全小玥（Electron 版用 @xenova/transformers + BGE-small-zh 做本地向量检索）的能力，
在 Python 侧提供**零依赖可用**的等价实现：

* 默认：字符 n-gram 哈希向量（512 维）+ 余弦相似度 —— 纯 Python/可选 numpy，离线、秒级
* 增强：若本地存在 sentence-transformers / transformers 嵌入模型，可开关切换为语义向量
* 与 `LongTermMemory` 互补：RAG 负责"想起来"，长期记忆负责"沉淀"

存储：`.star_core/rag/index.jsonl`（原文 + 元数据），向量随后懒加载。
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

from core.paths import APP_DIR, STAR_DIR

BASE_DIR = APP_DIR
RAG_DIR = STAR_DIR / 'rag'
INDEX = RAG_DIR / 'index.jsonl'

try:                                    # numpy 可选
    import numpy as _np
except Exception:                       # noqa: BLE001
    _np = None


def _tokens(text: str):
    text = (text or '').lower()
    words = re.findall(r'[a-z0-9]+', text)
    for w in words:
        yield w
    for seg in re.findall(r'[\u4e00-\u9fff]+', text):
        for n in (1, 2, 3):
            for i in range(len(seg) - n + 1):
                yield seg[i:i + n]


def embed(text: str, dim: int = 512):
    """字符 n-gram 哈希向量（L2 归一化）。"""
    vec = [0.0] * dim
    for tok in _tokens(text):
        h = hash(tok) % dim
        sign = 1.0 if (hash(tok + '#') % 2) else -1.0
        vec[h] += sign * (1.0 + 0.5 * min(len(tok), 4))
    if _np is not None:
        a = _np.asarray(vec, dtype='float32')
        n = float(_np.linalg.norm(a)) or 1.0
        return a / n
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def cosine(a, b) -> float:
    if _np is not None and isinstance(a, _np.ndarray):
        return float(a @ b)
    return float(sum(x * y for x, y in zip(a, b)))


class LocalRAG:
    def __init__(self, path: Path | None = None, dim: int = 512, embedder=None):
        self.path = Path(path) if path else INDEX
        self.dim = dim
        self.embedder = embedder or (lambda t: embed(t, dim))
        self.items = []          # [{id, text, meta, ts, vec}]
        self._loaded = False

    # ------------------------------------------------------------------ IO
    def load(self):
        self.items = []
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                d['vec'] = self.embedder(d.get('text', ''))
                self.items.append(d)
        self._loaded = True
        return len(self.items)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            for it in self.items:
                f.write(json.dumps({k: v for k, v in it.items() if k != 'vec'},
                                   ensure_ascii=False) + '\n')
        return self.path

    def _ensure(self):
        if not self._loaded:
            self.load()

    # ------------------------------------------------------------------ API
    def add(self, text: str, meta: dict | None = None, dedup: bool = True):
        self._ensure()
        text = (text or '').strip()
        if not text:
            return None
        if dedup:
            for it in self.items[-60:]:
                if it.get('text', '').strip() == text:
                    return it['id']
        item = {'id': f'r{int(time.time() * 1000)}', 'text': text, 'meta': meta or {},
                'ts': time.time(), 'vec': self.embedder(text)}
        self.items.append(item)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({k: v for k, v in item.items() if k != 'vec'},
                               ensure_ascii=False) + '\n')
        return item['id']

    def search(self, query: str, k: int = 4, min_score: float = 0.06):
        self._ensure()
        if not self.items or not query:
            return []
        qv = self.embedder(query)
        scored = []
        for it in self.items:
            s = cosine(qv, it['vec'])
            if s >= min_score:
                scored.append((s, it))
        scored.sort(key=lambda x: -x[0])
        return [{'score': round(s, 4), 'text': it['text'], 'meta': it.get('meta', {}),
                 'ts': it.get('ts')} for s, it in scored[:k]]

    def context(self, query: str, k: int = 4) -> str:
        hits = self.search(query, k=k)
        if not hits:
            return ''
        lines = [f"- {h['text'][:300]}" for h in hits]
        return '【相关记忆】\n' + '\n'.join(lines)

    def stats(self) -> dict:
        self._ensure()
        return {'items': len(self.items), 'path': str(self.path), 'dim': self.dim,
                'bytes': self.path.stat().st_size if self.path.exists() else 0}

    def clear(self):
        self.items = []
        self._loaded = True
        if self.path.exists():
            self.path.unlink()
        return True


_SINGLETON = None


def get_rag(**kw) -> LocalRAG:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = LocalRAG(**kw)
    return _SINGLETON


if __name__ == '__main__':
    import sys
    r = get_rag()
    if len(sys.argv) > 1 and sys.argv[1] == 'add':
        print(r.add(' '.join(sys.argv[2:])))
    elif len(sys.argv) > 1 and sys.argv[1] == 'search':
        for h in r.search(' '.join(sys.argv[2:])):
            print(h['score'], h['text'][:80])
    else:
        print(json.dumps(r.stats(), ensure_ascii=False, indent=1))
