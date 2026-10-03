"""记忆系统 - 短期工作记忆 + 长期向量记忆"""
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class MemoryItem:
    role: str
    content: str
    timestamp: float
    importance: float = 0.5


class ShortTermMemory:
    """短期工作记忆，保存最近 N 轮对话"""

    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._items: deque[MemoryItem] = deque(maxlen=max_size)

    def add(self, role: str, content: str, importance: float = 0.5):
        self._items.append(MemoryItem(
            role=role, content=content,
            timestamp=time.time(), importance=importance,
        ))

    def get_recent(self, n: Optional[int] = None) -> list[MemoryItem]:
        if n is None:
            return list(self._items)
        return list(self._items)[-n:]

    def to_prompt(self) -> str:
        lines = []
        for item in self._items:
            name = "用户" if item.role == "user" else "小凌"
            lines.append(f"{name}: {item.content}")
        return "\n".join(lines)

    def clear(self):
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


class LongTermMemory:
    """长期记忆 - 向量库 + 遗忘曲线"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self._items: list[MemoryItem] = []
        self._decay_rate = 0.995  # 每轮遗忘 0.5%

    def add(self, role: str, content: str, importance: float = 0.5):
        self._items.append(MemoryItem(
            role=role, content=content,
            timestamp=time.time(), importance=importance,
        ))

    def forget(self):
        """应用遗忘曲线，移除低重要性的旧记忆"""
        now = time.time()
        self._items = [
            item for item in self._items
            if (now - item.timestamp) * self._decay_rate * item.importance > 0.01
        ]

    def search(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        """简单关键词搜索"""
        results = []
        for item in self._items:
            if any(word in item.content for word in query.split()):
                results.append(item)
        return results[-top_k:]

    def stats(self) -> dict:
        return {"total": len(self._items)}
