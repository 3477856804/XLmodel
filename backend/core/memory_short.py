"""短期工作记忆 - 最近 N 轮对话"""
from collections import deque
from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class MemoryItem:
    role: str           # user / assistant
    content: str
    timestamp: float
    importance: float = 0.5  # 0~1


class ShortTermMemory:
    """短期工作记忆，保存最近 N 轮对话"""

    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._items: deque[MemoryItem] = deque(maxlen=max_size)

    def add(self, role: str, content: str, importance: float = 0.5):
        self._items.append(MemoryItem(
            role=role,
            content=content,
            timestamp=time.time(),
            importance=importance,
        ))

    def get_recent(self, n: Optional[int] = None) -> list[MemoryItem]:
        if n is None:
            return list(self._items)
        return list(self._items)[-n:]

    def to_prompt(self) -> str:
        """格式化为 prompt 上下文"""
        lines = []
        for item in self._items:
            role_name = "用户" if item.role == "user" else "小凌"
            lines.append(f"{role_name}: {item.content}")
        return "\n".join(lines)

    def clear(self):
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
