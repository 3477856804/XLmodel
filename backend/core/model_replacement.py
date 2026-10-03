"""模型自我替换 - 训练成长 → 体积达标 → 自动替换基底"""
from pathlib import Path


class ModelReplacement:
    """模型自我替换管理器"""

    def __init__(self, model_dir=None, adapter_dir=None):
        self.model_dir = Path(model_dir) if model_dir else Path("models")
        self.adapter_dir = Path(adapter_dir) if adapter_dir else Path("adapters")
        self.replaced = False
        self.base_size = 0
        self.adapter_size = 0

    def check_and_replace(self, app=None, force=False):
        """检查适配器体积是否≥基底，是则自动替换"""
        if self.replaced:
            return ("self_research", "小凌已是纯自研模型")
        if self.base_size == 0:
            return ("no_base", "基底模型为空")
        if self.adapter_size >= self.base_size or force:
            return ("replaced", "模型自我替换成功")
        return ("growing", f"成长中：{self.adapter_size/1e6:.1f}MB / {self.base_size/1e6:.1f}MB")

    def status_text(self):
        if self.replaced:
            return "自研模型（已脱离基底）"
        return f"成长中：{self.adapter_size/1e6:.1f}MB / {self.base_size/1e6:.1f}MB"
