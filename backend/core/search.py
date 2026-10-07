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
import os
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


# ============================================================================
# 代码搜索（code search）
# ============================================================================

# 需要跳过的目录名
_CODE_SKIP_DIRS = {
    ".git", "build", "__pycache__", ".dart_tool", "node_modules",
    ".idea", "venv", ".venv", "dist", ".next", "resources",
}
# 视为文本的常见扩展名（其余扩展名直接跳过，避免误读二进制）
_TEXT_EXTS = {
    ".py", ".dart", ".js", ".jsx", ".ts", ".tsx", ".json", ".md",
    ".markdown", ".yaml", ".yml", ".proto", ".css", ".scss", ".html",
    ".htm", ".xml", ".go", ".rs", ".java", ".c", ".h", ".cpp", ".hpp",
    ".sh", ".bash", ".sql", ".toml", ".ini", ".cfg", ".txt", ".kt",
    ".swift", ".rb", ".php", ".lua", ".r", ".m", ".mm", ".vue",
}
_MAX_FILE_BYTES = 1024 * 1024  # 跳过超过 1MB 的文件

# 定义行匹配：def / class / function / widget / func / struct / impl / interface
_DEF_RE = re.compile(
    r"^\s*(?:async\s+)?(?:def|class|function|func|struct|impl|interface|widget)\b"
)


def search_code(query: str, path: str = ".", max_results: int = 50) -> list:
    """在 path 下逐行 grep 代码（不区分大小写）。

    返回 [{file, line(1-based), column, text, symbol, kind}, ...]
      * kind = "definition"  若命中行同时是 def/class/function 等定义行
      * kind = "reference"   其余命中
    用 time.time() 计时；跳过二进制 / 大文件 / 构建产物目录。
    永不抛异常，出错返回 []。
    """
    import time as _t
    t0 = _t.time()
    out: list = []
    if not query:
        return out
    q = query.lower()
    root = os.path.abspath(os.path.expanduser(str(path or ".")))
    if not os.path.isdir(root):
        return out
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _CODE_SKIP_DIRS]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in _TEXT_EXTS:
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(full) > _MAX_FILE_BYTES:
                        continue
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, 1):
                            idx = line.lower().find(q)
                            if idx < 0:
                                continue
                            stripped = line.strip()
                            kind = "reference"
                            symbol = ""
                            if _DEF_RE.match(line):
                                kind = "definition"
                                m = re.search(
                                    r"(?:def|class|function|func|struct|impl|"
                                    r"interface|widget)\s+([A-Za-z_][A-Za-z0-9_]*)",
                                    line)
                                if m:
                                    symbol = m.group(1)
                            out.append({
                                "file": os.path.relpath(full, root),
                                "line": lineno,
                                "column": idx + 1,
                                "text": stripped[:300],
                                "symbol": symbol,
                                "kind": kind,
                            })
                            if len(out) >= max_results:
                                return out
                except OSError:
                    continue
    except Exception:  # noqa: BLE001
        pass
    return out


# ============================================================================
# 增量完善（v0.0.1）：增强缓存 / 热词统计 / 搜索建议 / 多源聚合
# 说明：以下均为独立新增类与函数，不改动上方既有搜索行为与函数签名。
# ============================================================================
import collections as _collections                                       # noqa: E402
import threading as _threading                                          # noqa: E402


class LruTtlCache:
    """带 LRU 淘汰与 TTL 过期的键值缓存，线程安全。

    相比模块级 _cache（简单字典），本类用 OrderedDict 实现真正的 LRU：
    命中即刷新到末尾，超容量时淘汰最久未使用项；过期项惰性清理。
    """

    def __init__(self, max_size: int = 128, ttl: float = 300.0):
        self.max_size = max(1, int(max_size))
        self.ttl = max(1.0, float(ttl))
        self._store: "_collections.OrderedDict" = _collections.OrderedDict()
        self._lock = _threading.Lock()

    def get(self, key: str):
        """取缓存；未命中或已过期返回 None。"""
        try:
            now = time.time()
            with self._lock:
                item = self._store.get(key)
                if item is None:
                    return None
                ts, value = item
                if (now - ts) > self.ttl:
                    self._store.pop(key, None)
                    return None
                self._store.move_to_end(key)
                return value
        except Exception:                                                  # noqa: BLE001
            return None

    def put(self, key: str, value) -> None:
        """写入缓存；超容量时淘汰最久未使用项。"""
        try:
            with self._lock:
                self._store[key] = (time.time(), value)
                self._store.move_to_end(key)
                while len(self._store) > self.max_size:
                    self._store.popitem(last=False)
        except Exception:                                                  # noqa: BLE001
            pass

    def evict_expired(self) -> int:
        """主动清理过期项，返回清理条数。"""
        try:
            now = time.time()
            n = 0
            with self._lock:
                stale = [k for k, (ts, _) in self._store.items()
                         if (now - ts) > self.ttl]
                for k in stale:
                    self._store.pop(k, None)
                    n += 1
            return n
        except Exception:                                                  # noqa: BLE001
            return 0

    def __len__(self) -> int:
        try:
            with self._lock:
                return len(self._store)
        except Exception:                                                  # noqa: BLE001
            return 0


class HotWordTracker:
    """搜索热词统计：按 query 频次计数，输出 TopN 热词。"""

    def __init__(self, max_terms: int = 1024):
        self.max_terms = max(16, int(max_terms))
        self._freq: dict = {}
        self._lock = _threading.Lock()

    def record(self, query: str) -> None:
        """记录一次搜索词；词表超容量时淘汰计数最低的一半。"""
        try:
            q = (query or "").strip()
            if not q:
                return
            with self._lock:
                self._freq[q] = self._freq.get(q, 0) + 1
                if len(self._freq) > self.max_terms:
                    drop = sorted(self._freq.items(), key=lambda kv: kv[1])
                    for k, _ in drop[:max(1, len(self._freq) // 2)]:
                        self._freq.pop(k, None)
        except Exception:                                                  # noqa: BLE001
            pass

    def top(self, n: int = 10) -> list:
        """返回 [(word, count), ...] 按频次降序。"""
        try:
            with self._lock:
                items = sorted(self._freq.items(),
                               key=lambda kv: kv[1], reverse=True)
                return [(w, c) for w, c in items[:max(1, n)]]
        except Exception:                                                  # noqa: BLE001
            return []


# 全局热词跟踪器（与既有 _history 并存，互不影响）
_hot_words = HotWordTracker()


def search_suggestions(prefix: str, limit: int = 5) -> list:
    """基于已有搜索历史与热词表的前缀自动补全建议。

    合并历史前缀命中与热词前缀命中，去重后按热度返回前 limit 条。
    """
    try:
        p = (prefix or "").strip().lower()
        if not p:
            return []
        hist = get_history()
        sug = [h for h in hist if h.lower().startswith(p)]
        for w, _c in _hot_words.top(50):
            if w.lower().startswith(p) and w not in sug:
                sug.append(w)
        return sug[:max(1, limit)]
    except Exception:                                                  # noqa: BLE001
        return []


def search_multi_source(query: str, n: int = 5,
                        engines=("duckduckgo", "searx")) -> list:
    """多源聚合搜索：同时查询多个搜索引擎，按 URL 去重合并。

    结果按来源顺序加权打分（先返回的源权重更高），同 URL 保留较长
    snippet 并叠加权重；任一源失败自动跳过，绝不抛异常。
    """
    try:
        merged: dict = {}
        for idx, eng in enumerate(engines or ("duckduckgo",)):
            weight = max(1.0, float(len(list(engines)) - idx))
            try:
                if eng == "searx":
                    res = _searx(query, n)
                else:
                    res = _ddg(query, n)
            except Exception:                                          # noqa: BLE001
                continue
            for r in (res or []):
                url = str(r.get("url") or "")
                key = url or str(r.get("title") or "")
                if not key:
                    continue
                if key in merged:
                    old = merged[key]
                    if len(str(r.get("snippet") or "")) > len(
                            str(old.get("snippet") or "")):
                        old["snippet"] = r.get("snippet", old.get("snippet"))
                    old["score"] = old.get("score", 1.0) + weight
                else:
                    merged[key] = dict(r)
                    merged[key]["score"] = weight
                    merged[key]["source"] = eng
        out = list(merged.values())
        out.sort(key=lambda r: r.get("score", 1.0), reverse=True)
        return out[:max(1, n)]
    except Exception:                                                  # noqa: BLE001
        return []


if __name__ == '__main__':
    import sys
    q = ' '.join(sys.argv[1:]) or '今天有什么新闻'
    for r in search_web(q):
        print('-', r['title'][:60], r['url'])
