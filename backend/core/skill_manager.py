"""技能管理器 - 扫描skills/目录，动态加载工具和提示词"""
import re
from pathlib import Path


class SkillManager:
    """技能管理器"""

    def __init__(self, skills_dir, tool_manager=None, memory=None):
        self.skills_dir = Path(skills_dir)
        self.tool_manager = tool_manager
        self.memory = memory
        self.skills = {}
        self.system_prompts = []
        self.load_all()

    def load_all(self):
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for md_file in sorted(self.skills_dir.glob("*.md")):
            if self.load_skill(md_file):
                count += 1
        return count

    def load_skill(self, md_path):
        try:
            content = Path(md_path).read_text(encoding="utf-8")
            name = md_path.stem
            m = re.search(r'^#\s*(.+)$', content, re.MULTILINE)
            desc = m.group(1).strip() if m else name
            self.skills[name] = {
                "name": name,
                "description": desc,
                "file": str(md_path),
                "enabled": True,
            }
            return True
        except Exception as e:
            print(f"  [技能] 加载失败 {md_path}: {e}")
            return False

    def list_skills(self):
        return list(self.skills.keys())

    def get_skill(self, name):
        return self.skills.get(name)
