"""小凌主引擎 - 整合所有模块"""
import time

from .long_term_memory import LongTermMemory
from .growth_manager import GrowthManager
from .model_replacement import ModelReplacement
from .session import SessionPersistence
from .multi_agent import MultiAgentSystem
from .knowledge_graph import KnowledgeGraph
from .scheduler import CronScheduler
from .self_evolution import SelfEvolution
from .tool_manager import ToolManager
from .skill_manager import SkillManager
from .goal_manager import GoalManager
from .guard import Guard
from .updater import UpdateChecker
from .platform_adapter import PlatformAdapter
from .offline_guard import OfflineGuard


class XiaoLing:
    """小凌主引擎"""

    def __init__(self):
        print("=" * 55)
        print("  小凌 v0.0.1 启动中")
        print("=" * 55)

        # 记忆
        self.memory = LongTermMemory("data/memory.json")
        self.memory.data["last_active"] = time.time()

        # 成长
        self.growth = GrowthManager()
        print(f"  [成长] 已积累{self.growth.total_items}条知识")

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

        # 自我演化
        self.evo = SelfEvolution(self.memory)
        print(f"  [自我] 心情{self.evo.state['mood']:+.2f}")

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

        # 平台
        self.platforms = PlatformAdapter(self)

        # 离线守卫
        self.network = OfflineGuard()

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
        reply = f"你说的是：{text}"
        self.session.append_turn(text, reply)
        return reply, None

    def show_status(self):
        return f"小凌 v0.0.1 | {self.evo.format_state()}"
