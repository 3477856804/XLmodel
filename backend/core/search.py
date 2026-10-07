#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 联网搜索 Agent（免 Key）
=================================

迁移自小玥的「全网搜索 Agent」（原实现走 Electron 主进程 + DuckDuckGo Lite）。
提供：
  * `search_web(query, n)`      → [{title, url, snippet}]
  * `fetch_text(url, max_chars)`→ 网页正文（去标签）
  * `answer_with_search(query)` → 检索 + 拼上下文，交给本地模型/老师模型作答
离线自动降级：无网络时返回 []，由引擎走本地知识；本地无网络时进一步
在 data/knowledge/ 目录做关键词匹配兜底，保证不崩溃。
"""
from __future__ import annotations

import gzip
import html
import json
import re
import time
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

try:
    from .config import DATA_DIR
except Exception:  # pragma: no cover
    DATA_DIR = Path("data")

KNOWLEDGE_DIR = DATA_DIR / "knowledge"

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# ---- 搜索结果缓存（LRU，最多 50 条，5 分钟 TTL）----
_cache: dict = {}            # query -> (timestamp, results)
_cache_lock = __import__('threading').Lock()
_CACHE_TTL = 300.0
_CACHE_MAX = 50
# ---- 搜索历史（最近 20 条 query）----
_history: list = []
_history_lock = __import__('threading').Lock()
_HISTORY_MAX = 20


def clear_cache() -> int:
    """清空搜索结果缓存，返回清除条数。"""
    with _cache_lock:
        n = len(_cache)
        _cache.clear()
        return n


def get_history() -> list:
    """返回最近搜索过的 query 列表。"""
    with _history_lock:
        return list(_history)


def clear_history() -> None:
    """清空搜索历史。"""
    with _history_lock:
        _history.clear()


def _remember_history(query: str) -> None:
    q = (query or '').strip()
    if not q:
        return
    with _history_lock:
        if _history and _history[-1] == q:
            return
        _history.append(q)
        del _history[:-_HISTORY_MAX]


def _sort_results(results: list, sort_by: str = 'relevance') -> list:
    """结果排序：relevance 按 score 降序（若无 score 保持原序）；time 按时间倒序。"""
    if not results:
        return results
    if sort_by == 'time':
        return sorted(results,
                      key=lambda r: r.get('time') or r.get('ts') or 0,
                      reverse=True)
    if any('score' in r for r in results):
        return sorted(results, key=lambda r: r.get('score', 0), reverse=True)
    return results


def _open(url, data=None, headers=None, timeout=8):
    req = urllib.request.Request(url, data=data, headers={'User-Agent': UA,
                                                          'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.6',
                                                          **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = r.headers.get('Content-Encoding', '')
        if 'gzip' in enc:
            raw = gzip.decompress(raw)
        elif 'deflate' in enc:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        ctype = r.headers.get('Content-Type', '')
        m = re.search(r'charset=([\w-]+)', ctype)
        return raw.decode(m.group(1) if m else 'utf-8', 'ignore')


def local_search(query: str, n: int = 5) -> list:
    """本地知识库兜底：在 data/knowledge/ 下做关键词匹配。

    支持 .txt / .md / .jsonl 文件；按 query 分词命中行数打分。
    目录不存在或无命中时返回 []，绝不抛异常。
    """
    if not query or not KNOWLEDGE_DIR.exists():
        return []
    try:
        words = [w for w in re.split(r"[\s,，。；;：:！!？?、]+", query) if len(w) >= 2]
        if not words:
            words = [query.strip()]
        hits = []
        files = [p for p in KNOWLEDGE_DIR.rglob("*")
                 if p.is_file() and p.suffix.lower() in (".txt", ".md", ".jsonl")]
        for fp in files:
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                score = sum(1 for w in words if w in line)
                if score:
                    hits.append((score, fp.name, line[:300]))
        hits.sort(key=lambda x: x[0], reverse=True)
        out = []
        for _, fname, snip in hits[:n]:
            out.append({"title": fname, "url": "", "snippet": snip,
                        "source": "local"})
        return out
    except Exception:  # noqa: BLE001
        return []


def search_web(query: str, n: int = 5, engine: str = 'duckduckgo',
               sort_by: str = 'relevance'):
    """免 Key 联网搜索；联网失败时回退本地知识库。"""
    key = f'{engine}|{n}|{query.strip()}'
    # 命中缓存（5 分钟内）直接返回
    with _cache_lock:
        hit = _cache.get(key)
        if hit and (time.time() - hit[0]) < _CACHE_TTL:
            return _sort_results(hit[1], sort_by)
    _remember_history(query)
    if engine == 'duckduckgo':
        res = _ddg(query, n)
    elif engine == 'searx':
        res = _searx(query, n)
    else:
        res = _ddg(query, n)
    if res:
        with _cache_lock:
            _cache[key] = (time.time(), res)
            if len(_cache) > _CACHE_MAX:
                _cache.pop(next(iter(_cache)))
        return _sort_results(res, sort_by)
    local = local_search(query, n)
    if local:
        print(f'  [搜索] 联网不可用，命中本地知识库 {len(local)} 条')
    return _sort_results(local, sort_by)


def _ddg(query: str, n: int = 5):
    try:
        url = 'https://lite.duckduckgo.com/lite/?' + urllib.parse.urlencode({'q': query})
        page = _open(url, timeout=10)
    except Exception as e:                                            # noqa: BLE001
        print(f'  [搜索] 失败：{type(e).__name__}: {e}')
        return []
    out = []
    # lite 版表格结构：<a class="result-link" href="..">title</a> + <td class="result-snippet">
    for m in re.finditer(r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        link, title = m.group(1), re.sub(r'<[^>]+>', '', m.group(2))
        seg = page[m.end():m.end() + 1200]
        sn = re.search(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', seg, re.S)
        snippet = re.sub(r'<[^>]+>', ' ', sn.group(1)) if sn else ''
        out.append({'title': html.unescape(title).strip(),
                    'url': html.unescape(link),
                    'snippet': re.sub(r'\s+', ' ', html.unescape(snippet)).strip()[:300]})
        if len(out) >= n:
            break
    if not out:      # 兼容新版结构
        for m in re.finditer(r'<a rel="nofollow" href="(http[^"]+)"[^>]*>(.*?)</a>', page, re.S):
            out.append({'title': re.sub(r'<[^>]+>', '', m.group(2)).strip(),
                        'url': m.group(1), 'snippet': ''})
            if len(out) >= n:
                break
    return out


def _searx(query: str, n: int = 5, instance='https://searx.be'):
    try:
        url = f'{instance}/search?' + urllib.parse.urlencode({'q': query, 'format': 'json'})
        data = json.loads(_open(url, timeout=10))
        return [{'title': r.get('title'), 'url': r.get('url'), 'snippet': r.get('content', '')[:300]}
                for r in data.get('results', [])[:n]]
    except Exception:                                                 # noqa: BLE001
        return []


def fetch_text(url: str, max_chars: int = 3000):
    try:
        page = _open(url, timeout=10)
    except Exception:                                                 # noqa: BLE001
        return ''
    page = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', ' ', page, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', ' ', page)
    text = html.unescape(re.sub(r'\s+', ' ', text)).strip()
    return text[:max_chars]


def answer_with_search(query: str, n: int = 4, fetch: bool = True) -> dict:
    """返回 {"query","results","context"}，context 可直接拼进提示词。"""
    results = search_web(query, n=n)
    parts = []
    for i, r in enumerate(results, 1):
        body = r.get('snippet') or ''
        if fetch and len(body) < 80 and r.get('url'):
            body = fetch_text(r['url'], 600)
        parts.append(f'[{i}] {r["title"]}\n{r["url"]}\n{body[:600]}')
    return {'query': query, 'results': results,
            'context': ('【联网检索结果】\n' + '\n\n'.join(parts)) if parts else ''}


if __name__ == '__main__':
    import sys
    q = ' '.join(sys.argv[1:]) or '今天有什么新闻'
    for r in search_web(q):
        print('-', r['title'][:60], r['url'])
