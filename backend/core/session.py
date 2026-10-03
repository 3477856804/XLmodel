"""会话持久化 - 超长上下文 + 断电恢复"""
import json
import time
from datetime import datetime
from pathlib import Path

from .paths import DATA_DIR

SESSION_HISTORY = DATA_DIR / "session_history.jsonl"
SESSION_CHECKPOINT = DATA_DIR / "session_checkpoint.json"


class SessionPersistence:
    """会话持久化管理器"""

    def __init__(self, app=None):
        self.app = app
        self.last_checkpoint_turn = 0
        self._saved_turns = 0

    def append_turn(self, user, reply, tool_calls=None):
        """每轮对话实时写入磁盘"""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            entry = {
                "time": time.time(),
                "datetime": datetime.now().isoformat(),
                "user": user,
                "reply": reply[:500],
                "tool_calls": (tool_calls or [])[:5],
            }
            with open(SESSION_HISTORY, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._saved_turns += 1
        except Exception as e:
            print(f"  [持久化] 写入失败: {e}")

    def get_recent_history(self, n=10):
        """读取最近 n 轮历史"""
        try:
            if not SESSION_HISTORY.exists():
                return []
            with open(SESSION_HISTORY, "r", encoding="utf-8") as f:
                lines = f.readlines()
            out = []
            for line in lines[-n:]:
                try:
                    out.append(json.loads(line.strip()))
                except Exception:
                    continue
            return out
        except Exception:
            return []

    def save_checkpoint(self):
        """保存检查点"""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            checkpoint = {
                "time": time.time(),
                "datetime": datetime.now().isoformat(),
                "session_history_turns": self._saved_turns,
            }
            SESSION_CHECKPOINT.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=1), encoding="utf-8")
            return True
        except Exception as e:
            print(f"  [检查点] 保存失败: {e}")
            return False

    def load_checkpoint(self):
        """恢复检查点"""
        try:
            if not SESSION_CHECKPOINT.exists():
                return None
            return json.loads(SESSION_CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:
            return None
