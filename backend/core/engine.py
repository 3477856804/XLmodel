"""小凌主引擎 - 整合所有模块"""
import time

from .memory import LongTermMemory
from .growth import GrowthEngine
from .model import ModelReplacement
from .session import SessionPersistence
from .multi_agent import MultiAgentSystem
from .knowledge import KnowledgeGraph
from .scheduler import CronScheduler
from .persona import EmotionEngine, RelationshipEngine
from .tools import ToolManager, SkillManager
from .goal_manager import GoalManager
from .guards import Guard, OfflineGuard
from .updater import UpdateChecker
from .plugin_manager import PluginManager


class XiaoLing:
    """小凌主引擎"""

    def __init__(self):
        print("=" * 55)
        print("  小凌 v0.0.1 启动中")
        print("=" * 55)

        # 记忆
        self.memory = LongTermMemory("data/memory.json")
        self.last_active = time.time()

        # 成长
        self.growth = GrowthEngine()
        try:
            _st = self.growth.status()
            print(f"  [成长] 进度 {_st.get('progress_percent', 0):.1f}%")
        except Exception as e:                                       # noqa: BLE001
            print(f"  [成长] 状态读取跳过：{e}")

        # 模型替换
        self.model_replace = ModelReplacement()
        print(f"  [模型] {self.model_replace.status_text()}")

        # 会话持久化
        self.session = SessionPersistence(self)

        # 多 Agent
        self.multiagent = MultiAgentSystem(self)

        # 知识图谱
        self.kg = KnowledgeGraph()

        # 定时任务
        self.cron = CronScheduler(self)

        # 人格
        self.emotion = EmotionEngine()
        self.relationship = RelationshipEngine()
        print(f"  [人格] 情绪{self.emotion.get_emotion_label()}")

        # 工具
        self.tools = ToolManager()
        print(f"  [工具] {len(self.tools.tools)}个已加载")

        # 技能
        self.skills = SkillManager("skills", self.tools)

        # 目标
        self.goals = GoalManager(self.memory)

        # 守卫
        self.guard = Guard()

        # 自动更新
        self.updater = UpdateChecker()

        # 离线守卫
        self.network = OfflineGuard()

        # 插件系统
        self.plugins = PluginManager()
        print(f"  [插件] {len(self.plugins.list_plugins())}个已加载")

        # 模型（懒加载）
        self.model = None
        self._model_loading = False

        self.conversation = []
        self.interaction_count = 0

        print("=" * 55)
        print("  小凌已就绪。")

    def chat(self, text):
        """聊天接口"""
        self.session.append_turn(text, "")

        # 插件钩子：聊天前
        self.plugins.emit("before_chat", text)

        # 优先用真实模型
        reply = None
        try:
            reply = self.model_replace.chat(text)
        except Exception as e:                                           # noqa: BLE001
            print(f"  [模型] 推理失败: {e}")
            reply = None

        # 模型不可用时兜底
        if not reply:
            reply = f"你说的是：{text}"

        # 插件钩子：聊天后（插件可改写回复）
        try:
            reply = self.plugins.process_message(reply) or reply
        except Exception:                                           # noqa: BLE001
            pass

        self.session.append_turn(text, reply)
        self.interaction_count += 1
        return reply, None

    def show_status(self):
        return f"小凌 v0.0.1 | 情绪: {self.emotion.get_emotion_label()}"
