"""小凌 · 记忆中心（短期 + 长期 + 会话 + 图谱 + RAG + 上下文压缩）"""
import hashlib
import json
import math
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

HISTORY_PATH = DATA_DIR / "session_history.jsonl"
CHECKPOINT_PATH = DATA_DIR / "session_checkpoint.json"
LONG_MEM_PATH = DATA_DIR / "memory.json"
GRAPH_PATH = DATA_DIR / "knowledge.json"
RAG_PATH = DATA_DIR / "rag.jsonl"

REL_VERBS = ("是", "叫", "属于", "包含", "用于", "来自", "在", "有", "需要", "喜欢", "想", "会")
ENTITY_RE = re.compile(r"([\u4e00-\u9fff]{2,6})")
SPLIT_RE = re.compile(r"[\s,，。；;：:！!？?、]+")
WORD_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z]+|\d+")


@dataclass
class MemoryItem:
    role: str
    content: str
    timestamp: float
    importance: float = 0.5
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content,
                "timestamp": self.timestamp, "importance": self.importance,
                "tags": list(self.tags)}

    @staticmethod
    def from_dict(d: dict) -> "MemoryItem":
        return MemoryItem(
            role=d.get("role", ""),
            content=d.get("content", ""),
            timestamp=float(d.get("timestamp", 0)),
            importance=float(d.get("importance", 0.5)),
            tags=list(d.get("tags") or []),
        )


class ShortTermMemory:
    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._items: deque[MemoryItem] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, role: str, content: str, importance: float = 0.5, tags=None):
        with self._lock:
            self._items.append(MemoryItem(role=role, content=content,
                                          timestamp=time.time(),
                                          importance=importance, tags=list(tags or [])))

    def recent(self, n: int | None = None) -> list:
        with self._lock:
            items = list(self._items)
        return items if n is None else items[-n:]

    def to_prompt(self) -> str:
        with self._lock:
            items = list(self._items)
        return "\n".join(f"{'用户' if i.role == 'user' else '小凌'}: {i.content}"
                         for i in items)

    def as_turns(self) -> list:
        with self._lock:
            return [{"role": i.role, "content": i.content} for i in self._items]

    def clear(self):
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


class LongTermMemory:
    def __init__(self, path: str | None = None, max_items: int = 5000,
                 decay_rate: float = 0.995):
        self.path = Path(path) if path else LONG_MEM_PATH
        self.max_items = max_items
        self.decay_rate = decay_rate
        self._items: list[MemoryItem] = []
        self._lock = threading.RLock()
        self._dirty = False
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else raw.get("items") or []
            self._items = [MemoryItem.from_dict(d) for d in items if isinstance(d, dict)]
        except Exception:
            self._items = []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {"updated_at": time.time(),
                    "items": [i.to_dict() for i in self._items]}
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
            self._dirty = False
        except OSError:
            pass

    def add(self, role: str, content: str, importance: float = 0.5, tags=None):
        with self._lock:
            self._items.append(MemoryItem(role=role, content=content,
                                          timestamp=time.time(),
                                          importance=importance, tags=list(tags or [])))
            if len(self._items) > self.max_items:
                self.forget()
                self._items = self._items[-int(self.max_items * 0.75):]
            self._dirty = True
            self._save()

    def forget(self):
        now = time.time()
        with self._lock:
            self._items = [
                i for i in self._items
                if (now - i.timestamp) * self.decay_rate * i.importance > 0.01
            ]

    def search(self, query: str, top_k: int = 5) -> list:
        if not query:
            return []
        words = [w for w in SPLIT_RE.split(query) if w]
        if not words:
            return []
        with self._lock:
            items = list(self._items)
        scored = []
        for i in items:
            hit = sum(1 for w in words if w in i.content)
            if hit:
                scored.append((hit * i.importance, i))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [i for _, i in scored[:top_k]]

    def recent(self, n: int = 20) -> list:
        with self._lock:
            return list(self._items[-n:])

    def by_tag(self, tag: str, limit: int = 50) -> list:
        with self._lock:
            return [i for i in self._items if tag in i.tags][-limit:]

    def clear(self):
        with self._lock:
            self._items = []
            self._save()

    def flush(self):
        with self._lock:
            if self._dirty:
                self._save()

    def stats(self) -> dict:
        with self._lock:
            n = len(self._items)
            if not n:
                return {"total": 0, "path": str(self.path)}
            avg = sum(i.importance for i in self._items) / n
            return {"total": n,
                    "avg_importance": round(avg, 3),
                    "oldest": min(i.timestamp for i in self._items),
                    "newest": max(i.timestamp for i in self._items),
                    "path": str(self.path)}


class SessionPersistence:
    def __init__(self, history_path: str | None = None,
                 checkpoint_path: str | None = None,
                 max_reply_chars: int = 800,
                 auto_trim: int = 2000):
        self.history_path = Path(history_path) if history_path else HISTORY_PATH
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else CHECKPOINT_PATH
        self.max_reply_chars = max_reply_chars
        self.auto_trim = auto_trim
        self._saved_turns = 0
        self._lock = threading.Lock()

    def append_turn(self, user: str, reply: str, tool_calls: list = None):
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "time": time.time(),
                "datetime": datetime.now().isoformat(timespec="seconds"),
                "user": (user or "")[:2000],
                "reply": (reply or "")[:self.max_reply_chars],
                "tool_calls": (tool_calls or [])[:8],
            }
            line = json.dumps(entry, ensure_ascii=False) + "\n"
            with self._lock:
                with open(self.history_path, "a", encoding="utf-8") as f:
                    f.write(line)
                self._saved_turns += 1
                over = self._saved_turns > self.auto_trim
            if over:
                self.trim(keep_last=self.auto_trim // 2)
        except OSError:
            pass

    def append_many(self, turns: list):
        for t in turns:
            if isinstance(t, dict):
                self.append_turn(t.get("user", ""), t.get("reply", ""),
                                 t.get("tool_calls"))

    def get_recent_history(self, n: int = 10) -> list:
        if not self.history_path.exists():
            return []
        try:
            with self._lock:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
        except OSError:
            return []
        out = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def history_count(self) -> int:
        if not self.history_path.exists():
            return 0
        try:
            with self._lock:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return sum(1 for line in f if line.strip())
        except OSError:
            return 0

    def save_checkpoint(self) -> bool:
        try:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                checkpoint = {
                    "time": time.time(),
                    "datetime": datetime.now().isoformat(timespec="seconds"),
                    "session_history_turns": self._saved_turns,
                }
            self.checkpoint_path.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=1),
                encoding="utf-8")
            return True
        except OSError:
            return False

    def load_checkpoint(self) -> dict | None:
        if not self.checkpoint_path.exists():
            return None
        try:
            return json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def trim(self, keep_last: int = 500) -> int:
        if not self.history_path.exists():
            return 0
        try:
            with self._lock:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    lines = [line for line in f if line.strip()]
            if len(lines) <= keep_last:
                return 0
            removed = len(lines) - keep_last
            with open(self.history_path, "w", encoding="utf-8") as f:
                f.writelines(lines[-keep_last:])
            return removed
        except OSError:
            return 0

    def clear(self):
        with self._lock:
            try:
                if self.history_path.exists():
                    self.history_path.unlink()
                if self.checkpoint_path.exists():
                    self.checkpoint_path.unlink()
                self._saved_turns = 0
            except OSError:
                pass

    def stats(self) -> dict:
        return {
            "turns": self.history_count(),
            "saved_session": self._saved_turns,
            "history_path": str(self.history_path),
            "checkpoint_path": str(self.checkpoint_path),
        }


class KnowledgeGraph:
    def __init__(self, path: str | None = None, max_entities: int = 5000,
                 max_relations: int = 20000):
        self.path = Path(path) if path else GRAPH_PATH
        self.max_entities = max_entities
        self.max_relations = max_relations
        self.entities: dict[str, dict] = {}
        self.relations: list[tuple] = []
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.entities = data.get("entities", {}) or {}
            rels = data.get("relations", []) or []
            self.relations = [tuple(r) if isinstance(r, (list, tuple)) else r for r in rels]
        except Exception:
            self.entities = {}
            self.relations = []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"updated_at": time.time(),
                       "entities": self.entities,
                       "relations": [list(r) for r in self.relations]}
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        except OSError:
            pass

    def learn(self, text: str) -> int:
        if not text or len(text) < 4:
            return 0
        added = 0
        with self._lock:
            for verb in REL_VERBS:
                pat = re.compile(ENTITY_RE.pattern + re.escape(verb) +
                                 r"([\u4e00-\u9fff\w]{2,10})")
                for m in pat.finditer(text):
                    subj = m.group(1).strip()
                    obj = m.group(2).strip()[:10]
                    if not subj or not obj or subj == obj:
                        continue
                    info = self.entities.setdefault(subj, {"count": 0, "relations": []})
                    info["count"] = int(info.get("count", 0)) + 1
                    pair = (subj, verb, obj)
                    if pair not in self.relations:
                        self.relations.append(pair)
                        info.setdefault("relations", []).append([verb, obj])
                    added += 1
            if len(self.relations) > self.max_relations:
                self.relations = self.relations[-int(self.max_relations * 0.7):]
            if len(self.entities) > self.max_entities:
                top = sorted(self.entities.items(),
                             key=lambda kv: kv[1].get("count", 0), reverse=True)
                self.entities = dict(top[:int(self.max_entities * 0.75)])
            if added:
                self._save()
        return added

    def query(self, entity: str, depth: int = 1) -> str:
        if not entity:
            return "请输入要查询的实体"
        with self._lock:
            if entity not in self.entities:
                return f"图谱中暂无「{entity}」的知识"
            info = self.entities[entity]
            lines = [f"实体「{entity}」：出现 {info.get('count', 0)} 次"]
            for rel in info.get("relations", [])[:depth * 5]:
                if isinstance(rel, (list, tuple)) and len(rel) >= 2:
                    lines.append(f"  · {entity} {rel[0]} {rel[1]}")
            return "\n".join(lines)

    def neighbors(self, entity: str, max_n: int = 10) -> list:
        out = []
        with self._lock:
            for subj, verb, obj in self.relations:
                if subj == entity:
                    out.append((verb, obj, "out"))
                elif obj == entity:
                    out.append((verb, subj, "in"))
                if len(out) >= max_n:
                    break
        return out

    def search(self, keyword: str, limit: int = 20) -> list:
        if not keyword:
            return []
        with self._lock:
            return [k for k in self.entities if keyword in k][:limit]

    def stats(self) -> dict:
        with self._lock:
            return {"entities": len(self.entities),
                    "relations": len(self.relations),
                    "path": str(self.path)}

    def clear(self):
        with self._lock:
            self.entities.clear()
            self.relations.clear()
            self._save()


def _hash_embed(text: str, dim: int = 512) -> list:
    vec = [0.0] * dim
    s = re.sub(r"\s+", "", (text or "").lower())
    if not s:
        return vec
    for n in (1, 2, 3):
        for i in range(max(len(s) - n + 1, 0)):
            gram = s[i:i + n]
            h = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % dim
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign / n
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


class RAG:
    def __init__(self, dim: int = 512, max_docs: int = 3000, path: str | None = None):
        self.dim = dim
        self.max_docs = max_docs
        self.path = Path(path) if path else RAG_PATH
        self.documents: list[dict] = []
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            docs = []
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        if isinstance(d, dict) and d.get("content"):
                            docs.append(d)
                    except json.JSONDecodeError:
                        continue
            self.documents = docs[-self.max_docs:]
        except OSError:
            self.documents = []

    def _append(self, doc: dict):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _compact(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                for d in self.documents:
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def add_document(self, content: str, metadata: dict = None):
        if not content or not content.strip():
            return
        doc = {"content": content.strip()[:4000],
               "metadata": metadata or {},
               "embedding": _hash_embed(content, self.dim),
               "time": time.time()}
        with self._lock:
            self.documents.append(doc)
            self._append(doc)
            if len(self.documents) > self.max_docs:
                self.documents = self.documents[-self.max_docs:]
                self._compact()

    def add_documents(self, items: list):
        for it in items:
            if isinstance(it, dict):
                self.add_document(it.get("content", ""), it.get("metadata"))
            else:
                self.add_document(str(it))

    def search(self, query: str, top_k: int = 5) -> list:
        if not query:
            return []
        with self._lock:
            docs = list(self.documents)
        if not docs:
            return []
        q = _hash_embed(query, self.dim)
        scored = []
        for d in docs:
            s = _cosine(q, d.get("embedding") or [])
            if s > 0.05:
                scored.append((s, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:top_k]]

    def format_for_prompt(self, query: str, top_k: int = 3) -> str:
        docs = self.search(query, top_k=top_k)
        if not docs:
            return ""
        lines = ["【相关知识】"]
        for d in docs:
            lines.append(f"- {d['content'][:150]}")
        return "\n".join(lines)

    def stats(self) -> dict:
        with self._lock:
            return {"documents": len(self.documents), "dim": self.dim,
                    "path": str(self.path)}

    def clear(self):
        with self._lock:
            self.documents.clear()
            try:
                if self.path.exists():
                    self.path.unlink()
            except OSError:
                pass


class ContextCompressor:
    def __init__(self, max_chars: int = 4000, keep_recent: int = 8,
                 summary_slots: int = 20):
        self.max_chars = max_chars
        self.keep_recent = keep_recent
        self._summaries: deque[str] = deque(maxlen=summary_slots)

    def compress(self, turns: list) -> str:
        if not turns:
            return ""
        text = "\n".join(f"{t.get('role','user')}: {t.get('content','')}" for t in turns)
        if len(text) <= self.max_chars:
            return text
        recent = turns[-self.keep_recent:]
        older = turns[:-self.keep_recent]
        summary = self._summarize(older)
        if summary:
            self._summaries.append(summary)
        recent_text = "\n".join(f"{t.get('role','user')}: {t.get('content','')}"
                                for t in recent)
        return f"（早期对话摘要：{summary}）\n{recent_text}"

    def _summarize(self, turns: list) -> str:
        if not turns:
            return ""
        keys = [t.get("content", "")[:30] for t in turns]
        return "；".join(keys[-6:])[:300]

    def recent_summary(self) -> str:
        return self._summaries[-1] if self._summaries else ""

    def clear(self):
        self._summaries.clear()


class MemoryHub:
    def __init__(self, base_dir=None, rag_dim: int = 512,
                 short_size: int = 20, long_max: int = 5000,
                 compress_chars: int = 4000):
        self.short = ShortTermMemory(max_size=short_size)
        self.long = LongTermMemory(max_items=long_max)
        self.session = SessionPersistence()
        self.graph = KnowledgeGraph()
        self.rag = RAG(dim=rag_dim)
        self.compressor = ContextCompressor(max_chars=compress_chars)
        self._lock = threading.RLock()

    def record_user(self, text: str, importance: float = 0.5, tags=None):
        self.short.add("user", text, importance, tags)
        self.long.add("user", text, importance, tags)

    def record_assistant(self, text: str, importance: float = 0.6, tags=None):
        self.short.add("assistant", text, importance, tags)
        self.long.add("assistant", text, importance, tags)

    def record_turn(self, user: str, reply: str, tool_calls: list = None,
                    tags=None):
        self.record_user(user, tags=tags)
        self.record_assistant(reply, tags=tags)
        self.session.append_turn(user, reply, tool_calls)

    def learn(self, text: str) -> int:
        return self.graph.learn(text)

    def index(self, text: str, metadata: dict = None):
        self.rag.add_document(text, metadata)

    def recall(self, query: str, top_k: int = 5) -> list:
        return self.long.search(query, top_k=top_k)

    def context(self, query: str = "", recent_n: int = 8,
                include_rag: bool = True) -> str:
        parts = []
        recent = self.short.recent(recent_n)
        if recent:
            parts.append("\n".join(f"{'用户' if i.role == 'user' else '小凌'}: {i.content}"
                                   for i in recent))
        if include_rag and query:
            rag_ctx = self.rag.format_for_prompt(query, top_k=3)
            if rag_ctx:
                parts.append(rag_ctx)
        return "\n".join(parts)

    def search_all(self, query: str, top_k: int = 5) -> dict:
        return {
            "long": [i.to_dict() for i in self.long.search(query, top_k)],
            "rag": self.rag.search(query, top_k),
            "graph": self.graph.search(query, limit=top_k),
        }

    def clear_short(self):
        self.short.clear()
        self.compressor.clear()

    def clear_long(self):
        self.long.clear()

    def clear_all(self):
        self.short.clear()
        self.long.clear()
        self.session.clear()
        self.compressor.clear()

    def reset_graph(self):
        self.graph.clear()

    def reset_rag(self):
        self.rag.clear()

    def flush(self):
        self.long.flush()

    def stats(self) -> dict:
        return {
            "short": len(self.short),
            "long": self.long.stats(),
            "session": self.session.stats(),
            "graph": self.graph.stats(),
            "rag": self.rag.stats(),
            "summary": self.compressor.recent_summary()[:80],
        }

    def selftest(self) -> dict:
        out = {}
        try:
            self.short.add("user", "ping")
            out["short"] = len(self.short) > 0
        except Exception as e:
            out["short"] = f"error: {e}"
        try:
            self.graph.learn("小凌是数字生命")
            out["graph"] = self.graph.stats()["entities"] > 0
        except Exception as e:
            out["graph"] = f"error: {e}"
        try:
            self.rag.add_document("测试文档内容")
            out["rag"] = self.rag.stats()["documents"] > 0
        except Exception as e:
            out["rag"] = f"error: {e}"
        return out


def merge_history_into_memory(store: LongTermMemory,
                              history: list,
                              skip_empty: bool = True) -> int:
    n = 0
    for h in history:
        u = (h.get("user") or "").strip()
        r = (h.get("reply") or "").strip()
        if skip_empty and not u:
            continue
        if u:
            store.add("user", u, importance=0.5)
            n += 1
        if r:
            store.add("assistant", r, importance=0.6)
            n += 1
    return n


def summarize_turns(turns: list, max_chars: int = 400) -> str:
    if not turns:
        return ""
    parts = []
    for t in turns[-20:]:
        c = (t.get("content") or "").strip()
        if c:
            parts.append(c[:60])
    return "；".join(parts)[:max_chars]


def build_prompt_context(short: ShortTermMemory,
                         long: LongTermMemory,
                         rag: RAG,
                         query: str = "",
                         recent_n: int = 8) -> str:
    parts = []
    recent = short.recent(recent_n)
    if recent:
        parts.append("\n".join(f"{'用户' if i.role == 'user' else '小凌'}: {i.content}"
                               for i in recent))
    if query:
        hits = long.search(query, top_k=3)
        if hits:
            parts.append("【长期记忆】\n" + "\n".join(f"- {i.content[:120]}" for i in hits))
        rag_ctx = rag.format_for_prompt(query, top_k=3)
        if rag_ctx:
            parts.append(rag_ctx)
    return "\n\n".join(parts)