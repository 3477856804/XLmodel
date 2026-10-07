import os, re, json, math, logging
from collections import Counter, defaultdict

class KnowledgeBase:
    """项目知识库：索引文档，支持关键词检索和简单语义匹配"""

    def __init__(self, index_path="data/kb_index.json"):
        self.index_path = index_path
        self.documents = {}  # path -> {content, tokens, title}
        self.doc_freq = Counter()
        self.total_docs = 0
        self._load_index()

    def index_directory(self, dir_path, extensions=None, max_files=200):
        """索引目录下的文档"""
        if extensions is None:
            extensions = {".md", ".txt", ".py", ".dart", ".json", ".yaml", ".yml", ".rst"}
        count = 0
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".dart_tool", "node_modules", "build"}]
            for fname in files:
                if count >= max_files: break
                fpath = os.path.join(root, fname)
                ext = os.path.splitext(fname)[1].lower()
                if ext in extensions:
                    try:
                        with open(fpath, "r", errors="ignore") as f:
                            content = f.read()
                        if content.strip():
                            self._add_document(fpath, content)
                            count += 1
                    except: pass
        self._save_index()
        return count

    def _add_document(self, path, content):
        tokens = self._tokenize(content)
        self.documents[path] = {
            "content": content[:5000],
            "tokens": tokens,
            "title": os.path.basename(path),
            "word_count": len(tokens),
        }
        for token in set(tokens):
            self.doc_freq[token] += 1
        self.total_docs = len(self.documents)

    def _tokenize(self, text):
        text = text.lower()
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
        return [t for t in tokens if t not in stop_words and len(t) > 1]

    def search(self, query, top_k=5) -> list:
        """TF-IDF 检索"""
        query_tokens = self._tokenize(query)
        if not query_tokens or self.total_docs == 0:
            return []
        scores = defaultdict(float)
        for token in query_tokens:
            if token in self.doc_freq:
                idf = math.log((self.total_docs + 1) / (self.doc_freq[token] + 1)) + 1
                for path, doc in self.documents.items():
                    tf = doc["tokens"].count(token) / max(doc["word_count"], 1)
                    scores[path] += tf * idf
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for path, score in ranked:
            if score > 0:
                doc = self.documents[path]
                snippet = self._extract_snippet(doc["content"], query_tokens)
                results.append({"path": path, "title": doc["title"], "score": round(score, 4),
                                "snippet": snippet, "word_count": doc["word_count"]})
        return results

    def _extract_snippet(self, content, query_tokens, context_len=100):
        content_lower = content.lower()
        best_pos = -1
        for token in query_tokens:
            pos = content_lower.find(token)
            if pos >= 0 and (best_pos < 0 or pos < best_pos):
                best_pos = pos
        if best_pos < 0:
            return content[:context_len] + "..."
        start = max(0, best_pos - 30)
        end = min(len(content), best_pos + context_len)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""
        return prefix + content[start:end].replace("\n", " ") + suffix

    def get_stats(self) -> dict:
        return {"total_docs": self.total_docs, "total_words": sum(d["word_count"] for d in self.documents.values()),
                "unique_terms": len(self.doc_freq)}

    def _save_index(self):
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        data = {"documents": {k: {**v, "tokens": None} for k, v in self.documents.items()},
                "doc_freq": dict(self.doc_freq), "total_docs": self.total_docs}
        with open(self.index_path, "w") as f:
            json.dump(data, f, ensure_ascii=False)

    def _load_index(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path) as f:
                    data = json.load(f)
                self.total_docs = data.get("total_docs", 0)
                self.doc_freq = Counter(data.get("doc_freq", {}))
                for path, doc in data.get("documents", {}).items():
                    content = doc.get("content", "")
                    self.documents[path] = {**doc, "tokens": self._tokenize(content)}
            except: pass
