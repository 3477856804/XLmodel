"""关系亲密度系统 - 从小透明到亲密无间"""
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict

from .platform import get_user_data_dir


class RelationshipLevel:
    STRANGER = "stranger"        # 陌生人 0-10
    FAMILIAR = "familiar"        # 熟悉 10-30
    FRIEND = "friend"            # 朋友 30-60
    CLOSE = "close"              # 亲密 60-90
    BONDED = "bonded"            # 羁绊 90-100

    LEVEL_NAMES = {
        STRANGER: "陌生人",
        FAMILIAR: "熟悉",
        FRIEND: "朋友",
        CLOSE: "亲密",
        BONDED: "羁绊",
    }


@dataclass
class Relationship:
    intimacy: float = 0.0       # 亲密度 0-100
    interactions: int = 0       # 互动次数
    last_interaction: float = 0  # 上次互动时间
    mood_bonus: float = 0.0     # 心情加成


class RelationshipEngine:
    """关系亲密度引擎"""

    def __init__(self):
        self.data_dir = get_user_data_dir() / "persona"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.file = self.data_dir / "relationship.json"
        self.rel = self._load()

    def _load(self) -> Relationship:
        if self.file.exists():
            try:
                data = json.loads(self.file.read_text(encoding="utf-8"))
                return Relationship(**data)
            except Exception:
                pass
        return Relationship()

    def _save(self):
        self.file.write_text(
            json.dumps(asdict(self.rel), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def interact(self, quality: float = 0.5):
        """一次互动，影响亲密度"""
        self.rel.interactions += 1
        self.rel.last_interaction = time.time()

        # 基础增长
        gain = quality * 2.0

        # 连续互动加成（每天第一次互动）
        if time.time() - self.rel.last_interaction > 86400:
            gain *= 1.5

        # 亲密度越高越难升
        difficulty = 1.0 - (self.rel.intimacy / 100.0) * 0.5
        gain *= difficulty

        self.rel.intimacy = min(100.0, self.rel.intimacy + gain)
        self._save()

    def get_level(self) -> str:
        if self.rel.intimacy < 10:
            return RelationshipLevel.STRANGER
        elif self.rel.intimacy < 30:
            return RelationshipLevel.FAMILIAR
        elif self.rel.intimacy < 60:
            return RelationshipLevel.FRIEND
        elif self.rel.intimacy < 90:
            return RelationshipLevel.CLOSE
        else:
            return RelationshipLevel.BONDED

    def get_level_name(self) -> str:
        return RelationshipLevel.LEVEL_NAMES[self.get_level()]

    def get_prompt_suffix(self) -> str:
        """关系对回复风格的影响"""
        suffixes = {
            RelationshipLevel.STRANGER: "（你们刚认识，小凌比较客气拘谨）",
            RelationshipLevel.FAMILIAR: "（你们有点熟了，小凌稍微放松了一些）",
            RelationshipLevel.FRIEND: "（你们是朋友，小凌语气自然亲切）",
            RelationshipLevel.CLOSE: "（你们关系很亲密，小凌像家人一样关心你）",
            RelationshipLevel.BONDED: "（你们有很深的羁绊，小凌非常在乎你）",
        }
        return suffixes[self.get_level()]

    def get_stats(self) -> dict:
        return {
            "intimacy": self.rel.intimacy,
            "level": self.get_level_name(),
            "interactions": self.rel.interactions,
        }
