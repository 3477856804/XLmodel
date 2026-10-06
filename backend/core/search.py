#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 联网搜索 Agent（免 Key）
=================================

迁移自小玥的「全网搜索 Agent」（原实现走 Electron 主进程 + DuckDuckGo Lite）。
提供：
  * `search_web(query, n)`      → [{title, url, snippet}]
  * `fetch_text(url, max_chars)`→ 网页正文（去标签）
  * `answer_with_search(query)` → 检索 + 拼上下文，交给本地模型/老师模型作答
离线自动降级：无网络时返回 []，由引擎走本地知识。
"""
from __future__ import annotations

import gzip
import html
import json
import re
import urllib.parse
import urllib.request
import zlib

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')


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


def search_web(query: str, n: int = 5, engine: str = 'duckduckgo'):
    """免 Key 联网搜索。"""
    if engine == 'duckduckgo':
        return _ddg(query, n)
    if engine == 'searx':
        return _searx(query, n)
    return _ddg(query, n)


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


