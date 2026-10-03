"""工具系统 - 工具管理器 + 技能管理器"""
import time
import re
from pathlib import Path


# ===== 工具管理器 =====
class ToolManager:
    """工具管理器 - 注册/执行/缓存工具"""

    CORE_TOOLS = {"get_time", "read_file", "write_file", "list_dir", "calculator", "remember", "recall"}
    WRITE_TOOLS = {"write_file", "str_replace", "run_cmd", "pip_install"}
    CACHEABLE_TOOLS = {"get_time", "calculator", "list_dir", "read_file"}

    def __init__(self, base_dir=None, memory=None):
        self.base_dir = Path(base_dir) if base_dir else Path(".")
        self.memory = memory
        self.tools = {}
        self.before_hooks = []
        self.after_hooks = []
        self._tool_cache = {}
        self._tool_cache_ttl = 60.0
        self._register()

    def register(self, name, func, desc):
        self.tools[name] = {"func": func, "desc": desc}

    def add_before_hook(self, hook):
        self.before_hooks.append(hook)

    def add_after_hook(self, hook):
        self.after_hooks.append(hook)

    def execute(self, name, args):
        """执行工具"""
        if name not in self.tools:
            return f"未知工具：{name}"
        cur_args = dict(args) if isinstance(args, dict) else {}
        try:
            result = str(self.tools[name]["func"](**cur_args))
        except Exception as e:
            result = f"工具出错：{e}"
        return result

    def _register(self):
        self.register("get_time", lambda **kw: time.strftime("%Y-%m-%d %H:%M:%S"), "获取当前时间")
        self.register("calculator", lambda expr="", **kw: eval(expr, {"__builtins__": {}}, {}), "计算器")

    def tool_list_text(self):
        return "可用工具：" + ", ".join(self.tools.keys())


# ===== 技能管理器 =====
class SkillManager:
    """技能管理器 - 扫描skills/目录，动态加载技能"""

    def __init__(self, skills_dir, tool_manager=None, memory=None):
        self.skills_dir = Path(skills_dir)
        self.tool_manager = tool_manager
        self.memory = memory
        self.skills = {}
        self.load_all()

    def load_all(self):
        """加载所有技能"""
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for md_file in sorted(self.skills_dir.glob("*.md")):
            if self.load_skill(md_file):
                count += 1
        return count

    def load_skill(self, md_path):
        """加载单个技能"""
        try:
            content = Path(md_path).read_text(encoding="utf-8")
            name = md_path.stem
            m = re.search(r'^#\s*(.+)$', content, re.MULTILINE)
            desc = m.group(1).strip() if m else name
            self.skills[name] = {"name": name, "description": desc, "file": str(md_path)}
            return True
        except Exception as e:
            print(f"  [技能] 加载失败 {md_path}: {e}")
            return False

    def list_skills(self):
        return list(self.skills.keys())
