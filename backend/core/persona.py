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