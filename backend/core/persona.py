"""人格系统 - 情绪状态机 + 关系亲密度"""
import random
from dataclasses import dataclass
from enum import Enum


# ===== 情绪 =====
class Emotion(Enum):
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    SCARED = "scared"
    DISGUSTED = "disgusted"
    NEUTRAL = "neutral"


@dataclass
class EmotionState:
    emotion: Emotion = Emotion.NEUTRAL
    intensity: float = 0.5
    duration: int = 0


class EmotionEngine:
    """情绪状态机"""

    TRANSITIONS = {
        Emotion.HAPPY: {Emotion.HAPPY: 0.6, Emotion.NEUTRAL: 0.2, Emotion.SURPRISED: 0.1, Emotion.SAD: 0.1},
        Emotion.SAD: {Emotion.SAD: 0.5, Emotion.NEUTRAL: 0.3, Emotion.ANGRY: 0.1, Emotion.HAPPY: 0.1},
        Emotion.ANGRY: {Emotion.ANGRY: 0.4, Emotion.NEUTRAL: 0.4, Emotion.HAPPY: 0.1, Emotion.SAD: 0.1},
        Emotion.SURPRISED: {Emotion.SURPRISED: 0.3, Emotion.NEUTRAL: 0.4, Emotion.HAPPY: 0.2, Emotion.SCARED: 0.1},
        Emotion.NEUTRAL: {Emotion.NEUTRAL: 0.5, Emotion.HAPPY: 0.2, Emotion.SAD: 0.1, Emotion.SURPRISED: 0.2},
    }

    def __init__(self):
        self.state = EmotionState()

    def update(self, user_input: str, quality: float = 0.5):
        positive = ["喜欢", "爱", "好", "棒", "开心", "谢谢", "哈哈", "可爱"]
        negative = ["讨厌", "烦", "笨", "蠢", "滚", "生气", "差"]
        pos = sum(1 for w in positive if w in user_input)
        neg = sum(1 for w in negative if w in user_input)
        if quality > 0.7: pos += 1
        elif quality < 0.3: neg += 1

        if pos > neg:
            self._shift(Emotion.HAPPY, 0.6 + pos * 0.1)
        elif neg > pos:
            self._shift(Emotion.ANGRY, 0.5 + neg * 0.1)
        else:
            self._random_shift()

        self.state.duration += 1
        if self.state.duration > 5:
            self._shift(Emotion.NEUTRAL, 0.3)

    def _shift(self, e: Emotion, i: float):
        self.state.emotion = e
        self.state.intensity = min(1.0, i)
        self.state.duration = 0

    def _random_shift(self):
        w = self.TRANSITIONS.get(self.state.emotion, self.TRANSITIONS[Emotion.NEUTRAL])
        self.state.emotion = random.choices(list(w.keys()), weights=list(w.values()))[0]
        self.state.duration = 0

    def get_emotion_label(self) -> str:
        labels = {Emotion.HAPPY: "开心", Emotion.SAD: "难过", Emotion.ANGRY: "生气",
                  Emotion.SURPRISED: "惊讶", Emotion.SCARED: "害怕",
                  Emotion.DISGUSTED: "厌恶", Emotion.NEUTRAL: "平静"}
        return labels[self.state.emotion]

    def get_prompt_suffix(self) -> str:
        s = {Emotion.HAPPY: "（小凌现在心情很好，语气轻快活泼）",
             Emotion.SAD: "（小凌有点难过，语气温柔低落）",
             Emotion.ANGRY: "（小凌有点生气，语气带点小脾气）",
             Emotion.SURPRISED: "（小凌很惊讶，语气意外）",
             Emotion.SCARED: "（小凌有点害怕，语气小心翼翼）",
             Emotion.NEUTRAL: "（小凌心情平静，正常语气）"}
        return s[self.state.emotion]


# ===== 关系 =====
class RelationshipLevel(Enum):
    STRANGER = "stranger"       # 陌生人
    FAMILIAR = "familiar"       # 认识
    FRIEND = "friend"           # 朋友
    CLOSE = "close"             # 亲密
    BONDED = "bonded"           # 羁绊


LEVEL_CONFIG = {
    RelationshipLevel.STRANGER: {"threshold": 0, "label": "陌生人", "style": "礼貌客气，保持距离"},
    RelationshipLevel.FAMILIAR: {"threshold": 10, "label": "认识", "style": "稍微熟一点，语气放松"},
    RelationshipLevel.FRIEND: {"threshold": 30, "label": "朋友", "style": "像朋友一样聊天，可以开玩笑"},
    RelationshipLevel.CLOSE: {"threshold": 60, "label": "亲密", "style": "很亲近，可以撒娇"},
    RelationshipLevel.BONDED: {"threshold": 100, "label": "羁绊", "style": "非常亲密，完全信任"},
}


class RelationshipEngine:
    """关系亲密度"""

    def __init__(self):
        self.score = 0
        self.level = RelationshipLevel.STRANGER

    def interact(self, quality: float = 0.5):
        """每次互动增加亲密度"""
        if quality > 0.7:
            self.score += 2
        elif quality > 0.3:
            self.score += 1
        else:
            self.score -= 0.5
        self.score = max(0, self.score)
        self._update_level()

    def _update_level(self):
        for level, cfg in reversed(LEVEL_CONFIG.items()):
            if self.score >= cfg["threshold"]:
                self.level = level
                break

    def get_level_label(self) -> str:
        return LEVEL_CONFIG[self.level]["label"]

    def get_prompt_suffix(self) -> str:
        style = LEVEL_CONFIG[self.level]["style"]
        return f"（和用户的关系：{self.get_level_label()}，{style}）"
