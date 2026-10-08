import os, re, json, math, logging
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

# jieba 中文分词：不可用时降级到正则分词
try:
    import jieba
    jieba.setLogLevel(logging.WARNING)
    _JIEBA_AVAILABLE = True
except ImportError:
    jieba = None  # type: ignore
    _JIEBA_AVAILABLE = False

# sentence-transformers 语义向量：不可用时混合检索降级为纯 TF-IDF
try:
    import sentence_transformers  # noqa: F401
    _ST_AVAILABLE = True
except ImportError:
    sentence_transformers = None  # type: ignore
    _ST_AVAILABLE = False

# 常见中文停用词
CHINESE_STOPWORDS = {
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这",
    "他", "她", "它", "们", "那", "些", "什么", "怎么", "如何",
    "呢", "吧", "吗", "啊", "呀", "嘛", "把", "被", "让", "向",
    "从", "对", "为", "以", "及", "或", "而", "且", "但", "如",
    "之", "于", "其", "此", "该", "各", "每", "等", "更", "最",
    "可", "可以", "能", "能够", "将", "已", "已经", "正", "刚",
    "过", "来", "去", "起", "开", "下", "中", "间", "内", "外",
    "时", "时候", "地方", "东西", "觉得", "知道", "想", "做",
}

_SEMANTIC_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_KEYWORD_WEIGHT = 0.6
_SEMANTIC_WEIGHT = 0.4


class KnowledgeBase:
    """项目知识库：文档分块索引，支持 TF-IDF 关键词检索、语义向量混合检索与引用溯源"""

    def __init__(self, index_path="data/kb_index.json"):
        self.index_path = index_path
        self.documents = {}  # doc_id -> {doc_id, name, path, chunk_ids, chunk_count, char_count}
        self.chunks = {}     # chunk_id -> {chunk_id, doc_id, name, path, chunk_index, offset, text, tokens, word_count}
        self.doc_freq = Counter()
        self.total_docs = 0
        self._semantic_model = None
        self._semantic_tried = False
        self._load_index()

    # ------------------------------------------------------------------ 分块
    @staticmethod
    def chunk_document(text, chunk_size=500, overlap=50):
        """把长文档切成带重叠的块，每块记录字符偏移量。

        返回 [{"chunk_index": int, "offset": int, "text": str}, ...]
        优先在段落/句子边界断开，保证上下文完整。
        """
        text = text or ""
        if chunk_size <= 0:
            chunk_size = 500
        if overlap < 0 or overlap >= chunk_size:
            overlap = int(chunk_size * 0.1)
        pieces = []
        if not text.strip():
            return pieces
        n = len(text)
        start = 0
        idx = 0
        while start < n:
            end = min(start + chunk_size, n)
            if end < n:
                window = text[start:end]
                brk = -1
                for mark in ("\n\n", "。", "！", "？", "；", ". ", "! ", "? "):
                    p = window.rfind(mark)
                    if p > brk:
                        brk = p
                if brk >= int(chunk_size * 0.5):
                    end = start + brk + 1
            piece = text[start:end].strip()
            if piece:
                pieces.append({"chunk_index": idx, "offset": start, "text": piece})
                idx += 1
            if end >= n:
                break
            start = max(end - overlap, start + 1)
        return pieces

    # ------------------------------------------------------------------ 文档管理
    def add_document(self, name, content, path=None):
        """索引一份文档：先分块，再逐块建倒排。同名文档会被替换。"""
        name = (name or "").strip() or (path or "untitled")
        if name in self.documents:
            self.delete_document(name)
        pieces = self.chunk_document(content)
        chunk_ids = []
        for piece in pieces:
            cid = "%s#c%d" % (name, piece["chunk_index"])
            tokens = self._tokenize(piece["text"])
            self.chunks[cid] = {
                "chunk_id": cid,
                "doc_id": name,
                "name": name,
                "path": path or name,
                "chunk_index": piece["chunk_index"],
                "offset": piece["offset"],
                "text": piece["text"],
                "tokens": tokens,
                "word_count": len(tokens),
            }
            chunk_ids.append(cid)
            for t in set(tokens):
                self.doc_freq[t] += 1
        self.documents[name] = {
            "doc_id": name,
            "name": name,
            "path": path or name,
            "chunk_ids": chunk_ids,
            "chunk_count": len(chunk_ids),
            "char_count": len(content or ""),
        }
        self.total_docs = len(self.documents)
        self._save_index()
        return len(chunk_ids)

    def index_directory(self, dir_path, extensions=None, max_files=200):
        """索引目录下的文档"""
        if extensions is None:
            extensions = {".md", ".txt", ".py", ".dart", ".json", ".yaml", ".yml", ".rst"}
        count = 0
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".dart_tool", "node_modules", "build"}]
            for fname in files:
                if count >= max_files:
                    break
                fpath = os.path.join(root, fname)
                ext = os.path.splitext(fname)[1].lower()
                if ext in extensions:
                    try:
                        with open(fpath, "r", errors="ignore") as f:
                            content = f.read()
                        if content.strip():
                            self.add_document(os.path.basename(fpath), content, path=fpath)
                            count += 1
                    except Exception as e:
                        logger.warning(f"[knowledge_base] 读取文档失败 {fpath}: {e}")
        self._save_index()
        return count

    def list_documents(self):
        """列出已索引文档"""
        return [
            {"name": d["name"], "path": d["path"], "chunks": d["chunk_count"],
             "chars": d["char_count"]}
            for d in sorted(self.documents.values(), key=lambda x: x["name"])
        ]

    def delete_document(self, name):
        """删除文档及其全部分块"""
        doc = self.documents.pop(name, None)
        if doc is None:
            return False
        for cid in doc["chunk_ids"]:
            ch = self.chunks.pop(cid, None)
            if ch is None:
                continue
            for t in set(ch["tokens"]):
                self.doc_freq[t] -= 1
                if self.doc_freq[t] <= 0:
                    del self.doc_freq[t]
        self.total_docs = len(self.documents)
        self._save_index()
        return True

    def reindex(self):
        """重建索引：重新分词并重建倒排表"""
        self.doc_freq = Counter()
        for ch in self.chunks.values():
            ch["tokens"] = self._tokenize(ch.get("text", ""))
            ch["word_count"] = len(ch["tokens"])
            for t in set(ch["tokens"]):
                self.doc_freq[t] += 1
        self._save_index()
        return {"docs": self.total_docs, "chunks": len(self.chunks),
                "terms": len(self.doc_freq)}

    # ------------------------------------------------------------------ 分词
    def _tokenize(self, text):
        text = text.lower()
        if _JIEBA_AVAILABLE and jieba is not None:
            # 英文用正则提取单词，中文用 jieba 精确分词
            en_tokens = re.findall(r'[a-z0-9_]+', text)
            zh_text = re.sub(r'[a-z0-9_]+', ' ', text)
            zh_tokens = [t.strip() for t in jieba.cut(zh_text, cut_all=False) if t.strip()]
            tokens = en_tokens + zh_tokens
        else:
            # 降级：正则整段匹配（中文会被当作一个 token）
            tokens = re.findall(r'[a-z0-9_\u4e00-\u9fff]+', text)
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                       "have", "has", "had", "do", "does", "did", "will", "would", "could",
                       "should", "may", "might", "must", "shall", "can", "need", "dare",
                       "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
                       "into", "through", "during", "before", "after", "above", "below",
                       "between", "out", "off", "over", "under", "again", "further", "then",
                       "once", "and", "but", "or", "nor", "not", "so", "yet", "both",
                       "either", "neither", "each", "every", "all", "any", "few", "more",
                       "most", "other", "some", "such", "no", "only", "own", "same", "than",
                       "too", "very", "just", "because", "if", "when", "where", "how", "what",
                       "which", "who", "whom", "this", "that", "these", "those", "it", "its",
                       "i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she",
                       "her", "they", "them", "their", "return", "def", "class", "import",
                       "final", "const", "void", "null", "true", "false", "self"}
        stop_words = stop_words | CHINESE_STOPWORDS
        result = []
        for t in tokens:
            if t in stop_words:
                continue
            # 过滤纯标点/空白 token：必须包含中文或字母数字
            if not re.search(r'[\u4e00-\u9fff a-z0-9]', t):
                continue
            # 英文/数字要求长度>1；中文允许单字（jieba 已过滤停用词）
            if re.match(r'^[a-z0-9_]+$', t):
                if len(t) > 1:
                    result.append(t)
            else:
                if len(t) >= 1:
                    result.append(t)
        return result

    # ------------------------------------------------------------------ 检索
    def search(self, query, top_k=5) -> list:
        """TF-IDF 关键词检索（块粒度）"""
        query_tokens = self._tokenize(query)
        if not query_tokens or not self.chunks:
            return []
        n_chunks = len(self.chunks)
        scores = defaultdict(float)
        for token in query_tokens:
            if token not in self.doc_freq:
                continue
            idf = math.log((n_chunks + 1) / (self.doc_freq[token] + 1)) + 1
            for cid, ch in self.chunks.items():
                tf = ch["tokens"].count(token) / max(ch["word_count"], 1)
                scores[cid] += tf * idf
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return self._format_results(ranked, query_tokens, top_k)

    def hybrid_search(self, query, top_k=5) -> list:
        """混合检索：TF-IDF 关键词 + 语义向量，加权融合去重。

        语义模型不可用时自动降级为纯关键词检索。
        """
        kw = self.search(query, top_k=max(top_k * 3, top_k))
        sem = self._semantic_search(query, top_k=max(top_k * 3, top_k))
        if not sem:
            return kw[:top_k]

        def _norm(items):
            vals = [r["score"] for r in items]
            if not vals:
                return {}
            lo, hi = min(vals), max(vals)
            span = (hi - lo) or 1.0
            return {r["chunk_id"]: (r["score"] - lo) / span for r in items}

        kw_n = _norm(kw)
        se_n = _norm(sem)
        fused = defaultdict(float)
        for cid, v in kw_n.items():
            fused[cid] += _KEYWORD_WEIGHT * v
        for cid, v in se_n.items():
            fused[cid] += _SEMANTIC_WEIGHT * v
        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)

        results = []
        for cid, score in ranked:
            ch = self.chunks.get(cid)
            if ch is None:
                continue
            results.append(self._result_item(ch, score, matched_by=(
                "semantic" if cid not in kw_n else ("keyword" if cid not in se_n else "both"))))
            if len(results) >= top_k:
                break
        return results

    def get_source(self, chunk_id) -> dict:
        """返回某个块的完整来源信息，供前端引用溯源"""
        ch = self.chunks.get(chunk_id)
        if ch is None:
            return None
        return {
            "chunk_id": chunk_id,
            "file": ch["name"],
            "path": ch["path"],
            "chunk": ch["chunk_index"],
            "offset": ch["offset"],
            "text": ch["text"],
        }

    # ------------------------------------------------------------------ 语义
    def _load_semantic_model(self):
        if self._semantic_tried:
            return self._semantic_model
        self._semantic_tried = True
        if not _ST_AVAILABLE:
            return None
        try:
            from sentence_transformers import SentenceTransformer
            self._semantic_model = SentenceTransformer(_SEMANTIC_MODEL_NAME)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[knowledge_base] 语义模型加载失败，降级纯关键词: {e}")
            self._semantic_model = None
        return self._semantic_model

    def _semantic_search(self, query, top_k=5):
        model = self._load_semantic_model()
        if model is None or not self.chunks:
            return []
        try:
            cids = list(self.chunks.keys())
            texts = [self.chunks[c]["text"] for c in cids]
            emb = model.encode([query] + texts, normalize_embeddings=True)
            qv, dv = emb[0], emb[1:]
            sims = dv @ qv
            order = (-sims).argsort()[:top_k]
            return [{"chunk_id": cids[int(i)], "score": float(sims[int(i)])} for i in order]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[knowledge_base] 语义检索失败，跳过: {e}")
            return []

    # ------------------------------------------------------------------ 结果组装
    def _result_item(self, ch, score, matched_by="keyword"):
        return {
            "chunk_id": ch["chunk_id"],
            "score": round(float(score), 4),
            "text": ch["text"],
            "matched_by": matched_by,
            "source": {
                "file": ch["name"],
                "path": ch["path"],
                "chunk": ch["chunk_index"],
                "offset": ch["offset"],
            },
        }

    def _format_results(self, ranked, query_tokens, top_k):
        results = []
        for cid, score in ranked:
            if score <= 0:
                continue
            ch = self.chunks.get(cid)
            if ch is None:
                continue
            item = self._result_item(ch, score)
            item["snippet"] = self._extract_snippet(ch["text"], query_tokens)
            results.append(item)
            if len(results) >= top_k:
                break
        return results

    def _extract_snippet(self, content, query_tokens, context_len=120):
        content_lower = content.lower()
        best_pos = -1
        for token in query_tokens:
            pos = content_lower.find(token)
            if pos >= 0 and (best_pos < 0 or pos < best_pos):
                best_pos = pos
        if best_pos < 0:
            return content[:context_len] + ("..." if len(content) > context_len else "")
        start = max(0, best_pos - 30)
        end = min(len(content), best_pos + context_len)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""
        return prefix + content[start:end].replace("\n", " ") + suffix

    def get_stats(self) -> dict:
        return {"total_docs": self.total_docs, "total_chunks": len(self.chunks),
                "total_words": sum(c["word_count"] for c in self.chunks.values()),
                "unique_terms": len(self.doc_freq),
                "semantic": self._load_semantic_model() is not None}

    # ------------------------------------------------------------------ 持久化
    def _save_index(self):
        os.makedirs(os.path.dirname(self.index_path) or ".", exist_ok=True)
        chunks_out = {
            cid: {k: v for k, v in ch.items() if k != "tokens"}
            for cid, ch in self.chunks.items()
        }
        data = {"documents": self.documents, "chunks": chunks_out,
                "doc_freq": dict(self.doc_freq), "total_docs": self.total_docs}
        with open(self.index_path, "w") as f:
            json.dump(data, f, ensure_ascii=False)

    def _load_index(self):
        if not os.path.exists(self.index_path):
            return
        try:
            with open(self.index_path) as f:
                data = json.load(f)
            self.total_docs = data.get("total_docs", 0)
            raw_chunks = data.get("chunks", {})
            if not raw_chunks:
                # 旧版文档级索引：把每份文档重新分块迁移进块索引
                for path, doc in data.get("documents", {}).items():
                    content = doc.get("content", "") or ""
                    if content.strip():
                        self.add_document(doc.get("title") or os.path.basename(path),
                                          content, path=path)
                return
            for cid, ch in raw_chunks.items():
                self.chunks[cid] = {**ch, "tokens": self._tokenize(ch.get("text", "")),
                                    "word_count": len([])}
                self.chunks[cid]["word_count"] = len(self.chunks[cid]["tokens"])
            self.documents = data.get("documents", {})
            self.doc_freq = Counter(data.get("doc_freq", {}))
            self.total_docs = len(self.documents)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[knowledge_base] 加载索引失败: {e}")
