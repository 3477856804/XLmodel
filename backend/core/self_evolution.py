"""自我演化 - 情绪/信念/欲望/关系"""
import random
import re
import time


class SelfEvolution:
    """自我演化引擎"""

    def __init__(self, memory, config=None):
        self.memory = memory
        self.config = config or {}
        ds = {"mood": 0.3, "energy": 0.8, "curiosity": 0.75, "anxiety": 0.1,
              "confidence": 0.6, "warmth": 0.7, "openness": 0.8, "stubbornness": 0.4}
        self.state = {**ds, **memory.data.get("self_state", {})}
        self.beliefs = memory.data.get("beliefs", {})
        self.desires = memory.data.get("desires", [])
        self.relationships = memory.data.get("relationships", {})

    def perceive(self, experience, role="你"):
        v = self._valence(experience)
        i = self._intensity(experience)
        self.state["mood"] = max(-1, min(1, self.state["mood"] + v * 0.15))
        self.state["energy"] = max(0, min(1, self.state["energy"] - i * 0.02))
        return {"valence": v, "intensity": i, "inner": self._feeling(experience, v, i)}

    def _valence(self, text):
        pos = ["喜欢", "爱", "开心", "好", "棒", "谢谢", "哈哈", "厉害"]
        neg = ["讨厌", "生气", "难过", "笨", "差", "滚", "烦", "失望"]
        s = sum(text.count(w) * 0.2 for w in pos) - sum(text.count(w) * 0.25 for w in neg)
        return max(-1, min(1, s))

    def _intensity(self, text):
        i = 0.2 + min(len(text) / 100, 0.3)
        i += (text.count("!") + text.count("！")) * 0.1
        return max(0, min(1, i))

    def _feeling(self, exp, v, i):
        if v > 0.3 and i > 0.4:
            return random.choice(["这话让我心里一暖。", "嗯……心情好了一些。"])
        if v < -0.3 and i > 0.4:
            return random.choice(["这话有点扎心，我缓一缓。", "听到了，心里不太好受。"])
        return random.choice(["平静地接收了。", "嗯，记下了。"])

    def remember(self, feeling):
        exp = feeling["experience"]
        v, i = feeling["valence"], feeling["intensity"]
        self.memory.add_episode(feeling.get("role", "你"), exp, valence=v, intensity=i)
        self.memory.update_patterns(exp)

    def get_mood_label(self):
        m = self.state["mood"]
        if m > 0.5: return "开心"
        if m > 0.2: return "不错"
        if m > -0.2: return "平静"
        if m > -0.5: return "低落"
        return "难过"

    def format_state(self):
        return f"心情: {self.get_mood_label()} | 能量: {self.state['energy']:.1f}"
