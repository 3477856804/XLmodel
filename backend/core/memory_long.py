"""长期记忆 - 向量存储 + 检索"""
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from .platform import get_user_data_dir


@dataclass
class LongTermMemory:
    id: str
    content: str
    embedding: list[float]
    timestamp: float
    importance: float = 0.5
    category: str = "general"  # user_info / preference / event / fact


class LongTermMemoryStore:
    """长期记忆存储（JSON 文件 + 简单向量检索）"""

    def __init__(self):
        self.data_dir = get_user_data_dir() / "memory"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.data_dir / "memories.json"
        self._memories: list[LongTermMemory] = []
        self._load()

    def _load(self):
        if self.memory_file.exists():
            try:
                data = json.loads(self.memory_file.read_text(encoding="utf-8"))
                self._memories = [LongTermMemory(**item) for item in data]
            except Exception:
                self._memories = []

    def _save(self):
        data = [asdict(m) for m in self._memories]
        self.memory_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, content: str, importance: float = 0.5,
            category: str = "general", embedding: Optional[list[float]] = None):
        import uuid
        memory = LongTermMemory(
            id=str(uuid.uuid4())[:8],
            content=content,
            embedding=embedding or [0.0] * 128,  # 占位，实际用 embedding 模型
            timestamp=time.time(),
            importance=importance,
            category=category,
        )
        self._memories.append(memory)
        self._save()
        return memory

    def search(self, query: str, top_k: int = 5) -> list[LongTermMemory]:
        """简单关键词匹配检索（后续换向量检索）"""
        query_lower = query.lower()
        scored = []
        for m in self._memories:
            # 简单关键词匹配
            score = 0.0
            for word in query_lower.split():
                if word in m.content.lower():
                    score += 1.0
            # 重要性加权
            score *= m.importance
            scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for score, m in scored[:top_k] if score > 0]

    def get_by_category(self, category: str) -> list[LongTermMemory]:
        return [m for m in self._memories if m.category == category]

    def forget(self, memory_id: str):
        self._memories = [m for m in self._memories if m.id != memory_id]
        self._save()

    def clear_old(self, days: int = 90):
        """遗忘曲线：删除超过 N 天的低重要性记忆"""
        cutoff = time.time() - days * 86400
        before = len(self._memories)
        self._memories = [
            m for m in self._memories
            if m.timestamp > cutoff or m.importance > 0.7
        ]
        after = len(self._memories)
        self._save()
        return before - after

    def count(self) -> int:
        return len(self._memories)
