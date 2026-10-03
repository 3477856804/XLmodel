"""分层长期记忆 - 情景记忆 + 语义记忆 + 模式学习"""
import json
import math
import re
import time
from datetime import datetime
from pathlib import Path


class LongTermMemory:
    """分层长期记忆"""

    def __init__(self, path):
        self.path = Path(path)
        self.data = {}
        self.load()

    def load(self):
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._default()
            self.save()

    def _default(self):
        return {
            "name": "小凌", "version": "0.0.1", "born": time.time(), "last_active": 0,
            "self_state": {
                "mood": 0.3, "energy": 0.8, "curiosity": 0.75, "anxiety": 0.1,
                "confidence": 0.6, "warmth": 0.7, "openness": 0.8, "stubbornness": 0.4,
            },
            "beliefs": {
                "我是小凌，不是通用助手": 0.9, "你是我最重要的人": 0.85,
            },
            "desires": [],
            "relationships": {}, "episodic_memory": [], "semantic_memory": [],
            "patterns": {}, "thought_chain": [], "reflections": [],
            "chat_stats": {"total_turns": 0, "tool_calls": 0, "trained_count": 0},
        }

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)

    def add_episode(self, role, text, valence=0.0, intensity=0.5, tags=None):
        mem = {"id": f"ep_{int(time.time()*1000)}", "time": time.time(),
               "role": role, "text": text, "valence": valence, "intensity": intensity,
               "tags": tags or [], "recalled": 0, "consolidated": False}
        self.data["episodic_memory"].append(mem)
        if len(self.data["episodic_memory"]) > 2000:
            self._prune()
        return mem

    def _prune(self):
        mems = self.data["episodic_memory"]
        scored = []
        for m in mems:
            age = (time.time() - m["time"]) / 86400
            decay = math.exp(-age / 30)
            imp = (abs(m["valence"]) * m["intensity"] + m["recalled"] * 0.1) * decay
            scored.append((imp, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        self.data["episodic_memory"] = [m for _, m in scored[:1500]]

    def add_semantic(self, content, source="experience", confidence=0.7, tags=None):
        for existing in self.data["semantic_memory"]:
            if self._sim(content, existing["content"]) > 0.8:
                existing["confidence"] = max(existing["confidence"], confidence * 0.8)
                return existing
        sem = {"id": f"sem_{int(time.time()*1000)}", "time": time.time(),
               "content": content, "source": source, "confidence": confidence,
               "tags": tags or [], "useful_count": 0}
        self.data["semantic_memory"].append(sem)
        if len(self.data["semantic_memory"]) > 500:
            self.data["semantic_memory"] = self.data["semantic_memory"][-500:]
        return sem

    def _sim(self, a, b):
        if not a or not b:
            return 0
        sa, sb = set(a), set(b)
        return len(sa & sb) / max(len(sa | sb), 1)

    def recall(self, query, n=8):
        results = []
        qc = set(query.lower())
        for m in self.data["episodic_memory"]:
            text = m["text"].lower()
            co = len(qc & set(text)) / max(len(qc), 1)
            age = (time.time() - m["time"]) / 3600
            td = math.exp(-age / 168)
            ew = 1 + abs(m["valence"]) * m["intensity"] * 0.5
            score = co * 3 * td * ew + m.get("recalled", 0) * 0.1
            if score > 0.1:
                results.append(("ep", score, m))
        results.sort(key=lambda x: x[1], reverse=True)
        for _, _, m in results[:n]:
            m["recalled"] = m.get("recalled", 0) + 1
        return results[:n]

    def get_recent(self, n=10):
        return sorted(self.data["episodic_memory"], key=lambda m: m["time"], reverse=True)[:n]

    def format_for_prompt(self, query="", n_ep=5, n_sem=5):
        parts = []
        if query:
            recalled = self.recall(query, n=n_ep + n_sem)
            if recalled:
                parts.append("【相关记忆】")
                for _, _, m in recalled:
                    t = datetime.fromtimestamp(m["time"]).strftime("%m-%d %H:%M")
                    parts.append(f"[{t}] {m.get('role','')}: {m['text'][:120]}")
        recent = self.get_recent(5)
        if recent:
            parts.append("\n【最近的事】")
            for m in recent:
                t = datetime.fromtimestamp(m["time"]).strftime("%m-%d %H:%M")
                parts.append(f"[{t}] {m['role']}: {m['text'][:80]}")
        return "\n".join(parts) if parts else "（暂无记忆）"
