"""成长管理器 - 知识持续积累 + 体积增长"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

from .paths import DATA_DIR

GROWTH_DIR = DATA_DIR / "growth"
GROWTH_INDEX = GROWTH_DIR / "index.jsonl"
GROWTH_LOG = GROWTH_DIR / "growth.log"


class GrowthManager:
    """成长管理器"""

    def __init__(self):
        self.dir = GROWTH_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.total_items = 0
        self.total_bytes = 0
        self._load_stats()

    def _load_stats(self):
        try:
            if GROWTH_INDEX.exists():
                with open(GROWTH_INDEX, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            self.total_items += 1
            for p in self.dir.rglob("*"):
                if p.is_file():
                    self.total_bytes += p.stat().st_size
        except Exception:
            pass

    def absorb(self, source, content, tags=None):
        """吸收一条知识"""
        try:
            entry = {
                "time": time.time(),
                "source": source,
                "content": content[:2000],
                "tags": tags or [],
            }
            with open(GROWTH_INDEX, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self.total_items += 1
            self.total_bytes += len(entry["content"])
            return True
        except Exception as e:
            print(f"  [成长] 吸收失败: {e}")
            return False

    def get_size(self):
        if self.total_bytes < 1024:
            return f"{self.total_bytes} B"
        if self.total_bytes < 1024 * 1024:
            return f"{self.total_bytes/1024:.1f} KB"
        return f"{self.total_bytes/1024/1024:.2f} MB"

    def recall(self, query, n=5):
        """从成长包检索相关知识"""
        results = []
        try:
            if GROWTH_INDEX.exists():
                with open(GROWTH_INDEX, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            text = entry.get("content", "").lower()
                            score = 0
                            for w in self._keywords(query):
                                if w in text:
                                    score += text.count(w) * 2
                            if score > 0:
                                results.append((score, entry))
                        except Exception:
                            continue
        except Exception:
            pass
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:n]

    def _keywords(self, text):
        kws = set()
        for w in re.findall(r'[a-zA-Z]{2,}', text):
            kws.add(w.lower())
        return kws

    def growth_report(self):
        return f"成长包：{self.total_items} 条知识 / {self.get_size()}"
