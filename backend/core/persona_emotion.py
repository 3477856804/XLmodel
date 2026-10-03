"""情绪状态机 - 小凌的情绪变化"""
import random
from dataclasses import dataclass
from enum import Enum


class Emotion(Enum):
    HAPPY = "happy"           # 开心
    SAD = "sad"               # 难过
    ANGRY = "angry"           # 生气
    SURPRISED = "surprised"   # 惊讶
    SCARED = "scared"         # 害怕
    DISGUSTED = "disgusted"  # 厌恶
    NEUTRAL = "neutral"       # 平静


@dataclass
class EmotionState:
    emotion: Emotion = Emotion.NEUTRAL
    intensity: float = 0.5  # 0~1
    duration: int = 0       # 持续轮数


class EmotionEngine:
    """情绪状态机"""

    # 情绪转换权重
    TRANSITIONS = {
        Emotion.HAPPY: {
            Emotion.HAPPY: 0.6, Emotion.NEUTRAL: 0.2,
            Emotion.SURPRISED: 0.1, Emotion.SAD: 0.1,
        },
        Emotion.SAD: {
            Emotion.SAD: 0.5, Emotion.NEUTRAL: 0.3,
            Emotion.ANGRY: 0.1, Emotion.HAPPY: 0.1,
        },
        Emotion.ANGRY: {
            Emotion.ANGRY: 0.4, Emotion.NEUTRAL: 0.4,
            Emotion.HAPPY: 0.1, Emotion.SAD: 0.1,
        },
        Emotion.SURPRISED: {
            Emotion.SURPRISED: 0.3, Emotion.NEUTRAL: 0.4,
            Emotion.HAPPY: 0.2, Emotion.SCARED: 0.1,
        },
        Emotion.NEUTRAL: {
            Emotion.NEUTRAL: 0.5, Emotion.HAPPY: 0.2,
            Emotion.SAD: 0.1, Emotion.SURPRISED: 0.2,
        },
    }

    def __init__(self):
        self.state = EmotionState()

    def update(self, user_input: str, interaction_quality: float = 0.5):
        """根据用户输入和互动质量更新情绪"""
        # 正面词
        positive_words = ["喜欢", "爱", "好", "棒", "开心", "谢谢", "哈哈", "可爱"]
        # 负面词
        negative_words = ["讨厌", "烦", "笨", "蠢", "滚", "生气", "差"]

        pos_score = sum(1 for w in positive_words if w in user_input)
        neg_score = sum(1 for w in negative_words if w in user_input)

        # 互动质量影响
        if interaction_quality > 0.7:
            pos_score += 1
        elif interaction_quality < 0.3:
            neg_score += 1

        # 情绪变化
        if pos_score > neg_score:
            self._shift_to(Emotion.HAPPY, 0.6 + pos_score * 0.1)
        elif neg_score > pos_score:
            self._shift_to(Emotion.ANGRY, 0.5 + neg_score * 0.1)
        else:
            # 随机转移
            self._random_shift()

        self.state.duration += 1
        # 持续太久就回到平静
        if self.state.duration > 5:
            self._shift_to(Emotion.NEUTRAL, 0.3)

    def _shift_to(self, emotion: Emotion, intensity: float):
        self.state.emotion = emotion
        self.state.intensity = min(1.0, intensity)
        self.state.duration = 0

    def _random_shift(self):
        weights = self.TRANSITIONS.get(self.state.emotion,
                                        self.TRANSITIONS[Emotion.NEUTRAL])
        emotions = list(weights.keys())
        probs = list(weights.values())
        self.state.emotion = random.choices(emotions, weights=probs)[0]
        self.state.duration = 0

    def get_emotion_label(self) -> str:
        labels = {
            Emotion.HAPPY: "开心",
            Emotion.SAD: "难过",
            Emotion.ANGRY: "生气",
            Emotion.SURPRISED: "惊讶",
            Emotion.SCARED: "害怕",
            Emotion.DISGUSTED: "厌恶",
            Emotion.NEUTRAL: "平静",
        }
        return labels[self.state.emotion]

    def get_prompt_suffix(self) -> str:
        """情绪对回复风格的影响"""
        suffixes = {
            Emotion.HAPPY: "（小凌现在心情很好，语气轻快活泼）",
            Emotion.SAD: "（小凌有点难过，语气温柔低落）",
            Emotion.ANGRY: "（小凌有点生气，语气带点小脾气）",
            Emotion.SURPRISED: "（小凌很惊讶，语气意外）",
            Emotion.SCARED: "（小凌有点害怕，语气小心翼翼）",
            Emotion.NEUTRAL: "（小凌心情平静，正常语气）",
        }
        return suffixes[self.state.emotion]
