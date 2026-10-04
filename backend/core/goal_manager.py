"""目标管理器 - 目标有生命周期，驱动agent持续执行直到完成"""
import time


class GoalManager:
    """目标管理器"""

    def __init__(self, memory=None):
        self.memory = memory
        self._path = "data/goals.json"
        self.goals = []
        self._load()

    def _load(self):
        import json, os
        try:
            os.makedirs("data", exist_ok=True)
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    self.goals = json.load(f)
        except Exception:
            self.goals = []

    def _save(self):
        import json
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self.goals, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def create(self, objective, max_rounds=20):
        goal = {
            "id": f"goal_{int(time.time()*1000)}",
            "objective": objective,
            "phase": "active",
            "rounds_started": 0,
            "max_rounds": max_rounds,
            "created_at": time.time(),
            "updated_at": time.time(),
            "blocked_reason": None,
            "history": [],
        }
        self.goals.append(goal)
        self._save()
        return goal

    def get_active(self):
        for g in self.goals:
            if g["phase"] == "active":
                return g
        return None

    def advance_round(self, goal_id=None):
        goal = self._find(goal_id) or self.get_active()
        if not goal:
            return None
        goal["rounds_started"] += 1
        goal["updated_at"] = time.time()
        if goal["rounds_started"] >= goal["max_rounds"]:
            goal["phase"] = "blocked"
            goal["blocked_reason"] = "达到最大轮次限制"
        self._save()
        return goal

    def complete(self, goal_id=None):
        goal = self._find(goal_id) or self.get_active()
        if not goal:
            return None
        goal["phase"] = "complete"
        goal["updated_at"] = time.time()
        self._save()
        return goal

    def block(self, reason, goal_id=None):
        goal = self._find(goal_id) or self.get_active()
        if not goal:
            return None
        goal["phase"] = "blocked"
        goal["blocked_reason"] = reason
        self._save()
        return goal

    def list_goals(self):
        if not self.goals:
            return "无目标"
        out = ""
        for g in self.goals[-10:]:
            out += f"[{g['phase']}] {g['objective'][:60]} (轮次{g['rounds_started']}/{g['max_rounds']})\n"
        return out.strip()

    def _find(self, goal_id):
        if not goal_id:
            return None
        for g in self.goals:
            if g["id"] == goal_id:
                return g
        return None
