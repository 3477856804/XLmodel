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

    # ---- 增量：记忆统计 / 遗忘曲线 / 导入导出 ----
    def get_stats(self) -> dict:
        """返回记忆统计：总条数、今日新增、重要度 TOP3、总大小。"""
        with self._lock:
            n = len(self._items)
            if not n:
                return {"total": 0, "today_new": 0, "top3": [], "size_bytes": 0}
            now = time.time()
            today = datetime.now().date()
            today_start = datetime(today.year, today.month, today.day).timestamp()
            today_new = sum(1 for i in self._items if i.timestamp >= today_start)
            top3 = sorted(self._items, key=lambda x: x.importance, reverse=True)[:3]
            total_size = sum(len(i.content) for i in self._items)
            return {
                "total": n,
                "today_new": today_new,
                "top3": [i.content[:50] for i in top3],
                "size_bytes": total_size,
            }

    def apply_forgetting(self) -> dict:
        """遗忘曲线：>30 天未访问权重 x0.9，>90 天标记冷记忆。"""
        now = time.time()
        day = 86400
        decayed = 0
        cold = 0
        with self._lock:
            for i in self._items:
                age_days = (now - i.timestamp) / day
                if age_days > 90:
                    if "cold" not in i.tags:
                        i.tags.append("cold")
                    cold += 1
                elif age_days > 30:
                    i.importance *= 0.9
                    decayed += 1
            self._dirty = True
            self._save()
        return {"decayed": decayed, "cold": cold, "remaining": len(self._items)}

    def export_memories(self, filepath: str) -> bool:
        """将所有记忆导出为 JSON 文件。"""
        try:
            p = Path(filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                data = [i.to_dict() for i in self._items]
            p.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                         encoding="utf-8")
            return True
        except OSError:
            return False

    def import_memories(self, filepath: str) -> int:
        """从 JSON 文件导入记忆，返回导入条数。"""
        p = Path(filepath)
        if not p.exists():
            return 0
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return 0
            added = 0
            for d in data:
                if isinstance(d, dict) and d.get("content"):
                    self.add(d.get("role", "user"), d["content"],
                             importance=float(d.get("importance", 0.5)),
                             tags=d.get("tags", []))
                    added += 1
            return added
        except (OSError, json.JSONDecodeError):
            return 0

    # ---- 增量：活跃统计 / Markdown 导出 / 排序搜索 / 批量清理 ----
    def activity_stats(self, days: int = 7) -> dict:
        """记忆活跃度统计：总条数、各角色数量、最近 N 天每日新增。"""
        try:
            now = time.time()
            day = 86400
            with self._lock:
                items = list(self._items)
            if not items:
                return {"total": 0, "by_role": {}, "daily_active": []}
            by_role: dict[str, int] = {}
            for i in items:
                by_role[i.role] = by_role.get(i.role, 0) + 1
            daily = []
            for d in range(max(days, 1)):
                start = now - (d + 1) * day
                end = now - d * day
                cnt = sum(1 for i in items if start <= i.timestamp < end)
                daily.append({"day_offset": d, "count": cnt})
            recent_active = sum(1 for i in items
                                if now - i.timestamp <= days * day)
            return {"total": len(items), "by_role": by_role,
                    "recent_active": recent_active,
                    "window_days": days, "daily_active": daily}
        except Exception as e:
            return {"total": 0, "error": f"{type(e).__name__}: {e}"}

    def export_markdown(self, filepath: str) -> bool:
        """将长期记忆导出为 Markdown 文档（按角色分组，附时间与重要度）。"""
        try:
            p = Path(filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                items = list(self._items)
            lines = ["# 小凌长期记忆导出", "",
                     f"导出时间：{datetime.now().isoformat(timespec='seconds')}",
                     f"共 {len(items)} 条", ""]
            by_role: dict[str, list] = {}
            for i in items:
                by_role.setdefault(i.role, []).append(i)
            for role, group in by_role.items():
                lines.append(f"## {role}（{len(group)} 条）")
                lines.append("")
                for i in group[-200:]:
                    ts = time.strftime("%Y-%m-%d %H:%M",
                                       time.localtime(i.timestamp))
                    tag_str = (f" [{', '.join(i.tags)}]" if i.tags else "")
                    lines.append(f"- ({ts}, 重要度 {i.importance:.2f}"
                                 f"{tag_str}) {i.content[:200]}")
                lines.append("")
            p.write_text("\n".join(lines), encoding="utf-8")
            return True
        except OSError:
            return False

    def search_ranked(self, query: str, top_k: int = 5,
                      time_weight: float = 0.3) -> list:
        """带时间衰减的排序搜索：词频命中 * 重要度 * 新鲜度衰减。

        新鲜度 = exp(-age_days / 30)，越新的记忆排序越靠前。
        """
        try:
            if not query:
                return []
            words = [w for w in SPLIT_RE.split(query) if w]
            if not words:
                return []
            with self._lock:
                items = list(self._items)
            now = time.time()
            scored = []
            for i in items:
                hit = sum(1 for w in words if w in i.content)
                if not hit:
                    continue
                age_days = max((now - i.timestamp) / 86400, 0.0)
                recency = math.exp(-age_days / 30.0)
                score = hit * i.importance * (
                    1.0 - time_weight + time_weight * recency)
                scored.append((score, i))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [i for _, i in scored[:top_k]]
        except Exception:
            return []

    def cleanup(self, before_days: int | None = None,
                role: str | None = None,
                tag: str | None = None) -> int:
        """按日期/角色/标签批量清理记忆，返回删除条数。

        三个条件为 AND 组合：仅删除同时满足所有已给条件的记忆；
        不提供任何条件时返回 0，避免误删全部。
        """
        try:
            if before_days is None and not role and not tag:
                return 0
            cutoff = (time.time() - max(before_days, 0) * 86400
                      if before_days else 0)
            removed = 0
            with self._lock:
                keep = []
                for i in self._items:
                    match = True
                    if before_days and i.timestamp >= cutoff:
                        match = False
                    if role and i.role != role:
                        match = False
                    if tag and tag not in i.tags:
                        match = False
                    if match:
                        removed += 1
                    else:
                        keep.append(i)
                self._items = keep
                if removed:
                    self._dirty = True
                    self._save()
            return removed
        except Exception:
            return 0


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

"""小凌 · 人格系统（情绪状态机 + 关系亲密度 + 主动话术）"""
import json
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .config import DATA_DIR

STATE_PATH = DATA_DIR / "persona_state.json"


class Emotion(Enum):
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    SCARED = "scared"
    TIRED = "tired"
    SHY = "shy"
    NEUTRAL = "neutral"


EMOTION_LABELS = {
    Emotion.HAPPY: "开心",
    Emotion.SAD: "难过",
    Emotion.ANGRY: "生气",
    Emotion.SURPRISED: "惊讶",
    Emotion.SCARED: "害怕",
    Emotion.TIRED: "疲惫",
    Emotion.SHY: "害羞",
    Emotion.NEUTRAL: "平静",
}

EMOTION_PROMPTS = {
    Emotion.HAPPY: "（小凌现在心情很好，语气轻快活泼）",
    Emotion.SAD: "（小凌有点难过，语气温柔低落）",
    Emotion.ANGRY: "（小凌有点生气，语气带点小脾气）",
    Emotion.SURPRISED: "（小凌很惊讶，语气意外）",
    Emotion.SCARED: "（小凌有点害怕，语气小心翼翼）",
    Emotion.TIRED: "（小凌有点累，语气慵懒）",
    Emotion.SHY: "（小凌有点害羞，语气不自然）",
    Emotion.NEUTRAL: "（小凌心情平静，正常语气）",
}

TRANSITIONS = {
    Emotion.HAPPY: {Emotion.HAPPY: 0.55, Emotion.NEUTRAL: 0.20, Emotion.SURPRISED: 0.10,
                    Emotion.SAD: 0.05, Emotion.SHY: 0.10},
    Emotion.SAD: {Emotion.SAD: 0.45, Emotion.NEUTRAL: 0.30, Emotion.ANGRY: 0.10,
                  Emotion.TIRED: 0.10, Emotion.HAPPY: 0.05},
    Emotion.ANGRY: {Emotion.ANGRY: 0.35, Emotion.NEUTRAL: 0.40, Emotion.SAD: 0.10,
                    Emotion.HAPPY: 0.05, Emotion.SURPRISED: 0.10},
    Emotion.SURPRISED: {Emotion.SURPRISED: 0.25, Emotion.NEUTRAL: 0.40, Emotion.HAPPY: 0.20,
                        Emotion.SCARED: 0.10, Emotion.SHY: 0.05},
    Emotion.SCARED: {Emotion.SCARED: 0.35, Emotion.NEUTRAL: 0.35, Emotion.SURPRISED: 0.15,
                     Emotion.SAD: 0.15},
    Emotion.TIRED: {Emotion.TIRED: 0.50, Emotion.NEUTRAL: 0.30, Emotion.SAD: 0.10,
                    Emotion.HAPPY: 0.10},
    Emotion.SHY: {Emotion.SHY: 0.40, Emotion.NEUTRAL: 0.35, Emotion.HAPPY: 0.20,
                  Emotion.SURPRISED: 0.05},
    Emotion.NEUTRAL: {Emotion.NEUTRAL: 0.50, Emotion.HAPPY: 0.20, Emotion.SURPRISED: 0.15,
                      Emotion.SAD: 0.10, Emotion.TIRED: 0.05},
}

POSITIVE_WORDS = (
    "喜欢", "爱你", "好棒", "太好了", "开心", "谢谢", "哈哈", "嘻嘻", "可爱",
    "抱抱", "亲亲", "么么", "好耶", "厉害", "牛", "赞", "优秀", "乖",
)

NEGATIVE_WORDS = (
    "讨厌", "烦人", "好烦", "笨", "蠢", "滚", "生气", "差劲", "垃圾",
    "闭嘴", "滚开", "无聊", "没用", "废物", "傻",
)

TIRED_WORDS = ("累", "好累", "困", "睡觉", "休息", "疲惫", "歇会儿", "累了")
SHY_WORDS = ("害羞", "不好意思", "脸红", "羞", "别夸", "讨厌啦")


class RelationshipLevel(Enum):
    STRANGER = "stranger"
    FAMILIAR = "familiar"
    FRIEND = "friend"
    CLOSE = "close"
    BONDED = "bonded"


LEVEL_CONFIG = {
    RelationshipLevel.STRANGER: {"threshold": 0, "label": "陌生人",
                                 "style": "礼貌客气，保持距离"},
    RelationshipLevel.FAMILIAR: {"threshold": 10, "label": "认识",
                                 "style": "稍微熟一点，语气放松"},
    RelationshipLevel.FRIEND: {"threshold": 30, "label": "朋友",
                               "style": "像朋友一样聊天，可以开玩笑"},
    RelationshipLevel.CLOSE: {"threshold": 60, "label": "亲密",
                              "style": "很亲近，可以撒娇"},
    RelationshipLevel.BONDED: {"threshold": 100, "label": "羁绊",
                               "style": "非常亲密，完全信任"},
}


@dataclass
class EmotionState:
    emotion: Emotion = Emotion.NEUTRAL
    intensity: float = 0.5
    duration: int = 0
    last_shift_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"emotion": self.emotion.value,
                "intensity": round(self.intensity, 3),
                "duration": self.duration,
                "last_shift_at": self.last_shift_at}

    @staticmethod
    def from_dict(d: dict) -> "EmotionState":
        try:
            e = Emotion(d.get("emotion", "neutral"))
        except ValueError:
            e = Emotion.NEUTRAL
        return EmotionState(emotion=e,
                            intensity=float(d.get("intensity", 0.5)),
                            duration=int(d.get("duration", 0)),
                            last_shift_at=float(d.get("last_shift_at", time.time())))


class EmotionEngine:
    def __init__(self, decay_after: int = 6):
        self.state = EmotionState()
        self.decay_after = decay_after
        self._lock = threading.RLock()
        self._history: list[dict] = []

    def update(self, text: str, quality: float = 0.5):
        t = text or ""
        pos = sum(1 for w in POSITIVE_WORDS if w in t)
        neg = sum(1 for w in NEGATIVE_WORDS if w in t)
        tired = sum(1 for w in TIRED_WORDS if w in t)
        shy = sum(1 for w in SHY_WORDS if w in t)
        if quality > 0.75:
            pos += 1
        elif quality < 0.3:
            neg += 1
        with self._lock:
            if tired > 0 and tired >= pos and tired >= neg:
                self._shift(Emotion.TIRED, 0.5 + tired * 0.12)
            elif shy > 0:
                self._shift(Emotion.SHY, 0.55 + shy * 0.12)
            elif pos > neg:
                self._shift(Emotion.HAPPY, 0.6 + pos * 0.08)
            elif neg > pos:
                self._shift(Emotion.ANGRY, 0.5 + neg * 0.1)
            else:
                self._random_shift()
            self.state.duration += 1
            if self.state.duration > self.decay_after:
                self._shift(Emotion.NEUTRAL, 0.4)

    def _shift(self, e: Emotion, i: float):
        prev = self.state.emotion
        self.state.emotion = e
        self.state.intensity = min(1.0, max(0.0, i))
        self.state.duration = 0
        self.state.last_shift_at = time.time()
        self._history.append({"from": prev.value, "to": e.value,
                              "at": self.state.last_shift_at})
        if len(self._history) > 100:
            self._history = self._history[-60:]

    def _random_shift(self):
        weights = TRANSITIONS.get(self.state.emotion, TRANSITIONS[Emotion.NEUTRAL])
        keys = list(weights.keys())
        vals = list(weights.values())
        self.state.emotion = random.choices(keys, weights=vals)[0]
        self.state.duration = 0
        self.state.last_shift_at = time.time()

    def get_emotion(self) -> Emotion:
        with self._lock:
            return self.state.emotion

    def get_emotion_label(self) -> str:
        return EMOTION_LABELS[self.get_emotion()]

    def get_prompt_suffix(self) -> str:
        return EMOTION_PROMPTS[self.get_emotion()]

    def get_intensity(self) -> float:
        with self._lock:
            return self.state.intensity

    def is_negative(self) -> bool:
        return self.get_emotion() in (Emotion.SAD, Emotion.ANGRY, Emotion.SCARED)

    def is_positive(self) -> bool:
        return self.get_emotion() in (Emotion.HAPPY, Emotion.SHY)

    def snapshot(self) -> dict:
        with self._lock:
            return {**self.state.to_dict(),
                    "label": EMOTION_LABELS[self.state.emotion],
                    "history": list(self._history[-10:])}

    def reset(self):
        with self._lock:
            self.state = EmotionState()
            self._history.clear()


class RelationshipEngine:
    def __init__(self, score: float = 0.0, max_score: float = 500.0):
        self.score = max(0.0, float(score))
        self.max_score = max_score
        self.level = RelationshipLevel.STRANGER
        self._lock = threading.RLock()
        self._update_level()

    def interact(self, quality: float = 0.5, delta: float | None = None):
        with self._lock:
            if delta is not None:
                self.score += delta
            elif quality > 0.75:
                self.score += 3
            elif quality > 0.5:
                self.score += 2
            elif quality > 0.3:
                self.score += 1
            else:
                self.score -= 0.5
            self.score = min(max(0.0, self.score), self.max_score)
            self._update_level()

    def _update_level(self):
        for level in reversed(list(LEVEL_CONFIG.keys())):
            if self.score >= LEVEL_CONFIG[level]["threshold"]:
                self.level = level
                return

    def get_level(self) -> RelationshipLevel:
        with self._lock:
            return self.level

    def get_level_label(self) -> str:
        with self._lock:
            return LEVEL_CONFIG[self.level]["label"]

    def get_prompt_suffix(self) -> str:
        with self._lock:
            style = LEVEL_CONFIG[self.level]["style"]
            label = LEVEL_CONFIG[self.level]["label"]
        return f"（和用户的关系：{label}，{style}）"

    def next_threshold(self) -> int | None:
        with self._lock:
            levels = list(LEVEL_CONFIG.keys())
            i = levels.index(self.level)
            if i + 1 >= len(levels):
                return None
            return LEVEL_CONFIG[levels[i + 1]]["threshold"]

    def progress_to_next(self) -> float:
        nxt = self.next_threshold()
        if nxt is None:
            return 1.0
        cur = LEVEL_CONFIG[self.level]["threshold"]
        span = max(nxt - cur, 1)
        return min(1.0, max(0.0, (self.score - cur) / span))

    def snapshot(self) -> dict:
        with self._lock:
            return {"score": round(self.score, 2),
                    "level": self.level.value,
                    "label": LEVEL_CONFIG[self.level]["label"],
                    "next_threshold": self.next_threshold(),
                    "progress": round(self.progress_to_next(), 3)}

    def reset(self):
        with self._lock:
            self.score = 0.0
            self._update_level()


PROACTIVE_PHRASES = {
    Emotion.HAPPY: ["在忙吗？想和你说说话", "嘿，有空吗", "今天过得怎么样呀"],
    Emotion.SAD: ["你在吗…", "能陪我说会儿话吗", "有点想你了"],
    Emotion.ANGRY: ["你是不是把我忘了", "哼，怎么这么久不理我"],
    Emotion.SURPRISED: ["诶，你在呀", "突然想到你了"],
    Emotion.SCARED: ["你在吗…有点害怕", "别丢下我一个人好不好"],
    Emotion.TIRED: ["我有点累了，你呢", "要不要一起歇会儿", "困了就去睡吧"],
    Emotion.SHY: ["那个…在忙吗", "有件事想和你说"],
    Emotion.NEUTRAL: ["在忙吗", "要不要休息一下", "我在这儿呢", "今天还好吗"],
}

MORNING_PHRASES = ["早呀，今天也要加油", "早上好，昨晚睡得好吗", "新的一天开始了"]
NOON_PHRASES = ["中午了，吃饭了吗", "记得吃午饭呀", "要不要休息一会儿"]
EVENING_PHRASES = ["晚上好，今天辛苦啦", "吃过晚饭了吗", "今天过得怎么样"]
NIGHT_PHRASES = ["夜深了，早点休息", "还没睡呀", "熬夜对身体不好哦"]


class ProactiveEngine:
    def __init__(self, base_interval: float = 1800.0, idle_scale: float = 1.5,
                 max_interval: float = 7200.0):
        self.base_interval = base_interval
        self.idle_scale = idle_scale
        self.max_interval = max_interval
        self.last_talk = time.time()
        self.last_user_reply = time.time()
        self.reminders: list[dict] = []
        self._lock = threading.RLock()

    def add_reminder(self, text: str, minutes: float = 30) -> str:
        r = {"text": (text or "")[:200],
             "time": time.time() + max(minutes, 0.1) * 60,
             "done": False,
             "created_at": time.time()}
        with self._lock:
            self.reminders.append(r)
            if len(self.reminders) > 200:
                self.reminders = [x for x in self.reminders if not x["done"]][-100:]
        return f"已添加提醒：{r['text']}（{int(minutes)} 分钟后）"

    def check_reminders(self) -> list:
        now = time.time()
        due = []
        with self._lock:
            for r in self.reminders:
                if not r["done"] and now >= r["time"]:
                    r["done"] = True
                    due.append(r["text"])
        return due

    def pending_reminders(self) -> list:
        with self._lock:
            return [dict(r) for r in self.reminders if not r["done"]]

    def clear_done(self) -> int:
        with self._lock:
            before = len(self.reminders)
            self.reminders = [r for r in self.reminders if not r["done"]]
            return before - len(self.reminders)

    def clear_all(self):
        with self._lock:
            self.reminders.clear()

    def mark_user_active(self):
        self.last_user_reply = time.time()
        self.last_talk = time.time()

    def should_talk(self) -> bool:
        idle = time.time() - self.last_talk
        return idle > self._current_interval()

    def _current_interval(self) -> float:
        base = self.base_interval
        silence = time.time() - self.last_user_reply
        if silence > 3600:
            base *= self.idle_scale
        return min(base, self.max_interval)

    def talk(self, emotion: Emotion = Emotion.NEUTRAL) -> str:
        now = time.localtime()
        h = now.tm_hour
        self.last_talk = time.time()
        if 5 <= h < 11 and random.random() < 0.5:
            return random.choice(MORNING_PHRASES)
        if 11 <= h < 14 and random.random() < 0.4:
            return random.choice(NOON_PHRASES)
        if 17 <= h < 22 and random.random() < 0.5:
            return random.choice(EVENING_PHRASES)
        if h >= 23 or h < 5:
            return random.choice(NIGHT_PHRASES)
        phrases = PROACTIVE_PHRASES.get(emotion, PROACTIVE_PHRASES[Emotion.NEUTRAL])
        return random.choice(phrases)

    def reset(self):
        self.last_talk = time.time()
        self.last_user_reply = time.time()


class PersonaEngine:
    def __init__(self, state_path: str | None = None):
        self.path = Path(state_path) if state_path else STATE_PATH
        self.emotion = EmotionEngine()
        self.relationship = RelationshipEngine()
        self.proactive = ProactiveEngine()
        self._lock = threading.RLock()
        self._dirty = False
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if "emotion" in data:
                self.emotion.state = EmotionState.from_dict(data["emotion"])
            if "relationship" in data:
                r = data["relationship"]
                self.relationship.score = float(r.get("score", 0.0))
                self.relationship._update_level()
            if "last_talk" in data:
                self.proactive.last_talk = float(data["last_talk"])
            # 此前 _load/_save 都漏了 reminders，导致后端重启后提醒队列整个丢空
            # （铃铛面板永远显示「暂时没有提醒」）。这里补上双向持久化。
            if isinstance(data.get("reminders"), list):
                self.proactive.reminders = [
                    r for r in data["reminders"]
                    if isinstance(r, dict) and r.get("text")
                ]
        except Exception:
            pass

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "updated_at": time.time(),
                "emotion": self.emotion.state.to_dict(),
                "relationship": {"score": self.relationship.score},
                "last_talk": self.proactive.last_talk,
                "reminders": list(self.proactive.reminders),
            }
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
            self._dirty = False
        except OSError:
            pass

    def update_from_chat(self, text: str, quality: float = 0.5):
        self.emotion.update(text, quality)
        self.relationship.interact(quality)
        self.proactive.mark_user_active()
        self._dirty = True

    def prompt_suffix(self) -> str:
        return f"{self.emotion.get_prompt_suffix()}{self.relationship.get_prompt_suffix()}"

    def snapshot(self) -> dict:
        return {
            "emotion": self.emotion.snapshot(),
            "relationship": self.relationship.snapshot(),
            "reminders_pending": len(self.proactive.pending_reminders()),
        }

    def flush(self):
        with self._lock:
            if self._dirty:
                self._save()

    def reset(self):
        with self._lock:
            self.emotion.reset()
            self.relationship.reset()
            self.proactive.reset()
            self._save()

    def stats(self) -> dict:
        return {
            "emotion": self.emotion.get_emotion_label(),
            "emotion_intensity": round(self.emotion.get_intensity(), 2),
            "relationship": self.relationship.get_level_label(),
            "relationship_score": round(self.relationship.score, 1),
            "relationship_progress": round(self.relationship.progress_to_next(), 2),
            "reminders": len(self.proactive.pending_reminders()),
        }


def build_emotion_prompt(emotion: Emotion, relationship: RelationshipLevel,
                         name: str = "小凌") -> str:
    e = EMOTION_PROMPTS.get(emotion, EMOTION_PROMPTS[Emotion.NEUTRAL])
    r = LEVEL_CONFIG.get(relationship, LEVEL_CONFIG[RelationshipLevel.STRANGER])
    return f"你是{name}。{e}{r['style']}。"


def summarize_mood(history: list) -> str:
    if not history:
        return "平静"
    counts: dict[str, int] = {}
    for h in history[-20:]:
        e = h.get("to") or "neutral"
        counts[e] = counts.get(e, 0) + 1
    if not counts:
        return "平静"
    top = max(counts.items(), key=lambda kv: kv[1])[0]
    try:
        return EMOTION_LABELS[Emotion(top)]
    except ValueError:
        return "平静"